"""
Seed a HubSpot account with synthetic CRM data for pilot testing.

Uses the same company/contact/deal data as generate_test_data.py but
pushes it into a real HubSpot account via the HubSpot Python SDK.

Usage:
    python scripts/seed_hubspot.py              # Create all records
    python scripts/seed_hubspot.py --clean      # Delete seeded records
    python scripts/seed_hubspot.py --dry-run    # Preview without creating

Prerequisites:
    - HUBSPOT_ACCESS_TOKEN in .env (Private App with read+write scopes)
    - pip install hubspot-api-client
"""

import os
import sys
import json
import time
import argparse
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from hubspot import HubSpot
from hubspot.crm.companies import SimplePublicObjectInputForCreate as CompanyInput
from hubspot.crm.contacts import SimplePublicObjectInputForCreate as ContactInput
from hubspot.crm.deals import SimplePublicObjectInputForCreate as DealInput
from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate as NoteInput
from hubspot.crm.associations.v4 import AssociationSpec

# ---------------------------------------------------------------------------
# SEED DATA — reused from generate_test_data.py
# ---------------------------------------------------------------------------
COMPANIES = [
    {"name": "NovaTech Solutions", "domain": "novatech.io", "industry": "COMPUTER_SOFTWARE", "size": "250-500", "hq": "Austin, TX"},
    {"name": "Greenfield Analytics", "domain": "greenfieldanalytics.com", "industry": "INFORMATION_TECHNOLOGY_AND_SERVICES", "size": "50-100", "hq": "Denver, CO"},
    {"name": "Meridian Healthcare", "domain": "meridianhc.com", "industry": "HOSPITAL_HEALTH_CARE", "size": "1000-5000", "hq": "Boston, MA"},
    {"name": "Apex Manufacturing", "domain": "apexmfg.com", "industry": "INDUSTRIAL_AUTOMATION", "size": "500-1000", "hq": "Detroit, MI"},
    {"name": "CloudBridge Systems", "domain": "cloudbridge.dev", "industry": "INTERNET", "size": "100-250", "hq": "San Francisco, CA"},
    {"name": "TerraLogistics", "domain": "terralogistics.com", "industry": "LOGISTICS_AND_SUPPLY_CHAIN", "size": "250-500", "hq": "Chicago, IL"},
    {"name": "Pinnacle Financial Group", "domain": "pinnaclefg.com", "industry": "FINANCIAL_SERVICES", "size": "500-1000", "hq": "New York, NY"},
    {"name": "Velocity Retail", "domain": "velocityretail.co", "industry": "RETAIL", "size": "100-250", "hq": "Seattle, WA"},
    {"name": "Stratos Energy", "domain": "stratosenergy.com", "industry": "OIL_ENERGY", "size": "50-100", "hq": "Houston, TX"},
    {"name": "Horizon Education", "domain": "horizonedu.org", "industry": "E_LEARNING", "size": "50-100", "hq": "Portland, OR"},
]

FIRST_NAMES = ["Sarah", "James", "Maria", "David", "Lisa", "Michael", "Priya", "Carlos", "Emma", "Wei",
               "Rachel", "Tom", "Fatima", "Alex", "Nina", "Robert", "Aisha", "Daniel", "Yuki", "Marcus"]

LAST_NAMES = ["Chen", "Williams", "Patel", "Rodriguez", "Thompson", "Kim", "O'Brien", "Nakamura",
              "Fischer", "Okafor", "Santos", "Johansson", "Ahmed", "Kowalski", "Dubois", "Singh"]

TITLES = ["VP of Engineering", "CTO", "Head of Operations", "CFO", "Director of IT",
          "VP of Sales", "Chief Data Officer", "Head of Procurement", "CEO", "Director of Digital Transformation"]

DEAL_STAGES = ["Discovery", "Qualification", "Demo Scheduled", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost"]
DEAL_STAGE_WEIGHTS = [0.15, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05]

# HubSpot deal stage IDs for default pipeline
STAGE_MAP = {
    "Discovery": "appointmentscheduled",
    "Qualification": "qualifiedtobuy",
    "Demo Scheduled": "presentationscheduled",
    "Proposal Sent": "decisionmakerboughtin",
    "Negotiation": "contractsent",
    "Closed Won": "closedwon",
    "Closed Lost": "closedlost",
}

NOTE_TEMPLATES = [
    "Discovery call completed. Prospect is evaluating our platform against 2 competitors. Main pain: inconsistent sales coaching across the team. Budget approved for Q1.",
    "Demo completed. Prospect impressed with AI roleplay feature. Their CTO asked about data security. Sent SOC 2 report. Next: technical review with IT.",
    "Proposal sent. Three-tier pricing. Recommended Professional plan. Included custom ROI model showing 340% return over 12 months.",
    "Negotiation call. Prospect wants 15% discount. Offered 10% for annual commitment + case study agreement. Decision expected next week.",
    "Follow-up: procurement approved the budget. Legal reviewing MSA. Target implementation start: 1st of next month.",
    "Competitor alert: prospect also evaluating CompetitorAlpha. Their demo is next Tuesday. Sending battle card to champion.",
]


# ---------------------------------------------------------------------------
# CREATION FUNCTIONS
# ---------------------------------------------------------------------------

def create_companies(client: HubSpot, dry_run: bool = False) -> dict:
    """Create companies in HubSpot. Returns {company_name: hubspot_id}."""
    created = {}
    for company in COMPANIES:
        hq_parts = company["hq"].split(", ")
        city = hq_parts[0] if hq_parts else ""
        state = hq_parts[1] if len(hq_parts) > 1 else ""

        properties = {
            "name": company["name"],
            "domain": company["domain"],
            "industry": company["industry"],
            "numberofemployees": company["size"].split("-")[0],  # Use lower bound
            "city": city,
            "state": state,
            "description": f"{company['name']} is a {company['industry'].lower()} company headquartered in {company['hq']}. [SYNTHETIC_TEST_DATA]",
        }

        if dry_run:
            print(f"  [DRY RUN] Would create company: {company['name']}")
            created[company["name"]] = f"dry_run_{company['name']}"
            continue

        try:
            result = client.crm.companies.basic_api.create(
                simple_public_object_input_for_create=CompanyInput(properties=properties)
            )
            created[company["name"]] = result.id
            print(f"  Created company: {company['name']} (ID: {result.id})")
            time.sleep(0.1)  # Rate limit safety
        except Exception as e:
            print(f"  Error creating company {company['name']}: {e}")

    return created


def create_contacts(client: HubSpot, company_ids: dict, dry_run: bool = False) -> dict:
    """Create contacts linked to companies. Returns {contact_key: hubspot_id}."""
    created = {}
    for company in COMPANIES:
        company_id = company_ids.get(company["name"])
        num_contacts = random.randint(1, 3)

        for i in range(num_contacts):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            title = random.choice(TITLES)

            properties = {
                "firstname": first,
                "lastname": last,
                "email": f"{first.lower()}.{last.lower()}@{company['domain']}",
                "jobtitle": title,
                "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
                "company": company["name"],
                "lifecyclestage": random.choice(["lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity"]),
                "hs_lead_status": "NEW",
                # Tag in company field for cleanup identification
            }

            if dry_run:
                key = f"{first}_{last}_{company['name']}"
                print(f"  [DRY RUN] Would create contact: {first} {last} at {company['name']}")
                created[key] = f"dry_run_{key}"
                continue

            try:
                result = client.crm.contacts.basic_api.create(
                    simple_public_object_input_for_create=ContactInput(properties=properties)
                )
                key = f"{first}_{last}_{company['name']}"
                created[key] = result.id
                print(f"  Created contact: {first} {last} at {company['name']} (ID: {result.id})")

                # Associate contact with company
                if company_id and not company_id.startswith("dry_run_"):
                    try:
                        client.crm.associations.v4.basic_api.create(
                            object_type="contacts",
                            object_id=result.id,
                            to_object_type="companies",
                            to_object_id=company_id,
                            association_spec=[AssociationSpec(
                                association_category="HUBSPOT_DEFINED",
                                association_type_id=279,  # Contact to Company (primary)
                            )]
                        )
                    except Exception as e:
                        print(f"    Warning: Could not associate contact to company: {e}")

                time.sleep(0.1)
            except Exception as e:
                print(f"  Error creating contact {first} {last}: {e}")

    return created


def create_deals(client: HubSpot, company_ids: dict, dry_run: bool = False) -> dict:
    """Create deals linked to companies. Returns {deal_name: hubspot_id}."""
    created = {}
    deal_templates = [
        "{company} - Annual Platform License",
        "{company} - Enterprise Expansion",
        "{company} - Pilot Program",
    ]

    for company in COMPANIES:
        company_id = company_ids.get(company["name"])
        deal_name = random.choice(deal_templates).format(company=company["name"])
        stage = random.choices(DEAL_STAGES, weights=DEAL_STAGE_WEIGHTS, k=1)[0]
        amount = random.choice([15000, 24000, 36000, 48000, 72000, 96000, 120000])
        close_date = (datetime.now() + timedelta(days=random.randint(-30, 90))).strftime("%Y-%m-%d")

        properties = {
            "dealname": deal_name,
            "amount": str(amount),
            "dealstage": STAGE_MAP.get(stage, "appointmentscheduled"),
            "pipeline": "default",
            "closedate": close_date,
            "description": f"Synthetic test deal with {company['name']}. Stage: {stage}. [SYNTHETIC_TEST_DATA]",
        }

        if dry_run:
            print(f"  [DRY RUN] Would create deal: {deal_name} ({stage}, ${amount:,})")
            created[deal_name] = f"dry_run_{deal_name}"
            continue

        try:
            result = client.crm.deals.basic_api.create(
                simple_public_object_input_for_create=DealInput(properties=properties)
            )
            created[deal_name] = result.id
            print(f"  Created deal: {deal_name} ({stage}, ${amount:,}) (ID: {result.id})")

            # Associate deal with company
            if company_id and not company_id.startswith("dry_run_"):
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="deals",
                        object_id=result.id,
                        to_object_type="companies",
                        to_object_id=company_id,
                        association_spec=[AssociationSpec(
                            association_category="HUBSPOT_DEFINED",
                            association_type_id=341,  # Deal to Company (primary)
                        )]
                    )
                except Exception as e:
                    print(f"    Warning: Could not associate deal to company: {e}")

            time.sleep(0.1)
        except Exception as e:
            print(f"  Error creating deal {deal_name}: {e}")

    return created


def create_notes(client: HubSpot, deal_ids: dict, dry_run: bool = False) -> int:
    """Create notes/engagements attached to deals. Returns count created."""
    count = 0

    for deal_name, deal_id in deal_ids.items():
        if deal_id.startswith("dry_run_"):
            continue

        # Create 2-4 notes per deal
        num_notes = random.randint(2, 4)
        selected_notes = random.sample(NOTE_TEMPLATES, min(num_notes, len(NOTE_TEMPLATES)))

        for i, note_body in enumerate(selected_notes):
            days_ago = (i + 1) * 7  # Space notes a week apart
            timestamp = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            properties = {
                "hs_timestamp": timestamp,
                "hs_note_body": note_body + " [SYNTHETIC_TEST_DATA]",
            }

            if dry_run:
                print(f"  [DRY RUN] Would create note for {deal_name}")
                count += 1
                continue

            try:
                result = client.crm.objects.notes.basic_api.create(
                    simple_public_object_input_for_create=NoteInput(
                        properties=properties,
                        associations=[{
                            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}],
                            "to": {"id": deal_id},
                        }],
                    )
                )
                count += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"    Warning: Could not create note for {deal_name}: {e}")

    print(f"  Created {count} notes across {len([d for d in deal_ids.values() if not d.startswith('dry_run_')])} deals")
    return count


# ---------------------------------------------------------------------------
# CLEANUP FUNCTIONS
# ---------------------------------------------------------------------------

def clean_synthetic_data(client: HubSpot):
    """Delete all records tagged as synthetic test data."""
    print("\n--- Cleaning synthetic data from HubSpot ---")

    # Delete contacts by matching company names from our seed data
    print("\nDeleting contacts...")
    total_deleted = 0
    try:
        from hubspot.crm.contacts import PublicObjectSearchRequest
        for company in COMPANIES:
            search_request = PublicObjectSearchRequest(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "company",
                        "operator": "EQ",
                        "value": company["name"],
                    }]
                }],
                limit=100,
            )
            results = client.crm.contacts.search_api.do_search(public_object_search_request=search_request)
            for record in results.results:
                client.crm.contacts.basic_api.archive(contact_id=record.id)
                print(f"  Deleted contact: {record.id}")
                total_deleted += 1
                time.sleep(0.1)
        print(f"  Deleted {total_deleted} contacts")
    except Exception as e:
        print(f"  Error cleaning contacts: {e}")

    # Delete deals with SYNTHETIC_TEST_DATA in description
    print("\nDeleting deals...")
    try:
        from hubspot.crm.deals import PublicObjectSearchRequest as DealSearch
        results = client.crm.deals.search_api.do_search(
            public_object_search_request=DealSearch(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "description",
                        "operator": "CONTAINS_TOKEN",
                        "value": "SYNTHETIC_TEST_DATA",
                    }]
                }],
                limit=100,
            )
        )
        for record in results.results:
            client.crm.deals.basic_api.archive(deal_id=record.id)
            print(f"  Deleted deal: {record.id}")
            time.sleep(0.1)
        print(f"  Deleted {len(results.results)} deals")
    except Exception as e:
        print(f"  Error cleaning deals: {e}")

    # Delete companies with SYNTHETIC_TEST_DATA in description
    print("\nDeleting companies...")
    try:
        from hubspot.crm.companies import PublicObjectSearchRequest as CompanySearch
        results = client.crm.companies.search_api.do_search(
            public_object_search_request=CompanySearch(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "description",
                        "operator": "CONTAINS_TOKEN",
                        "value": "SYNTHETIC_TEST_DATA",
                    }]
                }],
                limit=100,
            )
        )
        for record in results.results:
            client.crm.companies.basic_api.archive(company_id=record.id)
            print(f"  Deleted company: {record.id}")
            time.sleep(0.1)
        print(f"  Deleted {len(results.results)} companies")
    except Exception as e:
        print(f"  Error cleaning companies: {e}")

    print("\n  Cleanup complete.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed HubSpot with synthetic CRM data")
    parser.add_argument("--clean", action="store_true", help="Delete all seeded records")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    args = parser.parse_args()

    # Verify environment
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        print("ERROR: HUBSPOT_ACCESS_TOKEN not found in .env")
        print("Get a Private App token with read+write scopes from:")
        print("  HubSpot -> Settings -> Integrations -> Private Apps")
        sys.exit(1)

    # Initialize HubSpot client
    client = HubSpot(access_token=token)

    if args.clean:
        clean_synthetic_data(client)
        return

    print("=" * 60)
    print("Seeding HubSpot with Synthetic CRM Data")
    if args.dry_run:
        print("*** DRY RUN - no records will be created ***")
    print("=" * 60)

    # Create in order: companies -> contacts -> deals -> notes
    print("\n--- Creating Companies ---")
    company_ids = create_companies(client, args.dry_run)
    print(f"  -> {len(company_ids)} companies")

    print("\n--- Creating Contacts ---")
    contact_ids = create_contacts(client, company_ids, args.dry_run)
    print(f"  -> {len(contact_ids)} contacts")

    print("\n--- Creating Deals ---")
    deal_ids = create_deals(client, company_ids, args.dry_run)
    print(f"  -> {len(deal_ids)} deals")

    print("\n--- Creating Notes ---")
    note_count = create_notes(client, deal_ids, args.dry_run)
    print(f"  -> {note_count} notes")

    # Save created IDs for reference / cleanup
    if not args.dry_run:
        id_map = {
            "companies": company_ids,
            "contacts": contact_ids,
            "deals": deal_ids,
            "seeded_at": datetime.now().isoformat(),
        }
        id_file = os.path.join(os.path.dirname(__file__), "..", "data", "hubspot_seeded_ids.json")
        os.makedirs(os.path.dirname(id_file), exist_ok=True)
        with open(id_file, "w") as f:
            json.dump(id_map, f, indent=2)
        print(f"\n  Saved record IDs to: data/hubspot_seeded_ids.json")

    print("\n" + "=" * 60)
    print("Done! Your HubSpot account now has synthetic test data.")
    print("=" * 60)

    print("\nNext steps:")
    print("  1. Sync HubSpot -> RAG:  python scripts/sync_hubspot_to_rag.py")
    print("  2. Start the bot:        python app.py")
    print("  3. Test:                 /research NovaTech Solutions")
    print(f"\n  To clean up later:      python scripts/seed_hubspot.py --clean")


if __name__ == "__main__":
    main()
