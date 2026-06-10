#!/usr/bin/env python3
"""Build daily + weekly workflows for dynamic watchlist strategy."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = ROOT / "workflows" / "ai-trend-extractor.json"
WEEKLY_PATH = ROOT / "workflows" / "watchlist-generator.json"
WATCHLIST_CONTAINER_PATH = "/home/node/.n8n-files/config/watchlist.json"

# ---------------------------------------------------------------------------
# Shared JS: mechanical candidate extraction (weekly only)
# ---------------------------------------------------------------------------
MECHANICAL_EXTRACT_JS = r'''const GENERIC = new Set([
  'AI', 'ChatGPT', 'GPT', 'LLM', 'MCP', 'API', 'RSS', 'HTML', 'CSS', 'SEO', 'UI', 'UX',
  '生成AI', 'AI副業', 'ノーコード', '効率化', '副業', 'Python', 'JavaScript', 'TypeScript',
  'Docker', 'GitHub', 'Google', 'Amazon', 'Microsoft', 'Apple', 'Mac', 'Windows', 'Linux',
  'note', 'Qiita', 'Brain', 'Tips', 'Twitter', 'Discord', 'Slack', 'Gemini', 'Claude',
]);

function nodeItems(name) {
  try { return $(name).all() || []; } catch { return []; }
}

function getHtmlBody(nodeName) {
  const items = nodeItems(nodeName);
  if (!items.length) return '';
  const j = items[0].json;
  return j.data || j.body || '';
}

function parseTipsHtml(html) {
  const items = [];
  const alts = [...html.matchAll(/alt="([^"]{10,120})"/g)].map((m) => m[1]);
  const links = [...html.matchAll(/href="(https:\/\/tips\.jp\/u\/[^"]+\/a\/[^"]+)"/g)].map((m) => m[1]);
  for (let i = 0; i < links.length && items.length < 15; i++) {
    items.push(alts[i] || links[i].split('/').pop());
  }
  return items;
}

function parseBrainHtml(html) {
  const links = [...html.matchAll(/href="(\/u\/[^"]+\/a\/[^"]+)"/g)].map((m) => m[1].split('/').pop());
  return links.slice(0, 15);
}

function addToken(map, token, source) {
  const name = token.trim();
  if (!name || name.length < 2 || name.length > 24) return;
  if (GENERIC.has(name) || GENERIC.has(name.toLowerCase())) return;
  if (/^\d+$/.test(name)) return;
  const key = name.toLowerCase();
  const cur = map.get(key) || { name, score: 0, sources: new Set(), samples: [] };
  cur.score += 1;
  cur.sources.add(source);
  if (cur.samples.length < 2) cur.samples.push(name);
  map.set(key, cur);
}

function extractFromText(text, source, map) {
  if (!text) return;
  for (const m of text.matchAll(/\b([A-Za-z][A-Za-z0-9_-]{1,28})\.(dev|ai|app|io)\b/g)) {
    addToken(map, m[1], source);
  }
  for (const m of text.matchAll(/\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b/g)) {
    addToken(map, m[1], source);
  }
  for (const m of text.matchAll(/\b([A-Za-z][A-Za-z0-9]{2,20})\b/g)) {
    addToken(map, m[1], source);
  }
}

function readPreviousWatchlist() {
  const items = nodeItems('Read Previous Watchlist');
  if (!items.length) return null;
  const item = items[0];
  let content = '';
  if (item.binary?.data?.data) {
    content = Buffer.from(item.binary.data.data, 'base64').toString('utf8');
  } else if (typeof item.json?.data === 'string') {
    content = item.json.data;
  }
  if (!content) return null;
  try { return JSON.parse(content); } catch { return null; }
}

const map = new Map();

const noteItems = [
  ...nodeItems('RSS Read (note-AI副業)'),
  ...nodeItems('RSS Read (note-AIツール)'),
];
for (const item of noteItems) {
  extractFromText(item.json.title || '', 'note', map);
}

const qiitaItems = nodeItems('HTTP Request (Qiita)');
for (const item of qiitaItems) {
  extractFromText(item.json.title || '', 'qiita', map);
  for (const tag of item.json.tags || []) {
    addToken(map, tag.name, 'qiita-tag');
  }
}

const brainHtml = getHtmlBody('HTTP Request (Brain)');
for (const t of parseBrainHtml(brainHtml)) extractFromText(t, 'brain', map);

const tipsHtml = getHtmlBody('HTTP Request (Tips)');
for (const t of parseTipsHtml(tipsHtml)) extractFromText(t, 'tips', map);

const mechanicalTop = [...map.values()]
  .map((v) => ({
    name: v.samples[0] || v.name,
    score: v.score,
    sources: [...v.sources],
  }))
  .sort((a, b) => b.score - a.score || b.sources.length - a.sources.length)
  .slice(0, 40);

let summary = '=== 【週次: 機械抽出候補（7日分タイトル・タグから）】 ===\n';
if (mechanicalTop.length === 0) {
  summary += '（候補なし）\n';
} else {
  mechanicalTop.forEach((r, i) => {
    summary += `${i + 1}. ${r.name} | score:${r.score} | sources:${r.sources.join('+')}\n`;
  });
}

summary += '\n=== 【note新着（抜粋）】 ===\n';
for (const item of noteItems.slice(0, 20)) {
  summary += `- ${item.json.title}\n`;
}

summary += '\n=== 【Qiita記事（抜粋）】 ===\n';
for (const item of qiitaItems.slice(0, 15)) {
  const tags = (item.json.tags || []).map((t) => t.name).join(', ');
  summary += `- ${item.json.title} | ${tags}\n`;
}

const prev = readPreviousWatchlist();
summary += '\n=== 【前週 watchlist.json】 ===\n';
summary += JSON.stringify(prev || { active: [], emerging: [], retire: [] }, null, 2);

return [{
  json: {
    textData: summary,
    mechanicalTop,
    previousWatchlist: prev,
  },
}];'''

DAILY_COMBINE_JS = r'''// 日次: 生データ + 参考（watchlist / x-trends）。候補選定は LLM のみ。
function nodeItems(name) {
  try { return $(name).all() || []; } catch { return []; }
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

function parseTrends(raw) {
  const parsed = JSON.parse(raw);
  if (Array.isArray(parsed.data?.trends)) return parsed.data.trends;
  if (Array.isArray(parsed.trends)) return parsed.trends;
  return [];
}

function readWatchlist() {
  const items = nodeItems('Read Watchlist');
  if (!items.length) return null;
  const item = items[0];
  let content = '';
  if (item.binary?.data?.data) {
    content = Buffer.from(item.binary.data.data, 'base64').toString('utf8');
  } else if (typeof item.json?.data === 'string') {
    content = item.json.data;
  }
  if (!content) return null;
  try { return JSON.parse(content); } catch { return null; }
}

let combinedText = '=== 【超短期トレンド分析用マルチソースデータ】 ===\n';
combinedText += '※ Codeは生データと参考値のみ提供。候補選定はLLMがルーブリックで実施。\n';
combinedText += '※ 本命= note/Brain/Tips/Qiita 生テキスト。watchlist・x-trends は参考のみ。\n\n';

combinedText += '=== 【本命データ — 候補選定の主根拠】 ===\n\n';

try {
  const noteItems = [
    ...nodeItems('RSS Read (note-AI副業)'),
    ...nodeItems('RSS Read (note-AIツール)'),
  ];
  if (noteItems.length > 0) {
    combinedText += '■ [note新着記事（タイトルのみ）] ---------\n';
    for (const item of noteItems.slice(0, 15)) {
      combinedText += `- ${item.json.title} | ${item.json.link}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ noteデータ取得エラー: ${e.message}\n\n`;
}

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

try {
  const qiitaItems = nodeItems('HTTP Request (Qiita)');
  if (qiitaItems.length > 0) {
    combinedText += '■ [Qiita 技術記事] ---------\n';
    for (const item of qiitaItems.slice(0, 15)) {
      const tags = (item.json.tags || []).map((t) => t.name).join(', ');
      combinedText += `- ${item.json.title} | LG:${item.json.likes_count || 0} | ${tags} | ${item.json.url}\n`;
    }
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ Qiitaデータエラー: ${e.message}\n\n`;
}

combinedText += '=== 【参考データ — 週次ウォッチリスト（非本命）】 ===\n';
combinedText += '※ 月曜更新。候補の直接根拠にしない。既知ツールの文脈確認用。\n\n';
try {
  const wl = readWatchlist();
  if (!wl) {
    combinedText += '（watchlist.json 未生成 — 週次 Watchlist Generator を実行してください）\n\n';
  } else {
    combinedText += `■ 更新: ${wl.updatedAt || '不明'}\n`;
    combinedText += `■ active: ${(wl.active || []).join(', ') || '—'}\n`;
    combinedText += `■ emerging: ${(wl.emerging || []).join(', ') || '—'}\n`;
    combinedText += `■ retire: ${(wl.retire || []).join(', ') || '—'}\n`;
    if (wl.rationale) combinedText += `■ rationale: ${wl.rationale}\n`;
    combinedText += '\n';
  }
} catch (e) {
  combinedText += `※ watchlist 読込エラー: ${e.message}\n\n`;
}

combinedText += '=== 【参考データ — X Explore 全体トレンド（非限定）】 ===\n';
combinedText += '※ 日本全体。スポーツ・芸能等含む。候補の直接根拠にしない。\n\n';
try {
  const xJson = nodeItems('Normalize X Trends')[0]?.json || {};
  let xOutput = xJson.stdout;
  if (!xOutput && xJson.error) {
    combinedText += `※ x-trends エラー: ${String(xJson.error).slice(0, 300)}\n\n`;
  }
  if (!xOutput) xOutput = nodeItems('Normalize Mock X')[0]?.json?.stdout;
  if (xOutput) {
    const trends = parseTrends(xOutput);
    combinedText += '■ [X (Twitter) トレンド一覧（参考）] ---------\n';
    const sorted = [...trends].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
    for (const t of sorted.slice(0, 30)) {
      const vol = t.tweetVolume != null ? t.tweetVolume : '—';
      combinedText += `- #${t.rank ?? '?'} ${t.name} | Vol:${vol} | ${t.description || t.category || ''}\n`;
    }
    combinedText += '\n';
  } else {
    combinedText += '（X参考データなし）\n\n';
  }
} catch (e) {
  combinedText += `※ X参考データのパースエラー: ${e.message}\n\n`;
}

return [{ json: { textData: combinedText } }];'''

DAILY_LLM = """【役割】
直近3〜5日のマルチソース**生データ**を読み、**注目ツール候補リスト**と**全体分析**を出力するアナリスト。
固定監視リストは存在しない。**固有名詞の抽出・候補選定はすべて LLM が実施**する。

【データの読み方（厳守）】
- **「本命データ」** = note / Brain / Tips / Qiita の生タイトル・記事。**候補選定の唯一の主根拠**。
- **「週次ウォッチリスト（参考）」** = 週1更新の active/emerging/retire。**候補の直接根拠にしてはならない**。既知ツールの文脈確認のみ。
- **「X Explore 全体トレンド（参考）」** = カテゴリ非限定の宏观トレンド。**候補の直接根拠にしてはならない**。

【出力形式（厳守）】
1. candidates: 固有名詞ツール名の配列（優先度順）
2. overall_analysis: 全体所見を1つの文章で

【選定ルーブリック（candidates）】
1. **本命データ内で複数ソース（note + Qiita 等）に現れる固有名詞を最優先**
2. **定番（Claude Code, Cursor, ChatGPT）は最大1件**。ニッチ・新興を優先
3. **抽象語不可**: MCP, 生成AI, AI副業, ノーコード, 効率化 等
4. **本命データに根拠がある初出固有名詞**を積極採用。watchlist/X参考**のみ**のものは不可
5. 根拠弱ければ2〜3件でよい（無理に10件埋めない）

【overall_analysis】
- note/Brain/Tips/Qiita のシグナル（主）
- watchlist / X参考は補足1フレーズまで
- リード獲得の打ち手1〜2個

【文字数】overall_analysis 最大800文字。candidates は名前のみ。"""

WEEKLY_LLM = """【役割】
7日分の生データと機械抽出候補から、**来週の参考ウォッチリスト**を更新する。
これは日次朝刊の「参考枠」用であり、固定監視リストではない。

【入力】
- 機械抽出候補（score / sources 付き）
- note/Qiita 抜粋
- 前週 watchlist.json

【出力（厳守）】
- active: 今週も注目継続（2ソース以上 or 高score）
- emerging: 新規・要観察（1ソース・初出）
- retire: 前週 active だったが今週データに見当たらないもの
- rationale: 更新理由を1文

【ルール】
- 抽象語（生成AI, ChatGPT, MCP 等）は含めない
- 固有名詞ツール・サービス名のみ（1〜4語）
- active は最大15件、emerging は最大10件
- 迷ったら emerging に回す（日次LLMが本命データで最終判断）"""

WEEKLY_FORMAT_JS = r'''const output = $json.output || $json;
const mechanicalTop = $('Code (Mechanical Extract)').first().json.mechanicalTop || [];
const prev = $('Code (Mechanical Extract)').first().json.previousWatchlist || {};

const active = (output.active || []).map(String).filter(Boolean);
const emerging = (output.emerging || []).map(String).filter(Boolean);
let retire = (output.retire || []).map(String).filter(Boolean);

const prevActive = new Set(prev.active || []);
const seen = new Set([...active, ...emerging].map((s) => s.toLowerCase()));
for (const name of prevActive) {
  if (!seen.has(name.toLowerCase())) retire.push(name);
}
retire = [...new Set(retire)];

const doc = {
  updatedAt: new Date().toISOString(),
  version: 1,
  active: active.slice(0, 15),
  emerging: emerging.slice(0, 10),
  retire: retire.slice(0, 20),
  rationale: String(output.rationale || '').slice(0, 500),
  mechanicalTop: mechanicalTop.slice(0, 20),
};

const content = JSON.stringify(doc, null, 2);
return [{
  json: { watchlist: doc },
  binary: {
    data: {
      data: Buffer.from(content, 'utf8').toString('base64'),
      mimeType: 'application/json',
      fileName: 'watchlist.json',
    },
  },
}];'''

WEEKLY_SCHEMA = json.dumps(
    {
        "active": ["OpenClaw", "Dify", "n8n"],
        "emerging": ["NewTool"],
        "retire": ["Devin"],
        "rationale": "OpenClaw/Difyがnote+Qiitaで継続。Devinは7日間未出現。",
    },
    ensure_ascii=False,
    indent=2,
)


def patch_daily(wf: dict) -> None:
    nodes = wf["nodes"]
    connections = wf["connections"]

    # Add or update Read Watchlist
    read_wl = next((n for n in nodes if n["name"] == "Read Watchlist"), None)
    if not read_wl:
        read_wl = {
            "parameters": {"fileSelector": WATCHLIST_CONTAINER_PATH, "options": {}},
            "id": str(uuid.uuid4()),
            "name": "Read Watchlist",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [0, 1100],
            "continueOnFail": True,
        }
        nodes.append(read_wl)

    sched = connections.get("Schedule Trigger", {}).get("main", [[]])[0]
    if not any(c.get("node") == "Read Watchlist" for c in sched):
        sched.append({"node": "Read Watchlist", "type": "main", "index": 0})

    for node in nodes:
        if node["name"] == "Code (Combine Sources)":
            node["parameters"]["jsCode"] = DAILY_COMBINE_JS
        if node["name"] == "Basic LLM Chain":
            node["parameters"]["messages"]["messageValues"][0]["message"] = DAILY_LLM


def build_weekly() -> list:
    gemini_cred = {"googlePalmApi": {"id": "tcH7fCTdXqQaa31p", "name": "Google Gemini(PaLM) Api account"}}

    nodes = [
        {
            "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * 1"}]}},
            "id": str(uuid.uuid4()),
            "name": "Schedule Trigger",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-448, 400],
        },
        {
            "parameters": {"url": "https://note.com/hashtag/ai%E5%89%AF%E6%A5%AD/rss", "options": {}},
            "id": str(uuid.uuid4()),
            "name": "RSS Read (note-AI副業)",
            "type": "n8n-nodes-base.rssFeedRead",
            "typeVersion": 1.1,
            "position": [0, 200],
            "continueOnFail": True,
        },
        {
            "parameters": {"url": "https://note.com/hashtag/ai%E3%83%84%E3%83%BC%E3%83%AB/rss", "options": {}},
            "id": str(uuid.uuid4()),
            "name": "RSS Read (note-AIツール)",
            "type": "n8n-nodes-base.rssFeedRead",
            "typeVersion": 1.1,
            "position": [0, 360],
            "continueOnFail": True,
        },
        {
            "parameters": {
                "url": "https://brain-market.com/search?keyword=AI",
                "options": {"response": {"response": {"responseFormat": "text"}}},
            },
            "id": str(uuid.uuid4()),
            "name": "HTTP Request (Brain)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [0, 520],
            "continueOnFail": True,
        },
        {
            "parameters": {
                "url": "https://tips.jp/search?q=AI",
                "options": {"response": {"response": {"responseFormat": "text"}}},
            },
            "id": str(uuid.uuid4()),
            "name": "HTTP Request (Tips)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [0, 680],
            "continueOnFail": True,
        },
        {
            "parameters": {
                "url": "=https://qiita.com/api/v2/items?query=tag:n8n+OR+tag:Dify+OR+tag:Manus+OR+tag:Windsurf+OR+tag:OpenClaw+OR+tag:ComfyUI+OR+tag:AI+created:>={{ $today.minus({ days: 7 }).toISODate() }}&per_page=30",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [{"name": "Authorization", "value": "=Bearer {{ $env.QIITA_ACCESS_TOKEN }}"}]
                },
                "options": {},
            },
            "id": str(uuid.uuid4()),
            "name": "HTTP Request (Qiita)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [0, 840],
            "continueOnFail": True,
        },
        {
            "parameters": {"fileSelector": WATCHLIST_CONTAINER_PATH, "options": {}},
            "id": str(uuid.uuid4()),
            "name": "Read Previous Watchlist",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [0, 1000],
            "continueOnFail": True,
        },
        {
            "parameters": {"mode": "combine", "combineBy": "combineAll", "options": {}},
            "id": str(uuid.uuid4()),
            "name": "Merge All Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [280, 520],
        },
        {
            "parameters": {"jsCode": MECHANICAL_EXTRACT_JS},
            "id": str(uuid.uuid4()),
            "name": "Code (Mechanical Extract)",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [520, 520],
        },
        {
            "parameters": {
                "promptType": "define",
                "text": "={{ $json.textData }}",
                "hasOutputParser": True,
                "messages": {"messageValues": [{"message": WEEKLY_LLM}]},
            },
            "id": str(uuid.uuid4()),
            "name": "Basic LLM Chain",
            "type": "@n8n/n8n-nodes-langchain.chainLlm",
            "typeVersion": 1.6,
            "position": [760, 520],
        },
        {
            "parameters": {"modelName": "models/gemini-2.5-flash-lite", "options": {"temperature": 0.2}},
            "id": str(uuid.uuid4()),
            "name": "Google Gemini Chat Model",
            "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
            "typeVersion": 1,
            "position": [640, 720],
            "credentials": gemini_cred,
        },
        {
            "parameters": {"jsonSchemaExample": WEEKLY_SCHEMA},
            "id": str(uuid.uuid4()),
            "name": "Structured Output Parser",
            "type": "@n8n/n8n-nodes-langchain.outputParserStructured",
            "typeVersion": 1.2,
            "position": [880, 720],
        },
        {
            "parameters": {"jsCode": WEEKLY_FORMAT_JS},
            "id": str(uuid.uuid4()),
            "name": "Code (Format Watchlist)",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1000, 520],
        },
        {
            "parameters": {
                "operation": "write",
                "fileName": WATCHLIST_CONTAINER_PATH,
                "options": {},
            },
            "id": str(uuid.uuid4()),
            "name": "Write Watchlist",
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [1240, 520],
        },
    ]

    connections = {
        "Schedule Trigger": {
            "main": [[
                {"node": "RSS Read (note-AI副業)", "type": "main", "index": 0},
                {"node": "RSS Read (note-AIツール)", "type": "main", "index": 0},
                {"node": "HTTP Request (Brain)", "type": "main", "index": 0},
                {"node": "HTTP Request (Tips)", "type": "main", "index": 0},
                {"node": "HTTP Request (Qiita)", "type": "main", "index": 0},
                {"node": "Read Previous Watchlist", "type": "main", "index": 0},
            ]]
        },
        "RSS Read (note-AI副業)": {"main": [[{"node": "Merge All Sources", "type": "main", "index": 0}]]},
        "RSS Read (note-AIツール)": {"main": [[{"node": "Merge All Sources", "type": "main", "index": 1}]]},
        "HTTP Request (Brain)": {"main": [[{"node": "Merge All Sources", "type": "main", "index": 2}]]},
        "HTTP Request (Tips)": {"main": [[{"node": "Merge All Sources", "type": "main", "index": 3}]]},
        "HTTP Request (Qiita)": {"main": [[{"node": "Merge All Sources", "type": "main", "index": 4}]]},
        "Merge All Sources": {"main": [[{"node": "Code (Mechanical Extract)", "type": "main", "index": 0}]]},
        "Code (Mechanical Extract)": {"main": [[{"node": "Basic LLM Chain", "type": "main", "index": 0}]]},
        "Basic LLM Chain": {"main": [[{"node": "Code (Format Watchlist)", "type": "main", "index": 0}]]},
        "Code (Format Watchlist)": {"main": [[{"node": "Write Watchlist", "type": "main", "index": 0}]]},
        "Google Gemini Chat Model": {"ai_languageModel": [[{"node": "Basic LLM Chain", "type": "ai_languageModel", "index": 0}]]},
        "Structured Output Parser": {"ai_outputParser": [[{"node": "Basic LLM Chain", "type": "ai_outputParser", "index": 0}]]},
    }

    return [{
        "id": "wL7kG3mN9pQr2sTv",
        "name": "Watchlist Generator",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "active": False,
    }]


def main() -> None:
    with DAILY_PATH.open() as f:
        daily = json.load(f)
    patch_daily(daily[0])
    with DAILY_PATH.open("w") as f:
        json.dump(daily, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Updated", DAILY_PATH)

    weekly = build_weekly()
    with WEEKLY_PATH.open("w") as f:
        json.dump(weekly, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Created", WEEKLY_PATH)


if __name__ == "__main__":
    main()
