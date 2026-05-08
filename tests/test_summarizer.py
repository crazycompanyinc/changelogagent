from datetime import datetime, timezone

from changelogagent.core.models import ProjectEvent
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder


def test_summarizer_creates_weekly_entry():
    event = ProjectEvent(event_type="metric", source="mon", target="api", title="Latency improved", metadata={"delta_percent": 10}, timestamp=datetime(2026, 5, 6, tzinfo=timezone.utc))
    sequence = TimelineBuilder().build([event])
    narratives = NarrativeEngine().generate(sequence, [event])
    entry = Summarizer().summarize([event], narratives, period="weekly", now=event.timestamp)
    assert entry.title == "Week of May 4-10, 2026"
    assert entry.metrics_summary == "Latency improved"


def test_summarizer_exports_markdown():
    event = ProjectEvent(event_type="commit", source="dev", target="api", title="Change")
    sequence = TimelineBuilder().build([event])
    narratives = NarrativeEngine().generate(sequence, [event])
    entry = Summarizer().summarize([event], narratives)
    markdown = Summarizer().export(entry, narratives)
    assert markdown.startswith("# Week of")
