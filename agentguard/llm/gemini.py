"""Gemini backend for the confirmation run. The SDK is imported lazily so CI needs no key."""

from agentguard.config import GEMINI_LIMITS, Config, gemini_api_key
from agentguard.llm.budget import TokenBudget
from agentguard.llm.cache import DEFAULT_DIR
from agentguard.llm.client import LLMClient


def gemini_backend(
    model: str, messages: list[dict], temperature: float | None, seed: int | None, settings: dict
) -> tuple[str, int]:
    from google import genai
    from google.genai import types

    key = gemini_api_key()
    if not key:
        raise RuntimeError("AGENTGUARD_GEMINI_API_KEY is not set")
    system = "\n".join(m["content"] for m in messages if m["role"] == "system") or None
    user = "\n".join(m["content"] for m in messages if m["role"] == "user")
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        seed=seed,
        max_output_tokens=settings.get("max_completion_tokens"),
    )
    resp = genai.Client(api_key=key).models.generate_content(
        model=model, contents=user, config=config
    )
    used = resp.usage_metadata.total_token_count if resp.usage_metadata else 0
    return resp.text or "", used


def gemini_client(cfg: Config | None = None) -> LLMClient:
    cfg = cfg or Config()
    return LLMClient(
        gemini_backend,
        cfg.gemini_model,
        cfg.temperature,
        cfg.seed,
        settings={"max_completion_tokens": cfg.max_completion_tokens},
        budget=TokenBudget(DEFAULT_DIR, cfg.gemini_model, GEMINI_LIMITS),
        expected_completion_tokens=cfg.expected_completion_tokens,
    )
