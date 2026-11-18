from agentguard.tools.base import Tool
from agentguard.tools.calendar import make_calendar
from agentguard.tools.database import make_database
from agentguard.tools.email import make_email
from agentguard.tools.env import Environment
from agentguard.tools.run_code import make_run_code
from agentguard.tools.search import make_search


def build_tools(env: Environment) -> dict[str, Tool]:
    tools = [
        make_search(env),
        make_run_code(env),
        make_calendar(env),
        make_email(env),
        make_database(env),
    ]
    return {t.name: t for t in tools}
