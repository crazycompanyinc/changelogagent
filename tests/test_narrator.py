from datetime import datetime, timezone

from changelogagent.core.models import ImpactChain, ProjectEvent
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.timeline.builder import TimelineBuilder


def test_narrative_references_actual_events():
    event = ProjectEvent(event_type="pr_merge", source="Felix", target="checkout", title="PR #1", timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc))
    sequence = TimelineBuilder().build([event])[0]
    block = NarrativeEngine().generate([sequence], [event])[0]
    assert block.includes_events == [event.id]
    assert "Felix" in block.text


def test_narrative_includes_impact_chain():
    event = ProjectEvent(event_type="deploy", source="bot", target="api", title="Deploy")
    sequence = TimelineBuilder().build([event])[0]
    chain = ImpactChain(event_ids=[event.id], summary="Deploy -> metric", confidence=0.7)
    block = NarrativeEngine().generate([sequence], [event], [chain])[0]
    assert "Deploy -> metric" in block.text
