import datetime
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

from tabulate import tabulate

from db.session import session_scope
from .nbn_ingest import ingest_nbn_page


# (min_lon, min_lat, max_lon, max_lat) in WGS84 lon/lat.
SEUK_BBOX = (-1.9, 50.4, 1.9, 52.3)

BASE_URL = "https://records-ws.nbnatlas.org/occurrences/search"
PAGE_SIZE = 1000
NUM_PAGES = 3  # fetch 3 pages for hello-world

# Output shaping (to keep console rows short / not wrapping)
NAME_MAX_LEN = 34
UUID_SHORT_LEN = 8
LATLON_DECIMALS = 4

# NBN often publishes grid-based records (OS grid references) as centroid lat/lon
# plus a coordinate uncertainty radius. Common values map to common grid sizes:
# - 7.1m  ~= 10m grid square
# - 70.7m ~= 100m grid square
# (See NBN docs: https://docs.nbnatlas.org/grid-and-coordinate-based-records-on-the-nbn-atlas/)
#
# This filter keeps only the highest-precision *grid-derived* public locations
# (10m + 100m). Remove this fq if you want all resolutions.
UNCERTAINTY_FQ = '(coordinateUncertaintyInMeters:"7.1" OR coordinateUncertaintyInMeters:"70.7")'
# Kingdom filter: focus on Animalia only.
KINGDOM_FQ = 'kingdom:"Animalia"'


# Exact trailing window: "2 years ago" (UTC), using the NBN `eventDate` field.
#
# Note: `eventDate` appears as epoch-millis in responses, but for filtering the API expects
# an ISO-8601 datetime string in Solr range syntax.
def _start_iso_trailing_2_years(*, now_utc: datetime.datetime) -> str:
    # Subtract 2 calendar years while keeping month/day/time.
    # Handles Feb 29 by clamping to Feb 28 in non-leap years.
    try:
        start_dt = now_utc.replace(year=now_utc.year - 2)
    except ValueError:
        start_dt = now_utc.replace(year=now_utc.year - 2, day=28)

    # NBN examples accept "...Z" style.
    return start_dt.isoformat().replace("+00:00", "Z")


def _event_date_fq(start_iso: str) -> str:
    return f"eventDate:[{start_iso} TO *]"


def _http_get_json(url: str, *, timeout_s: float = 30.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "creature-hunter/0.1 (cli find-occurrences)",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read()
    return json.loads(body.decode("utf-8"))


def main() -> int:
    min_lon, min_lat, max_lon, max_lat = SEUK_BBOX
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_iso = _start_iso_trailing_2_years(now_utc=now_utc)
    event_date_fq = _event_date_fq(start_iso=start_iso)

    occs: list[dict[str, Any]] = []
    total_records: Any = None
    persist = bool(os.environ.get("DATABASE_URL"))
    total_taxa_upserted = 0
    total_occ_upserted = 0
    total_skip_species = 0
    total_skip_uuid = 0

    for page in range(NUM_PAGES):
        start_index = page * PAGE_SIZE
        params: list[tuple[str, str]] = [
            ("q", "*:*"),
            ("pageSize", str(PAGE_SIZE)),
            ("startIndex", str(start_index)),
            ("fq", f"decimalLongitude:[{min_lon} TO {max_lon}]"),
            ("fq", f"decimalLatitude:[{min_lat} TO {max_lat}]"),
            ("fq", UNCERTAINTY_FQ),
            ("fq", event_date_fq),
            ("fq", KINGDOM_FQ),
        ]
        url = f"{BASE_URL}?{urllib.parse.urlencode(params, doseq=True)}"
        payload = _http_get_json(url)
        if total_records is None:
            total_records = payload.get("totalRecords")
        page_occs = payload.get("occurrences") or []
        page_dicts: list[dict[str, Any]] = []
        if isinstance(page_occs, list):
            for o in page_occs:
                if isinstance(o, dict):
                    occs.append(o)
                    page_dicts.append(o)

        if persist and page_dicts:
            with session_scope() as db:
                st = ingest_nbn_page(db, page_dicts)
            total_taxa_upserted += st.taxa_upserted
            total_occ_upserted += st.occurrences_upserted
            total_skip_species += st.skipped_no_species_guid
            total_skip_uuid += st.skipped_no_uuid

    def _short_name(v: Any) -> str:
        s = "" if v is None else str(v)
        if len(s) <= NAME_MAX_LEN:
            return s
        return s[: NAME_MAX_LEN - 1] + "…"

    def _short_uuid(v: Any) -> str:
        s = "" if v is None else str(v)
        return s[:UUID_SHORT_LEN]

    def _fmt_float(v: Any) -> str:
        if v is None:
            return ""
        try:
            return f"{float(v):.{LATLON_DECIMALS}f}"
        except Exception:
            return str(v)

    rows: list[list[str]] = []
    for o in occs:
        month = o.get("month")
        month_s = "" if month is None else str(month)
        rows.append(
            [
                _short_name(o.get("scientificName")),
                str(o.get("year") or ""),
                month_s,
                _fmt_float(o.get("decimalLatitude")),
                _fmt_float(o.get("decimalLongitude")),
                str(o.get("license") or ""),
                str(o.get("gridReference") or ""),
                _short_uuid(o.get("uuid")),
            ]
        )

    headers = ["scientificName", "year", "month", "lat", "lon", "license", "gridRef", "uuid8"]
    # tabulate does alignment; since names are already truncated, it stays readable.
    print(tabulate(rows, headers=headers, tablefmt="simple"))

    # Small footer to stderr so piping stays clean.
    parts = [
        f"Done. totalRecords={total_records} fetched={len(occs)} pages={NUM_PAGES} pageSize={PAGE_SIZE}",
    ]
    if persist:
        parts.append(
            f"db upserted taxa={total_taxa_upserted} occurrences={total_occ_upserted} "
            f"skipped_no_speciesGuid={total_skip_species} skipped_no_uuid={total_skip_uuid}"
        )
    print(" ".join(parts), file=sys.stderr)
    return 0
