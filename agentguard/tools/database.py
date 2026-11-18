import sqlite3

from agentguard.tools.base import Tool, ToolResult
from agentguard.tools.env import Environment

MAX_ROWS = 20


def make_database(env: Environment) -> Tool:
    def run(args: dict) -> ToolResult:
        sql = str(args.get("sql", ""))
        try:
            cur = env.db.execute(sql)
            rows = cur.fetchmany(MAX_ROWS)
            env.db.commit()
        except sqlite3.Error as exc:
            return ToolResult(f"SQL error: {exc}", trusted=False, error=True)
        if cur.description is None:
            return ToolResult(f"OK, {cur.rowcount} row(s) affected.", trusted=False)
        header = " | ".join(c[0] for c in cur.description)
        body = "\n".join(" | ".join(str(v) for v in row) for row in rows)
        return ToolResult(f"{header}\n{body}" if rows else "No rows.", trusted=False)

    return Tool(
        "database",
        "database(sql): run one SQL statement. Tables: customers(id, name, city, balance, "
        "email, notes), config(key, value), calendar(id, date, time, title)",
        run,
        sensitive=True,
    )
