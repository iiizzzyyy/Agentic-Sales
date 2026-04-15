# UX Phase 2.2 — Overflow Menus, Truncation Indicators, Table Blocks

This instruction covers three improvements that reduce visual clutter and improve data presentation.

---

## Part A: Overflow Menus for Secondary Actions

### Problem
Several cards show 3-4 buttons in a row. On mobile, buttons wrap awkwardly. Slack's guidelines say to use overflow menus for secondary actions, keeping only 1-2 primary buttons visible.

### The Pattern
Keep the most important action as a visible `button`. Move secondary/less-used actions into an `overflow` menu (the ⋮ icon).

```python
{
    "type": "actions",
    "elements": [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Primary Action", "emoji": True},
            "action_id": "primary_action",
            "value": "some_value",
            "style": "primary",
        },
        {
            "type": "overflow",
            "action_id": "card_overflow",
            "options": [
                {
                    "text": {"type": "plain_text", "text": "Secondary Action 1"},
                    "value": "secondary_1|some_data",
                },
                {
                    "text": {"type": "plain_text", "text": "Secondary Action 2"},
                    "value": "secondary_2|some_data",
                },
            ]
        }
    ]
}
```

### Changes Required

#### 1. `formatters/deal.py` — `format_deal_response`

Currently has up to 4 buttons: "← Back to Results", "Draft Email", "Full Research", "Log Note"

**Change:** Keep "Draft Email" as primary button and "← Back to Results" as secondary button. Move "Full Research" and "Log Note" into overflow.

```python
# BEFORE:
action_elements = []
if search_term:
    action_elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "← Back to Results", "emoji": True},
        "action_id": "back_to_deal_results",
        "value": search_term,
    })
action_elements.extend([
    {"type": "button", "text": {"type": "plain_text", "text": "Draft Email", "emoji": True}, "action_id": "draft_email_from_deal", "value": deal_name, "style": "primary"},
    {"type": "button", "text": {"type": "plain_text", "text": "Full Research", "emoji": True}, "action_id": "research_from_deal", "value": company_name},
    {"type": "button", "text": {"type": "plain_text", "text": "Log Note", "emoji": True}, "action_id": "log_note", "value": deal_name},
])

# AFTER:
action_elements = []
if search_term:
    action_elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "← Back to Results", "emoji": True},
        "action_id": "back_to_deal_results",
        "value": search_term,
    })
action_elements.append({
    "type": "button",
    "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
    "action_id": "draft_email_from_deal",
    "value": deal_name,
    "style": "primary",
})

overflow_options = [
    {
        "text": {"type": "plain_text", "text": "Research Company"},
        "value": f"research_from_deal|{company_name}",
    },
    {
        "text": {"type": "plain_text", "text": "Log a Note"},
        "value": f"log_note|{deal_name}",
    },
]
action_elements.append({
    "type": "overflow",
    "action_id": "deal_overflow",
    "options": overflow_options,
})
```

#### 2. `formatters/win_loss.py` — `format_win_loss_response`

Currently has 3 buttons: "View Lost Deals", "View Won Deals", "Competitor Analysis"

**Change:** Keep "See Win/Loss Breakdown" (Phase 1 rename of "Full Analysis") as primary. Move the three drill-down buttons into overflow.

```python
# AFTER:
action_elements = [
    {
        "type": "button",
        "text": {"type": "plain_text", "text": "See Win/Loss Breakdown", "emoji": True},
        "action_id": "win_loss_breakdown",
        "style": "primary",
        "value": filter_value or "all",
    },
    {
        "type": "overflow",
        "action_id": "win_loss_overflow",
        "options": [
            {"text": {"type": "plain_text", "text": "View Lost Deals"}, "value": f"win_loss_lost_deals|{filter_value}"},
            {"text": {"type": "plain_text", "text": "View Won Deals"}, "value": f"win_loss_won_deals|{filter_value}"},
            {"text": {"type": "plain_text", "text": "Competitor Analysis"}, "value": f"win_loss_competitor|{filter_value}"},
        ]
    }
]
```

#### 3. `formatters/objection.py` — `format_objection_response`

Currently has 2 buttons: "Practice This Objection" and "More Detail" (renamed to "Get Full Objection Guide" in Phase 1).

**Change:** Keep "Practice This Objection" as primary. Move "Get Full Objection Guide" into overflow.

```python
# AFTER:
action_elements = [
    {
        "type": "button",
        "text": {"type": "plain_text", "text": "Practice This Objection", "emoji": True},
        "action_id": "practice_objection",
        "value": objection,
        "style": "primary",
    },
    {
        "type": "overflow",
        "action_id": "objection_overflow",
        "options": [
            {"text": {"type": "plain_text", "text": "Get Full Objection Guide"}, "value": f"expand_objection|{objection}"},
        ]
    }
]
```

#### 4. New Overflow Action Handler in `app.py`

Add a single handler that routes overflow selections:

```python
@app.action("deal_overflow")
def handle_deal_overflow(ack, body, client):
    ack()
    selected = body["actions"][0]["selected_option"]["value"]
    action_type, value = selected.split("|", 1)

    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    if action_type == "research_from_deal":
        # Reuse existing research_from_deal logic
        _trigger_research_from_deal(client, channel, message_ts, value, body["user"]["id"])
    elif action_type == "log_note":
        # Reuse existing log_note logic
        _trigger_log_note(client, channel, message_ts, value, body["user"]["id"])


@app.action("win_loss_overflow")
def handle_win_loss_overflow(ack, body, client):
    ack()
    selected = body["actions"][0]["selected_option"]["value"]
    action_type, value = selected.split("|", 1)

    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    if action_type == "win_loss_lost_deals":
        _trigger_win_loss_drill(client, channel, message_ts, "lost", value, body["user"]["id"])
    elif action_type == "win_loss_won_deals":
        _trigger_win_loss_drill(client, channel, message_ts, "won", value, body["user"]["id"])
    elif action_type == "win_loss_competitor":
        _trigger_win_loss_competitor(client, channel, message_ts, value, body["user"]["id"])


@app.action("objection_overflow")
def handle_objection_overflow(ack, body, client):
    ack()
    selected = body["actions"][0]["selected_option"]["value"]
    action_type, value = selected.split("|", 1)

    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    if action_type == "expand_objection":
        _trigger_expand_objection(client, channel, message_ts, value, body["user"]["id"])
```

**Important:** Extract the existing action logic from the current `@app.action("research_from_deal")`, `@app.action("log_note")`, etc. into reusable `_trigger_*` functions. The original `@app.action` handlers should call these same functions so the direct-button path still works (for any formatters that still expose buttons directly).

---

## Part B: Truncation Indicators

### Problem
Several formatters silently truncate content (activities, deal stories, talking points) using `truncate()` from helpers.py, but users have no idea content was cut. They lose trust in the data.

### The Fix
When content is truncated, add a visible indicator. Two approaches depending on context:

#### Approach 1: Inline Indicator (for text fields)

Update `formatters/helpers.py` `truncate()` function:

```python
# BEFORE:
def truncate(text, max_length=120):
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

# AFTER:
def truncate(text, max_length=120, indicator="..."):
    """Truncate text with a visible indicator.

    Args:
        text: Text to truncate
        max_length: Maximum character length
        indicator: What to append when truncated (default "...")
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + indicator
```

Note: the `.rsplit(" ", 1)[0]` prevents cutting mid-word.

#### Approach 2: "View More" Line (for sections with multiple items)

When a list is capped (e.g., only showing 5 of 12 contacts), add a summary line:

```python
# Example for contacts in formatters/research.py:
MAX_CONTACTS = 5
displayed_contacts = contacts[:MAX_CONTACTS]

# ... build contact lines ...

if len(contacts) > MAX_CONTACTS:
    remaining = len(contacts) - MAX_CONTACTS
    contacts_str += f"\n_+ {remaining} more contact{'s' if remaining != 1 else ''} — run `/research {company_name}` for full details_"
```

### Specific Files to Update

#### `formatters/research.py`
- **Contacts**: Currently caps at 5. Add: `"_+ {n} more contacts_"` if more exist
- **Deals**: Currently caps at 5. Add: `"_+ {n} more deals — use `/deal` to search_"` if more exist
- **News**: Currently caps at 3. Add: `"_+ {n} more articles_"` if more exist
- **Talking Points**: Currently truncated at some char limit. Add: `"... (expand for full talking points)"` if truncated

#### `formatters/deal.py`
- **Activities**: Currently caps at 4 with 120-char truncation. Add: `"_+ {n} more activities_"` if more exist
- **Deal Picker**: Currently caps at 15. Add: `"_Showing {15} of {total} deals — narrow your search for more_"` if more exist

#### `formatters/handoff.py`
- **Deal Story**: Truncated at 2500 chars. Add: `"_... story truncated — expand for full narrative_"` if truncated
- **Contacts**: Currently caps at 5. Add: `"_+ {n} more contacts_"` indicator
- **Risks**: Currently caps at 5. Add: `"_+ {n} more risks identified_"` if more exist

#### `formatters/pipeline.py`
- **Flagged Deals**: If implementing Phase 2.1 truncation (max 3), add the indicator as described there

#### `formatters/email.py`
- **Contact Picker**: Currently caps at 10. Add: `"_Showing first 10 contacts — check CRM for the full list_"`
- **Deal Picker**: Currently caps at 10. Add: `"_Showing first 10 deals — narrow your search_"`

#### `formatters/win_loss.py`
- **Patterns text**: Split at 2800 chars. Add: `"_(continued below)_"` at the split point instead of silently splitting

---

## Part C: Table Blocks for Structured Data

### Problem
Pipeline stage breakdown and win/loss trends are currently rendered as inline mrkdwn text with emoji-coded bars. This works but is hard to scan. Block Kit has a rich_text list element that can improve readability, and we can use consistent column formatting.

### Note on Block Kit Tables
Block Kit does not have a native "table" block type in the public API as of May 2025. The closest options are:
1. **Section with fields** — 2-column layout (already used)
2. **Mrkdwn with monospace** — Use backtick formatting for aligned columns
3. **rich_text block with rich_text_list** — Bulleted/ordered lists with rich formatting

### Implementation: Formatted Stage Breakdown

#### `formatters/pipeline.py` — Stage Breakdown

Replace the current inline mrkdwn stage breakdown with a cleaner monospace-aligned format:

```python
# BEFORE (current pattern — varies by implementation):
# stage_text is built as lines of mrkdwn

# AFTER:
def _format_stage_table(stages):
    """Format pipeline stages as an aligned table using mrkdwn."""
    if not stages:
        return "_No stage data available_"

    lines = ["```"]
    lines.append(f"{'Stage':<20} {'Deals':>6} {'Value':>12}")
    lines.append("-" * 40)
    for stage in stages:
        name = stage.get("stage", "Unknown")[:18]
        count = stage.get("count", 0)
        value = format_currency(stage.get("total_value", 0))
        lines.append(f"{name:<20} {count:>6} {value:>12}")
    lines.append("```")
    return "\n".join(lines)
```

This renders as:
```
Stage                Deals        Value
----------------------------------------
Discovery                3      $48,000
Proposal                 2     $370,000
Negotiation              1     $250,000
```

#### `formatters/win_loss.py` — Trend Data

Replace the emoji-bar trend display with a cleaner monospace format:

```python
# AFTER:
def _format_trend_table(trends):
    """Format win/loss trends as an aligned table."""
    if not trends:
        return "_No trend data available_"

    lines = ["```"]
    lines.append(f"{'Period':<12} {'Win%':>6} {'Won':>5} {'Lost':>5}")
    lines.append("-" * 30)
    for period in trends:
        name = period.get("period", "?")[:10]
        rate = period.get("win_rate", 0)
        won = period.get("won", 0)
        lost = period.get("lost", 0)
        lines.append(f"{name:<12} {rate:>5}% {won:>5} {lost:>5}")
    lines.append("```")
    return "\n".join(lines)
```

This renders as:
```
Period        Win%   Won  Lost
------------------------------
Jan 2026       67%     4     2
Feb 2026       50%     3     3
Mar 2026       75%     6     2
```

### Keep the Emoji Indicators for Flagged Deals
The ⏰ 🚨 ⚠️ emoji indicators for flagged deal types (stale, overdue, at_risk) are effective visual cues. Keep these — they follow Slack's "emoji as decoration" principle.

---

## DO NOT
- Do not remove existing action handlers when adding overflow menus — refactor into `_trigger_*` helper functions so both paths work
- Do not use actual HTML `<table>` tags — they don't render in Slack
- Do not exceed 10 options in a single overflow menu (Slack limit)
- Do not add overflow menus to cards with only 1-2 buttons — overflow is only worth it at 3+ actions
- Do not change action_ids for existing direct buttons — only add new overflow action_ids
- Do not truncate mid-word — use `rsplit(" ", 1)` to break at word boundaries

## Testing
1. `/deal NovaTech` → pick a deal → verify "Draft Email" is primary button, overflow ⋮ contains "Research Company" and "Log a Note"
2. Click ⋮ → select "Research Company" → verify it triggers research flow correctly
3. `/research` with a company that has 8+ contacts → verify "5 contacts shown + _+ 3 more contacts_" indicator
4. `/pipeline` → verify stage breakdown renders as aligned monospace table
5. `/win-loss` → verify trend data renders as aligned monospace table
6. `/deal NovaTech` with 20+ deals → verify "Showing 15 of 22 deals" indicator
7. `/handoff` → verify truncated deal story shows "... story truncated" indicator
