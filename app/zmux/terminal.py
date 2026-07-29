"""
ZMUX Terminal Execution Engine

Provides a real subprocess-based terminal that:
- Runs commands with stdout/stderr streaming
- Supports stdin input
- Handles cancellation (Ctrl+C)
- Maintains persistent working directory
- Returns real exit codes

Threat model: This executes real system commands within app-private storage.
Commands like /system/bin/sh can see more than app-private area per Android OS policy.
"""

import os
import queue
import select
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from zmux.paths import BIN_DIR, HOME_DIR, LOG_DIR


HELP_TEXT = """ZMUX Terminal v1.0.0

Built-in commands:
  help          Show this help message
  clear         Clear terminal screen
  pwd           Print working directory
  cd <dir>      Change directory
  exit          Exit terminal session

System commands:
  ls, cat, mkdir, touch, cp, mv, rm, echo, env, which, uname
  All standard Android/Linux commands available via /system/bin/sh

Python:
  python        Start Python interpreter
  python <file> Run Python script
  python -c "..."  Execute Python code
  pip           Python package manager (if available)

ZMUX Package Manager:
  zpip search <name>      Search for packages
  zpip info <name>        Show package info
  zpip install <name>     Install package
  zpip list               List installed packages
  zpip verify <name>      Verify package installation
  zpip uninstall <name>   Uninstall package
  zpip doctor             Check system health

Runtime Info:
  zmux-info               Show runtime fingerprint

Note: This terminal executes real system commands within app-private storage.
Standard shell commands can access areas permitted by Android OS.
"""


class ProcessStatus:
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    STOPPED = "stopped"
    FAILED = "failed"
    EXITED = "exited"


class TerminalSession:
    """Manages a persistent terminal session with real subprocess execution."""

    def __init__(self):
        self._cwd = HOME_DIR
        self._process: Optional[subprocess.Popen] = None
        self._output_queue: queue.Queue = queue.Queue()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._status = ProcessStatus.IDLE
        self._exit_code: Optional[int] = None
        self._lock = threading.Lock()
        self._env = self._build_env()

    def _build_env(self) -> dict:
        """Build a clean environment for subprocess execution."""
        env = os.environ.copy()
        env["HOME"] = str(HOME_DIR)
        env["TERM"] = "xterm-256color"
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
        # --- PATH construction ---------------------------------------------------
        # On Android the inherited os.environ may lack a usable PATH, causing
        # basic system commands (mkdir, ls, cat, ...) to fail with "Permission
        # denied" or "not found".  We therefore always include the standard
        # Android system binary directories *before* prepending BIN_DIR so that
        # both ZMUX wrappers and real system utilities are reachable.
        _SYSTEM_PATHS = [
            "/system/bin",
            "/system/xbin",
            "/vendor/bin",
            "/sbin",
        ]
        path = env.get("PATH", "")
        # Deduplicate while preserving order: BIN_DIR first, then system dirs,
        # then any pre-existing PATH entries.
        seen: set = {str(BIN_DIR)}  # BIN_DIR is always first, skip duplicates
        parts: list = [str(BIN_DIR)]
        for p in _SYSTEM_PATHS + (path.split(os.pathsep) if path else []):
            if p and p not in seen:
                seen.add(p)
                parts.append(p)
        env["PATH"] = os.pathsep.join(parts)
        # Add user packages to Python path
        from zmux.paths import USER_PACKAGES_DIR
        pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{USER_PACKAGES_DIR}:{pythonpath}" if pythonpath else str(USER_PACKAGES_DIR)
        return env

    def _read_stream(self, stream, stream_name: str):
        """Read from a stream and queue output."""
        try:
            for line in iter(stream.readline, ""):
                if line:
                    self._output_queue.put((stream_name, line))
        except (ValueError, OSError):
            pass
        finally:
            try:
                stream.close()
            except:
                pass

    def _drain_output(self) -> list:
        """Drain all pending output from the queue."""
        output = []
        while not self._output_queue.empty():
            try:
                stream, line = self._output_queue.get_nowait()
                output.append({"stream": stream, "line": line})
            except queue.Empty:
                break
        return output

    @property
    def cwd(self) -> Path:
        """Current working directory."""
        return self._cwd

    @property
    def status(self) -> str:
        """Current process status."""
        with self._lock:
            if self._process and self._process.poll() is None:
                return ProcessStatus.RUNNING
            return self._status

    @property
    def exit_code(self) -> Optional[int]:
        """Exit code of last process."""
        return self._exit_code

    def execute(self, command: str, timeout: Optional[float] = None) -> dict:
        """
        Execute a command and return result.
        
        Returns dict with:
        - ok: bool
        - stdout: str
        - stderr: str
        - exit_code: int
        - status: str
        """
        with self._lock:
            if self._process and self._process.poll() is None:
                return {
                    "ok": False,
                    "error": "Another process is running. Use stop() first.",
                    "status": ProcessStatus.RUNNING,
                }

        # Parse command
        if not command.strip():
            return {"ok": True, "stdout": "", "stderr": "", "exit_code": 0, "status": ProcessStatus.IDLE}

        # Handle built-in commands
        builtin_result = self._handle_builtin(command)
        if builtin_result is not None:
            return builtin_result

        # Execute real subprocess
        try:
            self._status = ProcessStatus.RUNNING
            self._exit_code = None
            
            # Use shell=False for security, but allow shell for complex commands
            # Document: shell=True is used here because terminal needs to support
            # pipes, redirects, and complex shell syntax. User is already in a shell.
            self._process = subprocess.Popen(
                command,
                cwd=str(self._cwd),
                env=self._env,
                shell=True,  # Documented: needed for shell features
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                # Use start_new_session instead of preexec_fn=os.setsid.
                # preexec_fn with os.setsid crashes on Android Bionic libc
                # (ARMv7 armeabi-v7a) due to unsafe after-fork signal state.
                # start_new_session is the safe POSIX equivalent.
                start_new_session=True,
            )

            # Start reader threads
            self._stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(self._process.stdout, "stdout"),
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._read_stream,
                args=(self._process.stderr, "stderr"),
                daemon=True,
            )
            self._stdout_thread.start()
            self._stderr_thread.start()

            # Wait for completion with optional timeout
            try:
                if timeout:
                    self._process.wait(timeout=timeout)
                else:
                    self._process.wait()
            except subprocess.TimeoutExpired:
                self.stop()
                return {
                    "ok": False,
                    "stdout": self._collect_output(),
                    "stderr": f"Command timed out after {timeout}s",
                    "exit_code": -1,
                    "status": ProcessStatus.FAILED,
                }

            # Collect remaining output
            if self._stdout_thread:
                self._stdout_thread.join(timeout=1)
            if self._stderr_thread:
                self._stderr_thread.join(timeout=1)

            stdout = self._collect_output()
            stderr = ""  # stderr is in output queue
            
            self._exit_code = self._process.returncode
            self._status = ProcessStatus.IDLE  # Terminal is ready for next command

            return {
                "ok": self._exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": self._exit_code,
                "status": self._status,
            }

        except FileNotFoundError:
            self._status = ProcessStatus.FAILED
            self._exit_code = 127
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Command not found: {command.split()[0]}",
                "exit_code": 127,
                "status": ProcessStatus.FAILED,
            }
        except Exception as e:
            self._status = ProcessStatus.FAILED
            self._exit_code = -1
            return {
                "ok": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "status": ProcessStatus.FAILED,
            }
        finally:
            self._process = None

    def _collect_output(self) -> str:
        """Collect all output from the queue."""
        lines = []
        while not self._output_queue.empty():
            try:
                stream, line = self._output_queue.get_nowait()
                if stream == "stdout":
                    lines.append(line)
            except queue.Empty:
                break
        return "".join(lines)

    def _handle_builtin(self, command: str) -> Optional[dict]:
        """Handle built-in commands that don't need subprocess."""
        parts = command.strip().split()
        if not parts:
            return None

        cmd = parts[0]

        if cmd == "cd":
            return self._builtin_cd(parts[1:])
        elif cmd == "pwd" and len(parts) == 1:
            return self._builtin_pwd()
        elif cmd == "clear" and len(parts) == 1:
            return {"ok": True, "stdout": "\033[2J\033[H", "stderr": "", "exit_code": 0, "status": ProcessStatus.IDLE}
        elif cmd == "help" and len(parts) == 1:
            return self._builtin_help()
        elif cmd == "exit" and len(parts) == 1:
            return self._builtin_exit()

        return None

    def _builtin_cd(self, args: list) -> dict:
        """Change directory with path traversal protection."""
        if not args:
            target = HOME_DIR
        else:
            target_str = " ".join(args)
            if target_str == "~":
                target = HOME_DIR
            elif target_str.startswith("~/"):
                target = HOME_DIR / target_str[2:]
            else:
                target = self._cwd / target_str

        # Resolve and validate
        try:
            target = target.resolve()
        except (OSError, ValueError) as e:
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"cd: {target_str}: {e}",
                "exit_code": 1,
                "status": ProcessStatus.FAILED,
            }

        # Security: prevent traversal outside HOME_DIR for built-in cd
        # Note: shell commands can still access broader filesystem per Android OS
        if not str(target).startswith(str(HOME_DIR)):
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"cd: cannot access '{target_str}': outside home directory",
                "exit_code": 1,
                "status": ProcessStatus.FAILED,
            }

        if not target.exists():
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"cd: {target_str}: No such file or directory",
                "exit_code": 1,
                "status": ProcessStatus.FAILED,
            }

        if not target.is_dir():
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"cd: {target_str}: Not a directory",
                "exit_code": 1,
                "status": ProcessStatus.FAILED,
            }

        self._cwd = target
        return {"ok": True, "stdout": "", "stderr": "", "exit_code": 0, "status": ProcessStatus.IDLE}

    def _builtin_pwd(self) -> dict:
        """Print working directory."""
        # Show relative path from HOME_DIR for readability
        try:
            rel = self._cwd.relative_to(HOME_DIR)
            display = f"~/{rel}" if str(rel) != "." else "~"
        except ValueError:
            display = str(self._cwd)
        
        return {
            "ok": True,
            "stdout": f"{display}\n",
            "stderr": "",
            "exit_code": 0,
            "status": ProcessStatus.IDLE,
        }

    def _builtin_help(self) -> dict:
        """Show help message."""
        return {
            "ok": True,
            "stdout": HELP_TEXT,
            "stderr": "",
            "exit_code": 0,
            "status": ProcessStatus.IDLE,
        }

    def _builtin_exit(self, args=None) -> dict:
        """Exit terminal session."""
        return {
            "ok": True,
            "stdout": "Goodbye!\n",
            "stderr": "",
            "exit_code": 0,
            "status": ProcessStatus.EXITED,
        }

    def send_input(self, text: str) -> dict:
        """Send input to running process."""
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return {"ok": False, "error": "No process running"}

            try:
                self._process.stdin.write(text + "\n")
                self._process.stdin.flush()
                return {"ok": True}
            except (BrokenPipeError, OSError) as e:
                return {"ok": False, "error": str(e)}

    def stop(self) -> dict:
        """Stop running process (Ctrl+C equivalent)."""
        with self._lock:
            if not self._process or self._process.poll() is not None:
                return {"ok": True, "message": "No process running"}

            try:
                # Send SIGINT (Ctrl+C)
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._process.pid), signal.SIGINT)
                else:
                    self._process.send_signal(signal.SIGINT)
                
                # Wait briefly for graceful shutdown
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                    else:
                        self._process.kill()
                    self._process.wait()

                self._status = ProcessStatus.STOPPED
                self._exit_code = self._process.returncode
                return {"ok": True, "exit_code": self._exit_code}
            except Exception as e:
                return {"ok": False, "error": str(e)}

    def get_prompt(self) -> str:
        """Get shell prompt string."""
        try:
            rel = self._cwd.relative_to(HOME_DIR)
            path = f"~/{rel}" if str(rel) != "." else "~"
        except ValueError:
            path = str(self._cwd)
        return f"zmux:{path}$ "


# Global terminal session instance
_terminal_session: Optional[TerminalSession] = None


def get_session() -> TerminalSession:
    """Get or create the global terminal session."""
    global _terminal_session
    if _terminal_session is None:
        _terminal_session = TerminalSession()
    return _terminal_session
