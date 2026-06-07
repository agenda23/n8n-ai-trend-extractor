# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Docker-based n8n automation system** that collects AI trend data from 5 sources every morning at 07:00 JST, analyzes it with Gemini 2.5 Flash for lead generation insights, and delivers a morning briefing to Slack/Discord.

Most artifacts in this repo are **not yet built** — the `specs/` directory contains the design documents that define what to build.

## Target Architecture (to be built)

```
n8n-ai-trend-extractor/
├── docker/
│   ├── Dockerfile          # n8nio/n8n base + twitter-cli global install
│   └── entrypoint.sh       # (optional) pre-start setup
├── docker-compose.yml      # n8n service, ports, volumes, env vars
├── .env.example            # Placeholder for all required secrets
├── workflows/
│   └── ai-trend-extractor.json   # Exported n8n workflow (version-controlled)
├── mock/
│   └── x-tweets-sample.json      # Fake X data for E2E testing without live API
├── scripts/
│   ├── setup-twitter-cli.sh
│   └── verify-sources.sh
└── specs/                  # Design documents (source of truth for intent)
```

## Runtime Commands

```bash
# Start n8n
docker compose up -d

# View logs
docker compose logs -f n8n

# Stop
docker compose down

# Rebuild after Dockerfile changes
docker compose build --no-cache && docker compose up -d

# Access n8n GUI
open http://localhost:5678

# Verify twitter-cli inside container
docker compose exec n8n twitter search "Dify" --json

# Test Qiita API (host)
curl -H "Authorization: Bearer $QIITA_ACCESS_TOKEN" \
  "https://qiita.com/api/v2/items?query=tag:AI&per_page=5"
```

## Key Design Decisions

### Docker vs npm
The specs describe both npm (`n8n start`) and Docker approaches. **Docker is canonical** per `specs/構築タスク一覧_Docker版.md`. Always use Docker Compose.

### twitter-cli authentication
`@public-clis/twitter-cli` uses browser Cookie auth (`auth_token` + `ct0` from DevTools → Application → Cookies → x.com). Cookie sessions expire — the system must alert via Slack when `Execute Command` fails. Cookie files live at `~/.config/twitter-cli` on the host and are shared into the container via volume mount (`./data/twitter-cli:/home/node/.config/twitter-cli`).

### n8n Execute Command requirements
Two env vars are mandatory for shell execution in n8n nodes:
```
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

### Unified JSON schema
The two spec files define slightly different output schemas. **Use this unified version** (from `specs/構築タスク一覧_Docker版.md` §3.3):

| Field | Type | Description |
|---|---|---|
| `keyword` | string | Trending tool/method |
| `category` | string | Classification |
| `market_evidence` | string | How it shows up in note/Brain/Tips/X |
| `tech_status_pain` | string | Implementation blockers from Qiita/X |
| `lead_hook` | string | Specific free-giveaway campaign idea |
| `score` | enum | `"高（即時実践推奨）"` / `"中（検証フェーズ）"` / `"低（様子見）"` |

This schema must match the Slack notification template's `{{this.*}}` references.

### Mock mode for development
Set `USE_MOCK_X=true` to replace the `Execute Command` node with a `Read Binary File` that loads `mock/x-tweets-sample.json`. This avoids burning X API quota and risking account flags during workflow development.

## n8n Workflow Structure

The single workflow `ai-trend-extractor` runs:
1. **Schedule Trigger** — 07:00 JST daily
2. **5 parallel collection branches**:
   - `Execute Command` → `twitter search '... min_faves:15' --since <3 days ago> --json`
   - `RSS Read` (×2) → note hashtag feeds
   - `HTTP Request` → Brain API (`brain-market.com/api/v1/search?keyword=AI&sort=new`)
   - `HTTP Request` → Tips (`tips.jp/search?q=AI`)
   - `HTTP Request` → Qiita API (`qiita.com/api/v2/items?query=tag:AI+created:>=<date>`)
3. **Code node** (JS, "Run Once for All Items") — merges all 5 sources into `{ textData: string }`
4. **Basic LLM Chain** with `gemini-2.5-flash` (temperature 0.3) + Structured Output Parser
5. **HTTP Request or Slack node** → formatted morning briefing
6. **Error Trigger** sub-workflow → Cookie expiry alert to Slack

## Required Credentials

| Credential | n8n Credential Type | Required |
|---|---|---|
| Gemini API key | Google AI / HTTP Header Auth | Yes |
| Slack Webhook URL | n8n HTTP Request / Slack node | Yes |
| Qiita access token | HTTP Header Auth (`Authorization: Bearer`) | Optional |
| Discord Webhook URL | HTTP Request | Optional |
| Google Sheets / Notion | respective n8n integrations | Optional |

## Build Phases (from specs)

Refer to `specs/構築タスク一覧_Docker版.md` for the full task checklist. The critical path is:

**Phase 0** (project skeleton) → **Phase 1** (Docker n8n running) → **Phase 2** (API auth, especially twitter-cli in container at P2-3) → **Phase 3** (workflow nodes) → **Phase 4** (Slack output) → **Phase 5** (error handling + schedule activation)

Phase 6 (n8n MCP integration for AI-driven workflow editing) is optional and can run in parallel after Phase 1.

## MCP Integration (optional)

To control n8n from Claude/Cursor via MCP, add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "n8n-mcp-server": {
      "command": "npx",
      "args": ["-y", "@n8n/mcp-server"],
      "env": {
        "N8N_API_KEY": "n8n_api_...",
        "N8N_BASE_URL": "http://localhost:5678"
      }
    }
  }
}
```

## Known Risks

- **Brain/Tips responses may be HTML**, not JSON — the Code node parser may need cheerio-style parsing or a different endpoint
- **X Cookie expires** roughly monthly — the Error Trigger alert is essential for unattended operation
- **Gemini rate limits** — the Code node already caps each source (X: 50 tweets, note/Qiita: 15 items) to control token volume
