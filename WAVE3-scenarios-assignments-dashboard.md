# Wave 3 — Simulation Builder, Scenario Assignment, Team Dashboard

Features #14, #20, #15. Manager-facing tools for creating, assigning, and tracking training.

**Depends on:** Wave 1 (SQLite + training data) + Wave 2 (skill gaps + methodologies)

---

## Feature #14: Simulation Builder (`/create-scenario`, `/scenarios`)

### Step 1: Add DB Helper Functions to `db.py`

Add these functions to the bottom of `db.py`:

```python
# ──────────────────────────────────────────────
# Scenarios
# ──────────────────────────────────────────────

def save_scenario(name, type, difficulty, created_by, persona, objectives=None,
                  scoring_methodology="discovery", tags=None, product_context=None):
    """Save a new scenario to the library. Returns scenario_id."""
    scenario_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO scenarios (id, name, type, difficulty, created_by, persona,
                                   objectives, scoring_methodology, tags, product_context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scenario_id, name, type, difficulty, created_by,
            json.dumps(persona) if isinstance(persona, dict) else persona,
            json.dumps(objectives) if objectives else None,
            scoring_methodology,
            json.dumps(tags) if tags else None,
            product_context,
        ))
    return scenario_id


def get_scenario(scenario_id):
    """Get a single scenario by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if row:
            result = dict(row)
            for field in ["persona", "objectives", "tags"]:
                if result.get(field):
                    try:
                        result[field] = json.loads(result[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return result
    return None


def list_scenarios(type_filter=None, difficulty_filter=None, limit=20):
    """List scenarios with optional filters."""
    with get_db() as conn:
        query = "SELECT * FROM scenarios WHERE 1=1"
        params = []
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)
        if difficulty_filter:
            query += " AND difficulty = ?"
            params.append(difficulty_filter)
        query += " ORDER BY usage_count DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            for field in ["persona", "objectives", "tags"]:
                if r.get(field):
                    try:
                        r[field] = json.loads(r[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(r)
        return results


def increment_scenario_usage(scenario_id, score=None):
    """Increment usage count and update rolling average score."""
    with get_db() as conn:
        if score is not None:
            conn.execute("""
                UPDATE scenarios SET
                    usage_count = usage_count + 1,
                    avg_score = CASE
                        WHEN avg_score IS NULL THEN ?
                        ELSE (avg_score * usage_count + ?) / (usage_count + 1)
                    END
                WHERE id = ?
            """, (score, score, scenario_id))
        else:
            conn.execute("UPDATE scenarios SET usage_count = usage_count + 1 WHERE id = ?", (scenario_id,))
```

### Step 2: Add `/create-scenario` Command with Modal

In `app.py`:

```python
@app.command("/create-scenario")
def handle_create_scenario(ack, command, client):
    ack()
    trigger_id = command["trigger_id"]
    user_id = command["user_id"]
    log_engagement(user_id, "command", command="/create-scenario")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "create_scenario_modal",
            "title": {"type": "plain_text", "text": "Create Scenario"},
            "submit": {"type": "plain_text", "text": "Save Scenario"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {"type": "input", "block_id": "name_block", "label": {"type": "plain_text", "text": "Scenario Name"},
                 "element": {"type": "plain_text_input", "action_id": "name", "placeholder": {"type": "plain_text", "text": "Discovery Call: Enterprise CFO"}}},

                {"type": "input", "block_id": "type_block", "label": {"type": "plain_text", "text": "Type"},
                 "element": {"type": "static_select", "action_id": "type", "options": [
                     {"text": {"type": "plain_text", "text": t.title()}, "value": t}
                     for t in ["discovery", "negotiation", "competitive", "cold_call", "objection", "custom"]
                 ]}},

                {"type": "input", "block_id": "difficulty_block", "label": {"type": "plain_text", "text": "Difficulty"},
                 "element": {"type": "static_select", "action_id": "difficulty", "options": [
                     {"text": {"type": "plain_text", "text": d.title()}, "value": d}
                     for d in ["beginner", "intermediate", "advanced", "expert"]
                 ]}},

                {"type": "input", "block_id": "persona_block", "label": {"type": "plain_text", "text": "Buyer Persona"},
                 "element": {"type": "plain_text_input", "action_id": "persona", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "Name, title, company, personality, background. Be specific about their attitude and objections."}}},

                {"type": "input", "block_id": "objectives_block", "label": {"type": "plain_text", "text": "Rep Objectives"},
                 "element": {"type": "plain_text_input", "action_id": "objectives", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "One per line:\nUncover 3 pain points\nIdentify the decision maker\nGet agreement on a demo"}}},

                {"type": "input", "block_id": "objections_block", "label": {"type": "plain_text", "text": "Key Objections the Buyer Will Raise"},
                 "element": {"type": "plain_text_input", "action_id": "objections", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "One per line:\nBudget is frozen until Q3\nAlready have an in-house solution\nNeed to see ROI proof"}},
                 "optional": True},

                {"type": "input", "block_id": "methodology_block", "label": {"type": "plain_text", "text": "Scoring Methodology"},
                 "element": {"type": "static_select", "action_id": "methodology", "initial_option":
                     {"text": {"type": "plain_text", "text": "Default"}, "value": "discovery"},
                     "options": [
                         {"text": {"type": "plain_text", "text": "Default"}, "value": "discovery"},
                         {"text": {"type": "plain_text", "text": "MEDDIC"}, "value": "meddic"},
                         {"text": {"type": "plain_text", "text": "SPIN"}, "value": "spin"},
                         {"text": {"type": "plain_text", "text": "Challenger"}, "value": "challenger"},
                         {"text": {"type": "plain_text", "text": "BANT"}, "value": "bant"},
                     ]}},
            ]
        }
    )


@app.view("create_scenario_modal")
def handle_create_scenario_submit(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    v = view["state"]["values"]

    name = v["name_block"]["name"]["value"]
    type_ = v["type_block"]["type"]["selected_option"]["value"]
    difficulty = v["difficulty_block"]["difficulty"]["selected_option"]["value"]
    persona_text = v["persona_block"]["persona"]["value"]
    objectives_text = v["objectives_block"]["objectives"]["value"]
    objections_text = v.get("objections_block", {}).get("objections", {}).get("value", "")
    methodology = v["methodology_block"]["methodology"]["selected_option"]["value"]

    # Parse persona into structured dict
    persona = {
        "description": persona_text,
        "objections": [o.strip() for o in objections_text.split("\n") if o.strip()] if objections_text else [],
    }
    objectives = [o.strip() for o in objectives_text.split("\n") if o.strip()]

    from db import save_scenario
    scenario_id = save_scenario(
        name=name, type=type_, difficulty=difficulty, created_by=user_id,
        persona=persona, objectives=objectives, scoring_methodology=methodology,
        tags=[type_, difficulty],
    )

    # DM confirmation
    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=f"✅ Scenario saved: *{name}* ({type_.title()} · {difficulty.title()})\nID: `{scenario_id}`\nUse `/scenarios` to browse or `/assign @rep {scenario_id}` to assign."
    )
```

### Step 3: Add `/scenarios` Command

```python
from db import list_scenarios

@app.command("/scenarios")
def handle_scenarios(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/scenarios")

    scenarios = list_scenarios()
    if not scenarios:
        say(channel=channel_id, text="No scenarios saved yet. Use `/create-scenario` to build your first one.")
        return

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Scenario Library", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{len(scenarios)} scenarios available"}]},
        {"type": "divider"},
    ]

    for s in scenarios[:15]:  # Cap at 15 for block limits
        score_display = f"{s['avg_score']:.1f}/10" if s.get("avg_score") else "Not yet scored"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*{s['name']}*\n"
                f"{s['type'].title()} · {s['difficulty'].title()} · "
                f"Practiced {s.get('usage_count', 0)}x · Avg: {score_display}"
            )},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice", "emoji": True},
                "action_id": "start_saved_scenario",
                "value": s["id"],
            }
        })

    from formatters.helpers import timestamp
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]})
    say(channel=channel_id, text=f"Scenario Library: {len(scenarios)} scenarios", blocks=blocks)
```

### Step 4: Integrate Saved Scenarios with Roleplay

Add an action handler for `start_saved_scenario`:

```python
@app.action("start_saved_scenario")
def handle_start_saved_scenario(ack, body, client):
    ack()
    scenario_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]

    from db import get_scenario, increment_scenario_usage
    scenario = get_scenario(scenario_id)
    if not scenario:
        client.chat_postEphemeral(channel=channel, user=user_id, text="Scenario not found.")
        return

    increment_scenario_usage(scenario_id)

    # Build the roleplay prompt from the saved scenario
    persona = scenario.get("persona", {})
    objectives = scenario.get("objectives", [])

    roleplay_prompt = f"""Scenario: {scenario['name']}
Difficulty: {scenario['difficulty']}
Buyer Persona: {persona.get('description', 'A business executive')}
Buyer Objections: {', '.join(persona.get('objections', []))}
Rep Objectives: {', '.join(objectives)}"""

    # Start the roleplay with this specific scenario
    # Reuse existing _start_roleplay logic but pass scenario_id and methodology
    _start_roleplay(
        client, channel, None, user_id,
        scenario=roleplay_prompt,
        scenario_id=scenario_id,
        methodology=scenario.get("scoring_methodology", "discovery"),
        company=persona.get("company", ""),
    )
```

---

## Feature #20: Manager Scenario Assignment

### Step 1: Add DB Functions to `db.py`

```python
# ──────────────────────────────────────────────
# Assignments
# ──────────────────────────────────────────────

def create_assignment(scenario_id, assigned_by, assigned_to, due_date=None):
    """Create a training assignment. Returns assignment_id."""
    assignment_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO assignments (id, scenario_id, assigned_by, assigned_to, due_date)
            VALUES (?, ?, ?, ?, ?)
        """, (assignment_id, scenario_id, assigned_by, assigned_to, due_date))
    return assignment_id


def get_user_assignments(user_id, status="pending"):
    """Get assignments for a user filtered by status."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.*, s.name as scenario_name, s.type as scenario_type,
                   s.difficulty as scenario_difficulty
            FROM assignments a
            JOIN scenarios s ON a.scenario_id = s.id
            WHERE a.assigned_to = ? AND a.status = ?
            ORDER BY a.due_date ASC NULLS LAST
        """, (user_id, status)).fetchall()
        return [dict(r) for r in rows]


def complete_assignment(assignment_id, session_id, score):
    """Mark an assignment as completed with the training session results."""
    with get_db() as conn:
        conn.execute("""
            UPDATE assignments SET status = 'completed', completed_at = datetime('now'),
                   session_id = ?, score = ?
            WHERE id = ?
        """, (session_id, score, assignment_id))


def get_team_assignments_summary():
    """Get assignment counts by status for team dashboard."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) as count FROM assignments GROUP BY status
        """).fetchall()
        return {r["status"]: r["count"] for r in rows}
```

### Step 2: Add `/assign` Command

```python
@app.command("/assign")
def handle_assign(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip()
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/assign")

    # Parse: /assign @user scenario-id [--due YYYY-MM-DD]
    import re
    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', text)
    if not user_match:
        say(channel=channel_id, text="Usage: `/assign @rep scenario-id`\nExample: `/assign @sarah abc123 --due 2026-03-19`")
        return

    target_user = user_match.group(1)
    remaining = text[user_match.end():].strip()

    # Parse due date
    due_date = None
    due_match = re.search(r'--due\s+(\d{4}-\d{2}-\d{2})', remaining)
    if due_match:
        due_date = due_match.group(1)
        remaining = remaining[:due_match.start()].strip()

    scenario_id = remaining.strip()
    if not scenario_id:
        # Show scenario picker
        say(channel=channel_id, text="Please provide a scenario ID. Run `/scenarios` to see available scenarios.")
        return

    from db import get_scenario, create_assignment
    scenario = get_scenario(scenario_id)
    if not scenario:
        say(channel=channel_id, text=f"Scenario `{scenario_id}` not found. Run `/scenarios` to browse.")
        return

    assignment_id = create_assignment(scenario_id, user_id, target_user, due_date)

    # Notify the assigned rep via DM
    dm = client.conversations_open(users=[target_user])
    due_text = f" Due by {due_date}." if due_date else ""
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=(
            f"📋 *New Training Assignment*\n"
            f"<@{user_id}> assigned you: *{scenario['name']}* ({scenario['type'].title()} · {scenario['difficulty'].title()}){due_text}"
        ),
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": (
                f"📋 *New Training Assignment*\n"
                f"<@{user_id}> assigned you: *{scenario['name']}*\n"
                f"{scenario['type'].title()} · {scenario['difficulty'].title()}{f' · Due {due_date}' if due_date else ''}"
            )}},
            {"type": "actions", "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice", "emoji": True},
                "action_id": "start_saved_scenario",
                "value": scenario_id,
                "style": "primary",
            }]},
        ]
    )

    say(channel=channel_id, text=f"✅ Assigned *{scenario['name']}* to <@{target_user}>.{due_text}")
```

### Step 3: Update Home Tab with Assignments

In `formatters/home_tab.py`, add an assignments section at the top of the Home tab blocks:

```python
from db import get_user_assignments

def _build_assignments_section(user_id):
    """Build Block Kit blocks for pending assignments."""
    assignments = get_user_assignments(user_id, status="pending")
    if not assignments:
        return []

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Your Assignments ({len(assignments)})", "emoji": True}},
    ]

    for a in assignments[:5]:
        due_text = f" · Due {a['due_date']}" if a.get("due_date") else ""
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*{a['scenario_name']}*\n"
                f"{a['scenario_type'].title()} · {a['scenario_difficulty'].title()}"
                f"{due_text} · Assigned by <@{a['assigned_by']}>"
            )},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice", "emoji": True},
                "action_id": "start_saved_scenario",
                "value": a["scenario_id"],
                "style": "primary",
            }
        })

    blocks.append({"type": "divider"})
    return blocks
```

Call `_build_assignments_section(user_id)` at the top when building the Home tab view.

---

## Feature #15: Team Performance Dashboard

### Step 1: Create `formatters/team_dashboard.py`

```python
"""Block Kit formatter for manager team dashboard."""
import json
from formatters.helpers import timestamp


def format_team_dashboard(team_data, skill_heatmap, assignment_summary, engagement_data):
    """Format team dashboard as Block Kit blocks.

    Args:
        team_data: list from get_team_training_summary()
        skill_heatmap: dict of {user_id: {dimension: avg_score}}
        assignment_summary: dict from get_team_assignments_summary()
        engagement_data: list from get_engagement_summary()
    """
    total_sessions = sum(u.get("total_sessions", 0) for u in team_data)
    avg_score = sum(u["avg_score"] for u in team_data if u.get("avg_score")) / max(len(team_data), 1)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Team Performance Dashboard", "emoji": True}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Total Sessions:* {total_sessions}"},
            {"type": "mrkdwn", "text": f"*Team Avg Score:* {avg_score:.1f}/10"},
            {"type": "mrkdwn", "text": f"*Active Reps:* {len(team_data)}"},
            {"type": "mrkdwn", "text": f"*Assignments:* {assignment_summary.get('pending', 0)} pending · {assignment_summary.get('completed', 0)} done"},
        ]},
        {"type": "divider"},
    ]

    # Rep leaderboard
    if team_data:
        lines = ["```", f"{'Rep':<20} {'Sessions':>8} {'Avg Score':>10} {'Last Active':>12}", "-" * 52]
        for u in team_data:
            name = f"<@{u['user_id']}>"[:18]
            sessions = u.get("total_sessions", 0)
            score = f"{u['avg_score']:.1f}/10" if u.get("avg_score") else "N/A"
            last = _short_time(u.get("last_active", ""))
            lines.append(f"{name:<20} {sessions:>8} {score:>10} {last:>12}")
        lines.append("```")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Rep Leaderboard*\n" + "\n".join(lines)}})
        blocks.append({"type": "divider"})

    # Skill heatmap
    if skill_heatmap:
        all_dims = set()
        for user_dims in skill_heatmap.values():
            all_dims.update(user_dims.keys())

        if all_dims:
            header = f"{'Skill':<22}" + "".join(f"{'<@' + uid + '>'[:8]:>8}" for uid in skill_heatmap.keys())
            lines = ["```", header, "-" * (22 + 8 * len(skill_heatmap))]
            for dim in sorted(all_dims):
                label = dim.replace("_", " ").title()[:20]
                scores = ""
                for uid in skill_heatmap:
                    s = skill_heatmap[uid].get(dim)
                    if s is not None:
                        icon = "G" if s >= 7 else "Y" if s >= 5 else "R"
                        scores += f"{icon} {s:.0f}    "
                    else:
                        scores += "  -     "
                lines.append(f"{label:<22}{scores}")
            lines.append("```")
            lines.append("_G=7+, Y=5-6.9, R=<5_")
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Skill Heatmap*\n" + "\n".join(lines)}})
            blocks.append({"type": "divider"})

    # Actions
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Assign Training", "emoji": True},
         "action_id": "open_assign_flow", "style": "primary"},
        {"type": "button", "text": {"type": "plain_text", "text": "Create Scenario", "emoji": True},
         "action_id": "open_create_scenario"},
    ]})

    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": f"SalesCoach AI · Manager Dashboard · {timestamp()}"}
    ]})

    fallback = f"Team Dashboard: {len(team_data)} reps, {total_sessions} sessions, avg {avg_score:.1f}/10"
    return blocks, fallback


def _short_time(iso):
    if not iso:
        return "Never"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days}d ago"
        return f"{diff.seconds // 3600}h ago"
    except:
        return iso[:10]
```

### Step 2: Add `/team-dashboard` Command

```python
from db import get_team_training_summary, get_dimension_averages, get_team_assignments_summary, get_engagement_summary
from formatters.team_dashboard import format_team_dashboard

@app.command("/team-dashboard")
def handle_team_dashboard(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    log_engagement(user_id, "command", command="/team-dashboard")

    # Get team data
    team_data = get_team_training_summary()

    if not team_data:
        say(channel=channel_id, text="No training data yet. Have your team run `/coach roleplay` to start building data.")
        return

    # Build skill heatmap
    skill_heatmap = {}
    for user in team_data:
        uid = user["user_id"]
        dims = get_dimension_averages(uid, min_sessions=2)
        if dims:
            skill_heatmap[uid] = {d["dimension"]: round(d["avg_score"], 1) for d in dims}

    assignment_summary = get_team_assignments_summary()
    engagement_data = get_engagement_summary(days=30)

    blocks, fallback = format_team_dashboard(team_data, skill_heatmap, assignment_summary, engagement_data)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

## DO NOT
- Do not require specific Slack user groups for manager commands — for POC, any user can access
- Do not expose scenario IDs in public channels — they're internal references
- Do not let assignment completion auto-fire without verifying the session matches the assigned scenario
- Do not exceed 50 blocks per message — paginate the dashboard if team is large

## Testing
1. `/create-scenario` → fill modal → save → should get confirmation DM with scenario ID
2. `/scenarios` → should list the scenario you just created with "Start Practice" button
3. Click "Start Practice" → roleplay starts with the saved persona/objectives
4. `/assign @user SCENARIO_ID --due 2026-03-19` → user gets DM with assignment → appears on their Home tab
5. `/team-dashboard` → shows leaderboard, skill heatmap, assignment counts
6. After seeding demo data: `/team-dashboard` → rich dashboard with 4 users' data
