# Migration Instructions: Direct APIs → OpenRouter + Local Embeddings

> **Context:** The `CLAUDE-CODE-BRIEFING.md` has been updated. We're switching from direct Anthropic/OpenAI API calls to OpenRouter (LLM gateway) and local HuggingFace embeddings. This eliminates the need for both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` — you only need `OPENROUTER_API_KEY`.
>
> **Read the updated `CLAUDE-CODE-BRIEFING.md` first** — specifically Sections 2, 4, 5, 7, 9B, and 16. Then follow the steps below.

---

## WHAT CHANGED AND WHY

**LLM calls:** `ChatAnthropic` → `ChatOpenAI` pointed at OpenRouter's endpoint. Same LangChain interface, same tool-calling, but now you can swap models by changing a string (`"anthropic/claude-sonnet-4.5"` → `"deepseek/deepseek-chat-v3"`).

**Embeddings:** `OpenAIEmbeddings` → `HuggingFaceEmbeddings` running locally. Free, no API key, runs on CPU.

**Net result:** One API key (`OPENROUTER_API_KEY`) replaces two. Everything else (MCP, LangGraph, Slack, ChromaDB, Tavily) is unchanged.

---

## STEP-BY-STEP MIGRATION

### Step 1: Update dependencies

**Remove from `requirements.txt`:**
```
langchain-anthropic>=0.3.0
```

**Add to `requirements.txt` (if not already present):**
```
langchain-huggingface>=0.1.0
sentence-transformers>=2.2.0
```

**Ensure these stay:**
```
langchain-openai>=0.2.0
```
(This is reused — `ChatOpenAI` works with OpenRouter's OpenAI-compatible endpoint)

**Run:**
```bash
pip install langchain-huggingface sentence-transformers
pip uninstall langchain-anthropic -y  # Optional cleanup
```

### Step 2: Update `.env`

**Remove these lines:**
```bash
ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-your-key
```

**Add these lines:**
```bash
# OpenRouter (single key for ALL LLM calls)
OPENROUTER_API_KEY=sk-or-v1-your-key

# Default model (change this to experiment — no code changes needed)
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4.5
```

Get your API key from https://openrouter.ai/keys

### Step 3: Create a helper for LLM initialization

Create or update a shared LLM factory so every graph file uses the same pattern:

```python
# llm_factory.py (new file, or add to an existing utils file)
import os
from langchain_openai import ChatOpenAI

def get_llm(model: str | None = None, **kwargs) -> ChatOpenAI:
    """
    Get an LLM instance via OpenRouter.

    Args:
        model: OpenRouter model string. Defaults to OPENROUTER_DEFAULT_MODEL env var.
               Examples: "anthropic/claude-sonnet-4.5", "deepseek/deepseek-chat-v3",
                         "qwen/qwen3-235b", "google/gemini-2.5-pro"
    """
    return ChatOpenAI(
        model=model or os.environ.get("OPENROUTER_DEFAULT_MODEL", "anthropic/claude-sonnet-4.5"),
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        **kwargs,
    )
```

### Step 4: Update all LLM references in graph files

Search your codebase for `ChatAnthropic` and replace with the factory:

```bash
grep -rn "ChatAnthropic\|langchain_anthropic" graphs/ app.py
```

**Before (direct Anthropic):**
```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")
llm_with_tools = ChatAnthropic(model="claude-sonnet-4-5-20250929").bind_tools(tools)
```

**After (OpenRouter):**
```python
from llm_factory import get_llm

llm = get_llm()  # Uses default model from env var
llm_with_tools = get_llm().bind_tools(tools)

# To experiment with a different model for a specific workflow:
router_llm = get_llm("anthropic/claude-haiku")  # Cheap + fast for routing
coach_llm = get_llm("anthropic/claude-sonnet-4.5")  # Best quality for coaching
assistant_llm = get_llm("deepseek/deepseek-chat-v3")  # Test cheaper model for research
```

Apply this to:
- `graphs/router.py`
- `graphs/coach.py`
- `graphs/assistant.py`
- Any other file that creates an LLM instance

### Step 5: Update embeddings in RAG

**Before (OpenAI API):**
```python
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
```

**After (local HuggingFace):**
```python
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```

Apply this to:
- `tools/rag.py`
- `scripts/index_playbooks.py`

**IMPORTANT:** After changing the embedding model, you MUST re-index your playbooks. The old ChromaDB vectors were created with OpenAI embeddings and are incompatible with HuggingFace embeddings. Delete the old index and rebuild:

```bash
rm -rf ./chroma_db
python scripts/index_playbooks.py
```

### Step 6: Clean up imports

Remove any remaining imports of `langchain_anthropic`:

```bash
grep -rn "langchain_anthropic\|from langchain_anthropic" .
```

All should be gone. The only LangChain LLM import should be `langchain_openai.ChatOpenAI` (used via the `llm_factory.py` helper or directly).

---

## VERIFICATION CHECKLIST

After migration, verify:

- [ ] `.env` has `OPENROUTER_API_KEY` and `OPENROUTER_DEFAULT_MODEL`
- [ ] `.env` does NOT have `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- [ ] `requirements.txt` includes `langchain-huggingface` and `sentence-transformers`
- [ ] `requirements.txt` does NOT include `langchain-anthropic`
- [ ] No remaining imports from `langchain_anthropic` (`grep -rn "langchain_anthropic"`)
- [ ] `llm_factory.py` exists with `get_llm()` function
- [ ] All graph files use `get_llm()` instead of `ChatAnthropic()`
- [ ] `tools/rag.py` uses `HuggingFaceEmbeddings` instead of `OpenAIEmbeddings`
- [ ] `scripts/index_playbooks.py` uses `HuggingFaceEmbeddings`
- [ ] Old ChromaDB index deleted and playbooks re-indexed with new embeddings
- [ ] A simple LLM call works: `get_llm().invoke("Hello")` returns a response
- [ ] Tool calling works: `get_llm().bind_tools(mcp_tools)` and a tool gets invoked correctly
- [ ] RAG search works: `rag.search("objection handling")` returns relevant chunks

---

## MODEL EXPERIMENTATION GUIDE

Once migrated, experimenting with models is trivial. Change the env var or pass a model string:

### Via environment variable (affects all workflows):
```bash
# In .env — change this line to try a new default model
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-chat-v3
```

### Via code (per-workflow):
```python
# Different models for different jobs
router_llm = get_llm("anthropic/claude-haiku")          # Fast + cheap for intent classification
coach_llm = get_llm("anthropic/claude-sonnet-4.5")      # Best quality for roleplay + feedback
assistant_llm = get_llm("deepseek/deepseek-chat-v3")    # Test cheaper model for research/email
pipeline_llm = get_llm("google/gemini-2.5-pro")         # 1M context for large pipeline analysis
```

### Models worth testing:

| Model | OpenRouter String | Good For | Price (input/output per M tokens) |
|-------|------------------|----------|-----------------------------------|
| Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` | Tool-use, coaching, complex reasoning | $3 / $15 |
| Claude Haiku | `anthropic/claude-haiku` | Fast routing, simple classification | $0.25 / $1.25 |
| DeepSeek Chat V3 | `deepseek/deepseek-chat-v3` | Reasoning, analysis, cheaper alternative | $0.27 / $1.10 |
| DeepSeek R1 | `deepseek/deepseek-r1` | Complex analysis, pipeline health | $0.55 / $2.19 |
| Qwen 3 235B | `qwen/qwen3-235b` | Multilingual, general purpose | $0.50 / $1.50 |
| Gemini 2.5 Pro | `google/gemini-2.5-pro` | Huge context (1M tokens), cheap | $1.25 / $10 |
| Llama 4 Maverick | `meta-llama/llama-4-maverick` | Open source, good all-round | $0.20 / $0.60 |

Check current pricing and available models: https://openrouter.ai/models

### Testing protocol:
1. Pick a workflow (e.g., `/research`)
2. Run it 3 times with the default model (Claude), save outputs
3. Change the model string for that workflow
4. Run the same 3 inputs, save outputs
5. Compare: quality, speed, cost, tool-calling reliability
6. If the cheaper model is "good enough" for that workflow, keep it

---

## COMMON ISSUES

1. **"401 Unauthorized" from OpenRouter** → Check your `OPENROUTER_API_KEY` is set correctly in `.env`. Get a key from https://openrouter.ai/keys
2. **"Model not found"** → Model strings are case-sensitive and include the provider prefix. Use `anthropic/claude-sonnet-4.5`, not `claude-sonnet-4.5`. Browse models at https://openrouter.ai/models
3. **Tool calling doesn't work with some models** → Not all models support tool/function calling well. Stick with Claude Sonnet for tool-heavy workflows. DeepSeek and Qwen tool support is improving but less reliable for complex multi-tool chains.
4. **ChromaDB returns bad results after switching embeddings** → You MUST delete the old index and re-index. Old vectors (OpenAI) and new vectors (HuggingFace) are incompatible: `rm -rf ./chroma_db && python scripts/index_playbooks.py`
5. **First embedding call is slow** → HuggingFace downloads the 80MB model on first use. Subsequent calls are fast (cached at `~/.cache/huggingface/`).
6. **Langfuse cost tracking shows $0** → OpenRouter model strings (like `anthropic/claude-sonnet-4.5`) may not be in Langfuse's default pricing table. Configure custom pricing in Langfuse settings to get accurate cost-per-trace.

---

## FILES CHANGED SUMMARY

| Action | File | What Changed |
|--------|------|-------------|
| CREATE | `llm_factory.py` | New helper: `get_llm(model)` returns OpenRouter-backed LLM |
| EDIT | `.env` | Remove `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`, add `OPENROUTER_API_KEY` + `OPENROUTER_DEFAULT_MODEL` |
| EDIT | `requirements.txt` | Remove `langchain-anthropic`, add `langchain-huggingface` + `sentence-transformers` |
| EDIT | `graphs/router.py` | `ChatAnthropic(...)` → `get_llm()` |
| EDIT | `graphs/coach.py` | `ChatAnthropic(...)` → `get_llm()` |
| EDIT | `graphs/assistant.py` | `ChatAnthropic(...)` → `get_llm()` |
| EDIT | `tools/rag.py` | `OpenAIEmbeddings(...)` → `HuggingFaceEmbeddings(...)` |
| EDIT | `scripts/index_playbooks.py` | `OpenAIEmbeddings(...)` → `HuggingFaceEmbeddings(...)` |
| DELETE | `./chroma_db/` | Must delete and re-index with new embeddings |
