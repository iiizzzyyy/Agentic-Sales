# Claude Code Task: Fix `/win-loss` Command — Two Bugs

> **Read `app.py` (lines 3009-3200) and `formatters/win_loss.py` first.**

---

## BUG 1: Patterns section shows raw markdown instead of clean Block Kit

### What's happening

The LLM is ignoring the structured `PATTERNS:` / `RECOMMENDATION_1:` format in the prompt and instead returning a full markdown report with `#`, `##`, `**`, `---`, numbered lists, etc. The parser at line 3127-3137 fails to find `PATTERNS:` so it falls through to the fallback at line 3136-3137:

```python
if not patterns:
    patterns = llm_response[:2000]  # <-- dumps raw markdown into a Block Kit section
```

This raw markdown gets shoved into a single `section` block's `mrkdwn` field, which Slack renders poorly — markdown headers (`#`, `##`) are NOT valid Slack mrkdwn, and the content is way too long for one section (3000 char limit).

### Root cause

Two issues working together:
1. The LLM prompt doesn't enforce the format strongly enough — the LLM generates a full pipeline digest instead of the requested `PATTERNS:` / `RECOMMENDATION_X:` format
2. The fallback (`patterns = llm_response[:2000]`) dumps the entire raw response without any cleanup

### Fix — THREE changes needed

#### Fix 1A: Strengthen the LLM prompt (app.py, around line 3092)

Replace the prompt content in `app_graph.invoke()` with this. The key changes are: adding "CRITICAL" format enforcement, adding "Do NOT" instructions, and limiting output length:

```python
result = app_graph.invoke({
    "messages": [HumanMessage(content=f"""Analyze these win/loss patterns and provide insights.

OVERALL: {total_won} won, {total_lost} lost, {win_rate:.0f}% win rate, {avg_cycle:.0f} day avg cycle

QUARTERLY TREND:
{chr(10).join([f"  {t['period']}: {t['win_rate']}% ({t['deals_won']}W/{t['deals_lost']}L)" for t in trend_data]) or "  No trend data"}

COMPETITOR CORRELATION:
{comp_summary or "  No competitor mentions found"}

DEAL DETAILS:
{deal_summaries or "  No closed deals"}

CRITICAL: Respond in EXACTLY this format. Do NOT use markdown headers (#), horizontal rules (---), or numbered lists. Do NOT write a full report. Just fill in the fields below:

PATTERNS:
• [First specific pattern — reference deal names, percentages, competitor names from the data above]
• [Second pattern]
• [Third pattern]
• [Fourth pattern — if applicable]

RECOMMENDATION_1: [One actionable recommendation in a single sentence]
RECOMMENDATION_2: [Another recommendation in a single sentence]
RECOMMENDATION_3: [Another recommendation in a single sentence]

Rules:
- Each bullet point must be ONE sentence, max 100 characters
- Do NOT write paragraphs, headers, or sub-sections
- Do NOT include a pipeline summary — that's already shown separately
- Reference specific data: deal names, win rates, competitor names
- Total response must be under 800 characters""")],
    "route": "assistant",
    "workflow": "research",
    "user_id": user_id,
    "channel_id": channel_id,
    "thread_ts": None,
})
```

#### Fix 1B: Improve the parser to handle LLM format variations (app.py, around line 3123)

Replace the parser block with this more robust version:

```python
llm_response = result["messages"][-1].content

# 7. Parse — handle both structured and freeform LLM responses
patterns = ""
recommendations = []

# First pass: try structured parsing
for line in llm_response.split("\n"):
    line = line.strip()
    if not line:
        continue
    if line.upper().startswith("PATTERNS:"):
        val = line.split(":", 1)[1].strip()
        if val:
            patterns = val
    elif line.startswith("•") or line.startswith("- •"):
        cleaned = line.lstrip("- ").strip()
        patterns += "\n" + cleaned
    elif line.upper().startswith("RECOMMENDATION_") or line.upper().startswith("RECOMMENDATION "):
        val = line.split(":", 1)[1].strip() if ":" in line else line
        if val:
            recommendations.append(val)

# Fallback: if structured parsing failed, clean up the raw response
if not patterns:
    # Strip markdown headers, horizontal rules, and excessive formatting
    clean_lines = []
    for line in llm_response.split("\n"):
        line = line.strip()
        # Skip markdown headers, horizontal rules, empty lines
        if line.startswith("#") or line.startswith("---") or line.startswith("==="):
            continue
        if not line:
            continue
        # Convert markdown bold to Slack bold
        line = line.replace("**", "*")
        # Convert numbered lists to bullets
        if len(line) > 2 and line[0].isdigit() and line[1] in (".", ")"):
            line = "• " + line[2:].strip()
        elif len(line) > 3 and line[0].isdigit() and line[1].isdigit() and line[2] in (".", ")"):
            line = "• " + line[3:].strip()
        # Add as bullet if not already
        if not line.startswith("•"):
            line = "• " + line
        clean_lines.append(line)

    # Take first 6 meaningful lines max
    patterns = "\n".join(clean_lines[:6])

    # Also try to extract recommendations from remaining lines
    if not recommendations and len(clean_lines) > 6:
        recommendations = [l.lstrip("• ").strip() for l in clean_lines[6:9]]

# Truncate patterns to fit Slack's 3000 char section limit
if len(patterns) > 2500:
    patterns = patterns[:2500] + "\n_...truncated_"
```

#### Fix 1C: Split long patterns into multiple Block Kit sections (formatters/win_loss.py)

Replace the patterns section in `format_win_loss_response()` (around line 69-74) with:

```python
# AI pattern analysis — split into multiple sections if too long
if patterns:
    # Split into chunks that fit Slack's 3000 char limit per section
    pattern_lines = patterns.split("\n")
    current_chunk = "*🧠 Patterns Detected:*\n"

    for line in pattern_lines:
        if len(current_chunk) + len(line) + 1 > 2800:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": current_chunk}
            })
            current_chunk = ""
        current_chunk += line + "\n"

    if current_chunk.strip():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": current_chunk}
        })
    blocks.append({"type": "divider"})
```

---

## BUG 2: "View Lost Deals", "View Won Deals", and "Competitor Analysis" buttons don't work

### What's happening

The action handlers exist (lines 3154-3199) and they look correct. The buttons have matching `action_id` values (`win_loss_lost_deals`, `win_loss_won_deals`, `win_loss_competitor`). But clicking them does nothing.

### Investigate — check these things in order:

1. **Check the Slack app console** at api.slack.com → Your App → Features → Interactivity & Shortcuts. Make sure **Interactivity** is toggled ON. For Socket Mode apps, this should work automatically, but verify it's enabled.

2. **Check the bot's terminal output** when you click a button. Look for error messages like:
   - `WARNING - No listener found for action: win_loss_lost_deals` → the handler isn't registered (unlikely since it's in app.py)
   - `ERROR` with a stack trace → the handler crashes
   - No output at all → Slack isn't sending the event (interactivity not configured)

3. **Check if other action buttons work.** Try clicking buttons from other commands (like `/deal` or `/pipeline`). If ALL buttons are broken, the issue is Slack configuration. If only `/win-loss` buttons are broken, the issue is in the handler code.

4. **Check that `client` parameter works for DMs.** The handlers use `client.chat_postMessage(channel=user_id, ...)` which sends a DM. This requires the `chat:write` OAuth scope AND the user must have had a prior DM with the bot (or use `conversations.open` first).

### Fix — update handlers to use `say` + channel instead of DM

The safest fix is to post the response in the SAME channel where the button was clicked, not as a DM. Replace all three handlers:

```python
@app.action("win_loss_lost_deals")
def handle_win_loss_lost(ack, body, say):
    """Show lost deals inline."""
    ack()
    channel = body["channel"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    lost = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedlost", "closed lost")]

    from formatters.helpers import format_currency
    if lost:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "❌ Lost Deals", "emoji": True}
            },
            {"type": "divider"},
        ]
        for d in lost:
            p = d.get("properties", {})
            deal_name = p.get("dealname", "Unknown")
            amount = float(p.get("amount", 0) or 0)

            # Get loss reason from activities
            loss_reason = ""
            for a in d.get("activities", []):
                note = a.get("body", a.get("note", ""))
                if any(word in note.lower() for word in ["lost", "competitor", "went with", "chose", "declined"]):
                    loss_reason = note[:120]
                    break

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{deal_name}*\n{format_currency(amount)}" + (f"\n_{loss_reason}_" if loss_reason else "")
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
                    "action_id": "view_deal_from_handoff",
                    "value": deal_name,
                }
            })

        say(text=f"Lost Deals: {len(lost)} deals", blocks=blocks, channel=channel)
    else:
        say(text="No lost deals found in current data.", channel=channel)


@app.action("win_loss_won_deals")
def handle_win_loss_won(ack, body, say):
    """Show won deals inline."""
    ack()
    channel = body["channel"]["id"]
    all_deals = mock_crm.load_mock_crm()["deals"]
    won = [d for d in all_deals if d.get("properties", {}).get("dealstage", "").lower() in ("closedwon", "closed won")]

    from formatters.helpers import format_currency
    if won:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "✅ Won Deals", "emoji": True}
            },
            {"type": "divider"},
        ]
        for d in won:
            p = d.get("properties", {})
            deal_name = p.get("dealname", "Unknown")
            amount = float(p.get("amount", 0) or 0)
            stage_label = p.get("dealstage_label", "Closed Won")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{deal_name}*\n{format_currency(amount)} • {stage_label}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Deal", "emoji": True},
                    "action_id": "view_deal_from_handoff",
                    "value": deal_name,
                }
            })

        say(text=f"Won Deals: {len(won)} deals", blocks=blocks, channel=channel)
    else:
        say(text="No won deals found in current data.", channel=channel)


@app.action("win_loss_competitor")
def handle_win_loss_competitor(ack, body, say):
    """Show competitor impact on win/loss."""
    ack()
    channel = body["channel"]["id"]

    all_deals = mock_crm.load_mock_crm()["deals"]
    competitor_mentions = {}

    for deal in all_deals:
        stage = deal.get("properties", {}).get("dealstage", "").lower()
        deal_name = deal.get("properties", {}).get("dealname", "Unknown")
        for activity in deal.get("activities", []):
            body_text = activity.get("body", activity.get("note", "")).lower()
            for comp in ["competitoralpha", "competitorbeta", "competitorgamma"]:
                if comp in body_text.replace(" ", ""):
                    readable = comp.replace("competitor", "Competitor ")
                    if readable not in competitor_mentions:
                        competitor_mentions[readable] = {"deals": [], "won": 0, "lost": 0}
                    if deal_name not in [d["name"] for d in competitor_mentions[readable]["deals"]]:
                        competitor_mentions[readable]["deals"].append({"name": deal_name, "stage": stage})
                    if "won" in stage:
                        competitor_mentions[readable]["won"] += 1
                    elif "lost" in stage:
                        competitor_mentions[readable]["lost"] += 1

    if competitor_mentions:
        from formatters.helpers import timestamp
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "⚔️ Competitor Impact on Deals", "emoji": True}
            },
            {"type": "divider"},
        ]

        for comp, data in competitor_mentions.items():
            deals_text = "\n".join([f"  • {d['name']} ({d['stage']})" for d in data["deals"][:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{comp}*\n"
                        f"Mentioned in {len(data['deals'])} deals (Won: {data['won']} | Lost: {data['lost']})\n"
                        f"{deals_text}"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Battle Card", "emoji": True},
                    "action_id": "battlecard_select",
                    "value": comp.replace(" ", ""),
                }
            })

        say(text="Competitor Impact on Deals", blocks=blocks, channel=channel)
    else:
        say(text="No competitor mentions found in deal activities.", channel=channel)
```

---

## TESTING AFTER FIX

1. Restart the bot: `python app.py`
2. Run `/win-loss` — verify:
   - Patterns section shows clean bullets, NOT raw markdown with `#` headers
   - Recommendations appear as separate bullets below patterns
   - Total output fits within Slack's display without truncation issues
3. Click "View Lost Deals" — verify it posts a formatted card in the same channel (not as a DM)
4. Click "View Won Deals" — same check
5. Click "Competitor Analysis" — verify it shows competitor mentions with "Battle Card" buttons

---

## FILES TO CHANGE

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `app.py` (line ~3092) | Strengthen LLM prompt with format enforcement |
| EDIT | `app.py` (line ~3123) | Replace parser with robust version + markdown cleanup fallback |
| EDIT | `app.py` (line ~3154-3199) | Replace all 3 action handlers — use `say` + channel, add Block Kit formatting, show deal details |
| EDIT | `formatters/win_loss.py` (line ~69) | Split long patterns into multiple Block Kit sections |
