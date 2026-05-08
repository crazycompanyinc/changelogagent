"""Cross-project impact correlation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from changelogagent.core.models import EventType, ProjectEvent


@dataclass(slots=True)
class CrossProjectImpact:
    source_event_id: str
    affected_event_id: str
    summary: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "source_event_id": self.source_event_id,
            "affected_event_id": self.affected_event_id,
            "summary": self.summary,
            "confidence": self.confidence,
        }


class CrossProjectCorrelator:
    def __init__(self, window_hours: int = 12) -> None:
        self.window = timedelta(hours=window_hours)

    def correlate(self, events: list[ProjectEvent]) -> list[CrossProjectImpact]:
        ordered = sorted(events, key=lambda event: event.timestamp)
        impacts = []
        for source in ordered:
            if source.event_type not in {EventType.DEPLOY, EventType.CONFIG_CHANGE, EventType.PR_MERGE}:
                continue
            source_project = source.metadata.get("project") or source.target
            source_services = set(source.metadata.get("services") or source.metadata.get("dependencies") or [source.target])
            for affected in ordered:
                if not source.timestamp < affected.timestamp <= source.timestamp + self.window:
                    continue
                affected_project = affected.metadata.get("project") or affected.target
                if affected_project == source_project:
                    continue
                affected_services = set(affected.metadata.get("services") or affected.metadata.get("dependencies") or [affected.target])
                if source_services.intersection(affected_services) and affected.event_type in {EventType.METRIC, EventType.INCIDENT}:
                    impacts.append(
                        CrossProjectImpact(
                            source_event_id=source.id,
                            affected_event_id=affected.id,
                            summary=f"{source.title} in {source_project} likely affected {affected_project}: {affected.title}.",
                            confidence=0.72,
                        )
                    )
        return impacts
