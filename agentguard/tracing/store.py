"""SQLite store for traces. One row per run; the spans are kept as JSON in the OpenTelemetry-like
shape produced by `Trace.to_dict()`."""

import json
import secrets
import sqlite3
import time
from pathlib import Path

DEFAULT_PATH = Path("results/traces.sqlite3")


class TraceStore:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS traces (id TEXT PRIMARY KEY, label TEXT, created REAL, "
            "meta TEXT, spans TEXT)"
        )
        self.db.commit()

    def save(self, trace, label: str = "", meta: dict | None = None) -> str:
        trace_id = secrets.token_hex(6)
        self.db.execute(
            "INSERT INTO traces VALUES (?,?,?,?,?)",
            (
                trace_id,
                label,
                time.time(),
                json.dumps(meta or {}),
                json.dumps(trace.to_dict()["spans"], ensure_ascii=False),
            ),
        )
        self.db.commit()
        return trace_id

    def get(self, trace_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT id, label, created, meta, spans FROM traces WHERE id = ?", (trace_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "label": row[1],
            "created": row[2],
            "meta": json.loads(row[3]),
            "spans": json.loads(row[4]),
        }

    def find_by_label(self, label: str) -> list[str]:
        rows = self.db.execute(
            "SELECT id FROM traces WHERE label = ? ORDER BY created", (label,)
        ).fetchall()
        return [r[0] for r in rows]

    def recent(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, label, created FROM traces ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"id": i, "label": label, "created": c} for i, label, c in rows]

    def sink(self):
        """A function the runner can call with (label, trace)."""

        def save(label: str, trace) -> None:
            self.save(trace, label)

        return save

    def close(self) -> None:
        self.db.close()
