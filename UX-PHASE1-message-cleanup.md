# UX Phase 1.2 — Message Cleanup After Button Clicks

## Problem
When a user clicks a button (e.g., "Draft Follow-Up Email" on a research card), the original card stays fully expanded with all buttons still active. After a 10-minute demo, the channel becomes a wall of stale, interactive cards with dead buttons. Slack's guidelines explicitly say to "condense the message down to a simple text record of what happened."

## Solution
After a button click, UPDATE the original message to collapse it into a compact summary line. Keep the header for context, remove the blocks, add a context line showing what action was taken.

## The Collapse Helper

Add this utility function near the top of `app.py` (after `handle_error`):

```python
def collapse_message(client, channel, message_ts, original_title, action_summary):
    """Collapse a rich Block Kit message into a compact summary after an action is taken.

    Args:
        client: Slack WebClient
        channel: Channel ID
        message_ts: Timestamp of the original message to update
        original_title: The card title to preserve (e.g., "Research Brief: NovaTech")
        action_summary: What happened (e.g., "✉️ Drafting email to Wei Ahmed...")
    """
    collapsed_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{original_title}*\n{action_summary}"
            }
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}
            ]
        },
    ]
    try:
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"{original_title} — {action_summary}",
            blocks=collapsed_blocks,
        )
    except Exception as e:
        print(f"[collapse_message] Failed to update message: {e}")
```

Import `timestamp` from `formatters.helpers` at the top if not already imported.

## Action Handlers to Update

Every action handler that triggers a new response should collapse the original message. The original message's `ts` is available in the action payload as `body["message"]["ts"]` and the channel as `body["channel"]["id"]`.

### High-Priority Actions (research/deal flow — demo-critical)

#### 1. `draft_email_from_research` (line ~1212)
```python
# At the START of the handler, after ack():
channel = body["channel"]["id"]
message_ts = body["message"]["ts"]
company_name = body["actions"][0]["value"]
collapse_message(client, channel, message_ts,
    f"Research Brief: {company_name}",
    "✉️ Drafting follow-up email..."
)
```

#### 2. `start_roleplay_from_research` (line ~1281)
```python
collapse_message(client, channel, message_ts,
    f"Research Brief: {company_name}",
    "🎯 Starting roleplay session..."
)
```

#### 3. `view_deal_detail` (line ~1359)
```python
deal_name = # extract from action value
collapse_message(client, channel, message_ts,
    "Deal Search Results",
    f"📋 Viewing deal: {deal_name}"
)
```

#### 4. `back_to_deal_results` (line ~1413)
```python
collapse_message(client, channel, message_ts,
    f"Deal: {deal_name}",
    "← Returned to search results"
)
```

#### 5. `draft_email_from_deal` (line ~1445)
```python
collapse_message(client, channel, message_ts,
    f"Deal: {deal_name}",
    "✉️ Drafting email..."
)
```

#### 6. `select_email_contact` (line ~1631)
After the user picks a contact from the contact picker, collapse the picker:
```python
collapse_message(client, channel, message_ts,
    "Contact Selection",
    f"✉️ Selected: {contact_name} — drafting email..."
)
```

#### 7. `select_email_deal` (line ~1706)
After the user picks a deal from the deal picker for email:
```python
collapse_message(client, channel, message_ts,
    "Deal Selection",
    f"📋 Selected: {deal_name} — choose a contact next..."
)
```

#### 8. `research_from_deal` (line ~1323)
```python
collapse_message(client, channel, message_ts,
    f"Deal: {deal_name}",
    f"🔍 Researching {company_name}..."
)
```

#### 9. `drill_flagged_deal` (line ~1882)
```python
collapse_message(client, channel, message_ts,
    "Pipeline Health",
    f"📋 Viewing flagged deal: {deal_name}"
)
```

#### 10. `refresh_pipeline` (line ~1924)
```python
collapse_message(client, channel, message_ts,
    "Pipeline Health",
    "🔄 Refreshing pipeline data..."
)
```

### Medium-Priority Actions (coaching flow)

#### 11. `practice_again` (line ~1800)
```python
collapse_message(client, channel, message_ts,
    "Roleplay Debrief",
    "🎯 Starting another practice round..."
)
```

#### 12. `try_suggested` (line ~1841)
```python
collapse_message(client, channel, message_ts,
    "Roleplay Debrief",
    "🎯 Trying suggested scenario..."
)
```

#### 13. `practice_objection` (line ~2082)
```python
collapse_message(client, channel, message_ts,
    "Objection Response",
    "🎯 Starting objection practice..."
)
```

### Lower-Priority Actions (expansion commands)

#### 14-20. Remaining action handlers:
Apply the same pattern to: `draft_followup_email`, `roleplay_competitor`, `draft_competitive_email`, `battlecard_practice`, `battlecard_draft_email`, `alert_view_deal`, `forecast_at_risk`, `draft_email_from_persona`, `roleplay_from_persona`, `view_deal_from_handoff`, `draft_handoff_email`, `regenerate_email_sequence`.

Each one follows the same pattern:
```python
channel = body["channel"]["id"]
message_ts = body["message"]["ts"]
collapse_message(client, channel, message_ts, ORIGINAL_TITLE, ACTION_SUMMARY)
```

## Special Cases

### Email draft buttons (create_gmail_draft, regenerate_email, copy_email_text)
These should NOT collapse the email card — the user is still interacting with it. Only collapse when the user LEAVES the flow (navigates to a different view).

### noop action (line ~2282)
Skip — this is a placeholder that does nothing.

### Home tab actions (home_view_deal, home_pipeline, etc.)
These trigger from the App Home tab, not from a message. The Home tab doesn't collapse — skip these.

## Extracting Action Values

Button values often contain JSON. To extract names:
```python
import json

action_value = body["actions"][0]["value"]
try:
    data = json.loads(action_value)
    deal_name = data.get("deal_name", "Unknown")
except (json.JSONDecodeError, TypeError):
    deal_name = action_value  # Plain string value
```

## DO NOT
- Do not collapse messages for Home tab actions (no message to collapse)
- Do not collapse the email draft card when sub-buttons (copy, regenerate, create Gmail) are clicked
- Do not collapse roleplay messages mid-conversation — only collapse the debrief after "Practice Again" or "Try Suggested"
- Do not remove the `ack()` call from any handler
- Do not change the `handle_error` function — it still handles errors for non-loading handlers

## Testing
1. `/research NovaTech` → click "Draft Follow-Up Email" → research card collapses to one line, contact picker appears
2. Pick a contact → contact picker collapses, email draft appears
3. `/deal NovaTech` → click "View Details" on picker → picker collapses, deal card appears
4. `/pipeline` → click "Drill into Flagged Deal" → pipeline card collapses, deal card appears
5. Verify collapsed messages show the correct title and action summary
6. Verify the new response appears correctly (not blocked by the collapse)
