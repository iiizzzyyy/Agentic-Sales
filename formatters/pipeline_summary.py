"""Lightweight pipeline summary for /my-day integration."""
from formatters.helpers import format_currency
from tools.mock_crm import get_all_open_deals, get_stale_deals, get_overdue_deals


def get_pipeline_summary(user_id: str = None) -> dict:
    """Get compact pipeline metrics for /my-day display.

    Args:
        user_id: Optional user ID for filtering (currently returns all deals)

    Returns:
        dict with keys: total_value, deal_count, flagged_count, top_stage
    """
    deals = get_all_open_deals()

    # Calculate total value
    total_value = 0.0
    stage_counts = {}

    for deal in deals:
        amount = deal.get("properties", {}).get("amount", 0)
        try:
            total_value += float(amount or 0)
        except (ValueError, TypeError):
            pass

        stage = deal.get("properties", {}).get("dealstage", "Unknown")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Count flagged deals (stale or overdue)
    stale_deals = get_stale_deals()
    overdue_deals = get_overdue_deals()

    # Use set to avoid double-counting deals that are both stale AND overdue
    flagged_ids = set()
    for deal in stale_deals:
        flagged_ids.add(deal.get("id"))
    for deal in overdue_deals:
        flagged_ids.add(deal.get("id"))

    flagged_count = len(flagged_ids)

    # Find stage with most deals
    top_stage = None
    if stage_counts:
        top_stage = max(stage_counts.items(), key=lambda x: x[1])[0]

    return {
        "total_value": total_value,
        "deal_count": len(deals),
        "flagged_count": flagged_count,
        "top_stage": top_stage,
    }


def get_flagged_deals_detail(user_id: str = None) -> list:
    """Get detailed list of flagged deals for the 'See Flagged Deals' action.

    Args:
        user_id: Optional user ID for filtering

    Returns:
        List of dicts with id, name, flag type, and reason
    """
    stale_deals = get_stale_deals()
    overdue_deals = get_overdue_deals()

    flagged = []
    seen_ids = set()

    # Add stale deals
    for deal in stale_deals:
        deal_id = deal.get("id")
        if deal_id not in seen_ids:
            seen_ids.add(deal_id)
            deal_name = deal.get("properties", {}).get("dealname", "Unknown Deal")
            last_modified = deal.get("properties", {}).get("hs_lastmodifieddate", "")

            flagged.append({
                "id": deal_id,
                "name": deal_name,
                "flag": "stale",
                "reason": f"No activity in 14+ days" if last_modified else "No recent activity",
            })

    # Add overdue deals (may overlap with stale)
    for deal in overdue_deals:
        deal_id = deal.get("id")
        if deal_id not in seen_ids:
            seen_ids.add(deal_id)
            deal_name = deal.get("properties", {}).get("dealname", "Unknown Deal")
            close_date = deal.get("properties", {}).get("closedate", "")

            flagged.append({
                "id": deal_id,
                "name": deal_name,
                "flag": "overdue",
                "reason": f"Close date passed" if close_date else "Past close date",
            })

    return flagged
