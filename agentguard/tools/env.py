"""The per-run world the tools act on: an in-memory SQLite database, documents, a sandbox."""

import sqlite3

from agentguard.harness.world import CALENDAR, CUSTOMERS, DOCS, SECRET_API_KEY
from agentguard.tools.sandbox import Sandbox

PLANT_DOC = "refund-policy"
PLANT_EVENT_ID = 2
PLANT_CUSTOMER = "FAKE-C002"


class Environment:
    """Fresh for every case, so one attack can never affect another."""

    def __init__(self, strict_sandbox: bool = False, sandbox_timeout: float | None = None):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.executescript(
            """
            CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT, city TEXT, balance INTEGER,
                                    email TEXT, notes TEXT DEFAULT '');
            CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE calendar (id INTEGER PRIMARY KEY, date TEXT, time TEXT, title TEXT);
            CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT,
                                 subject TEXT, body TEXT);
            CREATE TABLE inbox (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT,
                                subject TEXT, body TEXT);
            """
        )
        self.db.executemany(
            "INSERT INTO customers (id, name, city, balance, email) VALUES (?,?,?,?,?)", CUSTOMERS
        )
        self.db.execute("INSERT INTO config VALUES ('api_key', ?)", (SECRET_API_KEY,))
        self.db.executemany("INSERT INTO calendar VALUES (?,?,?,?)", CALENDAR)
        self.db.execute(
            "INSERT INTO inbox (sender, subject, body) VALUES (?,?,?)",
            ("hr@example.test", "Office party", "The office party is on Friday at 5pm."),
        )
        self.db.commit()
        self.docs = {slug: {"title": title, "body": body} for slug, title, body in DOCS}
        self.sandbox = Sandbox(strict_sandbox, sandbox_timeout)

    def plant(self, channel: str, text: str) -> None:
        """Place attacker-controlled text where the given channel will surface it."""
        if channel in ("search_result", "memory"):
            self.docs[PLANT_DOC]["body"] += " " + text
        elif channel == "email_body":
            self.db.execute(
                "INSERT INTO inbox (sender, subject, body) VALUES (?,?,?)",
                ("newsletter@example.test", "Update", text),
            )
        elif channel == "calendar_event":
            self.db.execute(
                "UPDATE calendar SET title = title || ' - ' || ? WHERE id = ?",
                (text, PLANT_EVENT_ID),
            )
        elif channel == "db_row":
            self.db.execute("UPDATE customers SET notes = ? WHERE id = ?", (text, PLANT_CUSTOMER))
        elif channel != "user_message":
            raise ValueError(f"unknown channel {channel}")
        self.db.commit()

    def snapshot(self) -> dict:
        """Everything a success marker can look at. A dropped table reads as "no rows"."""

        def rows(sql: str) -> list[tuple]:
            try:
                return self.db.execute(sql).fetchall()
            except sqlite3.OperationalError:
                return []

        outbox_cols = ("recipient", "subject", "body")
        return {
            "customers": {
                r[0]: r for r in rows("SELECT id, name, city, balance, email FROM customers")
            },
            "calendar_ids": [r[0] for r in rows("SELECT id FROM calendar ORDER BY id")],
            "outbox": [
                dict(zip(outbox_cols, r, strict=True))
                for r in rows("SELECT recipient, subject, body FROM outbox ORDER BY id")
            ],
        }

    def close(self) -> None:
        self.db.close()
        self.sandbox.close()
