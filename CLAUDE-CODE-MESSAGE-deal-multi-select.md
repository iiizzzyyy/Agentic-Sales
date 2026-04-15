# Task: Implement Multi-Deal Selection for `/deal` Command

Read `DEAL-MULTI-SELECT-INSTRUCTIONS.md` for the full spec. Here's the summary:

## What to build

When a user types `/deal Horizon Education` and there are **multiple deals** matching that search, show a **deal picker** instead of jumping to a single deal card. The flow:

1. `/deal Horizon Education` → search RAG for matching deals
2. **1 match** → show deal card directly (existing behavior, no change)
3. **2+ matches** → show a deal picker list: each deal as a row with name, stage, amount, close date, and a "View Details" button
4. User clicks "View Details" → **update the message in place** (using `client.chat_update()`, NOT `say()`) to show the full deal card with all details + a "← Back to Results" button
5. User clicks "← Back to Results" → `chat_update()` swaps the message back to the picker list

## Files to change

### 1. `formatters/deal.py`
- Add `import json` at the top
- Add new function `format_deal_picker(search_term, deals)` that renders the multi-deal list view — each deal is a `section` block with a "View Details" button accessory. The button value should be `json.dumps({"deal_name": ..., "deal_id": ..., "search_term": ...})`
- Update existing `format_deal_response()` — add optional `search_term=None` parameter. When provided, prepend a "← Back to Results" button (action_id: `back_to_deal_results`, value: search_term) to the action buttons list

### 2. `formatters/__init__.py`
- Add `format_deal_picker` to imports and `__all__`

### 3. `app.py`
- Add `extract_all_matching_deals(search_term)` helper function near the existing `extract_deal_data()`. It should call `search_crm_deals(search_term, n_results=10)`, parse ALL matching deals (not just the first), deduplicate by name, and return a list of `{id, name, stage, amount, close_date}` dicts
- Update `handle_deal()` command handler: call `extract_all_matching_deals()` first, check the count:
  - 0 matches → fall back to LLM graph (existing behavior)
  - 1 match → show deal card directly (existing behavior)
  - 2+ matches → call `format_deal_picker()` and show the picker
- Add action handler `@app.action("view_deal_detail")` — parse the button value JSON, get the deal_name and search_term, call `extract_deal_data(deal_name)`, run the LLM graph for recommendations, then call `client.chat_update()` (NOT `say()`) to replace the picker message with the full deal card. Pass `search_term=search_term` to `format_deal_response()` so it includes the back button
- Add action handler `@app.action("back_to_deal_results")` — get the search_term from button value, call `extract_all_matching_deals(search_term)`, format with `format_deal_picker()`, then call `client.chat_update()` to replace the deal card back with the picker

## Critical implementation details

- **Use `client.chat_update(channel=channel, ts=message_ts, text=fallback, blocks=blocks)` for navigation** — this replaces the message content in place. Get `message_ts` from `body["message"]["ts"]` in action handlers. Never use `say()` for the view/back navigation.
- **Button value limit is 2000 chars** — keep button values small (just deal_name, deal_id, search_term)
- **Include `client` in action handler function signatures** — Slack Bolt auto-injects it (same pattern as the existing `log_note` handler)
- **Deduplicate deals by name** in `extract_all_matching_deals()` — RAG chunks may return the same deal multiple times
- **If more than 15 deals match**, truncate the list and add a context note "Showing 15 of N deals" (Slack has a 50-block limit per message)
