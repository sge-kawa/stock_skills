# Slack Bridge メッセージフロー仕様

## 対応イベント

| イベント | トリガー | 返信先 |
|:---|:---|:---|
| `app_mention` | チャネル内で `@bot メッセージ` | 同チャネルのスレッド |
| `message.im` | Bot への DM | DM 内で返信 |

## 正常フロー

```
1. ユーザーが Slack でメッセージ送信
   ├── チャネル: @bot いい日本株ある？
   └── DM: いい日本株ある？

2. app.py がイベント受信

3. 同時実行チェック
   ├── 同一ユーザーが処理中
   │   └── 「前の処理が完了してから送ってください」とエフェメラル返信
   └── 処理中でない → 続行

4. リアクション付与: hourglass_flowing_sand

5. メッセージ前処理
   ├── メンションの場合: <@BOT_ID> を除去
   ├── セッションリセット判定（後述）
   └── 空メッセージチェック

6. Session Manager でセッション解決
   ├── 既存セッションあり → --resume <session-id>
   └── セッションなし → --session-id <new-uuid> で新規作成

7. Claude Code 実行（subprocess）
   claude -p [--resume <id> | --session-id <id>] \
     --output-format json \
     --permission-mode auto \
     --model $CLAUDE_MODEL \
     "<前処理済みメッセージ>"

8. 結果パース（formatter.py）
   ├── JSON から結果テキスト抽出
   ├── Markdown -> Slack mrkdwn 変換
   ├── 長文分割（4000文字制限対応）
   └── フッター付与

9. Slack にスレッドで投稿

10. リアクション更新: hourglass_flowing_sand -> white_check_mark

11. セッション情報更新
    ├── last_used_at 更新
    └── message_count インクリメント
```

## セッションリセットフロー

```
1. ユーザーが以下のいずれかを発言:
   - 「新しい会話」「リセット」「最初から」「会話をリセット」
   - 英語: "reset", "new session", "start over"

2. 現在のセッションを破棄
   └── sessions.json から該当エントリ削除

3. 「セッションをリセットしました。次のメッセージから新しい会話が始まります。」と返信

4. リアクション: arrows_counterclockwise
```

## エラーフロー

### タイムアウト

```
1. subprocess が CLAUDE_TIMEOUT_SECONDS を超過
2. プロセスを kill
3. リアクション更新: hourglass_flowing_sand -> alarm_clock
4. スレッドに投稿:
   「処理がタイムアウトしました（制限: {CLAUDE_TIMEOUT_SECONDS}秒）。
   メッセージを短くするか、対象を絞って再度お試しください。」
5. セッションは維持（次回 --resume で継続可能）
```

### Claude Code 異常終了

```
1. subprocess が非ゼロで終了
2. リアクション更新: hourglass_flowing_sand -> x
3. スレッドに投稿:
   「エラーが発生しました: {エラー概要}
   問題が続く場合はセッションをリセットしてください。」
4. セッションは維持（リセットはユーザー判断）
```

### Slack API エラー

```
1. メッセージ投稿に失敗
2. リトライ（最大3回、指数バックオフ）
3. それでも失敗 → ログ出力のみ（通知手段がないため）
```

## 同時実行制御

```python
# 処理中ユーザーの追跡（インメモリ set）
processing_users: set[str] = set()

# フロー
1. イベント受信 → user_id が processing_users に存在するか確認
2. 存在する → エフェメラルメッセージで拒否
3. 存在しない → processing_users.add(user_id)
4. 処理完了（正常/異常問わず） → processing_users.discard(user_id)
```

## Slack 返信フォーマット

### 通常返信

```
[Claude の分析結果（mrkdwn形式）]

---
:bar_chart: セッション: 15メッセージ目 | 開始: 2時間前
```

### 長文時（4000文字超）

メッセージを論理的な区切り（見出し単位）で分割し、複数メッセージとしてスレッドに連投する。

分割ロジック:
1. 見出し (`#`, `##`, `###`) で区切りを検出
2. 各ブロックが4000文字以下になるよう分割
3. 分割できない単一ブロックが4000文字超の場合、文字数で強制分割
4. フッターは最後のメッセージにのみ付与

### セッションリセット返信

```
:arrows_counterclockwise: セッションをリセットしました。
次のメッセージから新しい会話が始まります。
```
