# 動的ウォッチリスト戦略

固定 `TOOL_PATTERNS`（16ツール）による監視は、トレンドが移り変わっても古いレール上を走り続ける **構造的バイアス** を生みます。本ドキュメントは代替案と、採用した **3層アーキテクチャ** を記録します。

## 背景と課題

| 課題 | 説明 |
|------|------|
| 固定リストの陳腐化 | Dify / n8n 等がトレンドから外れても監視対象が変わらない |
| 新興ツールの取りこぼし | リスト外の固有名詞は構造化サマリーに出にくい |
| 設計思想との矛盾 | 「ツール=生データ、ワークフロー=抽出」なのに Combine で事前集計していた |

## 3層アーキテクチャ（採用）

```
[Layer 1] 生データ収集     note / Brain / Tips / Qiita / x-trends（参考）
[Layer 2] 動的ウォッチリスト  週次 WF が watchlist.json を更新
[Layer 3] 日次トレンド分析   生データ + LLM。watchlist は参考枠のみ
```

### スケジュール

| ワークフロー | cron | 役割 |
|-------------|------|------|
| **Watchlist Generator** | `0 6 * * 1`（月 06:00 JST） | 週次 watchlist 更新 |
| **AIトレンド抽出・リード獲得** | `0 7 * * *`（毎日 07:00 JST） | 朝刊配信 |

月曜 06:00 に watchlist を更新し、07:00 の朝刊で最新リストを参考表示します。

---

## 提案一覧

### 提案 A: 週次「ウォッチリスト生成」ワークフロー（**採用**）

別 n8n WF を週1回実行し、`config/watchlist.json` を更新します。

| 項目 | 内容 |
|------|------|
| 入力 | 7日分 note/Qiita/Brain/Tips 生タイトル、x-trends 参考トレンド |
| 処理 | 機械抽出（提案 B）→ LLM で active / emerging / retire に整理 |
| 出力 | `config/watchlist.json` |
| 日次 WF | ファイルを **参考セクション** として読み込みのみ |

**ルール（LLM + Code で適用）**

- 2ソース以上・7日以内に複数回出現 → `active`
- 1ソースのみ・新規 → `emerging`
- 前週 active だったが今週データに未出現 → `retire` 候補

### 提案 B: ルールベース固有名詞抽出（**採用・週次 WF 内**）

LLM 前処理として、タイトル・タグから候補語を機械抽出します。

- `.dev` / `.ai` / `.io` ドメイン
- CamelCase 固有名詞
- 3〜20文字の英字トークン
- **除外**: 抽象語ブラックリスト（生成AI, ChatGPT, MCP 等）のみ固定

週次 WF の `Code (Mechanical Extract)` が担当。日次 WF では **行わない**（バイアス回避）。

### 提案 C: 二段パイプライン（発見と深掘り分離）

| 頻度 | 役割 |
|------|------|
| 毎朝 | 生データ → LLM → 朝刊（現行） |
| 週1 | Discovery → watchlist 更新（採用） |
| 任意 | focus 候補のみ深掘り（将来拡張） |

Deep-dive WF は未実装。watchlist の `active` を入力にした検索 WF を後から追加可能。

### 提案 D: 外部シグナル（discovery 専用）

| ソース | 用途 |
|--------|------|
| Product Hunt AI | グローバル新規 |
| Hacker News Algolia | 技術バズ |
| GitHub Trending | OSS |
| Zenn/Qiita タグ急増 | 国内実装 |

**現状**: 未接続。週次 WF への入力追加として将来拡張可能。

---

## 採用構成（おすすめの組み合わせ）

1. **日次 WF**: `TOOL_PATTERNS` 削除。本命は生データ + LLM のみ
2. **週次 WF**: 提案 A + B ハイブリッド → `watchlist.json` 更新
3. **日次 WF**: `watchlist.json` を「今週の注目（参考）」セクション表示のみ
4. **x-trends**: 引き続き参考枠（日本 Explore 全体・カテゴリ非限定）

---

## watchlist.json スキーマ

パス: `config/watchlist.json`（コンテナ内: `/home/node/.n8n-files/config/watchlist.json`）

```json
{
  "updatedAt": "2026-06-10T06:00:00.000Z",
  "version": 1,
  "active": ["OpenClaw", "Dify", "n8n"],
  "emerging": ["SomeNewTool"],
  "retire": ["Devin"],
  "rationale": "週次LLMによる整理要約（1文）",
  "mechanicalTop": [
    { "name": "OpenClaw", "score": 5, "sources": ["note", "qiita"] }
  ]
}
```

| フィールド | 説明 |
|-----------|------|
| `active` | 今週の主監視候補（参考） |
| `emerging` | 新規・要ウォッチ（参考） |
| `retire` | 今週データに未出現のため降格 |
| `mechanicalTop` | 機械抽出上位（監査用） |

---

## データの読み方（LLM 向け）

| ブロック | 候補選定 | 用途 |
|---------|---------|------|
| 本命データ（note/Brain/Tips/Qiita 生テキスト） | **主根拠** | candidates |
| 週次ウォッチリスト（参考） | 参考のみ | 既知ツールの文脈補足 |
| x-trends 全体トレンド（参考） | 参考のみ | overall_analysis の宏观 |

---

## ファイル・ワークフロー

| パス | 説明 |
|------|------|
| `workflows/ai-trend-extractor.json` | 日次朝刊 WF |
| `workflows/watchlist-generator.json` | 週次 watchlist 更新 WF（ID: `wL7kG3mN9pQr2sTv`） |
| `config/watchlist.json` | 動的ウォッチリスト（週次更新） |
| `scripts/build-watchlist-workflows.py` | WF ビルドスクリプト |

---

## 運用

```bash
# 初回: config ディレクトリ確認
mkdir -p config

# WF 再ビルド（Combine / 週次 WF 更新後）
python3 scripts/build-watchlist-workflows.py

# n8n へインポート
docker compose exec -T n8n n8n import:workflow --input=/dev/stdin < workflows/ai-trend-extractor.json
docker compose exec -T n8n n8n import:workflow --input=/dev/stdin < workflows/watchlist-generator.json

# 週次 WF を手動実行（初回 watchlist 生成）
# n8n GUI → Watchlist Generator → Execute
```

---

## 将来拡張

詳細な優先順位・Phase 分けは [改善方針ロードマップ](./improvement-roadmap.md) を参照。

- 提案 D の外部ソースを週次 WF に追加
- `history/` に週次 watchlist スナップショット保存
- Deep-dive WF（active 候補のみ x-trends search / Qiita 深掘り）
- 手動オーバーライド: `config/watchlist.override.json` のマージ
