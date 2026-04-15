"""User settings storage for SalesCoach AI."""
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
