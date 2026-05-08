"""Click CLI for ChangelogAgent."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from changelogagent.analysis.anomaly import AnomalyDetector
from changelogagent.analysis.causal import CausalImpactAnalyzer
from changelogagent.analysis.cross_project import CrossProjectCorrelator
from changelogagent.analysis.predictive import PredictiveNarrative
from changelogagent.analysis.sentiment import ProjectSentimentAnalyzer
from changelogagent.core.db import EventStore
from changelogagent.export.formats import ChronicleExporter
from changelogagent.impact.analyzer import ImpactAnalyzer
from changelogagent.ingest.ingestor import EventIngestor
from changelogagent.narrator.engine import NarrativeEngine
from changelogagent.reports.stakeholders import StakeholderReportGenerator
from changelogagent.search.engine import ChronicleSearch
from changelogagent.summarizer.summarizer import Summarizer
from changelogagent.timeline.builder import TimelineBuilder
from changelogagent.visualization.timeline import TimelineVisualizer

console = Console()


def store_from_context(db_path: str | None = None) -> EventStore:
    return EventStore(db_path or os.environ.get("CHANGELOGAGENT_DB", ".changelogagent/changelogagent.db"))


def build_state(store: EventStore, period: str = "weekly") -> dict[str, Any]:
    events = store.list_events()
    sequences = TimelineBuilder().build(events)
    impacts = ImpactAnalyzer().analyze(events)
    narratives = NarrativeEngine().generate(sequences, events, impacts)
    entry = Summarizer().summarize(events, narratives, period=period)
    return {"events": events, "sequences": sequences, "impacts": impacts, "narratives": narratives, "entry": entry}


def print_timeline(events: list[Any]) -> None:
    """Render events as a terminal table."""

    table = Table(title="Project Timeline")
    for col in ["Time", "Type", "Source", "Target", "Title", "Score"]:
        table.add_column(col)
    for event in events:
        table.add_row(
            event.timestamp.strftime("%Y-%m-%d %H:%M"),
            event.event_type.value,
            event.source,
            event.target,
            event.title,
            f"{event.importance_score:.2f}",
        )
    console.print(table)


def print_impact_chains(chains: list[Any]) -> None:
    """Render detected impact chains."""

    if not chains:
        console.print("[yellow]No impact chains detected.[/yellow]")
        return
    for chain in chains:
        console.print(f"[cyan]{chain.confidence:.2f}[/cyan] {chain.summary}")


@click.group()
@click.option("--db", "db_path", default=None, help="SQLite database path.")
@click.pass_context
def cli(ctx: click.Context, db_path: str | None) -> None:
    """Living project narrative engine."""

    ctx.obj = {"store": store_from_context(db_path)}


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize local ChangelogAgent storage."""

    store = ctx.obj["store"]
    store.initialize()
    console.print(f"[green]Initialized[/green] {store.db_path}")


@cli.command()
@click.option("--type", "event_type", required=True)
@click.option("--source", required=True)
@click.option("--target", required=True)
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--metadata", default=None, help="JSON object string.")
@click.pass_context
def ingest(ctx: click.Context, event_type: str, source: str, target: str, title: str, description: str, metadata: str | None) -> None:
    """Ingest one event."""

    import json

    data = json.loads(metadata) if metadata else {}
    event = EventIngestor(ctx.obj["store"]).ingest(
        {
            "event_type": event_type,
            "source": source,
            "target": target,
            "title": title,
            "description": description,
            "metadata": data,
        }
    )
    console.print(f"[green]Ingested[/green] {event.id} ({event.event_type.value}, score={event.importance_score})")


@cli.command()
@click.option("--period", default="weekly", type=click.Choice(["daily", "weekly", "monthly"]))
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "html", "json"]))
@click.pass_context
def chronicle(ctx: click.Context, period: str, fmt: str) -> None:
    """View the project chronicle."""

    state = build_state(ctx.obj["store"], period)
    console.print(Summarizer().export(state["entry"], state["narratives"], fmt=fmt))


@cli.command()
@click.option("--service", default=None)
@click.pass_context
def timeline(ctx: click.Context, service: str | None) -> None:
    """View raw timeline events."""

    print_timeline(ctx.obj["store"].list_events(target=service))


@cli.command()
@click.option("--since", default=None, help="ISO date or datetime.")
@click.pass_context
def summary(ctx: click.Context, since: str | None) -> None:
    """Print a quick summary."""

    events = ctx.obj["store"].list_events()
    if since:
        start = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
        events = [event for event in events if event.timestamp >= start]
    sequences = TimelineBuilder().build(events)
    impacts = ImpactAnalyzer().analyze(events)
    narratives = NarrativeEngine().generate(sequences, events, impacts)
    entry = Summarizer().summarize(events, narratives)
    console.print(Panel(entry.summary, title=entry.title))


@cli.command()
@click.pass_context
def impact(ctx: click.Context) -> None:
    """Show detected impact chains."""

    events = ctx.obj["store"].list_events()
    print_impact_chains(ImpactAnalyzer().analyze(events) + CausalImpactAnalyzer().analyze(events))


@cli.command()
@click.argument("query")
@click.option("--target", default=None)
@click.pass_context
def search(ctx: click.Context, query: str, target: str | None) -> None:
    """Search across the chronicle."""

    for result in ChronicleSearch(ctx.obj["store"]).search(query, target=target):
        event = result.event
        console.print(f"[cyan]{event.timestamp:%Y-%m-%d %H:%M}[/cyan] {event.event_type.value} {event.target}: {result.snippet}")


@cli.command("v2-report")
@click.option("--audience", default="executive", type=click.Choice(["executive", "engineering", "standup"]))
@click.pass_context
def v2_report(ctx: click.Context, audience: str) -> None:
    """Generate a stakeholder-specific v2 report."""

    state = build_state(ctx.obj["store"])
    sentiment = ProjectSentimentAnalyzer().analyze(state["events"])
    report = StakeholderReportGenerator().generate(
        audience,
        state["entry"],
        state["narratives"],
        state["events"],
        state["impacts"] + CausalImpactAnalyzer().analyze(state["events"]),
        sentiment,
    )
    console.print(report)


@cli.command("v2-insights")
@click.pass_context
def v2_insights(ctx: click.Context) -> None:
    """Show causal chains, predictions, anomalies, mood, and cross-project impacts."""

    events = ctx.obj["store"].list_events()
    console.rule("[bold]Causal Chains")
    print_impact_chains(CausalImpactAnalyzer().analyze(events))
    console.rule("[bold]Predictions")
    for prediction in PredictiveNarrative().predict(events):
        console.print(f"[cyan]{prediction.confidence:.2f}[/cyan] {prediction.text}")
    console.rule("[bold]Anomalies")
    for anomaly in AnomalyDetector().detect(events):
        console.print(f"[yellow]{anomaly.severity}[/yellow] {anomaly.message}")
    console.rule("[bold]Project Mood")
    console.print(ProjectSentimentAnalyzer().analyze(events).summary)
    console.rule("[bold]Cross-Project")
    impacts = CrossProjectCorrelator().correlate(events)
    if impacts:
        for item in impacts:
            console.print(f"[cyan]{item.confidence:.2f}[/cyan] {item.summary}")
    else:
        console.print("[yellow]No cross-project impacts detected.[/yellow]")


@cli.command("timeline-ascii")
@click.pass_context
def timeline_ascii(ctx: click.Context) -> None:
    """Render an ASCII timeline visualization."""

    console.print(TimelineVisualizer().ascii(ctx.obj["store"].list_events()))


@cli.command("export")
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "html", "json", "pdf", "confluence", "notion"]))
@click.pass_context
def export_cmd(ctx: click.Context, fmt: str) -> None:
    """Export the chronicle in integration-ready formats."""

    state = build_state(ctx.obj["store"])
    exported = ChronicleExporter().export(state["entry"], state["narratives"], fmt=fmt)
    if isinstance(exported, bytes):
        console.print(exported.decode("latin-1"))
    elif isinstance(exported, dict):
        import json

        console.print(json.dumps(exported, indent=2))
    else:
        console.print(exported)


@cli.command()
@click.option("--port", default=8000, type=int)
@click.pass_context
def serve(ctx: click.Context, port: int) -> None:
    """Start API server."""

    import uvicorn

    os.environ["CHANGELOGAGENT_DB"] = str(ctx.obj["store"].db_path)
    uvicorn.run("changelogagent.server.app:create_app", factory=True, host="0.0.0.0", port=port)


@cli.command()
@click.pass_context
def demo(ctx: click.Context) -> None:
    """Run a simulated project week."""

    store = ctx.obj["store"]
    store.clear()
    events = demo_events()
    EventIngestor(store).ingest_many(events)
    state = build_state(store, "weekly")
    console.rule("[bold]ChangelogAgent Demo")
    console.print(Panel("A living chronicle for a checkout-focused project week.", title="Scenario"))
    print_timeline(state["events"])
    console.rule("[bold]Impact Chains")
    print_impact_chains(state["impacts"])
    console.rule("[bold]v2 Insights")
    console.print(ProjectSentimentAnalyzer().analyze(state["events"]).summary)
    for prediction in PredictiveNarrative().predict(state["events"]):
        console.print(prediction.text)
    for anomaly in AnomalyDetector().detect(state["events"]):
        console.print(anomaly.message)
    console.print(TimelineVisualizer().ascii(state["events"], width=60))
    console.rule("[bold]Executive Report")
    console.print(
        StakeholderReportGenerator().generate(
            "executive",
            state["entry"],
            state["narratives"],
            state["events"],
            state["impacts"],
            ProjectSentimentAnalyzer().analyze(state["events"]),
        )
    )
    console.rule("[bold]Weekly Chronicle")
    console.print(Summarizer().export(state["entry"], state["narratives"], fmt="markdown"))


def demo_events() -> list[dict[str, Any]]:
    base = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)

    def at(days: int, hours: int = 0) -> str:
        return (base + timedelta(days=days, hours=hours)).isoformat()

    return [
        {"event_type": "pr_merge", "source": "Felix-ContactCenter", "target": "/checkout/", "title": 'PR #142 "Redesign checkout flow"', "timestamp": at(0), "metadata": {"pr_number": 142}},
        {"event_type": "ci_run", "source": "CI", "target": "/checkout/", "title": "CI: 47/50 tests pass, 3 flaky", "timestamp": at(0, 1), "metadata": {"status": "passed", "passed_tests": 47, "total_tests": 50, "flaky_tests": 3}},
        {"event_type": "deploy", "source": "DeployBot", "target": "/checkout/", "title": "v2.3.1 deployed to production", "timestamp": at(0, 3), "metadata": {"version": "v2.3.1", "environment": "production"}},
        {"event_type": "metric", "source": "Monitoring", "target": "/checkout/", "title": "Conversion rate dropped 12%", "timestamp": at(1), "metadata": {"metric": "conversion_rate", "delta_percent": -12}},
        {"event_type": "agent_action", "source": "Felix-Jim", "target": "/checkout/", "title": 'Opened hotfix PR #143 "Move CTA above the fold"', "timestamp": at(1, 1), "metadata": {"pr_number": 143}},
        {"event_type": "incident", "source": "Support", "target": "/checkout/", "title": "Checkout page CTA not visible on mobile", "timestamp": at(1, 2), "metadata": {"severity": "high", "root_cause": "CTA below fold"}},
        {"event_type": "message", "source": "Slack", "target": "/checkout/", "title": "Support reports urgent checkout confusion from mobile users", "timestamp": at(1, 3), "metadata": {"provider": "slack", "channel": "support"}},
        {"event_type": "pr_merge", "source": "Felix-Jim", "target": "/checkout/", "title": 'PR #143 merged and deployed within 2 hours', "timestamp": at(1, 4), "metadata": {"pr_number": 143}},
        {"event_type": "metric", "source": "Monitoring", "target": "/checkout/", "title": "Conversion rate up 18% from pre-redesign baseline", "timestamp": at(2), "metadata": {"metric": "conversion_rate", "delta_percent": 18}},
        {"event_type": "agent_action", "source": "Felix-SEO", "target": "/checkout/", "title": 'Submitted PR #144 "Update checkout meta tags"', "timestamp": at(2, 2), "metadata": {"pr_number": 144}},
        {"event_type": "ci_run", "source": "CI", "target": "/checkout/", "title": "Green on all checks", "timestamp": at(2, 3), "metadata": {"status": "passed"}},
        {"event_type": "pr_merge", "source": "Agent-Alpha", "target": "/checkout/", "title": 'PR #145 "Add Google Pay option to checkout"', "timestamp": at(3), "metadata": {"pr_number": 145}},
        {"event_type": "deploy", "source": "DeployBot", "target": "/checkout/", "title": "v2.3.2 deployed", "timestamp": at(3, 2), "metadata": {"version": "v2.3.2", "environment": "production"}},
        {"event_type": "metric", "source": "Monitoring", "target": "orders-api", "title": "Shared payment dependency latency up 22%", "timestamp": at(3, 3), "metadata": {"metric": "latency", "delta_percent": -22, "project": "orders", "dependencies": ["payment"]}},
        {"event_type": "metric", "source": "Monitoring", "target": "/checkout/", "title": "Average checkout time reduced 8%", "timestamp": at(3, 5), "metadata": {"metric": "checkout_time", "delta_percent": 8}},
        {"event_type": "pr_merge", "source": "Felix-CEO", "target": "/checkout/", "title": 'PR #146 "Add order confirmation email template"', "timestamp": at(4), "metadata": {"pr_number": 146}},
        {"event_type": "jira_ticket", "source": "Jira", "target": "CHECKOUT", "title": "CHECKOUT-88: Follow up mobile checkout QA", "timestamp": at(4, 1), "metadata": {"status": "In Progress", "priority": "High"}},
        {"event_type": "agent_action", "source": "ChangelogAgent", "target": "project", "title": "Weekly summary generated", "timestamp": at(4, 4)},
    ]


if __name__ == "__main__":
    cli()
