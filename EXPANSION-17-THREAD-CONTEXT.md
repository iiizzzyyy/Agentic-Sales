# Claude Code Instructions: Thread-Based Coaching Context

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/rag.py`, and `tools/mock_crm.py` first.**

---

## CONTEXT — WHAT AND WHY

When a rep gets a response from any bot command (e.g., `/deal NovaTech`, `/research Apex`), they often have follow-up questions. Currently, they'd need to run a new slash command. With thread-based context, the rep can simply reply in the thread and the bot continues the conversation with full context of what was shown.

Example:
1. Rep runs `/deal NovaTech` → bot shows deal card
2. Rep replies in thread: "what should I say about the discount they asked for?"
3. Bot responds with deal-aware coaching WITHOUT needing a new command

This makes the bot feel conversational and intelligent — a huge demo differentiator.

---

## WHAT IT DOES

1. Any bot response creates a "context anchor" — the thread_ts + what command/data was shown
2. When a user replies in a thread under a bot message, the bot:
   - Looks up what was originally shown (deal? research? pipeline?)
   - Loads relevant data for that context
   - Treats the reply as a follow-up question and responds with context-aware help
3. Works across ALL commands — no special setup per command

---

## STEP 1: Create the Thread Context Store

Add to `app.py` (near the other in-memory state dicts):

```python
# Thread context — maps thread_ts to the context of the original command
# Each entry: {"command": str, "data": dict, "channel_id": str, "user_id": str}
thread_contexts = {}

# Maximum threads to track (prevent memory leaks in POC)
MAX_THREAD_CONTEXTS = 100
```

---

## STEP 2: Add Context Saving After Every Command Response

Create a helper function that saves context when any command posts a response:

```python
def save_thread_context(thread_ts: str, command: str, data: dict, channel_id: str, user_id: str):
    """Save context for a thread so follow-up replies can be handled.

    Args:
        thread_ts: The message timestamp that anchors this thread
        command: Which command created this message (e.g., "deal", "research", "pipeline")
        data: Key context data (company name, deal name, etc.)
        channel_id: Channel where the message was posted
        user_id: User who ran the command
    """
    global thread_contexts

    # Evict oldest if at capacity
    if len(thread_contexts) >= MAX_THREAD_CONTEXTS:
        oldest_key = next(iter(thread_contexts))
        del thread_contexts[oldest_key]

    thread_contexts[thread_ts] = {
        "command": command,
        "data": data,
        "channel_id": channel_id,
        "user_id": user_id,
    }
```

Then, update EACH command handler to save context after posting. For example, in the `/deal` handler:

```python
# After say() in handle_deal:
result = say(text=fallback, blocks=blocks, channel=channel_id)
save_thread_context(
    thread_ts=result["ts"],
    command="deal",
    data={"deal_name": deal_name, "company_name": company_name, "deal_stage": stage, "deal_amount": amount},
    channel_id=channel_id,
    user_id=user_id,
)
```

Do the same for:
- `/research` → save `{"company_name": company_name}`
- `/pipeline` → save `{"view": "pipeline"}`
- `/forecast` → save `{"view": "forecast"}`
- `/objection` → save `{"objection": objection_text}`
- `/handoff` → save `{"deal_name": deal_name, "company_name": company_name}`
- etc.

**Pattern:** Capture the return value of `say()` to get the `ts`, then call `save_thread_context()`.

---

## STEP 3: Update the Message Event Handler

In the existing `@app.event("message")` handler, add a check for thread_contexts AFTER the roleplay and live coaching checks:

```python
# Inside the message event handler, add this after roleplay/live-coaching checks:

# Check if this is a follow-up in a context-aware thread
thread_ts = event.get("thread_ts")
if thread_ts and thread_ts in thread_contexts:
    ctx = thread_contexts[thread_ts]
    user_message = event.get("text", "").strip()
    channel = event.get("channel")
    user_id = event.get("user")

    # Don't respond to bot's own messages
    if event.get("bot_id"):
        return

    # Build context based on the original command
    command = ctx["command"]
    data = ctx["data"]
    context_parts = []

    # Load relevant data based on original command type
    if command == "deal":
        deal = mock_crm.search_deal(data.get("deal_name", ""))
        if deal:
            context_parts.append(f"DEAL CONTEXT: {mock_crm.format_deal_for_display(deal)}")

            # Also load company and contacts
            company_id = deal.get("associations", {}).get("company", "")
            company = mock_crm.get_company_by_id(company_id)
            if company:
                context_parts.append(f"COMPANY: {mock_crm.format_company_for_display(company)}")

            contacts = mock_crm.get_contacts_for_company(company_id) if company_id else []
            for c in contacts[:3]:
                context_parts.append(f"CONTACT: {mock_crm.format_contact_for_display(c)}")

    elif command == "research":
        company = mock_crm.search_company(data.get("company_name", ""))
        if company:
            context_parts.append(f"COMPANY: {mock_crm.format_company_for_display(company)}")
            company_id = company.get("id", "")
            deals = mock_crm.get_deals_for_company(company_id)
            for d in deals[:3]:
                context_parts.append(f"DEAL: {mock_crm.format_deal_for_display(d)}")

    elif command == "pipeline":
        open_deals = mock_crm.get_all_open_deals()
        context_parts.append(f"PIPELINE: {len(open_deals)} open deals")
        for d in open_deals[:5]:
            context_parts.append(f"DEAL: {mock_crm.format_deal_for_display(d)}")

    elif command == "objection":
        from tools.rag import search_playbooks
        objection_ctx = search_playbooks(f"objection handling {data.get('objection', '')}", n_results=5)
        context_parts.append(f"OBJECTION CONTEXT: {objection_ctx}")

    # Always add RAG search for the follow-up question
    from tools.rag import search_playbooks
    rag_results = search_playbooks(user_message, n_results=3)
    if rag_results:
        context_parts.append(f"PLAYBOOK CONTEXT: {rag_results}")

    combined_context = "\n\n".join(context_parts)

    # Run LLM with context
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""A sales rep previously ran the /{command} command and got results about: {json.dumps(data)}.

Now they're asking a follow-up question in the thread: "{user_message}"

AVAILABLE CONTEXT:
{combined_context}

Answer their follow-up question using the context above. Be specific and actionable.
If the question requires data you don't have, suggest the right command to get it.
Format with Slack mrkdwn. Keep it concise — this is a thread reply, not a full report.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel,
        "thread_ts": thread_ts,
    })

    answer = result["messages"][-1].content

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=answer,
    )
    return  # Don't fall through to other handlers
```

---

## STEP 4: No New Formatters Needed

Thread replies use simple text messages (not Block Kit), which keeps them lightweight and conversational. This is intentional — threads should feel like a chat, not a dashboard.

---

## GOTCHAS

1. **Message handler order is critical.** Check in this order:
   1. Skip bot messages (`if event.get("bot_id"): return`)
   2. Check `active_live_coaching` (EXPANSION-12)
   3. Check `active_roleplays` (existing)
   4. Check `thread_contexts` (this expansion)
   5. Fall through to any catch-all

2. **Memory management.** `thread_contexts` is capped at 100 entries. Oldest entries are evicted. For production, use Redis or a database.

3. **`say()` return value.** Every `say()` call returns a dict with `"ts"` (the message timestamp). You MUST capture this to save context. If the command uses `client.chat_postMessage()` instead, it also returns `"ts"`.

4. **Bot self-reply loop.** Always check `event.get("bot_id")` at the top of the message handler to avoid the bot replying to itself in threads.

5. **Context data should be small.** Only store key identifiers (deal_name, company_name), not full data blobs. The handler reloads fresh data when responding.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `app.py` | Add `thread_contexts` dict, `save_thread_context()` helper, update message handler, add `save_thread_context()` calls to ALL existing command handlers |

**No new files — this is an enhancement to the existing message event handler and all existing command handlers.**

The biggest change is adding `save_thread_context()` calls to every existing command handler. There are ~15+ handlers that need updating. Here's the pattern for each:

```python
# Before (existing):
say(text=fallback, blocks=blocks, channel=channel_id)

# After (updated):
result = say(text=fallback, blocks=blocks, channel=channel_id)
save_thread_context(result["ts"], "command_name", {"key": "value"}, channel_id, user_id)
```
