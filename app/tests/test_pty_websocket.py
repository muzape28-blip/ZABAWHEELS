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
        assert session.process is not None
        assert session.process.poll() is None

        # Try to write some characters
        session.write_input(b"echo pty_test\n")
        time.sleep(0.2)

        # Output should be generated and buffered
        scrollback = session.get_scrollback()
        assert len(scrollback) > 0

        session.stop()
        assert not session.is_running
        assert session.process is None or session.process.poll() is not None
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
