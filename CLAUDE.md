# CLAUDE.md

Claude Code 向けのリポジトリガイドです。

## Project Overview

**Docker ベースの n8n 自動化システム**。5ソースから AI トレンドを毎朝 07:00 JST に収集し、Gemini でリード獲得視点の分析を行い、Discord 等へ配信します。**構築完了済み**。

## Documentation

ユーザー向けドキュメントは `docs/` に集約:

- [docs/setup.md](docs/setup.md) — セットアップ
- [docs/workflow-guide.md](docs/workflow-guide.md) — ワークフロー解説・キーワード・プロンプト変更
- [docs/operations.md](docs/operations.md) — 運用・調整
- [docs/configuration.md](docs/configuration.md) — 環境変数
- [docs/architecture.md](docs/architecture.md) — アーキテクチャ
- [docs/troubleshooting.md](docs/troubleshooting.md) — 障害対応

設計資料: `specs/`

## Directory Structure

```
n8n-ai-trend-extractor/
├── docker/Dockerfile           # n8n 2.23.4 + Python twitter-cli
├── docker-compose.yml
├── workflows/
│   ├── ai-trend-extractor.json
│   └── error-handler.json
├── mock/x-tweets-sample.json
├── scripts/
├── docs/                       # ユーザー向けドキュメント
├── specs/                      # 設計書
└── data/twitter-cli/           # Cookie キャッシュ（git 除外）
```

## Runtime Commands

```bash
docker compose up -d --build
docker compose logs -f n8n
docker compose restart n8n
docker compose exec n8n twitter search "Dify" --json --max 1
./scripts/verify-sources.sh
```

## Key Design Decisions

- **Docker canonical** — npm 直接起動ではなく Compose 運用
- **Python twitter-cli** — PyPI 版（npm `@public-clis/twitter-cli` は存在しない）
- **Cookie via `.env`** — `TWITTER_AUTH_TOKEN` + `TWITTER_CT0`
- **Merge node required** — 6入力 combineAll → Code
- **`$('ノード名').all()`** — n8n 2.x 構文（`$node` / `$items()` 廃止）
- **Notification via Code node** — Handlebars 非対応
- **Mock path** — `/home/node/.n8n-files/`（n8n 2.x ファイル制限）

## Unified JSON Schema

| Field | Description |
|-------|-------------|
| `keyword` | Trending tool/method |
| `category` | Classification |
| `market_evidence` | Market buzz evidence |
| `tech_status_pain` | Implementation blockers |
| `lead_hook` | Lead magnet campaign idea |
| `score` | 高/中/低 |

## Credentials

| Credential | Required |
|------------|----------|
| Google Gemini API (n8n Credential) | Yes |
| Discord Webhook (`.env`) | Recommended |
| Qiita token (`.env`) | Optional |
| X Cookie (`.env`) | Production X only |
