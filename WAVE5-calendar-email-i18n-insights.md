# Wave 5: Pam Parity — Calendar, Email Send, Multi-Language, Market Insights

## Overview
Wave 5 closes the feature gap with Jam's "Pam" personal assistant. These features are **independent of Waves 2-4** and can be built in parallel. They add calendar awareness, email send+attachments, multi-language LLM output, and market trend analysis.

**New commands:** `/my-day`, `/market-insights`
**Enhanced commands:** `/coach prep` (auto-detect next meeting), email actions (send + attach), `/settings` (language picker)
**New files:** `tools/calendar.py`, `tools/market_insights.py`, `formatters/calendar.py`, `formatters/market_insights.py`
**New data:** `data/mock_calendar/events.json`, `data/documents/` (attachment library)

**Prerequisite:** Wave 1 must be complete (SQLite + `db.py` + engagement telemetry).

---

## Part A: Calendar & Day Plan (Features #5 + #7)

### A1. Create `data/mock_calendar/events.json`

For the POC demo, create a synthetic calendar with 5-7 meetings spread across today and tomorrow. This lets the demo work without requiring Google Calendar API access.

```json
[
  {
    "id": "evt_001",
    "title": "Discovery Call — NovaTech",
    "start": "2026-03-12T14:00:00-07:00",
    "end": "2026-03-12T14:45:00-07:00",
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
    "start": "2026-03-12T15:30:00-07:00",
    "end": "2026-03-12T16:00:00-07:00",
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
    "start": "2026-03-12T17:00:00-07:00",
    "end": "2026-03-12T17:30:00-07:00",
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
    "start": "2026-03-13T10:00:00-07:00",
    "end": "2026-03-13T11:00:00-07:00",
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
    "start": "2026-03-13T14:00:00-07:00",
    "end": "2026-03-13T15:00:00-07:00",
    "attendees": ["tom.baker@dataflow.com"],
    "description": "Contract negotiation, they want 15% discount. Need to discuss multi-year terms.",
    "location": "Zoom",
    "company": "DataFlow Inc",
    "contact_name": "Tom Baker",
    "contact_title": "VP Procurement"
  }
]
```

### A2. Create `tools/calendar.py`

This module abstracts calendar operations. For the POC it reads from mock JSON. Later, swap in Google Calendar MCP calls.

```python
"""Calendar integration — mock mode reads from data/mock_calendar/events.json.
Future: swap in Google Calendar MCP or API calls."""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

MOCK_CALENDAR_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mock_calendar", "events.json")

def _load_mock_events() -> list[dict]:
    """Load mock calendar events from JSON."""
    if not os.path.exists(MOCK_CALENDAR_PATH):
        return []
    with open(MOCK_CALENDAR_PATH, "r") as f:
        return json.load(f)

def _parse_dt(iso_str: str) -> datetime:
    """Parse ISO 8601 datetime string."""
    return datetime.fromisoformat(iso_str)

def get_todays_events(user_id: str) -> list[dict]:
    """Return all events for today, sorted by start time.
    Args:
        user_id: Slack user ID (unused in mock — future: filter by user's calendar)
    Returns:
        List of event dicts sorted by start time
    """
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
    Used by /coach prep auto-detect.
    Args:
        user_id: Slack user ID
    Returns:
        Next external meeting dict, or None
    """
    events = _load_mock_events()
    now = datetime.now().astimezone()

    upcoming = [
        e for e in events
        if _parse_dt(e["start"]) > now and e.get("company")  # skip internal (company=null)
    ]
    if not upcoming:
        return None
    return min(upcoming, key=lambda e: e["start"])

def get_event_by_id(event_id: str) -> Optional[dict]:
    """Look up a single event by ID."""
    events = _load_mock_events()
    return next((e for e in events if e["id"] == event_id), None)

def find_available_slots(user_id: str, date_str: str, duration_minutes: int = 30) -> list[dict]:
    """Find open time slots on a given date for rescheduling.
    Args:
        user_id: Slack user ID
        date_str: Date string "YYYY-MM-DD"
        duration_minutes: Desired slot duration
    Returns:
        List of {"start": "HH:MM", "end": "HH:MM"} slots
    """
    events = _load_mock_events()
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Get events on that date
    day_events = sorted(
        [e for e in events if _parse_dt(e["start"]).date() == target_date],
        key=lambda e: e["start"]
    )

    # Business hours: 9 AM to 6 PM
    slots = []
    business_start = 9 * 60  # minutes from midnight
    business_end = 18 * 60

    busy_blocks = []
    for e in day_events:
        start_dt = _parse_dt(e["start"])
        end_dt = _parse_dt(e["end"])
        busy_blocks.append((start_dt.hour * 60 + start_dt.minute, end_dt.hour * 60 + end_dt.minute))

    # Find gaps
    cursor = business_start
    for busy_start, busy_end in busy_blocks:
        if cursor + duration_minutes <= busy_start:
            slots.append({
                "start": f"{cursor // 60:02d}:{cursor % 60:02d}",
                "end": f"{(cursor + duration_minutes) // 60:02d}:{(cursor + duration_minutes) % 60:02d}"
            })
        cursor = max(cursor, busy_end)

    # Check after last meeting
    if cursor + duration_minutes <= business_end:
        slots.append({
            "start": f"{cursor // 60:02d}:{cursor % 60:02d}",
            "end": f"{(cursor + duration_minutes) // 60:02d}:{(cursor + duration_minutes) % 60:02d}"
        })

    return slots[:5]  # Return max 5 suggestions

def update_event_time(event_id: str, new_start: str, new_end: str) -> bool:
    """Update an event's time (mock: rewrites JSON file).
    Args:
        event_id: Event ID to update
        new_start: New start ISO datetime
        new_end: New end ISO datetime
    Returns:
        True if updated, False if event not found
    """
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

### A3. Create `formatters/calendar.py`

```python
"""Block Kit formatters for calendar features."""

from datetime import datetime

def format_day_plan(events: list[dict], date_label: str) -> tuple[list[dict], str]:
    """Format the /my-day output card.
    Args:
        events: List of event dicts from tools/calendar.py
        date_label: e.g. "Thursday, Mar 12"
    Returns:
        (blocks, fallback_text) tuple
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📅 Your Day — {date_label}"}
        },
        {"type": "divider"}
    ]

    if not events:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "No meetings scheduled today. Perfect time for prospecting! 🎯"}
        })
        return blocks, f"📅 Your Day — {date_label}: No meetings"

    for event in events:
        start_dt = datetime.fromisoformat(event["start"])
        time_str = start_dt.strftime("%-I:%M %p")
        title = event.get("title", "Untitled")
        location = event.get("location", "")
        contact = event.get("contact_name", "")
        contact_title = event.get("contact_title", "")
        company = event.get("company", "")

        # Build subtitle line
        subtitle_parts = []
        if contact:
            subtitle_parts.append(f"{contact}" + (f" ({contact_title})" if contact_title else ""))
        if location:
            subtitle_parts.append(f"📍 {location}")
        subtitle = " · ".join(subtitle_parts)

        section_text = f"*{time_str}*  {title}"
        if subtitle:
            section_text += f"\n{subtitle}"

        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": section_text}
        }

        # Add action buttons for external meetings (company is set)
        if company:
            block["accessory"] = {
                "type": "overflow",
                "action_id": "calendar_meeting_actions",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "🎯 Prep for Meeting"},
                        "value": f"prep|{company}"
                    },
                    {
                        "text": {"type": "plain_text", "text": "🔍 Research Company"},
                        "value": f"research|{company}"
                    },
                    {
                        "text": {"type": "plain_text", "text": "🔄 Reschedule"},
                        "value": f"reschedule|{event['id']}"
                    }
                ]
            }
        else:
            # Internal meeting — just show "View Pipeline" if it's a pipeline review
            if "pipeline" in title.lower():
                block["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Pipeline"},
                    "action_id": "view_pipeline_from_calendar",
                    "value": "pipeline"
                }

        blocks.append(block)

    fallback = f"📅 Your Day — {date_label}: {len(events)} meetings"
    return blocks, fallback


def format_reschedule_modal(event: dict, available_slots: list[dict]) -> dict:
    """Build the reschedule modal view.
    Args:
        event: The event being rescheduled
        available_slots: List of {"start": "HH:MM", "end": "HH:MM"} dicts
    Returns:
        Slack modal view dict
    """
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
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{event['title']}*\nCurrently: {current_time}"
                }
            },
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


def format_reschedule_confirmation(event_title: str, old_time: str, new_time: str) -> tuple[list[dict], str]:
    """Confirmation card after rescheduling.
    Returns:
        (blocks, fallback_text) tuple
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"✅ *Rescheduled:* {event_title}\n~{old_time}~ → *{new_time}*\nAttendees will be notified."
            }
        }
    ]
    return blocks, f"✅ Rescheduled: {event_title} from {old_time} to {new_time}"
```

### A4. Add `/my-day` command to `app.py`

```python
@app.command("/my-day")
async def handle_my_day(ack, command, say):
    """Show today's calendar with meeting prep actions."""
    await ack()
    user_id = command["user_id"]

    # Log engagement
    log_engagement(user_id, "command", "my_day")

    from tools.calendar import get_todays_events
    from formatters.calendar import format_day_plan
    from datetime import datetime

    events = get_todays_events(user_id)
    date_label = datetime.now().strftime("%A, %b %-d")

    blocks, fallback = format_day_plan(events, date_label)
    await say(blocks=blocks, text=fallback)
```

### A5. Enhance `/coach prep` auto-detect

Modify the existing `/coach prep` handler in `app.py`. When the user runs `/coach prep` with no arguments, auto-detect the next meeting from calendar.

**Find the existing handler** (search for the `/coach` command handler and its `prep` subcommand logic):

```python
# BEFORE (simplified):
# company_name = command["text"].strip()  # user must specify

# AFTER:
text = command["text"].strip()
parts = text.split(maxsplit=1)
subcommand = parts[0] if parts else ""

if subcommand == "prep":
    company_name = parts[1] if len(parts) > 1 else ""

    # Auto-detect from calendar if no company specified
    meeting_context = ""
    if not company_name:
        from tools.calendar import get_next_meeting
        next_meeting = get_next_meeting(user_id)
        if next_meeting:
            company_name = next_meeting.get("company", "")
            contact = next_meeting.get("contact_name", "")
            contact_title = next_meeting.get("contact_title", "")
            meeting_time = datetime.fromisoformat(next_meeting["start"]).strftime("%-I:%M %p")
            meeting_context = (
                f"\n\n📅 Auto-detected from your calendar: "
                f"*{next_meeting['title']}* at {meeting_time}"
                + (f" with {contact} ({contact_title})" if contact else "")
            )
        else:
            await say("No upcoming meetings found. Use `/coach prep [company]` to prep manually.")
            return

    # ... rest of existing prep logic ...
    # Inject meeting_context into the prep output if non-empty
```

### A6. Add `calendar_meeting_actions` overflow handler

Handle the overflow menu actions from the `/my-day` card:

```python
@app.action("calendar_meeting_actions")
async def handle_calendar_meeting_action(ack, body, say, client):
    """Handle overflow menu actions on calendar events."""
    await ack()
    user_id = body["user"]["id"]
    selected = body["actions"][0]["selected_option"]["value"]
    action_type, value = selected.split("|", 1)

    if action_type == "prep":
        # Trigger prep flow for this company
        log_engagement(user_id, "action", "calendar_prep", {"company": value})
        # Reuse existing prep logic — call the prep function directly
        # or post a message instructing the user
        await say(f"🎯 Prepping for your meeting with *{value}*...")
        # [invoke the same prep logic used by /coach prep with company=value]

    elif action_type == "research":
        log_engagement(user_id, "action", "calendar_research", {"company": value})
        await say(f"🔍 Researching *{value}*...")
        # [invoke the same research logic used by /research with company=value]

    elif action_type == "reschedule":
        log_engagement(user_id, "action", "calendar_reschedule", {"event_id": value})
        from tools.calendar import get_event_by_id, find_available_slots
        from formatters.calendar import format_reschedule_modal

        event = get_event_by_id(value)
        if not event:
            await say("❌ Meeting not found.")
            return

        start_dt = datetime.fromisoformat(event["start"])
        slots = find_available_slots(user_id, start_dt.strftime("%Y-%m-%d"), duration_minutes=30)
        modal = format_reschedule_modal(event, slots)

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=modal
        )
```

### A7. Add reschedule modal submit handler

```python
@app.view("reschedule_modal_submit")
async def handle_reschedule_submit(ack, body, view, client, say):
    """Process reschedule modal submission."""
    await ack()
    user_id = body["user"]["id"]
    event_id = view["private_metadata"]
    selected_time = view["state"]["values"]["new_time_block"]["new_time_select"]["selected_option"]["value"]

    if selected_time == "none":
        return

    new_start_str, new_end_str = selected_time.split("|")

    from tools.calendar import get_event_by_id, update_event_time
    from formatters.calendar import format_reschedule_confirmation

    event = get_event_by_id(event_id)
    if not event:
        return

    old_dt = datetime.fromisoformat(event["start"])
    old_time = old_dt.strftime("%-I:%M %p")

    # Build new ISO datetimes (same date, new time)
    date_str = old_dt.strftime("%Y-%m-%d")
    tz_offset = old_dt.strftime("%z")
    new_start_iso = f"{date_str}T{new_start_str}:00{tz_offset}"
    new_end_iso = f"{date_str}T{new_end_str}:00{tz_offset}"

    update_event_time(event_id, new_start_iso, new_end_iso)

    log_engagement(user_id, "action", "meeting_rescheduled", {"event_id": event_id})

    blocks, fallback = format_reschedule_confirmation(
        event["title"], old_time, f"{new_start_str}"
    )

    # Post confirmation via DM
    dm = await client.conversations_open(users=[user_id])
    await client.chat_postMessage(
        channel=dm["channel"]["id"],
        blocks=blocks,
        text=fallback
    )
```

---

## Part B: Email Send + Attachments (Feature #4)

### B1. Create `data/documents/` structure

Create the document library with placeholder files for demo:

```
data/documents/
├── brochures/
│   ├── product_overview.pdf        (placeholder: 1-page product overview)
│   └── enterprise_solution.pdf     (placeholder: enterprise-focused brochure)
├── case_studies/
│   ├── case_study_apex.pdf         (placeholder: Apex Systems success story)
│   └── case_study_cloudbridge.pdf  (placeholder: CloudBridge migration story)
└── pricing/
    └── pricing_guide_2026.pdf      (placeholder: pricing tiers)
```

For the POC, create small text files as placeholder PDFs (or simple 1-page PDFs). The demo flow shows the UX of selecting and attaching, not the actual document content.

### B2. Create `tools/documents.py`

```python
"""Document library for email attachments."""

import os
from pathlib import Path

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "documents")

def list_documents() -> list[dict]:
    """List all available documents in the library.
    Returns:
        List of {"name": str, "category": str, "path": str, "size_kb": int}
    """
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

def get_document_by_name(search: str) -> dict | None:
    """Find a document by partial name match.
    Args:
        search: Partial name to search for (case-insensitive)
    Returns:
        Document dict or None
    """
    docs = list_documents()
    search_lower = search.lower()
    return next(
        (d for d in docs if search_lower in d["name"].lower() or search_lower in d["filename"].lower()),
        None
    )
```

### B3. Update email action flow in `app.py`

Find the existing `create_gmail_draft` action handler and enhance it:

**Current flow:** User clicks "Create Gmail Draft" → draft is created via Gmail MCP.

**Enhanced flow:** User clicks "Email Actions ▾" overflow → options: "Send Now", "Create Draft", "Attach Document"

#### Update the email card formatter

In the formatter that builds the email draft card (likely in `formatters/email.py` or inline in `app.py`), replace the single "Create Gmail Draft" button with an overflow + primary action:

```python
def format_email_card(to_name, to_email, subject, body, attachments=None):
    """Format email draft card with send, draft, and attach actions."""
    attachment_text = ""
    if attachments:
        attachment_text = "\n📎 " + ", ".join(
            f"_{a['name']}_ ({a['size_kb']} KB)" for a in attachments
        )

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Draft Follow-Up: {to_name}*\n"
                    f"To: {to_name} ({to_email})\n"
                    f"Subject: {subject}\n\n"
                    f"{body}"
                    f"{attachment_text}"
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📤 Send Now"},
                    "style": "primary",
                    "action_id": "email_send_now",
                    "value": json.dumps({
                        "to": to_email,
                        "subject": subject,
                        "body": body,
                        "attachments": [a["path"] for a in (attachments or [])]
                    }),
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Send Email?"},
                        "text": {"type": "mrkdwn", "text": f"Send this email to {to_email}?"},
                        "confirm": {"type": "plain_text", "text": "Send"},
                        "deny": {"type": "plain_text", "text": "Cancel"}
                    }
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Gmail Draft"},
                    "action_id": "create_gmail_draft",
                    "value": json.dumps({
                        "to": to_email,
                        "subject": subject,
                        "body": body
                    })
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📎 Attach Document"},
                    "action_id": "email_attach_document",
                    "value": json.dumps({
                        "to": to_email,
                        "to_name": to_name,
                        "subject": subject,
                        "body": body,
                        "attachments": [a["path"] for a in (attachments or [])]
                    })
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 Regenerate"},
                    "action_id": "regenerate_email"
                }
            ]
        }
    ]
    return blocks, f"Draft email to {to_name}: {subject}"
```

### B4. Add `email_send_now` action handler

```python
@app.action("email_send_now")
async def handle_email_send_now(ack, body, say):
    """Send email via Gmail MCP (or mock)."""
    await ack()
    user_id = body["user"]["id"]
    payload = json.loads(body["actions"][0]["value"])

    log_engagement(user_id, "action", "email_send", {"to": payload["to"]})

    try:
        # Use Gmail MCP send_email tool
        # The exact MCP tool name depends on which Gmail MCP server is configured
        # Typical: gmail_send_email or send_email
        result = await call_mcp_tool("gmail", "send_email", {
            "to": payload["to"],
            "subject": payload["subject"],
            "body": payload["body"]
            # Note: attachment support depends on the MCP server capabilities
        })
        await say(f"✅ Email sent to {payload['to']}!")
    except Exception as e:
        # Fallback: create draft instead
        await say(
            f"⚠️ Could not send directly (Gmail send not configured). "
            f"Creating draft instead..."
        )
        # Fall back to existing create_draft logic
        # [call existing draft creation code]
```

**Note:** The exact Gmail MCP tool names depend on your configured MCP server. Check `mcp_setup.py` for the Gmail MCP configuration. If only `create_draft` is available, show a message explaining send isn't available yet and create the draft.

### B5. Add `email_attach_document` action handler

```python
@app.action("email_attach_document")
async def handle_email_attach_document(ack, body, client):
    """Show document picker modal for email attachments."""
    await ack()
    user_id = body["user"]["id"]
    email_data = json.loads(body["actions"][0]["value"])

    from tools.documents import list_documents

    docs = list_documents()

    # Build document picker options
    doc_options = [
        {
            "text": {"type": "plain_text", "text": f"{d['name']} ({d['category']})"},
            "value": d["path"]
        }
        for d in docs
    ]

    modal = {
        "type": "modal",
        "callback_id": "email_attach_submit",
        "title": {"type": "plain_text", "text": "Attach Document"},
        "submit": {"type": "plain_text", "text": "Attach"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": json.dumps(email_data),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Select a document to attach to your email to *{email_data.get('to_name', email_data['to'])}*"
                }
            },
            {
                "type": "input",
                "block_id": "doc_select_block",
                "element": {
                    "type": "static_select",
                    "action_id": "doc_select",
                    "placeholder": {"type": "plain_text", "text": "Choose a document"},
                    "options": doc_options if doc_options else [
                        {"text": {"type": "plain_text", "text": "No documents available"}, "value": "none"}
                    ]
                },
                "label": {"type": "plain_text", "text": "Document Library"}
            }
        ]
    }

    await client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.view("email_attach_submit")
async def handle_email_attach_submit(ack, body, view, say):
    """Process document attachment selection — rebuild the email card with attachment."""
    await ack()
    user_id = body["user"]["id"]
    email_data = json.loads(view["private_metadata"])
    selected_path = view["state"]["values"]["doc_select_block"]["doc_select"]["selected_option"]["value"]

    if selected_path == "none":
        return

    from tools.documents import list_documents

    # Find the selected document info
    docs = list_documents()
    doc = next((d for d in docs if d["path"] == selected_path), None)
    if not doc:
        return

    # Rebuild attachments list
    existing = email_data.get("attachments", [])
    # Prevent duplicates
    if selected_path not in existing:
        existing.append(selected_path)

    # Get full doc info for display
    attachment_infos = [
        next((d for d in docs if d["path"] == p), {"name": "Unknown", "size_kb": 0})
        for p in existing
    ]

    log_engagement(user_id, "action", "email_attach_document", {"doc": doc["name"]})

    # Re-render the email card with attachment info
    # [call format_email_card with attachments=attachment_infos]
    # Post the updated card to the channel
```

---

## Part C: Multi-Language Support (Feature #10)

### C1. Add language to user settings

In `db.py`, the `user_settings` table already has a flexible schema. Add language as a recognized setting key.

**Update the `/settings` modal** — add a language dropdown after the existing fields:

```python
# In the /settings command handler, add this block to the modal:
{
    "type": "input",
    "block_id": "language_block",
    "optional": True,
    "element": {
        "type": "static_select",
        "action_id": "language_select",
        "placeholder": {"type": "plain_text", "text": "Select language"},
        "initial_option": {
            "text": {"type": "plain_text", "text": current_language_name},
            "value": current_language_code
        },
        "options": [
            {"text": {"type": "plain_text", "text": "🇺🇸 English"}, "value": "en"},
            {"text": {"type": "plain_text", "text": "🇩🇪 Deutsch"}, "value": "de"},
            {"text": {"type": "plain_text", "text": "🇫🇷 Français"}, "value": "fr"},
            {"text": {"type": "plain_text", "text": "🇪🇸 Español"}, "value": "es"},
            {"text": {"type": "plain_text", "text": "🇧🇷 Português"}, "value": "pt"}
        ]
    },
    "label": {"type": "plain_text", "text": "AI Response Language"},
    "hint": {"type": "plain_text", "text": "AI responses will be in your selected language. Interface labels remain in English."}
}
```

### C2. Create language injection helper

Add to a shared utilities location (e.g., `utils/language.py` or directly in the prompt files):

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
    """Return a language instruction string to prepend/append to LLM prompts.
    Returns empty string for English (default).

    Args:
        user_id: Slack user ID
    Returns:
        Language instruction string, or "" for English
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

### C3. Inject into all LLM system prompts

This is a mechanical change. Every place a system prompt is built for the LLM, append the language instruction.

**Files to modify:**

1. **`prompts/coach_prompts.py`** — All coach system prompts (prep, roleplay, debrief, objection, strategy)
2. **`prompts/assistant_prompts.py`** — All assistant system prompts (research, email draft, deal analysis)
3. **`graphs/coach.py`** — If system prompts are built inline in graph nodes

**Pattern for each prompt:**

```python
from utils.language import get_language_instruction

# Wherever a system prompt is constructed:
system_prompt = BASE_PROMPT_TEXT  # existing prompt
system_prompt += get_language_instruction(user_id)  # add language instruction
```

**List of specific injection points** (search for these in the codebase):

| Location | Prompt Purpose |
|----------|---------------|
| Coach prep node | Meeting preparation |
| Roleplay system prompt | Buyer persona in roleplay |
| Debrief system prompt | Performance feedback |
| Objection handling prompt | Objection response coaching |
| Strategy prompt | Deal strategy advice |
| Research prompt | Company research summary |
| Email draft prompt | Draft email generation |
| Win/loss prompt | Win/loss analysis |
| `/ask` prompt | General Q&A answers |
| Skill gap recommendations | Practice suggestions |
| Scenario generation (Wave 4) | LLM-generated scenarios |

**Important:** The language instruction goes at the END of the system prompt so it takes priority. Do NOT translate Slack Block Kit labels, button text, or structured JSON output — only free-text LLM responses.

### C4. Save language setting on modal submit

In the `/settings` modal submit handler, extract and save the language choice:

```python
# In the settings modal submit handler:
language = view["state"]["values"]["language_block"]["language_select"]["selected_option"]["value"]
# Save to user settings via db.py:
save_user_settings(user_id, {"language": language})
```

---

## Part D: Market Shift Insights (Feature #12)

### D1. Create `tools/market_insights.py`

```python
"""Market insights — LLM-powered analysis of trends across CRM data,
coaching sessions, and research outputs."""

import json
from datetime import datetime, timedelta
from db import get_db


def gather_recent_data(days: int = 30) -> dict:
    """Gather all relevant data from the last N days for analysis.
    Args:
        days: Lookback window in days
    Returns:
        Dict with keys: deal_notes, coaching_sessions, objections_encountered
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with get_db() as conn:
        # Training/coaching sessions
        sessions = conn.execute("""
            SELECT user_id, scenario_type, overall_score, strengths, improvements,
                   methodology, created_at
            FROM training_sessions
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()

        # Engagement events (captures command usage patterns)
        events = conn.execute("""
            SELECT user_id, event_type, event_name, metadata, created_at
            FROM engagement_events
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()

        # CRM write audit log (notes logged to CRM)
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
    """Build the LLM analysis prompt from gathered data.
    Args:
        data: Output from gather_recent_data()
    Returns:
        Formatted prompt string
    """
    sessions_text = ""
    for s in data["coaching_sessions"][:50]:  # cap at 50 for context window
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

    # Count most-used commands
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
    """Parse LLM insights response into structured dict for potential caching.
    Args:
        llm_response: Raw LLM response text
    Returns:
        Dict with parsed sections
    """
    return {
        "raw_text": llm_response,
        "generated_at": datetime.now().isoformat(),
        "data_window_days": 30
    }
```

### D2. Create `formatters/market_insights.py`

```python
"""Block Kit formatter for market insights card."""

from datetime import datetime


def format_market_insights(insights_text: str, data_summary: dict) -> tuple[list[dict], str]:
    """Format the /market-insights output.
    Args:
        insights_text: LLM-generated insights text
        data_summary: Dict with counts — sessions_count, notes_count, reps_count
    Returns:
        (blocks, fallback_text) tuple
    """
    now = datetime.now().strftime("%b %-d, %Y")
    sessions_count = data_summary.get("sessions_count", 0)
    notes_count = data_summary.get("notes_count", 0)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 Market & Team Insights"}
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Based on {sessions_count} coaching sessions and "
                        f"{notes_count} CRM notes from the last 30 days · "
                        f"Generated {now}"
                    )
                }
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": insights_text[:2900]}  # Slack block limit ~3000 chars
        }
    ]

    # If insights text is long, add overflow sections
    if len(insights_text) > 2900:
        remaining = insights_text[2900:5800]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": remaining}
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🔄 Refresh Insights"},
                "action_id": "refresh_market_insights",
                "value": "refresh"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 Export Summary"},
                "action_id": "export_market_insights",
                "value": "export"
            }
        ]
    })

    return blocks, f"📊 Market Insights — {sessions_count} sessions, {notes_count} notes analyzed"
```

### D3. Add `/market-insights` command to `app.py`

```python
@app.command("/market-insights")
async def handle_market_insights(ack, command, say):
    """Generate market and team insights from recent data."""
    await ack()
    user_id = command["user_id"]

    log_engagement(user_id, "command", "market_insights")

    await say("📊 Analyzing recent sales data... this may take a moment.")

    from tools.market_insights import gather_recent_data, build_insights_prompt
    from formatters.market_insights import format_market_insights

    # Gather data
    data = gather_recent_data(days=30)

    data_summary = {
        "sessions_count": len(data["coaching_sessions"]),
        "notes_count": len(data["crm_notes"]),
    }

    # Build and send to LLM
    prompt = build_insights_prompt(data)

    # Call LLM (use the same pattern as other LLM calls in the codebase)
    # This will be an invoke on the coach/assistant graph or a direct LLM call
    insights_text = await call_llm(
        system_prompt="You are a sales analytics expert. Analyze the provided data and give actionable insights.",
        user_message=prompt,
        user_id=user_id  # for language injection
    )

    blocks, fallback = format_market_insights(insights_text, data_summary)
    await say(blocks=blocks, text=fallback)


@app.action("refresh_market_insights")
async def handle_refresh_insights(ack, body, say):
    """Re-run market insights analysis."""
    await ack()
    user_id = body["user"]["id"]
    log_engagement(user_id, "action", "refresh_market_insights")
    # Re-invoke the same logic
    await say("📊 Refreshing insights...")
    # [same logic as handle_market_insights]


@app.action("export_market_insights")
async def handle_export_insights(ack, body, say):
    """Export insights as formatted text (copy-pasteable)."""
    await ack()
    user_id = body["user"]["id"]
    log_engagement(user_id, "action", "export_market_insights")
    # For POC: just re-post the insights as a plain text message
    await say("📋 Export coming soon — for now, you can copy the insights above.")
```

---

## Part E: Private Practice Space (Feature #19)

**Already covered** by `UX-PHASE3-smart-defaults-modals-settings.md`. When `coaching_privacy: true` in user settings, all coaching interactions (roleplay, debrief, skill gaps) are sent as DMs instead of channel messages.

No additional instruction file needed. Implement per the UX Phase 3 instructions.

---

## Implementation Checklist

| # | Task | Files | Status |
|---|------|-------|--------|
| A1 | Create mock calendar JSON | `data/mock_calendar/events.json` | ⬜ |
| A2 | Create `tools/calendar.py` | `tools/calendar.py` | ⬜ |
| A3 | Create `formatters/calendar.py` | `formatters/calendar.py` | ⬜ |
| A4 | Add `/my-day` command | `app.py` | ⬜ |
| A5 | Enhance `/coach prep` auto-detect | `app.py` | ⬜ |
| A6 | Add calendar overflow handler | `app.py` | ⬜ |
| A7 | Add reschedule modal | `app.py` | ⬜ |
| B1 | Create document library | `data/documents/` | ⬜ |
| B2 | Create `tools/documents.py` | `tools/documents.py` | ⬜ |
| B3 | Update email card formatter | `formatters/email.py` | ⬜ |
| B4 | Add `email_send_now` handler | `app.py` | ⬜ |
| B5 | Add `email_attach_document` flow | `app.py` | ⬜ |
| C1 | Add language to settings modal | `app.py` | ⬜ |
| C2 | Create language injection helper | `utils/language.py` | ⬜ |
| C3 | Inject into all LLM prompts | `prompts/*.py`, `graphs/*.py` | ⬜ |
| C4 | Save language on submit | `app.py` | ⬜ |
| D1 | Create `tools/market_insights.py` | `tools/market_insights.py` | ⬜ |
| D2 | Create `formatters/market_insights.py` | `formatters/market_insights.py` | ⬜ |
| D3 | Add `/market-insights` command | `app.py` | ⬜ |
| E | Private practice space | (see UX Phase 3) | ⬜ |

## Testing Notes

- **Calendar:** Run `/my-day` → verify 3 events render with correct times and action buttons. Click "Prep for Meeting" → should trigger prep flow. Click "Reschedule" → modal should show available slots.
- **Email:** Trigger an email draft → verify "Send Now", "Create Gmail Draft", and "Attach Document" buttons all appear. Click "Attach Document" → verify document picker modal loads with files from `data/documents/`.
- **Language:** Set language to German via `/settings` → run `/coach prep NovaTech` → verify LLM response is in German. Verify Block Kit button labels remain in English.
- **Insights:** Run `/market-insights` → verify it pulls data from SQLite and generates an analysis. With no data, should still return gracefully ("Not enough data for insights yet").
