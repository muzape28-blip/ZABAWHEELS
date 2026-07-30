"""Python-native command interpreter used by the ZMUX terminal.

This module deliberately never starts ``/system/bin/sh``.  Python source is
executed by the embedded p4a CPython runtime and Android utilities, when
needed, are started directly with ``subprocess`` and an absolute executable
path.
"""
from __future__ import annotations

import ast
import contextlib
import io
import os
import platform
import shlex
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Callable

from zmux.paths import HOME_DIR


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

    def execute(self, line: str, timeout: float | None = None) -> dict:
        line = line.strip()
        if not line:
            return self._result()
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
            if command == "python":
                return self._exec_python_command(parts[1:])
            if command in {"pip", "zpip", "help", "zmux-info"}:
                return self._exec_zmux_command(command, parts[1:])
            # A known executable or a line containing shell operators is a
            # command. Everything else is genuine Python source.
            if self._is_external_command(command) or any(x in line for x in ("|", ">", "<")):
                return self._exec_subprocess(line, timeout)
            return self._exec_python(line)
        except (OSError, ValueError) as exc:
            return self._result(stderr=f"{command}: {exc}\n", code=1)

    def _result(self, stdout: str = "", stderr: str = "", code: int = 0) -> dict:
        return {"ok": code == 0, "stdout": stdout, "stderr": stderr,
                "exit_code": code, "status": "idle"}

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

    def _cmd_rm(self, args: list[str]) -> str:
        recursive, force = any("r" in a for a in args if a.startswith("-")), any("f" in a for a in args if a.startswith("-"))
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
        return "".join((self._find_executable(arg) or "") + ("\n" if self._find_executable(arg) else "") for arg in args)
    def _cmd_uname(self, args: list[str]) -> str: return platform.platform() + "\n"

    def _cmd_cd(self, args: list[str]) -> str:
        if len(args) > 1: raise ValueError("too many arguments")
        target = self._path(args[0]) if args else HOME_DIR
        if not target.is_dir(): raise FileNotFoundError(target)
        self.cwd = target
        return ""

    def _exec_python(self, source: str) -> dict:
        out, err = io.StringIO(), io.StringIO()
        try:
            # eval gives REPL-like expression output; exec handles statements.
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = compile(source, "<zmux>", "eval")
                except SyntaxError:
                    code = compile(source, "<zmux>", "exec")
                    exec(code, self.globals, self.globals)
                else:
                    value = eval(code, self.globals, self.globals)
                    if value is not None: print(repr(value))
            return self._result(out.getvalue(), err.getvalue())
        except BaseException:
            return self._result(out.getvalue(), err.getvalue() + traceback.format_exc(), 1)

    def _exec_python_command(self, args: list[str]) -> dict:
        if not args:
            return self._result(stdout=f"Python {sys.version}\nUse Python expressions directly at this prompt.\n")
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
        if "/" in command:
            return command if os.path.isfile(command) and os.access(command, os.X_OK) else None
        for directory in ("/system/bin", "/system/xbin", "/vendor/bin", "/sbin", "/bin", "/usr/bin"):
            candidate = os.path.join(directory, command)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK): return candidate
        return None

    def _is_external_command(self, command: str) -> bool: return self._find_executable(command) is not None

    def _exec_subprocess(self, line: str, timeout: float | None) -> dict:
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
        try:
            if input_file: source_handle = input_file.open("r", encoding="utf-8")
            for index, stage in enumerate(cleaned):
                executable = self._find_executable(stage[0])
                if not executable: return self._result(stderr=f"{stage[0]}: command not found\n", code=127)
                stdin = previous.stdout if previous else source_handle
                proc = subprocess.Popen([executable, *stage[1:]], cwd=self.cwd, stdin=stdin,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if previous: previous.stdout.close()
                processes.append(proc); previous = proc
            stdout, stderr = processes[-1].communicate(timeout=timeout)
            for proc in processes[:-1]: proc.wait(timeout=timeout)
            if output_file:
                with output_file.open("a" if append else "w", encoding="utf-8") as handle: handle.write(stdout)
                stdout = ""
            code = next((p.returncode for p in processes if p.returncode), 0)
            return self._result(stdout, stderr, code)
        except subprocess.TimeoutExpired:
            for proc in processes: proc.kill()
            return self._result(stderr=f"Command timed out after {timeout}s\n", code=1)
