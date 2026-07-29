"""
ZMUX Terminal Server — Flask WebView backend.

Provides REST API for terminal operations and serves the terminal UI.
Loopback-only: 127.0.0.1 for WebView consumption.
"""

import functools
import socket
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from waitress import serve

from zmux.security import AUTH_TOKEN, verify_token
from zmux.terminal import get_session
from zmux import zpip

APP_VERSION = "1.0.0"
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
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        f"connect-src 'self' ws://127.0.0.1:{ws_port} ws://localhost:{ws_port}; "
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
            return jsonify({"ok": False, "message": "Access denied"}), 401
        return func(*args, **kwargs)

    return wrapped


def _get_json_payload():
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data(cache=True, as_text=True).strip():
            return None, jsonify({"ok": False, "message": "Invalid JSON", "code": "invalid_json"}), 400
        return {}, None
    if not isinstance(data, dict):
        return None, jsonify({"ok": False, "message": "JSON must be object", "code": "invalid_json_type"}), 400
    return data, None


ws_port = 5001

@app.get("/")
def index():
    return render_template("terminal.html", auth_token=AUTH_TOKEN, ws_port=ws_port)


@app.get("/api/health")
def health_check():
    session = get_session()
    return jsonify({"ok": True, "version": APP_VERSION, "app": "ZMUX", "type": "terminal", "status": session.status})


def _format_zpip_output(command, result):
    """Turn a structured zpip result into terminal-friendly text."""
    parts = command.strip().split()
    action = parts[1] if len(parts) > 1 else ""

    if action == "verify":
        pkg = result.get("package", parts[2] if len(parts) > 2 else "")
        if result.get("ok"):
            return f"{pkg} is installed and verified", 0
        missing = result.get("missing", [])
        if missing:
            return f"{pkg} verification failed: missing files: {', '.join(missing)}", 1
        error = result.get("error", "unknown error")
        return f"{pkg} verification failed: {error}", 1

    if action == "doctor" and "runtime" in result:
        rt = result.get("runtime", {})
        free = result.get("free_bytes", 0)
        pkgs = result.get("packages", {})
        idx = result.get("index", "unknown")
        lines = [
            "ZMUX Package Manager",
            f"Runtime: {rt.get('runtime_id', 'unknown')}",
            f"Python: {rt.get('python', {}).get('version', 'unknown')}",
            f"ABI: {rt.get('android', {}).get('abi', 'unknown')}",
            f"User packages: {rt.get('paths', {}).get('user_packages', 'unknown')}",
            f"Free storage: {free:,} bytes",
            f"Index: {idx}",
        ]
        if pkgs:
            lines.extend(("", "Installed packages:"))
            for name, status in pkgs.items():
                lines.append(f"  {name}: {'OK' if status.get('ok') else 'FAILED'}")
        return "\n".join(lines), 0 if result.get("ok") else 1

    if not result.get("ok"):
        return f"Error: {result.get('error', 'unknown error')}", 1

    if action == "install":
        pkg = result.get("package", "")
        ver = result.get("version", "")
        deps = result.get("dependencies_installed", [])
        msg = f"Successfully installed {pkg}{f'-{ver}' if ver else ''}"
        if deps:
            msg += f"\nAlso installed: {', '.join(deps)}"
        return msg, 0
    if action == "list":
        pkgs = result.get("packages", {})
        if pkgs:
            return "\n".join(
                f"{name} {record.get('version', '')}" for name, record in pkgs.items()
            ), 0
        return "No packages installed", 0
    if action == "search":
        results = result.get("results", [])
        return "\n".join(results) if results else "No packages found", 0
    if action == "info":
        pkg = result.get("name", "")
        installed = result.get("installed")
        available = result.get("available")
        lines = [f"Package: {pkg}"]
        if installed:
            lines.append(f"Installed: {installed.get('version', 'unknown')}")
        if available:
            lines.append(f"Available: {available.get('version', 'unknown')}")
        return "\n".join(lines), 0
    if action == "uninstall":
        return f"Successfully uninstalled {result.get('package', '')}", 0
    return "Command executed successfully", 0


@app.post("/api/exec")
@require_auth
def exec_command():
    payload, err = _get_json_payload()
    if err:
        return err
    command = payload.get("command", "")
    if not isinstance(command, str):
        return jsonify({"ok": False, "message": "Field 'command' must be a string"}), 400
    if command.strip().startswith("zpip"):
        result = zpip.dispatch(command)
        output, exit_code = _format_zpip_output(command, result)
        return jsonify(
            {
                "ok": exit_code == 0,
                "stdout": output + "\n",
                "stderr": "",
                "exit_code": exit_code,
                "status": "idle",
                "prompt": get_session().get_prompt(),
            }
        )
    if command.strip() == "zmux-info":
        fp = zpip.runtime_fingerprint()
        lines = ["ZMUX Runtime Fingerprint", "=" * 40, f"App version:        {fp['app_version']}", f"Python version:     {fp['python']['version']}", f"Implementation:     {fp['python']['implementation']}", f"SOABI:              {fp['python']['soabi']}", f"EXT_SUFFIX:         {fp['python']['ext_suffix']}", f"Pointer bits:       {fp['python']['pointer_bits']}", f"ABI:                {fp['android']['abi']}", f"Android API:        {fp['android']['api']}", f"Runtime ID:         {fp['runtime_id']}", f"p4a commit:         {fp['build_contract']['p4a_commit']}", f"NDK:                {fp['build_contract']['ndk']}", f"CWD:                {fp['paths']['cwd']}", f"User packages:      {fp['paths']['user_packages']}", f"Free storage:       {fp['storage']['free_bytes']:,} bytes"]
        installed = fp['installed']
        if installed:
            lines.append(f"Installed packages: {', '.join(installed)}")
        else:
            lines.append("Installed packages: (none)")
        return jsonify(
            {
                "ok": True,
                "stdout": "\n".join(lines) + "\n",
                "stderr": "",
                "exit_code": 0,
                "status": "idle",
                "prompt": get_session().get_prompt(),
            }
        )
    session = get_session()
    timeout = payload.get("timeout")
    if timeout is not None:
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": "timeout must be a number"}), 400
    result = session.execute(command, timeout=timeout)
    result["prompt"] = session.get_prompt()
    return jsonify(result)


@app.post("/api/input")
@require_auth
def send_input():
    payload, err = _get_json_payload()
    if err:
        return err
    text = payload.get("text", "")
    if not isinstance(text, str):
        return jsonify({"ok": False, "message": "Field 'text' must be a string"}), 400
    session = get_session()
    result = session.send_input(text)
    return jsonify(result)


@app.post("/api/stop")
@require_auth
def stop_process():
    session = get_session()
    result = session.stop()
    result["prompt"] = session.get_prompt()
    return jsonify(result)


@app.get("/api/status")
@require_auth
def get_status():
    session = get_session()
    return jsonify({"ok": True, "status": session.status, "exit_code": session.exit_code, "cwd": str(session.cwd), "prompt": session.get_prompt()})


@app.get("/api/prompt")
@require_auth
def get_prompt():
    session = get_session()
    return jsonify({"ok": True, "prompt": session.get_prompt()})


def run_server():
    global ws_port
    for port in range(5000, 5011):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
        except OSError as e:
            print(f"[WARN] Port {port} occupied ({e}), trying next...")
            continue
        try:
            print(f"[INFO] Starting ZMUX Terminal server on 127.0.0.1:{port}")

            # Find a free port for the WebSocket server
            candidate_ws_port = port + 1
            while True:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ws_s:
                        ws_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        ws_s.bind(("127.0.0.1", candidate_ws_port))
                    break
                except OSError:
                    candidate_ws_port += 1

            ws_port = candidate_ws_port
            print(f"[INFO] Selected WebSocket Port: {ws_port}")

            # Start WebSocket and PTY servers
            from zmux.ws_server import WebSocketServer
            from zmux.pty_session import get_pty_session

            ws_server = WebSocketServer(host="127.0.0.1", port=ws_port)
            ws_server.start()

            pty_sess = get_pty_session(ws_server)
            pty_sess.start()

            serve(app, host="127.0.0.1", port=port, threads=4)
            break
        except OSError as e:
            print(f"[WARN] Failed to start on port {port}: {e}, trying next...")
            if port == 5010:
                print("[ERROR] All ports 5000-5010 occupied.")
                raise
            continue
