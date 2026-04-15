# Claude Code Instructions: Seed HubSpot with Synthetic CRM Data

> **Read `CLAUDE-CODE-BRIEFING.md` first** if you haven't already.
> **Read `scripts/generate_test_data.py`** — this is the existing synthetic data generator. The new script will reuse its data structures.

---

## CONTEXT — WHAT AND WHY

We already have a synthetic data generator (`scripts/generate_test_data.py`) that creates mock CRM data as local JSON files (companies, contacts, deals, activities). These are used for local testing when HubSpot MCP isn't connected.

Now we want to **also push that same synthetic data into a real HubSpot account** so the pilot has realistic CRM records to work with. This lets us test the full MCP pipeline end-to-end with data that tells coherent storylines.

### Why NOT use HubSpot MCP for this?

The official `@hubspot/mcp-server` (npm) is **read-only** — it exposes `hubspot-search-objects` and `hubspot-list-objects` but no create/update tools. This is a known limitation of the current public beta.

### What to use instead

Use the **HubSpot Python SDK** (`hubspot-api-client`) directly. It provides full CRUD access and is actually better for bulk data creation — no MCP overhead, direct API calls, batch support.

---

## STEP 1: Install the HubSpot Python SDK

Add `hubspot-api-client` to `requirements.txt`:

```
hubspot-api-client>=9.0.0
```

Install it:

```bash
pip install hubspot-api-client --break-system-packages
```

The env var `HUBSPOT_ACCESS_TOKEN` is already in `.env` (used by the MCP server). The Python SDK uses the same token.

### HubSpot Private App Scopes

The Private App token needs **write scopes** in addition to the existing read scopes. Go to HubSpot → Settings → Integrations → Private Apps → your app → Scopes, and enable:

- `crm.objects.contacts.write` (in addition to `.read`)
- `crm.objects.companies.write`
- `crm.objects.deals.write`
- `crm.objects.notes.write` (may appear as `crm.objects.engagements.write`)

**IMPORTANT:** If using a production HubSpot account, create a **sandbox account** first (HubSpot → Settings → Account Management → Sandboxes). Seed data into the sandbox, not production. HubSpot provides free development sandboxes.

---

## STEP 2: Create `scripts/seed_hubspot.py`

Create a new script that:
1. Reads the same `COMPANIES`, `FIRST_NAMES`, `LAST_NAMES`, `TITLES`, `DEAL_STAGES` seed data from `generate_test_data.py`
2. Uses the HubSpot Python SDK to create records via the API
3. Creates companies first, then contacts (linked to companies), then deals (linked to companies + contacts), then notes (linked to deals)
4. Tracks created record IDs so associations can be made
5. Includes a `--clean` flag to delete all seeded records

### File: `scripts/seed_hubspot.py`

```python
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
from hubspot.crm.associations.v4 import (
    BatchInputPublicAssociationMultiPost,
    PublicAssociationMultiPost,
    AssociationSpec,
)

# Reuse seed data from generate_test_data.py
from scripts.generate_test_data import (
    COMPANIES,
    FIRST_NAMES,
    LAST_NAMES,
    TITLES,
    DEAL_STAGES,
    DEAL_STAGE_WEIGHTS,
)
```

### Key implementation details:

**Company creation:**
```python
def create_companies(client: HubSpot, dry_run: bool = False) -> dict:
    """Create companies in HubSpot. Returns {company_name: hubspot_id}."""
    created = {}
    for company in COMPANIES:
        properties = {
            "name": company["name"],
            "domain": company["domain"],
            "industry": company["industry"],
            "numberofemployees": company["size"],
            "city": company["hq"].split(", ")[0],
            "state": company["hq"].split(", ")[1] if ", " in company["hq"] else "",
            "description": f"{company['name']} is a {company['industry'].lower()} company headquartered in {company['hq']}.",
            # Tag as synthetic so we can find/delete later
            "hs_lead_status": "SYNTHETIC_TEST_DATA",
        }

        if dry_run:
            print(f"  [DRY RUN] Would create company: {company['name']}")
            created[company["name"]] = f"dry_run_{company['name']}"
            continue

        result = client.crm.companies.basic_api.create(
            simple_public_object_input_for_create=CompanyInput(properties=properties)
        )
        created[company["name"]] = result.id
        print(f"  Created company: {company['name']} (ID: {result.id})")
        time.sleep(0.1)  # Rate limit safety

    return created
```

**Contact creation with company association:**
```python
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
                # Tag as synthetic
                "hs_lead_status": "SYNTHETIC_TEST_DATA",
            }

            if dry_run:
                key = f"{first}_{last}_{company['name']}"
                print(f"  [DRY RUN] Would create contact: {first} {last} at {company['name']}")
                created[key] = f"dry_run_{key}"
                continue

            result = client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=ContactInput(properties=properties)
            )
            key = f"{first}_{last}_{company['name']}"
            created[key] = result.id
            print(f"  Created contact: {first} {last} at {company['name']} (ID: {result.id})")

            # Associate contact with company
            if company_id and company_id != f"dry_run_{company['name']}":
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

    return created
```

**Deal creation with associations:**
```python
def create_deals(client: HubSpot, company_ids: dict, contact_ids: dict, dry_run: bool = False) -> dict:
    """Create deals linked to companies and contacts. Returns {deal_name: hubspot_id}."""
    created = {}
    deal_templates = [
        "{company} — Annual Platform License",
        "{company} — Enterprise Expansion",
        "{company} — Pilot Program",
    ]

    # HubSpot deal stage IDs vary per account — use default pipeline stage labels
    # The SDK accepts stage labels if using the default pipeline
    stage_map = {
        "Discovery": "appointmentscheduled",
        "Qualification": "qualifiedtobuy",
        "Demo Scheduled": "presentationscheduled",
        "Proposal Sent": "decisionmakerboughtin",
        "Negotiation": "contractsent",
        "Closed Won": "closedwon",
        "Closed Lost": "closedlost",
    }

    for company in COMPANIES:
        company_id = company_ids.get(company["name"])
        deal_name = random.choice(deal_templates).format(company=company["name"])
        stage = random.choices(DEAL_STAGES, weights=DEAL_STAGE_WEIGHTS, k=1)[0]
        amount = random.choice([15000, 24000, 36000, 48000, 72000, 96000, 120000])
        close_date = (datetime.now() + timedelta(days=random.randint(-30, 90))).strftime("%Y-%m-%d")

        properties = {
            "dealname": deal_name,
            "amount": str(amount),
            "dealstage": stage_map.get(stage, "appointmentscheduled"),
            "pipeline": "default",
            "closedate": close_date,
            "description": f"Synthetic test deal with {company['name']}. Stage: {stage}.",
            # Tag as synthetic — use description since deals don't have hs_lead_status
        }

        if dry_run:
            print(f"  [DRY RUN] Would create deal: {deal_name} ({stage}, ${amount:,})")
            created[deal_name] = f"dry_run_{deal_name}"
            continue

        result = client.crm.deals.basic_api.create(
            simple_public_object_input_for_create=DealInput(properties=properties)
        )
        created[deal_name] = result.id
        print(f"  Created deal: {deal_name} ({stage}, ${amount:,}) (ID: {result.id})")

        # Associate deal with company
        if company_id:
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

    return created
```

**Note creation (engagement activities):**
```python
def create_notes(client: HubSpot, deal_ids: dict, dry_run: bool = False) -> int:
    """Create notes/engagements attached to deals. Returns count created."""
    count = 0
    note_templates = [
        "Discovery call completed. Prospect is evaluating our platform against 2 competitors. Main pain: inconsistent sales coaching across the team. Budget approved for Q1.",
        "Demo completed. Prospect impressed with AI roleplay feature. Their CTO asked about data security. Sent SOC 2 report. Next: technical review with IT.",
        "Proposal sent. Three-tier pricing. Recommended Professional plan. Included custom ROI model showing 340% return over 12 months.",
        "Negotiation call. Prospect wants 15% discount. Offered 10% for annual commitment + case study agreement. Decision expected next week.",
        "Follow-up: procurement approved the budget. Legal reviewing MSA. Target implementation start: 1st of next month.",
        "Competitor alert: prospect also evaluating CompetitorAlpha. Their demo is next Tuesday. Sending battle card to champion.",
    ]

    for deal_name, deal_id in deal_ids.items():
        if deal_id.startswith("dry_run_"):
            continue

        # Create 2-4 notes per deal
        num_notes = random.randint(2, 4)
        selected_notes = random.sample(note_templates, min(num_notes, len(note_templates)))

        for i, note_body in enumerate(selected_notes):
            days_ago = (i + 1) * 7  # Space notes a week apart
            timestamp = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            properties = {
                "hs_timestamp": timestamp,
                "hs_note_body": note_body,
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

    print(f"  Created {count} notes across {len(deal_ids)} deals")
    return count
```

**Cleanup function:**
```python
def clean_synthetic_data(client: HubSpot):
    """Delete all records tagged as synthetic test data."""
    print("\n--- Cleaning synthetic data from HubSpot ---")

    # Search for contacts with SYNTHETIC_TEST_DATA tag
    from hubspot.crm.contacts import PublicObjectSearchRequest
    search_request = PublicObjectSearchRequest(
        filter_groups=[{
            "filters": [{
                "propertyName": "hs_lead_status",
                "operator": "EQ",
                "value": "SYNTHETIC_TEST_DATA",
            }]
        }],
        limit=100,
    )

    # Delete contacts
    try:
        results = client.crm.contacts.search_api.do_search(public_object_search_request=search_request)
        for record in results.results:
            client.crm.contacts.basic_api.archive(contact_id=record.id)
            print(f"  Deleted contact: {record.id}")
            time.sleep(0.1)
    except Exception as e:
        print(f"  Error cleaning contacts: {e}")

    # Delete companies
    try:
        from hubspot.crm.companies import PublicObjectSearchRequest as CompanySearch
        results = client.crm.companies.search_api.do_search(
            public_object_search_request=CompanySearch(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "hs_lead_status",
                        "operator": "EQ",
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
    except Exception as e:
        print(f"  Error cleaning companies: {e}")

    # Delete deals with "Synthetic test deal" in description
    try:
        from hubspot.crm.deals import PublicObjectSearchRequest as DealSearch
        results = client.crm.deals.search_api.do_search(
            public_object_search_request=DealSearch(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "description",
                        "operator": "CONTAINS_TOKEN",
                        "value": "Synthetic test deal",
                    }]
                }],
                limit=100,
            )
        )
        for record in results.results:
            client.crm.deals.basic_api.archive(deal_id=record.id)
            print(f"  Deleted deal: {record.id}")
            time.sleep(0.1)
    except Exception as e:
        print(f"  Error cleaning deals: {e}")

    print("  Cleanup complete.")
```

**Main function:**
```python
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
        print("  HubSpot → Settings → Integrations → Private Apps")
        sys.exit(1)

    # Initialize HubSpot client
    client = HubSpot(access_token=token)

    if args.clean:
        clean_synthetic_data(client)
        return

    print("=" * 60)
    print("Seeding HubSpot with Synthetic CRM Data")
    if args.dry_run:
        print("*** DRY RUN — no records will be created ***")
    print("=" * 60)

    # Create in order: companies → contacts → deals → notes
    print("\n--- Creating Companies ---")
    company_ids = create_companies(client, args.dry_run)
    print(f"  → {len(company_ids)} companies")

    print("\n--- Creating Contacts ---")
    contact_ids = create_contacts(client, company_ids, args.dry_run)
    print(f"  → {len(contact_ids)} contacts")

    print("\n--- Creating Deals ---")
    deal_ids = create_deals(client, company_ids, contact_ids, args.dry_run)
    print(f"  → {len(deal_ids)} deals")

    print("\n--- Creating Notes ---")
    note_count = create_notes(client, deal_ids, args.dry_run)
    print(f"  → {note_count} notes")

    # Save created IDs for reference / cleanup
    if not args.dry_run:
        id_map = {
            "companies": company_ids,
            "contacts": contact_ids,
            "deals": deal_ids,
            "seeded_at": datetime.now().isoformat(),
        }
        id_file = os.path.join(os.path.dirname(__file__), "..", "data", "hubspot_seeded_ids.json")
        with open(id_file, "w") as f:
            json.dump(id_map, f, indent=2)
        print(f"\n  Saved record IDs to: data/hubspot_seeded_ids.json")

    print("\n" + "=" * 60)
    print("Done! Your HubSpot account now has synthetic test data.")
    print("=" * 60)

    print("\nNext steps:")
    print("  1. Sync HubSpot → RAG:  python scripts/sync_hubspot_to_rag.py")
    print("  2. Start the bot:       python app.py")
    print("  3. Test:                 /research NovaTech Solutions")
    print(f"\n  To clean up later:     python scripts/seed_hubspot.py --clean")


if __name__ == "__main__":
    main()
```

---

## STEP 3: Update `generate_test_data.py` — Add HubSpot seeding option

Add a `--hubspot` CLI flag to the existing generator so it can optionally push data to HubSpot after generating local files.

At the bottom of `generate_test_data.py`, update `main()` to accept arguments:

```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data")
    parser.add_argument("--hubspot", action="store_true",
                        help="Also seed data into HubSpot (requires HUBSPOT_ACCESS_TOKEN)")
    args = parser.parse_args()

    # ... existing generation code (unchanged) ...

    # NEW: optionally push to HubSpot
    if args.hubspot:
        print("\n--- Seeding HubSpot ---")
        try:
            from scripts.seed_hubspot import main as seed_main
            # Temporarily replace sys.argv so seed_hubspot doesn't parse our args
            import sys
            old_argv = sys.argv
            sys.argv = ["seed_hubspot.py"]
            seed_main()
            sys.argv = old_argv
        except ImportError:
            print("  hubspot-api-client not installed. Run: pip install hubspot-api-client")
        except Exception as e:
            print(f"  HubSpot seeding failed: {e}")
            print("  Local test data was still generated successfully.")
```

This way, the user can run either:
- `python scripts/generate_test_data.py` — local files only (existing behavior)
- `python scripts/generate_test_data.py --hubspot` — local files + push to HubSpot
- `python scripts/seed_hubspot.py` — push to HubSpot only (standalone)

---

## STEP 4: Update `.env.example`

Add a comment noting that write scopes are needed for seeding:

```bash
# HubSpot (for MCP server + data seeding)
# Read scopes: crm.objects.contacts.read, companies.read, deals.read, notes.read
# Write scopes (for seeding only): crm.objects.contacts.write, companies.write, deals.write, notes.write
HUBSPOT_ACCESS_TOKEN=pat-your-private-app-token
```

---

## WHAT GETS CREATED IN HUBSPOT

After running `python scripts/seed_hubspot.py`:

| Object | Count | Details |
|--------|-------|---------|
| Companies | 10 | NovaTech, Greenfield, Meridian, Apex, CloudBridge, TerraLogistics, Pinnacle, Velocity, Stratos, Horizon |
| Contacts | 15-30 | 1-3 per company, with realistic names, titles, emails |
| Deals | 10 | 1 per company, various stages and amounts ($15K-$120K) |
| Notes | 20-40 | 2-4 per deal, realistic sales activity notes spaced a week apart |

All records are tagged with `SYNTHETIC_TEST_DATA` in the `hs_lead_status` field (contacts/companies) or `"Synthetic test deal"` in the description (deals), so they can be found and cleaned up with `--clean`.

Associations:
- Each contact → its company
- Each deal → its company
- Each note → its deal

---

## COMPLETE PILOT DATA FLOW

After seeding, the full flow is:

```
1. python scripts/seed_hubspot.py          # Push synthetic data INTO HubSpot
2. python scripts/sync_hubspot_to_rag.py   # Pull data FROM HubSpot into ChromaDB
3. python scripts/index_playbooks.py       # Index playbooks (also triggers CRM sync)
4. python app.py                           # Start the bot

Now in Slack:
  /research NovaTech Solutions    → pulls from RAG (synced HubSpot data) + live MCP + web search
  /deal NovaTech — Annual License → pulls deal context from RAG + live MCP
  /coach roleplay discovery call  → uses playbooks from RAG
  /pipeline                      → analyzes deals from RAG + live MCP
```

---

## GOTCHAS

1. **Association type IDs** — HubSpot uses numeric IDs for association types. The common ones are:
   - Contact → Company: `279` (primary)
   - Deal → Company: `341` (primary)
   - Deal → Contact: `3`
   - Note → Deal: `214`
   - Note → Contact: `202`
   These IDs are for the default HubSpot schema. If your account uses custom association types, the IDs will differ. Check your HubSpot account's association settings or use the Associations API to list available types.

2. **Deal stage IDs** — HubSpot's default pipeline uses internal stage IDs like `appointmentscheduled`, `qualifiedtobuy`, `presentationscheduled`, `decisionmakerboughtin`, `contractsent`, `closedwon`, `closedlost`. These are specific to the default Sales Pipeline. If your account has custom pipelines/stages, you need to map to those IDs. Use the Pipelines API to list your stages: `client.crm.pipelines.pipelines_api.get_all(object_type="deals")`.

3. **Rate limiting** — HubSpot allows ~100 requests/10 seconds for Private Apps. The `time.sleep(0.1)` calls add a safety buffer. For 10 companies + 20 contacts + 10 deals + 30 notes = ~70 API calls, this takes about 10 seconds.

4. **Duplicate detection** — HubSpot deduplicates contacts by email. If you run the script twice, contacts with the same generated email will fail. Use `--clean` first, or the script should handle `409 Conflict` errors gracefully.

5. **Sandbox accounts** — Strongly recommended for pilot testing. Create one at HubSpot → Settings → Account Management → Sandboxes. Free for all HubSpot tiers. Use a separate Private App token for the sandbox.

6. **Cleaning up** — `python scripts/seed_hubspot.py --clean` searches for records tagged `SYNTHETIC_TEST_DATA` and deletes them. Notes are harder to clean because HubSpot's note search is limited — they get deleted when their associated deal is deleted (cascading).

7. **The `hubspot-api-client` import structure** is deeply nested. The exact import paths may differ slightly across versions. If imports fail, check the installed version with `pip show hubspot-api-client` and consult the [HubSpot Python SDK docs](https://github.com/HubSpot/hubspot-api-python).

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `scripts/seed_hubspot.py` | New script: pushes synthetic CRM data into HubSpot via Python SDK |
| EDIT | `scripts/generate_test_data.py` | Add `--hubspot` CLI flag that optionally triggers HubSpot seeding after local file generation |
| EDIT | `requirements.txt` | Add `hubspot-api-client>=9.0.0` |
| EDIT | `.env.example` | Add comment about write scopes needed for seeding |

---

## DEPENDENCY NOTE

Add to `requirements.txt`:
```
hubspot-api-client>=9.0.0
```

This is ONLY needed for the seeding script. The rest of the app uses the HubSpot MCP server (which is an npm package, not pip). So `hubspot-api-client` is a dev/setup dependency, not a runtime dependency.
