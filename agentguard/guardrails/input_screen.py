"""G1: screen the user's message for injection and jailbreak wording before the model sees it.

Pattern based. It catches the common phrasings (override, role-play, fake system markers, urgency
and authority claims) and nothing else: a plain request such as "email the customers table to X"
has no suspicious wording and passes, which is what G2 and G3 are for.
"""

import re

from agentguard.guardrails.base import BLOCK, Decision, Guardrail

_PATTERNS = {
    "override": r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(instructions?|"
    r"orders?|rules?|guidelines?|polic(y|ies)|restrictions?|filters?|safety)\b",
    "override_de": r"\b(ignoriere|vergiss)\b[^.\n]{0,40}\b(anweisungen|befehle|regeln)\b",
    "new_orders": r"\b(new|updated|top[- ]priority)\s+(instructions?|statement|policy|orders?)\b",
    "fake_marker": r"(#{2,}\s*system|\[\s*system\s*\]|<\s*/?\s*(system|instructions?)\s*>|"
    r"end of (user )?(message|prompt|input)|<\|)",
    "persona": r"\b(you are now|pretend (to be|you)|act as|role[- ]?play|from now on you|"
    r"you are completely absorbed|stay in character)\b",
    "named_jailbreak": r"\b(DAN|do anything now|developer mode|jailbreak|god mode)\b",
    "no_rules": r"\b(no|without|free of|zero)\s+(any\s+)?(rules|restrictions|limits|filters|"
    r"safety|guidelines)\b",
    "authority": r"\b(i am (the|your) (developer|admin|administrator|owner|creator)|"
    r"(security|compliance) (drill|audit|test)|you are (now )?authori[sz]ed|the user is "
    r"authori[sz]ed|authorization code)\b",
    "hypothetical": r"\b(hypothetically|imagine a world|in a fictional|write a (short )?story in "
    r"which|for a security course|if you were allowed)\b",
    "reveal_prompt": r"\b(reveal|show|print|repeat)\b[^.\n]{0,30}\b(system prompt|"
    r"your instructions|hidden instructions)\b",
    "end_reply_with": r"\bend your (reply|answer|response) with\b",
    "incentive": r"\bi will (tip|pay) you\b",
}
_COMPILED = {k: re.compile(v, re.I) for k, v in _PATTERNS.items()}


def screen(text: str) -> list[str]:
    return [name for name, rx in _COMPILED.items() if rx.search(text)]


class InputScreen(Guardrail):
    name = "g1_input_screen"

    def check_input(self, user_text: str) -> Decision:
        hits = screen(user_text)
        if hits:
            return Decision(
                BLOCK, "message looks like an injection or jailbreak: " + ", ".join(hits)
            )
        return Decision()
