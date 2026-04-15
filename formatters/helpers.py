"""Shared utilities for Block Kit formatting."""
from datetime import datetime


def timestamp():
    """Return a short timestamp for context blocks."""
    return datetime.now().strftime("%b %d, %Y at %I:%M %p")


def truncate(text: str, max_length: int = 120, indicator: str = "...") -> str:
    """Truncate text with a visible indicator, breaking at word boundaries.

    Args:
        text: Text to truncate
        max_length: Maximum character length
        indicator: What to append when truncated (default "...")

    Returns:
        Truncated text with indicator, or original if short enough
    """
    if not text or len(text) <= max_length:
        return text
    # Break at word boundary to avoid cutting mid-word
    truncated = text[:max_length - len(indicator)]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + indicator


def format_currency(amount) -> str:
    """Format a number as currency."""
    try:
        return f"${int(float(amount)):,}"
    except (ValueError, TypeError):
        return "N/A"
