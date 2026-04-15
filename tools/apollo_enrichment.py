"""Apollo.io enrichment for company and contact data.

Supports two modes:
1. MCP mode: Uses Apollo MCP connector tools (preferred)
2. API mode: Direct Apollo API calls (fallback)

Enable via: ENABLE_APOLLO_ENRICHMENT=true
"""

import os
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
