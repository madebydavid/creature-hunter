from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Taxon(Base):
    __tablename__ = "taxon"

    # Selected PK from JSON: `speciesGuid`
    species_guid: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Optional concept identifier (`taxonConceptID`) for cross-system joins/debugging.
    taxon_concept_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Snapshot taxonomy fields (nullable).
    scientific_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vernacular_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    taxon_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    taxon_rank_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    kingdom: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phylum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Note: JSON key is `classs` (not `class`). Keep column name as `classs` to avoid confusion.
    classs: Mapped[str | None] = mapped_column(String(64), nullable=True)

    order: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family: Mapped[str | None] = mapped_column(String(128), nullable=True)
    genus: Mapped[str | None] = mapped_column(String(128), nullable=True)
    genus_guid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    species: Mapped[str | None] = mapped_column(String(255), nullable=True)

    occurrences: Mapped[list[Occurrence]] = relationship(back_populates="taxon")


class Occurrence(Base):
    __tablename__ = "occurrence"

    # Selected PK from JSON: `uuid`
    uuid: Mapped[str] = mapped_column(String(36), primary_key=True)

    occurrence_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    taxon_species_guid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("taxon.species_guid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taxon: Mapped[Taxon] = relationship(back_populates="occurrences")

    # Core observation fields.
    event_date_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decimal_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    decimal_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_uncertainty_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    basis_of_record: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(128), nullable=True)

    data_provider_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_resource_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    license: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grid_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identification_verification_status: Mapped[str | None] = mapped_column(String(255), nullable=True)

    geospatial_kosher: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Repeated fields stored as JSONB arrays on the occurrence.
    assertions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    species_groups: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    recorded_by: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    collectors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    life_stage: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)

    # Forward-compat: keep the entire incoming record.
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class EmbeddingIngestCheckpoint(Base):
    """Resume cursor for AlphaEarth → Milvus embedding ingest (`load-data` CLI)."""

    __tablename__ = "embedding_ingest_checkpoint"

    job_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    next_block_y: Mapped[int] = mapped_column(Integer, nullable=False)
    next_block_x: Mapped[int] = mapped_column(Integer, nullable=False)
    total_written: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

