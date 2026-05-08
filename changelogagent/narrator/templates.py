"""Narrative sentence helpers."""

from __future__ import annotations

from changelogagent.core.models import EventType, ProjectEvent


def event_sentence(event: ProjectEvent) -> str:
    """Render a single grounded event sentence."""

    actor = event.source
    title = event.title.rstrip(".")
    if event.event_type == EventType.PR_MERGE:
        return f"{actor} merged {title} for {event.target}."
    if event.event_type == EventType.DEPLOY:
        version = event.metadata.get("version")
        version_text = f" {version}" if version else ""
        return f"{actor} deployed{version_text} to {event.target}."
    if event.event_type == EventType.METRIC:
        delta = event.metadata.get("delta_percent")
        if delta is not None:
            direction = "improved" if float(delta) > 0 else "degraded"
            return f"Monitoring showed {event.target} {direction} by {abs(float(delta)):g}%: {title}."
        return f"Monitoring reported {title} for {event.target}."
    if event.event_type == EventType.INCIDENT:
        return f"{event.target} experienced an incident: {title}."
    if event.event_type == EventType.CI_RUN:
        return f"CI reported {title}."
    if event.event_type == EventType.AGENT_ACTION:
        return f"{actor} took action on {event.target}: {title}."
    if event.event_type == EventType.ROLLBACK:
        return f"{actor} rolled back {event.target}: {title}."
    return f"{actor} recorded {title} for {event.target}."
