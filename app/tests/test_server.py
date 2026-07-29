"""Tests for terminal-facing server response formatting."""

import socket

from zmux.server import (
    _bind_listener,
    _bind_ws_socket,
    _format_zpip_output,
)


def test_install_output_uses_real_newlines():
    output, exit_code = _format_zpip_output(
        "zpip install demo",
        {
            "ok": True,
            "package": "demo",
            "version": "1.2.3",
            "dependencies_installed": ["dep-one", "dep-two"],
        },
    )

    assert exit_code == 0
    assert output == "Successfully installed demo-1.2.3\nAlso installed: dep-one, dep-two"


def test_failed_verify_keeps_useful_details():
    output, exit_code = _format_zpip_output(
        "zpip verify demo",
        {"ok": False, "package": "demo", "missing": ["demo/module.py"]},
    )

    assert exit_code == 1
    assert output == "demo verification failed: missing files: demo/module.py"


def test_doctor_reports_failed_packages_with_failure_exit_code():
    output, exit_code = _format_zpip_output(
        "zpip doctor",
        {
            "ok": False,
            "runtime": {
                "runtime_id": "runtime-test",
                "python": {"version": "3.14.2"},
                "android": {"abi": "arm64-v8a"},
                "paths": {"user_packages": "/tmp/packages"},
            },
            "free_bytes": 1024,
            "index": "https://example.invalid/index",
            "packages": {"broken": {"ok": False}},
        },
    )

    assert exit_code == 1
    assert "broken: FAILED" in output


def test_bind_listener_returns_live_listening_socket():
    sock = _bind_listener("127.0.0.1", 0)
    try:
        host, port = sock.getsockname()[:2]
        assert host == "127.0.0.1"
        assert port > 0
        # Must accept connections immediately (real listener, no probe race)
        probe = socket.create_connection(("127.0.0.1", port), timeout=2)
        probe.close()
    finally:
        sock.close()


def test_bind_ws_socket_skips_occupied_ports():
    http_sock = _bind_listener("127.0.0.1", 0)
    try:
        http_port = http_sock.getsockname()[1]
        blocker = _bind_listener("127.0.0.1", http_port + 1)
        try:
            ws_sock = _bind_ws_socket(http_port)
            try:
                assert ws_sock.getsockname()[1] > http_port + 1
            finally:
                ws_sock.close()
        finally:
            blocker.close()
    finally:
        http_sock.close()
