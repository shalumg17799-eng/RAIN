"""enterprise scoping, run lineage, artifact object-store uri

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = {
    "runs": [sa.Column("enterprise_id", sa.String(50)), sa.Column("parent_run_id", sa.String(36))],
    "artifacts": [sa.Column("enterprise_id", sa.String(50)), sa.Column("uri", sa.Text)],
    "agent_defs": [sa.Column("enterprise_id", sa.String(50))],
}
INDEXES = [("ix_runs_enterprise", "runs", ["enterprise_id"]), ("ix_runs_parent", "runs", ["parent_run_id"]),
           ("ix_artifacts_enterprise_kind", "artifacts", ["enterprise_id", "kind"])]


def upgrade():
    insp = sa.inspect(op.get_bind())
    for table, cols in COLUMNS.items():
        have = {c["name"] for c in insp.get_columns(table)}
        for col in cols:
            if col.name not in have:  # idempotent: adopts DBs created by Store.create_all
                op.add_column(table, col)
    have_idx = {i["name"] for t in COLUMNS for i in insp.get_indexes(t)}
    for name, table, cols in INDEXES:
        if name not in have_idx:
            op.create_index(name, table, cols)
    # child runs created before this migration carried the parent only in their input
    op.execute("update runs set parent_run_id = json_extract(input, '$.__parent') where parent_run_id is null and input like '%__parent%'"
               if op.get_bind().dialect.name == "sqlite" else
               "update runs set parent_run_id = (input::json ->> '__parent') where parent_run_id is null and input like '%__parent%'")


def downgrade():
    for name, table, _ in INDEXES:
        op.drop_index(name, table_name=table)
    for table, cols in COLUMNS.items():
        for col in cols:
            op.drop_column(table, col.name)
