"""FastAPI application factory."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query

from changelogagent.core.db import EventStore
from changelogagent.impact.analyzer import ImpactAnalyzer
from changelogagent.ingest.ingestor import EventIngestor
from changelogagent.server.webhooks import ingest_ci, ingest_deploy, ingest_git
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder
from changelogagent.narrator.engine import NarrativeEngine


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = EventStore(db_path or os.environ.get("CHANGELOGAGENT_DB", ".changelogagent/changelogagent.db"))
    app = FastAPI(title="ChangelogAgent")

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
        return EventIngestor(store).ingest(payload).to_dict()

    @app.get("/timeline")
    async def timeline(service: str | None = None) -> list[dict[str, Any]]:
        return [event.to_dict() for event in store.list_events(target=service)]

    @app.get("/impact")
    async def impact() -> list[dict[str, Any]]:
        return [chain.to_dict() for chain in ImpactAnalyzer().analyze(store.list_events())]

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

    @app.post("/webhook/git")
    async def webhook_git(payload: dict[str, Any]) -> list[dict[str, Any]]:
        return ingest_git(payload, EventIngestor(store))

    @app.post("/webhook/ci")
    async def webhook_ci(payload: dict[str, Any]) -> dict[str, Any]:
        return ingest_ci(payload, EventIngestor(store))

    @app.post("/webhook/deploy")
    async def webhook_deploy(payload: dict[str, Any]) -> dict[str, Any]:
        return ingest_deploy(payload, EventIngestor(store))

    return app


app = create_app()
