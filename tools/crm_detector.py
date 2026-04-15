"""
Detect CRM-loggable content in Slack messages.
Two-stage approach:
  1. Fast keyword check (no LLM cost) — filters out 95% of messages
  2. LLM classification + extraction (only on keyword hits) — confirms and structures
"""
import re
import json
from typing import Optional

# ── Stage 1: Keyword pre-filter ──────────────────────────────────────────

# Company names get loaded once from CRM data (mock or live)
_company_names_cache: list[str] | None = None


def _load_company_names() -> list[str]:
    """Load known company names from CRM data for matching.
    Cache after first load."""
    global _company_names_cache
    if _company_names_cache is not None:
        return _company_names_cache

    try:
        # Try mock CRM first (same source as /research and /deal)
        import os
        import json as json_mod
        companies_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "mock_crm", "companies.json"
        )
        if os.path.exists(companies_path):
            with open(companies_path) as f:
                data = json_mod.load(f)
            # Extract company names — adjust key based on actual JSON structure
            if isinstance(data, list):
                _company_names_cache = [
                    c.get("name", c.get("properties", {}).get("name", ""))
                    for c in data if c.get("name") or c.get("properties", {}).get("name")
                ]
            else:
                _company_names_cache = []
        else:
            _company_names_cache = []
    except Exception:
        _company_names_cache = []

    return _company_names_cache


def reload_company_names():
    """Force reload of company names cache."""
    global _company_names_cache
    _company_names_cache = None
    return _load_company_names()


# Action keywords that suggest a sales interaction happened
ACTION_KEYWORDS = [
    # Meeting/call indicators
    r"\b(?:just|finished|had|completed|wrapped)\s+(?:a\s+)?(?:call|meeting|demo|chat|session|sync)\b",
    r"\b(?:got off|came out of|back from)\s+(?:a\s+)?(?:call|meeting|demo)\b",
    r"\b(?:spoke|talked|met|chatted)\s+with\b",
    # Outcome indicators
    r"\b(?:they(?:'re| are)|he(?:'s| is)|she(?:'s| is))\s+(?:interested|excited|on board|hesitant|concerned|pushing back)\b",
    r"\b(?:agreed to|asked for|requested|wants?|need)\s+(?:a\s+)?(?:pricing|proposal|demo|contract|pilot|trial|next steps|follow.?up)\b",
    r"\b(?:sent|sending|shared|forwarded)\s+(?:the\s+)?(?:proposal|pricing|contract|deck|brochure|case study)\b",
    # Deal progression
    r"\b(?:moved?|moving|advance[ds]?|progress(?:ed|ing)?)\s+(?:to\s+)?(?:next stage|negotiation|closing|contract)\b",
    r"\b(?:closed|won|lost|dead|stalled|on hold)\b",
    # Follow-up signals
    r"\b(?:need to|should|gotta|have to)\s+(?:follow up|send|schedule|book|set up)\b",
    r"\bnext step[s]?\b",
]

# Compile patterns for performance
_ACTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ACTION_KEYWORDS]


def passes_keyword_filter(text: str) -> tuple[bool, list[str]]:
    """Fast pre-filter: does this message contain action keywords AND a company reference?

    Args:
        text: Raw Slack message text

    Returns:
        (passes, matched_companies) — True if message looks loggable, plus any matched company names
    """
    if len(text) < 20 or len(text) > 2000:
        # Too short to be meaningful, or too long (probably a paste/document)
        return False, []

    # Check for action keywords
    has_action = any(p.search(text) for p in _ACTION_PATTERNS)
    if not has_action:
        return False, []

    # Check for company name mention
    companies = _load_company_names()
    matched = [c for c in companies if c.lower() in text.lower()]

    # Also check for @-mentions of contacts (pattern: name + title/company context)
    # If no company matched but action keywords hit, still pass — the LLM can figure it out
    if matched:
        return True, matched

    # Fallback: if strong action keywords but no company match,
    # still pass if the message has enough substance (3+ words after keyword)
    if has_action and len(text.split()) >= 8:
        return True, []

    return False, []


# ── Stage 2: LLM classification + extraction ─────────────────────────────

CRM_DETECT_SYSTEM_PROMPT = """You are a CRM logging assistant. Analyze the following Slack message from a sales rep and determine:

1. Is this message describing a sales interaction that should be logged to CRM? (true/false)
2. If yes, extract structured data for the CRM note.

Rules for classification:
- YES: Messages about calls, meetings, demos, follow-ups, deal updates, customer conversations, proposals sent, objections encountered, next steps agreed
- NO: Casual chat, questions to teammates, internal discussions not about a specific customer, jokes, lunch plans, general announcements
- BORDERLINE → lean toward NO (we don't want false positives annoying the rep)

If loggable, extract:
- company: The company name mentioned (or "Unknown" if unclear)
- summary: A clean 1-2 sentence CRM note summarizing the interaction
- deal_stage_hint: Any signal about deal progression (or null)
- next_steps: Any follow-up actions mentioned (or null)
- sentiment: positive / neutral / negative / mixed

Respond with ONLY a JSON object, no markdown fencing:
{"loggable": true/false, "confidence": 0.0-1.0, "company": "...", "summary": "...", "deal_stage_hint": "...", "next_steps": "...", "sentiment": "..."}

If not loggable, respond: {"loggable": false, "confidence": 0.0-1.0}"""


def build_classification_prompt(message_text: str, matched_companies: list[str]) -> str:
    """Build the user prompt for LLM classification.

    Args:
        message_text: The Slack message to classify
        matched_companies: Company names found by keyword filter

    Returns:
        Formatted user prompt string
    """
    company_hint = ""
    if matched_companies:
        company_hint = f"\n\nKnown CRM companies detected in message: {', '.join(matched_companies)}"

    return f"Slack message from sales rep:\n\"{message_text}\"{company_hint}"


def parse_classification_response(llm_response: str) -> Optional[dict]:
    """Parse the LLM classification response.

    Args:
        llm_response: Raw LLM response text

    Returns:
        Parsed dict with loggable, confidence, company, summary, etc. or None on parse failure
    """
    # Try direct JSON parse
    try:
        result = json.loads(llm_response.strip())
        if isinstance(result, dict) and "loggable" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown fencing
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the response
    obj_match = re.search(r'\{[^{}]*"loggable"[^{}]*\}', llm_response)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def classify_message(text: str, llm_invoke_fn) -> Optional[dict]:
    """Full classification pipeline: keyword filter + LLM.

    Args:
        text: The Slack message text
        llm_invoke_fn: Function to call the LLM, signature: (system_prompt, user_prompt) -> response_text

    Returns:
        Classification result dict or None if not loggable/failed
    """
    # Stage 1: Keyword filter
    passes, matched_companies = passes_keyword_filter(text)
    if not passes:
        return None

    # Stage 2: LLM classification
    try:
        user_prompt = build_classification_prompt(text, matched_companies)
        llm_response = llm_invoke_fn(CRM_DETECT_SYSTEM_PROMPT, user_prompt)
        return parse_classification_response(llm_response)
    except Exception:
        return None
