# Claude Code Instructions: Multi-Deal Selection for `/deal` Command

> **Read `app.py`**, `formatters/deal.py`, and `formatters/helpers.py` first.

---

## CONTEXT — WHAT AND WHY

Currently, `/deal Horizon Education` does a single `extract_deal_data()` lookup and shows one deal card. If there are multiple deals matching "Horizon Education" (e.g., "Horizon Education — Annual Platform License" AND "Horizon Education — Pilot Program"), the user only sees the first one.

**New behavior:**
1. User types `/deal Horizon Education`
2. Bot searches RAG for matching deals
3. **If 1 match** → show the deal card directly (existing behavior)
4. **If 2+ matches** → show a deal picker: a list of matching deals showing name, amount, stage, and close date, each with a "View" button
5. User clicks "View" on a deal → the message **updates in place** (using `chat_update`) to show the full deal card for that deal
6. The deal card includes a "← Back to Results" button
7. User clicks "← Back to Results" → the message updates back to the deal picker list

This uses Slack's `chat_update` API to replace message content in place, which feels like navigating between views rather than posting new messages.

---

## STEP 1: Create the Deal Picker Formatter

Add a new function to `formatters/deal.py` that renders the multi-deal picker view.

### Add `format_deal_picker()` to `formatters/deal.py`:

```python
def format_deal_picker(
    search_term: str,
    deals: list,
) -> tuple[list, str]:
    """Format a deal selection list when multiple deals match.

    Args:
        search_term: What the user searched for (e.g., "Horizon Education")
        deals: List of deal dicts, each with: name, amount, stage, close_date, id

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 Deals matching \"{search_term}\"", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Found {len(deals)} deals. Select one to view details."}
            ]
        },
        {"type": "divider"},
    ]

    for deal in deals:
        deal_name = deal.get("name", "Unknown Deal")
        stage = deal.get("stage", "N/A")
        amount = deal.get("amount", 0)
        close_date = deal.get("close_date", "N/A")
        deal_id = deal.get("id", "")

        # Get emoji for stage
        stage_key = stage.lower().replace(" ", "").replace("_", "")
        emoji = STAGE_EMOJI.get(stage_key, "📊")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{emoji} {deal_name}*\n{stage} • {format_currency(amount)} • Close: {close_date}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details", "emoji": True},
                "action_id": "view_deal_detail",
                "value": json.dumps({
                    "deal_name": deal_name,
                    "deal_id": deal_id,
                    "search_term": search_term,
                }),
            }
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}
        ]
    })

    fallback = f"Found {len(deals)} deals matching \"{search_term}\""
    return blocks, fallback
```

**IMPORTANT:** Add `import json` at the top of `formatters/deal.py` — it's needed for `json.dumps()` in the button value.

### Update `format_deal_response()` — add "Back to Results" button

Modify the existing `format_deal_response()` function to accept an optional `search_term` parameter. When provided, add a "← Back to Results" button to the action buttons.

Add the parameter to the function signature:

```python
def format_deal_response(
    deal: dict,
    contacts: list,
    activities: list,
    recommendations: str,
    search_term: str = None,  # NEW — when set, adds "Back to Results" button
) -> tuple[list, str]:
```

Then, in the action buttons `elements` list, conditionally prepend the back button:

```python
# Build action buttons
action_elements = []

# Add "Back to Results" button if this was opened from a multi-deal picker
if search_term:
    action_elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "← Back to Results", "emoji": True},
        "action_id": "back_to_deal_results",
        "value": search_term,
    })

# Existing buttons
action_elements.extend([
    {
        "type": "button",
        "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
        "action_id": "draft_email_from_deal",
        "value": company or deal_name,
    },
    {
        "type": "button",
        "text": {"type": "plain_text", "text": "Full Research", "emoji": True},
        "action_id": "research_from_deal",
        "value": company or deal_name,
    },
    {
        "type": "button",
        "text": {"type": "plain_text", "text": "Log Note", "emoji": True},
        "action_id": "log_note",
        "value": deal_id or deal_name,
    },
])
```

Then use `action_elements` in the actions block instead of the hardcoded list.

---

## STEP 2: Update `formatters/__init__.py`

Add the new function to exports:

```python
from formatters.deal import format_deal_response, format_deal_picker
```

And add `format_deal_picker` to `__all__`.

---

## STEP 3: Create `extract_all_deals()` Helper in `app.py`

Currently `extract_deal_data()` returns only the first matching deal. Add a new helper that returns ALL matching deals for the picker.

Add this function to `app.py` near the existing `extract_deal_data()`:

```python
def extract_all_matching_deals(search_term: str) -> list:
    """Extract ALL deals matching a search term from RAG.

    Returns a list of deal dicts, each with: name, amount, stage, close_date, id
    Used for the multi-deal picker when multiple deals match.
    """
    from tools.rag import search_crm_deals
    rag_result = search_crm_deals(search_term, n_results=10)

    deals = []
    seen_names = set()  # Deduplicate

    for doc in rag_result.split("---"):
        if "Deal:" not in doc:
            continue
        parsed = parse_rag_text(doc)
        name = parsed.get("deal", "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Parse amount
        amount = parsed.get("amount", "0")
        try:
            amount = float(amount.replace("$", "").replace(",", "")) if amount else 0
        except (ValueError, TypeError):
            amount = 0

        # Parse close date
        close_date = parsed.get("close_date", "N/A")
        if close_date and close_date != "N/A" and len(close_date) > 10:
            close_date = close_date[:10]

        # Extract hubspot_id
        hubspot_id = ""
        source_value = parsed.get("[crm_deal", "")
        if source_value and "hubspot_crm_deal_" in source_value:
            hubspot_id = source_value.replace("]", "").replace("hubspot_crm_deal_", "").strip()

        deals.append({
            "id": hubspot_id,
            "name": name,
            "stage": parsed.get("stage", "N/A"),
            "amount": amount,
            "close_date": close_date,
        })

    return deals
```

---

## STEP 4: Update the `/deal` Command Handler in `app.py`

Replace the current `handle_deal()` function with a version that checks for multiple matches.

The key change: instead of going straight to the LLM graph → deal card, first check how many deals match. If multiple, show the picker instead.

```python
@app.command("/deal")
def handle_deal(ack, say, command):
    """Look up a deal by name — shows picker if multiple matches."""
    ack()
    deal_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not deal_name:
        say("Please provide a deal or company name: `/deal [name]`")
        return

    say(f"Looking up deals matching *{deal_name}*...", channel=channel_id)

    # Check how many deals match
    matching_deals = extract_all_matching_deals(deal_name)

    if len(matching_deals) == 0:
        # No matches in RAG — fall back to LLM with MCP tools
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/deal {deal_name}")],
            "route": "assistant",
            "workflow": "deal",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })
        say(text=result["messages"][-1].content, channel=channel_id)

    elif len(matching_deals) == 1:
        # Exactly 1 match — show deal card directly (existing behavior)
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/deal {matching_deals[0]['name']}")],
            "route": "assistant",
            "workflow": "deal",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        deal_data, contacts, activities = extract_deal_data(matching_deals[0]["name"])
        llm_response = result["messages"][-1].content
        recommendations = parse_recommendations(llm_response)

        if deal_data:
            blocks, fallback = format_deal_response(
                deal=deal_data,
                contacts=contacts,
                activities=activities,
                recommendations=recommendations,
            )
            say(text=fallback, blocks=blocks, channel=channel_id)
        else:
            say(text=llm_response, channel=channel_id)

    else:
        # Multiple matches — show deal picker
        from formatters import format_deal_picker
        blocks, fallback = format_deal_picker(deal_name, matching_deals)
        say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 5: Add Action Handlers for Navigation

Add two new action handlers to `app.py`:

### 5A. `view_deal_detail` — User clicks "View Details" on a deal in the picker

This handler uses `client.chat_update()` to replace the picker message with the full deal card.

```python
@app.action("view_deal_detail")
def handle_view_deal_detail(ack, body, say, client):
    """User clicked 'View Details' on a deal in the picker — update message to show deal card."""
    ack()

    action_value = json.loads(body["actions"][0]["value"])
    deal_name = action_value["deal_name"]
    search_term = action_value["search_term"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]  # The picker message to update

    # Get full deal data
    deal_data, contacts, activities = extract_deal_data(deal_name)

    if not deal_data:
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"Could not load details for {deal_name}.",
        )
        return

    # Run LLM for recommendations
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/deal {deal_name}")],
        "route": "assistant",
        "workflow": "deal",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content
    recommendations = parse_recommendations(llm_response)

    # Format deal card WITH "Back to Results" button
    blocks, fallback = format_deal_response(
        deal=deal_data,
        contacts=contacts,
        activities=activities,
        recommendations=recommendations,
        search_term=search_term,  # This adds the back button
    )

    # Update the picker message in place (not a new message)
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )
```

### 5B. `back_to_deal_results` — User clicks "← Back to Results" on a deal card

This handler uses `client.chat_update()` to replace the deal card with the picker again.

```python
@app.action("back_to_deal_results")
def handle_back_to_results(ack, body, client):
    """User clicked '← Back to Results' — update message back to deal picker."""
    ack()

    search_term = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Re-search for matching deals
    matching_deals = extract_all_matching_deals(search_term)

    if not matching_deals:
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"No deals found matching \"{search_term}\".",
        )
        return

    from formatters import format_deal_picker
    blocks, fallback = format_deal_picker(search_term, matching_deals)

    # Update the message back to the picker
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )
```

---

## STEP 6: Register `client` in Action Handlers

The `view_deal_detail` and `back_to_deal_results` handlers use `client` (the Slack Web API client) for `chat_update`. Make sure these handlers include `client` in their function signature.

In Slack Bolt, `client` is automatically injected when you include it as a parameter. The existing `log_note` handler already does this — follow the same pattern.

**IMPORTANT:** `chat_update` requires the `chat:write` scope, which should already be enabled (it's needed for `say()` too).

---

## WHAT THE UX LOOKS LIKE

### Multiple deals found:
```
┌─────────────────────────────────────────────┐
│ 📊 Deals matching "Horizon Education"       │
│ Found 2 deals. Select one to view details.  │
│─────────────────────────────────────────────│
│ 🤝 Horizon Education — Annual Platform      │
│ Negotiation • $72,000 • Close: 2026-04-15  │
│                              [View Details] │
│─────────────────────────────────────────────│
│ 📺 Horizon Education — Pilot Program        │
│ Demo Scheduled • $24,000 • Close: 2026-05-01│
│                              [View Details] │
│─────────────────────────────────────────────│
│ SalesCoach AI • Mar 05, 2026 at 2:30 PM     │
└─────────────────────────────────────────────┘
```

### User clicks "View Details" → message updates to:
```
┌─────────────────────────────────────────────┐
│ 🤝 Horizon Education — Annual Platform      │
│─────────────────────────────────────────────│
│ Stage:        │ Amount:                      │
│ Negotiation   │ $72,000                      │
│ Close Date:   │ Owner:                       │
│ 2026-04-15    │ Jordan Mitchell              │
│─────────────────────────────────────────────│
│ Primary Contact:                             │
│ Sarah Chen — VP of Engineering               │
│ sarah.chen@horizonedu.org                    │
│─────────────────────────────────────────────│
│ Recent Activity:                             │
│ • 2026-02-28 — Negotiation call. 15% disc...│
│ • 2026-02-21 — Demo completed. Impressed...  │
│─────────────────────────────────────────────│
│ Recommended Next Actions:                    │
│ • Follow up with procurement on MSA status   │
│ • Send battle card to champion               │
│─────────────────────────────────────────────│
│ [← Back to Results] [Draft Email]            │
│ [Full Research] [Log Note]                   │
│─────────────────────────────────────────────│
│ SalesCoach AI • HubSpot data • Mar 05, 2026  │
└─────────────────────────────────────────────┘
```

### User clicks "← Back to Results" → message updates back to the picker.

---

## GOTCHAS

1. **`chat_update` vs `say`** — `say()` posts a NEW message. `chat_update()` replaces an EXISTING message in place. For the navigation pattern, always use `chat_update()` with the original message's `ts` (timestamp). The timestamp is the message ID in Slack.

2. **Button `value` size limit** — Slack limits button values to 2000 characters. The `json.dumps()` in `view_deal_detail` needs to stay small. Only include `deal_name`, `deal_id`, and `search_term` — don't put entire deal data in the value.

3. **Block Kit 50-block limit** — Each Slack message can have at most 50 blocks. With the picker format (header + context + divider + 1 section per deal + footer), you can show up to ~20 deals before hitting the limit. If there are more than 15 matches, truncate the list and add a "Showing 15 of N deals" note.

4. **`client` injection** — In Slack Bolt, `client` is the `WebClient` instance. It's automatically provided when you include it as a function parameter. Don't import it separately.

5. **The LLM graph still runs** when viewing deal detail — this is intentional. The LLM provides the "Recommended Next Actions" text. If you want the picker view to be instant (no LLM call), you can skip the graph invocation and show a simpler card without recommendations, then add a "Get AI Analysis" button.

6. **Deduplication** — `extract_all_matching_deals()` deduplicates by deal name. RAG chunks might return the same deal across multiple chunks. The `seen_names` set prevents duplicates in the picker.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `formatters/deal.py` | Add `format_deal_picker()` function. Add `import json`. Add `search_term` param to `format_deal_response()` with back button logic. |
| EDIT | `formatters/__init__.py` | Add `format_deal_picker` to imports and `__all__` |
| EDIT | `app.py` | Add `extract_all_matching_deals()` helper. Update `handle_deal()` to check match count and show picker. Add `view_deal_detail` action handler. Add `back_to_deal_results` action handler. |
