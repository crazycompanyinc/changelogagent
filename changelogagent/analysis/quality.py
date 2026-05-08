"""Narrative quality scoring and feedback aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from changelogagent.core.models import NarrativeBlock, ProjectEvent


@dataclass(slots=True)
class NarrativeQuality:
    coherence: float
    completeness: float
    accuracy: float
    overall: float
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "coherence": self.coherence,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "overall": self.overall,
            "notes": self.notes,
        }


class NarrativeQualityScorer:
    def score(self, block: NarrativeBlock, events: list[ProjectEvent], *, feedback: list[dict[str, object]] | None = None) -> NarrativeQuality:
        event_ids = {event.id for event in events}
        included = [event_id for event_id in block.includes_events if event_id in event_ids]
        sentences = [part for part in block.text.split(".") if part.strip()]
        coherence = 0.9 if len(sentences) >= 2 and block.text[:1].isupper() else 0.65
        completeness = min(len(included) / max(len(events), 1), 1.0)
        accuracy = len(included) / max(len(block.includes_events), 1)
        notes = []
        if completeness < 0.6:
            notes.append("Narrative omits many available events.")
        if accuracy < 1.0:
            notes.append("Narrative references events not present in the evidence set.")
        if feedback:
            votes = [float(item.get("rating", 0)) for item in feedback if item.get("narrative_id") == block.id]
            if votes:
                accuracy = max(0.0, min(1.0, (accuracy + (sum(votes) / len(votes)) / 5) / 2))
                notes.append("Accuracy adjusted using stakeholder feedback.")
        overall = round((coherence + completeness + accuracy) / 3, 2)
        return NarrativeQuality(round(coherence, 2), round(completeness, 2), round(accuracy, 2), overall, notes)
