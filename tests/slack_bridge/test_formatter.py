"""formatter のテスト."""

import pytest

from slack_bridge.formatter import (
    add_footer,
    format_response,
    markdown_to_slack_mrkdwn,
    split_message,
)


class TestMarkdownToSlackMrkdwn:
    def test_bold_conversion(self):
        assert markdown_to_slack_mrkdwn("**太字**") == "*太字*"

    def test_heading_conversion(self):
        result = markdown_to_slack_mrkdwn("# 見出し1")
        assert "*見出し1*" in result

    def test_h2_conversion(self):
        result = markdown_to_slack_mrkdwn("## サブ見出し")
        assert "*サブ見出し*" in result

    def test_code_block_preserved(self):
        text = "```\n**not bold**\n```"
        result = markdown_to_slack_mrkdwn(text)
        assert "**not bold**" in result

    def test_table_to_code_block(self):
        text = "| Col1 | Col2 |\n|---|---|\n| A | B |"
        result = markdown_to_slack_mrkdwn(text)
        assert "```" in result
        assert "| A | B |" in result

    def test_mixed_content(self):
        text = "# Title\n\n**bold** and normal\n\n## Section\n\nMore text"
        result = markdown_to_slack_mrkdwn(text)
        assert "*Title*" in result
        assert "*bold*" in result
        assert "*Section*" in result


class TestSplitMessage:
    def test_short_message_no_split(self):
        text = "Short message"
        assert split_message(text) == ["Short message"]

    def test_long_message_splits(self):
        # 4000文字超のメッセージ
        text = "# Section 1\n" + "A" * 2000 + "\n# Section 2\n" + "B" * 2000
        parts = split_message(text)
        assert len(parts) >= 2
        for part in parts:
            assert len(part) <= 4000

    def test_single_huge_block_force_split(self):
        text = "A" * 8000
        parts = split_message(text)
        assert len(parts) >= 2
        for part in parts:
            assert len(part) <= 4000


class TestAddFooter:
    def test_footer_format(self):
        result = add_footer("Hello", 5, "2時間前")
        assert "5メッセージ目" in result
        assert "2時間前" in result
        assert "---" in result


class TestFormatResponse:
    def test_short_response(self):
        messages = format_response("# Title\n**Bold**", 3, "1時間前")
        assert len(messages) == 1
        assert "*Title*" in messages[0]
        assert "*Bold*" in messages[0]
        assert "3メッセージ目" in messages[0]

    def test_footer_on_last_message_only(self):
        long_text = "\n# Section\n".join(["X" * 2000 for _ in range(5)])
        messages = format_response(long_text, 10, "3時間前")
        assert len(messages) >= 2
        # フッターは最後のみ
        assert "10メッセージ目" in messages[-1]
        for msg in messages[:-1]:
            assert "メッセージ目" not in msg
