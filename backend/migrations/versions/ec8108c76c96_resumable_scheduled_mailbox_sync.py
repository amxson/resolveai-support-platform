"""Resumable mailbox sync; batch mode supports local SQLite."""

import sqlalchemy as sa
from alembic import op

revision = "ec8108c76c96"
down_revision = "202d3915204e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("mailboxes") as batch:
        batch.add_column(sa.Column("sync_actor_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("sync_cursor", sa.Text(), nullable=True))
        for name in ["synced_after", "scan_started", "next_sync_at"]:
            batch.add_column(
                sa.Column(name, sa.Float(), server_default="0", nullable=False)
            )
        batch.add_column(
            sa.Column("sync_failures", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("sync_error", sa.String(80), nullable=True))
        batch.create_foreign_key(
            "fk_mailboxes_sync_actor", "users", ["sync_actor_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("mailboxes") as batch:
        batch.drop_constraint("fk_mailboxes_sync_actor", type_="foreignkey")
        for name in [
            "sync_error",
            "sync_failures",
            "next_sync_at",
            "scan_started",
            "synced_after",
            "sync_cursor",
            "sync_actor_id",
        ]:
            batch.drop_column(name)
