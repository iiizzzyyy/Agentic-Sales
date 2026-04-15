"""Block Kit formatting for /deal command."""
import json
from datetime import datetime, timedelta
from formatters.helpers import timestamp, format_currency, truncate


# Stage emoji mapping
STAGE_EMOJI = {
    "discovery": "🔎",
    "qualification": "📋",
    "demo scheduled": "📺",
    "demoscheduled": "📺",
    "demo_scheduled": "📺",
    "proposal sent": "📄",
    "proposalsent": "📄",
    "proposal_sent": "📄",
    "negotiation": "🤝",
    "closedwon": "🎉",
    "closed_won": "🎉",
    "closedlost": "❌",
    "closed_lost": "❌",
}


def get_smart_actions(deal_data, search_term=None):
    """Return context-aware action buttons based on deal state.

    Priority logic:
    1. If deal is stale (no activity in 14+ days) → primary: "Re-engage Contact"
    2. If deal is in late stage (Negotiation/Contract) → primary: "Draft Email"
    3. If deal has no contact → primary: "Research Company"
    4. Default → primary: "Draft Email"

    Returns:
        tuple: (action_elements, context_hint, is_stale, days_since_activity)
    """
    deal_name = deal_data.get("name", "Unknown")
    company_name = deal_data.get("company", deal_data.get("name", "Unknown"))
    stage = deal_data.get("stage", "").lower()
    last_activity = deal_data.get("last_activity_date")
    deal_id = deal_data.get("id", "")

    # Determine staleness
    is_stale = False
    days_since_activity = 0
    if last_activity:
        try:
            last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            now = datetime.now(last_dt.tzinfo) if last_dt.tzinfo else datetime.now()
            delta = now - last_dt
            days_since_activity = delta.days
            is_stale = days_since_activity >= 14
        except (ValueError, TypeError):
            pass

    has_contact = bool(deal_data.get("primary_contact") or deal_data.get("contacts"))
    late_stage = stage in ("negotiation", "contract sent", "closing", "proposal", "proposal sent")

    # Build primary action based on context
    if is_stale and has_contact:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Re-engage Contact", "emoji": True},
            "action_id": "draft_email_from_deal",
            "value": company_name,
            "style": "primary",
        }
        context_hint = f"No activity in {days_since_activity} days — consider reaching out"
    elif not has_contact:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Research Company", "emoji": True},
            "action_id": "research_from_deal_direct",
            "value": company_name,
            "style": "primary",
        }
        context_hint = "No contact linked — research the company to find decision makers"
    else:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
            "action_id": "draft_email_from_deal",
            "value": company_name,
            "style": "primary",
        }
        context_hint = None

    # Build action elements list
    action_elements = []
    if search_term:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "← Back to Results", "emoji": True},
            "action_id": "back_to_deal_results",
            "value": search_term,
        })

    action_elements.append(primary)

    # Overflow for secondary actions (only add if they're NOT already the primary)
    overflow_options = []
    if primary["action_id"] != "research_from_deal_direct":
        overflow_options.append({
            "text": {"type": "plain_text", "text": "Research Company"},
            "value": f"research_from_deal|{company_name}",
        })
    if primary["action_id"] != "draft_email_from_deal":
        overflow_options.append({
            "text": {"type": "plain_text", "text": "Draft Email"},
            "value": f"draft_email_from_deal|{company_name}",
        })
    overflow_options.append({
        "text": {"type": "plain_text", "text": "Log a Note"},
        "value": f"log_note|{deal_id or deal_name}",
    })

    if overflow_options:
        action_elements.append({
            "type": "overflow",
            "action_id": "deal_overflow",
            "options": overflow_options,
        })

    return action_elements, context_hint, is_stale, days_since_activity


def format_deal_response(
    deal: dict,
    contacts: list,
    activities: list,
    recommendations: str,
    search_term: str = None,
) -> tuple[list, str]:
    """Format a deal status card as Block Kit.

    Args:
        deal: Deal data dict
        contacts: List of contacts
        activities: List of activities
        recommendations: LLM-generated recommendations
        search_term: If provided, adds "Back to Results" button for multi-deal navigation

    Returns:
        tuple: (blocks, fallback_text)
    """
    deal_name = deal.get("name", "Unknown Deal")
    stage = deal.get("stage", "Unknown")
    amount = deal.get("amount", 0)
    close_date = deal.get("close_date", "N/A")
    owner = deal.get("owner", "Unassigned")
    company = deal.get("company", deal_name)
    deal_id = deal.get("id", "")

    # Get emoji for stage
    stage_key = stage.lower().replace(" ", "").replace("_", "")
    emoji = STAGE_EMOJI.get(stage_key, "📊")

    # Build recent activity string with truncation indicator
    MAX_ACTIVITIES = 4
    if activities:
        displayed_activities = activities[:MAX_ACTIVITIES]
        activity_str = "\n".join([
            f"• _{a.get('date', 'N/A')[:10]}_ — {truncate(a.get('body', 'No details'), 120)}"
            for a in displayed_activities
        ])
        if len(activities) > MAX_ACTIVITIES:
            remaining = len(activities) - MAX_ACTIVITIES
            activity_str += f"\n_+ {remaining} more activit{'ies' if remaining != 1 else 'y'}_"
    else:
        activity_str = "_No recent activity — add notes with `/deal [company] note: [update]`_"

    # Primary contact
    if contacts:
        primary = contacts[0]
        contact_text = f"*Primary Contact:*\n{primary.get('name', 'Unknown')} — {primary.get('title', 'N/A')}\n{primary.get('email', 'N/A')}"
        deal["primary_contact"] = primary  # For smart actions
    else:
        contact_text = "*Primary Contact:*\n_No contact linked — use `/research [company]` to find contacts_"

    # Build smart action buttons based on deal context
    deal_data_for_actions = {
        **deal,
        "company": company,
        "contacts": contacts,
    }
    action_elements, context_hint, is_stale, days_since = get_smart_actions(deal_data_for_actions, search_term=search_term)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {deal_name}", "emoji": True}
        },

        # Deal metrics in 2-column grid
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Amount:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{close_date}"},
                {"type": "mrkdwn", "text": f"*Owner:*\n{owner}"},
            ]
        },

        {"type": "divider"},

        # Primary contact
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": contact_text}
        },

        # Recent activity
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recent Activity:*\n{activity_str}"}
        },

        {"type": "divider"},

        # Recommended next actions (from LLM)
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recommended Next Actions:*\n{recommendations}"}
        },

        # Action buttons
        {
            "type": "actions",
            "elements": action_elements
        },
    ]

    # Add context hint if smart actions determined one
    if context_hint:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"💡 _{context_hint}_"}]
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • HubSpot data • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    fallback = f"Deal: {deal_name}. Stage: {stage}. Amount: {format_currency(amount)}. Close date: {close_date}. Owner: {owner}. {len(contacts)} contacts, {len(activities)} recent activities. Recommendations: {recommendations[:150]}..."
    return blocks, fallback


def format_deal_picker(
    search_term: str,
    deals: list,
    page: int = 0,
    page_size: int = 10,
) -> tuple[list, str]:
    """Format a paginated deal selection list when multiple deals match.

    Args:
        search_term: What the user searched for (e.g., "Horizon Education")
        deals: List of deal dicts, each with: name, amount, stage, close_date, id
        page: Current page (0-indexed)
        page_size: Items per page

    Returns:
        tuple: (blocks, fallback_text)
    """
    total_deals = len(deals)
    start = page * page_size
    end = start + page_size
    display_deals = deals[start:end]
    total_pages = (total_deals + page_size - 1) // page_size

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Deals matching \"{search_term}\"", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing {start + 1}–{min(end, total_deals)} of {total_deals} deal{'s' if total_deals != 1 else ''}. Select one to view details."}
            ]
        },
        {"type": "divider"},
    ]

    for deal in display_deals:
        deal_name = deal.get("name", "Unknown Deal")
        stage = deal.get("stage", "N/A")
        amount = deal.get("amount", 0)
        close_date = deal.get("close_date", "N/A")
        deal_id = deal.get("id", "")

        # Get emoji for stage
        stage_key = stage.lower().replace(" ", "").replace("_", "")
        emoji = STAGE_EMOJI.get(stage_key, "📊")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{emoji} {deal_name}*\n{stage} • {format_currency(amount)} • Close: {close_date}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open Deal", "emoji": True},
                "action_id": "view_deal_detail",
                "value": json.dumps({
                    "deal_name": deal_name,
                    "deal_id": deal_id,
                    "search_term": search_term,
                }),
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
                "action_id": "deal_picker_prev",
                "value": json.dumps({"search_term": search_term, "page": page - 1}),
            })
        if end < total_deals:
            nav_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Next →", "emoji": True},
                "action_id": "deal_picker_next",
                "value": json.dumps({"search_term": search_term, "page": page + 1}),
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
    deal_summaries = "; ".join([f"{d.get('name', 'Unknown')}: {d.get('stage', 'N/A')}, {format_currency(d.get('amount', 0))}" for d in display_deals[:5]])
    fallback = f"Deals matching '{search_term}' — showing {start + 1}-{min(end, total_deals)} of {total_deals}. {deal_summaries}"
    return blocks, fallback
