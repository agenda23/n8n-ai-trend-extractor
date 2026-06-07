# FAQ（よくある質問）

## 一般

### このシステムは何をするものですか？

毎朝自動で X / note / Brain / Tips / Qiita から AI 関連トレンドを収集し、Gemini が「顧客獲得（リードマグネット）」視点で分析した朝刊を Discord 等に配信します。

### プログラミング知識は必要ですか？

n8n GUI での操作が中心です。初回セットアップ時に Docker コマンドと `.env` 編集が必要です。

### 費用はかかりますか？

| 項目 | 費用 |
|------|------|
| n8n（セルフホスト） | 無料 |
| Docker | 無料 |
| Gemini API | 無料枠あり（本番運用は課金推奨） |
| X データ取得 | 無料（Cookie 認証） |
| Discord | 無料 |

---

## データソース

### Qiita の「実装エラー」とは何ですか？

エラー記事だけを収集しているわけではありません。直近3日の `tag:AI` 記事タイトル・タグを Gemini が読み、「開発者が詰まりそうなポイント」として要約したものです。

### Brain / Tips のデータ精度は？

公式 API が使えないため、検索ページ HTML からリンク・タイトルを抽出しています。完全な商品情報ではない場合があります。

### X のデータは公式 API ですか？

いいえ。`twitter-cli`（Python 版）がブラウザ Cookie を使って検索します。利用規約・BAN リスクに注意し、サブアカウントの利用を推奨します。

---

## 運用

### スケジュールを変更したい

Schedule Trigger ノードの cron 式を編集してください。タイムゾーンは `GENERIC_TIMEZONE=Asia/Tokyo` です。

### 通知を止めたい

Discord / Slack の HTTP Request ノードを削除し、**Code (Format Notification)** で終了させてください。結果は n8n Executions で確認できます。

### Mac を閉じても動く？

Docker Desktop が起動していれば動作します。常時稼働には VPS 等での運用を推奨します。

### ワークフローを別マシンに移したい

1. リポジトリを clone
2. `.env` を手動で再作成
3. `docker compose up -d --build`
4. ワークフローをインポート
5. Gemini Credential を再設定

---

## トラブル

詳細は [トラブルシューティング](./troubleshooting.md) を参照してください。

### Gemini が 429 になる

無料枠のクォータ超過です。時間を空けるか、Google Cloud で課金を有効化してください。

### Cookie がすぐ切れる

通常は数週間〜1ヶ月程度持ちます。再ログイン後に `.env` を更新してください。

---

## カスタマイズ

### プロンプトを自社向けに変えたい

Basic LLM Chain のシステムプロンプトを編集してください。[運用マニュアル](./operations.md) の「Gemini プロンプトの調整」を参照。

### ソースを追加したい

1. 新しい収集ノードを Schedule から並列接続
2. Merge ノードの入力数を増やす
3. Code (Combine Sources) にパース処理を追加

設計の参考: `specs/AIトレンド抽出システム構築仕様書.md`
