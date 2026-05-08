# ChangelogAgent

ChangelogAgent turns operational events into a living project chronicle. It ingests commits, PR merges, CI runs, deploys, incidents, rollbacks, metrics, issues, Jira tickets, Slack/Discord messages, PagerDuty incidents, and agent actions, then builds timelines, detects causal impact chains, predicts likely outcomes, and writes stakeholder-specific narrative summaries.

## Install

```bash
pip install -e .
```

## Quick Start

```bash
changelogagent init
changelogagent ingest --type pr_merge --source Felix --target checkout --title "Redesign checkout flow"
changelogagent chronicle --format markdown
changelogagent v2-insights
changelogagent v2-report --audience executive
changelogagent search auth
changelogagent demo
```

By default the CLI stores data in `.changelogagent/changelogagent.db`. Set `CHANGELOGAGENT_DB` to use a different SQLite path.

## API

```bash
changelogagent serve --port 8000
```

Endpoints:

- `POST /events`
- `GET /chronicle`
- `GET /timeline`
- `GET /impact`
- `GET /summary`
- `GET /v2/causal`
- `GET /v2/predictions`
- `GET /v2/sentiment`
- `GET /v2/anomalies`
- `GET /v2/cross-project`
- `GET /v2/search?q=auth`
- `GET /v2/report/{executive|engineering|standup}`
- `GET /v2/export/{markdown|html|json|pdf|confluence|notion}`
- `GET /v2/timeline/ascii`
- `WS /v2/live`
- `POST /webhook/git`
- `POST /webhook/ci`
- `POST /webhook/deploy`
- `POST /v2/ingest/github`
- `POST /v2/ingest/slack`
- `POST /v2/ingest/discord`
- `POST /v2/ingest/pagerduty`
- `POST /v2/ingest/jira`
- `GET /health`

## v2 Capabilities

- Multi-source ingestion adapters for GitHub API snapshots, Slack, Discord, PagerDuty, and Jira.
- Causal impact analysis using temporal proximity, shared services/dependencies, and operational failure patterns.
- Predictive narrative generation from recent deploy and incident trajectories.
- Project sentiment analysis from incidents, rollbacks, and communication pressure.
- Stakeholder reports for executives, engineering deep dives, and team standups.
- Real-time chronicle updates over WebSocket.
- Anomaly detection for unusual deploy, incident, rollback, and communication rates.
- Cross-project correlation through shared service/dependency metadata.
- Narrative quality scoring for coherence, completeness, accuracy, and feedback-adjusted accuracy.
- Exports for Markdown, HTML, JSON, PDF bytes, Confluence payloads, and Notion payloads.
- Search across stored chronicle evidence.
- ASCII timeline visualization for terminal and API use.

## Architecture

- `core`: dataclasses and SQLite storage
- `ingest`: validation, enrichment, scoring, webhook event adapters
- `timeline`: event grouping into chronological sequences
- `impact`: grounded temporal cause-effect chain detection
- `analysis`: causal, predictive, sentiment, anomaly, cross-project, and quality engines
- `sources`: GitHub, Slack, Discord, PagerDuty, and Jira adapters/API clients
- `reports`: audience-specific report generation
- `export`: documentation-system export formats
- `search`: chronicle search service
- `realtime`: live feed fan-out for WebSocket subscribers
- `visualization`: ASCII timeline rendering
- `narrator`: template-backed narrative generation
- `summarizer`: daily, weekly, monthly chronicle entries
- `server`: FastAPI app and webhook receivers
- `cli.py`: Click command line interface
