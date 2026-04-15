# Migration Instructions: Direct API → MCP

> **Context:** You already built code based on the original `CLAUDE-CODE-BRIEFING.md` which used direct API wrappers (`tools/hubspot.py`, `tools/bigquery.py`, `tools/gmail.py`). The briefing has been updated — we're switching to MCP (Model Context Protocol) servers instead. This document tells you exactly what to change.
>
> **Read the updated `CLAUDE-CODE-BRIEFING.md` first** — specifically Sections 2, 3, 5, 9, 12, 13, and 16. Then come back here for the step-by-step migration.

---

## WHAT CHANGED AND WHY

We replaced direct Python API wrappers with MCP servers for HubSpot, BigQuery, and Gmail. Reasons:

1. **Zero throwaway code** — the MCP integration carries forward to production unchanged
2. **Pilot-ready** — reps can actually use the bot with real CRM/email during pilot
3. **Less code to maintain** — MCP servers expose tools automatically; no manual wrapper functions
4. **Industry standard** — MCP is the open protocol by Anthropic, adopted by Google, HubSpot, etc.

The `langchain-mcp-adapters` library bridges MCP tools into LangGraph seamlessly. From LangGraph's perspective, MCP tools look identical to regular Python tool functions.

---

## STEP-BY-STEP MIGRATION

### Step 1: Delete the old direct API tool files

Remove these files (they're replaced by MCP servers):

```bash
rm -f tools/hubspot.py
rm -f tools/bigquery.py
rm -f tools/gmail.py
```

Keep these files — they are NOT changing:
- `tools/web_search.py` (Tavily stays as direct API — too simple for MCP)
- `tools/rag.py` (ChromaDB stays as-is)
- `tools/__init__.py` (update imports — see Step 5)

### Step 2: Install new dependencies

**Python — add to `requirements.txt`:**
```
langchain-mcp-adapters>=0.1.0
```

**Python — remove from `requirements.txt` (if present):**
```
hubspot-api-client
google-cloud-bigquery
```

**Run:**
```bash
pip install langchain-mcp-adapters
```

**Node.js — install MCP servers:**
```bash
# HubSpot MCP Server (official)
npm install -g @hubspot/mcp-server

# Gmail MCP Server (community — shinzo-labs)
git clone https://github.com/shinzo-labs/gmail-mcp.git
cd gmail-mcp && npm install && npm run build
cd ..

# BigQuery — if using local server:
npm install -g mcp-server-bigquery
```

### Step 3: Update `.env`

Add these new variables (if not already present):

```bash
# Gmail OAuth (for Gmail MCP server — NOT a simple API key)
GMAIL_CLIENT_ID=your-google-oauth-client-id
GMAIL_CLIENT_SECRET=your-google-oauth-client-secret
```

These should already exist but verify they're there:
```bash
HUBSPOT_ACCESS_TOKEN=pat-your-private-app-token
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=your-dataset-name
```

### Step 4: Create `mcp_setup.py` (NEW FILE — core of the migration)

Create this file in the project root:

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
    # BigQuery: configure as stdio with local server
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
```

### Step 5: Update `app.py` — load MCP tools at startup

Find wherever you currently import or initialize HubSpot/BigQuery/Gmail tools. Replace that with:

```python
import asyncio
from mcp_setup import get_mcp_tools

# Load MCP tools once at startup (before Slack handler starts)
print("Loading MCP tools...")
mcp_tools = asyncio.run(get_mcp_tools())
print(f"Loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}")

# Pass mcp_tools to your graph builders
from graphs import build_main_graph
app_graph = build_main_graph(mcp_tools)
```

**IMPORTANT:** Print the tool names on first run. MCP tool names are auto-discovered and may differ from what you hardcoded. For example:
- HubSpot might expose `search_crm_objects` instead of `search_contacts`
- Gmail might use `gmail_send` instead of `send_email`

Adapt your code to the actual names.

### Step 6: Update graph files to use MCP tools instead of imported functions

**Before (old pattern — direct API):**
```python
# graphs/assistant.py
from tools.hubspot import search_company, get_deals, get_contacts
from tools.gmail import create_draft

tools = [search_company, get_deals, get_contacts, create_draft, web_search, rag_search]
llm_with_tools = ChatAnthropic(model="claude-sonnet-4-5-20250929").bind_tools(tools)
```

**After (new pattern — MCP):**
```python
# graphs/assistant.py
from tools.web_search import search_company_news
from tools.rag import search as rag_search

def build_assistant_graph(mcp_tools):
    """Build the assistant graph with MCP tools + direct tools."""
    # Combine MCP tools (HubSpot, Gmail, BigQuery) with direct tools (Tavily, RAG)
    all_tools = mcp_tools + [search_company_news, rag_search]

    llm_with_tools = ChatAnthropic(model="claude-sonnet-4-5-20250929").bind_tools(all_tools)

    # ... rest of graph definition using llm_with_tools ...
```

Apply the same pattern to `graphs/coach.py` and `graphs/router.py` — anywhere you previously imported from `tools/hubspot.py`, `tools/bigquery.py`, or `tools/gmail.py`, replace with the `mcp_tools` parameter.

### Step 7: Update `tools/__init__.py`

Remove any imports of the deleted tool files:

```python
# REMOVE these lines:
# from tools.hubspot import ...
# from tools.bigquery import ...
# from tools.gmail import ...

# KEEP these:
from tools.web_search import search_company_news
from tools.rag import search as rag_search
```

### Step 8: Update any hardcoded tool calls in prompts or graph nodes

Search your codebase for any place where you call HubSpot/BigQuery/Gmail tools by name. For example:

```bash
# Find all references to old tool functions
grep -rn "hubspot\|bigquery\|gmail" graphs/ tools/ prompts/ app.py
```

MCP tools are called by the LLM through the standard LangGraph tool-calling mechanism — the same way as before. The LLM sees the tool name and schema, decides to call it, and LangGraph executes it. You do NOT need to change how the LLM invokes tools. You only need to change how tools are **loaded and passed to the LLM**.

If you have any graph nodes that directly call tool functions (not through the LLM), those need updating:

**Before:**
```python
# Direct function call
result = search_company("Acme Corp")
```

**After:**
```python
# Let the LLM call it through tool-use, OR use the MCP tool directly:
# Find the tool by name from the mcp_tools list
hubspot_search = next(t for t in mcp_tools if "search" in t.name and "contact" in t.name)
result = await hubspot_search.ainvoke({"query": "Acme Corp"})
```

But ideally, let the LLM handle tool selection — that's the whole point of MCP + LangGraph.

---

## VERIFICATION CHECKLIST

After migration, verify:

- [ ] `mcp_setup.py` exists and runs without errors
- [ ] `asyncio.run(get_mcp_tools())` returns a list of tools (print them)
- [ ] `tools/hubspot.py`, `tools/bigquery.py`, `tools/gmail.py` are deleted
- [ ] `requirements.txt` includes `langchain-mcp-adapters>=0.1.0`
- [ ] `requirements.txt` does NOT include `hubspot-api-client` or `google-cloud-bigquery`
- [ ] No remaining imports from deleted tool files (`grep -rn "from tools.hubspot\|from tools.bigquery\|from tools.gmail"`)
- [ ] All graph builders accept `mcp_tools` as a parameter
- [ ] `app.py` loads MCP tools at startup and passes them to graph builders
- [ ] `/deal [real deal]` still works end-to-end
- [ ] `/research [real company]` still works end-to-end
- [ ] MCP servers stay alive across multiple Slack commands (no restart per request)

---

## COMMON ISSUES

1. **"command not found: npx"** → Install Node.js v18+ (`nvm install 18`)
2. **MCP server fails to start** → Check that env vars are set in `.env`. The MCP server inherits env from the config, not from your shell.
3. **Tool names don't match** → Print `[t.name for t in mcp_tools]` and update any hardcoded references
4. **`async` errors** → `get_mcp_tools()` is async. Use `asyncio.run()` at startup. If your Slack app is already async, just `await` it instead.
5. **Gmail OAuth popup** → First run of Gmail MCP requires browser OAuth consent. Complete it once; the server handles refresh after that.
6. **BigQuery not working** → BigQuery MCP is optional for the POC. If setup is slow, comment out the `"bigquery"` entry in `MCP_SERVERS` and move on. The demo works without analytics.

---

## FILES CHANGED SUMMARY

| Action | File | What Changed |
|--------|------|-------------|
| DELETE | `tools/hubspot.py` | Replaced by HubSpot MCP Server |
| DELETE | `tools/bigquery.py` | Replaced by BigQuery MCP Server |
| DELETE | `tools/gmail.py` | Replaced by Gmail MCP Server |
| CREATE | `mcp_setup.py` | MCP server config + tool loading |
| EDIT | `app.py` | Load MCP tools at startup, pass to graphs |
| EDIT | `graphs/assistant.py` | Accept `mcp_tools` param, combine with direct tools |
| EDIT | `graphs/coach.py` | Accept `mcp_tools` param, combine with direct tools |
| EDIT | `graphs/router.py` | Minor — may need `mcp_tools` if it uses tools |
| EDIT | `tools/__init__.py` | Remove deleted imports |
| EDIT | `requirements.txt` | Add `langchain-mcp-adapters`, remove old SDKs |
| EDIT | `.env` | Add `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` |
