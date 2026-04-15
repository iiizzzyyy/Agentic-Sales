# Wave 4 — Cohort Learning, Onboarding, Product Launch Training

Features #17, #13, #23. Multi-week structured training programs.

**Depends on:** Wave 3 (scenarios + assignments)

---

## Feature #17: Cohort-Based Learning Cycles

### Step 1: Add DB Functions to `db.py`

```python
# ──────────────────────────────────────────────
# Cohorts
# ──────────────────────────────────────────────

def create_cohort(name, description, created_by, participants, weeks_config,
                  graduation_min_avg=7.0, graduation_min_completion=0.9):
    """Create a cohort with weeks and scenario assignments.

    Args:
        weeks_config: list of dicts [{label, scenario_ids, min_score, start_date, end_date}]
        participants: list of user_id strings
    Returns cohort_id.
    """
    cohort_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO cohorts (id, name, description, created_by, graduation_min_avg_score, graduation_min_completion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cohort_id, name, description, created_by, graduation_min_avg, graduation_min_completion))

        # Add participants
        for uid in participants:
            conn.execute("INSERT INTO cohort_participants (cohort_id, user_id) VALUES (?, ?)", (cohort_id, uid))

        # Add weeks and their scenarios
        for i, week in enumerate(weeks_config):
            conn.execute("""
                INSERT INTO cohort_weeks (cohort_id, week_number, label, min_score, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cohort_id, i + 1, week.get("label", f"Week {i+1}"), week.get("min_score", 6.0),
                  week.get("start_date"), week.get("end_date")))

            week_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for sid in week.get("scenario_ids", []):
                conn.execute("INSERT INTO cohort_week_scenarios (week_id, scenario_id) VALUES (?, ?)", (week_id, sid))

    return cohort_id


def get_cohort(cohort_id):
    """Get full cohort details including weeks, scenarios, and participant progress."""
    with get_db() as conn:
        cohort = conn.execute("SELECT * FROM cohorts WHERE id = ?", (cohort_id,)).fetchone()
        if not cohort:
            return None
        result = dict(cohort)

        # Participants
        result["participants"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM cohort_participants WHERE cohort_id = ?", (cohort_id,)
            ).fetchall()
        ]

        # Weeks with scenarios
        weeks = conn.execute(
            "SELECT * FROM cohort_weeks WHERE cohort_id = ? ORDER BY week_number", (cohort_id,)
        ).fetchall()
        result["weeks"] = []
        for w in weeks:
            week_dict = dict(w)
            scenarios = conn.execute("""
                SELECT s.* FROM scenarios s
                JOIN cohort_week_scenarios cws ON s.id = cws.scenario_id
                WHERE cws.week_id = ?
            """, (w["id"],)).fetchall()
            week_dict["scenarios"] = [dict(s) for s in scenarios]
            result["weeks"].append(week_dict)

        return result


def get_cohort_progress(cohort_id):
    """Get per-participant progress through the cohort."""
    cohort = get_cohort(cohort_id)
    if not cohort:
        return None

    progress = []
    with get_db() as conn:
        for participant in cohort["participants"]:
            uid = participant["user_id"]
            user_progress = {"user_id": uid, "weeks": []}

            for week in cohort["weeks"]:
                week_scenarios = week["scenarios"]
                completions = []
                for scenario in week_scenarios:
                    # Check if user completed this scenario
                    session = conn.execute("""
                        SELECT overall_score FROM training_sessions
                        WHERE user_id = ? AND scenario_id = ?
                        ORDER BY timestamp DESC LIMIT 1
                    """, (uid, scenario["id"])).fetchone()

                    completions.append({
                        "scenario_id": scenario["id"],
                        "scenario_name": scenario.get("name", "Unknown"),
                        "completed": session is not None,
                        "score": session["overall_score"] if session else None,
                    })

                total = len(completions)
                done = sum(1 for c in completions if c["completed"])
                avg_score = sum(c["score"] for c in completions if c["score"]) / max(done, 1) if done else 0

                user_progress["weeks"].append({
                    "week_number": week["week_number"],
                    "label": week["label"],
                    "min_score": week["min_score"],
                    "total_scenarios": total,
                    "completed_scenarios": done,
                    "avg_score": round(avg_score, 1),
                    "completions": completions,
                })

            progress.append(user_progress)

    return {"cohort": cohort, "progress": progress}


def list_cohorts(status="active"):
    """List cohorts filtered by status."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM cohorts WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        return [dict(r) for r in rows]
```

### Step 2: Add `/create-cohort` Command

Since Slack modals can't handle dynamic week configuration well, use a thread-based approach:

```python
@app.command("/create-cohort")
def handle_create_cohort(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()
    log_engagement(user_id, "command", command="/create-cohort")

    # Parse: /create-cohort "Program Name" @user1 @user2 --weeks 4
    import re
    name_match = re.search(r'"([^"]+)"', text)
    user_matches = re.findall(r'<@(\w+)(?:\|[^>]*)?>', text)
    weeks_match = re.search(r'--weeks\s+(\d+)', text)

    if not name_match or not user_matches:
        say(channel=channel_id, text='Usage: `/create-cohort "Program Name" @user1 @user2 --weeks 4`')
        return

    program_name = name_match.group(1)
    num_weeks = int(weeks_match.group(1)) if weeks_match else 4

    # Store setup state, ask for week configuration in thread
    msg = client.chat_postMessage(
        channel=channel_id,
        text=(
            f"📚 *Creating: {program_name}*\n"
            f"Participants: {', '.join(f'<@{u}>' for u in user_matches)}\n"
            f"Duration: {num_weeks} weeks\n\n"
            f"Now configure each week. Reply in this thread with scenario IDs for each week.\n"
            f"Format: `week 1: scenario_id_1, scenario_id_2 | min_score: 6`\n"
            f"Or type `auto` to auto-populate from the scenario library.\n"
            f"When done, type `create` to finalize."
        )
    )

    # Store in-progress cohort config (in-memory, keyed by thread_ts)
    # This is stored in a dict on app for simplicity
    if not hasattr(app, '_cohort_drafts'):
        app._cohort_drafts = {}

    app._cohort_drafts[msg["ts"]] = {
        "name": program_name,
        "created_by": user_id,
        "participants": user_matches,
        "num_weeks": num_weeks,
        "weeks": {},
        "channel": channel_id,
    }
```

Add a message handler that listens in cohort configuration threads and processes `week N:` and `create` messages. When `create` is received, build the cohort with `create_cohort()` and auto-assign week 1 scenarios to all participants.

### Step 3: Add `/cohort-progress` Command

```python
@app.command("/cohort-progress")
def handle_cohort_progress(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()
    log_engagement(user_id, "command", command="/cohort-progress")

    cohorts = list_cohorts(status="active")
    if not cohorts:
        say(channel=channel_id, text="No active training programs. Use `/create-cohort` to start one.")
        return

    # If name provided, find that cohort; otherwise show the first/most recent
    target = cohorts[0]
    if text:
        matches = [c for c in cohorts if text.lower() in c["name"].lower()]
        if matches:
            target = matches[0]

    data = get_cohort_progress(target["id"])
    if not data:
        say(channel=channel_id, text="Could not load progress data.")
        return

    blocks, fallback = format_cohort_progress(data)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

### Step 4: Create `formatters/cohort.py`

Build Block Kit blocks showing: program name, per-participant progress bars, per-week scenario completion grid, overall status (on track / behind / at risk).

The progress bar uses Unicode block characters: `████████░░` for visual percentage.

```python
def _progress_bar(completed, total, width=10):
    if total == 0:
        return "░" * width
    filled = int((completed / total) * width)
    return "█" * filled + "░" * (width - filled)
```

---

## Feature #13: Structured Onboarding (`/onboard`)

### Step 1: Create Onboarding Template

Create `data/cohort_templates/new_hire_onboard.json`:

```json
{
  "name": "New Hire Sales Onboarding",
  "description": "4-week progressive training program for new sales reps",
  "weeks": [
    {
      "label": "Foundation",
      "min_score": 5.0,
      "scenarios": [
        {"name": "Cold Call: Friendly Gatekeeper", "type": "cold_call", "difficulty": "beginner",
         "persona": {"description": "Friendly receptionist at a mid-size company. Will transfer if given a good reason."},
         "objectives": ["Get past the gatekeeper", "Secure a 15-min meeting with the decision maker"]},
        {"name": "Discovery: SMB Owner", "type": "discovery", "difficulty": "beginner",
         "persona": {"description": "Small business owner, open to new ideas but time-pressed. Has 10 minutes."},
         "objectives": ["Identify 2 pain points", "Establish next step"]}
      ]
    },
    {
      "label": "Core Skills",
      "min_score": 6.0,
      "scenarios": [
        {"name": "Objection Handling: Budget", "type": "objection", "difficulty": "intermediate",
         "persona": {"description": "VP of Operations, interested but claims budget is locked for the quarter."},
         "objectives": ["Acknowledge the concern", "Reframe around ROI", "Get creative on timing"]},
        {"name": "Competitive: Incumbent Vendor", "type": "competitive", "difficulty": "intermediate",
         "persona": {"description": "IT Director, happy with current solution but open to hearing alternatives."},
         "objectives": ["Differentiate without bashing competitor", "Find unmet needs"]}
      ]
    },
    {
      "label": "Advanced",
      "min_score": 6.5,
      "scenarios": [
        {"name": "Discovery: Enterprise CFO", "type": "discovery", "difficulty": "advanced",
         "persona": {"description": "CFO at Fortune 500, analytical, skeptical. Needs hard data."},
         "objectives": ["Quantify business impact", "Map decision process", "Identify champion"]},
        {"name": "Negotiation: Multi-Stakeholder", "type": "negotiation", "difficulty": "advanced",
         "persona": {"description": "Procurement lead with engineering sponsor. Procurement wants discount, engineering wants features."},
         "objectives": ["Balance both stakeholders", "Protect pricing", "Create mutual value"]}
      ]
    },
    {
      "label": "Graduation",
      "min_score": 7.0,
      "scenarios": [
        {"name": "Full Cycle: Enterprise Deal", "type": "discovery", "difficulty": "expert",
         "persona": {"description": "CTO evaluating your solution against 2 competitors. Has budget but needs board approval. Complex 6-month decision process."},
         "objectives": ["Run full discovery", "Handle 3+ objections", "Secure concrete next step", "Score 7+/10 to graduate"]}
      ]
    }
  ]
}
```

### Step 2: Add `/onboard` Command

```python
@app.command("/onboard")
def handle_onboard(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip()
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/onboard")

    # Parse target user
    import re
    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', text)
    if not user_match:
        say(channel=channel_id, text="Usage: `/onboard @new-rep`")
        return

    target_user = user_match.group(1)

    # Load template
    template_path = os.path.join(DATA_DIR, "cohort_templates", "new_hire_onboard.json")
    with open(template_path) as f:
        template = json.load(f)

    # Create scenarios from template (save each to the library)
    from db import save_scenario, create_cohort, create_assignment
    from datetime import datetime, timedelta

    weeks_config = []
    start_date = datetime.now()

    for i, week in enumerate(template["weeks"]):
        scenario_ids = []
        for s in week["scenarios"]:
            sid = save_scenario(
                name=s["name"], type=s["type"], difficulty=s["difficulty"],
                created_by=user_id, persona=s["persona"],
                objectives=s.get("objectives", []),
                tags=["onboarding", f"week_{i+1}"],
            )
            scenario_ids.append(sid)

        week_start = start_date + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        weeks_config.append({
            "label": week["label"],
            "scenario_ids": scenario_ids,
            "min_score": week["min_score"],
            "start_date": week_start.strftime("%Y-%m-%d"),
            "end_date": week_end.strftime("%Y-%m-%d"),
        })

    # Create the cohort
    cohort_id = create_cohort(
        name=f"{template['name']} — <@{target_user}>",
        description=template["description"],
        created_by=user_id,
        participants=[target_user],
        weeks_config=weeks_config,
    )

    # Auto-assign Week 1 scenarios
    for sid in weeks_config[0]["scenario_ids"]:
        create_assignment(sid, user_id, target_user, due_date=weeks_config[0]["end_date"])

    # DM the new rep
    dm = client.conversations_open(users=[target_user])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=(
            f"👋 *Welcome to SalesCoach AI!*\n\n"
            f"<@{user_id}> has enrolled you in a 4-week onboarding program.\n\n"
            f"*Week 1: {weeks_config[0]['label']}* — {len(weeks_config[0]['scenario_ids'])} scenarios to complete by {weeks_config[0]['end_date']}\n\n"
            f"Check your Home tab for assignments, or type `/training-history` to track your progress."
        )
    )

    say(channel=channel_id, text=f"✅ Onboarding program created for <@{target_user}>. 4 weeks, {sum(len(w['scenario_ids']) for w in weeks_config)} scenarios. Week 1 assigned.")
```

---

## Feature #23: Product Launch Training

### Step 1: Add `/launch-training` Command

```python
@app.command("/launch-training")
def handle_launch_training(ack, command, client):
    ack()
    trigger_id = command["trigger_id"]
    user_id = command["user_id"]
    log_engagement(user_id, "command", command="/launch-training")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "launch_training_modal",
            "title": {"type": "plain_text", "text": "Launch Training"},
            "submit": {"type": "plain_text", "text": "Generate & Launch"},
            "blocks": [
                {"type": "input", "block_id": "product_name_block",
                 "label": {"type": "plain_text", "text": "Product Name"},
                 "element": {"type": "plain_text_input", "action_id": "product_name",
                             "placeholder": {"type": "plain_text", "text": "CloudSync Enterprise"}}},
                {"type": "input", "block_id": "product_desc_block",
                 "label": {"type": "plain_text", "text": "Product Description & Key Features"},
                 "element": {"type": "plain_text_input", "action_id": "product_desc", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "Describe the product, its key features, target audience, pricing, and competitive positioning..."}}},
                {"type": "input", "block_id": "competitors_block",
                 "label": {"type": "plain_text", "text": "Main Competitors"},
                 "element": {"type": "plain_text_input", "action_id": "competitors",
                             "placeholder": {"type": "plain_text", "text": "Competitor A, Competitor B"}},
                 "optional": True},
                {"type": "input", "block_id": "team_block",
                 "label": {"type": "plain_text", "text": "Team Members (mention with @)"},
                 "element": {"type": "plain_text_input", "action_id": "team",
                             "placeholder": {"type": "plain_text", "text": "@sarah @mike @alex"}}},
            ]
        }
    )


@app.view("launch_training_modal")
def handle_launch_training_submit(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    v = view["state"]["values"]

    product_name = v["product_name_block"]["product_name"]["value"]
    product_desc = v["product_desc_block"]["product_desc"]["value"]
    competitors = v.get("competitors_block", {}).get("competitors", {}).get("value", "")
    team_text = v["team_block"]["team"]["value"]

    import re
    team_users = re.findall(r'<@(\w+)(?:\|[^>]*)?>', team_text)

    # Use LLM to generate scenarios from product info
    from llm_factory import get_llm
    llm = get_llm()

    generation_prompt = f"""Generate 5 sales roleplay scenarios for training reps on a new product.

Product: {product_name}
Description: {product_desc}
Competitors: {competitors}

For each scenario, output a JSON array with objects containing:
- name: Scenario name
- type: One of [cold_call, discovery, objection, competitive, negotiation]
- difficulty: One of [beginner, intermediate, advanced]
- persona: {{description: "...", objections: ["..."]}}
- objectives: ["..."]

Output ONLY the JSON array, no other text."""

    response = llm.invoke(generation_prompt)

    # Parse generated scenarios
    try:
        import json
        scenarios_data = json.loads(response.content)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            scenarios_data = json.loads(match.group(0))
        else:
            # Notify failure
            dm = client.conversations_open(users=[user_id])
            client.chat_postMessage(channel=dm["channel"]["id"],
                text=f"⚠️ Failed to generate scenarios for {product_name}. Try again with more product detail.")
            return

    # Save scenarios and create 2-week cohort
    from db import save_scenario, create_cohort, create_assignment
    from datetime import datetime, timedelta

    scenario_ids = []
    for s in scenarios_data:
        sid = save_scenario(
            name=s["name"], type=s["type"], difficulty=s.get("difficulty", "intermediate"),
            created_by=user_id, persona=s.get("persona", {"description": "Business executive"}),
            objectives=s.get("objectives", []),
            tags=["product_launch", product_name.lower().replace(" ", "_")],
            product_context=product_desc[:500],
        )
        scenario_ids.append(sid)

    # Split into 2 weeks
    mid = len(scenario_ids) // 2
    weeks_config = [
        {"label": f"{product_name} — Fundamentals", "scenario_ids": scenario_ids[:mid or 1],
         "min_score": 6.0, "start_date": datetime.now().strftime("%Y-%m-%d"),
         "end_date": (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")},
        {"label": f"{product_name} — Advanced", "scenario_ids": scenario_ids[mid or 1:],
         "min_score": 6.5, "start_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
         "end_date": (datetime.now() + timedelta(days=13)).strftime("%Y-%m-%d")},
    ]

    cohort_id = create_cohort(
        name=f"Product Launch: {product_name}",
        description=f"Training sprint for {product_name} launch",
        created_by=user_id,
        participants=team_users,
        weeks_config=weeks_config,
    )

    # Auto-assign week 1 and DM all reps
    for uid in team_users:
        for sid in weeks_config[0]["scenario_ids"]:
            create_assignment(sid, user_id, uid, due_date=weeks_config[0]["end_date"])

        dm = client.conversations_open(users=[uid])
        client.chat_postMessage(channel=dm["channel"]["id"],
            text=(f"🚀 *New Product Training: {product_name}*\n"
                  f"<@{user_id}> launched a 2-week training sprint. "
                  f"{len(scenario_ids)} scenarios to practice.\n"
                  f"Check your Home tab for assignments."))

    # Confirm to manager
    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(channel=dm["channel"]["id"],
        text=(f"✅ *Product Launch Training Created: {product_name}*\n"
              f"Generated {len(scenario_ids)} scenarios for {len(team_users)} reps.\n"
              f"2-week program started. Use `/cohort-progress {product_name}` to track."))
```

## DO NOT
- Do not generate more than 6 scenarios per product launch (LLM quality degrades)
- Do not auto-assign all weeks upfront — only assign the current week
- Do not let cohort creation exceed Slack's 3-second modal timeout — use background processing for LLM calls
- Do not overwrite existing scenarios with the same name — always create new ones

## Testing
1. `/onboard @user` → creates 4-week program → user gets DM → check Home tab for week 1 assignments
2. `/cohort-progress` → shows progress grid with completion status
3. `/launch-training` → fill modal with product info → generates 5 scenarios → creates 2-week cohort → team gets DMs
4. `/scenarios` → should now include the onboarding and product launch scenarios tagged appropriately
