"""
Calendar tools for /my-day command.
Loads mock calendar data and provides helper functions.
"""
import os
import json
from datetime import datetime, timedelta

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mock_calendar", "events.json")


def load_calendar_data():
    """Load calendar events from JSON file."""
    if not os.path.exists(DATA_PATH):
        return {"events": [], "user_calendar_map": {}}
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def get_user_events(user_id, date=None):
    """
    Get calendar events for a user on a specific date.

    Args:
        user_id: Slack user ID
        date: datetime.date object (defaults to today)

    Returns:
        List of event dicts sorted by start time
    """
    data = load_calendar_data()

    if date is None:
        date = datetime.now().date()

    # Get event IDs for this user
    user_event_ids = data.get("user_calendar_map", {}).get(user_id, [])

    # If no mapping exists, return all events (demo mode)
    if not user_event_ids:
        user_event_ids = [e["id"] for e in data.get("events", [])]

    events = []
    for event in data.get("events", []):
        if event["id"] in user_event_ids:
            # Parse event date
            event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            if event_start.date() == date:
                events.append(event)

    # Sort by start time
    events.sort(key=lambda e: e["start"])
    return events


def get_events_for_week(user_id, start_date=None):
    """
    Get calendar events for a user for the week starting from start_date.

    Args:
        user_id: Slack user ID
        start_date: datetime.date object (defaults to today)

    Returns:
        Dict with date keys and list of events as values
    """
    data = load_calendar_data()

    if start_date is None:
        start_date = datetime.now().date()

    end_date = start_date + timedelta(days=7)

    # Get event IDs for this user
    user_event_ids = data.get("user_calendar_map", {}).get(user_id, [])

    # If no mapping exists, return all events (demo mode)
    if not user_event_ids:
        user_event_ids = [e["id"] for e in data.get("events", [])]

    week_events = {}
    for event in data.get("events", []):
        if event["id"] in user_event_ids:
            event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            event_date = event_start.date()
            if start_date <= event_date < end_date:
                date_key = event_date.isoformat()
                if date_key not in week_events:
                    week_events[date_key] = []
                week_events[date_key].append(event)

    # Sort events within each day
    for date_key in week_events:
        week_events[date_key].sort(key=lambda e: e["start"])

    return week_events


def get_customer_meetings(user_id, days_ahead=7):
    """
    Get upcoming customer meetings for prep suggestions.

    Args:
        user_id: Slack user ID
        days_ahead: Number of days to look ahead

    Returns:
        List of customer meeting events with deal/company info
    """
    data = load_calendar_data()
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)

    user_event_ids = data.get("user_calendar_map", {}).get(user_id, [])
    if not user_event_ids:
        user_event_ids = [e["id"] for e in data.get("events", [])]

    meetings = []
    for event in data.get("events", []):
        if event["id"] in user_event_ids and event.get("type") == "customer_meeting":
            event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            event_date = event_start.date()
            if today <= event_date < end_date:
                meetings.append(event)

    meetings.sort(key=lambda e: e["start"])
    return meetings


def get_event_by_id(event_id):
    """Get a single event by ID."""
    data = load_calendar_data()
    for event in data.get("events", []):
        if event["id"] == event_id:
            return event
    return None
