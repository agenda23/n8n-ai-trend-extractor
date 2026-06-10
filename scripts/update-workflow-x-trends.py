#!/usr/bin/env python3
"""Update workflow to use x-trends /api/v1/trends (raw) + workflow extraction."""

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "workflows" / "ai-trend-extractor.json"

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

function parseTrends(raw) {
  const parsed = JSON.parse(raw);
  if (Array.isArray(parsed.data?.trends)) return parsed.data.trends;
  if (Array.isArray(parsed.trends)) return parsed.trends;
  if (Array.isArray(parsed.data)) return parsed.data;
  return [];
}

function trendText(t) {
  return [t.name, ...(t.hashtags || []), t.description || ''].filter(Boolean).join(' ');
}

function extractBuzzFromTrends(trends) {
  const signals = new Map();

  for (const t of trends) {
    const text = trendText(t);
    if (!text) continue;
    const vol = t.tweetVolume ?? 0;

    for (const { name, re } of TOOL_PATTERNS) {
      if (!re.test(text)) continue;
      const cur = signals.get(name) || {
        mentions: 0,
        totalVolume: 0,
        maxVolume: 0,
        topSnippet: '',
      };
      cur.mentions += 1;
      cur.totalVolume += vol;
      if (vol >= cur.maxVolume) {
        cur.maxVolume = vol;
        cur.topSnippet = (t.name || '').slice(0, 100);
      }
      signals.set(name, cur);
    }
  }

  return [...signals.entries()]
    .map(([name, s]) => ({
      name,
      ...s,
      rankScore: s.maxVolume + s.mentions * 1000,
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
combinedText += '※ 上記以外の初出固有名詞は「Xトレンド」から積極探索すること。\n\n';
let buzzCandidates = [];
let secondaryCandidates = [];
let noteToolsAgg = [];
let qiitaToolsAgg = [];

// --- 1. X (Twitter) トレンド ---
try {
  const xJson = nodeItems('Normalize X Trends')[0]?.json || {};
  let xOutput = xJson.stdout;
  if (!xOutput && xJson.error) {
    combinedText += `■ [X (Twitter)] ---------\n※ x-trends エラー: ${String(xJson.error).slice(0, 300)}\n\n`;
  }
  if (!xOutput) xOutput = nodeItems('Normalize Mock X')[0]?.json?.stdout;
  if (xOutput) {
    const trends = parseTrends(xOutput);
    buzzCandidates = extractBuzzFromTrends(trends);

    combinedText += '■ [Xツール言及シグナル（トレンドから）] ---------\n';
    if (buzzCandidates.length === 0) {
      combinedText += '（Xトレンド上のツール言及なし。note/Qiita/トレンド名から候補を抽出すること）\n';
    } else {
      buzzCandidates.slice(0, 15).forEach((s, i) => {
        combinedText += `${i + 1}. ${s.name} | 言及${s.mentions} | 最高Vol${s.maxVolume} | 「${s.topSnippet}」\n`;
      });
    }
    combinedText += '\n';

    combinedText += '■ [X (Twitter) トレンド一覧] ---------\n';
    const sorted = [...trends].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
    for (const t of sorted.slice(0, 30)) {
      const vol = t.tweetVolume != null ? t.tweetVolume : '—';
      const desc = t.description || t.category || '';
      combinedText += `- #${t.rank ?? '?'} ${t.name} | Vol:${vol} | ${desc}\n`;
    }
    combinedText += '\n';
  } else {
    combinedText += '■ [X (Twitter)] ---------\n（Xデータなし: x-trends エラーまたはトレンド0件）\n\n';
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

NORMALIZE_X_TRENDS_JS = r'''const item = $input.first();
if (!item) {
  return [{ json: { stdout: JSON.stringify({ ok: false, data: { trends: [] } }), error: 'no response from x-trends' } }];
}

const response = item.json || {};
if (item.error) {
  const msg = String(item.error.message || item.error);
  return [{ json: { stdout: JSON.stringify({ ok: false, data: { trends: [] } }), error: msg } }];
}

let stdout = '';
let error;

if (response.ok && Array.isArray(response.data?.trends)) {
  stdout = JSON.stringify({
    ok: true,
    data: { trends: response.data.trends },
    meta: response.meta || {},
  });
} else {
  error = response.error?.message || 'x-trends trends fetch failed';
  stdout = JSON.stringify({ ok: false, data: { trends: [] }, error: response.error || error });
}

return [{ json: { stdout, error } }];'''

LLM_RUBRIC_SNIPPET = (
    "4. **TOOL_PATTERNS外の初出固有名詞**が「Xトレンド」にあれば積極採用（監視リスト外の新興ツールを見逃さない）"
)


def main():
    with WORKFLOW_PATH.open() as f:
        data = json.load(f)
    wf = data[0]
    nodes = wf["nodes"]
    connections = wf["connections"]

    # Remove old X Search nodes
    nodes = [n for n in nodes if n["name"] not in ("HTTP Request (X Search)", "Normalize X Search")]

    http_node = {
        "parameters": {
            "url": "={{ ($env.X_TRENDS_BASE_URL || 'http://x-trends:3920') + '/api/v1/trends' }}",
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "preset", "value": "japan"},
                    {"name": "count", "value": "50"},
                ]
            },
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "X-API-Key", "value": "={{ $env.X_TRENDS_API_KEY || '' }}"},
                ]
            },
            "options": {},
        },
        "id": str(uuid.uuid4()),
        "name": "HTTP Request (X Trends)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [0, 208],
        "continueOnFail": True,
    }

    normalize_node = {
        "parameters": {"jsCode": NORMALIZE_X_TRENDS_JS},
        "id": str(uuid.uuid4()),
        "name": "Normalize X Trends",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [224, 208],
    }

    nodes.append(http_node)
    nodes.append(normalize_node)

    for node in nodes:
        if node["name"] == "Read Mock X":
            node["parameters"]["fileSelector"] = "/home/node/.n8n-files/mock/x-trends-sample.json"
        if node["name"] == "Code (Combine Sources)":
            node["parameters"]["jsCode"] = COMBINE_JS
        if node["name"] == "Basic LLM Chain":
            msg = node["parameters"]["messages"]["messageValues"][0]["message"]
            msg = msg.replace("「X生投稿」", "「Xトレンド」")
            msg = msg.replace(
                "4. **TOOL_PATTERNS外の初出固有名詞**が「X生投稿」にあれば積極採用",
                LLM_RUBRIC_SNIPPET,
            )
            node["parameters"]["messages"]["messageValues"][0]["message"] = msg
        if node["name"] == "Code (Format Notification)":
            js = node["parameters"]["jsCode"]
            js = js.replace("twitter-cli Cookie", "x-trends 認証")
            node["parameters"]["jsCode"] = js

    wf["nodes"] = nodes

    connections["IF Mock X"]["main"][1] = [{"node": "HTTP Request (X Trends)", "type": "main", "index": 0}]
    connections.pop("HTTP Request (X Search)", None)
    connections.pop("Normalize X Search", None)
    connections["HTTP Request (X Trends)"] = {
        "main": [[{"node": "Normalize X Trends", "type": "main", "index": 0}]]
    }
    connections["Normalize X Trends"] = {
        "main": [[{"node": "Merge All Sources", "type": "main", "index": 0}]]
    }
    connections["RSS Read (note-AIツール)"] = {
        "main": [[{"node": "Merge All Sources", "type": "main", "index": 2}]]
    }
    connections["HTTP Request (Brain)"] = {
        "main": [[{"node": "Merge All Sources", "type": "main", "index": 3}]]
    }
    connections["HTTP Request (Tips)"] = {
        "main": [[{"node": "Merge All Sources", "type": "main", "index": 4}]]
    }
    connections["HTTP Request (Qiita)"] = {
        "main": [[{"node": "Merge All Sources", "type": "main", "index": 5}]]
    }

    with WORKFLOW_PATH.open("w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Updated", WORKFLOW_PATH)


if __name__ == "__main__":
    main()
