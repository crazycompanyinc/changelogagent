"""ASCII timeline views."""

from __future__ import annotations

from collections import defaultdict

from changelogagent.core.models import ProjectEvent


class TimelineVisualizer:
    def ascii(self, events: list[ProjectEvent], *, width: int = 100) -> str:
        if not events:
            return "No events."
        ordered = sorted(events, key=lambda event: event.timestamp)
        start = ordered[0].timestamp
        end = ordered[-1].timestamp
        span = max((end - start).total_seconds(), 1)
        lanes: dict[str, list[str]] = defaultdict(lambda: [" "] * width)
        labels: list[str] = []
        for event in ordered:
            pos = min(width - 1, max(0, int(((event.timestamp - start).total_seconds() / span) * (width - 1))))
            marker = event.event_type.value[:1].upper()
            lanes[event.target][pos] = marker
            labels.append(f"{marker} {event.timestamp.strftime('%Y-%m-%d %H:%M')} {event.target}: {event.title}")
        lane_lines = [f"{target[:18]:18} |{''.join(chars)}|" for target, chars in sorted(lanes.items())]
        return "\n".join([f"{start.isoformat()} -> {end.isoformat()}", *lane_lines, "", *labels])
