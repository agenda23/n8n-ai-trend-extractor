# コントリビューションガイド

ご協力ありがとうございます。以下のガイドラインに沿ってご参加ください。

## 開発環境

```bash
cp .env.example .env
docker compose up -d --build
```

詳細は [docs/setup.md](docs/setup.md) を参照してください。

## 変更の流れ

1. Issue で議論（大きな変更の場合）
2. ブランチを作成: `feature/xxx` または `fix/xxx`
3. 変更を実施
4. ワークフローを変更した場合は n8n からエクスポートし `workflows/` を更新
5. ドキュメントを必要に応じて更新（`docs/`）
6. Pull Request を作成

## コーディング規約

- 既存のディレクトリ構成・命名規則に従う
- 秘密情報（API キー、Cookie）はコミットしない
- `.env.example` に新しい環境変数を追記する
- 仕様変更時は `specs/` の該当ドキュメントも更新する

## ワークフロー JSON の更新

1. n8n GUI で変更
2. **Download** でエクスポート
3. `workflows/ai-trend-extractor.json` を上書き
4. PR に変更内容を記載

## ドキュメント

ユーザー向け: `docs/`  
設計資料: `specs/`

## 質問・バグ報告

GitHub Issues を利用してください。バグ報告時は以下を含めてください:

- 再現手順
- 期待する動作と実際の動作
- n8n / Docker のバージョン
- 関連する Executions のエラーメッセージ
