"""Typed models for ChangelogAgent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    """Supported project event types."""

    COMMIT = "commit"
    DEPLOY = "deploy"
    PR_MERGE = "pr_merge"
    INCIDENT = "incident"
    ROLLBACK = "rollback"
    CONFIG_CHANGE = "config_change"
    AGENT_ACTION = "agent_action"
    CI_RUN = "ci_run"
    METRIC = "metric"


class Tone(str, Enum):
    """Narrative tone labels."""

    NEUTRAL = "neutral"
    CONCERNED = "concerned"
    POSITIVE = "positive"
    CRITICAL = "critical"


def utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Create a readable unique identifier."""

    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class ProjectEvent:
    """An operational event captured from a project system."""

    event_type: EventType | str
    source: str
    target: str
    title: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)
    importance_score: float = 0.0
    id: str = field(default_factory=lambda: new_id("evt"))

    def __post_init__(self) -> None:
        self.event_type = EventType(self.event_type)
        self.importance_score = max(0.0, min(1.0, float(self.importance_score)))
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event for APIs and storage."""

        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "source": self.source,
            "target": self.target,
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "importance_score": self.importance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectEvent":
        """Deserialize an event from API or database data."""

        timestamp = data.get("timestamp", utcnow())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return cls(
            id=data.get("id") or new_id("evt"),
            event_type=data["event_type"],
            source=data["source"],
            target=data["target"],
            title=data["title"],
            description=data.get("description", ""),
            metadata=data.get("metadata") or {},
            timestamp=timestamp,
            importance_score=data.get("importance_score", 0.0),
        )


@dataclass(slots=True)
class EventSequence:
    """A chronological group of related events."""

    events: list[str]
    start_time: datetime
    end_time: datetime
    theme: str
    impact_summary: str = ""
    id: str = field(default_factory=lambda: new_id("seq"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "events": self.events,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "theme": self.theme,
            "impact_summary": self.impact_summary,
        }


@dataclass(slots=True)
class ImpactChain:
    """A grounded cause-effect chain detected across events."""

    event_ids: list[str]
    summary: str
    confidence: float
    id: str = field(default_factory=lambda: new_id("imp"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_ids": self.event_ids,
            "summary": self.summary,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class NarrativeBlock:
    """A narrative paragraph grounded in a sequence of events."""

    sequence_id: str
    text: str
    tone: Tone | str
    includes_events: list[str]
    generated_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("nar"))

    def __post_init__(self) -> None:
        self.tone = Tone(self.tone)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence_id": self.sequence_id,
            "text": self.text,
            "tone": self.tone.value,
            "includes_events": self.includes_events,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass(slots=True)
class ChronicleEntry:
    """A generated chronicle entry for a period."""

    title: str
    narratives: list[str]
    summary: str
    highlights: list[str]
    lowlights: list[str]
    metrics_summary: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("chr"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "narratives": self.narratives,
            "summary": self.summary,
            "highlights": self.highlights,
            "lowlights": self.lowlights,
            "metrics_summary": self.metrics_summary,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass(slots=True)
class ProjectChronicle:
    """The full living chronicle document."""

    entries: list[ChronicleEntry]

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self.entries]}
