"""Deploy webhook mapping."""

from __future__ import annotations

from typing import Any


def from_deploy_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a deploy service webhook into a normalized event payload."""

    status = payload.get("status", "completed")
    event_type = "rollback" if status == "rolled_back" else "deploy"
    version = payload.get("version", "unknown version")
    service = payload.get("service", payload.get("target", "project"))
    return {
        "event_type": event_type,
        "source": payload.get("source", payload.get("deployer", "deploy-service")),
        "target": service,
        "title": payload.get("title") or f"{version} {status} on {service}",
        "description": payload.get("description", ""),
        "metadata": {
            "version": version,
            "status": status,
            "environment": payload.get("environment", "production"),
        },
    }
