"""Central settings: guardrail switches, agent limits and secrets from the environment."""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

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
    # Verified and recorded in week 1 (see PLAN.md risk 1); empty until then.
    groq_model: str = ""
    gemini_model: str = ""
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
