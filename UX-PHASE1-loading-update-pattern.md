# UX Phase 1.1 — Loading Message → Update Pattern

## Problem
Every slash command posts a permanent loading message ("Researching NovaTech... give me 15 seconds.") to the channel. After the real result arrives, the channel has TWO messages — the loading text and the result card. This doubles visual clutter.

## Solution
Post the loading message, capture its `ts` (timestamp), then UPDATE that same message with the final Block Kit result. One message, zero waste.

## Pattern

The current pattern in every handler is:
```python
say(f"Researching *{company}*... give me 15 seconds.", channel=channel_id)
# ... do work ...
say(text=fallback, blocks=blocks, channel=channel_id)
```

Change to:
```python
loading_msg = client.chat_postMessage(
    channel=channel_id,
    text=f"⏳ Researching *{company}*... this takes about 15 seconds."
)
loading_ts = loading_msg["ts"]

# ... do work (graph invoke, extract data, format blocks) ...

client.chat_update(
    channel=channel_id,
    ts=loading_ts,
    text=fallback,
    blocks=blocks,
)
```

**IMPORTANT:** We need `client` (the Slack WebClient) in all handlers. The `say` function is a Bolt convenience wrapper. For `chat_postMessage` and `chat_update`, use `client` directly. Update all handler signatures to accept `client` from Bolt:

```python
@app.command("/research")
def handle_research(ack, say, command, client):  # <-- add client
```

Bolt automatically injects `client` when you add it as a parameter.

## Handlers to Update (7 total)

### 1. `/research` handler (line ~487)
```python
# BEFORE:
say(f"Researching *{company}*... give me 15 seconds.", channel=channel_id)

# AFTER:
loading_msg = client.chat_postMessage(
    channel=channel_id,
    text=f"⏳ Researching *{company}*... this takes about 15 seconds."
)
loading_ts = loading_msg["ts"]
```
Then at line ~523, replace `say(text=fallback, blocks=blocks, channel=channel_id)` with:
```python
client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)
```

### 2. `/deal` handler (line ~541)
```python
# BEFORE:
say(f"Looking up deals matching *{deal_name}*...", channel=channel_id)

# AFTER:
loading_msg = client.chat_postMessage(
    channel=channel_id,
    text=f"⏳ Looking up deals matching *{deal_name}*..."
)
loading_ts = loading_msg["ts"]
```
Then update ALL `say(text=..., blocks=...)` calls in this handler to use `client.chat_update(channel=channel_id, ts=loading_ts, ...)`.

### 3. `/pipeline` handler (line ~826)
```python
# BEFORE:
say("Analyzing pipeline health...", channel=channel_id)

# AFTER:
loading_msg = client.chat_postMessage(
    channel=channel_id,
    text="⏳ Analyzing pipeline health..."
)
loading_ts = loading_msg["ts"]
```

### 4. `/win-loss` handler (line ~3306)
```python
# BEFORE:
say("📉 Analyzing win/loss data...", channel=channel_id)

# AFTER:
loading_msg = client.chat_postMessage(
    channel=channel_id,
    text="⏳ Analyzing win/loss data..."
)
loading_ts = loading_msg["ts"]
```

### 5. `research_from_deal` action (line ~1330)
### 6. `drill_flagged_deal` action (line ~1893)
### 7. `refresh_pipeline` action (line ~1930)

Same pattern for all action handlers. Action handlers already have access to `client` via the Bolt action payload. Use `body["container"]["channel_id"]` or the channel from the action payload.

## Error Handling

If the work fails AFTER posting the loading message, update the loading message with the error instead of posting a new one:

```python
try:
    # ... do work ...
    client.chat_update(channel=channel_id, ts=loading_ts, text=fallback, blocks=blocks)
except Exception as e:
    client.chat_update(
        channel=channel_id,
        ts=loading_ts,
        text=f"⚠️ Something went wrong with this command. Error: {str(e)[:300]}"
    )
    import traceback
    traceback.print_exc()
```

This replaces the separate `handle_error()` call for these handlers — the loading message BECOMES the error message. No extra messages in the channel.

## DO NOT
- Do not use `chat_postEphemeral` for loading messages — ephemeral messages cannot be updated
- Do not delete the loading message and post a new one — the update pattern is cleaner
- Do not change the `say()` function signature or Bolt's internals
- Do not change handlers that don't have loading messages (like `/ask`, `/objection`, `/coach`)
- Do not remove the `ack()` call — it must stay as the first thing in every handler

## Testing
1. `/research NovaTech` → should show "⏳ Researching..." then smoothly replace with the research card (same message)
2. `/pipeline` → same pattern
3. `/deal NovaTech` → same pattern
4. Force an error → loading message should update to show the error, not post a separate error message
5. Check that the channel has exactly ONE message per command, not two
