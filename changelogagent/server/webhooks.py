"""Webhook receiver helpers."""

from __future__ import annotations

from changelogagent.ingest.ci_events import from_ci_webhook
from changelogagent.ingest.deploy_events import from_deploy_webhook
from changelogagent.ingest.git_events import from_git_webhook
from changelogagent.ingest.ingestor import EventIngestor


def ingest_git(payload: dict, ingestor: EventIngestor) -> list[dict]:
    return [event.to_dict() for event in ingestor.ingest_many(from_git_webhook(payload))]


def ingest_ci(payload: dict, ingestor: EventIngestor) -> dict:
    return ingestor.ingest(from_ci_webhook(payload)).to_dict()


def ingest_deploy(payload: dict, ingestor: EventIngestor) -> dict:
    return ingestor.ingest(from_deploy_webhook(payload)).to_dict()
