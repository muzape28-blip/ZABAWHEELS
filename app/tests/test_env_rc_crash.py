"""Tests for the child-process environment, ~/.zmuxrc startup file and crash log."""

import os
import threading
import time

import pytest

from zmux import crash, env
from zmux.paths import BIN_DIR, HOME_DIR, RC_FILENAME, read_rc_lines
from zmux.python_shell import PythonShell


class TestEnvironment:
    def test_build_env_sets_terminal_identity(self):
        result = env.build_env()
        assert result["TERM"] == "xterm-256color"
        assert result["COLORTERM"] == "truecolor"
        assert result["LANG"] == "C.UTF-8"
        assert result["HOME"] == str(HOME_DIR)
        assert result["ZMUX"] == "1"

    def test_path_starts_with_bin_dir_then_system_dirs(self):
        parts = env.build_path().split(os.pathsep)
        assert parts[0] == str(BIN_DIR), "BIN_DIR must win so ZMUX wrappers resolve first"
        assert "/system/bin" in parts

    def test_path_has_no_duplicates(self):
        parts = env.build_path().split(os.pathsep)
        assert len(parts) == len(set(parts))

    def test_pythonpath_exposes_installed_packages(self):
        from zmux.paths import USER_PACKAGES_DIR
        assert str(USER_PACKAGES_DIR) in env.build_env()["PYTHONPATH"].split(os.pathsep)

    def test_child_process_receives_the_built_env(self, tmp_path):
        """Regression: the only Popen used to run without env= at all."""
        shell = PythonShell(tmp_path)
        if shell._find_executable("printenv") is None:
            pytest.skip("printenv unavailable on this host")
        result = shell.execute("printenv ZMUX")
        assert result["stdout"].strip() == "1", "child did not inherit the ZMUX env"

    def test_find_executable_searches_bin_dir(self, tmp_path):
        """Regression: BIN_DIR was omitted from the hardcoded search list."""
        marker = BIN_DIR / "zmux_probe_binary"
        marker.write_text("#!/system/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(marker, 0o755)
        try:
            assert PythonShell(tmp_path)._find_executable("zmux_probe_binary") == str(marker)
        finally:
            marker.unlink(missing_ok=True)


class TestRcFile:
    def test_missing_rc_returns_empty(self, tmp_path):
        assert read_rc_lines(tmp_path) == []

    def test_comments_and_blank_lines_are_stripped(self, tmp_path):
        (tmp_path / RC_FILENAME).write_text(
            "# a comment\n\nimport math\n   \n  x = 1  \n", encoding="utf-8"
        )
        assert read_rc_lines(tmp_path) == ["import math", "x = 1"]

    def test_unreadable_rc_never_raises(self, tmp_path):
        (tmp_path / RC_FILENAME).write_bytes(b"\xff\xfe\x00invalid")
        assert isinstance(read_rc_lines(tmp_path), list)

    def test_rc_runs_before_first_prompt(self, tmp_path, monkeypatch):
        from zmux import pty_session

        class _WS:
            def __init__(self): self.data = bytearray()
            def register_callbacks(self, on_data, on_resize): pass
            def broadcast(self, payload): self.data.extend(payload)

        (tmp_path / RC_FILENAME).write_text("rc_value = 99\n", encoding="utf-8")
        monkeypatch.setattr(pty_session, "HOME_DIR", tmp_path)
        session = pty_session.PTYTerminalSession(_WS())
        session.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and session._busy.is_set():
                time.sleep(0.05)
            assert session.shell.globals.get("rc_value") == 99
        finally:
            session.stop()


class TestCrashLog:
    def test_record_writes_an_entry(self):
        path = crash._log_path()
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        try:
            raise ValueError("zmux_crash_probe")
        except ValueError as error:
            crash.record("unit-test", type(error), error, error.__traceback__)
        text = path.read_text(encoding="utf-8")
        assert "zmux_crash_probe" in text
        assert "[unit-test]" in text
        path.write_text(before, encoding="utf-8")

    def test_thread_exception_is_recorded(self):
        crash.install()
        path = crash._log_path()
        before = path.read_text(encoding="utf-8") if path.exists() else ""

        def boom():
            raise RuntimeError("zmux_thread_probe")

        worker = threading.Thread(target=boom, name="probe")
        worker.start()
        worker.join()
        text = path.read_text(encoding="utf-8")
        assert "zmux_thread_probe" in text, "worker-thread crash was not persisted"
        path.write_text(before, encoding="utf-8")


class TestPythonKeywordGuard:
    """`import math` must never run ImageMagick's `import` binary.

    Regression: _is_external_command() consulted PATH for every first word,
    so on any system shipping ImageMagick, `import math` failed with
    "unable to open X server" instead of importing the module.
    """

    def test_import_statement_is_python_not_imagemagick(self, tmp_path):
        shell = PythonShell(tmp_path)
        result = shell.execute("import math")
        assert result["exit_code"] == 0, result["stderr"]
        assert "X server" not in result["stderr"]
        assert shell.execute("print(math.pi)")["stdout"].startswith("3.14")

    def test_from_import_statement_works(self, tmp_path):
        shell = PythonShell(tmp_path)
        assert shell.execute("from pathlib import Path")["exit_code"] == 0

    def test_guard_does_not_block_real_external_commands(self, tmp_path):
        shell = PythonShell(tmp_path)
        if shell._find_executable("echo") is None:
            pytest.skip("echo unavailable on this host")
        assert shell._is_external_command("echo") is True

    @pytest.mark.parametrize("keyword", ["import", "print", "class", "while"])
    def test_keywords_are_never_external(self, tmp_path, keyword):
        assert PythonShell(tmp_path)._is_external_command(keyword) is False
