"""WebView shell for the ZMUX v1.0.0 core — Modular Python core + Oracle."""

import functools
from pathlib import Path
from typing import Any, Dict, Tuple, Union

from flask import Flask, jsonify, render_template, request
from waitress import serve

from zabacode.core.ai_provider import ALLOWED_PROVIDERS, PROVIDER_HANDLERS
from zabacode.core.checker import check_code
from zabacode.core.executor import (
    MAX_CODE_BYTES,
    MAX_INTERACTIVE_BYTES,
    PRELUDE_LINE_COUNT,
    execute_code_isolated,
    get_interactive_output,
    send_interactive_input,
    start_interactive_session,
    stop_interactive_session,
)
from zabacode.core.file_manager import delete_file, list_files, read_file, save_file
from zabacode.core.net import TLS_HELP_MESSAGE, ca_bundle_available
from zabacode.core.oracle import analyze_buffer, auto_fix_code, humanize_traceback, offline_reply
from zabacode.core.security import AUTH_TOKEN, load_keys, save_key, verify_token
from zabacode.core.zabapip import dispatch as dispatch_zpip
from zabacode.core.zabapip import runtime_fingerprint
from zabacode.lib_manager import get_all_libraries, install_library
from zabacode.plugins.implementations import PluginExecutor
from zabacode.plugins.registry import get_all_plugins
from zabacode.themes.definitions import get_theme, list_themes

APP_VERSION = "1.0.0"
MAX_AI_FIELD_CHARS = 100_000

BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "assets"),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


@app.after_request
def _security_headers(resp):
    """Lock the WebView down: no third-party origins, no framing, no sniffing."""
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'",
    )
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


def require_auth(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not verify_token(request.headers.get("X-ZMUX-Token", "")):
            return jsonify({"ok": False, "message": "Access denied: invalid authentication token."}), 401
        return func(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# JSON Validation Helper — Fix #23
# ---------------------------------------------------------------------------

def _get_json_payload() -> Tuple[Union[Dict[str, Any], None], Union[tuple[Any, int], None]]:
    """
    Parse and validate JSON body — must be an object, not array or primitive.
    Returns (payload_dict, error_response). If error_response is not None, return it.
    """
    data = request.get_json(silent=True)
    if data is None:
        # A body that was sent but could not be parsed must never be treated as
        # empty: that turns a client bug (e.g. a missing Content-Type header)
        # into a misleading "field is empty" reply. Fail loudly instead.
        if request.get_data(cache=True, as_text=True).strip():
            return None, (
                jsonify(
                    {
                        "ok": False,
                        "message": (
                            "Request body could not be parsed as JSON. "
                            "Send it with the header 'Content-Type: application/json'."
                        ),
                        "code": "invalid_json",
                    }
                ),
                400,
            )
        # Genuinely empty body — routes with defaults may proceed.
        return {}, None
    if not isinstance(data, dict):
        # JSON arrays or primitives are not allowed — previously treated as {} silently
        return None, (
            jsonify(
                {
                    "ok": False,
                    "message": "JSON body must be an object",
                    "code": "invalid_json_type",
                }
            ),
            400,
        )
    return data, None


def _validate_string_field(payload: dict, field: str, required: bool = False, max_len: int | None = None):
    """Validate a field is string if present, return error if not."""
    if field not in payload:
        if required:
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": f"Field '{field}' is required",
                        "code": "missing_field",
                    }
                ),
                400,
            )
        return None
    val = payload.get(field)
    if not isinstance(val, str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": f"Field '{field}' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    if max_len is not None and len(val) > max_len:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": f"Field '{field}' too large (max {max_len} chars)",
                    "code": "too_large",
                }
            ),
            413,
        )
    return None


@app.get("/")
def index():
    return render_template("index.html", auth_token=AUTH_TOKEN)


@app.get("/api/health")
def health_check():
    return jsonify(
        {"ok": True, "version": APP_VERSION, "providers": sorted(ALLOWED_PROVIDERS), "ui": "webview"}
    )


@app.post("/api/run")
@require_auth
def run_code():
    """Batch execution: run to completion, then return everything at once.

    Not what the RUN button uses — the editor drives ``/api/run/interactive/*``
    so that ``input()`` genuinely blocks and output streams live. This endpoint
    is the non-interactive counterpart, kept for automation, plugins and tests:

    * ``input()`` is stubbed by ``SAFE_INPUT_PATCH`` (returns ``""``) because
      nobody is there to type, which is why the reported traceback line needs
      ``line_offset=PRELUDE_LINE_COUNT`` below;
    * the whole run is bounded by a single 30 s timeout rather than the
      interactive session's idle/lifetime limits;
    * the response is one JSON blob (stdout, stderr, images, explain).

    The two paths deliberately do *not* share an execution flow — only the
    image capture in ``collect_new_images()`` is common.
    """
    payload, err = _get_json_payload()
    if err:
        return err

    # Validate code field must be string if present
    if "code" in payload and not isinstance(payload.get("code"), str):
        return (
            jsonify({"ok": False, "message": "Field 'code' must be a string", "code": "invalid_type"}),
            400,
        )
    if "stdin_data" in payload and not isinstance(payload.get("stdin_data"), str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'stdin_data' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )

    code = payload.get("code", "")
    stdin_data = payload.get("stdin_data", "")
    if not isinstance(code, str):
        return jsonify({"ok": False, "message": "Field 'code' must be a string."}), 400
    # Enforce size bound already in executor, but also early 413
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": f"Source too large: {len(code.encode('utf-8'))} bytes > {MAX_CODE_BYTES} limit",
                    "code": "too_large",
                }
            ),
            413,
        )

    result = execute_code_isolated(code, stdin_data=stdin_data)

    # Offline Oracle: explain the crash in plain language, no network needed.
    if not result.get("ok") and result.get("stderr"):
        explanation = humanize_traceback(result["stderr"], line_offset=PRELUDE_LINE_COUNT)
        if explanation.get("ok"):
            result["explain"] = explanation
    return jsonify(result)


# ---------------------------------------------------------------------------
# Interactive Execution & Check Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/run/interactive/start")
@require_auth
def run_interactive_start():
    payload, err = _get_json_payload()
    if err:
        return err

    code = payload.get("code", "")
    if not isinstance(code, str):
        return jsonify({"ok": False, "message": "Field 'code' must be a string."}), 400
    # Early 413 for oversized source — Fix #18
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": f"Source too large: {len(code.encode('utf-8'))} bytes > {MAX_CODE_BYTES} limit",
                    "code": "too_large",
                }
            ),
            413,
        )
    return jsonify(start_interactive_session(code))


@app.get("/api/run/interactive/output")
@require_auth
def run_interactive_output():
    return jsonify(get_interactive_output())


@app.post("/api/run/interactive/input")
@require_auth
def run_interactive_input():
    payload, err = _get_json_payload()
    if err:
        return err

    text = payload.get("text", "")
    if not isinstance(text, str):
        return jsonify({"ok": False, "message": "Field 'text' must be a string."}), 400
    # Bound input size
    if len(text.encode("utf-8")) > MAX_INTERACTIVE_BYTES:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Input too large (max 8KB)",
                    "code": "too_large",
                }
            ),
            413,
        )
    return jsonify(send_interactive_input(text))


@app.post("/api/run/interactive/stop")
@require_auth
def run_interactive_stop():
    return jsonify(stop_interactive_session())


@app.post("/api/check")
@require_auth
def check_code_endpoint():
    payload, err = _get_json_payload()
    if err:
        return err

    code = payload.get("code", "")
    if not isinstance(code, str):
        return jsonify({"ok": False, "message": "Field 'code' must be a string."}), 400
    return jsonify(check_code(code))


# ---------------------------------------------------------------------------
# Other Core Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/libraries")
@require_auth
def libraries():
    return jsonify(get_all_libraries())


@app.get("/api/runtime")
@require_auth
def runtime_report():
    """Export the actual running APK fingerprint for wheel compatibility."""
    return jsonify({"ok": True, "runtime": runtime_fingerprint()})


@app.post("/api/zpip")
@require_auth
def zpip_command():
    """Run a ZMUX zpip command through an allowlisted dispatcher, never a shell."""
    payload, err = _get_json_payload()
    if err:
        return err
    validation = _validate_string_field(payload, "command", required=True, max_len=256)
    if validation:
        return validation
    return jsonify(dispatch_zpip(payload["command"]))


@app.post("/api/libraries/install")
@require_auth
def install():
    payload, err = _get_json_payload()
    if err:
        return err

    # Fix #23: Validate 'name' must be string
    if "name" in payload and not isinstance(payload.get("name"), str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'name' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    return jsonify(install_library(payload.get("name", "")))


@app.get("/api/files")
@require_auth
def files():
    return jsonify({"files": list_files()})


@app.route("/api/files/<path:filename>", methods=["GET", "POST", "DELETE"])
@require_auth
def file_item(filename):
    if request.method == "GET":
        result = read_file(filename)
    elif request.method == "POST":
        payload, err = _get_json_payload()
        if err:
            return err
        if "content" in payload and not isinstance(payload.get("content"), str):
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "Field 'content' must be a string",
                        "code": "invalid_type",
                    }
                ),
                400,
            )
        result = save_file(filename, payload.get("content", ""))
    else:
        result = delete_file(filename)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.get("/api/themes")
def themes():
    return jsonify({"themes": list_themes()})


@app.get("/api/themes/<name>")
def theme(name):
    result = get_theme(name)
    if result is None:
        return jsonify({"ok": False, "message": "Theme not found"}), 404
    return jsonify({"ok": True, "theme": result})


@app.get("/api/tls/status")
def tls_status():
    """Report whether outbound HTTPS can verify certificates on this device."""
    ok = ca_bundle_available()
    return jsonify({"ok": ok, "message": "" if ok else TLS_HELP_MESSAGE})


@app.get("/api/marketplace/plugins")
def plugins():
    return jsonify({"ok": True, "plugins": get_all_plugins()})


@app.post("/api/plugins/execute")
@require_auth
def execute_plugin():
    payload, err = _get_json_payload()
    if err:
        return err

    plugin_id = payload.get("plugin_id", "")
    code = payload.get("code", "")
    if not isinstance(plugin_id, str) or not isinstance(code, str):
        return jsonify({"ok": False, "message": "Fields 'plugin_id' and 'code' must be strings."}), 400

    try:
        result = PluginExecutor.execute_plugin(plugin_id, code)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "message": f"Failed to execute plugin: {str(e)}"}), 500


@app.get("/api/keys/status")
@require_auth
def keys_status():
    keys = load_keys()
    return jsonify({provider: bool(keys.get(provider)) for provider in ALLOWED_PROVIDERS})


@app.post("/api/keys")
@require_auth
def set_key():
    payload, err = _get_json_payload()
    if err:
        return err

    # Fix #23: Validate provider and api_key are strings
    if "provider" in payload and not isinstance(payload.get("provider"), str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'provider' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    if "api_key" in payload and not isinstance(payload.get("api_key"), str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'api_key' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )

    provider = payload.get("provider", "")
    api_key = payload.get("api_key", "")
    if provider not in ALLOWED_PROVIDERS or not isinstance(api_key, str):
        return jsonify({"ok": False, "message": "Invalid provider or API key."}), 400
    save_key(provider, api_key)
    return jsonify({"ok": True})


@app.post("/api/ai/chat")
@require_auth
def ai_chat():
    payload, err = _get_json_payload()
    if err:
        return err

    provider = payload.get("provider", "openrouter")
    model = payload.get("model", "")
    message = payload.get("message", "")
    code = payload.get("code", "")

    # Fix #23 + #24: Strict validation for AI chat fields
    if not isinstance(provider, str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'provider' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    if not isinstance(model, str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'model' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    if not isinstance(message, str):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'message' must be a string",
                    "code": "invalid_type",
                }
            ),
            400,
        )
    if not isinstance(code, str):
        return (
            jsonify(
                {"ok": False, "message": "Field 'code' must be a string", "code": "invalid_type"}
            ),
            400,
        )

    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "message": "Invalid AI provider."}), 400
    if len(message) > MAX_AI_FIELD_CHARS or len(code) > MAX_AI_FIELD_CHARS:
        return jsonify({"ok": False, "message": "AI context is too large."}), 413

    # allow_offline should be bool if present
    allow_offline = payload.get("allow_offline", True)
    if not isinstance(allow_offline, bool):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Field 'allow_offline' must be a boolean",
                    "code": "invalid_type",
                }
            ),
            400,
        )

    # Fix #24: Separate Custom Endpoint URL validation, warn cleartext HTTP
    # For custom provider, we now support separate 'endpoint_url' field in addition to api_key
    # api_key may still be URL for backward compat, but we encourage endpoint_url
    endpoint_url = None
    if provider == "custom":
        # Accept both 'endpoint_url' and legacy 'api_key' as URL
        candidate = payload.get("endpoint_url") or payload.get("api_key") or ""
        if candidate:
            if not isinstance(candidate, str):
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "Field 'endpoint_url' must be a string URL",
                            "code": "invalid_type",
                        }
                    ),
                    400,
                )
            # Basic URL validation — must be http:// or https://
            if not (candidate.startswith("http://") or candidate.startswith("https://")):
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "Custom endpoint URL must start with http:// or https://",
                            "code": "invalid_url",
                        }
                    ),
                    400,
                )
            endpoint_url = candidate
            # Warn for cleartext HTTP — will be surfaced in UI, but also log
            if candidate.startswith("http://"):
                # Allow loopback/private network without hard fail, but warn
                # For now we allow but will include warning in response if needed
                pass

    api_key = load_keys().get(provider)
    # Ollama is offline-first (no key required)
    is_offline_provider = provider in ("ollama",)
    if not api_key and not is_offline_provider:
        # For custom, if endpoint_url provided in request payload, allow even if no saved key
        if provider == "custom" and endpoint_url:
            api_key = endpoint_url
        else:
            if allow_offline:
                fallback = offline_reply(message, code)
                fallback["fallback_reason"] = "no_api_key"
                return jsonify(fallback)
            return jsonify({"ok": False, "needs_key": True, "provider": provider}), 401
    # For offline providers, empty key is fine
    if not api_key:
        api_key = ""

    # If custom and endpoint_url provided in payload, override api_key with endpoint_url for this request
    if provider == "custom" and endpoint_url:
        api_key = endpoint_url

    result = PROVIDER_HANDLERS[provider](api_key, message, code, model=model)

    # Cloud unreachable (TLS, rate limit, airplane mode)? The Oracle still answers.
    if not result.get("ok") and allow_offline:
        fallback = offline_reply(message, code)
        fallback["fallback_reason"] = result.get("message", "provider_error")
        fallback["reply"] = (
            f"_{provider} unavailable — answering locally._\n\n" + fallback["reply"]
        )
        return jsonify(fallback)
    return jsonify(result)


@app.post("/api/oracle/explain")
@require_auth
def oracle_explain():
    """Explain a traceback in plain language. Works with zero network."""
    payload, err = _get_json_payload()
    if err:
        return err

    stderr = payload.get("stderr", "")
    if not isinstance(stderr, str):
        return jsonify({"ok": False, "message": "Field 'stderr' must be a string."}), 400
    return jsonify(humanize_traceback(stderr))


@app.post("/api/oracle/analyze")
@require_auth
def oracle_analyze():
    """Static AST analysis of the editor buffer. Works with zero network."""
    payload, err = _get_json_payload()
    if err:
        return err

    code = payload.get("code", "")
    if not isinstance(code, str):
        return jsonify({"ok": False, "message": "Field 'code' must be a string."}), 400
    return jsonify(analyze_buffer(code))

@app.post("/api/oracle/fix")
@require_auth
def oracle_fix():
    """Automatically patch code based on syntax error/traceback. Works offline."""
    payload, err = _get_json_payload()
    if err:
        return err

    code = payload.get("code", "")
    stderr = payload.get("stderr", "")
    if not isinstance(code, str):
        return jsonify({"ok": False, "message": "Field 'code' must be a string."}), 400
    if not isinstance(stderr, str):
        return jsonify({"ok": False, "message": "Field 'stderr' must be a string."}), 400

    return jsonify(auto_fix_code(code, stderr))


def run_webview_server():
    """Run WebView server with port conflict detection (Fix #27)."""
    import socket

    # Try ports 5000-5010 to handle collision/denial-of-service on fixed port
    for port in range(5000, 5011):
        try:
            # Quick check if port is available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                # If bind succeeds, port is free, close and let Waitress use it
        except OSError as e:
            print(f"[WARN] Port {port} occupied ({e}), trying next...")
            continue

        try:
            print(f"[INFO] Starting ZMUX WebView server on 127.0.0.1:{port}")
            print("[INFO] Loopback-only: exposure reduction, not full app-private boundary (see SECURITY.md #27)")
            print("[INFO] Token delivery: AUTH_TOKEN embedded in root HTML JS, validated via constant-time compare, sensitive routes require X-ZMUX-Token")
            serve(app, host="127.0.0.1", port=port, threads=4)
            break
        except OSError as e:
            print(f"[WARN] Failed to start on port {port}: {e}, trying next...")
            if port == 5010:
                print("[ERROR] All ports 5000-5010 occupied. Clear recovery: check other ZMUX instances or run `lsof -i :5000` / `netstat -tulpn` and kill conflicting process.")
                raise
            continue
