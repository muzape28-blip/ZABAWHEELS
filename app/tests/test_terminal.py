"""Tests for ZMUX terminal execution engine."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Setup path
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from zmux.terminal import TerminalSession, ProcessStatus


@pytest.fixture
def terminal():
    """Create a fresh terminal session."""
    return TerminalSession()


class TestBuiltinCommands:
    """Test built-in commands."""

    def test_pwd(self, terminal):
        """Test pwd command."""
        result = terminal.execute("pwd")
        assert result["ok"]
        assert result["exit_code"] == 0
        assert "~" in result["stdout"]

    def test_cd_home(self, terminal):
        """Test cd to home."""
        result = terminal.execute("cd")
        assert result["ok"]
        assert result["exit_code"] == 0

    def test_cd_nonexistent(self, terminal):
        """Test cd to non-existent directory."""
        result = terminal.execute("cd /nonexistent/path/12345")
        assert not result["ok"]
        assert result["exit_code"] == 1
        assert "No such file" in result["stderr"] or "cannot access" in result["stderr"]

    def test_clear(self, terminal):
        """Test clear command."""
        result = terminal.execute("clear")
        assert result["ok"]
        assert "\033[2J" in result["stdout"]

    def test_help(self, terminal):
        """Test help command."""
        result = terminal.execute("help")
        assert result["ok"]
        assert "ZMUX Terminal" in result["stdout"]
        assert "help" in result["stdout"]

    def test_exit(self, terminal):
        """Test exit command."""
        result = terminal.execute("exit")
        assert result["ok"]
        assert result["status"] == ProcessStatus.EXITED

    def test_empty_command(self, terminal):
        """Test empty command."""
        result = terminal.execute("")
        assert result["ok"]
        assert result["exit_code"] == 0


class TestRealCommands:
    """Test real subprocess execution."""

    def test_echo(self, terminal):
        """Test echo command."""
        result = terminal.execute("echo hello")
        assert result["ok"]
        assert "hello" in result["stdout"]
        assert result["exit_code"] == 0

    def test_ls(self, terminal):
        """Test ls command."""
        result = terminal.execute("ls")
        assert result["ok"]
        assert result["exit_code"] == 0

    def test_python_version(self, terminal):
        """Test python version."""
        result = terminal.execute("python3 --version")
        assert result["ok"]
        assert "Python" in result["stdout"]

    def test_python_c(self, terminal):
        """Test python -c."""
        result = terminal.execute('python3 -c "print(2+2)"')
        assert result["ok"]
        assert "4" in result["stdout"]

    def test_exit_code_nonzero(self, terminal):
        """Test command with non-zero exit code."""
        result = terminal.execute("exit 42")
        assert not result["ok"]
        assert result["exit_code"] == 42

    def test_stderr(self, terminal):
        """Test stderr output."""
        result = terminal.execute("python3 -c 'import sys; print(\"error\", file=sys.stderr)'")
        assert result["ok"]

    def test_invalid_command(self, terminal):
        """Test invalid command."""
        result = terminal.execute("this_command_does_not_exist_12345")
        assert not result["ok"]
        assert result["exit_code"] != 0


class TestWorkingDirectory:
    """Test working directory persistence."""

    def test_cwd_persistence(self, terminal):
        """Test that cwd persists between commands."""
        initial_cwd = terminal.cwd
        
        # Create a test directory
        test_dir = terminal.cwd / "test_dir"
        test_dir.mkdir(exist_ok=True)
        
        # Change to it
        terminal.execute(f"cd {test_dir}")
        
        # Verify cwd changed
        assert terminal.cwd == test_dir
        
        # Execute another command - cwd should still be test_dir
        result = terminal.execute("pwd")
        assert "test_dir" in result["stdout"]
        
        # Cleanup
        test_dir.rmdir()

    def test_path_traversal_protection(self, terminal):
        """Test that built-in cd prevents traversal outside home."""
        # Try to cd outside home
        result = terminal.execute("cd /etc")
        assert not result["ok"]
        assert "outside home" in result["stderr"]


class TestProcessControl:
    """Test process control (stop, input)."""

    def test_stop_idle(self, terminal):
        """Test stopping when no process is running."""
        result = terminal.stop()
        assert result["ok"]

    def test_send_input_idle(self, terminal):
        """Test sending input when no process is running."""
        result = terminal.send_input("test")
        assert not result["ok"]
        assert "No process running" in result["error"]


class TestPrompt:
    """Test prompt generation."""

    def test_prompt_format(self, terminal):
        """Test prompt format."""
        prompt = terminal.get_prompt()
        assert prompt.startswith("zmux:")
        assert prompt.endswith("$ ")

    def test_prompt_shows_path(self, terminal):
        """Test that prompt shows current path."""
        prompt = terminal.get_prompt()
        assert "~" in prompt  # Should show home as ~


class TestTimeout:
    """Test command timeout."""

    def test_timeout(self, terminal):
        """Test command timeout."""
        # sleep for 10s with 0.5s timeout should fail
        result = terminal.execute("sleep 10", timeout=0.5)
        assert not result["ok"]
        assert "timed out" in result.get("stderr", "").lower() or result["exit_code"] == -1


class TestStatus:
    """Test status tracking."""

    def test_initial_status(self, terminal):
        """Test initial status is idle."""
        assert terminal.status == ProcessStatus.IDLE

    def test_status_after_command(self, terminal):
        """Test status after successful command."""
        terminal.execute("echo test")
        assert terminal.status == ProcessStatus.IDLE

    def test_status_after_failed_command(self, terminal):
        """Test status after failed command."""
        terminal.execute("false")
        # Terminal returns to IDLE after command completes (ready for next command)
        assert terminal.status == ProcessStatus.IDLE
