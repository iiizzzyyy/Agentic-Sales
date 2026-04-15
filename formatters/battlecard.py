"""Block Kit formatting for /battlecard command."""
from formatters.helpers import timestamp, truncate


# Known competitors from the battle cards playbook
KNOWN_COMPETITORS = ["CompetitorAlpha", "CompetitorBeta", "CompetitorGamma", "Build In-House"]


def format_battlecard_picker() -> tuple[list, str]:
    """Format a competitor picker when no competitor specified.

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚔️ Battle Cards", "emoji": True}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Select a competitor to view their battle card:"}
        },

        {"type": "divider"},

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorAlpha", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorAlpha",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorBeta", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorBeta",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorGamma", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorGamma",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. Build In-House", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "Build In-House",
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Or type `/battlecard [name]` directly • {timestamp()}"}
            ]
        },
    ]

    fallback = "Select a competitor to view their battle card"
    return blocks, fallback


def format_battlecard_response(
    competitor_name: str,
    positioning: str,
    strengths: list,
    weaknesses: list,
    how_to_win: list,
    landmine_questions: list,
) -> tuple[list, str]:
    """Format a competitor battle card as Block Kit.

    Args:
        competitor_name: Name of the competitor
        positioning: Their market positioning statement
        strengths: List of their strengths
        weaknesses: List of their weaknesses
        how_to_win: List of strategies to win against them
        landmine_questions: List of questions to plant

    Returns:
        tuple: (blocks, fallback_text)
    """
    strengths_text = "\n".join([f"• 💪 {s}" for s in strengths[:5]]) if strengths else "• No data"
    weaknesses_text = "\n".join([f"• 🎯 {w}" for w in weaknesses[:5]]) if weaknesses else "• No data"
    win_text = "\n".join([f"• ✅ {w}" for w in how_to_win[:5]]) if how_to_win else "• No data"
    landmine_text = "\n".join([f"• 💣 _{q}_" for q in landmine_questions[:4]]) if landmine_questions else "• No data"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"⚔️ Battle Card: vs. {competitor_name}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Q1 2026 • Confidential: Internal Use Only • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Positioning
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Their Positioning:* _{positioning}_"}
        },

        {"type": "divider"},

        # Strengths and weaknesses side by side
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Their Strengths:*\n{strengths_text}"},
                {"type": "mrkdwn", "text": f"*Their Weaknesses:*\n{weaknesses_text}"},
            ]
        },

        {"type": "divider"},

        # How to win
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🏆 How to Win:*\n{win_text}"}
        },

        {"type": "divider"},

        # Landmine questions
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*💣 Landmine Questions to Plant:*\n{landmine_text}"}
        },

        {"type": "divider"},

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice Objection", "emoji": True},
                    "action_id": "battlecard_practice",
                    "value": competitor_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Get Full Competitor Analysis", "emoji": True},
                    "action_id": "battlecard_full_analysis",
                    "value": competitor_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
                    "action_id": "battlecard_draft_email",
                    "value": competitor_name,
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Battle Cards • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    fallback = f"Battle Card vs. {competitor_name}. Positioning: {positioning}. Strengths: {', '.join(strengths[:3]) if strengths else 'None'}. Weaknesses: {', '.join(weaknesses[:3]) if weaknesses else 'None'}. How to win: {', '.join(how_to_win[:2]) if how_to_win else 'N/A'}."
    return blocks, fallback
