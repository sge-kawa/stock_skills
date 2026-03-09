"""出力変換 - Claude Code JSON → Slack mrkdwn 変換."""

import re

# Slack ブロックのテキスト上限
SLACK_TEXT_LIMIT = 4000


def markdown_to_slack_mrkdwn(text: str) -> str:
    """GitHub-flavored Markdown を Slack mrkdwn に変換.

    変換ルール:
    - **太字** → *太字*
    - # 見出し → *見出し*
    - テーブルはコードブロック内に維持
    """
    lines = text.split("\n")
    result = []
    in_code_block = False
    in_table = False
    table_lines: list[str] = []

    for line in lines:
        # コードブロック内はそのまま
        if line.strip().startswith("```"):
            if in_table:
                # テーブル→コードブロック変換中に別のコードブロック
                result.append("```")
                result.extend(table_lines)
                result.append("```")
                table_lines = []
                in_table = False
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        # テーブル検出（| で始まる行）
        if re.match(r"^\s*\|", line):
            # セパレーター行（|---|---|）はスキップ
            if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
                if not in_table:
                    in_table = True
                continue
            if not in_table:
                in_table = True
            table_lines.append(line)
            continue

        # テーブル終了
        if in_table:
            result.append("```")
            result.extend(table_lines)
            result.append("```")
            table_lines = []
            in_table = False

        # 見出し変換: # Heading → *Heading*
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            heading_text = heading_match.group(2)
            result.append(f"\n*{heading_text}*")
            continue

        # 太字変換: **text** → *text*
        # ただし既に *text* の場合は変換しない
        converted = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)

        result.append(converted)

    # 残りのテーブル
    if in_table and table_lines:
        result.append("```")
        result.extend(table_lines)
        result.append("```")

    return "\n".join(result)


def add_footer(text: str, message_count: int, elapsed_time: str) -> str:
    """フッターを追加."""
    footer = f"\n---\n:bar_chart: セッション: {message_count}メッセージ目 | 開始: {elapsed_time}"
    return text + footer


def split_message(text: str) -> list[str]:
    """長文を Slack の制限に合わせて分割.

    分割ロジック:
    1. 見出し (#, ##, ###) で区切りを検出
    2. 各ブロックが SLACK_TEXT_LIMIT 以下になるよう分割
    3. 分割できない単一ブロックが制限超の場合、文字数で強制分割
    """
    if len(text) <= SLACK_TEXT_LIMIT:
        return [text]

    # 見出しで分割
    sections = re.split(r"(?=\n#{1,3}\s)", text)

    messages: list[str] = []
    current = ""

    for section in sections:
        if not section.strip():
            continue

        if len(current) + len(section) <= SLACK_TEXT_LIMIT:
            current += section
        else:
            if current.strip():
                messages.append(current.strip())
            # このセクション自体が制限超なら強制分割
            if len(section) > SLACK_TEXT_LIMIT:
                chunks = _force_split(section, SLACK_TEXT_LIMIT)
                messages.extend(chunks)
                current = ""
            else:
                current = section

    if current.strip():
        messages.append(current.strip())

    return messages if messages else [text[:SLACK_TEXT_LIMIT]]


def _force_split(text: str, limit: int) -> list[str]:
    """文字数で強制分割（改行位置を優先）."""
    chunks = []
    remaining = text

    while len(remaining) > limit:
        # 制限内で最後の改行を探す
        split_pos = remaining.rfind("\n", 0, limit)
        if split_pos == -1 or split_pos < limit // 2:
            split_pos = limit
        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def format_response(
    text: str,
    message_count: int,
    elapsed_time: str,
) -> list[str]:
    """Claude Code の応答を Slack 投稿用に整形.

    Returns:
        投稿するメッセージのリスト（フッターは最後のメッセージにのみ付与）
    """
    converted = markdown_to_slack_mrkdwn(text)
    messages = split_message(converted)

    # フッターは最後のメッセージにのみ
    if messages:
        last = messages[-1]
        messages[-1] = add_footer(last, message_count, elapsed_time)

    return messages
