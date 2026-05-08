"""v2 source integrations."""

from changelogagent.sources.adapters import (
    discord_messages_to_events,
    github_repository_to_events,
    jira_issues_to_events,
    pagerduty_incidents_to_events,
    slack_messages_to_events,
)

__all__ = [
    "discord_messages_to_events",
    "github_repository_to_events",
    "jira_issues_to_events",
    "pagerduty_incidents_to_events",
    "slack_messages_to_events",
]
