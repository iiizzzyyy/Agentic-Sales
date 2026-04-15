# Fix /research to Use Real CRM Data — Claude Code Instructions

**Goal:** The `/research` command currently shows "0 contacts · 0 active deals" even when the company has contacts and deals in the CRM. Fix it to pull data directly from the mock CRM instead of relying solely on RAG vector search.

---

## ROOT CAUSE

In `app.py` lines 633-635, the `/research` handler calls:

```python
company_data = extract_company_data(company)   # uses tools.rag.search_crm_companies
contacts = extract_contacts(company)            # uses tools.rag.search_contacts_by_company
deals = extract_deals(company)                  # uses tools.rag.search_deals_by_company
```

These functions search a vector store (ChromaDB) via RAG. When the vector embeddings don't produce good matches, they return 0 results — even though the actual CRM data (`data/mock_crm/contacts.json`, `deals.json`) has the records. For example, DataFlow has 3 contacts and 2 deals in the JSON files but the RAG search returns none.

**The fix:** Try the direct CRM lookup first (which is deterministic and reliable), and only fall back to RAG if nothing is found.

---

## IMPORTANT — Read before editing

- Read `app.py` lines 599-675 (the `/research` handler)
- Read `app.py` lines 238-390 (the `extract_*` functions)
- Read `app.py` lines 293-362 (the `get_contacts_for_deal_or_company` function — already exists!)
- Read `tools/mock_crm.py` lines 49-143 (the direct CRM functions)

---

## STEP 1: Add a `extract_contacts_with_crm_fallback` function in `app.py`

Add this new function right after the existing `extract_contacts` function (after line ~290, before `get_contacts_for_deal_or_company`). Do NOT delete the existing `extract_contacts` — it's still used as a fallback.

```python
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
```

## STEP 2: Add a `extract_deals_with_crm_priority` function in `app.py`

Add this right after the function from Step 1:

```python
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
```

## STEP 3: Also augment `extract_company_data` with CRM fallback

The company data (industry, size, revenue) also comes from RAG and can miss. Add CRM enrichment. Add this function right after the one from Step 2:

```python
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
```

## STEP 4: Update the `/research` handler to use the new functions

In `app.py`, in the `handle_research` function (lines ~633-635), change the three extract calls:

### FIND:

```python
        # Extract structured data
        company_data = extract_company_data(company)
        contacts = extract_contacts(company)
        deals = extract_deals(company)
```

### REPLACE WITH:

```python
        # Extract structured data — CRM direct lookup with RAG fallback
        company_data = extract_company_data_with_crm_priority(company)
        contacts = extract_contacts_with_crm_priority(company)
        deals = extract_deals_with_crm_priority(company)
```

---

## TESTING

1. Run `/research DataFlow` — should now show:
   - **3 contacts** (Priya Sharma, Marcus Chen, Jennifer Liu)
   - **2 active deals** (Enterprise Platform License, Professional Services Engagement)
   - Industry, size, revenue from CRM data
2. Run `/research NovaTech` — should also show CRM contacts and deals
3. Run `/research SomeRandomCompany` — should gracefully fall back to RAG results (may still show 0 if RAG has nothing, which is correct)
4. Click "Show Full Brief" — the expanded view should also show the correct contacts/deals (it uses the same cached data)

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| ADD | `app.py` | 3 new functions: `extract_contacts_with_crm_priority`, `extract_deals_with_crm_priority`, `extract_company_data_with_crm_priority` (add after existing `extract_*` functions, around line 290) |
| EDIT | `app.py` | In `handle_research` (line ~633-635), replace 3 `extract_*` calls with `*_with_crm_priority` versions |

No changes needed to `formatters/research.py` — it already handles the data correctly once it receives actual contacts and deals.
