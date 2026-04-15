"""Block Kit formatting for /handoff command."""
from formatters.helpers import timestamp, format_currency, truncate


def format_handoff_summary(
    deal_name: str,
    company_name: str,
    deal_summary: dict,
    key_contacts: list,
    conversation_history: str,
    risk_factors: list,
    next_steps: list,
    competitor_mentions: list,
    deal_id: str = "",
) -> tuple[list, str]:
    """Compact handoff summary — the first thing the user sees.

    Returns:
        tuple: (blocks, fallback_text)
    """
    stage = deal_summary.get("stage", "N/A")
    amount = deal_summary.get("amount", 0)
    close_date = deal_summary.get("close_date", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 Deal Handoff: {truncate(deal_name, 50)}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:* {company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:* {stage}"},
                {"type": "mrkdwn", "text": f"*Value:* {format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close:* {close_date}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{len(key_contacts)} contacts* · *{len(risk_factors)} risks* · *{len(next_steps)} next steps*"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Show Full Handoff Brief", "emoji": True},
                    "action_id": "expand_handoff",
                    "value": deal_id or deal_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal Card", "emoji": True},
                    "action_id": "view_deal_from_handoff",
                    "value": deal_id or deal_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Introduction Email", "emoji": True},
                    "action_id": "draft_handoff_email",
                    "value": f"{deal_name}||{company_name}",
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

    fallback = f"Deal Handoff: {deal_name} — {stage} — {format_currency(amount)}"
    return blocks, fallback


def format_handoff_response(
    deal_name: str,
    company_name: str,
    deal_summary: dict,
    key_contacts: list,
    conversation_history: str,
    risk_factors: list,
    next_steps: list,
    competitor_mentions: list,
    deal_id: str = "",
) -> tuple[list, str]:
    """Format a deal handoff brief as Block Kit.

    Args:
        deal_name: Name of the deal
        company_name: Company name
        deal_summary: Dict with 'stage', 'amount', 'close_date', 'owner', 'created'
        key_contacts: List of dicts with 'name', 'title', 'email', 'role_in_deal'
        conversation_history: LLM-generated narrative of deal history
        risk_factors: List of risk strings
        next_steps: List of recommended next step strings
        competitor_mentions: List of competitor names mentioned in notes
        deal_id: Optional unique deal ID for reliable lookup

    Returns:
        tuple: (blocks, fallback_text)
    """
    stage = deal_summary.get("stage", "Unknown")
    amount = deal_summary.get("amount", 0)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 Deal Handoff: {truncate(deal_name, 50)}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Comprehensive brief for deal transition • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Deal snapshot
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{deal_summary.get('close_date', 'N/A')}"},
            ]
        },

        {"type": "divider"},
    ]

    # Key contacts with truncation indicator
    MAX_CONTACTS = 5
    if key_contacts:
        displayed_contacts = key_contacts[:MAX_CONTACTS]
        contacts_text = ""
        for c in displayed_contacts:
            role = f" — _{c.get('role_in_deal', '')}_" if c.get('role_in_deal') else ""
            contacts_text += f"• *{c['name']}* ({c.get('title', 'N/A')}){role}\n  {c.get('email', '')}\n"
        if len(key_contacts) > MAX_CONTACTS:
            remaining = len(key_contacts) - MAX_CONTACTS
            contacts_text += f"_+ {remaining} more contact{'s' if remaining != 1 else ''}_\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👥 Key Contacts:*\n{contacts_text}"}
        })
        blocks.append({"type": "divider"})

    # Conversation history (narrative)
    if conversation_history:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📜 Deal Story:*\n{truncate(conversation_history, 2500)}"}
        })
        blocks.append({"type": "divider"})

    # Competitor mentions
    if competitor_mentions:
        comp_text = ", ".join([f"*{c}*" for c in competitor_mentions])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*⚔️ Competitors Mentioned:* {comp_text}"}
        })

    # Risk factors with truncation indicator
    MAX_RISKS = 5
    if risk_factors:
        displayed_risks = risk_factors[:MAX_RISKS]
        risk_text = "\n".join([f"• ⚠️ {r}" for r in displayed_risks])
        if len(risk_factors) > MAX_RISKS:
            remaining = len(risk_factors) - MAX_RISKS
            risk_text += f"\n_+ {remaining} more risk{'s' if remaining != 1 else ''}_"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🚨 Risk Factors:*\n{risk_text}"}
        })

    # Next steps with truncation indicator
    MAX_STEPS = 5
    if next_steps:
        displayed_steps = next_steps[:MAX_STEPS]
        steps_text = "\n".join([f"• ✅ {s}" for s in displayed_steps])
        if len(next_steps) > MAX_STEPS:
            remaining = len(next_steps) - MAX_STEPS
            steps_text += f"\n_+ {remaining} more step{'s' if remaining != 1 else ''}_"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📌 Recommended Next Steps:*\n{steps_text}"}
        })

    # Action buttons
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Deal Card", "emoji": True},
                "action_id": "view_deal_from_handoff",
                "value": deal_id or deal_name,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Draft Introduction Email", "emoji": True},
                "action_id": "draft_handoff_email",
                "value": f"{deal_name}||{company_name}",
            },
        ]
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Deal Handoff • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    contacts_summary = ", ".join([c['name'] for c in key_contacts[:3]]) if key_contacts else "No contacts"
    risks_summary = ", ".join(risk_factors[:2]) if risk_factors else "No risks identified"
    fallback = f"Deal Handoff Brief for {deal_name} at {company_name}. Stage: {stage}. Value: {format_currency(amount)}. Key contacts: {contacts_summary}. Risks: {risks_summary}."
    return blocks, fallback
