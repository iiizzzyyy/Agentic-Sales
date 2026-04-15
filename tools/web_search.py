"""Tavily web search wrapper for company research."""

import os
from tavily import TavilyClient


def search_company_news(company_name: str) -> str:
    """Search for recent news about a company. Return formatted summary."""
    client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

    results = client.search(
        query=f"{company_name} latest news 2026",
        max_results=5,
        search_depth="basic"
    )

    return format_search_results(results)


def format_search_results(results: dict) -> str:
    """Format Tavily search results into a readable summary."""
    if not results.get("results"):
        return "No recent news found."

    formatted = []
    for item in results["results"]:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")
        formatted.append(f"• *{title}*\n  {content[:200]}...\n  {url}")

    return "\n\n".join(formatted)
