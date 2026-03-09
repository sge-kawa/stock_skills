"""config のテスト."""

from unittest.mock import patch

import pytest


class TestValidate:
    def test_missing_tokens(self):
        with patch.dict("os.environ", {}, clear=True):
            # config モジュールを再読み込み
            import importlib
            from slack_bridge import config

            # 値を直接セット
            config.SLACK_BOT_TOKEN = ""
            config.SLACK_APP_TOKEN = ""
            errors = config.validate()
            assert len(errors) == 2
            assert any("SLACK_BOT_TOKEN" in e for e in errors)
            assert any("SLACK_APP_TOKEN" in e for e in errors)

    def test_valid_tokens(self):
        from slack_bridge import config

        config.SLACK_BOT_TOKEN = "xoxb-test"
        config.SLACK_APP_TOKEN = "xapp-test"
        errors = config.validate()
        assert len(errors) == 0
