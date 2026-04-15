"""LLM factory — supports Ollama (local, primary) and OpenRouter (cloud, fallback)."""
import os
from langchain_openai import ChatOpenAI


def get_llm(model: str | None = None, **kwargs) -> ChatOpenAI:
    """
    Get an LLM instance.

    Routing logic:
        - Default: Use local Ollama with qwen3.5:397b-cloud model
        - Fallback: If OLLAMA_BASE_URL not set, use OpenRouter

    Args:
        model: Model name override. If not provided, uses env defaults.
               Ollama examples: "qwen3.5:397b-cloud", "llama3.1:8b", "mistral"
               OpenRouter examples: "google/gemma-3-27b-it:free",
                                    "meta-llama/llama-3.3-70b-instruct:free"
    """
    ollama_url = os.environ.get("OLLAMA_BASE_URL")

    # ── Local Ollama (PRIMARY) ──
    # Default model: qwen3.5:397b-cloud (Anthropic-grade performance, local inference)
    if ollama_url:
        default_model = os.environ.get("OLLAMA_MODEL", "qwen3.5:397b-cloud")
        return ChatOpenAI(
            model=model or default_model,
            base_url=ollama_url,
            api_key="ollama",  # Ollama doesn't need a real key but LangChain requires one
            max_tokens=kwargs.pop("max_tokens", 2048),
            **kwargs,
        )

    # ── OpenRouter (cloud, fallback) ──
    # Only used if OLLAMA_BASE_URL is not set
    default_model = os.environ.get("OPENROUTER_DEFAULT_MODEL", "google/gemma-3-27b-it:free")

    return ChatOpenAI(
        model=model or default_model,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_tokens=kwargs.pop("max_tokens", 2048),
        **kwargs,
    )
