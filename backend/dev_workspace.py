"""Local-only development launcher. Production runs migrations separately."""
import os

import uvicorn
from alembic import command
from alembic.config import Config

if os.environ.get("APP_ENV") == "production":
    raise RuntimeError("Use the release migration step for production")
command.upgrade(Config("alembic.ini"), "head")
uvicorn.run("production.app:create_app", factory=True, host="127.0.0.1", port=8001)
