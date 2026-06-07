## 〜ローカルn8n ＋ マルチソース ＋ Gemini API による「顧客獲得特化型」超短期AIトレンド抽出システム〜

本書は、X（旧Twitter）、実売プラットフォーム（note, Brain, Tips）、技術コミュニティ（Qiita）から多角的にデータを収集し、直近3〜5日間に急増している「AI副業」「爆速・爆益」「最新効率化ワークフロー」など、最も熱量が高く顧客獲得（リードジェネレーション）に直結する超短期トレンドを完全自動で安全に抽出・構造化・通知するためのシステム構築仕様書である。

## 1. システム概要と特徴

### 1.1 システム構成図（概念）

```
                     ┌─ [X (twitter-cli)] ───＞ 「爆速/爆益/ClaudeCode」等のバズ・エンゲージメント検知
                     ├─ [note (RSS)] ────────＞ 実用ノウハウ、個人ビジネスの流行
[Schedule Trigger] ──┼─ [Brain (HTTP Req)] ──＞ 直感的なマネタイズ、有償教材の売れ筋
 (毎朝自動起動)       ├─ [Tips (HTTP Req)] ───＞ AI副業、特化型ノウハウの最前線
                     └─ [Qiita (API/RSS)] ───＞ 技術実装トレンド、開発者の課題・エラー

                               │（各データをパース・統合）
                               ▼
                        [Code (JavaScript)] ─＞ (生データのクレンジング、一元化テキスト整形)
                               │
                               ▼
                       [Basic LLM Chain] ───＞ (Gemini 2.5 Flashによる「顧客獲得視点」の横断分析)
                               ├─ [Google Gemini Chat Model]
                               └─ [Structured Output Parser] (JSON構造化 + 顧客獲得フック自動生成)
                               ▼
                 [Data Storage / Notifications] ─＞ (Notion/Sheets格納、Slack/Discord通知)
```

### 1.2 本システムの強み（顧客獲得フォーカス）

1. **実利キーワードの徹底ハック**: 「儲かる」「効率化」「爆速」「爆益」「ClaudeCode」「誰も知らなかった」など、能動的で購買意欲の高い副業ユーザーが最も活発に反応するキーワードを優先的に検知。
    
2. **マーケティングフックの自動生成**: 3〜5日の超短期スパイクを検出するだけでなく、それをフックに「どうすれば自分のターゲット顧客を獲得できるか（リード獲得企画）」をGeminiが自動提案。
    
3. **Cookie認証による高いXデータ安定性**: ブラウザの認証セッション（Cookie）を再利用するため、多要素認証（2FA）やボット検知によるログインブロックを完全に回避して安定稼働。
    
4. **ローカルセルフホスト**: 機密性の高いCookie情報やリード獲得の独自の分析プロンプトを外部に漏洩させない、安全なセルフホスト環境。
    

## 2. システム要件・前提条件

### 2.1 ローカル動作環境

- **n8n**: セルフホスト版（npm、Docker、またはデスクトップ版のいずれか）
    
- **OS**: macOS / Linux / Windows (WSL2推奨)
    
- **Node.js**: v18以上（npm版の場合）
    

### 2.2 必要アカウント・認証情報・API

- **X (Twitter) アカウント**: 閲覧用のサブアカウント（Cookie情報抽出用。アカウント制限対策として推奨）
    
- **Google AI Studio APIキー**: Gemini APIを利用するための無償/有償APIキー
    
- **Qiita アクセストークン** (任意): 個人アクセストークン（レートリミット緩和のために推奨）
    
- **通知先Webhook**: SlackのIncoming Webhook、またはDiscordのWebhook URL
    

## 3. 各コンポーネントのセットアップ手順

### 3.1 `twitter-cli` のインストールとCookieによる認証設定

Xアカウントのログイン制限を回避するために、ブラウザから認証Cookieを取得して `twitter-cli` に設定する。

#### 1. パッケージのグローバルインストール

```
npm install -g @public-clis/twitter-cli
```

#### 2. ブラウザからCookie情報の取得

1. Google Chrome等で X (Twitter) にログインする。
    
2. キーボードの `F12`（右クリック -> 「検証」）で**デベロッパーツール**を開く。
    
3. **「Application」**（アプリケーション）タブを選択する。
    
4. 左メニューから **「Cookies」** -> `https://x.com` を展開する。
    
5. 以下の2つのCookieキーの値（Value）をコピーする。
    
    - **`auth_token`** (約40文字の英数字。ログインセッション本体)
        
    - **`ct0`** (約160文字の英数字。CSRFトークン)
        

#### 3. CLI認証のセットアップ

`twitter login` コマンドを実行し、対話形式に従ってCookieの入力を指定する。

```
twitter login
```

- **「Use cookie login?」** に対して `Y` を選択。
    
- コピーした **`auth_token`** 和 **`ct0`** をそれぞれ貼り付ける。
    

#### 4. 動作確認

```
twitter search "Dify" --json
```

### 3.2 n8nのローカル実行環境の設定（環境変数）

n8nからシェルコマンドを動かせるように環境変数をセットして起動する。

- **npm起動の場合**:
    
    ```
    export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
    export N8N_BLOCK_ENV_ACCESS_IN_NODE=false
    n8n start
    ```
    

## 4. n8nワークフロー詳細設計

### 4.1 Trigger ノード

- **ノード名**: `Schedule Trigger`
    
- **設定**: 毎日朝 07:00 AM 起動
    

### 4.2 Multi-Source Data Collection（マルチソース収集）

n8n上で5つのデータ収集フローを並列に配置し、それぞれの出力を **`Merge` ノード（"Wait for All Items" モード）で必ず合流させてから** `Code` ノードに渡す。Mergeノードを挟まないと、Codeノードは最後に実行されたブランチの出力しか受け取れない。

#### ① X（旧Twitter）データ収集 (実利・爆速キーワード特化型)

副業クラスターが熱狂する「実利フック」「ClaudeCode新機能」「誰も知らなかった自動化ワークフロー」等に絞り込んだ高度なクエリを実行する。

- **ノード名**: `Execute Command`
    
- **コマンド**:
    
    ```
    twitter search '"ClaudeCode" OR "Claude Code" OR "爆速" OR "爆益" OR "儲かる" OR "神ワザ" OR "完全自動化" OR "誰も知らなかった" OR "ワークフロー" OR "Dify" OR "Cursor" min_faves:15' --since {{ $today.minus({ days: 3 }).toISODate() }} --until {{ $today.plus({ days: 1 }).toISODate() }} --json
    ```
    
    _※ `min_faves:15` に設定し、情報の確度が高く、ユーザーが実際にリプライやブックマークで活発に関わっているポストのみをフィルタリング。_
    _※ `--until` は排他的（指定日を含まない）仕様のため、`$today.plus({ days: 1 })` で当日ツイートを取得範囲に含める。_
    

#### ② noteデータ収集（RSSフィード監視）

noteの「AI副業」「AIツール」「自動化」タグの新着記事RSSを取得。n8nのRSS Readノードは1URLしか設定できないため、**2つの独立したRSS Readノード**を用意する。

- **ノード名**: `RSS Read (note-AI副業)`
    - **URL**: `https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss`

- **ノード名**: `RSS Read (note-AIツール)`
    - **URL**: `https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss`
        

#### ③ Brainデータ収集（HTTP Request）

Brainの「AI」関連の人気・新着記事リストのメタデータを収集。

- **ノード名**: `HTTP Request (Brain)`
    
- **Method**: `GET`
    
- **URL**: `https://brain-market.com/api/v1/search?keyword=AI&sort=new`

> ⚠️ **注意**: このエンドポイントは非公式であり、実際にHTMLを返す可能性がある。構築時にP2-6（疎通確認）でレスポンス形式を必ず確認し、HTMLの場合はCodeノード内でのHTMLパース処理（タイトル・説明文のテキスト抽出）を追加実装すること。

#### ④ Tipsデータ収集（HTTP Request）

TipsのAIカテゴリの新着・人気記事を収集。

- **ノード名**: `HTTP Request (Tips)`
    
- **Method**: `GET`
    
- **URL**: `https://tips.jp/search?q=AI`

> ⚠️ **注意**: BrainとTipsは別ノード（別ノード名）とすること。同一ノードにまとめるとCodeノードで一方のデータが消失する。BrainのAPIと同様にレスポンスがHTMLの場合があるため、P2-7で構造確認を行ってからCodeノードのパースロジックを実装すること。
    

#### ⑤ Qiitaデータ収集（Qiita API）

開発コミュニティが現在格闘している技術の裏付け、または「エラー解決・実装」の動向を抽出。

- **ノード名**: `HTTP Request`
    
- **Method**: `GET`
    
- **URL**: `https://qiita.com/api/v2/items?query=tag:AI+created:>=` + `{{ $today.minus({ days: 3 }).toISODate() }}`
    
- **Headers**: `Authorization: Bearer <Qiitaアクセストークン>`
    

### 4.3 Data Preparation & Normalization（データ一元化・整形）

5つの異なるフォーマット（XのJSON、RSSのXML、APIのJSON、HTML生データ）を `Code` ノードに引き渡し、Geminiが最も理解しやすい**ひとまとまりの統合テキスト**へ超高速でクレンジング整形する。

- **ノード名**: `Code`
    
- **実行モード**: `Run Once for All Items`
    
- **言語**: JavaScript
    
- **コード内容**:
    
    ```javascript
    // ※ n8n v1.x では $items() は廃止。$node["ノード名"].all() を使用すること。
    // ※ このCodeノードの前に Merge ノード（Wait for All Items モード）を必ず挟む。
    
    let combinedText = "=== 【超短期トレンド分析用マルチソースデータ】 ===\n\n";
    
    // --- 1. X (Twitter) データ処理 ---
    try {
      const xOutput = $node["Execute Command"].all()[0]?.json?.stdout;
      if (xOutput) {
        const tweets = JSON.parse(xOutput);
        combinedText += "■ [X (Twitter) の言及・バズ] ---------\n";
        let count = 0;
        for (const t of tweets) {
          const text = t.text || "";
          if (text && !text.includes("公式LINE") && !text.includes("プレゼント企画") && !text.includes("プロフをチェック")) {
            combinedText += `- [${t.created_at || '不明'}] Fav:${t.favorite_count || 0} / RT:${t.retweet_count || 0}\n  内容: ${text.replace(/\n/g, " ")}\n`;
            count++;
          }
          if (count >= 50) break;
        }
        combinedText += "\n";
      }
    } catch (e) {
      combinedText += `※ Xデータのパースエラー: ${e.message}\n\n`;
    }
    
    // --- 2. note データ処理（2フィード分を結合）---
    try {
      const noteItems = [
        ...$node["RSS Read (note-AI副業)"].all(),
        ...$node["RSS Read (note-AIツール)"].all()
      ];
      if (noteItems.length > 0) {
        combinedText += "■ [noteの新着・トレンド記事] ---------\n";
        for (const item of noteItems.slice(0, 15)) {
          combinedText += `- タイトル: ${item.json.title}\n  概要: ${item.json.contentSnippet || 'なし'}\n  URL: ${item.json.link}\n`;
        }
        combinedText += "\n";
      }
    } catch (e) {
      combinedText += `※ noteデータ取得エラー: ${e.message}\n\n`;
    }
    
    // --- 3. Brain データ処理 ---
    // ⚠️ レスポンスがHTMLの場合はここでのパースが失敗する。P2-6疎通確認後に実装を修正すること。
    try {
      const brainItems = $node["HTTP Request (Brain)"].all();
      if (brainItems.length > 0) {
        combinedText += "■ [Brain 実売商品・教材] ---------\n";
        for (const item of brainItems.slice(0, 10)) {
          combinedText += `- 教材名: ${item.json.title || '不明'}\n  価格: ${item.json.price || '無料/未詳'}円\n  概要: ${item.json.description || 'なし'}\n`;
        }
        combinedText += "\n";
      }
    } catch (e) {
      combinedText += `※ BrainデータエラーまたはHTML返却（要パーサー実装）: ${e.message}\n\n`;
    }
    
    // --- 4. Tips データ処理 ---
    // ⚠️ 同上。HTMLの場合はパーサー実装が必要。
    try {
      const tipsItems = $node["HTTP Request (Tips)"].all();
      if (tipsItems.length > 0) {
        combinedText += "■ [Tips 副業ノウハウ教材] ---------\n";
        for (const item of tipsItems.slice(0, 10)) {
          combinedText += `- 教材名: ${item.json.title || '不明'}\n  概要: ${item.json.description || 'なし'}\n`;
        }
        combinedText += "\n";
      }
    } catch (e) {
      combinedText += `※ TipsデータエラーまたはHTML返却（要パーサー実装）: ${e.message}\n\n`;
    }
    
    // --- 5. Qiita データ処理 ---
    try {
      const qiitaItems = $node["HTTP Request (Qiita)"].all();
      if (qiitaItems.length > 0) {
        combinedText += "■ [Qiita 技術実装・エラー解決] ---------\n";
        for (const item of qiitaItems.slice(0, 15)) {
          combinedText += `- 記事名: ${item.json.title}\n  LG数: ${item.json.likes_count || 0}\n  タグ: ${item.json.tags?.map(t => t.name).join(", ")}\n  URL: ${item.json.url}\n`;
        }
        combinedText += "\n";
      }
    } catch (e) {
      combinedText += `※ QiitaデータエラーまたはパースエラーL ${e.message}\n\n`;
    }
    
    return [{ json: { textData: combinedText } }];
    ```
    

### 4.4 AI Analysis（顧客獲得特化・クロス分析）

収集した実利データをGemini 2.5 Flashに渡し、情報鮮度、マネタイズ性、そして「どのように自社のリード（見込み顧客）獲得に繋げるか」のマーケティング戦略まで一括で落とし込む。

- **ノード名**: `Basic LLM Chain`
    
    - **Model**: `Google Gemini Chat Model` (Model: `gemini-2.5-flash`, Temperature: `0.3` ※企画発想力を少し高めるためやや高めに設定)
        
    - **Parser**: `Structured Output Parser` (JSON構造化)
        

#### ① Basic LLM Chain の高度プロンプト (Prompt)

```
【役割】
あなたは最先端のAIツール、AI副業、そして自動化ワークフローを熟知し、自社サービスや有償コンテンツへの「顧客獲得（リードジェネレーション）」を最も得意とする天才マーケティングディレクターです。

【入力データ】
X（実利キーワードのバズ）、note/Brain/Tips（直近の実売需要）、Qiita（技術実装の壁）が統合された、直近3〜5日間のデータ（{{ $json.textData }}）が提供されます。

【タスク】
提供されたマルチソースデータをクロス分析し、現在能動的なAI副業ユーザー、効率化を求めるビジネス層が「喉から手が出るほど欲しがっている」超短期トレンドキーワードを最大5つ抽出してください。
さらに、それらのターゲット層を惹きつけて、自社サービスへの登録や問い合わせ（顧客獲得）を発生させるための具体的な「リード獲得用配布企画（リードマグネット）」を逆算して提案してください。

【分析の軸（思考プロセス）】
1. 何が今、副業層や効率化ビジネス層を刺激しているか？（例：ClaudeCodeの誰も知らないコマンド、Dify×LINEの爆速構築法など）
2. note/Brain/Tipsで「お金を払ってでも買われている形（実売）」は何か？
3. Qiitaで「実装の段階でみんなが詰まっている壁」は何か？（＝ここを解決するプレゼントを配れば高確率でリストが取れる）
4. これらを踏まえ、どのようなコンテンツを企画・配布すれば最も能動的な顧客リストが獲得できるかを設計してください。
```

#### ② Structured Output Parser の設定 (JSON Schema)

```
{
  "type": "object",
  "properties": {
    "trends": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "keyword": {
            "type": "string",
            "description": "トレンドとなっているAIツール・手法（例: ClaudeCode, Dify+LINE, v0など）"
          },
          "category": {
            "type": "string",
            "description": "ツールの分類（例: '開発自動化', 'エージェント構築', '爆速マネタイズ手法' など）"
          },
          "market_evidence": {
            "type": "string",
            "description": "note/Brain/TipsやXで、副業ユーザーがどのような「爆益」「稼げる」文脈で反応しているか"
          },
          "tech_status_pain": {
            "type": "string",
            "description": "Qiita等の開発者やX検証者が詰まっているリアルな課題・実装エラー箇所"
          },
          "lead_hook": {
            "type": "string",
            "description": "★最重要：この層を自社顧客（リード）として獲得するために配布すべき『無料プレゼント（リードマグネット）の具体的な企画案』（例：『ClaudeCodeを使った爆速コード生成プロンプトテンプレート』『Dify APIエラーを2秒で解消するチートシート』など。ターゲットを熱狂させる具体的なタイトルと内容を提示すること）"
          },
          "score": {
            "type": "string",
            "enum": ["高（即時実践推奨）", "中（検証フェーズ）", "低（様子見）"],
            "description": "需要の急増度と、自社の顧客獲得（リードジェン）への貢献ポテンシャルから算出した統合スコア"
          }
        },
        "required": ["keyword", "category", "market_evidence", "tech_status_pain", "lead_hook", "score"]
      }
    }
  }
}
```

### 4.5 Data Storage & Notification（顧客獲得戦略の通知）

#### ① Slack/Discord通知用フォーマット（Codeノードで生成）

> ⚠️ n8nはHandlebars（`{{#each}}`）構文に対応していない。Slack/Discordノードへ渡す前に **Codeノードで文字列を組み立てる**こと。

- **ノード名**: `Code (Format Notification)`
- **言語**: JavaScript

```javascript
// Basic LLM Chain の出力（$json.trends 配列）を Slack 向けテキストに整形する
const trends = $json.trends || [];

let message = "📢 【朝刊】マルチソースAI実需分析 ＆ 顧客獲得（リード）戦略速報 📢\n\n";
message += "直近3日間の「X(バズ)」「note/Brain/Tips(実売)」「Qiita(実装エラー)」をGeminiが横断分析しました。\n\n";

for (const t of trends) {
  message += `🔥 キーワード: 【${t.keyword}】 （カテゴリ: ${t.category} / 顧客獲得価値: ${t.score}）\n`;
  message += `・ターゲットの実売需要: ${t.market_evidence}\n`;
  message += `・ターゲットの実装上の悩み: ${t.tech_status_pain}\n`;
  message += `💡 【顧客獲得（リード）施策案】:\n`;
  message += `👉 『 ${t.lead_hook} 』\n`;
  message += "--------------------------------------------------\n";
}

return [{ json: { text: message } }];
```

このCodeノードの出力（`$json.text`）をSlackノードの「Text」フィールドに渡す。

## 5. 運用ノウハウ・安全対策

### 5.1 能動的ユーザーを逃さない運用の極意

1. **「痛みの解決」にフォーカスしたプレゼント設計**: 副業ユーザーは「詰まっている時間」を極度に嫌います。QiitaやXから抽出された `tech_status_pain`（実装エラーや複雑な設定の壁）を即座に解決する簡易PDFやプロンプトテンプレートを `lead_hook` として設計し、Xで「〇〇を解決するワークフローを無料配布」といった企画を打つと、極めて能動的な見込み顧客のリストが圧倒的な初速で獲得可能になります。
    
2. **情報の「鮮度」のハック**: このシステムは3〜5日の「超短期スパイク」を捉えるため、`ClaudeCode`の新アップデートや新機能など、まだ大手がコンテンツ化していないタイミング（1〜2日以内）で素早く無料配布企画を立ち上げることが、競合を出し抜く最大のポイントです。