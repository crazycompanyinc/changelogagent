"""Small HTTP clients for source APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class APIClient:
    """Bearer-token JSON API client with explicit timeouts."""

    base_url: str
    token: str
    timeout: float = 10.0

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()


class GitHubClient(APIClient):
    def repository_snapshot(self, owner: str, repo: str) -> dict[str, Any]:
        base = f"/repos/{owner}/{repo}"
        return {
            "repository": self.get(base),
            "pull_requests": self.get(f"{base}/pulls", params={"state": "closed", "per_page": 50}),
            "issues": self.get(f"{base}/issues", params={"state": "all", "per_page": 50}),
            "commits": self.get(f"{base}/commits", params={"per_page": 50}),
        }


class PagerDutyClient(APIClient):
    def incidents(self, *, since: str | None = None) -> list[dict[str, Any]]:
        data = self.get("/incidents", params={"since": since} if since else None)
        return data.get("incidents", []) if isinstance(data, dict) else data


class JiraClient(APIClient):
    def search(self, jql: str, *, max_results: int = 50) -> list[dict[str, Any]]:
        data = self.get("/rest/api/3/search", params={"jql": jql, "maxResults": max_results})
        return data.get("issues", []) if isinstance(data, dict) else data
