# Claude Code 連携仕様

## 呼び出し方式

Claude Code CLI を `subprocess.run()` で実行する。`--print` モードを使用し、`--resume` / `--session-id` でセッション管理する。

## コマンド構築

### 初回（新規セッション）

```bash
claude -p \
  --session-id <新規UUID> \
  --output-format json \
  --permission-mode auto \
  --model sonnet \
  "ユーザーのメッセージ"
```

### 2回目以降（セッション継続）

```bash
claude -p \
  --resume <既存session-id> \
  --output-format json \
  --permission-mode auto \
  --model sonnet \
  "ユーザーのメッセージ"
```

## オプション詳細

| オプション | 値 | 理由 |
|:---|:---|:---|
| `-p` / `--print` | - | 非対話モード。結果出力後に終了 |
| `--session-id` | UUID v4 | 新規セッション作成時にIDを指定 |
| `--resume` | session-id | 既存セッションの継続 |
| `--output-format` | `json` | パース容易な構造化出力 |
| `--permission-mode` | `.env` で設定（デフォルト: `auto`） | ツール実行の権限モード。`auto` は自動承認で root 環境でも動作する（`bypassPermissions` は root 不可） |
| `--model` | `.env` で設定 | モデル選択 |

## 作業ディレクトリ

`subprocess.run()` の `cwd` パラメータで stock_skills リポジトリルートを指定する。これにより Claude Code が CLAUDE.md / rules / skills を自動ロードする。

```python
subprocess.run(
    ["claude", "-p", ...],
    cwd=config.CLAUDE_PROJECT_DIR,  # /root/develop/sge-kawa/stock_skills
    capture_output=True,
    text=True,
    timeout=config.CLAUDE_TIMEOUT_SECONDS,
)
```

## JSON 出力形式

`--output-format json` の出力構造（実測確認済み）:

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "応答テキスト（Markdown形式）",
  "session_id": "2d3997d1-570d-4470-a101-a95d6bdd8952",
  "total_cost_usd": 0.287,
  "duration_ms": 6840,
  "duration_api_ms": 6816,
  "num_turns": 1,
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 3,
    "cache_creation_input_tokens": 51545,
    "cache_read_input_tokens": 0,
    "output_tokens": 4
  },
  "permission_denials": [],
  "fast_mode_state": "off",
  "uuid": "90f91813-1aed-41fa-a491-1d71b9ece25d"
}
```

**パース時に使用する主要フィールド**:
- `result`: 応答テキスト
- `is_error`: エラー判定
- `session_id`: セッションID（検証用）
- `duration_ms`: 処理時間（フッター表示用）
- `num_turns`: ターン数

## エラーハンドリング

### タイムアウト

```python
try:
    result = subprocess.run(..., timeout=config.CLAUDE_TIMEOUT_SECONDS)
except subprocess.TimeoutExpired:
    # プロセスは自動で kill される
    # タイムアウトエラーを返す
```

### 非ゼロ終了

```python
if result.returncode != 0:
    # stderr からエラー情報を取得
    error_msg = result.stderr or "不明なエラー"
    # エラー情報を返す
```

### JSON パースエラー（--resume 失敗時）

`--resume` に存在しないセッションIDを渡すと、exit code は 0 だが JSON ではなくプレーンテキストが返る:
```
No conversation found with session ID: <uuid>
```

この場合、JSON パース失敗で検出し、新規セッションで再試行する:

```python
try:
    data = json.loads(result.stdout)
except json.JSONDecodeError:
    # --resume 失敗 → セッションを破棄して新規セッションで再実行
    session_manager.reset_session(user_id)
    # --session-id で再試行
```

## セキュリティ考慮

- `--permission-mode auto` はツール実行を自動承認するため、信頼できる環境でのみ使用する
- ユーザー入力はそのまま CLI 引数として渡すため、シェルインジェクション対策として `subprocess.run()` はリスト形式（`shell=False`）で呼び出す
- `.env` のトークン類はリポジトリにコミットしない（`.gitignore` で除外）

## パフォーマンス特性

| 操作 | 想定所要時間 |
|:---|:---|
| 簡単な質問（「何ができる？」等） | 5-15秒 |
| stock-report（個別銘柄レポート） | 15-30秒 |
| screen-stocks（スクリーニング） | 30-120秒 |
| market-research（Grok API 連携） | 30-180秒 |
| stress-test（ストレステスト） | 30-120秒 |

タイムアウトのデフォルト300秒はこれらを十分にカバーする設定。
