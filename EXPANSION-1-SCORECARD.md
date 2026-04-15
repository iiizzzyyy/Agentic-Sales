# Claude Code Instructions: `/scorecard` — Weekly Sales Rep Performance Dashboard

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `formatters/pipeline.py`, and `tools/rag.py` first.**

---

## CONTEXT — WHAT AND WHY

Sales reps and managers need a quick way to see how a rep is performing across all deal activity, coaching sessions, and pipeline movement. `/scorecard` gives a personalized performance snapshot — the kind of thing a manager would pull together manually from CRM reports.

This is a huge demo moment because it shows the AI isn't just reactive (answering questions), it's proactively **tracking and summarizing performance**.

---

## WHAT IT DOES

1. User types `/scorecard` (own metrics) or `/scorecard @username` (view someone else's)
2. Bot pulls data from:
   - HubSpot via RAG: deals owned by this rep, recent activity, deals moved/closed
   - In-memory roleplay state: coaching sessions completed, average scores
   - Mock/RAG pipeline data: deals progressed this week
3. LLM generates a performance summary
4. Bot posts a rich Block Kit scorecard

---

## STEP 1: Create `formatters/scorecard.py`

```python
"""Block Kit formatting for /scorecard command."""
from formatters.helpers import timestamp, format_currency


def format_scorecard_response(
    rep_name: str,
    period: str,
    metrics: dict,
    deal_activity: list,
    coaching_summary: dict,
    ai_insights: str,
) -> tuple[list, str]:
    """Format a rep performance scorecard as Block Kit.

    Args:
        rep_name: Display name of the rep
        period: Time period (e.g., "This Week", "Last 7 Days")
        metrics: Dict with keys: deals_progressed, deals_closed, revenue_closed,
                 emails_sent, meetings_booked, pipeline_delta
        deal_activity: List of dicts with 'name', 'action', 'detail' (e.g., moved to Negotiation)
        coaching_summary: Dict with keys: sessions_completed, avg_score, last_scenario
        ai_insights: LLM-generated performance insights and recommendations

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Performance emoji based on deals progressed
    deals_progressed = metrics.get("deals_progressed", 0)
    if deals_progressed >= 5:
        perf_emoji = "🔥"
        perf_label = "On Fire"
    elif deals_progressed >= 3:
        perf_emoji = "✅"
        perf_label = "Solid Week"
    elif deals_progressed >= 1:
        perf_emoji = "📊"
        perf_label = "Steady"
    else:
        perf_emoji = "⚠️"
        perf_label = "Needs Attention"

    # Deal activity list
    if deal_activity:
        activity_str = "\n".join([
            f"• *{d.get('name', 'Unknown')}* — {d.get('action', '')} {d.get('detail', '')}"
            for d in deal_activity[:8]
        ])
    else:
        activity_str = "_No deal activity this period_"

    # Coaching summary
    sessions = coaching_summary.get("sessions_completed", 0)
    avg_score = coaching_summary.get("avg_score", "N/A")
    last_scenario = coaching_summary.get("last_scenario", "None")
    coaching_str = f"• Sessions: {sessions}\n• Avg Score: {avg_score}/10\n• Last Practice: {last_scenario}"

    # Pipeline delta
    pipeline_delta = metrics.get("pipeline_delta", 0)
    delta_str = f"+{format_currency(pipeline_delta)}" if pipeline_delta >= 0 else f"-{format_currency(abs(pipeline_delta))}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{perf_emoji} Scorecard: {rep_name}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"📅 {period} • Performance: *{perf_label}*"}
            ]
        },

        # Top-line metrics
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Deals Progressed:*\n{deals_progressed}"},
                {"type": "mrkdwn", "text": f"*Deals Closed:*\n{metrics.get('deals_closed', 0)}"},
                {"type": "mrkdwn", "text": f"*Revenue Closed:*\n{format_currency(metrics.get('revenue_closed', 0))}"},
                {"type": "mrkdwn", "text": f"*Pipeline Delta:*\n{delta_str}"},
            ]
        },

        {"type": "divider"},

        # Deal activity
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recent Deal Activity:*\n{activity_str}"}
        },

        {"type": "divider"},

        # Coaching summary
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Coaching Progress:*\n{coaching_str}"}
        },

        {"type": "divider"},

        # AI insights
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*AI Insights:*\n{ai_insights}"}
        },

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Pipeline", "emoji": True},
                    "action_id": "refresh_pipeline",
                    "value": "refresh",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Coaching", "emoji": True},
                    "action_id": "start_coaching_from_scorecard",
                    "value": rep_name,
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Scorecard for {rep_name}: {deals_progressed} deals progressed, {metrics.get('deals_closed', 0)} closed"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.scorecard import format_scorecard_response
```

And add `"format_scorecard_response"` to `__all__`.

---

## STEP 3: Add Helper to Extract Rep Metrics from RAG/Mock

Add this helper function to `app.py` (near the other `extract_*` helpers):

```python
def extract_rep_metrics(user_id: str) -> dict:
    """Extract performance metrics for a rep from RAG and in-memory state.

    Returns dict with: rep_name, metrics, deal_activity, coaching_summary
    """
    from tools.rag import search_crm_deals
    from tools.mock_crm import get_all_open_deals, get_stale_deals

    # Get all deals (in production, filter by owner = user_id)
    all_deals = mock_crm.get_all_open_deals()
    stale_deals = mock_crm.get_stale_deals(days=7)

    # Calculate metrics
    deals_progressed = 0
    deals_closed = 0
    revenue_closed = 0
    deal_activity = []
    total_pipeline = 0

    for deal in all_deals:
        props = deal.get("properties", {})
        amount = float(props.get("amount", 0) or 0)
        stage = props.get("dealstage", "")
        total_pipeline += amount

        if stage in ("closedwon",):
            deals_closed += 1
            revenue_closed += amount
            deal_activity.append({
                "name": props.get("dealname", "Unknown"),
                "action": "🎉 Closed Won",
                "detail": format_currency(amount),
            })
        elif deal.get("_test_flag") not in ("stale", "overdue"):
            deals_progressed += 1
            deal_activity.append({
                "name": props.get("dealname", "Unknown"),
                "action": f"→ {stage}",
                "detail": format_currency(amount),
            })

    # Coaching summary from active_roleplays (in-memory)
    # Count completed roleplays (simple heuristic: threads no longer active)
    coaching_summary = {
        "sessions_completed": len([r for r in completed_roleplays]) if 'completed_roleplays' in dir() else 0,
        "avg_score": "N/A",
        "last_scenario": "None",
    }

    return {
        "metrics": {
            "deals_progressed": deals_progressed,
            "deals_closed": deals_closed,
            "revenue_closed": revenue_closed,
            "pipeline_delta": total_pipeline,
        },
        "deal_activity": deal_activity[:8],
        "coaching_summary": coaching_summary,
    }
```

---

## STEP 4: Add `/scorecard` Command Handler to `app.py`

```python
@app.command("/scorecard")
def handle_scorecard(ack, say, command):
    """Show rep performance scorecard."""
    ack()
    channel_id = command["channel_id"]
    user_id = command["user_id"]
    text = command["text"].strip()

    say(f"📊 Generating your scorecard...", channel=channel_id)

    # Extract metrics
    rep_data = extract_rep_metrics(user_id)

    # Run LLM for AI insights
    from tools.rag import search_playbooks
    rag_context = search_playbooks("sales performance best practices coaching improvement", n_results=3)

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Generate a brief performance insight for a sales rep.

Their metrics this week:
- Deals progressed: {rep_data['metrics']['deals_progressed']}
- Deals closed: {rep_data['metrics']['deals_closed']}
- Revenue closed: ${rep_data['metrics']['revenue_closed']:,}

Recent deal activity:
{json.dumps(rep_data['deal_activity'], indent=2)}

Based on these metrics, provide:
1. One specific strength to highlight (1 sentence)
2. One area to focus on this week (1 sentence)
3. One actionable recommendation (1 sentence)

Keep it concise — 3 sentences total.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    ai_insights = result["messages"][-1].content

    # Format and send
    from formatters import format_scorecard_response
    blocks, fallback = format_scorecard_response(
        rep_name=text if text else "You",
        period="This Week",
        metrics=rep_data["metrics"],
        deal_activity=rep_data["deal_activity"],
        coaching_summary=rep_data["coaching_summary"],
        ai_insights=ai_insights,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 5: Add Action Handler for "Start Coaching" Button

```python
@app.action("start_coaching_from_scorecard")
def handle_coaching_from_scorecard(ack, body, say):
    """Start a coaching session from the scorecard."""
    ack()
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    # Start a roleplay focused on the rep's weakest area
    say(
        text="🎯 Starting a practice session based on your scorecard...",
        channel=channel,
    )
    # Reuse existing coach logic — call handle_coach equivalent
    # Or post a suggestion: "Try `/coach roleplay discovery call` to practice"
    say(
        text="Try one of these:\n• `/coach roleplay discovery call` — practice opening\n• `/coach roleplay objection handling` — practice pushback\n• `/coach prep [company]` — prepare for your next meeting",
        channel=channel,
    )
```

---

## STEP 6: Track Completed Roleplays

In `app.py`, add a `completed_roleplays` list alongside the existing `active_roleplays` dict to track coaching history for the scorecard:

```python
# Add near the top with active_roleplays
completed_roleplays = []  # List of {user_id, scenario, score, timestamp}
```

Then in `handle_thread_reply()`, when a debrief is generated (turn_count >= 4), append to `completed_roleplays`:

```python
# After generating debrief, before removing from active_roleplays:
completed_roleplays.append({
    "user_id": active_roleplays[thread_ts]["user_id"],
    "scenario": active_roleplays[thread_ts].get("scenario", "Unknown"),
    "score": extracted_score,  # Parse from debrief text
    "timestamp": datetime.now().isoformat(),
})
```

---

## REGISTER IN SLACK

Add `/scorecard` slash command in api.slack.com:
- **Command:** `/scorecard`
- **Description:** `View your sales performance scorecard`
- **Usage Hint:** `[@username]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/scorecard.py` | New formatter for scorecard Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_scorecard_response` export |
| EDIT | `app.py` | Add `extract_rep_metrics()`, `handle_scorecard()`, `handle_coaching_from_scorecard()`, `completed_roleplays` list, update debrief to track completions |
