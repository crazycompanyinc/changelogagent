"""Git and PR webhook mapping."""

from __future__ import annotations

from typing import Any


def from_git_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a Git provider webhook into normalized event payloads."""

    events: list[dict[str, Any]] = []
    if "pull_request" in payload:
        pr = payload["pull_request"]
        action = payload.get("action", "updated")
        if action in {"closed", "merged"} and pr.get("merged", action == "merged"):
            events.append(
                {
                    "event_type": "pr_merge",
                    "source": pr.get("user", {}).get("login", payload.get("sender", {}).get("login", "git")),
                    "target": _target_from_files(pr.get("files") or payload.get("files") or []),
                    "title": f"PR #{pr.get('number', pr.get('id', 'unknown'))}: {pr.get('title', 'Merged pull request')}",
                    "description": pr.get("body") or "",
                    "metadata": {"pr_number": pr.get("number"), "url": pr.get("html_url"), "action": action},
                }
            )
    for commit in payload.get("commits", []):
        events.append(
            {
                "event_type": "commit",
                "source": commit.get("author", {}).get("name", payload.get("pusher", {}).get("name", "git")),
                "target": _target_from_files(commit.get("modified", []) + commit.get("added", [])),
                "title": commit.get("message", "Commit").splitlines()[0],
                "description": commit.get("message", ""),
                "metadata": {"sha": commit.get("id"), "url": commit.get("url")},
            }
        )
    return events


def _target_from_files(files: list[Any]) -> str:
    if not files:
        return "project"
    first = files[0]
    filename = first.get("filename") if isinstance(first, dict) else str(first)
    return filename.split("/")[0] if "/" in filename else filename
