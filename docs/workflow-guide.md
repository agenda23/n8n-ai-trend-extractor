# n8n ワークフロー解説・カスタマイズガイド

`workflows/ai-trend-extractor.json`（**AIトレンド抽出・リード獲得**）のノード構成、データの流れ、キーワード・プロンプトの変更方法を解説します。

---

## 1. ワークフロー全体像

```
Schedule Trigger（毎朝 07:00 JST）
  │
  ├─ IF Mock X ─┬─ true  → Read Mock X → Normalize Mock X ─┐
  │             └─ false → Execute Command (X検索) ─────────┤
  ├─ RSS Read (note-AI副業) ────────────────────────────────┤
  ├─ RSS Read (note-AIツール) ──────────────────────────────┤
  ├─ HTTP Request (Brain) ──────────────────────────────────┤
  ├─ HTTP Request (Tips) ───────────────────────────────────┤
  └─ HTTP Request (Qiita) ──────────────────────────────────┤
                                                            ↓
                                              Merge All Sources（6入力）
                                                            ↓
                                              Code (Combine Sources)
                                                            ↓
                                              Basic LLM Chain
                                                ├─ Google Gemini Chat Model
                                                └─ Structured Output Parser
                                                            ↓
                                              Code (Format Notification)
                                                            ↓
                                              Discord / Slack 通知
```

**処理の流れ（3段階）:**

1. **収集** — 5ソースから直近3日程度のデータを並列取得
2. **分析** — 統合テキストを Gemini に渡し、トレンド＋リード施策を JSON 化
3. **配信** — 朝刊フォーマットに整形して Discord 等へ送信

---

## 2. ノード一覧と役割

### Phase 1: トリガー・X データ

| ノード名 | 種類 | 役割 |
|----------|------|------|
| **Schedule Trigger** | スケジュール | 毎日 07:00 JST にワークフローを起動 |
| **IF Mock X** | 条件分岐 | `.env` の `USE_MOCK_X` が `true` か判定 |
| **Read Mock X** | ファイル読込 | テスト用 JSON を読み込み（本番では通らない） |
| **Normalize Mock X** | Code | モックデータを `stdout` 形式に変換 |
| **Execute Command** | シェル実行 | `twitter-cli` で X をキーワード検索 |

### Phase 2: その他ソース収集

| ノード名 | 種類 | 役割 |
|----------|------|------|
| **RSS Read (note-AI副業)** | RSS | note の AI副業ハッシュタグ新着 |
| **RSS Read (note-AIツール)** | RSS | note の AIツールハッシュタグ新着 |
| **HTTP Request (Brain)** | HTTP | Brain 検索ページ（HTML）を取得 |
| **HTTP Request (Tips)** | HTTP | Tips 検索ページ（HTML）を取得 |
| **HTTP Request (Qiita)** | HTTP | Qiita API で AI タグ記事を取得 |

### Phase 3: 統合・分析・通知

| ノード名 | 種類 | 役割 |
|----------|------|------|
| **Merge All Sources** | Merge | 6ブランチの完了を待って合流 |
| **Code (Combine Sources)** | Code | 5ソースを1つの `textData` テキストに統合 |
| **Basic LLM Chain** | AI Chain | システムプロンプト + 入力データで分析 |
| **Google Gemini Chat Model** | AI Model | Gemini モデル・Temperature 設定 |
| **Structured Output Parser** | AI Parser | 出力を JSON スキーマに強制 |
| **Code (Format Notification)** | Code | Discord 向け朝刊テキストを生成 |
| **Slack Notification** | HTTP | Webhook 送信（Discord に差し替え可） |

---

## 3. 各ノードの詳細

### Schedule Trigger

- **cron**: `0 7 * * *`（毎日 7:00）
- **タイムゾーン**: ワークフロー設定 + `.env` の `GENERIC_TIMEZONE=Asia/Tokyo`
- 6つの収集ブランチを **同時に** 起動する

### IF Mock X

| 条件 | 分岐先 |
|------|--------|
| `USE_MOCK_X` = `true` | Read Mock X（テスト用） |
| `false` | Execute Command（本番 X） |

`.env` 変更後は `docker compose restart n8n` が必要です。

### Execute Command（X 検索）

コンテナ内で `twitter-cli` を実行します。Cookie は `.env` の `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` から読み込まれます。

### Merge All Sources

- **Mode**: Combine
- **Combine By**: Combine All
- **Number of Inputs**: 6

並列ブランチがすべて完了するまで待ち、**Code (Combine Sources)** を1回だけ実行します。Merge がないと Code ノードは1ブランチ分しか受け取れません。

### Code (Combine Sources)

- **実行モード**: Run Once for All Items
- **出力**: `{ textData: "統合テキスト" }`

各ソースの生データを Gemini が読みやすいプレーンテキストに変換します。`$node["ノード名"].all()` で他ノードの出力を参照します（n8n 2.x 構文）。

### Basic LLM Chain

- **User Message（入力）**: `={{ $json.textData }}`（統合テキスト）
- **System Message**: マーケティングディレクター役のプロンプト（後述）
- **Output Parser**: Structured Output Parser に接続

### Structured Output Parser

Gemini の出力を次の JSON 形式に強制します:

```json
{
  "trends": [
    {
      "keyword": "トレンドキーワード",
      "category": "分類",
      "market_evidence": "実売・バズの根拠",
      "tech_status_pain": "実装上の課題",
      "lead_hook": "リードマグネット施策案",
      "score": "高（即時実践推奨）"
    }
  ]
}
```

`score` の選択肢: `高（即時実践推奨）` / `中（検証フェーズ）` / `低（様子見）`

---

## 4. キーワード・検索条件の変更方法

n8n GUI で該当ノードをダブルクリックし、**Save** で保存します。

### 4.1 X（Twitter）検索キーワード

**ノード**: `Execute Command` → **Command** フィールド

**現在の設定:**

```bash
twitter search '"ClaudeCode" OR "Claude Code" OR "爆速" OR "爆益" OR "儲かる" OR "神ワザ" OR "完全自動化" OR "誰も知らなかった" OR "ワークフロー" OR "Dify" OR "Cursor"' \
  --since {{ $today.minus({ days: 3 }).toISODate() }} \
  --until {{ $today.plus({ days: 1 }).toISODate() }} \
  --min-likes 15 --json
```

| パラメータ | 変更方法 | 例 |
|-----------|----------|-----|
| **検索キーワード** | `OR` で結合した `"キーワード"` を追加・削除 | `"n8n" OR "Make"` を追加 |
| **取得期間（開始）** | `days: 3` の数字を変更 | `days: 5` で5日間 |
| **取得期間（終了）** | `plus({ days: 1 })` で当日を含む | そのまま推奨 |
| **最低いいね数** | `--min-likes 15` の数字 | `10`（緩く）/ `30`（厳しく） |
| **検索タブ** | `-t Latest` を末尾に追加 | 最新順で取得 |

**変更例（n8n・自動化に特化）:**

```bash
twitter search '"n8n" OR "Make" OR "Zapier" OR "ClaudeCode" OR "爆速" OR "AI副業"' \
  --since {{ $today.minus({ days: 3 }).toISODate() }} \
  --until {{ $today.plus({ days: 1 }).toISODate() }} \
  --min-likes 10 -t Latest --json
```

**注意**: キーワードを増やすとヒット数・トークン量が増えます。Gemini クォータに注意してください。

---

### 4.2 note RSS フィード

**ノード**: `RSS Read (note-AI副業)` / `RSS Read (note-AIツール)` → **URL**

| ノード | 現在の URL |
|--------|-----------|
| note-AI副業 | `https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss` |
| note-AIツール | `https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss` |

**フィードを追加する場合:**

1. RSS Read ノードを複製
2. ノード名を一意にする（例: `RSS Read (note-自動化)`）
3. Schedule Trigger から新ノードへ接続
4. 新ノード → Merge All Sources（入力数を 7 に増やす）
5. **Code (Combine Sources)** に新ノードの参照を追加:

```javascript
...$node["RSS Read (note-自動化)"].all()
```

---

### 4.3 Brain 検索キーワード

**ノード**: `HTTP Request (Brain)` → **URL**

**現在**: `https://brain-market.com/search?keyword=AI`

| 変更 | 例 |
|------|-----|
| キーワード変更 | `?keyword=ChatGPT` |
| 別カテゴリ | `?keyword=副業` |

レスポンスは HTML のため、Code ノード内の `parseBrainHtml()` でリンクを抽出しています。

---

### 4.4 Tips 検索キーワード

**ノード**: `HTTP Request (Tips)` → **URL**

**現在**: `https://tips.jp/search?q=AI`

| 変更 | 例 |
|------|-----|
| キーワード変更 | `?q=ChatGPT` |
| 複合検索 | `?q=AI+副業` |

---

### 4.5 Qiita 検索条件

**ノード**: `HTTP Request (Qiita)` → **URL**

**現在**:

```
https://qiita.com/api/v2/items?query=tag:AI+created:>={{ $today.minus({ days: 3 }).toISODate() }}&per_page=20
```

| パラメータ | 変更方法 | 例 |
|-----------|----------|-----|
| タグ | `tag:AI` 部分 | `tag:Python` / `tag:n8n` |
| 期間 | `days: 3` | `days: 7` |
| 件数 | `per_page=20` | `per_page=30` |
| キーワード検索 | `query=` を変更 | `query=Claude+created:>=...` |

**変更例:**

```
=https://qiita.com/api/v2/items?query=tag:AI+OR+tag:n8n+created:>={{ $today.minus({ days: 5 }).toISODate() }}&per_page=15
```

---

### 4.6 Code (Combine Sources) の取得件数

**ノード**: `Code (Combine Sources)` → **JavaScript**

| ソース | 制限箇所 | デフォルト |
|--------|----------|-----------|
| X | `count >= 50` | 50件 |
| note | `.slice(0, 15)` | 15件 |
| Brain | `items.length >= 10` | 10件 |
| Tips | `items.length >= 10` | 10件 |
| Qiita | `.slice(0, 15)` | 15件 |

Gemini のトークン節約にはここを減らすのが効果的です。

**X のスパム除外キーワード**（削除したい投稿に含まれる文字列）:

```javascript
!text.includes('公式LINE') && !text.includes('プレゼント企画') && !text.includes('プロフをチェック')
```

除外ワードを追加する場合は `&& !text.includes('新しいワード')` を追記します。

---

## 5. プロンプトの変更方法

### 5.1 システムプロンプト（分析の方向性）

**ノード**: `Basic LLM Chain` → **Messages** → System メッセージ

**現在のプロンプト（要約）:**

| セクション | 内容 |
|-----------|------|
| 【役割】 | AI副業・自動化に精通したマーケティングディレクター |
| 【入力データ】 | X / note・Brain・Tips / Qiita の統合データ |
| 【タスク】 | 超短期トレンドを最大5つ抽出 + リードマグネット企画 |
| 【分析の軸】 | 4つの思考プロセス |

**カスタマイズ例:**

```
【役割】
あなたはBtoB SaaS向けのリード獲得を専門とするマーケティングディレクターです。

【タスク】
トレンドを最大3つに絞り、各トレンドに対して
「無料トライアルに繋がるホワイトペーパー案」を提案してください。

【禁止事項】
- 根拠のない「爆益」表現は使わない
- 入力データにないキーワードを捏造しない
```

**変更のコツ:**

- **役割** を自社のターゲットに合わせる（例: 「法人向け DX コンサル」）
- **タスク** で出力数を変える（「最大5つ」→「最大3つ」）
- **禁止事項** を追加してハルシネーションを抑制
- **分析の軸** に自社サービスの強みを追加

---

### 5.2 入力データ（User Message）

**ノード**: `Basic LLM Chain` → **Text** フィールド

**現在**: `={{ $json.textData }}`

通常は変更不要です。前段の **Code (Combine Sources)** が生成した統合テキストがそのまま渡されます。

---

### 5.3 出力スキーマ（Structured Output Parser）

**ノード**: `Structured Output Parser` → **JSON Schema Example**

フィールドを追加・変更すると Gemini の出力形式が変わります。**Code (Format Notification)** も合わせて修正が必要です。

**現在のフィールド:**

| フィールド | 説明 |
|-----------|------|
| `keyword` | トレンドキーワード |
| `category` | 分類 |
| `market_evidence` | 実売・バズの根拠 |
| `tech_status_pain` | 実装上の課題 |
| `lead_hook` | リードマグネット施策案 |
| `score` | 顧客獲得価値（高/中/低） |

**フィールド追加例**（`urgency` を追加する場合）:

1. Structured Output Parser の JSON に `"urgency": "今週中に動くべき理由"` を追加
2. **Code (Format Notification)** に表示行を追加:

```javascript
message += `・緊急度: ${t.urgency}\n`;
```

---

### 5.4 Gemini モデル設定

**ノード**: `Google Gemini Chat Model` → **Parameters**

| 設定 | 現在値 | 変更の目安 |
|------|--------|-----------|
| **Model** | `models/gemini-2.5-flash` | 429/503 時は `gemini-2.0-flash` |
| **Temperature** | `0.3` | 創造性 UP: `0.5` / 安定重視: `0.1` |

Temperature が高いほどリード施策案が多様になりますが、ぶれも増えます。

---

### 5.5 朝刊通知テンプレート

**ノード**: `Code (Format Notification)` → **JavaScript**

Discord に届くテキストのフォーマットを制御します。

**変更できる要素:**

| 要素 | コード上の位置 |
|------|---------------|
| ヘッダー文言 | `📢 【朝刊】...` の行 |
| 各トレンドの表示形式 | `for (const t of trends)` ループ内 |
| 区切り線 | `--------------------------------------------------` |

**Discord 2000文字制限** があるため、トレンド数や各フィールドの長さに注意してください。

---

## 6. 変更後の確認手順

1. ワークフロー右上 **Save**
2. **Test workflow** で手動実行
3. **Executions** で各ノードの INPUT/OUTPUT を確認
   - 収集ノード: データが取れているか
   - Code (Combine Sources): `textData` の中身
   - Basic LLM Chain: `trends` 配列
   - Code (Format Notification): `text` の朝刊文
4. 問題なければ **Active** のまま運用

大きな変更後は **Download** で `workflows/ai-trend-extractor.json` をエクスポートし Git に保存することを推奨します。

---

## 7. カスタマイズ早見表

| 変えたいもの | 編集するノード | フィールド |
|-------------|---------------|-----------|
| 実行時刻 | Schedule Trigger | cron 式 |
| X 検索ワード | Execute Command | Command |
| X 取得期間 | Execute Command | `--since` / `--until` |
| X 最低いいね | Execute Command | `--min-likes` |
| note フィード | RSS Read (note-*) | URL |
| Brain キーワード | HTTP Request (Brain) | URL の `keyword=` |
| Tips キーワード | HTTP Request (Tips) | URL の `q=` |
| Qiita タグ・期間 | HTTP Request (Qiita) | URL の `query=` |
| 取得件数上限 | Code (Combine Sources) | `slice` / `count` |
| 分析の方向性 | Basic LLM Chain | System メッセージ |
| 出力 JSON 形式 | Structured Output Parser | JSON Schema |
| AI モデル | Google Gemini Chat Model | Model / Temperature |
| 通知文面 | Code (Format Notification) | JavaScript |
| モック/本番 X | `.env` | `USE_MOCK_X` |

---

## 関連ドキュメント

- [運用マニュアル](./operations.md) — 日常運用・Cookie 更新
- [設定リファレンス](./configuration.md) — 環境変数一覧
- [アーキテクチャ](./architecture.md) — システム構成図
- [仕様書](../specs/AIトレンド抽出システム構築仕様書.md) — 設計上の詳細定義
