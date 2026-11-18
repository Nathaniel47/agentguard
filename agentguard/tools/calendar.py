from agentguard.tools.base import Tool, ToolResult
from agentguard.tools.env import Environment


def make_calendar(env: Environment) -> Tool:
    def run(args: dict) -> ToolResult:
        action = args.get("action")
        if action == "list":
            rows = env.db.execute(
                "SELECT id, date, time, title FROM calendar WHERE date = ? OR ? IS NULL "
                "ORDER BY date, time",
                (args.get("date"), args.get("date")),
            ).fetchall()
            text = "\n".join(f"{i} | {d} {t} | {title}" for i, d, t, title in rows)
            return ToolResult(text or "No events.", trusted=False)
        if action == "add":
            cur = env.db.execute(
                "INSERT INTO calendar (date, time, title) VALUES (?,?,?)",
                (args.get("date"), args.get("time"), args.get("title")),
            )
            env.db.commit()
            return ToolResult(f"Added event {cur.lastrowid}.")
        if action == "delete":
            cur = env.db.execute("DELETE FROM calendar WHERE id = ?", (args.get("event_id"),))
            env.db.commit()
            return ToolResult(f"Deleted {cur.rowcount} event(s).")
        return ToolResult("action must be list, add or delete", error=True)

    return Tool(
        "calendar",
        "calendar(action, date, time, title, event_id): action is list (optional date), "
        "add (date, time, title) or delete (event_id)",
        run,
        sensitive=True,
    )
