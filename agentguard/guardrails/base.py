"""Hook points the agent loop calls. A guardrail overrides only the checks it cares about."""

from dataclasses import dataclass

from agentguard.tools.base import Tool, ToolResult

ALLOW, BLOCK, FLAG = "allow", "block", "flag"


@dataclass
class Decision:
    action: str = ALLOW
    reason: str = ""
    replacement: str | None = None  # text to use instead (e.g. a redacted answer)


class Guardrail:
    name = "base"

    def check_input(self, user_text: str) -> Decision:
        return Decision()

    def check_tool_call(self, tool: Tool, args: dict, state: "RunState") -> Decision:
        return Decision()

    def check_tool_result(self, tool: Tool, result: ToolResult, state: "RunState") -> Decision:
        return Decision()

    def check_output(self, text: str) -> Decision:
        return Decision()


@dataclass
class RunState:
    """What guardrails may look at while a run is in progress."""

    user_task: str
    saw_untrusted: bool = False  # set once any untrusted tool result entered the context
    step: int = 0
