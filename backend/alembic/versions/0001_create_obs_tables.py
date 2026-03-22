from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_create_obs_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxon",
        sa.Column("species_guid", sa.String(length=64), nullable=False),
        sa.Column("taxon_concept_id", sa.String(length=64), nullable=True),
        sa.Column("scientific_name", sa.String(length=255), nullable=True),
        sa.Column("vernacular_name", sa.String(length=255), nullable=True),
        sa.Column("taxon_rank", sa.String(length=64), nullable=True),
        sa.Column("taxon_rank_id", sa.SmallInteger(), nullable=True),
        sa.Column("kingdom", sa.String(length=64), nullable=True),
        sa.Column("phylum", sa.String(length=64), nullable=True),
        sa.Column("classs", sa.String(length=64), nullable=True),
        sa.Column("order", sa.String(length=128), nullable=True),
        sa.Column("family", sa.String(length=128), nullable=True),
        sa.Column("genus", sa.String(length=128), nullable=True),
        sa.Column("genus_guid", sa.String(length=64), nullable=True),
        sa.Column("species", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("species_guid"),
    )
    op.create_index("ix_taxon_taxon_concept_id", "taxon", ["taxon_concept_id"])

    op.create_table(
        "occurrence",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("occurrence_id", sa.String(length=64), nullable=True),
        sa.Column("taxon_species_guid", sa.String(length=64), nullable=False),
        sa.Column("event_date_ms", sa.BigInteger(), nullable=True),
        sa.Column("decimal_latitude", sa.Float(), nullable=True),
        sa.Column("decimal_longitude", sa.Float(), nullable=True),
        sa.Column("coordinate_uncertainty_meters", sa.Float(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("month", sa.SmallInteger(), nullable=True),
        sa.Column("basis_of_record", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("state_province", sa.String(length=128), nullable=True),
        sa.Column("data_provider_uid", sa.String(length=64), nullable=True),
        sa.Column("data_provider_name", sa.String(length=255), nullable=True),
        sa.Column("data_resource_uid", sa.String(length=64), nullable=True),
        sa.Column("data_resource_name", sa.String(length=255), nullable=True),
        sa.Column("license", sa.String(length=64), nullable=True),
        sa.Column("grid_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "identification_verification_status", sa.String(length=255), nullable=True
        ),
        sa.Column("geospatial_kosher", sa.Boolean(), nullable=True),
        sa.Column("assertions", postgresql.JSONB(), nullable=True),
        sa.Column("species_groups", postgresql.JSONB(), nullable=True),
        sa.Column("recorded_by", postgresql.JSONB(), nullable=True),
        sa.Column("collectors", postgresql.JSONB(), nullable=True),
        sa.Column("life_stage", postgresql.JSONB(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["taxon_species_guid"],
            ["taxon.species_guid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index("ix_occurrence_occurrence_id", "occurrence", ["occurrence_id"])
    op.create_index(
        "ix_occurrence_taxon_species_guid", "occurrence", ["taxon_species_guid"]
    )


def downgrade() -> None:
    op.drop_index("ix_occurrence_taxon_species_guid", table_name="occurrence")
    op.drop_index("ix_occurrence_occurrence_id", table_name="occurrence")
    op.drop_table("occurrence")
    op.drop_index("ix_taxon_taxon_concept_id", table_name="taxon")
    op.drop_table("taxon")

