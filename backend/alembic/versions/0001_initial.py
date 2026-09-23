"""Initial tables; adopt the pre-migration MVP schema without deleting its data."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "scenarios" not in existing:
        op.create_table("scenarios", sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("name", sa.String(120), nullable=False),
                        sa.Column("scenario_type", sa.String(60), nullable=False),
                        sa.Column("description", sa.String(500), nullable=False),
                        sa.Column("configuration", sa.JSON, nullable=False),
                        sa.Column("created_at", sa.DateTime, nullable=False))
    if "algorithms" not in existing:
        op.create_table("algorithms", sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("name", sa.String(120), nullable=False),
                        sa.Column("version", sa.String(80), nullable=False),
                        sa.Column("description", sa.String(500), nullable=False),
                        sa.Column("configuration", sa.JSON, nullable=False),
                        sa.Column("artifact_id", sa.String(120), nullable=False),
                        sa.Column("created_at", sa.DateTime, nullable=False))
    if "runs" not in existing:
        op.create_table("runs", sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("scenario_id", sa.Integer, nullable=False),
                        sa.Column("algorithm_id", sa.Integer, nullable=False),
                        sa.Column("status", sa.String(30), nullable=False),
                        sa.Column("started_at", sa.DateTime, nullable=False),
                        sa.Column("ended_at", sa.DateTime), sa.Column("random_seed", sa.Integer, nullable=False),
                        sa.Column("environment", sa.JSON, nullable=False),
                        sa.Column("telemetry", sa.JSON, nullable=False),
                        sa.Column("metrics", sa.JSON, nullable=False),
                        sa.Column("error_message", sa.String(500), nullable=False))


def downgrade():
    op.drop_table("runs")
    op.drop_table("algorithms")
    op.drop_table("scenarios")
