import os

import pytest
from alembic import command
from alembic.config import Config

from production.app import create_app


@pytest.fixture
def application(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENV", "test")
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    app = create_app(url, secure_cookies=False)
    yield app
    app.state.engine.dispose()
    if os.environ.get("TEST_DATABASE_URL"):
        command.downgrade(config, "base")
