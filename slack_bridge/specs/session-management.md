# セッション管理仕様

## 概要

Slack ユーザーごとに Claude Code のセッションを管理し、会話の文脈を維持する。セッションの寿命はユーザーが明示的にリセットするまで継続する。

## データモデル

### Session

```python
@dataclass
class Session:
    session_id: str       # UUID v4
    user_id: str          # Slack user_id
    created_at: str       # ISO 8601
    last_used_at: str     # ISO 8601
    message_count: int    # 累積メッセージ数
```

### 永続化ファイル（sessions.json）

```json
{
  "U12345ABC": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-03-07T10:00:00+09:00",
    "last_used_at": "2026-03-07T12:30:00+09:00",
    "message_count": 15
  },
  "U67890DEF": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "created_at": "2026-03-07T11:00:00+09:00",
    "last_used_at": "2026-03-07T11:45:00+09:00",
    "message_count": 3
  }
}
```

ファイルパスは `SESSION_STORE_PATH` 環境変数で指定（デフォルト: `slack_bridge/data/sessions.json`）。

## セッションライフサイクル

### 1. セッション解決（メッセージ受信時）

```
get_or_create_session(user_id) -> (session, is_new)

1. sessions.json から user_id を検索
2. 見つかった → (既存 Session, False)
3. 見つからない → 新規 UUID 生成 → (新規 Session, True)
```

### 2. Claude Code 呼び出し引数の決定

```
is_new == True  → --session-id <session.session_id>
is_new == False → --resume <session.session_id>
```

### 3. セッション更新（呼び出し完了後）

```
update_session(user_id):
  session.last_used_at = now()
  session.message_count += 1
  save_to_file()
```

### 4. セッションリセット（ユーザー明示）

```
reset_session(user_id):
  sessions.json から user_id のエントリを削除
  save_to_file()
```

## リセットトリガー

以下のキーワードを含むメッセージをセッションリセットとして扱う:

```python
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
```

判定ロジック:
- メッセージ全体がリセットキーワードと一致（部分一致ではない）
- 前後の空白・句読点は除去して比較
- 長文の中に「リセット」が含まれるだけでは発動しない（意図しないリセット防止）

## フッター情報

各返信の末尾にセッション情報を付与する:

```
---
:bar_chart: セッション: {message_count}メッセージ目 | 開始: {elapsed_time}
```

`elapsed_time` の表示ルール:
- 1時間未満: `{分}分前`
- 1時間以上24時間未満: `{時間}時間前`
- 24時間以上: `{日}日前`

## ファイルロック

複数イベントが同時に sessions.json を更新する可能性があるため、ファイルロックを使用する。

```python
import fcntl

def save_sessions(data, path):
    with open(path, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
        fcntl.flock(f, fcntl.LOCK_UN)
```

ただし、1ユーザー1プロセス制限により実質的な競合は低い。

## エッジケース

| ケース | 対応 |
|:---|:---|
| sessions.json が存在しない | 空の `{}` で新規作成 |
| sessions.json が壊れている | バックアップ後、空で再作成。ログ出力 |
| --resume で指定したセッションが Claude 側に存在しない | Claude がエラーを返す → 新規セッションで再試行 |
| デーモン再起動 | sessions.json から復元。セッション継続可能 |
