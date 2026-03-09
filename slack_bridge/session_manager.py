"""セッション管理 - Slack user_id と Claude Code セッションの対応付け."""

import fcntl
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

RESET_KEYWORDS = [
    "リセット",
    "新しい会話",
    "最初から",
    "会話をリセット",
    "セッションリセット",
    "reset",
    "new session",
    "start over",
]


@dataclass
class Session:
    session_id: str
    user_id: str
    created_at: str
    last_used_at: str
    message_count: int = 0


class SessionManager:
    """Slack ユーザーごとの Claude Code セッション管理."""

    def __init__(self, store_path: str | None = None):
        self._store_path = Path(store_path or config.SESSION_STORE_PATH)
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        """sessions.json からロード."""
        if not self._store_path.exists():
            return {}
        try:
            text = self._store_path.read_text(encoding="utf-8")
            if not text.strip():
                return {}
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("sessions.json の読み込みに失敗: %s。空で再作成します。", e)
            backup = self._store_path.with_suffix(".json.bak")
            try:
                self._store_path.rename(backup)
                logger.info("バックアップを作成: %s", backup)
            except OSError:
                pass
            return {}

    def _save(self) -> None:
        """sessions.json に保存（ファイルロック付き）."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._store_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def get_or_create_session(self, user_id: str) -> tuple[Session, bool]:
        """セッションを取得または新規作成.

        Returns:
            (Session, is_new): セッションと新規作成かどうか
        """
        if user_id in self._sessions:
            data = self._sessions[user_id]
            session = Session(
                session_id=data["session_id"],
                user_id=user_id,
                created_at=data["created_at"],
                last_used_at=data["last_used_at"],
                message_count=data["message_count"],
            )
            return session, False

        now = datetime.now(timezone.utc).isoformat()
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            last_used_at=now,
            message_count=0,
        )
        self._sessions[user_id] = {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "last_used_at": session.last_used_at,
            "message_count": session.message_count,
        }
        self._save()
        return session, True

    def update_session(self, user_id: str) -> None:
        """セッションの last_used_at と message_count を更新."""
        if user_id not in self._sessions:
            return
        self._sessions[user_id]["last_used_at"] = datetime.now(timezone.utc).isoformat()
        self._sessions[user_id]["message_count"] += 1
        self._save()

    def reset_session(self, user_id: str) -> None:
        """セッションを破棄."""
        if user_id in self._sessions:
            del self._sessions[user_id]
            self._save()
            logger.info("セッションをリセット: user_id=%s", user_id)

    def get_session_info(self, user_id: str) -> dict | None:
        """セッション情報を取得（フッター表示用）."""
        return self._sessions.get(user_id)

    @staticmethod
    def is_reset_message(text: str) -> bool:
        """メッセージがセッションリセット要求かどうか判定.

        全体一致で判定（部分一致ではない）。
        前後の空白・句読点を除去して比較。
        """
        import re

        cleaned = re.sub(r"^[\s。、！!？?\.\,]+|[\s。、！!？?\.\,]+$", "", text)
        cleaned = cleaned.strip()
        return cleaned.lower() in [k.lower() for k in RESET_KEYWORDS]

    @staticmethod
    def format_elapsed_time(created_at: str) -> str:
        """経過時間を人間が読みやすい形式に変換."""
        try:
            created = datetime.fromisoformat(created_at)
            now = datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            delta = now - created
            total_seconds = int(delta.total_seconds())

            if total_seconds < 3600:
                minutes = max(1, total_seconds // 60)
                return f"{minutes}分前"
            elif total_seconds < 86400:
                hours = total_seconds // 3600
                return f"{hours}時間前"
            else:
                days = total_seconds // 86400
                return f"{days}日前"
        except (ValueError, TypeError):
            return "不明"
