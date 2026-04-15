# Implement All Missing Wave Commands — Claude Code Instructions

**Goal:** Add the missing Wave 3/4/5 features to `app.py` and create all supporting files.

## Command Consolidation Strategy (Slack 25-command limit)

Slack allows a maximum of 25 slash commands per app. We currently have **24** registered commands and need to add 10 new features. To stay within the limit, we consolidate related commands under **parent commands with subcommands** (the same pattern `/coach` already uses).

**New parent commands (3 new Slack registrations):**

| New Command | Subcommands | Replaces |
|-------------|-------------|----------|
| `/my-day` | _(standalone, no subcommands)_ | new |
| `/training` | `create`, `library`, `assign`, `launch`, `onboard`, `cohort`, `progress`, `history`, `gaps` | `/create-scenario`, `/scenarios`, `/assign`, `/launch-training`, `/onboard`, `/create-cohort`, `/cohort-progress`, `/training-history`, `/skill-gaps` |
| `/team` | `dashboard`, `insights` | `/team-dashboard`, `/market-insights` |

**Existing commands to REMOVE from Slack registration (2 freed slots):**
- `/training-history` → becomes `/training history`
- `/skill-gaps` → becomes `/training gaps`

**Final math:** 24 existing − 2 removed + 3 new = **25 commands** (exactly at the limit)

**IMPORTANT — Backward compatibility:** Keep the old `@app.command("/training-history")` and `@app.command("/skill-gaps")` handlers in `app.py` as thin redirects that call the same underlying logic. This way if someone has muscle memory for the old commands, they still work even though the Slack registration is removed. Slack won't auto-complete them but they'll still function if typed.

---

**CRITICAL — Sync vs Async:** The existing `app.py` uses **synchronous** handlers everywhere (`def handle_...`, not `async def`). The Wave 5 spec files show `async def` examples — **ignore that**. All new handlers MUST be synchronous `def` to match the existing codebase. Do NOT use `await`.

**CRITICAL — `log_engagement` signature:** The existing function is:
```python
log_engagement(user_id, event_type, command=None, action_id=None, **metadata)
```
Use keyword args: `log_engagement(user_id, "command", command="/my-day")` for commands, `log_engagement(user_id, "action", action_id="start_saved_scenario")` for actions.

---

## Phase 0: Verify DB Schema

The following tables should already exist in `db.py` (they were added previously). Verify they're present:
- `scenarios` — id, name, type, difficulty, created_by, persona, objectives, scoring_methodology, tags, product_context, usage_count, avg_score, created_at
- `assignments` — id, scenario_id, assigned_by, assigned_to, due_date, status, completed_at, session_id, score
- `cohorts` — id, name, description, created_by, status, graduation_min_avg_score, graduation_min_completion, created_at
- `cohort_participants` — id, cohort_id, user_id, enrolled_at, graduated_at
- `cohort_weeks` — id, cohort_id, week_number, label, min_score, start_date, end_date
- `cohort_week_scenarios` — id, week_id, scenario_id

If any are missing, add them to `init_db()` in `db.py`.

---

## Phase 1: Add DB Helper Functions to `db.py`

Add these functions to the bottom of `db.py`. Check if any already exist first — skip those.

### 1A. Scenario Functions

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

### 1B. Assignment Functions

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

### 1C. Cohort Functions

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

        for uid in participants:
            conn.execute("INSERT INTO cohort_participants (cohort_id, user_id) VALUES (?, ?)", (cohort_id, uid))

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

        result["participants"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM cohort_participants WHERE cohort_id = ?", (cohort_id,)
            ).fetchall()
        ]

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

### 1D. Update imports at top of `db.py`

Make sure `json` is imported at the top of `db.py` (it likely already is).

---

## Phase 2: Create New Data Files

### 2A. Create `data/mock_calendar/events.json`

```bash
mkdir -p data/mock_calendar
```

Write the file with 5 events. **Important:** Set dates relative to "today" for demo purposes. Use dates near the demo date. Example using March 2026:

```json
[
  {
    "id": "evt_001",
    "title": "Discovery Call — NovaTech",
    "start": "2026-03-16T14:00:00-07:00",
    "end": "2026-03-16T14:45:00-07:00",
    "attendees": ["sarah.chen@novatech.io", "john@ourcompany.com"],
    "description": "Initial discovery call to discuss their data pipeline challenges",
    "location": "Zoom",
    "company": "NovaTech",
    "contact_name": "Sarah Chen",
    "contact_title": "VP Engineering"
  },
  {
    "id": "evt_002",
    "title": "Pipeline Review — Internal",
    "start": "2026-03-16T15:30:00-07:00",
    "end": "2026-03-16T16:00:00-07:00",
    "attendees": ["team-sales@ourcompany.com"],
    "description": "Weekly pipeline review",
    "location": "Conference Room B",
    "company": null,
    "contact_name": null,
    "contact_title": null
  },
  {
    "id": "evt_003",
    "title": "Follow-up Call — Apex Systems",
    "start": "2026-03-16T17:00:00-07:00",
    "end": "2026-03-16T17:30:00-07:00",
    "attendees": ["mike.davis@apexsystems.com"],
    "description": "Follow up on proposal we sent last week",
    "location": "Phone",
    "company": "Apex Systems",
    "contact_name": "Mike Davis",
    "contact_title": "CTO"
  },
  {
    "id": "evt_004",
    "title": "Demo — CloudBridge Solutions",
    "start": "2026-03-17T10:00:00-07:00",
    "end": "2026-03-17T11:00:00-07:00",
    "attendees": ["jennifer.wu@cloudbridge.io", "raj.patel@cloudbridge.io"],
    "description": "Product demo for their DevOps team. Focus on automation features.",
    "location": "Google Meet",
    "company": "CloudBridge Solutions",
    "contact_name": "Jennifer Wu",
    "contact_title": "Director of DevOps"
  },
  {
    "id": "evt_005",
    "title": "Negotiation — DataFlow Inc",
    "start": "2026-03-17T14:00:00-07:00",
    "end": "2026-03-17T15:00:00-07:00",
    "attendees": ["tom.baker@dataflow.com"],
    "description": "Contract negotiation, they want 15% discount. Need to discuss multi-year terms.",
    "location": "Zoom",
    "company": "DataFlow Inc",
    "contact_name": "Tom Baker",
    "contact_title": "VP Procurement"
  }
]
```

### 2B. Create `data/cohort_templates/new_hire_onboard.json`

```bash
mkdir -p data/cohort_templates
```

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

### 2C. Create `data/documents/` directory structure

```bash
mkdir -p data/documents/brochures data/documents/case_studies data/documents/pricing
```

Create small placeholder text files (these represent PDFs in the real app):

```bash
echo "Product Overview - Placeholder brochure document" > data/documents/brochures/product_overview.pdf
echo "Enterprise Solution - Placeholder enterprise brochure" > data/documents/brochures/enterprise_solution.pdf
echo "Case Study: Apex Systems - How Apex reduced sales cycle by 40%" > data/documents/case_studies/case_study_apex.pdf
echo "Case Study: CloudBridge - Migration success story" > data/documents/case_studies/case_study_cloudbridge.pdf
echo "Pricing Guide 2026 - Starter, Pro, Enterprise tiers" > data/documents/pricing/pricing_guide_2026.pdf
```

---

## Phase 3: Create New Tool Modules

### 3A. Create `tools/calendar.py`

```python
"""Calendar integration — mock mode reads from data/mock_calendar/events.json.
Future: swap in Google Calendar MCP or API calls."""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

MOCK_CALENDAR_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mock_calendar", "events.json")


def _load_mock_events() -> list:
    """Load mock calendar events from JSON."""
    if not os.path.exists(MOCK_CALENDAR_PATH):
        return []
    with open(MOCK_CALENDAR_PATH, "r") as f:
        return json.load(f)


def _parse_dt(iso_str: str) -> datetime:
    """Parse ISO 8601 datetime string."""
    return datetime.fromisoformat(iso_str)


def get_todays_events(user_id: str) -> list:
    """Return all events for today, sorted by start time."""
    events = _load_mock_events()
    now = datetime.now().astimezone()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    todays = [
        e for e in events
        if today_start <= _parse_dt(e["start"]) < today_end
    ]
    return sorted(todays, key=lambda e: e["start"])


def get_next_meeting(user_id: str) -> Optional[dict]:
    """Return the next upcoming external meeting (skips internal meetings).
    Used by /coach prep auto-detect."""
    events = _load_mock_events()
    now = datetime.now().astimezone()

    upcoming = [
        e for e in events
        if _parse_dt(e["start"]) > now and e.get("company")
    ]
    if not upcoming:
        return None
    return min(upcoming, key=lambda e: e["start"])


def get_event_by_id(event_id: str) -> Optional[dict]:
    """Look up a single event by ID."""
    events = _load_mock_events()
    return next((e for e in events if e["id"] == event_id), None)


def find_available_slots(user_id: str, date_str: str, duration_minutes: int = 30) -> list:
    """Find open time slots on a given date for rescheduling."""
    events = _load_mock_events()
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    day_events = sorted(
        [e for e in events if _parse_dt(e["start"]).date() == target_date],
        key=lambda e: e["start"]
    )

    slots = []
    business_start = 9 * 60
    business_end = 18 * 60

    busy_blocks = []
    for e in day_events:
        start_dt = _parse_dt(e["start"])
        end_dt = _parse_dt(e["end"])
        busy_blocks.append((start_dt.hour * 60 + start_dt.minute, end_dt.hour * 60 + end_dt.minute))

    cursor = business_start
    for busy_start, busy_end in busy_blocks:
        if cursor + duration_minutes <= busy_start:
            slots.append({
                "start": f"{cursor // 60:02d}:{cursor % 60:02d}",
                "end": f"{(cursor + duration_minutes) // 60:02d}:{(cursor + duration_minutes) % 60:02d}"
            })
        cursor = max(cursor, busy_end)

    if cursor + duration_minutes <= business_end:
        slots.append({
            "start": f"{cursor // 60:02d}:{cursor % 60:02d}",
            "end": f"{(cursor + duration_minutes) // 60:02d}:{(cursor + duration_minutes) % 60:02d}"
        })

    return slots[:5]


def update_event_time(event_id: str, new_start: str, new_end: str) -> bool:
    """Update an event's time (mock: rewrites JSON file)."""
    events = _load_mock_events()
    for e in events:
        if e["id"] == event_id:
            e["start"] = new_start
            e["end"] = new_end
            with open(MOCK_CALENDAR_PATH, "w") as f:
                json.dump(events, f, indent=2)
            return True
    return False
```

### 3B. Create `tools/documents.py`

```python
"""Document library for email attachments."""

import os
from pathlib import Path

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")


def list_documents() -> list:
    """List all available documents in the library."""
    docs = []
    base = Path(DOCUMENTS_DIR)
    if not base.exists():
        return docs

    for category_dir in sorted(base.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        for file_path in sorted(category_dir.iterdir()):
            if file_path.is_file():
                docs.append({
                    "name": file_path.stem.replace("_", " ").title(),
                    "category": category.replace("_", " ").title(),
                    "path": str(file_path),
                    "filename": file_path.name,
                    "size_kb": round(file_path.stat().st_size / 1024, 1)
                })
    return docs


def get_document_by_name(search: str):
    """Find a document by partial name match."""
    docs = list_documents()
    search_lower = search.lower()
    return next(
        (d for d in docs if search_lower in d["name"].lower() or search_lower in d["filename"].lower()),
        None
    )
```

### 3C. Create `tools/market_insights.py`

```python
"""Market insights — LLM-powered analysis of trends across CRM data,
coaching sessions, and research outputs."""

import json
from datetime import datetime, timedelta
from db import get_db


def gather_recent_data(days: int = 30) -> dict:
    """Gather all relevant data from the last N days for analysis."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with get_db() as conn:
        sessions = conn.execute("""
            SELECT user_id, scenario_type, overall_score, strengths, improvements,
                   methodology, created_at
            FROM training_sessions
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()

        events = conn.execute("""
            SELECT user_id, event_type, event_name, metadata, created_at
            FROM engagement_events
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()

        crm_notes = conn.execute("""
            SELECT user_id, action_type, object_type, details, created_at
            FROM crm_audit_log
            WHERE created_at >= ? AND action_type = 'create_note'
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()

    return {
        "coaching_sessions": [dict(s) for s in sessions],
        "engagement_events": [dict(e) for e in events],
        "crm_notes": [dict(n) for n in crm_notes]
    }


def build_insights_prompt(data: dict) -> str:
    """Build the LLM analysis prompt from gathered data."""
    sessions_text = ""
    for s in data["coaching_sessions"][:50]:
        sessions_text += (
            f"- {s['created_at']}: {s.get('scenario_type', 'unknown')} session, "
            f"score {s.get('overall_score', 'N/A')}/10, "
            f"strengths: {s.get('strengths', 'N/A')}, "
            f"improvements: {s.get('improvements', 'N/A')}\n"
        )

    notes_text = ""
    for n in data["crm_notes"][:30]:
        details = n.get("details", "{}")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = {"raw": details}
        notes_text += f"- {n['created_at']}: {details.get('note_body', details.get('raw', ''))[:200]}\n"

    command_counts = {}
    for e in data["engagement_events"]:
        if e.get("event_type") == "command":
            name = e.get("event_name", "unknown")
            command_counts[name] = command_counts.get(name, 0) + 1

    usage_text = "\n".join(
        f"- /{name}: {count} uses"
        for name, count in sorted(command_counts.items(), key=lambda x: -x[1])[:10]
    )

    return f"""Analyze the following recent sales team data and identify actionable insights.

## Coaching Sessions (last 30 days):
{sessions_text or "No coaching sessions recorded."}

## CRM Notes Logged (last 30 days):
{notes_text or "No CRM notes logged."}

## Tool Usage Patterns:
{usage_text or "No usage data."}

Based on this data, provide:

1. **Top 5 Skill Gaps** — Which coaching dimensions show the most room for improvement across the team? Include specific scores and trends.

2. **Common Objection Patterns** — What objections or challenges appear repeatedly in coaching sessions and CRM notes?

3. **Competitor Mentions** — Any competitors referenced in notes or sessions? How frequently?

4. **Engagement Trends** — Is team coaching activity increasing or decreasing? Who are the most/least engaged reps?

5. **Recommended Actions** — 3 specific actions the sales manager should take based on these patterns.

Format your response as structured sections with clear headers. Use specific numbers and examples from the data."""


def format_insights_for_storage(llm_response: str) -> dict:
    """Parse LLM insights response into structured dict for potential caching."""
    return {
        "raw_text": llm_response,
        "generated_at": datetime.now().isoformat(),
        "data_window_days": 30
    }
```

---

## Phase 4: Create New Formatter Modules

### 4A. Create `formatters/calendar.py`

```python
"""Block Kit formatters for calendar features."""

from datetime import datetime


def format_day_plan(events, date_label):
    """Format the /my-day output card.
    Returns: (blocks, fallback_text) tuple
    """
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Your Day — {date_label}"}},
        {"type": "divider"}
    ]

    if not events:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "No meetings scheduled today. Perfect time for prospecting!"}
        })
        return blocks, f"Your Day — {date_label}: No meetings"

    for event in events:
        start_dt = datetime.fromisoformat(event["start"])
        time_str = start_dt.strftime("%-I:%M %p")
        title = event.get("title", "Untitled")
        location = event.get("location", "")
        contact = event.get("contact_name", "")
        contact_title = event.get("contact_title", "")
        company = event.get("company", "")

        subtitle_parts = []
        if contact:
            subtitle_parts.append(f"{contact}" + (f" ({contact_title})" if contact_title else ""))
        if location:
            subtitle_parts.append(f"{location}")
        subtitle = " · ".join(subtitle_parts)

        section_text = f"*{time_str}*  {title}"
        if subtitle:
            section_text += f"\n{subtitle}"

        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": section_text}
        }

        if company:
            block["accessory"] = {
                "type": "overflow",
                "action_id": "calendar_meeting_actions",
                "options": [
                    {"text": {"type": "plain_text", "text": "Prep for Meeting"}, "value": f"prep|{company}"},
                    {"text": {"type": "plain_text", "text": "Research Company"}, "value": f"research|{company}"},
                    {"text": {"type": "plain_text", "text": "Reschedule"}, "value": f"reschedule|{event['id']}"}
                ]
            }
        elif "pipeline" in title.lower():
            block["accessory"] = {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Pipeline"},
                "action_id": "view_pipeline_from_calendar",
                "value": "pipeline"
            }

        blocks.append(block)

    fallback = f"Your Day — {date_label}: {len(events)} meetings"
    return blocks, fallback


def format_reschedule_modal(event, available_slots):
    """Build the reschedule modal view."""
    slot_options = [
        {
            "text": {"type": "plain_text", "text": f"{slot['start']} – {slot['end']}"},
            "value": f"{slot['start']}|{slot['end']}"
        }
        for slot in available_slots
    ]

    start_dt = datetime.fromisoformat(event["start"])
    current_time = start_dt.strftime("%-I:%M %p")

    return {
        "type": "modal",
        "callback_id": "reschedule_modal_submit",
        "title": {"type": "plain_text", "text": "Reschedule Meeting"},
        "submit": {"type": "plain_text", "text": "Reschedule"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": event["id"],
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{event['title']}*\nCurrently: {current_time}"}},
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "new_time_block",
                "element": {
                    "type": "static_select",
                    "action_id": "new_time_select",
                    "placeholder": {"type": "plain_text", "text": "Pick a new time"},
                    "options": slot_options if slot_options else [
                        {"text": {"type": "plain_text", "text": "No slots available"}, "value": "none"}
                    ]
                },
                "label": {"type": "plain_text", "text": "Available Time Slots"}
            }
        ]
    }


def format_reschedule_confirmation(event_title, old_time, new_time):
    """Confirmation card after rescheduling."""
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Rescheduled:* {event_title}\n~{old_time}~ → *{new_time}*\nAttendees will be notified."}}
    ]
    return blocks, f"Rescheduled: {event_title} from {old_time} to {new_time}"
```

### 4B. Create `formatters/team_dashboard.py`

```python
"""Block Kit formatter for manager team dashboard."""

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
        {"type": "header", "text": {"type": "plain_text", "text": "Team Performance Dashboard"}},
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
        {"type": "button", "text": {"type": "plain_text", "text": "Assign Training"}, "action_id": "open_assign_flow", "style": "primary"},
        {"type": "button", "text": {"type": "plain_text", "text": "Create Scenario"}, "action_id": "open_create_scenario"},
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

### 4C. Create `formatters/cohort.py`

```python
"""Block Kit formatter for cohort progress view."""

from formatters.helpers import timestamp


def _progress_bar(completed, total, width=10):
    """Unicode progress bar."""
    if total == 0:
        return "░" * width
    filled = int((completed / total) * width)
    return "█" * filled + "░" * (width - filled)


def format_cohort_progress(data):
    """Format cohort progress as Block Kit blocks.

    Args:
        data: dict from get_cohort_progress() with keys "cohort" and "progress"
    Returns:
        (blocks, fallback_text) tuple
    """
    cohort = data["cohort"]
    progress = data["progress"]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Training Program: {cohort['name']}"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"{len(cohort.get('weeks', []))} weeks · {len(progress)} participants · Status: {cohort.get('status', 'active').title()}"}
        ]},
        {"type": "divider"},
    ]

    for participant in progress:
        uid = participant["user_id"]
        total_scenarios = sum(w["total_scenarios"] for w in participant["weeks"])
        completed_scenarios = sum(w["completed_scenarios"] for w in participant["weeks"])
        all_scores = [w["avg_score"] for w in participant["weeks"] if w["avg_score"] > 0]
        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0

        bar = _progress_bar(completed_scenarios, total_scenarios)
        pct = int((completed_scenarios / max(total_scenarios, 1)) * 100)

        lines = [f"*<@{uid}>* — {pct}% complete · Avg: {overall_avg:.1f}/10"]
        lines.append(f"`{bar}` {completed_scenarios}/{total_scenarios} scenarios")

        for week in participant["weeks"]:
            status_icon = "✅" if week["completed_scenarios"] == week["total_scenarios"] else "⏳"
            score_text = f" · Avg: {week['avg_score']:.1f}" if week["avg_score"] > 0 else ""
            lines.append(f"  {status_icon} Week {week['week_number']}: {week['label']} — {week['completed_scenarios']}/{week['total_scenarios']}{score_text}")

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": f"SalesCoach AI · Cohort Progress · {timestamp()}"}
    ]})

    fallback = f"Training: {cohort['name']} — {len(progress)} participants"
    return blocks, fallback
```

### 4D. Create `formatters/market_insights.py`

```python
"""Block Kit formatter for market insights card."""

from datetime import datetime


def format_market_insights(insights_text, data_summary):
    """Format the /market-insights output.
    Returns: (blocks, fallback_text) tuple
    """
    now = datetime.now().strftime("%b %-d, %Y")
    sessions_count = data_summary.get("sessions_count", 0)
    notes_count = data_summary.get("notes_count", 0)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Market & Team Insights"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": (
                f"Based on {sessions_count} coaching sessions and "
                f"{notes_count} CRM notes from the last 30 days · "
                f"Generated {now}"
            )}
        ]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": insights_text[:2900]}}
    ]

    if len(insights_text) > 2900:
        remaining = insights_text[2900:5800]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "Refresh Insights"}, "action_id": "refresh_market_insights", "value": "refresh"},
        {"type": "button", "text": {"type": "plain_text", "text": "Export Summary"}, "action_id": "export_market_insights", "value": "export"},
    ]})

    return blocks, f"Market Insights — {sessions_count} sessions, {notes_count} notes analyzed"
```

---

## Phase 5: Create Language Helper

### 5A. Create `utils/language.py`

```bash
mkdir -p utils
touch utils/__init__.py
```

```python
"""Language injection for multi-language LLM output."""

from db import get_user_settings

LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese"
}


def get_language_instruction(user_id: str) -> str:
    """Return a language instruction string to append to LLM prompts.
    Returns empty string for English (default).
    """
    settings = get_user_settings(user_id)
    language = settings.get("language", "en")

    if language == "en":
        return ""

    lang_name = LANGUAGE_NAMES.get(language, "English")
    return (
        f"\n\nIMPORTANT: Respond entirely in {lang_name}. "
        f"All analysis, recommendations, coaching feedback, email drafts, "
        f"research summaries, and conversation must be in {lang_name}. "
        f"Only technical terms, company names, and product names may remain in English."
    )
```

---

## Phase 6: Add New Command Handlers to `app.py`

### Command Consolidation Architecture

To stay within Slack's 25-command limit, we use **3 new Slack-registered commands** instead of 10 separate ones. The `/training` and `/team` commands use subcommand routing (same pattern as the existing `/coach` command).

**New Slack commands:**
1. `/my-day` — standalone (high-frequency daily use)
2. `/training <subcommand>` — routes to: `create`, `library`, `assign`, `launch`, `onboard`, `cohort`, `progress`, `history`, `gaps`
3. `/team <subcommand>` — routes to: `dashboard`, `insights`

**Existing commands to migrate (remove from Slack, keep handler as redirect):**
- `/training-history` → now `/training history` (keep old handler as thin redirect)
- `/skill-gaps` → now `/training gaps` (keep old handler as thin redirect)

Add the following to `app.py` after the existing command blocks (after `/log`). Add necessary imports at the top.

### Imports to add at top of `app.py`

```python
# Add these imports near the top, alongside existing imports:
from db import (
    save_scenario, get_scenario, list_scenarios, increment_scenario_usage,
    create_assignment, get_user_assignments, complete_assignment, get_team_assignments_summary,
    create_cohort, get_cohort, get_cohort_progress, list_cohorts,
)
```

**Note:** Check which of these are already imported. Only add what's missing.

### DB Helper Functions to add to `db.py` (if missing)

The `/team dashboard` command requires these functions. Check if they exist in `db.py` — if not, add them:

```python
def get_team_training_summary():
    """Get training summary for all users."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT user_id,
                   COUNT(*) as total_sessions,
                   AVG(overall_score) as avg_score,
                   MAX(created_at) as last_active
            FROM training_sessions
            GROUP BY user_id
            ORDER BY avg_score DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_dimension_averages(user_id, min_sessions=1):
    """Get average scores per dimension for a user."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT dimension, AVG(score) as avg_score, COUNT(*) as count
            FROM dimension_scores
            WHERE user_id = ?
            GROUP BY dimension
            HAVING count >= ?
        """, (user_id, min_sessions)).fetchall()
        return [dict(r) for r in rows]


def get_engagement_summary(days=30):
    """Get engagement event summary for the last N days."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT user_id, event_type, COUNT(*) as count
            FROM engagement_events
            WHERE created_at >= ?
            GROUP BY user_id, event_type
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]
```

---

### 6A. `/my-day` Command (standalone)

```python
@app.command("/my-day")
def handle_my_day(ack, command, say):
    """Show today's calendar with meeting prep actions."""
    ack()
    user_id = command["user_id"]
    log_engagement(user_id, "command", command="/my-day")

    from tools.calendar import get_todays_events
    from formatters.calendar import format_day_plan
    from datetime import datetime

    events = get_todays_events(user_id)
    date_label = datetime.now().strftime("%A, %b %-d")

    blocks, fallback = format_day_plan(events, date_label)
    say(blocks=blocks, text=fallback)
```

---

### 6B. `/training` Parent Command (subcommand router)

This is the main handler that routes all training-related subcommands. It replaces 9 separate slash commands with one.

```python
# ──────────────────────────────────────────────────────────────
# /training — Parent command for all training features
# Subcommands: create, library, assign, launch, onboard,
#              cohort, progress, history, gaps
# ──────────────────────────────────────────────────────────────

TRAINING_HELP_TEXT = """*`/training` — Training & Scenario Management*

Available subcommands:
• `/training create` — Create a custom roleplay scenario (opens modal)
• `/training library` — Browse the scenario library
• `/training assign @rep SCENARIO_ID [--due YYYY-MM-DD]` — Assign a scenario to a rep
• `/training launch` — Generate a product launch training program (opens modal)
• `/training onboard @new-rep` — Start a 4-week new hire onboarding program
• `/training cohort "Name" @user1 @user2 [--weeks 4]` — Create a multi-week training cohort
• `/training progress [program name]` — View cohort training progress
• `/training history` — View your training session history
• `/training gaps` — View your skill gap analysis"""


@app.command("/training")
def handle_training(ack, command, say, client):
    """Parent command that routes to training subcommands."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    if not text:
        say(channel=channel_id, text=TRAINING_HELP_TEXT)
        return

    # Parse subcommand (first word) and remaining args
    parts = text.split(None, 1)
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "create":
        _training_create(command, client, user_id)
    elif subcommand in ("library", "list", "scenarios"):
        _training_library(say, channel_id, user_id)
    elif subcommand == "assign":
        _training_assign(say, client, channel_id, user_id, args)
    elif subcommand == "launch":
        _training_launch(command, client, user_id)
    elif subcommand == "onboard":
        _training_onboard(say, client, channel_id, user_id, args)
    elif subcommand == "cohort":
        _training_cohort(say, client, channel_id, user_id, args)
    elif subcommand == "progress":
        _training_progress(say, channel_id, user_id, args)
    elif subcommand == "history":
        _training_history(say, command, user_id)
    elif subcommand == "gaps":
        _training_gaps(say, command, user_id)
    else:
        say(channel=channel_id, text=f"Unknown subcommand `{subcommand}`.\n\n{TRAINING_HELP_TEXT}")
```

#### 6B-1. `_training_create` — Opens scenario builder modal

```python
def _training_create(command, client, user_id):
    """Open the create-scenario modal. Called by /training create."""
    trigger_id = command["trigger_id"]
    log_engagement(user_id, "command", command="/training create")

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
                             "placeholder": {"type": "plain_text", "text": "Name, title, company, personality, background."}}},

                {"type": "input", "block_id": "objectives_block", "label": {"type": "plain_text", "text": "Rep Objectives"},
                 "element": {"type": "plain_text_input", "action_id": "objectives", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "One per line:\nUncover 3 pain points\nIdentify the decision maker"}}},

                {"type": "input", "block_id": "objections_block", "label": {"type": "plain_text", "text": "Key Objections the Buyer Will Raise"},
                 "element": {"type": "plain_text_input", "action_id": "objections", "multiline": True,
                             "placeholder": {"type": "plain_text", "text": "One per line:\nBudget is frozen until Q3\nAlready have an in-house solution"}},
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

    persona = {
        "description": persona_text,
        "objections": [o.strip() for o in objections_text.split("\n") if o.strip()] if objections_text else [],
    }
    objectives = [o.strip() for o in objectives_text.split("\n") if o.strip()]

    scenario_id = save_scenario(
        name=name, type=type_, difficulty=difficulty, created_by=user_id,
        persona=persona, objectives=objectives, scoring_methodology=methodology,
        tags=[type_, difficulty],
    )

    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=f"Scenario saved: *{name}* ({type_.title()} · {difficulty.title()})\nID: `{scenario_id}`\nUse `/training library` to browse or `/training assign @rep {scenario_id}` to assign."
    )
```

#### 6B-2. `_training_library` — Browse scenarios

```python
def _training_library(say, channel_id, user_id):
    """Show the scenario library. Called by /training library."""
    log_engagement(user_id, "command", command="/training library")

    scenarios = list_scenarios()
    if not scenarios:
        say(channel=channel_id, text="No scenarios saved yet. Use `/training create` to build your first one.")
        return

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Scenario Library"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{len(scenarios)} scenarios available"}]},
        {"type": "divider"},
    ]

    for s in scenarios[:15]:
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
                "text": {"type": "plain_text", "text": "Start Practice"},
                "action_id": "start_saved_scenario",
                "value": s["id"],
            }
        })

    from formatters.helpers import timestamp
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]})
    say(channel=channel_id, text=f"Scenario Library: {len(scenarios)} scenarios", blocks=blocks)
```

#### 6B-3. `_training_assign` — Assign scenario to rep

```python
def _training_assign(say, client, channel_id, user_id, args):
    """Assign a scenario to a rep. Called by /training assign @rep ID [--due DATE]."""
    log_engagement(user_id, "command", command="/training assign")

    import re
    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', args)
    if not user_match:
        say(channel=channel_id, text="Usage: `/training assign @rep scenario-id`\nExample: `/training assign @sarah abc123 --due 2026-03-19`")
        return

    target_user = user_match.group(1)
    remaining = args[user_match.end():].strip()

    due_date = None
    due_match = re.search(r'--due\s+(\d{4}-\d{2}-\d{2})', remaining)
    if due_match:
        due_date = due_match.group(1)
        remaining = remaining[:due_match.start()].strip()

    scenario_id = remaining.strip()
    if not scenario_id:
        say(channel=channel_id, text="Please provide a scenario ID. Run `/training library` to see available scenarios.")
        return

    scenario = get_scenario(scenario_id)
    if not scenario:
        say(channel=channel_id, text=f"Scenario `{scenario_id}` not found. Run `/training library` to browse.")
        return

    assignment_id = create_assignment(scenario_id, user_id, target_user, due_date)

    dm = client.conversations_open(users=[target_user])
    due_text = f" Due by {due_date}." if due_date else ""
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=(
            f"*New Training Assignment*\n"
            f"<@{user_id}> assigned you: *{scenario['name']}* ({scenario['type'].title()} · {scenario['difficulty'].title()}){due_text}"
        ),
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": (
                f"*New Training Assignment*\n"
                f"<@{user_id}> assigned you: *{scenario['name']}*\n"
                f"{scenario['type'].title()} · {scenario['difficulty'].title()}{f' · Due {due_date}' if due_date else ''}"
            )}},
            {"type": "actions", "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice"},
                "action_id": "start_saved_scenario",
                "value": scenario_id,
                "style": "primary",
            }]},
        ]
    )

    say(channel=channel_id, text=f"Assigned *{scenario['name']}* to <@{target_user}>.{due_text}")
```

#### 6B-4. `_training_launch` — Product launch training (modal)

```python
def _training_launch(command, client, user_id):
    """Open the launch-training modal. Called by /training launch."""
    trigger_id = command["trigger_id"]
    log_engagement(user_id, "command", command="/training launch")

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
                             "placeholder": {"type": "plain_text", "text": "Describe the product, its key features, target audience, pricing..."}}},
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
- persona: {{"description": "...", "objections": ["..."]}}
- objectives: ["..."]

Output ONLY the JSON array, no other text."""

    response = llm.invoke(generation_prompt)

    try:
        scenarios_data = json.loads(response.content)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            scenarios_data = json.loads(match.group(0))
        else:
            dm = client.conversations_open(users=[user_id])
            client.chat_postMessage(channel=dm["channel"]["id"],
                text=f"Failed to generate scenarios for {product_name}. Try again with more product detail.")
            return

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

    for uid in team_users:
        for sid in weeks_config[0]["scenario_ids"]:
            create_assignment(sid, user_id, uid, due_date=weeks_config[0]["end_date"])

        dm = client.conversations_open(users=[uid])
        client.chat_postMessage(channel=dm["channel"]["id"],
            text=(f"*New Product Training: {product_name}*\n"
                  f"<@{user_id}> launched a 2-week training sprint. "
                  f"{len(scenario_ids)} scenarios to practice.\n"
                  f"Check your Home tab for assignments."))

    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(channel=dm["channel"]["id"],
        text=(f"*Product Launch Training Created: {product_name}*\n"
              f"Generated {len(scenario_ids)} scenarios for {len(team_users)} reps.\n"
              f"2-week program started. Use `/training progress {product_name}` to track."))
```

#### 6B-5. `_training_onboard` — New hire onboarding

```python
def _training_onboard(say, client, channel_id, user_id, args):
    """Start 4-week onboarding for a new rep. Called by /training onboard @rep."""
    log_engagement(user_id, "command", command="/training onboard")

    import re
    user_match = re.search(r'<@(\w+)(?:\|[^>]*)?>', args)
    if not user_match:
        say(channel=channel_id, text="Usage: `/training onboard @new-rep`")
        return

    target_user = user_match.group(1)

    template_path = os.path.join(DATA_DIR, "cohort_templates", "new_hire_onboard.json")
    if not os.path.exists(template_path):
        say(channel=channel_id, text="Onboarding template not found. Create `data/cohort_templates/new_hire_onboard.json`.")
        return

    with open(template_path) as f:
        template = json.load(f)

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

    cohort_id = create_cohort(
        name=f"{template['name']} — <@{target_user}>",
        description=template["description"],
        created_by=user_id,
        participants=[target_user],
        weeks_config=weeks_config,
    )

    for sid in weeks_config[0]["scenario_ids"]:
        create_assignment(sid, user_id, target_user, due_date=weeks_config[0]["end_date"])

    dm = client.conversations_open(users=[target_user])
    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=(
            f"*Welcome to SalesCoach AI!*\n\n"
            f"<@{user_id}> has enrolled you in a 4-week onboarding program.\n\n"
            f"*Week 1: {weeks_config[0]['label']}* — {len(weeks_config[0]['scenario_ids'])} scenarios to complete by {weeks_config[0]['end_date']}\n\n"
            f"Check your Home tab for assignments, or type `/training history` to track your progress."
        )
    )

    say(channel=channel_id, text=f"Onboarding program created for <@{target_user}>. 4 weeks, {sum(len(w['scenario_ids']) for w in weeks_config)} scenarios. Week 1 assigned.")
```

#### 6B-6. `_training_cohort` — Create custom cohort

```python
def _training_cohort(say, client, channel_id, user_id, args):
    """Create a multi-week cohort. Called by /training cohort 'Name' @user1 @user2 [--weeks N]."""
    log_engagement(user_id, "command", command="/training cohort")

    import re
    name_match = re.search(r'"([^"]+)"', args)
    user_matches = re.findall(r'<@(\w+)(?:\|[^>]*)?>', args)
    weeks_match = re.search(r'--weeks\s+(\d+)', args)

    if not name_match or not user_matches:
        say(channel=channel_id, text='Usage: `/training cohort "Program Name" @user1 @user2 --weeks 4`')
        return

    program_name = name_match.group(1)
    num_weeks = int(weeks_match.group(1)) if weeks_match else 4

    msg = client.chat_postMessage(
        channel=channel_id,
        text=(
            f"*Creating: {program_name}*\n"
            f"Participants: {', '.join(f'<@{u}>' for u in user_matches)}\n"
            f"Duration: {num_weeks} weeks\n\n"
            f"Now configure each week. Reply in this thread with scenario IDs for each week.\n"
            f"Format: `week 1: scenario_id_1, scenario_id_2 | min_score: 6`\n"
            f"Or type `auto` to auto-populate from the scenario library.\n"
            f"When done, type `create` to finalize."
        )
    )

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

**Note:** You also need a message handler for thread replies to process `week N:` lines and the `create` finalization. Add this to the existing `handle_message_event` or as a separate thread listener. See Wave 4 spec for details.

#### 6B-7. `_training_progress` — Cohort progress

```python
def _training_progress(say, channel_id, user_id, args):
    """Show cohort progress. Called by /training progress [program name]."""
    log_engagement(user_id, "command", command="/training progress")

    cohorts = list_cohorts(status="active")
    if not cohorts:
        say(channel=channel_id, text="No active training programs. Use `/training cohort` to start one.")
        return

    target = cohorts[0]
    if args:
        matches = [c for c in cohorts if args.lower() in c["name"].lower()]
        if matches:
            target = matches[0]

    data = get_cohort_progress(target["id"])
    if not data:
        say(channel=channel_id, text="Could not load progress data.")
        return

    from formatters.cohort import format_cohort_progress
    blocks, fallback = format_cohort_progress(data)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

#### 6B-8. `_training_history` and `_training_gaps` — Redirects to existing logic

These subcommands reuse the existing logic from the current `/training-history` and `/skill-gaps` handlers. Extract the core logic from those handlers into helper functions, then call them here.

```python
def _training_history(say, command, user_id):
    """Redirect to existing training history logic. Called by /training history."""
    log_engagement(user_id, "command", command="/training history")
    # Call the same core logic as the existing handle_training_history handler.
    # Extract the body of handle_training_history into a shared function like
    # _show_training_history(say, command, user_id) and call it from both places.
    _show_training_history(say, command, user_id)


def _training_gaps(say, command, user_id):
    """Redirect to existing skill gaps logic. Called by /training gaps."""
    log_engagement(user_id, "command", command="/training gaps")
    # Same approach: extract core logic from handle_skill_gaps into
    # _show_skill_gaps(say, command, user_id) and call from both places.
    _show_skill_gaps(say, command, user_id)
```

**IMPORTANT — Backward compatibility redirects:** Update the existing handlers to call the shared functions:

```python
# Keep these existing handlers for backward compatibility (old muscle memory).
# They won't be in Slack autocomplete but will still work if typed.

@app.command("/training-history")
def handle_training_history(ack, say, command):
    ack()
    user_id = command["user_id"]
    _show_training_history(say, command, user_id)

@app.command("/skill-gaps")
def handle_skill_gaps(ack, say, command):
    ack()
    user_id = command["user_id"]
    _show_skill_gaps(say, command, user_id)
```

Extract the current body of each handler into `_show_training_history()` and `_show_skill_gaps()` respectively.

---

### 6C. `/team` Parent Command (subcommand router)

```python
# ──────────────────────────────────────────────────────────────
# /team — Parent command for manager/team tools
# Subcommands: dashboard, insights
# ──────────────────────────────────────────────────────────────

TEAM_HELP_TEXT = """*`/team` — Manager & Team Tools*

Available subcommands:
• `/team dashboard` — View team performance dashboard (leaderboard, skill heatmap, assignments)
• `/team insights` — Generate market and team insights from recent data"""


@app.command("/team")
def handle_team(ack, command, say, client):
    """Parent command for manager/team tools."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    if not text:
        say(channel=channel_id, text=TEAM_HELP_TEXT)
        return

    parts = text.split(None, 1)
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "dashboard":
        _team_dashboard(say, channel_id, user_id)
    elif subcommand == "insights":
        _team_insights(say, channel_id, user_id)
    else:
        say(channel=channel_id, text=f"Unknown subcommand `{subcommand}`.\n\n{TEAM_HELP_TEXT}")
```

#### 6C-1. `_team_dashboard`

```python
def _team_dashboard(say, channel_id, user_id):
    """Show team performance dashboard. Called by /team dashboard."""
    log_engagement(user_id, "command", command="/team dashboard")

    team_data = get_team_training_summary()

    if not team_data:
        say(channel=channel_id, text="No training data yet. Have your team run `/coach roleplay` to start building data.")
        return

    skill_heatmap = {}
    for user in team_data:
        uid = user["user_id"]
        dims = get_dimension_averages(uid, min_sessions=2)
        if dims:
            skill_heatmap[uid] = {d["dimension"]: round(d["avg_score"], 1) for d in dims}

    assignment_summary = get_team_assignments_summary()
    engagement_data = get_engagement_summary(days=30)

    from formatters.team_dashboard import format_team_dashboard
    blocks, fallback = format_team_dashboard(team_data, skill_heatmap, assignment_summary, engagement_data)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

#### 6C-2. `_team_insights`

```python
def _team_insights(say, channel_id, user_id):
    """Generate market and team insights. Called by /team insights."""
    log_engagement(user_id, "command", command="/team insights")

    say(channel=channel_id, text="Analyzing recent sales data... this may take a moment.")

    from tools.market_insights import gather_recent_data, build_insights_prompt
    from formatters.market_insights import format_market_insights

    data = gather_recent_data(days=30)

    data_summary = {
        "sessions_count": len(data["coaching_sessions"]),
        "notes_count": len(data["crm_notes"]),
    }

    if data_summary["sessions_count"] == 0 and data_summary["notes_count"] == 0:
        say(channel=channel_id, text="Not enough data for insights yet. Use the coaching and CRM features to build up data first.")
        return

    prompt = build_insights_prompt(data)

    from llm_factory import get_llm
    llm = get_llm()

    from utils.language import get_language_instruction
    lang_instruction = get_language_instruction(user_id)

    system_prompt = "You are a sales analytics expert. Analyze the provided data and give actionable insights." + lang_instruction
    from langchain_core.messages import SystemMessage, HumanMessage
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
    insights_text = response.content

    blocks, fallback = format_market_insights(insights_text, data_summary)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

---

## Phase 7: Add Action Handlers

Add these action handlers to `app.py` alongside the existing action handlers.

### 7A. `start_saved_scenario` Action

```python
@app.action("start_saved_scenario")
def handle_start_saved_scenario(ack, body, client):
    ack()
    scenario_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]

    scenario = get_scenario(scenario_id)
    if not scenario:
        client.chat_postEphemeral(channel=channel, user=user_id, text="Scenario not found.")
        return

    increment_scenario_usage(scenario_id)

    persona = scenario.get("persona", {})
    objectives = scenario.get("objectives", [])

    roleplay_prompt = f"""Scenario: {scenario['name']}
Difficulty: {scenario['difficulty']}
Buyer Persona: {persona.get('description', 'A business executive')}
Buyer Objections: {', '.join(persona.get('objections', []))}
Rep Objectives: {', '.join(objectives)}"""

    # Reuse the existing roleplay start mechanism.
    # Look for _start_roleplay() or the roleplay logic in the /coach handler
    # and invoke it with the scenario prompt.
    # Adapt the call to match your actual function signature.
    _start_roleplay(
        client, channel, None, user_id,
        scenario=roleplay_prompt,
        scenario_id=scenario_id,
        methodology=scenario.get("scoring_methodology", "discovery"),
        company=persona.get("company", ""),
    )
```

**IMPORTANT:** Check how `_start_roleplay` is defined in your existing code. The function signature may differ. If it doesn't exist as a standalone function, extract the roleplay initialization logic from the `/coach` handler into a reusable function.

### 7B. Dashboard Action Buttons

```python
@app.action("open_assign_flow")
def handle_open_assign_flow(ack, body, say):
    ack()
    channel = body["channel"]["id"]
    say(channel=channel, text="To assign training, run:\n`/training assign @rep SCENARIO_ID --due YYYY-MM-DD`\n\nRun `/training library` to find scenario IDs.")


@app.action("open_create_scenario")
def handle_open_create_scenario(ack, body, say):
    ack()
    channel = body["channel"]["id"]
    say(channel=channel, text="Run `/training create` to open the scenario builder.")
```

### 7C. Calendar Action Handlers

```python
@app.action("calendar_meeting_actions")
def handle_calendar_meeting_action(ack, body, say, client):
    """Handle overflow menu actions on calendar events."""
    ack()
    user_id = body["user"]["id"]
    selected = body["actions"][0]["selected_option"]["value"]
    action_type, value = selected.split("|", 1)

    if action_type == "prep":
        log_engagement(user_id, "action", action_id="calendar_prep")
        say(f"Prepping for your meeting with *{value}*...")
        # Reuse existing prep logic from /coach prep

    elif action_type == "research":
        log_engagement(user_id, "action", action_id="calendar_research")
        say(f"Researching *{value}*...")
        # Reuse existing /research logic

    elif action_type == "reschedule":
        log_engagement(user_id, "action", action_id="calendar_reschedule")
        from tools.calendar import get_event_by_id, find_available_slots
        from formatters.calendar import format_reschedule_modal

        event = get_event_by_id(value)
        if not event:
            say("Meeting not found.")
            return

        from datetime import datetime
        start_dt = datetime.fromisoformat(event["start"])
        slots = find_available_slots(user_id, start_dt.strftime("%Y-%m-%d"), duration_minutes=30)
        modal = format_reschedule_modal(event, slots)

        client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.action("view_pipeline_from_calendar")
def handle_view_pipeline_from_calendar(ack, body, say):
    ack()
    say("Loading your pipeline... Run `/pipeline` for the full view.")


@app.view("reschedule_modal_submit")
def handle_reschedule_submit(ack, body, view, client):
    """Process reschedule modal submission."""
    ack()
    user_id = body["user"]["id"]
    event_id = view["private_metadata"]
    selected_time = view["state"]["values"]["new_time_block"]["new_time_select"]["selected_option"]["value"]

    if selected_time == "none":
        return

    new_start_str, new_end_str = selected_time.split("|")

    from tools.calendar import get_event_by_id, update_event_time
    from formatters.calendar import format_reschedule_confirmation
    from datetime import datetime

    event = get_event_by_id(event_id)
    if not event:
        return

    old_dt = datetime.fromisoformat(event["start"])
    old_time = old_dt.strftime("%-I:%M %p")

    date_str = old_dt.strftime("%Y-%m-%d")
    tz_offset = old_dt.strftime("%z")
    new_start_iso = f"{date_str}T{new_start_str}:00{tz_offset}"
    new_end_iso = f"{date_str}T{new_end_str}:00{tz_offset}"

    update_event_time(event_id, new_start_iso, new_end_iso)
    log_engagement(user_id, "action", action_id="meeting_rescheduled")

    blocks, fallback = format_reschedule_confirmation(event["title"], old_time, new_start_str)

    dm = client.conversations_open(users=[user_id])
    client.chat_postMessage(channel=dm["channel"]["id"], blocks=blocks, text=fallback)
```

### 7D. Market Insights Action Handlers

```python
@app.action("refresh_market_insights")
def handle_refresh_insights(ack, body, say):
    ack()
    user_id = body["user"]["id"]
    log_engagement(user_id, "action", action_id="refresh_market_insights")
    say("Refreshing insights...")
    # Re-invoke the same logic as _team_insights
    # Consider extracting into a shared function


@app.action("export_market_insights")
def handle_export_insights(ack, body, say):
    ack()
    log_engagement(body["user"]["id"], "action", action_id="export_market_insights")
    say("Export coming soon — for now, you can copy the insights above.")
```

---

## Phase 8: Enhance Existing Commands

### 8A. Enhance `/settings` with Language Picker

Find the existing `/settings` modal in `app.py` and add a language dropdown block. In the modal submit handler, extract and save the language setting:

```python
# In the settings modal blocks, add:
{
    "type": "input",
    "block_id": "language_block",
    "optional": True,
    "element": {
        "type": "static_select",
        "action_id": "language_select",
        "placeholder": {"type": "plain_text", "text": "Select language"},
        "options": [
            {"text": {"type": "plain_text", "text": "English"}, "value": "en"},
            {"text": {"type": "plain_text", "text": "Deutsch"}, "value": "de"},
            {"text": {"type": "plain_text", "text": "Français"}, "value": "fr"},
            {"text": {"type": "plain_text", "text": "Español"}, "value": "es"},
            {"text": {"type": "plain_text", "text": "Português"}, "value": "pt"},
        ]
    },
    "label": {"type": "plain_text", "text": "AI Response Language"},
    "hint": {"type": "plain_text", "text": "AI responses will be in your selected language. Interface labels remain in English."}
}

# In the settings submit handler, extract and save:
language_block = v.get("language_block", {}).get("language_select", {})
if language_block and language_block.get("selected_option"):
    language = language_block["selected_option"]["value"]
    update_user_settings(user_id, {"language": language})
```

### 8B. Inject Language into All LLM Prompts

Add `from utils.language import get_language_instruction` to files that build LLM system prompts and append `get_language_instruction(user_id)` to each system prompt string. Key files:

- `prompts/assistant_prompts.py`
- `prompts/coach_prompts.py`
- `graphs/assistant.py`
- `graphs/coach.py`

**Pattern:**
```python
system_prompt = existing_prompt_text + get_language_instruction(user_id)
```

Only translate free-text LLM responses. Do NOT translate Slack Block Kit labels, button text, or JSON output.

### 8C. Enhance `/coach prep` Auto-Detect

In the `/coach` handler, when `subcommand == "prep"` and no company is specified, auto-detect from calendar:

```python
if not company_name:
    from tools.calendar import get_next_meeting
    next_meeting = get_next_meeting(user_id)
    if next_meeting:
        company_name = next_meeting.get("company", "")
        contact = next_meeting.get("contact_name", "")
        # Optionally prepend meeting context to the prep output
    else:
        say("No upcoming meetings found. Use `/coach prep [company]` to prep manually.")
        return
```

---

## Phase 9: Register Slack Commands

In the Slack API dashboard (https://api.slack.com/apps), make these changes:

### New commands to ADD (3):

| Command | Description | Usage Hint |
|---------|-------------|------------|
| `/my-day` | View today's schedule with meeting prep actions | |
| `/training` | Training & scenario management (create, library, assign, launch, onboard, cohort, progress, history, gaps) | `[subcommand] [args]` |
| `/team` | Manager tools — team dashboard and market insights | `[dashboard\|insights]` |

### Existing commands to REMOVE from Slack (2):

| Command | Replaced By |
|---------|-------------|
| `/training-history` | `/training history` |
| `/skill-gaps` | `/training gaps` |

**Note:** Only remove from the Slack API dashboard. Keep the `@app.command` handlers in `app.py` as backward-compatible redirects (see Phase 6B-8).

### Final command count verification:

```
Existing:     24
- Removed:     2  (training-history, skill-gaps)
+ Added:       3  (my-day, training, team)
= Total:      25  ✅ (exactly at the Slack limit)
```

For each new command, set the Request URL to your app's slash command endpoint (same as existing commands).

---

## Phase 10: Testing Checklist

### New commands:
1. `/my-day` → shows today's events with overflow action buttons
2. Click "Prep for Meeting" → triggers prep flow
3. Click "Reschedule" → opens modal with time slots
4. `/training` (no args) → shows help with all subcommands
5. `/training create` → modal opens → fill and submit → confirmation DM
6. `/training library` → lists scenarios with "Start Practice" buttons
7. Click "Start Practice" → roleplay begins with saved scenario
8. `/training assign @user SCENARIO_ID --due 2026-03-19` → user gets DM
9. `/training launch` → modal → generates scenarios → creates cohort
10. `/training onboard @user` → creates 4-week program → user gets DM
11. `/training cohort "Test Program" @user1 @user2 --weeks 4` → thread-based config flow
12. `/training progress` → shows progress bars and completion grid
13. `/team` (no args) → shows help with subcommands
14. `/team dashboard` → shows leaderboard, skill heatmap, assignments
15. `/team insights` → analyzes recent data → shows insights card
16. `/settings` → language dropdown appears → select German → LLM responses in German

### Backward compatibility:
17. `/training-history` → still works (redirects to same logic as `/training history`)
18. `/skill-gaps` → still works (redirects to same logic as `/training gaps`)

### Cross-references in output text:
19. Verify all user-facing messages reference the NEW command names:
    - `/training library` not `/scenarios`
    - `/training create` not `/create-scenario`
    - `/training assign` not `/assign`
    - `/training progress` not `/cohort-progress`
    - `/team dashboard` not `/team-dashboard`
    - `/team insights` not `/market-insights`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `NameError: name 'save_scenario' is not defined` | Add import to top of app.py |
| `sqlite3.OperationalError: no such table: scenarios` | Run `init_db()` or restart app to auto-create tables |
| `json.JSONDecodeError` in launch-training | LLM didn't return clean JSON — improve the generation prompt or add retry logic |
| Slack says "dispatch_failed" | Command not registered in Slack API dashboard |
| `/my-day` shows no events | Check dates in `events.json` match today's date |
| `DATA_DIR` not defined | Check existing code for how the data directory path is set (search for `DATA_DIR`) |
| Modal exceeds timeout (3s) | Move LLM calls out of modal submit handlers into background tasks |
| `/training` with no args doesn't respond | Make sure the `if not text:` check is at the top of `handle_training` |
| Old commands `/training-history` stop working | Keep the `@app.command` handlers in app.py — only remove from Slack API dashboard |
