"""Websocket terminal backed by the embedded Python runtime.

There is intentionally no PTY and no ``/system/bin/sh`` child here. Android
frequently marks app data noexec, which makes a shell unable to launch Python
scripts.  The terminal instead sends each completed line to :class:`PythonShell`.
"""
from __future__ import annotations

import codeop
import threading
from typing import Optional

from zmux.python_shell import PythonShell


class PTYTerminalSession:
    """Persistent, Python-native interactive terminal session.

    The public name is retained for compatibility with the websocket server,
    but this is a virtual terminal rather than a Unix PTY.
    """
    def __init__(self, ws_server):
        self.ws_server = ws_server
        self.shell = PythonShell()
        self.is_running = False
        self.process = None  # Compatibility: no shell process is spawned.
        self.lock = threading.RLock()
        self.buffer_lock = threading.Lock()
        self.scrollback_buffer = bytearray()
        self.scrollback_max_size = 32768
        self._line_buffer = ""
        self._python_lines: list[str] = []

    def start(self) -> None:
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            self.ws_server.register_callbacks(on_data=self.write_input, on_resize=self.resize)
            self._emit(b"ZMUX Python-native terminal\r\nPython code executes in the embedded runtime.\r\n>>> ")

    def stop(self) -> None:
        with self.lock:
            self.is_running = False
            self._line_buffer = ""
            self._python_lines.clear()

    def resize(self, cols: int, rows: int) -> None:
        # xterm owns display dimensions; no child PTY needs ioctl(TIOCSWINSZ).
        return None

    def get_scrollback(self) -> bytes:
        with self.buffer_lock:
            return bytes(self.scrollback_buffer)

    def _emit(self, data: bytes) -> None:
        with self.buffer_lock:
            self.scrollback_buffer.extend(data)
            if len(self.scrollback_buffer) > self.scrollback_max_size:
                del self.scrollback_buffer[:-self.scrollback_max_size]
        self.ws_server.broadcast(data)

    def write_input(self, data: bytes) -> None:
        """Process real keyboard input and execute a completed command line."""
        with self.lock:
            if not self.is_running:
                return
            text = data.decode("utf-8", errors="replace")
            for char in text:
                if char == "\x03":  # Ctrl+C
                    self._line_buffer = ""; self._python_lines.clear()
                    self._emit(b"^C\r\n>>> ")
                elif char in ("\x7f", "\x08"):
                    if self._line_buffer:
                        self._line_buffer = self._line_buffer[:-1]
                        self._emit(b"\b \b")
                elif char in ("\r", "\n"):
                    self._emit(b"\r\n")
                    self._submit_line(self._line_buffer)
                    self._line_buffer = ""
                elif char >= " ":
                    self._line_buffer += char
                    self._emit(char.encode("utf-8"))

    def _submit_line(self, line: str) -> None:
        # Support compound Python blocks (for/def/try etc.) without pretending
        # to be a shell. Known shell commands remain single-line operations.
        candidate = "\n".join([*self._python_lines, line])
        commands = set(self.shell.commands) | {"python", "python3", "pip", "zpip", "help", "zmux-info"}
        is_command = bool(line.strip()) and line.lstrip().split(maxsplit=1)[0] in commands
        if self._python_lines or not is_command:
            try:
                pending = codeop.compile_command(candidate, "<zmux>", "exec")
            except (SyntaxError, OverflowError, ValueError):
                pending = object()  # execute it to render CPython's real error
            if pending is None:
                self._python_lines.append(line)
                self._emit(b"... ")
                return
        result = self.shell.execute(candidate)
        self._python_lines.clear()
        output = (result.get("stdout", "") + result.get("stderr", "")).replace("\n", "\r\n")
        if output:
            self._emit(output.encode("utf-8", errors="replace"))
        self._emit(b">>> ")


_pty_session: Optional[PTYTerminalSession] = None


def get_pty_session(ws_server) -> PTYTerminalSession:
    global _pty_session
    if _pty_session is None:
        _pty_session = PTYTerminalSession(ws_server)
    return _pty_session
