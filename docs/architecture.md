# アーキテクチャ

## 概要

Docker 上の n8n をハブに、5つのデータソースから情報を収集し、Gemini で顧客獲得視点のトレンド分析を行い、Discord 等へ配信するシステムです。

## システム構成図

```
[ホストマシン]
  docker compose up
    └─ n8n コンテナ（カスタムイメージ）
          ├─ n8n 2.23.4
          ├─ twitter-cli（Python版）
          └─ 環境変数・ボリューム

[n8n ワークフロー]
  Schedule Trigger (07:00 JST)
    ├─ IF Mock X
    │    ├─ true  → Read Mock X → Normalize Mock X
    │    └─ false → Execute Command (twitter-cli)
    ├─ RSS Read (note-AI副業)
    ├─ RSS Read (note-AIツール)
    ├─ HTTP Request (Brain)   ※HTML パース
    ├─ HTTP Request (Tips)    ※HTML パース
    └─ HTTP Request (Qiita)   ※REST API
          ↓
    Merge All Sources (6入力)
          ↓
    Code (Combine Sources)
          ↓
    Basic LLM Chain
      ├─ Google Gemini Chat Model
      └─ Structured Output Parser
          ↓
    Code (Format Notification)
          ↓
    HTTP Request (Discord / Slack)
```

## コンポーネント

### Docker イメージ

| 要素 | 説明 |
|------|------|
| ベース | `n8nio/n8n:2.23.4` |
| 追加 | Python 3.12 + `twitter-cli`（マルチステージビルド） |
| ポート | `5678` |

### データソース

| # | ソース | 取得方法 | データ形式 |
|---|--------|----------|-----------|
| 1 | X | `twitter-cli`（Cookie 認証） | JSON (`{ data: [...] }`) |
| 2 | note | RSS（2フィード） | XML → 記事メタ |
| 3 | Brain | 検索ページ HTTP | HTML → リンク抽出 |
| 4 | Tips | 検索ページ HTTP | HTML → タイトル・URL 抽出 |
| 5 | Qiita | REST API v2 | JSON（記事メタ） |

> Brain の公式 API (`/api/v1/search`) は 404 のため、検索ページ HTML からリンクを抽出しています。

### AI 分析

| 要素 | 設定 |
|------|------|
| モデル | Gemini 2.0 Flash / 2.5 Flash |
| Temperature | 0.3 |
| 出力 | Structured JSON（`trends` 配列、最大5件） |

出力スキーマ:

| フィールド | 説明 |
|-----------|------|
| `keyword` | トレンドキーワード |
| `category` | 分類 |
| `market_evidence` | 実売・バズの根拠 |
| `tech_status_pain` | 実装上の課題（Qiita 等から推論） |
| `lead_hook` | リードマグネット施策案 |
| `score` | 顧客獲得価値（高/中/低） |

### 認証の流れ

```
.env (TWITTER_AUTH_TOKEN, TWITTER_CT0)
  → docker-compose.yml (environment)
    → コンテナ内 twitter-cli
      → Execute Command ノード
```

Gemini API キーは n8n **Credentials** で管理（`.env` の `GEMINI_API_KEY` は参照用）。

## ディレクトリ構成

```
n8n-ai-trend-extractor/
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── workflows/
│   ├── ai-trend-extractor.json
│   └── error-handler.json
├── mock/
│   └── x-tweets-sample.json
├── scripts/
│   ├── setup-twitter-cli.sh
│   └── verify-sources.sh
├── data/twitter-cli/        # Cookie キャッシュ（git 除外）
├── docs/                    # ユーザー向けドキュメント
└── specs/                   # 設計書・仕様書
```

## 設計上の判断

| 判断 | 理由 |
|------|------|
| Docker 運用 | 再現性・twitter-cli 同梱・環境変数管理 |
| Python 版 twitter-cli | npm 版は存在せず、実際の CLI は PyPI 版 |
| Merge ノード必須 | n8n 2.x で並列ブランチを Code に統合するため |
| `$node["名前"].all()` | n8n 2.x で `$items()` 廃止 |
| Code ノードで通知整形 | n8n は Handlebars 非対応 |
| モックモード | 開発時の X API 節約・BAN 回避 |

## 関連ドキュメント

- [セットアップマニュアル](./setup.md)
- [設定リファレンス](./configuration.md)
- [仕様書](../specs/AIトレンド抽出システム構築仕様書.md)
