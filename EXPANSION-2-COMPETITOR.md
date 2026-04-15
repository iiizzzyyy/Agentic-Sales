# Claude Code Instructions: `/competitor` — Real-Time Competitive Intelligence

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/web_search.py`, `tools/rag.py`, and `formatters/research.py` first.**

---

## CONTEXT — WHAT AND WHY

Sales reps often go into meetings blind about what competitors are doing. We already have static battle cards in the RAG playbooks, but `/competitor` combines those with **live web search** to give real-time competitive intelligence.

A rep about to lose a deal to CompetitorAlpha types `/competitor CompetitorAlpha` and gets: what they just announced, how to position against them, and talking points — all in 10 seconds.

---

## WHAT IT DOES

1. User types `/competitor [competitor_name]` or `/competitor [competitor_name] vs [our product]`
2. Bot pulls:
   - RAG: Battle cards, competitive positioning from playbooks
   - Tavily: Live news about the competitor (last 30 days)
   - RAG/CRM: Any deals where this competitor was mentioned in notes
3. LLM generates a competitive intel brief
4. Bot posts a rich Block Kit card with positioning, counter-arguments, and live news

---

## STEP 1: Create `formatters/competitor.py`

```python
"""Block Kit formatting for /competitor command."""
from formatters.helpers import timestamp, truncate


def format_competitor_response(
    competitor_name: str,
    positioning: str,
    strengths_weaknesses: dict,
    counter_arguments: list,
    recent_news: list,
    deals_at_risk: list,
    talking_points: str,
) -> tuple[list, str]:
    """Format a competitive intelligence brief as Block Kit.

    Args:
        competitor_name: Name of the competitor
        positioning: LLM-generated positioning statement
        strengths_weaknesses: Dict with 'strengths' and 'weaknesses' lists
        counter_arguments: List of dicts with 'objection' and 'response'
        recent_news: List of dicts with 'title', 'summary', 'url'
        deals_at_risk: List of dicts with 'deal_name', 'stage', 'amount'
        talking_points: LLM-generated talking points string

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Strengths & weaknesses
    strengths = strengths_weaknesses.get("strengths", [])
    weaknesses = strengths_weaknesses.get("weaknesses", [])
    strengths_str = "\n".join([f"• {s}" for s in strengths[:5]]) if strengths else "_Unknown_"
    weaknesses_str = "\n".join([f"• {w}" for w in weaknesses[:5]]) if weaknesses else "_Unknown_"

    # Counter-arguments
    if counter_arguments:
        counter_str = "\n".join([
            f"• *\"{c.get('objection', '')}\"*\n  → {c.get('response', '')}"
            for c in counter_arguments[:5]
        ])
    else:
        counter_str = "_No specific counter-arguments available_"

    # Recent news
    if recent_news:
        news_str = "\n".join([
            f"• *{truncate(n.get('title', ''), 80)}*\n  {truncate(n.get('summary', ''), 150)}"
            for n in recent_news[:4]
        ])
    else:
        news_str = "_No recent news found_"

    # Deals at risk
    if deals_at_risk:
        risk_str = "\n".join([
            f"• ⚠️ *{d.get('deal_name', 'Unknown')}* — {d.get('stage', 'N/A')} — ${int(float(d.get('amount', 0))):,}"
            for d in deals_at_risk[:5]
        ])
    else:
        risk_str = "_No active deals mentioning this competitor_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"⚔️ Competitive Intel: {competitor_name}", "emoji": True}
        },

        # Positioning
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Our Positioning:*\n{positioning}"}
        },

        {"type": "divider"},

        # Two-column: Their Strengths vs Their Weaknesses
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Their Strengths:*\n{strengths_str}"},
                {"type": "mrkdwn", "text": f"*Their Weaknesses:*\n{weaknesses_str}"},
            ]
        },

        {"type": "divider"},

        # Counter-arguments
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*When They Say → You Say:*\n{counter_str}"}
        },

        {"type": "divider"},

        # Recent news
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recent News (Last 30 Days):*\n{news_str}"}
        },

        {"type": "divider"},

        # Deals at risk
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Your Deals Mentioning {competitor_name}:*\n{risk_str}"}
        },

        {"type": "divider"},

        # Talking points
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Talking Points for Your Next Call:*\n{talking_points}"}
        },

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Roleplay vs This Competitor", "emoji": True},
                    "action_id": "roleplay_competitor",
                    "value": competitor_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Competitive Email", "emoji": True},
                    "action_id": "draft_competitive_email",
                    "value": competitor_name,
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Battle Cards + Live Search • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Competitive Intel: {competitor_name}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.competitor import format_competitor_response
```

And add `"format_competitor_response"` to `__all__`.

---

## STEP 3: Add `/competitor` Command Handler to `app.py`

```python
@app.command("/competitor")
def handle_competitor(ack, say, command):
    """Generate competitive intelligence brief."""
    ack()
    competitor_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not competitor_name:
        say("Please provide a competitor name: `/competitor [name]`", channel=channel_id)
        return

    say(f"⚔️ Gathering intel on *{competitor_name}*...", channel=channel_id)

    # 1. Search RAG for battle cards mentioning this competitor
    from tools.rag import search_playbooks, search_crm
    battle_card_context = search_playbooks(f"{competitor_name} competitor positioning battle card", n_results=5)
    crm_context = search_crm(f"{competitor_name} competitor", n_results=3)

    # 2. Live web search for recent competitor news
    from tools.web_search import search_company_news
    web_results = search_company_news(competitor_name)

    # 3. Run LLM to generate the competitive brief
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Generate a competitive intelligence brief about {competitor_name}.

BATTLE CARD / PLAYBOOK CONTEXT:
{battle_card_context}

CRM NOTES MENTIONING THIS COMPETITOR:
{crm_context}

RECENT NEWS ABOUT {competitor_name.upper()}:
{web_results}

Generate the following (be specific, not generic):

1. OUR POSITIONING (2-3 sentences): How we position against {competitor_name}
2. THEIR STRENGTHS (3-5 bullet points)
3. THEIR WEAKNESSES (3-5 bullet points)
4. COUNTER-ARGUMENTS (3-5 items): When the prospect says "[competitor claim]", respond with "[our counter]"
   Format each as: OBJECTION: "..." | RESPONSE: "..."
5. TALKING POINTS (3-5 bullet points): Specific things to say in a competitive deal

Be concise and actionable. Reps need to use this in the next 5 minutes.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    # 4. Parse the LLM response into structured data
    # Use a parsing helper (similar to parse_recommendations in app.py)
    positioning, strengths_weaknesses, counter_arguments, talking_points = parse_competitor_response(llm_response)

    # 5. Parse web results into news items
    recent_news = parse_news_items(web_results)

    # 6. Find deals mentioning this competitor
    deals_at_risk = find_deals_mentioning_competitor(competitor_name)

    # 7. Format and send
    from formatters import format_competitor_response
    blocks, fallback = format_competitor_response(
        competitor_name=competitor_name,
        positioning=positioning,
        strengths_weaknesses=strengths_weaknesses,
        counter_arguments=counter_arguments,
        recent_news=recent_news,
        deals_at_risk=deals_at_risk,
        talking_points=talking_points,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add Parsing Helpers to `app.py`

```python
def parse_competitor_response(llm_text: str) -> tuple:
    """Parse the LLM competitor analysis into structured data.

    Returns: (positioning, strengths_weaknesses, counter_arguments, talking_points)
    """
    positioning = ""
    strengths_weaknesses = {"strengths": [], "weaknesses": []}
    counter_arguments = []
    talking_points = ""

    # Split by sections (LLM typically uses numbered headers)
    sections = llm_text.split("\n")
    current_section = ""

    for line in sections:
        line_lower = line.lower().strip()
        if "positioning" in line_lower and ("1." in line_lower or "#" in line_lower):
            current_section = "positioning"
            continue
        elif "strength" in line_lower and ("2." in line_lower or "#" in line_lower):
            current_section = "strengths"
            continue
        elif "weakness" in line_lower and ("3." in line_lower or "#" in line_lower):
            current_section = "weaknesses"
            continue
        elif "counter" in line_lower and ("4." in line_lower or "#" in line_lower):
            current_section = "counters"
            continue
        elif "talking" in line_lower and ("5." in line_lower or "#" in line_lower):
            current_section = "talking"
            continue

        stripped = line.strip().lstrip("•-* ")
        if not stripped:
            continue

        if current_section == "positioning":
            positioning += stripped + " "
        elif current_section == "strengths":
            if stripped:
                strengths_weaknesses["strengths"].append(stripped)
        elif current_section == "weaknesses":
            if stripped:
                strengths_weaknesses["weaknesses"].append(stripped)
        elif current_section == "counters":
            if "OBJECTION:" in line and "RESPONSE:" in line:
                parts = line.split("RESPONSE:")
                objection = parts[0].replace("OBJECTION:", "").strip().strip('"').strip("•- ")
                response = parts[1].strip().strip('"')
                counter_arguments.append({"objection": objection, "response": response})
            elif "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    counter_arguments.append({
                        "objection": parts[0].strip().strip('"').strip("•- "),
                        "response": parts[1].strip().strip('"'),
                    })
        elif current_section == "talking":
            talking_points += f"• {stripped}\n"

    return positioning.strip(), strengths_weaknesses, counter_arguments, talking_points.strip()


def parse_news_items(web_results: str) -> list:
    """Parse web search results string into structured news items."""
    news = []
    items = web_results.split("•")
    for item in items:
        item = item.strip()
        if not item:
            continue
        lines = item.split("\n")
        title = lines[0].strip().strip("*") if lines else ""
        summary = lines[1].strip() if len(lines) > 1 else ""
        url = lines[2].strip() if len(lines) > 2 else ""
        if title:
            news.append({"title": title, "summary": summary, "url": url})
    return news


def find_deals_mentioning_competitor(competitor_name: str) -> list:
    """Search CRM notes for deals that mention a competitor."""
    from tools.rag import search_crm_deals
    results = search_crm_deals(competitor_name, n_results=5)
    deals = []
    for doc in results.split("---"):
        if competitor_name.lower() not in doc.lower():
            continue
        # Extract deal info from RAG chunk
        name = ""
        stage = "N/A"
        amount = 0
        for line in doc.split("\n"):
            if "Deal:" in line:
                name = line.split("Deal:")[-1].strip()
            elif "Stage:" in line:
                stage = line.split("Stage:")[-1].strip()
            elif "Amount:" in line:
                try:
                    amount = float(line.split("Amount:")[-1].strip().replace("$", "").replace(",", ""))
                except ValueError:
                    pass
        if name:
            deals.append({"deal_name": name, "stage": stage, "amount": amount})
    return deals
```

---

## STEP 5: Add Action Handlers

```python
@app.action("roleplay_competitor")
def handle_roleplay_competitor(ack, body, say):
    """Start a roleplay where the buyer brings up the competitor."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    say(
        text=f"🎯 Starting competitive roleplay — the buyer will bring up *{competitor}*...\nTry: `/coach roleplay competitive objection {competitor}`",
        channel=channel,
    )


@app.action("draft_competitive_email")
def handle_draft_competitive_email(ack, body, say):
    """Draft an email that positions against the competitor."""
    ack()
    competitor = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    say(
        text=f"✉️ Try: `/draft-email [company name]` — the AI will factor in competitive positioning against *{competitor}*.",
        channel=channel,
    )
```

---

## REGISTER IN SLACK

Add `/competitor` slash command in api.slack.com:
- **Command:** `/competitor`
- **Description:** `Get real-time competitive intelligence`
- **Usage Hint:** `[competitor name]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/competitor.py` | New formatter for competitive intel Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_competitor_response` export |
| EDIT | `app.py` | Add `handle_competitor()`, `parse_competitor_response()`, `parse_news_items()`, `find_deals_mentioning_competitor()`, `handle_roleplay_competitor()`, `handle_draft_competitive_email()` |
