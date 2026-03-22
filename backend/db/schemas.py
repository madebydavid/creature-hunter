from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaxonResponse(BaseModel):
    species_guid: str
    taxon_concept_id: str | None = None

    scientific_name: str | None = None
    vernacular_name: str | None = None
    taxon_rank: str | None = None
    taxon_rank_id: int | None = None

    kingdom: str | None = None
    phylum: str | None = None
    classs: str | None = None

    order: str | None = None
    family: str | None = None
    genus: str | None = None
    genus_guid: str | None = None

    species: str | None = None


class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    occurrence_id: str | None

    taxon_species_guid: str

    event_date_ms: int | None
    decimal_latitude: float | None
    decimal_longitude: float | None
    coordinate_uncertainty_meters: float | None

    year: int | None
    month: int | None

    basis_of_record: str | None
    country: str | None
    state_province: str | None

    data_provider_uid: str | None
    data_provider_name: str | None
    data_resource_uid: str | None
    data_resource_name: str | None

    assertions: list[str] = Field(default_factory=list)
    species_groups: list[str] = Field(default_factory=list)
    life_stage: list[str] = Field(default_factory=list)
    recorded_by: list[str] = Field(default_factory=list)
    collectors: list[str] = Field(default_factory=list)

    license: str | None
    identification_verification_status: str | None
    grid_reference: str | None

    geospatial_kosher: bool | None

    taxon: TaxonResponse | None = None

    @field_validator(
        "assertions",
        "species_groups",
        "life_stage",
        "recorded_by",
        "collectors",
        mode="before",
    )
    @classmethod
    def _none_list_to_empty(cls, v: object) -> list[str]:
        # Postgres JSONB columns can be NULL; keep our API contracts stable by
        # normalizing NULL -> [] for repeated fields.
        if v is None:
            return []
        # If it already looks like a list, let Pydantic handle the rest.
        return v  # type: ignore[return-value]

