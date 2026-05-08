"""Build chronological sequences from events."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from changelogagent.core.models import EventSequence, ProjectEvent


class TimelineBuilder:
    """Group events into related chronological sequences."""

    def __init__(self, max_gap_hours: int = 72) -> None:
        self.max_gap = timedelta(hours=max_gap_hours)

    def build(self, events: list[ProjectEvent]) -> list[EventSequence]:
        by_theme: dict[str, list[ProjectEvent]] = defaultdict(list)
        for event in sorted(events, key=lambda item: item.timestamp):
            by_theme[self.theme_for(event)].append(event)

        sequences: list[EventSequence] = []
        for theme, grouped in by_theme.items():
            chunk: list[ProjectEvent] = []
            for event in grouped:
                if chunk and event.timestamp - chunk[-1].timestamp > self.max_gap:
                    sequences.append(self._sequence(theme, chunk))
                    chunk = []
                chunk.append(event)
            if chunk:
                sequences.append(self._sequence(theme, chunk))
        return sorted(sequences, key=lambda sequence: sequence.start_time)

    def theme_for(self, event: ProjectEvent) -> str:
        module = event.metadata.get("module") or event.target.strip("/").split("/")[0] or "project"
        if "checkout" in f"{event.target} {event.title}".lower():
            return "checkout flow"
        if "auth" in f"{event.target} {event.title}".lower():
            return "auth migration"
        return str(module).replace("_", " ")

    def _sequence(self, theme: str, events: list[ProjectEvent]) -> EventSequence:
        titles = "; ".join(event.title for event in events[:3])
        suffix = "..." if len(events) > 3 else ""
        return EventSequence(
            events=[event.id for event in events],
            start_time=events[0].timestamp,
            end_time=events[-1].timestamp,
            theme=theme,
            impact_summary=f"{len(events)} event(s): {titles}{suffix}",
        )
