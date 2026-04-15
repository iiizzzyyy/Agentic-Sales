# Bug Fix Log - Action Handlers

**Date:** 2026-04-14  
**Issue:** "View All Flagged Deals" button, "Research Company" button, and "Log a Note" overflow action not working

## Root Causes Found

### 1. `view_all_flagged_deals` handler - KeyError on ephemeral messages
**Location:** `app.py:2687`  
**Problem:** Handler tried to access `body["message"]["ts"]` but ephemeral messages store timestamp in `body["container"]["message_ts"]`  
**Fix:** Check container type first:
```python
container = body.get("container", {})
if container.get("type") == "ephemeral_message":
    message_ts = container.get("message_ts")
else:
    message_ts = body.get("message", {}).get("ts") or container.get("message_ts")
```

### 2. `research_from_deal_direct` handler - Wrong import
**Location:** `app.py:6608`  
**Problem:** Tried to import `extract_company_data, extract_contacts, extract_deals` from `tools.mock_crm` but these functions are defined in `app.py`  
**Problem 2:** Parsed `talking_points` as a list but `format_research_summary` expects a string  
**Fix:** 
- Remove the incorrect import line
- Use existing `parse_talking_points(llm_response)` function which returns a string

### 3. `deal_overflow` handler - Same issues as #2
**Location:** `app.py:3030`  
**Problem:** Same wrong import and talking_points type error  
**Fix:** Same as #2

### 4. Duplicate `@app.action("log_note")` handlers
**Location:** `app.py:2227` and `app.py:6373`  
**Problem:** Two handlers registered for same action - Slack Bolt uses only the last one registered, causing unpredictable behavior  
**Fix:** Removed the old handler at line 2227 and its view handler `@view("submit_note")`. Kept the newer one at line 6373 which properly handles both direct button clicks and overflow menu selections.

### 5. `deal_overflow` "Log a Note" action showing command hint instead of opening modal
**Location:** `app.py:3101`  
**Problem:** Original code just told user to use `/deal ... note:` command  
**Fix:** Updated to call `client.views_open()` with the `log_note_modal` callback

## Key Patterns to Remember

### Ephemeral Message Action Handling
When handling button clicks from ephemeral messages (like `/pipeline` or `/deal` output):
```python
# ALWAYS check container for ephemeral messages
container = body.get("container", {})
if container.get("type") == "ephemeral_message":
    message_ts = container.get("message_ts")  # NOT body["message"]["ts"]
```

### Import Locations
- `extract_company_data`, `extract_contacts`, `extract_deals` → defined in `app.py`
- `parse_talking_points`, `parse_recommendations` → defined in `app.py`
- `format_*` functions → in `formatters/*.py`
- CRM write operations → `tools/crm_write.py`

### Talking Points Format
- `parse_talking_points(llm_response)` returns a **string**
- `format_research_summary` expects `talking_points: str`
- Do NOT parse talking_points as a list

### No Duplicate Handlers
- Only ONE `@app.action("action_id")` per action
- Slack Bolt uses the last registered handler silently
- Before adding a new handler, grep for existing ones

## Files Modified
- `app.py` - Fixed handlers: `view_all_flagged_deals`, `research_from_deal_direct`, `deal_overflow`, removed duplicate `log_note`

## Testing Checklist
Before claiming a fix is complete:
- [ ] Test button from ephemeral message (e.g., `/pipeline` → "View All Flagged Deals")
- [ ] Test button from deal card (e.g., `/deal X` → "Research Company")
- [ ] Test overflow menu actions (e.g., `/deal X` → ⋮ → "Log a Note")
- [ ] Check Slack DMs for confirmation messages
- [ ] Check app logs for errors

## Known Limitations

### Notes Saved to Mock CRM, Not HubSpot
**Status:** Expected behavior in current setup  
**Reason:** MCP servers fail to load at startup (`Skipping hubspot — continuing without it`), so the app uses mock CRM data for lookups. When `create_note` is called, it receives mock deal IDs (e.g., `deal_992410`) instead of real HubSpot IDs. The HubSpot SDK call fails because the deal doesn't exist in HubSpot, so it falls back to mock mode and saves to `data/mock_crm/deals.json`.

**To fix this:**
1. Debug why MCP servers fail to load (langchain-mcp-adapters compatibility issue)
2. Or: Ensure real HubSpot deal IDs are used when looking up deals (requires MCP working)

**Workaround:** Notes ARE being saved — just to local mock CRM. Check `data/mock_crm/deals.json` to see logged notes.
