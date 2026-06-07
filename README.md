# n8n AIトレンド抽出・リード獲得システム

X / note / Brain / Tips / Qiita の5ソースから超短期 AI トレンドを自動収集し、Gemini で顧客獲得（リードマグネット）視点の分析を行い、Discord 等へ朝刊速報を配信する **Docker + n8n** ワークフローです。

## 特徴

- **5ソース並列収集**: X（twitter-cli）、note RSS、Brain/Tips 検索、Qiita API
- **Gemini 分析**: トレンド抽出 + リードマグネット施策案を JSON 構造化
- **毎朝自動実行**: Schedule Trigger（07:00 JST）
- **モックモード**: X API を使わずに E2E テスト可能
- **セルフホスト**: Cookie やプロンプトを外部に漏らさない

## クイックスタート

```bash
git clone <repository-url>
cd n8n-ai-trend-extractor
cp .env.example .env
# .env を編集

docker compose up -d --build
open http://localhost:5678
```

1. n8n でオーナーアカウントを作成
2. `workflows/ai-trend-extractor.json` をインポート
3. Gemini Credential を設定
4. Test workflow で動作確認

詳細は **[セットアップマニュアル](docs/setup.md)** を参照してください。

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/README.md](docs/README.md) | ドキュメント索引 |
| [セットアップマニュアル](docs/setup.md) | 初回構築手順 |
| [ワークフロー解説・カスタマイズ](docs/workflow-guide.md) | ノード解説・キーワード・プロンプト変更 |
| [運用マニュアル](docs/operations.md) | 日常運用・調整・チューニング |
| [設定リファレンス](docs/configuration.md) | 環境変数・Credentials |
| [アーキテクチャ](docs/architecture.md) | システム構成・データフロー |
| [トラブルシューティング](docs/troubleshooting.md) | よくあるエラーと対処 |
| [FAQ](docs/faq.md) | よくある質問 |

設計資料（開発者向け）: `specs/` ディレクトリ

## ディレクトリ構成

```
n8n-ai-trend-extractor/
├── docker/                  # Dockerfile（n8n + twitter-cli）
├── docker-compose.yml
├── workflows/               # n8n ワークフロー JSON
├── mock/                    # テスト用 X データ
├── scripts/                 # 疎通確認・セットアップ補助
├── docs/                    # ユーザー向けドキュメント
├── specs/                   # 設計書・仕様書
└── data/twitter-cli/        # Cookie キャッシュ（git 除外）
```

## 必要なもの

| 項目 | 必須 |
|------|------|
| Docker + Compose v2 | ✅ |
| Google Gemini API キー | ✅ |
| X Cookie（本番 X 時） | ✅ |
| Discord Webhook（通知時） | 推奨 |

## ワークフロー概要

```
Schedule (07:00 JST) → 5ソース収集 → Merge → Code 統合
  → Gemini LLM Chain → 通知整形 → Discord
```

## ライセンス

[MIT License](LICENSE)

## セキュリティ

秘密情報の取り扱いについては [SECURITY.md](SECURITY.md) を参照してください。

## コントリビューション

[CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
