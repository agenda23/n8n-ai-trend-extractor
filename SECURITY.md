# セキュリティポリシー

## 報告方法

セキュリティ上の脆弱性を発見した場合は、**公開 Issue ではなく** リポジトリオーナーに直接ご連絡ください。

## 取り扱い上の注意

### 秘密情報の管理

以下は **絶対に Git にコミットしない** でください:

| 種類 | ファイル / 場所 |
|------|----------------|
| 環境変数 | `.env` |
| X Cookie | `TWITTER_AUTH_TOKEN`, `TWITTER_CT0` |
| API キー | Gemini, Qiita, Webhook URL |
| n8n データ | `n8n_data/` ボリューム |
| Cookie キャッシュ | `data/twitter-cli/` |

`.gitignore` で除外済みですが、コミット前に `git status` で確認してください。

### 推奨運用

- n8n は `localhost` でのローカル運用を推奨
- 外部公開する場合はリバースプロキシ + 認証（Basic Auth / OAuth）を設定
- X アカウントは閲覧用サブアカウントを使用
- Cookie は月1回程度でローテーション
- Docker イメージは定期的に更新

### Execute Command のリスク

n8n の Execute Command ノードはシェルコマンドを実行します。本ワークフローでは `twitter search` のみを使用しています。不要なコマンドを追加しないでください。

## 依存関係

- n8n: `n8nio/n8n:2.23.4`（Dockerfile で固定）
- twitter-cli: PyPI `twitter-cli`

定期的にベースイメージのセキュリティアップデートを確認してください。
