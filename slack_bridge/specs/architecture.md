# Slack Bridge アーキテクチャ仕様

## 概要

Slack からメッセージを送信し、Claude Code を経由して stock_skills の全スキルを実行できるブリッジシステム。Socket Mode を使用し、外部公開URLなしで動作する。

## システム構成

```
┌─────────────┐     Socket Mode      ┌──────────────────────────┐
│   Slack App  │ <------------------> │     slack_bridge/app.py   │
│  (Bot User)  │                      │     (常駐デーモン)         │
└─────────────┘                       └────────┬─────────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │  session_manager.py  │
                                    │  user_id -> session  │
                                    └──────────┬──────────┘
                                               │ subprocess
                                    ┌──────────▼──────────┐
                                    │   claude_runner.py   │
                                    │   claude -p --resume │
                                    │   --output-format json│
                                    └──────────┬──────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │    formatter.py      │
                                    │   JSON -> Slack mrkdwn│
                                    └─────────────────────┘
```

## ディレクトリ構成

```
stock_skills/
├── slack_bridge/
│   ├── __init__.py
│   ├── app.py                # メイン（Socket Mode デーモン）
│   ├── claude_runner.py      # Claude Code subprocess 管理
│   ├── session_manager.py    # user_id -> session_id マッピング
│   ├── formatter.py          # 出力変換（JSON -> Slack mrkdwn）
│   ├── config.py             # .env 読み込み・設定管理
│   ├── requirements.txt      # slack_bridge 固有の依存
│   ├── data/
│   │   └── sessions.json     # セッション永続化ファイル
│   ├── specs/
│   │   ├── architecture.md   # 本ファイル
│   │   └── ...
│   └── README.md             # セットアップ手順
├── .env.example              # 環境変数テンプレート（slack_bridge 用を追記）
└── ...
```

## コンポーネント詳細

### 1. app.py（メインデーモン）

**責務**: Slack イベントの受信・振り分け・レスポンス管理

- slack-bolt の `App` を Socket Mode で起動
- イベントハンドラ登録:
  - `app_mention`: チャネル内でのメンション
  - `message` (DM): Bot への DM
- 処理中の状態管理（リアクション制御）
- 同時実行制御（1ユーザー1プロセス）

### 2. claude_runner.py（Claude Code 呼び出し）

**責務**: Claude Code CLI を subprocess で実行し、結果を返す

- 呼び出しコマンド構築:
  ```bash
  claude -p [--resume <session-id> | --session-id <new-uuid>] \
    --output-format json \
    --permission-mode auto \
    "<ユーザーメッセージ>"
  ```
- タイムアウト制御（`subprocess.run(timeout=...)`)
- プロセスの標準出力・標準エラー取得
- 異常終了時のエラー情報収集

### 3. session_manager.py（セッション管理）

**責務**: Slack ユーザーと Claude Code セッションの対応付け

- `user_id` -> `session_id` (UUID) のマッピング
- セッション作成・継続・破棄
- 永続化（`data/sessions.json`）
- メッセージカウント管理

**データ構造**:
```json
{
  "U12345ABC": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-03-07T10:00:00Z",
    "last_used_at": "2026-03-07T12:30:00Z",
    "message_count": 15
  }
}
```

**セッションリセット**: ユーザーが「新しい会話」「リセット」「最初から」と発言した場合、現在のセッションを破棄し次回メッセージで新規セッションを作成する。

### 4. formatter.py（出力変換）

**責務**: Claude Code の JSON 出力を Slack に適した形式に変換

- JSON レスポンスからテキスト抽出
- Markdown -> Slack mrkdwn 変換
  - `**太字**` -> `*太字*`
  - `# 見出し` -> `*見出し*`
  - テーブル -> コードブロック
- 長文分割（Slack の 4000 文字/ブロック制限）
  - 4000文字以下: 通常投稿
  - 4000文字超: 複数メッセージに分割、またはファイル添付
- フッター付与:
  ```
  ---
  セッション: 15メッセージ目 | 開始: 2時間前
  ```

### 5. config.py（設定管理）

**責務**: `.env` からの設定読み込みとデフォルト値管理

## 環境変数

| 変数名 | 必須 | デフォルト | 説明 |
|:---|:---|:---|:---|
| `SLACK_BOT_TOKEN` | Yes | - | Slack Bot トークン (xoxb-) |
| `SLACK_APP_TOKEN` | Yes | - | Slack App トークン (xapp-) |
| `CLAUDE_TIMEOUT_SECONDS` | No | `300` | Claude Code プロセスのタイムアウト（秒） |
| `CLAUDE_MODEL` | No | `sonnet` | 使用する Claude モデル |
| `CLAUDE_PERMISSION_MODE` | No | `auto` | 権限モード（auto, default, plan 等） |
| `CLAUDE_PROJECT_DIR` | No | リポジトリルート自動検出 | Claude Code の作業ディレクトリ |
| `SESSION_STORE_PATH` | No | `slack_bridge/data/sessions.json` | セッション永続化ファイルパス |
| `LOG_LEVEL` | No | `INFO` | ログレベル（DEBUG, INFO, WARNING, ERROR） |
