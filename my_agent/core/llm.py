"""Shared LLM factory with cached API key retrieval.

Supports Google (Gemini), OpenAI (GPT), and Anthropic (Claude) models.

Usage in nodes:
    from my_agent.core.llm import get_llm
    llm = await get_llm(ModelConfig.ROUTER_MODEL, temperature=0)
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from my_agent.core.infisical_client import aget_secret

_cached_api_keys: dict[str, str] = {}

# Map model prefix → (provider name for LangChain, secret name in Infisical / env)
_PROVIDER_MAP = {
    "gemini": ("google_genai", "GEMINI_API_KEY"),
    "gpt-":   ("openai",       "OPENAI_API_KEY"),
    "o1":     ("openai",       "OPENAI_API_KEY"),
    "o3":     ("openai",       "OPENAI_API_KEY"),
    "o4":     ("openai",       "OPENAI_API_KEY"),
    "claude": ("anthropic",    "ANTHROPIC_API_KEY"),
}


def _resolve_provider(model: str) -> tuple[str, str]:
    """Return (langchain_provider, secret_name) for the given model identifier."""
    for prefix, (provider, secret) in _PROVIDER_MAP.items():
        if model.startswith(prefix):
            return provider, secret
    # Default to OpenAI for unknown models
    return "openai", "OPENAI_API_KEY"


async def _get_api_key(model: str) -> str:
    """Return cached API key for the corresponding model provider."""
    global _cached_api_keys

    provider, secret_name = _resolve_provider(model)

    if provider not in _cached_api_keys:
        _cached_api_keys[provider] = await aget_secret(secret_name)

    return _cached_api_keys[provider]


async def get_llm(
    model: str = "gpt-4o",
    temperature: float = 0,
) -> BaseChatModel:
    """Create a chat model instance using the cached API key.

    Supports models from Google (gemini-*), OpenAI (gpt-*, o1-*, o3-*, o4-*),
    and Anthropic (claude-*).

    Args:
        model: Model identifier (e.g. "gpt-4o", "gemini-2.5-flash", "claude-sonnet-4-20250514").
        temperature: Sampling temperature.

    Returns:
        Initialised LangChain chat model.
    """
    api_key = await _get_api_key(model)
    provider, _ = _resolve_provider(model)

    return init_chat_model(
        model=model,
        model_provider=provider,
        api_key=api_key,
        temperature=temperature,
    )
