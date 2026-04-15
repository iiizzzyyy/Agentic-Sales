"""Block Kit formatting for /research command."""
from formatters.helpers import timestamp, format_currency


def format_research_summary(
    company_name: str,
    company_data: dict,
    contacts: list,
    deals: list,
    news: list,
    talking_points: str,
) -> tuple[list, str]:
    """Compact research summary — the first thing the user sees.

    Returns:
        tuple: (blocks, fallback_text)
    """
    industry = company_data.get("industry", "N/A")
    size = company_data.get("size", "N/A")
    revenue = company_data.get("revenue", "N/A")

    # One-line summaries
    contact_summary = f"{len(contacts)} contact{'s' if len(contacts) != 1 else ''}"
    deal_summary = f"{len(deals)} active deal{'s' if len(deals) != 1 else ''}"
    news_summary = f"{len(news)} recent article{'s' if len(news) != 1 else ''}"

    # Extract first talking point
    first_talking_point = "N/A"
    if talking_points:
        lines = talking_points.strip().split("\n")
        for line in lines:
            cleaned = line.strip().lstrip("•-1234567890. ")
            if cleaned:
                first_talking_point = cleaned[:200]
                break

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Research Brief: {company_name}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Industry:* {industry}"},
                {"type": "mrkdwn", "text": f"*Size:* {size} employees"},
                {"type": "mrkdwn", "text": f"*Revenue:* {revenue}"},
                {"type": "mrkdwn", "text": f"*Data:* {contact_summary} · {deal_summary} · {news_summary}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Top Talking Point:* {first_talking_point}"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Show Full Brief", "emoji": True},
                    "action_id": "expand_research",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Follow-Up Email", "emoji": True},
                    "action_id": "draft_email_from_research",
                    "value": company_name,
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Roleplay", "emoji": True},
                    "action_id": "start_roleplay_from_research",
                    "value": company_name,
                },
            ]
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}
            ]
        },
    ]

    fallback = (
        f"Research Brief: {company_name}. "
        f"Industry: {industry}. Size: {size}. Revenue: {revenue}. "
        f"{contact_summary}, {deal_summary}, {news_summary}."
    )

    return blocks, fallback


def format_research_response(
    company_name: str,
    company_data: dict,
    contacts: list,
    deals: list,
    news: list,
    talking_points: str,
) -> tuple[list, str]:
    """Format a research brief as Block Kit.

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Build contacts string with truncation indicator
    MAX_CONTACTS = 5
    if contacts:
        displayed_contacts = contacts[:MAX_CONTACTS]
        contacts_str = "\n".join([
            f"• *{c.get('name', 'Unknown')}* — {c.get('title', 'N/A')} ({c.get('email', 'N/A')})"
            for c in displayed_contacts
        ])
        if len(contacts) > MAX_CONTACTS:
            remaining = len(contacts) - MAX_CONTACTS
            contacts_str += f"\n_+ {remaining} more contact{'s' if remaining != 1 else ''}_"
    else:
        contacts_str = "_No contacts in CRM yet — add contacts in HubSpot_"

    # Build deals string with truncation indicator
    MAX_DEALS = 5
    if deals:
        displayed_deals = deals[:MAX_DEALS]
        deals_str = "\n".join([
            f"• *{d.get('name', 'Unknown')}* — {d.get('stage', 'N/A')} — {format_currency(d.get('amount', 0))}"
            for d in displayed_deals
        ])
        if len(deals) > MAX_DEALS:
            remaining = len(deals) - MAX_DEALS
            deals_str += f"\n_+ {remaining} more deal{'s' if remaining != 1 else ''} — use `/deal` to search_"
    else:
        deals_str = "_No active deals — create one in HubSpot to track opportunities_"

    # Build news string with truncation indicator
    MAX_NEWS = 3
    if news:
        displayed_news = news[:MAX_NEWS]
        news_str = "\n".join([f"• {n.get('title', n) if isinstance(n, dict) else n}" for n in displayed_news])
        if len(news) > MAX_NEWS:
            remaining = len(news) - MAX_NEWS
            news_str += f"\n_+ {remaining} more article{'s' if remaining != 1 else ''}_"
    else:
        news_str = "_No recent news found — check back later_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Research Brief: {company_name}", "emoji": True}
        },

        # Company overview in 2-column layout
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Industry:*\n{company_data.get('industry', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Size:*\n{company_data.get('size', 'N/A')} employees"},
                {"type": "mrkdwn", "text": f"*HQ:*\n{company_data.get('hq', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Revenue:*\n{company_data.get('revenue', 'N/A')}"},
            ]
        },

        {"type": "divider"},

        # Key contacts
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Key Contacts:*\n{contacts_str}"}
        },

        # Active deals
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Active Deals:*\n{deals_str}"}
        },

        {"type": "divider"},

        # Recent news
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recent News:*\n{news_str}"}
        },

        # Talking points (from LLM)
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Talking Points:*\n{talking_points}"}
        },

        {"type": "divider"},

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Follow-Up Email", "emoji": True},
                    "action_id": "draft_email_from_research",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Roleplay", "emoji": True},
                    "action_id": "start_roleplay_from_research",
                    "value": company_name,
                },
            ]
        },

        # Footer
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Data from HubSpot + Tavily • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    contact_names = ", ".join([c.get('name', 'Unknown') for c in contacts[:3]]) if contacts else "None"
    deal_names = ", ".join([d.get('name', 'Unknown') for d in deals[:3]]) if deals else "None"
    fallback = f"Research Brief for {company_name}. Industry: {company_data.get('industry', 'N/A')}. Size: {company_data.get('size', 'N/A')} employees. {len(contacts)} contacts: {contact_names}. {len(deals)} deals: {deal_names}. Talking points: {talking_points[:150]}..."
    return blocks, fallback
