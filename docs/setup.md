# セットアップマニュアル

初回構築から本番稼働までの手順です。所要時間の目安は **1〜2時間** です。

## 前提条件

| 項目 | 要件 |
|------|------|
| OS | macOS / Linux / Windows (WSL2) |
| Docker | Docker Desktop または Docker Engine + Compose v2 |
| ディスク | 空き 5GB 以上 |
| ポート | `5678` が未使用であること |

### 必要なアカウント・キー

| 項目 | 必須 | 取得先 |
|------|------|--------|
| Google Gemini API キー | **必須** | [Google AI Studio](https://aistudio.google.com/) |
| X（Twitter）アカウント | 本番 X 利用時 | 閲覧用サブアカウント推奨 |
| Discord Webhook URL | 通知利用時 | Discord サーバー設定 |
| Qiita アクセストークン | 任意 | [Qiita 設定](https://qiita.com/settings/tokens) |

---

## Step 1: リポジトリの準備

```bash
git clone <repository-url>
cd n8n-ai-trend-extractor
cp .env.example .env
```

---

## Step 2: 環境変数の設定

`.env` を編集します。詳細は [設定リファレンス](./configuration.md) を参照。

**最低限必要な設定（モックモードでテスト）:**

```env
USE_MOCK_X=true
```

**本番運用時に追加:**

```env
USE_MOCK_X=false
TWITTER_AUTH_TOKEN=<auth_token>
TWITTER_CT0=<ct0>
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## Step 3: Docker 起動

```bash
docker compose up -d --build
```

起動確認:

```bash
docker compose ps          # Status: healthy
curl http://localhost:5678/healthz   # 200
open http://localhost:5678             # n8n GUI
```

初回アクセス時に **オーナーアカウント** を作成してください。

---

## Step 4: ワークフローのインポート

n8n GUI（http://localhost:5678）で:

1. **Workflows** → **Import from File**
2. `workflows/ai-trend-extractor.json` をインポート
3. （任意）`workflows/error-handler.json` をインポート

---

## Step 5: Gemini Credential の設定

1. 左メニュー **⋯** → **Credentials** → **Add Credential**
2. 種類: **Google Gemini(PaLM) API**（表示名は n8n バージョンにより異なる場合あり）
3. API キーを入力して保存
4. **AIトレンド抽出・リード獲得** ワークフローを開く
5. 画面下の **Google Gemini Chat Model** ノード → **Parameters** → Credential を選択
6. モデル: `models/gemini-2.0-flash` または `models/gemini-2.5-flash`（利用可能なもの）
7. **Save**

---

## Step 6: 通知の設定（Discord）

Slack ノードの代わりに Discord Webhook を使う場合:

1. **Code (Format Notification)** の後ろに **HTTP Request** ノードを配置（または Slack ノードを差し替え）
2. 設定:
   - **Method**: POST
   - **URL**: `={{ $env.DISCORD_WEBHOOK_URL }}`
   - **Body Content Type**: JSON
   - **Specify Body**: Using JSON
   - **JSON**:

```javascript
={{ JSON.stringify({ content: $json.text }) }}
```

3. `.env` に `DISCORD_WEBHOOK_URL` を設定
4. `docker compose restart n8n`

---

## Step 7: モックモードで E2E テスト

### モックファイルのパス（重要）

n8n 2.x ではファイル読み込みが `/home/node/.n8n-files` 配下に制限されます。

**Read Mock X** ノードのパスを次のいずれかに設定:

| 方法 | パス / 設定 |
|------|------------|
| A（推奨） | `/home/node/.n8n-files/mock/x-tweets-sample.json` + docker-compose でマウント変更 |
| B | `docker cp mock/x-tweets-sample.json <container>:/home/node/.n8n-files/x-tweets-sample.json` |

方法 A の docker-compose 追記例:

```yaml
volumes:
  - ./mock:/home/node/.n8n-files/mock:ro
```

### テスト実行

1. `.env`: `USE_MOCK_X=true`
2. `docker compose restart n8n`
3. ワークフロー右上 **Test workflow**
4. **Executions** で各ノードの成功を確認
5. Discord（または Executions の **Code (Format Notification)** 出力）で朝刊を確認

---

## Step 8: X Cookie の設定（本番）

1. ブラウザで X（x.com）にログイン
2. DevTools（F12）→ **Application** → **Cookies** → `https://x.com`
3. `auth_token` と `ct0` の Value をコピー
4. `.env` に設定:

```env
TWITTER_AUTH_TOKEN=...
TWITTER_CT0=...
USE_MOCK_X=false
```

5. 反映:

```bash
docker compose restart n8n
docker compose exec n8n twitter search "Dify" --json --max 1
```

JSON が返れば認証成功です。

---

## Step 9: 本番テスト

1. ワークフローを手動実行（Test workflow）
2. Discord に朝刊が届くことを確認
3. **Executions** → **HTTP Request (Qiita)** 等で各ソースのデータ取得を確認

---

## Step 10: スケジュール有効化

問題なければ:

1. ワークフロー右上のトグルを **Active** に
2. 毎朝 **07:00 JST** に自動実行されます

---

## 補助スクリプト

```bash
# データソース疎通確認
chmod +x scripts/verify-sources.sh
./scripts/verify-sources.sh

# twitter-cli セットアップ手順の表示
chmod +x scripts/setup-twitter-cli.sh
./scripts/setup-twitter-cli.sh
```

---

## セットアップ完了チェックリスト

- [ ] `docker compose ps` で healthy
- [ ] n8n オーナーアカウント作成済み
- [ ] ワークフローインポート済み
- [ ] Gemini Credential 紐付け済み
- [ ] モックモードで E2E 成功
- [ ] X Cookie 設定・本番 X 取得成功
- [ ] Discord 通知確認
- [ ] ワークフロー Active 化

次は [運用マニュアル](./operations.md) を参照してください。
