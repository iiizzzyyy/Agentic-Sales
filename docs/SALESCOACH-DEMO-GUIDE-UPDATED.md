# SalesCoach AI Demo Guide

**Version:** 2.0 (Hive Mind Architecture)  
**Last Updated:** 2026-04-08  
**LLM:** Ollama qwen3.5:397b-cloud (local inference)

---

## Executive Summary

SalesCoach AI is a Slack-based intelligent sales assistant powered by **Hive Mind multi-agent orchestration** and **local LLM inference**. It provides two primary capabilities:

1. **Coach Agent**: Roleplays sales calls, provides post-call feedback, meeting preparation
2. **Assistant Agent**: Research briefs, CRM updates, email drafts, pipeline health digests

**Key Differentiators:**
- **Hive Mind Architecture**: Dynamic task decomposition for complex requests
- **Local LLM**: qwen3.5:397b-cloud via Ollama (no cloud API costs, full data privacy)
- **Three-Tier Routing**: DIRECT (instant), WORKFLOW (structured), COMPLEX (multi-agent)
- **Self-Improving**: Memory system learns from every interaction

---

## Architecture Overview

### High-Level Architecture

```
Slack Message → Hive Mind Triage
                     ↓
        ┌────────────┼────────────┐
        ↓            ↓            ↓
    DIRECT       WORKFLOW      COMPLEX
    (Executor)   (Coach/       (PM Agent →
                 Assistant)     TaskGraph)
                     ↓              ↓
              (Typed Subgraphs)  DAG Executor
                                   (parallel batches)
                                        ↓
                                   Reviewer
                                        ↓
                                      Slack
```

### Hive Mind Orchestration

| Complexity | Description | Example | Processing |
|------------|-------------|---------|------------|
| **DIRECT** | Single tool call, instant response | "Show pipeline", "Deal status" | DirectExecutor |
| **WORKFLOW** | Single workflow, structured response | "Roleplay call", "Research company" | Coach/Assistant subgraphs |
| **COMPLEX** | Multi-step task, requires decomposition | "Prepare for QBR", "Analyze win/loss patterns" | PM Agent → DAG Executor → Reviewer |

### Key Components

1. **Triage Graph**: Classifies request complexity using qwen3.5:397b-cloud
2. **PM Agent**: Decomposes COMPLEX requests into executable TaskGraph DAGs
3. **DAG Executor**: Executes tasks in parallel batches with SQLite checkpointing
4. **Reviewer Agent**: Validates output quality before responding
5. **Memory System**: SQLite-backed lessons, preferences, patterns, failures

---

## Tech Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| **Language** | Python 3.11+ | |
| **Agent Framework** | LangGraph | StateGraph with checkpointing |
| **LLM** | Ollama qwen3.5:397b-cloud | Local inference, ~Anthropic-grade |
| **Slack SDK** | Bolt Python | Socket Mode |
| **Vector DB** | ChromaDB | HuggingFace embeddings (all-MiniLM-L6-v2) |
| **Reranking** | Cohere Rerank v4 | Top 5 results from RAG |
| **MCP Servers** | HubSpot, Gmail, BigQuery | Production-ready integrations |
| **Web Search** | Tavily API | Company news, competitive intel |
| **Memory** | SQLite | Lessons, preferences, failures, patterns |
| **Checkpointing** | SQLite | DAG execution fault tolerance |

---

## Setup & Installation

### Prerequisites

1. **Ollama installed**: `brew install ollama` (macOS) or download from ollama.ai
2. **Python 3.11+**: `python3 --version`
3. **Slack Workspace**: Admin access to install bot
4. **HubSpot Developer Account**: For MCP server (optional for demo)

### Step 1: Install Ollama and Pull Model

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama server
ollama serve

# In a separate terminal, pull the model (one-time, ~20GB)
ollama pull qwen3.5:397b-cloud
```

### Step 2: Clone and Setup Python Environment

```bash
# Clone repository
cd /path/to/project-sales

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required Variables:**

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Ollama (PRIMARY)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3.5:397b-cloud

# HubSpot (for MCP server)
HUBSPOT_ACCESS_TOKEN=pat-your-private-app-token

# Tavily (web search)
TAVILY_API_KEY=tvly-your-key

# Google Cloud (BigQuery + Gmail MCP)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=your-dataset-name
```

**Optional Variables:**

```bash
# Apollo.io enrichment (disabled by default)
ENABLE_APOLLO_ENRICHMENT=false
APOLLO_API_KEY=your-apollo-api-key

# Auto-CRM detection
AUTO_CRM_CHANNELS=C0123456789
AUTO_CRM_CONFIDENCE_THRESHOLD=0.7
AUTO_CRM_COOLDOWN_SECONDS=60
```

### Step 4: Initialize Database and Index Playbooks

```bash
# Database auto-initializes on startup

# Index playbooks into ChromaDB
python scripts/index_playbooks.py

# Seed demo data (optional)
python scripts/seed_demo_data.py
```

### Step 5: Run the App

```bash
# Start the app
python app.py

# Expected output:
# Loading MCP tools...
# Loaded 15 MCP tools: ['search_companies', 'get_deals', ...]
# Database initialized.
# Memory tables initialized.
# Triage graph compiled successfully.
```

---

## Slack Commands

### Coach Commands

| Command | Description | Complexity |
|---------|-------------|------------|
| `/coach roleplay <scenario>` | Start sales roleplay | WORKFLOW |
| `/coach feedback <call notes>` | Get post-call feedback | WORKFLOW |
| `/coach prep <meeting>` | Meeting preparation | WORKFLOW |

### Assistant Commands

| Command | Description | Complexity |
|---------|-------------|------------|
| `/research <company>` | Company research brief | DIRECT/WORKFLOW |
| `/deal <deal name>` | Deal status lookup | DIRECT |
| `/draft-email <context>` | Draft follow-up email | WORKFLOW |
| `/pipeline` | Pipeline health digest | DIRECT |

### Natural Language (Auto-Detect)

The Hive Mind Triage automatically classifies natural language:

- "Show my pipeline" → **DIRECT**
- "Roleplay a discovery call with VP Engineering" → **WORKFLOW**
- "Prepare for my QBR meeting next week with Acme Corp" → **COMPLEX**

---

## Demo Scenarios

### Scenario 1: DIRECT Path (Instant Response)

**User:** "Show pipeline"

**Expected Flow:**
1. Triage classifies as DIRECT
2. DirectExecutor queries HubSpot via MCP
3. Returns PipelineDigest artifact
4. Formatted Slack response in <2 seconds

**Expected Output:**
```
Pipeline Overview

Total: 24 deals ($1,245,000)

By Stage:
• Prospecting: 8 deals ($320,000)
• Qualification: 6 deals ($450,000)
• Proposal: 5 deals ($275,000)
• Negotiation: 3 deals ($150,000)
• Closed Won: 2 deals ($50,000)

At Risk: 3 deals
```

---

### Scenario 2: WORKFLOW Path (Structured Response)

**User:** "/coach roleplay discovery call with VP Engineering"

**Expected Flow:**
1. Triage classifies as WORKFLOW, route=coach
2. Coach subgraph executes roleplay_node
3. RAG retrieves playbooks, objection handling
4. Generates buyer persona
5. Starts interactive roleplay

**Expected Output:**
```
Buyer Persona:
- Name: Sarah Chen
- Title: VP of Engineering
- Company: Mid-market SaaS
- Traits: Technical, data-driven, skeptical of sales fluff

---

Sarah Chen: "Thanks for taking the time to connect. We've been 
evaluating solutions like yours, but honestly, we're pretty happy 
with our current setup. What makes you think we'd want to change?"
```

---

### Scenario 3: COMPLEX Path (Multi-Agent Orchestration)

**User:** "Prepare for my QBR meeting next week with Acme Corp"

**Expected Flow:**
1. Triage classifies as COMPLEX
2. PM Agent decomposes into TaskGraph:
   - fetch_pipeline (parallel)
   - fetch_wins_last_quarter (parallel)
   - fetch_losses_last_quarter
   - analyze_loss_patterns (depends on losses)
   - generate_qbr_slides (depends on all above)
   - draft_executive_summary (depends on slides)
3. DAG Executor runs parallel batches
4. Reviewer validates output
5. Memory extracts lessons

**Expected Output:**
```
QBR Deck: Acme Corp

Executive Summary:
- 67% win rate (vs. 54% avg)
- $45K avg deal size (vs. $32K avg)
- 3 open deals totaling $185K
- Key risk: Competitor X undercutting on price

Wins Last Quarter:
• Deal A: $52K - Closed via champion coaching
• Deal B: $38K - Won on implementation speed

Losses Last Quarter:
• Deal C: $75K - Lost to Competitor X (price)
• Deal D: $28K - Lost to status quo (no decision)

Pipeline Overview:
[Visual pipeline by stage]

Strategic Recommendations:
1. Executive alignment meeting with CEO
2. ROI analysis for price-sensitive deals
3. Reference call with Deal A customer
```

---

## Memory System

The Memory System learns from every interaction:

### User Preferences
- Coaching methodology (MEDDIC, SPIN, Challenger)
- Response format (detailed vs. summary)
- Privacy settings (coach visibility)

### Project Lessons
- "QBR prep requires win/loss analysis + pipeline data"
- "Acme Corp is strategic — prioritize in future requests"
- "RAG search for 'objection handling' returned outdated playbooks"

### Execution Failures
- Task type, error message, root cause, resolution
- Used for automatic retry and user guidance

### Successful Patterns
- "When researching tech companies, prioritize recent funding news"
- "Email drafts with personalization have 3x higher response rate"

---

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve

# Verify model is pulled
ollama list | grep qwen3.5
```

### MCP Tool Errors

```
Error: HubSpot API call failed
```

**Solution:** Verify `HUBSPOT_ACCESS_TOKEN` is valid and has required scopes.

### Triage Misclassification

```
User: "Prepare for QBR" → Classified as WORKFLOW instead of COMPLEX
```

**Solution:** Update triage prompt in `prompts/triage_prompt.py` to better recognize COMPLEX patterns.

### Memory Table Errors

```
SQLite error: no such table: project_lessons
```

**Solution:** Run `from graphs.memory_agent import init_memory_tables; init_memory_tables()` to initialize.

---

## Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| DIRECT latency | <2s | ~1.2s |
| WORKFLOW latency | <5s | ~3.8s |
| COMPLEX latency | <30s | ~18s |
| Memory injection overhead | <500ms | ~200ms |
| Reviewer rejection rate | <10% | ~5% |

---

## Security & Privacy

- **Local LLM**: No data leaves your infrastructure
- **SQLite Encryption**: Enable via `PRAGMA key = 'your-key'`
- **Slack OAuth**: Scoped permissions (minimal required)
- **MCP Auth**: OAuth 2.0 for HubSpot, Gmail; service account for BigQuery
- **Audit Logging**: All CRM writes logged in `crm_writes` table

---

## Next Steps

1. **Customize Playbooks**: Add your sales methodology to `data/playbooks/`
2. **Train Team**: Onboard reps with `/coach roleplay` sessions
3. **Monitor Usage**: Review `engagement_events` table for adoption metrics
4. **Expand Integrations**: Add more MCP servers (Gong, Salesforce, etc.)

---

## Support

- **Architecture Docs**: `architecture-diagrams.mermaid`
- **Hive Mind Plan**: `docs/HIVE-MIND-IMPLEMENTATION-PLAN.md`
- **Task Tracker**: `docs/HIVE-MIND-TASKS.md`
- **CLAUDE.md**: Developer guide
