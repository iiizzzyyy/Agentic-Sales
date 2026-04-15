# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SalesCoach AI — A Slack bot with two AI agents for sales teams:
- **Coach Agent**: Roleplays, post-call feedback, meeting prep
- **Assistant Agent**: Research briefs, CRM updates, email drafts, pipeline digests

POC using production architecture (LangGraph + MCP). Data flows from HubSpot, web search (Tavily), and BigQuery. Actions go to Gmail and HubSpot.

## Tech Stack

- **Language**: Python 3.11+
- **Agent Framework**: LangGraph with langchain-mcp-adapters
- **LLM**: Ollama local inference (default: qwen3.5:397b-cloud), OpenRouter fallback
- **Slack**: Bolt SDK with Socket Mode
- **Vector DB**: ChromaDB with local HuggingFace embeddings (all-MiniLM-L6-v2)
- **MCP Servers**: HubSpot (@hubspot/mcp-server), Gmail (shinzo-labs/gmail-mcp), BigQuery
- **Orchestration**: Hive Mind architecture (Triage → PM Agent → DAG Executor)

## Running the App

```bash
# 1. Start Ollama server (if not running)
ollama serve

# 2. Pull the LLM model (one-time)
ollama pull qwen3.5:397b-cloud

# 3. Setup Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env  # Edit with your API keys

# 5. Run the app
python app.py
```

MCP servers (HubSpot, Gmail, BigQuery) start as subprocesses automatically. Tools are auto-discovered at startup and logged to console.

**Note:** If `OLLAMA_BASE_URL` is not set, the app falls back to OpenRouter (cloud).

## Commands & Testing

No formal test suite. Test manually in Slack:
- `/my-day` — Shows today's calendar with pipeline summary inline
- `/coach roleplay discovery call with VP Engineering`
- `/research Acme Corp`
- `/deal My Big Deal`
- `/pipeline`

Index playbooks into ChromaDB: `python scripts/index_playbooks.py`

Seed demo data: `python scripts/seed_demo_data.py`

## Architecture

```
Slack Message → app.py (Bolt) → Triage Graph
                                     ↓
              ┌──────────────────────┼──────────────────────┐
              ↓                      ↓                      ↓
         DIRECT                WORKFLOW                COMPLEX
    (DirectExecutor)    (Coach/Assistant)        (PM Agent → DAG Executor)
                                                 ↓
                                          Parallel batches
                                                 ↓
                                            Reviewer
                                                 ↓
                         formatters/*.py → Slack Block Kit
```

**Key directories:**
- `graphs/` — LangGraph orchestration (triage.py, coach_typed.py, assistant_typed.py, pm_agent.py, dag_executor.py, reviewer_agent.py, architect_agent.py)
- `tools/` — Tool implementations (mock_crm.py, rag.py, web_search.py, executor.py)
- `formatters/` — Slack Block Kit formatting (32 files for different features)
- `prompts/` — System prompts for triage, coach, assistant, PM, architect, reviewer
- `data/` — SQLite database, mock CRM JSON, playbooks, documents, DAG checkpoints

**Entry points:**
- `app.py` — Main Slack app, all command handlers (~7500 lines)
- `mcp_setup.py` — MCP server initialization
- `llm_factory.py` — LLM routing (OpenRouter or Ollama fallback)
- `db.py` — SQLite database operations

## Adding Features

1. Create graph node(s) in `graphs/`
2. Create tool wrapper in `tools/` if needed
3. Create formatter in `formatters/`
4. Add system prompt in `prompts/` if needed
5. Add command handler in `app.py`
6. Update router prompt to recognize the intent

## Environment Variables

**Required (Primary — Ollama):**
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- `OLLAMA_BASE_URL=http://localhost:11434/v1`
- `OLLAMA_MODEL=qwen3.5:397b-cloud`

**Required (Fallback — OpenRouter, if Ollama not available):**
- `OPENROUTER_API_KEY`, `OPENROUTER_DEFAULT_MODEL`

**Other Required:**
- `HUBSPOT_ACCESS_TOKEN`, `TAVILY_API_KEY`

**Optional:** Google Cloud credentials for BigQuery/Gmail, `ENABLE_APOLLO_ENRICHMENT`

See `.env.example` for full list.

## Database

SQLite at `data/salescoach.db`. Auto-initialized on startup via `init_db()` in db.py.

Key tables: `user_settings`, `training_sessions`, `scenarios`, `assignments`, `cohorts`

## Notes

- MCP tool integration is production-ready; zero throwaway code
- Formatters output Block Kit JSON for rich Slack messages
- Mock CRM data in `data/mock_crm/` for offline development
- Detailed architecture docs in `CLAUDE-CODE-BRIEFING.md`
