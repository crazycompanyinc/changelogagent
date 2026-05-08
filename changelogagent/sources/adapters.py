"""Normalize external systems into ProjectEvent payloads.

The adapters are pure mappers so they are deterministic in tests and can be
used with webhooks, API clients, or batch imports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def github_repository_to_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map GitHub API repository data into normalized events."""

    events: list[dict[str, Any]] = []
    repo = payload.get("repository", {}).get("full_name") or payload.get("repo") or "github"
    for pr in payload.get("pull_requests", []):
        merged_at = pr.get("merged_at") or pr.get("closed_at") or pr.get("updated_at")
        if pr.get("merged") or merged_at:
            events.append(
                {
                    "event_type": "pr_merge",
                    "source": _login(pr.get("user")) or "github",
                    "target": _target_from_labels(pr.get("labels")) or repo,
                    "title": f"PR #{pr.get('number', 'unknown')}: {pr.get('title', 'Merged pull request')}",
                    "description": pr.get("body") or "",
                    "timestamp": merged_at,
                    "metadata": {
                        "provider": "github",
                        "repository": repo,
                        "url": pr.get("html_url"),
                        "additions": pr.get("additions", 0),
                        "deletions": pr.get("deletions", 0),
                        "changed_files": pr.get("changed_files", 0),
                    },
                }
            )
    for commit in payload.get("commits", []):
        events.append(
            {
                "event_type": "commit",
                "source": _login(commit.get("author")) or _login(commit.get("committer")) or "github",
                "target": _target_from_files(commit.get("files") or []) or repo,
                "title": (commit.get("commit", {}).get("message") or commit.get("message") or "Commit").splitlines()[0],
                "description": commit.get("commit", {}).get("message") or commit.get("message") or "",
                "timestamp": commit.get("commit", {}).get("author", {}).get("date") or commit.get("timestamp"),
                "metadata": {"provider": "github", "repository": repo, "sha": commit.get("sha"), "url": commit.get("html_url")},
            }
        )
    for issue in payload.get("issues", []):
        events.append(
            {
                "event_type": "issue",
                "source": _login(issue.get("user")) or "github",
                "target": _target_from_labels(issue.get("labels")) or repo,
                "title": f"Issue #{issue.get('number', 'unknown')}: {issue.get('title', 'Issue updated')}",
                "description": issue.get("body") or "",
                "timestamp": issue.get("created_at") or issue.get("updated_at"),
                "metadata": {
                    "provider": "github",
                    "repository": repo,
                    "state": issue.get("state"),
                    "url": issue.get("html_url"),
                    "labels": [label.get("name", label) for label in issue.get("labels", [])],
                },
            }
        )
    return [_with_timestamp(event) for event in events]


def slack_messages_to_events(messages: list[dict[str, Any]], *, channel: str = "slack") -> list[dict[str, Any]]:
    return [_message_event("slack", message, channel=channel) for message in messages]


def discord_messages_to_events(messages: list[dict[str, Any]], *, channel: str = "discord") -> list[dict[str, Any]]:
    return [_message_event("discord", message, channel=channel) for message in messages]


def pagerduty_incidents_to_events(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for incident in incidents:
        service = (incident.get("service") or {}).get("summary") or incident.get("service_name") or "service"
        events.append(
            {
                "event_type": "incident",
                "source": "pagerduty",
                "target": service,
                "title": incident.get("title") or incident.get("summary") or "PagerDuty incident",
                "description": incident.get("description") or "",
                "timestamp": incident.get("created_at") or incident.get("last_status_change_at"),
                "metadata": {
                    "provider": "pagerduty",
                    "incident_number": incident.get("incident_number"),
                    "severity": incident.get("urgency") or incident.get("severity"),
                    "status": incident.get("status"),
                    "url": incident.get("html_url"),
                },
            }
        )
    return [_with_timestamp(event) for event in events]


def jira_issues_to_events(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for issue in issues:
        fields = issue.get("fields", {})
        project = (fields.get("project") or {}).get("key") or issue.get("project") or "jira"
        key = issue.get("key", "unknown")
        events.append(
            {
                "event_type": "jira_ticket",
                "source": "jira",
                "target": project,
                "title": f"{key}: {fields.get('summary') or issue.get('summary') or 'Jira ticket'}",
                "description": _text(fields.get("description") or issue.get("description") or ""),
                "timestamp": fields.get("updated") or fields.get("created") or issue.get("updated"),
                "metadata": {
                    "provider": "jira",
                    "key": key,
                    "status": (fields.get("status") or {}).get("name"),
                    "priority": (fields.get("priority") or {}).get("name"),
                    "issue_type": (fields.get("issuetype") or {}).get("name"),
                },
            }
        )
    return [_with_timestamp(event) for event in events]


def _message_event(provider: str, message: dict[str, Any], *, channel: str) -> dict[str, Any]:
    text = message.get("text") or message.get("content") or ""
    target = message.get("service") or _infer_target(text) or channel
    return _with_timestamp(
        {
            "event_type": "message",
            "source": message.get("user") or message.get("author", {}).get("username") or provider,
            "target": target,
            "title": text[:96] or f"{provider.title()} message",
            "description": text,
            "timestamp": message.get("ts") or message.get("timestamp"),
            "metadata": {"provider": provider, "channel": channel, "message_id": message.get("id") or message.get("client_msg_id")},
        }
    )


def _with_timestamp(event: dict[str, Any]) -> dict[str, Any]:
    if not event.get("timestamp"):
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
    elif isinstance(event["timestamp"], (int, float)):
        event["timestamp"] = datetime.fromtimestamp(float(event["timestamp"]), timezone.utc).isoformat()
    elif isinstance(event["timestamp"], str) and event["timestamp"].replace(".", "", 1).isdigit():
        event["timestamp"] = datetime.fromtimestamp(float(event["timestamp"].split(".", 1)[0]), timezone.utc).isoformat()
    return event


def _login(value: Any) -> str | None:
    return value.get("login") or value.get("name") if isinstance(value, dict) else value


def _target_from_labels(labels: Any) -> str | None:
    for label in labels or []:
        name = label.get("name", label) if isinstance(label, dict) else str(label)
        if name.startswith("service:") or name.startswith("area:"):
            return name.split(":", 1)[1]
    return None


def _target_from_files(files: list[Any]) -> str | None:
    if not files:
        return None
    filename = files[0].get("filename") if isinstance(files[0], dict) else str(files[0])
    return filename.split("/", 1)[0]


def _infer_target(text: str) -> str | None:
    lowered = text.lower()
    for marker in ("auth", "api", "checkout", "payment", "redis", "gateway"):
        if marker in lowered:
            return marker
    return None


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("content") or value)
    return str(value)
