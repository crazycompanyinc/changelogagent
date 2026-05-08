# ChangelogAgent

ChangelogAgent turns operational events into a living project chronicle. It ingests commits, PR merges, CI runs, deploys, incidents, rollbacks, metrics, and agent actions, then builds timelines, detects grounded impact chains, and writes narrative summaries.

## Install

```bash
pip install -e .
```

## Quick Start

```bash
changelogagent init
changelogagent ingest --type pr_merge --source Felix --target checkout --title "Redesign checkout flow"
changelogagent chronicle --format markdown
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
- `POST /webhook/git`
- `POST /webhook/ci`
- `POST /webhook/deploy`
- `GET /health`

## Architecture

- `core`: dataclasses and SQLite storage
- `ingest`: validation, enrichment, scoring, webhook event adapters
- `timeline`: event grouping into chronological sequences
- `impact`: grounded temporal cause-effect chain detection
- `narrator`: template-backed narrative generation
- `summarizer`: daily, weekly, monthly chronicle entries
- `server`: FastAPI app and webhook receivers
- `cli.py`: Click command line interface
