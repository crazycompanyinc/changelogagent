import httpx
import pytest

from changelogagent.core.models import ProjectEvent
from changelogagent.ingest.git_events import from_git_webhook
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.server.app import create_app
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder


def test_git_webhook_commit_mapping_target_from_file():
    events = from_git_webhook({"commits": [{"message": "Update checkout", "modified": ["checkout/page.py"], "author": {"name": "dev"}}]})
    assert events[0]["event_type"] == "commit"
    assert events[0]["target"] == "checkout"


def test_metric_narrative_positive_tone():
    event = ProjectEvent(event_type="metric", source="mon", target="api", title="Latency improved", metadata={"delta_percent": 8})
    sequence = TimelineBuilder().build([event])
    block = NarrativeEngine().generate(sequence, [event])[0]
    assert block.tone.value == "positive"
    assert "improved by 8%" in block.text


def test_summarizer_exports_json_and_html():
    event = ProjectEvent(event_type="commit", source="dev", target="api", title="Change")
    sequence = TimelineBuilder().build([event])
    narratives = NarrativeEngine().generate(sequence, [event])
    entry = Summarizer().summarize([event], narratives)
    assert '"summary"' in Summarizer().export(entry, narratives, fmt="json")
    assert "<h1>" in Summarizer().export(entry, narratives, fmt="html")


@pytest.mark.asyncio
async def test_api_timeline_service_filter(tmp_path):
    transport = httpx.ASGITransport(app=create_app(tmp_path / "filter.db"))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/events", json={"event_type": "commit", "source": "a", "target": "api", "title": "API"})
        await client.post("/events", json={"event_type": "commit", "source": "b", "target": "web", "title": "Web"})
        response = await client.get("/timeline?service=api")
    assert [event["target"] for event in response.json()] == ["api"]


@pytest.mark.asyncio
async def test_api_impact_endpoint_returns_chain(tmp_path):
    transport = httpx.ASGITransport(app=create_app(tmp_path / "impact.db"))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/events", json={"event_type": "deploy", "source": "bot", "target": "api", "title": "Deploy"})
        await client.post("/events", json={"event_type": "metric", "source": "mon", "target": "api", "title": "Errors up", "metadata": {"delta_percent": -20}})
        response = await client.get("/impact")
    assert response.json()[0]["summary"] == "Deploy -> Errors up"
