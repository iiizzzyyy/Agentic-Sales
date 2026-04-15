# Wave 1B — Training History & Structured Debrief Scoring

Feature #21: Store every coaching session and surface history via `/training-history`.

**Depends on:** Wave 1A (SQLite foundation — `db.py` must exist)

---

## Step 1: Update Debrief Prompt for Structured JSON Output

In `prompts/coach_prompts.py`, find the debrief system prompt (the one that generates the roleplay debrief). Append this instruction at the end of the prompt:

```
CRITICAL — After the narrative debrief above, you MUST output a structured JSON block on its own line, fenced with ```json and ```. This JSON is parsed programmatically. Format:

```json
{
  "overall_score": 7.2,
  "dimensions": {
    "opening": 8,
    "needs_assessment": 6,
    "active_listening": 7,
    "objection_handling": 8,
    "next_steps": 7
  },
  "strengths": ["Built rapport quickly with personalized opener", "Used strong evidence from case study"],
  "improvements": ["Ask deeper follow-up questions when prospect mentions pain", "Don't rush past budget objection"],
  "scenario_type": "discovery",
  "recommended_next": "negotiation_pricing_pushback"
}
```

Dimension keys depend on the scenario type:
- Discovery: opening, needs_assessment, active_listening, objection_handling, next_steps
- Negotiation: value_establishment, negotiation_discipline, creative_structuring, composure, closing_strength
- Competitive: competitive_positioning, buyer_understanding, evidence_proof, strategic_questioning
- Cold Call: pattern_interrupt, relevance, value_in_30s, objection_handling, next_step
- Objection: empathy, reframing, evidence_use, pivot_skill, confidence
```

## Step 2: Parse Structured Scores from Debrief

In `app.py`, create a helper function to extract the JSON block from the LLM's debrief response:

```python
import json
import re
from db import save_training_session

def parse_debrief_scores(debrief_text):
    """Extract structured JSON scores from the LLM debrief response.

    The LLM outputs a ```json block at the end of the debrief.
    Returns parsed dict or None if parsing fails.
    """
    # Find JSON block between ```json and ```
    pattern = r'```json\s*\n(.*?)\n\s*```'
    match = re.search(pattern, debrief_text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def strip_json_block(debrief_text):
    """Remove the JSON block from the debrief for display purposes."""
    pattern = r'\s*```json\s*\n.*?\n\s*```\s*'
    return re.sub(pattern, '', debrief_text, flags=re.DOTALL).strip()
```

## Step 3: Save Session After Debrief

Find the roleplay debrief handler in `app.py`. It's the section that runs when `turn_count >= max_turns` and generates the debrief. After the debrief is generated and formatted, add:

```python
# After generating the debrief response from the LLM:
debrief_text = response.content  # The full LLM response

# Parse structured scores
scores_data = parse_debrief_scores(debrief_text)
display_debrief = strip_json_block(debrief_text)

# Save to database
if scores_data:
    session_id = save_training_session(
        user_id=user_id,
        session_type="roleplay",
        overall_score=scores_data.get("overall_score"),
        dimensions=scores_data.get("dimensions", {}),
        scenario=roleplay_state.get("scenario", ""),
        scenario_id=roleplay_state.get("scenario_id"),  # None unless from saved scenario
        scenario_type=scores_data.get("scenario_type", "discovery"),
        strengths=scores_data.get("strengths", []),
        improvements=scores_data.get("improvements", []),
        turns=turn_count,
        methodology=scores_data.get("scenario_type", "discovery"),
        company=roleplay_state.get("company", ""),
        persona=roleplay_state.get("persona_name", ""),
        raw_debrief=display_debrief,
    )
else:
    # Fallback: save with just the overall score parsed from the markdown
    # Look for "Overall Score: X/10" pattern
    score_match = re.search(r'Overall Score:\s*(\d+\.?\d*)/10', debrief_text)
    overall = float(score_match.group(1)) if score_match else None
    session_id = save_training_session(
        user_id=user_id,
        session_type="roleplay",
        overall_score=overall,
        scenario=roleplay_state.get("scenario", ""),
        scenario_type="discovery",
        turns=turn_count,
        company=roleplay_state.get("company", ""),
        persona=roleplay_state.get("persona_name", ""),
        raw_debrief=debrief_text,
    )

# Use display_debrief (JSON stripped) for the formatter
# Pass to format_roleplay_debrief() as before
```

Do the same for:
- **Coach-live summary handler** — after generating the live coaching summary
- **Coach prep handler** — after generating the meeting prep (save as type="prep", no scores)
- **Coach feedback handler** — after generating the feedback (save type="feedback")

## Step 4: Create `/training-history` Command Handler

In `app.py`:

```python
from db import get_training_history, get_training_stats
from formatters.training_history import format_training_history

@app.command("/training-history")
def handle_training_history(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/training-history")

    # Check if querying another user (manager use case): /training-history @user
    target_user = user_id
    if text.startswith("<@") and text.endswith(">"):
        target_user = text[2:-1].split("|")[0]  # Extract user ID from <@U12345|name>

    # Get data
    sessions = get_training_history(target_user, limit=10)
    stats = get_training_stats(target_user)

    if not sessions:
        say(
            channel=channel_id,
            text=f"No training sessions found{' for <@' + target_user + '>' if target_user != user_id else ''}. Start practicing with `/coach roleplay [scenario]`."
        )
        return

    blocks, fallback = format_training_history(target_user, sessions, stats)
    say(channel=channel_id, text=fallback, blocks=blocks)
```

## Step 5: Create `formatters/training_history.py`

```python
"""Block Kit formatter for training history."""
from formatters.helpers import timestamp, format_currency


def format_training_history(user_id, sessions, stats):
    """Format training history as Block Kit blocks.

    Args:
        user_id: The user whose history this is
        sessions: List of recent session dicts from get_training_history()
        stats: Aggregate stats dict from get_training_stats()
    """
    import json

    total = stats.get("total_sessions", 0)
    avg_score = stats.get("avg_score")
    best_score = stats.get("best_score")

    # Header
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Training History: <@{user_id}>", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Sessions:* {total}"},
                {"type": "mrkdwn", "text": f"*Avg Score:* {avg_score:.1f}/10" if avg_score else "*Avg Score:* N/A"},
                {"type": "mrkdwn", "text": f"*Best Score:* {best_score:.1f}/10" if best_score else "*Best Score:* N/A"},
                {"type": "mrkdwn", "text": f"*Last Session:* {_format_relative_time(stats.get('last_session', ''))}"},
            ]
        },
        {"type": "divider"},
    ]

    # Session list
    prev_score = None
    for session in sessions:
        score = session.get("overall_score")
        scenario = session.get("scenario", "Unknown scenario")
        scenario_type = session.get("scenario_type", "")
        ts = session.get("timestamp", "")
        turns = session.get("turns", "?")
        company = session.get("company", "")

        # Trend arrow compared to next-older session
        if score and prev_score:
            if score > prev_score + 0.3:
                trend = "↑"
            elif score < prev_score - 0.3:
                trend = "↓"
            else:
                trend = "→"
        else:
            trend = ""

        # Score color
        if score and score >= 7:
            score_display = f"🟢 {score:.1f}/10 {trend}"
        elif score and score >= 5:
            score_display = f"🟡 {score:.1f}/10 {trend}"
        elif score:
            score_display = f"🔴 {score:.1f}/10 {trend}"
        else:
            score_display = "N/A"

        type_label = scenario_type.replace("_", " ").title() if scenario_type else "General"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{scenario}*\n{type_label} · {turns} turns · {_format_relative_time(ts)}\nScore: {score_display}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Practice Again", "emoji": True},
                "action_id": "practice_from_history",
                "value": json.dumps({
                    "scenario": scenario,
                    "scenario_type": scenario_type,
                    "scenario_id": session.get("scenario_id"),
                    "company": company,
                }),
            }
        })

        prev_score = score

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Skill Gaps", "emoji": True},
                "action_id": "view_skill_gaps",
                "value": user_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start New Practice", "emoji": True},
                "action_id": "start_new_practice",
                "style": "primary",
            },
        ]
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]
    })

    fallback = (
        f"Training History for <@{user_id}>. "
        f"{total} sessions, avg score {avg_score:.1f}/10." if avg_score else
        f"Training History for <@{user_id}>. {total} sessions."
    )

    return blocks, fallback


def _format_relative_time(iso_timestamp):
    """Convert ISO timestamp to relative time string."""
    if not iso_timestamp:
        return "Unknown"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        if diff.days > 7:
            return dt.strftime("%b %d")
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        else:
            return f"{diff.seconds // 60}m ago"
    except (ValueError, TypeError):
        return iso_timestamp[:10] if iso_timestamp else "Unknown"
```

## Step 6: Add `practice_from_history` Action Handler

```python
@app.action("practice_from_history")
def handle_practice_from_history(ack, body, client):
    ack()
    data = json.loads(body["actions"][0]["value"])
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    message_ts = body["message"]["ts"]

    scenario = data.get("scenario", "discovery call")
    scenario_id = data.get("scenario_id")
    company = data.get("company", "")

    # Collapse the history card
    collapse_message(client, channel, message_ts,
        "Training History",
        f"Starting practice: {scenario}")

    # Trigger roleplay with the same scenario
    # Reuse the existing roleplay start logic
    _start_roleplay(client, channel, message_ts, user_id, scenario, scenario_id, company)
```

## DO NOT
- Do not remove the existing markdown-based debrief formatting — the JSON block is appended AFTER the human-readable debrief
- Do not fail silently if JSON parsing fails — save the session with just the overall score as fallback
- Do not display the JSON block to the user — `strip_json_block()` removes it before passing to the formatter

## Testing
1. Run `/coach roleplay discovery` → complete 4 turns → debrief should display as before BUT also save to SQLite
2. Check: `sqlite3 data/salescoach.db "SELECT id, overall_score, scenario_type FROM training_sessions ORDER BY timestamp DESC LIMIT 5"`
3. Run `/training-history` → should show the session you just completed with score and trend
4. Run `/training-history @another_user` → should show that user's history (or "no sessions found")
5. Click "Practice Again" on a history item → should start a new roleplay with that scenario
