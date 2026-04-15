"""
Slack Block Kit formatters for calendar-related views.
"""
import json
from datetime import datetime
from formatters.pipeline_summary import get_pipeline_summary
from formatters.helpers import format_currency


def format_my_day(events, user_name=None, user_id=None, pipeline_data=None):
    """
    Format the /my-day view with today's schedule.

    Args:
        events: List of event dicts from calendar tools
        user_name: Optional user name for greeting
        user_id: Optional user ID for fetching pipeline data
        pipeline_data: Optional pre-fetched pipeline dict (for testing)

    Returns:
        List of Slack blocks
    """
    today = datetime.now()
    date_str = today.strftime("%A, %B %d")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Your Day - {date_str}",
                "emoji": True
            }
        }
    ]

    # Pipeline summary section (if user_id provided)
    if user_id and pipeline_data is not False:
        try:
            pipeline = get_pipeline_summary(user_id)
            if pipeline["deal_count"] > 0:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Pipeline Summary*\n"
                            f"• *{format_currency(pipeline['total_value'])}* across {pipeline['deal_count']} deals\n"
                            f"• Most active stage: {pipeline['top_stage']}\n"
                            f"• {pipeline['flagged_count']} deals need attention"
                        ) if pipeline["flagged_count"] > 0 else (
                            f"*Pipeline Summary*\n"
                            f"• *{format_currency(pipeline['total_value'])}* across {pipeline['deal_count']} deals\n"
                            f"• Most active stage: {pipeline['top_stage']}\n"
                            f"• All deals on track"
                        )
                    }
                })
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Full Pipeline"},
                            "action_id": "view_full_pipeline",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "See Flagged Deals"},
                            "action_id": "view_flagged_deals",
                            "style": "danger" if pipeline["flagged_count"] > 0 else "primary"
                        }
                    ]
                })
                blocks.append({"type": "divider"})
        except Exception:
            pass  # Silently fail if pipeline data unavailable

    if not events:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No meetings scheduled for today. Great time to focus on outreach or training!"
            }
        })

        # Show pipeline context if available
        if user_id and pipeline_data is not False:
            try:
                pipeline = get_pipeline_summary(user_id)
                if pipeline["deal_count"] > 0:
                    blocks.append({
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"💼 You have {pipeline['deal_count']} deals ({format_currency(pipeline['total_value'])}) — consider following up on stale deals"
                            }
                        ]
                    })
            except Exception:
                pass

        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Training"},
                    "action_id": "quick_practice",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Pipeline"},
                    "action_id": "quick_pipeline"
                }
            ]
        })
        return blocks

    # Group events by type
    customer_meetings = [e for e in events if e.get("type") == "customer_meeting"]
    internal_meetings = [e for e in events if e.get("type") == "internal"]
    training_events = [e for e in events if e.get("type") == "training"]

    # Customer meetings section
    if customer_meetings:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Customer Meetings*"
            }
        })

        for event in customer_meetings:
            start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            time_str = start_time.strftime("%I:%M %p")

            meeting_text = f"*{time_str}* - {event['title']}"
            if event.get("notes"):
                meeting_text += f"\n_{event['notes']}_"

            block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": meeting_text
                }
            }

            # Add prep button if there's a deal associated
            if event.get("deal_id"):
                block["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Prep"},
                    "action_id": f"prep_meeting_{event['id']}",
                    "value": event["deal_id"]
                }

            blocks.append(block)

    # Internal meetings section
    if internal_meetings:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Internal*"
            }
        })

        for event in internal_meetings:
            start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            time_str = start_time.strftime("%I:%M %p")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{time_str}* - {event['title']}"
                }
            })

    # Training section
    if training_events:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Training*"
            }
        })

        for event in training_events:
            start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            time_str = start_time.strftime("%I:%M %p")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{time_str}* - {event['title']}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Join"},
                    "action_id": f"join_training_{event['id']}"
                }
            })

    # Summary footer
    blocks.append({"type": "divider"})
    total = len(events)
    customer_count = len(customer_meetings)
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{total} events today | {customer_count} customer meetings"
            }
        ]
    })

    return blocks


def format_meeting_prep(event, deal_info=None, company_info=None, deal_id=None):
    """
    Format meeting prep view with deal context.

    Args:
        event: Event dict from calendar
        deal_info: Optional deal data from CRM
        company_info: Optional company data from CRM
        deal_id: Optional deal ID for View Deal button

    Returns:
        List of Slack blocks
    """
    start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
    time_str = start_time.strftime("%I:%M %p on %A")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Prep: {event['title']}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Time:* {time_str}"
            }
        }
    ]

    # Attendees
    if event.get("attendees"):
        attendee_list = ", ".join(event["attendees"])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Attendees:* {attendee_list}"
            }
        })

    # Deal context
    if deal_info:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Deal:* {deal_info.get('name', 'Unknown')}\n*Stage:* {deal_info.get('stage', 'Unknown')}\n*Value:* ${float(deal_info.get('amount', 0) or 0):,.0f}"
            }
        })

    # Notes
    if event.get("notes"):
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Notes:* {event['notes']}"
            }
        })

    # Actions - build dynamically
    action_elements = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Practice Scenario"},
            "action_id": f"practice_for_meeting_{event['id']}",
            "value": deal_id or "",
            "style": "primary"
        }
    ]

    # Only add View Deal if we have a deal_id
    if deal_id:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Deal"},
            "action_id": "view_deal_from_handoff",
            "value": deal_id
        })

    blocks.append({
        "type": "actions",
        "elements": action_elements
    })

    return blocks


def format_practice_scenario_modal(event, inferred_scenario_type, inferred_persona, deal_id=None, channel_id=None):
    """
    Format modal for customizing practice scenario before starting roleplay.

    Args:
        event: Calendar event dict
        inferred_scenario_type: Auto-detected scenario type (discovery, demo, etc.)
        inferred_persona: Auto-detected persona dict with name, title, company
        deal_id: Optional deal ID
        channel_id: Channel ID to post roleplay in

    Returns:
        Modal view dict
    """
    scenario_options = [
        {"text": {"type": "plain_text", "text": "Discovery Call"}, "value": "discovery"},
        {"text": {"type": "plain_text", "text": "Product Demo"}, "value": "demo"},
        {"text": {"type": "plain_text", "text": "Negotiation"}, "value": "negotiation"},
        {"text": {"type": "plain_text", "text": "Cold Call"}, "value": "cold_call"},
        {"text": {"type": "plain_text", "text": "Competitive Deal"}, "value": "competitive"},
        {"text": {"type": "plain_text", "text": "QBR / Review"}, "value": "qbr"},
    ]

    role_options = [
        {"text": {"type": "plain_text", "text": "VP of Operations"}, "value": "VP of Operations"},
        {"text": {"type": "plain_text", "text": "Engineering Lead"}, "value": "Engineering Lead"},
        {"text": {"type": "plain_text", "text": "CTO"}, "value": "CTO"},
        {"text": {"type": "plain_text", "text": "CFO"}, "value": "CFO"},
        {"text": {"type": "plain_text", "text": "Procurement Manager"}, "value": "Procurement Manager"},
        {"text": {"type": "plain_text", "text": "Legal Counsel"}, "value": "Legal Counsel"},
    ]

    turn_options = [
        {"text": {"type": "plain_text", "text": "3 turns (quick)"}, "value": "3"},
        {"text": {"type": "plain_text", "text": "4 turns (standard)"}, "value": "4"},
        {"text": {"type": "plain_text", "text": "6 turns (extended)"}, "value": "6"},
        {"text": {"type": "plain_text", "text": "8 turns (deep practice)"}, "value": "8"},
    ]

    # Find initial options based on inferred values
    initial_scenario = next(
        (o for o in scenario_options if o["value"] == inferred_scenario_type),
        scenario_options[0]
    )
    initial_role = next(
        (o for o in role_options if o["value"] == inferred_persona.get("title")),
        role_options[0]
    )

    return {
        "type": "modal",
        "callback_id": "practice_scenario_modal",
        "private_metadata": json.dumps({
            "event_id": event["id"],
            "deal_id": deal_id or "",
            "company": inferred_persona.get("company", ""),
            "notes": event.get("notes", ""),
            "channel_id": channel_id or "",
        }),
        "title": {"type": "plain_text", "text": "Practice Scenario"},
        "submit": {"type": "plain_text", "text": "Start Practice"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Meeting:* {event.get('title', 'Meeting')}"
                }
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "scenario_type",
                "element": {
                    "type": "static_select",
                    "action_id": "scenario_select",
                    "initial_option": initial_scenario,
                    "options": scenario_options
                },
                "label": {"type": "plain_text", "text": "Scenario Type"}
            },
            {
                "type": "input",
                "block_id": "buyer_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "name_input",
                    "initial_value": inferred_persona.get("name", "Alex Chen"),
                    "placeholder": {"type": "plain_text", "text": "Buyer's name"}
                },
                "label": {"type": "plain_text", "text": "Buyer Name"}
            },
            {
                "type": "input",
                "block_id": "buyer_role",
                "element": {
                    "type": "static_select",
                    "action_id": "role_select",
                    "initial_option": initial_role,
                    "options": role_options
                },
                "label": {"type": "plain_text", "text": "Buyer Role"}
            },
            {
                "type": "input",
                "block_id": "turns",
                "element": {
                    "type": "static_select",
                    "action_id": "turns_select",
                    "initial_option": turn_options[1],  # Default 4 turns
                    "options": turn_options
                },
                "label": {"type": "plain_text", "text": "Number of Turns"}
            }
        ]
    }
