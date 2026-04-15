# Claude Code Task: Build 10 New Expansion Features (v2)

> **Read `CLAUDE-CODE-BRIEFING.md` and `app.py` first, then read each EXPANSION file before building it.**

---

## BUILD ORDER (optimized for dependencies and demo impact)

Build these features in EXACTLY this order. Each one builds on patterns from the previous.

### Phase 1: Instant-Response Commands (no LLM or simple LLM)

**1. `/battlecard` — Interactive Battle Card Viewer**
→ Read `EXPANSION-16-BATTLECARD.md`
- Parses `competitive_battle_cards.md` directly — NO LLM calls
- Fastest command to build and test (sub-second response)
- Add `parse_battle_cards()` to `tools/mock_crm.py`
- Creates `formatters/battlecard.py`

**2. `/alerts` — Proactive Pipeline Alerts**
→ Read `EXPANSION-15-PROACTIVE-ALERTS.md`
- Reuses `get_stale_deals()` and `get_overdue_deals()` from mock_crm
- Add `build_pipeline_alerts()` helper to `app.py`
- Creates `formatters/alerts.py`
- Background scheduler is COMMENTED OUT by default

### Phase 2: Data Analysis Commands (LLM + existing data)

**3. `/forecast` — AI Pipeline Forecast**
→ Read `EXPANSION-9-FORECAST.md`
- Add `STAGE_WIN_RATES` dict to `app.py`
- Uses `load_win_loss_analysis()` and `load_pipeline_analytics()` from mock_crm
- Creates `formatters/forecast.py`

**4. `/win-loss` — Win/Loss Analysis**
→ Read `EXPANSION-11-WIN-LOSS.md`
- Analyzes closed deals + CSV data
- Creates `formatters/win_loss.py`
- Depends on nothing new — uses existing mock_crm functions

**5. `/persona` — Buyer Persona Generator**
→ Read `EXPANSION-14-PERSONA.md`
- Uses ICP playbook via RAG + company CRM data
- Creates `formatters/persona.py`

### Phase 3: Multi-Step Commands (LLM + rich context)

**6. `/handoff` — Deal Handoff Brief**
→ Read `EXPANSION-10-HANDOFF.md`
- Loads ALL data for a deal: CRM, contacts, transcripts, emails, notes
- Creates `formatters/handoff.py`
- Heaviest data gathering of all commands

**7. `/email-sequence` — Multi-Touch Email Sequence**
→ Read `EXPANSION-13-EMAIL-SEQUENCE.md`
- Generates 4-email sequences with timing
- Creates `formatters/email_sequence.py`
- Uses regex action handlers (`re.compile()`)

### Phase 4: Interactive/Threaded Features

**8. `/coach-live` — Real-Time Call Coaching**
→ Read `EXPANSION-12-COACH-LIVE.md`
- Thread-based interactive coaching (like roleplay but for live calls)
- Add `active_live_coaching` dict to `app.py`
- Creates `formatters/coach_live.py` with 3 functions
- **IMPORTANT:** Add live coaching thread check BEFORE roleplay check in message handler

**9. Thread-Based Coaching Context**
→ Read `EXPANSION-17-THREAD-CONTEXT.md`
- Add `thread_contexts` dict and `save_thread_context()` helper
- Update message handler to detect context-aware thread replies
- **IMPORTANT:** Update ALL existing command handlers to save context after `say()`
- No new formatter — uses plain text thread replies

### Phase 5: Demo Meta-Feature (build LAST)

**10. `/demo-flow` — Guided Demo Walkthrough**
→ Read `EXPANSION-18-DEMO-FLOW.md`
- References ALL other command handlers — must be built last
- Creates `formatters/demo_flow.py` with `DEMO_STEPS` sequence
- `handle_demo_flow_next()` calls handlers programmatically

---

## PATTERNS TO FOLLOW

These patterns are already established in the codebase. Follow them exactly:

1. **Formatter pattern:**
   - Each command gets its own `formatters/xxx.py` file
   - Export function returns `tuple[list, str]` (blocks, fallback_text)
   - Add to `formatters/__init__.py` imports and `__all__`
   - Use `from formatters.helpers import timestamp, format_currency, truncate`

2. **Command handler pattern:**
   - `@app.command("/xxx")` with `ack()` first, then `say()` for loading message
   - Parse `command["text"]` for arguments
   - Load data from `mock_crm` → RAG search → LLM invoke → parse → format → say

3. **Action handler pattern:**
   - `@app.action("action_id")` with `ack()` first
   - Use `body["actions"][0]["value"]` for button value
   - Home tab buttons use `client.chat_postMessage(channel=user_id)` since they can't trigger slash commands

4. **LLM invoke pattern:**
   ```python
   result = app_graph.invoke({
       "messages": [HumanMessage(content=prompt)],
       "route": "assistant",  # or "coach" for coaching commands
       "workflow": "research",  # or "coach"
       "user_id": user_id,
       "channel_id": channel_id,
       "thread_ts": None,  # or thread_ts for threaded responses
   })
   answer = result["messages"][-1].content
   ```

5. **Thread interaction pattern** (for coach-live and thread context):
   - Check `event.get("thread_ts")` in message handler
   - Use `client.chat_postMessage(channel=channel, thread_ts=thread_ts)` for replies
   - Store state in module-level dicts (like `active_roleplays`)

---

## MESSAGE HANDLER ORDER (Critical!)

After building all features, the message event handler must check in THIS order:

```python
@app.event("message")
def handle_message(event, client, say):
    # 1. Skip bot messages
    if event.get("bot_id"):
        return

    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return

    # 2. Live coaching threads (EXPANSION-12)
    if thread_ts in active_live_coaching:
        # ... handle live coaching ...
        return

    # 3. Roleplay threads (existing)
    if thread_ts in active_roleplays:
        # ... handle roleplay ...
        return

    # 4. Context-aware thread replies (EXPANSION-17)
    if thread_ts in thread_contexts:
        # ... handle follow-up question ...
        return
```

---

## DO NOT

- Do NOT create new data files — all existing data in `data/mock_crm/` and `data/playbooks/` is sufficient
- Do NOT modify the LangGraph graph structure — use existing `app_graph.invoke()` pattern
- Do NOT add new Python dependencies unless absolutely necessary
- Do NOT change existing command behavior — only ADD new commands
- Do NOT forget to register commands in `formatters/__init__.py`
- Do NOT forget `ack()` at the top of every command/action handler

---

## TESTING CHECKLIST

After building all 10 features, test:
1. `/battlecard` (should be instant, no LLM)
2. `/battlecard CompetitorAlpha` (should show specific card)
3. `/alerts` (should show stale/overdue deals)
4. `/forecast` (should show 3 scenarios with insights)
5. `/win-loss` (should show patterns from CSV + deals)
6. `/persona NovaTech` (should generate buyer persona)
7. `/handoff NovaTech` (should generate handoff brief)
8. `/email-sequence NovaTech post-demo` (should generate 4 emails)
9. `/coach-live NovaTech discovery` then reply in thread, then "done"
10. Reply in thread under any `/deal` response — bot should answer with context
11. `/demo-flow` then click through all steps
