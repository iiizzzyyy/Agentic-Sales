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
