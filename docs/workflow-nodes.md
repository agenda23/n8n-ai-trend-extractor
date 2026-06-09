# ワークフロー ノード設定リファレンス（現行版）

`AIトレンド抽出・リード獲得` ワークフロー（`workflows/ai-trend-extractor.json`）の、**2026-06-09 時点の稼働中設定**をノード単位で解説します。

| 項目 | 値 |
|------|-----|
| n8n ワークフロー ID | `axXa37Sq1YQQbIYj` |
| 最終更新（n8n） | `2026-06-09T00:18:18Z` |
| 状態 | active |
| 一括更新スクリプト | `scripts/update-workflow-precision.py` |

---

## 設計方針

| 層 | 役割 |
|----|------|
| **収集ノード** | X / note / Brain / Tips / Qiita を並列取得 |
| **Code (Combine Sources)** | **データ整形のみ**。中立シグナルを LLM 向けテキストに統合 |
| **LLM (Gemini)** | **候補選定 + 全体分析**。ルーブリックに従い判断 |
| **Code (Format Notification)** | Discord 向け整形。抽象語除外・定番最大1件・2000字分割 |
| **Discord** | Webhook POST（複数パート対応） |

**要点:** Code は keyword を選ばない。何を候補にするかは LLM の仕事。

---

## 全体像

```
Schedule Trigger（毎朝 07:00 JST）
  │
  ├─ IF Mock X ─┬─ true  → Read Mock X → Normalize Mock X ──┐
  │             └─ false → Execute Command (twitter-cli) ────┤
  ├─ RSS Read (note-AI副業) ─────────────────────────────────┤
  ├─ RSS Read (note-AIツール) ───────────────────────────────┤
  ├─ HTTP Request (Brain) ─────────────────────────────────────┤
  ├─ HTTP Request (Tips) ──────────────────────────────────────┤
  └─ HTTP Request (Qiita) ─────────────────────────────────────┤
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
                                            Discord（Webhook POST）
```

**3段階の処理:**

1. **収集** — 5ソースを並列取得（X は本番 or モック）
2. **分析** — Gemini が `candidates[]`（最大10件・根拠弱ければ2〜3件）と `overall_analysis` を JSON 化
3. **配信** — Discord 朝刊テキストに整形（2000文字超は `[1/N]` 付きで自動分割）

---

## 前提・関連設定

| 項目 | 値・場所 |
|------|----------|
| タイムゾーン | `.env` の `GENERIC_TIMEZONE=Asia/Tokyo` |
| X モック切替 | `.env` の `USE_MOCK_X`（`true` / `false`） |
| X 認証 | `.env` の `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` |
| Qiita 認証 | `.env` の `QIITA_ACCESS_TOKEN`（任意） |
| Gemini | n8n Credentials `Google Gemini(PaLM) Api account` |
| モックファイル | ホスト `mock/x-tweets-sample.json` → コンテナ `/home/node/.n8n-files/mock/` |

`.env` 変更後は `docker compose restart n8n` が必要です。

**n8n 2.x 構文:** 他ノード参照は **`$('ノード名').all()`** を使用（`$node["名前"].all()` は動作しない）。

---

## Phase 1: トリガー・X データ

### 1. Schedule Trigger

| 項目 | 設定値 |
|------|--------|
| 種類 | Schedule Trigger |
| Cron | `0 7 * * *`（毎日 07:00） |
| 出力 | 1アイテム（空のトリガー信号） |

**役割:** 毎朝 07:00 JST に 6 本の収集ブランチを同時起動します。

**接続先:** IF Mock X、RSS ×2、HTTP Request ×3（Brain / Tips / Qiita）

---

### 2. IF Mock X

| 項目 | 設定値 |
|------|--------|
| 種類 | IF |
| 条件 | `{{ $env.USE_MOCK_X }}` が文字列 `true` と完全一致 |

| 分岐 | 接続先 |
|------|--------|
| **true** | Read Mock X |
| **false** | Execute Command |

**役割:** 本番（twitter-cli）とモック（ローカル JSON）を切り替えます。開発・検証時は `USE_MOCK_X=true` を推奨します。

---

### 3. Read Mock X

| 項目 | 設定値 |
|------|--------|
| 種類 | Read/Write Files from Disk |
| ファイルパス | `/home/node/.n8n-files/mock/x-tweets-sample.json` |

**役割:** モック用 X ツイート JSON を読み込みます。n8n 2.x のファイル制限により `.n8n-files` 配下のみ有効です。

**docker-compose マウント:**

```yaml
./mock:/home/node/.n8n-files/mock:ro
```

---

### 4. Normalize Mock X

| 項目 | 設定値 |
|------|--------|
| 種類 | Code |
| 出力 | `{ stdout: "<JSON文字列>" }` |

**役割:** Read Mock X の出力を Execute Command と同じ `stdout` 形式に正規化します。Combine Sources が本番・モックを同一ロジックで処理できます。

---

### 5. Execute Command

| 項目 | 設定値 |
|------|--------|
| 種類 | Execute Command |
| Continue On Fail | **有効**（X 失敗時もワークフロー継続） |

**コマンド（先頭 `=` で n8n 式評価）:**

```
=twitter search 'Dify OR n8n OR Manus OR OpenClaw OR Windsurf OR Bolt OR Lovable OR ComfyUI OR "v0.dev" OR "Gemini CLI" OR Make.com OR Zapier OR Devin OR Magnific OR 知らないと損 OR 神ワザ OR 爆速 OR 新ツール OR 初公開' --since {{ $today.minus({ days: 3 }).toISODate() }} --until {{ $today.plus({ days: 1 }).toISODate() }} --min-likes 5 --json
```

| パラメータ | 意味 |
|------------|------|
| 検索語 | ニッチ・新興ツール名 + バズ系日本語キーワードを OR 結合 |
| `--since` / `--until` | 直近 3 日間（実行日基準） |
| `--min-likes 5` | いいね 5 未満の投稿を除外 |
| `--json` | twitter-cli の JSON 出力 |

**設計意図:** Claude Code / Cursor / MCP は検索語から除外し、ニッチ・新興ツールの投稿収集を優先します（定番ツールの言及は生投稿・note 等から LLM が判断）。

**出力:** `stdout` に twitter-cli の JSON（`{ ok, data: [...] }` 形式）

**注意:** コマンド先頭の `=` がないと日付式が展開されずシェルエラーになります。

**カスタマイズ例:**

- 監視ツール追加: OR 句にツール名を追加（Combine Sources の `TOOL_PATTERNS` も合わせて更新）
- 閾値緩和: `--min-likes 3`
- 期間変更: `days: 3` → `days: 5`

---

## Phase 2: その他ソース収集

### 6. RSS Read (note-AI副業)

| 項目 | 設定値 |
|------|--------|
| URL | `https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss` |
| Continue On Fail | 有効 |

**役割:** note「AI副業」タグの新着 RSS を取得します。

---

### 7. RSS Read (note-AIツール)

| 項目 | 設定値 |
|------|--------|
| URL | `https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss` |
| Continue On Fail | 有効 |

**役割:** note「AIツール」タグの新着 RSS を取得します。Merge 入力には未接続で、Combine Sources が `$('RSS Read (note-AIツール)').all()` で直接参照します。

---

### 8. HTTP Request (Brain)

| 項目 | 設定値 |
|------|--------|
| URL | `https://brain-market.com/search?keyword=AI` |
| Response Format | Text（HTML） |
| Continue On Fail | 有効 |

**役割:** Brain の AI 検索結果 HTML を取得します。Combine Sources 内でリンクをパースし教材タイトルを抽出します。

---

### 9. HTTP Request (Tips)

| 項目 | 設定値 |
|------|--------|
| URL | `https://tips.jp/search?q=AI` |
| Response Format | Text（HTML） |
| Continue On Fail | 有効 |

**役割:** Tips の AI 検索結果 HTML を取得します。同様に HTML パースで教材タイトルを抽出します。

---

### 10. HTTP Request (Qiita)

| 項目 | 設定値 |
|------|--------|
| URL（式） | `=https://qiita.com/api/v2/items?query=tag:n8n+OR+tag:Dify+OR+tag:Manus+OR+tag:Windsurf+OR+tag:OpenClaw+OR+tag:ComfyUI+created:>{{ $today.minus({ days: 3 }).toISODate() }}&per_page=15` |
| Header | `Authorization: Bearer {{ $env.QIITA_ACCESS_TOKEN }}` |
| Continue On Fail | 有効 |

**役割:** 直近 3 日のツール関連タグ記事を Qiita API から取得します。トークン未設定でもワークフローは継続します（空または 401）。

---

## Phase 3: 統合・分析・通知

### 11. Merge All Sources

| 項目 | 設定値 |
|------|--------|
| Mode | Combine |
| Combine By | **Combine All** |
| 入力数 | 6 |

**入力マッピング:**

| Input | 接続元 |
|-------|--------|
| 0 | Normalize Mock X **または** Execute Command |
| 1 | RSS Read (note-AI副業) |
| 2 | （未使用 — note-AIツール は Code 側で `$()` 参照） |
| 3〜5 | Brain / Tips / Qiita |

**役割:** 並列ブランチの完了を待ち、Code (Combine Sources) を 1 回実行します。

---

### 12. Code (Combine Sources)

| 項目 | 設定値 |
|------|--------|
| 種類 | Code |
| 出力 | `{ textData, buzzCandidates }` |

**役割:** 5 ソースの生データを Gemini 向けプレーンテキスト（`textData`）に統合します。**候補選定は行いません。**

#### TOOL_PATTERNS（監視ツール 16 種）

MCP は含めません（抽象プロトコル名のため）。

| ツール名 | 検出パターン概要 |
|----------|------------------|
| Dify, n8n, Manus, OpenClaw | 単語境界マッチ |
| Windsurf, Lovable, ComfyUI, Devin, Magnific | 同上 |
| Bolt | `bolt.new` |
| v0 | `v0.dev` / `v0 dev` |
| Gemini CLI | `gemini cli` |
| Make | `make.com` |
| Zapier | `zapier` |
| Claude Code, Cursor | 定番ツール（検出のみ、選定は LLM） |

#### 主要ロジック

1. **X ツール言及シグナル** — `rankScore = 最高Eng + 言及×12` でソート（倍率・フィルタなし）
2. **X 生投稿** — エンゲージ上位 30 件
3. **note / Qiita** — タイトルからツール名カウント
4. **Brain / Tips** — HTML から教材タイトル・URL 抽出
5. **マルチソース言及カウント** — X / note / Qiita を横断し、裏付けソース数を付与（ルーブリック1用）
6. **代替候補** — X が空のとき note/Qiita から補完

#### textData セクション構成

```
=== 【超短期トレンド分析用マルチソースデータ】 ===
※ Codeは中立データのみ提供。候補選定はLLMがルーブリックで実施。
※ 監視ツール（TOOL_PATTERNS）: Dify, n8n, Manus, ...
※ 上記以外の初出固有名詞は「X生投稿」から積極探索すること。

■ [Xツール言及シグナル（参考データ）]
■ [X (Twitter) 生投稿（上位30件）]
■ [noteで検出された具体ツール名]
■ [note新着記事（タイトルのみ）]
■ [Brain 教材タイトル]
■ [Tips 教材タイトル]
■ [Qiitaで検出された具体ツール名]
■ [Qiita 技術記事]
■ [マルチソース言及カウント（選定参考）]   ← X 空でなければ出力
■ [代替バズ候補（X未取得時）]               ← X 空のときのみ
```

**マルチソース言及カウントの例:**

```
- Dify: X6 / note2 / Qiita1 | 裏付けソース:3 (X+note+Qiita)
- OpenClaw: X3 / note1 / Qiita0 | 裏付けソース:2 (X+note)
```

---

### 13. Basic LLM Chain

| 項目 | 設定値 |
|------|--------|
| 種類 | Basic LLM Chain |
| System Message | 選定ルーブリック + 出力形式（下記） |
| User Message | `={{ $json.textData }}` |
| Output Parser | Structured Output Parser に接続 |

#### 選定ルーブリック（candidates の判断基準）

| # | 基準 |
|---|------|
| 1 | **複数ソース（X + note/Qiita）で裏付けがあるものを最優先**（マルチソース言及カウントの裏付けソース数参照） |
| 2 | **定番（Claude Code, Cursor, ChatGPT）は最大1件**。それ以外はニッチ・新興を優先 |
| 3 | **抽象語は候補不可**: MCP, 生成AI, AI副業, ChatGPT, ノーコード, 効率化, AI画像生成 など |
| 4 | **TOOL_PATTERNS 外の初出固有名詞**は X 生投稿から積極採用 |
| 5 | **根拠が弱いものは省略可**（2〜3件でも可。無理に10件埋めない） |

#### 出力形式

| フィールド | 内容 |
|------------|------|
| `candidates` | 固有名詞ツール名の配列（優先度順、最大10件、個別説明なし） |
| `overall_analysis` | 全体所見 1 文（最大800文字） |

**overall_analysis に含める観点（全体で統合）:**

- X バズの傾向
- note / Brain / Tips の実売シグナル
- Qiita 等の実装トレンド・詰まりポイント
- リード獲得の打ち手（1〜2個）

---

### 14. Google Gemini Chat Model

| 項目 | 設定値 |
|------|--------|
| Model | `models/gemini-2.5-flash-lite` |
| Temperature | `0.2` |
| Credentials | `Google Gemini(PaLM) Api account` |

**役割:** LLM Chain の推論エンジン。低 Temperature で出力のブレを抑制します。

---

### 15. Structured Output Parser

| 項目 | 設定値 |
|------|--------|
| 種類 | Structured Output Parser |
| Schema | `candidates`（string[]）+ `overall_analysis`（string） |

**JSON スキーマ例（稼働中）:**

```json
{
  "candidates": [
    "OpenClaw",
    "Manus",
    "Dify",
    "ComfyUI",
    "n8n",
    "Lovable"
  ],
  "overall_analysis": "直近3日はOpenClaw/Manus/DifyがX+note+Qiitaの3ソースで裏付けあり。OpenClawはX高Eng、Manus/Difyはnote有料記事が複数。Qiitaはn8n×DifyのRAG連携質問が増加。定番のClaude Code言及は多いがルーブリック上は候補から外し差別化を図る。リード獲得は「OpenClaw初日セットアップ」か「Dify×Slack業務Bot」が有望。"
}
```

---

### 16. Code (Format Notification)

| 項目 | 設定値 |
|------|--------|
| 種類 | Code |
| 出力 | 複数アイテム `{ text, part, totalParts, candidates, overall_analysis }` |

**役割:**

1. LLM 出力を Discord 朝刊フォーマットに整形
2. **安全網フィルタ** — 抽象語（AI, ChatGPT, MCP, AI副業 等）を候補から除外
3. **定番ツール**（Claude Code / Cursor / ChatGPT）が2件以上なら **1件に制限**
4. 候補は最大10件、重複除去
5. **2000 文字超を自動分割** — `splitForDiscord()` で行単位分割、複数パート時は `[1/N]` ヘッダー付与
6. 複数アイテムを返し、Discord ノードがパートごとに POST

#### Discord 文字数予算（目安）

| 要素 | 目安 |
|------|------|
| ヘッダー + 候補リスト（10件） | 〜300字 |
| overall_analysis（LLM 上限） | 〜800字 |
| 合計 | 〜1100字（通常は1パートに収まる） |

超過時は全体分析の長文を境に `[2/2]` 等で分割されます。

**出力フォーマット例:**

```
📢 【朝刊】AIツール・バズシグナル速報 📢

直近3日間のマルチソース分析

【注目候補（6件）】
1. OpenClaw
2. Manus
3. Dify
4. ComfyUI
5. n8n
6. Lovable

【全体分析】
直近3日はOpenClaw/Manus/DifyがX+note+Qiitaの3ソースで裏付けあり...
```

---

### 17. Discord

| 項目 | 設定値 |
|------|--------|
| 種類 | HTTP Request |
| Method | POST |
| Body | `content={{ $json.text }}` |

**役割:** Discord Webhook へ朝刊テキストを送信します。Format Notification が複数パートを返した場合、パート数だけ POST が実行されます。

**セキュリティ推奨:** Webhook URL は現状ノード直書きです。`{{ $env.DISCORD_WEBHOOK_URL }}` または n8n Credentials への移行を推奨します。

---

## データフロー（JSON）

```
Execute Command / Normalize Mock X
  → { stdout: "..." }
       ↓
Code (Combine Sources)
  → { textData: "...", buzzCandidates: ["OpenClaw", "Dify", ...] }
       ↓
Basic LLM Chain (Gemini)
  → { output: { candidates: [...], overall_analysis: "..." } }
       ↓
Code (Format Notification)
  → { text: "...", part: 1, totalParts: 1, candidates: [...], overall_analysis: "..." }
       ↓
Discord
  → HTTP 204/200
```

---

## ワークフロー更新手順

ノード設定を一括反映する場合:

```bash
# n8n API へ PUT（Combine / LLM / Format / Execute Command / Qiita 等）
python3 scripts/update-workflow-precision.py

# リポジトリ JSON を同期
docker compose exec -T n8n n8n export:workflow --id=axXa37Sq1YQQbIYj --pretty > workflows/ai-trend-extractor.json
```

---

## よくあるカスタマイズ

| 目的 | 変更箇所 | 内容 |
|------|----------|------|
| 監視ツール追加 | Execute Command + `TOOL_PATTERNS` | 検索 OR 句と正規表現を追加 |
| 選定基準変更 | Basic LLM Chain プロンプト | ルーブリックを編集（`update-workflow-precision.py` 推奨） |
| 候補件数・分析長 | LLM プロンプト + Format Notification | `最大10件` / `overall_analysis 800字` を調整 |
| バズ閾値 | Execute Command | `--min-likes` の値 |
| 分析期間 | Execute Command, Qiita URL | `days: 3` の数値 |
| 通知先 | Discord ノード | Webhook URL |
| ローカルテスト | `.env` | `USE_MOCK_X=true` |

---

## 関連ファイル

| ファイル | 内容 |
|----------|------|
| `workflows/ai-trend-extractor.json` | ワークフロー定義（バージョン管理用） |
| `scripts/update-workflow-precision.py` | ノード一括更新スクリプト（正の設定ソース） |
| `mock/x-tweets-sample.json` | X モックデータ |
| [operations.md](./operations.md) | 日常運用 |
| [troubleshooting.md](./troubleshooting.md) | 障害対応 |
| [workflow-guide.md](./workflow-guide.md) | 旧カスタマイズガイド（一部内容は本ドキュメントに統合済み） |

---

## チューニング履歴

| 時期 | 変更内容 |
|------|----------|
| 2026-06-09 午前 | ビッグワード対策: X 検索から Claude Code / Cursor / MCP 除外、ニッチツール中心に |
| 2026-06-09 午後 | 出力形式を `candidates[]` + `overall_analysis` に変更（候補ごと分析を廃止） |
| 2026-06-09 夕方 | 選定ルーブリックを LLM に委譲。Combine Sources はデータ整形のみ。マルチソース言及カウント追加 |

**今後の改善候補:** 前週比言及増加率、全体分析の文字数自動トリム、Discord Webhook の環境変数化
