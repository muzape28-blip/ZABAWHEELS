"""Interactive terminal session backed by the embedded Python runtime.

There is intentionally no PTY and no ``/system/bin/sh`` child here. Android
frequently marks app data noexec, which makes a shell unable to launch Python
scripts. Instead each completed line goes to :class:`PythonShell`.

Terminal personality
--------------------
The session has two modes, mirroring how Termux users experience it:

- **shell mode** (default, ``zmux:~$``): filesystem/zmux commands run
  directly; anything unrecognized is evaluated as Python (ZMUX's escape
  hatch, kept from the original single-mode design).
- **REPL mode** (``>>>``): entered with ``python``/``python3``; everything is
  Python, exactly like the real CPython REPL — ``ls`` is a NameError here.
  Leave with ``exit()``/``quit()`` or Ctrl+D.

Interactivity
-------------
Commands run on a dedicated worker thread so the input path stays live:

- **Ctrl+C** sets the cooperative interrupt flag, SIGINTs any in-flight
  subprocess pipeline (escalating to SIGKILL), and injects
  ``KeyboardInterrupt`` into the worker thread via
  ``PyThreadState_SetAsyncExc``. Pure-Python runaways stop immediately;
  long blocking C calls unblock once they return (documented limitation).
- **stdin**: while a command runs, typed lines queue as stdin — ``input()``
  works. Lines still queued when the command finishes become type-ahead
  commands, matching real terminal semantics.
- **history**: Up/Down (``ESC [ A`` / ``ESC [ B``) recall submitted lines.
"""
from __future__ import annotations

import codeop
import contextlib
import platform
import queue
import sys
import threading
from typing import Optional

from zmux import crash
from zmux.paths import HOME_DIR, RC_FILENAME, display_path, read_rc_lines, seed_examples
from zmux.python_shell import PythonShell


_SENTINEL_COMPILE_ERROR = object()
_CSI_FINAL_BYTES = frozenset(
    chr(c) for c in range(0x40, 0x7F)  # @A–Z[\]^_`a–z{|}~
)
_REPL_ENTER = {"python", "python3"}
_REPL_EXIT = {"exit", "quit", "exit()", "quit()"}


class _QueueInput:
    """File-like stdin backed by the session's queue (for ``input()``).

    Blocks in short slices so a Ctrl+C (or session stop) unblocks the read
    instead of hanging the worker thread forever.
    """

    def __init__(self, session: "PTYTerminalSession") -> None:
        self._session = session

    def readline(self, _size: int = -1) -> str:
        session = self._session
        # Push any partial line (typically the input() prompt itself, which
        # has no trailing newline) before blocking. Without this the user is
        # asked a question they cannot see and the terminal looks frozen.
        stream = getattr(sys.stdout, "flush", None)
        if stream is not None:
            with contextlib.suppress(Exception):
                sys.stdout.flush()
        while True:
            if session.shell._interrupt.is_set():
                raise KeyboardInterrupt
            if not session.is_running:
                raise EOFError
            try:
                return session._stdin_queue.get(timeout=0.05) + "\n"
            except queue.Empty:
                continue

    def isatty(self) -> bool:
        return True


def _inject_keyboard_interrupt(thread: Optional[threading.Thread]) -> bool:
    """Raise KeyboardInterrupt asynchronously inside ``thread``.

    Same mechanism debuggers use to break into running code. Unavailable
    ctypes (or a dead thread) simply returns False; the cooperative flag in
    :meth:`PythonShell.interrupt` still covers stdin/subprocess waits.
    """
    if thread is None or not thread.is_alive():
        return False
    try:
        import ctypes
    except ImportError:
        return False
    result = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread.ident or 0), ctypes.py_object(KeyboardInterrupt)
    )
    if result > 1:  # pragma: no cover - corrupted state, undo per CPython docs
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread.ident or 0), None)
        return False
    return result == 1


class PTYTerminalSession:
    """Persistent, Python-native interactive terminal session.

    The public name is retained for compatibility with the websocket server,
    but this is a virtual terminal rather than a Unix PTY.
    """

    HISTORY_LIMIT = 500

    def __init__(self, ws_server, emit=None):
        self.ws_server = ws_server
        #: Where output goes. The session manager injects a callback that
        #: forwards to the websocket only while this session is on screen, so
        #: background sessions keep running without corrupting the display.
        #: Defaults to broadcasting directly (single-session / test use).
        self._emit_output = emit if emit is not None else ws_server.broadcast
        self.shell = PythonShell()
        self.is_running = False
        self.process = None  # Compatibility: no shell process is spawned.
        self.lock = threading.RLock()
        self.buffer_lock = threading.Lock()
        self.scrollback_buffer = bytearray()
        self.scrollback_max_size = 32768

        self._line_buffer = ""
        self._python_lines: list[str] = []
        self._mode = "shell"  # "shell" | "repl"
        self._history: list[str] = []
        self._history_index: Optional[int] = None
        self._history_stash = ""
        self._esc_state = ""  # "" | "esc" | "csi"

        self._command_queue: queue.Queue = queue.Queue()
        self._stdin_queue: queue.Queue[str] = queue.Queue()
        self._stdin = _QueueInput(self)
        self._busy = threading.Event()
        self._exec_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            # Only a session that owns the websocket outright registers here.
            # Under the session manager, routing belongs to the manager, so
            # a newly created background session must not steal input.
            if self._emit_output is self.ws_server.broadcast:
                self.ws_server.register_callbacks(on_data=self.write_input, on_resize=self.resize)
            self._exec_thread = threading.Thread(
                target=self._exec_loop, daemon=True, name="ZMUX-Terminal-Exec"
            )
            self._exec_thread.start()
            banner = "ZMUX terminal -- Python runs in the embedded runtime.\r\n"
            if seed_examples(HOME_DIR) is not None:
                banner += "Examples for a quick start: examples/\r\n"
            banner += "Type 'python' to enter the REPL, 'help' for commands.\r\n"
            self._emit(banner.encode("utf-8"))
            self._run_rc()
            self._emit_prompt()

    def _run_rc(self) -> None:
        """Execute ``~/.zmuxrc`` before the first prompt, if present.

        ZMUX has no login shell, so this is the only hook users have for
        aliases, imports or environment tweaks. Failures are reported but
        never prevent the terminal from starting.
        """
        lines = read_rc_lines(HOME_DIR)
        if not lines:
            return
        self.shell.output_sink = self._emit
        try:
            for line in lines:
                try:
                    result = self.shell.execute(line)
                except Exception as error:  # a bad rc must not kill startup
                    self._emit(f"{RC_FILENAME}: {error}\r\n".encode("utf-8", errors="replace"))
                    continue
                streamed = result.get("streamed", ())
                pending = "".join(
                    result.get(name, "") for name in ("stdout", "stderr")
                    if name not in streamed
                )
                if pending:
                    self._emit(pending.replace("\n", "\r\n").encode("utf-8", errors="replace"))
        finally:
            self.shell.output_sink = None

    def stop(self) -> None:
        with self.lock:
            self.is_running = False
            self._line_buffer = ""
            self._python_lines.clear()
            self.shell.interrupt()
            self._command_queue.put(None)  # poison pill for the worker

    def resize(self, cols: int, rows: int) -> None:
        # No child PTY needs ioctl(TIOCSWINSZ); we just track the width for
        # rendering decisions (e.g. Rich tracebacks).
        if cols > 0:
            self.shell.width = max(20, cols)

    # ------------------------------------------------------------- output
    def get_scrollback(self) -> bytes:
        with self.buffer_lock:
            return bytes(self.scrollback_buffer)

    def _emit(self, data: bytes) -> None:
        # Scrollback is always recorded, even when this session is in the
        # background — that is what makes switching back able to repaint.
        with self.buffer_lock:
            self.scrollback_buffer.extend(data)
            if len(self.scrollback_buffer) > self.scrollback_max_size:
                del self.scrollback_buffer[: -self.scrollback_max_size]
        self._emit_output(data)

    def _prompt(self) -> str:
        if self._mode == "repl":
            return ">>> "
        return f"zmux:{display_path(self.shell.cwd)}$ "

    def _emit_prompt(self) -> None:
        self._emit(self._prompt().encode("utf-8"))

    # -------------------------------------------------------------- input
    def write_input(self, data: bytes) -> None:
        """Process real keyboard input, queue completed lines/keystrokes."""
        with self.lock:
            if not self.is_running:
                return
            text = data.decode("utf-8", errors="replace")
            for char in text:
                self._handle_char(char)

    def _handle_char(self, char: str) -> None:
        # Escape-sequence parser first: arrow keys arrive as ESC [ A/B ...
        if self._esc_state or char == "\x1b":
            self._handle_escape_char(char)
            return
        if char == "\x03":  # Ctrl+C
            self._interrupt_running()
        elif char == "\x04":  # Ctrl+D
            if self._mode == "repl" and not self._line_buffer and not self._busy.is_set():
                self._leave_repl()
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

    def _handle_escape_char(self, char: str) -> None:
        if not self._esc_state and char == "\x1b":
            self._esc_state = "esc"
            return
        if self._esc_state == "esc":
            # CSI (ESC [ …) is the xterm.js default; SS3 (ESC O …) covers
            # application-cursor mode — arrows arrive in both dialects.
            self._esc_state = {"[": "csi", "O": "ss3"}.get(char, "")
            return
        if self._esc_state == "ss3":
            if char == "A":
                self._history_step(-1)
            elif char == "B":
                self._history_step(+1)
            self._esc_state = ""
            return
        # csi: swallow until a final byte arrives
        if char in _CSI_FINAL_BYTES:
            if char == "A":
                self._history_step(-1)
            elif char == "B":
                self._history_step(+1)
            self._esc_state = ""

    # ------------------------------------------------------------ history
    def _history_step(self, direction: int) -> None:
        if self._busy.is_set() or not self._history:
            return
        if self._history_index is None:
            if direction > 0:
                return
            self._history_stash = self._line_buffer
            self._history_index = len(self._history)
        new_index = self._history_index + direction
        if new_index >= len(self._history):
            self._history_index = None
            self._replace_line(self._history_stash)
            return
        self._history_index = max(0, new_index)
        self._replace_line(self._history[self._history_index])

    def _replace_line(self, text: str) -> None:
        self._line_buffer = text
        self._emit(b"\r\x1b[K" + text.encode("utf-8"))

    def _history_record(self, line: str) -> None:
        if line and (not self._history or self._history[-1] != line):
            self._history.append(line)
            del self._history[: -self.HISTORY_LIMIT]
        self._history_index = None

    # --------------------------------------------------------- submission
    def _submit_line(self, line: str) -> None:
        if self._busy.is_set():
            # A command is running: the line is stdin for it (or type-ahead).
            self._stdin_queue.put(line)
            return
        stripped = line.strip()
        if not stripped:
            if self._python_lines:
                # A blank line closes an open compound block, exactly like
                # the CPython REPL — hand it to the worker to finish the block.
                self._command_queue.put((line, self._mode))
            else:
                self._emit_prompt()
            return
        self._history_record(stripped)
        if self._mode == "shell" and stripped in _REPL_ENTER:
            self._enter_repl()
            return
        if self._mode == "repl" and stripped in _REPL_EXIT:
            self._leave_repl()
            return
        self._command_queue.put((line, self._mode))

    def _enter_repl(self) -> None:
        self._mode = "repl"
        self._emit(
            f"Python {platform.python_version()} (embedded ZMUX runtime)\r\n"
            'Type "exit()" or Ctrl+D to return to the shell\r\n'.encode("utf-8")
        )
        self._emit_prompt()

    def _leave_repl(self) -> None:
        self._mode = "shell"
        self._python_lines.clear()
        self._emit_prompt()

    # ----------------------------------------------------------- interrupt
    def _interrupt_running(self) -> None:
        self._line_buffer = ""
        self._python_lines.clear()
        self._emit(b"^C\r\n")
        if self._busy.is_set():
            self.shell.interrupt()  # flag + SIGINT pipeline, escalating
            # Only inject into pure-Python execution. When a subprocess
            # pipeline owns the wait, signals above cancel it deterministically
            # and injecting here could eat the pipeline's result instead.
            if not self.shell.has_running_processes():
                _inject_keyboard_interrupt(self._exec_thread)
        else:
            self._emit_prompt()

    # ------------------------------------------------------------- worker
    def _shell_commands(self) -> set:
        # python/python3 with arguments (`python file.py`, `python -c ...`)
        # route to the real script runner; the bare-word REPL entry was
        # already intercepted in _submit_line and never reaches the worker.
        return set(self.shell.commands) | {"pip", "zpip", "help", "zmux-info", "python", "python3"}

    def _exec_loop(self) -> None:
        """Single worker: executes queued command lines one at a time."""
        while True:
            try:
                item = self._command_queue.get()
            except KeyboardInterrupt:
                # Async injection arriving at idle (between commands) is
                # normal — swallow it, never let the worker thread die here.
                continue
            if item is None or not self.is_running:
                return
            line, mode = item
            # Snapshot BEFORE marking busy: a Ctrl+C landing afterwards bumps
            # the epoch, so the tagged clear below refuses to wipe it — the
            # spawn-race and pipeline checks rely on the flag surviving.
            epoch = self.shell._interrupt_epoch
            self._busy.set()
            self.shell.clear_interrupt(epoch=epoch)
            try:
                self._run_line(line, mode)
            except KeyboardInterrupt:
                # A Ctrl+C injection may land just after the command finished
                # (async delivery is racy by nature) — it must never kill the
                # worker thread, just render like an interrupted command.
                self._emit(b"KeyboardInterrupt\r\n")
                self.shell._interrupt.set()
                self._emit_prompt()
            except Exception as error:  # never let the worker die
                # Keeping the worker alive is right, but silently discarding
                # the traceback made real bugs unreportable — persist it.
                crash.record("terminal-exec", type(error), error, error.__traceback__)
                self._emit(f"[session error: {error}]\r\n".encode("utf-8", errors="replace"))
                self._emit_prompt()
            finally:
                self._finish_command()

    def _run_line(self, line: str, mode: str) -> None:
        if mode == "repl":
            self._run_python_line(line)
            return
        first = line.lstrip().split(maxsplit=1)[0] if line.strip() else ""
        if first in self._shell_commands() or self.shell._is_external_command(first):
            self._execute_and_render(line)
        else:
            self._run_python_line(line)  # shell mode Python escape hatch

    def _run_python_line(self, line: str) -> None:
        candidate = "\n".join([*self._python_lines, line])
        try:
            pending = codeop.compile_command(candidate, "<zmux>", "exec")
        except (SyntaxError, OverflowError, ValueError):
            pending = _SENTINEL_COMPILE_ERROR  # execute to render the real error
        if pending is None:
            self._python_lines.append(line)
            self._emit(b"... ")
            self._busy.clear()  # awaiting more input, not running
            return
        self._execute_and_render(candidate, force_python=True)
        self._python_lines.clear()

    def _execute_and_render(self, source: str, force_python: bool = False) -> None:
        """Run one line with output streaming live to the websocket.

        ``output_sink`` makes the shell push text as it is produced, so a
        progressive command is visible while it runs and — critically — an
        ``input()`` prompt reaches the screen *before* the read blocks.
        The result dict still carries the full text; it is deliberately not
        re-emitted here or every line would appear twice.
        """
        self.shell.stdin_provider = self._stdin
        self.shell.output_sink = self._emit
        try:
            result = self.shell.execute(source, force_python=force_python)
        finally:
            self.shell.stdin_provider = None
            self.shell.output_sink = None
        # Built-in commands (ls, echo, cd...) and zpip return their text
        # without touching the sink, so they still need rendering here. The
        # `streamed` tuple names what already reached the screen.
        streamed = result.get("streamed", ())
        pending = "".join(
            result.get(name, "") for name in ("stdout", "stderr") if name not in streamed
        )
        if pending:
            self._emit(pending.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8", errors="replace"))
        self._emit_prompt()

    def _finish_command(self) -> None:
        interrupted = self.shell._interrupt.is_set()
        self._busy.clear()
        if interrupted:
            # After Ctrl+C, discard type-ahead instead of executing stale lines.
            self._drain(self._stdin_queue)
            self.shell.clear_interrupt()
            return
        # Real-terminal type-ahead: lines typed while the command ran become
        # the next commands, in order.
        for leftover in self._drain(self._stdin_queue):
            self._submit_line(leftover)

    @staticmethod
    def _drain(source: "queue.Queue[str]") -> list:
        items = []
        while True:
            try:
                items.append(source.get_nowait())
            except queue.Empty:
                return items


_pty_session: Optional[PTYTerminalSession] = None


def get_pty_session(ws_server) -> PTYTerminalSession:
    """Return the single legacy session.

    Superseded by :mod:`zmux.sessions`, which supports several sessions and
    is what the server and websocket layer now use. Kept for callers that
    only ever want one terminal (and for existing tests).
    """
    global _pty_session
    if _pty_session is None:
        _pty_session = PTYTerminalSession(ws_server)
    return _pty_session
