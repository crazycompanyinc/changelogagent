import pytest

from changelogagent.ingest.ci_events import from_ci_webhook
from changelogagent.ingest.deploy_events import from_deploy_webhook
from changelogagent.ingest.git_events import from_git_webhook
from changelogagent.ingest.ingestor import EventIngestor


def test_ingestor_validates_required_fields(store):
    with pytest.raises(ValueError):
        EventIngestor(store).ingest({"event_type": "commit"})


def test_ingestor_enriches_and_scores(store):
    event = EventIngestor(store).ingest({"event_type": "deploy", "source": "bot", "target": "/checkout/", "title": "Deploy"})
    assert event.metadata["module"] == "checkout"
    assert event.importance_score > 0.7


def test_git_webhook_pr_merge_mapping():
    payload = {"action": "closed", "pull_request": {"merged": True, "number": 1, "title": "Add thing", "user": {"login": "sam"}}}
    assert from_git_webhook(payload)[0]["event_type"] == "pr_merge"


def test_ci_webhook_mapping():
    event = from_ci_webhook({"status": "passed", "passed_tests": 2, "total_tests": 3, "service": "api"})
    assert event["title"] == "CI passed: 2/3 tests passed"


def test_deploy_webhook_rollback_mapping():
    event = from_deploy_webhook({"status": "rolled_back", "service": "api"})
    assert event["event_type"] == "rollback"
