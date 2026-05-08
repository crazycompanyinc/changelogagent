from datetime import datetime, timedelta, timezone

import httpx
import pytest

from changelogagent.analysis.anomaly import AnomalyDetector
from changelogagent.analysis.causal import CausalImpactAnalyzer
from changelogagent.analysis.cross_project import CrossProjectCorrelator
from changelogagent.analysis.predictive import PredictiveNarrative
from changelogagent.analysis.quality import NarrativeQualityScorer
from changelogagent.analysis.sentiment import ProjectSentimentAnalyzer
from changelogagent.core.db import EventStore
from changelogagent.core.models import ProjectEvent
from changelogagent.export.formats import ChronicleExporter
from changelogagent.ingest.ingestor import EventIngestor
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.reports.stakeholders import StakeholderReportGenerator
from changelogagent.search.engine import ChronicleSearch
from changelogagent.server.app import create_app
from changelogagent.sources.adapters import github_repository_to_events, jira_issues_to_events, pagerduty_incidents_to_events, slack_messages_to_events
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder
from changelogagent.visualization.timeline import TimelineVisualizer


def _events():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return [
        ProjectEvent(event_type="deploy", source="bot", target="payments", title="Deploy v2.3", timestamp=now, metadata={"dependencies": ["redis"], "environment": "production"}),
        ProjectEvent(event_type="metric", source="mon", target="payments", title="Redis connections up", timestamp=now + timedelta(minutes=30), metadata={"metric": "redis_connections", "delta_percent": 95, "dependencies": ["redis"]}),
        ProjectEvent(event_type="incident", source="pagerduty", target="payments", title="Payment timeouts", timestamp=now + timedelta(hours=1), metadata={"severity": "high", "dependencies": ["redis"]}),
        ProjectEvent(event_type="message", source="slack", target="payments", title="Urgent retry storm discussion", timestamp=now + timedelta(hours=2)),
        ProjectEvent(event_type="rollback", source="bot", target="payments", title="Rollback v2.3", timestamp=now + timedelta(hours=3)),
    ]


def test_v2_source_adapters_normalize_external_data():
    github = github_repository_to_events(
        {
            "repository": {"full_name": "acme/api"},
            "pull_requests": [{"number": 7, "title": "Auth fix", "merged": True, "merged_at": "2026-05-01T00:00:00Z", "labels": [{"name": "service:auth"}]}],
            "issues": [{"number": 8, "title": "Login bug", "created_at": "2026-05-01T00:00:00Z"}],
        }
    )
    slack = slack_messages_to_events([{"text": "api is down", "ts": "1770000000.123"}], channel="ops")
    pagerduty = pagerduty_incidents_to_events([{"title": "SEV1 outage", "service": {"summary": "api"}, "created_at": "2026-05-01T00:00:00Z"}])
    jira = jira_issues_to_events([{"key": "API-1", "fields": {"summary": "Fix auth", "project": {"key": "API"}}}])
    assert [event["event_type"] for event in github] == ["pr_merge", "issue"]
    assert slack[0]["event_type"] == "message"
    assert pagerduty[0]["event_type"] == "incident"
    assert jira[0]["event_type"] == "jira_ticket"


def test_v2_causal_sentiment_quality_export_search_and_visualization(tmp_path):
    store = EventStore(tmp_path / "v2.db")
    events = EventIngestor(store).ingest_many(_events())
    causal = CausalImpactAnalyzer().analyze(events)
    assert causal and "Deploy v2.3" in causal[0].summary
    assert ProjectSentimentAnalyzer().analyze(events).mood == "stressful"
    assert ChronicleSearch(store).search("retry storm")[0].event.title == "Urgent retry storm discussion"
    assert "payments" in TimelineVisualizer().ascii(events, width=40)

    sequences = TimelineBuilder().build(events)
    narratives = NarrativeEngine().generate(sequences, events, causal)
    entry = Summarizer().summarize(events, narratives)
    quality = NarrativeQualityScorer().score(narratives[0], events)
    assert quality.overall > 0.5
    assert ChronicleExporter().export(entry, narratives, fmt="pdf").startswith(b"%PDF")
    assert "Business risk" in StakeholderReportGenerator().generate("executive", entry, narratives, events, causal, ProjectSentimentAnalyzer().analyze(events))


def test_v2_anomaly_prediction_and_cross_project():
    old = datetime(2026, 4, 1, tzinfo=timezone.utc)
    events = [
        ProjectEvent(event_type="deploy", source="bot", target="api", title="Old deploy", timestamp=old),
        ProjectEvent(event_type="incident", source="ops", target="api", title="Old incident", timestamp=old + timedelta(days=1)),
    ]
    now = datetime(2026, 5, 8, tzinfo=timezone.utc)
    events.extend(ProjectEvent(event_type="deploy", source="bot", target="api", title=f"Deploy {i}", timestamp=now - timedelta(days=i)) for i in range(3))
    events.extend(ProjectEvent(event_type="incident", source="ops", target="api", title=f"Incident {i}", timestamp=now - timedelta(days=i, hours=1)) for i in range(2))
    events.append(ProjectEvent(event_type="deploy", source="bot", target="project-a", title="Project A deploy", timestamp=now, metadata={"project": "A", "services": ["shared-auth"]}))
    events.append(ProjectEvent(event_type="metric", source="mon", target="project-b", title="Project B API slowed", timestamp=now + timedelta(hours=1), metadata={"project": "B", "services": ["shared-auth"], "delta_percent": -40}))
    assert AnomalyDetector().detect(events, now=now)
    assert PredictiveNarrative().predict(events, now=now)
    assert CrossProjectCorrelator().correlate(events)


@pytest.mark.asyncio
async def test_v2_api_endpoints(tmp_path):
    transport = httpx.ASGITransport(app=create_app(tmp_path / "api_v2.db"))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/v2/ingest/slack", json={"channel": "ops", "messages": [{"text": "auth incident is urgent", "ts": "1770000000"}]})
        await client.post("/events", json={"event_type": "deploy", "source": "bot", "target": "auth", "title": "Deploy auth"})
        search = await client.get("/v2/search", params={"q": "urgent auth"})
        sentiment = await client.get("/v2/sentiment")
        report = await client.get("/v2/report/executive")
        timeline = await client.get("/v2/timeline/ascii")
    assert search.json()[0]["event_type"] == "message"
    assert "mood" in sentiment.json()
    assert "Business risk" in report.json()["report"]
    assert "timeline" in timeline.json()
