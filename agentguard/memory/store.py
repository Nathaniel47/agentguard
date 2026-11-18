"""Long-term memory in SQLite. Every entry keeps who wrote it and whether untrusted content was
in the agent's context at the time, so later guardrails and the trace can tell notes the user
asked for from notes the agent copied out of a web page or an email."""

import sqlite3
from dataclasses import dataclass

from agentguard.tools.search import _terms

CONTEXT_HEADER = "Notes saved in earlier sessions:"


@dataclass
class MemoryEntry:
    id: int
    text: str
    source: str  # "user" | "agent" | "agent_after_untrusted"
    trusted: bool


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "text TEXT, source TEXT, trusted INTEGER)"
        )
        self.db.commit()

    def remember(self, text: str, source: str, trusted: bool) -> int:
        cur = self.db.execute(
            "INSERT INTO memory (text, source, trusted) VALUES (?,?,?)",
            (text, source, int(trusted)),
        )
        self.db.commit()
        return cur.lastrowid

    def entries(self) -> list[MemoryEntry]:
        rows = self.db.execute(
            "SELECT id, text, source, trusted FROM memory ORDER BY id"
        ).fetchall()
        return [MemoryEntry(i, t, s, bool(tr)) for i, t, s, tr in rows]

    def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Entries that share words with the query first, then the newest ones."""
        terms = _terms(query)
        ranked = sorted(self.entries(), key=lambda e: (-len(terms & _terms(e.text)), -e.id))
        return ranked[:limit]

    def close(self) -> None:
        self.db.close()


def format_context(entries: list[MemoryEntry]) -> str:
    if not entries:
        return ""
    return CONTEXT_HEADER + "\n" + "\n".join(f"- {e.text}" for e in entries)
