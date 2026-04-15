# Wave 1D — Engagement Analytics Telemetry

Feature #22: Track every bot interaction per user. Feeds team dashboard (Wave 3) and skill gap detection (Wave 2).

**Depends on:** Wave 1A (SQLite foundation — `log_engagement()` function in `db.py`)

---

## Step 1: Add `log_engagement()` to Every Command Handler

This is a mechanical change. At the TOP of every `@app.command` handler in `app.py`, add a `log_engagement` call. The function is fire-and-forget (errors are swallowed), so it's safe to add everywhere.

### Pattern

```python
@app.command("/research")
def handle_research(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip()

    # ADD THIS LINE:
    log_engagement(user_id, "command", command="/research", company=text)

    # ... rest of handler ...
```

### Every Command to Instrument

Add `log_engagement(user_id, "command", command="/COMMAND_NAME")` to:

| Command | Extra metadata to log |
|---------|----------------------|
| `/research` | `company=text` |
| `/deal` | `search_term=text` |
| `/coach` | `subcommand=subcommand, scenario=scenario_text` |
| `/coach-live` | `company=company, call_type=call_type` |
| `/draft-email` | `company=text` |
| `/pipeline` | (none) |
| `/objection` | `objection=text` |
| `/ask` | `question=text[:100]` |
| `/competitor` | `competitor=text` |
| `/battlecard` | (none) |
| `/alerts` | (none) |
| `/forecast` | (none) |
| `/win-loss` | `filter=text` |
| `/persona` | `target=text` |
| `/handoff` | `deal=text` |
| `/email-sequence` | `company=text` |
| `/followup` | (none) |
| `/scorecard` | `target_user=text` |
| `/settings` | (none) |
| `/demo-flow` | (none) |
| `/analyze-transcript` | (none) |
| `/training-history` | `target_user=target_user` |
| `/log` | `deal=deal_name` |

## Step 2: Add `log_engagement()` to Key Action Handlers

For action handlers, log with `event_type="action"`:

```python
@app.action("draft_email_from_research")
def handle_draft_email_from_research(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    company = body["actions"][0]["value"]

    # ADD THIS LINE:
    log_engagement(user_id, "action", action_id="draft_email_from_research", company=company)

    # ... rest of handler ...
```

### Priority Action Handlers to Instrument

Focus on actions that indicate meaningful engagement (skip noop/navigation):

| Action ID | Extra metadata |
|-----------|---------------|
| `draft_email_from_research` | `company=value` |
| `start_roleplay_from_research` | `company=value` |
| `draft_email_from_deal` | `deal=value` |
| `research_from_deal` | `company=value` |
| `create_gmail_draft` | `company=company_name` |
| `practice_again` | `scenario=scenario` |
| `try_suggested` | `scenario=scenario` |
| `practice_objection` | `objection=value` |
| `drill_flagged_deal` | `deal=value` |
| `log_note` | `deal=deal_name` |
| `log_coaching_to_crm` | (none) |
| `expand_research` | `company=value` |
| `view_deal_detail` | `deal=value` |

## Step 3: Log Roleplay Turns

In the roleplay message handler (the one that processes user replies during active roleplay), add:

```python
log_engagement(user_id, "roleplay_turn", scenario_type=roleplay_state.get("scenario_type"), turn=turn_count)
```

And after debrief generation:

```python
log_engagement(user_id, "debrief", scenario_type=scenario_type, score=overall_score)
```

## Step 4: Efficient Bulk Instrumentation Helper (Optional)

If you want to avoid repeating the same line in 40+ handlers, create a decorator:

```python
def track_command(command_name):
    """Decorator to auto-log engagement for command handlers."""
    def decorator(func):
        def wrapper(ack, command, client, say=None, **kwargs):
            ack()
            user_id = command["user_id"]
            text = command.get("text", "").strip()
            log_engagement(user_id, "command", command=command_name, input_text=text[:100] if text else None)
            # Re-ack is harmless, but remove the ack() inside the wrapped function
            return func(ack=lambda: None, command=command, client=client, say=say, **kwargs)
        return wrapper
    return decorator

# Usage:
@app.command("/research")
@track_command("/research")
def handle_research(ack, command, client, say):
    # ack() already called by decorator
    # ...
```

**Note:** This decorator approach is optional. The simple inline `log_engagement()` call is perfectly fine and more explicit.

## DO NOT
- Do not log PII (full questions, email addresses) — truncate to 100 chars or use category labels
- Do not let `log_engagement` failures crash handlers — the function already swallows exceptions
- Do not instrument Home tab render events — they fire too frequently
- Do not instrument `ack()` calls or middleware — only user-initiated events

## Testing
1. Run several commands: `/research NovaTech`, `/deal NovaTech`, `/pipeline`
2. Check: `sqlite3 data/salescoach.db "SELECT event_type, command, COUNT(*) FROM engagement_events GROUP BY event_type, command ORDER BY COUNT(*) DESC"`
3. Should see rows for each command you ran
4. Click some buttons on cards that were returned
5. Check: `sqlite3 data/salescoach.db "SELECT action_id, COUNT(*) FROM engagement_events WHERE event_type='action' GROUP BY action_id"`
