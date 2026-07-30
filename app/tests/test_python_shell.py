"""Regression tests for the Python-native terminal executor."""
import threading
import time
from pathlib import Path

import pytest

from zmux.python_shell import PythonShell


def test_python_expression_executes_in_persistent_repl(tmp_path: Path):
    shell = PythonShell(tmp_path)
    assert shell.execute("value = 21")["ok"]
    result = shell.execute("value * 2")
    assert result["ok"]
    assert result["stdout"] == "42\n"


def test_filesystem_commands_are_real(tmp_path: Path):
    shell = PythonShell(tmp_path)
    assert shell.execute("mkdir project")["ok"]
    assert shell.execute("touch project/main.py")["ok"]
    assert (tmp_path / "project" / "main.py").is_file()
    assert "main.py" in shell.execute("ls project")["stdout"]


def test_pipeline_and_redirect_do_not_require_a_shell(tmp_path: Path):
    shell = PythonShell(tmp_path)
    # echo/cat are real system programs for this syntax; PythonShell starts
    # them directly and owns all pipe/redirection wiring.
    result = shell.execute("echo native > output.txt")
    assert result["ok"]
    result = shell.execute("cat output.txt | grep native")
    assert result["ok"]
    assert result["stdout"] == "native\n"


def test_unknown_command_with_pipe_still_reaches_subprocess(tmp_path: Path):
    """Commands containing |, >, < must route to the pipeline executor even
    when the first word is not a known executable (regression guard for the
    operator-routing branch)."""
    shell = PythonShell(tmp_path)
    result = shell.execute("definitely-not-a-real-cmd-9z | cat")
    assert not result["ok"]
    assert result["exit_code"] == 127
    assert "command not found" in result["stderr"]


class TestRmFlags:
    """`rm` option parsing must be strict: a stray "-" argument that merely
    *contains* the letters r/f previously enabled recursive+force silently."""

    def test_rejects_deceptive_option_string(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        shell.execute("mkdir targeted")
        shell.execute("touch targeted/innocent.txt")
        result = shell.execute("rm -random-flag targeted")
        assert not result["ok"]
        assert "invalid option" in result["stderr"]
        # The directory must survive untouched.
        assert (tmp_path / "targeted" / "innocent.txt").is_file()

    def test_rejects_unknown_single_letter(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        shell.execute("touch keep.txt")
        result = shell.execute("rm -v keep.txt")
        assert not result["ok"]
        assert "invalid option" in result["stderr"]
        assert (tmp_path / "keep.txt").is_file()

    def test_accepts_valid_flag_forms(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        for flags in ("-r", "-R", "-rf", "-fr", "-Rf", "--recursive", "--recursive --force"):
            shell.execute("mkdir victim")
            shell.execute("touch victim/file.txt")
            result = shell.execute(f"rm {flags} victim")
            assert result["ok"], flags
            assert not (tmp_path / "victim").exists()

    def test_force_suppresses_missing_file(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        assert shell.execute("rm -f does-not-exist.txt")["ok"]
        assert shell.execute("rm --force also-missing.txt")["ok"]

    def test_missing_operand_rejected(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        result = shell.execute("rm")
        assert not result["ok"]
        assert "missing operand" in result["stderr"]

    def test_refuses_directory_without_recursive(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        shell.execute("mkdir plain")
        result = shell.execute("rm plain")
        assert not result["ok"]
        assert (tmp_path / "plain").is_dir()


def test_which_resolves_each_name_exactly_once(tmp_path: Path, monkeypatch):
    shell = PythonShell(tmp_path)
    calls = []

    def fake_find(command):
        calls.append(command)
        return "/system/bin/cat" if command == "cat" else None

    monkeypatch.setattr(shell, "_find_executable", fake_find)
    result = shell.execute("which cat")
    assert result["ok"]
    assert result["stdout"] == "/system/bin/cat\n"
    assert calls == ["cat"], f"expected 1 lookup, got {len(calls)}"


class TestInterrupt:
    """Cooperative Ctrl+C: interrupt() must unblock a running pipeline."""

    def test_interrupt_kills_running_subprocess(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        outcome = {}

        def _run():
            outcome["result"] = shell.execute("sleep 30")

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        # Wait until the process is actually registered, then interrupt.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not shell._procs:
            time.sleep(0.05)
        assert shell._procs, "pipeline process never registered"

        started = time.monotonic()
        shell.interrupt()
        worker.join(timeout=15)
        assert not worker.is_alive(), "pipeline thread still blocked after interrupt"
        assert time.monotonic() - started < 15
        assert outcome["result"]["exit_code"] != 0

    def test_clear_interrupt_resets_latch(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        shell.interrupt()
        assert shell._interrupt.is_set()
        shell.clear_interrupt()
        assert not shell._interrupt.is_set()


class TestCleanControlFlowRendering:
    """Ctrl+C and sys.exit must not dump traceback spam (real-REPL semantics)."""

    def test_keyboard_interrupt_is_one_line_130(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        result = shell._exec_python("raise KeyboardInterrupt")
        assert result["exit_code"] == 130
        assert "KeyboardInterrupt" in result["stderr"]
        assert "Traceback" not in result["stderr"]

    def test_system_exit_is_quiet_and_keeps_code(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        result = shell._exec_python("import sys; sys.exit(7)")
        assert result["exit_code"] == 7
        assert "Traceback" not in result["stderr"]

    def test_force_python_bypasses_command_builtins(self, tmp_path: Path):
        shell = PythonShell(tmp_path)
        result = shell.execute("ls", force_python=True)
        assert not result["ok"]
        assert "NameError" in result["stderr"]


class TestRichTraceback:
    def test_rich_rendering_when_rich_installed(self, tmp_path: Path, monkeypatch):
        pytest.importorskip("rich")
        import zmux.python_shell as python_shell

        monkeypatch.setattr(python_shell, "_rich_impl", python_shell._RICH_UNSET)
        shell = PythonShell(tmp_path)
        result = shell._exec_python("1/0")
        assert "ZeroDivisionError" in result["stderr"]
        assert "\x1b[" in result["stderr"], "rich traceback should carry ANSI styling"

    def test_plain_traceback_without_rich(self, tmp_path: Path, monkeypatch):
        import zmux.python_shell as python_shell

        monkeypatch.setattr(python_shell, "_rich_impl", None)  # simulate absence
        shell = PythonShell(tmp_path)
        result = shell._exec_python("1/0")
        assert "Traceback (most recent call last)" in result["stderr"]
        assert "\x1b[" not in result["stderr"]
