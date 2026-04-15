# Wave 2 — Skill Gap Detection, Custom Scorecards, Performance Self-Service

Features #16, #18, #9. Builds on Wave 1's training persistence and engagement tracking.

**Depends on:** Wave 1 (SQLite + training_sessions + dimension_scores tables populated)

---

## Feature #16: Skill Gap Detection

### Step 1: Create `tools/skill_analyzer.py`

```python
"""Analyze training history to detect skill gaps using SQLite aggregation."""
from db import get_db


def analyze_skill_gaps(user_id, min_sessions=3):
    """Identify consistent weak skill dimensions for a user.

    Returns dict with:
      - gaps: list of weak dimensions (avg < 6.0)
      - strengths: list of strong dimensions (avg >= 7.5)
      - total_sessions: number of sessions analyzed
      - status: 'ok' | 'insufficient_data'
    """
    with get_db() as conn:
        # Check total sessions
        count = conn.execute(
            "SELECT COUNT(*) FROM training_sessions WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        if count < min_sessions:
            return {"status": "insufficient_data", "total_sessions": count, "needed": min_sessions}

        # Get dimension averages with trend
        rows = conn.execute("""
            SELECT
                ds.dimension,
                AVG(ds.score) as avg_score,
                COUNT(*) as session_count,
                -- Get the score from the oldest and newest sessions for trend
                (SELECT ds2.score FROM dimension_scores ds2
                 JOIN training_sessions ts2 ON ds2.session_id = ts2.id
                 WHERE ts2.user_id = ? AND ds2.dimension = ds.dimension
                 ORDER BY ts2.timestamp DESC LIMIT 1
                ) as latest_score,
                (SELECT ds3.score FROM dimension_scores ds3
                 JOIN training_sessions ts3 ON ds3.session_id = ts3.id
                 WHERE ts3.user_id = ? AND ds3.dimension = ds.dimension
                 ORDER BY ts3.timestamp ASC LIMIT 1
                ) as oldest_score
            FROM dimension_scores ds
            JOIN training_sessions ts ON ds.session_id = ts.id
            WHERE ts.user_id = ?
            GROUP BY ds.dimension
            HAVING COUNT(*) >= ?
            ORDER BY avg_score ASC
        """, (user_id, user_id, user_id, min_sessions)).fetchall()

        gaps = []
        strengths = []

        for row in rows:
            dim_data = {
                "dimension": row["dimension"],
                "avg_score": round(row["avg_score"], 1),
                "session_count": row["session_count"],
                "latest_score": row["latest_score"],
                "trend": _calc_trend(row["oldest_score"], row["latest_score"]),
                "recommendation": _get_recommendation(row["dimension"], row["avg_score"]),
            }

            if row["avg_score"] < 6.0:
                gaps.append(dim_data)
            elif row["avg_score"] >= 7.5:
                strengths.append(dim_data)

        return {
            "status": "ok",
            "gaps": gaps,
            "strengths": sorted(strengths, key=lambda x: x["avg_score"], reverse=True),
            "total_sessions": count,
        }


def _calc_trend(oldest, latest):
    if oldest is None or latest is None:
        return "unknown"
    diff = latest - oldest
    if diff > 0.5:
        return "improving"
    elif diff < -0.5:
        return "declining"
    return "flat"


RECOMMENDATIONS = {
    "opening": "Practice cold call pattern interrupts and personalized openers",
    "needs_assessment": "Focus on open-ended discovery questions — try SPIN scenarios",
    "active_listening": "Practice paraphrasing and silence — let the prospect talk more",
    "objection_handling": "Run objection-specific roleplays — especially budget and timing",
    "next_steps": "Practice commitment-getting closes — always end with a concrete next step",
    "value_establishment": "Lead with business impact before discussing features",
    "negotiation_discipline": "Practice holding firm on pricing — use value justification",
    "creative_structuring": "Explore multi-year deals, phased rollouts, and bundling",
    "composure": "Practice staying calm under pressure — try aggressive buyer personas",
    "closing_strength": "Work on trial close techniques and urgency creation",
    "competitive_positioning": "Study battle cards and practice 'Why us' storytelling",
    "buyer_understanding": "Ask about evaluation criteria and decision process earlier",
    "evidence_proof": "Lead with case studies and quantified outcomes",
    "strategic_questioning": "Practice Socratic questioning — guide instead of tell",
    "pattern_interrupt": "Try unconventional openers that break the 'not interested' reflex",
    "relevance": "Research the prospect's specific pain before the call",
    "value_in_30s": "Craft and practice a 30-second value prop specific to each vertical",
}


def _get_recommendation(dimension, avg_score):
    base = RECOMMENDATIONS.get(dimension, f"Practice {dimension.replace('_', ' ')} scenarios")
    if avg_score < 4:
        return f"Priority: {base}"
    return base
```

### Step 2: Create `formatters/skill_gaps.py`

```python
"""Block Kit formatter for skill gap analysis."""
import json
from formatters.helpers import timestamp


def format_skill_gaps(user_id, analysis):
    """Format skill gap analysis as Block Kit blocks."""
    if analysis["status"] == "insufficient_data":
        return _format_insufficient_data(user_id, analysis)

    gaps = analysis["gaps"]
    strengths = analysis["strengths"]
    total = analysis["total_sessions"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Skill Analysis: <@{user_id}>", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Based on {total} training sessions"}]
        },
        {"type": "divider"},
    ]

    # Gaps section
    if gaps:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Areas Needing Improvement*"}
        })
        for gap in gaps:
            trend_icon = {"improving": "↑", "declining": "↓", "flat": "→"}.get(gap["trend"], "")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🔴 *{_format_dimension(gap['dimension'])}* — {gap['avg_score']}/10 {trend_icon}\n"
                        f"_{gap['recommendation']}_"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice This", "emoji": True},
                    "action_id": "practice_skill_gap",
                    "value": json.dumps({"dimension": gap["dimension"], "scenario_type": _dim_to_scenario(gap["dimension"])}),
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ *No significant skill gaps detected.* All dimensions averaging 6.0+ across sessions."}
        })

    blocks.append({"type": "divider"})

    # Strengths section
    if strengths:
        strength_lines = " · ".join(
            f"🟢 {_format_dimension(s['dimension'])} ({s['avg_score']}/10)"
            for s in strengths[:4]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Strengths:* {strength_lines}"}
        })
        blocks.append({"type": "divider"})

    # Actions
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Training History", "emoji": True},
                "action_id": "view_training_history",
                "value": user_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice", "emoji": True},
                "action_id": "start_new_practice",
                "style": "primary",
            },
        ]
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]
    })

    fallback = f"Skill Analysis: {len(gaps)} gaps found, {len(strengths)} strengths across {total} sessions"
    return blocks, fallback


def _format_insufficient_data(user_id, analysis):
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"Not enough data yet for <@{user_id}>. "
                f"Completed {analysis['total_sessions']} of {analysis['needed']} sessions needed.\n\n"
                f"Run `/coach roleplay` to start building your skill profile."
            )}
        }
    ]
    return blocks, f"Skill analysis: need {analysis['needed'] - analysis['total_sessions']} more sessions"


def _format_dimension(dim):
    return dim.replace("_", " ").title()


def _dim_to_scenario(dim):
    """Map a dimension to its most relevant scenario type."""
    mapping = {
        "opening": "cold_call", "needs_assessment": "discovery", "active_listening": "discovery",
        "objection_handling": "objection", "next_steps": "discovery",
        "value_establishment": "negotiation", "negotiation_discipline": "negotiation",
        "creative_structuring": "negotiation", "composure": "negotiation", "closing_strength": "negotiation",
        "competitive_positioning": "competitive", "buyer_understanding": "competitive",
        "evidence_proof": "competitive", "strategic_questioning": "competitive",
        "pattern_interrupt": "cold_call", "relevance": "cold_call",
        "value_in_30s": "cold_call", "next_step": "cold_call",
    }
    return mapping.get(dim, "discovery")
```

### Step 3: Add `/skill-gaps` Command

In `app.py`:

```python
from tools.skill_analyzer import analyze_skill_gaps
from formatters.skill_gaps import format_skill_gaps

@app.command("/skill-gaps")
def handle_skill_gaps(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/skill-gaps")

    # Allow checking another user: /skill-gaps @user
    target_user = user_id
    if text.startswith("<@") and text.endswith(">"):
        target_user = text[2:-1].split("|")[0]

    analysis = analyze_skill_gaps(target_user)
    blocks, fallback = format_skill_gaps(target_user, analysis)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

---

## Feature #18: Custom Methodology Scorecards

### Step 1: Create Methodology JSON Files

Create `data/playbooks/methodologies/` directory with 4 files:

**`meddic.json`:**
```json
{
  "name": "MEDDIC",
  "description": "Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion",
  "dimensions": [
    {"key": "metrics", "label": "Metrics Discovery", "description": "Did the rep quantify business impact and tie the solution to measurable outcomes?", "weight": 1.0},
    {"key": "economic_buyer", "label": "Economic Buyer Access", "description": "Did the rep identify and engage the person with budget authority?", "weight": 1.0},
    {"key": "decision_criteria", "label": "Decision Criteria", "description": "Did the rep uncover evaluation criteria the buyer uses to compare solutions?", "weight": 1.0},
    {"key": "decision_process", "label": "Decision Process", "description": "Did the rep map the buying process, stakeholders, timeline, and approval flow?", "weight": 1.0},
    {"key": "identify_pain", "label": "Pain Identification", "description": "Did the rep uncover deep, compelling pain beyond surface-level symptoms?", "weight": 1.2},
    {"key": "champion", "label": "Champion Development", "description": "Did the rep identify and cultivate an internal champion who will sell on their behalf?", "weight": 1.0}
  ]
}
```

**`spin.json`:**
```json
{
  "name": "SPIN Selling",
  "description": "Situation, Problem, Implication, Need-Payoff questions",
  "dimensions": [
    {"key": "situation_questions", "label": "Situation Questions", "description": "Did the rep gather context about the prospect's current state and environment?", "weight": 0.8},
    {"key": "problem_questions", "label": "Problem Questions", "description": "Did the rep uncover specific problems, difficulties, or dissatisfactions?", "weight": 1.0},
    {"key": "implication_questions", "label": "Implication Questions", "description": "Did the rep explore the consequences and impact of those problems?", "weight": 1.2},
    {"key": "need_payoff_questions", "label": "Need-Payoff Questions", "description": "Did the rep guide the prospect to articulate the value of solving the problem?", "weight": 1.2},
    {"key": "active_listening", "label": "Active Listening", "description": "Did the rep listen deeply, acknowledge responses, and build on what was said?", "weight": 1.0}
  ]
}
```

**`challenger.json`:**
```json
{
  "name": "Challenger Sale",
  "description": "Teach, Tailor, Take Control",
  "dimensions": [
    {"key": "commercial_teaching", "label": "Commercial Teaching", "description": "Did the rep share a unique insight that reframes how the prospect thinks about their problem?", "weight": 1.2},
    {"key": "tailoring", "label": "Tailoring the Message", "description": "Did the rep adapt their pitch to the prospect's specific role, industry, and priorities?", "weight": 1.0},
    {"key": "taking_control", "label": "Taking Control", "description": "Did the rep assertively guide the conversation, push back constructively, and maintain momentum?", "weight": 1.0},
    {"key": "constructive_tension", "label": "Constructive Tension", "description": "Did the rep respectfully challenge the prospect's assumptions to create urgency?", "weight": 1.0},
    {"key": "value_articulation", "label": "Value Articulation", "description": "Did the rep clearly connect their solution to quantified business outcomes?", "weight": 1.0}
  ]
}
```

**`bant.json`:**
```json
{
  "name": "BANT",
  "description": "Budget, Authority, Need, Timeline",
  "dimensions": [
    {"key": "budget", "label": "Budget Discovery", "description": "Did the rep uncover the prospect's budget range, funding source, or willingness to invest?", "weight": 1.0},
    {"key": "authority", "label": "Authority Mapping", "description": "Did the rep identify the decision maker and understand the approval chain?", "weight": 1.0},
    {"key": "need", "label": "Need Assessment", "description": "Did the rep uncover a genuine, compelling business need that maps to their solution?", "weight": 1.2},
    {"key": "timeline", "label": "Timeline Establishment", "description": "Did the rep determine the prospect's urgency and expected implementation timeline?", "weight": 1.0}
  ]
}
```

### Step 2: Create `tools/methodology.py`

```python
"""Load and manage sales methodology definitions."""
import os
import json

METHODOLOGIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "playbooks", "methodologies"
)

# Built-in fallback dimensions (used when no specific methodology is selected)
DEFAULT_DIMENSIONS = {
    "discovery": [
        {"key": "opening", "label": "Opening", "description": "Personalization, rapport, agenda setting", "weight": 1.0},
        {"key": "needs_assessment", "label": "Needs Assessment", "description": "Question quality, pain point discovery", "weight": 1.0},
        {"key": "active_listening", "label": "Active Listening", "description": "Follow-ups, acknowledgment, building on answers", "weight": 1.0},
        {"key": "objection_handling", "label": "Objection Handling", "description": "Exploration, reframing, evidence use", "weight": 1.0},
        {"key": "next_steps", "label": "Next Steps", "description": "Commitment getting, specificity, follow-up plan", "weight": 1.0},
    ],
    "negotiation": [
        {"key": "value_establishment", "label": "Value Establishment", "description": "Anchoring on value before discussing price", "weight": 1.0},
        {"key": "negotiation_discipline", "label": "Negotiation Discipline", "description": "Holding firm, knowing walk-away points", "weight": 1.0},
        {"key": "creative_structuring", "label": "Creative Structuring", "description": "Multi-year, phased, bundled deal structures", "weight": 1.0},
        {"key": "composure", "label": "Composure", "description": "Staying calm under pressure and silence", "weight": 1.0},
        {"key": "closing_strength", "label": "Closing Strength", "description": "Trial closes, urgency creation, commitment", "weight": 1.0},
    ],
}


def load_methodology(key):
    """Load a methodology definition. Returns dict with name, description, dimensions."""
    # Try loading from JSON file
    filepath = os.path.join(METHODOLOGIES_DIR, f"{key}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)

    # Fall back to built-in defaults
    if key in DEFAULT_DIMENSIONS:
        return {
            "name": key.title(),
            "description": f"Default {key} scoring rubric",
            "dimensions": DEFAULT_DIMENSIONS[key],
        }

    # Ultimate fallback: discovery
    return load_methodology("discovery")


def list_methodologies():
    """List all available methodology names."""
    methods = list(DEFAULT_DIMENSIONS.keys())
    if os.path.exists(METHODOLOGIES_DIR):
        for f in os.listdir(METHODOLOGIES_DIR):
            if f.endswith(".json"):
                name = f[:-5]
                if name not in methods:
                    methods.append(name)
    return methods


def build_scoring_prompt(methodology_key):
    """Build the scoring instruction for the LLM debrief prompt."""
    methodology = load_methodology(methodology_key)
    dimensions_text = "\n".join(
        f"- {d['label']} (1-10): {d['description']}"
        for d in methodology["dimensions"]
    )
    dimension_keys = ", ".join(f'"{d["key"]}"' for d in methodology["dimensions"])

    return f"""Score this roleplay using the **{methodology['name']}** methodology.

Evaluate each dimension on a 1-10 scale:
{dimensions_text}

In your JSON output, use these exact dimension keys: {dimension_keys}
Provide an overall weighted score and cite specific conversation moments for each dimension."""
```

### Step 3: Inject Methodology into Debrief Prompt

In `prompts/coach_prompts.py`, modify the debrief prompt to accept dynamic methodology:

```python
from tools.methodology import build_scoring_prompt

def get_debrief_prompt(methodology_key="discovery"):
    """Build the full debrief system prompt with methodology-specific scoring."""
    scoring_section = build_scoring_prompt(methodology_key)

    return f"""You are a sales coaching AI providing a roleplay debrief.

{scoring_section}

After the narrative debrief, output a ```json block with the structured scores as specified above.
"""
```

### Step 4: Pass Methodology from User Settings into Coach Graph

In `app.py`, when starting a roleplay or generating a debrief, read the user's methodology setting:

```python
from db import get_user_settings

# In roleplay debrief handler:
settings = get_user_settings(user_id)
methodology = settings.get("methodology", "discovery")

# Pass to the debrief prompt builder
debrief_prompt = get_debrief_prompt(methodology_key=methodology)
```

### Step 5: Update `/settings` Modal with Methodology Picker

In the `/settings` handler, add a new section to the modal:

```python
# Add after the existing settings blocks:
{
    "type": "section",
    "text": {"type": "mrkdwn", "text": "*Scoring Methodology*\nWhich framework should SalesCoach use to evaluate your roleplays?"}
},
{
    "type": "actions",
    "block_id": "methodology_block",
    "elements": [{
        "type": "static_select",
        "action_id": "methodology",
        "initial_option": {
            "text": {"type": "plain_text", "text": _methodology_label(settings["methodology"])},
            "value": settings["methodology"],
        },
        "options": [
            {"text": {"type": "plain_text", "text": "Default (Generic)"}, "value": "discovery"},
            {"text": {"type": "plain_text", "text": "MEDDIC"}, "value": "meddic"},
            {"text": {"type": "plain_text", "text": "SPIN Selling"}, "value": "spin"},
            {"text": {"type": "plain_text", "text": "Challenger Sale"}, "value": "challenger"},
            {"text": {"type": "plain_text", "text": "BANT"}, "value": "bant"},
        ]
    }]
},
```

And in the submit handler, save the methodology:

```python
methodology = values["methodology_block"]["methodology"]["selected_option"]["value"]
update_user_settings(user_id, methodology=methodology)
```

---

## Feature #9: Performance Self-Service ("How's my month going?")

### Step 1: Add Performance Context Detection to `/ask`

In the `/ask` handler in `app.py`, before invoking the assistant graph:

```python
from db import get_training_stats, get_training_history

PERFORMANCE_KEYWORDS = [
    "my month", "my quarter", "my target", "my win rate", "how am i",
    "my score", "improving", "my pipeline", "how many", "my deals",
    "my performance", "my stats", "my progress", "am i getting better",
    "my coaching", "my training", "my roleplays", "my sessions",
]

@app.command("/ask")
def handle_ask(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    question = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/ask", question=question[:100])

    # Check for performance-related questions
    extra_context = ""
    if any(kw in question.lower() for kw in PERFORMANCE_KEYWORDS):
        stats = get_training_stats(user_id)
        recent = get_training_history(user_id, limit=5)

        if stats and stats.get("total_sessions", 0) > 0:
            extra_context = f"""

--- USER'S PERSONAL DATA ---
Training Stats:
- Total coaching sessions: {stats['total_sessions']}
- Average score: {stats['avg_score']:.1f}/10
- Best score: {stats['best_score']:.1f}/10
- Last session: {stats['last_session']}

Recent Sessions:
"""
            for s in recent:
                extra_context += f"- {s['scenario']} ({s['scenario_type']}) — Score: {s['overall_score']}/10 — {s['timestamp']}\n"

            extra_context += "--- END PERSONAL DATA ---"

    # Inject into the question or system prompt before sending to the graph
    enhanced_question = question
    if extra_context:
        enhanced_question = f"{question}\n{extra_context}"

    # ... invoke the assistant graph with enhanced_question ...
```

## DO NOT
- Do not hardcode dimension keys — always load from methodology JSON
- Do not change the default scoring behavior — users who haven't set a methodology get the existing generic rubric
- Do not expose raw SQL errors to users — wrap in friendly messages
- Do not inject full training transcripts into `/ask` context — only summary stats

## Testing
1. `/settings` → change methodology to MEDDIC → save → `/coach roleplay discovery` → complete → debrief should score on MEDDIC dimensions (Metrics, Economic Buyer, etc.)
2. Check: `sqlite3 data/salescoach.db "SELECT dimension, score FROM dimension_scores WHERE session_id = (SELECT id FROM training_sessions ORDER BY timestamp DESC LIMIT 1)"` → should show MEDDIC dimension keys
3. `/skill-gaps` → should show gap analysis based on historical sessions
4. `/ask How's my month going?` → should include personal training stats in the answer
5. `/ask What's my win rate?` → should reference pipeline data
