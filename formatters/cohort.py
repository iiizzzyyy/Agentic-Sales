"""
Slack Block Kit formatters for cohort-related views.
"""
from datetime import datetime


def format_cohort_list(cohorts):
    """
    Format list of cohorts for /cohort-progress or selection.

    Args:
        cohorts: List of cohort dicts from db.list_cohorts()

    Returns:
        List of Slack blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Training Cohorts"
            }
        }
    ]

    if not cohorts:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No cohorts created yet. Use `/create-cohort` to create one."
            }
        })
        return blocks

    for cohort in cohorts:
        status_emoji = ":white_check_mark:" if cohort.get("status") == "completed" else ":hourglass_flowing_sand:"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_emoji} *{cohort.get('name', 'Unnamed')}*\n{cohort.get('description', 'No description')}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Progress"},
                "action_id": f"view_cohort_{cohort['id']}",
                "value": cohort["id"]
            }
        })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Created by <@{cohort.get('created_by', 'Unknown')}> | Status: {cohort.get('status', 'active')}"
                }
            ]
        })

        blocks.append({"type": "divider"})

    # Actions
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Create New Cohort"},
                "action_id": "open_create_cohort_modal",
                "style": "primary"
            }
        ]
    })

    return blocks


def format_cohort_progress(cohort_data):
    """
    Format detailed cohort progress view.

    Args:
        cohort_data: Dict from db.get_cohort_progress() with cohort info and progress list

    Returns:
        List of Slack blocks
    """
    cohort = cohort_data.get("cohort", {})
    progress = cohort_data.get("progress", [])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": cohort.get("name", "Cohort Progress")
            }
        }
    ]

    if cohort.get("description"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": cohort["description"]
            }
        })

    # Overall stats
    total_participants = len(progress)
    graduated = sum(1 for p in progress if p.get("graduated"))
    avg_completion = sum(p.get("completion_pct", 0) for p in progress) / total_participants if total_participants > 0 else 0
    avg_score = sum(p.get("avg_score", 0) for p in progress if p.get("avg_score")) / total_participants if total_participants > 0 else 0

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": f"*Participants*\n{total_participants}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Graduated*\n{graduated}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Avg Completion*\n{avg_completion:.0%}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Avg Score*\n{avg_score:.1f}/10"
            }
        ]
    })

    # Graduation requirements
    min_score = cohort.get("graduation_min_avg_score", 7.0)
    min_completion = cohort.get("graduation_min_completion", 0.9)
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Graduation: {min_score}+ avg score, {min_completion:.0%}+ completion"
            }
        ]
    })

    # Participant progress
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Participant Progress*"
        }
    })

    for p in progress:
        user_id = p.get("user_id", "Unknown")
        completed = p.get("completed_scenarios", 0)
        total = p.get("total_scenarios", 0)
        pct = p.get("completion_pct", 0)
        score = p.get("avg_score")
        graduated = p.get("graduated")

        status = ":mortar_board:" if graduated else (":white_check_mark:" if pct >= min_completion else ":hourglass_flowing_sand:")
        score_str = f"{score:.1f}" if score else "N/A"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status} <@{user_id}> - {completed}/{total} scenarios ({pct:.0%}) | Score: {score_str}"
            }
        })

    # Week breakdown if available
    weeks = cohort.get("weeks", [])
    if weeks:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Weekly Schedule*"
            }
        })

        for week in weeks:
            week_num = week.get("week_number", 0)
            label = week.get("label", f"Week {week_num}")
            scenarios = week.get("scenarios", [])
            scenario_count = len(scenarios)

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Week {week_num}: {label}*\n{scenario_count} scenarios | Min score: {week.get('min_score', 6.0)}"
                }
            })

    return blocks


def format_create_cohort_modal():
    """
    Format modal for creating a new cohort.

    Returns:
        Dict with modal view configuration
    """
    return {
        "type": "modal",
        "callback_id": "create_cohort_modal",
        "title": {
            "type": "plain_text",
            "text": "Create Training Cohort"
        },
        "submit": {
            "type": "plain_text",
            "text": "Create"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "cohort_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "name_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Q1 2026 New Hire Cohort"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Cohort Name"
                }
            },
            {
                "type": "input",
                "block_id": "cohort_description",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "4-week onboarding program for new sales reps"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Description"
                },
                "optional": True
            },
            {
                "type": "input",
                "block_id": "cohort_participants",
                "element": {
                    "type": "multi_users_select",
                    "action_id": "participants_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select team members"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Participants"
                }
            },
            {
                "type": "input",
                "block_id": "cohort_template",
                "element": {
                    "type": "static_select",
                    "action_id": "template_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template"
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "New Hire Onboarding (4 weeks)"},
                            "value": "new_hire_onboard"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Custom (configure manually)"},
                            "value": "custom"
                        }
                    ]
                },
                "label": {
                    "type": "plain_text",
                    "text": "Template"
                }
            },
            {
                "type": "input",
                "block_id": "min_avg_score",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "score_input",
                    "initial_value": "7.0",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "7.0"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Minimum Avg Score to Graduate"
                }
            }
        ]
    }


def format_onboard_confirmation(cohort_name, participants, template_name):
    """
    Format confirmation message after cohort creation.

    Args:
        cohort_name: Name of created cohort
        participants: List of user IDs
        template_name: Template used

    Returns:
        List of Slack blocks
    """
    participant_mentions = ", ".join(f"<@{uid}>" for uid in participants)

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":white_check_mark: *Cohort Created: {cohort_name}*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Template:* {template_name}\n*Participants:* {participant_mentions}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Participants have been notified and can start their training."
                }
            ]
        }
    ]
