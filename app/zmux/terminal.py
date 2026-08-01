"""ZMUX Terminal Session (REST API transport).

Manages one persistent terminal session for the REST endpoints
(``/api/exec``, ``/api/status`` ...). Commands are executed by the embedded
Python-native shell (:class:`zmux.python_shell.PythonShell`): Python source
runs in-process, filesystem commands use real Python filesystem APIs, and
external programs are only ever started by absolute path — never via
``/system/bin/sh``.

This module used to drive a streaming ``subprocess.Popen`` command engine;
that design was replaced by PythonShell. A few stream-oriented helpers
(out-of-band stdin, Ctrl+C cancellation) survive only as inert stubs because
no long-running process currently exists; a real cancellation mechanism is
planned work.

Threat model: commands execute within app-private storage. Native Android
utilities invoked by absolute path can see more than the app-private area,
per Android OS policy.
"""

import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional

from zmux.paths import BIN_DIR, HOME_DIR, display_path


HELP_TEXT = """ZMUX Terminal v1.0.0

Built-in commands:
  help          Show this help message
  clear         Clear terminal screen
  pwd           Print working directory
  cd <dir>      Change directory
  exit / quit   In the Python REPL: back to the shell. In shell mode these
                behave like CPython's builtins (exit() / Ctrl+D to leave)

Python-native terminal:
  Type Python expressions or statements directly (this is the primary REPL).
  python <file> Run a Python script in the embedded CPython runtime
  python -c "..." Execute Python code in the embedded CPython runtime
  pip           Python package manager (if available)

Filesystem commands:
  ls, cat, mkdir, touch, cp, mv, rm, echo, env, which, uname
  These use real Python filesystem APIs. Native Android utilities are invoked
  directly by absolute path; ZMUX never starts /system/bin/sh.

ZMUX Package Manager:
  zpip search <query>     Search curated index, installs, and PyPI
  zpip info <name>        Show package info
  zpip install <name>     Install package
  zpip list               List installed packages
  zpip verify <name>      Verify package installation
  zpip uninstall <name>   Uninstall package
  zpip doctor             Check system health

Runtime Info:
  zmux-info               Show runtime fingerprint

Storage:
  zmux-setup-storage      Request Android storage access and link the shared
                          directories into ~/storage (opt-in; ZMUX stays
                          sandboxed until you run it)

Alpine Linux shell (real PTY):
  linux                   Open the real interactive Alpine shell — a genuine
                          PTY (proot -> /bin/sh -l). vim, htop, less and tmux
                          work. 'exit' returns to the ZMUX console; the ZMX⇄
                          toolbar key detaches and returns immediately.
  linux <cmd...>          Run one shell command inside Alpine,
                          e.g. linux apk add openssh-client
  alpine <cmd...>         Alias of linux
  linux-setup             Install the Alpine userland (download ~4 MiB,
                          SHA-512 verified) — enables git and linux below
  git <args...>           Real git: clone, branch, checkout, push — normal
                          syntax. e.g. git clone <url>
  gates                   Run the strict on-device acceptance probe (G1-G5)
  zmux-pty-probe          Run the real-PTY acceptance probe (pty1-pty6)

Startup file:
  ~/.zmuxrc     Runs line by line when a session starts (imports, variables,
                commands). ZMUX has no login shell, so this replaces .bashrc.

Note: This terminal executes real system commands within app-private storage.
Standard shell commands can access areas permitted by Android OS.
There is no PTY, so full-screen programs (vim, htop, less) do not work.
"""


class ProcessStatus:
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    STOPPED = "stopped"
    FAILED = "failed"
    EXITED = "exited"


class TerminalSession:
    """Manages a persistent terminal session backed by the embedded Python shell.

    The session owns the working directory and the last exit code. Python
    state (variables, imports) persists across commands, giving REPL
    semantics; ``self._process`` is a compatibility placeholder for the
    retired subprocess engine and is always ``None`` today.
    """

    def __init__(self):
        self._cwd = HOME_DIR
        # The primary executor is embedded CPython, not /system/bin/sh.
        from zmux.python_shell import PythonShell
        self._python_shell = PythonShell(self._cwd)
        self._process: Optional[subprocess.Popen] = None
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

        # ``exit`` ends the virtual terminal session; it is not delegated to a
        # shell process. Preserve a requested numeric exit code for API users.
        exit_parts = command.split()
        if exit_parts and exit_parts[0] == "exit":
            try:
                code = int(exit_parts[1]) if len(exit_parts) > 1 else 0
            except ValueError:
                code = 2
            self._exit_code = code
            self._status = ProcessStatus.EXITED
            return {"ok": code == 0, "stdout": "Goodbye!\n", "stderr": "", "exit_code": code, "status": self._status}

        # PythonShell is the only command path.  In particular, do not use
        # shell=True: Android's shell cannot execute files from many app-private
        # mounts.  PythonShell executes Python in-process and invokes Android
        # utilities directly by absolute path when a native utility is needed.
        result = self._python_shell.execute(command, timeout=timeout)
        self._cwd = self._python_shell.cwd
        self._exit_code = result.get("exit_code")
        self._status = ProcessStatus.IDLE
        result["status"] = self._status
        return result

    def send_input(self, text: str) -> dict:
        """Send input to a running process.

        Currently inert: no long-lived streaming process exists, so this
        always reports that nothing is running. Kept as part of the REST API
        surface; a real stdin path is planned work.
        """
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
        """Stop the running process (Ctrl+C equivalent).

        Currently inert for the same reason as :meth:`send_input`: there is no
        child process to signal. Kept for API compatibility; real cancellation
        is planned work.
        """
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
        return f"zmux:{display_path(self._cwd)}$ "


# Global terminal session instance
_terminal_session: Optional[TerminalSession] = None


def get_session() -> TerminalSession:
    """Get or create the global terminal session."""
    global _terminal_session
    if _terminal_session is None:
        _terminal_session = TerminalSession()
    return _terminal_session
