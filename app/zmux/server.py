"""
ZMUX Terminal Server — Flask WebView backend.

Provides REST API for terminal operations and serves the terminal UI.
Loopback-only: 127.0.0.1 for WebView consumption.
"""

import functools
import os
import socket
import time
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
    ws_port = app.config["WS_PORT"]
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
    """Parse and validate JSON body.

    Returns a 2-tuple (payload, error_response).
    - On success: (dict, None)
    - On error:   (None, (jsonify_response, status_code))

    Callers must unpack exactly 2 values and return `err` when it is not None:

        payload, err = _get_json_payload()
        if err:
            return err
    """
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data(cache=True, as_text=True).strip():
            return None, (jsonify({"ok": False, "message": "Invalid JSON", "code": "invalid_json"}), 400)
        return {}, None
    if not isinstance(data, dict):
        return None, (jsonify({"ok": False, "message": "JSON must be object", "code": "invalid_json_type"}), 400)
    return data, None


# The WebSocket port is only known once run_server() has bound its listener,
# so it lives in app.config (read at request time) rather than in a mutable
# module global that tests could observe before the server even started.
app.config.setdefault("WS_PORT", 5001)


@app.get("/")
def index():
    return render_template("terminal.html", auth_token=AUTH_TOKEN, ws_port=app.config["WS_PORT"])


@app.get("/api/health")
def health_check():
    session = get_session()
    return jsonify({"ok": True, "version": APP_VERSION, "app": "ZMUX", "type": "terminal", "status": session.status})


# Backwards-compatible alias: the formatter now lives in zmux.zpip so the
# REST server and the CLI (python -m zmux.cli) share one implementation.
_format_zpip_output = zpip.format_output


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
        return jsonify(
            {
                "ok": True,
                "stdout": zpip.format_fingerprint(fp) + "\n",
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


#: The p4a webview bootstrap polls *exactly* this port (p4a.port = 5000) and
#: loads http://127.0.0.1:5000/ once it answers. On Android we must therefore
#: serve on this port — silently moving to another port leaves the WebView
#: waiting forever (the "stuck on loading screen" boot freeze).
P4A_HTTP_PORT = 5000
#: How long to wait for the p4a port to become free on Android (a zombie
#: process from a previous launch may hold it briefly).
P4A_BIND_TIMEOUT_SECONDS = 30.0


def _bind_listener(host: str, port: int, family: int = socket.AF_INET, reuse_port: bool = False) -> socket.socket:
    """Create, bind and listen on a socket. Raises OSError on failure."""
    sock = socket.socket(family, socket.SOCK_STREAM)
    if family == socket.AF_INET6 and hasattr(socket, "IPV6_V6ONLY"):
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if reuse_port and hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    sock.bind((host, port))
    sock.listen(min(socket.SOMAXCONN, 128))
    return sock


def _bind_ipv6_loopback(port: int, reuse_port: bool = False):
    """Best-effort extra listener on ::1 (the p4a bootstrap pings "localhost",
    which may resolve to IPv6 on some devices). Returns None when unavailable."""
    try:
        return _bind_listener("::1", port, family=socket.AF_INET6, reuse_port=reuse_port)
    except OSError:
        return None


def _is_android() -> bool:
    return any(k in os.environ for k in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"))


def _bind_http_socket() -> socket.socket:
    """Bind the HTTP listener, honouring the Android WebView port contract."""
    if _is_android():
        deadline = time.monotonic() + P4A_BIND_TIMEOUT_SECONDS
        while True:
            # Loopback candidates only. 0.0.0.0 was deliberately removed: "/"
            # serves the WebView auth token without authentication, so binding
            # a wildcard interface would hand that token to the whole LAN.
            for host in ("127.0.0.1", "localhost"):
                try:
                    return _bind_listener(host, P4A_HTTP_PORT, reuse_port=True)
                except OSError:
                    continue
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Could not bind 127.0.0.1:{P4A_HTTP_PORT} within "
                    f"{int(P4A_BIND_TIMEOUT_SECONDS)}s. The Android WebView "
                    "shell waits for this exact port, so ZMUX cannot start. "
                    "Close other ZMUX instances and restart the app."
                )
            print(f"[WARN] Port {P4A_HTTP_PORT} occupied, retrying...")
            time.sleep(0.1)
    for port in range(P4A_HTTP_PORT, P4A_HTTP_PORT + 11):
        try:
            return _bind_listener("127.0.0.1", port)
        except OSError as e:
            print(f"[WARN] Port {port} occupied ({e}), trying next...")
    raise RuntimeError(f"All ports {P4A_HTTP_PORT}-{P4A_HTTP_PORT + 10} occupied.")


def _bind_ws_socket(http_port: int) -> socket.socket:
    """Bind the WebSocket listener on the first free port above http_port.

    Loopback only, by design: the token-authenticated terminal stream must
    never be reachable from any non-loopback interface.
    """
    for port in range(http_port + 1, http_port + 101):
        try:
            return _bind_listener("127.0.0.1", port)
        except OSError:
            continue
    raise RuntimeError(f"Could not find a free WebSocket port above {http_port}.")


def run_server():
    # Bind real listeners up front (no probe-then-bind race).
    http_sock = _bind_http_socket()
    http_port = http_sock.getsockname()[1]

    listeners = [http_sock]
    ipv6_sock = _bind_ipv6_loopback(http_port)
    if ipv6_sock is not None:
        listeners.append(ipv6_sock)
        print(f"[INFO] Also listening on [::1]:{http_port} (localhost may resolve to IPv6)")

    ws_sock = _bind_ws_socket(http_port)
    ws_port = ws_sock.getsockname()[1]
    # Publish before serving so the CSP header and terminal.html render with
    # the real port from the very first request.
    app.config["WS_PORT"] = ws_port
    ws_listeners = [ws_sock]
    ws_ipv6 = _bind_ipv6_loopback(ws_port)
    if ws_ipv6 is not None:
        ws_listeners.append(ws_ipv6)
        print(f"[INFO] WebSocket also listening on [::1]:{ws_port}")

    print(f"[INFO] Starting ZMUX Terminal server on 127.0.0.1:{http_port}")
    print(f"[INFO] Selected WebSocket Port: {ws_port}")

    # Start WebSocket and PTY servers (passing the live listener avoids a
    # second bind race and guarantees the port advertised to the UI exists).
    from zmux.ws_server import WebSocketServer
    from zmux.sessions import get_manager

    ws_server = WebSocketServer(host="127.0.0.1", port=ws_port)
    ws_server.start(listeners=ws_listeners)

    # Creates the first session and owns input routing from here on.
    manager = get_manager(ws_server)
    ws_server.register_callbacks(on_data=manager.write_input, on_resize=manager.resize)

    try:
        serve(app, sockets=listeners, threads=4)
    finally:
        for listener in listeners:
            try:
                listener.close()
            except OSError:
                pass
