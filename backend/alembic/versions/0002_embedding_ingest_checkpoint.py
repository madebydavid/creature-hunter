from alembic import op
import sqlalchemy as sa


revision = "0002_embedding_ingest_checkpoint"
down_revision = "0001_create_obs_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding_ingest_checkpoint",
        sa.Column("job_id", sa.String(length=255), nullable=False),
        sa.Column("next_block_y", sa.Integer(), nullable=False),
        sa.Column("next_block_x", sa.Integer(), nullable=False),
        sa.Column("total_written", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("embedding_ingest_checkpoint")
