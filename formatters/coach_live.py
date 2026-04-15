"""Block Kit formatting for /coach-live command."""
from formatters.helpers import timestamp, truncate


def format_coach_live_start(
    company_name: str,
    call_type: str,
) -> tuple[list, str]:
    """Format the start of a live coaching session.

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎧 Live Coaching Active", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Company:* {company_name}\n"
                    f"*Call Type:* {call_type}\n\n"
                    "I'm listening. Reply in this thread with what the buyer says and I'll coach you in real-time."
                )
            }
        },

        {"type": "divider"},

        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How to use:*\n"
                    "• Paste what the buyer said → I'll suggest your response\n"
                    "• Type `they asked about pricing` → I'll prep your answer\n"
                    "• Type `they objected: [objection]` → instant rebuttal\n"
                    "• Type `done` → session summary with score"
                )
            }
        },

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "End Session", "emoji": True},
                    "action_id": "end_live_coaching",
                    "style": "danger",
                    "value": "end",
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Live Coaching • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    fallback = f"Live Coaching Session Active for {company_name}. Call type: {call_type}. Reply in the thread with what the buyer says and receive real-time coaching suggestions."
    return blocks, fallback


def format_coach_live_tip(
    tip_type: str,
    suggestion: str,
    technique: str,
    avoid: str,
) -> tuple[list, str]:
    """Format a single coaching tip in the thread.

    Args:
        tip_type: "positive", "redirect", "warning", "technique"
        suggestion: What to say or do next
        technique: The sales technique being applied
        avoid: What NOT to do

    Returns:
        tuple: (blocks, fallback_text)
    """
    type_emoji = {
        "positive": "✅",
        "redirect": "🔄",
        "warning": "⚠️",
        "technique": "💡",
    }
    emoji = type_emoji.get(tip_type, "💡")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{suggestion}*"
            }
        },
    ]

    fields = []
    if technique:
        fields.append({"type": "mrkdwn", "text": f"*Technique:* {technique}"})
    if avoid:
        fields.append({"type": "mrkdwn", "text": f"*Avoid:* ❌ {avoid}"})

    if fields:
        blocks.append({
            "type": "section",
            "fields": fields,
        })

    fallback = f"{emoji} {suggestion}"
    return blocks, fallback


def format_coach_live_summary(
    company_name: str,
    call_type: str,
    turns: int,
    highlights: list,
    improvements: list,
    score: int,
) -> tuple[list, str]:
    """Format the end-of-session summary.

    Args:
        company_name: Company name
        call_type: Type of call
        turns: Number of coaching exchanges
        highlights: List of things done well
        improvements: List of areas to improve
        score: Overall score 1-10

    Returns:
        tuple: (blocks, fallback_text)
    """
    score_emoji = "🟢" if score >= 7 else "🟡" if score >= 5 else "🔴"

    highlights_text = "\n".join([f"• ✅ {h}" for h in highlights[:4]]) if highlights else "• No specific highlights"
    improvements_text = "\n".join([f"• 📈 {i}" for i in improvements[:4]]) if improvements else "• No specific improvements"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎧 Live Coaching Summary", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Call Type:*\n{call_type}"},
                {"type": "mrkdwn", "text": f"*Coaching Turns:*\n{turns}"},
                {"type": "mrkdwn", "text": f"*Score:*\n{score_emoji} {score}/10"},
            ]
        },

        {"type": "divider"},

        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*What Went Well:*\n{highlights_text}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Areas to Improve:*\n{improvements_text}"}
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Session Complete • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    highlights_summary = ", ".join(highlights[:3]) if highlights else "None noted"
    improvements_summary = ", ".join(improvements[:3]) if improvements else "None noted"
    fallback = f"Live Coaching Summary for {company_name}. Call type: {call_type}. {turns} coaching turns. Score: {score}/10. Highlights: {highlights_summary}. Areas to improve: {improvements_summary}."
    return blocks, fallback
