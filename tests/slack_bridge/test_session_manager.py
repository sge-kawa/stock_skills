"""SessionManager のテスト."""

import json
import os
import tempfile

import pytest

from slack_bridge.session_manager import SessionManager


@pytest.fixture
def tmp_store(tmp_path):
    """一時セッションストアファイル."""
    return str(tmp_path / "sessions.json")


@pytest.fixture
def mgr(tmp_store):
    """SessionManager インスタンス."""
    return SessionManager(store_path=tmp_store)


class TestGetOrCreateSession:
    def test_new_session(self, mgr):
        session, is_new = mgr.get_or_create_session("U001")
        assert is_new is True
        assert session.user_id == "U001"
        assert session.message_count == 0
        assert len(session.session_id) == 36  # UUID format

    def test_existing_session(self, mgr):
        session1, _ = mgr.get_or_create_session("U001")
        session2, is_new = mgr.get_or_create_session("U001")
        assert is_new is False
        assert session2.session_id == session1.session_id

    def test_different_users(self, mgr):
        s1, _ = mgr.get_or_create_session("U001")
        s2, _ = mgr.get_or_create_session("U002")
        assert s1.session_id != s2.session_id


class TestUpdateSession:
    def test_update_increments_count(self, mgr):
        mgr.get_or_create_session("U001")
        mgr.update_session("U001")
        info = mgr.get_session_info("U001")
        assert info["message_count"] == 1

    def test_update_nonexistent_noop(self, mgr):
        mgr.update_session("U999")  # should not raise


class TestResetSession:
    def test_reset(self, mgr):
        mgr.get_or_create_session("U001")
        mgr.reset_session("U001")
        info = mgr.get_session_info("U001")
        assert info is None

    def test_reset_creates_new_on_next_call(self, mgr):
        s1, _ = mgr.get_or_create_session("U001")
        mgr.reset_session("U001")
        s2, is_new = mgr.get_or_create_session("U001")
        assert is_new is True
        assert s2.session_id != s1.session_id


class TestPersistence:
    def test_save_and_load(self, tmp_store):
        mgr1 = SessionManager(store_path=tmp_store)
        mgr1.get_or_create_session("U001")
        mgr1.update_session("U001")

        mgr2 = SessionManager(store_path=tmp_store)
        session, is_new = mgr2.get_or_create_session("U001")
        assert is_new is False
        assert session.message_count == 1

    def test_corrupt_file(self, tmp_store):
        with open(tmp_store, "w") as f:
            f.write("not json{{{")
        mgr = SessionManager(store_path=tmp_store)
        session, is_new = mgr.get_or_create_session("U001")
        assert is_new is True

    def test_empty_file(self, tmp_store):
        with open(tmp_store, "w") as f:
            f.write("")
        mgr = SessionManager(store_path=tmp_store)
        session, is_new = mgr.get_or_create_session("U001")
        assert is_new is True


class TestIsResetMessage:
    @pytest.mark.parametrize(
        "text",
        [
            "リセット",
            "新しい会話",
            "最初から",
            "会話をリセット",
            "セッションリセット",
            "reset",
            "new session",
            "start over",
            "  リセット  ",
            "リセット。",
            "reset!",
        ],
    )
    def test_reset_messages(self, text):
        assert SessionManager.is_reset_message(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "リセットしてから実行して",
            "設定をリセットする方法を教えて",
            "This has reset in a sentence",
            "いい株ある？",
            "",
        ],
    )
    def test_non_reset_messages(self, text):
        assert SessionManager.is_reset_message(text) is False


class TestFormatElapsedTime:
    def test_minutes(self):
        from datetime import datetime, timedelta, timezone

        t = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        result = SessionManager.format_elapsed_time(t)
        assert "分前" in result

    def test_hours(self):
        from datetime import datetime, timedelta, timezone

        t = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = SessionManager.format_elapsed_time(t)
        assert "時間前" in result

    def test_days(self):
        from datetime import datetime, timedelta, timezone

        t = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        result = SessionManager.format_elapsed_time(t)
        assert "日前" in result
