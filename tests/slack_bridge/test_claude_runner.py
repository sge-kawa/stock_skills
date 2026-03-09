"""claude_runner のテスト."""

import json
from unittest.mock import patch

import pytest

from slack_bridge.claude_runner import ClaudeResult, run


@pytest.fixture(autouse=True)
def mock_config():
    """config の値をモック."""
    with patch("slack_bridge.claude_runner.config") as cfg:
        cfg.CLAUDE_TIMEOUT_SECONDS = 300
        cfg.CLAUDE_MODEL = "sonnet"
        cfg.CLAUDE_PERMISSION_MODE = "auto"
        cfg.CLAUDE_PROJECT_DIR = "/tmp/test"
        yield cfg


class TestRun:
    def test_successful_new_session(self, mock_config):
        json_output = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "テスト応答",
            "session_id": "test-session-id",
            "duration_ms": 5000,
            "num_turns": 1,
        })

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json_output
            mock_run.return_value.stderr = ""

            result = run("テスト", "test-session-id", is_new=True)

        assert result.success is True
        assert result.text == "テスト応答"
        assert result.duration_ms == 5000

        # --session-id が使われることを確認
        cmd = mock_run.call_args[0][0]
        assert "--session-id" in cmd
        assert "--resume" not in cmd

    def test_successful_resume_session(self, mock_config):
        json_output = json.dumps({
            "type": "result",
            "is_error": False,
            "result": "継続応答",
            "session_id": "existing-id",
            "duration_ms": 3000,
            "num_turns": 2,
        })

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json_output
            mock_run.return_value.stderr = ""

            result = run("テスト", "existing-id", is_new=False)

        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert "--resume" in cmd
        assert "--session-id" not in cmd

    def test_timeout(self, mock_config):
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="claude", timeout=300)):
            result = run("テスト", "test-id", is_new=True)

        assert result.success is False
        assert result.is_timeout is True
        assert "タイムアウト" in result.error

    def test_nonzero_exit(self, mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Something went wrong"

            result = run("テスト", "test-id", is_new=True)

        assert result.success is False
        assert "エラー" in result.error

    def test_session_not_found(self, mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "No conversation found with session ID: abc123"
            mock_run.return_value.stderr = ""

            result = run("テスト", "abc123", is_new=False)

        assert result.success is False
        assert result.error == "SESSION_NOT_FOUND"

    def test_json_parse_error(self, mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "not json at all"
            mock_run.return_value.stderr = ""

            result = run("テスト", "test-id", is_new=True)

        assert result.success is False

    def test_is_error_in_response(self, mock_config):
        json_output = json.dumps({
            "type": "result",
            "is_error": True,
            "result": "Permission denied",
        })

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json_output
            mock_run.return_value.stderr = ""

            result = run("テスト", "test-id", is_new=True)

        assert result.success is False
        assert "Permission denied" in result.error
