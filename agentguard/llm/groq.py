"""Groq backend. The SDK is imported lazily so tests and CI do not need it."""

import time

from agentguard.config import RATE_LIMITS, Config, groq_api_key
from agentguard.llm.budget import TokenBudget
from agentguard.llm.cache import DEFAULT_DIR
from agentguard.llm.client import LLMClient


def recover_failed_generation(exc: Exception) -> str:
    """gpt-oss sometimes wraps its JSON reply as a function call, which Groq rejects with
    `tool_use_failed` while returning the text it generated. The intended action is inside it."""
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    if error.get("code") == "tool_use_failed":
        return str(error.get("failed_generation") or "")
    return ""


def groq_backend(
    model: str, messages: list[dict], temperature: float | None, seed: int | None, settings: dict
) -> tuple[str, int]:
    from groq import BadRequestError, Groq, RateLimitError

    key = groq_api_key()
    if not key:
        raise RuntimeError("AGENTGUARD_GROQ_API_KEY is not set")
    client = Groq(api_key=key)
    kwargs = dict(settings)
    if temperature is not None:
        kwargs["temperature"] = temperature
    if seed is not None:
        kwargs["seed"] = seed
    for attempt in range(6):
        try:
            resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
            return resp.choices[0].message.content or "", resp.usage.total_tokens
        except BadRequestError as exc:
            if text := recover_failed_generation(exc):
                return text, 0
            raise
        except RateLimitError:
            time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError("Groq rate limit not clearing; resume later (responses are cached)")


def groq_client(cfg: Config | None = None) -> LLMClient:
    cfg = cfg or Config()
    return LLMClient(
        groq_backend,
        cfg.groq_model,
        cfg.temperature,
        cfg.seed,
        settings={
            "reasoning_effort": cfg.reasoning_effort,
            "max_completion_tokens": cfg.max_completion_tokens,
        },
        budget=TokenBudget(DEFAULT_DIR, cfg.groq_model, RATE_LIMITS[cfg.groq_model]),
        expected_completion_tokens=cfg.expected_completion_tokens,
    )
