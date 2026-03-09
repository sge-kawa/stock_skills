"""Claude Code subprocess 管理."""

import json
import logging
import subprocess
from dataclasses import dataclass

from . import config

logger = logging.getLogger(__name__)


@dataclass
class ClaudeResult:
    """Claude Code の実行結果."""

    success: bool
    text: str
    session_id: str = ""
    duration_ms: int = 0
    num_turns: int = 0
    error: str = ""
    is_timeout: bool = False


def run(message: str, session_id: str, is_new: bool) -> ClaudeResult:
    """Claude Code CLI を subprocess で実行.

    Args:
        message: ユーザーメッセージ
        session_id: セッションID
        is_new: 新規セッションかどうか

    Returns:
        ClaudeResult
    """
    cmd = ["claude", "-p"]

    if is_new:
        cmd.extend(["--session-id", session_id])
    else:
        cmd.extend(["--resume", session_id])

    cmd.extend([
        "--output-format", "json",
        "--permission-mode", config.CLAUDE_PERMISSION_MODE,
        "--model", config.CLAUDE_MODEL,
        message,
    ])

    logger.info(
        "Claude Code 実行: session=%s, is_new=%s, message_len=%d",
        session_id[:8],
        is_new,
        len(message),
    )

    try:
        result = subprocess.run(
            cmd,
            cwd=config.CLAUDE_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=config.CLAUDE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Claude Code タイムアウト: session=%s", session_id[:8])
        return ClaudeResult(
            success=False,
            text="",
            error=f"処理がタイムアウトしました（制限: {config.CLAUDE_TIMEOUT_SECONDS}秒）。\n"
            "メッセージを短くするか、対象を絞って再度お試しください。",
            is_timeout=True,
        )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "不明なエラー"
        logger.error(
            "Claude Code 異常終了: session=%s, returncode=%d, stderr=%s",
            session_id[:8],
            result.returncode,
            error_msg[:200],
        )
        return ClaudeResult(
            success=False,
            text="",
            error=f"エラーが発生しました: {error_msg}\n"
            "問題が続く場合はセッションをリセットしてください。",
        )

    # JSON パース
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        # --resume 失敗の可能性（プレーンテキスト応答）
        stdout_preview = result.stdout.strip()[:200] if result.stdout else ""
        if "No conversation found with session ID" in stdout_preview:
            logger.warning(
                "セッションが見つかりません。新規セッションで再試行が必要: session=%s",
                session_id[:8],
            )
            return ClaudeResult(
                success=False,
                text="",
                error="SESSION_NOT_FOUND",
            )
        logger.error("JSON パースエラー: stdout=%s", stdout_preview)
        return ClaudeResult(
            success=False,
            text="",
            error="応答の解析に失敗しました。再度お試しください。",
        )

    if data.get("is_error"):
        return ClaudeResult(
            success=False,
            text="",
            error=data.get("result", "不明なエラー"),
        )

    return ClaudeResult(
        success=True,
        text=data.get("result", ""),
        session_id=data.get("session_id", session_id),
        duration_ms=data.get("duration_ms", 0),
        num_turns=data.get("num_turns", 0),
    )
