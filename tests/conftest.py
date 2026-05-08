from __future__ import annotations

import pytest

from changelogagent.core.db import EventStore


@pytest.fixture()
def store(tmp_path):
    return EventStore(tmp_path / "test.db")
