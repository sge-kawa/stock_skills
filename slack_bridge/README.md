# Slack Bridge

Slack から Claude Code を経由して stock_skills の全スキルを実行できるブリッジシステム。
Socket Mode を使用し、外部公開URLなしで動作する。

## セットアップ

### 1. Slack App 作成

[specs/slack-app-setup.md](specs/slack-app-setup.md) の手順に従い Slack App を作成する。

### 2. 環境変数

プロジェクトルートの `.env` に以下を追加:

```bash
# Slack Bridge - Socket Mode Bot (必須)
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxxx   # Bot User OAuth Token
SLACK_APP_TOKEN=xapp-xxxxxxxxxxxxx   # App-Level Token (connections:write)
```

オプション:

```bash
# Slack Bridge - オプション設定
CLAUDE_TIMEOUT_SECONDS=300      # Claude Code タイムアウト（秒）
CLAUDE_MODEL=sonnet             # 使用モデル
CLAUDE_PERMISSION_MODE=auto     # 権限モード
LOG_LEVEL=INFO                  # ログレベル
```

> **Note**: `.env.example` には含めていません。Slack Bridge 固有の設定はこの README で管理します。

### 3. 依存インストール

```bash
uv pip install slack-bolt slack-sdk
```

### 4. 起動

```bash
uv run python -m slack_bridge.app
```

## 使い方

- **チャネル**: `@Stock Assistant いい日本株ある？`
- **DM**: Bot に直接メッセージを送信

### セッション管理

会話の文脈はユーザーごとに維持される。リセットするには:

- 「リセット」
- 「新しい会話」
- 「reset」

## アーキテクチャ

詳細は [specs/](specs/) を参照。

```
Slack App ←→ app.py (Socket Mode) → session_manager.py → claude_runner.py → formatter.py
```
