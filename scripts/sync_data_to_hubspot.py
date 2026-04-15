#!/usr/bin/env python3
"""
Sync existing synthetic CRM data FROM JSON files INTO HubSpot.

Reads the exact data from data/mock_crm/*.json and pushes those exact records
to HubSpot - same names, amounts, stages, close dates, contacts, activities.

Usage:
    python scripts/sync_data_to_hubspot.py              # Push all data
    python scripts/sync_data_to_hubspot.py --dry-run    # Preview only
    python scripts/sync_data_to_hubspot.py --clean      # Delete synced records
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from hubspot import HubSpot
from hubspot.crm.companies import SimplePublicObjectInputForCreate as CompanyInput
from hubspot.crm.contacts import SimplePublicObjectInputForCreate as ContactInput
from hubspot.crm.deals import SimplePublicObjectInputForCreate as DealInput
from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate as NoteInput
from hubspot.crm.objects.meetings import SimplePublicObjectInputForCreate as MeetingInput
from hubspot.crm.objects.emails import SimplePublicObjectInputForCreate as EmailInput
from hubspot.crm.associations.v4 import BatchInputPublicDefaultAssociationMultiPost

# HubSpot employee count mapping (ranges -> midpoint integers)
EMPLOYEE_COUNT_MAP = {
    "1-10": "5",
    "10-50": "30",
    "50-100": "75",
    "100-250": "175",
    "250-500": "375",
    "500-1000": "750",
    "1000-5000": "3000",
    "5000+": "7500",
}

# HubSpot industry mapping (JSON labels -> HubSpot enum values)
INDUSTRY_MAP = {
    "enterprise software": "COMPUTER_SOFTWARE",
    "data analytics": "INFORMATION_TECHNOLOGY_AND_SERVICES",
    "healthcare tech": "HOSPITAL_HEALTH_CARE",
    "manufacturing": "MACHINERY",
    "cloud infrastructure": "INFORMATION_TECHNOLOGY_AND_SERVICES",
    "supply chain": "LOGISTICS_AND_SUPPLY_CHAIN",
    "financial services": "FINANCIAL_SERVICES",
    "retail tech": "RETAIL",
    "clean energy": "RENEWABLES_ENVIRONMENT",
    "edtech": "E_LEARNING",
}

# HubSpot deal stage mapping (JSON labels -> HubSpot internal IDs)
STAGE_MAP = {
    "discovery": "appointmentscheduled",
    "qualification": "qualifiedtobuy",
    "demo_scheduled": "presentationscheduled",
    "demo scheduled": "presentationscheduled",
    "demoscheduled": "presentationscheduled",
    "proposal_sent": "decisionmakerboughtin",
    "proposal sent": "decisionmakerboughtin",
    "proposalsent": "decisionmakerboughtin",
    "negotiation": "contractsent",
    "closed_won": "closedwon",
    "closedwon": "closedwon",
    "closed_lost": "closedlost",
    "closedlost": "closedlost",
}

# Association type IDs
ASSOC_CONTACT_TO_COMPANY = 279
ASSOC_DEAL_TO_COMPANY = 341
ASSOC_DEAL_TO_CONTACT = 3
ASSOC_NOTE_TO_DEAL = 214
ASSOC_MEETING_TO_DEAL = 212
ASSOC_MEETING_TO_CONTACT = 200
ASSOC_MEETING_TO_COMPANY = 188
ASSOC_EMAIL_TO_DEAL = 210
ASSOC_EMAIL_TO_CONTACT = 198
ASSOC_EMAIL_TO_COMPANY = 186

# Properties to skip when pushing to HubSpot
SKIP_PROPERTIES = {
    "createdate",
    "lastmodifieddate",
    "hs_lastmodifieddate",
    "dealstage_label",
    "hubspot_owner_id",  # Would need to map to real owner IDs
}

# Data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MOCK_CRM_DIR = os.path.join(DATA_DIR, "mock_crm")
ID_MAPPING_FILE = os.path.join(DATA_DIR, "hubspot_synced_ids.json")


def load_json_data():
    """Load all JSON data files."""
    with open(os.path.join(MOCK_CRM_DIR, "companies.json")) as f:
        companies = json.load(f)

    with open(os.path.join(MOCK_CRM_DIR, "contacts.json")) as f:
        contacts = json.load(f)

    with open(os.path.join(MOCK_CRM_DIR, "deals.json")) as f:
        deals = json.load(f)

    # Load meetings (optional file)
    meetings_path = os.path.join(MOCK_CRM_DIR, "meetings.json")
    if os.path.exists(meetings_path):
        with open(meetings_path) as f:
            meetings = json.load(f)
    else:
        meetings = []

    # Load email threads (all JSON files in email_threads/)
    emails = []
    email_dir = os.path.join(MOCK_CRM_DIR, "email_threads")
    if os.path.exists(email_dir):
        for filename in os.listdir(email_dir):
            if filename.endswith(".json"):
                with open(os.path.join(email_dir, filename)) as f:
                    emails.append(json.load(f))

    return companies, contacts, deals, meetings, emails


def filter_properties(props: dict, object_type: str = "general") -> dict:
    """Filter out properties that shouldn't be pushed to HubSpot."""
    filtered = {}
    for key, value in props.items():
        if key in SKIP_PROPERTIES:
            continue
        if key.startswith("_"):  # Skip internal flags like _test_flag
            continue
        if value is None:
            continue

        # Map industry to HubSpot enum value
        if key == "industry" and value:
            value = INDUSTRY_MAP.get(value.lower(), "COMPUTER_SOFTWARE")

        # Map employee count ranges to integers
        if key == "numberofemployees" and value:
            value = EMPLOYEE_COUNT_MAP.get(value, value)

        filtered[key] = str(value) if value is not None else ""
    return filtered


def create_companies(client: HubSpot, companies: list, dry_run: bool = False) -> dict:
    """Create companies in HubSpot. Returns mapping of local_id -> hubspot_id."""
    print(f"\n--- Creating Companies ({len(companies)} records) ---")
    mapping = {}
    success_count = 0

    for company in companies:
        local_id = company["id"]
        props = filter_properties(company.get("properties", {}))
        name = props.get("name", local_id)

        # Add tag for cleanup
        props["hs_lead_status"] = "NEW"  # HubSpot requires valid enum values

        if dry_run:
            print(f"  [DRY-RUN] Would create: {name}")
            mapping[local_id] = f"dry_run_{local_id}"
            continue

        try:
            result = client.crm.companies.basic_api.create(
                simple_public_object_input_for_create=CompanyInput(properties=props)
            )
            hubspot_id = result.id
            mapping[local_id] = hubspot_id
            print(f"  + {name} -> HubSpot ID: {hubspot_id}")
            success_count += 1
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"  x Failed to create {name}: {e}")

    print(f"  -> {success_count}/{len(companies)} companies created")
    return mapping


def create_contacts(client: HubSpot, contacts: list, company_mapping: dict, dry_run: bool = False) -> dict:
    """Create contacts in HubSpot. Returns mapping of local_id -> hubspot_id."""
    print(f"\n--- Creating Contacts ({len(contacts)} records) ---")
    mapping = {}
    success_count = 0

    for contact in contacts:
        local_id = contact["id"]
        props = filter_properties(contact.get("properties", {}))
        name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
        company_name = props.get("company", "")

        # Remove company property (it's just a text field, we use association instead)
        props.pop("company", None)

        if dry_run:
            print(f"  [DRY-RUN] Would create: {name} ({company_name})")
            mapping[local_id] = f"dry_run_{local_id}"
            continue

        try:
            result = client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=ContactInput(properties=props)
            )
            hubspot_id = result.id
            mapping[local_id] = hubspot_id
            print(f"  + {name} ({company_name}) -> HubSpot ID: {hubspot_id}")
            success_count += 1

            # Associate to company
            company_local_id = contact.get("associations", {}).get("company_id")
            if company_local_id and company_local_id in company_mapping:
                company_hubspot_id = company_mapping[company_local_id]
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="contacts",
                        object_id=hubspot_id,
                        to_object_type="companies",
                        to_object_id=company_hubspot_id,
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_CONTACT_TO_COMPANY}]
                    )
                except Exception as assoc_e:
                    print(f"    ! Association failed: {assoc_e}")

            time.sleep(0.1)
        except Exception as e:
            if "409" in str(e) or "CONFLICT" in str(e).upper():
                print(f"  ~ {name} already exists (conflict), skipping")
            else:
                print(f"  x Failed to create {name}: {e}")

    print(f"  -> {success_count}/{len(contacts)} contacts created")
    return mapping


def create_deals(client: HubSpot, deals: list, company_mapping: dict, contact_mapping: dict, dry_run: bool = False) -> dict:
    """Create deals in HubSpot. Returns mapping of local_id -> hubspot_id."""
    print(f"\n--- Creating Deals ({len(deals)} records) ---")
    mapping = {}
    success_count = 0

    for deal in deals:
        local_id = deal["id"]
        props = filter_properties(deal.get("properties", {}))
        deal_name = props.get("dealname", local_id)
        amount = props.get("amount", "0")
        stage_label = props.get("dealstage", "discovery").lower()

        # Map stage to HubSpot internal ID
        props["dealstage"] = STAGE_MAP.get(stage_label, "appointmentscheduled")

        # Add description tag for cleanup
        if "description" in props:
            props["description"] = f"[SYNTHETIC] {props['description']}"
        else:
            props["description"] = "[SYNTHETIC] Test deal created by sync script"

        if dry_run:
            print(f"  [DRY-RUN] Would create: {deal_name} (${amount})")
            mapping[local_id] = f"dry_run_{local_id}"
            continue

        try:
            result = client.crm.deals.basic_api.create(
                simple_public_object_input_for_create=DealInput(properties=props)
            )
            hubspot_id = result.id
            mapping[local_id] = hubspot_id
            print(f"  + {deal_name} (${int(float(amount)):,}) -> HubSpot ID: {hubspot_id}")
            success_count += 1

            # Associate to company
            company_local_id = deal.get("associations", {}).get("company")
            if company_local_id and company_local_id in company_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="deals",
                        object_id=hubspot_id,
                        to_object_type="companies",
                        to_object_id=company_mapping[company_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_DEAL_TO_COMPANY}]
                    )
                except Exception as e:
                    print(f"    ! Company association failed: {e}")

            # Associate to contact
            contact_local_id = deal.get("associations", {}).get("contact")
            if contact_local_id and contact_local_id in contact_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="deals",
                        object_id=hubspot_id,
                        to_object_type="contacts",
                        to_object_id=contact_mapping[contact_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_DEAL_TO_CONTACT}]
                    )
                except Exception as e:
                    print(f"    ! Contact association failed: {e}")

            time.sleep(0.1)
        except Exception as e:
            print(f"  x Failed to create {deal_name}: {e}")

    print(f"  -> {success_count}/{len(deals)} deals created")
    return mapping


def create_notes(client: HubSpot, deals: list, deal_mapping: dict, dry_run: bool = False) -> int:
    """Create notes for each deal's activities. Returns total notes created."""
    total_activities = sum(len(d.get("activities", [])) for d in deals)
    print(f"\n--- Creating Notes ({total_activities} activities) ---")

    if total_activities == 0:
        print("  No activities to create")
        return 0

    notes_created = 0

    for deal in deals:
        local_id = deal["id"]
        deal_name = deal.get("properties", {}).get("dealname", local_id)
        activities = deal.get("activities", [])

        if not activities:
            continue

        hubspot_deal_id = deal_mapping.get(local_id)
        if not hubspot_deal_id or hubspot_deal_id.startswith("dry_run_"):
            if dry_run:
                print(f"  [DRY-RUN] Would create {len(activities)} notes for \"{deal_name}\"")
                notes_created += len(activities)
            continue

        deal_notes_created = 0
        for activity in activities:
            body = activity.get("body", "")
            timestamp_str = activity.get("timestamp", datetime.now().isoformat())
            activity_type = activity.get("type", "NOTE")

            # Convert ISO timestamp to Unix milliseconds for HubSpot
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamp_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                timestamp_ms = int(datetime.now().timestamp() * 1000)

            # Prefix with activity type
            note_body = f"[{activity_type}] {body}"

            props = {
                "hs_timestamp": str(timestamp_ms),
                "hs_note_body": note_body,
            }

            try:
                result = client.crm.objects.notes.basic_api.create(
                    simple_public_object_input_for_create=NoteInput(properties=props)
                )
                note_id = result.id

                # Associate note to deal
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="notes",
                        object_id=note_id,
                        to_object_type="deals",
                        to_object_id=hubspot_deal_id,
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_NOTE_TO_DEAL}]
                    )
                except Exception as e:
                    print(f"    ! Note association failed: {e}")

                deal_notes_created += 1
                notes_created += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"    x Failed to create note: {e}")

        if deal_notes_created > 0:
            print(f"  + {deal_notes_created} notes for \"{deal_name[:50]}\"")

    print(f"  -> {notes_created} notes created")
    return notes_created


def create_meetings(client: HubSpot, meetings: list, deal_mapping: dict, contact_mapping: dict, company_mapping: dict, dry_run: bool = False) -> dict:
    """Create meetings in HubSpot. Returns mapping of local_id -> hubspot_id."""
    print(f"\n--- Creating Meetings ({len(meetings)} records) ---")
    mapping = {}
    success_count = 0

    for meeting in meetings:
        local_id = meeting["id"]
        props = meeting.get("properties", {})
        title = props.get("title", local_id)

        # Convert timestamps to HubSpot format (Unix milliseconds)
        start_time = props.get("start_time", "")
        end_time = props.get("end_time", "")

        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_ms = int(start_dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            start_ms = int(datetime.now().timestamp() * 1000)

        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            end_ms = int(end_dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            end_ms = start_ms + 3600000  # Default 1 hour

        hubspot_props = {
            "hs_timestamp": str(start_ms),
            "hs_meeting_title": title,
            "hs_meeting_body": props.get("summary", ""),
            "hs_meeting_start_time": str(start_ms),
            "hs_meeting_end_time": str(end_ms),
            "hs_meeting_outcome": "COMPLETED" if props.get("outcome") == "completed" else "SCHEDULED",
        }

        if dry_run:
            print(f"  [DRY-RUN] Would create: {title}")
            mapping[local_id] = f"dry_run_{local_id}"
            continue

        try:
            result = client.crm.objects.meetings.basic_api.create(
                simple_public_object_input_for_create=MeetingInput(properties=hubspot_props)
            )
            hubspot_id = result.id
            mapping[local_id] = hubspot_id
            print(f"  + {title[:50]} -> HubSpot ID: {hubspot_id}")
            success_count += 1

            associations = meeting.get("associations", {})

            # Associate to deal
            deal_local_id = associations.get("deal_id")
            if deal_local_id and deal_local_id in deal_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="meetings",
                        object_id=hubspot_id,
                        to_object_type="deals",
                        to_object_id=deal_mapping[deal_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_DEAL}]
                    )
                except Exception as e:
                    print(f"    ! Deal association failed: {e}")

            # Associate to contacts
            contact_ids = associations.get("contact_ids", [])
            for contact_local_id in contact_ids:
                if contact_local_id in contact_mapping:
                    try:
                        client.crm.associations.v4.basic_api.create(
                            object_type="meetings",
                            object_id=hubspot_id,
                            to_object_type="contacts",
                            to_object_id=contact_mapping[contact_local_id],
                            association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_CONTACT}]
                        )
                    except Exception as e:
                        print(f"    ! Contact association failed: {e}")

            # Associate to company
            company_local_id = associations.get("company_id")
            if company_local_id and company_local_id in company_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="meetings",
                        object_id=hubspot_id,
                        to_object_type="companies",
                        to_object_id=company_mapping[company_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_COMPANY}]
                    )
                except Exception as e:
                    print(f"    ! Company association failed: {e}")

            time.sleep(0.1)
        except Exception as e:
            print(f"  x Failed to create {title}: {e}")

    print(f"  -> {success_count}/{len(meetings)} meetings created")
    return mapping


def create_emails(client: HubSpot, email_threads: list, deal_mapping: dict, contact_mapping: dict, company_mapping: dict, dry_run: bool = False) -> int:
    """Create emails from email threads in HubSpot. Returns count of emails created."""
    total_emails = sum(len(t.get("messages", [])) for t in email_threads)
    print(f"\n--- Creating Emails ({total_emails} messages from {len(email_threads)} threads) ---")

    if total_emails == 0:
        print("  No emails to create")
        return 0

    emails_created = 0

    for thread in email_threads:
        thread_id = thread.get("thread_id", "unknown")
        subject = thread.get("subject", "No subject")
        messages = thread.get("messages", [])

        for msg in messages:
            from_email = msg.get("from", "")
            to_emails = msg.get("to", [])
            cc_emails = msg.get("cc", [])
            body = msg.get("body", "")
            date_str = msg.get("date", "")

            # Convert timestamp
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                timestamp_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                timestamp_ms = int(datetime.now().timestamp() * 1000)

            # Determine direction (INCOMING or OUTGOING based on sender domain)
            direction = "OUTGOING" if "ourcompany.com" in from_email else "INCOMING"

            hubspot_props = {
                "hs_timestamp": str(timestamp_ms),
                "hs_email_subject": subject,
                "hs_email_text": body,
                "hs_email_direction": direction,
                "hs_email_status": "SENT",
            }

            if dry_run:
                print(f"  [DRY-RUN] Would create email: {subject[:40]}...")
                emails_created += 1
                continue

            try:
                result = client.crm.objects.emails.basic_api.create(
                    simple_public_object_input_for_create=EmailInput(properties=hubspot_props)
                )
                hubspot_id = result.id
                emails_created += 1

                # Try to associate with contacts by email address
                all_emails = [from_email] + to_emails + cc_emails
                for email_addr in all_emails:
                    # Look up contact by matching email in our mapping (simplified approach)
                    # In a real scenario, you'd search HubSpot by email
                    pass

                time.sleep(0.1)
            except Exception as e:
                print(f"  x Failed to create email: {e}")

        if not dry_run:
            print(f"  + {len(messages)} emails from thread \"{subject[:40]}...\"")

    print(f"  -> {emails_created} emails created")
    return emails_created


def save_mapping(mapping: dict):
    """Save the ID mapping to a JSON file."""
    with open(ID_MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"\nID mapping saved to: {ID_MAPPING_FILE}")


def load_mapping() -> dict:
    """Load the ID mapping from JSON file."""
    if os.path.exists(ID_MAPPING_FILE):
        with open(ID_MAPPING_FILE) as f:
            return json.load(f)
    return {}


def clean_synced_records(client: HubSpot, dry_run: bool = False):
    """Delete all synced records using the saved ID mapping."""
    print("\n--- Cleaning Synced Records ---")

    mapping = load_mapping()
    if not mapping:
        print("No ID mapping found. Nothing to clean.")
        return

    # Delete in reverse order: meetings, notes, deals, contacts, companies
    for object_type in ["meetings", "notes", "deals", "contacts", "companies"]:
        ids = mapping.get(object_type, {})
        if not ids:
            continue

        print(f"\nDeleting {len(ids)} {object_type}...")
        deleted = 0

        for local_id, hubspot_id in ids.items():
            if hubspot_id.startswith("dry_run_"):
                continue

            if dry_run:
                print(f"  [DRY-RUN] Would delete {object_type} {hubspot_id}")
                deleted += 1
                continue

            try:
                if object_type == "companies":
                    client.crm.companies.basic_api.archive(company_id=hubspot_id)
                elif object_type == "contacts":
                    client.crm.contacts.basic_api.archive(contact_id=hubspot_id)
                elif object_type == "deals":
                    client.crm.deals.basic_api.archive(deal_id=hubspot_id)
                elif object_type == "notes":
                    client.crm.objects.notes.basic_api.archive(note_id=hubspot_id)
                elif object_type == "meetings":
                    client.crm.objects.meetings.basic_api.archive(meeting_id=hubspot_id)

                deleted += 1
                time.sleep(0.1)
            except Exception as e:
                if "404" not in str(e):
                    print(f"  x Failed to delete {hubspot_id}: {e}")

        print(f"  -> {deleted}/{len(ids)} {object_type} deleted")

    # Clear the mapping file
    if not dry_run:
        os.remove(ID_MAPPING_FILE)
        print(f"\nCleared ID mapping file")


def main():
    parser = argparse.ArgumentParser(description="Sync synthetic CRM data to HubSpot")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating records")
    parser.add_argument("--clean", action="store_true", help="Delete all synced records")
    args = parser.parse_args()

    # Check for HubSpot token
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        print("Error: HUBSPOT_ACCESS_TOKEN not set in environment")
        sys.exit(1)

    # Initialize HubSpot client
    client = HubSpot(access_token=token)

    print("=" * 60)
    if args.dry_run:
        print("DRY RUN - Previewing changes (no records will be created)")
    elif args.clean:
        print("Cleaning Synced Records from HubSpot")
    else:
        print("Syncing Synthetic Data to HubSpot")
    print("=" * 60)

    if args.clean:
        clean_synced_records(client, dry_run=args.dry_run)
        return

    # Load data
    companies, contacts, deals, meetings, emails = load_json_data()
    print(f"\nLoaded: {len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals, {len(meetings)} meetings, {len(emails)} email threads")

    # Create records
    company_mapping = create_companies(client, companies, dry_run=args.dry_run)
    contact_mapping = create_contacts(client, contacts, company_mapping, dry_run=args.dry_run)
    deal_mapping = create_deals(client, deals, company_mapping, contact_mapping, dry_run=args.dry_run)
    notes_count = create_notes(client, deals, deal_mapping, dry_run=args.dry_run)
    meeting_mapping = create_meetings(client, meetings, deal_mapping, contact_mapping, company_mapping, dry_run=args.dry_run)
    emails_count = create_emails(client, emails, deal_mapping, contact_mapping, company_mapping, dry_run=args.dry_run)

    # Save mapping
    full_mapping = {
        "companies": company_mapping,
        "contacts": contact_mapping,
        "deals": deal_mapping,
        "meetings": meeting_mapping,
        "synced_at": datetime.now().isoformat(),
    }

    if not args.dry_run:
        save_mapping(full_mapping)

    # Summary
    print("\n" + "=" * 60)
    print("Sync complete!" if not args.dry_run else "Dry run complete!")
    print(f"  Companies: {len(company_mapping)} | Contacts: {len(contact_mapping)} | Deals: {len(deal_mapping)}")
    print(f"  Notes: {notes_count} | Meetings: {len(meeting_mapping)} | Emails: {emails_count}")
    if not args.dry_run:
        print(f"  ID mapping saved to: {ID_MAPPING_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
