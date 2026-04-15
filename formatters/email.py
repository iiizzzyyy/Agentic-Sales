"""Block Kit formatting for /draft-email command."""
import json
from formatters.helpers import timestamp, format_currency


def format_contact_picker(
    company_name: str,
    contacts: list,
    email_context: dict,
    page: int = 0,
    page_size: int = 10,
) -> tuple[list, str]:
    """Format a paginated contact selection list before drafting an email.

    Args:
        company_name: Company name for the header
        contacts: List of dicts with 'name', 'title', 'email', 'source'
        email_context: Dict with context to pass through to the email draft action.
            Must include 'company_name' and optionally 'deal_name', 'trigger'.
            This gets JSON-encoded into the button value.
        page: Current page (0-indexed)
        page_size: Items per page

    Returns:
        tuple: (blocks, fallback_text)
    """
    total_contacts = len(contacts)
    start = page * page_size
    end = start + page_size
    display_contacts = contacts[start:end]
    total_pages = (total_contacts + page_size - 1) // page_size

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "✉️ Who should this email go to?", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Drafting follow-up for *{company_name}* — showing {start + 1}–{min(end, total_contacts)} of {total_contacts} contacts."}
            ]
        },
        {"type": "divider"},
    ]

    for contact in display_contacts:
        name = contact.get("name", "Unknown")
        title = contact.get("title", "")
        email = contact.get("email", "")
        source = contact.get("source", "")

        # Show where this contact came from
        source_tag = ""
        if source == "deal":
            source_tag = " · 📌 _Deal contact_"
        elif source == "company":
            source_tag = " · 🏢 _Company contact_"

        # Build button value with contact info + email context
        button_value = json.dumps({
            "contact_name": name,
            "contact_email": email,
            "company_name": email_context.get("company_name", company_name),
            "deal_name": email_context.get("deal_name", ""),
            "trigger": email_context.get("trigger", "direct"),
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{name}*\n{title} · {email}{source_tag}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Select", "emoji": True},
                "action_id": "select_email_contact",
                "value": button_value,
            }
        })

    blocks.append({"type": "divider"})

    # Pagination buttons (only if more than one page)
    if total_pages > 1:
        nav_elements = []
        if page > 0:
            nav_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "← Previous", "emoji": True},
                "action_id": "contact_picker_prev",
                "value": json.dumps({
                    "company_name": company_name,
                    "page": page - 1,
                    "email_context": email_context,
                }),
            })
        if end < total_contacts:
            nav_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Next →", "emoji": True},
                "action_id": "contact_picker_next",
                "value": json.dumps({
                    "company_name": company_name,
                    "page": page + 1,
                    "email_context": email_context,
                }),
            })
        if nav_elements:
            blocks.append({"type": "actions", "elements": nav_elements})

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • Page {page + 1} of {total_pages} • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    contact_list = ", ".join([f"{c.get('name', 'Unknown')} ({c.get('title', '')})" for c in display_contacts[:5]])
    fallback = f"Select a recipient for email draft to {company_name}. Showing {start + 1}-{min(end, total_contacts)} of {total_contacts}: {contact_list}"
    return blocks, fallback


def format_email_draft(
    company_name: str,
    to_name: str,
    to_email: str,
    subject: str,
    body: str,
) -> tuple[list, str]:
    """Format an email draft as Block Kit.

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Prepare data for button values
    email_data = json.dumps({"to": to_email, "subject": subject, "body": body})

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Draft Follow-Up: {company_name}", "emoji": True}
        },

        # Email metadata in fields
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*To:*\n{to_name} <{to_email}>"},
                {"type": "mrkdwn", "text": f"*Subject:*\n{subject}"},
            ]
        },

        {"type": "divider"},

        # Email body
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": body}
        },

        {"type": "divider"},

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Gmail Draft", "emoji": True},
                    "style": "primary",
                    "action_id": "create_gmail_draft",
                    "value": email_data,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Regenerate", "emoji": True},
                    "action_id": "regenerate_email",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Copy Text", "emoji": True},
                    "action_id": "copy_email_text",
                    "value": json.dumps({"subject": subject, "body": body}),
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Based on HubSpot deal context + your email playbook • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    fallback = f"Email Draft for {company_name}. To: {to_name} ({to_email}). Subject: {subject}. Body preview: {body[:150]}..."
    return blocks, fallback


def format_email_deal_picker(
    company_name: str,
    deals: list,
    email_context: dict = None,
    page: int = 0,
    page_size: int = 10,
) -> tuple[list, str]:
    """Format a paginated deal picker for email drafting.

    Args:
        company_name: Company name
        deals: List of deal dicts with name, stage, amount, id
        email_context: Context to pass through to the next step
        page: Current page (0-indexed)
        page_size: Items per page

    Returns:
        (blocks, fallback_text)
    """
    total_deals = len(deals)
    start = page * page_size
    end = start + page_size
    display_deals = deals[start:end]
    total_pages = (total_deals + page_size - 1) // page_size

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "✉️ Which deal is this email about?", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*{company_name}* — showing {start + 1}–{min(end, total_deals)} of {total_deals} deal{'s' if total_deals != 1 else ''}."}
            ]
        },
        {"type": "divider"},
    ]

    for deal in display_deals:
        deal_name = deal.get("name", "Unknown Deal")
        stage = deal.get("stage", "unknown")
        amount = deal.get("amount", 0)
        deal_id = deal.get("id", "")

        # Format value
        if isinstance(amount, (int, float)) and amount > 0:
            value_str = format_currency(amount)
        else:
            value_str = "N/A"

        action_value = json.dumps({
            "deal_name": deal_name,
            "deal_id": deal_id,
            "company_name": company_name,
            "stage": stage,
            "value": value_str,
            **(email_context or {}),
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{deal_name}*\nStage: {stage} | Value: {value_str}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Select Deal", "emoji": True},
                "action_id": "select_email_deal",
                "value": action_value,
            }
        })

    blocks.append({"type": "divider"})

    # Pagination buttons (only if more than one page)
    if total_pages > 1:
        nav_elements = []
        if page > 0:
            nav_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "← Previous", "emoji": True},
                "action_id": "email_deal_picker_prev",
                "value": json.dumps({
                    "company_name": company_name,
                    "page": page - 1,
                    "email_context": email_context or {},
                }),
            })
        if end < total_deals:
            nav_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Next →", "emoji": True},
                "action_id": "email_deal_picker_next",
                "value": json.dumps({
                    "company_name": company_name,
                    "page": page + 1,
                    "email_context": email_context or {},
                }),
            })
        if nav_elements:
            blocks.append({"type": "actions", "elements": nav_elements})

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • Page {page + 1} of {total_pages} • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    deal_list = ", ".join([f"{d.get('name', 'Unknown')} ({d.get('stage', 'N/A')})" for d in display_deals[:5]])
    fallback = f"Select a deal for {company_name} email. Showing {start + 1}-{min(end, total_deals)} of {total_deals}: {deal_list}"
    return blocks, fallback
