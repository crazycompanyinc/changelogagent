"""FastAPI application factory."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from changelogagent.analysis.anomaly import AnomalyDetector
from changelogagent.analysis.causal import CausalImpactAnalyzer
from changelogagent.analysis.cross_project import CrossProjectCorrelator
from changelogagent.analysis.predictive import PredictiveNarrative
from changelogagent.analysis.quality import NarrativeQualityScorer
from changelogagent.analysis.sentiment import ProjectSentimentAnalyzer
from changelogagent.core.db import EventStore
from changelogagent.export.formats import ChronicleExporter
from changelogagent.impact.analyzer import ImpactAnalyzer
from changelogagent.ingest.ingestor import EventIngestor
from changelogagent.realtime.live import LiveChronicle
from changelogagent.reports.stakeholders import StakeholderReportGenerator
from changelogagent.search.engine import ChronicleSearch
from changelogagent.server.webhooks import ingest_ci, ingest_deploy, ingest_git
from changelogagent.sources.adapters import (
    discord_messages_to_events,
    github_repository_to_events,
    jira_issues_to_events,
    pagerduty_incidents_to_events,
    slack_messages_to_events,
)
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.visualization.timeline import TimelineVisualizer


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = EventStore(db_path or os.environ.get("CHANGELOGAGENT_DB", ".changelogagent/changelogagent.db"))
    app = FastAPI(title="ChangelogAgent")
    live = LiveChronicle()

    def pipeline(period: str = "weekly") -> dict[str, Any]:
        events = store.list_events()
        sequences = TimelineBuilder().build(events)
        impacts = ImpactAnalyzer().analyze(events)
        narratives = NarrativeEngine().generate(sequences, events, impacts)
        entry = Summarizer().summarize(events, narratives, period=period)
        return {"events": events, "sequences": sequences, "impacts": impacts, "narratives": narratives, "entry": entry}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events")
    async def post_event(payload: dict[str, Any]) -> dict[str, Any]:
        event = EventIngestor(store).ingest(payload)
        await live.publish({"type": "event", "event": event.to_dict()})
        return event.to_dict()

    @app.get("/timeline")
    async def timeline(service: str | None = None) -> list[dict[str, Any]]:
        return [event.to_dict() for event in store.list_events(target=service)]

    @app.get("/impact")
    async def impact() -> list[dict[str, Any]]:
        events = store.list_events()
        chains = ImpactAnalyzer().analyze(events) + CausalImpactAnalyzer().analyze(events)
        return [chain.to_dict() for chain in chains]

    @app.get("/v2/causal")
    async def causal() -> list[dict[str, Any]]:
        return [chain.to_dict() for chain in CausalImpactAnalyzer().analyze(store.list_events())]

    @app.get("/v2/predictions")
    async def predictions() -> list[dict[str, Any]]:
        return [prediction.to_dict() for prediction in PredictiveNarrative().predict(store.list_events())]

    @app.get("/v2/sentiment")
    async def sentiment() -> dict[str, Any]:
        return ProjectSentimentAnalyzer().analyze(store.list_events()).to_dict()

    @app.get("/v2/anomalies")
    async def anomalies() -> list[dict[str, Any]]:
        return [anomaly.to_dict() for anomaly in AnomalyDetector().detect(store.list_events())]

    @app.get("/v2/cross-project")
    async def cross_project() -> list[dict[str, Any]]:
        return [impact.to_dict() for impact in CrossProjectCorrelator().correlate(store.list_events())]

    @app.get("/v2/search")
    async def search(q: str = Query(...), target: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [result.to_dict() for result in ChronicleSearch(store).search(q, target=target, limit=limit)]

    @app.get("/v2/timeline/ascii")
    async def ascii_timeline() -> dict[str, str]:
        return {"timeline": TimelineVisualizer().ascii(store.list_events())}

    @app.get("/summary")
    async def summary(period: str = Query("weekly")) -> dict[str, Any]:
        return pipeline(period)["entry"].to_dict()

    @app.get("/chronicle")
    async def chronicle(period: str = Query("weekly")) -> dict[str, Any]:
        state = pipeline(period)
        entry = state["entry"]
        return {
            **entry.to_dict(),
            "narrative_blocks": [block.to_dict() for block in state["narratives"] if block.id in entry.narratives],
        }

    @app.get("/v2/report/{audience}")
    async def stakeholder_report(audience: str, period: str = Query("weekly")) -> dict[str, str]:
        state = pipeline(period)
        sentiment_state = ProjectSentimentAnalyzer().analyze(state["events"])
        text = StakeholderReportGenerator().generate(
            audience,
            state["entry"],
            state["narratives"],
            state["events"],
            state["impacts"] + CausalImpactAnalyzer().analyze(state["events"]),
            sentiment_state,
        )
        return {"audience": audience, "report": text}

    @app.get("/v2/export/{fmt}")
    async def export(fmt: str, period: str = Query("weekly")) -> Any:
        state = pipeline(period)
        exported = ChronicleExporter().export(state["entry"], state["narratives"], fmt=fmt)
        if isinstance(exported, bytes):
            return {"format": fmt, "bytes": exported.decode("latin-1")}
        return exported

    @app.get("/v2/quality")
    async def quality(period: str = Query("weekly")) -> list[dict[str, Any]]:
        state = pipeline(period)
        return [NarrativeQualityScorer().score(block, state["events"]).to_dict() for block in state["narratives"]]

    @app.post("/webhook/git")
    async def webhook_git(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event for event in ingest_git(payload, EventIngestor(store))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.post("/webhook/ci")
    async def webhook_ci(payload: dict[str, Any]) -> dict[str, Any]:
        event = ingest_ci(payload, EventIngestor(store))
        await live.publish({"type": "event", "event": event})
        return event

    @app.post("/webhook/deploy")
    async def webhook_deploy(payload: dict[str, Any]) -> dict[str, Any]:
        event = ingest_deploy(payload, EventIngestor(store))
        await live.publish({"type": "event", "event": event})
        return event

    @app.post("/v2/ingest/github")
    async def ingest_github(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event.to_dict() for event in EventIngestor(store).ingest_many(github_repository_to_events(payload))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.post("/v2/ingest/slack")
    async def ingest_slack(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event.to_dict() for event in EventIngestor(store).ingest_many(slack_messages_to_events(payload.get("messages", []), channel=payload.get("channel", "slack")))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.post("/v2/ingest/discord")
    async def ingest_discord(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event.to_dict() for event in EventIngestor(store).ingest_many(discord_messages_to_events(payload.get("messages", []), channel=payload.get("channel", "discord")))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.post("/v2/ingest/pagerduty")
    async def ingest_pagerduty(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event.to_dict() for event in EventIngestor(store).ingest_many(pagerduty_incidents_to_events(payload.get("incidents", [])))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.post("/v2/ingest/jira")
    async def ingest_jira(payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = [event.to_dict() for event in EventIngestor(store).ingest_many(jira_issues_to_events(payload.get("issues", [])))]
        await live.publish({"type": "events", "events": events})
        return events

    @app.websocket("/v2/live")
    async def live_feed(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = live.subscribe()
        try:
            while True:
                message = await queue.get()
                await websocket.send_json(message)
        except WebSocketDisconnect:
            live.unsubscribe(queue)

    return app


app = create_app()
