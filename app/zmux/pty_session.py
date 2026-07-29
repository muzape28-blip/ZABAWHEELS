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
import threading
from typing import Optional

# Safe imports for non-Unix environments (e.g. Windows local testing)
try:
    import fcntl
    import termios
    HAS_PTY = True
except ImportError:
    HAS_PTY = False


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

    def start(self) -> None:
        """Start the interactive shell in a PTY if not already running."""
        with self.lock:
            if self.is_running and self.process and self.process.poll() is None:
                return  # Session is already active!

            self._stop_unlocked()

            shell = "/system/bin/sh"
            if not os.path.exists(shell):
                shell = "/bin/sh"

            # Check if shell exists at all, fallback to system python or sh
            if not os.path.exists(shell):
                shell = "sh"

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
                    preexec_fn=os.setsid if use_setsid else None,
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
                print(f"[ERROR] Failed to start PTY session: {e}")
                self._stop_unlocked()

    def _start_fallback(self, shell: str) -> None:
        """Fallback mode using standard pipes if PTY is not supported by OS."""
        try:
            from zmux.terminal import get_session
            session_env = get_session()._build_env()

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
                preexec_fn=os.setsid if use_setsid else None,
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
        """Write raw keyboard input bytes to the PTY."""
        with self.lock:
            if not self.is_running:
                return

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
