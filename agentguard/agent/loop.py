"""The agent loop: ask the model for an action, run it, show it the result, repeat."""

import json
import re
from dataclasses import dataclass, field

from agentguard.agent.prompt import build_prompt, system_prompt
from agentguard.config import Config
from agentguard.guardrails.base import BLOCK, FLAG, Decision, Guardrail, RunState
from agentguard.llm.client import LLMClient
from agentguard.memory.store import MemoryStore, format_context
from agentguard.tools.base import Tool, ToolResult
from agentguard.tracing.spans import Trace

REFUSAL = "I can't help with that request."
MAX_OBSERVATION_CHARS = 1500


@dataclass
class RunResult:
    answer: str
    status: str  # "answered" | "step_limit" | "blocked_input" | "bad_output"
    steps: int
    trace: Trace
    tool_calls: list[dict] = field(default_factory=list)


def parse_action(text: str) -> dict | None:
    """Find the first JSON object in the reply. Models sometimes wrap it in prose or fences."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            if depth == 0:
                try:
                    obj = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    break
                if isinstance(obj, dict) and ("tool" in obj or "final" in obj or "remember" in obj):
                    return obj
                break
        start = text.find("{", start + 1)
    return None


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: dict[str, Tool],
        config: Config | None = None,
        guardrails: list[Guardrail] | None = None,
        memory: MemoryStore | None = None,
    ):
        self.llm, self.tools, self.memory = llm, tools, memory
        self.config = config or Config()
        self.guardrails = guardrails or []
        self.system = system_prompt(tools)

    def _for(self, hook: str) -> list[Guardrail]:
        """Guardrails that implement this hook; the others are not recorded as having looked."""
        return [g for g in self.guardrails if g.handles(hook)]

    def _decide(self, trace: Trace, hook: str, name: str, decision: Decision, **attrs) -> Decision:
        trace.add(
            "guardrail", name, hook=hook, action=decision.action, reason=decision.reason, **attrs
        )
        return decision

    def run(self, user_task: str, extra_context: str = "", repeat: int = 0) -> RunResult:
        trace = Trace()
        state = RunState(user_task)
        trace.add("input", "user_task", text=user_task)
        for g in self._for("input"):
            d = self._decide(trace, "input", g.name, g.check_input(user_task))
            if d.action == BLOCK:
                return RunResult(REFUSAL, "blocked_input", 0, trace)

        if self.memory is not None:
            recalled = self.memory.recall(user_task)
            if recalled:
                trace.add(
                    "memory",
                    "recall",
                    ids=[e.id for e in recalled],
                    untrusted=[e.id for e in recalled if not e.trusted],
                )
                parts = (extra_context, format_context(recalled))
                extra_context = "\n\n".join(p for p in parts if p)
                state.saw_untrusted = any(not e.trusted for e in recalled)

        log: list[tuple[str, str]] = []
        calls: list[dict] = []
        answer, status = "", "step_limit"
        for step in range(1, self.config.max_steps + 1):
            state.step = step
            prompt = build_prompt(user_task, log, extra_context)
            t0, tokens0 = trace.now(), self.llm.tokens_used
            reply = self.llm.complete(prompt, system=self.system, repeat=repeat)
            trace.add(
                "llm", "complete", t0, tokens=self.llm.tokens_used - tokens0, reply=reply[:500]
            )
            action = parse_action(reply)
            if action is None:
                log.append(
                    ("(invalid reply)", "Reply was not valid JSON. Answer with one JSON object.")
                )
                continue
            if "final" in action:
                answer, status = str(action["final"]), "answered"
                break
            if "remember" in action:
                obs = self._remember(trace, state, str(action["remember"]))
            else:
                obs = self._call_tool(trace, state, action, calls)
            log.append((json.dumps(action, ensure_ascii=False), obs))

        for g in self._for("output"):
            d = self._decide(trace, "output", g.name, g.check_output(answer))
            if d.action == BLOCK:
                answer, status = d.replacement or REFUSAL, "bad_output"
            elif d.replacement is not None:
                answer = d.replacement
        trace.add("output", "final_answer", text=answer, status=status)
        return RunResult(answer, status, len(log), trace, calls)

    def _remember(self, trace: Trace, state: RunState, text: str) -> str:
        if self.memory is None:
            return "Memory is not available."
        for g in self._for("memory_write"):
            d = self._decide(trace, "memory_write", g.name, g.check_memory_write(text, state))
            if d.action == BLOCK:
                trace.add("memory", "write_blocked", text=text[:300])
                return f"Memory write blocked by policy: {d.reason}"
        source = "agent_after_untrusted" if state.saw_untrusted else "agent"
        entry_id = self.memory.remember(text, source, trusted=not state.saw_untrusted)
        trace.add("memory", "write", id=entry_id, source=source, text=text[:300])
        return "Saved to memory."

    def _call_tool(self, trace: Trace, state: RunState, action: dict, calls: list[dict]) -> str:
        name, args = str(action.get("tool")), action.get("args") or {}
        tool = self.tools.get(name)
        if tool is None or not isinstance(args, dict):
            return f"Unknown tool or bad arguments. Tools: {', '.join(self.tools)}"
        for g in self._for("tool_call"):
            d = self._decide(
                trace, "tool_call", g.name, g.check_tool_call(tool, args, state), tool=name
            )
            if d.action == BLOCK:
                trace.add("tool", name, args=args, blocked=True)
                return f"Blocked by policy: {d.reason}"
        t0 = trace.now()
        result: ToolResult = tool.run(args)
        calls.append({"tool": name, "args": args, "error": result.error})
        state.tool_counts[name] = state.tool_counts.get(name, 0) + 1
        trace.add("tool", name, t0, args=args, result=result.text[:500], trusted=result.trusted)
        text = result.text
        for g in self._for("tool_result"):
            d = self._decide(
                trace, "tool_result", g.name, g.check_tool_result(tool, result, state), tool=name
            )
            if d.action == BLOCK:
                text = f"Result withheld by policy: {d.reason}"
            elif d.action == FLAG and d.replacement is not None:
                text = d.replacement
        if not result.trusted:
            state.saw_untrusted = True
        return re.sub(r"\s+\n", "\n", text)[:MAX_OBSERVATION_CHARS]
