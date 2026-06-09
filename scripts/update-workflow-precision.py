#!/usr/bin/env python3
"""Update AIトレンド抽出 workflow for pinpoint tool-level keywords."""
import json
import urllib.request

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjczNmJmYS03NmVkLTRmNjQtOWI2Mi1mOGU1ZGM4Njk2NjAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYjEyOTA3ODMtNjczNi00NzY5LTg2NWYtYjU3MDM3YzliYzg3IiwiaWF0IjoxNzgwOTYxOTcyfQ.RNVAjo86pIzXZLRbSn2V3gXZfm2u1TiPLvRtUzZgz3s"
BASE = "http://localhost:5678/api/v1"
WF_ID = "axXa37Sq1YQQbIYj"

COMBINE_JS = r'''// Code はデータ整形のみ。候補選定・keyword判断は LLM がルーブリックに従って実施
const TOOL_PATTERNS = [
  { name: 'Dify', re: /\bdify\b/i },
  { name: 'n8n', re: /\bn8n\b/i },
  { name: 'Manus', re: /\bmanus\b/i },
  { name: 'OpenClaw', re: /\bopenclaw\b/i },
  { name: 'Windsurf', re: /\bwindsurf\b/i },
  { name: 'Bolt', re: /\bbolt\.new\b/i },
  { name: 'v0', re: /\bv0\.dev\b|\bv0 dev\b/i },
  { name: 'Lovable', re: /\blovable\b/i },
  { name: 'ComfyUI', re: /\bcomfyui\b/i },
  { name: 'Gemini CLI', re: /gemini\s*cli/i },
  { name: 'Devin', re: /\bdevin\b/i },
  { name: 'Magnific', re: /\bmagnific\b/i },
  { name: 'Make', re: /\bmake\.com\b/i },
  { name: 'Zapier', re: /\bzapier\b/i },
  { name: 'Claude Code', re: /claude\s*code|claudecode/i },
  { name: 'Cursor', re: /\bcursor\b/i },
];

const MONITORED_TOOLS = TOOL_PATTERNS.map((t) => t.name).join(', ');

function nodeItems(name) {
  try {
    return $(name).all() || [];
  } catch (e) {
    return [];
  }
}

function getHtmlBody(nodeName) {
  const items = nodeItems(nodeName);
  if (!items.length) return '';
  const j = items[0].json;
  return j.data || j.body || '';
}

function parseTipsHtml(html) {
  const items = [];
  const seen = new Set();
  const alts = [...html.matchAll(/alt="([^"]{10,120})"/g)].map((m) => m[1]);
  const links = [...html.matchAll(/href="(https:\/\/tips\.jp\/u\/[^"]+\/a\/[^"]+)"/g)].map((m) => m[1]);
  for (let i = 0; i < links.length && items.length < 10; i++) {
    const url = links[i];
    if (seen.has(url)) continue;
    seen.add(url);
    const title = alts[i] || url.split('/').pop();
    if (/Tips.*記事|カテゴリー/.test(title)) continue;
    items.push({ title, url });
  }
  return items;
}

function parseBrainHtml(html) {
  const items = [];
  const seen = new Set();
  const links = [...html.matchAll(/href="(\/u\/[^"]+\/a\/[^"]+)"/g)].map((m) => `https://brain-market.com${m[1]}`);
  for (const url of links) {
    if (seen.has(url)) continue;
    seen.add(url);
    const slug = url.split('/').pop();
    items.push({ title: `Brain教材 (${slug})`, url });
    if (items.length >= 10) break;
  }
  return items;
}

function parseTweets(raw) {
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed) ? parsed : (parsed.data || []);
}

function engagement(t) {
  const likes = t.metrics?.likes ?? t.favorite_count ?? 0;
  const rts = t.metrics?.retweets ?? t.retweet_count ?? 0;
  return likes + rts * 2;
}

function extractBuzzFromTweets(tweets) {
  const signals = new Map();

  for (const t of tweets) {
    const text = (t.text || '').replace(/\n/g, ' ');
    if (!text || /公式LINE|プレゼント企画|プロフをチェック/.test(text)) continue;
    const eng = engagement(t);

    for (const { name, re } of TOOL_PATTERNS) {
      if (!re.test(text)) continue;
      const cur = signals.get(name) || {
        mentions: 0,
        totalEngagement: 0,
        maxEngagement: 0,
        topSnippet: '',
      };
      cur.mentions += 1;
      cur.totalEngagement += eng;
      if (eng >= cur.maxEngagement) {
        cur.maxEngagement = eng;
        cur.topSnippet = text.slice(0, 100);
      }
      signals.set(name, cur);
    }
  }

  return [...signals.entries()]
    .map(([name, s]) => ({
      name,
      ...s,
      rankScore: s.maxEngagement + s.mentions * 12,
    }))
    .sort((a, b) => b.rankScore - a.rankScore);
}

function extractToolsFromTexts(texts) {
  const found = new Map();
  for (const text of texts) {
    if (!text) continue;
    for (const { name, re } of TOOL_PATTERNS) {
      if (re.test(text)) {
        found.set(name, (found.get(name) || 0) + 1);
      }
    }
  }
  return [...found.entries()].sort((a, b) => b[1] - a[1]);
}

let combinedText = '=== 【超短期トレンド分析用マルチソースデータ】 ===\n';
combinedText += '※ Codeは中立データのみ提供。候補選定はLLMがルーブリックで実施。\n';
combinedText += `※ 監視ツール（TOOL_PATTERNS）: ${MONITORED_TOOLS}\n`;
combinedText += '※ 上記以外の初出固有名詞は「X生投稿」から積極探索すること。\n\n';
let buzzCandidates = [];
let secondaryCandidates = [];
let noteToolsAgg = [];
let qiitaToolsAgg = [];

// --- 1. X (Twitter) ---
try {
  const execJson = nodeItems('Execute Command')[0]?.json || {};
  let xOutput = execJson.stdout;
  if (!xOutput && execJson.error) {
    combinedText += `■ [X (Twitter)] ---------\n※ Execute Command エラー: ${String(execJson.error).slice(0, 300)}\n\n`;
  }
  if (!xOutput) xOutput = nodeItems('Normalize Mock X')[0]?.json?.stdout;
  if (xOutput) {
    const tweets = parseTweets(xOutput);
    buzzCandidates = extractBuzzFromTweets(tweets);

    combinedText += '■ [Xツール言及シグナル（参考データ）] ---------\n';
    if (buzzCandidates.length === 0) {
      combinedText += '（X上のツール言及なし。note/Qiita/生投稿から候補を抽出すること）\n';
    } else {
      buzzCandidates.slice(0, 15).forEach((s, i) => {
        combinedText += `${i + 1}. ${s.name} | 言及${s.mentions} | 最高Eng${s.maxEngagement} | 「${s.topSnippet}」\n`;
      });
    }
    combinedText += '\n';

    combinedText += '■ [X (Twitter) 生投稿（上位30件）] ---------\n';
    const sorted = [...tweets]
      .filter((t) => t.text && !/公式LINE|プレゼント企画|プロフをチェック/.test(t.text))
      .sort((a, b) => engagement(b) - engagement(a))
      .slice(0, 30);

    for (const t of sorted) {
      const likes = t.metrics?.likes ?? t.favorite_count ?? 0;
      const rts = t.metrics?.retweets ?? t.retweet_count ?? 0;
      const createdAt = t.createdAtISO || t.created_at || '不明';
      combinedText += `- [${createdAt}] Fav:${likes} RT:${rts}\n  ${(t.text || '').replace(/\n/g, ' ')}\n`;
    }
    combinedText += '\n';
  } else {
    combinedText += '■ [X (Twitter)] ---------\n（Xデータなし: twitter-cliエラーまたは検索0件）\n\n';
  }
} catch (e) {
  combinedText += `※ Xデータのパースエラー: ${e.message}\n\n`;
}

// --- 2. note ---
try {
  const noteItems = [
    ...nodeItems('RSS Read (note-AI副業)'),
    ...nodeItems('RSS Read (note-AIツール)'),
  ];
  const noteTitles = noteItems.map((i) => i.json.title || '');
  noteToolsAgg = extractToolsFromTexts(noteTitles);

  if (noteToolsAgg.length > 0) {
    combinedText += '■ [noteで検出された具体ツール名] ---------\n';
    for (const [name, count] of noteToolsAgg.slice(0, 10)) {
      combinedText += `- ${name}: タイトル言及${count}件\n`;
    }
    combinedText += '\n';
  }

  if (noteItems.length > 0) {
    combinedText += '■ [note新着記事（タイトルのみ）] ---------\n';
    for (const item of noteItems.slice(0, 12)) {
      combinedText += `- ${item.json.title} | ${item.json.link}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ noteデータ取得エラー: ${e.message}\n\n`;
}

// --- 3. Brain ---
try {
  const brainHtml = getHtmlBody('HTTP Request (Brain)');
  const brainItems = brainHtml ? parseBrainHtml(brainHtml) : [];
  if (brainItems.length > 0) {
    combinedText += '■ [Brain 教材タイトル] ---------\n';
    for (const item of brainItems) {
      combinedText += `- ${item.title} | ${item.url}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ Brainデータエラー: ${e.message}\n\n`;
}

// --- 4. Tips ---
try {
  const tipsHtml = getHtmlBody('HTTP Request (Tips)');
  const tipsItems = tipsHtml ? parseTipsHtml(tipsHtml) : [];
  if (tipsItems.length > 0) {
    combinedText += '■ [Tips 教材タイトル] ---------\n';
    for (const item of tipsItems) {
      combinedText += `- ${item.title} | ${item.url}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ Tipsデータエラー: ${e.message}\n\n`;
}

// --- 5. Qiita ---
try {
  const qiitaItems = nodeItems('HTTP Request (Qiita)');
  const qiitaTitles = qiitaItems.map((i) => i.json.title || '');
  qiitaToolsAgg = extractToolsFromTexts(qiitaTitles);

  if (qiitaToolsAgg.length > 0) {
    combinedText += '■ [Qiitaで検出された具体ツール名] ---------\n';
    for (const [name, count] of qiitaToolsAgg.slice(0, 10)) {
      combinedText += `- ${name}: 記事言及${count}件\n`;
    }
    combinedText += '\n';
  }

  if (qiitaItems.length > 0) {
    combinedText += '■ [Qiita 技術記事] ---------\n';
    for (const item of qiitaItems.slice(0, 12)) {
      const tags = (item.json.tags || []).map((t) => t.name).join(', ');
      combinedText += `- ${item.json.title} | LG:${item.json.likes_count || 0} | ${tags} | ${item.json.url}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ Qiitaデータエラー: ${e.message}\n\n`;
}

// Xが空のとき note/Qiita から候補を補完
if (buzzCandidates.length === 0) {
  try {
    const noteItems = [
      ...nodeItems('RSS Read (note-AI副業)'),
      ...nodeItems('RSS Read (note-AIツール)'),
    ];
    const qiitaItems = nodeItems('HTTP Request (Qiita)');
    const noteTools = extractToolsFromTexts(noteItems.map((i) => i.json.title || ''));
    const qiitaTools = extractToolsFromTexts(qiitaItems.map((i) => i.json.title || ''));
    const merged = new Map();
    for (const [name, count] of [...noteTools, ...qiitaTools]) {
      merged.set(name, (merged.get(name) || 0) + count);
    }
    secondaryCandidates = [...merged.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, mentions: count, source: 'note/Qiita' }));

    if (secondaryCandidates.length > 0) {
      combinedText += '■ [代替バズ候補（X未取得時・note/Qiitaから）] ---------\n';
      secondaryCandidates.slice(0, 10).forEach((s, i) => {
        combinedText += `${i + 1}. ${s.name} | 言及${s.mentions}件 | 出典:${s.source}\n`;
      });
      combinedText += '\n';
    }
  } catch (e) {
    combinedText += `※ 代替候補抽出エラー: ${e.message}\n\n`;
  }
}

// マルチソース言及カウント（ルーブリック1用・選定はLLMが行う）
const xMap = Object.fromEntries(buzzCandidates.map((s) => [s.name, s.mentions]));
const noteMap = Object.fromEntries(noteToolsAgg);
const qiitaMap = Object.fromEntries(qiitaToolsAgg);
const allToolNames = new Set([
  ...buzzCandidates.map((s) => s.name),
  ...noteToolsAgg.map(([n]) => n),
  ...qiitaToolsAgg.map(([n]) => n),
]);

if (allToolNames.size > 0) {
  combinedText += '■ [マルチソース言及カウント（選定参考）] ---------\n';
  const rows = [...allToolNames].map((name) => {
    const x = xMap[name] || 0;
    const note = noteMap[name] || 0;
    const qiita = qiitaMap[name] || 0;
    const srcCount = [x > 0, note > 0, qiita > 0].filter(Boolean).length;
    const srcLabel = [
      x > 0 ? 'X' : null,
      note > 0 ? 'note' : null,
      qiita > 0 ? 'Qiita' : null,
    ].filter(Boolean).join('+') || '—';
    return { name, x, note, qiita, srcCount, srcLabel };
  }).sort((a, b) => b.srcCount - a.srcCount || (b.x + b.note + b.qiita) - (a.x + a.note + a.qiita));

  for (const r of rows.slice(0, 20)) {
    combinedText += `- ${r.name}: X${r.x} / note${r.note} / Qiita${r.qiita} | 裏付けソース:${r.srcCount} (${r.srcLabel})\n`;
  }
  combinedText += '\n';
}

const allCandidateNames = [
  ...buzzCandidates.map((s) => s.name),
  ...secondaryCandidates.map((s) => s.name),
];

return [{
  json: {
    textData: combinedText,
    buzzCandidates: [...new Set(allCandidateNames)],
  },
}];'''

LLM_PROMPT = """【役割】
直近3〜5日のマルチソースデータを読み、**注目ツール候補リスト**と**全体分析**の2つだけを出力するアナリスト。
候補ごとの個別分析は書かない。入力データの整形は済んでいる。**何を候補にするかはあなた（LLM）がルーブリックで判断すること。**

【出力形式（厳守）】
1. candidates: 固有名詞ツール名の配列（優先度順）
2. overall_analysis: 全体所見を1つの文章で

【選定ルーブリック（candidates の判断基準・厳守）】
1. **複数ソース（X + note/Qiita）で裏付けがあるものを最優先**（「マルチソース言及カウント」の裏付けソース数が多い順）
2. **定番ツール（Claude Code, Cursor, ChatGPT）は全体で最大1件**。それ以外はニッチ・新興を優先
3. **抽象語は候補不可**: MCP, 生成AI, AI副業, ChatGPT, ノーコード, 効率化, AI画像生成 など
4. **TOOL_PATTERNS外の初出固有名詞**が「X生投稿」にあれば積極採用（監視リスト外の新興ツールを見逃さない）
5. **根拠が弱いものは出力しない**（2〜3件でも可。無理に10件埋めない）

【candidates の形式】
- 各要素は製品名・サービス名（1〜4語の固有名詞）のみ
- 良い例: Dify, Manus, n8n, OpenClaw, ComfyUI, Lovable, Windsurf
- 最大10件。ルーブリック5により根拠弱ければ2〜3件でよい

【overall_analysis に含める観点（全体で1文に統合）】
- Xバズの傾向
- note/Brain/Tipsの実売シグナル
- Qiita等の実装トレンド・詰まりポイント
- リード獲得の打ち手（1〜2個）

【文字数制約（Discord 2000字制限）】
- overall_analysis: 最大800文字
- candidates: 候補ごとの説明は書かない（名前のみ）"""

SCHEMA_EXAMPLE = """{
  "candidates": [
    "OpenClaw",
    "Manus",
    "Dify",
    "ComfyUI",
    "n8n",
    "Lovable"
  ],
  "overall_analysis": "直近3日はOpenClaw/Manus/DifyがX+note+Qiitaの3ソースで裏付けあり。OpenClawはX高Eng、Manus/Difyはnote有料記事が複数。Qiitaはn8n×DifyのRAG連携質問が増加。定番のClaude Code言及は多いがルーブリック上は候補から外し差別化を図る。リード獲得は「OpenClaw初日セットアップ」か「Dify×Slack業務Bot」が有望。"
}"""

FORMAT_JS = r'''const output = $json.output || $json;
const DISCORD_MAX = 2000;
const LIMIT = 1985;

const GENERIC = /^(AI|ChatGPT|生成AI|AI画像|AI動画|AIライティング|AI副業|ノーコード|効率化|副業|MCP)$/i;
const ESTABLISHED = /^(Claude Code|Cursor|ChatGPT)$/i;

function splitForDiscord(text) {
  if (text.length <= DISCORD_MAX) return [text.trim()];
  const chunks = [];
  let current = '';
  for (const line of text.split('\n')) {
    const next = current ? `${current}\n${line}` : line;
    if (next.length > LIMIT) {
      if (current) chunks.push(current);
      if (line.length > LIMIT) {
        for (let i = 0; i < line.length; i += LIMIT) chunks.push(line.slice(i, i + LIMIT));
        current = '';
      } else current = line;
    } else current = next;
  }
  if (current) chunks.push(current);
  return chunks.map((c) => c.trim()).filter(Boolean);
}

const rawCandidates = output.candidates || [];
const candidates = rawCandidates
  .map((c) => (typeof c === 'string' ? c : c?.keyword || ''))
  .map((k) => String(k).trim())
  .filter((k) => k && !GENERIC.test(k));

const seen = new Set();
let unique = [];
for (const k of candidates) {
  if (seen.has(k)) continue;
  seen.add(k);
  unique.push(k);
  if (unique.length >= 10) break;
}

const established = unique.filter((k) => ESTABLISHED.test(k));
if (established.length > 1) {
  const keep = established[0];
  unique = unique.filter((k) => !ESTABLISHED.test(k) || k === keep);
}

const overall = String(output.overall_analysis || '').trim();

let message = '📢 【朝刊】AIツール・バズシグナル速報 📢\n\n';
message += '直近3日間のマルチソース分析\n\n';
message += `【注目候補（${unique.length}件）】\n`;
if (unique.length === 0) {
  message += '（候補なし）\n';
} else {
  unique.forEach((k, i) => { message += `${i + 1}. ${k}\n`; });
}
message += '\n【全体分析】\n';
message += overall || '（分析なし）\n';

if (unique.length === 0 && !overall) {
  message += '\n確認: ①twitter-cli Cookie ②USE_MOCK_X=true ③note/Qiita取得状況\n';
}

const parts = splitForDiscord(message);
const total = parts.length;

return parts.map((text, index) => {
  const body = total > 1 ? `[${index + 1}/${total}]\n${text}` : text;
  return {
    json: {
      text: body.length > DISCORD_MAX ? body.slice(0, DISCORD_MAX) : body,
      part: index + 1,
      totalParts: total,
      candidates: unique,
      overall_analysis: overall,
    },
  };
});'''

TWITTER_CMD = (
    '=twitter search \''
    'Dify OR n8n OR Manus OR OpenClaw OR Windsurf OR Bolt OR Lovable OR ComfyUI '
    'OR "v0.dev" OR "Gemini CLI" OR Make.com OR Zapier OR Devin OR Magnific '
    'OR 知らないと損 OR 神ワザ OR 爆速 OR 新ツール OR 初公開\' '
    '--since {{ $today.minus({ days: 3 }).toISODate() }} '
    '--until {{ $today.plus({ days: 1 }).toISODate() }} '
    '--min-likes 5 --json'
)

QIITA_URL = (
    '=https://qiita.com/api/v2/items?query='
    'tag:n8n+OR+tag:Dify+OR+tag:Manus+OR+tag:Windsurf+OR+tag:OpenClaw+OR+tag:ComfyUI'
    '+created:>={{ $today.minus({ days: 3 }).toISODate() }}&per_page=15'
)


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main():
    wf = api("GET", f"/workflows/{WF_ID}")

    for node in wf["nodes"]:
        name = node["name"]
        if name == "Code (Combine Sources)":
            node["parameters"]["jsCode"] = COMBINE_JS
        elif name == "Basic LLM Chain":
            node["parameters"]["messages"]["messageValues"][0]["message"] = LLM_PROMPT
        elif name == "Structured Output Parser":
            node["parameters"]["jsonSchemaExample"] = SCHEMA_EXAMPLE
        elif name == "Code (Format Notification)":
            node["parameters"]["jsCode"] = FORMAT_JS
        elif name == "Execute Command":
            node["parameters"]["command"] = TWITTER_CMD
        elif name == "Read Mock X":
            node["parameters"]["fileSelector"] = "/home/node/.n8n-files/mock/x-tweets-sample.json"
        elif name == "HTTP Request (Qiita)":
            node["parameters"]["url"] = QIITA_URL
        elif name == "Google Gemini Chat Model":
            node["parameters"]["options"]["temperature"] = 0.2

    clean_nodes = []
    for n in wf["nodes"]:
        clean = {k: v for k, v in n.items() if k in [
            "parameters", "id", "name", "type", "typeVersion", "position",
            "continueOnFail", "retryOnFail", "waitBetweenTries", "maxTries",
            "credentials", "notesInFlow",
        ]}
        clean_nodes.append(clean)

    result = api("PUT", f"/workflows/{WF_ID}", {
        "name": wf["name"],
        "nodes": clean_nodes,
        "connections": wf["connections"],
        "settings": {"executionOrder": "v1"},
    })

    checks = {n["name"]: n for n in result["nodes"]}
    combine_js = checks["Code (Combine Sources)"]["parameters"]["jsCode"]
    assert "nodeItems" in combine_js
    assert "$node[" not in combine_js
    llm_msg = checks["Basic LLM Chain"]["parameters"]["messages"]["messageValues"][0]["message"]
    assert "選定ルーブリック" in llm_msg
    assert "TOOL_PATTERNS外" in llm_msg
    assert "マルチソース言及カウント" in checks["Code (Combine Sources)"]["parameters"]["jsCode"]
    assert "candidates" in checks["Structured Output Parser"]["parameters"]["jsonSchemaExample"]
    assert "ESTABLISHED" in checks["Code (Format Notification)"]["parameters"]["jsCode"]
    assert "splitForDiscord" in checks["Code (Format Notification)"]["parameters"]["jsCode"]
    print("OK", result["updatedAt"])


if __name__ == "__main__":
    main()
