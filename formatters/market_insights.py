"""
Slack Block Kit formatters for market insights views.
"""
from datetime import datetime


def format_market_insights(digest):
    """
    Format the /market-insights view with daily digest.

    Args:
        digest: Dict from market_insights.get_daily_digest()

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Market Insights"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Daily digest for {datetime.now().strftime('%B %d, %Y')}"
                }
            ]
        }
    ]

    # Industry Trends
    trends = digest.get("trends", [])
    if trends:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:chart_with_upwards_trend: Industry Trends*"
            }
        })

        for trend in trends:
            relevance_emoji = ":fire:" if trend.get("relevance") == "high" else ""
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{relevance_emoji} *{trend.get('title', 'Untitled')}*\n{trend.get('summary', '')}\n_Source: {trend.get('source', 'Unknown')} | {trend.get('date', '')}_"
                }
            })

    # Competitor Updates
    competitor_news = digest.get("competitor_updates", [])
    if competitor_news:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:eyes: Competitor Watch*"
            }
        })

        for news in competitor_news:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{news.get('competitor', 'Unknown')}*: {news.get('title', 'Untitled')}\n{news.get('summary', '')}\n_Impact: {news.get('impact', 'Unknown')}_"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Battlecard"},
                    "action_id": f"view_battlecard_{news.get('competitor', '').lower().replace(' ', '_')}"
                }
            })

    # Customer Signals
    signals = digest.get("customer_signals", [])
    if signals:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:bell: Customer Signals*"
            }
        })

        for signal in signals:
            signal_type = signal.get("signal_type", "info")
            emoji = ":rocket:" if signal_type == "expansion" else (":warning:" if signal_type == "risk" else ":calendar:")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{signal.get('company', 'Unknown')}*\n{signal.get('summary', '')}"
                }
            })

    # Market Stats
    stats = digest.get("market_stats", {})
    if stats:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:bar_chart: Market Stats*"
            }
        })

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*TAM*\n{stats.get('tam', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Growth*\n{stats.get('tam_growth', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg Deal Size*\n{stats.get('avg_deal_size_industry', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg Sales Cycle*\n{stats.get('avg_sales_cycle', 'N/A')}"
                }
            ]
        })

        # Top buying criteria
        criteria = stats.get("top_buying_criteria", [])
        if criteria:
            criteria_text = "\n".join(f"• {c}" for c in criteria[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Buying Criteria:*\n{criteria_text}"
                }
            })

    # Actions
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Search Insights"},
                "action_id": "open_insights_search"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View All Competitors"},
                "action_id": "view_all_competitors"
            }
        ]
    })

    return blocks


def format_competitor_detail(competitor_name, battlecard_content):
    """
    Format detailed competitor battlecard view.

    Args:
        competitor_name: Name of competitor
        battlecard_content: Markdown content from battlecard file

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Battlecard: {competitor_name}"
            }
        }
    ]

    # Parse battlecard content into sections
    # For now, just show the raw content in a section
    # In production, this would parse markdown and format nicely

    # Truncate if too long for Slack
    if len(battlecard_content) > 2900:
        battlecard_content = battlecard_content[:2900] + "\n\n_[Content truncated - view full battlecard in docs]_"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": battlecard_content
        }
    })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Practice Objection Handling"},
                "action_id": f"practice_competitor_{competitor_name.lower().replace(' ', '_')}",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Back to Insights"},
                "action_id": "back_to_insights"
            }
        ]
    })

    return blocks


def format_insights_search_results(query, results):
    """
    Format search results for market insights.

    Args:
        query: Search query string
        results: Dict with trends, competitor_news, customer_signals lists

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Search Results: \"{query}\""
            }
        }
    ]

    total_results = len(results.get("trends", [])) + len(results.get("competitor_news", [])) + len(results.get("customer_signals", []))

    if total_results == 0:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No results found. Try a different search term."
            }
        })
        return blocks

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Found {total_results} results"
            }
        ]
    })

    # Show results by category
    for trend in results.get("trends", []):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":chart_with_upwards_trend: *{trend.get('title', '')}*\n{trend.get('summary', '')}"
            }
        })

    for news in results.get("competitor_news", []):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":eyes: *{news.get('competitor', '')}: {news.get('title', '')}*\n{news.get('summary', '')}"
            }
        })

    for signal in results.get("customer_signals", []):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":bell: *{signal.get('company', '')}*\n{signal.get('summary', '')}"
            }
        })

    return blocks
