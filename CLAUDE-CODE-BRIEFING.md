# Claude Code Briefing: Sales AI Agents — POC Build

> **IMPORTANT: Read this entire document before writing any code.**
> This is the distilled output of extensive brainstorming and architectural planning sessions.
> Every decision here has been researched and made deliberately. Follow them.

---

## 1. WHAT WE'RE BUILDING

A Slack bot that acts as two AI agents for a sales team:

1. **Coach Agent** — AI sales coach that runs roleplays, gives post-call feedback, and preps reps for meetings
2. **Assistant Agent** — Handles admin: research briefs, CRM updates, email drafts, pipeline health digests

The bot lives in Slack. Data comes from HubSpot CRM, the internet (via Tavily web search), and BigQuery. Actions go to Gmail and HubSpot.

**This is a PROOF OF CONCEPT for an executive demo AND pilot.** We are NOT building full production quality (no security hardening, no cloud deployment), but we ARE using the production architecture (MCP for tool integration, LangGraph for orchestration) so the POC can be piloted with real reps after the demo — and the tool integration layer carries forward to production with zero throwaway code.

---

## 2. POC TECH STACK (DO NOT DEVIATE)

| Component | Choice | Package | Why |
|-----------|--------|---------|-----|
| Language | Python 3.11+ | — | LangGraph + Slack Bolt best supported |
| Agent Framework | LangGraph | `langgraph` | Production architecture; validate now |
| MCP Adapter | langchain-mcp-adapters | `langchain-mcp-adapters` | Bridges MCP tools ↔ LangGraph seamlessly |
| LLM Gateway | OpenRouter | `langchain-openai` (OpenAI-compatible) | Single API key, swap models instantly, experiment with Claude/DeepSeek/Qwen/Gemini |
| Default LLM | Claude Sonnet 4.5 (via OpenRouter) | `anthropic/claude-sonnet-4.5` | Best tool-use (0.920), start here then experiment |
| Slack | Bolt SDK (Socket Mode) | `slack-bolt` | Runs locally, no server needed |
| Vector DB (RAG) | ChromaDB (local) | `chromadb` | pip install, zero config, local persistence |
| Embeddings | HuggingFace all-MiniLM-L6-v2 (local) | `langchain-huggingface` | Free, runs on CPU, no API key needed, good enough for POC |
| Web Search | Tavily | `tavily-python` | Free tier, optimized for AI agents |
| HubSpot | HubSpot MCP Server | `@hubspot/mcp-server` (npm) | Official public beta; production-ready |
| BigQuery | Google Managed MCP Server | Google Cloud managed | Auto-enabled; fully managed |
| Gmail | shinzo-labs/gmail-mcp | `shinzo-labs/gmail-mcp` | Community MIT; full API coverage |

### Why MCP in the POC (not direct API calls)
We deliberately chose MCP over direct API wrappers for the POC:
1. **Zero throwaway code** — the MCP tool integration layer carries forward to production unchanged. No rewriting tools/hubspot.py later.
2. **Pilot-ready** — with MCP, the POC isn't just a demo; it can be piloted with real reps because it runs the actual production architecture.
3. **Tool discovery is automatic** — MCP servers expose their available tools dynamically. The LangGraph agent discovers what it can do at startup. Less code to write than manual API wrappers.
4. **Adding tools later is trivial** — if during the pilot a rep asks "can it also check Salesforce?", you add an MCP server. No agent code changes.
5. **Setup is fast** — `langchain-mcp-adapters` makes MCP tools appear as regular LangGraph tools. ~15-30 minutes per server.
6. **Strengthens the executive pitch** — "We use MCP, the open protocol created by Anthropic and adopted by Google, HubSpot, Slack, and thousands of others. This is the industry standard, not a custom hack."

### How MCP Works in This Project

```
Your LangGraph Agent (MCP Client)
    │
    ├── langchain-mcp-adapters (pip install)
    │   Converts MCP tools → LangChain tools → available in LangGraph
    │
    ├──── HubSpot MCP Server (runs as subprocess via stdio)
    │     npm install @hubspot/mcp-server
    │     Exposes: search_contacts, get_deals, get_companies, get_notes, etc.
    │
    ├──── BigQuery MCP Server (Google managed remote)
    │     Enabled in your GCP project
    │     Exposes: run_query, get_schema, list_tables, etc.
    │
    ├──── Gmail MCP Server (runs as subprocess via stdio)
    │     Clone shinzo-labs/gmail-mcp
    │     Exposes: search_emails, create_draft, send_email, get_thread, etc.
    │
    └──── Tavily (direct — no MCP needed, it's just a simple API)
          pip install tavily-python
```

The `langchain-mcp-adapters` library handles all the MCP protocol details. From LangGraph's perspective, MCP tools look identical to regular Python tool functions.

### Why OpenRouter (not direct Anthropic/OpenAI APIs)
We use OpenRouter as an LLM gateway instead of calling provider APIs directly:
1. **One API key for all models** — `OPENROUTER_API_KEY` replaces `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`. Simpler setup, single billing.
2. **Model experimentation** — change `model="anthropic/claude-sonnet-4.5"` to `model="deepseek/deepseek-chat-v3"` in one line. Same code, same tools, instant comparison.
3. **200+ models accessible** — Claude, DeepSeek, Qwen, Gemini, Llama, Mistral — all through one endpoint.
4. **OpenAI-compatible API** — works with LangChain's `ChatOpenAI` class. All LangGraph features (tool calling, streaming, structured output) work unchanged.
5. **Works with Langfuse** — Langfuse's LangChain callback integration traces OpenRouter calls normally. Model names like `anthropic/claude-sonnet-4.5` appear in Langfuse, letting you filter and compare traces by model.

**Start with Claude Sonnet 4.5 as default** (best tool-use at 0.920), then experiment per-workflow to find cost/quality sweet spots.

### Why Local Embeddings (not OpenAI API)
We use HuggingFace `all-MiniLM-L6-v2` running locally instead of OpenAI's embedding API:
1. **No API key needed** — eliminates the `OPENAI_API_KEY` dependency entirely
2. **Free** — zero cost for embedding, no per-token charges
3. **Fast** — runs on CPU, 80MB model, sub-second for your 8 playbook documents
4. **Offline** — works without internet, no rate limits
5. **Good enough for POC** — slightly below OpenAI quality, but with 8 documents the difference is negligible. Senior dev can swap in Voyage AI or OpenAI for production if needed.

---

## 3. PROJECT STRUCTURE

```
sales-ai-agents/
├── .env                          # API keys (NEVER commit)
├── .env.example                  # Template for required keys
├── requirements.txt              # Python dependencies
├── app.py                        # Main entry point — Slack Bolt app
├── mcp_setup.py                  # MCP server initialization + tool loading
├── graphs/
│   ├── __init__.py
│   ├── router.py                 # Router graph — classifies intent, routes to Coach/Assistant
│   ├── coach.py                  # Coach agent graph — roleplay, feedback, prep
│   └── assistant.py              # Assistant agent graph — research, pipeline, email draft
├── tools/
│   ├── __init__.py
│   ├── web_search.py             # Tavily web search wrapper (direct, not MCP)
│   └── rag.py                    # ChromaDB RAG — index + search
├── prompts/
│   ├── router_prompt.py          # System prompt for intent classification
│   ├── coach_prompts.py          # System prompts for roleplay, feedback, prep
│   └── assistant_prompts.py      # System prompts for research, pipeline, email
├── data/
│   └── playbooks/                # Drop your sales playbook PDFs/docs here
└── scripts/
    └── index_playbooks.py        # One-time script to index playbooks into ChromaDB
```

Note: No `tools/hubspot.py`, `tools/bigquery.py`, or `tools/gmail.py` files needed.
MCP servers expose these tools automatically. The agent discovers them at startup.

---

## 4. ENVIRONMENT VARIABLES (.env)

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# OpenRouter (single key for ALL LLM calls — Claude, DeepSeek, Qwen, etc.)
OPENROUTER_API_KEY=sk-or-v1-your-key

# Default model (change this to experiment — no code changes needed)
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4.5

# HubSpot (for MCP server)
HUBSPOT_ACCESS_TOKEN=pat-your-private-app-token

# Tavily (web search — direct, not MCP)
TAVILY_API_KEY=tvly-your-key

# Google Cloud (for BigQuery MCP + Gmail MCP)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=your-dataset-name

# Gmail OAuth (for Gmail MCP server)
GMAIL_CLIENT_ID=your-google-oauth-client-id
GMAIL_CLIENT_SECRET=your-google-oauth-client-secret

# NO Anthropic or OpenAI keys needed!
# - LLM calls go through OpenRouter (single key above)
# - Embeddings run locally via HuggingFace (no API key)
```

---

## 5. DEPENDENCIES (requirements.txt)

```
slack-bolt>=1.20.0
langgraph>=0.2.0
langchain-openai>=0.2.0
langchain-community>=0.3.0
langchain-huggingface>=0.1.0
langchain-mcp-adapters>=0.1.0
chromadb>=0.5.0
tavily-python>=0.5.0
python-dotenv>=1.0.0
langchain-text-splitters>=0.3.0
pypdf>=4.0.0
sentence-transformers>=2.2.0
```

Note: `langchain-anthropic`, `langchain-openai` (for OpenAI direct), `hubspot-api-client`, and `google-cloud-bigquery` are NOT needed.
- LLM calls go through OpenRouter via `langchain-openai` (OpenAI-compatible endpoint)
- Embeddings run locally via `langchain-huggingface` + `sentence-transformers`
- HubSpot and BigQuery tools come through their MCP servers

### Additional setup (not pip — run separately):
```bash
# HubSpot MCP Server (Node.js)
npm install -g @hubspot/mcp-server

# Gmail MCP Server (clone and setup)
git clone https://github.com/shinzo-labs/gmail-mcp.git
cd gmail-mcp && npm install

# BigQuery MCP Server — no install needed if using Google's managed remote server
# Just ensure BigQuery API is enabled in your GCP project
```

---

## 6. SLASH COMMANDS TO IMPLEMENT (5 total)

### Command 1: `/research [company_name]`
**Agent:** Assistant
**What it does:**
1. Search HubSpot for the company → get deals, contacts, recent notes
2. Run Tavily web search for recent company news
3. (Optional) Query BigQuery for historical deal patterns with this company
4. Generate a meeting prep brief with: company overview, deal status, talking points, recent news, risk areas

**Slack output:** Rich Block Kit message with sections for each area.

### Command 2: `/deal [deal_name]`
**Agent:** Assistant
**What it does:**
1. Search HubSpot for the deal by name
2. Pull: deal stage, amount, close date, associated contacts, recent activities/notes
3. Generate a brief summary with next recommended actions

**Slack output:** Formatted deal card with key metrics and action items.

### Command 3: `/coach roleplay [scenario]`
**Agent:** Coach
**What it does:**
1. Parse the scenario (e.g., "discovery call with CFO", "pricing objection", "cold call to VP of Engineering")
2. RAG: Pull relevant ICP, objection scripts, and battle cards from ChromaDB
3. Generate a buyer persona with name, role, personality, and hidden objections
4. Start a multi-turn roleplay in a Slack thread:
   - Bot posts as the buyer (first message in thread)
   - Rep replies in thread
   - Bot scores the reply internally and responds as buyer
   - After 3-4 turns, bot posts a debrief: overall score, strengths, areas to improve, specific feedback per turn

**Implementation:** This is a simple loop for the POC — NOT durable execution. The conversation stays in a single Slack thread. Track state in a Python dict keyed by thread_ts.

**Slack output:** Thread-based conversation, then a final debrief message with a scorecard.

### Command 4: `/draft-email [company_name]`
**Agent:** Assistant
**What it does:**
1. Search HubSpot for the company/deal context
2. RAG: Pull relevant email templates or follow-up best practices
3. Generate a follow-up email draft based on the deal context
4. Post the draft in Slack (do NOT send via Gmail — just display it)

**Slack output:** Formatted email draft with subject line and body. Include buttons: "Copy to Clipboard" or "Looks Good" (cosmetic for demo).

### Command 5: `/pipeline`
**Agent:** Assistant
**What it does:**
1. Pull all open deals from HubSpot
2. (Optional) Query BigQuery for win rate trends
3. Analyze: flag stale deals (no activity in 14+ days), deals past close date, deals missing key data
4. Generate a pipeline health digest

**Slack output:** Summary card with: total pipeline value, deal count by stage, flagged deals with reasons, and recommended actions.

---

## 7. LANGGRAPH ARCHITECTURE

### Graph Structure

```
Main Graph (app.py invokes this)
│
├── Router Node (classifies intent)
│   ├── → Coach Subgraph
│   └── → Assistant Subgraph
│
├── Coach Subgraph (graphs/coach.py)
│   ├── roleplay_node → multi-turn loop
│   ├── feedback_node → post-call analysis
│   └── prep_node → meeting preparation
│
└── Assistant Subgraph (graphs/assistant.py)
    ├── research_node → company research brief
    ├── deal_node → deal status lookup
    ├── email_node → follow-up draft
    └── pipeline_node → pipeline health digest
```

### State Schema

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    """Shared state across the graph."""
    route: Literal["coach", "assistant", "direct"] | None  # Router decision
    workflow: str | None  # e.g., "roleplay", "research", "pipeline"
    user_id: str  # Slack user ID
    channel_id: str  # Slack channel ID
    thread_ts: str | None  # Slack thread timestamp
    hubspot_context: dict | None  # Cached HubSpot data for current request
    rag_context: str | None  # Retrieved RAG chunks
    web_context: str | None  # Web search results
```

### Router Implementation Pattern

```python
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

# All LLM calls go through OpenRouter — change model string to experiment
router_llm = ChatOpenAI(
    model=os.environ.get("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-sonnet-4.5"),
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

def router_node(state: AgentState) -> dict:
    """Classify the user's intent and choose a route."""
    last_message = state["messages"][-1].content

    response = router_llm.invoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=last_message)
    ])

    # Parse the route from the response
    # Expected: {"route": "coach"|"assistant", "workflow": "roleplay"|"research"|...}
    parsed = parse_router_response(response.content)
    return {"route": parsed["route"], "workflow": parsed["workflow"]}

def route_decision(state: AgentState) -> str:
    """Conditional edge: which subgraph to invoke."""
    if state["route"] == "coach":
        return "coach"
    return "assistant"

# Build the graph
graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("coach", coach_subgraph)
graph.add_node("assistant", assistant_subgraph)

graph.add_edge(START, "router")
graph.add_conditional_edges("router", route_decision, {
    "coach": "coach",
    "assistant": "assistant"
})
graph.add_edge("coach", END)
graph.add_edge("assistant", END)

app_graph = graph.compile()
```

---

## 8. SLACK BOLT APP PATTERN (app.py)

```python
import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_core.messages import HumanMessage

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Import the compiled LangGraph
from graphs import app_graph

@app.command("/research")
def handle_research(ack, say, command):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    company = command["text"].strip()

    # Show thinking indicator
    say(f"🔍 Researching *{company}*... give me 15 seconds.", channel=channel_id)

    # Invoke the graph
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/research {company}")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    # Extract the final response and send to Slack
    response_text = result["messages"][-1].content
    say(text=response_text, channel=channel_id)


@app.command("/coach")
def handle_coach(ack, say, command):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command["text"].strip()

    # Post initial message and get thread_ts
    result = say(f"🎯 Starting coaching session...", channel=channel_id)
    thread_ts = result["ts"]

    # Invoke the graph
    graph_result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/coach {text}")],
        "route": "coach",
        "workflow": "roleplay" if "roleplay" in text.lower() else "prep",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
    })

    response_text = graph_result["messages"][-1].content
    say(text=response_text, channel=channel_id, thread_ts=thread_ts)


@app.command("/deal")
def handle_deal(ack, say, command):
    ack()
    company = command["text"].strip()
    say(f"📊 Looking up deal: *{company}*...")

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/deal {company}")],
        "route": "assistant",
        "workflow": "deal",
        "user_id": command["user_id"],
        "channel_id": command["channel_id"],
        "thread_ts": None,
    })

    say(text=result["messages"][-1].content, channel=command["channel_id"])


@app.command("/draft-email")
def handle_draft_email(ack, say, command):
    ack()
    company = command["text"].strip()
    say(f"✉️ Drafting follow-up email for *{company}*...")

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {company}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": command["user_id"],
        "channel_id": command["channel_id"],
        "thread_ts": None,
    })

    say(text=result["messages"][-1].content, channel=command["channel_id"])


@app.command("/pipeline")
def handle_pipeline(ack, say, command):
    ack()
    say("📈 Analyzing pipeline health...")

    result = app_graph.invoke({
        "messages": [HumanMessage(content="/pipeline")],
        "route": "assistant",
        "workflow": "pipeline",
        "user_id": command["user_id"],
        "channel_id": command["channel_id"],
        "thread_ts": None,
    })

    say(text=result["messages"][-1].content, channel=command["channel_id"])


# Handle thread replies (for roleplay continuation)
@app.event("message")
def handle_thread_reply(event, say):
    """When a rep replies in a roleplay thread, continue the conversation."""
    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return  # Not a thread reply, ignore

    # Check if this thread is an active roleplay
    # (You'll need a simple dict to track active roleplay threads)
    if thread_ts in active_roleplays:
        result = app_graph.invoke({
            "messages": active_roleplays[thread_ts]["messages"] + [
                HumanMessage(content=event["text"])
            ],
            "route": "coach",
            "workflow": "roleplay",
            "user_id": event["user"],
            "channel_id": event["channel"],
            "thread_ts": thread_ts,
        })

        # Update stored messages
        active_roleplays[thread_ts]["messages"] = result["messages"]

        say(
            text=result["messages"][-1].content,
            channel=event["channel"],
            thread_ts=thread_ts
        )


# In-memory roleplay state (POC only — production uses LangGraph checkpointer)
active_roleplays = {}

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡ Sales AI Agent is running!")
    handler.start()
```

---

## 9. MCP SETUP & TOOL LOADING (mcp_setup.py)

This is the core new file that replaces manual tool wrappers. It starts MCP servers and loads their tools into LangGraph.

```python
"""
MCP Server Setup — loads tools from HubSpot, BigQuery, and Gmail MCP servers.
Tools are automatically discovered and made available to LangGraph agents.
"""
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

# MCP server configuration
# Each server runs as a subprocess (stdio transport) or connects to a remote endpoint
MCP_SERVERS = {
    "hubspot": {
        "command": "npx",
        "args": ["@hubspot/mcp-server"],
        "env": {
            "HUBSPOT_ACCESS_TOKEN": os.environ.get("HUBSPOT_ACCESS_TOKEN", ""),
        },
        "transport": "stdio",
    },
    "gmail": {
        "command": "node",
        "args": ["./gmail-mcp/dist/index.js"],  # Path to cloned gmail-mcp
        "env": {
            "GMAIL_CLIENT_ID": os.environ.get("GMAIL_CLIENT_ID", ""),
            "GMAIL_CLIENT_SECRET": os.environ.get("GMAIL_CLIENT_SECRET", ""),
        },
        "transport": "stdio",
    },
    # BigQuery: If using Google's managed remote MCP server, configure as HTTP/SSE
    # If using local mcp-server-bigquery, configure as stdio like above
    "bigquery": {
        "command": "npx",
        "args": ["mcp-server-bigquery"],
        "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            "BIGQUERY_PROJECT_ID": os.environ.get("BIGQUERY_PROJECT_ID", ""),
            "BIGQUERY_DATASET": os.environ.get("BIGQUERY_DATASET", ""),
        },
        "transport": "stdio",
    },
}


async def get_mcp_tools():
    """
    Start all MCP servers and return their tools as LangChain-compatible tools.
    These tools can be bound directly to a LangGraph agent via .bind_tools().
    """
    async with MultiServerMCPClient(MCP_SERVERS) as client:
        tools = client.get_tools()
        return tools


# Usage in your LangGraph nodes:
#
#   from mcp_setup import get_mcp_tools
#
#   mcp_tools = await get_mcp_tools()
#
#   # Bind MCP tools to your LLM (via OpenRouter)
#   llm_with_tools = ChatOpenAI(
#       model=os.environ.get("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-sonnet-4.5"),
#       base_url="https://openrouter.ai/api/v1",
#       api_key=os.environ["OPENROUTER_API_KEY"],
#   ).bind_tools(mcp_tools)
#
#   # The agent can now call HubSpot, BigQuery, and Gmail tools natively
#   # Tool names are auto-discovered from each MCP server
#   # Example tool names: "search_contacts", "get_deals", "run_query", "create_draft"
#   #
#   # To experiment with different models, just change the model string:
#   #   "anthropic/claude-sonnet-4.5"   — best tool-use (default)
#   #   "deepseek/deepseek-chat-v3"     — cheaper, good reasoning
#   #   "qwen/qwen3-235b"              — strong multilingual
#   #   "google/gemini-2.5-pro"         — 1M context, cheap
#   #   "meta-llama/llama-4-maverick"   — open source
```

### How MCP Tools Appear to the Agent

When the LangGraph agent starts, MCP servers expose their tools automatically:

**HubSpot MCP Server exposes tools like:**
- `search_contacts(query)` — search CRM contacts
- `get_company(company_id)` — get company details
- `get_deals(filters)` — list/filter deals
- `get_deal(deal_id)` — get single deal with associations
- `search_companies(query)` — search by company name
- `get_engagements(object_id)` — get notes, calls, emails for a record
- `create_note(object_id, body)` — log a note on a deal/contact

**BigQuery MCP Server exposes tools like:**
- `run_query(sql)` — execute a SQL query
- `get_table_schema(table)` — inspect table structure
- `list_tables(dataset)` — list available tables

**Gmail MCP Server exposes tools like:**
- `search_emails(query)` — search inbox
- `get_message(message_id)` — read an email
- `create_draft(to, subject, body)` — create a draft
- `send_email(to, subject, body)` — send an email
- `get_thread(thread_id)` — get email thread

The agent discovers these at startup. You don't write wrapper functions for any of them.

### IMPORTANT: MCP Client Lifecycle

The `MultiServerMCPClient` manages server subprocesses. For the POC, the simplest approach is to initialize it once at app startup and keep it alive for the session. In production, you'd use connection pooling.

```python
# In app.py — initialize MCP client at startup
import asyncio
from mcp_setup import get_mcp_tools

# Load MCP tools once at startup
mcp_tools = asyncio.run(get_mcp_tools())

# Pass mcp_tools to your graph builders
from graphs import build_main_graph
app_graph = build_main_graph(mcp_tools)
```

---

## 9B. ADDITIONAL TOOLS (Non-MCP)

### tools/web_search.py — Tavily (Direct, Not MCP)

Tavily is simple enough that MCP adds no value. Use directly.

```python
from tavily import TavilyClient

def search_company_news(company_name: str) -> str:
    """Search for recent news about a company. Return formatted summary."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(
        query=f"{company_name} latest news 2026",
        max_results=5,
        search_depth="basic"
    )
    # Format results into a readable summary
    return format_search_results(results)
```

### tools/rag.py — ChromaDB RAG

```python
import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Initialize — local embeddings, no API key needed
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("sales_knowledge")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
# First run downloads the 80MB model automatically. Runs on CPU, sub-second per query.

def index_document(text: str, metadata: dict):
    """Add a document to the RAG index."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=75
    )
    chunks = splitter.split_text(text)
    for i, chunk in enumerate(chunks):
        embedding = embeddings.embed_query(chunk)
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            metadatas=[{**metadata, "chunk_index": i}],
            ids=[f"{metadata.get('source', 'doc')}_{i}"]
        )

def search(query: str, n_results: int = 5) -> str:
    """Search the RAG index. Return formatted context string."""
    query_embedding = embeddings.embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    # Combine chunks into context string
    return "\n\n---\n\n".join(results["documents"][0])
```

### scripts/index_playbooks.py — Run Once to Load Playbooks

```python
"""
Run this script once to index your sales playbooks into ChromaDB.
Place PDF/text files in the data/playbooks/ directory first.

Usage: python scripts/index_playbooks.py
"""
from pypdf import PdfReader
from tools.rag import index_document
import os

PLAYBOOK_DIR = "data/playbooks"

for filename in os.listdir(PLAYBOOK_DIR):
    filepath = os.path.join(PLAYBOOK_DIR, filename)

    if filename.endswith(".pdf"):
        reader = PdfReader(filepath)
        text = "\n".join(page.extract_text() for page in reader.pages)
    elif filename.endswith((".txt", ".md")):
        with open(filepath) as f:
            text = f.read()
    else:
        continue

    print(f"Indexing: {filename} ({len(text)} chars)")
    index_document(text, {"source": filename, "type": "playbook"})

print("Done! Playbooks indexed into ChromaDB.")
```

---

## 10. SYSTEM PROMPTS

### Router Prompt (prompts/router_prompt.py)

```python
ROUTER_PROMPT = """You are an intent classifier for a sales AI assistant in Slack.

Given a user message, classify it into one of these categories:

COACH WORKFLOWS:
- "roleplay" — user wants to practice a sales conversation
- "feedback" — user wants feedback on a call or interaction
- "prep" — user wants help preparing for a meeting

ASSISTANT WORKFLOWS:
- "research" — user wants information about a company or prospect
- "deal" — user wants status on a specific deal
- "email" — user wants help drafting an email
- "pipeline" — user wants a pipeline health overview

Respond with ONLY a JSON object:
{"route": "coach" or "assistant", "workflow": "roleplay|feedback|prep|research|deal|email|pipeline"}

Do not explain. Just output the JSON."""
```

### Coach Roleplay Prompt (prompts/coach_prompts.py)

```python
ROLEPLAY_SYSTEM_PROMPT = """You are an AI sales coach running a roleplay session.

CONTEXT FROM PLAYBOOK:
{rag_context}

YOUR ROLE:
You play the buyer persona described below. Stay in character throughout the conversation.
After the rep's messages, internally score their performance but DO NOT reveal scores until the debrief.

BUYER PERSONA:
- Name: {persona_name}
- Title: {persona_title}
- Company: {persona_company}
- Personality: {persona_personality}
- Hidden objections: {persona_objections}
- What they care about: {persona_priorities}

RULES:
1. Stay in character as the buyer. Be realistic — don't make it too easy.
2. Respond naturally as this persona would. Use their communication style.
3. After 3-4 exchanges, break character and provide a debrief.
4. In the debrief, include:
   - Overall score (1-10)
   - What the rep did well (specific examples)
   - Areas to improve (specific, actionable)
   - Suggested follow-up practice

FORMAT YOUR DEBRIEF LIKE THIS:
---
🎯 **Roleplay Debrief**

**Overall Score: X/10**

**✅ What You Did Well:**
• [specific strength with example from the conversation]
• [specific strength with example]

**🔧 Areas to Improve:**
• [specific area with concrete suggestion]
• [specific area with concrete suggestion]

**📝 Recommended Practice:**
• [next roleplay scenario to work on]
---"""

FEEDBACK_SYSTEM_PROMPT = """You are an AI sales coach analyzing a sales interaction.

CONTEXT FROM PLAYBOOK:
{rag_context}

CALL/MEETING NOTES:
{call_notes}

Analyze this interaction against sales best practices and provide:
1. Overall effectiveness score (1-10)
2. Key moments that went well (with quotes if available)
3. Missed opportunities
4. Specific action items for improvement
5. Recommended follow-up with the prospect

Be specific, not generic. Reference actual moments from the interaction."""

PREP_SYSTEM_PROMPT = """You are an AI sales coach helping a rep prepare for a meeting.

HUBSPOT DEAL DATA:
{hubspot_context}

COMPANY NEWS:
{web_context}

PLAYBOOK CONTEXT:
{rag_context}

BIGQUERY DATA:
{bq_context}

Create a concise but thorough meeting prep brief:

📋 **Meeting Prep: {company_name}**

**Account Summary:**
[Key details from HubSpot — deal stage, value, key contacts, recent activity]

**Recent News & Intel:**
[Relevant company news from web search]

**Key Talking Points:**
[3-5 specific talking points based on deal context and playbook]

**Potential Objections & Responses:**
[Likely objections based on deal stage and persona, with suggested responses]

**Questions to Ask:**
[Strategic questions to advance the deal]

**Risk Areas:**
[Things to watch out for based on deal history]"""
```

### Assistant Prompts (prompts/assistant_prompts.py)

```python
RESEARCH_SYSTEM_PROMPT = """You are a sales research assistant.

HUBSPOT DATA:
{hubspot_context}

WEB SEARCH RESULTS:
{web_context}

PLAYBOOK CONTEXT:
{rag_context}

Generate a research brief for the sales rep. Include:

🔍 **Research Brief: {company_name}**

**Company Overview:**
[What they do, size, industry, recent developments]

**Your Relationship:**
[Deal history, key contacts, last interaction from HubSpot]

**Recent News:**
[Relevant news and what it means for the deal]

**Talking Points:**
[3-5 actionable talking points]

**Competitive Landscape:**
[Any competitive intel from web search]

Keep it concise. Reps need to scan this in 2 minutes before a meeting."""

PIPELINE_SYSTEM_PROMPT = """You are a sales operations analyst reviewing the pipeline.

OPEN DEALS:
{deals_data}

ANALYTICS:
{bq_context}

Generate a pipeline health digest:

📈 **Pipeline Health Digest**

**Summary:**
[Total pipeline value, deal count, weighted forecast]

**By Stage:**
[Deal count and value per stage]

**⚠️ Flagged Deals:**
[Deals with issues — explain why each is flagged]
• Stale: no activity in 14+ days
• Overdue: past projected close date
• At risk: missing key data or stalled

**Recommended Actions:**
[Top 3-5 specific actions the team should take this week]"""

EMAIL_SYSTEM_PROMPT = """You are a sales email copywriter.

HUBSPOT DEAL CONTEXT:
{hubspot_context}

PLAYBOOK CONTEXT:
{rag_context}

Draft a follow-up email for {company_name}.

Requirements:
- Subject line (compelling, not generic)
- Personalized based on the deal context and last interaction
- Clear call-to-action
- Professional but warm tone
- Under 150 words (reps can expand)

Format:
📧 **Draft Follow-Up Email**

**To:** [contact name and email if available]
**Subject:** [subject line]

[email body]

---
_Edit as needed before sending._"""
```

---

## 11. ROLEPLAY MULTI-TURN FLOW (POC Simplified)

For the POC, we handle multi-turn roleplay with a simple in-memory dict. No durable execution needed.

```python
# In app.py, the roleplay flow works like this:

# 1. /coach roleplay discovery call → handle_coach()
#    - Creates buyer persona
#    - Posts first buyer message in a new thread
#    - Stores state in active_roleplays[thread_ts]

# 2. Rep replies in thread → handle_thread_reply()
#    - Loads state from active_roleplays[thread_ts]
#    - Appends rep's message to conversation history
#    - Coach LLM generates buyer response (or debrief if turn >= 4)
#    - Posts response in thread
#    - Updates stored state

# 3. After turn 4, Coach generates debrief instead of buyer response
#    - Posts scorecard in thread
#    - Removes from active_roleplays

# State structure:
active_roleplays = {
    "thread_ts_12345": {
        "messages": [...],  # Full conversation history
        "turn_count": 3,
        "persona": {...},   # Buyer persona details
        "user_id": "U123",
        "rag_context": "..." # Cached RAG context
    }
}
```

---

## 12. WHAT TO SKIP (POC ONLY)

DO NOT implement any of the following — they're for the production build:

- ❌ Durable execution / LangGraph checkpointer (use in-memory dict for roleplay)
- ❌ Multi-model routing (no Gemini, no Haiku — Claude Sonnet for everything)
- ❌ Cohere Rerank (basic ChromaDB search is fine)
- ❌ PII detection / redaction
- ❌ Access control / OAuth scoping
- ❌ Audit logging / observability
- ❌ Production error handling (basic try/except is fine)
- ❌ Cloud deployment (run locally)
- ❌ Rate limiting
- ❌ Rep profile storage
- ❌ Scheduled tasks (pipeline digest on-demand only)

Things we DO include (changed from original plan):
- ✅ MCP servers for HubSpot, BigQuery, Gmail (zero throwaway code, pilot-ready)
- ✅ Gmail MCP — can actually create drafts and send emails during pilot

---

## 13. BUILD ORDER

Follow this exact sequence. Each step should be testable before moving to the next.

### Step 1: Skeleton + MCP Setup (1-1.5 hours)
- Create project structure (see Section 3)
- Install Python dependencies (`pip install -r requirements.txt`)
- Install Node.js MCP servers (`npm install -g @hubspot/mcp-server`, clone `shinzo-labs/gmail-mcp`)
- Set up `.env` with all API keys and tokens
- Create a bare Slack Bolt app that responds to a test command (`/ping → pong`)
- Implement `mcp_setup.py` (see Section 9) — start MCP servers, verify tools load
- **Test:** Run `get_mcp_tools()` and print the list of discovered tools. You should see HubSpot tools (search_contacts, get_deals, etc.) and Gmail tools (search_emails, create_draft, etc.). If BigQuery is configured, you'll see its tools too. This is your sanity check that the MCP layer works.

### Step 2: MCP Tools + Deal Command (1-2 hours)
- Wire MCP tools into a test LangGraph node: bind tools to Claude via `.bind_tools(mcp_tools)`
- Test HubSpot MCP: can you search a company? Get deals? Get contacts? (Use the auto-discovered tool names)
- Implement the Assistant subgraph skeleton (`graphs/assistant.py`)
- Implement `/deal` command end-to-end: Slack → Assistant → HubSpot MCP → formatted response
- **Test:** `/deal [real deal from your HubSpot]` returns deal info in Slack

### Step 3: Router + Research Command (2-3 hours)
- Implement the Router graph (`graphs/router.py`) with intent classification
- Implement `tools/web_search.py` (Tavily — direct, not MCP)
- Implement `/research` command: HubSpot MCP data + Tavily web search → Claude generates brief
- **Test:** `/research [real company]` returns a research brief with CRM data and recent news

### Step 4: RAG Setup (1-2 hours)
- Implement `tools/rag.py` (ChromaDB — see Section 9B)
- Run `scripts/index_playbooks.py` with 2-3 real playbook documents
- **Test:** does `rag.search("objection handling")` return relevant chunks?

### Step 5: Coach Roleplay (3-4 hours)
- Implement Coach subgraph (`graphs/coach.py`)
- Implement `/coach roleplay` with buyer persona generation + RAG context
- Implement thread-based multi-turn conversation (in-memory `active_roleplays` dict)
- Implement debrief generation after 3-4 turns
- **Test:** run a full roleplay in Slack — buyer responses feel realistic, debrief has specific feedback

### Step 6: Email Draft + Pipeline (2-3 hours)
- Implement `/draft-email` with HubSpot MCP context + RAG
- (Optional) Test Gmail MCP: create a draft in the rep's Gmail (pilot feature)
- Implement `/pipeline` with HubSpot MCP deal analysis
- (Optional) Add BigQuery MCP queries for win-rate analytics
- **Test:** `/draft-email [company]` returns a contextual email, `/pipeline` flags stale deals

### Step 7: Polish (2-3 hours)
- Format all Slack responses with Block Kit (headers, sections, bullet points)
- Add typing indicators ("🔍 Researching..." messages)
- Test all 5 commands end-to-end against real HubSpot data
- Verify MCP server lifecycle — servers stay alive across multiple commands without restarting
- Fix any rough edges

**Total estimated POC build time: 13-19 hours of focused work**
(Spread across 2-3 weeks with testing and iteration)

---

## 14. TESTING CHECKLIST

Before the executive demo, verify each command works:

- [ ] `/research [real company from your HubSpot]` → returns a rich brief
- [ ] `/deal [real deal name]` → returns deal status and actions
- [ ] `/coach roleplay discovery call` → starts roleplay, runs 3-4 turns, gives debrief with scores
- [ ] `/draft-email [real company]` → generates a contextual follow-up email
- [ ] `/pipeline` → returns pipeline digest with flagged deals
- [ ] RAG context is relevant (playbook content appears in coaching and prep)
- [ ] Responses are formatted nicely in Slack (not raw text walls)

---

## 15. PRODUCTION ROADMAP (For Reference Only — NOT for POC)

After executive approval, a hired senior developer will rebuild this properly:

- LangGraph with durable execution and Postgres checkpointer
- Multi-model via OpenRouter or direct APIs: Claude Sonnet (Coach) + Gemini 2.5 Pro (Assistant) + Haiku (Router)
- MCP servers for HubSpot, BigQuery, Gmail (official + community)
- Qdrant/Weaviate vector DB replacing ChromaDB
- Voyage AI or OpenAI embeddings replacing local HuggingFace + Cohere Rerank
- GCP deployment: Cloud Run + Cloud SQL + Qdrant Cloud
- PII handling, access control, audit logging
- Rep profile storage and skill tracking
- Scheduled pipeline digests
- Observability with Langfuse/LangSmith

The full architecture is documented in `brainstorm-sales-agents.md` and `architecture-diagrams.mermaid` in the project folder.

---

## 16. KEY GOTCHAS

1. **Slack Socket Mode requires TWO tokens:** Bot Token (xoxb-) AND App Token (xapp-). Both are needed.
2. **MCP server lifecycle:** The `MultiServerMCPClient` spawns MCP servers as subprocesses. Initialize it ONCE at app startup and keep it alive. If you create a new client per request, you'll spawn (and kill) Node.js processes on every Slack command — slow and wasteful. See the "MCP Client Lifecycle" pattern in Section 9.
3. **MCP tool names vary by server version.** After loading tools with `get_mcp_tools()`, print the full tool list on first run. HubSpot might expose `search_crm_objects` instead of `search_contacts`, or Gmail might use `gmail_send` instead of `send_email`. Adapt your prompts to the actual tool names discovered at runtime.
4. **Node.js is required** for the HubSpot and Gmail MCP servers (they run as `npx` / `node` subprocesses). Make sure `node` v18+ and `npm` are installed on the machine where you run the POC.
5. **Gmail OAuth flow:** The Gmail MCP server (`shinzo-labs/gmail-mcp`) needs OAuth credentials, not just an API key. You'll need to create an OAuth 2.0 Client ID in Google Cloud Console and complete the consent flow once. The server handles token refresh after that.
6. **HubSpot MCP uses a Private App token,** not OAuth. Create a Private App in HubSpot Settings → Integrations → Private Apps. Grant it scopes: `crm.objects.contacts.read`, `crm.objects.deals.read`, `crm.objects.companies.read`, `crm.objects.deals.write` (for note creation).
7. **ChromaDB** persists to disk by default with `PersistentClient`. Your indexed playbooks survive restarts.
8. **Slack thread_ts** is your thread identifier. All replies in a roleplay go to the same thread_ts.
9. **OpenRouter model strings** use the format `provider/model-name`. The default is `anthropic/claude-sonnet-4.5`. To experiment, change the `OPENROUTER_DEFAULT_MODEL` env var — no code changes needed. Browse available models at https://openrouter.ai/models.
10. **OpenRouter adds ~100-200ms latency** (proxy hop). Negligible for a Slack bot where users expect 5-15 second responses.
11. **Tool-calling quality varies by model.** Claude Sonnet is top-tier for tool use. If you swap to DeepSeek or Qwen and the agent stops calling MCP tools correctly, it's the model, not your code. Test tool-heavy workflows (like `/research` which chains HubSpot + Tavily + RAG) before switching models for those flows.
12. **HuggingFace embeddings — first run downloads the model.** `all-MiniLM-L6-v2` is 80MB. The first `embed_query()` call downloads it to `~/.cache/huggingface/`. Subsequent runs use the cached model. No API key needed.
13. **Tavily free tier** is 1,000 searches/month. Plenty for a POC.
14. **Block Kit formatting** in Slack uses `mrkdwn` (Slack's markdown), not standard markdown. Bold is `*text*`, not `**text**`.
15. **BigQuery is optional for the POC.** If the BigQuery MCP setup is slow, skip it — the demo works without analytics. Add it in Week 3 if time permits.
16. **`langchain-mcp-adapters` is async.** The `get_mcp_tools()` function is `async`. Use `asyncio.run()` at startup (see Section 9) or run the whole Slack app with an async event loop.
17. **Do NOT use `langchain-anthropic` or direct `ANTHROPIC_API_KEY`.** All LLM calls go through OpenRouter via `langchain-openai`'s `ChatOpenAI` with `base_url="https://openrouter.ai/api/v1"`. This is intentional — it gives us model flexibility.

---

*This briefing was generated from extensive brainstorming sessions. The full context lives in `brainstorm-sales-agents.md`. Reference it if you need deeper architectural rationale for any decision.*
