# Slack App セットアップ仕様

## Slack App 作成手順

### 1. App 作成

- https://api.slack.com/apps から「Create New App」
- 「From scratch」を選択
- App Name: `Stock Assistant`（任意）
- Workspace: 対象ワークスペースを選択

### 2. Socket Mode 有効化

- Settings > Socket Mode > 「Enable Socket Mode」を ON
- App-Level Token を生成:
  - Token Name: `socket-mode`
  - Scope: `connections:write`
  - 生成された `xapp-...` トークンを `SLACK_APP_TOKEN` として `.env` に設定

### 3. Bot User 設定

- Features > App Home
  - Display Name: `Stock Assistant`
  - Default Username: `stock-assistant`
  - 「Always Show My Bot as Online」を ON

### 4. OAuth & Permissions

Features > OAuth & Permissions > Bot Token Scopes に以下を追加:

| スコープ | 用途 |
|:---|:---|
| `app_mentions:read` | メンションイベントの受信 |
| `chat:write` | メッセージの送信 |
| `im:history` | DM 履歴の読み取り |
| `im:read` | DM の受信 |
| `im:write` | DM の送信 |
| `reactions:write` | リアクションの付与・更新 |
| `files:write` | ファイルアップロード（長文添付用） |

設定後「Install to Workspace」→ 生成された `xoxb-...` トークンを `SLACK_BOT_TOKEN` として `.env` に設定。

### 5. Event Subscriptions

Features > Event Subscriptions > 「Enable Events」を ON

**Subscribe to bot events** に以下を追加:

| イベント | 説明 |
|:---|:---|
| `app_mention` | Bot がメンションされた時 |
| `message.im` | Bot への DM 受信時 |

### 6. App Home タブ（任意）

Features > App Home:
- 「Messages Tab」を ON（DM を許可）
- 「Allow users to send Slash commands and messages from the messages tab」を ON

## トークン一覧

| トークン | 形式 | 用途 | 設定先 |
|:---|:---|:---|:---|
| App-Level Token | `xapp-...` | Socket Mode 接続 | `SLACK_APP_TOKEN` |
| Bot User OAuth Token | `xoxb-...` | API 呼び出し | `SLACK_BOT_TOKEN` |

## 動作確認

1. Bot をチャネルに招待: `/invite @Stock Assistant`
2. メンション: `@Stock Assistant いい日本株ある？`
3. DM: Bot に直接メッセージを送信
