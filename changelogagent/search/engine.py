"""Search across stored events and generated chronicle text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from changelogagent.core.db import EventStore
from changelogagent.core.models import ProjectEvent


@dataclass(slots=True)
class SearchResult:
    event: ProjectEvent
    snippet: str

    def to_dict(self) -> dict[str, object]:
        data = self.event.to_dict()
        data["snippet"] = self.snippet
        return data


class ChronicleSearch:
    def __init__(self, store: EventStore) -> None:
        self.store = store

    def search(
        self,
        query: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        target: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        return [SearchResult(event, self._snippet(event, query)) for event in self.store.search_events(query, start=start, end=end, target=target, limit=limit)]

    @staticmethod
    def _snippet(event: ProjectEvent, query: str) -> str:
        text = f"{event.title}. {event.description}".strip()
        if len(text) <= 180:
            return text
        term = next((item for item in query.split() if item.lower() in text.lower()), "")
        index = text.lower().find(term.lower()) if term else 0
        start = max(index - 60, 0)
        return text[start : start + 180].strip()
