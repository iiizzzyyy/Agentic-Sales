# FIX: Add Error Handling to ALL Slash Command Handlers

## Problem
When a slash command fails after the initial `say()` message (e.g., "Researching NovaTech...
give me 15 seconds."), the error is swallowed silently by Slack Bolt. The user sees the
loading message but never gets a response. No error appears in the terminal.

This is because Bolt catches exceptions in handlers and logs them at a level that may not
be visible. The handler crashes mid-execution and the user is left waiting forever.

## Fix — Wrap Every Handler with try/except

### Step 1: Add Error Reporting Helper

At the top of `app.py` (near the imports), add:

```python
import traceback

def handle_error(say, channel_id, command_name, error):
    """Report errors to both terminal and Slack."""
    error_msg = str(error)
    tb = traceback.format_exc()

    # Print full traceback to terminal
    print(f"\n{'='*60}")
    print(f"ERROR in {command_name}:")
    print(tb)
    print(f"{'='*60}\n")

    # Send user-friendly error to Slack
    say(
        text=f"⚠️ Something went wrong with `{command_name}`. Error: {error_msg[:300]}",
        channel=channel_id,
    )
```

### Step 2: Wrap the /research Handler

```python
@app.command("/research")
def handle_research(ack, say, command):
    """Research a company - pulls HubSpot data + web search."""
    ack()
    user_id = command["user_id"]
    channel_id = command["channel_id"]
    company = command["text"].strip()

    if not company:
        say("Please provide a company name: `/research [company_name]`")
        return

    say(f"Researching *{company}*... give me 15 seconds.", channel=channel_id)

    try:
        # Invoke the graph
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/research {company}")],
            "route": "assistant",
            "workflow": "research",
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": None,
            "company_name": company,
        })

        # Extract structured data
        company_data = extract_company_data(company)
        contacts = extract_contacts(company)
        deals = extract_deals(company)
        llm_response = result["messages"][-1].content
        talking_points = parse_talking_points(llm_response)

        # Get news from web context if available
        news = []
        if result.get("web_context"):
            news = [{"title": line.strip("• -")} for line in result["web_context"].split("\n") if line.strip()][:3]

        # Format with Block Kit
        blocks, fallback = format_research_response(
            company_name=company,
            company_data=company_data,
            contacts=contacts,
            deals=deals,
            news=news,
            talking_points=talking_points,
        )

        say(text=fallback, blocks=blocks, channel=channel_id)

    except Exception as e:
        handle_error(say, channel_id, "/research", e)
```

### Step 3: Wrap ALL Other Slash Command Handlers

Apply the same pattern to EVERY slash command handler in app.py. The pattern is:

1. Keep `ack()` OUTSIDE the try/except (it must always run within 3 seconds)
2. Keep the initial parameter parsing and validation outside try/except
3. Wrap everything after the first `say()` in try/except
4. Call `handle_error(say, channel_id, "/command-name", e)` in the except block

Commands to wrap (search for `@app.command` to find all of them):
- `/research` (line 436)
- `/deal` (line 486)
- `/coach` (line 543)
- `/draft-email` (line 643)
- `/pipeline` (line 722)
- `/objection` (line ~1741)
- `/ask` (line ~1896)
- `/followup` (line ~2186)
- `/competitor` (line ~2414)
- `/battlecard` (line ~2628)
- `/alerts` (line ~2764)
- `/forecast` (line ~2896)
- `/win-loss` (line ~3036)
- `/persona` (line ~3387)
- `/handoff` (line ~3587)
- `/email-sequence` (line ~3988)
- `/coach-live` (line ~4182)
- `/demo-flow` (line ~4248)

### Step 4: Also Wrap Action Handlers

The same pattern applies to `@app.action()` handlers. Wrap the body of each
action handler in try/except. For action handlers, use `client.chat_postMessage`
instead of `say` for error reporting:

```python
@app.action("some_action")
def handle_some_action(ack, body, client):
    ack()
    try:
        # ... handler code ...
    except Exception as e:
        channel = body["channel"]["id"]
        tb = traceback.format_exc()
        print(f"\nERROR in action handler:\n{tb}\n")
        client.chat_postMessage(
            channel=channel,
            text=f"⚠️ Something went wrong. Error: {str(e)[:300]}",
        )
```

## Why This Matters
Once this is applied, re-run `/research NovaTech`. The error will now:
1. Print a full Python traceback in your terminal
2. Show an error message in Slack so the user knows something failed

This will immediately reveal whether the issue is:
- Missing TAVILY_API_KEY (Tavily web search crash)
- OpenRouter API failure (LLM timeout or auth error)
- ChromaDB not indexed (RAG search failure)
- A formatting bug in the Block Kit builder

## DO NOT
- Do not put `ack()` inside the try/except — it MUST run within 3 seconds or Slack retries
- Do not swallow errors silently — always print the traceback AND notify the user
- Do not remove the error handling after debugging — keep it permanently
