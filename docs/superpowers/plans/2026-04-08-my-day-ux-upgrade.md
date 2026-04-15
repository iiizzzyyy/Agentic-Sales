# /my-day UX Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Use /pipeline to view..." text response with an inline pipeline preview directly in the /my-day view, following Slack's design guidelines for progressive disclosure and actionable empty states.

**Architecture:** Modify the `format_my_day` function in `formatters/calendar.py` to include an inline pipeline summary section when the user has pipeline data. Add a new `get_pipeline_summary` helper that fetches lightweight pipeline metrics. Update the empty state to show actionable guidance instead of just suggesting training/pipeline.

**Tech Stack:** Python 3.11+, Slack Block Kit, existing CRM tools (`tools/crm.py`), existing pipeline formatter (`formatters/pipeline.py`)

---

### Task 1: Add Pipeline Summary Helper Function

**Files:**
- Create: `formatters/pipeline_summary.py` (new helper)
- Modify: `tools/crm.py` (add `get_pipeline_summary` function if not exists)

- [ ] **Step 1: Check existing pipeline data access**

Read `tools/crm.py` to understand how pipeline data is fetched. Look for functions like `get_user_pipeline`, `get_deals_by_stage`, etc.

- [ ] **Step 2: Create lightweight pipeline summary helper**

```python
# formatters/pipeline_summary.py
"""Lightweight pipeline summary for /my-day integration."""
from tools.crm import get_user_deals  # or equivalent


def get_pipeline_summary(user_id: str) -> dict:
    """Get compact pipeline metrics for /my-day display.
    
    Returns:
        dict with keys: total_value, deal_count, flagged_count, top_stage
    """
    deals = get_user_deals(user_id)
    
    total_value = sum(float(d.get('amount', 0) or 0) for d in deals)
    deal_count = len(deals)
    
    # Count flagged deals (stale, overdue, at_risk)
    flagged_count = sum(1 for d in deals if d.get('flag'))
    
    # Find stage with most deals
    stage_counts = {}
    for deal in deals:
        stage = deal.get('stage', 'Unknown')
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    
    top_stage = max(stage_counts.items(), key=lambda x: x[1])[0] if stage_counts else None
    
    return {
        'total_value': total_value,
        'deal_count': deal_count,
        'flagged_count': flagged_count,
        'top_stage': top_stage,
    }
```

- [ ] **Step 3: Commit**

```bash
git add formatters/pipeline_summary.py
git commit -m "feat: add pipeline_summary helper for /my-day integration"
```

---

### Task 2: Update format_my_day with Inline Pipeline Preview

**Files:**
- Modify: `formatters/calendar.py:1-165`
- Test: Manual testing via `/my-day` command

- [ ] **Step 1: Import the pipeline summary helper**

```python
# At top of formatters/calendar.py
from formatters.pipeline_summary import get_pipeline_summary
from formatters.helpers import format_currency
```

- [ ] **Step 2: Update format_my_day signature to accept user_id**

```python
def format_my_day(events, user_name=None, user_id=None, pipeline_data=None):
    """
    Format the /my-day view with today's schedule.

    Args:
        events: List of event dicts from calendar tools
        user_name: Optional user name for greeting
        user_id: Optional user ID for fetching pipeline data
        pipeline_data: Optional pre-fetched pipeline dict (for testing)

    Returns:
        List of Slack blocks
    """
```

- [ ] **Step 3: Add pipeline summary section after the header**

```python
# After the header block (~line 31), add:
    
    # Pipeline summary section (if user_id provided)
    if user_id and pipeline_data is not False:  # Explicit False to disable
        try:
            pipeline = get_pipeline_summary(user_id)
            if pipeline['deal_count'] > 0:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Pipeline Summary*\n"
                            f"• *{format_currency(pipeline['total_value'])}* across {pipeline['deal_count']} deals\n"
                            f"• Most active stage: {pipeline['top_stage']}\n"
                            f"• {pipeline['flagged_count']} deals need attention"
                        ) if pipeline['flagged_count'] > 0 else (
                            f"*Pipeline Summary*\n"
                            f"• *{format_currency(pipeline['total_value'])}* across {pipeline['deal_count']} deals\n"
                            f"• Most active stage: {pipeline['top_stage']}\n"
                            f"• All deals on track"
                        )
                    }
                })
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Full Pipeline"},
                            "action_id": "view_full_pipeline",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "See Flagged Deals"},
                            "action_id": "view_flagged_deals",
                            "style": "danger" if pipeline['flagged_count'] > 0 else "primary"
                        }
                    ]
                })
                blocks.append({"type": "divider"})
        except Exception:
            pass  # Silently fail if pipeline data unavailable
```

- [ ] **Step 4: Update empty state actions**

Replace the current empty state actions (~lines 41-56) with:

```python
    if not events:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No meetings scheduled for today. Great time to focus on outreach or training!"
            }
        })
        
        # Still show pipeline summary if available
        if user_id and pipeline_data is not False:
            try:
                pipeline = get_pipeline_summary(user_id)
                if pipeline['deal_count'] > 0:
                    blocks.append({
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"💼 You have {pipeline['deal_count']} deals ({format_currency(pipeline['total_value'])}) — consider following up on stale deals"
                            }
                        ]
                    })
            except Exception:
                pass
        
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Training"},
                    "action_id": "quick_practice",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Pipeline"},
                    "action_id": "quick_pipeline"
                }
            ]
        })
        return blocks
```

- [ ] **Step 5: Commit**

```bash
git add formatters/calendar.py
git commit -m "feat: add inline pipeline preview to /my-day view"
```

---

### Task 3: Add Button Action Handlers

**Files:**
- Modify: `app.py` (~line 7405-7414)

- [ ] **Step 1: Replace quick_pipeline handler with full pipeline preview**

```python
@app.action("quick_pipeline")
def handle_quick_pipeline_action(ack, body, client):
    """Show inline pipeline preview when clicking View Pipeline from /my-day."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    
    try:
        from formatters.pipeline import format_pipeline_response
        from tools.crm import get_user_pipeline_data  # or equivalent
        
        # Fetch pipeline data
        pipeline_data = get_user_pipeline_data(user_id)
        
        # Format the response
        blocks, fallback = format_pipeline_response(
            total_value=pipeline_data['total_value'],
            deal_count=pipeline_data['deal_count'],
            weighted_forecast=pipeline_data['weighted_forecast'],
            deals_by_stage=pipeline_data['deals_by_stage'],
            flagged_deals=pipeline_data['flagged_deals'],
            recommendations=pipeline_data['recommendations'],
        )
        
        # Post as ephemeral message (Slack best practice)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text=fallback
        )
    except Exception as e:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Couldn't load pipeline data. Try `/pipeline` for the full view."
        )


@app.action("view_full_pipeline")
def handle_view_full_pipeline_action(ack, body, client):
    """Handle View Full Pipeline button from /my-day inline preview."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    
    # Same implementation as quick_pipeline
    handle_quick_pipeline_action(ack, body, client)


@app.action("view_flagged_deals")
def handle_view_flagged_deals_action(ack, body, client):
    """Handle See Flagged Deals button from /my-day inline preview."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    
    try:
        from tools.crm import get_flagged_deals
        
        flagged = get_flagged_deals(user_id)
        
        if flagged:
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Flagged Deals", "emoji": True}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Found {len(flagged)} deals that need attention:"}
                }
            ]
            
            for deal in flagged[:5]:  # Show top 5
                flag_emoji = {"stale": "⏰", "overdue": "🚨", "at_risk": "⚠️"}
                emoji = flag_emoji.get(deal.get('flag', 'at_risk'), '⚠️')
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{deal.get('name', 'Unknown')}*\n{deal.get('reason', 'Needs attention')}"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Deal"},
                        "action_id": "view_deal_from_flagged",
                        "value": deal.get('id', '')
                    }
                })
            
            if len(flagged) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"...and {len(flagged) - 5} more. Use `/pipeline` for full view."}
                    ]
                })
            
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                blocks=blocks,
                text=f"Flagged Deals: {len(flagged)} deals need attention"
            )
        else:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="Great news! No flagged deals — your pipeline looks healthy."
            )
    except Exception as e:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Couldn't load flagged deals. Try `/pipeline` for the full view."
        )
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add action handlers for /my-day pipeline buttons"
```

---

### Task 4: Update /my-day Command Handler

**Files:**
- Modify: `app.py` (~line 6626-6641)

- [ ] **Step 1: Pass user_id to format_my_day**

```python
@app.command("/my-day")
def handle_my_day(ack, command, say):
    """Show today's calendar with meeting prep actions and pipeline preview."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/my-day")

    try:
        from datetime import datetime
        from formatters.calendar import format_my_day
        
        events = get_user_events(user_id, datetime.now().date())
        date_label = datetime.now().strftime("%A, %b %-d")
        
        # Pass user_id for pipeline summary
        blocks = format_my_day(events, user_name=None, user_id=user_id)
        
        say(channel=channel_id, blocks=blocks, text=f"Your Day - {date_label}")
    except Exception as e:
        handle_error(say, channel_id, "/my-day", e)
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: pass user_id to format_my_day for pipeline integration"
```

---

### Task 5: Testing and Verification

**Files:**
- Test: Manual testing via Slack

- [ ] **Step 1: Test with no meetings, no pipeline**

Run `/my-day` with empty calendar and empty CRM. Expected: Clean empty state with training/pipeline buttons.

- [ ] **Step 2: Test with no meetings, has pipeline**

Run `/my-day` with empty calendar but deals in CRM. Expected: Empty state message + pipeline summary inline + action buttons.

- [ ] **Step 3: Test with meetings, has pipeline**

Run `/my-day` with meetings scheduled. Expected: Meeting list + pipeline summary section at top + divider.

- [ ] **Step 4: Test View Pipeline button**

Click "View Pipeline" button. Expected: Ephemeral message with full pipeline digest appears (not channel message).

- [ ] **Step 5: Test See Flagged Deals button**

Click "See Flagged Deals" when flagged deals exist. Expected: Ephemeral list of flagged deals with View Deal buttons.

- [ ] **Step 6: Test See Flagged Deals when none exist**

Click when all deals are healthy. Expected: Friendly confirmation message "No flagged deals — looking good!"

---

### Task 6: Documentation Update

**Files:**
- Modify: `README.md` or `CLAUDE.md` (update /my-day command docs)

- [ ] **Step 1: Update CLAUDE.md /my-day section**

```markdown
## Commands

### /my-day

Shows today's calendar with meeting prep actions. Now includes:
- Inline pipeline summary at the top (when deals exist)
- Quick actions: "Start Training", "View Pipeline"
- Pipeline preview buttons: "View Full Pipeline", "See Flagged Deals"

Pipeline data is fetched from HubSpot CRM and displayed as a compact summary.
Full pipeline view appears as an ephemeral message (only visible to you).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update /my-day command documentation"
```

---

## Verification

After all tasks complete:

```bash
# Run the app
python app.py

# In Slack, test:
/my-day
# Should show pipeline summary inline (if deals exist)
# Click "View Pipeline" → ephemeral full digest
# Click "See Flagged Deals" → ephemeral flagged list
```

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `formatters/pipeline_summary.py` | Create | Lightweight pipeline helper |
| `formatters/calendar.py` | Modify | Add inline pipeline preview |
| `formatters/helpers.py` | Read | Verify format_currency exists |
| `tools/crm.py` | Read | Verify data access functions |
| `app.py` | Modify | Add button handlers, update /my-day command |
| `CLAUDE.md` | Modify | Update documentation |

---

**Plan complete. Ready for execution.**
