# EXPANSION: Apollo.io Enrichment for /research Command

## Goal
Add optional Apollo.io enrichment to the `/research` command so that when enabled,
company and contact data is enriched with LinkedIn profiles, employee counts, funding info,
technographics, and verified email addresses from Apollo.io.

This is a POST-POC enhancement. For the demo, keep it OFF by default so that synthetic
company lookups don't return "not found" from Apollo.

## Prerequisites
- Apollo.io MCP connector connected (or Apollo API key)
- Env var: `ENABLE_APOLLO_ENRICHMENT=true` (default: false)
- Env var: `APOLLO_API_KEY=your_key` (if using direct API instead of MCP)

## Architecture

```
/research NovaTech
    │
    ├── CRM Data (mock_crm / HubSpot MCP)         ← always
    ├── RAG Search (playbooks, CRM records)         ← always
    ├── Web Search (Tavily)                         ← if real company
    ├── Mock News (generated)                       ← if demo company
    └── Apollo Enrichment                           ← if ENABLE_APOLLO_ENRICHMENT=true
         ├── Company: funding, headcount, tech stack, LinkedIn URL
         └── Contacts: verified emails, LinkedIn profiles, seniority
```

## What to Build

### Step 1: Create Apollo Enrichment Tool

Create `tools/apollo_enrichment.py`:

```python
"""Apollo.io enrichment for company and contact data.

Supports two modes:
1. MCP mode: Uses Apollo MCP connector tools (preferred)
2. API mode: Direct Apollo API calls (fallback)

Enable via: ENABLE_APOLLO_ENRICHMENT=true
"""

import os
import json
import requests

APOLLO_ENABLED = os.environ.get("ENABLE_APOLLO_ENRICHMENT", "false").lower() == "true"
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
APOLLO_BASE_URL = "https://api.apollo.io/v1"


def is_apollo_enabled() -> bool:
    """Check if Apollo enrichment is enabled and configured."""
    return APOLLO_ENABLED and bool(APOLLO_API_KEY)


def enrich_company(company_name: str, domain: str = None) -> dict | None:
    """Enrich a company with Apollo.io data.

    Args:
        company_name: Company name to search
        domain: Optional domain for more precise matching

    Returns:
        Dict with enriched company data, or None if not found/disabled
    """
    if not is_apollo_enabled():
        return None

    try:
        # Search for the company
        response = requests.post(
            f"{APOLLO_BASE_URL}/organizations/search",
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
            params={"api_key": APOLLO_API_KEY},
            json={
                "q_organization_name": company_name,
                "page": 1,
                "per_page": 1,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        orgs = data.get("organizations", [])
        if not orgs:
            return None

        org = orgs[0]
        return {
            "name": org.get("name"),
            "domain": org.get("primary_domain"),
            "linkedin_url": org.get("linkedin_url"),
            "industry": org.get("industry"),
            "estimated_num_employees": org.get("estimated_num_employees"),
            "annual_revenue": org.get("annual_revenue_printed"),
            "founded_year": org.get("founded_year"),
            "technologies": org.get("technologies", [])[:10],
            "city": org.get("city"),
            "state": org.get("state"),
            "country": org.get("country"),
            "short_description": org.get("short_description"),
            "funding_total": org.get("total_funding_printed"),
            "latest_funding_round": org.get("latest_funding_round_type"),
        }

    except Exception as e:
        print(f"[Apollo] Company enrichment error: {e}")
        return None


def enrich_contacts(company_name: str, domain: str = None, limit: int = 5) -> list:
    """Enrich contacts at a company with Apollo.io data.

    Returns list of enriched contact dicts with LinkedIn URLs and verified emails.
    """
    if not is_apollo_enabled():
        return []

    try:
        search_params = {
            "q_organization_name": company_name,
            "page": 1,
            "per_page": limit,
            "person_seniorities": ["vp", "director", "c_suite", "manager"],
        }
        if domain:
            search_params["q_organization_domains"] = domain

        response = requests.post(
            f"{APOLLO_BASE_URL}/people/search",
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
            params={"api_key": APOLLO_API_KEY},
            json=search_params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        contacts = []
        for person in data.get("people", []):
            contacts.append({
                "name": person.get("name"),
                "title": person.get("title"),
                "email": person.get("email"),
                "email_status": person.get("email_status"),  # verified, guessed, etc.
                "linkedin_url": person.get("linkedin_url"),
                "city": person.get("city"),
                "seniority": person.get("seniority"),
                "departments": person.get("departments", []),
            })
        return contacts

    except Exception as e:
        print(f"[Apollo] Contact enrichment error: {e}")
        return []


def format_apollo_company_context(data: dict) -> str:
    """Format Apollo company data for LLM context."""
    if not data:
        return ""

    lines = ["\n*Apollo.io Company Intelligence:*"]

    if data.get("short_description"):
        lines.append(f"  Description: {data['short_description']}")
    if data.get("estimated_num_employees"):
        lines.append(f"  Employees: {data['estimated_num_employees']}")
    if data.get("annual_revenue"):
        lines.append(f"  Annual Revenue: {data['annual_revenue']}")
    if data.get("founded_year"):
        lines.append(f"  Founded: {data['founded_year']}")
    if data.get("funding_total"):
        lines.append(f"  Total Funding: {data['funding_total']} ({data.get('latest_funding_round', 'N/A')})")
    if data.get("linkedin_url"):
        lines.append(f"  LinkedIn: {data['linkedin_url']}")
    if data.get("technologies"):
        lines.append(f"  Tech Stack: {', '.join(data['technologies'][:8])}")

    return "\n".join(lines)


def format_apollo_contacts_context(contacts: list) -> str:
    """Format Apollo contact data for LLM context."""
    if not contacts:
        return ""

    lines = ["\n*Apollo.io Contact Intelligence:*"]
    for c in contacts:
        name = c.get("name", "Unknown")
        title = c.get("title", "")
        email = c.get("email", "")
        email_status = c.get("email_status", "")
        linkedin = c.get("linkedin_url", "")

        status_label = f" ({email_status})" if email_status else ""
        line = f"  - {name}, {title}"
        if email:
            line += f" | {email}{status_label}"
        if linkedin:
            line += f" | LinkedIn: {linkedin}"
        lines.append(line)

    return "\n".join(lines)
```

### Step 2: Integrate into Research Node

In `graphs/assistant.py`, update `research_node()`:

```python
def research_node(state: dict) -> dict:
    """Generate a company research brief."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    company_name = state.get("company_name") or extract_company_name(last_message)

    # Web search
    if use_mock and mock_crm.is_known_mock_company(company_name):
        web_context = _generate_mock_news(company_name)
    else:
        web_context = search_company_news(company_name)

    # RAG context
    rag_context = rag_search(f"sales approach {company_name} ICP")
    crm_rag_context = search_crm(company_name)

    # Apollo enrichment (optional)
    apollo_context = ""
    from tools.apollo_enrichment import is_apollo_enabled, enrich_company, enrich_contacts
    from tools.apollo_enrichment import format_apollo_company_context, format_apollo_contacts_context
    if is_apollo_enabled():
        apollo_company = enrich_company(company_name)
        apollo_contacts = enrich_contacts(company_name, limit=5)
        apollo_context = format_apollo_company_context(apollo_company)
        apollo_context += "\n" + format_apollo_contacts_context(apollo_contacts)

    if use_mock:
        crm_context = _get_mock_company_context(company_name)
        system_prompt = f"""You are a sales research assistant.

TASK: Generate a research brief for {company_name}.

CRM DATA:
{crm_context}

CRM DATA (from RAG):
{crm_rag_context}

WEB SEARCH RESULTS:
{web_context}
{apollo_context}
PLAYBOOK CONTEXT:
{rag_context}

Format your response as:

*Research Brief: {company_name}*

*Company Overview:*
[What they do, size, industry, recent developments]

*Your Relationship:*
[Deal history, key contacts, last interaction from CRM]

*Recent News:*
[Relevant news and what it means for the deal]
{"*Apollo.io Intelligence:*" + chr(10) + "[LinkedIn profile, employee count, funding, tech stack, key contacts with verified emails]" + chr(10) if apollo_context else ""}
*Talking Points:*
[3-5 actionable talking points]

Keep it concise. Reps need to scan this in 2 minutes."""
    else:
        # Similar update for non-mock path — add apollo_context to system prompt
        # ...
```

### Step 3: Update Research Formatter (Optional Enhancement)

If you want a dedicated Apollo section in the Block Kit output, update `formatters/research.py`
to accept an `apollo_data` parameter and render it as a separate section with LinkedIn links.

This is optional — the LLM will naturally incorporate Apollo data into its response
if it's included in the system prompt context.

## Environment Variables

Add to `.env`:
```
# Apollo.io Enrichment (disabled by default for demo)
ENABLE_APOLLO_ENRICHMENT=false
APOLLO_API_KEY=your_apollo_api_key_here
```

For the demo with real companies:
```
ENABLE_APOLLO_ENRICHMENT=true
APOLLO_API_KEY=ak_xxxxxxxxxxxxx
```

## Testing

1. With `ENABLE_APOLLO_ENRICHMENT=false` (default):
   - `/research NovaTech` → should work as before, no Apollo section
   - Verify no errors in terminal

2. With `ENABLE_APOLLO_ENRICHMENT=true` and a valid API key:
   - `/research [real company name]` → should include Apollo intelligence section
   - LinkedIn URL, employee count, funding, tech stack should appear
   - Contacts should show verified emails and LinkedIn profiles

3. With `ENABLE_APOLLO_ENRICHMENT=true` but invalid API key:
   - Should gracefully degrade — no Apollo section, no errors
   - Print warning to terminal

## DO NOT
- Do not enable Apollo by default — it will fail for demo companies
- Do not store Apollo API responses in ChromaDB — they're ephemeral enrichment
- Do not call Apollo for every command — only /research (and optionally /handoff)
- Do not remove the existing CRM data flow — Apollo supplements, not replaces
- Do not expose the Apollo API key in Slack messages or error responses
