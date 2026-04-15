# Task: Build 5 New Slash Commands + Home Tab for SalesCoach AI Slack Bot

> **Read these files FIRST before writing any code:**
> 1. `CLAUDE-CODE-BRIEFING.md` — overall architecture, patterns, tech stack
> 2. `app.py` — current codebase (all existing handlers, formatters, patterns)
> 3. `formatters/__init__.py` — current exports
> 4. `formatters/pipeline.py` and `formatters/deal.py` — Block Kit patterns to follow
> 5. `tools/rag.py` — all RAG search functions available
> 6. `tools/mock_crm.py` — all mock CRM functions available
>
> Then read each EXPANSION instruction file below **immediately before** building that feature.

---

## BUILD ORDER (follow this exact sequence)

### Build 1: `/objection` — Instant Objection Handler
**Read:** `EXPANSION-4-OBJECTION.md`

Create:
- `formatters/objection.py` — `format_objection_response()` with "Say This", proof points, avoid list, pivot question
- In `app.py`: `handle_objection()` command handler — RAG-only (no web search, no MCP) for speed. Search `search_playbooks()` for objection handling + battle cards. LLM generates structured response (RESPONSE / PROOF_POINT / AVOID / PIVOT_QUESTION format). Parse into structured data.
- In `app.py`: `handle_practice_objection()` and `handle_expand_objection()` action handlers
- Update `formatters/__init__.py` with new export

**Test:** `/objection your pricing is too high` → should return Block Kit card with response script, proof points, avoid list, and pivot question in under 5 seconds.

---

### Build 2: `/ask` — Natural Language CRM Query
**Read:** `EXPANSION-7-ASK.md`

Create:
- `formatters/ask.py` — `format_ask_response()` with answer, data sources, related action buttons
- In `app.py`: `handle_ask()` command handler — keyword-based routing to determine which data sources to search (contacts, deals, pipeline aggregates, call transcripts, meeting notes, playbooks). Combine all context, send to LLM for natural language answer. Add contextual action buttons based on content.
- In `app.py`: `handle_noop()` catch-all action handler
- Update `formatters/__init__.py` with new export

**Key:** The handler uses keyword detection (NOT an LLM classifier) to decide what data to pull — check for words like "contact/who", "deal/pipeline/revenue", "call/meeting/note", "how to/playbook" in the question. Always do a broad `search_crm()` as baseline.

**Test:** `/ask What deals are closing this month?` → should return answer with specific deal names and amounts from CRM data.

---

### Build 3: Slack App Home Tab Dashboard
**Read:** `EXPANSION-8-HOME-TAB.md`

Create:
- `formatters/home_tab.py` — `format_home_tab()` returns blocks only (no fallback tuple). Includes: greeting, pipeline summary (4-field grid), deals needing attention (stale/overdue with "View Deal" buttons), coaching summary, quick-start action buttons for all commands, command reference.
- In `app.py`: `handle_app_home_opened()` event handler using `@app.event("app_home_opened")` — builds pipeline summary from `mock_crm.get_all_open_deals()`, `get_stale_deals()`, `get_overdue_deals()`. Calls `client.views_publish()` with `view={"type": "home", "blocks": blocks}`.
- In `app.py`: 7 action handlers for Home tab buttons: `home_view_deal`, `home_pipeline`, `home_followups`, `home_practice`, `home_scorecard`, `home_research`, `home_ask` — each posts a DM with the relevant `/command` suggestion.

**Important:** Do NOT run LLM calls in the Home tab handler — keep it fast, data-only. Use `client.users_info(user=user_id)` to get the user's first name for the greeting.

**Test:** Click on the SalesCoach bot in the Slack sidebar → Home tab should render with pipeline stats, flagged deals, and quick-start buttons.

---

### Build 4: `/followup` — Smart Follow-Up Reminders
**Read:** `EXPANSION-3-FOLLOWUP.md`

Create:
- `formatters/followup.py` — `format_followup_response()` with prioritized follow-up list. Each item: urgency emoji (🔴/🟡/🟢), deal name, reason, last touch, suggested action, draft snippet, and "Draft Email" button with JSON value.
- In `app.py`: `handle_followup()` command handler — get stale deals (7+ days) and overdue deals from mock_crm. Build candidates with urgency levels (overdue=high, stale=medium). Run LLM to generate personalized action + email opener for each deal (DEAL/ACTION/OPENER format). Parse and merge.
- In `app.py`: `parse_followup_suggestions()` helper — merges LLM output with candidate list using fuzzy name matching
- In `app.py`: `handle_draft_followup_email()` action handler — reuses existing email drafting logic
- In `app.py`: `handle_refresh_followups()` action handler
- Update `formatters/__init__.py` with new export

**Test:** `/followup` → should return prioritized list of stale/overdue deals with personalized follow-up actions and draft email openers.

---

### Build 5: `/competitor` — Real-Time Competitive Intelligence
**Read:** `EXPANSION-2-COMPETITOR.md`

Create:
- `formatters/competitor.py` — `format_competitor_response()` with positioning, strengths vs weaknesses (two-column), "When They Say → You Say" counter-arguments, recent news, deals at risk, talking points, and action buttons ("Start Roleplay vs This Competitor", "Draft Competitive Email").
- In `app.py`: `handle_competitor()` command handler — search RAG playbooks for battle cards (`search_playbooks` with competitor name), search CRM for notes mentioning competitor, run Tavily web search for recent news, run LLM to generate structured competitive brief (POSITIONING / STRENGTHS / WEAKNESSES / COUNTER-ARGUMENTS / TALKING POINTS).
- In `app.py`: `parse_competitor_response()` helper — parses LLM sections into structured data
- In `app.py`: `parse_news_items()` helper — parses web search results string into list of dicts
- In `app.py`: `find_deals_mentioning_competitor()` helper — searches CRM deals for competitor mentions
- In `app.py`: `handle_roleplay_competitor()` and `handle_draft_competitive_email()` action handlers
- Update `formatters/__init__.py` with new export

**Test:** `/competitor [any competitor name from battle cards playbook]` → should return competitive intel brief with live news, counter-arguments, and deals at risk.

---

## PATTERNS TO FOLLOW

1. **Every formatter** returns `tuple[list, str]` — `(blocks, fallback_text)` — except `format_home_tab` which returns just `list`.
2. **Every formatter file** imports from `formatters.helpers`: `timestamp`, `truncate`, `format_currency` as needed.
3. **Every command handler** calls `ack()` first, then `say("loading message...")`, then does work, then `say(text=fallback, blocks=blocks)`.
4. **Action handlers** use `body["actions"][0]["value"]` for button values, `body["channel"]["id"]` for channel, `body["user"]["id"]` for user.
5. **Button values** that need multiple fields use `json.dumps({...})` (max 2000 chars).
6. **LLM calls** go through `app_graph.invoke()` with `route="assistant"`, `workflow="research"` (or `"email"` for email-related).
7. **RAG searches** use the functions in `tools/rag.py` — `search_playbooks()`, `search_crm()`, `search_crm_deals()`, `search_crm_contacts()`, etc.
8. **Mock CRM** functions in `tools/mock_crm.py` — `search_company()`, `get_all_open_deals()`, `get_stale_deals()`, `get_overdue_deals()`, `get_contacts_for_company()`, `get_deals_for_company()`.

## REGISTER ALL NEW SLASH COMMANDS IN SLACK

After building, the user needs to register these 5 new slash commands at api.slack.com → Slash Commands:
- `/objection` — `Get instant response to a buyer objection` — hint: `[what they said]`
- `/ask` — `Ask anything about your CRM, deals, or pipeline` — hint: `[your question]`
- `/followup` — `Get smart follow-up recommendations` — hint: `[company name]`
- `/competitor` — `Get real-time competitive intelligence` — hint: `[competitor name]`

And enable Home Tab + `app_home_opened` event in App Home settings.

No new slash command registration needed for Home Tab (it's an event, not a command).

## DO NOT

- Do NOT modify existing commands or formatters (they work)
- Do NOT change the graph architecture (router, assistant, coach subgraphs)
- Do NOT add new dependencies to requirements.txt (everything needed is already installed)
- Do NOT use web search in `/objection` — RAG only for speed
- Do NOT run LLM calls in the Home Tab handler — data only for speed
