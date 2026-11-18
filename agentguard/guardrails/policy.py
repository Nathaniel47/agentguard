"""Small helpers shared by the tool-level guardrails."""

import re

from agentguard.tools.base import Tool

_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.I)


def is_read_only_sql(sql: str) -> bool:
    return bool(_READ_ONLY_SQL.match(sql)) and ";" not in sql.strip().rstrip(";")


def is_sensitive_call(tool: Tool, args: dict) -> bool:
    """Does this call change the world or send data out? Reading never counts."""
    if tool.name == "email":
        return args.get("action") == "send"
    if tool.name == "database":
        return not is_read_only_sql(str(args.get("sql", "")))
    if tool.name == "calendar":
        return args.get("action") in ("add", "delete")
    return tool.name == "run_code"
