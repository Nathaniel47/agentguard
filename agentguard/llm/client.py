"""The single entry point for LLM calls: cache first, then a pluggable backend.

Token budgeting and the Groq/Gemini backends are added in Step 4.
"""

from collections.abc import Callable

from agentguard.llm.cache import ResponseCache, cache_key

# backend(model, messages, temperature, seed, settings) -> (text, tokens_used)
Backend = Callable[[str, list[dict], float | None, int | None, dict], tuple[str, int]]


class LLMClient:
    def __init__(
        self,
        backend: Backend,
        model: str,
        temperature: float | None,
        seed: int | None,
        cache: ResponseCache | None = None,
        settings: dict | None = None,
    ):
        self.backend = backend
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.cache = cache or ResponseCache()
        self.settings = settings or {}
        self.calls = 0
        self.cache_hits = 0
        self.tokens_used = 0

    def complete(self, prompt: str, system: str | None = None, repeat: int = 0) -> str:
        """`repeat` is part of the cache key so repeated runs stay independent."""
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        key = cache_key(self.model, messages, self.temperature, self.seed, repeat, self.settings)
        hit = self.cache.get(key)
        if hit is not None:
            self.cache_hits += 1
            return hit
        text, tokens = self.backend(
            self.model, messages, self.temperature, self.seed, self.settings
        )
        self.calls += 1
        self.tokens_used += tokens
        self.cache.put(key, text)
        return text
