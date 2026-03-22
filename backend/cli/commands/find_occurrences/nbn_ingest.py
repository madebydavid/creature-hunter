from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.models import Occurrence, Taxon


@dataclass(frozen=True)
class IngestPageStats:
    taxa_upserted: int
    occurrences_upserted: int
    skipped_no_species_guid: int
    skipped_no_uuid: int


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


def _coerce_month(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if 1 <= v <= 12 else None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            m = int(s, 10)
        except ValueError:
            return None
        return m if 1 <= m <= 12 else None
    try:
        m = int(v)
    except (TypeError, ValueError):
        return None
    return m if 1 <= m <= 12 else None


def _coerce_geospatial_kosher(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("true", "1", "yes"):
            return True
        if t in ("false", "0", "no"):
            return False
    return None


def _str_list(v: Any) -> list[str] | None:
    if v is None:
        return None
    if not isinstance(v, list):
        return None
    out: list[str] = []
    for x in v:
        if x is None:
            continue
        out.append(str(x))
    return out


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _taxon_row(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    sg = raw.get("speciesGuid")
    if not isinstance(sg, str) or not sg.strip():
        return None
    sg = sg.strip()
    tr_id = _int_or_none(raw.get("taxonRankID"))
    if tr_id is not None and (tr_id < -32768 or tr_id > 32767):
        tr_id = None
    return {
        "species_guid": sg,
        "taxon_concept_id": _str_or_none(raw.get("taxonConceptID")),
        "scientific_name": _str_or_none(raw.get("scientificName")),
        "vernacular_name": _str_or_none(raw.get("vernacularName")),
        "taxon_rank": _str_or_none(raw.get("taxonRank")),
        "taxon_rank_id": tr_id,
        "kingdom": _str_or_none(raw.get("kingdom")),
        "phylum": _str_or_none(raw.get("phylum")),
        "classs": _str_or_none(raw.get("classs")),
        "order": _str_or_none(raw.get("order")),
        "family": _str_or_none(raw.get("family")),
        "genus": _str_or_none(raw.get("genus")),
        "genus_guid": _str_or_none(raw.get("genusGuid")),
        "species": _str_or_none(raw.get("species")),
    }


def _occurrence_row(raw: Mapping[str, Any], species_guid: str) -> dict[str, Any] | None:
    uid = raw.get("uuid")
    if not isinstance(uid, str) or not uid.strip():
        return None
    uid = uid.strip()

    y = _int_or_none(raw.get("year"))
    if y is not None and (y < -32768 or y > 32767):
        y = None

    return {
        "uuid": uid,
        "occurrence_id": _str_or_none(raw.get("occurrenceID")),
        "taxon_species_guid": species_guid,
        "event_date_ms": _int_or_none(raw.get("eventDate")),
        "decimal_latitude": _float_or_none(raw.get("decimalLatitude")),
        "decimal_longitude": _float_or_none(raw.get("decimalLongitude")),
        "coordinate_uncertainty_meters": _float_or_none(
            raw.get("coordinateUncertaintyInMeters")
        ),
        "year": y,
        "month": _coerce_month(raw.get("month")),
        "basis_of_record": _str_or_none(raw.get("basisOfRecord")),
        "country": _str_or_none(raw.get("country")),
        "state_province": _str_or_none(raw.get("stateProvince")),
        "data_provider_uid": _str_or_none(raw.get("dataProviderUid")),
        "data_provider_name": _str_or_none(raw.get("dataProviderName")),
        "data_resource_uid": _str_or_none(raw.get("dataResourceUid")),
        "data_resource_name": _str_or_none(raw.get("dataResourceName")),
        "license": _str_or_none(raw.get("license")),
        "grid_reference": _str_or_none(raw.get("gridReference")),
        "identification_verification_status": _str_or_none(
            raw.get("identificationVerificationStatus")
        ),
        "geospatial_kosher": _coerce_geospatial_kosher(raw.get("geospatialKosher")),
        "assertions": _str_list(raw.get("assertions")),
        "species_groups": _str_list(raw.get("speciesGroups")),
        "recorded_by": _str_list(raw.get("recordedBy")),
        "collectors": _str_list(raw.get("collectors")),
        "life_stage": _str_list(raw.get("lifeStage")),
        "raw_payload": dict(raw),
    }


def _bulk_upsert(
    session: Session,
    table: Any,
    rows: list[dict[str, Any]],
    pk_columns: tuple[str, ...],
) -> None:
    if not rows:
        return
    stmt = pg_insert(table).values(rows)
    excluded = stmt.excluded
    pk_set = set(pk_columns)
    set_ = {
        c.name: excluded[c.name]
        for c in table.columns
        if c.name not in pk_set
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=list(pk_columns),
        set_=set_,
    )
    session.execute(stmt)


def ingest_nbn_page(session: Session, records: list[Any]) -> IngestPageStats:
    skipped_no_species_guid = 0
    skipped_no_uuid = 0

    taxon_by_guid: dict[str, dict[str, Any]] = {}
    occ_by_uuid: dict[str, dict[str, Any]] = {}

    for item in records:
        if not isinstance(item, Mapping):
            continue
        raw = dict(item)
        taxon = _taxon_row(raw)
        if taxon is None:
            skipped_no_species_guid += 1
            continue
        sg = taxon["species_guid"]
        taxon_by_guid[sg] = taxon

        occ = _occurrence_row(raw, sg)
        if occ is None:
            skipped_no_uuid += 1
            continue
        occ_by_uuid[occ["uuid"]] = occ

    occ_rows = list(occ_by_uuid.values())

    taxon_rows = list(taxon_by_guid.values())
    _bulk_upsert(session, Taxon.__table__, taxon_rows, ("species_guid",))
    _bulk_upsert(session, Occurrence.__table__, occ_rows, ("uuid",))

    return IngestPageStats(
        taxa_upserted=len(taxon_rows),
        occurrences_upserted=len(occ_rows),
        skipped_no_species_guid=skipped_no_species_guid,
        skipped_no_uuid=skipped_no_uuid,
    )
