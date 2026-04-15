"""Utilities for handling call transcript ingestion."""

import os
import re
import json
from datetime import datetime

TRANSCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "mock_crm", "call_transcripts"
)

COACHING_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "playbooks", "coaching_from_transcripts"
)

MANIFEST_FILE = os.path.join(COACHING_SCRIPTS_DIR, "analysis_manifest.json")


def save_transcript(content: str, company: str, call_type: str, date: str = None) -> str:
    """Save a new transcript file and return the filepath.

    Args:
        content: The transcript text (markdown format)
        company: Company name (e.g., "NovaTech")
        call_type: Type of call (e.g., "discovery", "negotiation")
        date: Date string (YYYY-MM-DD), defaults to today

    Returns:
        Path to the saved transcript file
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Sanitize company name for filename
    safe_company = re.sub(r'[^\w]', '_', company.lower())
    filename = f"{call_type}_call_{safe_company}_{date}.md"
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)

    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def list_unanalyzed_transcripts() -> list:
    """List transcripts that haven't been analyzed yet."""
    analyzed = set()
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            manifest = json.load(f)
            analyzed = set(manifest.get("analyzed", {}).keys())

    if not os.path.exists(TRANSCRIPTS_DIR):
        return []

    all_transcripts = [
        f for f in os.listdir(TRANSCRIPTS_DIR)
        if f.endswith('.md') and not f.startswith('.')
    ]

    unanalyzed = [f for f in all_transcripts if f not in analyzed]
    return sorted(unanalyzed)


def list_all_transcripts() -> list:
    """List all transcript files."""
    if not os.path.exists(TRANSCRIPTS_DIR):
        return []

    return sorted([
        f for f in os.listdir(TRANSCRIPTS_DIR)
        if f.endswith('.md') and not f.startswith('.')
    ])


def get_analysis_status() -> dict:
    """Get the status of transcript analysis.

    Returns:
        Dict with 'total', 'analyzed', 'pending', and 'last_run'
    """
    all_transcripts = list_all_transcripts()
    unanalyzed = list_unanalyzed_transcripts()

    last_run = None
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            manifest = json.load(f)
            last_run = manifest.get("last_run")

    return {
        "total": len(all_transcripts),
        "analyzed": len(all_transcripts) - len(unanalyzed),
        "pending": len(unanalyzed),
        "pending_files": unanalyzed,
        "last_run": last_run,
    }


def anonymize_transcript(content: str, replacements: dict = None) -> str:
    """Anonymize a transcript by replacing sensitive information.

    Args:
        content: Raw transcript text
        replacements: Optional dict of {real_value: anonymized_value}

    Returns:
        Anonymized transcript text
    """
    # Default patterns to anonymize
    patterns = [
        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
        # Phone numbers (various formats)
        (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]'),
        (r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b', '[PHONE]'),
        # SSN patterns
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
        # Credit card patterns (basic)
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]'),
    ]

    result = content
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)

    # Apply custom replacements
    if replacements:
        for real, anon in replacements.items():
            result = result.replace(real, anon)

    return result


def get_transcript_metadata(filename: str) -> dict:
    """Extract metadata from a transcript filename.

    Args:
        filename: Transcript filename (e.g., "discovery_call_novatech_2026-02-18.md")

    Returns:
        Dict with 'call_type', 'company', 'date'
    """
    parts = filename.replace(".md", "").split("_")

    metadata = {
        "call_type": None,
        "company": None,
        "date": None,
    }

    # Find call type
    for i, part in enumerate(parts):
        if part == "call" and i > 0:
            metadata["call_type"] = parts[i - 1]
            if i + 1 < len(parts):
                metadata["company"] = parts[i + 1].title()
            break

    # Find date (last part that looks like YYYY-MM-DD)
    for part in reversed(parts):
        if re.match(r'\d{4}-\d{2}-\d{2}', part):
            metadata["date"] = part
            break

    return metadata
