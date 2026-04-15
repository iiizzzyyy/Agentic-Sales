# Claude Code Task: Fix "View Deal" Buttons All Showing Same Deal

> **Read `app.py` — find the `handle_win_loss_lost` (action: `win_loss_lost_deals`) and `handle_win_loss_won` (action: `win_loss_won_deals`) handlers, and the `handle_view_deal_from_handoff` handler.**

---

## THE BUG

When clicking "View Deal" on any won or lost deal in the list, they ALL show the same deal instead of the one that was clicked.

## ROOT CAUSE

Every "View Deal" button in the list uses the exact same `action_id: "view_deal_from_handoff"`. Slack requires `action_id` to be unique within a single message. When multiple buttons share the same `action_id`, Slack can't distinguish which was clicked — it sends the `value` from the wrong button (typically the last one in the list).

Look at the loop in `handle_win_loss_lost`:
```python
for d in lost:
    blocks.append({
        "accessory": {
            "type": "button",
            "action_id": "view_deal_from_handoff",  # <-- SAME for every deal!
            "value": deal_name,
        }
    })
```

## THE FIX

Make each button's `action_id` unique by appending an index. Then use a regex-based action handler to catch all of them.

### Step 1: Update `handle_win_loss_lost` — add index to action_id

Find the lost deals loop and change the button's `action_id`:

```python
# In handle_win_loss_lost, inside the loop:
for i, d in enumerate(lost):  # <-- add enumerate
    p = d.get("properties", {})
    deal_name = p.get("dealname", "Unknown")
    amount = float(p.get("amount", 0) or 0)

    # Get loss reason from activities
    loss_reason = ""
    for a in d.get("activities", []):
        note = a.get("body", a.get("note", ""))
        if any(word in note.lower() for word in ["lost", "competitor", "went with", "chose", "declined"]):
            loss_reason = note[:120]
            break

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{deal_name}*\n{format_currency(amount)}" + (f"\n_{loss_reason}_" if loss_reason else "")
        },
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
            "action_id": f"view_deal_{i}",  # <-- UNIQUE per deal
            "value": deal_name,
        }
    })
```

### Step 2: Update `handle_win_loss_won` — same fix

```python
# In handle_win_loss_won, inside the loop:
for i, d in enumerate(won):  # <-- add enumerate
    p = d.get("properties", {})
    deal_name = p.get("dealname", "Unknown")
    amount = float(p.get("amount", 0) or 0)
    stage_label = p.get("dealstage_label", "Closed Won")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{deal_name}*\n{format_currency(amount)} • {stage_label}"
        },
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
            "action_id": f"view_deal_{i}",  # <-- UNIQUE per deal
            "value": deal_name,
        }
    })
```

### Step 3: Replace the old handler with a regex-based one

Remove or replace the existing `handle_view_deal_from_handoff` handler. Add a regex-based handler that catches `view_deal_0`, `view_deal_1`, `view_deal_2`, etc.:

```python
import re

@app.action(re.compile(r"view_deal_\d+"))
def handle_view_deal_by_index(ack, body, say):
    """View a deal card inline — handles view_deal_0, view_deal_1, etc."""
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

### Step 4: Keep the old handler as a fallback

If `view_deal_from_handoff` is used elsewhere (search app.py for other references), keep it but update it to do the same thing as above instead of sending a DM. If it's ONLY used by the won/lost lists, remove it entirely since the regex handler replaces it.

Search app.py for `view_deal_from_handoff` — if it appears in other formatters or handlers (like `/handoff`), keep it and update it:

```python
@app.action("view_deal_from_handoff")
def handle_view_deal_from_handoff(ack, body, say):
    """Fallback handler for view_deal_from_handoff action_id."""
    ack()
    deal_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    # Reuse the same logic — call the deal lookup directly
    handle_view_deal_by_index.__wrapped__(ack=lambda: None, body=body, say=say)
```

Actually, simpler approach: just make `handle_view_deal_from_handoff` do the same deal card logic. Copy the exact same body from `handle_view_deal_by_index` into `handle_view_deal_from_handoff`.

### Step 5: Apply the same fix everywhere

Search the ENTIRE `app.py` for any other place where buttons are generated inside a loop with a hardcoded `action_id`. This is the same bug pattern — look for:
```python
for ... in ...:
    blocks.append({
        "accessory": {
            "action_id": "some_fixed_string",  # <-- BUG if inside a loop
        }
    })
```

If you find any, apply the same fix: use `f"action_id_{i}"` with `enumerate()` and add a `re.compile()` handler.

### Step 6: Make sure `import re` is at the top of app.py

Check if `import re` already exists at the top of `app.py`. If not, add it to the imports section.

---

## TESTING

1. Restart bot: `python app.py`
2. Run `/win-loss`
3. Click "View Lost Deals" → see list with 2+ deals
4. Click "View Deal" on the FIRST deal → verify it shows the correct deal card with the right name, company, and amount
5. Click "View Deal" on the SECOND deal → verify it shows a DIFFERENT deal card (not the same one)
6. Same test with "View Won Deals"

---

## FILES TO CHANGE

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `app.py` | Add `import re` if missing |
| EDIT | `app.py` | Update `handle_win_loss_lost` — use `enumerate()` + `f"view_deal_{i}"` |
| EDIT | `app.py` | Update `handle_win_loss_won` — same fix |
| EDIT | `app.py` | Add `handle_view_deal_by_index` with `re.compile(r"view_deal_\d+")` |
| EDIT | `app.py` | Update `handle_view_deal_from_handoff` to show deal card instead of DM |
| AUDIT | `app.py` | Search for same bug pattern in other loop-generated buttons |
