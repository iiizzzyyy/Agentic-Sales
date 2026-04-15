"""Block Kit formatting for /win-loss command."""
from formatters.helpers import timestamp, format_currency


def format_win_loss_response(
    overall_metrics: dict,
    trend_data: list,
    patterns: str,
    recommendations: list,
    filter_label: str,
) -> tuple[list, str]:
    """Format win/loss analysis as Block Kit.

    Args:
        overall_metrics: Dict with 'win_rate', 'avg_cycle_days', 'avg_deal_size', 'total_won', 'total_lost'
        trend_data: List of dicts with 'period', 'win_rate', 'deals_won', 'deals_lost'
        patterns: LLM-generated pattern analysis
        recommendations: List of recommendation strings
        filter_label: What filter was applied (e.g., "All Deals", "Q1 2026", "Competitor Deals")

    Returns:
        tuple: (blocks, fallback_text)
    """
    win_rate = overall_metrics.get("win_rate", 0)
    avg_cycle = overall_metrics.get("avg_cycle_days", 0)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📉 Win/Loss Analysis", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"📊 {filter_label} · Analysis period: Last 12 months · Generated {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Key metrics
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Win Rate:*\n{win_rate:.0f}%"},
                {"type": "mrkdwn", "text": f"*Avg Cycle:*\n{avg_cycle:.0f} days"},
                {"type": "mrkdwn", "text": f"*Avg Deal Size:*\n{format_currency(overall_metrics.get('avg_deal_size', 0))}"},
                {"type": "mrkdwn", "text": f"*Won / Lost:*\n{overall_metrics.get('total_won', 0)} / {overall_metrics.get('total_lost', 0)}"},
            ]
        },

        {"type": "divider"},
    ]

    # Trend data in monospace table
    if trend_data:
        # Build monospace table for trend data
        trend_table = "```\n"
        trend_table += "Period      | Win %  | W / L\n"
        trend_table += "------------+--------+-------\n"
        for t in trend_data[-5:]:
            period = t['period'][:11].ljust(11)
            win_rate = f"{t['win_rate']}%".rjust(6)
            w_l = f"{t.get('deals_won', '?')} / {t.get('deals_lost', '?')}".rjust(5)
            trend_table += f"{period} | {win_rate} | {w_l}\n"
        trend_table += "```"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📈 Trend:*\n{trend_table}"}
        })
        blocks.append({"type": "divider"})

    # AI pattern analysis — split into multiple sections if too long
    if patterns:
        # Split into chunks that fit Slack's 3000 char limit per section
        pattern_lines = patterns.split("\n")
        current_chunk = "*🧠 Patterns Detected:*\n"
        section_count = 0
        MAX_PATTERN_SECTIONS = 3

        for line in pattern_lines:
            if len(current_chunk) + len(line) + 1 > 2800:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": current_chunk}
                })
                section_count += 1
                if section_count >= MAX_PATTERN_SECTIONS:
                    blocks.append({
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "_Pattern analysis truncated — use overflow menu for full report_"}]
                    })
                    break
                current_chunk = ""
            current_chunk += line + "\n"

        if current_chunk.strip() and section_count < MAX_PATTERN_SECTIONS:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": current_chunk}
            })
        blocks.append({"type": "divider"})

    # Recommendations
    if recommendations:
        rec_text = "\n".join([f"• 💡 {r}" for r in recommendations[:4]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📌 Recommendations:*\n{rec_text}"}
        })

    # Action buttons with overflow for secondary actions
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Lost Deals", "emoji": True},
                "action_id": "win_loss_lost_deals",
                "value": "lost",
                "style": "primary",
            },
            {
                "type": "overflow",
                "action_id": "win_loss_overflow",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "View Won Deals"},
                        "value": "win_loss_won_deals|won",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Competitor Analysis"},
                        "value": "win_loss_competitor|competitor",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Export Report"},
                        "value": "win_loss_export|export",
                    },
                ],
            },
        ]
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Win/Loss Analysis • {timestamp()}"}
        ]
    })

    # Rich fallback for screen readers
    recs_summary = "; ".join(recommendations[:2]) if recommendations else "No recommendations"
    fallback = f"Win/Loss Analysis for {filter_label}. Win rate: {win_rate:.0f}%. Average cycle: {avg_cycle:.0f} days. Won: {overall_metrics.get('total_won', 0)} deals. Lost: {overall_metrics.get('total_lost', 0)} deals. Average deal size: {format_currency(overall_metrics.get('avg_deal_size', 0))}. Key recommendations: {recs_summary}."
    return blocks, fallback
