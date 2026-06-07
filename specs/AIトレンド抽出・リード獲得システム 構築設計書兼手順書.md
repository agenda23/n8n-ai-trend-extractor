## 〜マルチソース（X/note/Brain/Tips/Qiita）連携 ＆ n8n MCPによる自律型ワークフロー構築検討〜

本書は、Xをはじめとする複数メディアから、能動的なAI副業ユーザーが熱狂する「実利・爆速・効率化」の超短期スパイク（3〜5日の急上昇トレンド）を検知し、自社の見込み顧客（リード）を獲得するためのシステム構築設計書である。さらに、最新のプロトコルであるMCP（Model Context Protocol）を用いて、AIエージェント（Cursor, Cline, Claude Desktop等）からn8nワークフローを自律的に構築・操作・改修させるための技術的アプローチについての検討と導入手順を網羅している。

## 1. 導入背景と「顧客獲得リサーチ」の要件

### 1.1 ターゲットユーザーの行動心理

SNS（特にX）において、能動的に行動を起こしている「AI副業・効率化クラスター」は、以下のような特定の「実利シグナル」に極めて敏感に反応する。

- **反応トリガー**: 「儲かる」「効率化」「爆速」「爆益」「ClaudeCode新機能」「誰も知らなかった効率的ワークフロー」など、即座に利益や時間短縮に結びつく直接的なパワーワード。
    
- **行動特性**: 有益な自動化ワークフローが公開されると、「リポスト（拡散）」「ブックマーク」「公式LINE登録」といったエンゲージメント（能動的なアクション）を即時かつ活発に行う。
    

### 1.2 本システムのゴール

このターゲット層が今まさに直面している「課題（Pain Point）」や「今朝バズっているツール」を3〜5日のスパンで確実に検知し、それらをハックする「無料プレゼント（リードマグネット）の配布企画」を自動抽出し、最短最速で顧客獲得を達成する。

## 2. 全体システムアーキテクチャ

本システムは、セルフホスト（ローカル）のn8nをハブとし、複数のソース（X/note/Brain/Tips/Qiita）から情報をパラレルで収集・結合、Gemini APIを用いて顧客獲得視点でクロス分析を行う。

```
                       ┌─ ① X (twitter-cli) ──＞ 「爆速/爆益/ClaudeCode」等のバズ
                       ├─ ② note (RSS) ────────＞ 実売トレンド・ビジネス事例
[Schedule Trigger] ────┼─ ③ Brain (HTTP API) ──＞ 有料コンテンツ売れ行き
 (毎日朝7:00起動)       ├─ ④ Tips (HTTP API) ───＞ 副業ノウハウ
                       └─ ⑤ Qiita (REST API) ──＞ 開発実装上のエラー・壁
                               │
                               ▼
                    [Codeノード (JavaScript)] ───＞ テキスト整形・自動クレンジング
                               │
                               ▼
               [Basic LLM Chain (Gemini API)] ───＞ 顧客獲得（リード）戦略・配布企画の自動構築
                               │
                               ▼
                     [Google Sheets / Notion] ───＞ トレンドデータベースへ蓄積
                               │
                               ▼
                  [Slack / Discord / LINE] ────＞ マーケティング速報・企画書の自動配信
```

## 3. n8n MCP（Model Context Protocol）による自律構築の検討

### 3.1 n8n MCPの概念と導入メリット

**Model Context Protocol (MCP)** は、AIモデルがローカル開発環境や外部API（n8n）とセキュアに接続するためのオープン標準プロトコルである。 n8nにMCPを適用することで、ユーザー自身がGUIでノードを接続しなくても、**「Cursor」「Cline」「Claude Desktop」などのAIエージェントに自然言語で指示を出すだけで、n8nワークフローを裏側で直接構築・改修・テストさせることが可能**になる。

#### 💡 解決する課題

1. **仕様変更への追従コスト削減**: XやQiita、Brain等のAPI仕様や取得構造が3〜5日で変わった際、AIに「n8nのワークフローを修正して」と指示するだけで自動修正が完了する。
    
2. **ワークフロー自動生成の高度化**: LLM分析の結果、「新しい収集チャネルが必要」と判断した場合、AIエージェント自身が新しいノードをn8nに追加構築する自律サイクル（自律自己進化型エージェント）が可能になる。
    

### 3.2 構成パターン（MCPクライアント vs MCPサーバー）

#### パターンA：AIエージェントをクライアントとして、n8nを操作する場合（推奨）

AIエージェント（Cline / Cursor等）をホストとし、ローカルn8nのMCPサーバー（またはAPI）に接続。AIエージェントがn8nのワークフローを読み書きできる環境を整える。

```
[Claude 3.5 / Gemini 2.5] (AIエージェント脳)
           │
           ▼ (MCP Protocol)
   [Cline / Cursor (IDE)] (MCPクライアント)
           │
           ▼
[n8n MCP Tool (n8n Webhook / API)] ──＞ n8n内のワークフローの作成・修正・実行
```

### 3.3 n8n MCPを用いたAIエージェント連携の実践手順

ローカルに構築されたn8nの管理をAIエージェント（Claude DesktopやCline）に委ねるためのステップは以下の通り。

#### ステップ1: n8n APIキーの発行

1. ローカルn8nのGUIにアクセスし、**「Settings」 > 「User Settings」 > 「Personal API Keys」** に移動。
    
2. **「Create owner API key」** をクリックし、生成されたAPIキー（`n8n_api_...`）をコピー。
    

#### ステップ2: Cline / Claude Desktop のMCP設定

AIエージェントツールにn8nを制御するためのMCPサーバー設定を追加する。ここでは、標準的なn8n APIをMCPツールとして解釈・実行するためのNode.js製「n8n-mcp-server」（あるいはカスタムスクリプト）を設定ファイルに記載する。

- **`claude_desktop_config.json`（またはClineの設定）への記述例**:
    

```
{
  "mcpServers": {
    "n8n-mcp-server": {
      "command": "npx",
      "args": [
        "-y",
        "@n8n/mcp-server"
      ],
      "env": {
        "N8N_API_KEY": "あなたのn8n_api_keyをここに記述",
        "N8N_BASE_URL": "http://localhost:5678"
      }
    }
  }
}
```

#### ステップ3: AIエージェントに指示してワークフローを自動作成・保守させる

設定完了後、AIエージェントのチャット欄（ClineやClaude Desktop）に以下のような自然言語での開発指示を投げることで、エージェントが直接裏側でワークフローをデプロイする。

> **AIエージェントへの指示（プロンプト）例**: 「ローカルのn8nに、『超短期トレンド抽出システム』のワークフローを構築して。 要件は、毎朝7時に起動し、`twitter-cli`でコマンド `twitter search '"ClaudeCode" OR "爆速" min_faves:15' --json` を実行、取得データをCodeノードでクレンジングし、`gemini-2.5-flash`ノードを使ってリードマグネット企画を出力、最終的にSlackへ通知するフローです。」

## 4. 各プラットフォームのセットアップ手順

### 4.1 `twitter-cli` のCookieログインセットアップ

自動ログイン制限を強固に回避し、高い安定性を担保するためにブラウザの認証Cookieを抽出する。

#### 1. グローバルインストール

```
npm install -g @public-clis/twitter-cli
```

#### 2. Cookie値（セッション）の抽出

1. ブラウザで X (Twitter) にログインする。
    
2. `F12`（検証） -> **「Application（アプリケーション）」** タブを開く。
    
3. 左メニュー **「Cookies」** -> `https://x.com` を選択。
    
4. 以下の2つの値（Value）をコピーする。
    
    - **`auth_token`** (ログインセッション本体)
        
    - **`ct0`** (CSRFトークン)
        

#### 3. CLIへの認証設定

```
twitter login
```

- **「Use cookie login? (Y/n)」** に `Y` と答える。
    
- 画面の指示に従い、`auth_token` と `ct0` を貼り付けて認証を完了させる。
    

#### 4. 取得確認（動作確認用コマンド）

```
twitter search '"ClaudeCode" OR "爆速" min_faves:15' --json
```

### 4.2 n8nのローカル環境設定

ローカルn8nでシェルコマンド（Execute Commandノード）を実行可能にするため、環境変数を設定して起動する。

```
export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
n8n start
```

## 5. n8nワークフロー詳細設計（コード＆ノードパラメータ）

### 5.1 Execute Command ノード（Xデータ収集）

- **Command**:
    
    ```
    twitter search '"ClaudeCode" OR "Claude Code" OR "爆速" OR "爆益" OR "儲かる" OR "神ワザ" OR "完全自動化" OR "誰も知らなかった" OR "ワークフロー" OR "Dify" OR "Cursor" min_faves:15' --since {{ $today.minus({ days: 3 }).toISODate() }} --until {{ $today.toISODate() }} --json
    ```
    

### 5.2 Codeノード（JavaScriptによるデータ整形とクレンジング）

各プラットフォームから集計した異なるJSON/XML/HTML構造を一元化し、LLMのトークン効率を最大化する。

```javascript
// ※ n8n v1.x では $items() は廃止。$node["ノード名"].all() を使用すること。
// ※ このCodeノードの前に Merge ノード（Wait for All Items モード）を必ず挟む。
// ※ 統一スキーマは構築仕様書.md §4.3 を正とする。本書のスキーマ定義は参考のみ。

let combinedText = "=== 【顧客獲得用超短期AI実需分析データ】 ===\n\n";

// --- 1. X (Twitter) データのクレンジングと統合 ---
try {
  const xOutput = $node["Execute Command"].all()[0]?.json?.stdout;
  if (xOutput) {
    const tweets = JSON.parse(xOutput);
    combinedText += "■ [X (Twitter) のバズ・実利発言] ---------\n";
    let count = 0;
    for (const t of tweets) {
      const text = t.text || "";
      if (text && !text.includes("公式LINE") && !text.includes("プロフをチェック") && !text.includes("プレゼント配")) {
        combinedText += `- [${t.created_at || '不明'}] Fav:${t.favorite_count || 0} / RT:${t.retweet_count || 0}\n  内容: ${text.replace(/\n/g, " ")}\n`;
        count++;
      }
      if (count >= 50) break;
    }
  }
} catch (e) {
  combinedText += `※ Xデータのパースエラー: ${e.message}\n`;
}

// --- 2. note データの統合（2フィード分を結合）---
try {
  const noteItems = [
    ...$node["RSS Read (note-AI副業)"].all(),
    ...$node["RSS Read (note-AIツール)"].all()
  ];
  if (noteItems.length > 0) {
    combinedText += "\n■ [noteの実売・副業ノウハウ新着] ---------\n";
    for (const item of noteItems.slice(0, 15)) {
      combinedText += `- タイトル: ${item.json.title}\n  概要: ${item.json.contentSnippet || 'なし'}\n`;
    }
  }
} catch (e) {
  combinedText += `※ noteデータエラー: ${e.message}\n`;
}

// --- 3. Qiita データの統合 ---
try {
  const qiitaItems = $node["HTTP Request (Qiita)"].all();
  if (qiitaItems.length > 0) {
    combinedText += "\n■ [Qiita 技術実装の課題とエラー] ---------\n";
    for (const item of qiitaItems.slice(0, 15)) {
      combinedText += `- 記事名: ${item.json.title}\n  LG数: ${item.json.likes_count || 0}\n  タグ: ${item.json.tags?.map(t => t.name).join(", ")}\n`;
    }
  }
} catch (e) {
  combinedText += `※ Qiitaデータエラー: ${e.message}\n`;
}

return [{ json: { textData: combinedText } }];
```

### 5.3 Advanced AI / Google Gemini Chat Model 設定

- **Model**: `gemini-2.5-flash` (高速・大容量コンテキスト・超安価)
    
- **Temperature**: `0.3` (リードマグネットの創造性と分析の堅実性のバランスをとる)
    

#### 【Basic LLM Chain】 高度システムプロンプト

```
【役割】
あなたはAIツール、自動化、AI副業クラスターを深く理解し、自社への「顧客（リード）獲得」を劇的に増加させる天才マーケティングディレクターです。

【入力データ】
X（実利キーワードのバズ）、note（直近のノウハウ実売動向）、Qiita（技術課題・実装上の悩み）を統合した直近3〜5日間のトレンドデータ（{{ $json.textData }}）です。

【タスク】
ターゲット（能動的な副業志望ユーザー、業務効率化層）が、今まさに惹きつけられているトレンド（スパイクキーワード）を最大5つ抽出してください。
さらに、それらのターゲット層をハックし、自社顧客としてリスト（LINE、メールマガジン等）を獲得するための「即時実践可能な無料配布プレゼント（リードマグネット）の具体的な企画案」を設計して、指定のJSONスキーマに従って出力してください。
```

#### 【Structured Output Parser】スキーマ

> ⚠️ **このスキーマは採用しない。** 本書（設計書）と構築仕様書でフィールド名が異なり、通知テンプレートと整合しない。**実装時は `構築仕様書.md` §4.4②のスキーマ（`tech_status_pain` / `lead_hook` / `category` フィールドを持つもの）を使用すること。** 下記は参考として残す。
>
> | 本書フィールド | 仕様書の統一フィールド |
> |---|---|
> | `target_pain` | → `tech_status_pain` |
> | `lead_magnet_title` + `lead_magnet_content` | → `lead_hook`（統合） |
> | （なし） | → `category`（追加） |

```json
{
  "type": "object",
  "properties": {
    "trends": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "keyword": { "type": "string" },
          "category": { "type": "string" },
          "market_evidence": { "type": "string" },
          "tech_status_pain": { "type": "string" },
          "lead_hook": { "type": "string" },
          "score": {
            "type": "string",
            "enum": ["高（即時実践推奨）", "中（検証フェーズ）", "低（様子見）"]
          }
        },
        "required": ["keyword", "category", "market_evidence", "tech_status_pain", "lead_hook", "score"]
      }
    }
  }
}
```

## 6. 運用・安全対策およびテスト戦略

1. **セッション切れ（Cookie制限）のアラート**: XのCookieセッションが無効化した場合、`Execute Command` ノードがエラーを返します。n8nの `Error Trigger` ノードを設置し、エラー発生時は即座にSlack等へ「Cookie再設定要請」を自動通知する安全設計（フェイルセーフ）を組み込みます。
    
2. **モックファイルを用いたローカルテスト**: 構築初期のデバッグフェーズでは、XアカウントのBANを防ぐため、`Execute Command` は実行せず、事前にローカルで取得した `.json` ファイル（擬似データ）を `Read Binary File` でロードしてテストを行います。これにより、不要なリクエスト消費を防ぎます。