"""
CRM write operations using HubSpot Python SDK.
Falls back to mock mode (SQLite + JSON append) when HUBSPOT_ACCESS_TOKEN is not set.
"""
import os
import json
import time
from datetime import datetime

# Import from parent directory
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import log_crm_write

# Try to import HubSpot SDK
try:
    from hubspot import HubSpot
    from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate as NoteInput
    from hubspot.crm.deals import SimplePublicObjectInput as DealUpdate
    HUBSPOT_SDK_AVAILABLE = True
except ImportError:
    HUBSPOT_SDK_AVAILABLE = False

# Association type IDs (from HubSpot docs)
ASSOC_NOTE_TO_DEAL = 214
ASSOC_NOTE_TO_CONTACT = 202

# Mock CRM data paths
MOCK_CRM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mock_crm")


def _get_hubspot_client():
    """Get HubSpot client if token is available."""
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if token and HUBSPOT_SDK_AVAILABLE:
        return HubSpot(access_token=token)
    return None


def is_mock_mode():
    """Check if we're in mock mode (no HubSpot token)."""
    return _get_hubspot_client() is None


def search_deal_in_hubspot(deal_name: str) -> dict | None:
    """Search for a deal in HubSpot by name or ID.

    Args:
        deal_name: Deal name or ID to search for

    Returns:
        Deal dict from HubSpot or None if not found
    """
    client = _get_hubspot_client()
    if not client:
        return None

    # First, check if this looks like a HubSpot ID (numeric string)
    if deal_name.isdigit() or deal_name.startswith('deal_'):
        # Try direct ID lookup
        try:
            # Strip 'deal_' prefix if present
            clean_id = deal_name.replace('deal_', '')
            deal = client.crm.deals.basic_api.get_by_id(deal_id=clean_id, properties=['dealname', 'amount', 'dealstage', 'closedate'])
            return {
                "id": deal.id,
                "properties": deal.properties,
            }
        except Exception as e:
            print(f"[HubSpot search_deal by ID] Error: {e}")
            # Fall through to name search

    try:
        # Search deals by dealname property
        response = client.crm.deals.search_api.do_search(
            public_object_search_request={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "dealname",
                        "operator": "CONTAINS_TOKEN",
                        "value": deal_name
                    }]
                }],
                "properties": ["dealname", "amount", "dealstage", "closedate"],
                "limit": 10
            }
        )

        if response.results:
            # Return the first match as a dict
            deal = response.results[0]
            return {
                "id": deal.id,
                "properties": deal.properties,
            }
    except Exception as e:
        print(f"[HubSpot search_deal] Error: {e}")

    return None


def search_company_in_hubspot(company_name: str) -> dict | None:
    """Search for a company in HubSpot by name.

    Args:
        company_name: Company name to search for

    Returns:
        Company dict from HubSpot or None if not found
    """
    client = _get_hubspot_client()
    if not client:
        return None

    try:
        response = client.crm.companies.search_api.do_search(
            public_object_search_request={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "name",
                        "operator": "CONTAINS_TOKEN",
                        "value": company_name
                    }]
                }],
                "properties": ["name", "industry", "numberofemployees", "annualrevenue"],
                "limit": 10
            }
        )

        if response.results:
            company = response.results[0]
            return {
                "id": company.id,
                "properties": company.properties,
            }
    except Exception as e:
        print(f"[HubSpot search_company] Error: {e}")

    return None


def create_note(user_id, deal_id, deal_name, note_body, contact_id=None):
    """Create a note and associate it with a deal (and optionally a contact).

    Args:
        user_id: Slack user who created the note
        deal_id: HubSpot deal ID (or mock deal ID)
        deal_name: Human-readable deal name
        note_body: The note text
        contact_id: Optional HubSpot contact ID to associate

    Returns:
        dict with 'success', 'note_id', 'mode' (hubspot/mock)
    """
    client = _get_hubspot_client()
    print(f"[CREATE_NOTE] Called with deal_id={deal_id}, deal_name={deal_name}")
    print(f"[CREATE_NOTE] HubSpot client: {client is not None}")

    if client:
        # --- HubSpot Mode ---
        try:
            print(f"[CREATE_NOTE] Creating note in HubSpot...")
            timestamp_ms = int(datetime.now().timestamp() * 1000)
            result = client.crm.objects.notes.basic_api.create(
                simple_public_object_input_for_create=NoteInput(properties={
                    "hs_timestamp": str(timestamp_ms),
                    "hs_note_body": note_body,
                })
            )
            note_id = result.id
            print(f"[CREATE_NOTE] Note created with ID: {note_id}")

            # Associate note to deal
            try:
                print(f"[CREATE_NOTE] Associating note to deal {deal_id}...")
                client.crm.associations.v4.basic_api.create(
                    object_type="notes",
                    object_id=note_id,
                    to_object_type="deals",
                    to_object_id=deal_id,
                    association_spec=[{
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": ASSOC_NOTE_TO_DEAL
                    }]
                )
                print(f"[CREATE_NOTE] Association successful")
            except Exception as assoc_error:
                print(f"[CREATE_NOTE] Association failed: {assoc_error}")
                # Don't fail the whole operation - note was created

            # Associate note to contact if provided
            if contact_id:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="notes",
                        object_id=note_id,
                        to_object_type="contacts",
                        to_object_id=contact_id,
                        association_spec=[{
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": ASSOC_NOTE_TO_CONTACT
                        }]
                    )
                except Exception:
                    pass

            log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, note_id, "synced")
            return {"success": True, "note_id": note_id, "mode": "hubspot"}

        except Exception as e:
            log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, None, "failed")
            return {"success": False, "error": str(e), "mode": "hubspot"}

    else:
        # --- Mock Mode ---
        note_id = f"mock_note_{int(time.time())}"
        _append_mock_activity(deal_id, {
            "type": "NOTE",
            "body": note_body,
            "timestamp": datetime.now().isoformat(),
            "created_by": user_id,
        })
        log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, note_id, "mock")
        return {"success": True, "note_id": note_id, "mode": "mock"}


def update_deal_stage(user_id, deal_id, deal_name, new_stage):
    """Update a deal's stage in HubSpot.

    Args:
        new_stage: HubSpot internal stage ID (e.g., 'contractsent', 'closedwon')
    """
    client = _get_hubspot_client()

    if client:
        try:
            client.crm.deals.basic_api.update(
                deal_id=deal_id,
                simple_public_object_input=DealUpdate(properties={
                    "dealstage": new_stage
                })
            )
            log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, deal_id, "synced")
            return {"success": True, "mode": "hubspot"}
        except Exception as e:
            log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, None, "failed")
            return {"success": False, "error": str(e), "mode": "hubspot"}
    else:
        _update_mock_deal_stage(deal_id, new_stage)
        log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, deal_id, "mock")
        return {"success": True, "mode": "mock"}


def log_coaching_activity(user_id, deal_id, deal_name, session_type, score, scenario):
    """Log a coaching session as a CRM activity note on a deal."""
    note_body = (
        f"[COACHING] {session_type.title()} session completed\n"
        f"Scenario: {scenario}\n"
        f"Score: {score}/10\n"
        f"Logged automatically by SalesCoach AI"
    )
    return create_note(user_id, deal_id, deal_name, note_body)


# --- Mock Mode Helpers ---

def _append_mock_activity(deal_id, activity):
    """Append an activity to mock CRM deals.json."""
    deals_file = os.path.join(MOCK_CRM_DIR, "deals.json")
    try:
        with open(deals_file, "r") as f:
            deals = json.load(f)

        for deal in deals:
            if deal["id"] == deal_id:
                if "activities" not in deal:
                    deal["activities"] = []
                deal["activities"].append(activity)
                break

        with open(deals_file, "w") as f:
            json.dump(deals, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # Silent fail in mock mode


def _update_mock_deal_stage(deal_id, new_stage):
    """Update a deal's stage in mock CRM deals.json."""
    deals_file = os.path.join(MOCK_CRM_DIR, "deals.json")
    try:
        with open(deals_file, "r") as f:
            deals = json.load(f)

        for deal in deals:
            if deal["id"] == deal_id:
                deal["properties"]["dealstage"] = new_stage
                break

        with open(deals_file, "w") as f:
            json.dump(deals, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
