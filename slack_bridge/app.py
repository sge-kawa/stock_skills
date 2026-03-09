"""Slack Bridge メインデーモン - Socket Mode で Slack イベントを受信し Claude Code を実行."""

import logging
import re
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from . import config
from .claude_runner import run as run_claude
from .formatter import format_response
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

# 処理中ユーザーの追跡（インメモリ）
_processing_users: set[str] = set()
_processing_lock = threading.Lock()


def create_app() -> App:
    """Slack App を構築."""
    config.setup_logging()

    errors = config.validate()
    if errors:
        for e in errors:
            logger.error(e)
        raise SystemExit("必須環境変数が不足しています。.env を確認してください。")

    app = App(token=config.SLACK_BOT_TOKEN)
    session_mgr = SessionManager()

    @app.event("app_mention")
    def handle_mention(event, say, client):
        """チャネル内でメンションされた時の処理."""
        _handle_message(event, say, client, session_mgr, is_dm=False)

    @app.event("message")
    def handle_dm(event, say, client):
        """DM 受信時の処理."""
        # Bot 自身のメッセージは無視
        if event.get("bot_id") or event.get("subtype"):
            return
        # DM のみ処理（channel_type == "im"）
        if event.get("channel_type") != "im":
            return
        _handle_message(event, say, client, session_mgr, is_dm=True)

    return app


def _handle_message(event, say, client, session_mgr: SessionManager, is_dm: bool):
    """メッセージ処理の共通ロジック."""
    user_id = event.get("user", "")
    channel = event.get("channel", "")
    text = event.get("text", "")
    ts = event.get("ts", "")

    # スレッド返信用の thread_ts（メンションの場合は元メッセージの ts）
    thread_ts = event.get("thread_ts", ts) if not is_dm else None

    # メンション除去
    if not is_dm:
        text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    # 空メッセージチェック
    if not text.strip():
        return

    # セッションリセット判定
    if SessionManager.is_reset_message(text):
        session_mgr.reset_session(user_id)
        _post_message(
            client,
            channel,
            ":arrows_counterclockwise: セッションをリセットしました。\n"
            "次のメッセージから新しい会話が始まります。",
            thread_ts=thread_ts,
        )
        # リアクション
        try:
            client.reactions_add(channel=channel, name="arrows_counterclockwise", timestamp=ts)
        except Exception:
            pass
        return

    # 同時実行チェック
    with _processing_lock:
        if user_id in _processing_users:
            try:
                client.chat_postEphemeral(
                    channel=channel,
                    user=user_id,
                    text="前の処理が完了してから送ってください。",
                )
            except Exception:
                pass
            return
        _processing_users.add(user_id)

    try:
        # 処理中リアクション
        try:
            client.reactions_add(channel=channel, name="hourglass_flowing_sand", timestamp=ts)
        except Exception:
            pass

        # セッション解決
        session, is_new = session_mgr.get_or_create_session(user_id)

        # Claude Code 実行
        result = run_claude(text, session.session_id, is_new)

        # --resume 失敗時のリトライ
        if not result.success and result.error == "SESSION_NOT_FOUND":
            logger.info("セッション不存在。新規セッションで再試行: user=%s", user_id)
            session_mgr.reset_session(user_id)
            session, is_new = session_mgr.get_or_create_session(user_id)
            result = run_claude(text, session.session_id, is_new)

        # リアクション更新
        _update_reaction(client, channel, ts, result)

        if result.success:
            # セッション更新
            session_mgr.update_session(user_id)
            session_info = session_mgr.get_session_info(user_id)
            message_count = session_info["message_count"] if session_info else 1
            elapsed = SessionManager.format_elapsed_time(session.created_at)

            # 整形・分割・投稿
            messages = format_response(result.text, message_count, elapsed)
            for msg in messages:
                _post_message(client, channel, msg, thread_ts=thread_ts)
        else:
            # エラー応答
            _post_message(client, channel, result.error, thread_ts=thread_ts)

    except Exception:
        logger.exception("メッセージ処理中に予期しないエラー: user=%s", user_id)
        try:
            client.reactions_add(channel=channel, name="x", timestamp=ts)
        except Exception:
            pass
        _post_message(
            client,
            channel,
            "予期しないエラーが発生しました。しばらくしてから再度お試しください。",
            thread_ts=thread_ts,
        )
    finally:
        with _processing_lock:
            _processing_users.discard(user_id)


def _post_message(client, channel: str, text: str, thread_ts: str | None = None):
    """Slack にメッセージを投稿（リトライ付き）."""
    import time

    for attempt in range(3):
        try:
            kwargs = {"channel": channel, "text": text}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            client.chat_postMessage(**kwargs)
            return
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                logger.warning("Slack 投稿リトライ (%d/3): %s", attempt + 1, e)
                time.sleep(wait)
            else:
                logger.error("Slack 投稿失敗 (3回リトライ後): %s", e)


def _update_reaction(client, channel: str, ts: str, result):
    """リアクションを更新."""
    # 砂時計を除去
    try:
        client.reactions_remove(channel=channel, name="hourglass_flowing_sand", timestamp=ts)
    except Exception:
        pass

    # 結果に応じたリアクション
    if result.success:
        emoji = "white_check_mark"
    elif result.is_timeout:
        emoji = "alarm_clock"
    else:
        emoji = "x"

    try:
        client.reactions_add(channel=channel, name=emoji, timestamp=ts)
    except Exception:
        pass


def main():
    """エントリーポイント."""
    import signal

    config.setup_logging()

    errors = config.validate()
    if errors:
        for e in errors:
            logger.error(e)
        raise SystemExit("必須環境変数が不足しています。.env を確認してください。")

    app = create_app()
    handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)

    def _shutdown(signum, frame):
        logger.info("シャットダウンシグナルを受信しました。停止します...")
        handler.close()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Slack Bridge を起動します... (Ctrl+C で停止)")
    logger.info("  プロジェクト: %s", config.CLAUDE_PROJECT_DIR)
    logger.info("  モデル: %s", config.CLAUDE_MODEL)
    logger.info("  タイムアウト: %d秒", config.CLAUDE_TIMEOUT_SECONDS)

    handler.start()


if __name__ == "__main__":
    main()
