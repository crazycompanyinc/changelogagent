"""Narrative generation from event sequences."""

from __future__ import annotations

from changelogagent.core.models import EventSequence, EventType, ImpactChain, NarrativeBlock, ProjectEvent, Tone
from changelogagent.narrator.templates import event_sentence


class NarrativeEngine:
    """Turn event sequences and detected impact chains into narrative blocks."""

    def generate(
        self,
        sequences: list[EventSequence],
        events: list[ProjectEvent],
        impact_chains: list[ImpactChain] | None = None,
    ) -> list[NarrativeBlock]:
        by_id = {event.id: event for event in events}
        chain_by_event = {}
        for chain in impact_chains or []:
            for event_id in chain.event_ids:
                chain_by_event[event_id] = chain

        blocks = []
        for sequence in sequences:
            sequence_events = [by_id[event_id] for event_id in sequence.events if event_id in by_id]
            if not sequence_events:
                continue
            text = self._paragraph(sequence, sequence_events, chain_by_event)
            blocks.append(
                NarrativeBlock(
                    sequence_id=sequence.id,
                    text=text,
                    tone=self._tone(sequence_events),
                    includes_events=[event.id for event in sequence_events],
                )
            )
        return blocks

    def _paragraph(
        self,
        sequence: EventSequence,
        events: list[ProjectEvent],
        chain_by_event: dict[str, ImpactChain],
    ) -> str:
        day = events[0].timestamp.strftime("%A")
        sentences = [event_sentence(event) for event in events]
        chain = next((chain_by_event.get(event.id) for event in events if event.id in chain_by_event), None)
        if chain:
            sentences.append(f"The detected impact chain was: {chain.summary}.")
        return f"{day}: In the {sequence.theme} theme, " + " ".join(sentences)

    @staticmethod
    def _tone(events: list[ProjectEvent]) -> Tone:
        if any(event.event_type == EventType.INCIDENT for event in events):
            return Tone.CRITICAL
        if any(event.event_type == EventType.ROLLBACK for event in events):
            return Tone.CONCERNED
        metric_deltas = [float(event.metadata["delta_percent"]) for event in events if "delta_percent" in event.metadata]
        if metric_deltas and sum(metric_deltas) > 0:
            return Tone.POSITIVE
        if metric_deltas and sum(metric_deltas) < 0:
            return Tone.CONCERNED
        return Tone.NEUTRAL
