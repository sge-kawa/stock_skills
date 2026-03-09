"""設定管理 - .env からの読み込みとデフォルト値."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


def _find_project_dir() -> str:
    """stock_skills リポジトリルートを自動検出."""
    current = Path(__file__).resolve().parent.parent
    if (current / "CLAUDE.md").exists():
        return str(current)
    return str(Path.cwd())


# .env をロード（プロジェクトルートの .env を探す）
_project_dir = _find_project_dir()
load_dotenv(Path(_project_dir) / ".env")

# Slack トークン（必須）
SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN: str = os.environ.get("SLACK_APP_TOKEN", "")

# Claude Code 設定
CLAUDE_TIMEOUT_SECONDS: int = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))
CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "sonnet")
CLAUDE_PERMISSION_MODE: str = os.environ.get("CLAUDE_PERMISSION_MODE", "auto")
CLAUDE_PROJECT_DIR: str = os.environ.get("CLAUDE_PROJECT_DIR", _find_project_dir())

# セッション永続化
SESSION_STORE_PATH: str = os.environ.get(
    "SESSION_STORE_PATH",
    str(Path(__file__).resolve().parent / "data" / "sessions.json"),
)

# ログ
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


def validate() -> list[str]:
    """必須設定の検証。エラーメッセージのリストを返す."""
    errors = []
    if not SLACK_BOT_TOKEN:
        errors.append("SLACK_BOT_TOKEN が設定されていません")
    if not SLACK_APP_TOKEN:
        errors.append("SLACK_APP_TOKEN が設定されていません")
    return errors


def setup_logging() -> None:
    """ログ設定."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
