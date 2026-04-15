"""Block Kit formatting for /coach command."""
import json
from formatters.helpers import timestamp


def format_roleplay_start(persona: dict, scenario: str) -> tuple[list, str]:
    """Format the initial roleplay setup message (Block Kit).

    Returns:
        tuple: (blocks, fallback_text)
    """
    persona_name = persona.get("name", "The Buyer")
    persona_title = persona.get("title", "Decision Maker")
    persona_company = persona.get("company", "Prospect Inc")
    persona_personality = persona.get("personality", "Professional and skeptical")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Roleplay Session Starting", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Scenario:*\n{scenario}"},
                {"type": "mrkdwn", "text": "*Turns:*\n3-4 exchanges, then debrief"},
                {"type": "mrkdwn", "text": "*You are:*\nThe sales rep"},
                {"type": "mrkdwn", "text": f"*I am:*\n{persona_name}, {persona_title}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Buyer Profile:*\n• *Name:* {persona_name}\n• *Title:* {persona_title} at {persona_company}\n• *Personality:* {persona_personality}\n\n_Reply in this thread to begin. I'll stay in character as {persona_name}._"
            }
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Tip: Treat this like a real call. Use discovery questions, handle objections, and try to advance the deal."}
            ]
        },
    ]

    # Rich fallback for screen readers
    fallback = f"Roleplay session starting. Scenario: {scenario}. You are the sales rep. The buyer is {persona_name}, {persona_title} at {persona_company}. Personality: {persona_personality}. Reply in the thread to begin."
    return blocks, fallback


def format_roleplay_debrief(
    score: int,
    strengths: list,
    improvements: list,
    next_practice: str,
    scenario: str = "",
    company: str = "",
    scenario_type: str = "discovery",
) -> tuple[list, str]:
    """Format the final debrief scorecard (Block Kit).

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Score color indicator
    if score >= 8:
        score_display = f"*{score}/10* — Excellent"
    elif score >= 6:
        score_display = f"*{score}/10* — Good, room to grow"
    else:
        score_display = f"*{score}/10* — Needs work"

    strengths_str = "\n".join([f"• {s}" for s in strengths]) if strengths else "_No specific strengths noted_"
    improvements_str = "\n".join([f"• {i}" for i in improvements]) if improvements else "_No specific improvements noted_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Roleplay Debrief", "emoji": True}
        },

        # Score
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Overall Score:* {score_display}"}
        },

        {"type": "divider"},

        # Strengths
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*What You Did Well:*\n{strengths_str}"}
        },

        # Areas to improve
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Areas to Improve:*\n{improvements_str}"}
        },

        {"type": "divider"},

        # Next practice suggestion
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recommended Practice:*\n{next_practice}"}
        },

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice Again", "emoji": True},
                    "style": "primary",
                    "action_id": "practice_again",
                    "value": scenario,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Try Suggested Scenario", "emoji": True},
                    "action_id": "try_suggested",
                    "value": next_practice,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Log to CRM", "emoji": True},
                    "action_id": "log_coaching_to_crm",
                    "value": json.dumps({
                        "session_type": "roleplay",
                        "score": score,
                        "scenario": scenario,
                        "company": company,
                        "scenario_type": scenario_type,
                    }),
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Scored against your sales playbook • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    strengths_summary = ", ".join(strengths[:3]) if strengths else "None noted"
    improvements_summary = ", ".join(improvements[:3]) if improvements else "None noted"
    fallback = f"Roleplay Debrief. Score: {score}/10. Strengths: {strengths_summary}. Areas to improve: {improvements_summary}. Recommended next practice: {next_practice}"
    return blocks, fallback
