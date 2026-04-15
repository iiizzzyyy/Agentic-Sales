"""Block Kit formatting for /demo-flow command."""
from formatters.helpers import timestamp


# Define the demo sequence
DEMO_STEPS = [
    {
        "step": 1,
        "title": "Pipeline Overview",
        "command": "/pipeline",
        "description": "See your full pipeline at a glance with AI-powered health scoring.",
        "emoji": "📈",
    },
    {
        "step": 2,
        "title": "Deal Deep Dive",
        "command": "/deal NovaTech",
        "description": "Get a comprehensive deal card with contacts, history, and AI recommendations.",
        "emoji": "🔍",
    },
    {
        "step": 3,
        "title": "Company Research",
        "command": "/research Apex Manufacturing",
        "description": "Instant research brief with company info, key stakeholders, and talking points.",
        "emoji": "🏢",
    },
    {
        "step": 4,
        "title": "Battle Card",
        "command": "/battlecard CompetitorAlpha",
        "description": "Instant competitive intel — strengths, weaknesses, and landmine questions.",
        "emoji": "⚔️",
    },
    {
        "step": 5,
        "title": "Objection Handler",
        "command": "/objection your pricing is too high",
        "description": "Real-time objection response — what to say, proof points, and pivot questions.",
        "emoji": "🛡️",
    },
    {
        "step": 6,
        "title": "AI Q&A",
        "command": "/ask What deals are closing this month?",
        "description": "Ask anything in plain English. The AI searches your CRM and answers naturally.",
        "emoji": "🧠",
    },
    {
        "step": 7,
        "title": "Pipeline Forecast",
        "command": "/forecast",
        "description": "AI-weighted forecast with risk analysis and actionable insights.",
        "emoji": "📊",
    },
    {
        "step": 8,
        "title": "Buyer Persona",
        "command": "/persona NovaTech",
        "description": "AI-generated buyer persona with pain points, messaging do's/don'ts, and conversation starters.",
        "emoji": "👤",
    },
    {
        "step": 9,
        "title": "Email Sequence",
        "command": "/email-sequence NovaTech post-demo",
        "description": "Multi-touch email campaign generated from deal context and playbooks.",
        "emoji": "📧",
    },
    {
        "step": 10,
        "title": "Sales Roleplay",
        "command": "/coach roleplay discovery call",
        "description": "Practice a live call with an AI buyer persona. Get scored and coached.",
        "emoji": "🎯",
    },
]


def format_demo_welcome() -> tuple[list, str]:
    """Format the demo welcome screen."""
    steps_preview = "\n".join([f"• {s['emoji']} {s['title']}" for s in DEMO_STEPS])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎬 SalesCoach AI — Live Demo", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Welcome to the guided demo of SalesCoach AI.\n\n"
                    "This walkthrough will showcase all AI capabilities in sequence. "
                    "Click *Next →* to advance through each feature.\n\n"
                    f"*Demo Sequence ({len(DEMO_STEPS)} features):*\n{steps_preview}"
                )
            }
        },

        {"type": "divider"},

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "▶️ Start Demo", "emoji": True},
                    "action_id": "demo_flow_next",
                    "value": "0",
                    "style": "primary",
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI Demo • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    steps_list = ", ".join([s['title'] for s in DEMO_STEPS])
    fallback = f"SalesCoach AI Live Demo. This guided walkthrough covers {len(DEMO_STEPS)} features: {steps_list}. Click Start Demo to begin."
    return blocks, fallback


def format_demo_step_intro(step_index: int) -> tuple[list, str]:
    """Format the introduction card for a demo step.

    Args:
        step_index: 0-based index into DEMO_STEPS

    Returns:
        tuple: (blocks, fallback_text)
    """
    step = DEMO_STEPS[step_index]
    total = len(DEMO_STEPS)
    progress = f"{'█' * (step_index + 1)}{'░' * (total - step_index - 1)}"

    blocks = [
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Demo Step {step['step']}/{total} • {progress}"}
            ]
        },
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{step['emoji']} {step['title']}", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{step['description']}\n\n*Running:* `{step['command']}`"
            }
        },

        {"type": "divider"},
    ]

    # Rich fallback for screen readers
    fallback = f"Demo Step {step['step']} of {total}: {step['title']}. {step['description']} Running command: {step['command']}"
    return blocks, fallback


def format_demo_step_nav(step_index: int) -> list:
    """Format navigation buttons after a demo step result is shown.

    Args:
        step_index: Current 0-based index

    Returns:
        list: Block Kit blocks for navigation
    """
    total = len(DEMO_STEPS)
    is_last = step_index >= total - 1

    elements = []

    if not is_last:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Next →", "emoji": True},
            "action_id": "demo_flow_next",
            "value": str(step_index + 1),
            "style": "primary",
        })

    elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "End Demo", "emoji": True},
        "action_id": "demo_flow_end",
        "value": "end",
        "style": "danger" if is_last else None,
    })
    # Remove None style
    if elements[-1].get("style") is None:
        del elements[-1]["style"]

    return [
        {"type": "divider"},
        {
            "type": "actions",
            "elements": elements,
        },
    ]


def format_demo_complete() -> tuple[list, str]:
    """Format the demo completion card."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎉 Demo Complete!", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"You've seen all {len(DEMO_STEPS)} AI capabilities of SalesCoach AI.\n\n"
                    "*Available Commands:*\n"
                    "`/pipeline` • `/deal` • `/research` • `/battlecard` • `/objection` • "
                    "`/ask` • `/forecast` • `/persona` • `/email-sequence` • `/coach` • "
                    "`/handoff` • `/win-loss` • `/alerts` • `/coach-live` • `/demo-flow`"
                )
            }
        },

        {"type": "divider"},

        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Thank you for watching the demo! Try any command to explore further."
            }
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Demo Complete • {timestamp()}"}
            ]
        },
    ]

    # Rich fallback for screen readers
    fallback = f"Demo Complete. You've seen all {len(DEMO_STEPS)} AI capabilities of SalesCoach AI. Try any slash command to explore further."
    return blocks, fallback
