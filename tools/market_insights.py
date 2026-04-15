"""
Market insights tools - mock data for /market-insights command.
In production, this would integrate with news APIs, industry feeds, etc.
"""
from datetime import datetime, timedelta
import random

# Mock market insights data
MOCK_INSIGHTS = {
    "industry_trends": [
        {
            "id": "trend_001",
            "title": "AI-Powered Sales Tools See 340% YoY Growth",
            "summary": "Enterprise adoption of AI sales coaching platforms accelerated in Q1 2026, with companies reporting average productivity gains of 25-40%.",
            "source": "Gartner",
            "date": "2026-03-14",
            "relevance": "high",
            "tags": ["AI", "sales technology", "productivity"]
        },
        {
            "id": "trend_002",
            "title": "Remote Sales Teams Outperforming In-Office",
            "summary": "New study shows distributed sales teams closed 18% more deals in 2025, attributed to better work-life balance and expanded talent pools.",
            "source": "Harvard Business Review",
            "date": "2026-03-10",
            "relevance": "medium",
            "tags": ["remote work", "sales performance"]
        },
        {
            "id": "trend_003",
            "title": "B2B Buyers Expect Personalized Digital Experiences",
            "summary": "78% of B2B buyers say they expect the same personalized experience they get as consumers. Sales teams leveraging AI personalization see 32% higher engagement.",
            "source": "Forrester",
            "date": "2026-03-08",
            "relevance": "high",
            "tags": ["personalization", "buyer expectations", "digital selling"]
        }
    ],
    "competitor_news": [
        {
            "id": "comp_001",
            "competitor": "CompetitorAlpha",
            "title": "CompetitorAlpha Raises $50M Series B",
            "summary": "Funding will be used to expand AI capabilities and enter European market. CEO quotes 'aggressive growth targets' for 2026.",
            "source": "TechCrunch",
            "date": "2026-03-12",
            "impact": "Watch - may increase competitive pressure in EU deals"
        },
        {
            "id": "comp_002",
            "competitor": "CompetitorAlpha",
            "title": "CompetitorAlpha Customer Churn Concerns",
            "summary": "G2 reviews show increasing complaints about limited customization and poor enterprise support. NPS dropped 15 points in Q4 2025.",
            "source": "G2 Crowd Analysis",
            "date": "2026-03-05",
            "impact": "Opportunity - target their enterprise customers"
        },
        {
            "id": "comp_003",
            "competitor": "SalesForce",
            "title": "Salesforce Announces Einstein Sales Coach GA",
            "summary": "Native AI coaching built into Sales Cloud. Limited to Salesforce-only shops. Early reviews praise integration but note feature gaps vs. specialized tools.",
            "source": "Salesforce Blog",
            "date": "2026-03-01",
            "impact": "Moderate - affects pure Salesforce deals, our HubSpot focus is differentiated"
        }
    ],
    "customer_signals": [
        {
            "id": "signal_001",
            "company": "DataFlow Inc",
            "signal_type": "expansion",
            "summary": "DataFlow announced 40% headcount growth in sales team. Current deal may have upsell opportunity.",
            "source": "LinkedIn",
            "date": "2026-03-15",
            "deal_id": "deal_df_001"
        },
        {
            "id": "signal_002",
            "company": "NovaTech Solutions",
            "signal_type": "event",
            "summary": "NovaTech presenting at SaaStr Annual next month. Good opportunity for case study if deal closes.",
            "source": "SaaStr Agenda",
            "date": "2026-03-13",
            "deal_id": "deal_992410"
        },
        {
            "id": "signal_003",
            "company": "Velocity Retail",
            "signal_type": "risk",
            "summary": "Velocity Retail CFO interview mentions 'tightening discretionary spend'. Monitor deal closely.",
            "source": "Retail Dive",
            "date": "2026-03-11",
            "deal_id": "deal_831953"
        }
    ],
    "market_stats": {
        "tam": "$4.2B",
        "tam_growth": "28% CAGR",
        "avg_deal_size_industry": "$45K",
        "avg_sales_cycle": "62 days",
        "top_buying_criteria": [
            "Ease of use (78%)",
            "ROI / time to value (72%)",
            "Integration with existing tools (68%)",
            "AI capabilities (61%)",
            "Price (54%)"
        ]
    }
}


def get_industry_trends(limit=5, relevance_filter=None):
    """
    Get recent industry trends.

    Args:
        limit: Max number of trends to return
        relevance_filter: Optional - 'high', 'medium', or 'low'

    Returns:
        List of trend dicts
    """
    trends = MOCK_INSIGHTS["industry_trends"]

    if relevance_filter:
        trends = [t for t in trends if t.get("relevance") == relevance_filter]

    return trends[:limit]


def get_competitor_news(competitor=None, limit=5):
    """
    Get recent competitor news.

    Args:
        competitor: Optional competitor name to filter by
        limit: Max number of items to return

    Returns:
        List of competitor news dicts
    """
    news = MOCK_INSIGHTS["competitor_news"]

    if competitor:
        news = [n for n in news if n.get("competitor", "").lower() == competitor.lower()]

    return news[:limit]


def get_customer_signals(deal_id=None, signal_type=None, limit=10):
    """
    Get customer buying signals.

    Args:
        deal_id: Optional deal ID to filter by
        signal_type: Optional - 'expansion', 'event', 'risk'
        limit: Max number of signals to return

    Returns:
        List of signal dicts
    """
    signals = MOCK_INSIGHTS["customer_signals"]

    if deal_id:
        signals = [s for s in signals if s.get("deal_id") == deal_id]

    if signal_type:
        signals = [s for s in signals if s.get("signal_type") == signal_type]

    return signals[:limit]


def get_market_stats():
    """
    Get overall market statistics.

    Returns:
        Dict with market stats
    """
    return MOCK_INSIGHTS["market_stats"]


def get_daily_digest():
    """
    Get a curated daily digest of insights.

    Returns:
        Dict with trends, competitor news, and signals for today
    """
    today = datetime.now().date()

    # In production, this would filter by date. For mock data, return recent items.
    return {
        "date": today.isoformat(),
        "trends": get_industry_trends(limit=2, relevance_filter="high"),
        "competitor_updates": get_competitor_news(limit=2),
        "customer_signals": get_customer_signals(limit=3),
        "market_stats": get_market_stats()
    }


def search_insights(query):
    """
    Search all insights for a query string.

    Args:
        query: Search string (case-insensitive)

    Returns:
        Dict with matching items from each category
    """
    query_lower = query.lower()
    results = {
        "trends": [],
        "competitor_news": [],
        "customer_signals": []
    }

    for trend in MOCK_INSIGHTS["industry_trends"]:
        if query_lower in trend["title"].lower() or query_lower in trend["summary"].lower():
            results["trends"].append(trend)

    for news in MOCK_INSIGHTS["competitor_news"]:
        if query_lower in news["title"].lower() or query_lower in news["summary"].lower() or query_lower in news.get("competitor", "").lower():
            results["competitor_news"].append(news)

    for signal in MOCK_INSIGHTS["customer_signals"]:
        if query_lower in signal["company"].lower() or query_lower in signal["summary"].lower():
            results["customer_signals"].append(signal)

    return results
