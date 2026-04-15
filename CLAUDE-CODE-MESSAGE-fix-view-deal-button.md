# Claude Code Task: Fix "View Deal" Buttons in Won/Lost Deal Lists

> **Read `app.py` lines 3758-3767 first.**

---

## THE BUG

When clicking "View Deal" buttons in the Won Deals or Lost Deals lists (from `/win-loss`), nothing happens.

The buttons use `action_id: "view_deal_from_handoff"` and the handler at line 3758 does:

```python
client.chat_postMessage(channel=user_id, text=f"Use `/deal {deal_name}` to view the full deal card.")
```

This silently fails because it tries to DM the user via `client.chat_postMessage(channel=user_id)`, which requires an open DM conversation. Even if the DM works, it just tells the user to type a command — it doesn't actually show the deal.

---

## THE FIX

Replace the `handle_view_deal_from_handoff` handler (around line 3758) with one that actually runs the deal lookup and posts a deal card in the same channel:

```python
@app.action("view_deal_from_handoff")
def handle_view_deal_from_handoff(ack, body, say):
    """View a deal card inline from any button that references a deal."""
    ack()
    deal_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    # Look up the deal
    deal = mock_crm.search_deal(deal_name)

    if not deal:
        say(text=f"Could not find deal matching '{deal_name}'.", channel=channel)
        return

    props = deal.get("properties", {})
    company_id = deal.get("associations", {}).get("company", "")
    company = mock_crm.get_company_by_id(company_id) if company_id else None
    company_name = company.get("properties", {}).get("name", "Unknown") if company else "Unknown"

    # Get contact
    contact_id = deal.get("associations", {}).get("contact", "")
    contact = mock_crm.get_contact_by_id(contact_id) if contact_id else None

    # Build a quick deal summary using Block Kit
    from formatters.helpers import format_currency, timestamp

    amount = float(props.get("amount", 0) or 0)
    stage = props.get("dealstage", "Unknown").replace("_", " ").title()

    # Contact info
    contact_text = "No contact on file"
    if contact:
        c_props = contact.get("properties", {})
        contact_text = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')} — {c_props.get('jobtitle', 'N/A')} ({c_props.get('email', '')})"

    # Recent activities
    activities = deal.get("activities", [])
    activity_text = ""
    for a in activities[:3]:
        note = a.get("body", a.get("note", ""))[:120]
        date = a.get("timestamp", "")[:10]
        activity_text += f"• [{date}] {note}\n"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 {props.get('dealname', deal_name)}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{props.get('closedate', 'N/A')[:10]}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👤 Contact:*\n{contact_text}"}
        },
    ]

    if activity_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📝 Recent Activity:*\n{activity_text}"}
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • Quick View • {timestamp()}"}
        ]
    })

    say(text=f"Deal: {props.get('dealname', deal_name)}", blocks=blocks, channel=channel)
```

**Key changes:**
1. Changed `client` parameter to `say` — posts in the same channel, not as a DM
2. Actually looks up the deal data and shows a deal card instead of just saying "use `/deal`"
3. Shows company, stage, value, close date, contact, and recent activities inline

---

## ALSO CHECK

Search `app.py` for any OTHER action handlers that use `client.chat_postMessage(channel=user_id)` — these all have the same silent-failure problem. Any handler that sends a response to the user should use `say(channel=channel)` or `client.chat_postMessage(channel=body["channel"]["id"])` instead of `channel=user_id`.

Quick grep to find them:
```
chat_postMessage(channel=user_id
```

For each one found: change `channel=user_id` to `channel=body["channel"]["id"]` (or use `say` with `channel=channel`). Exception: Home tab button handlers MUST use `channel=user_id` since Home tab actions don't have a channel context — those are fine as-is.

---

## TESTING

1. Restart bot: `python app.py`
2. Run `/win-loss`
3. Click "View Lost Deals" → should show lost deals list
4. Click "View Deal" on any lost deal → should show a deal card with company, stage, value, contact, and activity notes IN THE SAME CHANNEL
5. Same test with "View Won Deals" → "View Deal"

---

## FILES TO CHANGE

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `app.py` (line ~3758) | Replace `handle_view_deal_from_handoff` — use `say`, show actual deal card |
| AUDIT | `app.py` | Find all `chat_postMessage(channel=user_id)` in action handlers and fix the ones that silently fail |
