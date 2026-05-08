from datetime import datetime, timedelta, timezone

from changelogagent.core.models import ProjectEvent
from changelogagent.impact.analyzer import ImpactAnalyzer


def test_impact_detects_deploy_metric_recovery_chain():
    now = datetime.now(timezone.utc)
    events = [
        ProjectEvent(event_type="deploy", source="bot", target="checkout", title="Deploy A", timestamp=now),
        ProjectEvent(event_type="metric", source="mon", target="checkout", title="Conversion dropped", metadata={"delta_percent": -12}, timestamp=now + timedelta(hours=1)),
        ProjectEvent(event_type="pr_merge", source="dev", target="checkout", title="Hotfix", timestamp=now + timedelta(hours=2)),
    ]
    chains = ImpactAnalyzer().analyze(events)
    assert chains
    assert chains[0].event_ids == [event.id for event in events]


def test_impact_detects_incident_followed_by_deploy():
    now = datetime.now(timezone.utc)
    events = [
        ProjectEvent(event_type="incident", source="ops", target="api", title="Outage", timestamp=now),
        ProjectEvent(event_type="deploy", source="bot", target="api", title="Fix deploy", timestamp=now + timedelta(hours=1)),
    ]
    assert len(ImpactAnalyzer().analyze(events)) == 1
