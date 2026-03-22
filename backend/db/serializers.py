from __future__ import annotations

from db.models import Occurrence, Taxon
from db.schemas import ObservationResponse, TaxonResponse


def serialize_taxon(taxon: Taxon | None) -> TaxonResponse | None:
    if taxon is None:
        return None
    return TaxonResponse.model_validate(taxon, from_attributes=True)


def serialize_observation(occ: Occurrence, taxon: Taxon | None = None) -> ObservationResponse:
    # Build the response from scalar attributes on the ORM object.
    resp = ObservationResponse.model_validate(occ, from_attributes=True)

    # If the caller provides an explicit Taxon, use it. Otherwise, try the
    # relationship attribute (may trigger lazy-load if not pre-loaded).
    taxon_to_use = taxon if taxon is not None else getattr(occ, "taxon", None)
    resp.taxon = serialize_taxon(taxon_to_use)

    return resp

