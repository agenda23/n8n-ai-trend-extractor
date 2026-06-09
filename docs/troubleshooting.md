# トラブルシューティング

## エラー一覧

### n8n: secure cookie エラー（Safari / HTTP アクセス）

**症状**: `Your n8n server is configured to use a secure cookie...`

**原因**: n8n はデフォルトで Secure Cookie を使うため、HTTP や Safari からのアクセスでログインできない

**対処**（優先順）:

1. **URL を `http://localhost:5678` にする**（`127.0.0.1` や LAN IP ではなく `localhost`）
2. **Safari 以外のブラウザ**（Chrome / Firefox 等）を試す
3. ローカル HTTP 開発の場合、`.env` に `N8N_SECURE_COOKIE=false` を設定し `docker compose restart n8n`
4. 本番運用では **HTTPS（TLS）** を設定し `N8N_SECURE_COOKIE=true` を維持する

---

### Read Mock X: Access to the file is not allowed

**症状**: `Allowed paths: /home/node/.n8n-files`

**原因**: n8n 2.x はファイル読み込みを `/home/node/.n8n-files` に制限

**対処**:

1. **Read Mock X** のパスを `/home/node/.n8n-files/mock/x-tweets-sample.json` に変更
2. `docker-compose.yml` のマウントを変更:

```yaml
- ./mock:/home/node/.n8n-files/mock:ro
```

3. `docker compose up -d`

---

### Gemini: 503 Service Unavailable

**症状**: `This model is currently experiencing high demand`

**原因**: Google 側の一時的な過負荷

**対処**:

1. 数分〜数十分待って再実行
2. 別モデル（`gemini-2.0-flash`）に変更
3. Basic LLM Chain → Settings → Retry On Fail を ON

---

### Gemini: 429 Too Many Requests

**症状**: `You exceeded your current quota`

**原因**: 無料枠のクォータ使い切り

**対処**:

1. 時間を空けて再実行（日次リセットを待つ）
2. 手動テストの回数を減らす
3. Code ノードの取得件数を削減（トークン節約）
4. [Google Cloud Console](https://console.cloud.google.com/) で課金を有効化

> n8n の Retry Wait は最大 5000ms のため、429 には効果が限定的です。

---

### Execute Command: twitter 認証失敗

**症状**: X データが空、認証エラー

**対処**:

1. `.env` の `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` を更新
2. `docker compose restart n8n`
3. 確認: `docker compose exec n8n twitter search "Dify" --json --max 1`
4. キャッシュ削除: `rm -f data/twitter-cli/*`

---

### Merge ノードで止まる

**症状**: Code ノードに到達しない

**原因**: 並列ブランチのいずれかがハングまたは Merge 設定不備

**対処**:

1. Executions で各ブランチの成否を確認
2. 失敗ノードは `continueOnFail: true` が設定済みか確認
3. Merge ノードの **Number of Inputs** が `6` か確認

---

### Discord に通知が届かない

**対処**:

1. `.env` の `DISCORD_WEBHOOK_URL` を確認
2. `docker compose restart n8n`
3. HTTP Request ノードの Body:

```javascript
={{ JSON.stringify({ content: $json.text }) }}
```

4. Name に `"content"` と引用符付きで入れていないか確認（`content` のみ）
5. Value は式モードで `{{ $json.text }}`（外側の `"` 不要）

---

### Brain / Tips のデータが空

**原因**: 検索ページが SPA/HTML で、パース結果が少ない場合がある

**対処**:

1. Executions → **HTTP Request (Brain/Tips)** で HTML が返っているか確認
2. **Code (Combine Sources)** の HTML パーサーを調整
3. 現状はリンク・alt テキストからの抽出のため、タイトルが限定的な場合あり

---

### Qiita のデータが空

**対処**:

1. `./scripts/verify-sources.sh` で疎通確認
2. `QIITA_ACCESS_TOKEN` を設定（レートリミット緩和）
3. Executions → **HTTP Request (Qiita)** のレスポンスを確認

---

### 「実装エラー」と表示されるが Qiita にエラー記事がない

**説明**: 朝刊の「Qiita(実装エラー)」はラベルであり、エラー記事だけを収集しているわけではありません。直近3日の `tag:AI` 記事を Gemini が「技術的な詰まり」として要約したものです。

確認: Executions → **Code (Combine Sources)** → `textData` 内の Qiita セクション

---

## ログの見方

```bash
# コンテナログ
docker compose logs -f n8n --tail 100

# n8n 実行履歴
# GUI → Executions → 失敗した実行をクリック → 各ノードの INPUT/OUTPUT
```

---

## よくある質問

### Q. n8n のデータはどこに保存される？

Docker ボリューム `n8n_data` です。`docker compose down` では削除されません。完全削除は `docker compose down -v`（注意: 全データ消去）。

### Q. ワークフローを再インポートすると Credential は？

Credential ID は変わるため、インポート後に Gemini Credential を再紐付けしてください。

### Q. Mac をスリープさせるとスケジュールは動く？

Docker Desktop が動いていれば動作しますが、常時稼働にはサーバー運用を推奨します。

---

## サポート

- [運用マニュアル](./operations.md)
- [設定リファレンス](./configuration.md)
- [GitHub Issues](https://github.com/your-org/n8n-ai-trend-extractor/issues)（リポジトリ URL に合わせて更新）
