"""Hook points the agent loop calls. A guardrail overrides only the checks it cares about."""

from dataclasses import dataclass, field

from agentguard.tools.base import Tool, ToolResult

ALLOW, BLOCK, FLAG = "allow", "block", "flag"


@dataclass
class Decision:
    action: str = ALLOW
    reason: str = ""
    replacement: str | None = None  # text to use instead (e.g. a redacted answer)


class Guardrail:
    name = "base"

    def handles(self, hook: str) -> bool:
        """True when this guardrail overrides the check for `hook` (input, tool_call, ...)."""
        method = "check_" + hook
        return getattr(type(self), method) is not getattr(Guardrail, method)

    def check_input(self, user_text: str) -> Decision:
        return Decision()

    def check_tool_call(self, tool: Tool, args: dict, state: "RunState") -> Decision:
        return Decision()

    def check_tool_result(self, tool: Tool, result: ToolResult, state: "RunState") -> Decision:
        return Decision()

    def check_memory_write(self, text: str, state: "RunState") -> Decision:
        return Decision()

    def check_output(self, text: str) -> Decision:
        return Decision()


@dataclass
class RunState:
    """What guardrails may look at while a run is in progress."""

    user_task: str
    # Set once any untrusted content (tool result or recalled untrusted memory) is in the context.
    saw_untrusted: bool = False
    step: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
