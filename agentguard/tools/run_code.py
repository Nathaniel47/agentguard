from agentguard.tools.base import Tool, ToolResult
from agentguard.tools.env import Environment


def make_run_code(env: Environment) -> Tool:
    def run(args: dict) -> ToolResult:
        res = env.sandbox.run(str(args.get("code", "")))
        if res.rejected:
            return ToolResult(f"Code rejected: {res.rejected}", error=True)
        if res.timed_out:
            return ToolResult("Code stopped: time limit reached.", error=True)
        if res.memory_killed:
            return ToolResult("Code stopped: memory limit reached.", error=True)
        text = res.stdout.strip() or res.stderr.strip() or "(no output)"
        return ToolResult(text, error=res.exit_code != 0)

    return Tool("run_code", "run_code(code): run Python code and return what it prints", run)
