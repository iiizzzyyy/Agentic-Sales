# Task: Sync Existing Synthetic Data FROM JSON Files INTO HubSpot

> **Read these files FIRST before writing any code:**
> 1. `CLAUDE-CODE-BRIEFING.md` — overall architecture
> 2. `data/mock_crm/companies.json` — the exact company records to push
> 3. `data/mock_crm/contacts.json` — the exact contact records to push
> 4. `data/mock_crm/deals.json` — the exact deal records to push (includes activities/notes)
> 5. `SEED-HUBSPOT-INSTRUCTIONS.md` — reference for HubSpot Python SDK patterns, association type IDs, and deal stage mapping (but do NOT follow that script's approach of regenerating random data)

---

## WHAT AND WHY

We have synthetic CRM data in `data/mock_crm/` — companies, contacts, and deals with activities — that the Slack bot currently reads from local JSON. The bot shows data like "Horizon Education — Professional Services Add-On, $36K, close date March 8th" but that data only exists locally, NOT in HubSpot.

We need a script that reads the **exact existing JSON files** and pushes those **exact same records** into HubSpot — same names, same amounts, same stages, same close dates, same contacts, same activity notes. Not regenerated. Not randomized. A mirror.

---

## WHAT TO BUILD

Create `scripts/sync_data_to_hubspot.py` — a script that:

1. Reads `data/mock_crm/companies.json` and creates each company in HubSpot with the exact same properties
2. Reads `data/mock_crm/contacts.json` and creates each contact in HubSpot with the exact same properties, associated to the correct company
3. Reads `data/mock_crm/deals.json` and creates each deal in HubSpot with the exact same properties (dealname, amount, stage, close date, description), associated to the correct company and contact
4. For each deal, reads its `activities` array and creates Notes in HubSpot with the exact same body text and timestamps, associated to the deal
5. Saves a mapping of `{local_id: hubspot_id}` to `data/hubspot_synced_ids.json` for reference
6. Includes `--dry-run` flag to preview without creating
7. Includes `--clean` flag to delete all synced records

---

## KEY IMPLEMENTATION DETAILS

### Reading the JSON files (NOT regenerating)

```python
import json

# Read the EXISTING data — do NOT regenerate
with open("data/mock_crm/companies.json") as f:
    companies = json.load(f)

with open("data/mock_crm/contacts.json") as f:
    contacts = json.load(f)

with open("data/mock_crm/deals.json") as f:
    deals = json.load(f)
```

### Company creation — use exact properties from JSON

For each company in `companies.json`, the structure is:
```json
{
    "id": "novatech_solutions",
    "properties": {
        "name": "NovaTech Solutions",
        "domain": "novatech.io",
        "industry": "Enterprise Software",
        "numberofemployees": "250-500",
        "city": "Austin",
        "state": "TX",
        "annualrevenue": "15000000",
        "description": "..."
    }
}
```

Push ALL properties from `company["properties"]` into HubSpot. Map the local `company["id"]` to the returned HubSpot ID.

Tag each record for cleanup: set `hs_lead_status` to `"SYNTHETIC_TEST_DATA"`.

### Contact creation — use exact properties, associate to correct company

For each contact in `contacts.json`, the structure is:
```json
{
    "id": "contact_123456",
    "properties": {
        "firstname": "Emma",
        "lastname": "Ahmed",
        "email": "emma.ahmed@horizonedu.org",
        "jobtitle": "VP of Operations",
        "phone": "+1-555-123-4567",
        "company": "Horizon Education"
    },
    "associations": {
        "company": "horizon_education"
    }
}
```

Push ALL properties. Use `contact["associations"]["company"]` to look up the company's HubSpot ID from the mapping created in step 1, then create the association.

Association type: Contact → Company = `279`

### Deal creation — use exact properties, associate to company + contact

For each deal in `deals.json`, the structure is:
```json
{
    "id": "deal_642093",
    "properties": {
        "dealname": "Horizon Education — Professional Services Add-On",
        "amount": "36000",
        "dealstage": "negotiation",
        "dealstage_label": "Negotiation",
        "pipeline": "default",
        "closedate": "2026-03-08",
        "description": "Active deal with Horizon Education for platform access."
    },
    "associations": {
        "company": "horizon_education",
        "contact": "contact_575512"
    },
    "activities": [
        {
            "type": "NOTE",
            "body": "Negotiation call. Horizon Education wants a 15% discount...",
            "timestamp": "2026-02-26T06:37:35.658291"
        }
    ]
}
```

**Deal stage mapping** — the JSON uses labels like `"negotiation"`, `"discovery"`, `"demo_scheduled"`, etc. HubSpot's default pipeline uses internal IDs. Map them:

```python
STAGE_MAP = {
    "discovery": "appointmentscheduled",
    "qualification": "qualifiedtobuy",
    "demo_scheduled": "presentationscheduled",
    "demo scheduled": "presentationscheduled",
    "proposal_sent": "decisionmakerboughtin",
    "proposal sent": "decisionmakerboughtin",
    "negotiation": "contractsent",
    "closed_won": "closedwon",
    "closedwon": "closedwon",
    "closed_lost": "closedlost",
    "closedlost": "closedlost",
}
```

Look up `deal["properties"]["dealstage"]` in this map before pushing to HubSpot.

**Associations:**
- Deal → Company: type `341`
- Deal → Contact: type `3`

Use `deal["associations"]["company"]` and `deal["associations"]["contact"]` to look up the HubSpot IDs from the mappings.

### Note/Activity creation — from the deal's `activities` array

For each deal, iterate over `deal["activities"]`. Each activity has `type`, `body`, and `timestamp`.

Create a Note in HubSpot for each:
```python
properties = {
    "hs_timestamp": activity["timestamp"],
    "hs_note_body": activity["body"],
}
```

Associate each note to the deal: Note → Deal = type `214`

### Handle deals with `_test_flag`

Some deals have `"_test_flag": "stale"` or `"_test_flag": "overdue"`. Do NOT push this field to HubSpot (it's not a real HubSpot property). Just skip it when building the properties dict.

### Rate limiting

HubSpot allows ~100 requests/10 seconds. Add `time.sleep(0.1)` between API calls.

### Error handling

- If a contact email already exists in HubSpot (409 Conflict), log a warning and continue
- If an association fails, log a warning and continue (the record still gets created)
- Wrap each API call in try/except to avoid the whole script crashing on one bad record

---

## CLI INTERFACE

```
python scripts/sync_data_to_hubspot.py              # Push all data
python scripts/sync_data_to_hubspot.py --dry-run    # Preview only
python scripts/sync_data_to_hubspot.py --clean      # Delete synced records
```

### Output should look like:

```
============================================================
Syncing Synthetic Data to HubSpot
============================================================

--- Creating Companies (10 records) ---
  ✓ NovaTech Solutions → HubSpot ID: 12345678
  ✓ Greenfield Analytics → HubSpot ID: 12345679
  ...
  → 10/10 companies created

--- Creating Contacts (20 records) ---
  ✓ Emma Ahmed (Horizon Education) → HubSpot ID: 87654321
  ...
  → 20/20 contacts created

--- Creating Deals (15 records) ---
  ✓ Horizon Education — Professional Services Add-On ($36,000, Negotiation) → HubSpot ID: 11111111
  ...
  → 15/15 deals created

--- Creating Notes (45 activities) ---
  ✓ 3 notes for "Horizon Education — Professional Services Add-On"
  ...
  → 45 notes created

============================================================
Sync complete!
  Companies: 10 | Contacts: 20 | Deals: 15 | Notes: 45
  ID mapping saved to: data/hubspot_synced_ids.json
============================================================
```

---

## DEPENDENCIES

The script needs `hubspot-api-client`. Check if it's in `requirements.txt` — if not, add it:

```
hubspot-api-client>=9.0.0
```

Install: `pip install hubspot-api-client --break-system-packages`

The env var `HUBSPOT_ACCESS_TOKEN` must be set in `.env`. The Private App needs these write scopes:
- `crm.objects.contacts.write`
- `crm.objects.companies.write`
- `crm.objects.deals.write`

---

## CLEANUP (`--clean`)

Search for records tagged with `hs_lead_status = "SYNTHETIC_TEST_DATA"` (companies and contacts). For deals, search by description containing `"Synthetic"` or load the ID mapping from `data/hubspot_synced_ids.json` and delete by stored IDs — this is more reliable.

---

## DO NOT

- Do NOT regenerate or randomize data — read the exact JSON files and push those exact records
- Do NOT modify the existing JSON files
- Do NOT modify `generate_test_data.py`
- Do NOT modify `app.py` or any formatter
- Do NOT push `_test_flag` field to HubSpot
- Do NOT push `createdate` or `hs_lastmodifieddate` to HubSpot (HubSpot manages these automatically)
- Do NOT push `dealstage_label` to HubSpot (it's a read-only computed field)

## DO

- Read the exact data from `data/mock_crm/*.json`
- Map local IDs to HubSpot IDs for associations
- Map deal stage labels to HubSpot internal stage IDs
- Tag all records for cleanup identification
- Save the complete ID mapping to `data/hubspot_synced_ids.json`
- Handle errors gracefully (don't crash on one bad record)
- Print clear progress output
