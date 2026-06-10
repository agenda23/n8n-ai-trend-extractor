#!/usr/bin/env python3
"""Patch Combine Sources + LLM prompt: x-trends as reference-only section."""

import json
from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "workflows" / "ai-trend-extractor.json"

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

function extractToolHintsFromTrends(trends) {
  const signals = new Map();
  for (const t of trends) {
    const text = trendText(t);
    if (!text) continue;
    const vol = t.tweetVolume ?? 0;
    for (const { name, re } of TOOL_PATTERNS) {
      if (!re.test(text)) continue;
      const cur = signals.get(name) || { mentions: 0, maxVolume: 0, topSnippet: '' };
      cur.mentions += 1;
      if (vol >= cur.maxVolume) {
        cur.maxVolume = vol;
        cur.topSnippet = (t.name || '').slice(0, 100);
      }
      signals.set(name, cur);
    }
  }
  return [...signals.entries()]
    .map(([name, s]) => ({ name, ...s }))
    .sort((a, b) => b.maxVolume - a.maxVolume || b.mentions - a.mentions);
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
combinedText += '※ 候補選定の主根拠は「本命データ」（note/Brain/Tips/Qiita）。\n';
combinedText += '※ x-trends は日本全体トレンドの参考値（スポーツ・芸能等含む）。候補の直接根拠にしない。\n\n';

let primaryCandidates = [];
let noteToolsAgg = [];
let qiitaToolsAgg = [];

// === 本命データ（候補選定の主根拠） ===
combinedText += '=== 【本命データ — 候補選定の主根拠】 ===\n\n';

// --- note ---
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

// --- Brain ---
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

// --- Tips ---
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

// --- Qiita ---
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

// マルチソース言及カウント（note/Qiita のみ — ルーブリック1用）
const noteMap = Object.fromEntries(noteToolsAgg);
const qiitaMap = Object.fromEntries(qiitaToolsAgg);
const allToolNames = new Set([
  ...noteToolsAgg.map(([n]) => n),
  ...qiitaToolsAgg.map(([n]) => n),
]);

primaryCandidates = [...allToolNames];

if (allToolNames.size > 0) {
  combinedText += '■ [マルチソース言及カウント（本命・選定参考）] ---------\n';
  const rows = [...allToolNames].map((name) => {
    const note = noteMap[name] || 0;
    const qiita = qiitaMap[name] || 0;
    const srcCount = [note > 0, qiita > 0].filter(Boolean).length;
    const srcLabel = [
      note > 0 ? 'note' : null,
      qiita > 0 ? 'Qiita' : null,
    ].filter(Boolean).join('+') || '—';
    return { name, note, qiita, srcCount, srcLabel };
  }).sort((a, b) => b.srcCount - a.srcCount || (b.note + b.qiita) - (a.note + a.qiita));

  for (const r of rows.slice(0, 20)) {
    combinedText += `- ${r.name}: note${r.note} / Qiita${r.qiita} | 裏付けソース:${r.srcCount} (${r.srcLabel})\n`;
  }
  combinedText += '\n';
} else {
  combinedText += '■ [マルチソース言及カウント] ---------\n（note/Qiita からツール言及なし）\n\n';
}

// === 参考データ（x-trends — カテゴリ非限定の全体トレンド） ===
combinedText += '=== 【参考データ — X Explore 全体トレンド（非限定）】 ===\n';
combinedText += '※ 日本全体のトレンド。AI/ツール以外（スポーツ・芸能等）を含む。\n';
combinedText += '※ 候補選定の主根拠にしない。overall_analysis の宏观文脈補足にのみ使用可。\n\n';

try {
  const xJson = nodeItems('Normalize X Trends')[0]?.json || {};
  let xOutput = xJson.stdout;
  if (!xOutput && xJson.error) {
    combinedText += `■ [X (Twitter) 参考トレンド] ---------\n※ x-trends エラー: ${String(xJson.error).slice(0, 300)}\n\n`;
  }
  if (!xOutput) xOutput = nodeItems('Normalize Mock X')[0]?.json?.stdout;

  if (xOutput) {
    const trends = parseTrends(xOutput);
    const xHints = extractToolHintsFromTrends(trends);

    if (xHints.length > 0) {
      combinedText += '■ [X参考: TOOL_PATTERNS一致（カテゴリ非限定・参考のみ）] ---------\n';
      xHints.slice(0, 10).forEach((s, i) => {
        combinedText += `${i + 1}. ${s.name} | 言及${s.mentions} | Vol${s.maxVolume} | 「${s.topSnippet}」\n`;
      });
      combinedText += '\n';
    }

    combinedText += '■ [X (Twitter) トレンド一覧（参考）] ---------\n';
    const sorted = [...trends].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
    if (sorted.length === 0) {
      combinedText += '（トレンド0件）\n';
    } else {
      for (const t of sorted.slice(0, 30)) {
        const vol = t.tweetVolume != null ? t.tweetVolume : '—';
        const desc = t.description || t.category || '';
        combinedText += `- #${t.rank ?? '?'} ${t.name} | Vol:${vol} | ${desc}\n`;
      }
    }
    combinedText += '\n';
  } else {
    combinedText += '■ [X (Twitter) 参考トレンド] ---------\n（Xデータなし）\n\n';
  }
} catch (e) {
  combinedText += `※ X参考データのパースエラー: ${e.message}\n\n`;
}

return [{
  json: {
    textData: combinedText,
    buzzCandidates: [...new Set(primaryCandidates)],
  },
}];'''

LLM_MESSAGE = """【役割】
直近3〜5日のマルチソースデータを読み、**注目ツール候補リスト**と**全体分析**の2つだけを出力するアナリスト。
候補ごとの個別分析は書かない。入力データの整形は済んでいる。**何を候補にするかはあなた（LLM）がルーブリックで判断すること。**

【データの読み方（厳守）】
- **「本命データ」** = note / Brain / Tips / Qiita。**候補選定の主根拠**。
- **「参考データ（X Explore 全体トレンド）」** = x-trends による日本全体トレンド。スポーツ・芸能・一般話題を含み、**AIツール候補の直接根拠にしてはならない**。
- X参考データは overall_analysis の宏观文脈（「今日のX全体の空気感」等）にのみ触れてよい。candidates には X参考のみの根拠で載せない。

【出力形式（厳守）】
1. candidates: 固有名詞ツール名の配列（優先度順）
2. overall_analysis: 全体所見を1つの文章で

【選定ルーブリック（candidates の判断基準・厳守）】
1. **複数ソース（note + Qiita、できれば Brain/Tips も）で裏付けがあるものを最優先**（「マルチソース言及カウント（本命）」の裏付けソース数が多い順）
2. **定番ツール（Claude Code, Cursor, ChatGPT）は全体で最大1件**。それ以外はニッチ・新興を優先
3. **抽象語は候補不可**: MCP, 生成AI, AI副業, ChatGPT, ノーコード, 効率化, AI画像生成 など
4. **TOOL_PATTERNS外の初出固有名詞**が「本命データ」にあれば積極採用。**X参考データのみ**に現れるものは候補にしない
5. **根拠が弱いものは出力しない**（2〜3件でも可。無理に10件埋めない）

【candidates の形式】
- 各要素は製品名・サービス名（1〜4語の固有名詞）のみ
- 良い例: Dify, Manus, n8n, OpenClaw, ComfyUI, Lovable, Windsurf
- 最大10件。ルーブリック5により根拠弱ければ2〜3件でよい

【overall_analysis に含める観点（全体で1文に統合）】
- note/Brain/Tipsの実売シグナル（主）
- Qiita等の実装トレンド・詰まりポイント（主）
- X参考トレンドから読み取れる宏观の空気感（補足・1フレーズ程度）
- リード獲得の打ち手（1〜2個）

【文字数制約（Discord 2000字制限）】
- overall_analysis: 最大800文字
- candidates: 候補ごとの説明は書かない（名前のみ）"""


def main():
    with WORKFLOW_PATH.open() as f:
        data = json.load(f)
    wf = data[0]

    for node in wf["nodes"]:
        if node["name"] == "Code (Combine Sources)":
            node["parameters"]["jsCode"] = COMBINE_JS
        if node["name"] == "Basic LLM Chain":
            node["parameters"]["messages"]["messageValues"][0]["message"] = LLM_MESSAGE

    with WORKFLOW_PATH.open("w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Patched", WORKFLOW_PATH)


if __name__ == "__main__":
    main()
