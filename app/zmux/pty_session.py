"""
ZMUX PTY Session Manager — Real Unix Pseudoterminal Integration.

Spawns /system/bin/sh in a real PTY so that interactive CLI programs like
python REPL, vim, top, etc., can run and detect a real terminal (isatty).
Maintains a persistent session across webview reloads and screen rotation.
"""

import os
import select
import struct
import subprocess
import sys
import threading
from typing import Optional

# Safe imports for non-Unix environments (e.g. Windows local testing)
try:
    import fcntl
    import termios
    HAS_PTY = True
except ImportError:
    HAS_PTY = False

# ---------------------------------------------------------------------------
# ZMUX built-in commands that must be intercepted before reaching /system/bin/sh.
#
# On Android, app-private storage is frequently mounted with the ``noexec``
# flag or restricted by SELinux, which makes the shell wrapper scripts in
# BIN_DIR un-executable (``Permission denied``).  By intercepting these
# commands at the PTY input layer and handling them purely in Python we
# bypass the filesystem execution restriction entirely.
# ---------------------------------------------------------------------------
_INTERCEPT_COMMANDS = frozenset({"clear", "help", "zmux-info", "zpip", "pip"})


class PTYTerminalSession:
    """Manages a persistent PTY session running an interactive shell."""

    def __init__(self, ws_server):
        self.ws_server = ws_server
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.lock = threading.Lock()
        # True only when the child was spawned in its own session/group
        # (os.setsid). killpg() is unsafe otherwise — the child would share
        # *our* process group and SIGKILL would take the whole app down.
        self._own_process_group = False

        # Ring buffer for recent terminal output (scrollback replay on reload)
        self.scrollback_buffer = bytearray()
        self.scrollback_max_size = 32768  # 32KB scrollback replay
        self.buffer_lock = threading.Lock()

        # Line buffer for intercepting ZMUX built-in commands before they
        # reach /system/bin/sh.  Keystrokes are accumulated here until a
        # carriage return (\r) or newline (\n) arrives, at which point the
        # complete line is checked against _INTERCEPT_COMMANDS.
        self._line_buffer = ""
        self._line_buffer_lock = threading.Lock()

    def _resolve_shell(self) -> str:
        for candidate in ("/system/bin/sh", "/bin/sh", "/system/xbin/sh", "sh"):
            if candidate == "sh" or (os.path.exists(candidate) and os.access(candidate, os.X_OK)):
                return candidate
        return "sh"

    @staticmethod
    def resolve_python() -> str:
        """Find the Python interpreter binary on the system."""
        for candidate in ("python3", "python"):
            from shutil import which
            path = which(candidate)
            if path:
                return path
        return sys.executable or "python"

    def start(self) -> None:
        """Start the interactive shell in a PTY if not already running."""
        with self.lock:
            if self.is_running and self.process and self.process.poll() is None:
                return  # Session is already active!

            self._stop_unlocked()

            shell = self._resolve_shell()
            print(f"[INFO] Spawning interactive PTY session using: {shell}")

            if not HAS_PTY or not hasattr(os, "openpty"):
                # Fallback path for non-PTY systems (e.g. Windows dev)
                self._start_fallback(shell)
                return

            try:
                self.master_fd, self.slave_fd = os.openpty()

                # Build clean environment
                from zmux.terminal import get_session
                session_env = get_session()._build_env()

                use_setsid = hasattr(os, "setsid")
                self.process = subprocess.Popen(
                    [shell],
                    stdin=self.slave_fd,
                    stdout=self.slave_fd,
                    stderr=self.slave_fd,
                    cwd=str(get_session().cwd),
                    env=session_env,
                    start_new_session=use_setsid,
                    close_fds=True,
                )
                self._own_process_group = use_setsid

                # Close slave_fd in parent process as it is owned by the child
                os.close(self.slave_fd)
                self.slave_fd = None

                self.is_running = True

                # Clear old scrollback on fresh shell start
                with self.buffer_lock:
                    self.scrollback_buffer.clear()

                # Register websocket callbacks
                self.ws_server.register_callbacks(
                    on_data=self.write_input,
                    on_resize=self.resize
                )

                # Start real-time reader thread
                self.reader_thread = threading.Thread(
                    target=self._read_loop,
                    daemon=True,
                    name="ZMUX-PTY-Reader"
                )
                self.reader_thread.start()

            except Exception as e:
                print(f"[WARN] Failed to start PTY session ({e}), falling back to standard pipe session...")
                self._stop_unlocked()
                self._start_fallback(shell)

    def _start_fallback(self, shell: str) -> None:
        """Fallback mode using standard pipes if PTY is not supported by OS."""
        try:
            from zmux.terminal import get_session
            session_env = get_session()._build_env()
            # When running without a real PTY the terminal has no real
            # screen-size or cursor-control capabilities.  Setting TERM=dumb
            # prevents programs from emitting escape sequences that would
            # garble the output and avoids "No controlling tty" warnings.
            session_env["TERM"] = "dumb"

            use_setsid = hasattr(os, "setsid")
            self.process = subprocess.Popen(
                [shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(get_session().cwd),
                env=session_env,
                text=False,
                bufsize=0,
                start_new_session=use_setsid,
            )
            self._own_process_group = use_setsid
            self.is_running = True

            # Clear old scrollback
            with self.buffer_lock:
                self.scrollback_buffer.clear()

            self.ws_server.register_callbacks(
                on_data=self.write_input,
                on_resize=self.resize
            )

            # Fallback reader thread
            self.reader_thread = threading.Thread(
                target=self._fallback_read_loop,
                daemon=True,
                name="ZMUX-PTY-Fallback-Reader"
            )
            self.reader_thread.start()
        except Exception as e:
            print(f"[ERROR] Failed to start fallback PTY session: {e}")
            self._stop_unlocked()

    def _read_loop(self) -> None:
        """Poll PTY master and broadcast output to client."""
        while self.is_running and self.master_fd is not None:
            try:
                # Polling wait to check running state and avoid blocking CPU
                r, _, _ = select.select([self.master_fd], [], [], 0.05)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 4096)
                    if not data:
                        break  # EOF: shell closed

                    # Update scrollback replay buffer
                    with self.buffer_lock:
                        self.scrollback_buffer.extend(data)
                        if len(self.scrollback_buffer) > self.scrollback_max_size:
                            # Trim older data
                            self.scrollback_buffer = self.scrollback_buffer[-self.scrollback_max_size:]

                    # Broadcast raw bytes to all websocket connections
                    self.ws_server.broadcast(data)
            except (OSError, ValueError):
                break
            except Exception as e:
                print(f"[ERROR] PTY read loop exception: {e}")
                break

        self.stop()

    def _fallback_read_loop(self) -> None:
        """Fallback read loop from stdout stream."""
        while self.is_running and self.process and self.process.stdout:
            try:
                data = self.process.stdout.read(1024)
                if not data:
                    break
                with self.buffer_lock:
                    self.scrollback_buffer.extend(data)
                    if len(self.scrollback_buffer) > self.scrollback_max_size:
                        self.scrollback_buffer = self.scrollback_buffer[-self.scrollback_max_size:]
                self.ws_server.broadcast(data)
            except Exception:
                break
        self.stop()

    def get_scrollback(self) -> bytes:
        """Get the current scrollback buffer bytes for replay on connect."""
        with self.buffer_lock:
            return bytes(self.scrollback_buffer)

    def write_input(self, data: bytes) -> None:
        """Write raw keyboard input bytes to the PTY.

        ZMUX built-in commands (clear, help, zmux-info, zpip, pip) are
        intercepted here and handled in Python instead of being forwarded to
        /system/bin/sh.  This bypasses Android SELinux / noexec restrictions
        on app-private storage that would otherwise cause "Permission denied".
        """
        with self.lock:
            if not self.is_running:
                return

            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = ""

            with self._line_buffer_lock:
                for ch in text:
                    if ch in ("\r", "\n"):
                        line = self._line_buffer.strip()
                        self._line_buffer = ""
                        if line and self._try_intercept(line):
                            # Command was handled locally; do not send to shell
                            continue
                        # Not an intercept command — forward the newline to shell
                        self._write_to_pty(ch.encode("utf-8"))
                    elif ch == "\x7f" or ch == "\x08":
                        # Backspace / DEL — trim line buffer
                        self._line_buffer = self._line_buffer[:-1]
                        self._write_to_pty(data)
                    elif ch == "\x03":
                        # Ctrl+C — clear line buffer, forward to shell
                        self._line_buffer = ""
                        self._write_to_pty(data)
                    else:
                        self._line_buffer += ch
                        self._write_to_pty(ch.encode("utf-8"))

    def _write_to_pty(self, data: bytes) -> None:
        """Write raw bytes to the PTY master fd or fallback stdin."""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except Exception as e:
                print(f"[ERROR] Failed to write raw PTY input: {e}")
        elif self.process and self.process.stdin:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except Exception as e:
                print(f"[ERROR] Failed to write fallback PTY input: {e}")

    def _try_intercept(self, line: str) -> bool:
        """Try to intercept a ZMUX built-in command.

        Returns True if the command was handled locally, False if it should
        be forwarded to the shell.
        """
        parts = line.strip().split()
        if not parts:
            return False
        cmd = parts[0]
        if cmd not in _INTERCEPT_COMMANDS:
            return False

        # Handle the command in Python
        try:
            if cmd == "clear":
                self._write_output(b"\033[H\033[2J\033[3J")
            elif cmd == "help":
                from zmux.terminal import HELP_TEXT
                self._write_output(HELP_TEXT.encode("utf-8"))
            elif cmd == "zmux-info":
                from zmux.zpip import format_fingerprint, runtime_fingerprint
                output = format_fingerprint(runtime_fingerprint()) + "\n"
                self._write_output(output.encode("utf-8"))
            elif cmd == "zpip":
                from zmux.zpip import dispatch, format_output
                result = dispatch(line)
                output, _ = format_output(line, result)
                self._write_output((output + "\n").encode("utf-8"))
            elif cmd == "pip":
                msg = (
                    "pip is not available inside this ZMUX runtime.\r\n"
                    "Use the ZMUX package manager instead:\r\n"
                    "  zpip search <name>      Search for packages\r\n"
                    "  zpip info <name>        Show package info\r\n"
                    "  zpip install <name>     Install a package\r\n"
                    "  zpip list               List installed packages\r\n"
                    "  zpip verify <name>      Verify a package installation\r\n"
                    "  zpip uninstall <name>   Uninstall a package\r\n"
                    "  zpip doctor             Check system health\r\n"
                )
                self._write_output(msg.encode("utf-8"))
        except Exception as e:
            err = f"zmux: {cmd}: error: {e}\r\n"
            self._write_output(err.encode("utf-8"))
        return True

    def _write_output(self, data: bytes) -> None:
        """Write output data back to the PTY so the user can see it."""
        with self.buffer_lock:
            self.scrollback_buffer.extend(data)
            if len(self.scrollback_buffer) > self.scrollback_max_size:
                self.scrollback_buffer = self.scrollback_buffer[-self.scrollback_max_size:]
        self.ws_server.broadcast(data)

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY terminal size using ioctl TIOCSWINSZ."""
        if not HAS_PTY or self.master_fd is None:
            return

        with self.lock:
            try:
                # winsize struct is: unsigned short rows, cols, xpixel, ypixel -> 'HHHH'
                size_struct = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size_struct)
            except Exception as e:
                print(f"[ERROR] PTY resize ioctl failed: {e}")

    def stop(self) -> None:
        """Gracefully stop and clean up the active shell and PTY."""
        with self.lock:
            self._stop_unlocked()

    def _stop_unlocked(self) -> None:
        self.is_running = False

        if self.process:
            try:
                # Terminate the shell's process group — but only if the child
                # actually has its own group. Otherwise killpg() would target
                # our own process group and kill the whole app.
                if self._own_process_group and hasattr(os, "killpg"):
                    try:
                        os.killpg(os.getpgid(self.process.pid), 9)
                    except Exception:
                        pass
                self.process.terminate()
                self.process.wait(timeout=0.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self._own_process_group = False

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except Exception:
                pass
            self.slave_fd = None


# Global active PTY session instance
_pty_session: Optional[PTYTerminalSession] = None


def get_pty_session(ws_server) -> PTYTerminalSession:
    """Get or create the global persistent PTY terminal session."""
    global _pty_session
    if _pty_session is None:
        _pty_session = PTYTerminalSession(ws_server)
    return _pty_session
