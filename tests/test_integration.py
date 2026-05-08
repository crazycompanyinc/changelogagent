from click.testing import CliRunner
import httpx
import pytest

from changelogagent.cli import cli
from changelogagent.server.app import create_app


def test_cli_ingest_and_chronicle(tmp_path):
    db = tmp_path / "cli.db"
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(db), "ingest", "--type", "pr_merge", "--source", "Felix", "--target", "checkout", "--title", "PR #1"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["--db", str(db), "chronicle"])
    assert "PR #1" in result.output


def test_cli_demo_runs(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(tmp_path / "demo.db"), "demo"])
    assert result.exit_code == 0
    assert "Conversion rate dropped 12%" in result.output
    assert "Weekly Chronicle" in result.output


@pytest.mark.asyncio
async def test_api_event_timeline_and_chronicle(tmp_path):
    transport = httpx.ASGITransport(app=create_app(tmp_path / "api.db"))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/events", json={"event_type": "incident", "source": "ops", "target": "api", "title": "Outage"})
        health = await client.get("/health")
        timeline = await client.get("/timeline")
        chronicle = await client.get("/chronicle")
    assert response.status_code == 200
    assert health.json() == {"status": "ok"}
    assert len(timeline.json()) == 1
    assert chronicle.json()["lowlights"] == ["Outage"]


@pytest.mark.asyncio
async def test_api_webhooks(tmp_path):
    transport = httpx.ASGITransport(app=create_app(tmp_path / "api_webhook.db"))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ci = await client.post("/webhook/ci", json={"status": "passed", "service": "api"})
        deploy = await client.post("/webhook/deploy", json={"version": "v1", "service": "api"})
        timeline = await client.get("/timeline")
    assert ci.status_code == 200
    assert deploy.status_code == 200
    assert len(timeline.json()) == 2
