"""One-time SQLite snapshot import into an empty, migrated PostgreSQL database.

Run with server configuration in the environment. The source must be an offline
SQLite backup, never the actively written workspace. Sessions and OAuth nonces
are deliberately excluded; users sign in again on the hosted domain.
"""

import argparse
import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, select, text

from production.database import Base

EXCLUDED = {"sessions", "oauth_states", "rate_windows"}


def copy_snapshot(source_path, target_url):
    source_path = Path(source_path).resolve(strict=True)
    if not target_url.startswith("postgresql+psycopg://"):
        raise ValueError("Target must be PostgreSQL")
    source = create_engine(f"sqlite:///{source_path.as_posix()}")
    target = create_engine(target_url, pool_pre_ping=True, hide_parameters=True)
    expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    counts = {}
    try:
        with source.connect() as src, target.begin() as dst:
            for connection in (src, dst):
                if (
                    connection.execute(
                        text("select version_num from alembic_version")
                    ).scalar()
                    != expected
                ):
                    raise ValueError("Both databases must be at the current schema")
            # Check every application table before any write; import is one transaction.
            for table in Base.metadata.sorted_tables:
                if dst.scalar(select(func.count()).select_from(table)):
                    raise ValueError("Target is not empty; refusing to overwrite data")
            for table in Base.metadata.sorted_tables:
                if table.name in EXCLUDED:
                    continue
                rows = [dict(row) for row in src.execute(select(table)).mappings()]
                if rows:
                    dst.execute(table.insert(), rows)
                counts[table.name] = len(rows)
            for table in Base.metadata.sorted_tables:
                if table.name not in counts:
                    continue
                if (
                    dst.scalar(select(func.count()).select_from(table))
                    != counts[table.name]
                ):
                    raise ValueError("Row-count verification failed")
        return counts
    finally:
        source.dispose()
        target.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        counts = copy_snapshot(args.snapshot, os.environ["DATABASE_URL"])
    except Exception as error:
        # Driver exception text may contain private row values or connection details.
        raise SystemExit(
            f"Import aborted ({type(error).__name__}); no credentials logged."
        ) from None
    print("Import committed; row counts verified:", counts)


if __name__ == "__main__":
    main()
