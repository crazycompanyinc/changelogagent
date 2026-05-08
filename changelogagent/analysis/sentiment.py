"""Project mood and communication pressure analysis."""

from __future__ import annotations

from dataclasses import dataclass

from changelogagent.core.models import EventType, ProjectEvent


NEGATIVE = ("blocked", "urgent", "timeout", "down", "failed", "rollback", "stress", "incident")
POSITIVE = ("fixed", "resolved", "green", "improved", "launched", "shipped")


@dataclass(slots=True)
class ProjectSentiment:
    mood: str
    score: float
    summary: str
    communication_events: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mood": self.mood,
            "score": self.score,
            "summary": self.summary,
            "communication_events": self.communication_events,
        }


class ProjectSentimentAnalyzer:
    def analyze(self, events: list[ProjectEvent]) -> ProjectSentiment:
        if not events:
            return ProjectSentiment("quiet", 0.0, "No activity was recorded.", 0)
        score = 0.0
        incidents = 0
        rollbacks = 0
        messages = 0
        for event in events:
            text = f"{event.title} {event.description}".lower()
            score += sum(0.1 for word in POSITIVE if word in text)
            score -= sum(0.14 for word in NEGATIVE if word in text)
            if event.event_type == EventType.INCIDENT:
                incidents += 1
                score -= 0.35
            if event.event_type == EventType.ROLLBACK:
                rollbacks += 1
                score -= 0.25
            if event.event_type == EventType.MESSAGE:
                messages += 1
        score = round(max(-1.0, min(1.0, score)), 2)
        mood = "healthy" if score > 0.25 else "stressful" if score < -0.25 else "focused"
        summary = f"This period felt {mood}: {incidents} incident(s), {rollbacks} rollback(s), and {messages} communication event(s)."
        return ProjectSentiment(mood, score, summary, messages)
