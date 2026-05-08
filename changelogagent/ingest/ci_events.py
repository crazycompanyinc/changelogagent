"""CI webhook mapping."""

from __future__ import annotations

from typing import Any


def from_ci_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a CI webhook payload into a normalized event payload."""

    status = payload.get("status") or payload.get("conclusion") or "unknown"
    total = payload.get("total_tests")
    passed = payload.get("passed_tests")
    title = payload.get("title") or f"CI {status}"
    if passed is not None and total is not None:
        title = f"CI {status}: {passed}/{total} tests passed"
    return {
        "event_type": "ci_run",
        "source": payload.get("source", payload.get("provider", "ci")),
        "target": payload.get("target", payload.get("service", "project")),
        "title": title,
        "description": payload.get("description", ""),
        "metadata": {
            "status": status,
            "passed_tests": passed,
            "total_tests": total,
            "run_id": payload.get("run_id"),
        },
    }
