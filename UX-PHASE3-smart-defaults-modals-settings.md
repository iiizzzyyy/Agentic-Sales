# UX Phase 3 — Smart Defaults, Modal Flows, Notifications, DM Privacy

Phase 3 brings context-awareness, multi-step modals, user preferences, and channel-appropriate behavior. These are production-quality improvements.

---

## Part A: Smart Defaults (Context-Aware Actions)

### Problem
Every deal card shows the same buttons regardless of context. A deal in "Discovery" stage that hasn't been touched in 3 weeks needs different actions than a deal in "Negotiation" that was updated yesterday. Slack's design guide says: "Anticipate what the user needs."

### Implementation

#### Step 1: Create `get_smart_actions()` in `formatters/deal.py`

Add a function that returns contextually appropriate action elements:

```python
from datetime import datetime, timedelta
from formatters.helpers import format_currency

def get_smart_actions(deal_data, search_term=None):
    """Return context-aware action buttons based on deal state.

    Priority logic:
    1. If deal is stale (no activity in 14+ days) → primary: "Re-engage Contact"
    2. If deal is in late stage (Negotiation/Contract) → primary: "Draft Email"
    3. If deal has no contact → primary: "Research Company"
    4. Default → primary: "Draft Email"
    """
    deal_name = deal_data.get("name", "Unknown")
    company_name = deal_data.get("company", "Unknown")
    stage = deal_data.get("stage", "").lower()
    last_activity = deal_data.get("last_activity_date")  # ISO string or None

    # Determine staleness
    is_stale = False
    if last_activity:
        try:
            last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            is_stale = (datetime.now(last_dt.tzinfo) - last_dt) > timedelta(days=14)
        except (ValueError, TypeError):
            pass

    has_contact = bool(deal_data.get("primary_contact"))
    late_stage = stage in ("negotiation", "contract sent", "closing", "proposal")

    # Build primary action
    if is_stale and has_contact:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Re-engage Contact", "emoji": True},
            "action_id": "draft_email_from_deal",
            "value": deal_name,
            "style": "primary",
        }
    elif not has_contact:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Research Company", "emoji": True},
            "action_id": "research_from_deal",
            "value": company_name,
            "style": "primary",
        }
    else:
        primary = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
            "action_id": "draft_email_from_deal",
            "value": deal_name,
            "style": "primary",
        }

    # Build action elements list
    action_elements = []
    if search_term:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "← Back to Results", "emoji": True},
            "action_id": "back_to_deal_results",
            "value": search_term,
        })

    action_elements.append(primary)

    # Overflow for secondary actions
    overflow_options = []
    # Only add to overflow if they're NOT already the primary
    if primary["action_id"] != "research_from_deal":
        overflow_options.append({
            "text": {"type": "plain_text", "text": "Research Company"},
            "value": f"research_from_deal|{company_name}",
        })
    if primary["action_id"] != "draft_email_from_deal":
        overflow_options.append({
            "text": {"type": "plain_text", "text": "Draft Email"},
            "value": f"draft_email_from_deal|{deal_name}",
        })
    overflow_options.append({
        "text": {"type": "plain_text", "text": "Log a Note"},
        "value": f"log_note|{deal_name}",
    })

    if overflow_options:
        action_elements.append({
            "type": "overflow",
            "action_id": "deal_overflow",
            "options": overflow_options,
        })

    return action_elements
```

#### Step 2: Update `format_deal_response` to Use `get_smart_actions`

```python
# BEFORE (in format_deal_response):
action_elements = [...]  # static list of buttons

# AFTER:
action_elements = get_smart_actions(deal_data, search_term=search_term)
```

#### Step 3: Context Hint in Deal Card

Add a context line that explains WHY the primary action was chosen:

```python
# After the action block, before the footer:
if is_stale:
    hint_text = f"💡 _No activity in {days_since_activity} days — consider reaching out_"
elif not has_contact:
    hint_text = "💡 _No contact linked — research the company to find decision makers_"
else:
    hint_text = None

if hint_text:
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": hint_text}]
    })
```

---

## Part B: Modal Flows for Multi-Step Interactions

### Problem
The email drafting flow currently works as: Research Card → Contact Picker (new message) → Email Draft (new message). That's 3 messages in the channel for one email. Slack's design guide says: "Use modals for multi-step workflows."

### Strategy
Replace the Contact Picker → Email Draft message chain with a single modal that opens on button click. The modal has two views: Step 1 picks the contact, Step 2 shows the draft.

### Implementation

#### Step 1: Open Modal from "Draft Follow-Up Email" Button

In `app.py`, update the `draft_email_from_research` action handler:

```python
@app.action("draft_email_from_research")
def handle_draft_email_from_research(ack, body, client):
    ack()
    company_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    trigger_id = body["trigger_id"]  # Required for opening modals
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Collapse the original card (Phase 1.2)
    collapse_message(client, channel, message_ts,
        f"Research Brief: {company_name}",
        "✉️ Opening email composer..."
    )

    # Fetch contacts for this company
    contacts = _get_contacts_for_company(company_name, user_id)

    if not contacts:
        client.chat_postMessage(
            channel=channel,
            thread_ts=message_ts,
            text=f"_No contacts found for {company_name} — try `/research {company_name}` to find contacts online_"
        )
        return

    # Build contact picker modal
    modal_blocks = _build_contact_picker_modal_blocks(contacts, company_name)

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "email_contact_picker_modal",
            "title": {"type": "plain_text", "text": "Draft Email"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps({
                "company_name": company_name,
                "channel": channel,
                "thread_ts": message_ts,
            }),
            "blocks": modal_blocks,
        }
    )
```

#### Step 2: Build Modal Blocks for Contact Selection

```python
def _build_contact_picker_modal_blocks(contacts, company_name):
    """Build Block Kit blocks for the contact picker inside a modal."""
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Choose a contact for {company_name}*\nSelect who should receive the follow-up email."}
        },
        {"type": "divider"},
    ]

    for i, contact in enumerate(contacts[:10]):
        name = contact.get("name", "Unknown")
        title = contact.get("title", "")
        email = contact.get("email", "No email")
        source = contact.get("source", "CRM")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{name}*\n{title}\n📧 {email} · _{source}_"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Select", "emoji": True},
                "action_id": f"modal_select_contact_{i}",
                "value": json.dumps({"name": name, "email": email, "title": title}),
            }
        })

    return blocks
```

#### Step 3: Handle Contact Selection in Modal → Update to Email Draft View

```python
# Register action handlers for each contact button in the modal
for i in range(10):
    @app.action(f"modal_select_contact_{i}")
    def handle_modal_contact_select(ack, body, client, action_index=i):
        ack()
        contact_data = json.loads(body["actions"][0]["value"])
        metadata = json.loads(body["view"]["private_metadata"])
        company_name = metadata["company_name"]
        channel = metadata["channel"]
        thread_ts = metadata["thread_ts"]
        user_id = body["user"]["id"]

        # Generate the email draft
        contact_name = contact_data["name"]
        contact_email = contact_data["email"]

        # Show loading state
        client.views_update(
            view_id=body["view"]["id"],
            view={
                "type": "modal",
                "callback_id": "email_draft_modal",
                "title": {"type": "plain_text", "text": "Draft Email"},
                "close": {"type": "plain_text", "text": "Close"},
                "private_metadata": json.dumps({
                    **metadata,
                    "contact_name": contact_name,
                    "contact_email": contact_email,
                }),
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"⏳ Drafting email to *{contact_name}*..."}
                    }
                ]
            }
        )

        # Generate email (call LLM)
        email_data = _generate_email_draft(company_name, contact_data, user_id)

        # Update modal with the draft
        draft_blocks = _build_email_draft_modal_blocks(email_data, contact_data, company_name)

        client.views_update(
            view_id=body["view"]["id"],
            view={
                "type": "modal",
                "callback_id": "email_draft_modal",
                "title": {"type": "plain_text", "text": "Draft Email"},
                "submit": {"type": "plain_text", "text": "Create Gmail Draft"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "private_metadata": json.dumps({
                    **metadata,
                    "contact_name": contact_name,
                    "contact_email": contact_email,
                    "email_subject": email_data.get("subject", ""),
                    "email_body": email_data.get("body", ""),
                }),
                "blocks": draft_blocks,
            }
        )
```

#### Step 4: Email Draft Modal View

```python
def _build_email_draft_modal_blocks(email_data, contact_data, company_name):
    """Build Block Kit blocks for the email draft inside a modal."""
    return [
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*To:* {contact_data['name']} ({contact_data['email']})"},
                {"type": "mrkdwn", "text": f"*Company:* {company_name}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "input",
            "block_id": "subject_block",
            "label": {"type": "plain_text", "text": "Subject"},
            "element": {
                "type": "plain_text_input",
                "action_id": "subject_input",
                "initial_value": email_data.get("subject", ""),
            }
        },
        {
            "type": "input",
            "block_id": "body_block",
            "label": {"type": "plain_text", "text": "Email Body"},
            "element": {
                "type": "plain_text_input",
                "action_id": "body_input",
                "multiline": True,
                "initial_value": email_data.get("body", ""),
            }
        },
    ]
```

#### Step 5: Handle Modal Submission (Create Gmail Draft)

```python
@app.view("email_draft_modal")
def handle_email_draft_submit(ack, body, client, view):
    ack()
    metadata = json.loads(view["private_metadata"])
    values = view["state"]["values"]

    subject = values["subject_block"]["subject_input"]["value"]
    email_body = values["body_block"]["body_input"]["value"]
    contact_email = metadata["contact_email"]
    contact_name = metadata["contact_name"]
    channel = metadata["channel"]
    thread_ts = metadata.get("thread_ts")

    # Create Gmail draft (existing logic)
    success = _create_gmail_draft(contact_email, subject, email_body)

    # Post confirmation to the channel/thread
    if success:
        confirmation = f"✅ Gmail draft created for *{contact_name}* ({contact_email})\n*Subject:* {subject}"
    else:
        confirmation = f"⚠️ Could not create Gmail draft. Email copied to clipboard instead."

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=confirmation,
    )
```

### Benefits of Modal Flow
1. **Zero channel clutter** — contact picker and email draft are in a modal, not the channel
2. **Editable draft** — the user can edit subject/body directly in the modal before sending
3. **Clean UX** — single submit button creates the Gmail draft
4. **Back button** — user can close modal without affecting the channel

### Keep the Message-Based Flow as Fallback
Modals require a `trigger_id` which expires after 3 seconds. If `views_open` fails (expired trigger), fall back to the current message-based contact picker flow. Wrap the `views_open` call in try/except.

---

## Part C: User Preferences via `/settings`

### Problem
Different users want different things: some want verbose research briefs, others want compact summaries. Some want DM responses, others want channel responses. There's no way to configure this.

### Implementation

#### Step 1: Create Settings Storage

Add a simple JSON-based settings store:

```python
# settings_store.py
import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "data", "user_settings.json")

DEFAULT_SETTINGS = {
    "response_mode": "channel",      # "channel" or "dm"
    "detail_level": "summary",       # "summary" or "full"
    "notification_frequency": "all",  # "all", "important", "minimal"
    "coaching_privacy": True,         # True = coaching in DM only
}

def get_user_settings(user_id):
    """Get settings for a user, with defaults."""
    all_settings = _load_settings()
    user = all_settings.get(user_id, {})
    return {**DEFAULT_SETTINGS, **user}

def update_user_settings(user_id, key, value):
    """Update a single setting for a user."""
    all_settings = _load_settings()
    if user_id not in all_settings:
        all_settings[user_id] = {}
    all_settings[user_id][key] = value
    _save_settings(all_settings)

def _load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
```

#### Step 2: Add `/settings` Slash Command

In `app.py`:

```python
from settings_store import get_user_settings, update_user_settings

@app.command("/settings")
def handle_settings(ack, command, client):
    ack()
    user_id = command["user_id"]
    trigger_id = command["trigger_id"]
    settings = get_user_settings(user_id)

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "settings_modal",
            "title": {"type": "plain_text", "text": "SalesCoach Settings"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Response Mode*\nWhere should SalesCoach post responses?"}
                },
                {
                    "type": "actions",
                    "block_id": "response_mode_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "response_mode",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "In channel" if settings["response_mode"] == "channel" else "Direct message"},
                            "value": settings["response_mode"],
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "In channel"}, "value": "channel"},
                            {"text": {"type": "plain_text", "text": "Direct message"}, "value": "dm"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Detail Level*\nHow much detail in research/deal responses?"}
                },
                {
                    "type": "actions",
                    "block_id": "detail_level_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "detail_level",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Summary first (expand for full)" if settings["detail_level"] == "summary" else "Full detail always"},
                            "value": settings["detail_level"],
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Summary first (expand for full)"}, "value": "summary"},
                            {"text": {"type": "plain_text", "text": "Full detail always"}, "value": "full"},
                        ]
                    }]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Coaching Privacy*\nKeep coaching scores and roleplay debriefs private?"}
                },
                {
                    "type": "actions",
                    "block_id": "coaching_privacy_block",
                    "elements": [{
                        "type": "radio_buttons",
                        "action_id": "coaching_privacy",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Yes — DM only" if settings["coaching_privacy"] else "No — post in channel"},
                            "value": "true" if settings["coaching_privacy"] else "false",
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes — DM only"}, "value": "true"},
                            {"text": {"type": "plain_text", "text": "No — post in channel"}, "value": "false"},
                        ]
                    }]
                },
            ]
        }
    )


@app.view("settings_modal")
def handle_settings_submit(ack, body, view):
    ack()
    user_id = body["user"]["id"]
    values = view["state"]["values"]

    response_mode = values["response_mode_block"]["response_mode"]["selected_option"]["value"]
    detail_level = values["detail_level_block"]["detail_level"]["selected_option"]["value"]
    coaching_privacy = values["coaching_privacy_block"]["coaching_privacy"]["selected_option"]["value"] == "true"

    update_user_settings(user_id, "response_mode", response_mode)
    update_user_settings(user_id, "detail_level", detail_level)
    update_user_settings(user_id, "coaching_privacy", coaching_privacy)
```

#### Step 3: Use Settings in Handlers

Update key handlers to respect user settings:

```python
# In /research handler:
settings = get_user_settings(user_id)

# Detail level
if settings["detail_level"] == "summary":
    blocks, fallback = format_research_summary(...)
else:
    blocks, fallback = format_research_response(...)

# Response mode
if settings["response_mode"] == "dm":
    # Open a DM channel with the user
    dm = client.conversations_open(users=[user_id])
    target_channel = dm["channel"]["id"]
else:
    target_channel = channel_id
```

```python
# In coaching handlers (roleplay debrief, coach live summary):
settings = get_user_settings(user_id)

if settings["coaching_privacy"]:
    # Send debrief/scores via DM
    dm = client.conversations_open(users=[user_id])
    target_channel = dm["channel"]["id"]
    # Post a brief note in the original channel
    client.chat_postMessage(
        channel=original_channel,
        thread_ts=thread_ts,
        text="✅ Coaching debrief sent to your DMs."
    )
else:
    target_channel = original_channel
```

---

## Part D: DM Privacy & Channel-Aware Responses

### Problem
Coaching scores, roleplay debriefs, and personal performance data should not be posted in public channels where managers and teammates can see them. Slack's design guide says: "Don't leak sensitive information into shared spaces."

### Rules for Channel-Aware Behavior

| Content Type | Public Channel | DM | Group DM |
|-------------|---------------|-----|----------|
| Research Brief | ✅ Channel | ✅ DM | ✅ Group DM |
| Deal Detail | ✅ Channel | ✅ DM | ✅ Group DM |
| Pipeline Health | ✅ Channel | ✅ DM | ✅ Group DM |
| Email Draft | ✅ Channel | ✅ DM | ✅ Group DM |
| Roleplay Start | ✅ Channel | ✅ DM | ✅ Group DM |
| **Roleplay Debrief** | ⚠️ DM only* | ✅ DM | ⚠️ DM only* |
| **Coach Live Summary** | ⚠️ DM only* | ✅ DM | ⚠️ DM only* |
| **Win/Loss Analysis** | ⚠️ DM only* | ✅ DM | ⚠️ DM only* |
| Alerts Digest | ✅ Channel | ✅ DM | ✅ Group DM |
| Forecast | ✅ Channel | ✅ DM | ✅ Group DM |

*Unless the user has set `coaching_privacy: false` in `/settings`.

### Implementation

Add a helper to determine the right response channel:

```python
def get_response_channel(client, user_id, original_channel, content_type="general"):
    """Determine where to post the response based on content sensitivity and user settings.

    Args:
        client: Slack WebClient
        user_id: The requesting user's ID
        original_channel: The channel the command was run in
        content_type: "general", "coaching", or "performance"

    Returns:
        (target_channel, should_notify_original): tuple
    """
    settings = get_user_settings(user_id)

    # General content always goes to the original channel
    if content_type == "general":
        if settings["response_mode"] == "dm":
            dm = client.conversations_open(users=[user_id])
            return dm["channel"]["id"], True
        return original_channel, False

    # Coaching/performance content
    if content_type in ("coaching", "performance"):
        if settings["coaching_privacy"]:
            dm = client.conversations_open(users=[user_id])
            return dm["channel"]["id"], True
        return original_channel, False

    return original_channel, False
```

Then in each handler:

```python
target_channel, notify = get_response_channel(client, user_id, channel_id, content_type="coaching")

client.chat_postMessage(channel=target_channel, text=fallback, blocks=blocks)

if notify:
    client.chat_postMessage(
        channel=channel_id,
        text=f"✅ Results sent to your DMs.",
    )
```

---

## Part E: Pagination for Large Datasets

### Problem
Deal picker caps at 15 deals, contact picker at 10. Users with many deals can't access the rest. No "next page" mechanism exists.

### Implementation

Add pagination state to picker formatters:

#### `formatters/deal.py` — `format_deal_picker`

```python
def format_deal_picker(deals, search_term, page=0, page_size=10):
    """Format a paginated deal picker.

    Args:
        deals: Full list of matching deals
        search_term: The search query
        page: Current page (0-indexed)
        page_size: Items per page
    """
    total = len(deals)
    start = page * page_size
    end = start + page_size
    page_deals = deals[start:end]
    total_pages = (total + page_size - 1) // page_size

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Deals matching \"{search_term}\"", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing {start+1}–{min(end, total)} of {total} deals"}
            ]
        },
        {"type": "divider"},
    ]

    # Add deal sections (same as current logic)
    for deal in page_deals:
        blocks.append(_format_deal_picker_item(deal))

    blocks.append({"type": "divider"})

    # Pagination buttons
    nav_elements = []
    if page > 0:
        nav_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "← Previous Page", "emoji": True},
            "action_id": "deal_picker_prev",
            "value": json.dumps({"search_term": search_term, "page": page - 1}),
        })
    if end < total:
        nav_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Next Page →", "emoji": True},
            "action_id": "deal_picker_next",
            "value": json.dumps({"search_term": search_term, "page": page + 1}),
        })

    if nav_elements:
        blocks.append({"type": "actions", "elements": nav_elements})

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI • Page {page+1} of {total_pages} • {timestamp()}"}]
    })

    fallback = f"Deals matching \"{search_term}\" — showing {start+1}-{min(end, total)} of {total}"
    return blocks, fallback
```

#### Add Pagination Action Handlers

```python
@app.action("deal_picker_prev")
@app.action("deal_picker_next")
def handle_deal_pagination(ack, body, client):
    ack()
    data = json.loads(body["actions"][0]["value"])
    search_term = data["search_term"]
    page = data["page"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    # Re-fetch deals (or use cache)
    deals = _search_deals(search_term, user_id)
    blocks, fallback = format_deal_picker(deals, search_term, page=page)

    # UPDATE the existing picker message (don't post a new one)
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )
```

Apply the same pattern to `format_contact_picker` and `format_email_deal_picker` in `formatters/email.py`.

---

## Part F: Timestamp Context for Metrics

### Problem
Pipeline health says "Total Value: $668,000" but doesn't say as-of-when. Win/loss shows "Win Rate: 67%" but for what time period? Users can't trust metrics without temporal context.

### Implementation

Add explicit date context to all analytics-type formatters:

#### `formatters/pipeline.py`
```python
# Add to the header context block:
{
    "type": "context",
    "elements": [
        {"type": "mrkdwn", "text": f"📊 Pipeline snapshot as of {timestamp()} · Data from HubSpot CRM"}
    ]
}
```

#### `formatters/win_loss.py`
```python
# The filter label context already exists — enhance it:
# BEFORE:
{"type": "mrkdwn", "text": f"Filter: {filter_label}"}

# AFTER:
{"type": "mrkdwn", "text": f"📊 {filter_label} · Analysis period: Last 12 months · Generated {timestamp()}"}
```

#### `formatters/forecast.py`
```python
# Add temporal context:
{"type": "mrkdwn", "text": f"📊 Forecast as of {timestamp()} · Based on current pipeline data"}
```

#### `formatters/alerts.py`
```python
# Add to the digest header:
{"type": "mrkdwn", "text": f"📊 Alerts checked {timestamp()} · Monitoring last 48 hours of activity"}
```

---

## DO NOT
- Do not make `/settings` data persist across different Slack workspaces — scope to user_id
- Do not auto-DM users without their consent — respect the default settings
- Do not add more than 3 settings to start — keep the modal simple
- Do not break existing flows when adding modals — keep message-based flow as fallback
- Do not paginate lists under 10 items — pagination only kicks in when total > page_size
- Do not cache user settings in memory — always read from the JSON file (it's small and infrequent)
- Do not add timestamps to every block — only to analytics/metrics cards where temporal context matters

## Testing
1. `/settings` → modal opens → change detail level to "Full detail always" → save → `/research NovaTech` → full research card appears (not summary)
2. `/settings` → enable coaching privacy → `/coach roleplay` → complete roleplay → debrief appears in DM, channel shows "✅ Results sent to your DMs"
3. `/deal NovaTech` with 25+ deals → deal picker shows page 1 (10 deals) → click "Next Page" → page 2 appears (same message updated)
4. Deal card for stale deal (14+ days no activity) → primary button is "Re-engage Contact" with context hint
5. Deal card with no contact → primary button is "Research Company"
6. "Draft Follow-Up Email" from research → modal opens → pick contact → loading state → email draft in modal → submit creates Gmail draft → confirmation in channel thread
7. `/pipeline` → shows "Pipeline snapshot as of Mar 11, 2026 at 2:34 PM"
8. `/win-loss` → shows "Analysis period: Last 12 months"
