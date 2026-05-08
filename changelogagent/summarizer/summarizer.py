"""Generate period summaries and export chronicle entries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from html import escape

from changelogagent.core.models import ChronicleEntry, EventType, NarrativeBlock, ProjectEvent, ProjectChronicle


class Summarizer:
    """Create daily, weekly, and monthly chronicle entries."""

    def summarize(
        self,
        events: list[ProjectEvent],
        narratives: list[NarrativeBlock],
        *,
        period: str = "weekly",
        now: datetime | None = None,
    ) -> ChronicleEntry:
        now = now or (max((event.timestamp for event in events), default=datetime.now(timezone.utc)))
        start, end, title = self.period_bounds(period, now)
        period_events = [event for event in events if start <= event.timestamp <= end]
        included_ids = {event.id for event in period_events}
        period_narratives = [block for block in narratives if included_ids.intersection(block.includes_events)]
        highlights = [event.title for event in sorted(period_events, key=lambda e: e.importance_score, reverse=True)[:5]]
        lowlights = [event.title for event in period_events if event.event_type in {EventType.INCIDENT, EventType.ROLLBACK}]
        metric_events = [event for event in period_events if event.event_type == EventType.METRIC]
        metrics_summary = "; ".join(event.title for event in metric_events) or "No metric changes recorded."
        summary = self._summary(period_events, metric_events)
        return ChronicleEntry(
            title=title,
            narratives=[block.id for block in period_narratives],
            summary=summary,
            highlights=highlights,
            lowlights=lowlights,
            metrics_summary=metrics_summary,
            period_start=start,
            period_end=end,
        )

    def chronicle(self, entries: list[ChronicleEntry]) -> ProjectChronicle:
        return ProjectChronicle(entries=sorted(entries, key=lambda entry: entry.period_start, reverse=True))

    def export(self, entry: ChronicleEntry, narratives: list[NarrativeBlock], *, fmt: str = "markdown") -> str:
        narrative_map = {block.id: block for block in narratives}
        blocks = [narrative_map[nid] for nid in entry.narratives if nid in narrative_map]
        if fmt == "json":
            data = entry.to_dict()
            data["narrative_blocks"] = [block.to_dict() for block in blocks]
            return json.dumps(data, indent=2)
        if fmt == "html":
            paragraphs = "\n".join(f"<p>{escape(block.text)}</p>" for block in blocks)
            return f"<h1>{escape(entry.title)}</h1><p>{escape(entry.summary)}</p>{paragraphs}"
        lines = [f"# {entry.title}", "", entry.summary, "", "## Narrative"]
        lines.extend(f"\n{block.text}" for block in blocks)
        lines.extend(["", "## Highlights", *[f"- {item}" for item in entry.highlights]])
        if entry.lowlights:
            lines.extend(["", "## Lowlights", *[f"- {item}" for item in entry.lowlights]])
        lines.extend(["", "## Metrics", entry.metrics_summary])
        return "\n".join(lines).strip() + "\n"

    def period_bounds(self, period: str, now: datetime) -> tuple[datetime, datetime, str]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
            return start, end, start.strftime("%A, %B %-d, %Y")
        if period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = next_month - timedelta(microseconds=1)
            return start, end, start.strftime("%B %Y")
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        return start, end, f"Week of {start.strftime('%B %-d')}-{end.strftime('%-d, %Y')}"

    @staticmethod
    def _summary(events: list[ProjectEvent], metrics: list[ProjectEvent]) -> str:
        if not events:
            return "No project events were recorded for this period."
        important = max(events, key=lambda event: event.importance_score)
        metric_text = f" Metrics included {len(metrics)} recorded change(s)." if metrics else ""
        return f"{len(events)} event(s) were recorded. The highest-signal event was: {important.title}.{metric_text}"
