# EXPANSION-19: Configurable Roleplay Turn Count

## Goal
Make the roleplay debrief turn count configurable instead of hardcoded to 4.
Allow users to specify turn count via the `/coach roleplay` command syntax.
Default to 4 turns for quick sessions, support up to 12 turns for deep practice.

## Current State
- `graphs/coach.py` line 99: `if turn_count >= 4:` — hardcoded debrief trigger
- `graphs/coach.py` line 76: system prompt says "After 3-4 exchanges"
- `app.py` line 944: `if turn_count >= 4:` — hardcoded debrief trigger in message handler
- `app.py` stores `turn_count` in `active_roleplays[thread_ts]`

## What to Build

### Step 1: Add Configuration Constant

At the top of `app.py` (near the `active_roleplays = {}` line):

```python
# Roleplay configuration
DEFAULT_ROLEPLAY_TURNS = 4
MIN_ROLEPLAY_TURNS = 3
MAX_ROLEPLAY_TURNS = 12
```

### Step 2: Parse Turn Count from Command

In the `/coach` handler (`handle_coach` function, around line 563), parse an optional `--turns N` flag:

```python
if workflow == "roleplay":
    # Parse optional --turns flag
    max_turns = DEFAULT_ROLEPLAY_TURNS
    if "--turns" in text:
        parts = text.split("--turns")
        text = parts[0].strip()  # Remove flag from scenario text
        try:
            requested_turns = int(parts[1].strip().split()[0])
            max_turns = max(MIN_ROLEPLAY_TURNS, min(requested_turns, MAX_ROLEPLAY_TURNS))
        except (ValueError, IndexError):
            pass  # Keep default

    scenario = text.replace("roleplay ", "").strip()
```

Then store `max_turns` in the roleplay state:

```python
active_roleplays[thread_ts] = {
    "messages": result["messages"],
    "turn_count": 1,
    "max_turns": max_turns,  # ADD THIS
    "rag_context": result.get("rag_context", ""),
    "user_id": user_id,
    "channel_id": channel_id,
    "scenario": scenario,
}
```

### Step 3: Update the Message Handler Debrief Check

In the message handler (around line 944), replace the hardcoded check:

```python
# BEFORE:
if turn_count >= 4:

# AFTER:
max_turns = roleplay.get("max_turns", DEFAULT_ROLEPLAY_TURNS)
if turn_count >= max_turns:
```

### Step 4: Update `continue_roleplay()` in `graphs/coach.py`

The `continue_roleplay()` function at line 93 also has a hardcoded check.
Add `max_turns` as a parameter:

```python
# BEFORE:
def continue_roleplay(state: dict, turn_count: int) -> dict:
    ...
    if turn_count >= 4:

# AFTER:
def continue_roleplay(state: dict, turn_count: int, max_turns: int = 4) -> dict:
    ...
    if turn_count >= max_turns:
```

Update the caller in `app.py` message handler:

```python
result = continue_roleplay(
    {
        "messages": messages,
        "rag_context": roleplay.get("rag_context", ""),
    },
    turn_count,
    max_turns=roleplay.get("max_turns", DEFAULT_ROLEPLAY_TURNS),
)
```

### Step 5: Update System Prompts

In `graphs/coach.py`, make the roleplay system prompt dynamic.

In `roleplay_node()` (line 67), the system prompt currently says:
"After 3-4 exchanges from the rep, break character and provide a debrief"

This prompt is used for the INITIAL turn only (turn 1). For longer sessions, we want the AI to stay in character longer. However, `roleplay_node()` doesn't currently receive `max_turns` from the state.

**Option A (simpler):** Leave the initial prompt as-is. The actual debrief timing is controlled by the `if turn_count >= max_turns` check in `continue_roleplay()`, so the initial prompt doesn't need to be precise. The AI won't trigger a debrief on its own — we control when to ask for it.

**Option B (more polished):** Pass `max_turns` through the graph state:

In `app.py` handle_coach handler, add `max_turns` to the invoke state:
```python
result = app_graph.invoke({
    "messages": [HumanMessage(content=f"/coach {text}")],
    "route": "coach",
    "workflow": workflow,
    "user_id": user_id,
    "channel_id": channel_id,
    "thread_ts": thread_ts,
    "max_turns": max_turns,  # ADD THIS
})
```

Then in `roleplay_node()`:
```python
max_turns = state.get("max_turns", 4)
# Update system prompt:
f"After {max_turns - 1}-{max_turns} exchanges from the rep, break character..."
```

**Use Option A** — it's simpler and the behavior is the same since we control debrief timing externally.

### Step 6: Add Mid-Session Progress Indicator

For longer sessions (6+ turns), add a subtle progress hint so the rep knows how far along they are. In the message handler, after posting the AI's in-character response:

```python
if turn_count >= max_turns:
    # Debrief (existing code)
    ...
else:
    # Continue roleplay
    say(text=response_text, channel=event["channel"], thread_ts=thread_ts)

    # Progress indicator for longer sessions
    if max_turns >= 6 and turn_count == max_turns - 2:
        say(
            text="_Coach note: 2 turns remaining before debrief. Make them count!_",
            channel=event["channel"],
            thread_ts=thread_ts,
        )

    # Update state
    active_roleplays[thread_ts] = { ... }
```

### Step 7: Update All Other Roleplay Start Points

There are several other places that start roleplays (action handlers). Search for ALL occurrences of `"turn_count": 1` and add `"max_turns": DEFAULT_ROLEPLAY_TURNS` next to each:

- `handle_roleplay_from_research` (around line 1177)
- Action handler around line 1598
- Action handler around line 1638

These use the default since they don't have a `--turns` flag.

### Step 8: Update the Usage Message

In the `/coach` handler, update the usage hint:

```python
if not text:
    say(
        "Usage:\n"
        "• `/coach roleplay [scenario]` — 4-turn practice session\n"
        "• `/coach roleplay [scenario] --turns 8` — longer session (3-12 turns)\n"
        "• `/coach prep [company]` — meeting prep brief\n"
        "• `/coach feedback [notes]` — call feedback"
    )
    return
```

## Command Examples

```
/coach roleplay discovery call                    → 4 turns (default)
/coach roleplay pricing negotiation --turns 8     → 8 turns
/coach roleplay competitive deal --turns 6        → 6 turns
/coach roleplay cold call --turns 12              → 12 turns (max)
```

## Testing

1. `/coach roleplay discovery call` → should debrief after turn 4 (unchanged)
2. `/coach roleplay discovery call --turns 8` → should stay in character for 7 turns, debrief on turn 8
3. `/coach roleplay test --turns 2` → should clamp to 3 (minimum)
4. `/coach roleplay test --turns 20` → should clamp to 12 (maximum)
5. For a `--turns 8` session, verify the "2 turns remaining" hint appears at turn 6
6. Verify all roleplay action buttons (from /research, /competitor, etc.) still work with default turns

## DO NOT
- Do not change the default from 4 — it should stay as the default for demos
- Do not add max_turns to /coach-live — live coaching sessions end with "done", not a turn count
- Do not break the existing debrief formatting — the Block Kit debrief card should work the same regardless of turn count
