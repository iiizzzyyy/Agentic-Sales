# Claude Code Instructions: `/coach-live` — Real-Time Call Coaching

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `graphs/coach.py`, `tools/rag.py`, and `data/playbooks/sales_methodology.md` first.**

---

## CONTEXT — WHAT AND WHY

Unlike `/objection` (single response) or `/coach roleplay` (practice session), `/coach-live` is a continuous coaching mode where a rep pastes snippets from an ongoing call and gets instant micro-feedback. Think of it as an AI whispering in the rep's ear during a live call.

This is the "AI copilot in real-time" demo moment. The rep is on a call, and the AI is coaching them turn by turn.

---

## WHAT IT DOES

1. Rep types `/coach-live NovaTech discovery` to start a live coaching session
2. Bot starts a thread with instructions: "I'm watching. Paste what the buyer says and I'll coach you."
3. Rep pastes snippets like: "They said: we're happy with our current solution"
4. Bot responds IN THE THREAD with instant micro-coaching: what to say next, what technique to use, what to avoid
5. Rep types `done` to end the session and get a summary

---

## STEP 1: Create `formatters/coach_live.py`

```python
"""Block Kit formatting for /coach-live command."""
from formatters.helpers import timestamp, truncate


def format_coach_live_start(
    company_name: str,
    call_type: str,
) -> tuple[list, str]:
    """Format the start of a live coaching session.

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎧 Live Coaching Active", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Company:* {company_name}\n"
                    f"*Call Type:* {call_type}\n\n"
                    "I'm listening. Reply in this thread with what the buyer says and I'll coach you in real-time."
                )
            }
        },

        {"type": "divider"},

        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How to use:*\n"
                    "• Paste what the buyer said → I'll suggest your response\n"
                    "• Type `they asked about pricing` → I'll prep your answer\n"
                    "• Type `they objected: [objection]` → instant rebuttal\n"
                    "• Type `done` → session summary with score"
                )
            }
        },

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "End Session", "emoji": True},
                    "action_id": "end_live_coaching",
                    "style": "danger",
                    "value": "end",
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Live Coaching • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Live Coaching Active — {company_name} ({call_type})"
    return blocks, fallback


def format_coach_live_tip(
    tip_type: str,
    suggestion: str,
    technique: str,
    avoid: str,
) -> tuple[list, str]:
    """Format a single coaching tip in the thread.

    Args:
        tip_type: "positive", "redirect", "warning", "technique"
        suggestion: What to say or do next
        technique: The sales technique being applied
        avoid: What NOT to do

    Returns:
        tuple: (blocks, fallback_text)
    """
    type_emoji = {
        "positive": "✅",
        "redirect": "🔄",
        "warning": "⚠️",
        "technique": "💡",
    }
    emoji = type_emoji.get(tip_type, "💡")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{suggestion}*"
            }
        },
    ]

    fields = []
    if technique:
        fields.append({"type": "mrkdwn", "text": f"*Technique:* {technique}"})
    if avoid:
        fields.append({"type": "mrkdwn", "text": f"*Avoid:* ❌ {avoid}"})

    if fields:
        blocks.append({
            "type": "section",
            "fields": fields,
        })

    fallback = f"{emoji} {suggestion}"
    return blocks, fallback


def format_coach_live_summary(
    company_name: str,
    call_type: str,
    turns: int,
    highlights: list,
    improvements: list,
    score: int,
) -> tuple[list, str]:
    """Format the end-of-session summary.

    Args:
        company_name: Company name
        call_type: Type of call
        turns: Number of coaching exchanges
        highlights: List of things done well
        improvements: List of areas to improve
        score: Overall score 1-10

    Returns:
        tuple: (blocks, fallback_text)
    """
    score_emoji = "🟢" if score >= 7 else "🟡" if score >= 5 else "🔴"

    highlights_text = "\n".join([f"• ✅ {h}" for h in highlights[:4]]) if highlights else "• No specific highlights"
    improvements_text = "\n".join([f"• 📈 {i}" for i in improvements[:4]]) if improvements else "• No specific improvements"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🎧 Live Coaching Summary", "emoji": True}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Call Type:*\n{call_type}"},
                {"type": "mrkdwn", "text": f"*Coaching Turns:*\n{turns}"},
                {"type": "mrkdwn", "text": f"*Score:*\n{score_emoji} {score}/10"},
            ]
        },

        {"type": "divider"},

        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*What Went Well:*\n{highlights_text}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Areas to Improve:*\n{improvements_text}"}
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"SalesCoach AI • Session Complete • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Live Coaching Summary — {company_name} — Score: {score}/10"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.coach_live import format_coach_live_start, format_coach_live_tip, format_coach_live_summary
```

And add all three to `__all__`.

---

## STEP 3: Add `/coach-live` Handler and Thread Listener to `app.py`

**Key design:** Uses a thread for the coaching session. Store session state in `active_live_coaching` dict (same pattern as `active_roleplays`).

```python
# In-memory live coaching state
active_live_coaching = {}


@app.command("/coach-live")
def handle_coach_live(ack, say, command):
    """Start a real-time live call coaching session."""
    ack()
    text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not text:
        say(
            "Start live coaching: `/coach-live [company] [call type]`\n"
            "Examples:\n• `/coach-live NovaTech discovery`\n"
            "• `/coach-live Apex negotiation`\n"
            "• `/coach-live Horizon pricing discussion`",
            channel=channel_id,
        )
        return

    # Parse company and call type
    parts = text.split(maxsplit=1)
    company_name = parts[0]
    call_type = parts[1] if len(parts) > 1 else "general"

    # Load company context for coaching
    company = mock_crm.search_company(company_name)
    company_full_name = company.get("properties", {}).get("name", company_name) if company else company_name

    from tools.rag import search_playbooks
    methodology_context = search_playbooks(f"{call_type} call methodology techniques", n_results=5)

    # Post the start message and capture thread_ts
    from formatters import format_coach_live_start
    blocks, fallback = format_coach_live_start(company_full_name, call_type.title())

    result = say(text=fallback, blocks=blocks, channel=channel_id)
    thread_ts = result["ts"]

    # Store session state
    active_live_coaching[thread_ts] = {
        "company": company_full_name,
        "call_type": call_type,
        "user_id": user_id,
        "channel_id": channel_id,
        "turns": 0,
        "history": [],
        "methodology_context": methodology_context,
    }
```

---

## STEP 4: Handle Thread Replies for Live Coaching

**Important:** You need to update the existing `@app.event("message")` handler to detect live coaching threads. Add this check BEFORE the existing roleplay thread check:

```python
# Inside the message event handler, add this block:

# Check if this is a live coaching thread
thread_ts = event.get("thread_ts")
if thread_ts and thread_ts in active_live_coaching:
    session = active_live_coaching[thread_ts]
    user_message = event.get("text", "").strip()
    channel = event.get("channel")

    # Check for end command
    if user_message.lower() in ("done", "end", "stop"):
        # Generate summary
        history_text = "\n".join([f"Turn {i+1}: Buyer said: {h['buyer']} → Coach suggested: {h['suggestion'][:80]}"
                                   for i, h in enumerate(session["history"])])

        summary_result = app_graph.invoke({
            "messages": [HumanMessage(content=f"""Summarize this live coaching session.

COMPANY: {session['company']}
CALL TYPE: {session['call_type']}
COACHING TURNS: {session['turns']}

SESSION HISTORY:
{history_text}

Generate EXACTLY this format:
SCORE: [1-10 based on coachability and response quality]
HIGHLIGHT_1: [Something the rep did well or responded well to]
HIGHLIGHT_2: [Another highlight]
IMPROVEMENT_1: [Area to improve]
IMPROVEMENT_2: [Another area to improve]""")],
            "route": "coach",
            "workflow": "coach",
            "user_id": session["user_id"],
            "channel_id": channel,
            "thread_ts": thread_ts,
        })

        # Parse summary
        summary_text = summary_result["messages"][-1].content
        score = 7
        highlights = []
        improvements = []

        for line in summary_text.split("\n"):
            line = line.strip()
            if line.upper().startswith("SCORE:"):
                try:
                    score = int("".join(filter(str.isdigit, line.split(":", 1)[1][:3])))
                except (ValueError, IndexError):
                    score = 7
            elif line.upper().startswith("HIGHLIGHT_"):
                highlights.append(line.split(":", 1)[1].strip() if ":" in line else line)
            elif line.upper().startswith("IMPROVEMENT_"):
                improvements.append(line.split(":", 1)[1].strip() if ":" in line else line)

        from formatters import format_coach_live_summary
        blocks, fallback = format_coach_live_summary(
            company_name=session["company"],
            call_type=session["call_type"],
            turns=session["turns"],
            highlights=highlights,
            improvements=improvements,
            score=score,
        )

        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=fallback,
            blocks=blocks,
        )

        # Clean up
        del active_live_coaching[thread_ts]
        return

    # Regular coaching turn
    session["turns"] += 1

    coaching_result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""You are a real-time sales coach. A rep is on a live {session['call_type']} call with {session['company']}.

The buyer just said: "{user_message}"

SALES METHODOLOGY CONTEXT:
{session['methodology_context']}

PREVIOUS COACHING (last 3):
{chr(10).join([f"  Buyer: {h['buyer'][:60]} → You coached: {h['suggestion'][:60]}" for h in session['history'][-3:]]) or "  First turn"}

Respond in EXACTLY this format:
TIP_TYPE: [positive|redirect|warning|technique]
SUGGESTION: [What the rep should say or do RIGHT NOW — be specific and concise, max 2 sentences]
TECHNIQUE: [Name of the sales technique being applied, e.g., "SPIN Implication Question", "Feel-Felt-Found"]
AVOID: [One thing NOT to do in this moment]

Be concise — the rep is on a live call and needs to respond in seconds.""")],
        "route": "coach",
        "workflow": "coach",
        "user_id": session["user_id"],
        "channel_id": channel,
        "thread_ts": thread_ts,
    })

    coaching_text = coaching_result["messages"][-1].content

    # Parse
    tip_type = "technique"
    suggestion = ""
    technique = ""
    avoid = ""

    for line in coaching_text.split("\n"):
        line = line.strip()
        if line.upper().startswith("TIP_TYPE:"):
            tip_type = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("SUGGESTION:"):
            suggestion = line.split(":", 1)[1].strip()
        elif line.upper().startswith("TECHNIQUE:"):
            technique = line.split(":", 1)[1].strip()
        elif line.upper().startswith("AVOID:"):
            avoid = line.split(":", 1)[1].strip()

    if not suggestion:
        suggestion = coaching_text[:200]

    # Store in history
    session["history"].append({
        "buyer": user_message,
        "suggestion": suggestion,
    })

    from formatters import format_coach_live_tip
    blocks, fallback = format_coach_live_tip(tip_type, suggestion, technique, avoid)

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=fallback,
        blocks=blocks,
    )
    return  # Don't fall through to other message handlers
```

---

## STEP 5: Add Action Handler

```python
@app.action("end_live_coaching")
def handle_end_live_coaching(ack, body, client):
    """End a live coaching session via button."""
    ack()
    channel = body["channel"]["id"]
    # Find the session by checking message_ts
    message_ts = body.get("message", {}).get("ts")
    if message_ts and message_ts in active_live_coaching:
        user_id = body["user"]["id"]
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text="Type `done` in this thread to get your session summary.",
        )
```

---

## REGISTER IN SLACK

Add `/coach-live` slash command in api.slack.com:
- **Command:** `/coach-live`
- **Description:** `Start real-time coaching during a live call`
- **Usage Hint:** `[company] [call type]`

---

## GOTCHAS

1. **Thread detection order matters** — check `active_live_coaching` BEFORE `active_roleplays` in the message event handler, since both use thread-based interaction.

2. **Latency is critical** — use a concise prompt. Consider using a faster model (Haiku) for live coaching if the response time is too slow.

3. **Thread messages don't trigger slash commands** — the coaching interaction happens through the `message` event handler detecting replies in the coaching thread.

4. **Memory management** — sessions should be cleaned up after the "done" command. Consider adding a timeout (e.g., 1 hour) to auto-cleanup abandoned sessions.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/coach_live.py` | New formatter with 3 functions: start, tip, summary |
| EDIT | `formatters/__init__.py` | Add 3 new exports |
| EDIT | `app.py` | Add `active_live_coaching` dict, `handle_coach_live()`, thread detection in message handler, `handle_end_live_coaching()` |
