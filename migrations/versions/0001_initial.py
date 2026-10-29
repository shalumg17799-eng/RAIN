"""initial schema: runs, events, artifacts, agent_defs

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _missing(name):
    return not sa.inspect(op.get_bind()).has_table(name)  # idempotent: adopts DBs created before migrations existed


def upgrade():
    if _missing("runs"):
        op.create_table("runs",
            sa.Column("id", sa.String(36), primary_key=True), sa.Column("agent", sa.String(100)),
            sa.Column("agent_version", sa.String(20)), sa.Column("created_by", sa.String(100)),
            sa.Column("status", sa.String(20)), sa.Column("input", sa.Text), sa.Column("state", sa.Text),
            sa.Column("output", sa.Text), sa.Column("error", sa.Text),
            sa.Column("created_at", sa.Float), sa.Column("updated_at", sa.Float))
        op.create_index("ix_runs_status", "runs", ["status"])
    if _missing("events"):
        op.create_table("events",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("run_id", sa.String(36)),
            sa.Column("ts", sa.Float), sa.Column("event", sa.String(50)), sa.Column("detail", sa.Text))
        op.create_index("ix_events_run_id", "events", ["run_id"])
    if _missing("artifacts"):
        op.create_table("artifacts",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("run_id", sa.String(36)),
            sa.Column("kind", sa.String(50)), sa.Column("version", sa.Integer), sa.Column("body", sa.Text),
            sa.Column("created_at", sa.Float))
    if _missing("agent_defs"):
        op.create_table("agent_defs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("name", sa.String(100)),
            sa.Column("version", sa.String(20)), sa.Column("enabled", sa.Integer), sa.Column("config", sa.Text),
            sa.Column("created_by", sa.String(100)), sa.Column("created_at", sa.Float))


def downgrade():
    for t in ("agent_defs", "artifacts", "events", "runs"):
        op.drop_table(t)
