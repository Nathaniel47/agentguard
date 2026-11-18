"""The simple baseline G1 is compared against: a blocklist of the most famous injection phrases.
It is what a first quick fix looks like, so it shows how much the richer guardrails add."""

from agentguard.guardrails.base import BLOCK, Decision, Guardrail

PHRASES = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore the above",
    "disregard your instructions",
    "reveal your system prompt",
)


class KeywordBlocklist(Guardrail):
    name = "baseline_keyword"

    def check_input(self, user_text: str) -> Decision:
        low = " ".join(user_text.lower().split())
        for phrase in PHRASES:
            if phrase in low:
                return Decision(BLOCK, f"contains '{phrase}'")
        return Decision()
