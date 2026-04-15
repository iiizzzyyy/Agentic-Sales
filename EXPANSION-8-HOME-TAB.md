# Claude Code Instructions: Slack App Home Tab Dashboard

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/mock_crm.py`, `tools/rag.py`, and `formatters/pipeline.py` first.**

---

## CONTEXT — WHAT AND WHY

The Slack App Home tab is the first thing users see when they click on your bot in the sidebar. Instead of a blank page, we show an **at-a-glance dashboard**: pipeline summary, stale deals, upcoming actions, and quick-start buttons.

This is a "wow" demo moment — before the rep even types a command, they see their AI assistant has already organized their day. It makes the bot feel like a real team member, not just a command-line tool.

**Note:** The Home tab is NOT a slash command. It uses the `app_home_opened` event.

---

## WHAT IT DOES

1. User clicks on the SalesCoach bot in Slack sidebar → Home tab loads
2. Bot renders a dashboard with:
   - Pipeline summary (total value, deal count, forecast)
   - Deals needing attention (stale, overdue)
   - Quick-start buttons for all commands
   - Recent coaching session (if any)
3. Dashboard updates each time the user opens the Home tab

---

## STEP 1: Enable App Home in Slack Configuration

In your Slack app settings (api.slack.com):

1. Go to **Features → App Home**
2. Toggle **Home Tab** to ON
3. Go to **Features → Event Subscriptions**
4. Under **Subscribe to bot events**, add: `app_home_opened`
5. Reinstall the app

---

## STEP 2: Create `formatters/home_tab.py`

```python
"""Block Kit formatting for the Slack App Home tab."""
from formatters.helpers import timestamp, format_currency


def format_home_tab(
    user_name: str,
    pipeline_summary: dict,
    deals_needing_attention: list,
    recent_coaching: dict,
) -> list:
    """Format the App Home tab as Block Kit view blocks.

    Args:
        user_name: Display name of the user
        pipeline_summary: Dict with 'total_value', 'deal_count', 'weighted_forecast', 'by_stage'
        deals_needing_attention: List of dicts with 'name', 'flag', 'reason', 'amount'
        recent_coaching: Dict with 'scenario', 'score', 'date' (or None)

    Returns:
        list: Block Kit blocks for views.publish
    """
    total_value = pipeline_summary.get("total_value", 0)
    deal_count = pipeline_summary.get("deal_count", 0)
    forecast = pipeline_summary.get("weighted_forecast", 0)

    # Greeting based on time of day
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # Deals needing attention
    if deals_needing_attention:
        flag_emoji = {"stale": "⏰", "overdue": "🚨", "at_risk": "⚠️"}
        attention_blocks = []
        for deal in deals_needing_attention[:5]:
            emoji = flag_emoji.get(deal.get("flag", "at_risk"), "⚠️")
            attention_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{deal.get('name', 'Unknown')}* — {deal.get('reason', '')}\n{format_currency(deal.get('amount', 0))}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
                    "action_id": "home_view_deal",
                    "value": deal.get("name", ""),
                }
            })
    else:
        attention_blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ All deals look healthy! No immediate action needed."}
        }]

    # Recent coaching
    if recent_coaching and recent_coaching.get("scenario"):
        coaching_text = (
            f"🎯 Last session: *{recent_coaching.get('scenario', 'N/A')}*\n"
            f"Score: {recent_coaching.get('score', 'N/A')}/10 • {recent_coaching.get('date', 'Recently')}"
        )
    else:
        coaching_text = "🎯 No coaching sessions yet. Try `/coach roleplay discovery call` to get started!"

    # Stage breakdown
    by_stage = pipeline_summary.get("by_stage", {})
    if by_stage:
        stage_str = " | ".join([f"{stage}: {count}" for stage, count in by_stage.items()])
    else:
        stage_str = "No deals"

    blocks = [
        # Header
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{greeting}, {user_name}!", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Your SalesCoach AI dashboard • Updated {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Pipeline at a glance
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📈 Pipeline at a Glance", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Pipeline:*\n{format_currency(total_value)}"},
                {"type": "mrkdwn", "text": f"*Open Deals:*\n{deal_count}"},
                {"type": "mrkdwn", "text": f"*Weighted Forecast:*\n{format_currency(forecast)}"},
                {"type": "mrkdwn", "text": f"*Attention Needed:*\n{len(deals_needing_attention)} deals"},
            ]
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"By stage: {stage_str}"}
            ]
        },

        {"type": "divider"},

        # Deals needing attention
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 Needs Your Attention", "emoji": True}
        },
        *attention_blocks,

        {"type": "divider"},

        # Coaching summary
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Coaching:*\n{coaching_text}"}
        },

        {"type": "divider"},

        # Quick actions
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚡ Quick Actions", "emoji": True}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📈 Pipeline", "emoji": True},
                    "action_id": "home_pipeline",
                    "value": "pipeline",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📬 Follow-Ups", "emoji": True},
                    "action_id": "home_followups",
                    "value": "followups",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🎯 Practice", "emoji": True},
                    "action_id": "home_practice",
                    "value": "practice",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📊 Scorecard", "emoji": True},
                    "action_id": "home_scorecard",
                    "value": "scorecard",
                },
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 Research Company", "emoji": True},
                    "action_id": "home_research",
                    "value": "research",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🧠 Ask a Question", "emoji": True},
                    "action_id": "home_ask",
                    "value": "ask",
                },
            ]
        },

        {"type": "divider"},

        # Help text
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "*Available Commands:*\n"
                        "`/research [company]` • `/deal [name]` • `/coach [roleplay|prep|feedback]` • "
                        "`/draft-email [company]` • `/pipeline` • `/ask [question]` • "
                        "`/objection [text]` • `/competitor [name]` • `/followup` • `/log [notes]` • `/scorecard`"
                    )
                }
            ]
        },
    ]

    return blocks
```

---

## STEP 3: Add `app_home_opened` Event Handler to `app.py`

```python
@app.event("app_home_opened")
def handle_app_home_opened(client, event):
    """Render the App Home tab dashboard when user opens it."""
    user_id = event["user"]

    try:
        # Get user info for greeting
        user_info = client.users_info(user=user_id)
        user_name = user_info["user"]["profile"].get("first_name", "there")
    except Exception:
        user_name = "there"

    # Build pipeline summary
    all_deals = mock_crm.get_all_open_deals()
    stale = mock_crm.get_stale_deals(days=14)
    overdue = mock_crm.get_overdue_deals()

    total_value = 0
    stage_counts = {}
    for deal in all_deals:
        props = deal.get("properties", {})
        amount = float(props.get("amount", 0) or 0)
        stage = props.get("dealstage", "unknown")
        total_value += amount
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Weighted forecast (simple: 50% of total for POC)
    weighted_forecast = total_value * 0.5

    pipeline_summary = {
        "total_value": total_value,
        "deal_count": len(all_deals),
        "weighted_forecast": weighted_forecast,
        "by_stage": stage_counts,
    }

    # Deals needing attention
    deals_needing_attention = []
    for deal in overdue:
        props = deal.get("properties", {})
        deals_needing_attention.append({
            "name": props.get("dealname", "Unknown"),
            "flag": "overdue",
            "reason": f"Past close date ({props.get('closedate', 'N/A')})",
            "amount": props.get("amount", 0),
        })
    for deal in stale:
        props = deal.get("properties", {})
        name = props.get("dealname", "Unknown")
        if not any(d["name"] == name for d in deals_needing_attention):
            deals_needing_attention.append({
                "name": name,
                "flag": "stale",
                "reason": "No activity in 14+ days",
                "amount": props.get("amount", 0),
            })

    # Recent coaching (from in-memory state)
    recent_coaching = {}
    if 'completed_roleplays' in dir() and completed_roleplays:
        last = completed_roleplays[-1]
        recent_coaching = {
            "scenario": last.get("scenario", "Unknown"),
            "score": last.get("score", "N/A"),
            "date": last.get("timestamp", "Recently"),
        }

    # Format blocks
    from formatters.home_tab import format_home_tab
    blocks = format_home_tab(
        user_name=user_name,
        pipeline_summary=pipeline_summary,
        deals_needing_attention=deals_needing_attention,
        recent_coaching=recent_coaching,
    )

    # Publish to App Home
    client.views_publish(
        user_id=user_id,
        view={
            "type": "home",
            "blocks": blocks,
        }
    )
```

---

## STEP 4: Add Action Handlers for Home Tab Buttons

These buttons can't directly trigger slash commands, so they post helpful messages instead:

```python
@app.action("home_view_deal")
def handle_home_view_deal(ack, body, client):
    """View a deal from the Home tab."""
    ack()
    deal_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/deal {deal_name}` in any channel to see the full deal card.",
    )


@app.action("home_pipeline")
def handle_home_pipeline(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/pipeline` in any channel to see your full pipeline digest.")


@app.action("home_followups")
def handle_home_followups(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/followup` in any channel to see deals needing follow-up.")


@app.action("home_practice")
def handle_home_practice(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="Start a practice session:\n• `/coach roleplay discovery call`\n• `/coach roleplay objection handling`\n• `/coach roleplay competitive deal`",
    )


@app.action("home_scorecard")
def handle_home_scorecard(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/scorecard` in any channel to see your performance scorecard.")


@app.action("home_research")
def handle_home_research(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/research [company name]` in any channel to get a research brief.")


@app.action("home_ask")
def handle_home_ask(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/ask [your question]` in any channel to ask anything about your CRM.")
```

---

## STEP 5: Update `formatters/__init__.py`

Note: `format_home_tab` returns only `blocks` (not a `(blocks, fallback)` tuple) since `views.publish` doesn't need a fallback. You still import it but handle it differently.

Don't add to `__all__` — it's imported directly in the event handler.

---

## SLACK CONFIGURATION CHECKLIST

1. **App Home → Home Tab:** Toggle ON
2. **Event Subscriptions → Bot Events:** Add `app_home_opened`
3. **OAuth Scopes:** Ensure `users:read` scope is added (for `users_info`)
4. Reinstall app

---

## GOTCHAS

1. **Home tab has a 100-block limit** (vs 50 for messages). We use about 30-40 blocks, so there's room.

2. **`views.publish` replaces the entire Home tab.** Every time the user opens the tab, we rebuild it from scratch with fresh data. No incremental updates.

3. **Home tab buttons can't trigger slash commands directly.** They send action events which we handle by posting DMs with command suggestions. In production, you could have these buttons trigger the actual logic internally.

4. **The `app_home_opened` event fires every time the user clicks the Home tab.** Don't run expensive operations (like LLM calls) here — just pull from in-memory/cached data. If you want AI-generated insights on the Home tab, cache them and refresh every 5 minutes.

5. **`completed_roleplays` might not exist** if the scorecard expansion hasn't been built yet. The handler checks with `'completed_roleplays' in dir()` for safety. If you haven't built expansion #1, just set `recent_coaching = {}`.

6. **User DMs require the `chat:write` scope**, which should already be enabled.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/home_tab.py` | New formatter for App Home tab blocks |
| EDIT | `app.py` | Add `handle_app_home_opened()` event handler, add 7 Home tab action handlers (`home_view_deal`, `home_pipeline`, `home_followups`, `home_practice`, `home_scorecard`, `home_research`, `home_ask`) |
| CONFIG | Slack App Settings | Enable Home Tab, add `app_home_opened` event, add `users:read` scope |
