# Add Local Ollama Support — Claude Code Instructions

**Goal:** Allow the app to use a local Ollama model instead of OpenRouter. Switching between the two should be a `.env` toggle — no code changes needed to swap back and forth.

---

## CONTEXT

- All LLM calls go through `llm_factory.py` → `get_llm()` which returns a `ChatOpenAI` instance
- Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`
- LangChain's `ChatOpenAI` works with Ollama's API — just change `base_url` and set a dummy `api_key`

---

## STEP 1: Fix the `.env` typo

Line 9 currently has a double assignment:

```
OPENROUTER_DEFAULT_MODEL=OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-chat-v3-0324:free
```

Fix it to:

```
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-chat-v3-0324:free
```

## STEP 2: Add Ollama config to `.env`

Add these lines to the `.env` file, right after the `OPENROUTER_DEFAULT_MODEL` line:

```
# Ollama (local LLM — uncomment to use instead of OpenRouter)
# Set OLLAMA_BASE_URL to enable local Ollama. Comment it out to use OpenRouter.
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1:8b
```

**NOTE:** The user should replace `llama3.1:8b` with whatever model they have installed locally. Run `ollama list` to see available models.

## STEP 3: Update `llm_factory.py`

Replace the entire contents of `llm_factory.py` with:

```python
"""LLM factory — supports OpenRouter (cloud) and Ollama (local)."""
import os
from langchain_openai import ChatOpenAI


def get_llm(model: str | None = None, **kwargs) -> ChatOpenAI:
    """
    Get an LLM instance.

    Routing logic:
        - If OLLAMA_BASE_URL is set → use local Ollama
        - Otherwise → use OpenRouter

    Args:
        model: Model name override. If not provided, uses env defaults.
               Ollama examples: "llama3.1:8b", "mistral", "qwen2.5:72b"
               OpenRouter examples: "deepseek/deepseek-chat-v3-0324:free",
                                    "meta-llama/llama-3.3-70b-instruct:free"
    """
    ollama_url = os.environ.get("OLLAMA_BASE_URL")

    if ollama_url:
        # ── Local Ollama ──
        default_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        return ChatOpenAI(
            model=model or default_model,
            base_url=ollama_url,
            api_key="ollama",  # Ollama doesn't need a real key but LangChain requires one
            max_tokens=kwargs.pop("max_tokens", 2048),
            **kwargs,
        )

    # ── OpenRouter (cloud) ──
    default_model = os.environ.get("OPENROUTER_DEFAULT_MODEL", "google/gemma-3-27b-it:free")

    return ChatOpenAI(
        model=model or default_model,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_tokens=kwargs.pop("max_tokens", 2048),
        **kwargs,
    )
```

---

## HOW TO SWITCH BETWEEN OLLAMA AND OPENROUTER

**Use Ollama (local):**
```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1:8b
```

**Use OpenRouter (cloud):**
Comment out or remove the `OLLAMA_BASE_URL` line:
```env
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=llama3.1:8b
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-chat-v3-0324:free
```

The presence/absence of `OLLAMA_BASE_URL` is the switch. If it's set, Ollama is used. If not, OpenRouter is used. No code changes needed to toggle.

---

## PREREQUISITES

Make sure Ollama is running before starting the app:

```bash
# Check available models
ollama list

# If you need to pull a model
ollama pull llama3.1:8b

# Ollama should be running (it usually auto-starts)
# Verify with:
curl http://localhost:11434/v1/models
```

---

## TESTING

1. Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env`
2. Restart the app
3. Run `/research DataFlow` — should get a response from your local Ollama model
4. Run `/ask What deals are closing this month?` — verify general LLM flow works
5. To verify the toggle: comment out `OLLAMA_BASE_URL`, restart, confirm it falls back to OpenRouter

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| FIX | `.env` line 9 | Remove duplicate `OPENROUTER_DEFAULT_MODEL=` prefix |
| ADD | `.env` | Add `OLLAMA_BASE_URL` and `OLLAMA_MODEL` variables |
| REPLACE | `llm_factory.py` | Full rewrite — add Ollama routing with OpenRouter fallback |
