"""
LLM client — OpenAI-compatible API wrapper.

Reads configuration from config.py (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL).
Supports any OpenAI-compatible service: OpenAI, DeepSeek, Qwen, etc.
"""

from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    return _client


def ask_llm(messages: list) -> str:
    if not messages:
        raise ValueError("messages must not be empty")

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
        )
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}") from e

    choice = response.choices[0] if response.choices else None
    if choice is None or not choice.message or not choice.message.content:
        raise RuntimeError("LLM returned empty response")

    return choice.message.content
