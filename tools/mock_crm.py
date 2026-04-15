"""
Mock CRM data loader for local testing when MCP servers aren't connected.
Loads synthetic data from data/mock_crm/ and data/mock_bq/.
"""

import os
import json
import csv
import glob
from datetime import datetime, timedelta

# Base paths
MOCK_CRM_DIR = "data/mock_crm"
MOCK_BQ_DIR = "data/mock_bq"

# Cached data
_crm_data = None


def load_mock_crm() -> dict:
    """Load synthetic CRM data for local testing. Cached after first load."""
    global _crm_data
    if _crm_data is not None:
        return _crm_data

    _crm_data = {"companies": [], "contacts": [], "deals": []}

    # Load companies
    companies_path = os.path.join(MOCK_CRM_DIR, "companies.json")
    if os.path.exists(companies_path):
        with open(companies_path, encoding="utf-8") as f:
            _crm_data["companies"] = json.load(f)

    # Load contacts
    contacts_path = os.path.join(MOCK_CRM_DIR, "contacts.json")
    if os.path.exists(contacts_path):
        with open(contacts_path, encoding="utf-8") as f:
            _crm_data["contacts"] = json.load(f)

    # Load deals
    deals_path = os.path.join(MOCK_CRM_DIR, "deals.json")
    if os.path.exists(deals_path):
        with open(deals_path, encoding="utf-8") as f:
            _crm_data["deals"] = json.load(f)

    # Load owners
    owners_path = os.path.join(MOCK_CRM_DIR, "owners.json")
    if os.path.exists(owners_path):
        with open(owners_path, encoding="utf-8") as f:
            _crm_data["owners"] = json.load(f)
    else:
        _crm_data["owners"] = []

    _enrich_contact_owners()
    return _crm_data


def search_company(name: str) -> dict | None:
    """Search mock CRM by company name (fuzzy match)."""
    crm_data = load_mock_crm()
    name_lower = name.lower()

    for company in crm_data["companies"]:
        company_name = company.get("properties", {}).get("name", "")
        if name_lower in company_name.lower():
            return company

    return None


def is_known_mock_company(name: str) -> bool:
    """Check if a company name matches a known synthetic/demo company."""
    crm_data = load_mock_crm()
    name_lower = name.lower()

    for company in crm_data["companies"]:
        company_name = company.get("properties", {}).get("name", "")
        if name_lower in company_name.lower() or company_name.lower() in name_lower:
            return True
    return False


def get_mock_company_full_name(name: str) -> str | None:
    """Get the full name of a mock company by partial match."""
    crm_data = load_mock_crm()
    name_lower = name.lower()

    for company in crm_data["companies"]:
        company_name = company.get("properties", {}).get("name", "")
        if name_lower in company_name.lower():
            return company_name
    return None


def get_company_by_id(company_id: str) -> dict | None:
    """Get a company by its ID."""
    crm_data = load_mock_crm()

    for company in crm_data["companies"]:
        if company.get("id") == company_id:
            return company

    return None


def get_deals_for_company(company_id: str) -> list[dict]:
    """Get all deals associated with a company."""
    crm_data = load_mock_crm()
    deals = []

    for deal in crm_data["deals"]:
        associations = deal.get("associations", {})
        if associations.get("company") == company_id:
            deals.append(deal)

    return deals


def search_deal(name: str) -> dict | None:
    """Search for a deal by name (fuzzy match)."""
    crm_data = load_mock_crm()
    name_lower = name.lower()

    for deal in crm_data["deals"]:
        deal_name = deal.get("properties", {}).get("dealname", "")
        if name_lower in deal_name.lower():
            return deal

    return None


def get_deal_by_id(deal_id: str) -> dict | None:
    """Get a deal by its unique ID."""
    crm_data = load_mock_crm()
    for deal in crm_data["deals"]:
        if deal.get("id") == deal_id:
            return deal
    return None


def get_deal_by_name(deal_name: str) -> dict | None:
    """Get a deal by its name (fallback when ID is not available)."""
    crm_data = load_mock_crm()
    for deal in crm_data["deals"]:
        if deal.get("properties", {}).get("dealname") == deal_name:
            return deal
    return None


def get_contacts_for_company(company_id: str) -> list[dict]:
    """Get contacts associated with a company."""
    crm_data = load_mock_crm()
    contacts = []

    for contact in crm_data["contacts"]:
        associations = contact.get("associations", {})
        # Check both "company" and "company_id" keys for compatibility
        if associations.get("company") == company_id or associations.get("company_id") == company_id:
            contacts.append(contact)

    return contacts


def get_contact_by_id(contact_id: str) -> dict | None:
    """Look up a contact by its ID."""
    crm_data = load_mock_crm()
    for contact in crm_data["contacts"]:
        if contact.get("id") == contact_id:
            return contact
    return None


def get_all_open_deals() -> list[dict]:
    """Get all open deals (not closed won/lost) for pipeline analysis."""
    crm_data = load_mock_crm()
    open_deals = []

    closed_stages = ["closedwon", "closedlost", "closed won", "closed lost"]

    for deal in crm_data["deals"]:
        stage = deal.get("properties", {}).get("dealstage", "").lower()
        if stage not in closed_stages:
            open_deals.append(deal)

    return open_deals


def get_stale_deals(stale_days: int = 14) -> list[dict]:
    """Find deals with no activity in N days (for /pipeline)."""
    crm_data = load_mock_crm()
    stale = []

    for deal in crm_data["deals"]:
        # Check test flag first
        if deal.get("_test_flag") == "stale":
            stale.append(deal)
            continue

        # Otherwise check actual dates
        last_modified = deal.get("properties", {}).get("hs_lastmodifieddate")
        if last_modified:
            try:
                last_date = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
                days_since = (datetime.now(last_date.tzinfo) - last_date).days
                if days_since > stale_days:
                    stale.append(deal)
            except Exception:
                pass

    return stale


def get_overdue_deals() -> list[dict]:
    """Find deals past their close date."""
    crm_data = load_mock_crm()
    overdue = []

    for deal in crm_data["deals"]:
        # Check test flag first
        if deal.get("_test_flag") == "overdue":
            overdue.append(deal)
            continue

        # Otherwise check actual dates
        close_date = deal.get("properties", {}).get("closedate")
        if close_date:
            try:
                close = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
                if close < datetime.now(close.tzinfo):
                    overdue.append(deal)
            except Exception:
                pass

    return overdue


def load_email_thread(company_name: str) -> dict | None:
    """Load mock email thread for a company."""
    email_threads_dir = os.path.join(MOCK_CRM_DIR, "email_threads")
    if not os.path.exists(email_threads_dir):
        return None

    company_lower = company_name.lower().replace(" ", "")

    for filepath in glob.glob(os.path.join(email_threads_dir, "*.json")):
        with open(filepath, encoding="utf-8") as f:
            thread = json.load(f)

        # Check if company name appears in thread subject or participants
        subject = thread.get("subject", "").lower()
        if company_lower in subject.replace(" ", ""):
            return thread

        for participant in thread.get("participants", []):
            email = participant.get("email", "").lower()
            if company_lower in email:
                return thread

    return None


def load_call_transcript(company_name: str) -> str | None:
    """Load call transcript for a company."""
    transcripts_dir = os.path.join(MOCK_CRM_DIR, "call_transcripts")
    if not os.path.exists(transcripts_dir):
        return None

    company_lower = company_name.lower()

    for filepath in glob.glob(os.path.join(transcripts_dir, "*.md")):
        filename = os.path.basename(filepath).lower()
        if company_lower in filename:
            with open(filepath, encoding="utf-8") as f:
                return f.read()

    return None


def load_meeting_notes(company_name: str) -> str | None:
    """Load meeting notes for a company."""
    notes_dir = os.path.join(MOCK_CRM_DIR, "meeting_notes")
    if not os.path.exists(notes_dir):
        return None

    company_lower = company_name.lower()

    for filepath in glob.glob(os.path.join(notes_dir, "*.md")):
        filename = os.path.basename(filepath).lower()
        if company_lower in filename:
            with open(filepath, encoding="utf-8") as f:
                return f.read()

    return None


def load_pipeline_analytics() -> list[dict]:
    """Load mock BigQuery pipeline analytics data."""
    analytics_path = os.path.join(MOCK_BQ_DIR, "pipeline_analytics.csv")
    if not os.path.exists(analytics_path):
        return []

    with open(analytics_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_win_loss_analysis() -> list[dict]:
    """Load mock BigQuery win/loss analysis data."""
    analysis_path = os.path.join(MOCK_BQ_DIR, "win_loss_analysis.csv")
    if not os.path.exists(analysis_path):
        return []

    with open(analysis_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def format_company_for_display(company: dict) -> str:
    """Format a company dict into a readable string."""
    props = company.get("properties", {})
    lines = [f"*{props.get('name', 'Unknown Company')}*"]

    if props.get("domain"):
        lines.append(f"Domain: {props['domain']}")
    if props.get("industry"):
        lines.append(f"Industry: {props['industry']}")
    if props.get("numberofemployees"):
        lines.append(f"Employees: {props['numberofemployees']}")
    if props.get("city") or props.get("state"):
        location = ", ".join(filter(None, [props.get("city"), props.get("state")]))
        lines.append(f"Location: {location}")

    return "\n".join(lines)


def format_deal_for_display(deal: dict) -> str:
    """Format a deal dict into a readable string."""
    props = deal.get("properties", {})
    lines = [f"*{props.get('dealname', 'Unknown Deal')}*"]

    if props.get("dealstage"):
        lines.append(f"Stage: {props['dealstage']}")
    if props.get("amount"):
        try:
            amount = float(props["amount"])
            lines.append(f"Value: ${amount:,.2f}")
        except (ValueError, TypeError):
            lines.append(f"Value: {props['amount']}")
    if props.get("closedate"):
        lines.append(f"Close Date: {props['closedate'][:10]}")

    # Include activities if present
    activities = deal.get("activities", [])
    if activities:
        lines.append("\n*Recent Activity:*")
        for activity in activities[:3]:
            note = activity.get("note", "")[:150]
            lines.append(f"• {note}")

    return "\n".join(lines)


def format_contact_for_display(contact: dict) -> str:
    """Format a contact dict into a readable string."""
    props = contact.get("properties", {})
    name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip() or "Unknown"
    title = props.get("jobtitle", "No title")
    email = props.get("email", "")

    return f"• {name} ({title}) - {email}"


def parse_battle_cards() -> dict:
    """Parse the competitive_battle_cards.md playbook into structured data.

    Returns:
        Dict mapping competitor names to their battle card data.
    """
    battle_cards_path = os.path.join("data", "playbooks", "competitive_battle_cards.md")
    if not os.path.exists(battle_cards_path):
        return {}

    with open(battle_cards_path, encoding="utf-8") as f:
        content = f.read()

    cards = {}
    current_competitor = None
    current_section = None
    current_items = []

    for line in content.split("\n"):
        line = line.strip()

        # Detect competitor header
        if line.startswith("## BATTLE CARD: vs."):
            if current_competitor:
                # Save previous section
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items

            competitor_name = line.replace("## BATTLE CARD: vs.", "").strip()
            current_competitor = competitor_name
            cards[current_competitor] = {
                "positioning": "",
                "strengths": [],
                "weaknesses": [],
                "how_to_win": [],
                "landmine_questions": [],
            }
            current_section = None
            current_items = []

        elif current_competitor:
            if line.startswith("**Their Positioning:**"):
                cards[current_competitor]["positioning"] = line.replace("**Their Positioning:**", "").strip().strip('"')
            elif line.startswith("**Their Strengths:**"):
                current_section = "strengths"
                current_items = []
            elif line.startswith("**Their Weaknesses:**"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "weaknesses"
                current_items = []
            elif line.startswith("**How to Win:**"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "how_to_win"
                current_items = []
            elif line.startswith("**Landmine Questions"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "landmine_questions"
                current_items = []
            elif line.startswith("- ") and current_section:
                item = line[2:].strip().strip('"')
                # Remove numbering like "1. "
                if item and item[0].isdigit() and ". " in item:
                    item = item.split(". ", 1)[1]
                current_items.append(item)

    # Save last section
    if current_competitor and current_section and current_items:
        cards[current_competitor][current_section] = current_items

    return cards


# ──────────────────────────────────────────────
# Contact owner enrichment
# ──────────────────────────────────────────────

def _enrich_contact_owners():
    """Add hubspot_owner_id to contacts based on their company's deal owners."""
    crm_data = load_mock_crm()

    # Build company → owner map (use the first deal's owner for each company)
    company_owner_map = {}
    for deal in crm_data["deals"]:
        company_id = deal.get("associations", {}).get("company")
        if company_id and company_id not in company_owner_map:
            owner_id = deal.get("properties", {}).get("hubspot_owner_id")
            if owner_id:
                company_owner_map[company_id] = owner_id

    # Enrich contacts
    for contact in crm_data["contacts"]:
        if "hubspot_owner_id" not in contact.get("properties", {}):
            company_id = contact.get("associations", {}).get("company_id") or contact.get("associations", {}).get("company")
            if company_id and company_id in company_owner_map:
                contact.setdefault("properties", {})["hubspot_owner_id"] = company_owner_map[company_id]


# ──────────────────────────────────────────────
# Owner-filtered wrappers
# ──────────────────────────────────────────────

def _filter_by_owner(deals: list[dict], owner_id: str | None) -> list[dict]:
    """Filter a list of deals by hubspot_owner_id. If owner_id is None, return all (manager mode)."""
    if owner_id is None:
        return deals
    return [d for d in deals if d.get("properties", {}).get("hubspot_owner_id") == owner_id]


def get_all_open_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get open deals, optionally filtered by owner. None = all (manager)."""
    return _filter_by_owner(get_all_open_deals(), owner_id)


def get_stale_deals_for_user(stale_days: int = 14, owner_id: str | None = None) -> list[dict]:
    """Get stale deals, optionally filtered by owner."""
    return _filter_by_owner(get_stale_deals(stale_days), owner_id)


def get_overdue_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get overdue deals, optionally filtered by owner."""
    return _filter_by_owner(get_overdue_deals(), owner_id)


def get_all_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get ALL deals (including closed), optionally filtered by owner."""
    crm_data = load_mock_crm()
    return _filter_by_owner(crm_data["deals"], owner_id)


def get_companies_for_user(owner_id: str | None = None) -> list[dict]:
    """Get companies that have at least one deal owned by this user.
    If owner_id is None, return all companies (manager mode).
    """
    if owner_id is None:
        return load_mock_crm()["companies"]

    # Find company IDs from user's deals
    user_deals = get_all_deals_for_user(owner_id)
    company_ids = set()
    for deal in user_deals:
        company_id = deal.get("associations", {}).get("company")
        if company_id:
            company_ids.add(company_id)

    # Return matching companies
    return [c for c in load_mock_crm()["companies"] if c.get("id") in company_ids]


def search_deal_for_user(name: str, owner_id: str | None = None) -> dict | None:
    """Search for a deal by name, respecting ownership.
    If owner_id is None, return any match (manager mode).
    """
    deal = search_deal(name)
    if deal is None:
        return None
    if owner_id is None:
        return deal
    if deal.get("properties", {}).get("hubspot_owner_id") == owner_id:
        return deal
    return None
