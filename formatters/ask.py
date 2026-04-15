"""Block Kit formatting for /ask command."""
from formatters.helpers import timestamp, truncate


def format_ask_response(
    question: str,
    answer: str,
    data_sources: list,
    related_actions: list,
) -> tuple[list, str]:
    """Format a natural language CRM answer as Block Kit.

    Args:
        question: The original question
        answer: LLM-generated answer
        data_sources: List of source descriptions (e.g., "HubSpot CRM", "Sales Playbooks")
        related_actions: List of dicts with 'label', 'action_id', 'value'

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Data sources tag
    sources_str = " • ".join(data_sources) if data_sources else "AI Knowledge"

    # Truncate answer if too long for Slack
    truncated_answer = truncate(answer, 2800)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Answer", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"_You asked: {truncate(question, 100)}_"}
            ]
        },

        {"type": "divider"},

        # The answer
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": truncated_answer}
        },
    ]

    # Add action buttons if any related actions are suggested
    if related_actions:
        action_elements = []
        for action in related_actions[:4]:  # Max 4 buttons
            action_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": action.get("label", "View"), "emoji": True},
                "action_id": action.get("action_id", "noop"),
                "value": action.get("value", "") or "none",
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": action_elements,
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Sources: {sources_str} • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    fallback = f"Answer to your question '{truncate(question, 50)}': {truncate(answer, 300)}. Sources: {sources_str}."
    return blocks, fallback
