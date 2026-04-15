# Update Demo Flow with Wave 3/4/5 Commands — Claude Code Instructions

**Goal:** Update `/demo-flow` to showcase the new Wave 3/4/5 features (`/my-day`, `/training`, `/team`) in addition to the existing 10 steps.

> **Read `formatters/demo_flow.py` and the `handle_demo_flow_next` function in `app.py` (around line 5265) before making changes.**

---

## CONTEXT

The current demo flow has 10 steps covering only Wave 1/2 commands. We need to add 4 new steps for the Wave 3/4/5 features, bringing the total to **14 steps**. The new steps showcase:

- `/my-day` — Calendar + meeting prep (Wave 5)
- `/training library` — Scenario library (Wave 3)
- `/training onboard @new-rep` — Onboarding program (Wave 4)
- `/team dashboard` — Manager team dashboard (Wave 3)

We're NOT demoing every subcommand — just the most visually impressive ones for a live demo audience.

---

## STEP 1: Update `DEMO_STEPS` in `formatters/demo_flow.py`

Replace the entire `DEMO_STEPS` list with this expanded 14-step version. The original 10 steps stay in positions 1–10, and the 4 new steps are added as 11–14.

### FIND (the full DEMO_STEPS list, lines ~6-77):

```python
DEMO_STEPS = [
    {
        "step": 1,
        "title": "Pipeline Overview",
```

...through to the closing `]` of DEMO_STEPS (line ~77).

### REPLACE WITH:

```python
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
    {
        "step": 11,
        "title": "My Day — Calendar & Meeting Prep",
        "command": "/my-day",
        "description": "See today's schedule with one-click meeting prep, deal context, and training reminders.",
        "emoji": "📅",
    },
    {
        "step": 12,
        "title": "Training Scenario Library",
        "command": "/training library",
        "description": "Browse the full scenario library — filter by type, difficulty, and skill area.",
        "emoji": "📚",
    },
    {
        "step": 13,
        "title": "New Hire Onboarding",
        "command": "/training onboard @new-rep",
        "description": "Auto-generate a 4-week onboarding program with weekly scenario assignments and milestones.",
        "emoji": "🚀",
    },
    {
        "step": 14,
        "title": "Team Dashboard",
        "command": "/team dashboard",
        "description": "Manager view — see team training progress, completion rates, and skill gaps at a glance.",
        "emoji": "👥",
    },
]
```

---

## STEP 2: Update `format_demo_complete` Available Commands in `formatters/demo_flow.py`

In the `format_demo_complete()` function (line ~214), update the "Available Commands" text block to include the new commands.

### FIND:

```python
                    "`/pipeline` • `/deal` • `/research` • `/battlecard` • `/objection` • "
                    "`/ask` • `/forecast` • `/persona` • `/email-sequence` • `/coach` • "
                    "`/handoff` • `/win-loss` • `/alerts` • `/coach-live` • `/demo-flow`"
```

### REPLACE WITH:

```python
                    "`/pipeline` • `/deal` • `/research` • `/battlecard` • `/objection` • "
                    "`/ask` • `/forecast` • `/persona` • `/email-sequence` • `/coach` • "
                    "`/handoff` • `/win-loss` • `/alerts` • `/coach-live` • `/my-day` • "
                    "`/training` • `/team` • `/demo-flow`"
```

---

## STEP 3: Update the `handle_demo_flow_next` handler routing in `app.py`

In `app.py`, in the `handle_demo_flow_next` function (around line 5301), add routing for the 3 new commands. The current `if/elif` chain handles commands by their first token (e.g., `cmd == "pipeline"`).

### FIND the routing block (lines ~5302-5323):

```python
        if cmd == "pipeline":
            handle_pipeline(lambda: None, say, fake_command)
        elif cmd == "deal":
            handle_deal(lambda: None, say, fake_command)
        elif cmd == "research":
            handle_research(lambda: None, say, fake_command)
        elif cmd == "battlecard":
            handle_battlecard(lambda: None, say, fake_command)
        elif cmd == "objection":
            handle_objection(lambda: None, say, fake_command)
        elif cmd == "ask":
            handle_ask(lambda: None, say, fake_command)
        elif cmd == "forecast":
            handle_forecast(lambda: None, say, fake_command)
        elif cmd == "persona":
            handle_persona(lambda: None, say, fake_command)
        elif cmd == "email-sequence":
            handle_email_sequence(lambda: None, say, fake_command)
        elif cmd == "coach":
            say("Try `/coach roleplay discovery call` to start a live roleplay session!", channel=channel)
        else:
            say(f"Command `/{cmd}` not found in demo flow.", channel=channel)
```

### REPLACE WITH:

```python
        if cmd == "pipeline":
            handle_pipeline(lambda: None, say, fake_command)
        elif cmd == "deal":
            handle_deal(lambda: None, say, fake_command)
        elif cmd == "research":
            handle_research(lambda: None, say, fake_command)
        elif cmd == "battlecard":
            handle_battlecard(lambda: None, say, fake_command)
        elif cmd == "objection":
            handle_objection(lambda: None, say, fake_command)
        elif cmd == "ask":
            handle_ask(lambda: None, say, fake_command)
        elif cmd == "forecast":
            handle_forecast(lambda: None, say, fake_command)
        elif cmd == "persona":
            handle_persona(lambda: None, say, fake_command)
        elif cmd == "email-sequence":
            handle_email_sequence(lambda: None, say, fake_command)
        elif cmd == "coach":
            say("Try `/coach roleplay discovery call` to start a live roleplay session!", channel=channel)
        elif cmd == "my-day":
            handle_my_day(lambda: None, fake_command, say)
        elif cmd == "training":
            handle_training(lambda: None, fake_command, say, client)
        elif cmd == "team":
            handle_team(lambda: None, fake_command, say, client)
        else:
            say(f"Command `/{cmd}` not found in demo flow.", channel=channel)
```

**IMPORTANT — Argument order:** Check the actual function signatures before applying:
- `handle_my_day(ack, command, say)` — so pass `(lambda: None, fake_command, say)`
- `handle_training(ack, command, say, client)` — so pass `(lambda: None, fake_command, say, client)`
- `handle_team(ack, command, say, client)` — so pass `(lambda: None, fake_command, say, client)`

These match the existing handler signatures. The `client` variable is already available in `handle_demo_flow_next` (it's in the function args: `ack, body, say, client`).

---

## STEP 4: Update `EXPANSION-18-DEMO-FLOW.md` (optional — for doc consistency)

Update the instruction doc `EXPANSION-18-DEMO-FLOW.md` to reflect the new 14-step sequence. In the `DEMO_STEPS` list in the markdown, add the same 4 new steps. Also update the handler routing block and the demo complete available commands list.

This is optional — the code changes in Steps 1-3 are what matters.

---

## TESTING

1. Run `/demo-flow` — should show welcome card listing **14 features** (not 10)
2. Click through all 14 steps — each should trigger the correct handler
3. Steps 11-14 specifically:
   - Step 11 (`/my-day`) — shows today's calendar with Prep/Join buttons
   - Step 12 (`/training library`) — shows scenario library
   - Step 13 (`/training onboard @new-rep`) — shows onboarding program
   - Step 14 (`/team dashboard`) — shows team performance dashboard
4. "Demo Complete" card should list all commands including `/my-day`, `/training`, `/team`
5. Progress bar should show 14 segments instead of 10

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `formatters/demo_flow.py` | Expand `DEMO_STEPS` from 10 → 14 entries; update `format_demo_complete` available commands |
| EDIT | `app.py` | Add `my-day`, `training`, `team` routes to `handle_demo_flow_next` |
| EDIT (optional) | `EXPANSION-18-DEMO-FLOW.md` | Update doc to match new 14-step sequence |
