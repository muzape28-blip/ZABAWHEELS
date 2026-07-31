"""Python-native command interpreter used by the ZMUX terminal.

This module deliberately never starts ``/system/bin/sh``.  Python source is
executed by the embedded p4a CPython runtime and Android utilities, when
needed, are started directly with ``subprocess`` and an absolute executable
path.
"""
from __future__ import annotations

import contextlib
import io
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable

from zmux.env import build_env, build_path
from zmux.paths import HOME_DIR
from zmux.streams import StreamingWriter


# --- Optional Rich rendering (DX polish) --------------------------------------
# Rich is a pure-python universal wheel; when installed (e.g. via
# ``zpip install rich``) tracebacks render syntax-highlighted. Everything
# degrades to plain ``traceback.format_exc()`` output when it is absent.
_RICH_UNSET = object()
_rich_impl = _RICH_UNSET


def _get_rich():
    """Import rich lazily, once. Returns (Console, Traceback) or None."""
    global _rich_impl
    if _rich_impl is _RICH_UNSET:
        try:
            from rich.console import Console
            from rich.traceback import Traceback
            _rich_impl = (Console, Traceback)
        except Exception:
            _rich_impl = None
    return _rich_impl


class PythonShell:
    """A persistent Python REPL with real Python filesystem commands.

    ``execute`` returns terminal-style dictionaries so it can be used by both
    the HTTP endpoint and the websocket terminal.  No output is fabricated:
    output is either produced by CPython, Python's filesystem APIs, or a real
    child process.
    """

    def __init__(self, cwd: Path | None = None):
        self.cwd = Path(cwd or HOME_DIR).resolve()
        self.globals = {"__name__": "__main__", "__package__": None, "__builtins__": __builtins__}
        self.commands: dict[str, Callable[[list[str]], str]] = {
            "ls": self._cmd_ls, "mkdir": self._cmd_mkdir, "rm": self._cmd_rm,
            "cp": self._cmd_cp, "mv": self._cmd_mv, "cat": self._cmd_cat,
            "touch": self._cmd_touch, "echo": self._cmd_echo, "pwd": self._cmd_pwd,
            "cd": self._cmd_cd, "clear": self._cmd_clear, "env": self._cmd_env,
            "which": self._cmd_which, "uname": self._cmd_uname,
        }
        # --- Interactivity / cancellation infrastructure -----------------------
        #: Terminal width reported by the front-end (used by Rich rendering).
        self.width = 80
        #: Optional file-like stdin provider installed while user code runs;
        #: the websocket terminal feeds it so ``input()`` works.
        self.stdin_provider = None
        #: Optional callback taking already-encoded terminal bytes. When set,
        #: command output streams to it as it is produced instead of being
        #: buffered until the command finishes. The returned result dict still
        #: carries the complete text, so REST callers are unaffected.
        self.output_sink = None
        #: Cooperative Ctrl+C: set by :meth:`interrupt`; checked by the stdin
        #: provider and combined with async KeyboardInterrupt injection.
        self._interrupt = threading.Event()
        #: Monotonic counter bumped on every Ctrl+C. Lets the execution loop
        #: distinguish "flag set before this command started" (discardable)
        #: from "flag set for this command" without a busy-state race window.
        self._interrupt_epoch = 0
        #: In-flight pipeline processes, so :meth:`interrupt` can signal them.
        self._procs: list[subprocess.Popen] = []
        self._procs_lock = threading.Lock()
        #: >0 while inside _exec_subprocess (even between spawn and register),
        #: so Ctrl+C classification never misreads a pipeline as pure Python.
        self._subprocess_depth = 0

    # ------------------------------------------------------------------ cancel
    def interrupt(self) -> None:
        """Cooperative Ctrl+C.

        Sets the interrupt flag (stdin providers stop blocking) and forwards
        SIGINT to any in-flight pipeline process group, escalating to SIGKILL.
        Pure-Python runaway code is interrupted by the caller injecting
        ``KeyboardInterrupt`` into the execution thread (see pty_session).
        """
        self._interrupt_epoch += 1
        self._interrupt.set()
        with self._procs_lock:
            victims = [p for p in self._procs if p.poll() is None]
        for proc in victims:
            with contextlib.suppress(ProcessLookupError, OSError):
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                else:
                    proc.send_signal(signal.SIGINT)

        def _escalate() -> None:
            for proc in victims:
                if proc.poll() is not None:
                    continue
                with contextlib.suppress(ProcessLookupError, OSError):
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()

        timer = threading.Timer(1.5, _escalate)
        timer.daemon = True
        timer.start()

    def has_running_processes(self) -> bool:
        """True while subprocess execution owns the worker (pre-spawn counts)."""
        with self._procs_lock:
            if self._subprocess_depth > 0:
                return True
            return any(p.poll() is None for p in self._procs)

    def clear_interrupt(self, epoch: int | None = None) -> None:
        """Reset the Ctrl+C latch.

        With ``epoch``, only clears when no *newer* interrupt arrived since
        that epoch — a Ctrl+C pressed mid-startup must survive loop setup.
        """
        if epoch is None or epoch == self._interrupt_epoch:
            self._interrupt.clear()

    def execute(self, line: str, timeout: float | None = None, force_python: bool = False) -> dict:
        line = line.strip()
        if not line:
            return self._result()
        if force_python:
            # REPL mode evaluates *everything* as Python — command builtins
            # are intentionally not consulted (`ls` must be a NameError there).
            return self._exec_python(line)
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return self._result(stderr=f"parse error: {exc}\n", code=2)
        if not parts:
            return self._result()
        command = parts[0]
        try:
            # Operators need the pipeline/redirection executor even when the
            # first word is also a Python-backed built-in (for example
            # ``echo hello > file``).
            if any(x in line for x in ("|", ">", "<")):
                return self._exec_subprocess(line, timeout)
            if command in self.commands:
                return self._result(stdout=self.commands[command](parts[1:]))
            if command in {"python", "python3"}:
                return self._exec_python_command(parts[1:])
            if command in {"pip", "zpip", "help", "zmux-info"}:
                return self._exec_zmux_command(command, parts[1:])
            # A known external executable is run as a command. Everything else
            # is genuine Python source. (Lines containing |, >, < already went
            # to _exec_subprocess above — no need to test for them twice.)
            if self._is_external_command(command):
                return self._exec_subprocess(line, timeout)
            return self._exec_python(line)
        except (OSError, ValueError) as exc:
            return self._result(stderr=f"{command}: {exc}\n", code=1)

    def _result(self, stdout: str = "", stderr: str = "", code: int = 0,
                streamed: tuple = ()) -> dict:
        """Build a terminal-style result.

        ``streamed`` names the streams already pushed to :attr:`output_sink`
        while the command ran (``"stdout"`` / ``"stderr"``). The interactive
        terminal uses it to emit only what has *not* been shown yet, so
        streamed output is never duplicated and non-streaming paths (built-in
        commands, zpip) still render. REST callers ignore it and read the
        complete text from ``stdout``/``stderr`` as before.
        """
        return {"ok": code == 0, "stdout": stdout, "stderr": stderr,
                "exit_code": code, "status": "idle", "streamed": streamed}

    def _path(self, value: str) -> Path:
        value = os.path.expanduser(value)
        p = Path(value)
        return (p if p.is_absolute() else self.cwd / p).resolve()

    def _cmd_ls(self, args: list[str]) -> str:
        target = self._path(next((a for a in args if not a.startswith("-")), "."))
        show_all, long = "-a" in args or "-la" in args or "-al" in args, any("l" in a for a in args if a.startswith("-"))
        entries = sorted(target.iterdir(), key=lambda p: p.name)
        if not show_all:
            entries = [p for p in entries if not p.name.startswith(".")]
        if long:
            return "".join(f"{p.stat().st_mode:06o} {p.stat().st_size:>8} {p.name}\n" for p in entries)
        return "  ".join(p.name for p in entries) + ("\n" if entries else "")

    def _cmd_mkdir(self, args: list[str]) -> str:
        parents = "-p" in args
        values = [a for a in args if not a.startswith("-")]
        if not values: raise ValueError("missing operand")
        for value in values: self._path(value).mkdir(parents=parents, exist_ok=parents)
        return ""

    # Options accepted by _cmd_rm. Anything else is rejected loudly instead of
    # being fuzzy-matched: previously any "-" argument *containing* the letter
    # "r"/"f" enabled recursive/force (e.g. `rm -random-flag dir/` would have
    # recursively deleted a directory the user never asked to touch).
    _RM_LONG_FLAGS = {"--recursive", "--force"}
    _RM_CLUSTER_LETTERS = frozenset("rRf")

    def _cmd_rm(self, args: list[str]) -> str:
        recursive = force = False
        for arg in args:
            if not arg.startswith("-"):
                continue
            if arg in self._RM_LONG_FLAGS:
                if arg == "--recursive":
                    recursive = True
                else:
                    force = True
            elif arg[1:] and set(arg[1:]) <= self._RM_CLUSTER_LETTERS:
                recursive = recursive or "r" in arg or "R" in arg
                force = force or "f" in arg
            else:
                shown = arg if arg.startswith("--") else arg[1:]
                raise ValueError(f"invalid option -- '{shown}'")
        values = [a for a in args if not a.startswith("-")]
        if not values: raise ValueError("missing operand")
        for value in values:
            path = self._path(value)
            try:
                if path.is_dir() and not path.is_symlink():
                    if not recursive: raise IsADirectoryError(path)
                    shutil.rmtree(path)
                else: path.unlink()
            except FileNotFoundError:
                if not force: raise
        return ""

    def _cmd_cp(self, args: list[str]) -> str:
        if len(args) != 2: raise ValueError("usage: cp SOURCE DEST")
        src, dest = self._path(args[0]), self._path(args[1])
        if dest.is_dir(): dest /= src.name
        shutil.copy2(src, dest); return ""

    def _cmd_mv(self, args: list[str]) -> str:
        if len(args) != 2: raise ValueError("usage: mv SOURCE DEST")
        shutil.move(str(self._path(args[0])), str(self._path(args[1]))); return ""

    def _cmd_cat(self, args: list[str]) -> str:
        if not args: raise ValueError("missing operand")
        return "".join(self._path(arg).read_text(encoding="utf-8") for arg in args)

    def _cmd_touch(self, args: list[str]) -> str:
        if not args: raise ValueError("missing operand")
        for arg in args: self._path(arg).touch(exist_ok=True)
        return ""

    def _cmd_echo(self, args: list[str]) -> str: return " ".join(args) + "\n"
    def _cmd_pwd(self, args: list[str]) -> str: return str(self.cwd) + "\n"
    def _cmd_clear(self, args: list[str]) -> str: return "\033[H\033[2J\033[3J"
    def _cmd_env(self, args: list[str]) -> str: return "".join(f"{k}={v}\n" for k, v in sorted(os.environ.items()))
    def _cmd_which(self, args: list[str]) -> str:
        found = []
        for arg in args:
            resolved = self._find_executable(arg)  # single lookup per name
            if resolved:
                found.append(resolved)
        return "".join(path + "\n" for path in found)
    def _cmd_uname(self, args: list[str]) -> str: return platform.platform() + "\n"

    def _cmd_cd(self, args: list[str]) -> str:
        if len(args) > 1: raise ValueError("too many arguments")
        target = self._path(args[0]) if args else HOME_DIR
        # Keep the virtual terminal inside app-private storage. This avoids
        # exposing arbitrary device paths while preserving a real persistent
        # directory change for subsequent Python and subprocess operations.
        try:
            target.relative_to(HOME_DIR.resolve())
        except ValueError:
            raise PermissionError(f"cannot access '{target}': outside home directory")
        if not target.is_dir():
            raise FileNotFoundError(f"No such file or directory: '{target}'")
        self.cwd = target
        return ""

    @contextlib.contextmanager
    def _stdin_context(self):
        """Point sys.stdin at the installed provider while user code runs.

        (contextlib.redirect_stdin only exists on Python 3.12+; the embedded
        runtime is 3.11, so the swap is done by hand.)
        """
        if self.stdin_provider is None:
            yield
            return
        old_stdin = sys.stdin
        sys.stdin = self.stdin_provider
        try:
            yield
        finally:
            sys.stdin = old_stdin

    def _format_traceback(self) -> str:
        """Rich-rendered traceback when available; stdlib format otherwise."""
        rich = _get_rich()
        if rich is not None:
            Console, Traceback = rich
            buffer = io.StringIO()
            console = Console(
                file=buffer,
                force_terminal=True,
                width=max(20, self.width),
                color_system="standard",
                highlight=False,
            )
            console.print(Traceback(show_locals=False))
            return buffer.getvalue()
        return traceback.format_exc()

    def _make_sinks(self):
        """Return (stdout, stderr) sinks honouring :attr:`output_sink`.

        With a sink installed both streams stream live to the terminal; the
        text is still accumulated so the result dict stays complete.
        """
        if self.output_sink is None:
            return io.StringIO(), io.StringIO()
        return StreamingWriter(self.output_sink), StreamingWriter(self.output_sink)

    def _streamed(self) -> tuple:
        """Streams already forwarded live (empty when no sink is installed)."""
        return ("stdout", "stderr") if self.output_sink is not None else ()

    @staticmethod
    def _drain(stream) -> str:
        """Flush a sink (if streaming) and return everything written to it."""
        flush = getattr(stream, "flush", None)
        if flush is not None:
            flush()
        return stream.getvalue()

    def _exec_python(self, source: str) -> dict:
        out, err = self._make_sinks()
        try:
            # eval gives REPL-like expression output; exec handles statements.
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self._stdin_context():
                try:
                    code = compile(source, "<zmux>", "eval")
                except SyntaxError:
                    code = compile(source, "<zmux>", "exec")
                    exec(code, self.globals, self.globals)
                else:
                    value = eval(code, self.globals, self.globals)
                    if value is not None: print(repr(value))
            return self._result(self._drain(out), self._drain(err), streamed=self._streamed())
        except KeyboardInterrupt:
            # Ctrl+C (async-injected or raised by user/stdin): mirror CPython's
            # own REPL — a one-line notice and exit status 130, no traceback.
            # Written through the sink so it streams like any other output.
            err.write("KeyboardInterrupt\n")
            return self._result(self._drain(out), self._drain(err), 130, streamed=self._streamed())
        except SystemExit as exc:
            # Quiet exit like the real REPL exiting a subshell: no traceback
            # spam; propagate the numeric code when one was given.
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            return self._result(self._drain(out), self._drain(err), code, streamed=self._streamed())
        except BaseException:
            err.write(self._format_traceback())
            return self._result(self._drain(out), self._drain(err), 1, streamed=self._streamed())

    def _exec_python_command(self, args: list[str]) -> dict:
        if not args or args[0] in {"--version", "-V"}:
            suffix = "Use Python expressions directly at this prompt.\n" if not args else ""
            return self._result(stdout=f"Python {sys.version}\n{suffix}")
        if args[0] == "-c":
            if len(args) < 2: return self._result(stderr="python: argument expected for -c\n", code=2)
            return self._exec_python(args[1])
        script = self._path(args[0])
        try:
            source = script.read_text(encoding="utf-8")
        except OSError as exc:
            return self._result(stderr=f"python: {exc}\n", code=1)
        old_name, old_file, old_argv = self.globals.get("__name__"), self.globals.get("__file__"), sys.argv
        self.globals.update(__name__="__main__", __file__=str(script)); sys.argv = [str(script), *args[1:]]
        try: return self._exec_python(source)
        finally:
            self.globals["__name__"], self.globals["__file__"], sys.argv = old_name, old_file, old_argv

    def _exec_zmux_command(self, command: str, args: list[str]) -> dict:
        from zmux import cli
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([command, *args])
        return self._result(out.getvalue(), err.getvalue(), code)

    def _find_executable(self, command: str) -> str | None:
        """Resolve ``command`` against the ZMUX PATH.

        Uses the same PATH the children receive (BIN_DIR first, then the
        Android system directories), so the generated ``zpip``/``help``/
        ``zmux-info`` wrappers in BIN_DIR are reachable here too. Previously
        this searched a hardcoded list that omitted BIN_DIR entirely, making
        those wrappers unresolvable from the pipeline executor.
        """
        if "/" in command:
            return command if os.path.isfile(command) and os.access(command, os.X_OK) else None
        for directory in build_path().split(os.pathsep):
            candidate = os.path.join(directory, command)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK): return candidate
        return None

    #: Words that must never be treated as external programs, even when a
    #: same-named binary exists on PATH. `import` is the notorious one: it is
    #: ImageMagick's screenshot tool *and* the most common Python statement
    #: there is, so `import math` used to run ImageMagick and fail with
    #: "unable to open X server". The others are equally common statement
    #: keywords that ship as binaries on some systems.
    PYTHON_KEYWORD_GUARD = frozenset({
        "import", "from", "print", "exec", "eval", "assert", "del", "pass",
        "raise", "return", "yield", "lambda", "with", "while", "for", "if",
        "else", "elif", "try", "except", "finally", "class", "def", "global",
        "nonlocal", "not", "and", "or", "is", "in", "break", "continue",
        "async", "await", "match", "case", "true", "false", "none",
    })

    def _is_external_command(self, command: str) -> bool:
        """True when ``command`` should be run as an external program.

        Python statement keywords are excluded so shell mode's Python escape
        hatch keeps working regardless of what happens to be installed on the
        device's PATH.
        """
        if command in self.PYTHON_KEYWORD_GUARD:
            return False
        return self._find_executable(command) is not None

    def _exec_subprocess(self, line: str, timeout: float | None) -> dict:
        with self._procs_lock:
            self._subprocess_depth += 1
        try:
            return self._exec_subprocess_inner(line, timeout)
        finally:
            with self._procs_lock:
                self._subprocess_depth -= 1

    def _read_stdout_streaming(self, proc, timeout: float | None, stream: bool) -> str:
        """Read ``proc`` stdout to EOF, forwarding chunks to the terminal.

        Returns the complete text so the REST result stays identical. When no
        output sink is installed (REST calls) or the pipeline redirects to a
        file, this simply accumulates without emitting.

        ``readline()`` blocks, so the read runs on a helper thread and the
        caller waits with a deadline: ``timeout`` must keep working exactly as
        it did under ``communicate(timeout=...)``, which this replaced.
        """
        sink = self.output_sink if stream else None
        chunks: list = []
        handle = proc.stdout

        def pump() -> None:
            try:
                # Line-oriented: the smallest unit a terminal can usefully
                # render, and it avoids splitting escape sequences mid-line.
                for chunk in iter(handle.readline, ""):
                    chunks.append(chunk)
                    if sink is not None:
                        sink(chunk.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8", "replace"))
            except (ValueError, OSError):
                pass  # handle closed underneath us (timeout kill path)

        reader = threading.Thread(target=pump, daemon=True, name="ZMUX-Stdout-Reader")
        reader.start()
        reader.join(timeout=timeout)
        if reader.is_alive():
            # Still producing past the deadline: surface the same error the
            # previous communicate(timeout=...) call raised, and let the
            # caller's handler kill the pipeline.
            raise subprocess.TimeoutExpired(proc.args, timeout)
        with contextlib.suppress(Exception):
            handle.close()
        proc.wait(timeout=timeout)
        return "".join(chunks)

    def _exec_subprocess_inner(self, line: str, timeout: float | None) -> dict:
        # Parse pipelines ourselves; shell=True would reintroduce /system/bin/sh.
        lexer = shlex.shlex(line, posix=True, punctuation_chars="|<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
        stages, current = [], []
        for token in tokens:
            if token == "|": stages.append(current); current = []
            else: current.append(token)
        stages.append(current)
        if any(not stage for stage in stages): return self._result(stderr="invalid pipeline\n", code=2)
        # Redirection is parsed here rather than delegated to sh.  Restrict it
        # to input on the first stage and output on the final stage, matching
        # the common command-line forms: ``cat < in | grep x > out``.
        input_file = output_file = None
        append = False
        cleaned = []
        for index, stage in enumerate(stages):
            argv = []
            pos = 0
            while pos < len(stage):
                token = stage[pos]
                if token in {"<", ">", ">>"}:
                    if pos + 1 >= len(stage): return self._result(stderr=f"missing redirection target after {token}\n", code=2)
                    target = self._path(stage[pos + 1])
                    if token == "<" and index == 0: input_file = target
                    elif token in {">", ">>"} and index == len(stages) - 1:
                        output_file, append = target, token == ">>"
                    else: return self._result(stderr="redirection must be at pipeline edge\n", code=2)
                    pos += 2; continue
                argv.append(token); pos += 1
            if not argv: return self._result(stderr="invalid command\n", code=2)
            cleaned.append(argv)
        previous, processes, source_handle = None, [], None
        stderr_parts: list[str] = []
        stderr_threads: list[threading.Thread] = []
        try:
            if input_file: source_handle = input_file.open("r", encoding="utf-8")
            for index, stage in enumerate(cleaned):
                executable = self._find_executable(stage[0])
                if not executable: return self._result(stderr=f"{stage[0]}: command not found\n", code=127)
                stdin = previous.stdout if previous else source_handle
                # start_new_session gives every pipeline its own process group,
                # so interrupt() can killpg() it without signalling our own
                # server process (shared group would nuke the app itself).
                proc = subprocess.Popen([executable, *stage[1:]], cwd=self.cwd, stdin=stdin,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        env=build_env(self.cwd), start_new_session=True)
                if previous: previous.stdout.close()
                processes.append(proc); previous = proc
                # Register for Ctrl+C signalling (interrupt() kills the group).
                with self._procs_lock:
                    self._procs.append(proc)
                # Close the spawn race: Ctrl+C may have been pressed in the
                # gap between worker start and Popen returning.
                if self._interrupt.is_set() and proc.poll() is None:
                    with contextlib.suppress(ProcessLookupError, OSError):
                        if hasattr(os, "killpg"):
                            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                        else:
                            proc.send_signal(signal.SIGINT)
                # Drain every stderr concurrently. Waiting for only the last
                # pipeline member can deadlock when an earlier member writes a
                # large error stream.
                def drain(stream=proc.stderr):
                    stderr_parts.append(stream.read())
                reader = threading.Thread(target=drain, daemon=True)
                reader.start(); stderr_threads.append(reader)
            # Stream the final stage's stdout instead of communicate(): a
            # long-running child (ping, logcat, a build) must appear live in
            # the terminal, not arrive in one block when it exits. Redirected
            # output still goes to the file, never to the screen.
            did_stream = self.output_sink is not None and output_file is None
            stdout = self._read_stdout_streaming(
                processes[-1], timeout, stream=output_file is None
            )
            for proc in processes[:-1]: proc.wait(timeout=timeout)
            for reader in stderr_threads: reader.join(timeout=1)
            if output_file:
                with output_file.open("a" if append else "w", encoding="utf-8") as handle: handle.write(stdout)
                stdout = ""
            code = next((p.returncode for p in processes if p.returncode), 0)
            if code < 0:
                # Killed by a signal: say so plainly instead of printing a bare
                # negative exit code (Termux renders this as
                # "[Process completed (signal N)]").
                sig = -code
                hint = f"[process terminated by signal {sig}"
                if sig == 9:
                    hint += " — SIGKILL; on Android 12+ this is often the OS phantom-process limit"
                stderr_parts.append(hint + "]\n")
            # Only stdout was forwarded live; stderr is collected by the
            # drain threads and rendered by the caller after the fact.
            return self._result(stdout, "".join(stderr_parts), code,
                                streamed=("stdout",) if did_stream else ())
        except subprocess.TimeoutExpired:
            for proc in processes: proc.kill()
            return self._result(stderr=f"Command timed out after {timeout}s\n", code=1)
        finally:
            with self._procs_lock:
                self._procs = [p for p in self._procs if p not in processes]
            if source_handle: source_handle.close()
