from datetime import datetime, timedelta, timezone

from changelogagent.core.models import ProjectEvent
from changelogagent.timeline.builder import TimelineBuilder


def test_timeline_groups_by_theme():
    now = datetime.now(timezone.utc)
    events = [
        ProjectEvent(event_type="pr_merge", source="a", target="/checkout/", title="Checkout", timestamp=now),
        ProjectEvent(event_type="deploy", source="b", target="/checkout/", title="Deploy checkout", timestamp=now + timedelta(hours=1)),
    ]
    sequences = TimelineBuilder().build(events)
    assert len(sequences) == 1
    assert sequences[0].events == [events[0].id, events[1].id]


def test_timeline_splits_large_gaps():
    now = datetime.now(timezone.utc)
    events = [
        ProjectEvent(event_type="commit", source="a", target="api", title="A", timestamp=now),
        ProjectEvent(event_type="commit", source="a", target="api", title="B", timestamp=now + timedelta(days=10)),
    ]
    assert len(TimelineBuilder(max_gap_hours=24).build(events)) == 2
