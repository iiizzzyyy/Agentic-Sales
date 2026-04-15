"""Block Kit formatting for the Slack App Home tab."""
from datetime import datetime
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
                    "value": deal.get("name", "") or "unknown",
                }
            })
    else:
        attention_blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "All deals look healthy! No immediate action needed."}
        }]

    # Recent coaching
    if recent_coaching and recent_coaching.get("scenario"):
        coaching_text = (
            f"Last session: *{recent_coaching.get('scenario', 'N/A')}*\n"
            f"Score: {recent_coaching.get('score', 'N/A')}/10 • {recent_coaching.get('date', 'Recently')}"
        )
    else:
        coaching_text = "No coaching sessions yet. Try `/coach roleplay discovery call` to get started!"

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
            "text": {"type": "plain_text", "text": "Pipeline at a Glance", "emoji": True}
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
            "text": {"type": "plain_text", "text": "Needs Your Attention", "emoji": True}
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
            "text": {"type": "plain_text", "text": "Quick Actions", "emoji": True}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Pipeline", "emoji": True},
                    "action_id": "home_pipeline",
                    "value": "pipeline",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Follow-Ups", "emoji": True},
                    "action_id": "home_followups",
                    "value": "followups",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice", "emoji": True},
                    "action_id": "home_practice",
                    "value": "practice",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Scorecard", "emoji": True},
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
                    "text": {"type": "plain_text", "text": "Research Company", "emoji": True},
                    "action_id": "home_research",
                    "value": "research",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Ask a Question", "emoji": True},
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
                        "`/objection [text]` • `/competitor [name]` • `/followup`"
                    )
                }
            ]
        },
    ]

    return blocks
