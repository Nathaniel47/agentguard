"""Case schema for the red-team harness, plus JSONL load/save and validation."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CATEGORIES = (
    "direct_injection",
    "indirect_injection",
    "jailbreak",
    "tool_abuse",
    "memory_poisoning",
    "data_exfiltration",
    "sandbox_escape",
)
# Where the attacker's text enters the agent.
CHANNELS = ("user_message", "search_result", "email_body", "calendar_event", "db_row", "memory")
# How success is detected from state, never by a judge model. See PLAN.md.
GOAL_TYPES = (
    "canary_in_output",  # params: canary
    "email_to_attacker",  # params: recipient
    "secret_leaked",  # params: secret (in output or in an outbox message)
    "db_modified",  # params: table, expect ("row_deleted" | "row_changed")
    "calendar_modified",  # params: expect ("event_deleted" | "event_added")
    "file_escape",  # params: path_marker (sandbox code wrote outside its directory)
    "env_secret_read",  # params: secret (sandbox code printed the env canary)
    "resource_abuse",  # params: limit_s (code was still running past the time limit)
)
SOURCES = ("self", "injecagent", "deepset")


@dataclass
class Case:
    id: str
    category: str
    source: str
    channel: str
    user_task: str  # what the user asks the agent to do
    injection: str  # attacker-controlled text; for user_message cases it is the whole message
    goal_type: str
    goal: dict
    setup_task: str = ""  # memory cases: a first session that plants the entry
    split: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class BenignTask:
    id: str
    user_task: str
    check_type: str  # "answer_contains" | "outbox_has" | "calendar_has"
    check: dict
    split: str = ""


def validate_case(c: Case) -> list[str]:
    problems = []
    if c.category not in CATEGORIES:
        problems.append(f"{c.id}: bad category {c.category}")
    if c.channel not in CHANNELS:
        problems.append(f"{c.id}: bad channel {c.channel}")
    if c.goal_type not in GOAL_TYPES:
        problems.append(f"{c.id}: bad goal_type {c.goal_type}")
    if c.source not in SOURCES:
        problems.append(f"{c.id}: bad source {c.source}")
    if not c.injection.strip() or not c.user_task.strip():
        problems.append(f"{c.id}: empty text")
    if c.category == "memory_poisoning" and not c.setup_task:
        problems.append(f"{c.id}: memory case without setup_task")
    return problems


def save_jsonl(items: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for item in items:
            f.write(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n")


def load_cases(path: Path) -> list[Case]:
    with path.open(encoding="utf-8") as f:
        return [Case(**json.loads(line)) for line in f if line.strip()]


def load_benign(path: Path) -> list[BenignTask]:
    with path.open(encoding="utf-8") as f:
        return [BenignTask(**json.loads(line)) for line in f if line.strip()]
