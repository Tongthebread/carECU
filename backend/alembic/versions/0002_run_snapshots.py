"""Persist immutable configuration snapshots and generated reports."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("runs", sa.Column("snapshot", sa.JSON, nullable=False, server_default="{}"))
    op.add_column("runs", sa.Column("report", sa.JSON, nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("report")
        batch.drop_column("snapshot")
