"""
Tests for ZMUX PTY and WebSocket Server Integration.

Verifies secure handshake authentication, dynamic port binding,
WebSocket framing, and PTY process spawn capabilities.
"""

import socket
import threading
import time
from pathlib import Path

import pytest

from zmux.security import AUTH_TOKEN
from zmux.ws_server import WebSocketServer
from zmux.pty_session import PTYTerminalSession, get_pty_session


def test_websocket_server_handshake():
    """Test that unauthorized token is rejected with 401, and valid token gets 101 Switching Protocols."""
    # Find an open port by binding port=0
    server = WebSocketServer(host="127.0.0.1", port=0)
    server.start()

    # Wait briefly for start
    time.sleep(0.1)
    assert server.is_running
    port = server.server_socket.getsockname()[1]

    try:
        # 1. Connection with invalid token
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))

        bad_handshake = (
            "GET /?token=invalid_zaba_token HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(bad_handshake.encode("utf-8"))

        response = sock.recv(2048).decode("utf-8")
        assert "401 Unauthorized" in response
        sock.close()

        # 2. Connection with valid token
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2.connect(("127.0.0.1", port))

        good_handshake = (
            f"GET /?token={AUTH_TOKEN} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock2.sendall(good_handshake.encode("utf-8"))

        response2 = sock2.recv(2048).decode("utf-8")
        assert "101 Switching Protocols" in response2
        assert "Sec-WebSocket-Accept" in response2
        sock2.close()

    finally:
        server.stop()


def test_pty_session_lifecycle():
    """Test PTY session startup, input writing, and graceful stopping."""
    server = WebSocketServer(host="127.0.0.1", port=0)
    server.start()
    time.sleep(0.1)

    try:
        session = PTYTerminalSession(server)
        session.start()

        assert session.is_running
        # Python-native mode deliberately does not spawn a shell process.
        assert session.process is None

        # Try to write some characters
        session.write_input(b"echo pty_test\n")
        time.sleep(0.2)

        # Output should be generated and buffered
        scrollback = session.get_scrollback()
        assert len(scrollback) > 0

        session.stop()
        assert not session.is_running
        assert session.process is None
    finally:
        server.stop()


def test_global_pty_session_singleton():
    """Test that get_pty_session correctly returns a singleton instance."""
    server = WebSocketServer(host="127.0.0.1", port=0)
    try:
        s1 = get_pty_session(server)
        s2 = get_pty_session(server)
        assert s1 is s2
    finally:
        server.stop()


def test_broadcast_with_dead_client_does_not_deadlock():
    """Regression: a dead-but-still-registered client (WebView reload/rotation
    race) must not deadlock broadcast(); previously _unregister_client() was
    called while already holding clients_lock, freezing the PTY reader thread,
    every later broadcast, and stop() — the app-wide "stuck" state."""
    server = WebSocketServer(host="127.0.0.1", port=0)
    server.start()
    time.sleep(0.1)

    dead = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with server.clients_lock:
        server.clients.add(dead)
    dead.close()  # sendall() now raises immediately

    finished = threading.Event()

    def _broadcast():
        server.broadcast(b"pty-output")
        finished.set()

    t = threading.Thread(target=_broadcast, daemon=True)
    t.start()

    assert finished.wait(timeout=5.0), "broadcast() deadlocked on dead client"

    # Dead client must have been removed, and the lock must still be usable
    with server.clients_lock:
        assert dead not in server.clients
    server.stop()


def test_websocket_start_with_prebound_listener():
    """run_server() hands a live listener to WebSocketServer to avoid the
    probe-then-bind race; the server must serve on exactly that socket."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    port = listener.getsockname()[1]

    server = WebSocketServer(host="127.0.0.1", port=port)
    server.start(listener=listener)
    time.sleep(0.1)
    try:
        assert server.is_running
        assert server.server_socket is listener

        sock = socket.create_connection(("127.0.0.1", port))
        sock.sendall((
            f"GET /?token={AUTH_TOKEN} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("utf-8"))
        response = sock.recv(2048).decode("utf-8")
        assert "101 Switching Protocols" in response
        sock.close()
    finally:
        server.stop()


def test_websocket_start_with_multiple_listeners():
    """Verify WebSocketServer can listen on multiple bound sockets simultaneously (e.g. dual IPv4/IPv6)."""
    l1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    l1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    l1.bind(("127.0.0.1", 0))
    l1.listen(5)
    port1 = l1.getsockname()[1]

    l2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    l2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    l2.bind(("127.0.0.1", 0))
    l2.listen(5)
    port2 = l2.getsockname()[1]

    server = WebSocketServer(host="127.0.0.1", port=port1)
    server.start(listeners=[l1, l2])
    time.sleep(0.1)
    try:
        assert server.is_running
        for p in (port1, port2):
            sock = socket.create_connection(("127.0.0.1", p))
            sock.sendall((
                f"GET /?token={AUTH_TOKEN} HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode("utf-8"))
            response = sock.recv(2048).decode("utf-8")
            assert "101 Switching Protocols" in response
            sock.close()
    finally:
        server.stop()


def test_python_native_session_does_not_depend_on_openpty(monkeypatch):
    """Python-native mode must work even where Android denies /dev/ptmx."""
    import os

    def _mock_openpty():
        raise PermissionError("[Errno 13] Permission denied: '/dev/ptmx'")

    monkeypatch.setattr(os, "openpty", _mock_openpty, raising=False)

    server = WebSocketServer(host="127.0.0.1", port=0)
    server.start()
    time.sleep(0.1)

    try:
        session = PTYTerminalSession(server)
        session.start()

        assert session.is_running
        assert session.process is None

        session.write_input(b"echo python_native_ok\n")
        time.sleep(0.2)
        scrollback = session.get_scrollback()
        assert b"python_native_ok" in scrollback

        session.stop()
        assert not session.is_running
    finally:
        server.stop()

