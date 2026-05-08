"""Predictive narrative generation from trajectory and history."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from changelogagent.core.models import EventType, ProjectEvent


@dataclass(slots=True)
class Prediction:
    text: str
    confidence: float
    supporting_event_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "confidence": self.confidence, "supporting_event_ids": self.supporting_event_ids}


class PredictiveNarrative:
    """Generate plain-English forecasts from current event rates."""

    def predict(self, events: list[ProjectEvent], *, now: datetime | None = None, horizon_days: int = 7) -> list[Prediction]:
        if not events:
            return []
        now = now or max(event.timestamp for event in events)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        recent_start = now - timedelta(days=7)
        prior_start = recent_start - timedelta(days=28)
        recent = [event for event in events if recent_start <= event.timestamp <= now]
        prior = [event for event in events if prior_start <= event.timestamp < recent_start]
        recent_counts = Counter(event.event_type for event in recent)
        prior_counts = Counter(event.event_type for event in prior)
        predictions = []
        if recent_counts[EventType.DEPLOY] >= 2:
            incident_ratio = prior_counts[EventType.INCIDENT] / max(prior_counts[EventType.DEPLOY], 1)
            expected = round(recent_counts[EventType.DEPLOY] * incident_ratio)
            if expected:
                predictions.append(
                    Prediction(
                        text=f"If the current deploy rate continues, expect about {expected} incident(s) in the next {horizon_days} days based on recent history.",
                        confidence=0.62,
                        supporting_event_ids=[event.id for event in recent if event.event_type in {EventType.DEPLOY, EventType.INCIDENT}],
                    )
                )
        if recent_counts[EventType.INCIDENT] >= 2:
            predictions.append(
                Prediction(
                    text="Incident pressure is elevated; expect more rollback or mitigation work before the system stabilizes.",
                    confidence=0.7,
                    supporting_event_ids=[event.id for event in recent if event.event_type == EventType.INCIDENT],
                )
            )
        return predictions
