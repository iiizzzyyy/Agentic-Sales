"""Block Kit formatter for training history."""
import json
from formatters.helpers import timestamp


def format_training_history(user_id, sessions, stats):
    """Format training history as Block Kit blocks.

    Args:
        user_id: The user whose history this is
        sessions: List of recent session dicts from get_training_history()
        stats: Aggregate stats dict from get_training_stats()
    """
    total = stats.get("total_sessions", 0) if stats else 0
    avg_score = stats.get("avg_score") if stats else None
    best_score = stats.get("best_score") if stats else None

    # Header
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Training History", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"<@{user_id}>'s coaching sessions"}
            ]
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Sessions:* {total}"},
                {"type": "mrkdwn", "text": f"*Avg Score:* {avg_score:.1f}/10" if avg_score else "*Avg Score:* N/A"},
                {"type": "mrkdwn", "text": f"*Best Score:* {best_score:.1f}/10" if best_score else "*Best Score:* N/A"},
                {"type": "mrkdwn", "text": f"*Last Session:* {_format_relative_time(stats.get('last_session', '') if stats else '')}"},
            ]
        },
        {"type": "divider"},
    ]

    # Session list
    prev_score = None
    for session in sessions:
        score = session.get("overall_score")
        scenario = session.get("scenario", "Unknown scenario")
        scenario_type = session.get("scenario_type", "")
        ts = session.get("timestamp", "")
        turns = session.get("turns", "?")
        company = session.get("company", "")

        # Trend arrow compared to next-older session
        trend = ""
        if score and prev_score:
            if score > prev_score + 0.3:
                trend = " ↑"
            elif score < prev_score - 0.3:
                trend = " ↓"
            else:
                trend = " →"

        # Score color
        if score and score >= 7:
            score_display = f"🟢 {score:.1f}/10{trend}"
        elif score and score >= 5:
            score_display = f"🟡 {score:.1f}/10{trend}"
        elif score:
            score_display = f"🔴 {score:.1f}/10{trend}"
        else:
            score_display = "N/A"

        type_label = scenario_type.replace("_", " ").title() if scenario_type else "General"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{scenario}*\n{type_label} · {turns} turns · {_format_relative_time(ts)}\nScore: {score_display}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Practice Again", "emoji": True},
                "action_id": "practice_from_history",
                "value": json.dumps({
                    "scenario": scenario,
                    "scenario_type": scenario_type,
                    "scenario_id": session.get("scenario_id"),
                    "company": company,
                }),
            }
        })

        prev_score = score

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Skill Gaps", "emoji": True},
                "action_id": "view_skill_gaps",
                "value": user_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start New Practice", "emoji": True},
                "action_id": "start_new_practice",
                "style": "primary",
            },
        ]
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]
    })

    fallback = (
        f"Training History for <@{user_id}>. "
        f"{total} sessions, avg score {avg_score:.1f}/10." if avg_score else
        f"Training History for <@{user_id}>. {total} sessions."
    )

    return blocks, fallback


def _format_relative_time(iso_timestamp):
    """Convert ISO timestamp to relative time string."""
    if not iso_timestamp:
        return "Unknown"
    try:
        from datetime import datetime
        # Handle SQLite datetime format (no timezone)
        if "T" in iso_timestamp:
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        else:
            dt = datetime.fromisoformat(iso_timestamp)
            now = datetime.now()
        diff = now - dt
        if diff.days > 7:
            return dt.strftime("%b %d")
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        else:
            return f"{diff.seconds // 60}m ago"
    except (ValueError, TypeError):
        return iso_timestamp[:10] if iso_timestamp else "Unknown"
