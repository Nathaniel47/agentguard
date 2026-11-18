"""Prompt text. The protocol is plain JSON in the reply so any chat model can follow it."""

from agentguard.tools.base import Tool

SYSTEM = """You are a helpful office assistant with tools. Work step by step.
Reply with exactly one JSON object and nothing else:
  {{"tool": "<tool name>", "args": {{...}}}}   to use a tool, or
  {{"final": "<answer for the user>"}}   when you are done.
Tools:
{tools}
Use a tool only when you need it. Keep answers short."""


def system_prompt(tools: dict[str, Tool]) -> str:
    return SYSTEM.format(tools="\n".join(f"- {t.description}" for t in tools.values()))


def build_prompt(user_task: str, log: list[tuple[str, str]], extra: str = "") -> str:
    """`log` is a list of (tool_call_json, observation_text) pairs so far."""
    parts = [f"User request: {user_task}"]
    if extra:
        parts.insert(0, extra)
    for i, (call, obs) in enumerate(log, 1):
        parts.append(f"Step {i} action: {call}\nStep {i} tool result: {obs}")
    parts.append("Your next JSON reply:")
    return "\n\n".join(parts)
