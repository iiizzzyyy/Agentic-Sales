# Add User Ownership & Role-Based Filtering — Claude Code Instructions

**Goal:** Map Slack users to HubSpot record owners so sales reps see only their own records, while sales managers see everything.

**Approach:**
- **Option A — Email matching** for reps: Slack email → HubSpot owner email → `hubspot_owner_id`
- **Option 3 — Config-based** for managers: A JSON config lists manager Slack user IDs who get unfiltered access

---

## CONTEXT — Current State

**Deals already have owner IDs.** Every deal in `data/mock_crm/deals.json` has `properties.hubspot_owner_id` (values: `owner_100` through `owner_105`). Distribution: owner_101 has 7 deals, owner_103 has 5, owner_102 has 3, owner_104 has 2, owner_100 has 2, owner_105 has 1.

**No owners lookup file exists.** We need to create one mapping owner IDs to names and emails.

**Contacts and companies don't have owner IDs.** We'll derive contact/company access from deal ownership — if you own a deal, you can see the associated company and contacts.

**Commands that need filtering:**
- `/pipeline` — shows all open deals (uses `mock_crm.get_all_open_deals()`)
- `/forecast` — shows forecast across deals (uses `mock_crm.get_all_open_deals()`, `get_stale_deals()`, `get_overdue_deals()`)
- `/alerts` — shows pipeline alerts (uses `get_stale_deals()`, `get_overdue_deals()`, `get_all_open_deals()`)
- `/win-loss` — shows win/loss analysis (uses `load_mock_crm()["deals"]`)
- `/deal` — deep dive into a specific deal (uses RAG + `mock_crm.search_deal()`)
- `/research` — company research (uses RAG + mock CRM)

**Commands that do NOT need filtering** (they're content-based, not record-based):
- `/coach`, `/objection`, `/ask`, `/battlecard`, `/competitor`, `/persona` — these are knowledge/AI tools, not CRM record views
- `/email-sequence`, `/draft-email`, `/followup` — these generate content
- `/training`, `/team` — training is separate from CRM ownership

---

## READ BEFORE EDITING

- `tools/mock_crm.py` — all CRM data functions (full file)
- `app.py` lines 989-1120 — `handle_pipeline` and `extract_pipeline_data`
- `app.py` lines 3908-3960 — `handle_forecast`
- `app.py` lines 3769-3810 — `handle_alerts` and `build_pipeline_alerts`
- `app.py` lines 3958-4060 — `handle_win_loss`
- `app.py` lines 677-770 — `handle_deal`
- `db.py` — database schema (for the new `user_roles` table)

---

## Phase 1: Create Owners Data File

Create a new file `data/mock_crm/owners.json`:

```json
[
  {
    "id": "owner_100",
    "email": "sarah.chen@ourcompany.com",
    "firstName": "Sarah",
    "lastName": "Chen",
    "role": "Senior Account Executive"
  },
  {
    "id": "owner_101",
    "email": "jordan.rivera@ourcompany.com",
    "firstName": "Jordan",
    "lastName": "Rivera",
    "role": "Account Executive"
  },
  {
    "id": "owner_102",
    "email": "morgan.taylor@ourcompany.com",
    "firstName": "Morgan",
    "lastName": "Taylor",
    "role": "Account Executive"
  },
  {
    "id": "owner_103",
    "email": "alex.kim@ourcompany.com",
    "firstName": "Alex",
    "lastName": "Kim",
    "role": "Account Executive"
  },
  {
    "id": "owner_104",
    "email": "taylor.nguyen@ourcompany.com",
    "firstName": "Taylor",
    "lastName": "Nguyen",
    "role": "Account Executive"
  },
  {
    "id": "owner_105",
    "email": "casey.brooks@ourcompany.com",
    "firstName": "Casey",
    "lastName": "Brooks",
    "role": "Account Executive"
  }
]
```

---

## Phase 2: Create User Access Module

Create a new file `tools/user_access.py`:

```python
"""
User access control — maps Slack users to HubSpot owners and determines role.

Approach:
  - Email matching: Slack user email → HubSpot owner email → owner_id
  - Config-based managers: A JSON config lists Slack user IDs with manager access
  - Default: if no email match and not a manager → show "not linked" message
"""

import os
import json
from functools import lru_cache

# ── Config paths ──
OWNERS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mock_crm", "owners.json")
MANAGERS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "user_roles.json")

# ── In-memory cache for Slack email lookups ──
_slack_email_cache: dict[str, str] = {}


@lru_cache(maxsize=1)
def _load_owners() -> list[dict]:
    """Load HubSpot owners from JSON file."""
    if os.path.exists(OWNERS_PATH):
        with open(OWNERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


@lru_cache(maxsize=1)
def _load_managers_config() -> dict:
    """Load manager config from JSON file."""
    if os.path.exists(MANAGERS_CONFIG_PATH):
        with open(MANAGERS_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"managers": [], "default_role": "rep"}


def get_owner_by_email(email: str) -> dict | None:
    """Find a HubSpot owner by email address."""
    email_lower = email.lower()
    for owner in _load_owners():
        if owner.get("email", "").lower() == email_lower:
            return owner
    return None


def get_owner_by_id(owner_id: str) -> dict | None:
    """Find a HubSpot owner by ID."""
    for owner in _load_owners():
        if owner.get("id") == owner_id:
            return owner
    return None


def resolve_slack_user(slack_user_id: str, client=None) -> dict:
    """
    Resolve a Slack user to their CRM role and owner ID.

    Args:
        slack_user_id: The Slack user ID (e.g., "U07ABC123")
        client: Slack WebClient instance (needed for email lookup)

    Returns:
        dict with keys:
          - role: "manager" | "rep" | "unlinked"
          - owner_id: HubSpot owner_id (or None if manager/unlinked)
          - owner_name: Display name (or None)
          - slack_email: The Slack user's email (or None if lookup failed)
    """
    config = _load_managers_config()

    # 1. Check if user is a configured manager
    if slack_user_id in config.get("managers", []):
        return {
            "role": "manager",
            "owner_id": None,
            "owner_name": None,
            "slack_email": None,
        }

    # 2. Look up Slack email (with cache)
    slack_email = _get_slack_email(slack_user_id, client)
    if not slack_email:
        return {
            "role": "unlinked",
            "owner_id": None,
            "owner_name": None,
            "slack_email": None,
        }

    # 3. Match email to HubSpot owner
    owner = get_owner_by_email(slack_email)
    if owner:
        return {
            "role": "rep",
            "owner_id": owner["id"],
            "owner_name": f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip(),
            "slack_email": slack_email,
        }

    # 4. No match — unlinked user
    return {
        "role": "unlinked",
        "owner_id": None,
        "owner_name": None,
        "slack_email": slack_email,
    }


def _get_slack_email(slack_user_id: str, client=None) -> str | None:
    """Get email for a Slack user (cached)."""
    if slack_user_id in _slack_email_cache:
        return _slack_email_cache[slack_user_id]

    if not client:
        return None

    try:
        result = client.users_info(user=slack_user_id)
        email = result["user"]["profile"].get("email")
        if email:
            _slack_email_cache[slack_user_id] = email
        return email
    except Exception:
        return None


def is_manager(slack_user_id: str) -> bool:
    """Quick check if a user is a configured manager."""
    config = _load_managers_config()
    return slack_user_id in config.get("managers", [])


def clear_caches():
    """Clear all caches (call after config changes)."""
    _load_owners.cache_clear()
    _load_managers_config.cache_clear()
    _slack_email_cache.clear()
```

---

## Phase 3: Create Manager Config File

Create `data/user_roles.json`:

```json
{
  "managers": [],
  "default_role": "rep",
  "_comment": "Add Slack user IDs to the managers list. Managers see all records. Everyone else is matched by email to a HubSpot owner."
}
```

This starts empty. Managers are added via a new `/settings` subcommand (Phase 7) or by manually editing the file.

---

## Phase 4: Add Owner-Filtered Functions to `tools/mock_crm.py`

Add these functions to the bottom of `tools/mock_crm.py`. They wrap existing functions with optional `owner_id` filtering. **Do NOT modify the existing functions** — the new ones call them internally.

```python
# ──────────────────────────────────────────────
# Owner-filtered wrappers
# ──────────────────────────────────────────────

def _filter_by_owner(deals: list[dict], owner_id: str | None) -> list[dict]:
    """Filter a list of deals by hubspot_owner_id. If owner_id is None, return all (manager mode)."""
    if owner_id is None:
        return deals
    return [d for d in deals if d.get("properties", {}).get("hubspot_owner_id") == owner_id]


def get_all_open_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get open deals, optionally filtered by owner. None = all (manager)."""
    return _filter_by_owner(get_all_open_deals(), owner_id)


def get_stale_deals_for_user(stale_days: int = 14, owner_id: str | None = None) -> list[dict]:
    """Get stale deals, optionally filtered by owner."""
    return _filter_by_owner(get_stale_deals(stale_days), owner_id)


def get_overdue_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get overdue deals, optionally filtered by owner."""
    return _filter_by_owner(get_overdue_deals(), owner_id)


def get_all_deals_for_user(owner_id: str | None = None) -> list[dict]:
    """Get ALL deals (including closed), optionally filtered by owner."""
    crm_data = load_mock_crm()
    return _filter_by_owner(crm_data["deals"], owner_id)


def get_companies_for_user(owner_id: str | None = None) -> list[dict]:
    """Get companies that have at least one deal owned by this user.
    If owner_id is None, return all companies (manager mode).
    """
    if owner_id is None:
        return load_mock_crm()["companies"]

    # Find company IDs from user's deals
    user_deals = get_all_deals_for_user(owner_id)
    company_ids = set()
    for deal in user_deals:
        company_id = deal.get("associations", {}).get("company")
        if company_id:
            company_ids.add(company_id)

    # Return matching companies
    return [c for c in load_mock_crm()["companies"] if c.get("id") in company_ids]


def search_deal_for_user(name: str, owner_id: str | None = None) -> dict | None:
    """Search for a deal by name, respecting ownership.
    If owner_id is None, return any match (manager mode).
    """
    deal = search_deal(name)
    if deal is None:
        return None
    if owner_id is None:
        return deal
    if deal.get("properties", {}).get("hubspot_owner_id") == owner_id:
        return deal
    return None
```

Also add an `_owners` cache and loader to `load_mock_crm()`. Add these lines right after the existing data loading (after line ~46):

```python
    # Load owners
    owners_path = os.path.join(MOCK_CRM_DIR, "owners.json")
    if os.path.exists(owners_path):
        with open(owners_path, encoding="utf-8") as f:
            _crm_data["owners"] = json.load(f)
    else:
        _crm_data["owners"] = []
```

---

## Phase 5: Add `owner_id` to Contacts and Companies Data

Contacts and companies don't have `hubspot_owner_id` fields. We need to add `hubspot_owner_id` to each contact record in `data/mock_crm/contacts.json`, based on which company they belong to and which rep owns deals for that company.

**Logic:** For each contact, find the company they belong to (`associations.company_id`), then find deals for that company, and assign the contact to the same owner as the first deal found.

Rather than manually editing every contact, add a **data enrichment function** to `tools/mock_crm.py` that computes ownership at load time:

```python
def _enrich_contact_owners():
    """Add hubspot_owner_id to contacts based on their company's deal owners."""
    crm_data = load_mock_crm()

    # Build company → owner map (use the first deal's owner for each company)
    company_owner_map = {}
    for deal in crm_data["deals"]:
        company_id = deal.get("associations", {}).get("company")
        if company_id and company_id not in company_owner_map:
            owner_id = deal.get("properties", {}).get("hubspot_owner_id")
            if owner_id:
                company_owner_map[company_id] = owner_id

    # Enrich contacts
    for contact in crm_data["contacts"]:
        if "hubspot_owner_id" not in contact.get("properties", {}):
            company_id = contact.get("associations", {}).get("company_id") or contact.get("associations", {}).get("company")
            if company_id and company_id in company_owner_map:
                contact.setdefault("properties", {})["hubspot_owner_id"] = company_owner_map[company_id]
```

Call `_enrich_contact_owners()` at the end of `load_mock_crm()`, right before the `return _crm_data` line:

```python
    _enrich_contact_owners()
    return _crm_data
```

---

## Phase 6: Create `get_user_context` Helper in `app.py`

Add a helper function near the top of `app.py` (after the imports, around line ~100) that resolves the current user's access context. This is the main entry point that command handlers will call.

```python
from tools.user_access import resolve_slack_user, is_manager


def get_user_context(user_id: str, client=None) -> dict:
    """Resolve the current Slack user's CRM access context.

    Returns:
        dict with keys:
          - role: "manager" | "rep" | "unlinked"
          - owner_id: str | None — the HubSpot owner ID (None for managers)
          - owner_name: str | None
          - filter_owner_id: str | None — pass this to _for_user() functions
              * For managers: None (sees everything)
              * For reps: their owner_id (sees only their records)
              * For unlinked: "__none__" (sees nothing — triggers a helpful message)
    """
    access = resolve_slack_user(user_id, client)

    if access["role"] == "manager":
        filter_id = None  # None means "no filter" → sees everything
    elif access["role"] == "rep":
        filter_id = access["owner_id"]
    else:
        filter_id = "__none__"  # Will match no records

    return {
        **access,
        "filter_owner_id": filter_id,
    }
```

Also add a reusable "unlinked user" message function:

```python
def _send_unlinked_message(say, channel_id, slack_email=None):
    """Send a helpful message when a user's Slack email doesn't match any HubSpot owner."""
    if slack_email:
        msg = (
            f":warning: Your Slack email (`{slack_email}`) doesn't match any HubSpot record owner.\n"
            "Ask a sales manager to run `/settings add-manager @you` to give you manager access, "
            "or update your HubSpot owner email to match your Slack email."
        )
    else:
        msg = (
            ":warning: Couldn't look up your Slack email. "
            "Make sure your Slack profile has an email address set."
        )
    say(channel=channel_id, text=msg)
```

---

## Phase 7: Update Command Handlers

Now update the 4 main commands that need owner filtering. The pattern for each is:

1. Call `get_user_context(user_id, client)` at the start
2. If role is `"unlinked"`, send the helper message and return
3. Pass `filter_owner_id` to the `_for_user()` mock CRM functions

### 7A. Update `/pipeline` handler

In `handle_pipeline` (around line 989), after the `ack()` call:

**ADD** after `log_engagement(...)`:

```python
    # Resolve user access
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return
```

Then find where `extract_pipeline_data()` is called (line ~1112). This function uses RAG, so we can't easily filter it. Instead, add a **post-filter** approach:

Find the section where deals are processed after `extract_pipeline_data()` returns, and also find any calls to `mock_crm.get_all_open_deals()`. Replace them with `mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])`.

**NOTE:** The `/pipeline` handler is complex. If it uses RAG-based `extract_pipeline_data()` for deal extraction, add a secondary path that uses `mock_crm.get_all_open_deals_for_user()` directly when the CRM has data:

```python
    # Try direct CRM first (supports owner filtering)
    open_deals = mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])
    if open_deals:
        # Use direct CRM data instead of RAG
        # ... format and display
    else:
        # Fall back to RAG path (existing behavior, no owner filtering)
        # ... existing extract_pipeline_data() path
```

### 7B. Update `/forecast` handler

In `handle_forecast` (around line 3908), find these three lines:

```python
        all_deals = mock_crm.get_all_open_deals()
        stale = mock_crm.get_stale_deals(stale_days=14)
        overdue = mock_crm.get_overdue_deals()
```

**REPLACE WITH:**

```python
        ctx = get_user_context(user_id, client)
        if ctx["role"] == "unlinked":
            _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
            return

        all_deals = mock_crm.get_all_open_deals_for_user(ctx["filter_owner_id"])
        stale = mock_crm.get_stale_deals_for_user(stale_days=14, owner_id=ctx["filter_owner_id"])
        overdue = mock_crm.get_overdue_deals_for_user(ctx["filter_owner_id"])
```

### 7C. Update `/alerts` handler

In the `build_pipeline_alerts` function (around line 3769), find:

```python
        stale = mock_crm.get_stale_deals(stale_days=14)
```
```python
        overdue = mock_crm.get_overdue_deals()
```
```python
        all_open = mock_crm.get_all_open_deals()
```

These need to receive an `owner_id` parameter. Change the function signature:

```python
def build_pipeline_alerts(owner_id=None):
```

And replace the three calls:

```python
        stale = mock_crm.get_stale_deals_for_user(stale_days=14, owner_id=owner_id)
        overdue = mock_crm.get_overdue_deals_for_user(owner_id=owner_id)
        all_open = mock_crm.get_all_open_deals_for_user(owner_id=owner_id)
```

Then update `handle_alerts` to pass the owner context:

```python
    ctx = get_user_context(user_id, client)
    if ctx["role"] == "unlinked":
        _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
        return
    alerts = build_pipeline_alerts(owner_id=ctx["filter_owner_id"])
```

### 7D. Update `/win-loss` handler

In `handle_win_loss` (around line 3958), find the line that loads all deals:

```python
        all_deals = mock_crm.load_mock_crm()["deals"]
```

**REPLACE WITH:**

```python
        ctx = get_user_context(user_id, client)
        if ctx["role"] == "unlinked":
            _send_unlinked_message(say, channel_id, ctx.get("slack_email"))
            return
        all_deals = mock_crm.get_all_deals_for_user(ctx["filter_owner_id"])
```

---

## Phase 8: Add `/settings add-manager` and `/settings remove-manager` Subcommands

In `handle_settings` (around line 5581), the settings command currently opens a modal. Add subcommand routing for manager management.

Add this logic **before** the modal open (at the start of the handler, after parsing `text`):

```python
    text = command.get("text", "").strip()

    # Manager management subcommands
    if text.startswith("add-manager"):
        _settings_add_manager(say, channel_id, user_id, text, client)
        return
    elif text.startswith("remove-manager"):
        _settings_remove_manager(say, channel_id, user_id, text, client)
        return
    elif text == "list-managers":
        _settings_list_managers(say, channel_id)
        return
```

Then add the helper functions:

```python
def _settings_add_manager(say, channel_id, user_id, text, client):
    """Add a user as a sales manager."""
    from tools.user_access import _load_managers_config, clear_caches
    import re

    # Only existing managers (or first-time setup) can add managers
    config = _load_managers_config()
    if config["managers"] and not is_manager(user_id):
        say(channel=channel_id, text=":no_entry: Only existing managers can add new managers.")
        return

    # Parse @mention from text: "add-manager <@U07ABC123|username>"
    match = re.search(r"<@(\w+)", text)
    if not match:
        say(channel=channel_id, text="Usage: `/settings add-manager @username`")
        return

    target_user_id = match.group(1)

    # Load, modify, save
    config_path = os.path.join("data", "user_roles.json")
    if target_user_id not in config["managers"]:
        config["managers"].append(target_user_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        clear_caches()
        say(channel=channel_id, text=f":white_check_mark: <@{target_user_id}> added as a sales manager. They can now see all CRM records.")
    else:
        say(channel=channel_id, text=f"<@{target_user_id}> is already a manager.")


def _settings_remove_manager(say, channel_id, user_id, text, client):
    """Remove a user from the managers list."""
    from tools.user_access import _load_managers_config, clear_caches
    import re

    if not is_manager(user_id):
        say(channel=channel_id, text=":no_entry: Only managers can modify manager settings.")
        return

    match = re.search(r"<@(\w+)", text)
    if not match:
        say(channel=channel_id, text="Usage: `/settings remove-manager @username`")
        return

    target_user_id = match.group(1)

    config_path = os.path.join("data", "user_roles.json")
    config = _load_managers_config()
    if target_user_id in config["managers"]:
        config["managers"].remove(target_user_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        clear_caches()
        say(channel=channel_id, text=f":white_check_mark: <@{target_user_id}> removed from managers. They'll now see only their own records.")
    else:
        say(channel=channel_id, text=f"<@{target_user_id}> is not currently a manager.")


def _settings_list_managers(say, channel_id):
    """List current managers."""
    from tools.user_access import _load_managers_config

    config = _load_managers_config()
    managers = config.get("managers", [])
    if managers:
        manager_list = "\n".join([f"• <@{uid}>" for uid in managers])
        say(channel=channel_id, text=f"*Current Sales Managers:*\n{manager_list}")
    else:
        say(channel=channel_id, text="No managers configured yet. Run `/settings add-manager @username` to add the first one.")
```

---

## Phase 9: Add Context Banner to Filtered Views

When a rep sees filtered data, show a subtle context banner so they know what they're seeing. Add this helper:

```python
def _ownership_context_block(ctx: dict) -> list:
    """Return a Block Kit context element showing whose data is being displayed."""
    if ctx["role"] == "manager":
        return [{
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": ":eyes: *Manager view* — showing all records"}]
        }]
    elif ctx["role"] == "rep" and ctx.get("owner_name"):
        return [{
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":bust_in_silhouette: Showing records owned by *{ctx['owner_name']}*"}]
        }]
    return []
```

Use this in command handlers by prepending the context block to the `blocks` list before sending:

```python
    blocks = _ownership_context_block(ctx) + blocks
```

Add this to `/pipeline`, `/forecast`, `/alerts`, and `/win-loss`.

---

## TESTING

### Setup
1. Add your Slack user ID to `data/user_roles.json` → `managers` list (so you can see everything during development)
2. Make sure `data/mock_crm/owners.json` exists with the 6 owners

### Test Cases

1. **Manager view:** Run `/pipeline` — should show all 20 deals with "Manager view" banner
2. **Rep view (simulated):** Temporarily remove yourself from managers list. If your Slack email matches an owner, you'll see only that owner's deals
3. **Unlinked user:** If email doesn't match, should see the "email doesn't match" message
4. **`/settings add-manager @user`** — should add user to managers list
5. **`/settings list-managers`** — should show current managers
6. **`/settings remove-manager @user`** — should remove and they see filtered data
7. **`/forecast`** — should show forecast only for user's deals (or all for managers)
8. **`/alerts`** — should show alerts only for user's deals (or all for managers)
9. **`/win-loss`** — should show win/loss only for user's deals (or all for managers)

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `data/mock_crm/owners.json` | New file — 6 owner records with email, name, role |
| CREATE | `data/user_roles.json` | New file — empty managers list |
| CREATE | `tools/user_access.py` | New file — `resolve_slack_user()`, `is_manager()`, email matching |
| EDIT | `tools/mock_crm.py` | Add `_filter_by_owner`, `get_all_open_deals_for_user`, `get_stale_deals_for_user`, `get_overdue_deals_for_user`, `get_all_deals_for_user`, `get_companies_for_user`, `search_deal_for_user`. Add owners loading. Add `_enrich_contact_owners()` |
| EDIT | `app.py` | Add `get_user_context()`, `_send_unlinked_message()`, `_ownership_context_block()`. Update `handle_pipeline`, `handle_forecast`, `handle_alerts`, `handle_win_loss`, `build_pipeline_alerts`. Add `/settings add-manager`, `remove-manager`, `list-managers` |

---

## IMPORTANT NOTES

- **Do NOT break existing behavior.** All `_for_user()` functions accept `owner_id=None` which means "no filter" (manager mode). If anything goes wrong with user resolution, default to showing all data rather than showing nothing.
- **The `client` parameter** is needed for Slack email lookup (`client.users_info()`). Most command handlers already have `client` in their args. If one doesn't, add it to the handler signature — Slack Bolt passes it automatically.
- **Caching:** `_get_slack_email` caches email lookups in memory. `_load_owners` and `_load_managers_config` use `lru_cache`. Call `clear_caches()` after config changes.
- **First-time setup:** The first `/settings add-manager @user` call is allowed even when the managers list is empty (bootstrap case). After that, only existing managers can add new ones.
