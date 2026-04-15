# Fix /my-day Button Handlers — Claude Code Instructions

## Problem Summary

The `/my-day` command renders correctly, but clicking the **Prep** and **Join** buttons either does nothing or shows an error.

---

## Bug 1: Prep Button — Silent Crash (AttributeError)

**File:** `app.py`, line ~7107
**Handler:** `handle_prep_meeting_action` (registered at `@app.action(re.compile(r"^prep_meeting_"))`)

**Root cause:** The handler calls `mock_crm.get_deal(deal_id)` but that function does not exist. The correct function name is `mock_crm.get_deal_by_id(deal_id)`.

**The error:** `AttributeError: module 'tools.mock_crm' has no attribute 'get_deal'`

Slack receives no response (the handler crashes after `ack()`), so the user sees nothing happen. The warning triangle icon (⚠) next to the Prep button in Slack is Slack's indicator that the action handler failed.

**Fix:** In `app.py`, in the `handle_prep_meeting_action` function, change:

```python
# BEFORE (line ~7107):
deal = mock_crm.get_deal(deal_id)

# AFTER:
deal = mock_crm.get_deal_by_id(deal_id)
```

**Also add error handling** — wrap the body of the handler (after `ack()`) in a try/except so future errors are visible instead of silent:

```python
@app.action(re.compile(r"^prep_meeting_"))
def handle_prep_meeting_action(ack, body, client):
    """Prep for a meeting from /my-day."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("prep_meeting_", "")
    deal_id = body["actions"][0].get("value", "")
    channel_id = body["channel"]["id"]

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Meeting not found.")
            return

        deal_info = None
        if deal_id:
            deal = mock_crm.get_deal_by_id(deal_id)  # <-- FIXED: was get_deal
            if deal:
                deal_info = {
                    "name": deal.get("properties", {}).get("dealname", "Unknown"),
                    "stage": deal.get("properties", {}).get("dealstage", "Unknown"),
                    "amount": deal.get("properties", {}).get("amount", 0)
                }

        blocks = format_meeting_prep(event, deal_info)
        client.chat_postMessage(channel=channel_id, blocks=blocks, text=f"Prep: {event['title']}")
    except Exception as e:
        handle_action_error(client, channel_id, "prep_meeting", e)
```

---

## Bug 2: Join Button — Works But Could Be Better

**Status:** The Join button actually works — it outputs the "Training: New Hire Sales Training" message with "No pending assignments" text. However there are two improvements to make:

### 2A. Add error handling (same pattern as Prep fix)

Wrap the handler body in try/except for robustness:

```python
@app.action(re.compile(r"^join_training_"))
def handle_join_training_action(ack, body, client):
    """Join a training session from /my-day."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("join_training_", "")
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Training event not found.")
            return

        cohort_id = event.get("cohort_id", "")

        # Check if there are pending assignments for this user
        assignments = get_user_assignments(user_id, status="pending")
        if assignments:
            a = assignments[0]
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Training: {event['title']}*\n"
                            f"_{event.get('notes', '')}_\n\n"
                            f"Your next assignment: *{a['scenario_name']}* "
                            f"({a['scenario_type'].replace('_', ' ').title()} · {a['scenario_difficulty'].title()})"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Start Practice"},
                            "action_id": "start_saved_scenario",
                            "value": a["scenario_id"],
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View All Assignments"},
                            "action_id": "quick_practice"
                        }
                    ]
                }
            ]
            client.chat_postMessage(channel=channel_id, blocks=blocks, text=f"Training: {event['title']}")
        else:
            client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"*Training: {event['title']}*\n"
                    f"_{event.get('notes', '')}_\n\n"
                    f"No pending assignments. Use `/training library` to browse scenarios or `/coach roleplay` for a quick session."
                )
            )
    except Exception as e:
        handle_action_error(client, channel_id, "join_training", e)
```

### 2B. Add `practice_for_meeting_` handler error wrapping

The `practice_for_meeting_` handler (for the "Practice Scenario" button on the prep detail card) also needs error handling:

```python
@app.action(re.compile(r"^practice_for_meeting_"))
def handle_practice_for_meeting_action(ack, body, client):
    """Start a roleplay scenario to practice for a specific meeting."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("practice_for_meeting_", "")
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Meeting not found.")
            return

        title = event.get("title", "Meeting")
        client.chat_postMessage(
            channel=channel_id,
            text=(
                f"Starting practice session for *{title}*...\n"
                f"Try `/coach roleplay` with context from this meeting, "
                f"or `/training library` to find a matching scenario."
            )
        )
    except Exception as e:
        handle_action_error(client, channel_id, "practice_for_meeting", e)
```

---

## Summary of Changes

| File | Change | Lines |
|------|--------|-------|
| `app.py` | Fix `mock_crm.get_deal()` → `mock_crm.get_deal_by_id()` in `handle_prep_meeting_action` | ~7107 |
| `app.py` | Add try/except to `handle_prep_meeting_action` using existing `handle_action_error` | ~7089-7116 |
| `app.py` | Add try/except to `handle_join_training_action` using existing `handle_action_error` | ~7119-7183 |
| `app.py` | Add try/except to `handle_practice_for_meeting_action` using existing `handle_action_error` | ~7186-7210 |

## Testing

1. Run `/my-day`
2. Click **Prep** on the DataFlow meeting → should now show the meeting prep card with deal info (deal name, stage, amount)
3. Click **Join** on the New Hire Sales Training → should show training info (already works, now with error handling)
4. If Prep card shows "Practice Scenario" button → click it → should respond with coaching suggestion
