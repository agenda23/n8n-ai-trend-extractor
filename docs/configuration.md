# 設定リファレンス

## 環境変数（`.env`）

`.env.example` をコピーして `.env` を作成します。**`.env` は Git にコミットしないでください。**

### n8n 基本設定

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `N8N_HOST` | `localhost` | n8n ホスト名 |
| `N8N_PORT` | `5678` | n8n ポート |
| `N8N_PROTOCOL` | `http` | プロトコル |
| `N8N_SECURE_COOKIE` | `false` | セキュア Cookie（HTTP ローカルでは `false`、HTTPS 本番では `true` 推奨） |
| `GENERIC_TIMEZONE` | `Asia/Tokyo` | スケジュールのタイムゾーン |
| `TZ` | `Asia/Tokyo` | コンテナのシステム TZ |

### n8n 動作設定（変更非推奨）

| 変数 | 値 | 説明 |
|------|-----|------|
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | `true` | 設定ファイルの権限強制 |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` | Code ノードから `$env` 参照を許可 |
| `NODES_EXCLUDE` | `[]` | （旧 Execute Command 用・現行ワークフローでは未使用） |

### データ収集

| 変数 | 必須 | 説明 |
|------|------|------|
| `USE_MOCK_X` | - | `true`: モックデータ使用 / `false`: 本番 X |
| `TWITTER_AUTH_TOKEN` | 本番 X 時 | x-trends 用 X Cookie `auth_token` |
| `X_TRENDS_BASE_URL` | - | n8n から x-trends への URL（デフォルト `http://x-trends:3920`） |
| `X_TRENDS_API_KEY` | 任意 | x-trends HTTP API キー（`API_KEY` 設定時） |
| `QIITA_ACCESS_TOKEN` | 任意 | Qiita API トークン（レート緩和） |

### 通知

| 変数 | 必須 | 説明 |
|------|------|------|
| `DISCORD_WEBHOOK_URL` | 通知時 | Discord Incoming Webhook |
| `SLACK_WEBHOOK_URL` | 通知時 | Slack Incoming Webhook |

### 参照用（n8n Credentials で管理するもの）

| 変数 | 説明 |
|------|------|
| `GEMINI_API_KEY` | Gemini API キー（n8n Credential にも登録） |

### MCP 連携（任意）

| 変数 | 説明 |
|------|------|
| `N8N_API_KEY` | n8n Personal API Key |
| `N8N_BASE_URL` | `http://localhost:5678` |

---

## n8n Credentials

GUI で設定する認証情報です。

| Credential 名 | 種類 | 用途 | 必須 |
|--------------|------|------|------|
| Google Gemini API | Google Gemini(PaLM) API | LLM 分析 | **必須** |
| Qiita API Token | HTTP Header Auth | Qiita 取得（任意） | 任意 |

### Gemini Credential の紐付け先

**Google Gemini Chat Model** ノード（Basic LLM Chain のサブノード）

---

## Docker ボリューム

| ホスト | コンテナ | 用途 |
|--------|----------|------|
| `n8n_data`（名前付き） | `/home/node/.n8n` | n8n データ永続化 |
| `./mock` | `/home/node/.n8n-files/mock`（読み取り専用） | モックデータ |

> n8n 2.x のファイル読み込み制限により、モック利用時は `/home/node/.n8n-files/` 配下へのマウントを推奨します。詳細は [セットアップマニュアル](./setup.md) Step 7 を参照。

---

## ワークフロー環境変数の参照

ワークフロー内で `$env` を参照するノード:

| ノード | 参照 |
|--------|------|
| IF Mock X | `$env.USE_MOCK_X` |
| HTTP Request (X Trends) | `$env.X_TRENDS_BASE_URL`, `$env.X_TRENDS_API_KEY` |
| HTTP Request (Qiita) | `$env.QIITA_ACCESS_TOKEN` |
| Discord / Slack 通知 | `$env.DISCORD_WEBHOOK_URL` 等 |

`.env` 変更後は `docker compose restart n8n` が必要です。

---

## 設定例

### 開発・テスト

```env
USE_MOCK_X=true
GENERIC_TIMEZONE=Asia/Tokyo
```

### 本番運用

```env
USE_MOCK_X=false
TWITTER_AUTH_TOKEN=xxxxxxxx
X_TRENDS_BASE_URL=http://x-trends:3920
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
GENERIC_TIMEZONE=Asia/Tokyo
```
