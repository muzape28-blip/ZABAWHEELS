"""Regression tests for the Python-native terminal executor."""
from pathlib import Path

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
