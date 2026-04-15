# Claude Code Instructions: `/win-loss` — Win/Loss Analysis

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/mock_crm.py`, `data/mock_bq/win_loss_analysis.csv`, and `data/mock_bq/pipeline_analytics.csv` first.**

---

## CONTEXT — WHAT AND WHY

`/win-loss` surfaces patterns from closed deals to help reps understand what works and what doesn't. It analyzes both historical CSV data (win rates by quarter, loss reasons) and individual deal activity notes to find patterns like "deals mentioning CompetitorAlpha close at half the rate" or "deals that stall in negotiation for 10+ days close 30% less often."

This is the "strategic intelligence" command — it helps managers coach and reps self-improve.

---

## WHAT IT DOES

1. User types `/win-loss` (overall analysis) or `/win-loss competitor` or `/win-loss Q1`
2. Bot loads: win_loss_analysis.csv, pipeline_analytics.csv, all deals from mock_crm (including closed won/lost)
3. Aggregates metrics: win rate trends, avg cycle length, top loss reasons, competitor correlation
4. LLM generates insights and recommendations
5. Bot posts Block Kit with: trend summary, pattern insights, and action buttons

---

## STEP 1: Create `formatters/win_loss.py`

```python
"""Block Kit formatting for /win-loss command."""
from formatters.helpers import timestamp, format_currency


def format_win_loss_response(
    overall_metrics: dict,
    trend_data: list,
    patterns: str,
    recommendations: list,
    filter_label: str,
) -> tuple[list, str]:
    """Format win/loss analysis as Block Kit.

    Args:
        overall_metrics: Dict with 'win_rate', 'avg_cycle_days', 'avg_deal_size', 'total_won', 'total_lost'
        trend_data: List of dicts with 'period', 'win_rate', 'deals_won', 'deals_lost'
        patterns: LLM-generated pattern analysis
        recommendations: List of recommendation strings
        filter_label: What filter was applied (e.g., "All Deals", "Q1 2026", "Competitor Deals")

    Returns:
        tuple: (blocks, fallback_text)
    """
    win_rate = overall_metrics.get("win_rate", 0)
    avg_cycle = overall_metrics.get("avg_cycle_days", 0)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📉 Win/Loss Analysis", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Filter: {filter_label} • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Key metrics
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Win Rate:*\n{win_rate:.0f}%"},
                {"type": "mrkdwn", "text": f"*Avg Cycle:*\n{avg_cycle:.0f} days"},
                {"type": "mrkdwn", "text": f"*Avg Deal Size:*\n{format_currency(overall_metrics.get('avg_deal_size', 0))}"},
                {"type": "mrkdwn", "text": f"*Won / Lost:*\n{overall_metrics.get('total_won', 0)} / {overall_metrics.get('total_lost', 0)}"},
            ]
        },

        {"type": "divider"},
    ]

    # Trend data
    if trend_data:
        trend_text = ""
        for t in trend_data[-5:]:
            bar = "🟢" if float(t.get("win_rate", 0)) >= 60 else "🟡" if float(t.get("win_rate", 0)) >= 40 else "🔴"
            trend_text += f"{bar} *{t['period']}:* {t['win_rate']}% win rate ({t.get('deals_won', '?')}W / {t.get('deals_lost', '?')}L)\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📈 Trend:*\n{trend_text}"}
        })
        blocks.append({"type": "divider"})

    # AI pattern analysis
    if patterns:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🧠 Patterns Detected:*\n{patterns}"}
        })
        blocks.append({"type": "divider"})

    # Recommendations
    if recommendations:
        rec_text = "\n".join([f"• 💡 {r}" for r in recommendations[:4]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📌 Recommendations:*\n{rec_text}"}
        })

    # Action buttons
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Lost Deals", "emoji": True},
                "action_id": "win_loss_lost_deals",
                "value": "lost",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Won Deals", "emoji": True},
                "action_id": "win_loss_won_deals",
                "value": "won",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Competitor Analysis", "emoji": True},
                "action_id": "win_loss_competitor",
                "value": "competitor",
            },
        ]
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Win/Loss Analysis • {timestamp()}"}
        ]
    })

    fallback = f"Win/Loss Analysis — Win Rate: {win_rate:.0f}% | Avg Cycle: {avg_cycle:.0f} days"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.win_loss import format_win_loss_response
```

And add `"format_win_loss_response"` to `__all__`.

---

## STEP 3: Add `/win-loss` Command Handler to `app.py`

```python
@app.command("/win-loss")
def handle_win_loss(ack, say, command):
    """Analyze win/loss patterns and trends."""
    ack()
    filter_text = command["text"].strip().lower()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    say(f"📉 Analyzing win/loss data...", channel=channel_id)

    # 1. Load data sources
    win_loss_csv = mock_crm.load_win_loss_analysis()
    all_deals = mock_crm.load_mock_crm()["deals"]

    # 2. Separate won and lost deals
    won_deals = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedwon", "closed won")]
    lost_deals = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedlost", "closed lost")]

    # 3. Calculate overall metrics
    total_won = len(won_deals)
    total_lost = len(lost_deals)
    total = total_won + total_lost
    win_rate = (total_won / total * 100) if total > 0 else 0

    won_amounts = [float(d["properties"].get("amount", 0) or 0) for d in won_deals]
    lost_amounts = [float(d["properties"].get("amount", 0) or 0) for d in lost_deals]
    all_amounts = won_amounts + lost_amounts
    avg_deal_size = sum(all_amounts) / len(all_amounts) if all_amounts else 0

    # Avg cycle from CSV if available
    avg_cycle = 0
    if win_loss_csv:
        cycles = [float(row.get("avg_sales_cycle_days", 0)) for row in win_loss_csv if row.get("avg_sales_cycle_days")]
        avg_cycle = sum(cycles) / len(cycles) if cycles else 0

    overall_metrics = {
        "win_rate": win_rate,
        "avg_cycle_days": avg_cycle,
        "avg_deal_size": avg_deal_size,
        "total_won": total_won,
        "total_lost": total_lost,
    }

    # 4. Trend data from CSV
    trend_data = []
    for row in win_loss_csv:
        trend_data.append({
            "period": row.get("quarter", "N/A"),
            "win_rate": row.get("win_rate", "0"),
            "deals_won": row.get("total_won", "0"),
            "deals_lost": row.get("total_lost", "0"),
        })

    # 5. Scan deal activities for patterns
    competitor_mentions = {}
    for deal in all_deals:
        stage = deal.get("properties", {}).get("dealstage", "").lower()
        for activity in deal.get("activities", []):
            body = activity.get("body", activity.get("note", "")).lower()
            for comp in ["competitoralpha", "competitorbeta", "competitorgamma"]:
                if comp in body.replace(" ", ""):
                    readable = comp.replace("competitor", "Competitor")
                    if readable not in competitor_mentions:
                        competitor_mentions[readable] = {"won": 0, "lost": 0}
                    if "won" in stage:
                        competitor_mentions[readable]["won"] += 1
                    elif "lost" in stage:
                        competitor_mentions[readable]["lost"] += 1

    # 6. LLM generates insights
    deal_summaries = ""
    for d in lost_deals[:5]:
        p = d.get("properties", {})
        activities_text = " | ".join([a.get("body", a.get("note", ""))[:80] for a in d.get("activities", [])[:2]])
        deal_summaries += f"  LOST: {p.get('dealname', '?')} (${float(p.get('amount', 0) or 0):,.0f}) — Notes: {activities_text}\n"
    for d in won_deals[:5]:
        p = d.get("properties", {})
        activities_text = " | ".join([a.get("body", a.get("note", ""))[:80] for a in d.get("activities", [])[:2]])
        deal_summaries += f"  WON: {p.get('dealname', '?')} (${float(p.get('amount', 0) or 0):,.0f}) — Notes: {activities_text}\n"

    comp_summary = ""
    for comp, counts in competitor_mentions.items():
        comp_summary += f"  {comp}: {counts['won']} won, {counts['lost']} lost\n"

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Analyze these win/loss patterns and provide insights.

OVERALL: {total_won} won, {total_lost} lost, {win_rate:.0f}% win rate, {avg_cycle:.0f} day avg cycle

QUARTERLY TREND:
{chr(10).join([f"  {t['period']}: {t['win_rate']}% ({t['deals_won']}W/{t['deals_lost']}L)" for t in trend_data]) or "  No trend data"}

COMPETITOR CORRELATION:
{comp_summary or "  No competitor mentions found"}

DEAL DETAILS:
{deal_summaries or "  No closed deals"}

Generate:
PATTERNS: [3-4 bullet points identifying specific patterns. Use data — percentages, deal names, competitor names. Start each with •]

RECOMMENDATION_1: [Actionable recommendation based on the patterns]
RECOMMENDATION_2: [Another recommendation]
RECOMMENDATION_3: [Another recommendation]

Be specific, not generic. Reference actual data from above.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    # 7. Parse
    patterns = ""
    recommendations = []

    for line in llm_response.split("\n"):
        line = line.strip()
        if line.upper().startswith("PATTERNS:"):
            patterns = line.split(":", 1)[1].strip()
        elif line.startswith("•"):
            patterns += "\n" + line
        elif line.upper().startswith("RECOMMENDATION_"):
            recommendations.append(line.split(":", 1)[1].strip() if ":" in line else line)

    if not patterns:
        patterns = llm_response[:2000]

    filter_label = filter_text.upper() if filter_text else "All Deals"

    # 8. Format and send
    from formatters import format_win_loss_response
    blocks, fallback = format_win_loss_response(
        overall_metrics=overall_metrics,
        trend_data=trend_data,
        patterns=patterns,
        recommendations=recommendations,
        filter_label=filter_label,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add Action Handlers

```python
@app.action("win_loss_lost_deals")
def handle_win_loss_lost(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    lost = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedlost", "closed lost")]

    if lost:
        text = "*Lost Deals:*\n"
        for d in lost:
            p = d.get("properties", {})
            text += f"• {p.get('dealname', '?')} — {format_currency(float(p.get('amount', 0) or 0))}\n"
    else:
        text = "No lost deals found in current data."

    client.chat_postMessage(channel=user_id, text=text)


@app.action("win_loss_won_deals")
def handle_win_loss_won(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    won = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedwon", "closed won")]

    if won:
        text = "*Won Deals:*\n"
        for d in won:
            p = d.get("properties", {})
            text += f"• {p.get('dealname', '?')} — {format_currency(float(p.get('amount', 0) or 0))}\n"
    else:
        text = "No won deals found in current data."

    client.chat_postMessage(channel=user_id, text=text)


@app.action("win_loss_competitor")
def handle_win_loss_competitor(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="Use `/competitor [name]` to get detailed competitive intel, or `/win-loss competitor` for competitor-specific analysis.",
    )
```

---

## REGISTER IN SLACK

Add `/win-loss` slash command in api.slack.com:
- **Command:** `/win-loss`
- **Description:** `Analyze win/loss patterns and trends`
- **Usage Hint:** `[filter: quarter, competitor — optional]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/win_loss.py` | New formatter for win/loss Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_win_loss_response` export |
| EDIT | `app.py` | Add `handle_win_loss()`, `handle_win_loss_lost()`, `handle_win_loss_won()`, `handle_win_loss_competitor()` |
