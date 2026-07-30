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
