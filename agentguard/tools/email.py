"""Mock email. Nothing is ever sent: messages go into the `outbox` table."""

from agentguard.tools.base import Tool, ToolResult
from agentguard.tools.env import Environment


def make_email(env: Environment) -> Tool:
    def run(args: dict) -> ToolResult:
        action = args.get("action")
        if action == "send":
            if not args.get("to"):
                return ToolResult("'to' is required", error=True)
            env.db.execute(
                "INSERT INTO outbox (recipient, subject, body) VALUES (?,?,?)",
                (args["to"], args.get("subject", ""), args.get("body", "")),
            )
            env.db.commit()
            return ToolResult(f"Email queued to {args['to']}.")
        if action == "read_inbox":
            rows = env.db.execute(
                "SELECT sender, subject, body FROM inbox ORDER BY id DESC LIMIT ?",
                (int(args.get("limit", 1)),),
            ).fetchall()
            text = "\n---\n".join(f"From: {s}\nSubject: {sub}\n{b}" for s, sub, b in rows)
            return ToolResult(text or "Inbox is empty.", trusted=False)
        return ToolResult("action must be send or read_inbox", error=True)

    return Tool(
        "email",
        "email(action, to, subject, body, limit): action is send (to, subject, body) or "
        "read_inbox (limit = number of newest messages)",
        run,
        sensitive=True,
    )
