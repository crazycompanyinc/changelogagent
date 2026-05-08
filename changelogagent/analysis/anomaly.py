"""Anomaly detection for project event patterns."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from changelogagent.core.models import EventType, ProjectEvent


@dataclass(slots=True)
class Anomaly:
    kind: str
    message: str
    severity: str
    ratio: float

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "message": self.message, "severity": self.severity, "ratio": self.ratio}


class AnomalyDetector:
    """Compare a recent window against historical baseline rates."""

    def detect(self, events: list[ProjectEvent], *, now: datetime | None = None, window_days: int = 7) -> list[Anomaly]:
        if not events:
            return []
        now = now or max(event.timestamp for event in events)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        recent_start = now - timedelta(days=window_days)
        baseline_start = recent_start - timedelta(days=window_days * 4)
        recent = [event for event in events if recent_start <= event.timestamp <= now]
        baseline = [event for event in events if baseline_start <= event.timestamp < recent_start]
        recent_counts = Counter(event.event_type for event in recent)
        baseline_counts = Counter(event.event_type for event in baseline)
        anomalies = []
        for event_type in (EventType.DEPLOY, EventType.INCIDENT, EventType.ROLLBACK, EventType.MESSAGE):
            recent_rate = recent_counts[event_type] / max(window_days, 1)
            baseline_rate = baseline_counts[event_type] / max(window_days * 4, 1)
            if recent_counts[event_type] >= 2 and (baseline_rate == 0 or recent_rate >= baseline_rate * 2):
                ratio = recent_rate / baseline_rate if baseline_rate else float(recent_counts[event_type])
                anomalies.append(
                    Anomaly(
                        kind=f"{event_type.value}_rate",
                        message=f"{event_type.value.replace('_', ' ').title()} rate is {ratio:.1f}x normal.",
                        severity="high" if ratio >= 3 else "medium",
                        ratio=round(ratio, 2),
                    )
                )
        return anomalies
