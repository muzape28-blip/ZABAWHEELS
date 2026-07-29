"""
ZMUX Terminal Server — Flask WebView backend.

Provides REST API for terminal operations and serves the terminal UI.
Loopback-only: 127.0.0.1 for WebView consumption.
"""

import functools
import json
import os
import socket
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from waitress import serve

from zmux.security import AUTH_TOKEN, verify_token
from zmux.terminal import get_session, ProcessStatus
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
    """Decorator to require valid auth token."""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not verify_token(request.headers.get("X-ZMUX-Token", "")):
            return jsonify({"ok": False, "message": "Access denied: invalid authentication token."}), 401
        return func(*args, **kwargs)
    return wrapped


def _get_json_payload():
    """Parse and validate JSON body."""
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data(cache=True, as_text=True).strip():
            return None, (
                jsonify({
                    "ok": False,
                    "message": "Request body could not be parsed as JSON.",
                    "code": "invalid_json",
                }),
                400,
            )
        return {}, None
    if not isinstance(data, dict):
        return None, (
            jsonify({
                "ok": False,
                "message": "JSON body must be an object",
                "code": "invalid_json_type",
            }),
            400,
        )
    return data, None


@app.get("/")
def index():
    """Serve the terminal UI."""
    return render_template("terminal.html", auth_token=AUTH_TOKEN)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    session = get_session()
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "app": "ZMUX",
        "type": "terminal",
        "status": session.status,
    })


@app.post("/api/exec")
@require_auth
def exec_command():
    """Execute a terminal command."""
    payload, err = _get_json_payload()
    if err:
        return err

    command = payload.get("command", "")
    if not isinstance(command, str):
        return jsonify({"ok": False, "message": "Field 'command' must be a string"}), 400

    # Handle zpip commands
    if command.strip().startswith("zpip"):
        result = zpip.dispatch(command)
        # Format zpip output for terminal
        if result.get("ok"):
            output = json.dumps(result, indent=2)
        else:
            output = f"Error: {result.get('error', 'unknown error')}"
        return jsonify({
            "ok": result.get("ok", False),
            "stdout": output + "\n",
            "stderr": "",
            "exit_code": 0 if result.get("ok") else 1,
            "status": "idle",
            "prompt": get_session().get_prompt(),
        })

    # Handle zmux-info command
    if command.strip() == "zmux-info":
        fp = zpip.runtime_fingerprint()
        lines = [
            f"ZMUX Runtime Fingerprint",
            f"{'='*40}",
            f"App version:        {fp['app_version']}",
            f"Python version:     {fp['python']['version']}",
            f"Implementation:     {fp['python']['implementation']}",
            f"SOABI:              {fp['python']['soabi']}",
            f"EXT_SUFFIX:         {fp['python']['ext_suffix']}",
            f"Pointer bits:       {fp['python']['pointer_bits']}",
            f"ABI:                {fp['android']['abi']}",
            f"Android API:        {fp['android']['api']}",
            f"Runtime ID:         {fp['runtime_id']}",
            f"p4a commit:         {fp['build_contract']['p4a_commit']}",
            f"NDK:                {fp['build_contract']['ndk']}",
            f"CWD:                {fp['paths']['cwd']}",
            f"User packages:      {fp['paths']['user_packages']}",
            f"Free storage:       {fp['storage']['free_bytes']:,} bytes",
            f"Installed packages: {', '.join(fp['installed']) if fp['installed'] else '(none)'}",
            "",
        ]
        return jsonify({
            "ok": True,
            "stdout": "\n".join(lines),
            "stderr": "",
            "exit_code": 0,
            "status": "idle",
            "prompt": get_session().get_prompt(),
        })

    # Execute real command
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
    """Send input to running process."""
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
    """Stop running process (Ctrl+C)."""
    session = get_session()
    result = session.stop()
    result["prompt"] = session.get_prompt()
    return jsonify(result)


@app.get("/api/status")
@require_auth
def get_status():
    """Get terminal status."""
    session = get_session()
    return jsonify({
        "ok": True,
        "status": session.status,
        "exit_code": session.exit_code,
        "cwd": str(session.cwd),
        "prompt": session.get_prompt(),
    })


@app.get("/api/prompt")
@require_auth
def get_prompt():
    """Get current shell prompt."""
    session = get_session()
    return jsonify({
        "ok": True,
        "prompt": session.get_prompt(),
    })


def run_server():
    """Run WebView server with port conflict detection."""
    # Try ports 5000-5010 to handle collision/denial-of-service on fixed port
    for port in range(5000, 5011):
        try:
            # Quick check if port is available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
        except OSError as e:
            print(f"[WARN] Port {port} occupied ({e}), trying next...")
            continue

        try:
            print(f"[INFO] Starting ZMUX Terminal server on 127.0.0.1:{port}")
            print("[INFO] Loopback-only: exposure reduction, not full app-private boundary")
            print("[INFO] Token delivery: AUTH_TOKEN embedded in root HTML, validated via constant-time compare")
            serve(app, host="127.0.0.1", port=port, threads=4)
            break
        except OSError as e:
            print(f"[WARN] Failed to start on port {port}: {e}, trying next...")
            if port == 5010:
                print("[ERROR] All ports 5000-5010 occupied.")
                raise
            continue
