# Claude Code Instructions: `/battlecard` — Interactive Battle Card Viewer

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/rag.py`, and `data/playbooks/competitive_battle_cards.md` first.**

---

## CONTEXT — WHAT AND WHY

While `/competitor` does a full competitive analysis (web search + RAG + LLM), `/battlecard` is a fast, focused tool to browse your internal battle card playbook data. No LLM calls needed for the basic view — just load and format the battle card markdown.

This is the "field sales quick reference" tool. Rep is about to walk into a meeting and needs to know: "What are CompetitorAlpha's weaknesses? What landmine questions should I plant?"

**Key difference from `/competitor`:** `/battlecard` is instant (no LLM, no web search), while `/competitor` is comprehensive (LLM analysis + web).

---

## WHAT IT DOES

1. User types `/battlecard` → shows a dropdown to pick a competitor
2. User types `/battlecard CompetitorAlpha` → shows that competitor's battle card immediately
3. Battle card includes: positioning, strengths, weaknesses, how-to-win, landmine questions
4. Action buttons: "Practice Objection", "Draft Competitive Email", "Full Analysis"

---

## STEP 1: Create `formatters/battlecard.py`

```python
"""Block Kit formatting for /battlecard command."""
from formatters.helpers import timestamp, truncate


# Known competitors from the battle cards playbook
KNOWN_COMPETITORS = ["CompetitorAlpha", "CompetitorBeta", "CompetitorGamma", "Build In-House"]


def format_battlecard_picker() -> tuple[list, str]:
    """Format a competitor picker when no competitor specified.

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚔️ Battle Cards", "emoji": True}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Select a competitor to view their battle card:"}
        },

        {"type": "divider"},

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorAlpha", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorAlpha",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorBeta", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorBeta",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. CompetitorGamma", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "CompetitorGamma",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "vs. Build In-House", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": "Build In-House",
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Or type `/battlecard [name]` directly • {timestamp()}"}
            ]
        },
    ]

    fallback = "Select a competitor to view their battle card"
    return blocks, fallback


def format_battlecard_response(
    competitor_name: str,
    positioning: str,
    strengths: list,
    weaknesses: list,
    how_to_win: list,
    landmine_questions: list,
) -> tuple[list, str]:
    """Format a competitor battle card as Block Kit.

    Args:
        competitor_name: Name of the competitor
        positioning: Their market positioning statement
        strengths: List of their strengths
        weaknesses: List of their weaknesses
        how_to_win: List of strategies to win against them
        landmine_questions: List of questions to plant

    Returns:
        tuple: (blocks, fallback_text)
    """
    strengths_text = "\n".join([f"• 💪 {s}" for s in strengths[:5]]) if strengths else "• No data"
    weaknesses_text = "\n".join([f"• 🎯 {w}" for w in weaknesses[:5]]) if weaknesses else "• No data"
    win_text = "\n".join([f"• ✅ {w}" for w in how_to_win[:5]]) if how_to_win else "• No data"
    landmine_text = "\n".join([f"• 💣 _{q}_" for q in landmine_questions[:4]]) if landmine_questions else "• No data"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"⚔️ Battle Card: vs. {competitor_name}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Q1 2026 • Confidential: Internal Use Only • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Positioning
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Their Positioning:* _{positioning}_"}
        },

        {"type": "divider"},

        # Strengths and weaknesses side by side
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Their Strengths:*\n{strengths_text}"},
                {"type": "mrkdwn", "text": f"*Their Weaknesses:*\n{weaknesses_text}"},
            ]
        },

        {"type": "divider"},

        # How to win
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🏆 How to Win:*\n{win_text}"}
        },

        {"type": "divider"},

        # Landmine questions
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*💣 Landmine Questions to Plant:*\n{landmine_text}"}
        },

        {"type": "divider"},

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice Objection", "emoji": True},
                    "action_id": "battlecard_practice",
                    "value": competitor_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Full Analysis", "emoji": True},
                    "action_id": "battlecard_full_analysis",
                    "value": competitor_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
                    "action_id": "battlecard_draft_email",
                    "value": competitor_name,
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Battle Cards • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Battle Card: vs. {competitor_name}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.battlecard import format_battlecard_picker, format_battlecard_response
```

And add both to `__all__`.

---

## STEP 3: Add Battle Card Parser to `tools/mock_crm.py` (or `app.py`)

This function parses the battle cards markdown file directly — no LLM needed:

```python
def parse_battle_cards() -> dict:
    """Parse the competitive_battle_cards.md playbook into structured data.

    Returns:
        Dict mapping competitor names to their battle card data.
    """
    battle_cards_path = os.path.join("data", "playbooks", "competitive_battle_cards.md")
    if not os.path.exists(battle_cards_path):
        return {}

    with open(battle_cards_path, encoding="utf-8") as f:
        content = f.read()

    cards = {}
    current_competitor = None
    current_section = None
    current_items = []

    for line in content.split("\n"):
        line = line.strip()

        # Detect competitor header
        if line.startswith("## BATTLE CARD: vs."):
            if current_competitor:
                # Save previous section
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items

            competitor_name = line.replace("## BATTLE CARD: vs.", "").strip()
            current_competitor = competitor_name
            cards[current_competitor] = {
                "positioning": "",
                "strengths": [],
                "weaknesses": [],
                "how_to_win": [],
                "landmine_questions": [],
            }
            current_section = None
            current_items = []

        elif current_competitor:
            if line.startswith("**Their Positioning:**"):
                cards[current_competitor]["positioning"] = line.replace("**Their Positioning:**", "").strip().strip('"')
            elif line.startswith("**Their Strengths:**"):
                current_section = "strengths"
                current_items = []
            elif line.startswith("**Their Weaknesses:**"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "weaknesses"
                current_items = []
            elif line.startswith("**How to Win:**"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "how_to_win"
                current_items = []
            elif line.startswith("**Landmine Questions"):
                if current_section and current_items:
                    cards[current_competitor][current_section] = current_items
                current_section = "landmine_questions"
                current_items = []
            elif line.startswith("- ") and current_section:
                item = line[2:].strip().strip('"')
                # Remove numbering like "1. "
                if item and item[0].isdigit() and ". " in item:
                    item = item.split(". ", 1)[1]
                current_items.append(item)

    # Save last section
    if current_competitor and current_section and current_items:
        cards[current_competitor][current_section] = current_items

    return cards
```

Add this function to `tools/mock_crm.py` since it loads from the data directory.

---

## STEP 4: Add `/battlecard` Command Handler to `app.py`

```python
@app.command("/battlecard")
def handle_battlecard(ack, say, command):
    """View competitive battle cards."""
    ack()
    competitor_name = command["text"].strip()
    channel_id = command["channel_id"]

    # If no competitor specified, show the picker
    if not competitor_name:
        from formatters import format_battlecard_picker
        blocks, fallback = format_battlecard_picker()
        say(text=fallback, blocks=blocks, channel=channel_id)
        return

    # Parse battle cards
    cards = mock_crm.parse_battle_cards()

    # Fuzzy match competitor name
    matched = None
    for name in cards:
        if competitor_name.lower() in name.lower() or name.lower() in competitor_name.lower():
            matched = name
            break

    if not matched:
        say(
            f"No battle card found for '{competitor_name}'.\n"
            f"Available: {', '.join(cards.keys()) if cards else 'None — run `python scripts/generate_test_data.py` first'}",
            channel=channel_id,
        )
        return

    card = cards[matched]

    from formatters import format_battlecard_response
    blocks, fallback = format_battlecard_response(
        competitor_name=matched,
        positioning=card.get("positioning", ""),
        strengths=card.get("strengths", []),
        weaknesses=card.get("weaknesses", []),
        how_to_win=card.get("how_to_win", []),
        landmine_questions=card.get("landmine_questions", []),
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 5: Add Action Handlers

```python
@app.action("battlecard_select")
def handle_battlecard_select(ack, body, say):
    """Handle competitor selection from the picker."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    cards = mock_crm.parse_battle_cards()
    card = cards.get(competitor, {})

    if not card:
        say(text=f"No battle card found for {competitor}.", channel=channel)
        return

    from formatters import format_battlecard_response
    blocks, fallback = format_battlecard_response(
        competitor_name=competitor,
        positioning=card.get("positioning", ""),
        strengths=card.get("strengths", []),
        weaknesses=card.get("weaknesses", []),
        how_to_win=card.get("how_to_win", []),
        landmine_questions=card.get("landmine_questions", []),
    )

    say(text=fallback, blocks=blocks, channel=channel)


@app.action("battlecard_practice")
def handle_battlecard_practice(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Try: `/coach roleplay competitive deal — buyer is evaluating {competitor}`",
    )


@app.action("battlecard_full_analysis")
def handle_battlecard_full_analysis(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/competitor {competitor}` for a full AI analysis with live web intelligence.",
    )


@app.action("battlecard_draft_email")
def handle_battlecard_draft_email(ack, body, client):
    ack()
    competitor = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/draft-email [company]` and mention {competitor} in your request to get a competitive positioning email.",
    )
```

---

## REGISTER IN SLACK

Add `/battlecard` slash command in api.slack.com:
- **Command:** `/battlecard`
- **Description:** `View competitive battle cards`
- **Usage Hint:** `[competitor name — optional]`

---

## PERFORMANCE NOTE

This command should respond in **under 1 second** because:
- It reads a local markdown file (no API calls)
- It parses text (no LLM calls)
- It formats Block Kit (no network)

This is the fastest command in the bot.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/battlecard.py` | New formatter with picker + battle card display |
| EDIT | `formatters/__init__.py` | Add `format_battlecard_picker` and `format_battlecard_response` |
| EDIT | `tools/mock_crm.py` | Add `parse_battle_cards()` function |
| EDIT | `app.py` | Add `handle_battlecard()`, `handle_battlecard_select()`, `handle_battlecard_practice()`, `handle_battlecard_full_analysis()`, `handle_battlecard_draft_email()` |
