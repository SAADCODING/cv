"""Thin wrapper around the Anthropic API for structured-output calls."""

import json

import anthropic

from .config import ANTHROPIC_MODEL

_client: anthropic.Anthropic | None = None


class LLMError(Exception):
    """Raised when an LLM call fails in a way the caller should surface to the user."""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        try:
            _client = anthropic.Anthropic()
        except anthropic.AnthropicError as e:
            raise LLMError(
                "Anthropic client could not be created. Set ANTHROPIC_API_KEY in "
                "job-agent/backend/.env (see .env.example). Details: " + str(e)
            ) from e
    return _client


def structured(system: str, user: str, schema: dict, max_tokens: int = 8192) -> dict:
    """Run one structured-output completion and return the parsed JSON object."""
    client = _get_client()
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic API key is invalid or missing (401).") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Anthropic API rate limit hit; wait a moment and retry.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Anthropic API (network error).") from e
    except TypeError as e:
        # The SDK raises TypeError at request time when no credentials are configured.
        if "authentication" in str(e).lower():
            raise LLMError(
                "No Anthropic API key configured. Copy job-agent/backend/.env.example "
                "to .env and set ANTHROPIC_API_KEY."
            ) from e
        raise

    if response.stop_reason == "refusal":
        raise LLMError("The model declined to process this content.")
    if response.stop_reason == "max_tokens":
        raise LLMError("Model output was truncated (max_tokens). Try a smaller input.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LLMError("Model returned no text content.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError("Model returned invalid JSON.") from e
