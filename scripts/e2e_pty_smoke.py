#!/usr/bin/env python3
"""End-to-end smoke test: real server + real WebSocket client + real PTY.

Simulates the xterm.js frontend against the actual ZMUX server, driving the
Alpine PTY shell end to end: `linux` -> banner -> commands -> Ctrl+C ->
`exit` -> host console, plus `zmux-pty-probe` and Phase-2 auto-start.

Usage: python e2e_pty_smoke.py <port>
"""
import base64
import hashlib
import os
import re
import socket
import struct
import sys
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def ws_connect(port, token):
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET /?token={token} HTTP/1.1\r\n"
        f"Host: {HOST}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s = socket.create_connection((HOST, port), timeout=10)
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp += chunk
    if b"101" not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError(f"handshake failed: {resp[:200]!r}")
    return s


def ws_send_text(sock, text):
    data = text.encode("utf-8")
    header = bytes([0x81])
    n = len(data)
    if n < 126:
        header += bytes([0x80 | n])
    elif n < 65536:
        header += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(header + masked)


def ws_recv(sock, timeout=12.0):
    sock.settimeout(timeout)
    try:
        first = sock.recv(2)
    except socket.timeout:
        return None
    if len(first) < 2:
        return None
    opcode = first[0] & 0x0F
    length = first[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    payload = _recv_exact(sock, length)
    if opcode == 8:
        return ("close", payload)
    return (opcode, payload)


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def collect_until(sock, needle, timeout=12.0, out=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = ws_recv(sock, timeout=1.0)
        if msg is None:
            continue
        opcode, payload = msg
        if opcode == 1:
            if out is not None:
                out.append(payload.decode("utf-8", "replace"))
            if isinstance(needle, bytes) and needle in payload:
                return True
        elif opcode == 2:
            if out is not None:
                out.append(payload)
            if isinstance(needle, bytes) and needle in payload:
                return True
    return False


def main():
    # 1) fetch the page, extract the WS auth token + WS port (like the
    #    frontend does: the HTTP server and WS server are different ports).
    token = None
    ws_port = None
    try:
        html = urllib.request.urlopen(f"http://{HOST}:{PORT}/", timeout=10).read().decode()
        m = re.search(r'const AUTH_TOKEN = "([^"]+)"', html)
        token = m.group(1) if m else None
        m = re.search(r"const WS_PORT = (\d+)", html)
        ws_port = int(m.group(1)) if m else None
    except Exception as e:
        check("fetch-index", False, f"{e}")
        return 1
    check("fetch-index", token is not None and ws_port is not None, f"ws_port={ws_port}")

    sock = ws_connect(ws_port, token)
    check("ws-handshake", True)

    # 2+3) the initial scrollback replay arrives in one frame: host banner
    #      AND (Phase 2) the Alpine shell banner, plus the shell prompt.
    frames = []
    got = collect_until(sock, b"[Alpine Linux shell", timeout=10.0, out=frames)
    blob = b"".join(f if isinstance(f, bytes) else f.encode() for f in frames)
    check("initial-banner", b"ZMUX terminal" in blob)
    check("phase2-auto-alpine-shell", got)

    # 4) run a command inside the real shell
    ws_send_text(sock, "echo E2E-OK-$((7*6))\r")
    got = collect_until(sock, b"E2E-OK-42")
    check("alpine-command", got)

    # 5) Ctrl+C kills a foreground sleep (kernel SIGINT)
    ws_send_text(sock, "sleep 20\r")
    time.sleep(0.5)
    ws_send_text(sock, "\x03")
    ws_send_text(sock, "echo AFTER-CTRLC\r")
    got = collect_until(sock, b"AFTER-CTRLC", timeout=5.0)
    check("ctrl-c-kills-foreground", got)

    # 6) resize via JSON action reaches the shell
    ws_send_text(sock, '{"action":"resize","cols":47,"rows":11}')
    ws_send_text(sock, "stty size\r")
    got = collect_until(sock, b"11 47")
    check("resize-tiocswinsz", got)

    # 7) exit -> host console
    ws_send_text(sock, "exit\r")
    got = collect_until(sock, b"[Alpine shell exited", timeout=10.0)
    got2 = collect_until(sock, b"zmux:")
    check("exit-returns-host-console", got and got2)

    # 8) host builtins still work after returning
    ws_send_text(sock, "zmux-pty-probe\n")
    collected = []
    got = collect_until(sock, b"pty6-exit-code", timeout=60.0, out=collected)
    blob = b"".join(c if isinstance(c, bytes) else c.encode() for c in collected)
    check("pty-probe-runs", got)
    n_pass = blob.count(b"[PASS]")
    n_fail = blob.count(b"[FAIL]")
    check("pty-probe-all-pass", n_pass == 6 and n_fail == 0, f"({n_pass} pass, {n_fail} fail)")
    # Wait until the probe command fully finishes (host prompt returns) so a
    # pending busy-flag cannot silently swallow the toggle below.
    got_prompt = collect_until(sock, b"zmux:", timeout=30.0)
    check("pty-probe-completed", got_prompt)

    # 9) JSON action toggles (from host console it re-enters Alpine)
    ws_send_text(sock, '{"action":"pty.toggle"}')
    got = collect_until(sock, b"[Alpine Linux shell", timeout=10.0)
    check("pty-toggle-reattach", got)
    # detach back
    ws_send_text(sock, '{"action":"pty.toggle"}')
    got = collect_until(sock, b"detached from Alpine shell", timeout=10.0)
    check("pty-toggle-detach", got)

    sock.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
