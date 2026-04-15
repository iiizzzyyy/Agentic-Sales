# Implementation Plan: Pam & Lisa Feature Parity

19 features across 5 implementation waves. Each wave builds on the previous, and features within a wave can be built in parallel.

---

## Architecture Decision: Persistent Data Layer — SQLite

Almost every feature below needs **persistent storage** (training history, scenarios, engagement logs, cohort state). The current bot is entirely in-memory with JSON file mock data.

### Decision: SQLite (single `data/salescoach.db` file)

**Why SQLite over JSON files:**
- Cross-cutting queries are trivial: `SELECT AVG(overall_score) FROM sessions WHERE user_id = ? AND dimension = 'needs_assessment' AND timestamp > date('now', '-30 days')` — painful with JSON, one-liner in SQL
- Team dashboard needs: `SELECT user_id, COUNT(*), AVG(overall_score) FROM training_sessions GROUP BY user_id` — one query vs loading every user's JSON file
- Engagement analytics: `SELECT event_type, COUNT(*) FROM engagement_events WHERE timestamp > ? GROUP BY event_type`
- Zero external dependencies — sqlite3 ships with Python
- Single file, portable, easy to copy/reset for demos
- Demo seeding via a single SQL script

**Why SQLite over MongoDB Atlas free tier:**
- No network dependency (runs offline, no cloud connection needed)
- No connection management, no auth setup, no Atlas account
- Simpler for a POC — MongoDB's document model doesn't add value when SQLite handles JSON columns fine
- One less thing to break during a live demo

**Database location:** `data/salescoach.db`
**Migration from settings_store.py:** Move user settings into SQLite too (single source of truth)

### Database Schema (created in Wave 1):

```sql
-- User settings (replaces settings_store.py JSON)
CREATE TABLE user_settings (
    user_id TEXT PRIMARY KEY,
    response_mode TEXT DEFAULT 'channel',
    detail_level TEXT DEFAULT 'summary',
    coaching_privacy INTEGER DEFAULT 1,
    methodology TEXT DEFAULT 'discovery',
    language TEXT DEFAULT 'en',
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Training session history (Wave 1 - Feature #21)
CREATE TABLE training_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    type TEXT NOT NULL,              -- roleplay, coach_live, prep, feedback
    scenario TEXT,                   -- free text scenario description
    scenario_id TEXT,                -- FK to scenarios table (Wave 3)
    scenario_type TEXT,              -- discovery, negotiation, competitive, cold_call, objection
    overall_score REAL,
    turns INTEGER,
    methodology TEXT,
    strengths TEXT,                  -- JSON array
    improvements TEXT,               -- JSON array
    company TEXT,
    persona TEXT,
    raw_debrief TEXT                 -- Full markdown debrief for display
);

-- Dimension scores (normalized from training_sessions)
CREATE TABLE dimension_scores (
    session_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    score REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES training_sessions(id),
    PRIMARY KEY (session_id, dimension)
);

-- Engagement events (Wave 1 - Feature #22)
CREATE TABLE engagement_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,        -- command, action, roleplay_turn, debrief
    command TEXT,                    -- /research, /deal, etc.
    action_id TEXT,                  -- draft_email_from_research, etc.
    metadata TEXT                    -- JSON blob for extra context
);

-- CRM write log (Wave 1 - Feature #2+#11)
CREATE TABLE crm_writes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    user_id TEXT NOT NULL,
    write_type TEXT NOT NULL,        -- note, stage_update, task, activity
    object_type TEXT,                -- deal, contact, company
    object_id TEXT,                  -- HubSpot or mock ID
    object_name TEXT,                -- Human-readable name
    content TEXT,                    -- Note body, stage name, etc.
    hubspot_id TEXT,                 -- HubSpot record ID if synced
    status TEXT DEFAULT 'pending'    -- pending, synced, failed, mock
);

-- Scenarios library (Wave 3 - Feature #14)
CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,              -- discovery, negotiation, competitive, cold_call, objection, custom
    difficulty TEXT DEFAULT 'intermediate',
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    persona TEXT NOT NULL,           -- JSON blob
    objectives TEXT,                 -- JSON array
    scoring_methodology TEXT DEFAULT 'discovery',
    tags TEXT,                       -- JSON array
    usage_count INTEGER DEFAULT 0,
    avg_score REAL,
    product_context TEXT             -- For product launch scenarios
);

-- Assignments (Wave 3 - Feature #20)
CREATE TABLE assignments (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    assigned_to TEXT NOT NULL,
    assigned_at TEXT DEFAULT (datetime('now')),
    due_date TEXT,
    status TEXT DEFAULT 'pending',   -- pending, completed, overdue
    completed_at TEXT,
    session_id TEXT,                 -- FK to training_sessions
    score REAL,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
);

-- Cohorts / Training Programs (Wave 4 - Feature #17)
CREATE TABLE cohorts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'active',    -- active, completed, archived
    graduation_min_avg_score REAL DEFAULT 7.0,
    graduation_min_completion REAL DEFAULT 0.9
);

CREATE TABLE cohort_participants (
    cohort_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    joined_at TEXT DEFAULT (datetime('now')),
    graduated INTEGER DEFAULT 0,
    graduated_at TEXT,
    FOREIGN KEY (cohort_id) REFERENCES cohorts(id),
    PRIMARY KEY (cohort_id, user_id)
);

CREATE TABLE cohort_weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id TEXT NOT NULL,
    week_number INTEGER NOT NULL,
    label TEXT,
    min_score REAL DEFAULT 6.0,
    start_date TEXT,
    end_date TEXT,
    FOREIGN KEY (cohort_id) REFERENCES cohorts(id)
);

CREATE TABLE cohort_week_scenarios (
    week_id INTEGER NOT NULL,
    scenario_id TEXT NOT NULL,
    FOREIGN KEY (week_id) REFERENCES cohort_weeks(id),
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
    PRIMARY KEY (week_id, scenario_id)
);

-- Indexes for common queries
CREATE INDEX idx_sessions_user ON training_sessions(user_id);
CREATE INDEX idx_sessions_timestamp ON training_sessions(timestamp);
CREATE INDEX idx_sessions_type ON training_sessions(scenario_type);
CREATE INDEX idx_engagement_user ON engagement_events(user_id);
CREATE INDEX idx_engagement_timestamp ON engagement_events(timestamp);
CREATE INDEX idx_assignments_to ON assignments(assigned_to, status);
CREATE INDEX idx_crm_writes_user ON crm_writes(user_id);
```

---

## Architecture Decision: HubSpot Write Strategy

### Current State
- **Read path:** `@hubspot/mcp-server` npm package via MCP (stdio transport) — exposes `hubspot-search-objects` and `hubspot-list-objects`
- **Write path:** Direct `hubspot-api-client` Python SDK in `scripts/sync_data_to_hubspot.py` — creates companies, contacts, deals, notes, and associations

### Decision: Python SDK for Writes (Option 3)

The official `@hubspot/mcp-server` (v0.4.0) may now support write tools, but this is unconfirmed and changing rapidly. The community `shinzo-labs/hubspot-mcp` has full CRUD but adds another dependency.

**We already have proven write patterns** in `sync_data_to_hubspot.py` using the `hubspot-api-client` Python SDK. The safest path:

1. **Extract write functions from the sync script** into a reusable `tools/crm_write.py` module
2. **Keep MCP for reads** (search, list — proven and working)
3. **Use Python SDK for writes** (create notes, update deals, log activities — proven patterns exist)
4. **Log all writes to SQLite** `crm_writes` table for audit trail + mock mode

**Write operations needed:**
| Operation | SDK Method | Used By |
|-----------|-----------|---------|
| Create note on deal | `client.crm.objects.notes.basic_api.create()` + association | `/log`, "Log Note" button, auto-log coaching |
| Update deal stage | `client.crm.deals.basic_api.update()` | "Move to Proposal" button |
| Create task | `client.crm.objects.tasks.basic_api.create()` | Follow-up reminders |
| Create activity | `client.crm.objects.notes.basic_api.create()` | Coaching session logging |

**Mock mode:** When `HUBSPOT_ACCESS_TOKEN` is not set, write to SQLite `crm_writes` table only and update mock JSON files so subsequent reads reflect the changes. This keeps the demo working offline.

---

## Wave 1: Foundation Layer (Training Persistence + CRM Write-Back)
*Everything else depends on these two capabilities.*

### Feature #21 — Training Progress Tracking
**What:** Store every coaching session (roleplay debrief, coach-live summary, prep session) with scores, scenario type, timestamp, and user ID. Surface history via a new `/training-history` command.

**Files to create:**
- `training_store.py` — CRUD for training records
- `formatters/training_history.py` — Block Kit formatter for history view

**Files to modify:**
- `app.py` — Add `/training-history` command handler; update roleplay debrief handler, coach-live summary handler, and prep handler to call `training_store.save_session()` after each session completes
- `graphs/coach.py` — Return structured score data (not just markdown) from debrief

**Data schema:**
```json
{
  "session_id": "uuid",
  "user_id": "U12345",
  "timestamp": "2026-03-12T14:30:00Z",
  "type": "roleplay|coach_live|prep|feedback",
  "scenario": "discovery_call_novatech",
  "scenario_type": "discovery|negotiation|competitive|cold_call|objection",
  "scores": {
    "overall": 7.2,
    "dimensions": {
      "opening": 8,
      "needs_assessment": 6,
      "active_listening": 7,
      "objection_handling": 8,
      "next_steps": 7
    }
  },
  "strengths": ["Good rapport building", "Strong evidence use"],
  "improvements": ["Ask more open questions", "Deeper pain discovery"],
  "turns": 4,
  "methodology": "discovery",
  "metadata": {
    "company": "NovaTech",
    "persona": "Sarah Chen, VP Engineering"
  }
}
```

**Debrief parser:** The current debrief is LLM-generated markdown. We need to change the system prompt to also output structured JSON that we can parse and store. Update `DEBRIEF_PROMPT` in `prompts/coach_prompts.py` to request a JSON block alongside the human-readable debrief:

```
After the narrative debrief, output a JSON block in this exact format:
```json
{"overall": 7.2, "dimensions": {"opening": 8, ...}, "strengths": [...], "improvements": [...]}
```
```

**`/training-history` output:**
- Last 10 sessions with date, scenario type, overall score, trend arrow (↑↓→)
- Average score across all sessions
- Total sessions count
- "Practice Again" button on each row

**Effort:** Medium (2-3 instruction files)

---

### Feature #2 + #11 — CRM Write-Back & Auto-Updates
**What:** Enable writing data back to HubSpot — notes, deal stage updates, activity logging. Make the existing "Log Note" button actually work, and add auto-logging from coaching sessions.

**Files to create:**
- `tools/crm_write.py` — HubSpot write operations (create note, update deal, log activity)
- `formatters/crm_write.py` — Confirmation cards after CRM updates

**Files to modify:**
- `app.py` — Wire up the `log_note` action handler to actually write; add `/log` command; add auto-logging hooks in debrief handler
- `tools/mock_crm.py` — Add write operations for mock mode (append to JSON files)

**Capabilities:**
1. **`/log [deal-name] [note text]`** — Quick note logging to CRM
2. **"Log Note" button** on deal cards → opens modal with text input → writes note to HubSpot
3. **Auto-log coaching sessions** — After roleplay debrief, offer "Log to CRM" button that creates an activity on the deal: "Coaching session: discovery roleplay, score 7.2/10"
4. **Deal stage update** — "Move to Proposal" button on deal cards writes stage change to HubSpot

**HubSpot MCP write tools needed:**
- `create_engagement` (notes, calls, tasks)
- `update_deal` (stage, amount, close date)
- `create_task` (follow-up tasks)

**Mock mode:** When HubSpot MCP is unavailable, append to `data/mock_crm/deals.json` activities array so the data shows up in subsequent reads.

**Effort:** Medium (1-2 instruction files)

---

### Feature #22 — Engagement Analytics
**What:** Track every bot interaction (commands, button clicks, feature usage) per user. This is the telemetry layer that feeds the team dashboard (#15) and skill gap detection (#16).

**Files to create:**
- `engagement_store.py` — Append-only event log
- No formatter needed yet (consumed by #15 team dashboard)

**Files to modify:**
- `app.py` — Add `log_engagement(user_id, event_type, metadata)` call at the top of every command handler and action handler

**Event schema:**
```json
{
  "timestamp": "2026-03-12T14:30:00Z",
  "user_id": "U12345",
  "event_type": "command|action|roleplay_turn|debrief",
  "command": "/research",
  "action_id": "draft_email_from_research",
  "metadata": {"company": "NovaTech", "scenario": "discovery"}
}
```

**Implementation pattern:** A simple decorator or wrapper:
```python
def log_engagement(user_id, event_type, **metadata):
    store = _load_engagement_log()
    store.append({"timestamp": datetime.utcnow().isoformat(), "user_id": user_id, "event_type": event_type, **metadata})
    _save_engagement_log(store)
```

Call at the top of every `@app.command` and `@app.action` handler.

**Effort:** Small (1 instruction file — mostly mechanical insertion)

---

## Wave 2: Coaching Intelligence (Skill Tracking + Custom Scoring)
*Depends on Wave 1's training persistence and engagement tracking.*

### Feature #16 — Skill Gap Detection
**What:** Aggregate training history to identify per-user skill patterns. If a rep scores 5/10 on "needs_assessment" across 4 sessions, flag it as a skill gap.

**Files to create:**
- `tools/skill_analyzer.py` — Aggregation logic over training history
- `formatters/skill_gaps.py` — Block Kit formatter for skill gap report

**Files to modify:**
- `app.py` — Add `/skill-gaps [@user]` command (manager can check any rep, rep defaults to self)

**Analysis logic:**
```python
def analyze_skill_gaps(user_id, min_sessions=3):
    """Analyze training history to find consistent weak areas."""
    sessions = training_store.get_sessions(user_id)
    if len(sessions) < min_sessions:
        return {"status": "insufficient_data", "sessions": len(sessions), "needed": min_sessions}

    # Aggregate dimension scores across sessions
    dimension_scores = defaultdict(list)
    for session in sessions:
        for dim, score in session["scores"]["dimensions"].items():
            dimension_scores[dim].append(score)

    # Identify gaps: dimensions with avg < 6.0 across 3+ sessions
    gaps = []
    for dim, scores in dimension_scores.items():
        avg = sum(scores) / len(scores)
        trend = scores[-1] - scores[0]  # Improving or declining?
        if avg < 6.0:
            gaps.append({
                "skill": dim,
                "avg_score": round(avg, 1),
                "sessions": len(scores),
                "trend": "improving" if trend > 0.5 else "declining" if trend < -0.5 else "flat",
                "latest": scores[-1],
                "recommendation": _get_recommendation(dim, avg),
            })

    return {"gaps": sorted(gaps, key=lambda x: x["avg_score"]), "total_sessions": len(sessions)}
```

**Output card:**
- Header: "Skill Gap Analysis: @username"
- For each gap: skill name, avg score, trend arrow, recommended scenario
- "Start Practice" button for each gap (pre-fills roleplay with the weak skill)
- If no gaps: congratulatory message with overall average

**Effort:** Medium (1 instruction file)

---

### Feature #18 — Custom Methodology Scorecards
**What:** Let managers define which scoring rubric to use (MEDDIC, SPIN, Challenger, BANT, custom). The roleplay debrief scores against the selected methodology instead of the generic rubric.

**Files to create:**
- `data/playbooks/methodologies/meddic.json` — MEDDIC scoring dimensions and criteria
- `data/playbooks/methodologies/spin.json` — SPIN scoring dimensions
- `data/playbooks/methodologies/challenger.json` — Challenger scoring dimensions
- `data/playbooks/methodologies/bant.json` — BANT scoring dimensions
- `tools/methodology.py` — Load and manage methodologies

**Files to modify:**
- `settings_store.py` — Add `methodology` setting (team-wide, set by manager)
- `prompts/coach_prompts.py` — Dynamically inject methodology-specific scoring criteria into the debrief prompt
- `graphs/coach.py` — Pass methodology context into roleplay and debrief
- `app.py` — Update `/settings` modal to include methodology picker (dropdown)

**MEDDIC example schema:**
```json
{
  "name": "MEDDIC",
  "description": "Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion",
  "dimensions": [
    {"key": "metrics", "label": "Metrics Discovery", "description": "Did the rep quantify the business impact? Did they tie solution to measurable outcomes?", "weight": 1.0},
    {"key": "economic_buyer", "label": "Economic Buyer Access", "description": "Did the rep identify and engage the economic buyer?", "weight": 1.0},
    {"key": "decision_criteria", "label": "Decision Criteria", "description": "Did the rep uncover what criteria the buyer uses to evaluate solutions?", "weight": 1.0},
    {"key": "decision_process", "label": "Decision Process", "description": "Did the rep map the buying process, stakeholders, and timeline?", "weight": 1.0},
    {"key": "identify_pain", "label": "Pain Identification", "description": "Did the rep uncover deep, compelling pain beyond surface symptoms?", "weight": 1.2},
    {"key": "champion", "label": "Champion Development", "description": "Did the rep identify and cultivate an internal champion?", "weight": 1.0}
  ]
}
```

**Dynamic prompt injection:**
```python
def build_debrief_prompt(methodology_key="discovery"):
    methodology = load_methodology(methodology_key)
    dimensions_text = "\n".join(
        f"- {d['label']} (1-10): {d['description']}"
        for d in methodology["dimensions"]
    )
    return f"""Score this roleplay using the {methodology['name']} methodology.

Evaluate each dimension on a 1-10 scale:
{dimensions_text}

Provide an overall weighted score and specific examples from the conversation for each dimension."""
```

**`/settings` update:** Add a "Scoring Methodology" section with a static_select dropdown: MEDDIC, SPIN, Challenger, BANT, Default (generic).

**Effort:** Medium (1-2 instruction files)

---

### Feature #9 — Performance Self-Service ("How's my month going?")
**What:** Enhance `/ask` to recognize personal performance questions and pull from training history + CRM data to give conversational answers.

**Files to modify:**
- `graphs/assistant.py` — Add performance context to the `/ask` node when the question matches performance intent
- `prompts/assistant_prompts.py` — Add performance-aware system prompt section
- `tools/rag.py` — Add `search_training_history()` function

**Intent detection patterns:**
- "How's my month going?" → pull scorecard data + training history
- "What's my Q3 target?" → pull pipeline/forecast data
- "How many roleplays have I done?" → pull training history count
- "What's my win rate?" → pull win/loss data for this user
- "Am I improving at discovery?" → pull skill trend from training history

**Implementation:** In the `/ask` handler, before invoking the graph, check if the question matches performance patterns. If so, inject personal context:

```python
performance_keywords = ["my month", "my quarter", "my target", "my win rate",
                        "how am i", "my score", "improving", "my pipeline",
                        "how many", "my deals", "my performance"]

if any(kw in question.lower() for kw in performance_keywords):
    # Inject personal context
    training_summary = training_store.get_user_summary(user_id)
    pipeline_summary = _get_user_pipeline_summary(user_id)
    extra_context = f"\n\nUser's training data:\n{training_summary}\n\nUser's pipeline:\n{pipeline_summary}"
    # Append to the question context sent to the LLM
```

**Effort:** Small (1 instruction file)

---

## Wave 3: Manager Tools (Scenarios, Assignments, Dashboard)
*Depends on Wave 1 + 2 for data to display and score against.*

### Feature #14 — Simulation Builder
**What:** A `/create-scenario` command that lets managers define reusable roleplay scenarios with specific personas, objectives, difficulty levels, and scoring criteria. Saved to a scenario library.

**Files to create:**
- `scenario_store.py` — CRUD for scenario library
- `formatters/scenario.py` — Block Kit for scenario cards and library view

**Files to modify:**
- `app.py` — Add `/create-scenario`, `/scenarios`, `/edit-scenario` commands
- `graphs/coach.py` — When a scenario ID is provided, load it from the library instead of generating on-the-fly

**`/create-scenario` flow (modal):**
1. User runs `/create-scenario` → opens modal
2. Modal fields:
   - **Name** (text input): "Discovery Call: Enterprise CFO"
   - **Type** (select): Discovery / Negotiation / Competitive / Cold Call / Objection / Custom
   - **Difficulty** (select): Beginner / Intermediate / Advanced / Expert
   - **Buyer Persona** (text area): "CFO at a Fortune 500 manufacturing company, skeptical of AI, budget-constrained..."
   - **Objectives** (text area): "Uncover 3 pain points, identify the decision process, get agreement on a next meeting"
   - **Key Objections** (text area): "Budget is frozen until Q3, Already have an in-house solution, Need to see ROI proof"
   - **Methodology** (select): MEDDIC / SPIN / Challenger / BANT / Default
3. On submit → save to `data/scenarios/` as JSON → confirm in channel

**Scenario schema:**
```json
{
  "id": "uuid",
  "name": "Discovery Call: Enterprise CFO",
  "type": "discovery",
  "difficulty": "advanced",
  "created_by": "U12345",
  "created_at": "2026-03-12T14:30:00Z",
  "persona": {
    "name": "Margaret Chen",
    "title": "CFO",
    "company": "GlobalMfg Corp",
    "personality": "Analytical, skeptical, time-pressed",
    "background": "15 years in manufacturing finance...",
    "objections": ["Budget frozen until Q3", "In-house solution exists"],
    "priorities": ["Cost reduction", "Board reporting", "Compliance"]
  },
  "objectives": ["Uncover 3 pain points", "Identify decision process", "Get next meeting"],
  "scoring_methodology": "meddic",
  "tags": ["enterprise", "cfo", "manufacturing"],
  "usage_count": 0,
  "avg_score": null
}
```

**`/scenarios` command:**
- Lists all saved scenarios as a scrollable picker
- Shows: name, type, difficulty, avg score, times practiced
- "Start Practice" button on each
- Filter by type/difficulty

**Integration with roleplay:** When a rep runs `/coach roleplay --scenario [id]`, load the saved scenario instead of generating one on-the-fly. Pass the persona, objectives, and methodology directly to the roleplay node.

**Effort:** Large (2 instruction files — modal + store + integration)

---

### Feature #20 — Manager Scenario Assignment
**What:** Managers can assign specific scenarios to reps with deadlines. Reps see their assignments on their Home tab and get DM reminders.

**Files to create:**
- `assignment_store.py` — CRUD for assignments
- `formatters/assignments.py` — Block Kit for assignment cards

**Files to modify:**
- `app.py` — Add `/assign` command, update Home tab to show pending assignments
- `formatters/home_tab.py` — Add "Your Assignments" section

**`/assign` flow:**
1. Manager runs `/assign @rep scenario-name` or `/assign @rep --scenario [id]`
2. Bot validates the scenario exists and the target is a valid user
3. Creates assignment record
4. DMs the rep: "Your manager assigned you a training exercise: Discovery Call: Enterprise CFO (Advanced). Due by Mar 19."
5. Assignment appears on rep's Home tab under "Pending Assignments"

**Assignment schema:**
```json
{
  "id": "uuid",
  "scenario_id": "scenario-uuid",
  "assigned_by": "U_MANAGER",
  "assigned_to": "U_REP",
  "assigned_at": "2026-03-12T14:30:00Z",
  "due_date": "2026-03-19T23:59:59Z",
  "status": "pending|completed|overdue",
  "completed_at": null,
  "session_id": null,
  "score": null
}
```

**Completion tracking:** When a rep completes a roleplay for an assigned scenario, automatically mark the assignment as completed and store the session_id + score. Notify the manager: "Sarah completed 'Discovery Call: Enterprise CFO' — Score: 7.8/10."

**Home tab update:** Add an "Assignments" section at the top:
```
📋 Your Assignments (2 pending)
┌──────────────────────────────────────────┐
│ Discovery Call: Enterprise CFO           │
│ Assigned by @manager · Due Mar 19       │
│ [Start Practice]                         │
├──────────────────────────────────────────┤
│ Objection Handling: Budget               │
│ Assigned by @manager · Due Mar 21       │
│ [Start Practice]                         │
└──────────────────────────────────────────┘
```

**Effort:** Medium (1-2 instruction files)

---

### Feature #15 — Team Performance Dashboard
**What:** A `/team-dashboard` command for managers that shows all reps' coaching activity, scores, skill gaps, and engagement at a glance.

**Files to create:**
- `formatters/team_dashboard.py` — Block Kit formatter for dashboard

**Files to modify:**
- `app.py` — Add `/team-dashboard` command handler
- `training_store.py` — Add `get_team_summary(user_ids)` function
- `engagement_store.py` — Add `get_team_engagement(user_ids)` function

**Dashboard sections:**

1. **Team Overview header:**
   - Total sessions this week/month
   - Team avg score
   - Most active rep / Least active rep

2. **Rep Leaderboard (monospace table):**
   ```
   Rep              Sessions  Avg Score  Trend  Last Active
   ──────────────────────────────────────────────────────────
   @sarah.jones          12      7.8/10    ↑    2h ago
   @mike.chen             8      6.5/10    →    1d ago
   @alex.kumar            3      5.2/10    ↓    5d ago
   ```

3. **Skill Gap Heatmap (simplified):**
   ```
   Skill               @sarah  @mike  @alex
   ──────────────────────────────────────────
   Opening              🟢 8.1  🟡 6.2  🔴 4.8
   Needs Assessment     🟢 7.5  🔴 5.0  🔴 4.2
   Objection Handling   🟡 6.8  🟡 6.8  🟡 6.0
   ```
   (🟢 ≥7, 🟡 5-6.9, 🔴 <5)

4. **Pending Assignments:**
   - X assignments pending, Y overdue, Z completed this week

5. **Action buttons:**
   - "Assign Training" → launches `/assign`
   - "View Rep Detail" → overflow menu with rep names → `/training-history @rep`
   - "Export Report" → generates summary text

**Manager detection:** Check if user is in a Slack user group (e.g., `@managers`) or has a specific role. For POC, any user can run `/team-dashboard` — restrict later.

**Mock data:** For demo, pre-populate `training_history/` with 20-30 synthetic sessions across 3-4 mock users to make the dashboard look rich.

**Effort:** Medium-Large (1-2 instruction files)

---

## Wave 4: Training Programs (Cohorts, Onboarding, Product Launch)
*Depends on Wave 3 for scenario library and assignment system.*

### Feature #17 — Cohort-Based Learning Cycles
**What:** Managers can create multi-week training programs (cohorts) with a sequence of scenarios, deadlines, and graduation criteria. Reps progress through the program together.

**Files to create:**
- `cohort_store.py` — CRUD for cohort programs
- `formatters/cohort.py` — Block Kit for cohort progress cards

**Files to modify:**
- `app.py` — Add `/create-cohort`, `/cohorts`, `/cohort-progress` commands
- `formatters/home_tab.py` — Add "Active Programs" section

**`/create-cohort` flow (modal):**
```
Modal: Create Training Program
─────────────────────────────
Program Name:    [New Hire Ramp Q1 2026           ]
Description:     [4-week onboarding for new SDRs   ]
Duration:        [4 weeks ▾]
Participants:    [@sarah, @mike, @alex             ]

Week 1 — Foundation
  Scenario: [Cold Call: Gatekeeper ▾]
  Scenario: [Discovery: SMB Owner ▾]
  Min Score: [6 ]

Week 2 — Intermediate
  Scenario: [Objection: Budget ▾]
  Scenario: [Competitive: Incumbent ▾]
  Min Score: [6 ]

Week 3 — Advanced
  Scenario: [Discovery: Enterprise CFO ▾]
  Scenario: [Negotiation: Multi-Stakeholder ▾]
  Min Score: [7 ]

Week 4 — Graduation
  Scenario: [Full Cycle: Enterprise ▾]
  Min Score: [7.5]

[Cancel]  [Create Program]
```

**Note:** Slack modals have a 100-block limit. For the POC, use a simpler approach — manager provides program details as structured text:

```
/create-cohort "New Hire Ramp" @sarah @mike @alex --weeks 4
```

Then the bot asks follow-up questions in a thread to configure each week.

**Cohort schema:**
```json
{
  "id": "uuid",
  "name": "New Hire Ramp Q1 2026",
  "created_by": "U_MANAGER",
  "created_at": "2026-03-01T00:00:00Z",
  "participants": ["U_SARAH", "U_MIKE", "U_ALEX"],
  "weeks": [
    {
      "week_number": 1,
      "label": "Foundation",
      "scenarios": ["scenario-id-1", "scenario-id-2"],
      "min_score": 6.0,
      "start_date": "2026-03-03",
      "end_date": "2026-03-09"
    }
  ],
  "graduation_criteria": {"min_avg_score": 7.0, "min_completion": 0.9},
  "status": "active|completed|archived"
}
```

**Progress tracking:** `/cohort-progress [program-name]`
```
📚 New Hire Ramp Q1 2026 — Week 2 of 4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@sarah  ████████░░ Week 2  |  Avg: 7.2  ✅ On track
@mike   ██████░░░░ Week 2  |  Avg: 6.1  ⚠️ Below min
@alex   ████░░░░░░ Week 1  |  Avg: 5.4  🔴 Behind

Week 2 Scenarios:
  ✅ @sarah — Objection: Budget (7.5/10)
  ✅ @sarah — Competitive: Incumbent (6.9/10)
  ✅ @mike — Objection: Budget (6.2/10)
  ⬜ @mike — Competitive: Incumbent (not started)
  ⬜ @alex — Objection: Budget (not started)
  ⬜ @alex — Competitive: Incumbent (not started)
```

**Automation hooks:**
- Auto-assign week's scenarios when a new week starts
- DM reps with weekly reminders
- Notify manager when someone falls behind
- Graduation notification when all weeks complete and criteria met

**Effort:** Large (2-3 instruction files)

---

### Feature #13 — Structured Onboarding Flow
**What:** A pre-built cohort template specifically for new hire onboarding. `/onboard @new-rep` creates a 4-week program using curated beginner → advanced scenarios.

**Files to create:**
- `data/cohort_templates/new_hire_onboard.json` — Pre-built 4-week program
- `data/cohort_templates/product_launch.json` — Reused by #23

**Files to modify:**
- `app.py` — Add `/onboard @user` command that creates a cohort from the template
- `cohort_store.py` — Add `create_from_template()` method

**Template:** The onboarding template uses scenarios from the scenario library:
- Week 1: Product knowledge quiz, cold call basics, simple discovery
- Week 2: Objection handling, competitive positioning, email sequences
- Week 3: Complex discovery, negotiation fundamentals, multi-stakeholder
- Week 4: Full-cycle roleplay, live call practice, graduation assessment

**Implementation:** `/onboard @sarah` → loads `new_hire_onboard.json` → creates cohort with just that user → auto-assigns week 1 scenarios → DMs the rep with welcome message.

**Effort:** Small (1 instruction file — mostly template creation, reuses cohort infrastructure)

---

### Feature #23 — Product Launch Training Mode
**What:** `/launch-training [product-name]` creates a focused training sprint for the whole team on a new product. Manager provides product context (or uploads a doc), and the system generates roleplay scenarios specific to the new product.

**Files to create:**
- `data/cohort_templates/product_launch.json` — Template structure

**Files to modify:**
- `app.py` — Add `/launch-training` command
- `graphs/coach.py` — Add product-context injection into roleplay node

**Flow:**
1. Manager runs `/launch-training "CloudSync Enterprise"`
2. Bot opens modal: paste product description, key features, target personas, common objections
3. LLM generates 4-6 scenario variants automatically (cold call, discovery, objection handling, competitive positioning — all themed around the new product)
4. Saves scenarios to the library with `tag: "product_launch_cloudsync"`
5. Creates a 1-2 week cohort for the whole team
6. DMs all reps with the new training program

**LLM scenario generation prompt:**
```
Given this new product information:
{product_description}

Generate 5 roleplay scenarios for sales reps to practice. For each scenario, provide:
- Name, type, difficulty, buyer persona, objectives, likely objections

Scenario types to generate:
1. Cold call introducing the new product
2. Discovery call exploring fit
3. Handling "we already have a solution" objection
4. Competitive positioning against [existing competitor]
5. Executive-level value conversation
```

**Effort:** Medium (1 instruction file — reuses cohort + scenario infrastructure)

---

## Wave 5: Pam Parity (Calendar, Email, Multi-Language, Market Insights)
*Independent of Waves 2-4. Can be built in parallel.*

### Feature #5 — Calendar & Day Plan Awareness
**What:** Integrate with Google Calendar (via MCP or API) to give the bot awareness of the user's meetings. Enhance `/coach prep` to auto-detect the next meeting and prep for it.

**Files to create:**
- `tools/calendar.py` — Calendar read operations (next meeting, today's schedule, meeting details)
- `formatters/calendar.py` — Block Kit for day plan card

**Files to modify:**
- `app.py` — Add `/my-day` command; modify `/coach prep` to auto-detect next meeting
- `graphs/coach.py` — Inject meeting context into prep node

**MCP approach:** Use a Google Calendar MCP server (community package exists: `@anthropic/google-calendar-mcp`). Configure in `mcp_setup.py`.

**Mock fallback:** Create `data/mock_calendar/events.json` with synthetic meetings:
```json
[
  {
    "id": "evt_1",
    "title": "Discovery Call — NovaTech",
    "start": "2026-03-12T14:00:00-07:00",
    "end": "2026-03-12T14:45:00-07:00",
    "attendees": ["sarah@novatech.io", "john@ourcompany.com"],
    "description": "Initial discovery call to discuss their data pipeline challenges",
    "location": "Zoom",
    "company": "NovaTech"
  }
]
```

**`/my-day` output:**
```
📅 Your Day — Thursday, Mar 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2:00 PM  Discovery Call — NovaTech
         Sarah Chen (VP Eng) · Zoom
         [Prep for This Meeting]  [Research NovaTech]

3:30 PM  Pipeline Review — Internal
         @team-sales · Conference Room B
         [View Pipeline]

5:00 PM  Follow-up Call — Apex Systems
         Mike Davis (CTO) · Phone
         [Prep for This Meeting]  [View Deal]
```

**Smart `/coach prep`:**
Currently: `/coach prep NovaTech` requires manually specifying the company.
Enhanced: `/coach prep` (no args) → looks up next meeting from calendar → extracts company name → auto-preps.

```python
# In /coach prep handler:
if not company_name:
    next_meeting = calendar.get_next_meeting(user_id)
    if next_meeting:
        company_name = next_meeting.get("company") or _extract_company(next_meeting["title"])
        meeting_context = f"Meeting: {next_meeting['title']} at {next_meeting['start']}"
    else:
        say("No upcoming meetings found. Use `/coach prep [company]` to prep manually.")
        return
```

**Effort:** Medium (1-2 instruction files)

---

### Feature #7 — Auto Rescheduling
**What:** From the `/my-day` view, add a "Reschedule" button on meetings. Opens a modal with time slot suggestions. Writes the change to Google Calendar.

**Files to modify:**
- `app.py` — Add `reschedule_meeting` action handler
- `tools/calendar.py` — Add `update_event()`, `find_available_slots()` functions
- `formatters/calendar.py` — Add reschedule modal blocks

**Flow:**
1. From `/my-day`, click "Reschedule" on a meeting
2. Modal shows: current time, suggested alternative slots (based on calendar availability)
3. User picks a slot → calendar event is updated → attendees get notification
4. Confirmation in channel: "Moved 'Discovery Call — NovaTech' from 2:00 PM to 4:00 PM. Attendees notified."

**Note:** This requires calendar WRITE access. For POC demo, we can update mock data and show the flow without actually writing to Google Calendar.

**Effort:** Small (1 instruction file — reuses calendar infrastructure)

---

### Feature #4 — Email Send + Attachments
**What:** Upgrade from "Create Gmail Draft" to actually sending emails. Support attaching documents (brochures, proposals, case studies).

**Files to modify:**
- `app.py` — Update `create_gmail_draft` action to offer "Send Now" option; add attachment flow
- `formatters/email.py` — Add "Send Now" button alongside "Create Gmail Draft"
- `tools/` — Add document lookup for attachments

**Implementation:**
1. **Send Now:** After email draft is confirmed, add a "Send Now" button. Uses Gmail MCP `send_email` tool instead of `create_draft`.
2. **Attachments:** Add an "Attach Document" button on the email draft card. Opens a picker showing available documents from a `data/documents/` folder (brochures, case studies, price lists). Selected document gets attached to the email.

**Document library:**
```
data/documents/
├── brochures/
│   ├── product_overview.pdf
│   └── enterprise_solution.pdf
├── case_studies/
│   ├── case_study_apex.pdf
│   └── case_study_cloudbridge.pdf
└── pricing/
    └── pricing_guide_2026.pdf
```

**Email draft card update:**
```
Draft Follow-Up: NovaTech
To: Sarah Chen (sarah@novatech.io)
Subject: Following up on our discovery call

[email body here]

📎 Attached: Product Overview Brochure (2.4 MB)

[Send Now]  [Create Gmail Draft]  [Attach Document]  [Regenerate]
```

**Effort:** Medium (1 instruction file)

---

### Feature #10 — Multi-Language Support
**What:** Support generating responses in the user's preferred language. Not full i18n of the UI — just LLM output language and key UI labels.

**Files to modify:**
- `settings_store.py` — Add `language` setting
- `app.py` — Update `/settings` modal with language dropdown
- `prompts/coach_prompts.py` — Inject language instruction into all system prompts
- `prompts/assistant_prompts.py` — Same

**Supported languages (POC):** English, German, French, Spanish, Portuguese

**Implementation:** The simplest approach — add a language instruction to every LLM system prompt:

```python
language = get_user_settings(user_id).get("language", "en")
language_names = {"en": "English", "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese"}

language_instruction = ""
if language != "en":
    language_instruction = f"\n\nIMPORTANT: Respond entirely in {language_names[language]}. All analysis, recommendations, coaching feedback, and email drafts must be in {language_names[language]}."

# Prepend to every system prompt:
system_prompt = BASE_PROMPT + language_instruction
```

**UI labels:** Keep Slack Block Kit labels (button text, headers) in English for the POC. Only LLM-generated content switches language. Note this in the settings: "AI responses will be in your selected language. Interface labels remain in English."

**Effort:** Small (1 instruction file — mechanical prompt injection)

---

### Feature #12 — Market Shift Insights / Customer Sentiment
**What:** Aggregate patterns from across all deal notes, coaching sessions, and research to surface market trends. "What objections are coming up most?" "Which competitors are mentioned more this quarter?"

**Files to create:**
- `tools/market_insights.py` — Aggregation logic across CRM data
- `formatters/market_insights.py` — Block Kit for insights card

**Files to modify:**
- `app.py` — Add `/market-insights` command

**Analysis dimensions:**
1. **Top objections this quarter** — Scan deal notes and coaching sessions for objection patterns
2. **Competitor mentions** — Count competitor references across all deal notes
3. **Emerging themes** — LLM-powered clustering of recent deal notes to find patterns
4. **Sentiment shift** — Compare this month's deal note tone vs. last month's

**Implementation:** This is heavily LLM-dependent. Pull all recent deal notes (last 30 days), coaching transcripts, and research outputs. Feed them to the LLM with an analysis prompt:

```
Analyze these recent sales interactions and identify:
1. The 5 most common objections (with frequency)
2. Competitors mentioned (with frequency and context)
3. Emerging market themes or shifts
4. Changes in buyer sentiment compared to the prior period

Data:
{deal_notes_last_30_days}
{coaching_transcripts_last_30_days}
```

**For POC/mock:** Pre-generate a compelling insights card using the mock CRM data.

**Effort:** Medium (1 instruction file)

---

### Feature #19 — Private Practice Space
**What:** Already planned in UX Phase 3 (`UX-PHASE3-smart-defaults-modals-settings.md`). Coaching sessions happen in DMs when `coaching_privacy: true`.

**Status:** Instruction file already exists. No additional work needed beyond implementing Phase 3.

**Effort:** None (already covered)

---

## Implementation Order & Dependencies

```
                         ┌─────────────────────────┐
                         │  WAVE 1: Foundation      │
                         │  #21 Training History    │
                         │  #2+#11 CRM Write-Back   │
                         │  #22 Engagement Analytics │
                         └───────────┬─────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
          ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼──────────┐
          │  WAVE 2:       │ │  WAVE 5:     │ │                 │
          │  Coaching Intel│ │  Pam Parity  │ │  (independent)  │
          │  #16 Skill Gaps│ │  #5 Calendar │ │                 │
          │  #18 Scorecards│ │  #7 Resched  │ │                 │
          │  #9 Self-Serve │ │  #4 Send+Att │ │                 │
          └────────┬───────┘ │  #10 i18n    │ │                 │
                   │         │  #12 Insights│ │                 │
          ┌────────▼───────┐ │  #19 Privacy │ │                 │
          │  WAVE 3:       │ └──────────────┘ │                 │
          │  Manager Tools │                  │                 │
          │  #14 Scenarios │                  │                 │
          │  #20 Assign    │                  │                 │
          │  #15 Dashboard │                  │                 │
          └────────┬───────┘                  │                 │
                   │                          │                 │
          ┌────────▼───────┐                  │                 │
          │  WAVE 4:       │                  │                 │
          │  Training Pgms │                  │                 │
          │  #17 Cohorts   │                  │                 │
          │  #13 Onboarding│                  │                 │
          │  #23 Prod Lnch │                  │                 │
          └────────────────┘                  │                 │
                                              │                 │
```

Waves 2-4 are sequential (each builds on the last).
Wave 5 is independent and can be built in parallel with Waves 2-4.

---

## Estimated Instruction Files

| Wave | Features | Instruction Files | Approx Effort |
|------|----------|-------------------|---------------|
| 1 | #21, #2+#11, #22 | 3-4 files | Medium |
| 2 | #16, #18, #9 | 3 files | Medium |
| 3 | #14, #20, #15 | 4-5 files | Large |
| 4 | #17, #13, #23 | 3-4 files | Large |
| 5 | #5, #7, #4, #10, #12, #19 | 5-6 files | Medium |
| **Total** | **19 features** | **18-22 files** | |

---

## New Slash Commands Summary

| Command | Wave | Description |
|---------|------|-------------|
| `/training-history [@user]` | 1 | View coaching session history and score trends |
| `/log [deal] [note]` | 1 | Quick-log a note to CRM |
| `/skill-gaps [@user]` | 2 | Analyze skill weaknesses across sessions |
| `/create-scenario` | 3 | Build a reusable roleplay scenario |
| `/scenarios` | 3 | Browse the scenario library |
| `/assign @rep [scenario]` | 3 | Assign training to a rep |
| `/team-dashboard` | 3 | Manager view of all reps' progress |
| `/create-cohort` | 4 | Build a multi-week training program |
| `/cohort-progress [name]` | 4 | View cohort completion status |
| `/onboard @rep` | 4 | Start a new-hire onboarding program |
| `/launch-training [product]` | 4 | Create product-focused training sprint |
| `/my-day` | 5 | Calendar day plan with meeting prep |
| `/market-insights` | 5 | Aggregated market and objection trends |

Total new commands: **13** (on top of existing 19 = **32 commands**)

---

## New Data Files Summary

```
data/
├── salescoach.db              Wave 1 — SQLite database (ALL persistent data)
├── mock_crm/                  (existing — still used as read source for mock mode)
├── playbooks/
│   └── methodologies/         Wave 2 — scoring methodology definitions
│       ├── meddic.json
│       ├── spin.json
│       ├── challenger.json
│       └── bant.json
├── cohort_templates/          Wave 4 — pre-built program templates
│   ├── new_hire_onboard.json
│   └── product_launch.json
├── documents/                 Wave 5 — email attachment library
│   ├── brochures/
│   ├── case_studies/
│   └── pricing/
└── mock_calendar/             Wave 5 — synthetic calendar events
    └── events.json
```

## New Source Files Summary

```
(root)
├── db.py                      Wave 1 — SQLite connection + init_db() + seed_demo_data()
│
├── tools/
│   ├── crm_write.py           Wave 1 — HubSpot Python SDK write operations
│   ├── skill_analyzer.py      Wave 2 — SQL-based skill gap aggregation
│   ├── methodology.py         Wave 2 — Load methodology JSON definitions
│   ├── calendar.py            Wave 5 — Calendar read/write (MCP or mock)
│   └── market_insights.py     Wave 5 — LLM-powered trend analysis
│
├── formatters/
│   ├── training_history.py    Wave 1
│   ├── crm_write.py           Wave 1
│   ├── skill_gaps.py          Wave 2
│   ├── scenario.py            Wave 3
│   ├── assignments.py         Wave 3
│   ├── team_dashboard.py      Wave 3
│   ├── cohort.py              Wave 4
│   ├── calendar.py            Wave 5
│   └── market_insights.py     Wave 5
│
└── scripts/
    └── seed_demo_data.py      Wave 1 — Populate SQLite with synthetic training data
```
