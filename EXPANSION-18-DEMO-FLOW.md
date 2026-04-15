# Claude Code Instructions: `/demo-flow` — Guided Demo Walkthrough

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, and all `formatters/*.py` files first.**

---

## CONTEXT — WHAT AND WHY

`/demo-flow` is a meta-feature: it walks through all the bot's capabilities in a scripted, polished sequence. Instead of the presenter typing commands live (and risking typos or long loading times), `/demo-flow` presents each capability one at a time with a "Next →" button.

This is a demo safety net. It ensures every live demo hits all the key features in the right order with pre-loaded example inputs. The presenter just clicks "Next" and narrates.

---

## WHAT IT DOES

1. User types `/demo-flow` to start
2. Bot posts a welcome card with a "Start Demo" button
3. Each click of "Next →" triggers the next capability in sequence:
   - Step 1: Pipeline Overview (`/pipeline`)
   - Step 2: Deal Deep Dive (`/deal NovaTech`)
   - Step 3: Company Research (`/research Apex Manufacturing`)
   - Step 4: Battle Card (`/battlecard CompetitorAlpha`)
   - Step 5: Objection Handler (`/objection your pricing is too high`)
   - Step 6: AI Q&A (`/ask What deals are closing this month?`)
   - Step 7: Forecast (`/forecast`)
   - Step 8: Buyer Persona (`/persona NovaTech`)
   - Step 9: Email Sequence (`/email-sequence NovaTech post-demo`)
   - Step 10: Roleplay Start (`/coach roleplay discovery call`)
4. Each step shows what command is being run and posts the result
5. After the last step, shows a "Demo Complete" card with all available commands

---

## STEP 1: Create `formatters/demo_flow.py`

```python
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

    fallback = "SalesCoach AI — Live Demo"
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

    fallback = f"Demo Step {step['step']}: {step['title']}"
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
    all_commands = "\n".join([f"`{s['command'].split()[0]}`" for s in DEMO_STEPS])

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

    fallback = "Demo Complete — SalesCoach AI"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.demo_flow import format_demo_welcome, format_demo_step_intro, format_demo_step_nav, format_demo_complete, DEMO_STEPS
```

And add all to `__all__`.

---

## STEP 3: Add `/demo-flow` Command Handler to `app.py`

```python
@app.command("/demo-flow")
def handle_demo_flow(ack, say, command):
    """Start a guided demo walkthrough."""
    ack()
    channel_id = command["channel_id"]

    from formatters import format_demo_welcome
    blocks, fallback = format_demo_welcome()
    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add the "Next" Action Handler

This is the core of `/demo-flow` — it triggers the actual commands programmatically:

```python
@app.action("demo_flow_next")
def handle_demo_flow_next(ack, body, say, client):
    """Execute the next demo step."""
    ack()
    step_index = int(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    from formatters.demo_flow import DEMO_STEPS, format_demo_step_intro, format_demo_step_nav, format_demo_complete

    if step_index >= len(DEMO_STEPS):
        # Demo complete
        blocks, fallback = format_demo_complete()
        say(text=fallback, blocks=blocks, channel=channel)
        return

    step = DEMO_STEPS[step_index]

    # Post the step intro
    intro_blocks, intro_fallback = format_demo_step_intro(step_index)
    say(text=intro_fallback, blocks=intro_blocks, channel=channel)

    # Execute the actual command
    # Parse the command and text from the step definition
    parts = step["command"].split(maxsplit=1)
    cmd = parts[0].lstrip("/")
    cmd_text = parts[1] if len(parts) > 1 else ""

    # Create a fake command dict to pass to the handler
    fake_command = {
        "text": cmd_text,
        "channel_id": channel,
        "user_id": user_id,
    }

    # Route to the appropriate handler
    try:
        handler_map = {
            "pipeline": lambda: handle_pipeline(lambda: None, say, fake_command) if 'handle_pipeline' in dir() else say("Run `/pipeline` to see this.", channel=channel),
            "deal": lambda: handle_deal(lambda: None, say, fake_command),
            "research": lambda: handle_research(lambda: None, say, fake_command),
            "battlecard": lambda: handle_battlecard(lambda: None, say, fake_command),
            "objection": lambda: handle_objection(lambda: None, say, fake_command),
            "ask": lambda: handle_ask(lambda: None, say, fake_command),
            "forecast": lambda: handle_forecast(lambda: None, say, fake_command),
            "persona": lambda: handle_persona(lambda: None, say, fake_command),
            "email-sequence": lambda: handle_email_sequence(lambda: None, say, fake_command),
            "coach": lambda: say("Try `/coach roleplay discovery call` to start a live roleplay session!", channel=channel),
        }

        handler = handler_map.get(cmd)
        if handler:
            handler()
        else:
            say(f"Command `/{cmd}` not found in demo flow.", channel=channel)
    except Exception as e:
        say(f"Error running demo step: {str(e)[:200]}", channel=channel)

    # Post navigation buttons
    nav_blocks = format_demo_step_nav(step_index)
    say(text="", blocks=nav_blocks, channel=channel)


@app.action("demo_flow_end")
def handle_demo_flow_end(ack, body, say):
    """End the demo."""
    ack()
    channel = body["channel"]["id"]

    from formatters.demo_flow import format_demo_complete
    blocks, fallback = format_demo_complete()
    say(text=fallback, blocks=blocks, channel=channel)
```

---

## REGISTER IN SLACK

Add `/demo-flow` slash command in api.slack.com:
- **Command:** `/demo-flow`
- **Description:** `Guided walkthrough of all AI capabilities`
- **Usage Hint:** (none)

---

## GOTCHAS

1. **Handler references** — The `handler_map` references functions by name. These must be defined BEFORE the demo-flow handler in `app.py`. If some expansions aren't built yet, the demo will gracefully fall through to a message suggesting the user try the command manually.

2. **`/coach roleplay`** is special — it requires threaded interaction, so the demo flow just suggests the command instead of running it inline. The presenter can run it manually as the finale.

3. **Rate limiting** — Each step makes API calls (say, LLM, etc.). Add a small delay if Slack rate-limits you. The "Next" button provides natural pacing.

4. **`ack()` passthrough** — When calling handlers programmatically, pass `lambda: None` as the `ack` argument since the action was already acknowledged.

5. **Demo step order matters** — The sequence is designed to tell a story: overview → detail → competitive → coaching → forecast → outreach → practice. Adjust the order in `DEMO_STEPS` if needed.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/demo_flow.py` | New formatter with DEMO_STEPS, welcome, step intro, nav, complete |
| EDIT | `formatters/__init__.py` | Add demo_flow exports |
| EDIT | `app.py` | Add `handle_demo_flow()`, `handle_demo_flow_next()`, `handle_demo_flow_end()` |
