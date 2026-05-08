"""SQLite storage for ChangelogAgent."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from changelogagent.core.models import ProjectEvent


class EventStore:
    """Small SQLite repository for project events."""

    def __init__(self, db_path: str | Path = ".changelogagent/changelogagent.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    importance_score REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_target ON events(target)")

    def add_event(self, event: ProjectEvent) -> ProjectEvent:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events
                (id, event_type, source, target, title, description, metadata, timestamp, importance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.event_type.value,
                    event.source,
                    event.target,
                    event.title,
                    event.description,
                    json.dumps(event.metadata, sort_keys=True),
                    event.timestamp.isoformat(),
                    event.importance_score,
                ),
            )
        return event

    def add_events(self, events: Iterable[ProjectEvent]) -> list[ProjectEvent]:
        saved = []
        for event in events:
            saved.append(self.add_event(event))
        return saved

    def list_events(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        target: str | None = None,
        event_type: str | None = None,
    ) -> list[ProjectEvent]:
        clauses: list[str] = []
        params: list[object] = []
        if start:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("timestamp <= ?")
            params.append(end.isoformat())
        if target:
            clauses.append("target = ?")
            params.append(target)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM events {where} ORDER BY timestamp ASC", params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def clear(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM events")

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> ProjectEvent:
        return ProjectEvent.from_dict(
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "source": row["source"],
                "target": row["target"],
                "title": row["title"],
                "description": row["description"],
                "metadata": json.loads(row["metadata"]),
                "timestamp": row["timestamp"],
                "importance_score": row["importance_score"],
            }
        )
