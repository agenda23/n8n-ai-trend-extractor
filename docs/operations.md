# 運用マニュアル

日常運用・調整・チューニングの手順です。

## 日常運用

### 毎日の確認（推奨）

1. n8n GUI → **Executions** で直近の実行結果を確認
2. Discord に朝刊が届いているか確認（07:00 頃）
3. 失敗がある場合は [トラブルシューティング](./troubleshooting.md) を参照

### 基本コマンド

```bash
# ログ確認
docker compose logs -f n8n

# 再起動（.env 変更後）
docker compose restart n8n

# 停止
docker compose down

# 再ビルド（Dockerfile 変更後）
docker compose build --no-cache && docker compose up -d
```

---

## X Cookie の更新

Cookie は **月1回程度** 失効します。X データ取得が失敗したら更新してください。

### 手順

1. ブラウザで X に再ログイン
2. DevTools → Cookies → `auth_token` / `ct0` を取得
3. `.env` を更新:

```env
TWITTER_AUTH_TOKEN=新しい値
TWITTER_CT0=新しい値
```

4. 反映と確認:

```bash
docker compose restart n8n
docker compose exec n8n twitter search "Dify" --json --max 1
```

5. 古いキャッシュを削除する場合:

```bash
rm -f data/twitter-cli/*
docker compose restart n8n
```

---

## モックモードと本番モードの切り替え

| モード | `.env` | 用途 |
|--------|--------|------|
| モック | `USE_MOCK_X=true` | テスト・Gemini 節約・X API 不使用 |
| 本番 | `USE_MOCK_X=false` | 実際の X データ収集 |

変更後は必ず `docker compose restart n8n` を実行してください。

---

## 調整ガイド

> ノードごとの詳細な解説・キーワード・プロンプトの変更手順は [ワークフロー解説・カスタマイズガイド](./workflow-guide.md) を参照してください。

### 1. 実行スケジュールの変更

**Schedule Trigger** ノードを編集:

- デフォルト: 毎日 07:00 JST（cron: `0 7 * * *`）
- タイムゾーンは `.env` の `GENERIC_TIMEZONE=Asia/Tokyo` と連動

### 2. X 検索キーワードの変更

**Execute Command** ノードのコマンドを編集:

```bash
twitter search '"キーワード1" OR "キーワード2"' \
  --since {{ $today.minus({ days: 3 }).toISODate() }} \
  --until {{ $today.plus({ days: 1 }).toISODate() }} \
  --min-likes 15 --json
```

| パラメータ | 説明 | 調整例 |
|-----------|------|--------|
| 検索クエリ | トレンド対象キーワード | 自社ニッチに合わせて追加 |
| `--min-likes` | 最低いいね数 | `10`（緩く）〜 `30`（厳しく） |
| `--since` / `--until` | 取得期間 | `days: 5` で5日間に拡大 |

### 3. note RSS フィードの追加・変更

**RSS Read** ノードの URL を変更、またはノードを複製して追加:

- AI副業: `https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss`
- AIツール: `https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss`

追加時は **Merge All Sources** の入力数と **Code (Combine Sources)** の `$node["ノード名"]` 参照を更新してください。

### 4. Gemini プロンプトの調整

**Basic LLM Chain** のシステムプロンプトを編集:

- ターゲット層の定義（例: 「SaaS 創業者」に特化）
- 抽出トレンド数（「最大5つ」→「最大3つ」）
- リードマグネットのトーン（例: より具体的なタイトルを要求）

**Structured Output Parser** の JSON スキーマは [仕様書](../specs/AIトレンド抽出システム構築仕様書.md) §4.4② に準拠してください。

### 5. Gemini モデルの変更

**Google Gemini Chat Model** ノード:

| モデル | 特徴 |
|--------|------|
| `models/gemini-2.5-flash` | 最新・高速（503/429 が出やすい場合あり） |
| `models/gemini-2.0-flash` | 安定 |
| `models/gemini-1.5-flash` | さらに安定（レガシー） |

429（クォータ超過）が頻発する場合はモデル変更より **Google Cloud 課金有効化** を検討してください。

### 6. 通知先の変更

| 通知先 | 設定方法 |
|--------|----------|
| Discord | HTTP Request → `{ content: $json.text }` |
| Slack | HTTP Request → `{ text: $json.text }` |
| 通知なし | **Code (Format Notification)** で終了。Executions で確認 |
| Google Sheets | Google Sheets ノードで `trends` 配列を行追加 |
| Notion | Notion ノードで DB にページ作成 |

Discord の `content` は **最大2000文字** です。超える場合は Code ノードで分割送信を検討してください。

### 7. 取得件数の調整（トークン節約）

**Code (Combine Sources)** 内のスライス数:

| ソース | デフォルト | 変数箇所 |
|--------|-----------|----------|
| X | 50件 | `count >= 50` |
| note | 15件 | `.slice(0, 15)` |
| Brain / Tips | 10件 | `.slice(0, 10)` |
| Qiita | 15件 | `.slice(0, 15)` |

Gemini のクォータ節約には件数を減らすのが効果的です。

### 8. リトライ設定

**Basic LLM Chain** → **Settings**:

- **Retry On Fail**: ON/OFF
- **Max. Tries**: `1`（再試行なし）〜 `3`
- **Wait Between Tries**: 最大 `5000` ms（n8n の上限）

429 対策としてリトライを増やしても効果は限定的です。クォータ回復を待つ方が確実です。

---

## ワークフローのバックアップ

n8n GUI で定期的にエクスポート:

1. ワークフロー → **⋯** → **Download**
2. `workflows/` に上書き保存（Git 管理推奨）

n8n データ全体は Docker ボリューム `n8n_data` に保存されます。

```bash
# ボリューム一覧
docker volume ls | grep n8n
```

---

## バージョンアップ

### n8n イメージの更新

`docker/Dockerfile` のベースイメージタグを変更:

```dockerfile
FROM n8nio/n8n:2.23.4
```

```bash
docker compose build --no-cache && docker compose up -d
```

アップデート前にワークフローをエクスポートしておいてください。

---

## セキュリティ運用

- `.env` は **絶対に Git にコミットしない**
- X Cookie は定期的にローテーション
- n8n はローカルホスト（`localhost:5678`）での運用を推奨
- 外部公開する場合はリバースプロキシ + 認証を追加

詳細は [SECURITY.md](../SECURITY.md) を参照してください。
