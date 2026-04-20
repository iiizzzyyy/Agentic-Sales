# SalesCoach AI

**AI-Powered Sales Coach & Assistant for Slack**

A Slack-native sales intelligence platform powered by two AI agents that deliver roleplay coaching, real-time deal support, and manager analytics — all grounded in your HubSpot CRM data.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Overview

SalesCoach AI combines **AI coaching** with **CRM intelligence** to help sales teams:

- **Practice** realistic roleplay scenarios with AI buyers
- **Research** companies instantly with CRM + web data synthesis
- **Close** deals with AI-drafted emails and risk assessments
- **Improve** skills with personalized feedback and gap analysis
- **Manage** team performance with dashboards and analytics

**32 slash commands** | **2 AI agents** | **Real CRM integration** | **SQLite analytics**

---

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/iiizzzyyy/Agentic-Sales.git
cd Agentic-Sales
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Start Ollama (local LLM)
ollama serve
ollama pull qwen3.5:397b-cloud

# 3. Configure environment
cp .env.example .env
# Edit .env with your Slack tokens and API keys

# 4. Run the app
python app.py
```

---

## Core Features

### AI Sales Coach
Roleplay against AI buyers in realistic scenarios. Get scored feedback based on your sales methodology (MEDDIC, SPIN, Challenger, BANT).

```
/coach roleplay negotiation with CFO pushing for 20% discount
```

### AI Sales Assistant
Research companies, draft emails, analyze deals, and manage pipeline — all from Slack.

```
/research Acme Corp
/deal Enterprise Migration Deal
/pipeline
```

### Manager Intelligence
Team dashboards, skill gap analysis, scenario library, and cohort-based training programs.

```
/team-dashboard
/skill-gaps
/create-scenario
/launch-training
```

---

## All 32 Commands

### Core Commands (5)
| Command | Description |
|---------|-------------|
| `/research [company]` | Company intelligence brief from CRM + web |
| `/deal [deal name]` | Deep dive on specific deal with risk assessment |
| `/coach [scenario]` | Roleplay practice with AI buyer |
| `/draft-email [deal]` | Context-aware email draft with attachments |
| `/pipeline` | Pipeline health digest with AI recommendations |

### Expansion Commands (14)
| Command | Description |
|---------|-------------|
| `/objection [type]` | Handle specific objections with playbook guidance |
| `/ask [question]` | Free-form Q&A about deals, pipeline, or performance |
| `/followup [deal]` | Generate follow-up actions from recent activity |
| `/competitor [name]` | Competitive analysis with positioning strategy |
| `/battlecard [competitor]` | Instant battle card (sub-second response) |
| `/alerts` | Proactive deal alerts (stale, overdue, at-risk) |
| `/forecast` | AI-powered forecast: committed, best case, stretch |
| `/win-loss` | Analyze won/lost patterns and competitor correlation |
| `/persona [contact]` | Detailed buyer persona with engagement strategy |
| `/handoff [deal]` | Comprehensive deal handoff brief |
| `/email-sequence [deal]` | 4-email nurture sequence with timing |
| `/coach-live` | Real-time coaching during live calls |
| `/settings` | Configure methodology, language, privacy |
| `/demo-flow` | Guided walkthrough for new users |

### Wave 1: Foundation (2)
| Command | Description |
|---------|-------------|
| `/training-history` | View coaching sessions with scores and trends |
| `/log [note]` | Quick-log notes to HubSpot CRM |

### Wave 2: Coaching Intelligence (1)
| Command | Description |
|---------|-------------|
| `/skill-gaps` | Color-coded skill analysis with "Practice This" buttons |

### Wave 3: Manager Tools (4)
| Command | Description |
|---------|-------------|
| `/create-scenario` | Build reusable roleplay scenarios |
| `/scenarios` | Browse scenario library |
| `/assign [rep] [scenario]` | Assign training with due dates |
| `/team-dashboard` | Manager view: leaderboard, heatmaps, assignments |

### Wave 4: Training Programs (4)
| Command | Description |
|---------|-------------|
| `/create-cohort` | Multi-week training programs |
| `/cohort-progress` | Track cohort completion status |
| `/onboard` | 4-week new hire onboarding program |
| `/launch-training` | AI-generated product launch training |

### Wave 5: Pam Parity (2)
| Command | Description |
|---------|-------------|
| `/my-day` | Calendar with meeting actions (Prep, Research, Reschedule) |
| `/market-insights` | Strategic trends: objections, competitors, engagement |

---

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

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.11+ |
| **Agent Framework** | LangGraph with langchain-mcp-adapters |
| **LLM** | Ollama (qwen3.5:397b-cloud), OpenRouter fallback |
| **Slack** | Bolt SDK with Socket Mode |
| **Vector DB** | ChromaDB + HuggingFace embeddings |
| **MCP Servers** | HubSpot, Gmail, BigQuery |
| **Analytics** | SQLite (11 tables, WAL mode) |

### Key Directories

```
.
├── graphs/          # LangGraph orchestration (triage, coach, assistant, PM, DAG)
├── tools/           # Tool implementations (CRM, RAG, web search, executor)
├── formatters/      # Slack Block Kit (32 files)
├── prompts/         # System prompts for all agents
├── data/            # SQLite DB, mock CRM, playbooks, documents
├── scripts/         # Index playbooks, seed demo data
└── app.py           # Main entry point (~7500 lines)
```

---

## Demo Story

The platform tells a cohesive story through three acts:

### Act 1: Sarah's Morning (Rep Workflow)
Sarah has a $180K negotiation at 2pm. She:
1. Runs `/my-day` to see her calendar
2. Clicks **Prep** on the DataFlow meeting → auto-runs `/research`
3. Reviews the deal with `/deal Enterprise Migration`
4. Logs a quick note with `/log "Customer concerned about exit clause"`
5. Checks pipeline health with `/pipeline`
6. Drafts follow-up email with `/draft-email`

### Act 2: The Coaching Loop
Sarah practices for her negotiation:
1. `/coach roleplay pricing negotiation with CRO`
2. 6-turn roleplay in a Slack thread
3. Gets scored debrief with MEDDIC dimensions
4. Reviews progress with `/training-history`
5. Targets weak areas with `/skill-gaps` → **Practice This**

### Act 3: Marcus's View (Manager)
Marcus builds team capability:
1. `/team-dashboard` sees Sarah improving, Jake struggling
2. `/create-scenario` builds pricing objection training
3. `/assign Jake scenario` with due date
4. `/launch-training` generates 5 scenarios from product brief
5. `/market-insights` spots pricing objection spike

---

## Environment Variables

**Required (Slack):**
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

**Required (LLM):**
```bash
# Primary: Local Ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3.5:397b-cloud

# Fallback: OpenRouter (if Ollama unavailable)
OPENROUTER_API_KEY=sk-or-v1-your-key
```

**Required (Integrations):**
```bash
HUBSPOT_ACCESS_TOKEN=pat-your-token
TAVILY_API_KEY=tvly-your-key
```

**Optional:**
```bash
# Google Cloud (BigQuery + Gmail)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# Apollo enrichment
ENABLE_APOLLO_ENRICHMENT=true
APOLLO_API_KEY=your-key
```

See `.env.example` for full list.

---

## Data & Integrations

### CRM Integration
- **Reads:** HubSpot MCP server (companies, contacts, deals, activities)
- **Writes:** HubSpot Python SDK (notes, deal updates)
- **Mock Mode:** SQLite + JSON for offline development

### RAG Knowledge Base
- 2,104 chunks from 22 sales playbooks
- ChromaDB with local HuggingFace embeddings
- Methodology definitions (MEDDIC, SPIN, Challenger, BANT)

### Analytics Database
SQLite stores:
- Training sessions with dimensional scores
- Engagement events (command usage, button clicks)
- CRM audit log (all write-backs)
- User settings, scenarios, assignments, cohorts

---

## Scripts

```bash
# Index playbooks into ChromaDB
python scripts/index_playbooks.py

# Seed demo data (training history, skill scores)
python scripts/seed_demo_data.py

# Sync data to HubSpot (production)
python scripts/sync_data_to_hubspot.py
```

---

## Security

- `.env` file excluded via `.gitignore`
- Pre-commit hook blocks secret commits
- No credentials in source code
- Placeholder values in `.env.example`

---

## Demo Resources

- **Demo Script:** `SalesCoach-AI-Demo-Script.docx` — 25-30 min interactive walkthrough
- **Demo Guide:** `SalesCoach-AI-Demo-Guide.docx` — All 32 commands with examples
- **Architecture:** `CLAUDE-CODE-BRIEFING.md` — Technical deep dive

---

## License

MIT
