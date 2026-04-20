"""
Tests for CLI argument parsing and help output.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest


class TestCLIHelp:
    """Test that CLI help messages are properly formed."""

    def test_main_help(self):
        """Main CLI --help should display all subcommands."""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0
        assert "create" in result.stdout
        assert "list" in result.stdout
        assert "status" in result.stdout
        assert "agents" in result.stdout

    def test_agents_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "agents", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0

    def test_sessions_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "sessions", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0
        assert "export" in result.stdout
        assert "import" in result.stdout

    def test_benchmark_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "benchmark", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0

    def test_scores_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "scores", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0
        assert "compare" in result.stdout

    def test_route_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "route", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0

    def test_create_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "create", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0

    def test_show_cmd_help(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "show-cmd", "--help"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
        )
        assert result.returncode == 0
        assert "--bare" in result.stdout  # bare mode flag


class TestCLISubcommands:
    """Test CLI subcommands execute without error."""

    def test_agents_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "agents"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        assert result.returncode == 0
        assert "claude" in result.stdout.lower() or "Claude" in result.stdout

    def test_sessions_list_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "sessions", "list"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        # Should not crash (empty or with data is fine)
        assert result.returncode == 0

    def test_sessions_stats_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "sessions", "stats"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        assert result.returncode == 0

    def test_scores_show_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "scores", "show"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        assert result.returncode == 0

    def test_scores_compare_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "scores", "compare"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        assert result.returncode == 0

    def test_route_command(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "route", "帮我写一个 Python 函数"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=15,
        )
        assert result.returncode == 0
        assert "claude" in result.stdout.lower() or "Claude" in result.stdout


class TestCLIExitCodes:
    """Test CLI error handling."""

    def test_status_nonexistent_task(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "status", "nonexistent-task-xyz"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=10,
        )
        # Should exit with error (task not found)
        assert result.returncode != 0

    def test_stop_nonexistent_task(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "stop", "nonexistent-task-xyz"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=10,
        )
        # Should exit with error
        assert result.returncode != 0

    def test_sessions_get_nonexistent(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "sessions", "get", "nonexistent-session-xyz"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=10,
        )
        assert result.returncode != 0

    def test_sessions_log_nonexistent(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "ai_task_system.v4.cli", "sessions", "log", "nonexistent-session-xyz"
            ],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(_PKG_ROOT.parent)},
            cwd=str(_PKG_ROOT.parent),
            timeout=10,
        )
        assert result.returncode != 0
