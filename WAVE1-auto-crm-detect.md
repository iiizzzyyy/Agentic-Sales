# Wave 1E — Auto-Detect CRM-Loggable Messages (Suggest & Confirm)

Feature #2 enhancement: Passively listen to sales channel messages, detect when a rep posts something that looks like a sales interaction update, and offer to log it to CRM with a one-click ephemeral confirmation.

**Depends on:** Wave 1A (SQLite + `db.py`), Wave 1C (`tools/crm_write.py`)

**Approach:** "Suggest and confirm" — the bot never auto-logs. It posts an ephemeral message (visible only to the author) with a pre-filled note and a "Log to CRM" button. The rep clicks to confirm or ignores it.

---

## Step 1: Create `tools/crm_detector.py`

This module decides whether a Slack message looks like a loggable sales interaction and extracts structured data from it.

```python
"""
Detect CRM-loggable content in Slack messages.
Two-stage approach:
  1. Fast keyword check (no LLM cost) — filters out 95% of messages
  2. LLM classification + extraction (only on keyword hits) — confirms and structures
"""
import re
import json
from typing import Optional

# ── Stage 1: Keyword pre-filter ──────────────────────────────────────────

# Company names get loaded once from CRM data (mock or live)
_company_names_cache: list[str] | None = None

def _load_company_names() -> list[str]:
    """Load known company names from CRM data for matching.
    Cache after first load."""
    global _company_names_cache
    if _company_names_cache is not None:
        return _company_names_cache

    try:
        # Try mock CRM first (same source as /research and /deal)
        import os, json as json_mod
        companies_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "mock_crm", "companies.json"
        )
        if os.path.exists(companies_path):
            with open(companies_path) as f:
                data = json_mod.load(f)
            # Extract company names — adjust key based on actual JSON structure
            if isinstance(data, list):
                _company_names_cache = [
                    c.get("name", c.get("properties", {}).get("name", ""))
                    for c in data if c.get("name") or c.get("properties", {}).get("name")
                ]
            else:
                _company_names_cache = []
        else:
            _company_names_cache = []
    except Exception:
        _company_names_cache = []

    return _company_names_cache


# Action keywords that suggest a sales interaction happened
ACTION_KEYWORDS = [
    # Meeting/call indicators
    r"\b(?:just|finished|had|completed|wrapped)\s+(?:a\s+)?(?:call|meeting|demo|chat|session|sync)\b",
    r"\b(?:got off|came out of|back from)\s+(?:a\s+)?(?:call|meeting|demo)\b",
    r"\b(?:spoke|talked|met|chatted)\s+with\b",
    # Outcome indicators
    r"\b(?:they(?:'re| are)|he(?:'s| is)|she(?:'s| is))\s+(?:interested|excited|on board|hesitant|concerned|pushing back)\b",
    r"\b(?:agreed to|asked for|requested|wants?|need)\s+(?:a\s+)?(?:pricing|proposal|demo|contract|pilot|trial|next steps|follow.?up)\b",
    r"\b(?:sent|sending|shared|forwarded)\s+(?:the\s+)?(?:proposal|pricing|contract|deck|brochure|case study)\b",
    # Deal progression
    r"\b(?:moved?|moving|advance[ds]?|progress(?:ed|ing)?)\s+(?:to\s+)?(?:next stage|negotiation|closing|contract)\b",
    r"\b(?:closed|won|lost|dead|stalled|on hold)\b",
    # Follow-up signals
    r"\b(?:need to|should|gotta|have to)\s+(?:follow up|send|schedule|book|set up)\b",
    r"\bnext step[s]?\b",
]

# Compile patterns for performance
_ACTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ACTION_KEYWORDS]


def passes_keyword_filter(text: str) -> tuple[bool, list[str]]:
    """Fast pre-filter: does this message contain action keywords AND a company reference?

    Args:
        text: Raw Slack message text

    Returns:
        (passes, matched_companies) — True if message looks loggable, plus any matched company names
    """
    if len(text) < 20 or len(text) > 2000:
        # Too short to be meaningful, or too long (probably a paste/document)
        return False, []

    # Check for action keywords
    has_action = any(p.search(text) for p in _ACTION_PATTERNS)
    if not has_action:
        return False, []

    # Check for company name mention
    companies = _load_company_names()
    matched = [c for c in companies if c.lower() in text.lower()]

    # Also check for @-mentions of contacts (pattern: name + title/company context)
    # If no company matched but action keywords hit, still pass — the LLM can figure it out
    if matched:
        return True, matched

    # Fallback: if strong action keywords but no company match,
    # still pass if the message has enough substance (3+ words after keyword)
    if has_action and len(text.split()) >= 8:
        return True, []

    return False, []


# ── Stage 2: LLM classification + extraction ─────────────────────────────

CRM_DETECT_SYSTEM_PROMPT = """You are a CRM logging assistant. Analyze the following Slack message from a sales rep and determine:

1. Is this message describing a sales interaction that should be logged to CRM? (true/false)
2. If yes, extract structured data for the CRM note.

Rules for classification:
- YES: Messages about calls, meetings, demos, follow-ups, deal updates, customer conversations, proposals sent, objections encountered, next steps agreed
- NO: Casual chat, questions to teammates, internal discussions not about a specific customer, jokes, lunch plans, general announcements
- BORDERLINE → lean toward NO (we don't want false positives annoying the rep)

If loggable, extract:
- company: The company name mentioned (or "Unknown" if unclear)
- summary: A clean 1-2 sentence CRM note summarizing the interaction
- deal_stage_hint: Any signal about deal progression (or null)
- next_steps: Any follow-up actions mentioned (or null)
- sentiment: positive / neutral / negative / mixed

Respond with ONLY a JSON object, no markdown fencing:
{"loggable": true/false, "confidence": 0.0-1.0, "company": "...", "summary": "...", "deal_stage_hint": "...", "next_steps": "...", "sentiment": "..."}

If not loggable, respond: {"loggable": false, "confidence": 0.0-1.0}"""


def build_classification_prompt(message_text: str, matched_companies: list[str]) -> str:
    """Build the user prompt for LLM classification.

    Args:
        message_text: The Slack message to classify
        matched_companies: Company names found by keyword filter

    Returns:
        Formatted user prompt string
    """
    company_hint = ""
    if matched_companies:
        company_hint = f"\n\nKnown CRM companies detected in message: {', '.join(matched_companies)}"

    return f"Slack message from sales rep:\n\"{message_text}\"{company_hint}"


def parse_classification_response(llm_response: str) -> Optional[dict]:
    """Parse the LLM classification response.

    Args:
        llm_response: Raw LLM response text

    Returns:
        Parsed dict with loggable, confidence, company, summary, etc. or None on parse failure
    """
    # Try direct JSON parse
    try:
        result = json.loads(llm_response.strip())
        if isinstance(result, dict) and "loggable" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown fencing
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the response
    obj_match = re.search(r'\{[^{}]*"loggable"[^{}]*\}', llm_response)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    return None
```

---

## Step 2: Create `formatters/crm_detect.py`

Build the ephemeral suggestion card that the rep sees.

```python
"""Block Kit formatter for the auto-detect CRM logging suggestion."""

import json


def format_crm_suggestion(
    original_text: str,
    extracted: dict,
    message_ts: str,
    channel_id: str
) -> tuple[list[dict], str]:
    """Format the ephemeral suggestion card.

    Args:
        original_text: The original Slack message (truncated for display)
        extracted: Dict from LLM classification with company, summary, next_steps, sentiment
        message_ts: Timestamp of the original message (for threading)
        channel_id: Channel where the message was posted

    Returns:
        (blocks, fallback_text) tuple
    """
    company = extracted.get("company", "Unknown")
    summary = extracted.get("summary", original_text[:200])
    next_steps = extracted.get("next_steps")
    sentiment = extracted.get("sentiment", "neutral")

    # Sentiment emoji
    sentiment_emoji = {
        "positive": "🟢",
        "neutral": "🟡",
        "negative": "🔴",
        "mixed": "🔵"
    }.get(sentiment, "🟡")

    # Build the note preview
    note_preview = f"*{company}*\n{summary}"
    if next_steps:
        note_preview += f"\n\n📋 Next steps: {next_steps}"

    # Action payload — everything needed to log without re-processing
    log_payload = json.dumps({
        "company": company,
        "summary": summary,
        "next_steps": next_steps,
        "sentiment": sentiment,
        "source_channel": channel_id,
        "source_ts": message_ts,
    })

    blocks = [
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"💡 Looks like a loggable interaction — want to save it to CRM?"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{sentiment_emoji} {note_preview}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Log to CRM"},
                    "style": "primary",
                    "action_id": "auto_crm_confirm",
                    "value": log_payload
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit & Log"},
                    "action_id": "auto_crm_edit",
                    "value": log_payload
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss"},
                    "action_id": "auto_crm_dismiss",
                    "value": "dismiss"
                }
            ]
        }
    ]

    return blocks, f"💡 Log to CRM? {company}: {summary[:100]}"
```

---

## Step 3: Add the Slack Message Listener in `app.py`

This is the core listener. It fires on every message in configured sales channels, runs the fast keyword filter, and only calls the LLM when the filter passes.

### 3A. Configuration — which channels to monitor

```python
import os

# Channels where auto-CRM-detect is active
# Set via env var as comma-separated channel IDs, or empty to disable
AUTO_CRM_CHANNELS = set(
    os.environ.get("AUTO_CRM_CHANNELS", "").split(",")
) - {""}

# Minimum LLM confidence score to show the suggestion (0.0-1.0)
AUTO_CRM_CONFIDENCE_THRESHOLD = 0.7

# Cooldown: don't suggest to the same user more than once every N seconds
# Prevents annoying rapid-fire suggestions if someone posts multiple updates
AUTO_CRM_COOLDOWN_SECONDS = 60
_auto_crm_cooldown: dict[str, float] = {}  # user_id -> last_suggestion_timestamp
```

### 3B. The message event listener

```python
@app.event("message")
async def handle_message_for_crm_detect(event, client, say):
    """Listen for messages in sales channels and suggest CRM logging.

    This handler should be registered AFTER the roleplay message handler
    so it doesn't interfere with active roleplay threads.
    """
    import time as time_mod
    from tools.crm_detector import (
        passes_keyword_filter,
        build_classification_prompt,
        parse_classification_response,
        CRM_DETECT_SYSTEM_PROMPT
    )
    from formatters.crm_detect import format_crm_suggestion

    # ── Guard clauses (fast exit for irrelevant messages) ────────────

    # Skip if auto-detect is disabled (no channels configured)
    if not AUTO_CRM_CHANNELS:
        return

    # Skip if not in a monitored channel
    channel_id = event.get("channel", "")
    if channel_id not in AUTO_CRM_CHANNELS:
        return

    # Skip bot messages, edits, thread replies, and subtypes (joins, leaves, etc.)
    if event.get("bot_id") or event.get("subtype") or event.get("thread_ts"):
        return

    user_id = event.get("user", "")
    text = event.get("text", "")
    message_ts = event.get("ts", "")

    if not user_id or not text:
        return

    # Skip if user is in cooldown
    now = time_mod.time()
    last_suggestion = _auto_crm_cooldown.get(user_id, 0)
    if now - last_suggestion < AUTO_CRM_COOLDOWN_SECONDS:
        return

    # ── Stage 1: Fast keyword filter ─────────────────────────────────
    passes, matched_companies = passes_keyword_filter(text)
    if not passes:
        return

    # ── Stage 2: LLM classification ──────────────────────────────────
    try:
        user_prompt = build_classification_prompt(text, matched_companies)

        # Use the same LLM call pattern as the rest of the codebase
        # This should be a lightweight/fast call — consider using a smaller model
        # or setting max_tokens low (200 is plenty for the JSON response)
        llm_response = await call_llm(
            system_prompt=CRM_DETECT_SYSTEM_PROMPT,
            user_message=user_prompt,
            user_id=user_id,
            max_tokens=200  # JSON response is small
        )

        result = parse_classification_response(llm_response)
        if not result:
            return

        if not result.get("loggable", False):
            return

        if result.get("confidence", 0) < AUTO_CRM_CONFIDENCE_THRESHOLD:
            return

    except Exception:
        # LLM call failed — silently skip, don't disrupt the channel
        return

    # ── Stage 3: Post ephemeral suggestion ───────────────────────────
    try:
        blocks, fallback = format_crm_suggestion(
            original_text=text,
            extracted=result,
            message_ts=message_ts,
            channel_id=channel_id
        )

        # Ephemeral = only visible to the message author
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text=fallback
        )

        # Log the suggestion event (not the actual log — that happens on confirm)
        log_engagement(user_id, "auto_crm", "suggestion_shown", {
            "company": result.get("company", ""),
            "confidence": result.get("confidence", 0),
            "channel": channel_id
        })

        # Set cooldown
        _auto_crm_cooldown[user_id] = now

    except Exception:
        # Ephemeral post failed — silently skip
        pass
```

### 3C. Important: Ordering with existing message handlers

The `@app.event("message")` handler for auto-CRM-detect must NOT interfere with roleplay message handling. Slack Bolt dispatches to all matching listeners, so the guard clauses above (skip thread replies, skip bot messages) ensure coexistence. However, be aware:

- **Roleplay messages** happen in threads (`thread_ts` is set) — auto-CRM-detect skips threads.
- **Channel messages** are what auto-CRM-detect monitors — roleplay doesn't happen at the channel level.
- If there's an existing `@app.event("message")` catch-all, you may need to merge the logic or add this as a separate listener function. Bolt allows multiple listeners for the same event.

---

## Step 4: Add Action Handlers for the Suggestion Card

### 4A. Confirm — log to CRM immediately

```python
@app.action("auto_crm_confirm")
async def handle_auto_crm_confirm(ack, body, client):
    """User clicked 'Log to CRM' on the auto-detect suggestion."""
    await ack()
    user_id = body["user"]["id"]
    payload = json.loads(body["actions"][0]["value"])

    from tools.crm_write import create_note

    company = payload["company"]
    summary = payload["summary"]
    next_steps = payload.get("next_steps", "")

    # Build the CRM note body
    note_body = summary
    if next_steps:
        note_body += f"\n\nNext steps: {next_steps}"

    # Write to CRM (or mock)
    try:
        result = await create_note(
            note_body=note_body,
            company_name=company,
            user_id=user_id
        )

        # Replace the ephemeral message with confirmation
        # (Ephemeral messages can't be updated, so post a new one)
        await client.chat_postEphemeral(
            channel=payload["source_channel"],
            user=user_id,
            text=f"✅ Logged to CRM: *{company}* — {summary[:80]}..."
        )

        log_engagement(user_id, "auto_crm", "confirmed", {
            "company": company,
            "source": "auto_detect"
        })

    except Exception as e:
        await client.chat_postEphemeral(
            channel=payload["source_channel"],
            user=user_id,
            text=f"❌ Failed to log: {str(e)[:100]}. Try `/log {company} {summary[:50]}` manually."
        )
```

### 4B. Edit & Log — open a modal to refine the note before logging

```python
@app.action("auto_crm_edit")
async def handle_auto_crm_edit(ack, body, client):
    """User clicked 'Edit & Log' — open modal with pre-filled note."""
    await ack()
    payload = json.loads(body["actions"][0]["value"])

    modal = {
        "type": "modal",
        "callback_id": "auto_crm_edit_submit",
        "title": {"type": "plain_text", "text": "Edit CRM Note"},
        "submit": {"type": "plain_text", "text": "Log to CRM"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": json.dumps({
            "company": payload["company"],
            "source_channel": payload["source_channel"],
            "source_ts": payload["source_ts"]
        }),
        "blocks": [
            {
                "type": "input",
                "block_id": "company_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "company_input",
                    "initial_value": payload.get("company", ""),
                    "placeholder": {"type": "plain_text", "text": "Company name"}
                },
                "label": {"type": "plain_text", "text": "Company"}
            },
            {
                "type": "input",
                "block_id": "note_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "note_input",
                    "multiline": True,
                    "initial_value": payload.get("summary", ""),
                    "placeholder": {"type": "plain_text", "text": "CRM note content"}
                },
                "label": {"type": "plain_text", "text": "Note"}
            },
            {
                "type": "input",
                "block_id": "next_steps_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "next_steps_input",
                    "initial_value": payload.get("next_steps", "") or "",
                    "placeholder": {"type": "plain_text", "text": "Follow-up actions"}
                },
                "label": {"type": "plain_text", "text": "Next Steps"}
            }
        ]
    }

    await client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.view("auto_crm_edit_submit")
async def handle_auto_crm_edit_submit(ack, body, view, client):
    """Process the edited CRM note submission."""
    await ack()
    user_id = body["user"]["id"]
    metadata = json.loads(view["private_metadata"])

    company = view["state"]["values"]["company_block"]["company_input"]["value"]
    note = view["state"]["values"]["note_block"]["note_input"]["value"]
    next_steps = view["state"]["values"]["next_steps_block"]["next_steps_input"]["value"]

    from tools.crm_write import create_note

    note_body = note
    if next_steps:
        note_body += f"\n\nNext steps: {next_steps}"

    try:
        await create_note(
            note_body=note_body,
            company_name=company,
            user_id=user_id
        )

        # Confirm via DM (modal closes automatically)
        dm = await client.conversations_open(users=[user_id])
        await client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f"✅ Logged to CRM: *{company}* — {note[:80]}..."
        )

        log_engagement(user_id, "auto_crm", "edited_and_confirmed", {"company": company})

    except Exception as e:
        dm = await client.conversations_open(users=[user_id])
        await client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f"❌ Failed to log: {str(e)[:100]}"
        )
```

### 4C. Dismiss — just acknowledge

```python
@app.action("auto_crm_dismiss")
async def handle_auto_crm_dismiss(ack, body):
    """User dismissed the suggestion. Log it for tuning."""
    await ack()
    user_id = body["user"]["id"]

    log_engagement(user_id, "auto_crm", "dismissed", {})
    # Ephemeral messages disappear on their own eventually
    # No further action needed
```

---

## Step 5: Environment Configuration

Add these to `.env` (or document for the operator):

```bash
# Auto CRM Detection — comma-separated Slack channel IDs to monitor
# Leave empty to disable auto-detect entirely
# Find channel IDs: right-click channel name in Slack → "Copy link" → ID is the last segment
AUTO_CRM_CHANNELS=C06XXXXXXXX,C06YYYYYYYY

# Confidence threshold (0.0-1.0) — higher = fewer but more accurate suggestions
# Default 0.7 is a good starting point. Raise to 0.85 if reps find it too noisy.
AUTO_CRM_CONFIDENCE_THRESHOLD=0.7

# Cooldown in seconds between suggestions to the same user
# Default 60 prevents rapid-fire suggestions
AUTO_CRM_COOLDOWN_SECONDS=60
```

---

## Step 6: Demo Setup

For the demo, configure `AUTO_CRM_CHANNELS` with the demo channel ID. Then:

1. Post a message like: "Just got off a great discovery call with NovaTech. Sarah Chen is interested in the enterprise tier but wants to see a case study first. Need to send that over by Friday."
2. The bot shows an ephemeral suggestion card with extracted company (NovaTech), summary, next steps, and sentiment.
3. Click "Log to CRM" to show instant logging, OR click "Edit & Log" to show the refinement modal.
4. Show that casual messages like "anyone want coffee?" or "standup in 5 min" are correctly ignored.

**Demo talking point:** "The bot passively monitors your sales channels and detects when you mention a customer interaction. Instead of forcing you to switch context and manually update CRM, it offers a one-click log. This is how we close the gap with Pam's automatic CRM capture — but with human confirmation so nothing gets logged by mistake."

---

## Tuning Notes

**If too many false positives (annoying):**
- Raise `AUTO_CRM_CONFIDENCE_THRESHOLD` to 0.85 or 0.9
- Remove weaker keyword patterns from `ACTION_KEYWORDS`
- Add a "Don't suggest for this type of message" feedback button

**If too few detections (missing real updates):**
- Lower threshold to 0.6
- Add more keyword patterns
- Expand `_load_company_names()` to include deal names and contact names

**Tracking suggestion quality:**
The engagement events (`auto_crm/suggestion_shown`, `auto_crm/confirmed`, `auto_crm/dismissed`) let you calculate the confirmation rate. A healthy rate is 30-50% confirms. Below 20% means too noisy; above 60% means the threshold might be too high (missing some).

---

## Implementation Checklist

| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Create `tools/crm_detector.py` | `tools/crm_detector.py` | ⬜ |
| 2 | Create `formatters/crm_detect.py` | `formatters/crm_detect.py` | ⬜ |
| 3 | Add message listener + config | `app.py` | ⬜ |
| 4 | Add confirm/edit/dismiss handlers | `app.py` | ⬜ |
| 5 | Add env vars to `.env.example` | `.env.example` | ⬜ |
| 6 | Test with demo messages | manual | ⬜ |

## Testing

- **True positive:** Post "Just finished a call with NovaTech, they want pricing by EOW" → should get suggestion with company=NovaTech
- **True negative:** Post "Anyone free for lunch?" → no suggestion
- **True negative:** Post "Looking at the Q1 forecast numbers" → no suggestion (internal, no customer interaction)
- **Borderline:** Post "NovaTech meeting went well" → may or may not trigger depending on threshold. Short messages with company name but no detail should lean toward no-suggestion at threshold 0.7.
- **Cooldown:** Post two loggable messages 30 seconds apart → second one should be silently skipped
- **Edit flow:** Click "Edit & Log" → modal opens pre-filled → change company name → submit → logs with edited values
