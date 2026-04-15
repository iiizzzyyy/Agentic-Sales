"""Block Kit formatters for CRM write confirmations."""
from formatters.helpers import timestamp


def format_note_confirmation(deal_name, note_body, mode):
    """Simple confirmation after logging a note."""
    mode_label = "Synced to HubSpot" if mode == "hubspot" else "Saved locally"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Note logged on {deal_name}*\n> {note_body[:300]}"}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{mode_label} · SalesCoach AI · {timestamp()}"}]
        }
    ]
    fallback = f"Note logged on {deal_name}: {note_body[:100]}"
    return blocks, fallback
