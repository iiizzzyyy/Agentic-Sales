"""
Sales AI Agents - Slack Bot POC
Main entry point: Slack Bolt app with Socket Mode

Uses MCP servers for HubSpot, BigQuery, Gmail integration.
Block Kit formatting for all responses.
"""
import os
import json
import asyncio
import re
import traceback
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_core.messages import HumanMessage

load_dotenv()

# Initialize Slack app
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Import formatters
from formatters import (
    format_research_response,
    format_research_summary,
    format_deal_response,
    format_roleplay_start,
    format_roleplay_debrief,
    format_email_draft,
    format_pipeline_response,
    format_handoff_response,
    format_handoff_summary,
)

# Import mock CRM for data extraction
from tools import mock_crm

# Import user access control
from tools.user_access import resolve_slack_user, is_manager

# Import database module (replaces settings_store)
from db import (
    init_db, get_user_settings, update_user_settings, log_engagement,
    save_training_session, get_training_history, get_training_stats,
    get_team_training_summary, get_dimension_averages,
    # Scenario functions
    save_scenario, get_scenario, list_scenarios, increment_scenario_usage,
    # Assignment functions
    create_assignment, get_user_assignments, complete_assignment, get_team_assignments_summary,
    # Cohort functions
    create_cohort, add_cohort_participant, add_cohort_week, add_scenario_to_week,
    get_cohort, get_cohort_progress, list_cohorts
)

# Import skill analyzer for gap detection
from tools.skill_analyzer import analyze_skill_gaps
from formatters.skill_gaps import format_skill_gaps

# Import Wave commands tools and formatters
from tools.calendar import get_user_events, get_customer_meetings
from tools.documents import get_battlecard, search_documents, list_documents
from tools.market_insights import get_daily_digest, get_competitor_news, search_insights
from formatters.calendar import format_my_day, format_meeting_prep
from formatters.team_dashboard import format_team_dashboard, format_rep_detail
from formatters.cohort import format_cohort_list, format_cohort_progress, format_create_cohort_modal, format_onboard_confirmation
from formatters.market_insights import format_market_insights, format_competitor_detail, format_insights_search_results
from utils.language import get_ui_string, get_llm_language_prompt, format_language_options_for_slack

# Import methodology tools
from tools.methodology import load_methodology, build_scoring_prompt
from prompts.coach_prompts import get_roleplay_system_prompt

# Load MCP tools at startup
print("Loading MCP tools...")
from mcp_setup import get_mcp_tools_safe

try:
    mcp_tools = asyncio.run(get_mcp_tools_safe())
    print(f"Loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}")
except Exception as e:
    print(f"Warning: Could not load MCP tools: {e}")
    print("Continuing without MCP tools (limited functionality)")
    mcp_tools = []

# Initialize SQLite database (creates tables if not exist)
init_db()
print("Database initialized.")

# Initialize memory tables for Hive Mind orchestration
from graphs.memory_agent import init_memory_tables
init_memory_tables()
print("Memory tables initialized.")

# Build the main graph with MCP tools (using triage graph)
from graphs.triage import build_main_graph as build_triage_graph
app_graph = build_triage_graph(mcp_tools)
print("Triage graph compiled successfully.")

# Import continue_roleplay for thread handling
from graphs.coach import continue_roleplay

# In-memory roleplay state (POC only — production uses LangGraph checkpointer)
active_roleplays = {}

# Caches for progressive disclosure (expand buttons)
research_cache = {}  # {cache_key: {company_data, contacts, deals, news, talking_points}}
handoff_cache = {}   # {cache_key: {deal_name, company_name, deal_summary, ...}}

# Roleplay configuration
DEFAULT_ROLEPLAY_TURNS = 4
MIN_ROLEPLAY_TURNS = 3
MAX_ROLEPLAY_TURNS = 12

# --- Auto-CRM Detection Configuration (Wave 1E) ---
# Channels where auto-CRM-detect is active (comma-separated channel IDs via env var)
AUTO_CRM_CHANNELS = set(
    os.environ.get("AUTO_CRM_CHANNELS", "").split(",")
) - {""}

# Minimum LLM confidence score to show the suggestion (0.0-1.0)
AUTO_CRM_CONFIDENCE_THRESHOLD = float(os.environ.get("AUTO_CRM_CONFIDENCE_THRESHOLD", "0.7"))

# Cooldown: don't suggest to the same user more than once every N seconds
AUTO_CRM_COOLDOWN_SECONDS = int(os.environ.get("AUTO_CRM_COOLDOWN_SECONDS", "60"))
_auto_crm_cooldown: dict[str, float] = {}  # user_id -> last_suggestion_timestamp


# --- User Access Context Helpers ---

def get_user_context(user_id: str, client=None) -> dict:
    """Resolve the current Slack user's CRM access context.

    Returns:
        dict with keys:
          - role: "manager" | "rep" | "unlinked"
          - owner_id: str | None — the HubSpot owner ID (None for managers)
          - owner_name: str | None
          - filter_owner_id: str | None — pass this to _for_user() functions
              * For managers: None (sees everything)
              * For reps: their owner_id (sees only their records)
              * For unlinked: "__none__" (sees nothing — triggers a helpful message)
    """
    access = resolve_slack_user(user_id, client)

    if access["role"] == "manager":
        filter_id = None  # None means "no filter" → sees everything
    elif access["role"] == "rep":
        filter_id = access["owner_id"]
    else:
        filter_id = "__none__"  # Will match no records

    return {
        **access,
        "filter_owner_id": filter_id,
    }


def _send_unlinked_message(say, channel_id, slack_email=None):
    """Send a helpful message when a user's Slack email doesn't match any HubSpot owner."""
    if slack_email:
        msg = (
            f":warning: Your Slack email (`{slack_email}`) doesn't match any HubSpot record owner.\n"
            "Ask a sales manager to run `/settings add-manager @you` to give you manager access, "
            "or update your HubSpot owner email to match your Slack email."
        )
    else:
        msg = (
            ":warning: Couldn't look up your Slack email. "
            "Make sure your Slack profile has an email address set."
        )
    say(channel=channel_id, text=msg)


def _ownership_context_block(ctx: dict) -> list:
    """Return a Block Kit context element showing whose data is being displayed."""
    if ctx["role"] == "manager":
        return [{
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": ":eyes: *Manager view* — showing all records"}]
        }]
    elif ctx["role"] == "rep" and ctx.get("owner_name"):
        return [{
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":bust_in_silhouette: Showing records owned by *{ctx['owner_name']}*"}]
        }]
    return []


# Import CRM detector (deferred to avoid circular imports)
from tools.crm_detector import (
    passes_keyword_filter,
    build_classification_prompt,
    parse_classification_response,
    CRM_DETECT_SYSTEM_PROMPT,
)
from formatters.crm_detect import format_crm_suggestion


# --- Error handling helper ---

def handle_error(say, channel_id, command_name, error):
    """Report errors to both terminal and Slack."""
    error_msg = str(error)
    tb = traceback.format_exc()

    # Print full traceback to terminal
    print(f"\n{'='*60}")
    print(f"ERROR in {command_name}:")
    print(tb)
    print(f"{'='*60}\n")

    # Send user-friendly error to Slack
    say(
        text=f"⚠️ Something went wrong with `{command_name}`. Error: {error_msg[:300]}",
        channel=channel_id,
    )


def handle_action_error(client, channel_id, action_name, error):
    """Report action handler errors to both terminal and Slack."""
    error_msg = str(error)
    tb = traceback.format_exc()

    # Print full traceback to terminal
    print(f"\n{'='*60}")
    print(f"ERROR in action {action_name}:")
    print(tb)
    print(f"{'='*60}\n")

    # Send user-friendly error to Slack
    client.chat_postMessage(
        channel=channel_id,
        text=f"⚠️ Something went wrong. Error: {error_msg[:300]}",
    )


# --- Response channel helper for privacy-aware responses ---

def get_response_channel(client, user_id, original_channel, content_type="general"):
    """Determine where to post the response based on content sensitivity and user settings.

    Args:
        client: Slack WebClient
        user_id: The requesting user's ID
        original_channel: The channel the command was run in
        content_type: "general", "coaching", or "performance"

    Returns:
        (target_channel, should_notify_original): tuple
    """
    settings = get_user_settings(user_id)

    # General content always goes to the original channel unless user prefers DM
    if content_type == "general":
        if settings["response_mode"] == "dm":
            dm = client.conversations_open(users=[user_id])
            return dm["channel"]["id"], True
        return original_channel, False

    # Coaching/performance content respects coaching_privacy setting
    if content_type in ("coaching", "performance"):
        if settings["coaching_privacy"]:
            dm = client.conversations_open(users=[user_id])
            return dm["channel"]["id"], True
        return original_channel, False

    return original_channel, False


# --- Debrief parsing helpers ---

def parse_debrief_scores(debrief_text):
    """Extract structured JSON scores from the LLM debrief response.

    The LLM outputs a ```json block at the end of the debrief.
    Returns parsed dict or None if parsing fails.
    """
    # Find JSON block between ```json and ```
    pattern = r'```json\s*\n(.*?)\n\s*```'
    match = re.search(pattern, debrief_text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def strip_json_block(debrief_text):
    """Remove the JSON block from the debrief for display purposes."""
    pattern = r'\s*```json\s*\n.*?\n\s*```\s*'
    return re.sub(pattern, '', debrief_text, flags=re.DOTALL).strip()


# --- Helper functions for extracting data ---

def parse_rag_text(text: str) -> dict:
    """Parse RAG text output into a dict of field: value pairs."""
    result = {}
    for line in text.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower().replace(" ", "_")] = value.strip()
    return result


def extract_company_data(company_name: str) -> dict:
    """Extract structured company data from RAG (HubSpot synced data)."""
    from tools.rag import search_crm_companies
    rag_result = search_crm_companies(company_name, n_results=1)

    # Parse the RAG text output
    parsed = parse_rag_text(rag_result)

    # Format revenue with currency
    revenue = parsed.get("annual_revenue", "N/A")
    if revenue and revenue != "N/A" and revenue != "None":
        try:
            revenue = f"${int(float(revenue)):,}"
        except (ValueError, TypeError):
            pass

    # Build location from city/state/country
    location_parts = []
    if parsed.get("city") and parsed.get("city") != "None":
        location_parts.append(parsed["city"])
    if parsed.get("state") and parsed.get("state") != "None":
        location_parts.append(parsed["state"])
    if parsed.get("country") and parsed.get("country") != "None":
        location_parts.append(parsed["country"])
    hq = ", ".join(location_parts) if location_parts else "N/A"

    return {
        "industry": parsed.get("industry", "N/A") if parsed.get("industry") != "None" else "N/A",
        "size": parsed.get("number_of_employees", "N/A") if parsed.get("number_of_employees") != "None" else "N/A",
        "hq": hq,
        "revenue": revenue if revenue != "None" else "N/A",
    }


def extract_contacts(company_name: str) -> list:
    """Extract contacts for a company from RAG (filtered by company metadata)."""
    from tools.rag import search_contacts_by_company
    rag_result = search_contacts_by_company(company_name, n_results=5)

    contacts = []
    # Split by document separator
    for doc in rag_result.split("---"):
        if "Contact:" not in doc:
            continue
        parsed = parse_rag_text(doc)
        name = parsed.get("contact", "Unknown")
        if name and name != "Unknown":
            contacts.append({
                "name": name,
                "title": parsed.get("job_title", "N/A") if parsed.get("job_title") != "N/A" else "N/A",
                "email": parsed.get("email", "N/A"),
            })
    return contacts


def get_contacts_for_deal_or_company(
    deal_name: str = None,
    company_name: str = None,
) -> list:
    """Get contacts associated with a deal first, then fall back to company contacts.

    Priority order:
    1. Contact directly associated with the deal (from deals.json associations.contact)
    2. All contacts associated with the company (from contacts.json associations.company_id)
    3. RAG search as last resort (existing extract_contacts behavior)

    Returns list of dicts with: id, name, title, email, source ("deal" or "company" or "rag")
    """
    contacts = []
    seen_ids = set()

    # 1. Get the deal's directly associated contact
    if deal_name:
        deal = mock_crm.search_deal(deal_name)
        if deal:
            deal_contact_id = deal.get("associations", {}).get("contact", "")
            if deal_contact_id:
                contact = mock_crm.get_contact_by_id(deal_contact_id)
                if contact:
                    props = contact.get("properties", {})
                    contacts.append({
                        "id": contact["id"],
                        "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                        "title": props.get("jobtitle", "N/A"),
                        "email": props.get("email", ""),
                        "source": "deal",
                    })
                    seen_ids.add(contact["id"])

            # Also get the company from the deal for step 2
            if not company_name:
                company_id = deal.get("associations", {}).get("company", "")
                if company_id:
                    company_data = mock_crm.get_company_by_id(company_id)
                    if company_data:
                        company_name = company_data.get("properties", {}).get("name", "")

    # 2. Get all contacts for the company
    if company_name:
        company_data = mock_crm.search_company(company_name)
        if company_data:
            company_id = company_data.get("id", "")
            company_contacts = mock_crm.get_contacts_for_company(company_id)
            for c in company_contacts:
                if c["id"] in seen_ids:
                    continue
                seen_ids.add(c["id"])
                props = c.get("properties", {})
                contacts.append({
                    "id": c["id"],
                    "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                    "title": props.get("jobtitle", "N/A"),
                    "email": props.get("email", ""),
                    "source": "company",
                })

    # 3. Fall back to RAG search if nothing found
    if not contacts:
        rag_contacts = extract_contacts(company_name or deal_name or "")
        for c in rag_contacts:
            c["source"] = "rag"
            c["id"] = ""
        contacts = rag_contacts

    return contacts


def extract_deals(company_name: str) -> list:
    """Extract deals for a company from RAG (filtered by company name in deal text)."""
    from tools.rag import search_deals_by_company
    rag_result = search_deals_by_company(company_name, n_results=5)

    deals = []
    # Split by document separator
    for doc in rag_result.split("---"):
        if "Deal:" not in doc:
            continue
        parsed = parse_rag_text(doc)
        name = parsed.get("deal", "Unknown")
        if name and name != "Unknown":
            amount = parsed.get("amount", "0")
            # Clean up amount (remove $, commas, etc.)
            try:
                amount = float(amount.replace("$", "").replace(",", "")) if amount else 0
            except (ValueError, TypeError):
                amount = 0
            deals.append({
                "name": name,
                "stage": parsed.get("stage", "N/A"),
                "amount": amount,
            })
    return deals


def extract_contacts_with_crm_priority(company_name: str) -> list:
    """Get contacts for a company — CRM direct lookup first, RAG fallback.

    Returns list of dicts with: name, title, email
    """
    # 1. Try direct CRM lookup (reliable, deterministic)
    company = mock_crm.search_company(company_name)
    if company:
        company_id = company.get("id", "")
        crm_contacts = mock_crm.get_contacts_for_company(company_id)
        if crm_contacts:
            return [
                {
                    "name": f"{c.get('properties', {}).get('firstname', '')} {c.get('properties', {}).get('lastname', '')}".strip() or "Unknown",
                    "title": c.get("properties", {}).get("jobtitle", "N/A"),
                    "email": c.get("properties", {}).get("email", "N/A"),
                }
                for c in crm_contacts
            ]

    # 2. Fall back to RAG search
    return extract_contacts(company_name)


def extract_deals_with_crm_priority(company_name: str) -> list:
    """Get deals for a company — CRM direct lookup first, RAG fallback.

    Returns list of dicts with: name, stage, amount
    """
    # 1. Try direct CRM lookup (reliable, deterministic)
    company = mock_crm.search_company(company_name)
    if company:
        company_id = company.get("id", "")
        crm_deals = mock_crm.get_deals_for_company(company_id)
        if crm_deals:
            deals = []
            for d in crm_deals:
                props = d.get("properties", {})
                raw_amount = props.get("amount", "0")
                try:
                    amount = float(raw_amount)
                except (ValueError, TypeError):
                    amount = 0.0
                deals.append({
                    "name": props.get("dealname", "Unknown"),
                    "stage": props.get("dealstage", "N/A"),
                    "amount": amount,
                })
            return deals

    # 2. Fall back to RAG search
    return extract_deals(company_name)


def extract_company_data_with_crm_priority(company_name: str) -> dict:
    """Get company data — CRM direct lookup first, RAG fallback.

    Merges both sources: CRM fields override RAG where available.
    """
    # Start with RAG data (gets web-enriched fields)
    data = extract_company_data(company_name)

    # Overlay with direct CRM data where available
    company = mock_crm.search_company(company_name)
    if company:
        props = company.get("properties", {})

        # Only override if the CRM has a real value (not None/empty)
        industry = props.get("industry", "")
        if industry and industry != "None":
            # Clean up HubSpot-style industry names (e.g., "PROFESSIONAL_TRAINING_COACHING")
            data["industry"] = industry.replace("_", " ").title()

        size = props.get("numberofemployees", "") or props.get("number_of_employees", "")
        if size and str(size) != "None":
            data["size"] = str(size)

        revenue = props.get("annualrevenue", "") or props.get("annual_revenue", "")
        if revenue and str(revenue) != "None" and str(revenue) != "0":
            try:
                data["revenue"] = f"${int(float(str(revenue))):,}"
            except (ValueError, TypeError):
                pass

        city = props.get("city", "")
        state = props.get("state", "")
        country = props.get("country", "")
        location_parts = [p for p in [city, state, country] if p and p != "None"]
        if location_parts:
            data["hq"] = ", ".join(location_parts)

    return data


def extract_deal_data(deal_name: str) -> tuple:
    """Extract deal data and related info from RAG."""
    from tools.rag import search_crm_deals
    rag_result = search_crm_deals(deal_name, n_results=1)

    # Parse the first deal
    parsed = parse_rag_text(rag_result.split("---")[0] if "---" in rag_result else rag_result)

    if not parsed.get("deal"):
        return None, [], []

    # Extract hubspot_id from the metadata source line
    # Format: "[crm_deal: hubspot_crm_deal_488327866572]" parses as key="[crm_deal", value="hubspot_crm_deal_XXX]"
    hubspot_id = ""
    source_value = parsed.get("[crm_deal", "")
    if source_value and "hubspot_crm_deal_" in source_value:
        hubspot_id = source_value.replace("]", "").replace("hubspot_crm_deal_", "").strip()

    # Parse amount
    amount = parsed.get("amount", "0")
    try:
        amount = float(amount.replace("$", "").replace(",", "")) if amount else 0
    except (ValueError, TypeError):
        amount = 0

    # Parse close date
    close_date = parsed.get("close_date", "N/A")
    if close_date and close_date != "N/A" and len(close_date) > 10:
        close_date = close_date[:10]

    # Extract company name from deal name (format: "Company - Deal Type")
    company = deal_name
    deal_full_name = parsed.get("deal", "")
    if " - " in deal_full_name:
        company = deal_full_name.split(" - ")[0].strip()

    deal_data = {
        "id": hubspot_id,
        "name": parsed.get("deal", "Unknown"),
        "stage": parsed.get("stage", "N/A"),
        "amount": amount,
        "close_date": close_date,
        "owner": parsed.get("owner", "Unassigned"),
        "company": company,
    }

    # Get contacts related to this deal/company
    contacts = extract_contacts(deal_name)
    activities = []  # Would need to search notes/activities

    return deal_data, contacts, activities


def extract_all_matching_deals(search_term: str) -> list:
    """Extract ALL deals matching a search term from RAG.

    Returns a list of deal dicts, each with: name, amount, stage, close_date, id
    Used for the multi-deal picker when multiple deals match.
    """
    from tools.rag import search_deals_by_company
    rag_result = search_deals_by_company(search_term, n_results=10)

    deals = []
    seen_ids = set()  # Deduplicate by HubSpot ID (not name, since names can be duplicated)

    for doc in rag_result.split("---"):
        if "Deal:" not in doc:
            continue
        parsed = parse_rag_text(doc)
        name = parsed.get("deal", "")
        if not name:
            continue

        # Extract hubspot_id from metadata source line
        hubspot_id = ""
        source_value = parsed.get("[crm_deal", "")
        if source_value and "hubspot_crm_deal_" in source_value:
            hubspot_id = source_value.replace("]", "").replace("hubspot_crm_deal_", "").strip()

        # Deduplicate by ID (deals can have same name but different IDs)
        if hubspot_id and hubspot_id in seen_ids:
            continue
        if hubspot_id:
            seen_ids.add(hubspot_id)

        # Parse amount
        amount = parsed.get("amount", "0")
        try:
            amount = float(amount.replace("$", "").replace(",", "")) if amount else 0
        except (ValueError, TypeError):
            amount = 0

        # Parse close date
        close_date = parsed.get("close_date", "N/A")
        if close_date and close_date != "N/A" and len(close_date) > 10:
            close_date = close_date[:10]

        deals.append({
            "id": hubspot_id,
            "name": name,
            "stage": parsed.get("stage", "N/A"),
            "amount": amount,
            "close_date": close_date,
        })

    return deals


def extract_pipeline_data() -> tuple:
    """Extract pipeline data for the digest from RAG."""
    from tools.rag import search_crm_deals
    rag_result = search_crm_deals("open deals pipeline", n_results=20)

    # Parse all deals from RAG
    deals = []
    for doc in rag_result.split("---"):
        if "Deal:" not in doc:
            continue
        parsed = parse_rag_text(doc)
        name = parsed.get("deal", "")
        if not name:
            continue
        amount = parsed.get("amount", "0")
        try:
            amount = float(amount.replace("$", "").replace(",", "")) if amount else 0
        except (ValueError, TypeError):
            amount = 0
        deals.append({
            "name": name,
            "stage": parsed.get("stage", "N/A"),
            "amount": amount,
            "close_date": parsed.get("close_date", ""),
        })

    # Filter for open deals (not closed won/lost)
    open_deals = [d for d in deals if "closed" not in d.get("stage", "").lower()]
    stale_deals = []  # Would need last activity date to determine
    overdue_deals = []  # Would need to compare close date to today

    # Calculate totals
    total_value = sum(d.get("amount", 0) for d in open_deals)

    # Weighted forecast (simplified: 50% of total)
    weighted_forecast = total_value * 0.5

    # Group by stage
    by_stage = {}
    for deal in open_deals:
        stage = deal.get("stage", "Unknown")
        if stage not in by_stage:
            by_stage[stage] = {"count": 0, "value": 0}
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += deal.get("amount", 0)

    deals_by_stage = [(stage, data["count"], data["value"]) for stage, data in by_stage.items()]

    # Build flagged deals (simplified - would need activity dates for proper detection)
    flagged_deals = []
    for deal in stale_deals[:3]:
        flagged_deals.append({
            "id": deal.get("id", ""),
            "name": deal.get("name", "Unknown"),
            "flag": "stale",
            "reason": "No activity in 14+ days",
        })
    for deal in overdue_deals[:2]:
        flagged_deals.append({
            "id": deal.get("id", ""),
            "name": deal.get("name", "Unknown"),
            "flag": "overdue",
            "reason": f"Past close date: {deal.get('close_date', 'N/A')[:10] if deal.get('close_date') else 'N/A'}",
        })

    return total_value, len(open_deals), weighted_forecast, deals_by_stage, flagged_deals


def parse_talking_points(llm_response: str) -> str:
    """Extract talking points from LLM response."""
    # The LLM response includes talking points - extract or use as-is
    if "Talking Points" in llm_response:
        parts = llm_response.split("Talking Points")
        if len(parts) > 1:
            return parts[1].split("\n\n")[0].strip(":* \n")
    return llm_response[-500:] if len(llm_response) > 500 else llm_response


def parse_recommendations(llm_response: str) -> str:
    """Extract recommendations from LLM response."""
    if "Recommended" in llm_response or "Next Actions" in llm_response:
        for marker in ["Recommended Next Actions", "Recommended Actions", "Next Actions"]:
            if marker in llm_response:
                parts = llm_response.split(marker)
                if len(parts) > 1:
                    return parts[1].split("\n\n")[0].strip(":* \n")
    return "• Review deal history and recent activity\n• Schedule follow-up call\n• Update CRM notes"


# --- Slash Command Handlers ---

@app.command("/test")
def handle_test(ack, say, command):
    """Test command to verify the bot is running."""
    ack()
    tool_names = [t.name for t in mcp_tools] if mcp_tools else ["none"]
    say(f"Sales AI Agent is alive! MCP tools loaded: {', '.join(tool_names)}")


@app.command("/research")
def handle_research(ack, say, command, client):
    """Research a company - pulls HubSpot data + web search."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    company = command["text"].strip()

    log_engagement(user_id, "command", command="/research", company=company)

    if not company:
        say("Please provide a company name: `/research [company_name]`")
        return

    # Post loading message and capture ts for later update
    loading_msg = client.chat_postMessage(
        channel=channel_id,
        text=f"⏳ Researching *{company}*... this takes about 15 seconds."
    )
    loading_ts = loading_msg["ts"]

    try:
        # Invoke the graph
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/research {company}")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
            "company_name": company,
        })

        # Extract structured data
        # Extract structured data — CRM direct lookup with RAG fallback
        company_data = extract_company_data_with_crm_priority(company)
        contacts = extract_contacts_with_crm_priority(company)
        deals = extract_deals_with_crm_priority(company)
        llm_response = result["messages"][-1].content
        talking_points = parse_talking_points(llm_response)

        # Get news from web context if available
        news = []
        if result.get("web_context"):
            news = [{"title": line.strip("• -")} for line in result["web_context"].split("\n") if line.strip()][:3]

        # Cache research data for progressive disclosure (expand button)
        cache_key = f"research_{user_id}_{company}"
        research_cache[cache_key] = {
            "company_data": company_data,
            "contacts": contacts,
            "deals": deals,
            "news": news,
            "talking_points": talking_points,
        }

        # Format with compact summary (progressive disclosure)
        blocks, fallback = format_research_summary(
            company_name=company,
            company_data=company_data,
            contacts=contacts,
            deals=deals,
            news=news,
            talking_points=talking_points,
        )

        # Update loading message with final result
        client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        # Update loading message with error
        client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            text=f"⚠️ Something went wrong with `/research`. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.command("/deal")
def handle_deal(ack, say, command, client):
    """Look up a deal by name — shows picker if multiple matches."""
    ack()
    deal_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/deal", search_term=deal_name)

    if not deal_name:
        say("Please provide a deal or company name: `/deal [name]`")
        return

    # Post loading message and capture ts for later update
    loading_msg = client.chat_postMessage(
        channel=channel_id,
        text=f"⏳ Looking up deals matching *{deal_name}*..."
    )
    loading_ts = loading_msg["ts"]

    try:
        # Check how many deals match
        matching_deals = extract_all_matching_deals(deal_name)

        if len(matching_deals) == 0:
            # No matches in RAG — fall back to LLM with MCP tools
            result = app_graph.invoke({
                "messages": [HumanMessage(content=f"/deal {deal_name}")],
                "route": "assistant",
                "workflow": "deal",
                "user_id": user_id,
                "channel_id": channel_id,
                "thread_ts": None,
            })
            client.chat_update(channel=channel_id, ts=loading_ts, text=result["messages"][-1].content)

        elif len(matching_deals) == 1:
            # Exactly 1 match — show deal card directly (existing behavior)
            result = app_graph.invoke({
                "messages": [HumanMessage(content=f"/deal {matching_deals[0]['name']}")],
                "route": "assistant",
                "workflow": "deal",
                "user_id": user_id,
                "channel_id": channel_id,
                "thread_ts": None,
            })

            deal_data, contacts, activities = extract_deal_data(matching_deals[0]["name"])
            llm_response = result["messages"][-1].content
            recommendations = parse_recommendations(llm_response)

            if deal_data:
                blocks, fallback = format_deal_response(
                    deal=deal_data,
                    contacts=contacts,
                    activities=activities,
                    recommendations=recommendations,
                )
                client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)
            else:
                client.chat_update(channel=channel_id, ts=loading_ts, text=llm_response)

        else:
            # Multiple matches — show deal picker
            from formatters import format_deal_picker
            blocks, fallback = format_deal_picker(deal_name, matching_deals)
            client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            text=f"⚠️ Something went wrong with `/deal`. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.command("/coach")
def handle_coach(ack, say, command):
    """Start a coaching session - roleplay, feedback, or prep."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command["text"].strip()

    # Determine subcommand for logging
    subcommand = "roleplay"
    if text.lower().startswith("prep "):
        subcommand = "prep"
    elif text.lower().startswith("feedback "):
        subcommand = "feedback"
    log_engagement(user_id, "command", command="/coach", subcommand=subcommand, scenario=text[:100])

    if not text:
        say(
            "Usage:\n"
            "• `/coach roleplay [scenario]` — 4-turn practice session\n"
            "• `/coach roleplay [scenario] --turns 8` — longer session (3-12 turns)\n"
            "• `/coach prep [company]` — meeting prep brief\n"
            "• `/coach feedback [notes]` — call feedback"
        )
        return

    # Determine workflow
    workflow = "roleplay"
    if text.lower().startswith("prep "):
        workflow = "prep"
    elif text.lower().startswith("feedback "):
        workflow = "feedback"

    try:
        # For roleplay, use Block Kit start message
        if workflow == "roleplay":
            # Parse optional --turns flag
            max_turns = DEFAULT_ROLEPLAY_TURNS
            if "--turns" in text:
                parts = text.split("--turns")
                text = parts[0].strip()  # Remove flag from scenario text
                try:
                    requested_turns = int(parts[1].strip().split()[0])
                    max_turns = max(MIN_ROLEPLAY_TURNS, min(requested_turns, MAX_ROLEPLAY_TURNS))
                except (ValueError, IndexError):
                    pass  # Keep default

            scenario = text.replace("roleplay ", "").strip()

            # Create a placeholder persona (LLM will generate the real one)
            persona = {
                "name": "Alex Chen",
                "title": "VP of Operations",
                "company": "Target Corp",
                "personality": "Analytical, detail-oriented, skeptical of new vendors",
            }

            blocks, fallback = format_roleplay_start(persona, scenario)
            result_msg = say(text=fallback, blocks=blocks, channel=channel_id)
            thread_ts = result_msg["ts"]

            # Invoke the graph
            result = app_graph.invoke({
                "messages": [HumanMessage(content=f"/coach {text}")],
                "route": "coach",
                "workflow": workflow,
                "user_id": user_id,
                "channel_id": channel_id,
                "thread_ts": thread_ts,
            })

            # Send the LLM's roleplay response in thread (plain text, conversational)
            response_text = result["messages"][-1].content
            say(text=response_text, channel=channel_id, thread_ts=thread_ts)

            # Store roleplay state for thread continuation
            active_roleplays[thread_ts] = {
                "messages": result["messages"],
                "turn_count": 1,
                "max_turns": max_turns,
                "rag_context": result.get("rag_context", ""),
                "user_id": user_id,
                "channel_id": channel_id,
                "scenario": scenario,
            }
            print(f"[Coach] Started roleplay ({max_turns} turns), stored thread_ts={thread_ts} in active_roleplays")
        else:
            # Prep and feedback use plain response for now
            result_msg = say(f"Starting {workflow} session...", channel=channel_id)
            thread_ts = result_msg["ts"]

            result = app_graph.invoke({
                "messages": [HumanMessage(content=f"/coach {text}")],
                "route": "coach",
                "workflow": workflow,
                "user_id": user_id,
                "channel_id": channel_id,
                "thread_ts": thread_ts,
            })

            response_text = result["messages"][-1].content
            say(text=response_text, channel=channel_id, thread_ts=thread_ts)

    except Exception as e:
        handle_error(say, channel_id, "/coach", e)


def _draft_email_direct(say, graph, company_name, deal_name, contact, user_id, channel_id):
    """Draft an email directly (no pickers needed)."""
    contact_name = contact.get("name", "Contact")
    contact_email = contact.get("email", "")

    say(f"Drafting follow-up email for *{company_name}*...", channel=channel_id)

    context_text = deal_name if deal_name else company_name
    result = graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {context_text}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
    })

    llm_response = result["messages"][-1].content

    subject = f"Following up - {company_name}"
    body = llm_response
    if "Subject:" in llm_response:
        parts = llm_response.split("Subject:")
        if len(parts) > 1:
            subject_line = parts[1].split("\n")[0].strip()
            subject = subject_line
            body = "\n".join(parts[1].split("\n")[1:]).strip()

    body = body.replace("*", "").strip()
    if len(body) > 2000:
        body = body[:2000]

    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=contact_name,
        to_email=contact_email or "contact@example.com",
        subject=subject,
        body=body,
    )
    say(text=fallback, blocks=blocks, channel=channel_id)


@app.command("/draft-email")
def handle_draft_email(ack, say, command):
    """Draft a follow-up email for a company/deal."""
    ack()
    company = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/draft-email", company=company)

    if not company:
        say("Please provide a company name: `/draft-email [company_name]`")
        return

    try:
        # Step 1: Check how many deals this company has
        matching_deals = extract_all_matching_deals(company)

        if len(matching_deals) == 0:
            # No deals — fall through to contact-only flow
            contacts = get_contacts_for_deal_or_company(deal_name=company, company_name=company)
            if len(contacts) == 0:
                say(text=f"⚠️ No deals or contacts found for *{company}*.", channel=channel_id)
                return
            elif len(contacts) > 1:
                from formatters import format_contact_picker
                blocks, fallback = format_contact_picker(
                    company_name=company,
                    contacts=contacts,
                    email_context={"company_name": company, "deal_name": "", "trigger": "draft_email"},
                )
                say(text=fallback, blocks=blocks, channel=channel_id)
                return
            else:
                # Single contact, no deals — draft directly
                primary_contact = contacts[0]
                _draft_email_direct(say, app_graph, company, "", primary_contact, user_id, channel_id)
                return

        elif len(matching_deals) == 1:
            # Single deal — skip deal picker, go to contact picker
            deal = matching_deals[0]
            deal_name = deal.get("name", company)
            contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company)

            if len(contacts) == 0:
                say(text=f"⚠️ No contacts found for *{company}*.", channel=channel_id)
                return
            elif len(contacts) > 1:
                from formatters import format_contact_picker
                blocks, fallback = format_contact_picker(
                    company_name=company,
                    contacts=contacts,
                    email_context={
                        "company_name": company,
                        "deal_name": deal_name,
                        "deal_id": deal.get("id", ""),
                        "trigger": "draft_email",
                    },
                )
                say(text=fallback, blocks=blocks, channel=channel_id)
                return
            else:
                primary_contact = contacts[0]
                _draft_email_direct(say, app_graph, company, deal_name, primary_contact, user_id, channel_id)
                return

        else:
            # Multiple deals — show deal picker
            from formatters import format_email_deal_picker
            blocks, fallback = format_email_deal_picker(
                company_name=company,
                deals=matching_deals,
                email_context={"trigger": "draft_email"},
            )
            say(text=fallback, blocks=blocks, channel=channel_id)
            return

    except Exception as e:
        handle_error(say, channel_id, "/draft-email", e)


@app.command("/pipeline")
def handle_pipeline(ack, say, command, client):
    """Generate a pipeline health digest."""
    ack()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/pipeline")

    # Resolve user access
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return

    # Post loading message and capture ts for later update
    loading_msg = client.chat_postMessage(
        channel=channel_id,
        text="⏳ Analyzing pipeline health..."
    )
    loading_ts = loading_msg["ts"]

    try:
        # Try direct CRM first (supports owner filtering)
        open_deals = mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])
        if open_deals:
            # Use direct CRM data with owner filtering
            from tools.mock_crm import get_stale_deals_for_user, get_overdue_deals_for_user
            total_value = sum(float(d.get("properties", {}).get("amount", 0) or 0) for d in open_deals)
            deal_count = len(open_deals)
            weighted_forecast = total_value * 0.5

            # Group by stage
            by_stage = {}
            for deal in open_deals:
                stage = deal.get("properties", {}).get("dealstage", "Unknown")
                if stage not in by_stage:
                    by_stage[stage] = {"count": 0, "value": 0}
                by_stage[stage]["count"] += 1
                by_stage[stage]["value"] += float(deal.get("properties", {}).get("amount", 0) or 0)
            deals_by_stage = [(stage, data["count"], data["value"]) for stage, data in by_stage.items()]

            # Flagged deals
            stale = get_stale_deals_for_user(stale_days=14, owner_id=ctx["filter_owner_id"])
            overdue = get_overdue_deals_for_user(owner_id=ctx["filter_owner_id"])
            flagged_deals = []
            for deal in stale[:3]:
                props = deal.get("properties", {})
                flagged_deals.append({
                    "id": deal.get("id", ""),
                    "name": props.get("dealname", "Unknown"),
                    "flag": "stale",
                    "reason": "No activity in 14+ days",
                })
            for deal in overdue[:2]:
                props = deal.get("properties", {})
                flagged_deals.append({
                    "id": deal.get("id", ""),
                    "name": props.get("dealname", "Unknown"),
                    "flag": "overdue",
                    "reason": f"Past close date: {props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'}",
                })
        else:
            # Fall back to RAG path (existing behavior, no owner filtering)
            total_value, deal_count, weighted_forecast, deals_by_stage, flagged_deals = extract_pipeline_data()

        # Invoke the graph for LLM recommendations
        result = app_graph.invoke({
            "messages": [HumanMessage(content="/pipeline")],
            "route": "assistant",
            "workflow": "pipeline",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        # Parse recommendations from LLM
        llm_response = result["messages"][-1].content
        recommendations = []
        if "Recommended" in llm_response:
            rec_section = llm_response.split("Recommended")[-1]
            for line in rec_section.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("•") or line.startswith("-")):
                    recommendations.append(line.lstrip("0123456789.-• "))
                    if len(recommendations) >= 5:
                        break

        if not recommendations:
            recommendations = [
                "Follow up on stale deals this week",
                "Update close dates for overdue opportunities",
                "Schedule discovery calls for new leads",
            ]

        blocks, fallback = format_pipeline_response(
            total_value=total_value,
            deal_count=deal_count,
            weighted_forecast=weighted_forecast,
            deals_by_stage=deals_by_stage,
            flagged_deals=flagged_deals,
            recommendations=recommendations,
        )

        # Prepend ownership context banner
        blocks = _ownership_context_block(ctx) + blocks

        # Update loading message with final result
        client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            text=f"⚠️ Something went wrong with `/pipeline`. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


# --- Auto-CRM Detection Helper (Wave 1E) ---

def _handle_auto_crm_detection(event, client, channel_id, user_id, text, message_ts):
    """Detect if a message looks like a loggable sales interaction and offer to log it.

    This function is called for channel-level messages (not thread replies) in monitored channels.
    It uses a two-stage approach:
    1. Fast keyword filter (no LLM cost)
    2. LLM classification (only if keyword filter passes)
    """
    import time as time_mod
    from langchain_core.messages import SystemMessage, HumanMessage as HM

    # Check cooldown
    now = time_mod.time()
    last_suggestion = _auto_crm_cooldown.get(user_id, 0)
    if now - last_suggestion < AUTO_CRM_COOLDOWN_SECONDS:
        return

    # Stage 1: Fast keyword filter
    passes, matched_companies = passes_keyword_filter(text)
    if not passes:
        return

    print(f"[Auto-CRM] Keyword filter passed for user {user_id}, matched companies: {matched_companies}")

    # Stage 2: LLM classification
    try:
        user_prompt = build_classification_prompt(text, matched_companies)

        # Use the existing LLM through the graph's LLM
        from llm_factory import get_llm
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=CRM_DETECT_SYSTEM_PROMPT),
            HM(content=user_prompt)
        ])

        result = parse_classification_response(response.content)
        if not result:
            print(f"[Auto-CRM] Failed to parse LLM response")
            return

        if not result.get("loggable", False):
            print(f"[Auto-CRM] LLM said not loggable")
            return

        confidence = result.get("confidence", 0)
        if confidence < AUTO_CRM_CONFIDENCE_THRESHOLD:
            print(f"[Auto-CRM] Confidence {confidence} below threshold {AUTO_CRM_CONFIDENCE_THRESHOLD}")
            return

        print(f"[Auto-CRM] Detected loggable message: company={result.get('company')}, confidence={confidence}")

    except Exception as e:
        print(f"[Auto-CRM] LLM classification failed: {e}")
        return

    # Stage 3: Post ephemeral suggestion
    try:
        blocks, fallback = format_crm_suggestion(
            original_text=text,
            extracted=result,
            message_ts=message_ts,
            channel_id=channel_id
        )

        # Ephemeral = only visible to the message author
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text=fallback
        )

        # Log the suggestion event
        log_engagement(user_id, "auto_crm_suggestion", company=result.get("company", ""), confidence=confidence)

        # Set cooldown
        _auto_crm_cooldown[user_id] = now

        print(f"[Auto-CRM] Suggestion posted to user {user_id}")

    except Exception as e:
        print(f"[Auto-CRM] Failed to post ephemeral: {e}")


# --- Message Handler (Thread Replies + Auto-CRM Detection) ---

@app.event("message")
def handle_message_event(event, say, client):
    """Handle messages: thread replies (roleplay, coaching) and auto-CRM detection."""
    import time as time_mod

    print(f"[Message Event] Received: subtype={event.get('subtype')}, thread_ts={event.get('thread_ts')}, bot_id={event.get('bot_id')}, text={event.get('text', '')[:50] if event.get('text') else None}")

    # Ignore message subtypes (edits, deletes, etc.)
    if event.get("subtype"):
        return

    # Ignore bot's own messages
    if event.get("bot_id"):
        return

    # Ignore messages without text
    if not event.get("text"):
        return

    thread_ts = event.get("thread_ts")
    channel = event.get("channel")
    user_id = event.get("user", "")
    text = event.get("text", "").strip()
    message_ts = event.get("ts", "")

    # --- Auto-CRM Detection (channel-level messages only) ---
    if not thread_ts and channel in AUTO_CRM_CHANNELS:
        _handle_auto_crm_detection(event, client, channel, user_id, text, message_ts)

    # --- Thread Reply Handling ---
    if not thread_ts:
        return  # Not a thread reply, nothing more to do

    channel = event.get("channel")
    user_message = event.get("text", "").strip()
    user_id = event.get("user")

    # 1. Check if this is a live coaching thread (EXPANSION-12)
    if thread_ts in active_live_coaching:
        session = active_live_coaching[thread_ts]

        # Check for end command
        if user_message.lower() in ("done", "end", "stop"):
            # Generate summary
            history_text = "\n".join([f"Turn {i+1}: Buyer said: {h['buyer']} → Coach suggested: {h['suggestion'][:80]}"
                                       for i, h in enumerate(session["history"])])

            summary_result = app_graph.invoke({
                "messages": [HumanMessage(content=f"""Summarize this live coaching session.

COMPANY: {session['company']}
CALL TYPE: {session['call_type']}
COACHING TURNS: {session['turns']}

SESSION HISTORY:
{history_text}

Generate EXACTLY this format:
SCORE: [1-10 based on coachability and response quality]
HIGHLIGHT_1: [Something the rep did well or responded well to]
HIGHLIGHT_2: [Another highlight]
IMPROVEMENT_1: [Area to improve]
IMPROVEMENT_2: [Another area to improve]""")],
                "route": "coach",
                "workflow": "coach",
                "user_id": session["user_id"],
                "channel_id": channel,
                "thread_ts": thread_ts,
            })

            # Parse summary
            summary_text = summary_result["messages"][-1].content
            score = 7
            highlights = []
            improvements = []

            for line in summary_text.split("\n"):
                line = line.strip()
                if line.upper().startswith("SCORE:"):
                    try:
                        score = int("".join(filter(str.isdigit, line.split(":", 1)[1][:3])))
                    except (ValueError, IndexError):
                        score = 7
                elif line.upper().startswith("HIGHLIGHT_"):
                    highlights.append(line.split(":", 1)[1].strip() if ":" in line else line)
                elif line.upper().startswith("IMPROVEMENT_"):
                    improvements.append(line.split(":", 1)[1].strip() if ":" in line else line)

            from formatters import format_coach_live_summary
            blocks, fallback = format_coach_live_summary(
                company_name=session["company"],
                call_type=session["call_type"],
                turns=session["turns"],
                highlights=highlights,
                improvements=improvements,
                score=score,
            )

            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=fallback,
                blocks=blocks,
            )

            # Clean up
            del active_live_coaching[thread_ts]
            return

        # Regular coaching turn
        session["turns"] += 1

        coaching_result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""You are a real-time sales coach. A rep is on a live {session['call_type']} call with {session['company']}.

The buyer just said: "{user_message}"

SALES METHODOLOGY CONTEXT:
{session['methodology_context']}

PREVIOUS COACHING (last 3):
{chr(10).join([f"  Buyer: {h['buyer'][:60]} → You coached: {h['suggestion'][:60]}" for h in session['history'][-3:]]) or "  First turn"}

Respond in EXACTLY this format:
TIP_TYPE: [positive|redirect|warning|technique]
SUGGESTION: [What the rep should say or do RIGHT NOW — be specific and concise, max 2 sentences]
TECHNIQUE: [Name of the sales technique being applied, e.g., "SPIN Implication Question", "Feel-Felt-Found"]
AVOID: [One thing NOT to do in this moment]

Be concise — the rep is on a live call and needs to respond in seconds.""")],
            "route": "coach",
            "workflow": "coach",
            "user_id": session["user_id"],
            "channel_id": channel,
            "thread_ts": thread_ts,
        })

        coaching_text = coaching_result["messages"][-1].content

        # Parse
        tip_type = "technique"
        suggestion = ""
        technique = ""
        avoid = ""

        for line in coaching_text.split("\n"):
            line = line.strip()
            if line.upper().startswith("TIP_TYPE:"):
                tip_type = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("SUGGESTION:"):
                suggestion = line.split(":", 1)[1].strip()
            elif line.upper().startswith("TECHNIQUE:"):
                technique = line.split(":", 1)[1].strip()
            elif line.upper().startswith("AVOID:"):
                avoid = line.split(":", 1)[1].strip()

        if not suggestion:
            suggestion = coaching_text[:200]

        # Store in history
        session["history"].append({
            "buyer": user_message,
            "suggestion": suggestion,
        })

        from formatters import format_coach_live_tip
        blocks, fallback = format_coach_live_tip(tip_type, suggestion, technique, avoid)

        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=fallback,
            blocks=blocks,
        )
        return  # Don't fall through to other message handlers

    print(f"[Thread Reply] thread_ts={thread_ts}, active_roleplays={list(active_roleplays.keys())}")

    # 2. Check if this thread is an active roleplay
    if thread_ts in active_roleplays:
        print(f"[Thread Reply] Found active roleplay for thread {thread_ts}")
        try:
            roleplay = active_roleplays[thread_ts]
            turn_count = roleplay["turn_count"] + 1
            max_turns = roleplay.get("max_turns", DEFAULT_ROLEPLAY_TURNS)
            user_id = roleplay.get("user_id", event.get("user", ""))

            # Log roleplay turn engagement
            log_engagement(user_id, "roleplay_turn", turn_number=turn_count, scenario=roleplay.get("scenario", ""))

            # Get user's methodology preference for scoring
            user_settings = get_user_settings(user_id)
            methodology = user_settings.get("methodology", "discovery")

            # Add user message to history
            messages = roleplay["messages"] + [HumanMessage(content=event["text"])]

            print(f"[Thread Reply] Continuing roleplay, turn {turn_count}/{max_turns}, methodology={methodology}")
            # Continue roleplay
            result = continue_roleplay(
                {
                    "messages": messages,
                    "rag_context": roleplay.get("rag_context", ""),
                },
                turn_count,
                max_turns=max_turns,
                methodology=methodology,
            )

            response_text = result["messages"][-1].content
            print(f"[Thread Reply] Got response: {response_text[:100]}...")

            # Check if this is a debrief (reached max turns)
            if turn_count >= max_turns:
                user_id = roleplay.get("user_id", "")

                # Parse structured scores from JSON block
                scores_data = parse_debrief_scores(response_text)
                display_debrief = strip_json_block(response_text)

                if scores_data:
                    score = scores_data.get("overall_score", 7)
                    strengths = scores_data.get("strengths", ["Good discovery questions", "Professional tone"])
                    improvements = scores_data.get("improvements", ["Could handle objections more confidently"])
                    next_practice = scores_data.get("recommended_next", "Try a negotiation scenario")

                    # Save to database with full dimension scores
                    session_id = save_training_session(
                        user_id=user_id,
                        session_type="roleplay",
                        overall_score=score,
                        dimensions=scores_data.get("dimensions", {}),
                        scenario=roleplay.get("scenario", ""),
                        scenario_id=roleplay.get("scenario_id"),
                        scenario_type=scores_data.get("scenario_type", "discovery"),
                        strengths=strengths,
                        improvements=improvements,
                        turns=turn_count,
                        methodology=scores_data.get("scenario_type", "discovery"),
                        company=roleplay.get("company", ""),
                        persona=roleplay.get("persona_name", ""),
                        raw_debrief=display_debrief,
                    )
                    print(f"[Debrief] Saved session {session_id} with score {score}")
                else:
                    # Fallback: parse score from markdown if JSON failed
                    score = 7
                    score_match = re.search(r'Overall Score:\s*(\d+\.?\d*)/10', response_text)
                    if score_match:
                        score = float(score_match.group(1))

                    strengths = ["Good discovery questions", "Professional tone"]
                    improvements = ["Could handle objections more confidently", "Ask more follow-up questions"]
                    next_practice = "Try a negotiation scenario with a price-sensitive buyer"

                    # Save basic session without dimension scores
                    session_id = save_training_session(
                        user_id=user_id,
                        session_type="roleplay",
                        overall_score=score,
                        scenario=roleplay.get("scenario", ""),
                        scenario_type="discovery",
                        turns=turn_count,
                        company=roleplay.get("company", ""),
                        persona=roleplay.get("persona_name", ""),
                        raw_debrief=response_text,
                    )
                    print(f"[Debrief] Saved session {session_id} with fallback score {score}")

                blocks, fallback = format_roleplay_debrief(
                    score=score,
                    strengths=strengths,
                    improvements=improvements,
                    next_practice=next_practice,
                    scenario=roleplay.get("scenario", ""),
                    company=roleplay.get("company", ""),
                    scenario_type=scores_data.get("scenario_type", "discovery") if scores_data else "discovery",
                )

                say(text=fallback, blocks=blocks, channel=event["channel"], thread_ts=thread_ts)

                # Roleplay complete, remove from active
                del active_roleplays[thread_ts]
            else:
                # Continue roleplay with plain text (conversational)
                say(text=response_text, channel=event["channel"], thread_ts=thread_ts)

                # Progress indicator for longer sessions
                if max_turns >= 6 and turn_count == max_turns - 2:
                    say(
                        text="_Coach note: 2 turns remaining before debrief. Make them count!_",
                        channel=event["channel"],
                        thread_ts=thread_ts,
                    )

                # Update state
                active_roleplays[thread_ts] = {
                    "messages": result["messages"],
                    "turn_count": turn_count,
                    "max_turns": max_turns,
                    "rag_context": result.get("rag_context", ""),
                    "user_id": roleplay["user_id"],
                    "channel_id": event["channel"],
                    "scenario": roleplay.get("scenario", ""),
                }
        except Exception as e:
            print(f"[Thread Reply] ERROR: {e}")
            import traceback
            traceback.print_exc()
            say(text=f"Sorry, something went wrong with the roleplay: {str(e)}", channel=event["channel"], thread_ts=thread_ts)
        return  # Don't fall through

    # 3. Check if this is a follow-up in a context-aware thread (EXPANSION-17)
    if thread_ts in thread_contexts:
        ctx = thread_contexts[thread_ts]

        # Build context based on the original command
        command = ctx["command"]
        data = ctx["data"]
        context_parts = []

        # Load relevant data based on original command type
        if command == "deal":
            deal = mock_crm.search_deal(data.get("deal_name", ""))
            if deal:
                context_parts.append(f"DEAL CONTEXT: {mock_crm.format_deal_for_display(deal)}")

                # Also load company and contacts
                company_id = deal.get("associations", {}).get("company", "")
                company = mock_crm.get_company_by_id(company_id)
                if company:
                    context_parts.append(f"COMPANY: {mock_crm.format_company_for_display(company)}")

                contacts = mock_crm.get_contacts_for_company(company_id) if company_id else []
                for c in contacts[:3]:
                    context_parts.append(f"CONTACT: {mock_crm.format_contact_for_display(c)}")

        elif command == "research":
            company = mock_crm.search_company(data.get("company_name", ""))
            if company:
                context_parts.append(f"COMPANY: {mock_crm.format_company_for_display(company)}")
                company_id = company.get("id", "")
                deals = mock_crm.get_deals_for_company(company_id)
                for d in deals[:3]:
                    context_parts.append(f"DEAL: {mock_crm.format_deal_for_display(d)}")

        elif command == "pipeline":
            open_deals = mock_crm.get_all_open_deals()
            context_parts.append(f"PIPELINE: {len(open_deals)} open deals")
            for d in open_deals[:5]:
                context_parts.append(f"DEAL: {mock_crm.format_deal_for_display(d)}")

        elif command == "objection":
            from tools.rag import search_playbooks
            objection_ctx = search_playbooks(f"objection handling {data.get('objection', '')}", n_results=5)
            context_parts.append(f"OBJECTION CONTEXT: {objection_ctx}")

        # Always add RAG search for the follow-up question
        from tools.rag import search_playbooks
        rag_results = search_playbooks(user_message, n_results=3)
        if rag_results:
            context_parts.append(f"PLAYBOOK CONTEXT: {rag_results}")

        combined_context = "\n\n".join(context_parts)

        # Run LLM with context
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""A sales rep previously ran the /{command} command and got results about: {json.dumps(data)}.

Now they're asking a follow-up question in the thread: "{user_message}"

AVAILABLE CONTEXT:
{combined_context}

Answer their follow-up question using the context above. Be specific and actionable.
If the question requires data you don't have, suggest the right command to get it.
Format with Slack mrkdwn. Keep it concise — this is a thread reply, not a full report.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": thread_ts,
        })

        answer = result["messages"][-1].content

        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=answer,
        )
        return  # Don't fall through to other handlers

    print(f"[Thread Reply] No active session for thread {thread_ts}")


# --- Action Handlers (Interactive Buttons) ---

@app.action("expand_research")
def handle_expand_research(ack, body, client):
    """User clicked 'Show Full Brief' on a research summary."""
    ack()
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    company_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="expand_research", company=company_name)

    # Look up cached research data
    cache_key = f"research_{user_id}_{company_name}"
    cached = research_cache.get(cache_key)

    if not cached:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ Research data for *{company_name}* has expired. Run `/research {company_name}` again."
        )
        return

    # Get the full blocks
    blocks, fallback = format_research_response(
        company_name=company_name,
        company_data=cached["company_data"],
        contacts=cached["contacts"],
        deals=cached["deals"],
        news=cached["news"],
        talking_points=cached["talking_points"],
    )

    # Post full research as a threaded reply
    client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


@app.action("expand_handoff")
def handle_expand_handoff(ack, body, client):
    """User clicked 'Show Full Handoff Brief' on a handoff summary."""
    ack()
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    deal_id_or_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    # Look up cached handoff data
    cache_key = f"handoff_{user_id}_{deal_id_or_name}"
    cached = handoff_cache.get(cache_key)

    if not cached:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ Handoff data has expired. Run `/handoff {deal_id_or_name}` again."
        )
        return

    # Get the full blocks
    blocks, fallback = format_handoff_response(
        deal_name=cached["deal_name"],
        company_name=cached["company_name"],
        deal_summary=cached["deal_summary"],
        key_contacts=cached["key_contacts"],
        conversation_history=cached["conversation_history"],
        risk_factors=cached["risk_factors"],
        next_steps=cached["next_steps"],
        competitor_mentions=cached["competitor_mentions"],
        deal_id=cached["deal_id"],
    )

    # Post full handoff as a threaded reply
    client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


@app.action("draft_email_from_research")
def handle_draft_from_research(ack, body, say, client):
    """User clicked 'Draft Follow-Up Email' on a research brief."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="draft_email_from_research", company=company_name)

    # Get contacts using deal/company associations
    contacts = get_contacts_for_deal_or_company(company_name=company_name)

    if len(contacts) == 0:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ No contacts found for *{company_name}*."
        )
        return

    elif len(contacts) > 1:
        # Multiple contacts — show picker as threaded reply
        from formatters import format_contact_picker
        blocks, fallback = format_contact_picker(
            company_name=company_name,
            contacts=contacts,
            email_context={
                "company_name": company_name,
                "deal_name": "",
                "trigger": "research",
            },
        )
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=fallback,
            blocks=blocks,
        )
        return

    # Exactly 1 contact — draft email directly
    primary_contact = contacts[0]
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"⏳ Drafting follow-up email for *{company_name}*..."
    )

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {company_name}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    subject = f"Following up - {company_name}"
    body_text = llm_response
    if "Subject:" in llm_response:
        parts = llm_response.split("Subject:")
        if len(parts) > 1:
            subject = parts[1].split("\n")[0].strip()
            body_text = "\n".join(parts[1].split("\n")[1:]).strip()

    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=primary_contact.get("name", "Contact"),
        to_email=primary_contact.get("email", "contact@example.com"),
        subject=subject,
        body=body_text[:2000],
    )

    # Update loading message with email draft
    client.chat_update(
        channel=channel,
        ts=loading_msg["ts"],
        text=fallback,
        blocks=blocks,
    )


@app.action("start_roleplay_from_research")
def handle_roleplay_from_research(ack, body, say):
    """User clicked 'Start Roleplay' on a research brief."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="start_roleplay_from_research", company=company_name)

    scenario = f"discovery call for {company_name}"
    persona = {
        "name": "Alex Chen",
        "title": "VP of Operations",
        "company": company_name,
        "personality": "Analytical, detail-oriented, skeptical of new vendors",
    }

    blocks, fallback = format_roleplay_start(persona, scenario)
    result_msg = say(text=fallback, blocks=blocks, channel=channel)
    thread_ts = result_msg["ts"]

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/coach roleplay discovery call for {company_name}")],
        "route": "coach",
        "workflow": "roleplay",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": thread_ts,
    })

    response_text = result["messages"][-1].content
    say(text=response_text, channel=channel, thread_ts=thread_ts)

    active_roleplays[thread_ts] = {
        "messages": result["messages"],
        "turn_count": 1,
        "max_turns": DEFAULT_ROLEPLAY_TURNS,
        "rag_context": result.get("rag_context", ""),
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "scenario": scenario,
    }


@app.action("research_from_deal")
def handle_research_from_deal(ack, body, client):
    """User clicked 'Full Research' on a deal card."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="research_from_deal", company=company_name)

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"⏳ Researching *{company_name}*..."
    )
    loading_ts = loading_msg["ts"]

    try:
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/research {company_name}")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": None,
        })

        company_data = extract_company_data(company_name)
        contacts = extract_contacts(company_name)
        deals = extract_deals(company_name)
        llm_response = result["messages"][-1].content
        talking_points = parse_talking_points(llm_response)
        news = []

        # Cache research data for progressive disclosure
        cache_key = f"research_{user_id}_{company_name}"
        research_cache[cache_key] = {
            "company_data": company_data,
            "contacts": contacts,
            "deals": deals,
            "news": news,
            "talking_points": talking_points,
        }

        # Use compact summary format
        blocks, fallback = format_research_summary(
            company_name=company_name,
            company_data=company_data,
            contacts=contacts,
            deals=deals,
            news=news,
            talking_points=talking_points,
        )

        # Update loading message with final result
        client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.action("view_deal_detail")
def handle_view_deal_detail(ack, body, client):
    """User clicked 'Open Deal' on a deal in the picker — post deal card as threaded reply."""
    ack()
    import json as json_module

    action_value = json_module.loads(body["actions"][0]["value"])
    deal_name = action_value["deal_name"]
    search_term = action_value["search_term"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="view_deal_detail", deal=deal_name)

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"⏳ Loading deal details for *{deal_name}*..."
    )

    # Get full deal data
    deal_data, contacts, activities = extract_deal_data(deal_name)

    if not deal_data:
        client.chat_update(
            channel=channel,
            ts=loading_msg["ts"],
            text=f"⚠️ Could not load details for {deal_name}.",
        )
        return

    # Run LLM for recommendations
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/deal {deal_name}")],
        "route": "assistant",
        "workflow": "deal",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content
    recommendations = parse_recommendations(llm_response)

    # Format deal card WITH "Back to Results" button
    blocks, fallback = format_deal_response(
        deal=deal_data,
        contacts=contacts,
        activities=activities,
        recommendations=recommendations,
        search_term=search_term,  # This adds the back button
    )

    # Update loading message with deal card
    client.chat_update(
        channel=channel,
        ts=loading_msg["ts"],
        text=fallback,
        blocks=blocks,
    )


@app.action("back_to_deal_results")
def handle_back_to_results(ack, body, client):
    """User clicked '← Back to Results' — update message back to deal picker."""
    ack()

    search_term = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Re-search for matching deals
    matching_deals = extract_all_matching_deals(search_term)

    if not matching_deals:
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"No deals found matching \"{search_term}\".",
        )
        return

    from formatters import format_deal_picker
    blocks, fallback = format_deal_picker(search_term, matching_deals)

    # Update the message back to the picker
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


@app.action("draft_email_from_deal")
def handle_draft_from_deal(ack, body, say, client):
    """User clicked 'Draft Email' on a deal card."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="draft_email_from_deal", company=company_name)

    # Get contacts using deal/company associations (deal_name helps find the associated contact)
    contacts = get_contacts_for_deal_or_company(deal_name=company_name, company_name=company_name)

    if len(contacts) == 0:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ No contacts found for *{company_name}*."
        )
        return

    elif len(contacts) > 1:
        # Multiple contacts — show picker as threaded reply
        from formatters import format_contact_picker
        blocks, fallback = format_contact_picker(
            company_name=company_name,
            contacts=contacts,
            email_context={
                "company_name": company_name,
                "deal_name": company_name,
                "trigger": "deal",
            },
        )
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=fallback,
            blocks=blocks,
        )
        return

    # Exactly 1 contact — draft email directly
    primary_contact = contacts[0]
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"⏳ Drafting email for *{company_name}*..."
    )

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {company_name}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    subject = f"Following up - {company_name}"
    body_text = llm_response
    if "Subject:" in llm_response:
        parts = llm_response.split("Subject:")
        if len(parts) > 1:
            subject = parts[1].split("\n")[0].strip()
            body_text = "\n".join(parts[1].split("\n")[1:]).strip()

    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=primary_contact.get("name", "Contact"),
        to_email=primary_contact.get("email", "contact@example.com"),
        subject=subject,
        body=body_text[:2000],
    )

    # Update loading message with email draft
    client.chat_update(
        channel=channel,
        ts=loading_msg["ts"],
        text=fallback,
        blocks=blocks,
    )


# Removed duplicate @app.action("log_note") - the active handler is at line 6373
# Removed duplicate @app.view("submit_note") - the active handler is "log_note_modal"

@app.action("create_gmail_draft")
def handle_create_draft(ack, body, say):
    """User clicked 'Create Gmail Draft' — use Gmail MCP to create the draft."""
    ack()
    email_data = json.loads(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    thread_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="create_gmail_draft")

    # In production, this would use Gmail MCP tool
    say(
        text=f"Draft created in Gmail! Check your drafts folder.\n\n*Subject:* {email_data['subject']}",
        channel=channel,
        thread_ts=thread_ts,
    )


@app.action("regenerate_email")
def handle_regenerate(ack, body, say):
    """User clicked 'Regenerate' — create a new email draft with same contact."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    say(text=f"Regenerating email for *{company_name}*...", channel=channel)

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {company_name} -- different approach, more casual tone")],
        "route": "assistant",
        "workflow": "email",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    # Use proper contact lookup (no picker on regenerate — keep same contact)
    contacts = get_contacts_for_deal_or_company(deal_name=company_name, company_name=company_name)
    primary_contact = contacts[0] if contacts else {"name": "Contact", "email": "contact@example.com"}
    llm_response = result["messages"][-1].content

    subject = f"Quick follow-up - {company_name}"
    body_text = llm_response
    if "Subject:" in llm_response:
        parts = llm_response.split("Subject:")
        if len(parts) > 1:
            subject = parts[1].split("\n")[0].strip()
            body_text = "\n".join(parts[1].split("\n")[1:]).strip()

    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=primary_contact.get("name", "Contact"),
        to_email=primary_contact.get("email", "contact@example.com"),
        subject=subject,
        body=body_text[:2000],
    )

    say(text=fallback, blocks=blocks, channel=channel)


@app.action("copy_email_text")
def handle_copy_text(ack, body, say):
    """User clicked 'Copy Text' — post the email as plain text they can copy."""
    ack()
    email_data = json.loads(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    thread_ts = body["message"]["ts"]

    plain_text = f"Subject: {email_data['subject']}\n\n{email_data['body']}"
    say(text=plain_text, channel=channel, thread_ts=thread_ts)


@app.action("select_email_contact")
def handle_select_email_contact(ack, body, client):
    """User selected a contact for the email draft — now draft the email."""
    ack()

    action_data = json.loads(body["actions"][0]["value"])
    contact_name = action_data.get("contact_name", "Contact")
    contact_email = action_data.get("contact_email", "")
    company_name = action_data.get("company_name", "")
    deal_name = action_data.get("deal_name", "")

    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    message_ts = body["message"]["ts"]
    # Get thread_ts if we're in a thread, otherwise use message_ts as thread parent
    thread_ts = body["message"].get("thread_ts", message_ts)

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"✉️ Drafting email to *{contact_name}* ({contact_email})...",
    )

    # Run the LLM to generate the email
    context_text = deal_name if deal_name else company_name
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {context_text}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": user_id,
        "channel_id": channel,
        "thread_ts": None,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
    })

    llm_response = result["messages"][-1].content

    # Parse subject and body from LLM response
    subject = f"Following up - {company_name}"
    body_text = llm_response
    if "Subject:" in llm_response:
        lines = llm_response.split("\n")
        for i, line in enumerate(lines):
            if "Subject:" in line:
                subject = line.split("Subject:")[-1].strip().strip("*")
                body_text = "\n".join(lines[i+1:]).strip()
                break

    if len(body_text) > 2000:
        body_text = body_text[:2000]

    # Format the email draft with the SELECTED contact
    from formatters import format_email_draft
    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=contact_name,
        to_email=contact_email,
        subject=subject,
        body=body_text,
    )

    # Update loading message with email draft
    client.chat_update(
        channel=channel,
        ts=loading_msg["ts"],
        text=fallback,
        blocks=blocks,
    )


@app.action("select_email_deal")
def handle_select_email_deal(ack, body, client):
    """User selected a deal — now show contact picker for that deal."""
    ack()

    action_data = json.loads(body["actions"][0]["value"])
    deal_name = action_data.get("deal_name", "")
    deal_id = action_data.get("deal_id", "")
    company_name = action_data.get("company_name", "")
    stage = action_data.get("stage", "")
    value = action_data.get("value", "")

    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    message_ts = body["message"]["ts"]
    # Get thread_ts if we're in a thread, otherwise use message_ts as thread parent
    thread_ts = body["message"].get("thread_ts", message_ts)

    # Get contacts for this deal/company
    contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company_name)

    if len(contacts) == 0:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"⚠️ No contacts found for *{deal_name}*.",
        )
        return

    elif len(contacts) == 1:
        # Single contact — draft directly
        contact = contacts[0]
        contact_name = contact.get("name", "Contact")
        contact_email = contact.get("email", "")

        loading_msg = client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"✉️ Drafting email to *{contact_name}* about *{deal_name}*...",
        )

        context_text = deal_name if deal_name else company_name
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/draft-email {context_text}")],
            "route": "assistant",
            "workflow": "email",
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": None,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": contact_email,
        })

        llm_response = result["messages"][-1].content
        subject = f"Following up - {company_name}"
        body_text = llm_response
        if "Subject:" in llm_response:
            lines = llm_response.split("\n")
            for i, line in enumerate(lines):
                if "Subject:" in line:
                    subject = line.split("Subject:")[-1].strip().strip("*")
                    body_text = "\n".join(lines[i+1:]).strip()
                    break

        if len(body_text) > 2000:
            body_text = body_text[:2000]

        from formatters import format_email_draft
        blocks, fallback = format_email_draft(
            company_name=company_name,
            to_name=contact_name,
            to_email=contact_email,
            subject=subject,
            body=body_text,
        )
        client.chat_update(channel=channel, ts=loading_msg["ts"], text=fallback, blocks=blocks)

    else:
        # Multiple contacts — show contact picker in thread
        from formatters import format_contact_picker
        blocks, fallback = format_contact_picker(
            company_name=company_name,
            contacts=contacts,
            email_context={
                "company_name": company_name,
                "deal_name": deal_name,
                "deal_id": deal_id,
                "trigger": "draft_email",
            },
        )
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=fallback, blocks=blocks)


@app.action("practice_again")
def handle_practice_again(ack, body, say):
    """User clicked 'Practice Again' on a debrief — restart the same scenario."""
    ack()
    scenario = body["actions"][0]["value"] or "discovery call"
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="practice_again", scenario=scenario)

    persona = {
        "name": "Jordan Smith",
        "title": "Director of Procurement",
        "company": "Prospect Inc",
        "personality": "Direct, time-conscious, focused on ROI",
    }

    blocks, fallback = format_roleplay_start(persona, scenario)
    result_msg = say(text=fallback, blocks=blocks, channel=channel)
    thread_ts = result_msg["ts"]

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/coach roleplay {scenario}")],
        "route": "coach",
        "workflow": "roleplay",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": thread_ts,
    })

    response_text = result["messages"][-1].content
    say(text=response_text, channel=channel, thread_ts=thread_ts)

    active_roleplays[thread_ts] = {
        "messages": result["messages"],
        "turn_count": 1,
        "max_turns": DEFAULT_ROLEPLAY_TURNS,
        "rag_context": result.get("rag_context", ""),
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "scenario": scenario,
    }


@app.action("try_suggested")
def handle_try_suggested(ack, body, say):
    """User clicked 'Try Suggested Scenario' on a debrief."""
    ack()
    suggested = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="try_suggested", scenario=suggested)

    persona = {
        "name": "Morgan Lee",
        "title": "CFO",
        "company": "Growth Corp",
        "personality": "Numbers-focused, skeptical, asks tough questions",
    }

    blocks, fallback = format_roleplay_start(persona, suggested)
    result_msg = say(text=fallback, blocks=blocks, channel=channel)
    thread_ts = result_msg["ts"]

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/coach roleplay {suggested}")],
        "route": "coach",
        "workflow": "roleplay",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": thread_ts,
    })

    response_text = result["messages"][-1].content
    say(text=response_text, channel=channel, thread_ts=thread_ts)

    active_roleplays[thread_ts] = {
        "messages": result["messages"],
        "turn_count": 1,
        "max_turns": DEFAULT_ROLEPLAY_TURNS,
        "rag_context": result.get("rag_context", ""),
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "scenario": suggested,
    }


@app.action("drill_flagged_deal")
def handle_drill_flagged(ack, body, client):
    """User clicked 'Drill into Flagged Deal' on pipeline digest."""
    deal_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    log_engagement(user_id, "action", action_id="drill_flagged_deal", deal_id=deal_id)

    # Validate BEFORE ack
    if not deal_id or deal_id == "none":
        ack()
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text="No flagged deals to drill into."
        )
        return

    # Try to find deal - first by ID, then fallback to lookup by name
    deal = None
    if hasattr(mock_crm, 'get_deal_by_id'):
        deal = mock_crm.get_deal_by_id(deal_id)

    # Fallback: try lookup by name if ID didn't work
    if not deal and hasattr(mock_crm, 'get_deal_by_name'):
        deal = mock_crm.get_deal_by_name(deal_id)

    if not deal:
        ack()
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ Could not find deal with ID/name: {deal_id}"
        )
        return

    # Now safe to ack and proceed
    ack()

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text="⏳ Looking up deal details..."
    )
    loading_ts = loading_msg["ts"]

    try:
        deal_name = deal.get("properties", {}).get("dealname", deal_id)

        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/deal {deal_name}")],
            "route": "assistant",
            "workflow": "deal",
            "user_id": body["user"]["id"],
            "channel_id": channel,
            "thread_ts": None,
        })

        deal_data, contacts, activities = extract_deal_data(deal_name)
        llm_response = result["messages"][-1].content
        recommendations = parse_recommendations(llm_response)

        if deal_data:
            blocks, fallback = format_deal_response(
                deal=deal_data,
                contacts=contacts,
                activities=activities,
                recommendations=recommendations,
            )
            client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)
        else:
            client.chat_update(channel=channel, ts=loading_ts, text=llm_response)

    except Exception as e:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.action("view_all_flagged_deals")
def handle_view_all_flagged_deals(ack, body, client):
    """User clicked 'View All Flagged Deals' — show summary with deep dive options."""
    ack()
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="view_all_flagged_deals")

    # Get the message_ts from container (ephemeral messages use container.ts)
    container = body.get("container", {})
    if container.get("type") == "ephemeral_message":
        message_ts = container.get("message_ts")
    else:
        message_ts = body.get("message", {}).get("ts") or container.get("message_ts")

    # Post loading message in thread (or as new ephemeral if no thread)
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts if message_ts else None,
        text="⏳ Loading flagged deals..."
    )
    loading_ts = loading_msg["ts"]

    try:
        # Use direct CRM data (same as /pipeline handler)
        open_deals = mock_crm.get_all_open_deals_for_user(None)
        if not open_deals:
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                text="No open deals found — pipeline may be empty."
            )
            return

        from tools.mock_crm import get_stale_deals_for_user, get_overdue_deals_for_user

        # Flagged deals
        stale = get_stale_deals_for_user(stale_days=14, owner_id=None)
        overdue = get_overdue_deals_for_user(owner_id=None)
        flagged_deals = []
        for deal in stale:
            props = deal.get("properties", {})
            flagged_deals.append({
                "id": deal.get("id", ""),
                "name": props.get("dealname", "Unknown"),
                "flag": "stale",
                "reason": "No activity in 14+ days",
            })
        for deal in overdue:
            props = deal.get("properties", {})
            flagged_deals.append({
                "id": deal.get("id", ""),
                "name": props.get("dealname", "Unknown"),
                "flag": "overdue",
                "reason": f"Past close date: {props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'}",
            })

        if not flagged_deals:
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                text="No flagged deals — your pipeline looks healthy!"
            )
            return

        # Format and display
        from formatters.pipeline import format_flagged_deals_summary
        blocks, fallback = format_flagged_deals_summary(flagged_deals)
        client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.action("back_to_pipeline")
def handle_back_to_pipeline(ack, body, client):
    """User clicked 'Back to Pipeline' — simple acknowledgment."""
    ack()
    # This is a navigation button — just acknowledge and let the user re-run /pipeline
    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=body["message"]["ts"],
        text="Use `/pipeline` to refresh the pipeline view."
    )


@app.action("refresh_pipeline")
def handle_refresh_pipeline(ack, body, client):
    """User clicked 'Refresh Pipeline' — re-run the pipeline analysis."""
    ack()
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text="⏳ Refreshing pipeline data..."
    )
    loading_ts = loading_msg["ts"]

    try:
        result = app_graph.invoke({
            "messages": [HumanMessage(content="/pipeline")],
            "route": "assistant",
            "workflow": "pipeline",
            "user_id": body["user"]["id"],
            "channel_id": channel,
            "thread_ts": None,
        })

        total_value, deal_count, weighted_forecast, deals_by_stage, flagged_deals = extract_pipeline_data()

        llm_response = result["messages"][-1].content
        recommendations = []
        if "Recommended" in llm_response:
            rec_section = llm_response.split("Recommended")[-1]
            for line in rec_section.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("•") or line.startswith("-")):
                    recommendations.append(line.lstrip("0123456789.-• "))
                    if len(recommendations) >= 5:
                        break

        if not recommendations:
            recommendations = [
                "Follow up on stale deals this week",
                "Update close dates for overdue opportunities",
                "Schedule discovery calls for new leads",
            ]

        blocks, fallback = format_pipeline_response(
            total_value=total_value,
            deal_count=deal_count,
            weighted_forecast=weighted_forecast,
            deals_by_stage=deals_by_stage,
            flagged_deals=flagged_deals,
            recommendations=recommendations,
        )

        # Update loading message with final result
        client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


# --- /objection Command ---

@app.command("/objection")
def handle_objection(ack, say, command):
    """Instant objection handling response — optimized for speed."""
    ack()
    objection_text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/objection", objection=objection_text[:100])

    if not objection_text:
        say(
            "Tell me the objection: `/objection [what they said]`\n"
            "Examples:\n• `/objection your pricing is too high`\n"
            "• `/objection we're already using a competitor`\n"
            "• `/objection we need to think about it`",
            channel=channel_id,
        )
        return

    say(f"Finding response...", channel=channel_id)

    try:
        # 1. RAG search — objection playbook + battle cards (fast, no API calls)
        from tools.rag import search_playbooks
        objection_context = search_playbooks(
            f"objection handling: {objection_text}",
            n_results=5,
        )
        battle_card_context = search_playbooks(
            f"competitive positioning value proposition pricing",
            n_results=3,
        )

        # 2. LLM — concise prompt for fast response
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""A sales rep is on a LIVE CALL. The buyer just said: "{objection_text}"

The rep needs a response RIGHT NOW. Be concise and actionable.

OBJECTION HANDLING PLAYBOOK:
{objection_context}

BATTLE CARDS / VALUE PROP:
{battle_card_context}

Generate EXACTLY this format:

RESPONSE: [2-3 sentence response the rep can say verbatim. Acknowledge the concern, reframe, provide value.]

PROOF_POINT_1: [One specific data point, case study reference, or ROI number]
PROOF_POINT_2: [Another proof point]
PROOF_POINT_3: [Another proof point]

AVOID_1: [One thing NOT to say — a common mistake]
AVOID_2: [Another thing to avoid]

PIVOT_QUESTION: [One question to redirect the conversation productively]

Be specific, not generic. Use the playbook context.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 3. Parse the structured response
        response_script = ""
        proof_points = []
        avoid = []
        follow_up = ""

        for line in llm_response.split("\n"):
            line = line.strip()
            if line.upper().startswith("RESPONSE:"):
                response_script = line.split(":", 1)[1].strip()
            elif line.upper().startswith("PROOF_POINT"):
                proof_points.append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("AVOID"):
                avoid.append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("PIVOT_QUESTION:"):
                follow_up = line.split(":", 1)[1].strip()

        # Fallback if parsing fails — use the whole LLM response as the script
        if not response_script:
            response_script = llm_response[:500]

        if not follow_up:
            follow_up = "What would make this a no-brainer for you?"

        # 4. Format and send
        from formatters import format_objection_response
        blocks, fallback = format_objection_response(
            objection=objection_text,
            response_script=response_script,
            proof_points=proof_points,
            avoid=avoid,
            follow_up_question=follow_up,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/objection", e)


@app.action("practice_objection")
def handle_practice_objection(ack, body, say):
    """Start a roleplay focused on this specific objection."""
    ack()
    objection = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    log_engagement(user_id, "action", action_id="practice_objection", objection=objection)

    say(
        text=f"Try: `/coach roleplay objection handling — buyer says: {objection}`",
        channel=channel,
    )


@app.action("expand_objection")
def handle_expand_objection(ack, body, say):
    """Get a more detailed analysis of this objection."""
    ack()
    objection = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    say(f"Getting deeper analysis of this objection...", channel=channel)

    # Run a more detailed LLM analysis
    from tools.rag import search_playbooks
    context = search_playbooks(f"objection handling {objection}", n_results=8)

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Provide an in-depth analysis of this sales objection: "{objection}"

PLAYBOOK CONTEXT:
{context}

Include:
1. Why buyers typically raise this objection (root causes)
2. Three different response approaches (empathetic, data-driven, redirect)
3. Real-world examples of how top reps handle this
4. How to prevent this objection earlier in the sales process

Keep it practical and actionable.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel,
        "thread_ts": None,
    })

    say(text=result["messages"][-1].content, channel=channel)


@app.action("objection_overflow")
def handle_objection_overflow(ack, body, say):
    """Handle overflow menu selections for objection responses."""
    ack()
    selected_option = body["actions"][0]["selected_option"]["value"]
    action, value = selected_option.split("|", 1)
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    if action == "expand_objection":
        # Delegate to the existing expand handler
        body["actions"][0]["value"] = value
        handle_expand_objection(ack=lambda: None, body=body, say=say)
    elif action == "save_objection":
        say(
            text=f"Objection saved to your playbook: _{value}_",
            channel=channel,
            thread_ts=message_ts,
        )


@app.action("deal_overflow")
def handle_deal_overflow(ack, body, client):
    """Handle overflow menu selections for deal cards."""
    ack()
    selected_option = body["actions"][0]["selected_option"]["value"]
    action, value = selected_option.split("|", 1)
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    trigger_id = body["trigger_id"]

    # Get message_ts from container for ephemeral messages
    container = body.get("container", {})
    if container.get("type") == "ephemeral_message":
        message_ts = container.get("message_ts")
    else:
        message_ts = body.get("message", {}).get("ts") or container.get("message_ts")

    if action == "research_from_deal":
        # Trigger research workflow
        log_engagement(user_id, "action", action_id="research_from_deal_overflow", company=value)

        loading_msg = client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts if message_ts else None,
            text=f"⏳ Researching *{value}*..."
        )
        loading_ts = loading_msg["ts"]

        try:
            result = app_graph.invoke({
                "messages": [HumanMessage(content=f"/research {value}")],
                "route": "assistant",
                "workflow": "research",
                "user_id": user_id,
                "channel_id": channel,
                "thread_ts": None,
            })

            # These functions are defined in app.py
            company_data = extract_company_data(value)
            contacts = extract_contacts(value)
            deals = extract_deals(value)
            llm_response = result["messages"][-1].content

            # Use the existing parse_talking_points function (returns a string, not a list)
            talking_points = parse_talking_points(llm_response)

            blocks, fallback = format_research_summary(
                company_name=value,
                company_data=company_data,
                contacts=contacts,
                deals=deals,
                news=[],
                talking_points=talking_points,
            )

            client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)

        except Exception as e:
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
            )
            traceback.print_exc()

    elif action == "log_note":
        # Open modal to log a note
        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "log_note_modal",
                "title": {"type": "plain_text", "text": "Log Note"},
                "submit": {"type": "plain_text", "text": "Save to CRM"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "private_metadata": json.dumps({"deal_name": value}),
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Deal:* {value}"}
                    },
                    {
                        "type": "input",
                        "block_id": "note_input_block",
                        "label": {"type": "plain_text", "text": "Note"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "note_text",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "What happened? Key takeaways, next steps, decisions made..."},
                        }
                    },
                ]
            }
        )


@app.action("win_loss_overflow")
def handle_win_loss_overflow(ack, body, say):
    """Handle overflow menu selections for win/loss analysis."""
    ack()
    selected_option = body["actions"][0]["selected_option"]["value"]
    action, value = selected_option.split("|", 1)
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    if action == "win_loss_won_deals":
        # Delegate to existing handler
        body["actions"][0]["value"] = value
        handle_win_loss_won(ack=lambda: None, body=body, say=say)
    elif action == "win_loss_competitor":
        # Delegate to existing handler
        body["actions"][0]["value"] = value
        handle_win_loss_competitor(ack=lambda: None, body=body, say=say)
    elif action == "win_loss_export":
        say(
            text="Exporting win/loss report... _This feature is coming soon._",
            channel=channel,
            thread_ts=message_ts,
        )


# --- /ask Command ---

@app.command("/ask")
def handle_ask(ack, say, command):
    """Answer any natural language question about CRM/pipeline/deals."""
    ack()
    question = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/ask", question=question[:100])

    if not question:
        say(
            "Ask me anything about your CRM:\n"
            "• `/ask What deals are closing this month?`\n"
            "• `/ask Who's our contact at NovaTech?`\n"
            "• `/ask Show me stale deals over $50K`\n"
            "• `/ask What happened in our last call with Apex?`",
            channel=channel_id,
        )
        return

    say(f"Thinking...", channel=channel_id)

    try:
        # 1. Classify the question to determine data sources
        question_lower = question.lower()
        data_sources = []
        context_parts = []
        related_actions = []

        # Check for performance-related questions (Feature #9: Self-Service)
        PERFORMANCE_KEYWORDS = [
            "my month", "my quarter", "my target", "my win rate", "how am i",
            "my score", "improving", "my pipeline", "how many", "my deals",
            "my performance", "my stats", "my progress", "am i getting better",
            "my coaching", "my training", "my roleplays", "my sessions",
        ]
        if any(kw in question_lower for kw in PERFORMANCE_KEYWORDS):
            stats = get_training_stats(user_id)
            recent = get_training_history(user_id, limit=5)

            if stats and stats.get("total_sessions", 0) > 0:
                personal_context = f"""USER'S PERSONAL TRAINING DATA:
- Total coaching sessions: {stats['total_sessions']}
- Average score: {stats['avg_score']:.1f}/10
- Best score: {stats['best_score']:.1f}/10
- Last session: {stats['last_session']}

Recent Sessions:
"""
                for s in recent:
                    personal_context += f"- {s['scenario']} ({s['scenario_type']}) — Score: {s['overall_score']}/10 — {s['timestamp']}\n"

                context_parts.append(personal_context)
                data_sources.append("Training History")

        # Determine what data to pull based on the question
        from tools.rag import search_crm, search_crm_deals, search_crm_contacts, search_playbooks

        # Always search CRM broadly
        crm_results = search_crm(question, n_results=8)
        if crm_results and "No" not in crm_results[:20]:
            context_parts.append(f"CRM DATA:\n{crm_results}")
            data_sources.append("HubSpot CRM")

        # If question mentions contacts or people
        if any(w in question_lower for w in ["contact", "who", "person", "email", "phone", "name"]):
            contact_results = search_crm_contacts(question, n_results=5)
            if contact_results and "No" not in contact_results[:20]:
                context_parts.append(f"CONTACTS:\n{contact_results}")

        # If question is about deals, pipeline, revenue, stage
        if any(w in question_lower for w in ["deal", "pipeline", "revenue", "stage", "closing", "stale", "overdue", "amount", "forecast"]):
            deal_results = search_crm_deals(question, n_results=8)
            if deal_results and "No" not in deal_results[:20]:
                context_parts.append(f"DEALS:\n{deal_results}")

            # Also pull mock CRM aggregates for pipeline questions
            all_deals = mock_crm.get_all_open_deals()
            stale = mock_crm.get_stale_deals(stale_days=14)
            overdue = mock_crm.get_overdue_deals()

            pipeline_summary = f"Total open deals: {len(all_deals)}\n"
            pipeline_summary += f"Stale deals (14+ days): {len(stale)}\n"
            pipeline_summary += f"Overdue deals: {len(overdue)}\n"

            # Stage breakdown
            stage_counts = {}
            total_value = 0
            for d in all_deals:
                props = d.get("properties", {})
                stage = props.get("dealstage", "unknown")
                amount = float(props.get("amount", 0) or 0)
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
                total_value += amount

            pipeline_summary += f"Total pipeline value: ${total_value:,.0f}\n"
            for stage, count in stage_counts.items():
                pipeline_summary += f"  {stage}: {count} deals\n"

            context_parts.append(f"PIPELINE SUMMARY:\n{pipeline_summary}")
            data_sources.append("Pipeline Analytics")

            # Add related action
            related_actions.append({
                "label": "View Full Pipeline",
                "action_id": "refresh_pipeline",
                "value": "refresh",
            })

        # If question is about activities, calls, meetings, notes
        if any(w in question_lower for w in ["call", "meeting", "note", "activity", "last", "discuss", "talked"]):
            from tools.rag import search_call_transcripts, search_meeting_notes
            transcript_results = search_call_transcripts(question, n_results=3)
            meeting_results = search_meeting_notes(question, n_results=3)
            if transcript_results and "No" not in transcript_results[:20]:
                context_parts.append(f"CALL TRANSCRIPTS:\n{transcript_results}")
                data_sources.append("Call Transcripts")
            if meeting_results and "No" not in meeting_results[:20]:
                context_parts.append(f"MEETING NOTES:\n{meeting_results}")
                data_sources.append("Meeting Notes")

        # If question is about best practices, methodology, playbook
        if any(w in question_lower for w in ["how to", "best practice", "playbook", "template", "approach", "strategy"]):
            playbook_results = search_playbooks(question, n_results=5)
            if playbook_results:
                context_parts.append(f"SALES PLAYBOOKS:\n{playbook_results}")
                data_sources.append("Sales Playbooks")

        if not data_sources:
            data_sources.append("AI Knowledge")

        # 2. Run LLM to generate answer
        combined_context = "\n\n---\n\n".join(context_parts) if context_parts else "No specific data found."

        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""A sales rep asked: "{question}"

Here is the data available to answer their question:

{combined_context}

Answer the question directly and concisely. Use specific data from the context above.
If the answer involves specific deals, contacts, or numbers — include them.
If you can't find the answer in the data, say so honestly and suggest what command they could use.

Format your answer using Slack mrkdwn:
- Bold with *text*
- Bullet points with •
- Keep it scannable — reps are busy

Do NOT wrap your response in any code blocks or extra formatting. Just answer naturally.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        answer = result["messages"][-1].content

        # 3. Format and send
        from formatters import format_ask_response
        blocks, fallback = format_ask_response(
            question=question,
            answer=answer,
            data_sources=data_sources,
            related_actions=related_actions,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/ask", e)


@app.action("noop")
def handle_noop(ack):
    """No-op handler for placeholder buttons."""
    ack()


# --- App Home Tab ---

@app.event("app_home_opened")
def handle_app_home_opened(client, event):
    """Render the App Home tab dashboard when user opens it."""
    user_id = event["user"]

    try:
        # Get user info for greeting
        user_info = client.users_info(user=user_id)
        user_name = user_info["user"]["profile"].get("first_name", "there")
    except Exception:
        user_name = "there"

    # Build pipeline summary
    all_deals = mock_crm.get_all_open_deals()
    stale = mock_crm.get_stale_deals(stale_days=14)
    overdue = mock_crm.get_overdue_deals()

    total_value = 0
    stage_counts = {}
    for deal in all_deals:
        props = deal.get("properties", {})
        amount = float(props.get("amount", 0) or 0)
        stage = props.get("dealstage", "unknown")
        total_value += amount
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Weighted forecast (simple: 50% of total for POC)
    weighted_forecast = total_value * 0.5

    pipeline_summary = {
        "total_value": total_value,
        "deal_count": len(all_deals),
        "weighted_forecast": weighted_forecast,
        "by_stage": stage_counts,
    }

    # Deals needing attention
    deals_needing_attention = []
    for deal in overdue:
        props = deal.get("properties", {})
        deals_needing_attention.append({
            "name": props.get("dealname", "Unknown"),
            "flag": "overdue",
            "reason": f"Past close date ({props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'})",
            "amount": props.get("amount", 0),
        })
    for deal in stale:
        props = deal.get("properties", {})
        name = props.get("dealname", "Unknown")
        if not any(d["name"] == name for d in deals_needing_attention):
            deals_needing_attention.append({
                "name": name,
                "flag": "stale",
                "reason": "No activity in 14+ days",
                "amount": props.get("amount", 0),
            })

    # Recent coaching (from in-memory state - check if exists)
    recent_coaching = {}

    # Format blocks
    from formatters.home_tab import format_home_tab
    blocks = format_home_tab(
        user_name=user_name,
        pipeline_summary=pipeline_summary,
        deals_needing_attention=deals_needing_attention,
        recent_coaching=recent_coaching,
    )

    # Publish to App Home
    client.views_publish(
        user_id=user_id,
        view={
            "type": "home",
            "blocks": blocks,
        }
    )


@app.action("home_view_deal")
def handle_home_view_deal(ack, body, client):
    """View a deal from the Home tab."""
    ack()
    deal_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/deal {deal_name}` in any channel to see the full deal card.",
    )


@app.action("home_pipeline")
def handle_home_pipeline(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/pipeline` in any channel to see your full pipeline digest.")


@app.action("home_followups")
def handle_home_followups(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/followup` in any channel to see deals needing follow-up.")


@app.action("home_practice")
def handle_home_practice(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="Start a practice session:\n• `/coach roleplay discovery call`\n• `/coach roleplay objection handling`\n• `/coach roleplay competitive deal`",
    )


@app.action("home_scorecard")
def handle_home_scorecard(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/scorecard` in any channel to see your performance scorecard.")


@app.action("home_research")
def handle_home_research(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/research [company name]` in any channel to get a research brief.")


@app.action("home_ask")
def handle_home_ask(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(channel=user_id, text="Use `/ask [your question]` in any channel to ask anything about your CRM.")


# --- /followup Command ---

@app.command("/followup")
def handle_followup(ack, say, command):
    """Generate smart follow-up recommendations for open deals."""
    ack()
    filter_text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/followup")

    say(f"Scanning deals for follow-up actions...", channel=channel_id)

    try:
        # 1. Get deals that need follow-up
        stale_deals = mock_crm.get_stale_deals(stale_days=7)
        overdue_deals = mock_crm.get_overdue_deals()

        # Build candidate list with urgency
        candidates = []

        for deal in overdue_deals:
            props = deal.get("properties", {})
            deal_name = props.get("dealname", "Unknown")
            # Optional filter
            if filter_text and filter_text.lower() not in deal_name.lower():
                continue
            candidates.append({
                "deal_name": deal_name,
                "company": deal_name.split("—")[0].strip() if "—" in deal_name else deal_name,
                "urgency": "high",
                "reason": f"Past close date ({props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'})",
                "amount": props.get("amount", 0),
                "stage": props.get("dealstage", ""),
                "last_activity": "",
            })

        for deal in stale_deals:
            props = deal.get("properties", {})
            deal_name = props.get("dealname", "Unknown")
            if filter_text and filter_text.lower() not in deal_name.lower():
                continue
            # Skip if already in candidates (overdue takes priority)
            if any(c["deal_name"] == deal_name for c in candidates):
                continue
            candidates.append({
                "deal_name": deal_name,
                "company": deal_name.split("—")[0].strip() if "—" in deal_name else deal_name,
                "urgency": "medium",
                "reason": "No activity in 7+ days",
                "amount": props.get("amount", 0),
                "stage": props.get("dealstage", ""),
                "last_activity": "",
            })

        if not candidates:
            say("All your deals look active! No follow-ups needed right now.", channel=channel_id)
            return

        # 2. Run LLM to generate personalized follow-up suggestions
        deals_summary = "\n".join([
            f"- {c['deal_name']} | Stage: {c['stage']} | Urgency: {c['urgency']} | Reason: {c['reason']}"
            for c in candidates[:10]
        ])

        from tools.rag import search_playbooks
        rag_context = search_playbooks("follow up email stale deal re-engage", n_results=3)

        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""For each deal below, generate:
1. A specific follow-up action (1 sentence)
2. A draft email opening line (1 sentence, conversational, not generic)

DEALS NEEDING FOLLOW-UP:
{deals_summary}

FOLLOW-UP BEST PRACTICES FROM PLAYBOOK:
{rag_context}

Format your response as:
DEAL: [deal name]
ACTION: [specific action]
OPENER: [email opening line]

Repeat for each deal. Be specific — reference the deal stage and reason for follow-up.""")],
            "route": "assistant",
            "workflow": "email",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 3. Parse LLM response and merge with candidates
        followup_items = parse_followup_suggestions(candidates, llm_response)

        # 4. Format and send
        from formatters import format_followup_response
        blocks, fallback = format_followup_response(
            followup_items=followup_items,
            total_count=len(candidates),
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/followup", e)


def parse_followup_suggestions(candidates: list, llm_text: str) -> list:
    """Merge LLM-generated suggestions into the candidate deal list."""
    # Parse LLM output (DEAL: / ACTION: / OPENER: format)
    suggestions = {}
    current_deal = None

    for line in llm_text.split("\n"):
        line = line.strip()
        if line.upper().startswith("DEAL:"):
            current_deal = line.split(":", 1)[1].strip()
        elif line.upper().startswith("ACTION:") and current_deal:
            suggestions.setdefault(current_deal, {})["action"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("OPENER:") and current_deal:
            suggestions.setdefault(current_deal, {})["opener"] = line.split(":", 1)[1].strip()

    # Merge suggestions into candidates
    for candidate in candidates:
        deal_name = candidate["deal_name"]
        # Fuzzy match — check if any suggestion key is contained in deal name or vice versa
        matched = None
        for key in suggestions:
            if key.lower() in deal_name.lower() or deal_name.lower() in key.lower():
                matched = suggestions[key]
                break

        if matched:
            candidate["suggested_action"] = matched.get("action", "Follow up with a personalized email")
            candidate["draft_snippet"] = matched.get("opener", "")
        else:
            candidate["suggested_action"] = "Send a check-in email referencing your last conversation"
            candidate["draft_snippet"] = ""

    return candidates


@app.action("draft_followup_email")
def handle_draft_followup_email(ack, body, say, client):
    """Draft a follow-up email for a specific deal from the follow-up list."""
    ack()
    action_data = json.loads(body["actions"][0]["value"])
    company = action_data.get("company", action_data.get("deal_name", ""))
    deal_name = action_data.get("deal_name", "")
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Get contacts using deal/company associations
    contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company)

    if len(contacts) == 0:
        say(text=f"⚠️ No contacts found for *{company}*.", channel=channel)
        return

    elif len(contacts) > 1:
        # Multiple contacts — show picker (update the message in place)
        from formatters import format_contact_picker
        blocks, fallback = format_contact_picker(
            company_name=company,
            contacts=contacts,
            email_context={
                "company_name": company,
                "deal_name": deal_name,
                "trigger": "followup",
            },
        )
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=fallback,
            blocks=blocks,
        )
        return

    # Exactly 1 contact — draft email directly
    primary_contact = contacts[0]
    say(f"Drafting follow-up for *{company}*...", channel=channel)

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {company}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": body["user"]["id"],
        "channel_id": channel,
        "thread_ts": None,
    })

    # Extract and format email
    llm_response = result["messages"][-1].content

    # Parse email from response
    subject = f"Following up - {company}"
    body_text = llm_response

    # Try to extract subject if present
    if "Subject:" in llm_response:
        lines = llm_response.split("\n")
        for i, line in enumerate(lines):
            if "Subject:" in line:
                subject = line.split("Subject:")[-1].strip()
                body_text = "\n".join(lines[i+1:]).strip()
                break

    from formatters import format_email_draft
    blocks, fallback = format_email_draft(
        company_name=company,
        to_name=primary_contact.get("name", "Contact"),
        to_email=primary_contact.get("email", ""),
        subject=subject,
        body=body_text,
    )
    say(text=fallback, blocks=blocks, channel=channel)


@app.action("refresh_followups")
def handle_refresh_followups(ack, body, client):
    """Refresh the follow-up list."""
    ack()
    channel = body["channel"]["id"]
    client.chat_postMessage(
        channel=channel,
        text="Use `/followup` to refresh your follow-up list.",
    )


# --- /competitor Command ---

@app.command("/competitor")
def handle_competitor(ack, say, command):
    """Generate competitive intelligence brief."""
    ack()
    competitor_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/competitor", competitor=competitor_name)

    if not competitor_name:
        say("Please provide a competitor name: `/competitor [name]`", channel=channel_id)
        return

    say(f"Gathering intel on *{competitor_name}*...", channel=channel_id)

    try:
        # 1. Search RAG for battle cards mentioning this competitor
        from tools.rag import search_playbooks, search_crm
        battle_card_context = search_playbooks(f"{competitor_name} competitor positioning battle card", n_results=5)
        crm_context = search_crm(f"{competitor_name} competitor", n_results=3)

        # 2. Live web search for recent competitor news
        from tools.web_search import search_company_news
        web_results = search_company_news(competitor_name)

        # 3. Run LLM to generate the competitive brief
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Generate a competitive intelligence brief about {competitor_name}.

BATTLE CARD / PLAYBOOK CONTEXT:
{battle_card_context}

CRM NOTES MENTIONING THIS COMPETITOR:
{crm_context}

RECENT NEWS ABOUT {competitor_name.upper()}:
{web_results}

Generate the following (be specific, not generic):

1. OUR POSITIONING (2-3 sentences): How we position against {competitor_name}
2. THEIR STRENGTHS (3-5 bullet points)
3. THEIR WEAKNESSES (3-5 bullet points)
4. COUNTER-ARGUMENTS (3-5 items): When the prospect says "[competitor claim]", respond with "[our counter]"
   Format each as: OBJECTION: "..." | RESPONSE: "..."
5. TALKING POINTS (3-5 bullet points): Specific things to say in a competitive deal

Be concise and actionable. Reps need to use this in the next 5 minutes.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 4. Parse the LLM response into structured data
        positioning, strengths_weaknesses, counter_arguments, talking_points = parse_competitor_response(llm_response)

        # 5. Parse web results into news items
        recent_news = parse_news_items(web_results)

        # 6. Find deals mentioning this competitor
        deals_at_risk = find_deals_mentioning_competitor(competitor_name)

        # 7. Format and send
        from formatters import format_competitor_response
        blocks, fallback = format_competitor_response(
            competitor_name=competitor_name,
            positioning=positioning,
            strengths_weaknesses=strengths_weaknesses,
            counter_arguments=counter_arguments,
            recent_news=recent_news,
            deals_at_risk=deals_at_risk,
            talking_points=talking_points,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/competitor", e)


def parse_competitor_response(llm_text: str) -> tuple:
    """Parse the LLM competitor analysis into structured data.

    Returns: (positioning, strengths_weaknesses, counter_arguments, talking_points)
    """
    positioning = ""
    strengths_weaknesses = {"strengths": [], "weaknesses": []}
    counter_arguments = []
    talking_points = ""

    # Split by sections (LLM typically uses numbered headers)
    sections = llm_text.split("\n")
    current_section = ""

    for line in sections:
        line_lower = line.lower().strip()
        if "positioning" in line_lower and ("1." in line_lower or "#" in line_lower or ":" in line_lower):
            current_section = "positioning"
            continue
        elif "strength" in line_lower and ("2." in line_lower or "#" in line_lower or "their strength" in line_lower):
            current_section = "strengths"
            continue
        elif "weakness" in line_lower and ("3." in line_lower or "#" in line_lower or "their weakness" in line_lower):
            current_section = "weaknesses"
            continue
        elif "counter" in line_lower and ("4." in line_lower or "#" in line_lower):
            current_section = "counters"
            continue
        elif "talking" in line_lower and ("5." in line_lower or "#" in line_lower):
            current_section = "talking"
            continue

        stripped = line.strip().lstrip("•-* ")
        if not stripped:
            continue

        if current_section == "positioning":
            positioning += stripped + " "
        elif current_section == "strengths":
            if stripped:
                strengths_weaknesses["strengths"].append(stripped)
        elif current_section == "weaknesses":
            if stripped:
                strengths_weaknesses["weaknesses"].append(stripped)
        elif current_section == "counters":
            if "OBJECTION:" in line and "RESPONSE:" in line:
                parts = line.split("RESPONSE:")
                objection = parts[0].replace("OBJECTION:", "").strip().strip('"').strip("•- ")
                response = parts[1].strip().strip('"')
                counter_arguments.append({"objection": objection, "response": response})
            elif "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    counter_arguments.append({
                        "objection": parts[0].strip().strip('"').strip("•- "),
                        "response": parts[1].strip().strip('"'),
                    })
        elif current_section == "talking":
            talking_points += f"• {stripped}\n"

    return positioning.strip(), strengths_weaknesses, counter_arguments, talking_points.strip()


def parse_news_items(web_results: str) -> list:
    """Parse web search results string into structured news items."""
    news = []
    items = web_results.split("•")
    for item in items:
        item = item.strip()
        if not item:
            continue
        lines = item.split("\n")
        title = lines[0].strip().strip("*") if lines else ""
        summary = lines[1].strip() if len(lines) > 1 else ""
        url = lines[2].strip() if len(lines) > 2 else ""
        if title:
            news.append({"title": title, "summary": summary, "url": url})
    return news


def find_deals_mentioning_competitor(competitor_name: str) -> list:
    """Search CRM notes for deals that mention a competitor."""
    from tools.rag import search_crm_deals
    results = search_crm_deals(competitor_name, n_results=5)
    deals = []
    for doc in results.split("---"):
        if competitor_name.lower() not in doc.lower():
            continue
        # Extract deal info from RAG chunk
        name = ""
        stage = "N/A"
        amount = 0
        for line in doc.split("\n"):
            if "Deal:" in line or "dealname" in line.lower():
                name = line.split(":")[-1].strip()
            elif "Stage:" in line or "dealstage" in line.lower():
                stage = line.split(":")[-1].strip()
            elif "Amount:" in line or "amount" in line.lower():
                try:
                    amount = float(line.split(":")[-1].strip().replace("$", "").replace(",", ""))
                except ValueError:
                    pass
        if name:
            deals.append({"deal_name": name, "stage": stage, "amount": amount})
    return deals


@app.action("roleplay_competitor")
def handle_roleplay_competitor(ack, body, say):
    """Start a roleplay where the buyer brings up the competitor."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    say(
        text=f"Starting competitive roleplay — the buyer will bring up *{competitor}*...\nTry: `/coach roleplay competitive objection {competitor}`",
        channel=channel,
    )


@app.action("draft_competitive_email")
def handle_draft_competitive_email(ack, body, say):
    """Draft an email that positions against the competitor."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    say(
        text=f"Try: `/draft-email [company name]` — the AI will factor in competitive positioning against *{competitor}*.",
        channel=channel,
    )


# --- /battlecard Command (EXPANSION-16) ---

@app.command("/battlecard")
def handle_battlecard(ack, say, command):
    """View competitive battle cards."""
    ack()
    competitor_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/battlecard")

    # If no competitor specified, show the picker
    if not competitor_name:
        from formatters import format_battlecard_picker
        blocks, fallback = format_battlecard_picker()
        say(text=fallback, blocks=blocks, channel=channel_id)
        return

    try:
        # Parse battle cards
        cards = mock_crm.parse_battle_cards()

        # Fuzzy match competitor name
        matched = None
        for name in cards:
            if competitor_name.lower() in name.lower() or name.lower() in competitor_name.lower():
                matched = name
                break

        if not matched:
            say(
                f"No battle card found for '{competitor_name}'.\n"
                f"Available: {', '.join(cards.keys()) if cards else 'None — run `python scripts/generate_test_data.py` first'}",
                channel=channel_id,
            )
            return

        card = cards[matched]

        from formatters import format_battlecard_response
        blocks, fallback = format_battlecard_response(
            competitor_name=matched,
            positioning=card.get("positioning", ""),
            strengths=card.get("strengths", []),
            weaknesses=card.get("weaknesses", []),
            how_to_win=card.get("how_to_win", []),
            landmine_questions=card.get("landmine_questions", []),
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/battlecard", e)


@app.action(re.compile(r"battlecard_select_\d+"))
def handle_battlecard_select_by_index(ack, body, say):
    """Handle competitor selection — handles battlecard_select_0, battlecard_select_1, etc."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    cards = mock_crm.parse_battle_cards()
    card = cards.get(competitor, {})

    if not card:
        say(text=f"No battle card found for {competitor}.", channel=channel)
        return

    from formatters import format_battlecard_response
    blocks, fallback = format_battlecard_response(
        competitor_name=competitor,
        positioning=card.get("positioning", ""),
        strengths=card.get("strengths", []),
        weaknesses=card.get("weaknesses", []),
        how_to_win=card.get("how_to_win", []),
        landmine_questions=card.get("landmine_questions", []),
    )

    say(text=fallback, blocks=blocks, channel=channel)


@app.action("battlecard_select")
def handle_battlecard_select(ack, body, say):
    """Handle competitor selection from the picker (fallback for non-indexed buttons)."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    cards = mock_crm.parse_battle_cards()
    card = cards.get(competitor, {})

    if not card:
        say(text=f"No battle card found for {competitor}.", channel=channel)
        return

    from formatters import format_battlecard_response
    blocks, fallback = format_battlecard_response(
        competitor_name=competitor,
        positioning=card.get("positioning", ""),
        strengths=card.get("strengths", []),
        weaknesses=card.get("weaknesses", []),
        how_to_win=card.get("how_to_win", []),
        landmine_questions=card.get("landmine_questions", []),
    )

    say(text=fallback, blocks=blocks, channel=channel)


@app.action("battlecard_practice")
def handle_battlecard_practice(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Try: `/coach roleplay competitive deal — buyer is evaluating {competitor}`",
    )


@app.action("battlecard_full_analysis")
def handle_battlecard_full_analysis(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/competitor {competitor}` for a full AI analysis with live web intelligence.",
    )


@app.action("battlecard_draft_email")
def handle_battlecard_draft_email(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/draft-email [company]` and mention {competitor} in your request to get a competitive positioning email.",
    )


# --- /alerts Command (EXPANSION-15) ---

@app.command("/alerts")
def handle_alerts(ack, say, command, client):
    """Show current pipeline alerts."""
    ack()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/alerts")

    # Resolve user access
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return

    try:
        # Build alerts list
        alerts = build_pipeline_alerts(owner_id=ctx["filter_owner_id"])

        # Total pipeline value
        open_deals = mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])
        total_value = sum(float(d.get("properties", {}).get("amount", 0) or 0) for d in open_deals)

        from formatters import format_alerts_digest
        blocks, fallback = format_alerts_digest(alerts, total_value)

        # Prepend ownership context banner
        blocks = _ownership_context_block(ctx) + blocks

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/alerts", e)


def build_pipeline_alerts(owner_id=None) -> list:
    """Scan the pipeline and build a list of alerts."""
    from datetime import datetime

    alerts = []

    # Stale deals
    stale = mock_crm.get_stale_deals_for_user(stale_days=14, owner_id=owner_id)
    for deal in stale:
        props = deal.get("properties", {})
        alerts.append({
            "type": "stale",
            "emoji": "⏰",
            "title": f"Stale: {props.get('dealname', 'Unknown')}",
            "detail": "No activity in 14+ days. Time to re-engage.",
            "deal_name": props.get("dealname", ""),
            "amount": float(props.get("amount", 0) or 0),
        })

    # Overdue deals
    overdue = mock_crm.get_overdue_deals_for_user(owner_id=owner_id)
    for deal in overdue:
        props = deal.get("properties", {})
        # Avoid duplicates with stale
        deal_name = props.get("dealname", "")
        if not any(a["deal_name"] == deal_name for a in alerts):
            alerts.append({
                "type": "overdue",
                "emoji": "🚨",
                "title": f"Overdue: {deal_name}",
                "detail": f"Past close date ({props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'}). Update the timeline or close.",
                "deal_name": deal_name,
                "amount": float(props.get("amount", 0) or 0),
            })

    # Deals closing soon (within 3 days)
    open_deals = mock_crm.get_all_open_deals_for_user(owner_id=owner_id)
    for deal in open_deals:
        props = deal.get("properties", {})
        close_date = props.get("closedate", "")
        deal_name = props.get("dealname", "")

        if close_date and deal_name not in [a["deal_name"] for a in alerts]:
            try:
                close = datetime.fromisoformat(close_date.replace("Z", "+00:00")).replace(tzinfo=None)
                days_until = (close - datetime.now()).days
                if 0 < days_until <= 3:
                    alerts.append({
                        "type": "closing_soon",
                        "emoji": "⚡",
                        "title": f"Closing Soon: {deal_name}",
                        "detail": f"Closes in {days_until} day{'s' if days_until != 1 else ''}. Confirm next steps.",
                        "deal_name": deal_name,
                        "amount": float(props.get("amount", 0) or 0),
                    })
            except (ValueError, TypeError):
                pass

    # Competitor mentions in recent notes
    for deal in open_deals:
        props = deal.get("properties", {})
        deal_name = props.get("dealname", "")
        for activity in deal.get("activities", []):
            body = activity.get("body", activity.get("note", "")).lower()
            if any(comp in body for comp in ["competitoralpha", "competitorbeta", "competitorgamma", "competitor"]):
                if deal_name not in [a["deal_name"] for a in alerts if a["type"] == "competitor"]:
                    alerts.append({
                        "type": "competitor",
                        "emoji": "⚔️",
                        "title": f"Competitor Alert: {deal_name}",
                        "detail": "Competitor mentioned in recent activity. Review battle cards.",
                        "deal_name": deal_name,
                        "amount": float(props.get("amount", 0) or 0),
                    })
                break

    # Sort by priority: overdue > closing_soon > stale > competitor
    priority = {"overdue": 0, "closing_soon": 1, "stale": 2, "competitor": 3}
    alerts.sort(key=lambda a: priority.get(a["type"], 99))

    return alerts


@app.action("alert_view_deal")
def handle_alert_view_deal(ack, body, client):
    """View a deal from an alert."""
    ack()
    deal_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/deal {deal_name}` to see the full deal card.",
    )


# --- /forecast Command (EXPANSION-9) ---

# Stage win rate weights for forecast calculation
STAGE_WIN_RATES = {
    "discovery": 0.10,
    "qualification": 0.25,
    "demo_scheduled": 0.40,
    "demo scheduled": 0.40,
    "proposal_sent": 0.60,
    "proposal sent": 0.60,
    "negotiation": 0.80,
    "closedwon": 1.0,
    "closed won": 1.0,
    "closedlost": 0.0,
    "closed lost": 0.0,
}


@app.command("/forecast")
def handle_forecast(ack, say, command, client):
    """AI-powered pipeline forecast with weighted scenarios."""
    ack()
    period_text = command["text"].strip() or "Current Quarter"
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/forecast")

    # Resolve user access
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return

    say(f"📊 Building forecast...", channel=channel_id)

    try:
        # 1. Load all deals (filtered by owner)
        open_deals = mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])
        stale = mock_crm.get_stale_deals_for_user(stale_days=14, owner_id=ctx["filter_owner_id"])
        overdue = mock_crm.get_overdue_deals_for_user(ctx["filter_owner_id"])

        stale_names = {d["properties"]["dealname"] for d in stale}
        overdue_names = {d["properties"]["dealname"] for d in overdue}

        # 2. Calculate stage breakdown with weighted values
        stage_data = {}
        best_case = 0
        committed = 0
        worst_case = 0
        risk_flags = []

        for deal in open_deals:
            props = deal.get("properties", {})
            stage = props.get("dealstage", "unknown").lower()
            amount = float(props.get("amount", 0) or 0)
            deal_name = props.get("dealname", "Unknown")
            win_rate = STAGE_WIN_RATES.get(stage, 0.20)

            weighted = amount * win_rate

            # Accumulate stage data
            if stage not in stage_data:
                stage_data[stage] = {"count": 0, "value": 0, "weighted": 0}
            stage_data[stage]["count"] += 1
            stage_data[stage]["value"] += amount
            stage_data[stage]["weighted"] += weighted

            # Three scenarios
            best_case += amount
            committed += weighted
            if win_rate >= 0.60:
                worst_case += weighted

            # Flag risky deals
            if deal_name in stale_names:
                risk_flags.append({
                    "deal_name": deal_name,
                    "reason": "Stale — no activity in 14+ days",
                    "amount": amount,
                })
            elif deal_name in overdue_names:
                risk_flags.append({
                    "deal_name": deal_name,
                    "reason": f"Past close date ({props.get('closedate', 'N/A')[:10] if props.get('closedate') else 'N/A'})",
                    "amount": amount,
                })

        # Stage breakdown for formatter
        stage_breakdown = []
        for stage_name, data in sorted(stage_data.items(), key=lambda x: x[1]["weighted"], reverse=True):
            stage_breakdown.append({
                "stage": stage_name.replace("_", " ").title(),
                "count": data["count"],
                "value": data["value"],
                "weighted": data["weighted"],
            })

        # 3. Load historical data for LLM context
        win_loss = mock_crm.load_win_loss_analysis()

        historical_context = ""
        if win_loss:
            historical_context += "HISTORICAL WIN/LOSS:\n"
            for row in win_loss[-3:]:
                historical_context += f"  {row.get('quarter', 'N/A')}: Win rate {row.get('win_rate', 'N/A')}%, Avg cycle {row.get('avg_sales_cycle_days', 'N/A')} days, Top loss reason: {row.get('top_loss_reason', 'N/A')}\n"

        # 4. LLM generates narrative insights
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Analyze this sales pipeline forecast and provide 3-4 concise insights.

FORECAST SUMMARY:
- Committed (weighted): ${committed:,.0f}
- Best case (all close): ${best_case:,.0f}
- Worst case (high-confidence only): ${worst_case:,.0f}
- Open deals: {len(open_deals)}
- At-risk deals: {len(risk_flags)}

STAGE BREAKDOWN:
{chr(10).join([f"  {s['stage']}: {s['count']} deals, ${s['value']:,.0f} total, ${s['weighted']:,.0f} weighted" for s in stage_breakdown])}

RISK FLAGS:
{chr(10).join([f"  {r['deal_name']}: {r['reason']} (${r['amount']:,.0f})" for r in risk_flags]) or "  None"}

{historical_context}

Generate 3-4 bullet points of insight. Be specific — reference deal names, dollar amounts, and percentages.
Focus on: concentration risk, pipeline velocity, and actionable recommendations.
Format each insight as a bullet starting with •
Keep it under 500 characters total.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        insights = result["messages"][-1].content

        # 5. Format and send
        from formatters import format_forecast_response
        blocks, fallback = format_forecast_response(
            committed=committed,
            best_case=best_case,
            worst_case=worst_case,
            stage_breakdown=stage_breakdown,
            risk_flags=risk_flags,
            insights=insights,
            period=period_text.title() if period_text != "Current Quarter" else "Current Quarter",
        )

        # Prepend ownership context banner
        blocks = _ownership_context_block(ctx) + blocks

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/forecast", e)


@app.action("forecast_at_risk")
def handle_forecast_at_risk(ack, body, client):
    """Show at-risk deals from forecast."""
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="Use `/pipeline` to see all deals needing attention, or `/deal [name]` to view a specific at-risk deal.",
    )


# --- /win-loss Command (EXPANSION-11) ---

@app.command("/win-loss")
def handle_win_loss(ack, say, command, client):
    """Analyze win/loss patterns and trends."""
    ack()
    filter_text = command["text"].strip().lower()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/win-loss", filter=filter_text or None)

    # Resolve user access
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return

    # Post loading message and capture ts for later update
    loading_msg = client.chat_postMessage(
        channel=channel_id,
        text="⏳ Analyzing win/loss data..."
    )
    loading_ts = loading_msg["ts"]

    try:
        # 1. Load data sources
        win_loss_csv = mock_crm.load_win_loss_analysis()
        all_deals = mock_crm.get_all_deals_for_user(ctx["filter_owner_id"])

        # 2. Separate won and lost deals
        won_deals = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedwon", "closed won")]
        lost_deals = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedlost", "closed lost")]

        # 3. Calculate overall metrics
        total_won = len(won_deals)
        total_lost = len(lost_deals)
        total = total_won + total_lost
        win_rate = (total_won / total * 100) if total > 0 else 0

        won_amounts = [float(d["properties"].get("amount", 0) or 0) for d in won_deals]
        lost_amounts = [float(d["properties"].get("amount", 0) or 0) for d in lost_deals]
        all_amounts = won_amounts + lost_amounts
        avg_deal_size = sum(all_amounts) / len(all_amounts) if all_amounts else 0

        # Avg cycle from CSV if available
        avg_cycle = 0
        if win_loss_csv:
            cycles = [float(row.get("avg_sales_cycle_days", 0)) for row in win_loss_csv if row.get("avg_sales_cycle_days")]
            avg_cycle = sum(cycles) / len(cycles) if cycles else 0

        overall_metrics = {
            "win_rate": win_rate,
            "avg_cycle_days": avg_cycle,
            "avg_deal_size": avg_deal_size,
            "total_won": total_won,
            "total_lost": total_lost,
        }

        # 4. Trend data from CSV
        trend_data = []
        for row in win_loss_csv:
            trend_data.append({
                "period": row.get("quarter", "N/A"),
                "win_rate": row.get("win_rate", "0"),
                "deals_won": row.get("total_won", "0"),
                "deals_lost": row.get("total_lost", "0"),
            })

        # 5. Scan deal activities for patterns
        competitor_mentions = {}
        for deal in all_deals:
            stage = deal.get("properties", {}).get("dealstage", "").lower()
            for activity in deal.get("activities", []):
                body = activity.get("body", activity.get("note", "")).lower()
                for comp in ["competitoralpha", "competitorbeta", "competitorgamma"]:
                    if comp in body.replace(" ", ""):
                        readable = comp.replace("competitor", "Competitor")
                        if readable not in competitor_mentions:
                            competitor_mentions[readable] = {"won": 0, "lost": 0}
                        if "won" in stage:
                            competitor_mentions[readable]["won"] += 1
                        elif "lost" in stage:
                            competitor_mentions[readable]["lost"] += 1

        # 6. LLM generates insights
        deal_summaries = ""
        for d in lost_deals[:5]:
            p = d.get("properties", {})
            activities_text = " | ".join([a.get("body", a.get("note", ""))[:80] for a in d.get("activities", [])[:2]])
            deal_summaries += f"  LOST: {p.get('dealname', '?')} (${float(p.get('amount', 0) or 0):,.0f}) — Notes: {activities_text}\n"
        for d in won_deals[:5]:
            p = d.get("properties", {})
            activities_text = " | ".join([a.get("body", a.get("note", ""))[:80] for a in d.get("activities", [])[:2]])
            deal_summaries += f"  WON: {p.get('dealname', '?')} (${float(p.get('amount', 0) or 0):,.0f}) — Notes: {activities_text}\n"

        comp_summary = ""
        for comp, counts in competitor_mentions.items():
            comp_summary += f"  {comp}: {counts['won']} won, {counts['lost']} lost\n"

        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Analyze these win/loss patterns and provide insights.

OVERALL: {total_won} won, {total_lost} lost, {win_rate:.0f}% win rate, {avg_cycle:.0f} day avg cycle

QUARTERLY TREND:
{chr(10).join([f"  {t['period']}: {t['win_rate']}% ({t['deals_won']}W/{t['deals_lost']}L)" for t in trend_data]) or "  No trend data"}

COMPETITOR CORRELATION:
{comp_summary or "  No competitor mentions found"}

DEAL DETAILS:
{deal_summaries or "  No closed deals"}

CRITICAL: Respond in EXACTLY this format. Do NOT use markdown headers (#), horizontal rules (---), or numbered lists. Do NOT write a full report. Just fill in the fields below:

PATTERNS:
• [First specific pattern — reference deal names, percentages, competitor names from the data above]
• [Second pattern]
• [Third pattern]
• [Fourth pattern — if applicable]

RECOMMENDATION_1: [One actionable recommendation in a single sentence]
RECOMMENDATION_2: [Another recommendation in a single sentence]
RECOMMENDATION_3: [Another recommendation in a single sentence]

Rules:
- Each bullet point must be ONE sentence, max 100 characters
- Do NOT write paragraphs, headers, or sub-sections
- Do NOT include a pipeline summary — that's already shown separately
- Reference specific data: deal names, win rates, competitor names
- Total response must be under 800 characters""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 7. Parse — handle both structured and freeform LLM responses
        patterns = ""
        recommendations = []

        # First pass: try structured parsing
        for line in llm_response.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("PATTERNS:"):
                val = line.split(":", 1)[1].strip()
                if val:
                    patterns = val
            elif line.startswith("•") or line.startswith("- •"):
                cleaned = line.lstrip("- ").strip()
                patterns += "\n" + cleaned
            elif line.upper().startswith("RECOMMENDATION_") or line.upper().startswith("RECOMMENDATION "):
                val = line.split(":", 1)[1].strip() if ":" in line else line
                if val:
                    recommendations.append(val)

        # Fallback: if structured parsing failed, clean up the raw response
        if not patterns:
            # Strip markdown headers, horizontal rules, and excessive formatting
            clean_lines = []
            for line in llm_response.split("\n"):
                line = line.strip()
                # Skip markdown headers, horizontal rules, empty lines
                if line.startswith("#") or line.startswith("---") or line.startswith("==="):
                    continue
                if not line:
                    continue
                # Convert markdown bold to Slack bold
                line = line.replace("**", "*")
                # Convert numbered lists to bullets
                if len(line) > 2 and line[0].isdigit() and line[1] in (".", ")"):
                    line = "• " + line[2:].strip()
                elif len(line) > 3 and line[0].isdigit() and line[1].isdigit() and line[2] in (".", ")"):
                    line = "• " + line[3:].strip()
                # Add as bullet if not already
                if not line.startswith("•"):
                    line = "• " + line
                clean_lines.append(line)

            # Take first 6 meaningful lines max
            patterns = "\n".join(clean_lines[:6])

            # Also try to extract recommendations from remaining lines
            if not recommendations and len(clean_lines) > 6:
                recommendations = [l.lstrip("• ").strip() for l in clean_lines[6:9]]

        # Truncate patterns to fit Slack's 3000 char section limit
        if len(patterns) > 2500:
            patterns = patterns[:2500] + "\n_...truncated_"

        filter_label = filter_text.upper() if filter_text else "All Deals"

        # 8. Format and send
        from formatters import format_win_loss_response
        blocks, fallback = format_win_loss_response(
            overall_metrics=overall_metrics,
            trend_data=trend_data,
            patterns=patterns,
            recommendations=recommendations,
            filter_label=filter_label,
        )

        # Prepend ownership context banner
        blocks = _ownership_context_block(ctx) + blocks

        # Update loading message with final result
        client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            text=f"⚠️ Something went wrong with `/win-loss`. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


@app.action("win_loss_lost_deals")
def handle_win_loss_lost(ack, body, say):
    """Show lost deals inline."""
    ack()
    channel = body["channel"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    lost = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedlost", "closed lost")]

    from formatters.helpers import format_currency
    if lost:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "❌ Lost Deals", "emoji": True}
            },
            {"type": "divider"},
        ]
        for i, d in enumerate(lost):
            p = d.get("properties", {})
            deal_name = p.get("dealname", "Unknown")
            deal_id = d.get("id", "")
            amount = float(p.get("amount", 0) or 0)

            # Get loss reason from activities
            loss_reason = ""
            for a in d.get("activities", []):
                note = a.get("body", a.get("note", ""))
                if any(word in note.lower() for word in ["lost", "competitor", "went with", "chose", "declined"]):
                    loss_reason = note[:120]
                    break

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{deal_name}*\n{format_currency(amount)}" + (f"\n_{loss_reason}_" if loss_reason else "")
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
                    "action_id": f"view_deal_{i}",
                    "value": deal_id or deal_name,
                }
            })

        say(text=f"Lost Deals: {len(lost)} deals", blocks=blocks, channel=channel)
    else:
        say(text="No lost deals found in current data.", channel=channel)


@app.action("win_loss_won_deals")
def handle_win_loss_won(ack, body, say):
    """Show won deals inline."""
    ack()
    channel = body["channel"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    won = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedwon", "closed won")]

    from formatters.helpers import format_currency
    if won:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "✅ Won Deals", "emoji": True}
            },
            {"type": "divider"},
        ]
        for i, d in enumerate(won):
            p = d.get("properties", {})
            deal_name = p.get("dealname", "Unknown")
            deal_id = d.get("id", "")
            amount = float(p.get("amount", 0) or 0)
            stage_label = p.get("dealstage_label", "Closed Won")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{deal_name}*\n{format_currency(amount)} • {stage_label}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
                    "action_id": f"view_deal_{i}",
                    "value": deal_id or deal_name,
                }
            })

        say(text=f"Won Deals: {len(won)} deals", blocks=blocks, channel=channel)
    else:
        say(text="No won deals found in current data.", channel=channel)


@app.action("win_loss_competitor")
def handle_win_loss_competitor(ack, body, say):
    """Show competitor impact on win/loss."""
    ack()
    channel = body["channel"]["id"]

    all_deals = mock_crm.load_mock_crm()["deals"]
    competitor_mentions = {}

    for deal in all_deals:
        stage = deal.get("properties", {}).get("dealstage", "").lower()
        deal_name = deal.get("properties", {}).get("dealname", "Unknown")
        for activity in deal.get("activities", []):
            body_text = activity.get("body", activity.get("note", "")).lower()
            for comp in ["competitoralpha", "competitorbeta", "competitorgamma"]:
                if comp in body_text.replace(" ", ""):
                    readable = comp.replace("competitor", "Competitor ")
                    if readable not in competitor_mentions:
                        competitor_mentions[readable] = {"deals": [], "won": 0, "lost": 0}
                    if deal_name not in [d["name"] for d in competitor_mentions[readable]["deals"]]:
                        competitor_mentions[readable]["deals"].append({"name": deal_name, "stage": stage})
                    if "won" in stage:
                        competitor_mentions[readable]["won"] += 1
                    elif "lost" in stage:
                        competitor_mentions[readable]["lost"] += 1

    if competitor_mentions:
        from formatters.helpers import timestamp
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "⚔️ Competitor Impact on Deals", "emoji": True}
            },
            {"type": "divider"},
        ]

        for i, (comp, data) in enumerate(competitor_mentions.items()):
            deals_text = "\n".join([f"  • {d['name']} ({d['stage']})" for d in data["deals"][:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{comp}*\n"
                        f"Mentioned in {len(data['deals'])} deals (Won: {data['won']} | Lost: {data['lost']})\n"
                        f"{deals_text}"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Battle Card", "emoji": True},
                    "action_id": f"battlecard_select_{i}",
                    "value": comp.replace(" ", ""),
                }
            })

        say(text="Competitor Impact on Deals", blocks=blocks, channel=channel)
    else:
        say(text="No competitor mentions found in deal activities.", channel=channel)


# --- /persona Command (EXPANSION-14) ---

@app.command("/persona")
def handle_persona(ack, say, command):
    """Generate a buyer persona for a company contact."""
    ack()
    text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/persona", target=text or None)

    if not text:
        say(
            "Generate a buyer persona: `/persona [company] [role — optional]`\n"
            "Examples:\n• `/persona NovaTech`\n"
            "• `/persona Horizon Education CFO`\n"
            "• `/persona Apex VP of Engineering`",
            channel=channel_id,
        )
        return

    # Parse company and optional role
    parts = text.split(maxsplit=1)
    company_query = parts[0]
    target_role = parts[1] if len(parts) > 1 else None

    say(f"👤 Building buyer persona for *{text}*...", channel=channel_id)

    try:
        # 1. Find company
        company = mock_crm.search_company(company_query)
        if not company:
            say(f"Could not find company matching '{company_query}'.", channel=channel_id)
            return

        company_name = company.get("properties", {}).get("name", company_query)
        company_id = company.get("id", "")
        company_props = company.get("properties", {})

        # 2. Find matching contact (if role specified)
        contacts = mock_crm.get_contacts_for_company(company_id)
        matched_contact = None

        if target_role and contacts:
            for c in contacts:
                c_title = c.get("properties", {}).get("jobtitle", "").lower()
                if target_role.lower() in c_title:
                    matched_contact = c
                    break

        if not matched_contact and contacts:
            matched_contact = contacts[0]

        if matched_contact:
            c_props = matched_contact.get("properties", {})
            persona_name = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')}".strip()
            persona_title = c_props.get("jobtitle", target_role or "Decision Maker")
        else:
            persona_name = f"Typical {target_role or 'Decision Maker'}"
            persona_title = target_role or "Decision Maker"

        # 3. Load context
        deals = mock_crm.get_deals_for_company(company_id)
        deal_context = ""
        for d in deals[:3]:
            dp = d.get("properties", {})
            deal_context += f"Deal: {dp.get('dealname', '?')}, Stage: {dp.get('dealstage', '?')}, ${float(dp.get('amount', 0) or 0):,.0f}\n"
            for a in d.get("activities", [])[:2]:
                deal_context += f"  Note: {a.get('body', a.get('note', ''))[:100]}\n"

        from tools.rag import search_playbooks
        icp_context = search_playbooks(f"ideal customer profile {company_props.get('industry', '')} {persona_title} buyer persona pain points", n_results=5)
        methodology_context = search_playbooks(f"sales methodology {persona_title} stakeholder discovery", n_results=3)

        # 4. LLM generates persona
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Generate a detailed buyer persona for selling to this contact.

CONTACT: {persona_name} — {persona_title}
COMPANY: {company_name}
INDUSTRY: {company_props.get('industry', 'Technology')}
SIZE: {company_props.get('numberofemployees', 'Unknown')} employees
LOCATION: {company_props.get('city', '')}, {company_props.get('state', '')}

DEAL HISTORY:
{deal_context or 'No deals yet'}

ICP PLAYBOOK:
{icp_context}

SALES METHODOLOGY:
{methodology_context}

Generate EXACTLY this format:

BACKGROUND: [2-3 sentences about what this persona cares about, their daily challenges, and what success looks like for them]

PAIN_POINT_1: [Specific pain point relevant to their role and industry]
PAIN_POINT_2: [Another pain point]
PAIN_POINT_3: [Another pain point]

PRIORITY_1: [What they're prioritizing right now]
PRIORITY_2: [Another priority]
PRIORITY_3: [Another priority]

DECISION_STYLE: [How they make decisions — data-driven, consensus-builder, gut-feel, risk-averse, etc. 1-2 sentences]
COMMUNICATION_PREF: [How they prefer to communicate — formal emails, quick Slack, detailed presentations, executive summaries. 1-2 sentences]

DO_1: [Messaging approach that will resonate]
DO_2: [Another do]
DO_3: [Another do]

DONT_1: [Messaging mistake to avoid]
DONT_2: [Another don't]
DONT_3: [Another don't]

VALUE_PROP_1: [Specific value prop that will resonate with this persona]
VALUE_PROP_2: [Another value prop]

STARTER_1: [Conversation opening question that shows you understand their world]
STARTER_2: [Another starter]
STARTER_3: [Another starter]

Be specific to {company_name} and {persona_title}'s role. Use deal context if available. Don't be generic.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 5. Parse
        persona_profile = {"background": "", "pain_points": [], "priorities": [], "decision_style": "", "communication_pref": ""}
        messaging_guide = {"do": [], "dont": [], "value_props": []}
        conversation_starters = []

        for line in llm_response.split("\n"):
            line = line.strip()
            if line.upper().startswith("BACKGROUND:"):
                persona_profile["background"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("PAIN_POINT_"):
                persona_profile["pain_points"].append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("PRIORITY_"):
                persona_profile["priorities"].append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("DECISION_STYLE:"):
                persona_profile["decision_style"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("COMMUNICATION_PREF:"):
                persona_profile["communication_pref"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("DO_"):
                messaging_guide["do"].append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("DONT_"):
                messaging_guide["dont"].append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("VALUE_PROP_"):
                messaging_guide["value_props"].append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("STARTER_"):
                conversation_starters.append(line.split(":", 1)[1].strip() if ":" in line else line)

        if not persona_profile["background"]:
            persona_profile["background"] = llm_response[:500]

        # 6. Format and send
        from formatters import format_persona_response
        blocks, fallback = format_persona_response(
            company_name=company_name,
            persona_name=persona_name,
            persona_title=persona_title,
            persona_profile=persona_profile,
            messaging_guide=messaging_guide,
            conversation_starters=conversation_starters,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/persona", e)


@app.action("draft_email_from_persona")
def handle_draft_from_persona(ack, body, client):
    """Draft an email tailored to this persona."""
    ack()
    user_id = body["user"]["id"]
    value = body["actions"][0]["value"]
    company = value.split("||")[0] if "||" in value else value
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/draft-email {company}` to draft an email tailored to this contact.",
    )


@app.action("roleplay_from_persona")
def handle_roleplay_from_persona(ack, body, client):
    """Start a roleplay with this persona."""
    ack()
    user_id = body["user"]["id"]
    value = body["actions"][0]["value"]
    company, title = value.split("||", 1) if "||" in value else (value, "decision maker")
    client.chat_postMessage(
        channel=user_id,
        text=f"Try: `/coach roleplay discovery call with {title} at {company}`",
    )


# --- /handoff Command (EXPANSION-10) ---

@app.command("/handoff")
def handle_handoff(ack, say, command):
    """Generate a comprehensive deal handoff brief."""
    ack()
    query = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/handoff", deal=query or None)

    if not query:
        say(
            "Specify a deal or company: `/handoff [company or deal name]`\n"
            "Examples:\n• `/handoff NovaTech`\n• `/handoff Horizon Education`",
            channel=channel_id,
        )
        return

    say(f"📋 Building handoff brief for *{query}*...", channel=channel_id)

    try:
        # 1. Find the deal and company
        deal = mock_crm.search_deal(query)
        company = mock_crm.search_company(query)

        if not deal and not company:
            say(f"Could not find a deal or company matching '{query}'. Try the exact name.", channel=channel_id)
            return

        # If we found company but not deal, get the first deal for that company
        if company and not deal:
            company_id = company.get("id", "")
            company_deals = mock_crm.get_deals_for_company(company_id)
            if company_deals:
                deal = company_deals[0]  # Use the first/primary deal

        if not deal:
            say(f"Found company '{query}' but no associated deals.", channel=channel_id)
            return

        props = deal.get("properties", {})
        deal_name = props.get("dealname", "Unknown")
        company_id = deal.get("associations", {}).get("company", "")

        if not company:
            company = mock_crm.get_company_by_id(company_id)

        company_name = company.get("properties", {}).get("name", "Unknown") if company else "Unknown"

        # 2. Load ALL data for this deal
        # Contacts
        contact_id = deal.get("associations", {}).get("contact", "")
        deal_contact = mock_crm.get_contact_by_id(contact_id) if contact_id else None
        company_contacts = mock_crm.get_contacts_for_company(company_id) if company_id else []

        key_contacts = []
        if deal_contact:
            c_props = deal_contact.get("properties", {})
            key_contacts.append({
                "name": f"{c_props.get('firstname', '')} {c_props.get('lastname', '')}".strip(),
                "title": c_props.get("jobtitle", ""),
                "email": c_props.get("email", ""),
                "role_in_deal": "Primary deal contact",
            })
        for cc in company_contacts:
            cc_props = cc.get("properties", {})
            cc_name = f"{cc_props.get('firstname', '')} {cc_props.get('lastname', '')}".strip()
            if not any(kc["name"] == cc_name for kc in key_contacts):
                key_contacts.append({
                    "name": cc_name,
                    "title": cc_props.get("jobtitle", ""),
                    "email": cc_props.get("email", ""),
                    "role_in_deal": "Company stakeholder",
                })

        # Activity notes
        activities = deal.get("activities", [])
        activity_text = ""
        for a in activities:
            activity_text += f"[{a.get('timestamp', 'N/A')[:10] if a.get('timestamp') else 'N/A'}] {a.get('type', 'NOTE')}: {a.get('body', a.get('note', ''))}\n\n"

        # Call transcripts
        transcript = mock_crm.load_call_transcript(company_name)

        # Email threads
        email_thread = mock_crm.load_email_thread(company_name)

        # Meeting notes
        meeting_notes = mock_crm.load_meeting_notes(company_name)

        # RAG search for additional context
        from tools.rag import search_playbooks
        rag_context = search_playbooks(f"{company_name} {deal_name}", n_results=5)

        # 3. LLM synthesizes the handoff brief
        full_context = f"""DEAL: {deal_name}
COMPANY: {company_name}
STAGE: {props.get('dealstage', 'unknown')}
AMOUNT: ${float(props.get('amount', 0) or 0):,.0f}
CLOSE DATE: {props.get('closedate', 'N/A')}

ACTIVITY NOTES:
{activity_text or 'No activity notes.'}

CALL TRANSCRIPTS:
{transcript[:2000] if transcript else 'No transcripts available.'}

EMAIL THREADS:
{json.dumps(email_thread, indent=2)[:2000] if email_thread else 'No email threads.'}

MEETING NOTES:
{meeting_notes[:2000] if meeting_notes else 'No meeting notes.'}

RAG CONTEXT:
{rag_context[:1000]}"""

        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Generate a deal handoff brief for a new rep taking over this deal.

{full_context}

Respond in EXACTLY this format:

DEAL_STORY: [3-5 sentences narrating the deal from start to current state. Include key milestones, decisions, and tone of the relationship. Write it like you're briefing a colleague over coffee.]

RISK_1: [A specific risk factor with context]
RISK_2: [Another risk]
RISK_3: [Another risk — if applicable]

NEXT_STEP_1: [Specific, actionable next step with timing]
NEXT_STEP_2: [Another next step]
NEXT_STEP_3: [Another next step]

COMPETITORS: [Comma-separated list of competitors mentioned, or "None"]

CONTACT_ROLES: [For each contact, describe their role in the deal: decision maker, champion, blocker, technical evaluator, etc. Format: Name=Role, Name=Role]

Be specific — use names, dates, dollar amounts from the data.""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 4. Parse structured response
        conversation_history = ""
        risk_factors = []
        next_steps = []
        competitor_mentions = []

        for line in llm_response.split("\n"):
            line = line.strip()
            if line.upper().startswith("DEAL_STORY:"):
                conversation_history = line.split(":", 1)[1].strip()
            elif line.upper().startswith("RISK_"):
                risk_factors.append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("NEXT_STEP_"):
                next_steps.append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("COMPETITORS:"):
                comps = line.split(":", 1)[1].strip()
                if comps.lower() != "none":
                    competitor_mentions = [c.strip() for c in comps.split(",") if c.strip()]
            elif line.upper().startswith("CONTACT_ROLES:"):
                # Update contact roles from LLM analysis
                roles_str = line.split(":", 1)[1].strip()
                for role_pair in roles_str.split(","):
                    if "=" in role_pair:
                        name_part, role_part = role_pair.split("=", 1)
                        name_part = name_part.strip()
                        role_part = role_part.strip()
                        for kc in key_contacts:
                            if name_part.lower() in kc["name"].lower():
                                kc["role_in_deal"] = role_part

        if not conversation_history:
            conversation_history = llm_response[:2500]

        # 5. Format and send
        deal_summary = {
            "stage": props.get("dealstage", "Unknown").replace("_", " ").title(),
            "amount": float(props.get("amount", 0) or 0),
            "close_date": props.get("closedate", "N/A")[:10] if props.get("closedate") else "N/A",
            "owner": props.get("hubspot_owner_id", "N/A"),
            "created": props.get("createdate", "N/A")[:10] if props.get("createdate") else "N/A",
        }

        deal_id = deal.get("id", "")

        # Cache handoff data for progressive disclosure (expand button)
        cache_key = f"handoff_{user_id}_{deal_id or deal_name}"
        handoff_cache[cache_key] = {
            "deal_name": deal_name,
            "company_name": company_name,
            "deal_summary": deal_summary,
            "key_contacts": key_contacts,
            "conversation_history": conversation_history,
            "risk_factors": risk_factors,
            "next_steps": next_steps,
            "competitor_mentions": competitor_mentions,
            "deal_id": deal_id,
        }

        # Format with compact summary (progressive disclosure)
        blocks, fallback = format_handoff_summary(
            deal_name=deal_name,
            company_name=company_name,
            deal_summary=deal_summary,
            key_contacts=key_contacts,
            conversation_history=conversation_history,
            risk_factors=risk_factors,
            next_steps=next_steps,
            competitor_mentions=competitor_mentions,
            deal_id=deal_id,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/handoff", e)


@app.action(re.compile(r"view_deal_\d+"))
def handle_view_deal_by_index(ack, body, say):
    """View a deal card inline — handles view_deal_0, view_deal_1, etc."""
    ack()
    value = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    # Try to find by ID first (unique), then fall back to name search (backward compat)
    deal = mock_crm.get_deal_by_id(value)
    if not deal:
        deal = mock_crm.search_deal(value)

    if not deal:
        say(text=f"Could not find deal matching '{value}'.", channel=channel)
        return

    props = deal.get("properties", {})
    deal_name = props.get("dealname", "Unknown")
    company_id = deal.get("associations", {}).get("company", "")
    company = mock_crm.get_company_by_id(company_id) if company_id else None
    company_name = company.get("properties", {}).get("name", "Unknown") if company else "Unknown"

    # Get contact
    contact_id = deal.get("associations", {}).get("contact", "")
    contact = mock_crm.get_contact_by_id(contact_id) if contact_id else None

    from formatters.helpers import format_currency, timestamp

    amount = float(props.get("amount", 0) or 0)
    stage = props.get("dealstage", "Unknown").replace("_", " ").title()

    # Contact info
    contact_text = "No contact on file"
    if contact:
        c_props = contact.get("properties", {})
        contact_text = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')} — {c_props.get('jobtitle', 'N/A')} ({c_props.get('email', '')})"

    # Recent activities
    activities = deal.get("activities", [])
    activity_text = ""
    for a in activities[:3]:
        note = a.get("body", a.get("note", ""))[:120]
        date = a.get("timestamp", "")[:10]
        activity_text += f"• [{date}] {note}\n"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 {deal_name}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{props.get('closedate', 'N/A')[:10]}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👤 Contact:*\n{contact_text}"}
        },
    ]

    if activity_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📝 Recent Activity:*\n{activity_text}"}
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • Quick View • {timestamp()}"}
        ]
    })

    say(text=f"Deal: {deal_name}", blocks=blocks, channel=channel)


@app.action("view_deal_from_handoff")
def handle_view_deal_from_handoff(ack, body, client):
    """View a deal card inline from any button that references a deal."""
    ack()
    value = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Try to find by ID first (unique), then fall back to name search (backward compat)
    deal = mock_crm.get_deal_by_id(value)
    if not deal:
        deal = mock_crm.search_deal(value)

    if not deal:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"⚠️ Could not find deal matching '{value}'."
        )
        return

    props = deal.get("properties", {})
    deal_name = props.get("dealname", "Unknown")
    company_id = deal.get("associations", {}).get("company", "")
    company = mock_crm.get_company_by_id(company_id) if company_id else None
    company_name = company.get("properties", {}).get("name", "Unknown") if company else "Unknown"

    # Get contact
    contact_id = deal.get("associations", {}).get("contact", "")
    contact = mock_crm.get_contact_by_id(contact_id) if contact_id else None

    # Build a quick deal summary using Block Kit
    from formatters.helpers import format_currency, timestamp

    amount = float(props.get("amount", 0) or 0)
    stage = props.get("dealstage", "Unknown").replace("_", " ").title()

    # Contact info
    contact_text = "No contact on file"
    if contact:
        c_props = contact.get("properties", {})
        contact_text = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')} — {c_props.get('jobtitle', 'N/A')} ({c_props.get('email', '')})"

    # Recent activities
    activities = deal.get("activities", [])
    activity_text = ""
    for a in activities[:3]:
        note = a.get("body", a.get("note", ""))[:120]
        date = a.get("timestamp", "")[:10]
        activity_text += f"• [{date}] {note}\n"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 {deal_name}", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{props.get('closedate', 'N/A')[:10]}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👤 Contact:*\n{contact_text}"}
        },
    ]

    if activity_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📝 Recent Activity:*\n{activity_text}"}
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • Quick View • {timestamp()}"}
        ]
    })

    # Post deal card as threaded reply
    client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"Deal: {props.get('dealname', deal_name)}",
        blocks=blocks,
    )


@app.action("draft_handoff_email")
def handle_draft_handoff_email(ack, body, client):
    """Draft an introduction email for the new rep taking over."""
    ack()
    value = body["actions"][0]["value"]
    deal_name, company_name = value.split("||", 1) if "||" in value else (value, "")
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts,
        text=f"✉️ Drafting handoff introduction email..."
    )

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Draft a professional introduction email from a new sales rep taking over the deal "{deal_name}" at {company_name}.

The email should:
- Introduce themselves as the new point of contact
- Acknowledge the existing relationship
- Reference where the deal stands
- Propose a brief sync call to get aligned
- Be warm but professional

Keep it under 150 words. No subject line needed — just the body.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel,
        "thread_ts": None,
    })

    # Update loading message with email draft
    client.chat_update(
        channel=channel,
        ts=loading_msg["ts"],
        text=result["messages"][-1].content,
    )


# --- /email-sequence Command (EXPANSION-13) ---

@app.command("/email-sequence")
def handle_email_sequence(ack, say, command):
    """Generate a multi-touch email nurture sequence."""
    ack()
    text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/email-sequence", company=text.split()[0] if text else None)

    if not text:
        say(
            "Generate an email sequence: `/email-sequence [company] [type]`\n"
            "Types: `post-demo`, `cold-outreach`, `re-engagement`, `proposal-followup`, `win-back`\n"
            "Examples:\n• `/email-sequence NovaTech post-demo`\n"
            "• `/email-sequence Horizon cold-outreach`\n"
            "• `/email-sequence Greenfield re-engagement`",
            channel=channel_id,
        )
        return

    # Parse company and sequence type
    parts = text.split(maxsplit=1)
    company_query = parts[0]
    sequence_type = parts[1] if len(parts) > 1 else "post-demo"

    say(f"📧 Building email sequence for *{company_query}*...", channel=channel_id)

    try:
        # 1. Find company and deal
        company = mock_crm.search_company(company_query)
        if not company:
            say(f"Could not find company matching '{company_query}'.", channel=channel_id)
            return

        company_name = company.get("properties", {}).get("name", company_query)
        company_id = company.get("id", "")
        deals = mock_crm.get_deals_for_company(company_id)
        contacts = mock_crm.get_contacts_for_company(company_id)

        # Get primary contact
        contact_name = "Contact"
        contact_email = ""
        if contacts:
            c_props = contacts[0].get("properties", {})
            contact_name = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')}".strip()
            contact_email = c_props.get("email", "")

        # Deal context
        deal_context = ""
        if deals:
            deal = deals[0]
            d_props = deal.get("properties", {})
            deal_context = f"Deal: {d_props.get('dealname', 'N/A')}, Stage: {d_props.get('dealstage', 'N/A')}, Value: ${float(d_props.get('amount', 0) or 0):,.0f}"
            # Include recent activity
            for a in deal.get("activities", [])[:3]:
                deal_context += f"\nActivity: {a.get('body', a.get('note', ''))[:100]}"

        # 2. Load email playbook via RAG
        from tools.rag import search_playbooks
        template_context = search_playbooks(f"email template {sequence_type} sequence follow-up", n_results=5)
        case_study_context = search_playbooks(f"case study ROI results {company.get('properties', {}).get('industry', '')}", n_results=3)

        # 3. LLM generates the sequence
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Generate a {sequence_type} email sequence for {company_name}.

CONTACT: {contact_name} ({contact_email})
COMPANY: {company_name} — {company.get('properties', {}).get('industry', 'Technology')}
{deal_context}

EMAIL TEMPLATES REFERENCE:
{template_context}

CASE STUDIES:
{case_study_context}

Generate EXACTLY 4 emails in this format. Each email should take a different angle and escalate in urgency.

EMAIL_1_DAY: Day 1
EMAIL_1_ANGLE: [Brief description of the angle, e.g., "Value recap and social proof"]
EMAIL_1_SUBJECT: [Subject line]
EMAIL_1_BODY: [Full email body, 80-120 words. Professional, personalized, clear CTA.]

EMAIL_2_DAY: Day 3
EMAIL_2_ANGLE: [Different angle]
EMAIL_2_SUBJECT: [Subject line]
EMAIL_2_BODY: [Full email body]

EMAIL_3_DAY: Day 7
EMAIL_3_ANGLE: [Different angle]
EMAIL_3_SUBJECT: [Subject line]
EMAIL_3_BODY: [Full email body]

EMAIL_4_DAY: Day 14
EMAIL_4_ANGLE: [Final angle — more direct/urgent]
EMAIL_4_SUBJECT: [Subject line]
EMAIL_4_BODY: [Full email body]

Requirements:
- Each email must have a different angle (don't repeat the same pitch)
- Reference specific deal details and the contact by name
- Include a clear CTA in each email
- Escalate urgency progressively
- Keep each email 80-120 words
- Do NOT use generic placeholder text""")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
        })

        llm_response = result["messages"][-1].content

        # 4. Parse the emails
        emails = []
        current_email = {}

        for line in llm_response.split("\n"):
            line = line.strip()
            for i in range(1, 6):
                prefix = f"EMAIL_{i}_"
                if line.upper().startswith(f"{prefix}DAY:"):
                    if current_email and current_email.get("body"):
                        emails.append(current_email)
                    current_email = {"day": line.split(":", 1)[1].strip()}
                elif line.upper().startswith(f"{prefix}ANGLE:"):
                    current_email["angle"] = line.split(":", 1)[1].strip()
                elif line.upper().startswith(f"{prefix}SUBJECT:"):
                    current_email["subject"] = line.split(":", 1)[1].strip()
                elif line.upper().startswith(f"{prefix}BODY:"):
                    current_email["body"] = line.split(":", 1)[1].strip()

        if current_email and current_email.get("body"):
            emails.append(current_email)

        if not emails:
            # Fallback: just show the raw LLM output
            say(text=llm_response, channel=channel_id)
            return

        # 5. Format and send
        from formatters import format_email_sequence_response
        blocks, fallback = format_email_sequence_response(
            company_name=company_name,
            sequence_type=sequence_type,
            emails=emails,
            contact_name=contact_name,
            contact_email=contact_email,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/email-sequence", e)


@app.action("regenerate_email_sequence")
def handle_regenerate_sequence(ack, body, client):
    """Regenerate the entire email sequence."""
    ack()
    user_id = body["user"]["id"]
    value = body["actions"][0]["value"]
    company, seq_type = value.split("||", 1) if "||" in value else (value, "post-demo")
    client.chat_postMessage(
        channel=user_id,
        text=f"Run `/email-sequence {company} {seq_type}` to regenerate the sequence.",
    )


# Dynamic action handlers for copy/refine buttons
@app.action(re.compile(r"copy_sequence_email_\d+"))
def handle_copy_sequence_email(ack, body, client):
    """Copy a specific email from the sequence."""
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="📋 To copy: click the email text above and use Ctrl+C. Slack doesn't support programmatic clipboard access.",
    )


@app.action(re.compile(r"refine_sequence_email_\d+"))
def handle_refine_sequence_email(ack, body, client):
    """Refine a specific email from the sequence."""
    ack()
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text="✏️ To refine an email, use `/draft-email [company]` with specific instructions about what to change.",
    )


# --- /coach-live Command (EXPANSION-12) ---

# In-memory live coaching state
active_live_coaching = {}


@app.command("/coach-live")
def handle_coach_live(ack, say, command):
    """Start a real-time live call coaching session."""
    ack()
    text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    # Parse early for logging
    parts = text.split(maxsplit=1) if text else []
    company_name = parts[0] if parts else None
    call_type = parts[1] if len(parts) > 1 else "general"
    log_engagement(user_id, "command", command="/coach-live", company=company_name, call_type=call_type)

    if not text:
        say(
            "Start live coaching: `/coach-live [company] [call type]`\n"
            "Examples:\n• `/coach-live NovaTech discovery`\n"
            "• `/coach-live Apex negotiation`\n"
            "• `/coach-live Horizon pricing discussion`",
            channel=channel_id,
        )
        return

    try:
        # Load company context for coaching (company_name and call_type already parsed above)
        company = mock_crm.search_company(company_name)
        company_full_name = company.get("properties", {}).get("name", company_name) if company else company_name

        from tools.rag import search_playbooks
        methodology_context = search_playbooks(f"{call_type} call methodology techniques", n_results=5)

        # Post the start message and capture thread_ts
        from formatters import format_coach_live_start
        blocks, fallback = format_coach_live_start(company_full_name, call_type.title())

        result = say(text=fallback, blocks=blocks, channel=channel_id)
        thread_ts = result["ts"]

        # Store session state
        active_live_coaching[thread_ts] = {
            "company": company_full_name,
            "call_type": call_type,
            "user_id": user_id,
            "channel_id": channel_id,
            "turns": 0,
            "history": [],
            "methodology_context": methodology_context,
        }

    except Exception as e:
        handle_error(say, channel_id, "/coach-live", e)


@app.action("end_live_coaching")
def handle_end_live_coaching(ack, body, client):
    """End a live coaching session via button."""
    ack()
    channel = body["channel"]["id"]
    # Find the session by checking message_ts
    message_ts = body.get("message", {}).get("ts")
    if message_ts and message_ts in active_live_coaching:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text="Type `done` in this thread to get your session summary.",
        )


# --- /demo-flow Command (EXPANSION-18) ---

@app.command("/demo-flow")
def handle_demo_flow(ack, say, command):
    """Start a guided demo walkthrough."""
    ack()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    log_engagement(user_id, "command", command="/demo-flow")

    try:
        from formatters import format_demo_welcome
        blocks, fallback = format_demo_welcome()
        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/demo-flow", e)


@app.action("demo_flow_next")
def handle_demo_flow_next(ack, body, say, client):
    """Execute the next demo step."""
    ack()
    step_index = int(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    from formatters.demo_flow import DEMO_STEPS, format_demo_step_intro, format_demo_step_nav, format_demo_complete

    if step_index >= len(DEMO_STEPS):
        # Demo complete
        blocks, fallback = format_demo_complete()
        say(text=fallback, blocks=blocks, channel=channel)
        return

    step = DEMO_STEPS[step_index]

    # Post the step intro
    intro_blocks, intro_fallback = format_demo_step_intro(step_index)
    say(text=intro_fallback, blocks=intro_blocks, channel=channel)

    # Execute the actual command
    # Parse the command and text from the step definition
    parts = step["command"].split(maxsplit=1)
    cmd = parts[0].lstrip("/")
    cmd_text = parts[1] if len(parts) > 1 else ""

    # Create a fake command dict to pass to the handler
    fake_command = {
        "text": cmd_text,
        "channel_id": channel,
        "user_id": user_id,
    }

    # Route to the appropriate handler
    try:
        if cmd == "pipeline":
            handle_pipeline(lambda: None, say, fake_command)
        elif cmd == "deal":
            handle_deal(lambda: None, say, fake_command)
        elif cmd == "research":
            handle_research(lambda: None, say, fake_command)
        elif cmd == "battlecard":
            handle_battlecard(lambda: None, say, fake_command)
        elif cmd == "objection":
            handle_objection(lambda: None, say, fake_command)
        elif cmd == "ask":
            handle_ask(lambda: None, say, fake_command)
        elif cmd == "forecast":
            handle_forecast(lambda: None, say, fake_command)
        elif cmd == "persona":
            handle_persona(lambda: None, say, fake_command)
        elif cmd == "email-sequence":
            handle_email_sequence(lambda: None, say, fake_command)
        elif cmd == "coach":
            say("Try `/coach roleplay discovery call` to start a live roleplay session!", channel=channel)
        else:
            say(f"Command `/{cmd}` not found in demo flow.", channel=channel)
    except Exception as e:
        say(f"Error running demo step: {str(e)[:200]}", channel=channel)

    # Post navigation buttons
    nav_blocks = format_demo_step_nav(step_index)
    say(text="", blocks=nav_blocks, channel=channel)


@app.action("demo_flow_end")
def handle_demo_flow_end(ack, body, say):
    """End the demo."""
    ack()
    channel = body["channel"]["id"]

    from formatters.demo_flow import format_demo_complete
    blocks, fallback = format_demo_complete()
    say(text=fallback, blocks=blocks, channel=channel)


# --- Thread Context Store (EXPANSION-17) ---

# Thread context — maps thread_ts to the context of the original command
# Each entry: {"command": str, "data": dict, "channel_id": str, "user_id": str}
thread_contexts = {}

# Maximum threads to track (prevent memory leaks in POC)
MAX_THREAD_CONTEXTS = 100


def save_thread_context(thread_ts: str, command: str, data: dict, channel_id: str, user_id: str):
    """Save context for a thread so follow-up replies can be handled.

    Args:
        thread_ts: The message timestamp that anchors this thread
        command: Which command created this message (e.g., "deal", "research", "pipeline")
        data: Key context data (company name, deal name, etc.)
        channel_id: Channel where the message was posted
        user_id: User who ran the command
    """
    global thread_contexts

    # Evict oldest if at capacity
    if len(thread_contexts) >= MAX_THREAD_CONTEXTS:
        oldest_key = next(iter(thread_contexts))
        del thread_contexts[oldest_key]

    thread_contexts[thread_ts] = {
        "command": command,
        "data": data,
        "channel_id": channel_id,
        "user_id": user_id,
    }


# --- /analyze-transcript Command (EXPANSION-21) ---

@app.command("/analyze-transcript")
def handle_analyze_transcript(ack, say, command):
    """Analyze call transcripts and generate coaching scripts."""
    ack()
    channel_id = command["channel_id"]
    user_id = command["user_id"]
    text = command["text"].strip()

    log_engagement(user_id, "command", command="/analyze-transcript")

    try:
        import subprocess
        import threading
        from tools.transcript_utils import get_analysis_status, list_all_transcripts

        # Show current status
        status = get_analysis_status()
        say(
            f"Analyzing call transcripts for coaching insights...\n"
            f"• Total transcripts: {status['total']}\n"
            f"• Already analyzed: {status['analyzed']}\n"
            f"• Pending: {status['pending']}\n\n"
            f"This may take 1-2 minutes per transcript.",
            channel=channel_id
        )

        def run_analysis():
            try:
                cmd = [".venv/bin/python", "scripts/analyze_transcripts.py"]
                if text:
                    # User specified a specific file
                    cmd.extend(["--file", text])
                else:
                    # Analyze only new transcripts
                    cmd.append("--skip-existing")

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode == 0:
                    # Count generated files
                    import glob
                    scripts = glob.glob("data/playbooks/coaching_from_transcripts/coaching_*.md")

                    say(
                        text=f"✓ Transcript analysis complete!\n"
                             f"Generated {len(scripts)} coaching script(s).\n\n"
                             f"Re-indexing RAG store...",
                        channel=channel_id,
                    )

                    # Re-index
                    reindex = subprocess.run(
                        [".venv/bin/python", "scripts/index_playbooks.py"],
                        capture_output=True, text=True, timeout=120,
                    )

                    if reindex.returncode == 0:
                        say(
                            text="✓ RAG store re-indexed. New coaching insights are now available in:\n"
                                 "• `/coach roleplay` — richer scenarios\n"
                                 "• `/coach-live` — better coaching tips\n"
                                 "• `/ask` — coaching Q&A",
                            channel=channel_id,
                        )
                    else:
                        say(text=f"Re-indexing had issues: {reindex.stderr[:500]}", channel=channel_id)
                else:
                    say(text=f"Analysis error: {result.stderr[:500]}", channel=channel_id)

            except subprocess.TimeoutExpired:
                say(text="Analysis timed out after 5 minutes.", channel=channel_id)
            except Exception as e:
                say(text=f"Error: {str(e)}", channel=channel_id)

        # Run in background thread so we don't block Slack
        thread = threading.Thread(target=run_analysis, daemon=True)
        thread.start()

    except Exception as e:
        handle_error(say, channel_id, "/analyze-transcript", e)


# --- /settings Command ---

def _methodology_label(key):
    """Get human-readable label for a methodology key."""
    labels = {
        "discovery": "Default (Generic)",
        "meddic": "MEDDIC",
        "spin": "SPIN Selling",
        "challenger": "Challenger Sale",
        "bant": "BANT",
        "negotiation": "Negotiation",
        "cold_call": "Cold Call",
        "competitive": "Competitive",
    }
    return labels.get(key, key.title())


def _language_label(code):
    """Get human-readable label for a language code."""
    from utils.language import get_language_name
    return get_language_name(code)


@app.command("/settings")
def handle_settings(ack, say, command, client):
    """Open user settings modal, or handle manager subcommands."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    # Manager management subcommands
    if text.startswith("add-manager"):
        _settings_add_manager(say, channel_id, user_id, text, client)
        return
    elif text.startswith("remove-manager"):
        _settings_remove_manager(say, channel_id, user_id, text, client)
        return
    elif text == "list-managers":
        _settings_list_managers(say, channel_id)
        return

    trigger_id = command["trigger_id"]
    settings = get_user_settings(user_id)

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "settings_modal",
            "title": {"type": "plain_text", "text": "SalesCoach Settings"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Response Mode*\nWhere should SalesCoach post responses?"}
                },
                {
                    "type": "actions",
                    "block_id": "response_mode_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "response_mode",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "In channel" if settings["response_mode"] == "channel" else "Direct message"},
                            "value": settings["response_mode"],
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "In channel"}, "value": "channel"},
                            {"text": {"type": "plain_text", "text": "Direct message"}, "value": "dm"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Detail Level*\nHow much detail in research/deal responses?"}
                },
                {
                    "type": "actions",
                    "block_id": "detail_level_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "detail_level",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Summary first (expand for full)" if settings["detail_level"] == "summary" else "Full detail always"},
                            "value": settings["detail_level"],
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Summary first (expand for full)"}, "value": "summary"},
                            {"text": {"type": "plain_text", "text": "Full detail always"}, "value": "full"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Coaching Privacy*\nKeep coaching scores and roleplay debriefs private?"}
                },
                {
                    "type": "actions",
                    "block_id": "coaching_privacy_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "coaching_privacy",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Yes — DM only" if settings["coaching_privacy"] else "No — post in channel"},
                            "value": "true" if settings["coaching_privacy"] else "false",
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes — DM only"}, "value": "true"},
                            {"text": {"type": "plain_text", "text": "No — post in channel"}, "value": "false"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Scoring Methodology*\nWhich framework should SalesCoach use to evaluate your roleplays?"}
                },
                {
                    "type": "actions",
                    "block_id": "methodology_block",
                    "elements": [{
                        "type": "static_select",
                        "action_id": "methodology",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": _methodology_label(settings.get("methodology", "discovery"))},
                            "value": settings.get("methodology", "discovery"),
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Default (Generic)"}, "value": "discovery"},
                            {"text": {"type": "plain_text", "text": "MEDDIC"}, "value": "meddic"},
                            {"text": {"type": "plain_text", "text": "SPIN Selling"}, "value": "spin"},
                            {"text": {"type": "plain_text", "text": "Challenger Sale"}, "value": "challenger"},
                            {"text": {"type": "plain_text", "text": "BANT"}, "value": "bant"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Language*\nWhich language should SalesCoach use for responses?"}
                },
                {
                    "type": "actions",
                    "block_id": "language_block",
                    "elements": [{
                        "type": "static_select",
                        "action_id": "language",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": _language_label(settings.get("language", "en"))},
                            "value": settings.get("language", "en"),
                        },
                        "options": format_language_options_for_slack()
                    }]
                },
            ]
        }
    )


def _settings_add_manager(say, channel_id, user_id, text, client):
    """Add a user as a sales manager."""
    from tools.user_access import _load_managers_config, clear_caches
    import re as _re

    # Only existing managers (or first-time setup) can add managers
    config = _load_managers_config()
    if config["managers"] and not is_manager(user_id):
        say(channel=channel_id, text=":no_entry: Only existing managers can add new managers.")
        return

    # Parse @mention from text: "add-manager <@U07ABC123|username>"
    match = _re.search(r"<@(\w+)", text)
    if not match:
        say(channel=channel_id, text="Usage: `/settings add-manager @username`")
        return

    target_user_id = match.group(1)

    # Load, modify, save
    config_path = os.path.join("data", "user_roles.json")
    if target_user_id not in config["managers"]:
        config["managers"].append(target_user_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        clear_caches()
        say(channel=channel_id, text=f":white_check_mark: <@{target_user_id}> added as a sales manager. They can now see all CRM records.")
    else:
        say(channel=channel_id, text=f"<@{target_user_id}> is already a manager.")


def _settings_remove_manager(say, channel_id, user_id, text, client):
    """Remove a user from the managers list."""
    from tools.user_access import _load_managers_config, clear_caches
    import re as _re

    if not is_manager(user_id):
        say(channel=channel_id, text=":no_entry: Only managers can modify manager settings.")
        return

    match = _re.search(r"<@(\w+)", text)
    if not match:
        say(channel=channel_id, text="Usage: `/settings remove-manager @username`")
        return

    target_user_id = match.group(1)

    config_path = os.path.join("data", "user_roles.json")
    config = _load_managers_config()
    if target_user_id in config["managers"]:
        config["managers"].remove(target_user_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        clear_caches()
        say(channel=channel_id, text=f":white_check_mark: <@{target_user_id}> removed from managers. They'll now see only their own records.")
    else:
        say(channel=channel_id, text=f"<@{target_user_id}> is not currently a manager.")


def _settings_list_managers(say, channel_id):
    """List current managers."""
    from tools.user_access import _load_managers_config

    config = _load_managers_config()
    managers = config.get("managers", [])
    if managers:
        manager_list = "\n".join([f"• <@{uid}>" for uid in managers])
        say(channel=channel_id, text=f"*Current Sales Managers:*\n{manager_list}")
    else:
        say(channel=channel_id, text="No managers configured yet. Run `/settings add-manager @username` to add the first one.")


@app.view("settings_modal")
def handle_settings_submit(ack, body, view):
    """Handle settings modal submission."""
    ack()
    user_id = body["user"]["id"]
    values = view["state"]["values"]

    response_mode = values["response_mode_block"]["response_mode"]["selected_option"]["value"]
    detail_level = values["detail_level_block"]["detail_level"]["selected_option"]["value"]
    coaching_privacy = values["coaching_privacy_block"]["coaching_privacy"]["selected_option"]["value"] == "true"
    methodology = values["methodology_block"]["methodology"]["selected_option"]["value"]
    language = values["language_block"]["language"]["selected_option"]["value"]

    update_user_settings(user_id,
        response_mode=response_mode,
        detail_level=detail_level,
        coaching_privacy=coaching_privacy,
        methodology=methodology,
        language=language
    )


# No-op handler for radio button and select interactions in settings modal
@app.action("response_mode")
@app.action("detail_level")
@app.action("coaching_privacy")
@app.action("methodology")
@app.action("language")
def handle_settings_radio_noop(ack):
    """Acknowledge radio button and select interactions in settings modal."""
    ack()


# --- /training-history Command ---

@app.command("/training-history")
def handle_training_history(ack, command, client, say):
    """Show user's training session history."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/training-history")

    # Check if querying another user (manager use case): /training-history @user
    target_user = user_id
    if text.startswith("<@") and text.endswith(">"):
        target_user = text[2:-1].split("|")[0]  # Extract user ID from <@U12345|name>

    # Get data
    sessions = get_training_history(target_user, limit=10)
    stats = get_training_stats(target_user)

    if not sessions:
        say(
            channel=channel_id,
            text=f"No training sessions found{' for <@' + target_user + '>' if target_user != user_id else ''}. Start practicing with `/coach roleplay [scenario]`."
        )
        return

    from formatters.training_history import format_training_history
    blocks, fallback = format_training_history(target_user, sessions, stats)
    say(channel=channel_id, text=fallback, blocks=blocks)


@app.action("practice_from_history")
def handle_practice_from_history(ack, body, say):
    """Start a new roleplay based on a previous session."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    scenario = data.get("scenario", "discovery call")
    scenario_type = data.get("scenario_type", "discovery")
    company = data.get("company", "")

    # Guide user to start the practice
    scenario_hint = f" with {company}" if company else ""
    say(
        channel=channel,
        text=f"To practice this scenario again, use:\n`/coach roleplay {scenario_type}{scenario_hint}`"
    )


# --- /skill-gaps Command ---

@app.command("/skill-gaps")
def handle_skill_gaps(ack, command, client, say):
    """Analyze skill gaps based on training history."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/skill-gaps")

    # Allow checking another user: /skill-gaps @user
    target_user = user_id
    if text.startswith("<@") and text.endswith(">"):
        target_user = text[2:-1].split("|")[0]

    analysis = analyze_skill_gaps(target_user)
    blocks, fallback = format_skill_gaps(target_user, analysis)
    say(channel=channel_id, text=fallback, blocks=blocks)


@app.action("view_skill_gaps")
def handle_view_skill_gaps(ack, body, say):
    """Show skill gaps based on dimension scores (button handler)."""
    ack()
    user_id = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    analysis = analyze_skill_gaps(user_id)
    blocks, fallback = format_skill_gaps(user_id, analysis)
    say(channel=channel, text=fallback, blocks=blocks)


@app.action("view_training_history")
def handle_view_training_history_button(ack, body, say):
    """Show training history (button handler)."""
    ack()
    user_id = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    sessions = get_training_history(user_id, limit=10)
    stats = get_training_stats(user_id)

    if not sessions:
        say(channel=channel, text="No training sessions found. Start practicing with `/coach roleplay [scenario]`.")
        return

    from formatters.training_history import format_training_history
    blocks, fallback = format_training_history(user_id, sessions, stats)
    say(channel=channel, text=fallback, blocks=blocks)


@app.action("practice_skill_gap")
def handle_practice_skill_gap(ack, body, say):
    """Start a practice session targeting a specific skill gap."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    dimension = data.get("dimension", "discovery")
    scenario_type = data.get("scenario_type", "discovery")
    channel = body["channel"]["id"]

    log_engagement(body["user"]["id"], "action", action_id="practice_skill_gap", dimension=dimension)

    # Guide user to start practice for the specific gap
    say(
        channel=channel,
        text=f"To improve *{dimension.replace('_', ' ').title()}*, try:\n"
             f"`/coach roleplay {scenario_type}`"
    )


@app.action("start_new_practice")
def handle_start_new_practice(ack, body, say):
    """Guide user to start a new practice session."""
    ack()
    channel = body["channel"]["id"]

    say(
        channel=channel,
        text="Start a new practice session:\n"
             "• `/coach roleplay discovery` — Practice discovery calls\n"
             "• `/coach roleplay negotiation` — Practice pricing discussions\n"
             "• `/coach roleplay objection` — Handle tough objections\n"
             "• `/coach roleplay cold_call` — Cold calling practice\n"
             "• `/coach roleplay competitive` — Competitive displacement"
    )


# --- CRM Write Commands ---

def _find_deal_by_name(deal_name):
    """Find a deal by name. Tries HubSpot first, then falls back to mock CRM."""
    from tools.crm_write import search_deal_in_hubspot, is_mock_mode

    # Try HubSpot first if available
    if not is_mock_mode():
        hubspot_deal = search_deal_in_hubspot(deal_name)
        if hubspot_deal:
            return hubspot_deal

    # Fallback to mock CRM
    return mock_crm.search_deal(deal_name)


def _find_deal_by_company(company_name):
    """Find the primary deal for a company. Tries HubSpot first, then falls back to mock CRM."""
    from tools.crm_write import search_company_in_hubspot, is_mock_mode

    # Try HubSpot first if available
    if not is_mock_mode():
        hubspot_company = search_company_in_hubspot(company_name)
        if hubspot_company:
            company_id = hubspot_company.get("id", "")
            # Get deals for this company from HubSpot
            try:
                from tools.crm_write import _get_hubspot_client
                client = _get_hubspot_client()
                if client:
                    response = client.crm.deals.search_api.do_search(
                        public_object_search_request={
                            "filterGroups": [{
                                "filters": [{
                                    "propertyName": "associatedcompanyid",
                                    "operator": "EQ",
                                    "value": company_id
                                }]
                            }],
                            "properties": ["dealname", "amount", "dealstage"],
                            "limit": 10
                        }
                    )
                    if response.results:
                        deal = response.results[0]
                        return {"id": deal.id, "properties": deal.properties}
            except Exception as e:
                print(f"[HubSpot get_deals_for_company] Error: {e}")

    # Fallback to mock CRM
    company = mock_crm.search_company(company_name)
    if not company:
        return None
    company_id = company.get("id", "")
    deals = mock_crm.get_deals_for_company(company_id)
    return deals[0] if deals else None


@app.command("/log")
def handle_log(ack, command, client, say):
    """Log a note to a deal in CRM."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/log")

    if not text:
        say(channel=channel_id, text="Usage: `/log [deal-name] [your note]`\nExample: `/log NovaTech Great call with Sarah — she's interested in the enterprise plan`")
        return

    # Parse: first word(s) before a clear separator are the deal name
    if " — " in text:
        deal_name, note_body = text.split(" — ", 1)
    elif " - " in text:
        deal_name, note_body = text.split(" - ", 1)
    else:
        # First word is deal name, rest is note
        parts = text.split(" ", 1)
        if len(parts) < 2:
            say(channel=channel_id, text="Please include both a deal name and your note.\nExample: `/log NovaTech — Great call, she wants a proposal`")
            return
        deal_name, note_body = parts[0], parts[1]

    deal_name = deal_name.strip()
    note_body = note_body.strip()

    # Look up the deal
    deal = _find_deal_by_name(deal_name)
    if not deal:
        say(channel=channel_id, text=f"Could not find a deal matching *{deal_name}*. Try `/deal {deal_name}` to search.")
        return

    deal_id = deal.get("id")
    actual_deal_name = deal.get("properties", {}).get("dealname", deal_name)

    # Create the note
    from tools.crm_write import create_note
    result = create_note(user_id, deal_id, actual_deal_name, note_body)

    mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
    if result["success"]:
        say(
            channel=channel_id,
            text=f"✅ Note logged on *{actual_deal_name}* ({mode_label}):\n> {note_body[:200]}"
        )
    else:
        say(
            channel=channel_id,
            text=f"⚠️ Failed to log note: {result.get('error', 'Unknown error')}. Try again or contact support."
        )


@app.action("log_note")
def handle_log_note_action(ack, body, client):
    """Open modal to log a note on a deal."""
    ack()
    trigger_id = body["trigger_id"]
    # Value can be deal_id or "log_note|deal_name" format from overflow
    value = body["actions"][0]["value"]
    if "|" in value:
        _, deal_name = value.split("|", 1)
    else:
        deal_name = value

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "log_note_modal",
            "title": {"type": "plain_text", "text": "Log Note"},
            "submit": {"type": "plain_text", "text": "Save to CRM"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps({"deal_name": deal_name}),
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Deal:* {deal_name}"}
                },
                {
                    "type": "input",
                    "block_id": "note_input_block",
                    "label": {"type": "plain_text", "text": "Note"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "note_text",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What happened? Key takeaways, next steps, decisions made..."},
                    }
                },
            ]
        }
    )


@app.view("log_note_modal")
def handle_log_note_submit(ack, body, client, view):
    """Handle log note modal submission."""
    import traceback
    ack()
    user_id = body["user"]["id"]
    metadata = json.loads(view["private_metadata"])
    deal_name = metadata["deal_name"]
    note_text = view["state"]["values"]["note_input_block"]["note_text"]["value"]

    print(f"[LOG_NOTE] Modal submitted by {user_id} for deal '{deal_name}' with note: {note_text[:100]}")

    try:
        from tools.crm_write import search_deal_in_hubspot, create_note, is_mock_mode, _get_hubspot_client

        # Check HubSpot connection status
        hubspot_client = _get_hubspot_client()
        print(f"[LOG_NOTE] HubSpot client available: {hubspot_client is not None}")
        print(f"[LOG_NOTE] is_mock_mode: {is_mock_mode()}")

        # Always try HubSpot first
        deal = None
        if hubspot_client:
            print(f"[LOG_NOTE] Searching HubSpot for deal: {deal_name}")
            deal = search_deal_in_hubspot(deal_name)
            if deal:
                print(f"[LOG_NOTE] Found in HubSpot: ID={deal.get('id')}, Name={deal.get('properties', {}).get('dealname')}")
            else:
                print(f"[LOG_NOTE] Not found in HubSpot, trying mock CRM")

        # Fallback to mock CRM if not found in HubSpot
        if not deal:
            deal = _find_deal_by_name(deal_name)
            if deal:
                print(f"[LOG_NOTE] Found in mock CRM: ID={deal.get('id')}")

        if not deal:
            print(f"[LOG_NOTE] Deal '{deal_name}' not found")
            # DM error to user
            dm = client.conversations_open(users=[user_id])
            client.chat_postMessage(
                channel=dm["channel"]["id"],
                text=f"⚠️ Could not find deal *{deal_name}*. Note not saved."
            )
            return

        deal_id = deal.get("id")
        actual_deal_name = deal.get("properties", {}).get("dealname", deal_name)
        print(f"[LOG_NOTE] Found deal: {actual_deal_name} (ID: {deal_id})")

        result = create_note(user_id, deal_id, actual_deal_name, note_text)
        print(f"[LOG_NOTE] create_note result: {result}")

        # DM confirmation to the user
        dm = client.conversations_open(users=[user_id])
        mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
        if result["success"]:
            client.chat_postMessage(
                channel=dm["channel"]["id"],
                text=f"✅ Note saved on *{actual_deal_name}* ({mode_label}):\n> {note_text[:200]}"
            )
        else:
            client.chat_postMessage(
                channel=dm["channel"]["id"],
                text=f"⚠️ Failed to save note: {result.get('error', 'Unknown error')}"
            )
    except Exception as e:
        print(f"[LOG_NOTE] Error: {e}")
        traceback.print_exc()
        dm = client.conversations_open(users=[user_id])
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f"⚠️ Unexpected error: {str(e)[:300]}"
        )


@app.action("log_coaching_to_crm")
def handle_log_coaching_to_crm(ack, body, client):
    """Log a coaching session to CRM as a note on the deal."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]

    company = data.get("company", "")
    if not company:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text="No company associated with this session. Use `/log [deal] [note]` instead."
        )
        return

    # Find deal by company name
    deal = _find_deal_by_company(company)
    if not deal:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text=f"No deal found for *{company}*. Use `/log [deal] [note]` to log manually."
        )
        return

    deal_id = deal.get("id")
    deal_name = deal.get("properties", {}).get("dealname", company)

    from tools.crm_write import log_coaching_activity
    result = log_coaching_activity(
        user_id, deal_id, deal_name,
        data.get("session_type", "roleplay"),
        data.get("score", "N/A"),
        data.get("scenario", ""),
    )

    mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
    if result["success"]:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text=f"✅ Coaching session logged on *{deal_name}* ({mode_label})"
        )
    else:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text=f"⚠️ Failed to log: {result.get('error', 'Unknown error')}"
        )


# --- Pagination Handlers ---

@app.action("deal_picker_prev")
@app.action("deal_picker_next")
def handle_deal_pagination(ack, body, client):
    """Handle deal picker pagination."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    search_term = data["search_term"]
    page = data["page"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    # Re-fetch deals
    deals = extract_deals_for_company(search_term, user_id)
    from formatters.deal import format_deal_picker
    blocks, fallback = format_deal_picker(search_term, deals, page=page)

    # Update the existing picker message
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


@app.action("contact_picker_prev")
@app.action("contact_picker_next")
def handle_contact_pagination(ack, body, client):
    """Handle contact picker pagination."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    company_name = data["company_name"]
    page = data["page"]
    email_context = data.get("email_context", {})
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    # Re-fetch contacts
    contacts = extract_contacts(company_name, user_id)
    from formatters.email import format_contact_picker
    blocks, fallback = format_contact_picker(company_name, contacts, email_context, page=page)

    # Update the existing picker message
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


@app.action("email_deal_picker_prev")
@app.action("email_deal_picker_next")
def handle_email_deal_pagination(ack, body, client):
    """Handle email deal picker pagination."""
    ack()
    data = json.loads(body["actions"][0]["value"])
    company_name = data["company_name"]
    page = data["page"]
    email_context = data.get("email_context", {})
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    # Re-fetch deals
    deals = extract_deals_for_company(company_name, user_id)
    from formatters.email import format_email_deal_picker
    blocks, fallback = format_email_deal_picker(company_name, deals, email_context, page=page)

    # Update the existing picker message
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )


# --- Smart Actions Handler ---

@app.action("research_from_deal_direct")
def handle_research_from_deal_direct(ack, body, client):
    """Handle 'Research Company' button from deal card (smart action)."""
    ack()
    company_name = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    # Get message_ts from container for ephemeral messages
    container = body.get("container", {})
    if container.get("type") == "ephemeral_message":
        message_ts = container.get("message_ts")
    else:
        message_ts = body.get("message", {}).get("ts") or container.get("message_ts")

    log_engagement(user_id, "action", action_id="research_from_deal_direct", company=company_name)

    # Post loading message in thread
    loading_msg = client.chat_postMessage(
        channel=channel,
        thread_ts=message_ts if message_ts else None,
        text=f"⏳ Researching *{company_name}*..."
    )
    loading_ts = loading_msg["ts"]

    try:
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/research {company_name}")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": None,
        })

        # These functions are defined in app.py
        company_data = extract_company_data(company_name)
        contacts = extract_contacts(company_name)
        deals = extract_deals(company_name)
        llm_response = result["messages"][-1].content

        # Use the existing parse_talking_points function (returns a string, not a list)
        talking_points = parse_talking_points(llm_response)

        # Cache research data for progressive disclosure
        cache_key = f"research_{user_id}_{company_name}"
        research_cache[cache_key] = {
            "company_data": company_data,
            "contacts": contacts,
            "deals": deals,
            "news": [],
            "talking_points": talking_points,
        }

        # Use compact summary format
        blocks, fallback = format_research_summary(
            company_name=company_name,
            company_data=company_data,
            contacts=contacts,
            deals=deals,
            news=[],
            talking_points=talking_points,
        )

        # Update loading message with final result
        client.chat_update(channel=channel, ts=loading_ts, text=fallback, blocks=blocks)

    except Exception as e:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}"
        )
        traceback.print_exc()


# --- Auto-CRM Detection Action Handlers (Wave 1E) ---

@app.action("auto_crm_confirm")
def handle_auto_crm_confirm(ack, body, client):
    """User clicked 'Log to CRM' on the auto-detect suggestion."""
    ack()
    user_id = body["user"]["id"]
    payload = json.loads(body["actions"][0]["value"])

    from tools.crm_write import create_note

    company = payload["company"]
    summary = payload["summary"]
    next_steps = payload.get("next_steps", "")
    source_channel = payload.get("source_channel", "")

    # Build the CRM note body
    note_body = summary
    if next_steps:
        note_body += f"\n\nNext steps: {next_steps}"

    # Try to find the company and associated deal
    company_obj = mock_crm.search_company(company)
    deal_id = None
    deal_name = company  # Fallback

    if company_obj:
        company_id = company_obj.get("id", "")
        deals = mock_crm.get_deals_for_company(company_id)
        if deals:
            deal = deals[0]  # Use first deal
            deal_id = deal.get("id", "")
            deal_name = deal.get("properties", {}).get("dealname", company)

    # Write to CRM (or mock)
    try:
        if deal_id:
            result = create_note(
                user_id=user_id,
                deal_id=deal_id,
                deal_name=deal_name,
                note_body=note_body
            )
        else:
            # No deal found - log directly to mock
            from db import log_crm_write
            import time
            note_id = f"auto_note_{int(time.time())}"
            log_crm_write(user_id, "note", "company", company, company, note_body, note_id, "mock")
            result = {"success": True, "mode": "mock", "note_id": note_id}

        # Post ephemeral confirmation
        mode_label = "Synced to HubSpot" if result.get("mode") == "hubspot" else "Saved locally"
        client.chat_postEphemeral(
            channel=source_channel,
            user=user_id,
            text=f":white_check_mark: Logged to CRM ({mode_label}): *{company}* — {summary[:80]}..."
        )

        log_engagement(user_id, "auto_crm_confirmed", company=company)

    except Exception as e:
        client.chat_postEphemeral(
            channel=source_channel,
            user=user_id,
            text=f":x: Failed to log: {str(e)[:100]}. Try `/log {company}` manually."
        )


@app.action("auto_crm_edit")
def handle_auto_crm_edit(ack, body, client):
    """User clicked 'Edit & Log' — open modal with pre-filled note."""
    ack()
    payload = json.loads(body["actions"][0]["value"])

    modal = {
        "type": "modal",
        "callback_id": "auto_crm_edit_submit",
        "title": {"type": "plain_text", "text": "Edit CRM Note"},
        "submit": {"type": "plain_text", "text": "Log to CRM"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": json.dumps({
            "source_channel": payload.get("source_channel", ""),
            "source_ts": payload.get("source_ts", "")
        }),
        "blocks": [
            {
                "type": "input",
                "block_id": "company_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "company_input",
                    "initial_value": payload.get("company", ""),
                    "placeholder": {"type": "plain_text", "text": "Company name"}
                },
                "label": {"type": "plain_text", "text": "Company"}
            },
            {
                "type": "input",
                "block_id": "note_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "note_input",
                    "multiline": True,
                    "initial_value": payload.get("summary", ""),
                    "placeholder": {"type": "plain_text", "text": "CRM note content"}
                },
                "label": {"type": "plain_text", "text": "Note"}
            },
            {
                "type": "input",
                "block_id": "next_steps_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "next_steps_input",
                    "initial_value": payload.get("next_steps", "") or "",
                    "placeholder": {"type": "plain_text", "text": "Follow-up actions"}
                },
                "label": {"type": "plain_text", "text": "Next Steps"}
            }
        ]
    }

    client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.view("auto_crm_edit_submit")
def handle_auto_crm_edit_submit(ack, body, view, client):
    """Process the edited CRM note submission."""
    ack()
    user_id = body["user"]["id"]
    metadata = json.loads(view["private_metadata"])

    company = view["state"]["values"]["company_block"]["company_input"]["value"]
    note = view["state"]["values"]["note_block"]["note_input"]["value"]
    next_steps = view["state"]["values"]["next_steps_block"]["next_steps_input"]["value"]

    from tools.crm_write import create_note

    note_body = note
    if next_steps:
        note_body += f"\n\nNext steps: {next_steps}"

    # Try to find the company and associated deal
    company_obj = mock_crm.search_company(company)
    deal_id = None
    deal_name = company

    if company_obj:
        company_id = company_obj.get("id", "")
        deals = mock_crm.get_deals_for_company(company_id)
        if deals:
            deal = deals[0]
            deal_id = deal.get("id", "")
            deal_name = deal.get("properties", {}).get("dealname", company)

    try:
        if deal_id:
            result = create_note(
                user_id=user_id,
                deal_id=deal_id,
                deal_name=deal_name,
                note_body=note_body
            )
        else:
            from db import log_crm_write
            import time
            note_id = f"auto_note_{int(time.time())}"
            log_crm_write(user_id, "note", "company", company, company, note_body, note_id, "mock")
            result = {"success": True, "mode": "mock", "note_id": note_id}

        # Send DM confirmation (modal closes automatically)
        dm = client.conversations_open(users=[user_id])
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f":white_check_mark: Logged to CRM: *{company}* — {note[:80]}..."
        )

        log_engagement(user_id, "auto_crm_edited", company=company)

    except Exception as e:
        dm = client.conversations_open(users=[user_id])
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f":x: Failed to log: {str(e)[:100]}"
        )


@app.action("auto_crm_dismiss")
def handle_auto_crm_dismiss(ack, body):
    """User dismissed the suggestion. Log it for tuning."""
    ack()
    user_id = body["user"]["id"]

    log_engagement(user_id, "auto_crm_dismissed")
    # Ephemeral messages disappear on their own eventually


# =====================================================
# WAVE COMMANDS - Consolidated Command Structure
# =====================================================
# /my-day - standalone
# /training - parent with subcommands: create, library, assign, launch, onboard, cohort, progress, history, gaps
# /team - parent with subcommands: dashboard, insights
# =====================================================

@app.command("/my-day")
def handle_my_day(ack, command, say):
    """Show today's calendar with meeting prep actions and pipeline preview."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/my-day")

    try:
        from datetime import datetime
        from formatters.calendar import format_my_day

        events = get_user_events(user_id, datetime.now().date())
        date_label = datetime.now().strftime("%A, %b %-d")

        # Pass user_id for pipeline summary
        blocks = format_my_day(events, user_name=None, user_id=user_id)

        say(channel=channel_id, blocks=blocks, text=f"Your Day - {date_label}")
    except Exception as e:
        handle_error(say, channel_id, "/my-day", e)


# ──────────────────────────────────────────────────────────────
# /training — Parent command for all training features
# Subcommands: create, library, assign, launch, onboard,
#              cohort, progress, history, gaps
# ──────────────────────────────────────────────────────────────

TRAINING_HELP_TEXT = """*`/training` — Training & Scenario Management*

Available subcommands:
• `/training create` — Create a custom roleplay scenario (opens modal)
• `/training library` — Browse the scenario library
• `/training assign @rep SCENARIO_ID [--due YYYY-MM-DD]` — Assign a scenario to a rep
• `/training launch` — Generate a product launch training program (opens modal)
• `/training onboard @new-rep` — Start a 4-week new hire onboarding program
• `/training cohort "Name" @user1 @user2 [--weeks 4]` — Create a multi-week training cohort
• `/training progress [program name]` — View cohort training progress
• `/training history` — View your training session history
• `/training gaps` — View your skill gap analysis"""


@app.command("/training")
def handle_training(ack, command, say, client):
    """Parent command that routes to training subcommands."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    if not text:
        say(channel=channel_id, text=TRAINING_HELP_TEXT)
        return

    parts = text.split(None, 1)
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    try:
        if subcommand == "create":
            _training_create(command, client, user_id)
        elif subcommand in ("library", "list", "scenarios"):
            _training_library(say, channel_id, user_id)
        elif subcommand == "assign":
            _training_assign(say, client, channel_id, user_id, args)
        elif subcommand == "launch":
            _training_launch(command, client, user_id)
        elif subcommand == "onboard":
            _training_onboard(say, client, channel_id, user_id, args)
        elif subcommand == "cohort":
            _training_cohort(say, client, channel_id, user_id, args)
        elif subcommand == "progress":
            _training_progress(say, channel_id, user_id, args)
        elif subcommand == "history":
            _training_history(say, command, user_id, channel_id)
        elif subcommand == "gaps":
            _training_gaps(say, command, user_id, channel_id)
        else:
            say(channel=channel_id, text=f"Unknown subcommand `{subcommand}`.\n\n{TRAINING_HELP_TEXT}")
    except Exception as e:
        handle_error(say, channel_id, f"/training {subcommand}", e)


def _training_create(command, client, user_id):
    """Open the create-scenario modal."""
    trigger_id = command["trigger_id"]
    log_engagement(user_id, "command", command="/training create")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "create_scenario_modal",
            "title": {"type": "plain_text", "text": "Create Scenario"},
            "submit": {"type": "plain_text", "text": "Save Scenario"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "input", "block_id": "name_block", "label": {"type": "plain_text", "text": "Scenario Name"},
                 "element": {"type": "plain_text_input", "action_id": "name", "placeholder": {"type": "plain_text", "text": "Discovery Call: Enterprise CFO"}}},

                {"type": "input", "block_id": "type_block", "label": {"type": "plain_text", "text": "Type"},
                 "element": {"type": "static_select", "action_id": "type", "options": [
                     {"text": {"type": "plain_text", "text": t.title()}, "value": t}
                     for t in ["discovery", "negotiation", "competitive", "cold_call", "objection", "demo"]
                 ]}},

                {"type": "input", "block_id": "difficulty_block", "label": {"type": "plain_text", "text": "Difficulty"},
                 "element": {"type": "static_select", "action_id": "difficulty", "options": [
                     {"text": {"type": "plain_text", "text": d.title()}, "value": d}
                     for d in ["beginner", "intermediate", "advanced", "expert"]
                 ], "initial_option": {"text": {"type": "plain_text", "text": "Intermediate"}, "value": "intermediate"}}},

                {"type": "input", "block_id": "persona_block", "label": {"type": "plain_text", "text": "Buyer Persona"},
                 "element": {"type": "plain_text_input", "action_id": "persona", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "Name, title, company, personality, background."}}},

                {"type": "input", "block_id": "objectives_block", "label": {"type": "plain_text", "text": "Rep Objectives"},
                 "element": {"type": "plain_text_input", "action_id": "objectives", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "One per line:\nUncover 3 pain points\nIdentify the decision maker"}}},

                {"type": "input", "block_id": "methodology_block", "label": {"type": "plain_text", "text": "Scoring Methodology"},
                 "element": {"type": "static_select", "action_id": "methodology", "initial_option":
                     {"text": {"type": "plain_text", "text": "Default"}, "value": "discovery"},
                     "options": [
                         {"text": {"type": "plain_text", "text": "Default"}, "value": "discovery"},
                         {"text": {"type": "plain_text", "text": "MEDDIC"}, "value": "meddic"},
                         {"text": {"type": "plain_text", "text": "SPIN"}, "value": "spin"},
                         {"text": {"type": "plain_text", "text": "Challenger"}, "value": "challenger"},
                         {"text": {"type": "plain_text", "text": "BANT"}, "value": "bant"},
                     ]}},
            ]
        }
    )


@app.view("create_scenario_modal")
def handle_create_scenario_submit(ack, body, view, client):
    """Handle scenario creation modal submission."""
    ack()
    user_id = body["user"]["id"]
    v = view["state"]["values"]

    name = v["name_block"]["name"]["value"]
    type_ = v["type_block"]["type"]["selected_option"]["value"]
    difficulty = v["difficulty_block"]["difficulty"]["selected_option"]["value"]
    persona_text = v["persona_block"]["persona"]["value"]
    objectives_text = v["objectives_block"]["objectives"]["value"]
    methodology = v["methodology_block"]["methodology"]["selected_option"]["value"]

    objectives = [o.strip() for o in objectives_text.split("\n") if o.strip()]

    scenario_id = save_scenario(
        name=name,
        scenario_type=type_,
        created_by=user_id,
        persona=persona_text,
        objectives=objectives,
        difficulty=difficulty,
        scoring_methodology=methodology,
        tags=[type_, difficulty],
    )

    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=f":white_check_mark: Scenario saved: *{name}* ({type_.title()} · {difficulty.title()})\nID: `{scenario_id}`\n\nUse `/training library` to browse or `/training assign @rep {scenario_id}` to assign."
    )

    log_engagement(user_id, "scenario_created", scenario_id=scenario_id, scenario_type=type_)


def _training_library(say, channel_id, user_id):
    """Show the scenario library."""
    log_engagement(user_id, "command", command="/training library")

    scenarios = list_scenarios()
    if not scenarios:
        say(channel=channel_id, text="No scenarios saved yet. Use `/training create` to build your first one.")
        return

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Scenario Library"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{len(scenarios)} scenarios available"}]},
        {"type": "divider"},
    ]

    for s in scenarios[:15]:
        score_display = f"{s['avg_score']:.1f}/10" if s.get("avg_score") else "Not yet scored"
        difficulty_emoji = {"beginner": ":green_circle:", "intermediate": ":large_yellow_circle:", "advanced": ":red_circle:", "expert": ":purple_circle:"}.get(s.get("difficulty"), ":white_circle:")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"{difficulty_emoji} *{s['name']}*\n"
                f"{s['type'].replace('_', ' ').title()} · {s.get('difficulty', 'intermediate').title()} · "
                f"Practiced {s.get('usage_count', 0)}x · Avg: {score_display}"
            )},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice"},
                "action_id": "start_saved_scenario",
                "value": s["id"],
                "style": "primary",
            }
        })

    blocks.append({"type": "divider"})
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Create New Scenario"}, "action_id": "open_create_scenario_modal"}
    ]})

    say(channel=channel_id, text=f"Scenario Library: {len(scenarios)} scenarios", blocks=blocks)


def _training_assign(say, client, channel_id, user_id, args):
    """Assign a scenario to a rep."""
    log_engagement(user_id, "command", command="/training assign")

    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', args)
    if not user_match:
        say(channel=channel_id, text="Usage: `/training assign @rep scenario-id`\nExample: `/training assign @sarah abc123 --due 2026-03-19`")
        return

    target_user = user_match.group(1)
    remaining = args[user_match.end():].strip()

    due_date = None
    due_match = re.search(r'--due\s+(\d{4}-\d{2}-\d{2})', remaining)
    if due_match:
        due_date = due_match.group(1)
        remaining = remaining[:due_match.start()].strip()

    scenario_id = remaining.strip()
    if not scenario_id:
        say(channel=channel_id, text="Please provide a scenario ID. Run `/training library` to see available scenarios.")
        return

    scenario = get_scenario(scenario_id)
    if not scenario:
        say(channel=channel_id, text=f"Scenario `{scenario_id}` not found. Run `/training library` to browse.")
        return

    assignment_id = create_assignment(scenario_id, user_id, target_user, due_date)

    dm = client.conversations_open(users=[target_user])
    due_text = f" Due by {due_date}." if due_date else ""
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=f"New Training Assignment from <@{user_id}>: {scenario['name']}{due_text}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": (
                f"*New Training Assignment*\n"
                f"<@{user_id}> assigned you: *{scenario['name']}*\n"
                f"{scenario['type'].replace('_', ' ').title()} · {scenario.get('difficulty', 'intermediate').title()}{f' · Due {due_date}' if due_date else ''}"
            )}},
            {"type": "actions", "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice"},
                "action_id": "start_saved_scenario",
                "value": scenario_id,
                "style": "primary",
            }]},
        ]
    )

    say(channel=channel_id, text=f":white_check_mark: Assigned *{scenario['name']}* to <@{target_user}>.{due_text}")


def _training_launch(command, client, user_id):
    """Open the launch-training modal for product launch training."""
    trigger_id = command["trigger_id"]
    log_engagement(user_id, "command", command="/training launch")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "launch_training_modal",
            "title": {"type": "plain_text", "text": "Launch Training"},
            "submit": {"type": "plain_text", "text": "Generate & Launch"},
            "blocks": [
                {"type": "input", "block_id": "product_name_block",
                 "label": {"type": "plain_text", "text": "Product Name"},
                 "element": {"type": "plain_text_input", "action_id": "product_name",
                             "placeholder": {"type": "plain_text", "text": "CloudSync Enterprise"}}},
                {"type": "input", "block_id": "product_desc_block",
                 "label": {"type": "plain_text", "text": "Product Description & Key Features"},
                 "element": {"type": "plain_text_input", "action_id": "product_desc", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "Describe the product, its key features, target audience, pricing..."}}},
                {"type": "input", "block_id": "competitors_block",
                 "label": {"type": "plain_text", "text": "Main Competitors"},
                 "element": {"type": "plain_text_input", "action_id": "competitors",
                             "placeholder": {"type": "plain_text", "text": "Competitor A, Competitor B"}},
                 "optional": True},
                {"type": "input", "block_id": "team_block",
                 "label": {"type": "plain_text", "text": "Team Members (mention with @)"},
                 "element": {"type": "plain_text_input", "action_id": "team",
                             "placeholder": {"type": "plain_text", "text": "@sarah @mike @alex"}}},
            ]
        }
    )


@app.view("launch_training_modal")
def handle_launch_training_submit(ack, body, view, client):
    """Handle launch training modal - generates scenarios via LLM."""
    ack()
    user_id = body["user"]["id"]
    v = view["state"]["values"]

    product_name = v["product_name_block"]["product_name"]["value"]
    product_desc = v["product_desc_block"]["product_desc"]["value"]
    competitors = v.get("competitors_block", {}).get("competitors", {}).get("value", "")
    team_text = v["team_block"]["team"]["value"]

    team_users = re.findall(r'<@(\w+)(?:\|[^>]*)?>', team_text)

    # Notify user that generation is starting
    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=f":hourglass_flowing_sand: Generating training scenarios for *{product_name}*... This may take a moment."
    )

    try:
        from llm_factory import get_llm
        llm = get_llm()

        generation_prompt = f"""Generate 5 sales roleplay scenarios for training reps on a new product.

Product: {product_name}
Description: {product_desc}
Competitors: {competitors}

For each scenario, output a JSON array with objects containing:
- name: Scenario name
- type: One of [cold_call, discovery, objection, competitive, negotiation]
- difficulty: One of [beginner, intermediate, advanced]
- persona: Brief description of the buyer
- objectives: Array of learning objectives

Output ONLY the JSON array, no other text."""

        response = llm.invoke(generation_prompt)

        try:
            scenarios_data = json.loads(response.content)
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if match:
                scenarios_data = json.loads(match.group(0))
            else:
                client.chat_postMessage(
                    channel=dm["channel"]["id"],
                    text=f":x: Failed to generate scenarios for {product_name}. Try again with more product detail."
                )
                return

        from datetime import datetime, timedelta

        scenario_ids = []
        for s in scenarios_data:
            sid = save_scenario(
                name=s["name"],
                scenario_type=s["type"],
                difficulty=s.get("difficulty", "intermediate"),
                created_by=user_id,
                persona=s.get("persona", "Business executive"),
                objectives=s.get("objectives", []),
                tags=["product_launch", product_name.lower().replace(" ", "_")],
                product_context=product_desc[:500],
            )
            scenario_ids.append(sid)

        # Create assignments for team
        due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        for uid in team_users:
            for sid in scenario_ids:
                create_assignment(sid, user_id, uid, due_date=due_date)

            # Notify team member
            team_dm = client.conversations_open(users=[uid])
            client.chat_postMessage(
                channel=team_dm["channel"]["id"],
                text=(
                    f"*New Product Training: {product_name}*\n"
                    f"<@{user_id}> launched a training program with {len(scenario_ids)} scenarios.\n"
                    f"Due by {due_date}. Use `/training library` to start practicing."
                )
            )

        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=(
                f":white_check_mark: *Product Launch Training Created: {product_name}*\n"
                f"Generated {len(scenario_ids)} scenarios for {len(team_users)} reps.\n"
                f"Use `/training library` to view scenarios."
            )
        )

        log_engagement(user_id, "launch_training_created", product=product_name, scenarios=len(scenario_ids))

    except Exception as e:
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f":x: Error generating training: {str(e)[:200]}"
        )


def _training_onboard(say, client, channel_id, user_id, args):
    """Start 4-week onboarding for a new rep."""
    log_engagement(user_id, "command", command="/training onboard")

    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', args)
    if not user_match:
        say(channel=channel_id, text="Usage: `/training onboard @new-rep`")
        return

    target_user = user_match.group(1)

    template_path = os.path.join(os.path.dirname(__file__), "data", "cohort_templates", "new_hire_onboard.json")
    if not os.path.exists(template_path):
        say(channel=channel_id, text="Onboarding template not found. Please create `data/cohort_templates/new_hire_onboard.json`.")
        return

    with open(template_path) as f:
        template = json.load(f)

    from datetime import datetime, timedelta

    # Create scenarios from template and assign to user
    all_scenario_ids = []
    week_info = []

    for i, week in enumerate(template.get("weeks", [])):
        week_start = datetime.now() + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        week_scenarios = []

        for s in week.get("scenarios", []):
            sid = save_scenario(
                name=s["name"],
                scenario_type=s["type"],
                difficulty=s["difficulty"],
                created_by=user_id,
                persona=s["persona"].get("description", str(s["persona"])) if isinstance(s["persona"], dict) else s["persona"],
                objectives=s.get("objectives", []),
                tags=["onboarding", f"week_{i+1}"],
            )
            week_scenarios.append(sid)
            all_scenario_ids.append(sid)

            # Create assignment
            create_assignment(sid, user_id, target_user, due_date=week_end.strftime("%Y-%m-%d"))

        week_info.append({
            "label": week.get("label", f"Week {i+1}"),
            "scenarios": len(week_scenarios),
            "due": week_end.strftime("%Y-%m-%d")
        })

    # Notify the new hire
    dm = client.conversations_open(users=[target_user])
    week_summary = "\n".join([f"• *Week {i+1}: {w['label']}* — {w['scenarios']} scenarios (due {w['due']})" for i, w in enumerate(week_info)])

    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=(
            f":mortar_board: *Welcome to SalesCoach AI!*\n\n"
            f"<@{user_id}> has enrolled you in a {len(week_info)}-week onboarding program.\n\n"
            f"{week_summary}\n\n"
            f"Use `/training library` to start practicing!"
        )
    )

    say(channel=channel_id, text=f":white_check_mark: Onboarding program created for <@{target_user}>. {len(week_info)} weeks, {len(all_scenario_ids)} scenarios assigned.")
    log_engagement(user_id, "onboarding_created", target_user=target_user, scenarios=len(all_scenario_ids))


def _training_cohort(say, client, channel_id, user_id, args):
    """Create a multi-week cohort."""
    log_engagement(user_id, "command", command="/training cohort")

    name_match = re.search(r'"([^"]+)"', args)
    user_matches = re.findall(r'<@(\w+)(?:\|[^>]*)?>', args)
    weeks_match = re.search(r'--weeks\s+(\d+)', args)

    if not name_match or not user_matches:
        say(channel=channel_id, text='Usage: `/training cohort "Program Name" @user1 @user2 --weeks 4`')
        return

    program_name = name_match.group(1)
    num_weeks = int(weeks_match.group(1)) if weeks_match else 4
    participants = ", ".join(f"<@{u}>" for u in user_matches)

    # Create cohort in database
    cohort_id = create_cohort(
        name=program_name,
        created_by=user_id,
        description=f"{num_weeks}-week training program"
    )

    # Add participants
    for uid in user_matches:
        add_cohort_participant(cohort_id, uid)

    say(
        channel=channel_id,
        text=(
            f":white_check_mark: *Cohort Created: {program_name}*\n"
            f"Participants: {participants}\n"
            f"Duration: {num_weeks} weeks\n"
            f"Cohort ID: `{cohort_id}`\n\n"
            f"Now add scenarios using `/training assign` or use `/training progress {program_name}` to track progress."
        )
    )

    # Notify participants
    for uid in user_matches:
        dm = client.conversations_open(users=[uid])
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f":clipboard: You've been added to training cohort *{program_name}* by <@{user_id}>."
        )

    log_engagement(user_id, "cohort_created", cohort_id=cohort_id, participants=len(user_matches))


def _training_progress(say, channel_id, user_id, args):
    """Show cohort progress."""
    log_engagement(user_id, "command", command="/training progress")

    cohorts = list_cohorts(status="active")
    if not cohorts:
        say(channel=channel_id, text="No active training programs. Use `/training cohort` or `/training onboard` to start one.")
        return

    target = cohorts[0]
    if args:
        matches = [c for c in cohorts if args.lower() in c["name"].lower()]
        if matches:
            target = matches[0]

    data = get_cohort_progress(target["id"])
    if not data:
        say(channel=channel_id, text="Could not load progress data.")
        return

    blocks = format_cohort_progress(data)
    say(channel=channel_id, blocks=blocks, text=f"Cohort Progress: {target['name']}")


def _training_history(say, command, user_id, channel_id):
    """Show training history - calls existing logic."""
    log_engagement(user_id, "command", command="/training history")
    _show_training_history_impl(say, command, user_id, channel_id)


def _training_gaps(say, command, user_id, channel_id):
    """Show skill gaps - calls existing logic."""
    log_engagement(user_id, "command", command="/training gaps")
    _show_skill_gaps_impl(say, command, user_id, channel_id)


def _show_training_history_impl(say, command, user_id, channel_id):
    """Implementation of training history display."""
    sessions = get_training_history(user_id, limit=10)
    stats = get_training_stats(user_id)

    if not sessions:
        say(channel=channel_id, text="No training sessions yet. Use `/training library` to start practicing!")
        return

    from formatters.training_history import format_training_history
    blocks, fallback = format_training_history(user_id, sessions, stats)
    say(channel=channel_id, text=fallback, blocks=blocks)


def _show_skill_gaps_impl(say, command, user_id, channel_id):
    """Implementation of skill gaps display."""
    gaps = analyze_skill_gaps(user_id)

    if not gaps or not gaps.get("dimensions"):
        say(channel=channel_id, text="Not enough training data for skill gap analysis. Complete more practice sessions first.")
        return

    blocks = format_skill_gaps(gaps)
    say(channel=channel_id, blocks=blocks, text="Your Skill Gap Analysis")


# ──────────────────────────────────────────────────────────────
# /team — Parent command for manager/team tools
# Subcommands: dashboard, insights
# ──────────────────────────────────────────────────────────────

TEAM_HELP_TEXT = """*`/team` — Manager & Team Tools*

Available subcommands:
• `/team dashboard` — View team performance dashboard (leaderboard, skill heatmap, assignments)
• `/team insights` — Generate market and team insights from recent data"""


@app.command("/team")
def handle_team(ack, command, say, client):
    """Parent command for manager/team tools."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    if not text:
        say(channel=channel_id, text=TEAM_HELP_TEXT)
        return

    parts = text.split(None, 1)
    subcommand = parts[0].lower()

    try:
        if subcommand == "dashboard":
            _team_dashboard(say, channel_id, user_id)
        elif subcommand == "insights":
            _team_insights(say, channel_id, user_id)
        else:
            say(channel=channel_id, text=f"Unknown subcommand `{subcommand}`.\n\n{TEAM_HELP_TEXT}")
    except Exception as e:
        handle_error(say, channel_id, f"/team {subcommand}", e)


def _team_dashboard(say, channel_id, user_id):
    """Show team performance dashboard."""
    log_engagement(user_id, "command", command="/team dashboard")

    team_stats = get_team_training_summary()

    if not team_stats:
        say(channel=channel_id, text="No training data yet. Have your team run `/training library` to start building data.")
        return

    assignments_summary = get_team_assignments_summary()

    blocks = format_team_dashboard(team_stats, assignments_summary)
    say(channel=channel_id, blocks=blocks, text="Team Training Dashboard")


def _team_insights(say, channel_id, user_id):
    """Generate market and team insights."""
    log_engagement(user_id, "command", command="/team insights")

    say(channel=channel_id, text=":hourglass_flowing_sand: Analyzing recent sales data... this may take a moment.")

    try:
        digest = get_daily_digest()
        blocks = format_market_insights(digest)
        say(channel=channel_id, blocks=blocks, text="Market & Team Insights")
    except Exception as e:
        say(channel=channel_id, text=f":x: Error generating insights: {str(e)[:200]}")


# ──────────────────────────────────────────────────────────────
# Wave Commands Action Handlers
# Note: /training-history and /skill-gaps still work via their
# original handlers above - no need for duplicate redirects
# ──────────────────────────────────────────────────────────────

@app.action("start_saved_scenario")
def handle_start_saved_scenario(ack, body, client):
    """Start a roleplay from a saved scenario."""
    ack()
    scenario_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]

    scenario = get_scenario(scenario_id)
    if not scenario:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="Scenario not found.")
        return

    increment_scenario_usage(scenario_id)

    # Get user settings
    settings = get_user_settings(user_id)
    methodology = scenario.get("scoring_methodology") or settings.get("methodology", "discovery")
    language = settings.get("language", "en")
    lang_prompt = get_llm_language_prompt(language)

    persona = scenario.get("persona", "A professional prospect")
    objectives = scenario.get("objectives", [])

    # Post starting message
    result = client.chat_postMessage(
        channel=channel_id,
        blocks=format_roleplay_start(scenario['name'], persona, DEFAULT_ROLEPLAY_TURNS),
        text=f"Starting roleplay: {scenario['name']}"
    )
    thread_ts = result["ts"]

    # Start roleplay
    from graphs.coach import start_roleplay
    scenario_text = f"{scenario['name']}: {persona}"
    rp_messages = start_roleplay(
        persona, scenario_text, methodology=methodology, language_instruction=lang_prompt
    )

    active_roleplays[thread_ts] = {
        "messages": rp_messages,
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "turns": 0,
        "max_turns": DEFAULT_ROLEPLAY_TURNS,
        "methodology": methodology,
        "persona": persona,
        "scenario": scenario_text,
        "scenario_id": scenario_id,
        "company": scenario.get("product_context", ""),
        "language": language,
    }

    # Post first AI response
    first_response = rp_messages[-1].content if rp_messages else "Hello, how can I help you today?"
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"*{persona.split(',')[0] if ',' in persona else 'Prospect'}:* {first_response}"
    )

    log_engagement(user_id, "action", action_id="start_saved_scenario", scenario_id=scenario_id)


@app.action("open_create_scenario_modal")
def handle_open_create_scenario_action(ack, body, client):
    """Open create scenario modal from button."""
    ack()
    user_id = body["user"]["id"]
    trigger_id = body["trigger_id"]

    # Reuse the same modal
    _training_create({"trigger_id": trigger_id}, client, user_id)


@app.action("open_assign_flow")
def handle_open_assign_flow(ack, body, say):
    """Guide user to assign command."""
    ack()
    channel = body["channel"]["id"]
    say(channel=channel, text="To assign training, run:\n`/training assign @rep SCENARIO_ID --due YYYY-MM-DD`\n\nRun `/training library` to find scenario IDs.")


@app.action("quick_practice")
def handle_quick_practice_action(ack, body, client, say):
    """Quick practice button from /my-day."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    scenarios = list_scenarios(limit=5)
    if not scenarios:
        client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*No training scenarios available*\n\n"
                              "Get started by:\n"
                              "• Running `/training create` to create a custom scenario\n"
                              "• Using `/coach quick practice` for an instant session\n"
                              "• Running `/seed-scenarios` to load default scenarios"
                    }
                }
            ],
            text="No training scenarios available"
        )
        return

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Quick Practice - Choose a Scenario:*"}}
    ]

    for s in scenarios:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{s['name']}*\n_{s['type'].replace('_', ' ').title()}_"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start"},
                "action_id": "start_saved_scenario",
                "value": s["id"],
                "style": "primary"
            }
        })

    client.chat_postMessage(channel=channel_id, blocks=blocks, text="Quick Practice")


@app.action("quick_pipeline")
def handle_quick_pipeline_action(ack, body, client):
    """Show inline pipeline preview when clicking View Pipeline from /my-day."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        from formatters.pipeline import format_pipeline_response
        from tools.mock_crm import get_all_open_deals, get_stale_deals, get_overdue_deals

        # Fetch pipeline data
        deals = get_all_open_deals()

        total_value = sum(float(d.get("properties", {}).get("amount", 0) or 0) for d in deals)
        deal_count = len(deals)

        # Calculate weighted forecast and deals by stage
        weighted_forecast = 0.0
        stage_counts = {}
        for deal in deals:
            amount = float(deal.get("properties", {}).get("amount", 0) or 0)
            stage = deal.get("properties", {}).get("dealstage", "Unknown")
            # Simple weighting: early stages 25%, mid 50%, late 75%, negotiation 90%
            weights = {"prospecting": 0.25, "qualified": 0.50, "discovery": 0.50,
                       "demo": 0.60, "proposal": 0.75, "negotiation": 0.90}
            weight = weights.get(stage.lower(), 0.50)
            weighted_forecast += amount * weight
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        deals_by_stage = [(stage, count, sum(
            float(deal_iter.get("properties", {}).get("amount", 0) or 0)
            for deal_iter in deals if deal_iter.get("properties", {}).get("dealstage") == stage
        )) for stage, count in stage_counts.items()]

        # Flagged deals
        flagged_ids = set()
        for stale_deal in get_stale_deals():
            flagged_ids.add(stale_deal.get("id"))
        for overdue_deal in get_overdue_deals():
            flagged_ids.add(overdue_deal.get("id"))

        # Pre-compute overdue deal IDs for lookup
        overdue_ids = {od.get("id") for od in get_overdue_deals()}

        flagged_deals = []
        for deal in deals:
            if deal.get("id") in flagged_ids:
                name = deal.get("properties", {}).get("dealname", "Unknown")
                if deal.get("id") in overdue_ids:
                    flag = "overdue"
                    reason = "Close date passed"
                else:
                    flag = "stale"
                    reason = "No activity in 14+ days"
                flagged_deals.append({"id": deal.get("id"), "name": name, "flag": flag, "reason": reason})

        # Recommendations
        recommendations = []
        if flagged_deals:
            recommendations.append(f"Follow up on {len(flagged_deals)} flagged deal(s)")
        if deal_count > 0 and weighted_forecast < total_value * 0.5:
            recommendations.append("Push to move deals into later stages")

        # Format the response
        blocks, fallback = format_pipeline_response(
            total_value=total_value,
            deal_count=deal_count,
            weighted_forecast=weighted_forecast,
            deals_by_stage=deals_by_stage,
            flagged_deals=flagged_deals,
            recommendations=recommendations,
        )

        # Post as ephemeral message (Slack best practice)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text=fallback
        )
    except Exception as e:
        import logging
        logging.error(f"Pipeline action error: {e}")
        # Post error as ephemeral so only the user sees it
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Couldn't load pipeline data. Error: {str(e)}"
        )


@app.action("view_full_pipeline")
def handle_view_full_pipeline_action(ack, body, client):
    """Handle View Full Pipeline button from /my-day inline preview."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    # Same implementation as quick_pipeline
    handle_quick_pipeline_action(ack, body, client)


@app.action("view_flagged_deals")
def handle_view_flagged_deals_action(ack, body, client):
    """Handle See Flagged Deals button from /my-day inline preview."""
    ack()
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        from formatters.pipeline_summary import get_flagged_deals_detail

        flagged = get_flagged_deals_detail(user_id)

        if flagged:
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Flagged Deals", "emoji": True}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Found {len(flagged)} deals that need attention:"}
                }
            ]

            for deal in flagged[:5]:  # Show top 5
                flag_emoji = {"stale": "⏰", "overdue": "🚨", "at_risk": "⚠️"}
                emoji = flag_emoji.get(deal.get("flag", "at_risk"), "⚠️")
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{deal.get('name', 'Unknown')}*\n{deal.get('reason', 'Needs attention')}"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Deal"},
                        "action_id": "view_deal_from_flagged",
                        "value": deal.get("id", "")
                    }
                })

            if len(flagged) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"...and {len(flagged) - 5} more. Use `/pipeline` for full view."}
                    ]
                })

            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                blocks=blocks,
                text=f"Flagged Deals: {len(flagged)} deals need attention"
            )
        else:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="Great news! No flagged deals — your pipeline looks healthy."
            )
    except Exception as e:
        import traceback
        print(f"ERROR in handle_view_flagged_deals_action: {e}")
        print(traceback.format_exc())
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Couldn't load flagged deals: {str(e)}. Try `/pipeline` for the full view."
        )


@app.action(re.compile(r"^prep_meeting_"))
def handle_prep_meeting_action(ack, body, client):
    """Prep for a meeting from /my-day."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("prep_meeting_", "")
    deal_id = body["actions"][0].get("value", "")
    channel_id = body["channel"]["id"]

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Meeting not found.")
            return

        deal_info = None
        if deal_id:
            deal = mock_crm.get_deal_by_id(deal_id)
            if deal:
                deal_info = {
                    "name": deal.get("properties", {}).get("dealname", "Unknown"),
                    "stage": deal.get("properties", {}).get("dealstage", "Unknown"),
                    "amount": deal.get("properties", {}).get("amount", 0)
                }

        blocks = format_meeting_prep(event, deal_info, deal_id=deal_id)
        client.chat_postMessage(channel=channel_id, blocks=blocks, text=f"Prep: {event['title']}")
    except Exception as e:
        handle_action_error(client, channel_id, "prep_meeting", e)


@app.action(re.compile(r"^join_training_"))
def handle_join_training_action(ack, body, client):
    """Join a training session from /my-day."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("join_training_", "")
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Training event not found.")
            return

        cohort_id = event.get("cohort_id", "")

        # Check if there are pending assignments for this user
        assignments = get_user_assignments(user_id, status="pending")
        if assignments:
            # Show the first pending assignment with a start button
            a = assignments[0]
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Training: {event['title']}*\n"
                            f"_{event.get('notes', '')}_\n\n"
                            f"Your next assignment: *{a['scenario_name']}* "
                            f"({a['scenario_type'].replace('_', ' ').title()} · {a['scenario_difficulty'].title()})"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Start Practice"},
                            "action_id": "start_saved_scenario",
                            "value": a["scenario_id"],
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View All Assignments"},
                            "action_id": "quick_practice"
                        }
                    ]
                }
            ]
            client.chat_postMessage(channel=channel_id, blocks=blocks, text=f"Training: {event['title']}")
        else:
            # No assignments — suggest quick practice
            client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"*Training: {event['title']}*\n"
                    f"_{event.get('notes', '')}_\n\n"
                    f"No pending assignments. Use `/training library` to browse scenarios or `/coach roleplay` for a quick session."
                )
            )
    except Exception as e:
        handle_action_error(client, channel_id, "join_training", e)


def build_meeting_roleplay_context(event, deal_info=None):
    """Build roleplay scenario and persona from meeting context.

    Args:
        event: Calendar event dict
        deal_info: Optional deal data from CRM

    Returns:
        tuple: (scenario_type, persona_dict, methodology)
    """
    title = event.get("title", "Sales Meeting")
    attendees = event.get("attendees", [])
    notes = event.get("notes", "")

    # Infer scenario type from title
    title_lower = title.lower()
    if "demo" in title_lower:
        scenario_type = "demo"
        methodology = "discovery"
    elif "discovery" in title_lower:
        scenario_type = "discovery"
        methodology = "discovery"
    elif "negotiation" in title_lower or "contract" in title_lower or "pricing" in title_lower:
        scenario_type = "negotiation"
        methodology = "negotiation"
    elif "qbr" in title_lower or "review" in title_lower:
        scenario_type = "qbr"
        methodology = "discovery"
    elif "cold" in title_lower:
        scenario_type = "cold_call"
        methodology = "cold_call"
    else:
        scenario_type = "discovery"
        methodology = "discovery"

    # Extract company name from title or attendees
    company_name = "the prospect"
    if " - " in title:
        company_name = title.split(" - ")[-1].strip()
    elif attendees:
        # Extract domain from first attendee email
        domain = attendees[0].split("@")[-1].split(".")[0]
        company_name = domain.replace("_", " ").title()

    # Build persona from first attendee
    persona_name = "Alex Chen"  # Default
    if attendees:
        email = attendees[0]
        name_part = email.split("@")[0]
        # Convert alex.rivera to Alex Rivera
        persona_name = " ".join(p.title() for p in name_part.replace(".", " ").replace("_", " ").split())

    # Infer title from notes or meeting type
    notes_lower = notes.lower()
    if "engineering" in notes_lower or "technical" in notes_lower:
        persona_title = "Engineering Lead"
    elif "legal" in notes_lower:
        persona_title = "Legal Counsel"
    elif "cto" in notes_lower or "cio" in notes_lower:
        persona_title = "CTO"
    elif "cfo" in notes_lower or "finance" in notes_lower:
        persona_title = "CFO"
    else:
        persona_title = "VP of Operations"

    persona = {
        "name": persona_name,
        "title": persona_title,
        "company": company_name,
    }

    return scenario_type, persona, methodology


def get_personality_for_role(role):
    """Return personality traits based on buyer role."""
    personalities = {
        "VP of Operations": "Analytical, results-driven, skeptical of new vendors",
        "Engineering Lead": "Technical, detail-focused, wants proof of performance",
        "CTO": "Strategic, technical, concerned about integration and scale",
        "CFO": "ROI-focused, skeptical of costs, needs hard numbers",
        "Procurement Manager": "Process-driven, focused on compliance and pricing",
        "Legal Counsel": "Cautious, compliance-focused, detail-oriented",
    }
    return personalities.get(role, "Professional and analytical")


@app.action(re.compile(r"^practice_for_meeting_"))
def handle_practice_for_meeting_action(ack, body, client):
    """Open modal to customize practice scenario for a meeting."""
    ack()
    action_id = body["actions"][0]["action_id"]
    event_id = action_id.replace("practice_for_meeting_", "")
    deal_id = body["actions"][0].get("value", "")
    trigger_id = body["trigger_id"]
    channel_id = body["channel"]["id"]

    print(f"[DEBUG practice_for_meeting] channel_id={channel_id}, event_id={event_id}")

    try:
        from tools.calendar import get_event_by_id
        event = get_event_by_id(event_id)

        if not event:
            client.chat_postMessage(channel=channel_id, text="Meeting not found.")
            return

        # Auto-infer scenario and persona
        scenario_type, persona, _ = build_meeting_roleplay_context(event)

        # Open modal with inferred values
        from formatters.calendar import format_practice_scenario_modal
        modal = format_practice_scenario_modal(event, scenario_type, persona, deal_id, channel_id)
        client.views_open(trigger_id=trigger_id, view=modal)

    except Exception as e:
        handle_action_error(client, channel_id, "practice_for_meeting", e)


@app.view("practice_scenario_modal")
def handle_practice_scenario_modal_submit(ack, body, client, view):
    """Process practice scenario modal and start roleplay."""
    ack()
    user_id = body["user"]["id"]

    try:
        # Extract form values
        values = view["state"]["values"]
        scenario_type = values["scenario_type"]["scenario_select"]["selected_option"]["value"]
        buyer_name = values["buyer_name"]["name_input"]["value"]
        buyer_role = values["buyer_role"]["role_select"]["selected_option"]["value"]
        max_turns = int(values["turns"]["turns_select"]["selected_option"]["value"])

        # Get metadata
        metadata = json.loads(view.get("private_metadata", "{}"))
        company = metadata.get("company", "the prospect")
        notes = metadata.get("notes", "")
        channel_id = metadata.get("channel_id", "")

        print(f"[DEBUG modal_submit] metadata={metadata}")
        print(f"[DEBUG modal_submit] channel_id from metadata={channel_id}")

        # Build scenario string
        scenario_labels = {
            "discovery": "discovery call",
            "demo": "product demo",
            "negotiation": "negotiation",
            "cold_call": "cold call",
            "competitive": "competitive deal",
            "qbr": "quarterly business review",
        }
        scenario = f"{scenario_labels.get(scenario_type, scenario_type)} for {company}"
        if notes:
            scenario += f" - {notes}"

        # Build persona
        persona = {
            "name": buyer_name,
            "title": buyer_role,
            "company": company,
            "personality": get_personality_for_role(buyer_role),
        }

        # Map scenario type to methodology
        methodology_map = {
            "discovery": "discovery",
            "demo": "discovery",
            "negotiation": "negotiation",
            "cold_call": "cold_call",
            "competitive": "competitive",
            "qbr": "discovery",
        }
        methodology = methodology_map.get(scenario_type, "discovery")

        log_engagement(user_id, "action", action_id="practice_scenario_start",
                      scenario_type=scenario_type, company=company)

        # Use the original channel where user clicked Practice Scenario
        if not channel_id:
            # Fallback to DM if channel_id not available
            dm = client.conversations_open(users=[user_id])
            channel_id = dm["channel"]["id"]

        # Format and post roleplay start message
        from formatters.coach import format_roleplay_start
        blocks, fallback = format_roleplay_start(persona, scenario)
        result_msg = client.chat_postMessage(
            channel=channel_id,
            text=fallback,
            blocks=blocks
        )
        thread_ts = result_msg["ts"]

        # Invoke roleplay graph
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/coach roleplay {scenario}")],
            "route": "coach",
            "workflow": "roleplay",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
        })

        # Post buyer's opening in thread
        response_text = result["messages"][-1].content
        client.chat_postMessage(
            channel=channel_id,
            text=response_text,
            thread_ts=thread_ts
        )

        # Store active roleplay state
        active_roleplays[thread_ts] = {
            "messages": result["messages"],
            "turn_count": 1,
            "max_turns": max_turns,
            "rag_context": result.get("rag_context", ""),
            "user_id": user_id,
            "channel_id": channel_id,
            "scenario": scenario,
            "company": company,
            "persona_name": persona.get("name", ""),
        }

    except Exception as e:
        # Log error - can't easily message user from view handler
        print(f"Error in practice_scenario_modal: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Sales AI Agent is running with Block Kit formatting!")
    handler.start()
