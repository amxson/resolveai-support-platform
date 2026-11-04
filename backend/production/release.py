"""Reviewed release entrypoint: migrate, then run one API with an embedded worker."""

import os

import uvicorn
from alembic import command
from alembic.config import Config


def main():
    # CLI secret values remain environment-only, never arguments or output.
    command.upgrade(Config("alembic.ini"), "head")
    uvicorn.run(
        "production.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        access_log=False,
    )


if __name__ == "__main__":
    main()
