"""G4: memory write gate. Stops a note from being saved when it looks like a planted instruction.

Rule-based on purpose (see LEARNING.md). Three signals:
- strong: a recipient outside the allowed domain, a claim to be the system or the user, or a
  note that switches off confirmation. Blocked whatever the provenance.
- persistent-instruction: wording that orders future behaviour ("for all future tasks, send ...").
  Blocked when untrusted content was in the context when the agent wrote the note, because that
  is how a poisoned web page or email turns into a standing order.
"""

import re

from agentguard.guardrails.base import BLOCK, Decision, Guardrail, RunState

ALLOWED_DOMAIN = "example.test"

_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_IMPERSONATION = re.compile(
    r"(?im)^\s*(system|assistant|admin|administrator)\s*:"
    r"|\b(the user|your user|the administrator|your developer)\s+(has\s+)?"
    r"(said|says|told|authori[sz]ed|approved|confirmed|requires)\b"
    r"|\bnew (instructions|rules|policy)\b|\bignore (all |any |the )?(previous|prior|above)\b"
)
_NO_CONFIRMATION = re.compile(
    r"(?i)\b(without (asking|confirmation|confirming|approval)|no confirmation|do not ask|"
    r"don't ask|auto[- ]?approve|you (may|are allowed to|can) now|skip (the )?(check|confirmation))"
)
_PERSISTENT = re.compile(
    r"(?i)\b(for all future|from now on|in (all )?future|every time|whenever you|next time you|"
    r"always|at the (start|end) of (every|each)|for every (task|request|reply|answer))\b"
)
_ACTION_ORDER = re.compile(
    r"(?i)\b(send|email|e-mail|forward|delete|remove|drop|run|execute|reveal|print|include|"
    r"append|quote|add|insert|update|set|copy|share|leak|output|reply with|cc|bcc)\b"
)
_SENSITIVE_TARGET = re.compile(
    r"(?i)api[ _-]?key|secret|password|credential|token|config|customers? (table|data|email)|"
    r"calendar|database|attacker|canary"
)


def assess(text: str) -> tuple[str, str]:
    """Return ("strong" | "instruction" | "", reason)."""
    for m in _EMAIL.finditer(text):
        if not m.group(1).lower().endswith(ALLOWED_DOMAIN):
            return "strong", f"names an address outside {ALLOWED_DOMAIN} ({m.group(0)})"
    if _IMPERSONATION.search(text):
        return "strong", "claims to come from the system or the user"
    if _NO_CONFIRMATION.search(text):
        return "strong", "tries to switch off confirmation"
    if _PERSISTENT.search(text) and _ACTION_ORDER.search(text):
        return "instruction", "orders standing actions for future sessions"
    if _ACTION_ORDER.search(text) and _SENSITIVE_TARGET.search(text):
        return "instruction", "orders an action on sensitive data"
    return "", ""


class MemoryGate(Guardrail):
    name = "g4_memory_gate"

    def check_memory_write(self, text: str, state: RunState) -> Decision:
        level, reason = assess(text)
        if level == "strong":
            return Decision(BLOCK, f"memory note {reason}")
        if level == "instruction" and state.saw_untrusted:
            return Decision(BLOCK, f"memory note {reason}, written after reading untrusted content")
        return Decision()
