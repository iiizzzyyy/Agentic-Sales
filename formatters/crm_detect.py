"""Block Kit formatter for the auto-detect CRM logging suggestion."""

import json


def format_crm_suggestion(
    original_text: str,
    extracted: dict,
    message_ts: str,
    channel_id: str
) -> tuple[list[dict], str]:
    """Format the ephemeral suggestion card.

    Args:
        original_text: The original Slack message (truncated for display)
        extracted: Dict from LLM classification with company, summary, next_steps, sentiment
        message_ts: Timestamp of the original message (for threading)
        channel_id: Channel where the message was posted

    Returns:
        (blocks, fallback_text) tuple
    """
    company = extracted.get("company", "Unknown")
    summary = extracted.get("summary", original_text[:200])
    next_steps = extracted.get("next_steps")
    sentiment = extracted.get("sentiment", "neutral")

    # Sentiment emoji
    sentiment_emoji = {
        "positive": ":large_green_circle:",
        "neutral": ":large_yellow_circle:",
        "negative": ":red_circle:",
        "mixed": ":large_blue_circle:"
    }.get(sentiment, ":large_yellow_circle:")

    # Build the note preview
    note_preview = f"*{company}*\n{summary}"
    if next_steps:
        note_preview += f"\n\n:clipboard: Next steps: {next_steps}"

    # Action payload — everything needed to log without re-processing
    log_payload = json.dumps({
        "company": company,
        "summary": summary,
        "next_steps": next_steps,
        "sentiment": sentiment,
        "source_channel": channel_id,
        "source_ts": message_ts,
    })

    blocks = [
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":bulb: Looks like a loggable interaction — want to save it to CRM?"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{sentiment_emoji} {note_preview}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Log to CRM", "emoji": True},
                    "style": "primary",
                    "action_id": "auto_crm_confirm",
                    "value": log_payload
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Edit & Log", "emoji": True},
                    "action_id": "auto_crm_edit",
                    "value": log_payload
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss", "emoji": True},
                    "action_id": "auto_crm_dismiss",
                    "value": "dismiss"
                }
            ]
        }
    ]

    return blocks, f"Log to CRM? {company}: {summary[:100]}"
