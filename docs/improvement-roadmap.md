# 改善方針ロードマップ

3層アーキテクチャ（[動的ウォッチリスト戦略](./watchlist-strategy.md)）の **初回運用結果** を踏まえ、品質・運用・拡張の改善方針を整理します。

## 現状評価（2026-06-10）

| 領域 | 状態 | 所見 |
|------|------|------|
| パイプライン | ✅ 動作 | 収集 → Combine → LLM → 通知まで成功 |
| 日次 WF | ✅ 動作 | 固定 `TOOL_PATTERNS` 廃止済み。本命=生データ + LLM |
| 週次 WF | ✅ 動作 | `config/watchlist.json` が更新される |
| watchlist 品質 | ⚠️ 要改善 | `Flash` / `mini` / `Haiku` 等のモデル名・一般語が active に混入 |
| 日次 candidates | ⚠️ 要観察 | watchlist 参考枠は LLM ルールで本命根拠を優先する設計だが、プロンプト強化余地あり |
| インフラ | ⚠️ 軽微 | WF インポート後の active 化、Discord Webhook の env 化が未完了 |

**結論:** アーキテクチャは正しく機能している。**次の焦点は watchlist 機械抽出の精度と LLM ガードレールの強化**。

---

## 改善の原則

1. **固定監視リストに戻らない** — `TOOL_PATTERNS` 型の事前バイアスは再導入しない
2. **本命と参考を分離し続ける** — 候補選定の主根拠は note / Brain / Tips / Qiita の生データのみ
3. **週次でノイズ除去、日次で判断** — 精度改善は主に Layer 2（週次）と LLM プロンプトで行う
4. **変更は `build-watchlist-workflows.py` 経由** — ワークフロー JSON の手編集を最小化

---

## Phase 1: watchlist 品質（優先・短期）

初回実行で判明した **機械抽出ノイズ** を減らす。

### 1-1. ブラックリスト拡張

`Code (Mechanical Extract)` の `GENERIC` Set に以下カテゴリを追加する。

| カテゴリ | 例 | 理由 |
|---------|-----|------|
| モデル世代名 | `Flash`, `Haiku`, `Sonnet`, `Opus`, `mini`, `Pro` | ツール名ではなくモデル修飾 |
| 一般英単語 | `Agent`, `context`, `quot`, `note1` | タイトル内の汎用語 |
| EC・汎用サービス | `Etsy`, `SUZURI` | AI ツールではない（文脈依存） |
| 小文字のみ | `mini`, `context` | 固有名詞ツールの可能性が低い |

**実装箇所:** `scripts/build-watchlist-workflows.py` → `MECHANICAL_EXTRACT_JS` の `GENERIC`

### 1-2. 抽出ルールの厳格化

| 変更 | 内容 | 期待効果 |
|------|------|----------|
| 英字トークン最小長 | 3文字 → **4文字**（`AI` 等は既に除外） | 短いノイズ削減 |
| 先頭小文字除外 | `[a-z]` 始まりの英字トークンは捨てる | `mini`, `context` 除外 |
| CamelCase 優先 | スコア加算を CamelCase / `.ai` ドメインに **重み付け** | 真のツール名を上位に |
| 2ソース必須（active 候補） | 機械抽出段階で `sources.length >= 2` のみ `mechanicalTop` 上位に | note 単独ノイズ削減 |

### 1-3. 週次 LLM プロンプト強化

`WEEKLY_LLM` に明示ルールを追加する。

- **ツール・サービス名のみ**（モデル名・抽象語・一般名詞は不可）
- `active` 採用条件: **2ソース以上** または **前週 active かつ今週も再出現**
- 迷ったら `emerging`（現行方針の明文化）
- 出力前に自己チェック: 「これはダウンロード/登録できるプロダクト名か？」

**実装箇所:** `scripts/build-watchlist-workflows.py` → `WEEKLY_LLM`

### 1-4. Format Watchlist の後処理

`Code (Format Watchlist)` で LLM 出力を機械フィルタする。

```javascript
// 例: active/emerging から GENERIC 再チェック、1文字差の重複統合
```

LLM の誤採用を二重ガードする。**Phase 1 の最終防衛線**。

### 成功指標（Phase 1）

| 指標 | 目標 |
|------|------|
| `active` のノイズ率 | 週次実行後、明らかな非ツール語が **2件以下** |
| `mechanicalTop` と `active` の一致度 | 上位5件中3件以上が実在ツール名 |
| 手動修正頻度 | `watchlist.json` 手編集が **月1回未満** |

---

## Phase 2: 日次朝刊品質（中期）

watchlist は参考枠のため日次 candidates への直接影響は限定的だが、**全体分析と通知品質**を上げる。

### 2-1. 日次 LLM プロンプト

| 項目 | 改善内容 |
|------|----------|
| watchlist 参照 | 「参考セクションにあっても本命データに無い語は candidates 不可」を再強調 |
| 定番上限 | Claude Code / Cursor / ChatGPT 合計 **最大1件**（現行維持・監視） |
| 根拠の明示 | `overall_analysis` に「どのソースで何を見たか」を1フレーズ含める |

**実装箇所:** `scripts/build-watchlist-workflows.py` → `DAILY_LLM`

### 2-2. Format Notification

| 項目 | 改善内容 |
|------|----------|
| candidates 表示 | 本命データに根拠が薄い候補を注釈付きで除外（任意） |
| 文字数 | `overall_analysis` の800字超を Code で自動トリム |
| Discord 分割 | 2000字超の分割ロジックは現行維持 |

**実装箇所:** `workflows/ai-trend-extractor.json` の `Code (Format Notification)`（別途パッチスクリプト化を検討）

### 2-3. Qiita 取得の見直し

週次・日次とも Query に OR タグ列挙がある。固定タグ列挙は **軽いバイアス** のため:

| 案 | 内容 |
|----|------|
| A（推奨） | `tag:AI` + `created:>` のみに簡素化。ツール名は LLM がタイトルから判断 |
| B | 週次で LLM が抽出した `active` を翌週の Qiita query に **参考** として渡す（本命ではない） |

---

## Phase 3: 運用・信頼性（中期）

### 3-1. watchlist 履歴

```
config/history/watchlist-YYYY-MM-DD.json
```

週次 `Write Watchlist` の前にコピー保存。差分レビューとロールバックに使う。

### 3-2. 手動オーバーライド

```
config/watchlist.override.json
```

| フィールド | 用途 |
|-----------|------|
| `forceActive` | 週次 LLM が漏らしたツールを常時 active に |
| `forceRetire` | ノイズを強制 retire |
| `blocklist` | 機械抽出・LLM 両方で除外 |

週次 `Format Watchlist` で `override` をマージする。

### 3-3. インフラ

| 項目 | 内容 |
|------|------|
| Discord Webhook | ノード直書き → `$env.DISCORD_WEBHOOK_URL` |
| WF インポート後 | active 化チェックリストを [operations.md](./operations.md) に記載済み |
| 実行監視 | n8n Executions + Discord 朝刊到達の二重確認 |

---

## Phase 4: 拡張（長期・提案 D / C）

[watchlist-strategy.md](./watchlist-strategy.md) の未採用案を段階導入する。

| 優先 | 拡張 | 効果 |
|------|------|------|
| 1 | **Zenn RSS / タグ急増** | 国内実装シグナル強化 |
| 2 | **Product Hunt AI** | グローバル新規ツールの early signal |
| 3 | **Deep-dive WF** | `active` 候補のみ x-trends search / Qiita 深掘り |
| 4 | **GitHub Trending / HN** | OSS・技術バズ（英語圏） |

外部ソース追加時も **Layer 1 = 生データ、Layer 3 = LLM 判断** の分離を維持する。

---

## やらないこと

| 施策 | 理由 |
|------|------|
| 日次 WF に `TOOL_PATTERNS` 復活 | 構造的バイアスに回帰 |
| watchlist を candidates の直接根拠にする | 設計思想（本命=生データ）に反する |
| x-trends `/search` で複合 OR 監視 | x-trends の想定用途外。参考は `/trends` のみ |
| 機械抽出を日次 Combine に入れる | 日次は整形のみ。抽出は週次 + LLM |

---

## 実装・反映手順

```bash
# 1. build-watchlist-workflows.py を編集
# 2. WF 再生成
python3 scripts/build-watchlist-workflows.py

# 3. n8n インポート
docker compose exec -T n8n n8n import:workflow --input=/dev/stdin < workflows/ai-trend-extractor.json
docker compose exec -T n8n n8n import:workflow --input=/dev/stdin < workflows/watchlist-generator.json

# 4. GUI で両 WF を active 化
# 5. 週次 WF を手動 Execute → watchlist.json を目視確認
```

---

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [watchlist-strategy.md](./watchlist-strategy.md) | 採用アーキテクチャ・提案 A〜D |
| [workflow-nodes.md](./workflow-nodes.md) | ノード設定リファレンス |
| [operations.md](./operations.md) | 日常運用・初回セットアップ |

---

## 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-06-10 | 初版。初回運用所見（watchlist ノイズ）を Phase 1 として具体化 |
