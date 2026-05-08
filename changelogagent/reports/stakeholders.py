"""Audience-specific chronicle reports."""

from __future__ import annotations

from changelogagent.analysis.sentiment import ProjectSentiment
from changelogagent.core.models import ChronicleEntry, EventType, ImpactChain, NarrativeBlock, ProjectEvent


class StakeholderReportGenerator:
    """Generate executive, engineering, and standup reports from one evidence set."""

    def generate(
        self,
        audience: str,
        entry: ChronicleEntry,
        narratives: list[NarrativeBlock],
        events: list[ProjectEvent],
        impacts: list[ImpactChain],
        sentiment: ProjectSentiment | None = None,
    ) -> str:
        audience = audience.lower().replace("-", "_")
        if audience in {"executive", "exec"}:
            return self._executive(entry, events, impacts, sentiment)
        if audience in {"engineering", "engineer", "deep_dive"}:
            return self._engineering(entry, narratives, events, impacts)
        if audience in {"standup", "team"}:
            return self._standup(entry, events)
        raise ValueError("audience must be executive, engineering, or standup")

    def _executive(
        self,
        entry: ChronicleEntry,
        events: list[ProjectEvent],
        impacts: list[ImpactChain],
        sentiment: ProjectSentiment | None,
    ) -> str:
        incidents = sum(event.event_type == EventType.INCIDENT for event in events)
        rollbacks = sum(event.event_type == EventType.ROLLBACK for event in events)
        deploys = sum(event.event_type == EventType.DEPLOY for event in events)
        mood = f" Project mood: {sentiment.mood}." if sentiment else ""
        return (
            f"# Executive Summary\n\n{entry.summary}\n\n"
            f"Business risk indicators: {incidents} incident(s), {rollbacks} rollback(s), {deploys} production deploy(s), "
            f"and {len(impacts)} detected impact chain(s).{mood}\n\n"
            f"Top signal: {entry.highlights[0] if entry.highlights else 'No high-signal event.'}"
        )

    def _engineering(
        self,
        entry: ChronicleEntry,
        narratives: list[NarrativeBlock],
        events: list[ProjectEvent],
        impacts: list[ImpactChain],
    ) -> str:
        event_lines = [f"- {event.timestamp.isoformat()} `{event.event_type.value}` {event.target}: {event.title}" for event in events]
        impact_lines = [f"- {chain.summary} (confidence {chain.confidence:.2f})" for chain in impacts] or ["- No causal chains detected."]
        narrative_lines = [f"- {block.text}" for block in narratives]
        return "\n".join(["# Engineering Deep Dive", "", entry.metrics_summary, "", "## Causal Chains", *impact_lines, "", "## Event Evidence", *event_lines, "", "## Narrative", *narrative_lines])

    def _standup(self, entry: ChronicleEntry, events: list[ProjectEvent]) -> str:
        happened = [event.title for event in events[-5:]]
        blockers = [event.title for event in events if event.event_type in {EventType.INCIDENT, EventType.ROLLBACK}]
        next_items = [event.title for event in events if event.event_type in {EventType.JIRA_TICKET, EventType.ISSUE}][-3:]
        lines = ["# Team Standup", "", "## What Happened", *[f"- {item}" for item in happened]]
        lines.extend(["", "## Blockers", *[f"- {item}" for item in blockers]] if blockers else ["", "## Blockers", "- None recorded."])
        lines.extend(["", "## Next", *[f"- {item}" for item in next_items]] if next_items else ["", "## Next", "- Continue follow-up from the latest high-signal events."])
        return "\n".join(lines)
