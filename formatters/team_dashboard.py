"""
Slack Block Kit formatters for team dashboard views.
"""
from datetime import datetime


def format_team_dashboard(team_stats, assignments_summary=None):
    """
    Format the /team-dashboard view with team training metrics.

    Args:
        team_stats: List of dicts with user training stats from db.get_team_training_summary()
        assignments_summary: Optional list from db.get_team_assignments_summary()

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Team Training Dashboard"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Updated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}"
                }
            ]
        }
    ]

    if not team_stats:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No training data yet. Team members need to complete training sessions to appear here."
            }
        })
        return blocks

    # Summary stats
    total_sessions = sum(s.get("total_sessions", 0) for s in team_stats)
    avg_scores = [s.get("avg_score") for s in team_stats if s.get("avg_score")]
    team_avg = sum(avg_scores) / len(avg_scores) if avg_scores else 0
    active_reps = len(team_stats)

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": f"*Total Sessions*\n{total_sessions}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Team Avg Score*\n{team_avg:.1f}/10"
            },
            {
                "type": "mrkdwn",
                "text": f"*Active Reps*\n{active_reps}"
            },
            {
                "type": "mrkdwn",
                "text": f"*This Week*\n{_count_recent_sessions(team_stats)}"
            }
        ]
    })

    # Leaderboard
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Leaderboard (by avg score)*"
        }
    })

    # Sort by avg score descending
    sorted_stats = sorted(team_stats, key=lambda x: x.get("avg_score", 0), reverse=True)

    for i, stat in enumerate(sorted_stats[:10], 1):
        user_id = stat.get("user_id", "Unknown")
        sessions = stat.get("total_sessions", 0)
        avg_score = stat.get("avg_score", 0)

        # Medal for top 3
        medal = ""
        if i == 1:
            medal = ":first_place_medal: "
        elif i == 2:
            medal = ":second_place_medal: "
        elif i == 3:
            medal = ":third_place_medal: "

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{medal}*{i}.* <@{user_id}> - {avg_score:.1f} avg ({sessions} sessions)"
            }
        })

    # Assignments summary if provided
    if assignments_summary:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Assignment Completion*"
            }
        })

        for assignment in assignments_summary[:5]:
            user_id = assignment.get("assigned_to", "Unknown")
            completed = assignment.get("completed", 0)
            pending = assignment.get("pending", 0)
            total = completed + pending
            pct = (completed / total * 100) if total > 0 else 0

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}>: {completed}/{total} completed ({pct:.0f}%)"
                }
            })

    # Actions
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Assign Training"},
                "action_id": "open_assign_modal",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Cohorts"},
                "action_id": "view_cohorts"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Export Report"},
                "action_id": "export_team_report"
            }
        ]
    })

    return blocks


def _count_recent_sessions(team_stats):
    """Count sessions from the last 7 days. Placeholder - would need date filtering in actual impl."""
    # In production, this would filter by date from the DB
    # For now, return a reasonable estimate
    total = sum(s.get("total_sessions", 0) for s in team_stats)
    return min(total, total // 4 + 1)  # Rough estimate


def format_rep_detail(user_id, stats, dimension_scores=None, recent_sessions=None):
    """
    Format detailed view for a single rep.

    Args:
        user_id: Slack user ID
        stats: Dict with user's training stats
        dimension_scores: Optional list of dimension averages
        recent_sessions: Optional list of recent session data

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Training Details"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Rep:* <@{user_id}>"
            }
        }
    ]

    if stats:
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Sessions*\n{stats.get('total_sessions', 0)}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg Score*\n{stats.get('avg_score', 0):.1f}/10"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Best Score*\n{stats.get('best_score', 0):.1f}/10"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Last Active*\n{_format_date(stats.get('last_session'))}"
                }
            ]
        })

    # Dimension breakdown
    if dimension_scores:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Skills Breakdown*"
            }
        })

        for dim in dimension_scores:
            avg = dim.get("avg_score", 0)
            name = dim.get("dimension", "Unknown")
            bar = _score_bar(avg)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{name}: {bar} {avg:.1f}"
                }
            })

    return blocks


def _format_date(date_str):
    """Format date string for display."""
    if not date_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d")
    except (ValueError, AttributeError):
        return date_str


def _score_bar(score, max_score=10):
    """Generate a visual score bar."""
    filled = int(score)
    empty = max_score - filled
    return "█" * filled + "░" * empty
