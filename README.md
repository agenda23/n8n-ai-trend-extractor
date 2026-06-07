# n8n AIトレンド抽出・リード獲得システム

X / note / Brain / Tips / Qiita の5ソースから超短期AIトレンドを収集し、Gemini 2.5 Flash で顧客獲得（リードマグネット）視点の分析を行い、Slack へ朝刊速報を配信する n8n ワークフローです。

## クイックスタート

### 1. 環境変数の準備

```bash
cp .env.example .env
# .env を編集: GEMINI_API_KEY, SLACK_WEBHOOK_URL 等を設定
```

### 2. n8n 起動

```bash
docker compose up -d --build
open http://localhost:5678
```

初回アクセス時にオーナーアカウントを作成してください。

### 3. ワークフローのインポート

1. n8n GUI → **Workflows** → **Import from File**
2. `workflows/ai-trend-extractor.json` をインポート
3. `workflows/error-handler.json` をインポート（エラー通知用）

### 4. Credentials の設定

| Credential | 種類 | 設定内容 |
|------------|------|----------|
| Google Gemini API | Google Gemini(PaLM) API | Google AI Studio の API キー |

インポート後、**Basic LLM Chain** 配下の **Google Gemini Chat Model** ノードで Credential を選択してください。

### 5. 動作確認（モックモード）

`.env` で `USE_MOCK_X=true`（デフォルト）の状態で、ワークフローを手動実行します。X API を叩かずに E2E テストが可能です。

本番 X 収集に切り替える場合:

```bash
# .env
USE_MOCK_X=false
```

あわせて [twitter-cli 認証](#twitter-cli-認証) を完了してください。

## ディレクトリ構成

```
├── docker/
│   └── Dockerfile              # n8n + twitter-cli
├── docker-compose.yml
├── .env.example
├── workflows/
│   ├── ai-trend-extractor.json # メインワークフロー
│   └── error-handler.json      # エラー通知
├── mock/
│   └── x-tweets-sample.json    # テスト用 X データ
├── scripts/
│   ├── setup-twitter-cli.sh
│   └── verify-sources.sh
├── data/twitter-cli/           # Cookie 認証情報（git 除外）
└── specs/                      # 設計書・仕様書
```

## twitter-cli 認証

twitter-cli は **Python 版**（PyPI: `twitter-cli`）を使用します。

```bash
chmod +x scripts/setup-twitter-cli.sh
./scripts/setup-twitter-cli.sh
```

1. ブラウザで X にログイン
2. DevTools → Application → Cookies → `auth_token` と `ct0` を取得
3. `.env` に `TWITTER_AUTH_TOKEN` と `TWITTER_CT0` を設定
4. Cookie キャッシュは `data/twitter-cli/` に保存され、コンテナと共有されます

コンテナ内での確認:

```bash
docker compose exec n8n twitter search "Dify" --json
```

## データソース疎通確認

```bash
chmod +x scripts/verify-sources.sh
./scripts/verify-sources.sh
```

## 運用コマンド

```bash
# ログ確認
docker compose logs -f n8n

# 再起動
docker compose restart n8n

# 停止
docker compose down

# イメージ再ビルド
docker compose build --no-cache && docker compose up -d
```

## ワークフロー概要

```
Schedule Trigger (毎朝 07:00 JST)
  ├─ IF Mock X → Read Mock / Execute Command (twitter-cli)
  ├─ RSS Read (note-AI副業)
  ├─ RSS Read (note-AIツール)
  ├─ HTTP Request (Brain)  ※検索ページ HTML をパース
  ├─ HTTP Request (Tips)   ※検索ページ HTML をパース
  └─ HTTP Request (Qiita)
        ↓
  Merge All Sources (6入力)
        ↓
  Code (Combine Sources)
        ↓
  Basic LLM Chain (Gemini 2.5 Flash)
        ↓
  Code (Format Notification)
        ↓
  Slack Notification
```

## 注意事項

- **Brain API** (`/api/v1/search`) は 404 のため、検索ページ HTML からリンクを抽出しています
- **X Cookie** は定期的に失効します。`error-handler` ワークフローで Slack 通知されます
- **Qiita トークン** は任意です（未設定でも公開 API で動作、レートリミットあり）
- 仕様書: `specs/AIトレンド抽出システム構築仕様書.md`
- 構築タスク: `specs/構築タスク一覧_Docker版.md`
