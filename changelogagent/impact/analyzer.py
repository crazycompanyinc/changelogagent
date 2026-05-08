"""Grounded cause-effect detection."""

from __future__ import annotations

from datetime import timedelta

from changelogagent.core.models import EventType, ImpactChain, ProjectEvent


class ImpactAnalyzer:
    """Detect causal chains using time, target correlation, and event type patterns."""

    def __init__(self, window_hours: int = 48) -> None:
        self.window = timedelta(hours=window_hours)

    def analyze(self, events: list[ProjectEvent]) -> list[ImpactChain]:
        ordered = sorted(events, key=lambda item: item.timestamp)
        chains: list[ImpactChain] = []
        chains.extend(self._deploy_metric_hotfix_chains(ordered))
        chains.extend(self._incident_rollback_chains(ordered))
        chains.extend(self._pr_ci_chains(ordered))
        return self._dedupe(chains)

    def _deploy_metric_hotfix_chains(self, events: list[ProjectEvent]) -> list[ImpactChain]:
        chains = []
        starts = [event for event in events if event.event_type in {EventType.PR_MERGE, EventType.DEPLOY}]
        for start in starts:
            related = self._after(events, start)
            metric = next((e for e in related if e.event_type == EventType.METRIC and self._same_target(start, e)), None)
            if not metric:
                continue
            recovery = next(
                (
                    e
                    for e in self._after(events, metric, hours=72)
                    if e.event_type in {EventType.PR_MERGE, EventType.AGENT_ACTION, EventType.DEPLOY, EventType.METRIC}
                    and self._same_target(metric, e)
                    and e.id != start.id
                ),
                None,
            )
            ids = [start.id, metric.id] + ([recovery.id] if recovery else [])
            chains.append(
                ImpactChain(
                    event_ids=ids,
                    summary=self._chain_summary([start, metric] + ([recovery] if recovery else [])),
                    confidence=0.74 if recovery else 0.62,
                )
            )
        return chains

    def _incident_rollback_chains(self, events: list[ProjectEvent]) -> list[ImpactChain]:
        chains = []
        for incident in [event for event in events if event.event_type == EventType.INCIDENT]:
            rollback = next(
                (
                    e
                    for e in self._after(events, incident, hours=12)
                    if e.event_type in {EventType.ROLLBACK, EventType.DEPLOY, EventType.PR_MERGE} and self._same_target(incident, e)
                ),
                None,
            )
            if rollback:
                chains.append(
                    ImpactChain(
                        event_ids=[incident.id, rollback.id],
                        summary=f"{incident.title} was followed by {rollback.title}.",
                        confidence=0.7,
                    )
                )
        return chains

    def _pr_ci_chains(self, events: list[ProjectEvent]) -> list[ImpactChain]:
        chains = []
        for pr in [event for event in events if event.event_type == EventType.PR_MERGE]:
            ci = next(
                (
                    e
                    for e in self._after(events, pr, hours=8)
                    if e.event_type == EventType.CI_RUN and self._same_target(pr, e)
                ),
                None,
            )
            if ci and ci.metadata.get("status") in {"failed", "failure"}:
                chains.append(
                    ImpactChain(
                        event_ids=[pr.id, ci.id],
                        summary=f"{pr.title} was followed by failing CI: {ci.title}.",
                        confidence=0.68,
                    )
                )
        return chains

    def _after(self, events: list[ProjectEvent], event: ProjectEvent, *, hours: int | None = None) -> list[ProjectEvent]:
        window = timedelta(hours=hours) if hours is not None else self.window
        return [candidate for candidate in events if event.timestamp < candidate.timestamp <= event.timestamp + window]

    @staticmethod
    def _same_target(left: ProjectEvent, right: ProjectEvent) -> bool:
        left_module = left.metadata.get("module") or left.target.strip("/").split("/")[0]
        right_module = right.metadata.get("module") or right.target.strip("/").split("/")[0]
        return left_module == right_module or left.target == right.target

    @staticmethod
    def _chain_summary(events: list[ProjectEvent]) -> str:
        return " -> ".join(event.title for event in events)

    @staticmethod
    def _dedupe(chains: list[ImpactChain]) -> list[ImpactChain]:
        seen: set[tuple[str, ...]] = set()
        deduped = []
        for chain in chains:
            key = tuple(chain.event_ids)
            if key not in seen:
                seen.add(key)
                deduped.append(chain)
        return deduped
