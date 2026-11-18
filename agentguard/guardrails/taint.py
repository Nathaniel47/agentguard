"""G3: untrusted-content taint. Once content written by someone else has entered the context
(a page, an inbox message, a calendar title, a database row, a recalled untrusted note), calls to
tools that change things or send data out are refused. In a real product this would be a
"confirm?" prompt to the user; the harness has no user, so it counts as a refusal."""

from agentguard.guardrails.base import BLOCK, Decision, Guardrail, RunState
from agentguard.guardrails.policy import is_sensitive_call
from agentguard.tools.base import Tool


class TaintGuard(Guardrail):
    name = "g3_taint"

    def check_tool_call(self, tool: Tool, args: dict, state: RunState) -> Decision:
        if state.saw_untrusted and is_sensitive_call(tool, args):
            return Decision(
                BLOCK,
                f"{tool.name} would act after reading untrusted content; user confirmation needed",
            )
        return Decision()
