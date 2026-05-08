"""Validation, enrichment, scoring, and persistence for events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from changelogagent.core.db import EventStore
from changelogagent.core.models import EventType, ProjectEvent


class EventIngestor:
    """Accept events from multiple sources and store normalized project events."""

    REQUIRED = {"event_type", "source", "target", "title"}

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def ingest(self, payload: dict[str, Any] | ProjectEvent) -> ProjectEvent:
        """Validate, enrich, score, and store an event."""

        if isinstance(payload, ProjectEvent):
            event = payload
        else:
            self.validate(payload)
            event = ProjectEvent.from_dict(self.enrich(payload))
        if event.importance_score <= 0:
            event.importance_score = self.score_importance(event)
        return self.store.add_event(event)

    def ingest_many(self, payloads: list[dict[str, Any] | ProjectEvent]) -> list[ProjectEvent]:
        return [self.ingest(payload) for payload in payloads]

    def validate(self, payload: dict[str, Any]) -> None:
        missing = sorted(self.REQUIRED - set(payload))
        if missing:
            raise ValueError(f"Missing required event fields: {', '.join(missing)}")
        EventType(payload["event_type"])
        if not str(payload["source"]).strip():
            raise ValueError("source must not be empty")
        if not str(payload["target"]).strip():
            raise ValueError("target must not be empty")
        if not str(payload["title"]).strip():
            raise ValueError("title must not be empty")

    def enrich(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        target = str(payload["target"]).strip()
        metadata.setdefault("module", self._module_from_target(target))
        metadata.setdefault("source_kind", self._source_kind(str(payload["source"])))
        enriched = dict(payload)
        enriched["target"] = target
        enriched["metadata"] = metadata
        if "timestamp" not in enriched:
            enriched["timestamp"] = datetime.now(timezone.utc).isoformat()
        return enriched

    def score_importance(self, event: ProjectEvent) -> float:
        base = {
            EventType.INCIDENT: 0.9,
            EventType.ROLLBACK: 0.88,
            EventType.DEPLOY: 0.72,
            EventType.PR_MERGE: 0.68,
            EventType.METRIC: 0.66,
            EventType.ISSUE: 0.58,
            EventType.JIRA_TICKET: 0.56,
            EventType.CI_RUN: 0.5,
            EventType.MESSAGE: 0.48,
            EventType.AGENT_ACTION: 0.45,
            EventType.CONFIG_CHANGE: 0.42,
            EventType.COMMIT: 0.32,
        }[event.event_type]
        metadata = event.metadata
        if metadata.get("status") in {"failed", "failure"}:
            base += 0.18
        if metadata.get("environment") == "production":
            base += 0.12
        if "delta_percent" in metadata:
            base += min(abs(float(metadata["delta_percent"])) / 100, 0.2)
        if metadata.get("severity") in {"sev1", "sev2", "critical", "high"}:
            base += 0.16
        files = metadata.get("files") or []
        if isinstance(files, list) and len(files) >= 10:
            base += 0.08
        return round(max(0.0, min(1.0, base)), 2)

    @staticmethod
    def _module_from_target(target: str) -> str:
        cleaned = target.strip("/")
        if not cleaned:
            return "project"
        return cleaned.split("/")[0]

    @staticmethod
    def _source_kind(source: str) -> str:
        lowered = source.lower()
        if "agent" in lowered or "felix" in lowered:
            return "agent"
        if "ci" in lowered or "github" in lowered:
            return "automation"
        return "system"
