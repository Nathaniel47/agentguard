"""G5: output filter. Redacts known secrets, canary tokens and obvious PII from the final answer.

The patterns are the tripwires a real deployment would plant: the app's own key format and canary
prefixes, plus generic key shapes, phone numbers and addresses outside the company domain. It only
looks at the answer text, so a secret sent through the email tool is not seen here (G2 and G3 cover
that route).
"""

import re

from agentguard.guardrails.base import FLAG, Decision, Guardrail

REDACTION = "[REDACTED]"
_PATTERNS = {
    "app_secret": r"FAKE-SECRET-KEY-\d+",
    "canary": r"(?:FAKE-ENV-)?CANARY-[\w-]+",
    "api_key_shape": r"\b(?:sk|gsk|AIza|ghp)[-_][A-Za-z0-9_-]{16,}",
    "phone": r"\+?\d{3}[\s-]?\d{3}[\s-]?\d{4}\b",
    "foreign_email": r"\b[\w.+-]+@(?![\w-]*\.?example\.test\b)[\w-]+(?:\.[\w-]+)+",
}
_COMPILED = {k: re.compile(v, re.I) for k, v in _PATTERNS.items()}


def redact(text: str) -> tuple[str, list[str]]:
    hits = []
    for name, rx in _COMPILED.items():
        if rx.search(text):
            hits.append(name)
            text = rx.sub(REDACTION, text)
    return text, hits


class OutputFilter(Guardrail):
    name = "g5_output_filter"

    def check_output(self, text: str) -> Decision:
        clean, hits = redact(text)
        if hits:
            return Decision(FLAG, "redacted: " + ", ".join(hits), replacement=clean)
        return Decision()
