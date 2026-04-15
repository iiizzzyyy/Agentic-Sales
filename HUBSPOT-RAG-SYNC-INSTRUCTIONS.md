# Claude Code Instructions: Integrate HubSpot CRM Data into RAG

> **Read `CLAUDE-CODE-BRIEFING.md` first** (Sections 2, 9, 9B) if you haven't already.
> **Read `scripts/sync_hubspot_to_rag.py`** and `tools/rag.py` — these are already created/updated.

---

## CONTEXT — WHAT CHANGED AND WHY

We have a new script `scripts/sync_hubspot_to_rag.py` that pulls CRM data (companies, contacts, deals, notes) from HubSpot via MCP and indexes them into ChromaDB. The RAG module `tools/rag.py` has been updated with new search functions for CRM data types.

**The goal:** When a rep types `/research NovaTech`, the agent should pull context from BOTH playbooks (how to handle enterprise objections) AND CRM data (NovaTech is a 500-person fintech with a $75K deal in negotiation). Right now the graph nodes only call `rag_search()` generically — they need to also call the new CRM-specific search functions.

**New files already created (DO NOT recreate):**
- `scripts/sync_hubspot_to_rag.py` — fetches HubSpot CRM data via MCP, indexes into ChromaDB
- `tools/rag.py` — already updated with `search_crm()`, `search_crm_companies()`, `search_crm_contacts()`, `search_crm_deals()` functions

---

## STEP 1: Update `graphs/assistant.py` — Add CRM RAG to All Nodes

The file currently imports `from tools.rag import search as rag_search`. You need to also import the new CRM search functions and use them in each node.

### 1A. Update the import

Change:
```python
from tools.rag import search as rag_search
```

To:
```python
from tools.rag import search as rag_search, search_crm, search_crm_deals, search_crm_contacts
```

### 1B. Update `create_research_node` — add CRM RAG context

In the `research_node` inner function, after the existing `rag_context = rag_search(...)` line, add a CRM search:

```python
# Get RAG context (existing — keep this)
rag_context = rag_search(f"sales approach {company_name} ICP")

# NEW: Get CRM context from RAG (pre-synced HubSpot data)
crm_rag_context = search_crm(company_name)
```

Then inject `crm_rag_context` into BOTH the `use_mock` and `not use_mock` system prompts. Add this section to each prompt, right after the existing `PLAYBOOK CONTEXT:` section:

```
CRM DATA (from RAG):
{crm_rag_context}
```

For the mock branch, this gives richer context on top of the mock CRM data.
For the MCP branch, this gives the LLM pre-loaded CRM context so it makes fewer MCP tool calls (faster responses). The LLM can still call live HubSpot MCP tools if it needs real-time data.

### 1C. Update `create_deal_node` — add CRM RAG context

In the `deal_node` inner function, after `deal_name = extract_company_name(last_message)`, add:

```python
# Get deal and contact context from RAG (pre-synced HubSpot data)
deal_rag_context = search_crm_deals(deal_name)
contact_rag_context = search_crm_contacts(deal_name)
crm_rag_context = f"Deal matches:\n{deal_rag_context}\n\nRelated contacts:\n{contact_rag_context}"
```

Then inject `crm_rag_context` into both the `use_mock` and `not use_mock` system prompts. Add after existing data sections:

```
CRM DATA (from RAG):
{crm_rag_context}
```

For the MCP branch, this pre-loads deal context so the LLM has background before making any live MCP calls.

### 1D. Update `create_email_node` — add CRM RAG context

The email node already gets `rag_context` for email templates. Add CRM context for personalization:

After `rag_context = rag_search("follow-up email template sales")`, add:

```python
# NEW: Get CRM context for personalization
crm_rag_context = search_crm(company_name)
```

Then inject into both system prompts, after the existing `EMAIL TEMPLATE CONTEXT` section:

```
CRM DATA (from RAG):
{crm_rag_context}
```

### 1E. Update `create_pipeline_node` — add CRM RAG context

For the pipeline node, add a broad CRM search at the top of the function:

```python
# Get all deals from RAG for pipeline context
crm_rag_context = search_crm_deals("open deals pipeline")
```

Inject into both system prompts as:

```
CRM DEAL DATA (from RAG):
{crm_rag_context}
```

---

## STEP 2: Update `graphs/coach.py` — Add CRM RAG to Prep Node

### 2A. Update the import

Change:
```python
from tools.rag import search as rag_search
```

To:
```python
from tools.rag import search as rag_search, search_crm, search_crm_companies
```

### 2B. Update `create_prep_node` — add CRM RAG context

In the `prep_node` inner function, after the existing `rag_context = rag_search(...)` line, add:

```python
# NEW: Get CRM context for company background
crm_rag_context = search_crm(company_name)
```

Then inject into the system prompt. Add after the existing `PLAYBOOK CONTEXT (from RAG):` section:

```
CRM DATA (from RAG):
{crm_rag_context}
```

This gives the prep workflow company background, deal status, and contact info even before making live MCP calls.

### 2C. Roleplay and feedback nodes — NO changes needed

The `roleplay_node` and `feedback_node` don't need CRM data. They use playbook context (objection scripts, best practices) which is already working.

---

## STEP 3: Update `scripts/index_playbooks.py` — Optional CRM Sync Trigger

At the very end of the `main()` function in `scripts/index_playbooks.py`, add an optional CRM sync call. This way, running `python scripts/index_playbooks.py` indexes everything in one go.

Add these lines at the bottom of `main()`, after the existing summary printout:

```python
# Optional: sync HubSpot CRM data into RAG
print("\n--- HubSpot CRM Sync ---")
try:
    import asyncio
    from scripts.sync_hubspot_to_rag import sync_hubspot_to_rag
    asyncio.run(sync_hubspot_to_rag())
except Exception as e:
    print(f"CRM sync skipped: {e}")
    print("To sync CRM data separately, run: python scripts/sync_hubspot_to_rag.py")
```

**IMPORTANT:** This should NOT block playbook indexing if HubSpot isn't configured. The try/except ensures it fails gracefully.

---

## STEP 4: Verify Everything Works

### 4A. Test CRM RAG search functions

Run a quick Python check to verify the new RAG functions work:

```python
python -c "
from tools.rag import search_crm, search_crm_deals, search_crm_contacts, search_crm_companies, get_collection_stats
stats = get_collection_stats()
print(f'ChromaDB has {stats[\"total_chunks\"]} chunks')
print('CRM search test:', search_crm('test query')[:100])
"
```

If ChromaDB has no CRM data yet, the search will return "No CRM data found." — that's expected until you run the sync script.

### 4B. Test the sync script (requires HUBSPOT_ACCESS_TOKEN in .env)

```bash
python scripts/sync_hubspot_to_rag.py
```

If HUBSPOT_ACCESS_TOKEN isn't set, the script will error with instructions on how to get one. That's fine — for testing without HubSpot, the mock CRM data from `scripts/generate_test_data.py` already provides fallback data.

### 4C. Test the full flow

After syncing, test that the agent workflows use the CRM RAG data:

```bash
# Start the bot
python app.py
```

Then in Slack:
- `/research [company name from your HubSpot]` — should include CRM data in the brief
- `/deal [deal name from your HubSpot]` — should show deal details from RAG
- `/draft-email [company name]` — should personalize based on CRM context

---

## DUAL-SOURCE PATTERN — IMPORTANT

After this change, agent nodes get CRM data from TWO sources:

1. **RAG (pre-synced)** — fast, works offline, but may be stale. Loaded via `search_crm()`, `search_crm_deals()`, etc.
2. **Live MCP calls** — real-time, always current, but slower. The LLM calls HubSpot tools via `bind_tools()`.

**How they work together:**
- The RAG data is injected into the system prompt as static context (always available, instant)
- The MCP tools are bound to the LLM so it CAN call them if it needs fresher data
- For the mock branch (`use_mock=True`), only RAG is used (no MCP calls)
- For the MCP branch (`use_mock=False`), the LLM gets RAG context pre-loaded AND can make live MCP calls

**DO NOT remove the existing MCP tool-calling pattern.** The RAG enrichment is additive — it gives the LLM a head start but doesn't replace live tool access.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| ALREADY DONE | `scripts/sync_hubspot_to_rag.py` | New script — already created, do not recreate |
| ALREADY DONE | `tools/rag.py` | CRM search functions — already added, do not recreate |
| EDIT | `graphs/assistant.py` | Add CRM RAG imports + inject CRM context into all 4 node prompts (Steps 1A-1E) |
| EDIT | `graphs/coach.py` | Add CRM RAG imports + inject CRM context into prep_node prompt (Steps 2A-2B) |
| EDIT (optional) | `scripts/index_playbooks.py` | Add CRM sync trigger at end of main() (Step 3) |

---

## GOTCHAS

1. **Do NOT clear/recreate `tools/rag.py` or `scripts/sync_hubspot_to_rag.py`** — they're already done.

2. **The `search_crm()` function returns "No CRM data found."** if the sync hasn't been run yet. This is fine — the node prompts should handle this gracefully (the LLM will just work with whatever context it has).

3. **Import paths:** The CRM RAG functions are in `tools.rag`, same module as `search`. Import them explicitly: `from tools.rag import search as rag_search, search_crm, search_crm_deals, search_crm_contacts`.

4. **Do NOT make the system prompts too long.** Each CRM RAG section should be a concise block, not a dump of all records. The RAG functions already limit results (`n_results=5` default).

5. **The `crm_rag_context` variable name** should be distinct from `rag_context` (which is playbook context) and `crm_context` (which is mock CRM data in the `use_mock` branch). Use `crm_rag_context` to avoid confusion.

6. **Re-index ChromaDB from scratch** when testing: `rm -rf ./chroma_db && python scripts/index_playbooks.py && python scripts/sync_hubspot_to_rag.py`
