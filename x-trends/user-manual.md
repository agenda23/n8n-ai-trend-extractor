# x-trends ユーザーマニュアル

x-trends（X / Twitter トレンド CLI）の汎用リファレンスです。

> **この Mac で個人利用する場合**（グローバル CLI インストール・日常コマンド）は [local-setup.md](./local-setup.md) を参照してください。

## 目次

1. [セットアップ](#1-セットアップ)
2. [環境変数](#2-環境変数)
3. [CLI リファレンス](#3-cli-リファレンス)
4. [HTTP API リファレンス](#4-http-api-リファレンス)
5. [n8n 連携](#5-n8n-連携)
6. [トラブルシューティング](#6-トラブルシューティング)
7. [既知の制限](#7-既知の制限)

---

## 1. セットアップ

### 必要なもの

- Node.js 20+
- pnpm
- X（Twitter）のアカウント

### リポジトリから使う（開発）

```bash
git clone <repo-url>
cd twitter-cli-test
pnpm install
cp .env.example .env
# .env を開き TWITTER_AUTH_TOKEN を記入
pnpm build   # グローバル CLI 利用時
```

### 認証情報

`TWITTER_AUTH_TOKEN` は次の優先順位（高→低）で自動解決されます。

| 順位 | ソース | 用途 |
|------|--------|------|
| 1 | `process.env.TWITTER_AUTH_TOKEN` | シェル export、CI Secrets |
| 2 | `DOTENV_PATH` または `~/.config/x-trends/.env` | グローバル CLI |
| 3 | カレントディレクトリの `.env` | プロジェクトローカル |
| 4 | パッケージルートの `.env` | リポジトリ開発 |

**`auth_token` の確認方法:**

1. x.com にブラウザでログイン
2. DevTools（F12）→ Application → Cookies → `https://x.com`
3. `auth_token` の値をコピー

> セキュリティ: `auth_token` はログインセッションと同等の権限を持ちます。`.env` を Git にコミットしないでください。

### コマンドの呼び方

| 方法 | 例 |
|------|-----|
| リポジトリ内（pnpm script） | `pnpm x-trends list --preset japan` |
| グローバル CLI | `x-trends list --preset japan` |

以降の例は `x-trends` で記載します。リポジトリ内では `pnpm x-trends` に読み替えてください。

### 動作確認

```bash
x-trends settings
# → {"ok":true,"data":{"settings":{"location":null}},...}
```

---

## 2. 環境変数

起動時に自動読み込みされます。**`process.env` に既に設定された値は `.env` より優先**されます。

| 変数名 | 必須 | デフォルト | 説明 |
|--------|------|-----------|------|
| `TWITTER_AUTH_TOKEN` | **はい** | — | X の `auth_token` Cookie 値 |
| `DOTENV_PATH` | いいえ | `~/.config/x-trends/.env` | ユーザー設定 `.env` のパス |
| `API_KEY` | HTTP 時推奨 | — | HTTP API キー（`X-API-Key` ヘッダー） |
| `PORT` | いいえ | `3920` | HTTP サーバーポート |
| `REQUEST_DELAY_MS` | いいえ | `3000` | emusks リクエスト間の最小待機（ms） |
| `CACHE_TTL_SECONDS` | いいえ | `300` | トレンドキャッシュ TTL（秒） |
| `SEARCH_CACHE_TTL_SECONDS` | いいえ | `900` | 検索キャッシュ TTL（秒） |
| `EMUSKS_CLIENT` | いいえ | `web` | emusks クライアント種別（変更非推奨） |
| `LOG_LEVEL` | いいえ | `info` | ログレベル |

---

## 3. CLI リファレンス

### CLI の動作

- 単発コマンド（`list` 等）は完了後 **自動終了**します（emusks / cycletls のバックグラウンドプロセスを解放）。
- `serve` のみ常駐します。
- emusks へのリクエストは **直列** で実行されます（`REQUEST_DELAY_MS` 間隔）。

### グローバルオプション

| オプション | 短縮 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `--format <fmt>` | `-f` | `json` | 出力形式: `json` \| `table` |
| `--raw` | — | false | emusks 生レスポンスを `_raw` に含める |
| `--verbose` | `-v` | false | デバッグログ |
| `--version` | `-V` | — | バージョン |
| `--help` | `-h` | — | ヘルプ |

---

### `list` — トレンド一覧取得

```bash
x-trends list [オプション]
```

| オプション | 短縮 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `--woeid <number>` | `-w` | — | 地域 WOEID |
| `--preset <name>` | `-p` | — | プリセット名（下表） |
| `--count <number>` | `-n` | 20 | 取得件数（最大 50） |
| `--source <src>` | `-s` | `explore` | `explore` \| `sidebar` \| `merge` |
| `--no-exclude-promoted` | — | — | プロモーション込み |
| `--categories <list>` | — | — | `category` フィルタ（カンマ区切り。下表参照） |
| `--diff` | — | false | 前回との差分 |
| `--cursor <cursor>` | — | — | ページネーションカーソル |

**WOEID プリセット:**

| preset | 地域 | WOEID |
|--------|------|-------|
| `worldwide` | 全世界 | 1 |
| `japan` | 日本 | 23424856 |
| `us` | 米国 | 23424977 |
| `uk` | 英国 | 23424975 |
| `tokyo` | 東京 | 1118370 |

**`--source` と API 呼び出し回数:**

| source | 追加呼び出し | 説明 |
|--------|------------|------|
| `explore` | explore 1回 | Explore タブ |
| `sidebar` | sidebar 1回 | サイドバー |
| `merge` | explore + sidebar | 両方取得し名前で重複除去 |

`--preset` / `--woeid` 指定時は login + setLocation + fetch の **3 回以上**（`merge` なら最大 4 回）。`REQUEST_DELAY_MS` により呼び出し間に待機が入ります。

**`--diff`:**

差分は `~/.cache/x-trends/` にスナップショット保存。初回はベースライン作成のみで `changes` は付きません。

**`category` と `description` · `--categories` フィルタ:**

| フィールド | 由来 | 例 | CLI でフィルタ |
|-----------|------|-----|---------------|
| `category` | パーサーが付与 | `trending`, `topic`, `promoted` | `--categories` で可能 |
| `description` | X の `trend_metadata.domain_context` | `"Gaming · Trending"`, `"Trending in Japan"` | **不可**（出力のみ） |

`--categories` は **`category` フィールドのみ** を対象にします。`description` による指定・フィルタオプションはありません。

**`--categories` に指定できる値（実態）:**

| 値 | いつ付くか | 備考 |
|----|-----------|------|
| `trending` | 通常のトレンド | 最も多い |
| `topic` | AI 要約付きトレンド（Explore の `stories` モジュール） | 日本トレンドの上位に出やすい |
| `promoted` | プロモーション | デフォルトでは `--exclude-promoted` により **除外**される。含めるには `--no-exclude-promoted` が必要 |
| `event`, `unknown` | — | 型定義にはあるが **現パーサーでは付与されない**。指定しても通常 0 件 |

未知のカテゴリ名（例: `--categories foo`）を指定してもエラーにはならず、0 件になります。

**`description` で絞りたい場合（後処理）:**

```bash
# "Gaming" を含む description のみ
x-trends list --preset japan --format json \
  | jq '.data.trends[] | select(.description | test("Gaming"))'

# 完全一致
x-trends list --preset japan --format json \
  | jq '.data.trends[] | select(.description == "Trending in Japan")'
```

**使用例:**

```bash
x-trends list --preset japan --format table
x-trends list --preset japan --diff
x-trends list --preset japan --categories trending,topic
x-trends list --preset worldwide --no-exclude-promoted --count 50
```

**出力例（JSON）:**

```json
{
  "ok": true,
  "data": {
    "trends": [
      {
        "id": null,
        "name": "#トレンド名",
        "url": "https://x.com/search?q=...",
        "tweetVolume": 45200,
        "rank": 1,
        "category": "trending",
        "description": "Trending in Japan",
        "hashtags": ["#トレンド名"],
        "warnings": []
      }
    ]
  },
  "meta": {
    "woeid": 23424856,
    "preset": "japan",
    "source": "explore",
    "excludePromoted": true,
    "count": 9,
    "cached": false,
    "apiCalls": 3,
    "parserVersion": "1",
    "partial": false
  }
}
```

---

### `locations` — 地域一覧・検索

```bash
x-trends locations [--search <query>]
```

```bash
x-trends locations --search Tokyo
x-trends locations --search Japan --format table
```

---

### `settings` — Explore 設定確認

```bash
x-trends settings
```

---

### `search` — ツイート検索（Phase 2）

サンプル取得です。完全集計ではありません。

```bash
x-trends search --query <query> [オプション]
```

| オプション | 短縮 | デフォルト | 上限 |
|-----------|------|-----------|------|
| `--query <query>` | `-q` | **必須** | — |
| `--mode <mode>` | `-m` | `top` | `top` \| `latest` |
| `--count <number>` | `-n` | 20 | 20 |
| `--max-pages <number>` | — | 1 | 2 |
| `--since <date>` | — | — | 7 日以内 |

> `meta.sampled: true` が常に付与されます。

```bash
x-trends search --query "#AI" --count 10
x-trends search --query "#AI lang:ja" --mode latest --max-pages 2
```

---

### `detail` — トレンド AI サマリー（Phase 2）

```bash
x-trends detail --id <trendId>
```

> `list` の `id` は通常 `null` です。有効な Trend REST ID が別途必要です。

---

### `serve` — HTTP サーバー

```bash
x-trends serve [--port 3920] [--host 0.0.0.0]
```

---

## 4. HTTP API リファレンス

ベース URL: `http://localhost:3920`

### 認証

`API_KEY` 設定時、`/api/*` には `X-API-Key` ヘッダーが必要です。

### エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | ヘルスチェック（認証不要） |
| GET | `/api/v1/trends` | トレンド一覧 |
| GET | `/api/v1/trends/:trendId` | トレンド詳細 |
| GET | `/api/v1/locations` | 地域一覧 |
| GET | `/api/v1/settings` | Explore 設定 |
| GET | `/api/v1/search` | ツイート検索 |
| GET | `/openapi.json` | OpenAPI 3.0 |

### `GET /api/v1/trends`

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `woeid` | number | — | WOEID |
| `preset` | string | — | `japan` 等 |
| `count` | number | 20 | 最大 50 |
| `source` | string | `explore` | `explore` \| `sidebar` \| `merge` |
| `exclude-promoted` | boolean | `true` | プロモーション除外 |
| `categories` | string | — | カンマ区切り |
| `diff` | boolean | `false` | 差分付与 |
| `raw` | boolean | `false` | 生レスポンス |

```bash
curl "http://localhost:3920/api/v1/trends?preset=japan&diff=true"
```

### エラーレスポンス

```json
{
  "ok": false,
  "error": {
    "code": "UPSTREAM_ERROR",
    "message": "Empty or invalid response during API call..."
  }
}
```

| コード | HTTP | 説明 |
|--------|------|------|
| `AUTH_REQUIRED` | 401 | トークン未設定 / 無効な API キー |
| `AUTH_FAILED` | 401 | X 認証失敗 |
| `RATE_LIMITED` | 429 | レート制限 |
| `INVALID_PARAMS` | 400 | 不正パラメータ |
| `UPSTREAM_ERROR` | 502 | X / emusks 側エラー（空レスポンス等） |
| `PARSE_ERROR` | 502 | パース失敗 |

---

## 5. n8n 連携

```
Schedule Trigger（15分以上）
  ↓
HTTP Request: GET /api/v1/trends?preset=japan&diff=true
  ↓
IF: {{ $json.data.changes.new.length > 0 }}
  ↓
通知ノード
```

**HTTP Request ノード:**

- URL: `http://localhost:3920/api/v1/trends`
- Query: `preset=japan`, `diff=true`
- Headers: `X-API-Key: ...`（`API_KEY` 設定時）

ポーリング間隔は **15 分以上** を推奨します。

---

## 6. トラブルシューティング

### `TWITTER_AUTH_TOKEN is not set`

```bash
echo "$TWITTER_AUTH_TOKEN"
cat ~/.config/x-trends/.env
cat .env
```

### `Error [AUTH_FAILED]: Login failed`

トークンが無効または期限切れです。x.com で再ログインして新しい `auth_token` を取得してください。

### `Error [UPSTREAM_ERROR]: Empty or invalid response...`

X API が空レスポンスを返しました。レート制限・トークン期限切れ・一時的な障害が考えられます。数分後に再試行するか、トークンを更新してください。

```bash
x-trends list --preset japan --raw
```

### `Error [RATE_LIMITED]`

数分待って再試行。`REQUEST_DELAY_MS` を増やすと緩和できます。

```bash
REQUEST_DELAY_MS=5000 x-trends list --preset japan
```

### トレンド 0 件 / `partial: true`

GraphQL 構造変更の可能性。`--raw` で生レスポンスを確認してください。

### `--diff` で `changes` が出ない

初回実行はスナップショット作成のみ。2 回目以降に差分が表示されます。

```bash
ls ~/.cache/x-trends/
```

### 出力後に終了しない

最新版では CLI 完了後に自動終了します。古いビルドの場合は `pnpm build` してください。

---

## 7. 既知の制限

| 項目 | 説明 |
|------|------|
| `id` が `null` | Explore トレンドは REST ID が取得できない |
| `search` はサンプル | 完全集計ではない |
| 並列リクエスト禁止 | BAN リスクあり |
| `--since` | 7 日以内のみ |
| emusks AGPL-3.0 | ネットワーク提供時はソース公開義務に注意 |

---

## 関連ドキュメント

- [local-setup.md](./local-setup.md) — この Mac 向けセットアップ・CLI 早見表
- [../README.md](../README.md) — プロジェクト概要
- [../spec/](../spec/) — 設計仕様
