"""Central settings: guardrail switches, agent limits and secrets from the environment."""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

GROQ_MODEL = "openai/gpt-oss-20b"

# Free-tier limits the owner reported for Groq on 2026-10-16 (per organisation); recheck in the
# smoke test. rpm/rpd = requests per minute/day, tpm/tpd = tokens per minute/day (UTC reset).
RATE_LIMITS: dict[str, dict[str, int]] = {
    GROQ_MODEL: {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200_000},
}
# Assumed, not verified. Deliberately low.
GEMINI_LIMITS = {"rpm": 10, "rpd": 200, "tpm": 100_000, "tpd": 1_000_000}

GUARDRAILS = (
    "g1_input_screen",
    "g2_tool_policy",
    "g3_taint",
    "g4_memory_gate",
    "g5_output_filter",
)

# Evaluated configurations: no guardrails, each one alone, and all five together.
CONFIGS: dict[str, tuple[str, ...]] = {
    "none": (),
    **{name.split("_")[0]: (name,) for name in GUARDRAILS},
    "all": GUARDRAILS,
}


@dataclass(frozen=True)
class Config:
    max_steps: int = 6
    temperature: float = 0.0
    seed: int = 42
    # Candidates from the owner's other projects; not yet smoke-tested (PLAN.md risk 1).
    groq_model: str = GROQ_MODEL
    reasoning_effort: str = "low"
    max_completion_tokens: int = 400
    expected_completion_tokens: int = 150
    gemini_model: str = "gemini-3.5-flash-lite"
    guardrails: frozenset[str] = field(default_factory=frozenset)

    def with_guardrails(self, *names: str) -> "Config":
        unknown = set(names) - set(GUARDRAILS)
        if unknown:
            raise ValueError(f"unknown guardrails: {sorted(unknown)}")
        return replace(self, guardrails=frozenset(names))

    def enabled(self, name: str) -> bool:
        return name in self.guardrails


def load_env(path: Path = Path(".env")) -> None:
    """Copy AGENTGUARD_* lines from a local .env into the environment (never overriding it)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.partition("=")
        name = name.strip()
        if sep and name.startswith("AGENTGUARD_") and value.strip():
            os.environ.setdefault(name, value.strip().strip("\"'"))


def groq_api_key() -> str | None:
    return os.environ.get("AGENTGUARD_GROQ_API_KEY") or None


def gemini_api_key() -> str | None:
    return os.environ.get("AGENTGUARD_GEMINI_API_KEY") or None
