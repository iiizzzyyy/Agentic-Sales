# FIX: Suppress Web Search for Synthetic/Demo Companies

## Bug Description
When running `/research NovaTech`, the "Recent News" section shows irrelevant results from
a real company called "Novatech" (a PC builder) including YouTube videos. This happens because
the web search tool (Tavily) searches the real internet for fictional/synthetic company names.

This makes the demo look broken — executives see YouTube links about a PC builder instead of
relevant business intelligence.

## Root Cause
In `graphs/assistant.py` `research_node()` (line 44-45):
```python
web_context = search_company_news(company_name)
```
This calls Tavily with `"{company_name} latest news 2026"` which returns real web results
for the closest real company name match.

In `tools/web_search.py`:
```python
results = client.search(
    query=f"{company_name} latest news 2026",
    max_results=5,
    search_depth="basic"
)
```

## Fix — Smart Web Search with Demo Mode

### Step 1: Add Demo Company Detection

In `tools/mock_crm.py`, add a helper function:

```python
def is_known_mock_company(name: str) -> bool:
    """Check if a company name matches a known synthetic/demo company."""
    _load_data()
    for company in _crm_data.get("companies", []):
        company_name = company.get("properties", {}).get("name", "")
        if name.lower() in company_name.lower() or company_name.lower() in name.lower():
            return True
    return False


def get_mock_company_full_name(name: str) -> str | None:
    """Get the full name of a mock company by partial match."""
    _load_data()
    for company in _crm_data.get("companies", []):
        company_name = company.get("properties", {}).get("name", "")
        if name.lower() in company_name.lower():
            return company_name
    return None
```

### Step 2: Update `research_node()` in `graphs/assistant.py`

At line 44, add a conditional check:

```python
def research_node(state: dict) -> dict:
    """Generate a company research brief."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    company_name = state.get("company_name") or extract_company_name(last_message)

    # Smart web search — skip for known demo/synthetic companies
    if use_mock and mock_crm.is_known_mock_company(company_name):
        web_context = _generate_mock_news(company_name)
    else:
        web_context = search_company_news(company_name)

    # ... rest of function unchanged
```

### Step 3: Add Mock News Generator

In `graphs/assistant.py`, add a helper function near the other mock helpers:

```python
def _generate_mock_news(company_name: str) -> str:
    """Generate plausible mock news for demo companies.

    Instead of hitting real web search (which returns irrelevant results for
    fictional companies), generate demo-appropriate news snippets based on
    the company's CRM data.
    """
    company = mock_crm.search_company(company_name)
    if not company:
        return "No recent news found."

    props = company.get("properties", {})
    full_name = props.get("name", company_name)
    industry = props.get("industry", "technology")
    city = props.get("city", "")
    state = props.get("state", "")
    num_employees = props.get("numberofemployees", "")

    # Get deals for context
    company_id = company.get("id")
    deals = mock_crm.get_deals_for_company(company_id) if company_id else []

    # Build plausible news items based on company data
    news_items = []

    if num_employees:
        news_items.append(
            f"• *{full_name} Expands Workforce* — The {industry} company "
            f"has grown to {num_employees} employees, signaling continued investment "
            f"in their product and go-to-market teams."
        )

    if city and state:
        news_items.append(
            f"• *{full_name} Strengthens {city} Presence* — Headquartered in "
            f"{city}, {state}, the company continues to attract top talent in the region."
        )

    if len(deals) >= 2:
        total_value = sum(
            d.get("properties", {}).get("amount", 0)
            for d in deals
            if d.get("properties", {}).get("amount")
        )
        if total_value:
            news_items.append(
                f"• *{full_name} in Active Evaluation Phase* — Multiple enterprise "
                f"deals in pipeline indicate growing demand for their solutions."
            )

    if not news_items:
        news_items.append(f"• *{full_name}* — Active in the {industry} space with ongoing market presence.")

    return "\n\n".join(news_items)
```

### Step 4: Update `app.py` to Handle Mock News in Research Output

In `handle_research()` at line 468-471, the news parsing looks for bullet points from web context.
The mock news already uses bullet format, so it should work. But add a flag so the formatter
knows this is demo data:

```python
# Get news from web context if available
news = []
is_demo_news = False
if result.get("web_context"):
    is_demo_news = use_mock and mock_crm.is_known_mock_company(company)
    news = [{"title": line.strip("• -*")} for line in result["web_context"].split("\n") if line.strip() and line.strip().startswith("•")][:3]
```

Note: `use_mock` may not be directly accessible in app.py. Check how the mock flag is determined.
If it's based on an env var like `USE_MOCK_CRM`, use that instead:

```python
import os
USE_MOCK = os.environ.get("USE_MOCK_CRM", "true").lower() == "true"
```

### Step 5: Add `ENABLE_WEB_SEARCH` Env Var (Optional)

For extra control, add an env var to toggle web search entirely:

```python
# In tools/web_search.py:
def search_company_news(company_name: str) -> str:
    """Search for recent news about a company."""
    if not os.environ.get("TAVILY_API_KEY"):
        return "Web search not configured."

    if os.environ.get("ENABLE_WEB_SEARCH", "true").lower() != "true":
        return "Web search disabled."

    client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
    # ... rest unchanged
```

## Testing

1. `/research NovaTech` → "Recent News" should show plausible mock news, NOT YouTube videos
2. `/research Apex` → should show mock news about Apex Industries
3. If `ENABLE_WEB_SEARCH=true` and a non-mock company name is used, real web search should still work
4. The LLM's talking points should still be relevant (they're based on CRM data, not web search)
5. Verify the news section renders cleanly in Block Kit (no raw URLs, no YouTube links)

## DO NOT
- Do not disable web search entirely — it works fine for real companies in production
- Do not remove the Tavily integration — just bypass it for known mock companies
- Do not hardcode company names — use the `is_known_mock_company()` check against the actual data
- Do not change the format of the news output — keep the bullet format consistent
