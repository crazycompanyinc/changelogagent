"""Causal impact analysis using temporal, dependency, and pattern signals."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from changelogagent.core.models import EventType, ImpactChain, ProjectEvent


NEGATIVE_WORDS = ("timeout", "down", "failed", "failure", "error", "rollback", "storm", "spike", "dropped")


class CausalImpactAnalyzer:
    """Build multi-hop cause/effect chains from operational events."""

    def __init__(self, window_hours: int = 24) -> None:
        self.window = timedelta(hours=window_hours)

    def analyze(self, events: list[ProjectEvent]) -> list[ImpactChain]:
        ordered = sorted(events, key=lambda event: event.timestamp)
        chains: list[ImpactChain] = []
        for event in ordered:
            if event.event_type not in {EventType.DEPLOY, EventType.PR_MERGE, EventType.CONFIG_CHANGE}:
                continue
            chain = self._walk(ordered, event)
            if len(chain) >= 3:
                chains.append(
                    ImpactChain(
                        event_ids=[item.id for item in chain],
                        summary=" -> ".join(self._node_label(item) for item in chain),
                        confidence=self._confidence(chain),
                    )
                )
        return self._dedupe(chains)

    def _walk(self, events: list[ProjectEvent], start: ProjectEvent) -> list[ProjectEvent]:
        chain = [start]
        current = start
        seen = {start.id}
        while True:
            candidates = [
                event
                for event in events
                if event.id not in seen and current.timestamp < event.timestamp <= current.timestamp + self.window
            ]
            scored = [(self._causal_score(current, candidate), candidate) for candidate in candidates]
            scored = [(score, event) for score, event in scored if score >= 0.45]
            if not scored:
                break
            scored.sort(key=lambda item: (-item[0], item[1].timestamp))
            current = scored[0][1]
            chain.append(current)
            seen.add(current.id)
            if len(chain) >= 6 or current.event_type == EventType.ROLLBACK:
                break
        return chain

    def _causal_score(self, cause: ProjectEvent, effect: ProjectEvent) -> float:
        score = 0.0
        if _same_module(cause, effect):
            score += 0.35
        if _shared_dependency(cause, effect):
            score += 0.25
        if cause.event_type in {EventType.DEPLOY, EventType.PR_MERGE, EventType.CONFIG_CHANGE} and effect.event_type == EventType.METRIC:
            score += 0.35
        if cause.event_type == EventType.METRIC and effect.event_type in {EventType.INCIDENT, EventType.MESSAGE}:
            score += 0.3
        if cause.event_type == EventType.INCIDENT and effect.event_type in {EventType.ROLLBACK, EventType.DEPLOY, EventType.PR_MERGE}:
            score += 0.3
        if _negative(effect):
            score += 0.15
        minutes = max((effect.timestamp - cause.timestamp).total_seconds() / 60, 1)
        if minutes <= 180:
            score += 0.15
        return min(score, 1.0)

    @staticmethod
    def _node_label(event: ProjectEvent) -> str:
        metric = event.metadata.get("metric")
        delta = event.metadata.get("delta_percent")
        if metric and delta is not None:
            arrow = "up" if float(delta) > 0 else "down"
            return f"{metric} {arrow} {abs(float(delta)):g}%"
        return event.title

    @staticmethod
    def _confidence(chain: list[ProjectEvent]) -> float:
        return round(min(0.55 + (len(chain) * 0.08), 0.92), 2)

    @staticmethod
    def _dedupe(chains: list[ImpactChain]) -> list[ImpactChain]:
        by_start: dict[str, ImpactChain] = {}
        for chain in chains:
            existing = by_start.get(chain.event_ids[0])
            if existing is None or len(chain.event_ids) > len(existing.event_ids):
                by_start[chain.event_ids[0]] = chain
        return list(by_start.values())


def _same_module(left: ProjectEvent, right: ProjectEvent) -> bool:
    return _module(left) == _module(right) or left.target == right.target


def _module(event: ProjectEvent) -> str:
    return str(event.metadata.get("module") or event.target.strip("/").split("/")[0] or event.target)


def _shared_dependency(left: ProjectEvent, right: ProjectEvent) -> bool:
    left_deps = set(left.metadata.get("dependencies") or left.metadata.get("services") or [])
    right_deps = set(right.metadata.get("dependencies") or right.metadata.get("services") or [])
    return bool(left_deps.intersection(right_deps))


def _negative(event: ProjectEvent) -> bool:
    text = f"{event.title} {event.description}".lower()
    if any(word in text for word in NEGATIVE_WORDS):
        return True
    delta = event.metadata.get("delta_percent")
    return delta is not None and float(delta) < 0
