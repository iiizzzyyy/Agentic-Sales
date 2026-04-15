# Wave 1C — CRM Write-Back via HubSpot Python SDK

Features #2 + #11: Enable writing notes, updating deals, and logging activities to HubSpot.

**Depends on:** Wave 1A (SQLite foundation)

---

## Step 1: Create `tools/crm_write.py`

Extract write patterns from `scripts/sync_data_to_hubspot.py` into a reusable module:

```python
"""
CRM write operations using HubSpot Python SDK.
Falls back to mock mode (SQLite + JSON append) when HUBSPOT_ACCESS_TOKEN is not set.
"""
import os
import json
import time
from datetime import datetime
from db import log_crm_write

# Try to import HubSpot SDK
try:
    from hubspot import HubSpot
    from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate as NoteInput
    from hubspot.crm.deals import SimplePublicObjectInput as DealUpdate
    HUBSPOT_SDK_AVAILABLE = True
except ImportError:
    HUBSPOT_SDK_AVAILABLE = False

# Association type IDs (from HubSpot docs)
ASSOC_NOTE_TO_DEAL = 214
ASSOC_NOTE_TO_CONTACT = 202

# Mock CRM data paths
MOCK_CRM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mock_crm")


def _get_hubspot_client():
    """Get HubSpot client if token is available."""
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if token and HUBSPOT_SDK_AVAILABLE:
        return HubSpot(access_token=token)
    return None


def is_mock_mode():
    """Check if we're in mock mode (no HubSpot token)."""
    return _get_hubspot_client() is None


def create_note(user_id, deal_id, deal_name, note_body, contact_id=None):
    """Create a note and associate it with a deal (and optionally a contact).

    Args:
        user_id: Slack user who created the note
        deal_id: HubSpot deal ID (or mock deal ID)
        deal_name: Human-readable deal name
        note_body: The note text
        contact_id: Optional HubSpot contact ID to associate

    Returns:
        dict with 'success', 'note_id', 'mode' (hubspot/mock)
    """
    client = _get_hubspot_client()

    if client:
        # --- HubSpot Mode ---
        try:
            timestamp_ms = int(datetime.now().timestamp() * 1000)
            result = client.crm.objects.notes.basic_api.create(
                simple_public_object_input_for_create=NoteInput(properties={
                    "hs_timestamp": str(timestamp_ms),
                    "hs_note_body": note_body,
                })
            )
            note_id = result.id

            # Associate note to deal
            try:
                client.crm.associations.v4.basic_api.create(
                    object_type="notes",
                    object_id=note_id,
                    to_object_type="deals",
                    to_object_id=deal_id,
                    association_spec=[{
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": ASSOC_NOTE_TO_DEAL
                    }]
                )
            except Exception:
                pass  # Association failure is non-critical

            # Associate note to contact if provided
            if contact_id:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="notes",
                        object_id=note_id,
                        to_object_type="contacts",
                        to_object_id=contact_id,
                        association_spec=[{
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": ASSOC_NOTE_TO_CONTACT
                        }]
                    )
                except Exception:
                    pass

            log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, note_id, "synced")
            return {"success": True, "note_id": note_id, "mode": "hubspot"}

        except Exception as e:
            log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, None, "failed")
            return {"success": False, "error": str(e), "mode": "hubspot"}

    else:
        # --- Mock Mode ---
        note_id = f"mock_note_{int(time.time())}"
        _append_mock_activity(deal_id, {
            "type": "NOTE",
            "body": note_body,
            "timestamp": datetime.now().isoformat(),
            "created_by": user_id,
        })
        log_crm_write(user_id, "note", "deal", deal_id, deal_name, note_body, note_id, "mock")
        return {"success": True, "note_id": note_id, "mode": "mock"}


def update_deal_stage(user_id, deal_id, deal_name, new_stage):
    """Update a deal's stage in HubSpot.

    Args:
        new_stage: HubSpot internal stage ID (e.g., 'contractsent', 'closedwon')
    """
    client = _get_hubspot_client()

    if client:
        try:
            client.crm.deals.basic_api.update(
                deal_id=deal_id,
                simple_public_object_input=DealUpdate(properties={
                    "dealstage": new_stage
                })
            )
            log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, deal_id, "synced")
            return {"success": True, "mode": "hubspot"}
        except Exception as e:
            log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, None, "failed")
            return {"success": False, "error": str(e), "mode": "hubspot"}
    else:
        _update_mock_deal_stage(deal_id, new_stage)
        log_crm_write(user_id, "stage_update", "deal", deal_id, deal_name, new_stage, deal_id, "mock")
        return {"success": True, "mode": "mock"}


def log_coaching_activity(user_id, deal_id, deal_name, session_type, score, scenario):
    """Log a coaching session as a CRM activity note on a deal."""
    note_body = (
        f"[COACHING] {session_type.title()} session completed\n"
        f"Scenario: {scenario}\n"
        f"Score: {score}/10\n"
        f"Logged automatically by SalesCoach AI"
    )
    return create_note(user_id, deal_id, deal_name, note_body)


# --- Mock Mode Helpers ---

def _append_mock_activity(deal_id, activity):
    """Append an activity to mock CRM deals.json."""
    deals_file = os.path.join(MOCK_CRM_DIR, "deals.json")
    try:
        with open(deals_file, "r") as f:
            deals = json.load(f)

        for deal in deals:
            if deal["id"] == deal_id:
                if "activities" not in deal:
                    deal["activities"] = []
                deal["activities"].append(activity)
                break

        with open(deals_file, "w") as f:
            json.dump(deals, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # Silent fail in mock mode


def _update_mock_deal_stage(deal_id, new_stage):
    """Update a deal's stage in mock CRM deals.json."""
    deals_file = os.path.join(MOCK_CRM_DIR, "deals.json")
    try:
        with open(deals_file, "r") as f:
            deals = json.load(f)

        for deal in deals:
            if deal["id"] == deal_id:
                deal["properties"]["dealstage"] = new_stage
                break

        with open(deals_file, "w") as f:
            json.dump(deals, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
```

## Step 2: Add `/log` Command

In `app.py`:

```python
from tools.crm_write import create_note, is_mock_mode

@app.command("/log")
def handle_log(ack, command, client, say):
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    text = command.get("text", "").strip()

    log_engagement(user_id, "command", command="/log")

    if not text:
        say(channel=channel_id, text="Usage: `/log [deal-name] [your note]`\nExample: `/log NovaTech Great call with Sarah — she's interested in the enterprise plan`")
        return

    # Parse: first word(s) before a clear separator are the deal name
    # Try to split on " - " or " — " first, then fall back to first word
    if " — " in text:
        deal_name, note_body = text.split(" — ", 1)
    elif " - " in text:
        deal_name, note_body = text.split(" - ", 1)
    else:
        # First word is deal name, rest is note
        parts = text.split(" ", 1)
        if len(parts) < 2:
            say(channel=channel_id, text="Please include both a deal name and your note.\nExample: `/log NovaTech — Great call, she wants a proposal`")
            return
        deal_name, note_body = parts[0], parts[1]

    deal_name = deal_name.strip()
    note_body = note_body.strip()

    # Look up the deal ID from mock CRM or HubSpot
    deal = _find_deal_by_name(deal_name)
    if not deal:
        say(channel=channel_id, text=f"Could not find a deal matching *{deal_name}*. Try `/deal {deal_name}` to search.")
        return

    deal_id = deal.get("id")
    actual_deal_name = deal.get("properties", {}).get("dealname", deal_name)

    # Create the note
    result = create_note(user_id, deal_id, actual_deal_name, note_body)

    mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
    if result["success"]:
        say(
            channel=channel_id,
            text=f"✅ Note logged on *{actual_deal_name}* ({mode_label}):\n> {note_body[:200]}"
        )
    else:
        say(
            channel=channel_id,
            text=f"⚠️ Failed to log note: {result.get('error', 'Unknown error')}. Try again or contact support."
        )
```

## Step 3: Wire Up "Log Note" Button on Deal Cards

Find the existing `log_note` action handler in `app.py` (or create it if it's a noop). Replace with:

```python
@app.action("log_note")
def handle_log_note(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    deal_name = body["actions"][0]["value"]

    # Open a modal for the note text
    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "log_note_modal",
            "title": {"type": "plain_text", "text": "Log Note"},
            "submit": {"type": "plain_text", "text": "Save to CRM"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps({"deal_name": deal_name}),
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Deal:* {deal_name}"}
                },
                {
                    "type": "input",
                    "block_id": "note_input_block",
                    "label": {"type": "plain_text", "text": "Note"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "note_text",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What happened? Key takeaways, next steps, decisions made..."},
                    }
                },
            ]
        }
    )


@app.view("log_note_modal")
def handle_log_note_submit(ack, body, client, view):
    ack()
    user_id = body["user"]["id"]
    metadata = json.loads(view["private_metadata"])
    deal_name = metadata["deal_name"]
    note_text = view["state"]["values"]["note_input_block"]["note_text"]["value"]

    deal = _find_deal_by_name(deal_name)
    if not deal:
        return

    deal_id = deal.get("id")
    result = create_note(user_id, deal_id, deal_name, note_text)

    # DM confirmation to the user
    dm = client.conversations_open(users=[user_id])
    mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
    if result["success"]:
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=f"✅ Note saved on *{deal_name}* ({mode_label}):\n> {note_text[:200]}"
        )
```

## Step 4: Add "Log to CRM" Button on Roleplay Debrief

In the roleplay debrief handler, after saving the training session, add a "Log to CRM" button to the debrief card. In `formatters/coach.py`, update `format_roleplay_debrief` to include:

```python
# Add to the actions block in the debrief card:
{
    "type": "button",
    "text": {"type": "plain_text", "text": "Log to CRM", "emoji": True},
    "action_id": "log_coaching_to_crm",
    "value": json.dumps({
        "session_type": "roleplay",
        "score": overall_score,
        "scenario": scenario,
        "company": company,
    }),
}
```

Then add the action handler:

```python
@app.action("log_coaching_to_crm")
def handle_log_coaching_to_crm(ack, body, client):
    ack()
    data = json.loads(body["actions"][0]["value"])
    user_id = body["user"]["id"]
    channel = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    company = data.get("company", "")
    if not company:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text="No company associated with this session. Use `/log [deal] [note]` instead."
        )
        return

    # Find deal by company name
    deal = _find_deal_by_company(company)
    if not deal:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text=f"No deal found for *{company}*. Use `/log [deal] [note]` to log manually."
        )
        return

    deal_id = deal.get("id")
    deal_name = deal.get("properties", {}).get("dealname", company)

    from tools.crm_write import log_coaching_activity
    result = log_coaching_activity(
        user_id, deal_id, deal_name,
        data.get("session_type", "roleplay"),
        data.get("score", "N/A"),
        data.get("scenario", ""),
    )

    mode_label = "HubSpot" if result.get("mode") == "hubspot" else "locally"
    if result["success"]:
        client.chat_postEphemeral(
            channel=channel, user=user_id,
            text=f"✅ Coaching session logged on *{deal_name}* ({mode_label})"
        )
```

## Step 5: Create `formatters/crm_write.py`

```python
"""Block Kit formatters for CRM write confirmations."""
from formatters.helpers import timestamp


def format_note_confirmation(deal_name, note_body, mode):
    """Simple confirmation after logging a note."""
    mode_label = "Synced to HubSpot" if mode == "hubspot" else "Saved locally"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"✅ *Note logged on {deal_name}*\n> {note_body[:300]}"}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{mode_label} · SalesCoach AI · {timestamp()}"}]
        }
    ]
    fallback = f"Note logged on {deal_name}: {note_body[:100]}"
    return blocks, fallback
```

## DO NOT
- Do not import `hubspot` at module level without try/except — it may not be installed
- Do not let CRM write failures crash the app — always wrap in try/except
- Do not write to HubSpot without logging to the `crm_writes` SQLite table (audit trail)
- Do not bypass mock mode — when no token is set, writes go to JSON + SQLite only

## Testing
1. Without `HUBSPOT_ACCESS_TOKEN`: `/log NovaTech — Great call with Sarah` → should save to mock CRM JSON and SQLite
2. Check: `sqlite3 data/salescoach.db "SELECT * FROM crm_writes ORDER BY timestamp DESC LIMIT 5"`
3. With `HUBSPOT_ACCESS_TOKEN`: Same command → should create a real HubSpot note
4. Deal card → click "Log Note" → modal appears → type note → submit → confirmation DM
5. Complete a roleplay → debrief card shows "Log to CRM" button → click → coaching logged on the deal
