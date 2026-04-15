# UX Phase 2.1 — Threading Strategy & Progressive Disclosure

This instruction covers two related improvements: keeping conversation flows organized via threads, and reducing information overload via progressive disclosure.

---

## Part A: Threading Strategy

### Problem
Every action response (deal detail, email draft, roleplay debrief) is posted as a new top-level message in the channel. After a 10-minute demo, the channel is a long scroll of disconnected cards. Slack's design guide says: "Use threads to keep conversations organized."

### The Rule
When a user clicks a button on Card A and we generate Card B, Card B should be posted **as a threaded reply** to Card A (or to the loading message that replaced Card A).

### Implementation

#### Step 1: Pass `thread_ts` Through Action Handlers

Every action handler has access to the original message's `ts` via `body["message"]["ts"]`. After collapsing the original message (Phase 1.2), post the NEW response as a reply:

```python
# In every action handler that generates a follow-up card:
channel = body["channel"]["id"]
message_ts = body["message"]["ts"]  # This becomes thread_ts

# Phase 1.2: collapse the original card
collapse_message(client, channel, message_ts, ORIGINAL_TITLE, ACTION_SUMMARY)

# ... do work, generate blocks/fallback ...

# Post the new card IN THE THREAD of the original message
client.chat_postMessage(
    channel=channel,
    thread_ts=message_ts,
    text=fallback,
    blocks=blocks,
)
```

#### Step 2: Which Handlers to Thread

**Thread these action handlers** (they generate follow-up cards from a parent card):

| Parent Card | Action | Follow-Up Card | Handler |
|-------------|--------|----------------|---------|
| Research Brief | "Draft Follow-Up Email" | Contact Picker | `draft_email_from_research` |
| Research Brief | "Start Roleplay" | Roleplay Start | `start_roleplay_from_research` |
| Deal Picker | "Open Deal" | Deal Detail | `view_deal_detail` |
| Deal Detail | "Draft Email" | Contact Picker or Email Draft | `draft_email_from_deal` |
| Deal Detail | "Full Research" | Research Brief | `research_from_deal` |
| Deal Detail | "← Back to Results" | Deal Picker | `back_to_deal_results` |
| Contact Picker | Select contact | Email Draft | `select_email_contact` |
| Deal Selection (email) | Select deal | Contact Picker | `select_email_deal` |
| Pipeline Health | "Drill into Flagged Deal" | Deal Detail | `drill_flagged_deal` |
| Pipeline Health | "Refresh Pipeline" | Pipeline Health (refreshed) | `refresh_pipeline` |
| Roleplay Debrief | "Practice Again" | Roleplay Start | `practice_again` |
| Roleplay Debrief | "Try Suggested" | Roleplay Start | `try_suggested` |
| Objection Response | "Practice This Objection" | Roleplay Start | `practice_objection` |
| Battlecard | "Practice" | Roleplay Start | `battlecard_practice` |
| Persona | "Draft Email" | Email Draft | `draft_email_from_persona` |
| Persona | "Start Roleplay" | Roleplay Start | `roleplay_from_persona` |
| Handoff | "View Deal Card" | Deal Detail | `view_deal_from_handoff` |
| Handoff | "Draft Introduction Email" | Email Draft | `draft_handoff_email` |

**Do NOT thread these** (they are top-level slash commands that start new flows):
- `/research`, `/deal`, `/pipeline`, `/ask`, `/objection`, `/coach`, `/competitor`, `/battlecard`, `/followup`, `/forecast`, `/persona`, `/draft-email`, `/email-sequence`, `/handoff`, `/win-loss`, `/alerts`

These stay as top-level channel messages.

#### Step 3: Roleplay Special Case

Roleplay messages are already conversational (back-and-forth). The roleplay flow should work like this:
1. `/coach roleplay` → top-level message (roleplay start card)
2. User types response → processed by `handle_roleplay_response` → reply in thread of the roleplay start
3. AI coach responds → reply in same thread
4. Debrief → reply in same thread
5. "Practice Again" from debrief → NEW top-level message (fresh start)

The `handle_roleplay_response` (line ~2221 in app.py) already has `thread_ts` logic for active roleplay sessions. Verify this works correctly and doesn't break.

#### Step 4: Thread-Aware Loading Messages

When using the Phase 1.1 loading → update pattern inside a thread, the loading message should also be in the thread:

```python
loading_msg = client.chat_postMessage(
    channel=channel,
    thread_ts=message_ts,  # Keep it in the thread
    text=f"⏳ Researching *{company}*... this takes about 15 seconds."
)
loading_ts = loading_msg["ts"]

# ... do work ...

client.chat_update(
    channel=channel,
    ts=loading_ts,
    text=fallback,
    blocks=blocks,
)
```

---

## Part B: Progressive Disclosure

### Problem
`/research` returns 10+ blocks with contacts, deals, news, talking points all at once. `/handoff` returns deal story, contacts, competitors, risks, next steps. This is overwhelming, especially on mobile. Slack says: "Don't overload messages. Show what's essential."

### Strategy
Show a **compact summary** first, with a "Show Full Brief" button that expands the detail into the thread.

### Implementation for `/research`

#### Step 1: Create `format_research_summary()` in `formatters/research.py`

Add a new function that returns a compact 4-block summary:

```python
def format_research_summary(company_name, company_data, contacts, deals, news, talking_points):
    """Compact research summary — the first thing the user sees."""
    industry = company_data.get("industry", "N/A")
    size = company_data.get("size", "N/A")
    revenue = company_data.get("revenue", "N/A")

    # One-line summaries
    contact_summary = f"{len(contacts)} contact{'s' if len(contacts) != 1 else ''}"
    deal_summary = f"{len(deals)} active deal{'s' if len(deals) != 1 else ''}"
    news_summary = f"{len(news)} recent article{'s' if len(news) != 1 else ''}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Research Brief: {company_name}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Industry:* {industry}"},
                {"type": "mrkdwn", "text": f"*Size:* {size} employees"},
                {"type": "mrkdwn", "text": f"*Revenue:* {revenue}"},
                {"type": "mrkdwn", "text": f"*Data:* {contact_summary} · {deal_summary} · {news_summary}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Top Talking Point:* {talking_points.split(chr(10))[0][:200] if talking_points else 'N/A'}"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Show Full Brief", "emoji": True},
                    "action_id": "expand_research",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Follow-Up Email", "emoji": True},
                    "action_id": "draft_email_from_research",
                    "value": company_name,
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Roleplay", "emoji": True},
                    "action_id": "start_roleplay_from_research",
                    "value": company_name,
                },
            ]
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}
            ]
        },
    ]

    fallback = (
        f"Research Brief: {company_name}. "
        f"Industry: {industry}. Size: {size}. Revenue: {revenue}. "
        f"{contact_summary}, {deal_summary}, {news_summary}."
    )

    return blocks, fallback
```

#### Step 2: Update `/research` Handler

In the `/research` handler (app.py line ~487), change the formatter call:

```python
# BEFORE:
blocks, fallback = format_research_response(company_name, company_data, contacts, deals, news, talking_points)

# AFTER:
blocks, fallback = format_research_summary(company_name, company_data, contacts, deals, news, talking_points)
```

Import `format_research_summary` from `formatters.research`.

#### Step 3: Add `expand_research` Action Handler

In `app.py`, add a new action handler:

```python
@app.action("expand_research")
def handle_expand_research(ack, body, client):
    ack()
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    company_name = body["actions"][0]["value"]

    # Look up cached research data
    user_id = body["user"]["id"]
    cache_key = f"research_{user_id}_{company_name}"
    cached = research_cache.get(cache_key)

    if not cached:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ Research data for {company_name} has expired. Run `/research {company_name}` again."
        )
        return

    # Get the full blocks
    blocks, fallback = format_research_response(
        company_name,
        cached["company_data"],
        cached["contacts"],
        cached["deals"],
        cached["news"],
        cached["talking_points"],
    )

    # Post full research as a threaded reply
    client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=fallback,
        blocks=blocks,
    )
```

#### Step 4: Cache Research Data

In the `/research` handler, after generating the data but before formatting, cache it:

```python
# Add near the top of app.py:
research_cache = {}  # Simple in-memory cache: {cache_key: {company_data, contacts, deals, news, talking_points}}

# In the /research handler, after data extraction:
cache_key = f"research_{user_id}_{company_name}"
research_cache[cache_key] = {
    "company_data": company_data,
    "contacts": contacts,
    "deals": deals,
    "news": news,
    "talking_points": talking_points,
}
```

### Implementation for `/handoff`

Apply the same pattern:

#### Step 1: Create `format_handoff_summary()` in `formatters/handoff.py`

Compact version showing: deal name, company, stage, value, close date, contact count, and a "Show Full Handoff Brief" button.

```python
def format_handoff_summary(deal_name, deal_data, contacts, story, competitors, risks, next_steps):
    """Compact handoff summary."""
    company = deal_data.get("company", "N/A")
    stage = deal_data.get("stage", "N/A")
    value = format_currency(deal_data.get("amount", 0))
    close_date = deal_data.get("close_date", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Deal Handoff: {deal_name}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:* {company}"},
                {"type": "mrkdwn", "text": f"*Stage:* {stage}"},
                {"type": "mrkdwn", "text": f"*Value:* {value}"},
                {"type": "mrkdwn", "text": f"*Close:* {close_date}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{len(contacts)} contacts* · *{len(risks)} risks* · *{len(next_steps)} next steps*"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Show Full Handoff Brief", "emoji": True},
                    "action_id": "expand_handoff",
                    "value": deal_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal Card", "emoji": True},
                    "action_id": "view_deal_from_handoff",
                    "value": deal_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Introduction Email", "emoji": True},
                    "action_id": "draft_handoff_email",
                    "value": deal_name,
                },
            ]
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}]
        },
    ]

    fallback = f"Deal Handoff: {deal_name} — {stage} — {value}"
    return blocks, fallback
```

#### Step 2: Add `expand_handoff` Action Handler

Same pattern as `expand_research` — post full handoff blocks as a threaded reply using cached data.

### Implementation for `/pipeline`

The pipeline card is already fairly compact, but the "Flagged Deals" section can get long. Instead of progressive disclosure, use **inline truncation**:

- Show at most 3 flagged deals in the main card
- If there are more, add a line: `"... and {n} more flagged deals"` with the "Drill into Flagged Deal" button

```python
# In formatters/pipeline.py, limit flagged deals displayed:
MAX_FLAGGED_DISPLAY = 3

# When building flagged deals text:
displayed_flagged = flagged_deals[:MAX_FLAGGED_DISPLAY]
# ... build text for displayed_flagged ...

if len(flagged_deals) > MAX_FLAGGED_DISPLAY:
    remaining = len(flagged_deals) - MAX_FLAGGED_DISPLAY
    flagged_text += f"\n_... and {remaining} more flagged deal{'s' if remaining != 1 else ''}_"
```

---

## DO NOT
- Do not thread slash command responses — only thread action-triggered follow-ups
- Do not remove the full `format_research_response` function — it's still used by `expand_research`
- Do not break the roleplay threading that already exists
- Do not thread Home tab action responses (they don't have a parent message)
- Do not cache data indefinitely — consider adding a TTL or max cache size in production

## Testing
1. `/research NovaTech` → compact summary appears → click "Show Full Brief" → full research appears in thread
2. Click "Draft Follow-Up Email" on research summary → research summary collapses → contact picker appears in thread
3. `/pipeline` → click "Drill into Flagged Deal" → pipeline collapses → deal card appears in thread
4. `/handoff NovaTech` → compact summary → "Show Full Handoff Brief" → full brief in thread
5. Verify roleplay still works correctly (messages stay in thread of roleplay start)
6. Verify "Practice Again" from debrief starts a new top-level message
