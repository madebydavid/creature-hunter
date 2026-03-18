import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional
import hashlib

import numpy as np
import xarray as xr
from pyproj import Transformer

from checkpoint_sqlite import Checkpoint, CheckpointStore
from ee_embeddings import band_names, build_annual_embedding_image, init_ee, load_key_json, open_xarray_dataset, require_env
from milvus_sink import MilvusSink


EMB_DIM = 64

# SEUK bbox guess in WGS84 lon/lat. Tweak this tuple as desired.
# (min_lon, min_lat, max_lon, max_lat)
SEUK_BBOX = (-1.9, 50.4, 1.9, 52.3)

# Hard-coded “current year / most recent” as requested.
EMBEDDING_YEAR = 2025

# Treat the embedding raster as a fixed grid in British National Grid.
TARGET_EPSG = "EPSG:27700"
# Default to 100m for dev iteration speed.
SCALE_METERS = 100

_DEFAULT_CHECKPOINT_DB_PATH = os.path.join(os.path.dirname(__file__), "checkpoints.sqlite")
CHECKPOINT_DB_PATH = os.environ.get("CHECKPOINT_DB_PATH", _DEFAULT_CHECKPOINT_DB_PATH)


@dataclass(frozen=True)
class GridOrigin:
    x0: float
    y0: float


def _collection_name(year: int) -> str:
    return f"seuk_embeddings_annual_{year}_{SCALE_METERS}m"


def _fmt_eta(seconds: float) -> str:
    if not np.isfinite(seconds) or seconds < 0:
        return "unknown"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}d{h:02d}h"
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m{s:02d}s"

def _job_id(target_collection: str) -> str:
    # Tie checkpoint to ingest config so changes don’t collide.
    payload = {
        "target_collection": target_collection,
        "year": EMBEDDING_YEAR,
        "bbox": SEUK_BBOX,
        "epsg": TARGET_EPSG,
        "scale_m": SCALE_METERS,
        "dim": EMB_DIM,
        "source": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{target_collection}:{digest[:12]}"

def _grid_origin_from_coords(x_coords: np.ndarray, y_coords: np.ndarray) -> GridOrigin:
    # Use the minimum coord as the origin so ix/iy are non-negative.
    # x_coords and y_coords are 1D coordinate arrays in meters.
    return GridOrigin(x0=float(np.min(x_coords)), y0=float(np.min(y_coords)))


def _pack_id(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    # Pack two non-negative int32 indices into a single int64:
    # id = (iy << 32) | (ix & 0xFFFFFFFF)
    ix_u = (ix.astype(np.int64) & 0xFFFFFFFF)
    iy_u = (iy.astype(np.int64) & 0xFFFFFFFF)
    return (iy_u << 32) | ix_u


def _iter_blocks(ds: xr.Dataset) -> Iterable[tuple[int, int, xr.Dataset]]:
    """
    Iterate through ds in deterministic Y-major block order.
    Requires ds to have 1D coords X and Y.
    """
    y_chunks = ds.chunks.get("Y") if getattr(ds, "chunks", None) else None
    x_chunks = ds.chunks.get("X") if getattr(ds, "chunks", None) else None
    if not y_chunks or not x_chunks:
        # Fall back to single block.
        yield (0, 0, ds)
        return

    # xarray/dask versions differ: chunks may be a tuple of ints (sizes),
    # or a tuple-of-tuples (one tuple per dask array axis). Normalize to a
    # flat tuple[int, ...] of chunk sizes.
    def _norm_chunks(chunks_obj: object) -> tuple[int, ...]:
        if not isinstance(chunks_obj, tuple) or len(chunks_obj) == 0:
            raise TypeError(f"Unexpected chunks object: {type(chunks_obj)}")
        first = chunks_obj[0]
        if isinstance(first, int):
            return chunks_obj  # already flat sizes
        if isinstance(first, tuple) and (len(first) == 0 or isinstance(first[0], int)):
            return first  # tuple-of-tuples; use first axis sizes
        raise TypeError(f"Unexpected chunks shape: {chunks_obj!r}")

    y_sizes = _norm_chunks(y_chunks)
    x_sizes = _norm_chunks(x_chunks)

    y_starts: list[int] = []
    acc = 0
    for c in y_sizes:
        y_starts.append(acc)
        acc += c

    x_starts: list[int] = []
    acc = 0
    for c in x_sizes:
        x_starts.append(acc)
        acc += c

    for by, y0 in enumerate(y_starts):
        y_len = y_sizes[by]
        for bx, x0 in enumerate(x_starts):
            x_len = x_sizes[bx]
            yield (by, bx, ds.isel(Y=slice(y0, y0 + y_len), X=slice(x0, x0 + x_len)))


def _block_grid_shape(ds: xr.Dataset) -> tuple[int, int]:
    """
    Return (num_y_blocks, num_x_blocks) for current ds chunking.
    """
    y_chunks = ds.chunks.get("Y") if getattr(ds, "chunks", None) else None
    x_chunks = ds.chunks.get("X") if getattr(ds, "chunks", None) else None
    if not y_chunks or not x_chunks:
        return (1, 1)

    def _norm(chunks_obj: object) -> tuple[int, ...]:
        if not isinstance(chunks_obj, tuple) or len(chunks_obj) == 0:
            return (int(chunks_obj),)  # type: ignore[arg-type]
        first = chunks_obj[0]
        if isinstance(first, int):
            return chunks_obj
        if isinstance(first, tuple):
            return first
        return (1,)

    y_sizes = _norm(y_chunks)
    x_sizes = _norm(x_chunks)
    return (len(y_sizes), len(x_sizes))


def main() -> int:
    key_file = require_env("GOOGLE_APPLICATION_CREDENTIALS")
    key = load_key_json(key_file)

    service_account = os.environ.get("SERVICE_ACCOUNT_EMAIL") or key.get("client_email")
    project = os.environ.get("GCP_PROJECT_ID") or key.get("project_id")

    if not service_account:
        raise RuntimeError("Could not determine service account email (client_email).")
    if not project:
        raise RuntimeError("Could not determine project id (project_id).")

    init_ee(key_file=key_file, service_account=service_account, project=project)
    print(f"EE initialized. service_account={service_account} project={project}")

    # Hard-coded SEUK bbox in WGS84 lon/lat.
    bbox = SEUK_BBOX
    bands = band_names(EMB_DIM)
    im = build_annual_embedding_image(year=EMBEDDING_YEAR, bbox_wgs84=bbox, bands=bands)
    ds = open_xarray_dataset(
        image=im,
        bbox_wgs84=bbox,
        projection=TARGET_EPSG,
        scale_m=SCALE_METERS,
        chunks={"X": 512, "Y": 512},
    )

    print("Opened xarray dataset:")
    print(f"  dims={dict(ds.dims)}")
    print(f"  data_vars={list(ds.data_vars)}")
    print(f"  coords={list(ds.coords)}")

    missing_bands = [b for b in bands if b not in ds.data_vars]
    if missing_bands:
        raise RuntimeError(f"Dataset is missing expected embedding bands: {missing_bands[:5]}...")

    x_coords = np.asarray(ds["X"].values)
    y_coords = np.asarray(ds["Y"].values)
    origin = _grid_origin_from_coords(x_coords, y_coords)
    print(f"Grid origin (for id packing): x0={origin.x0:.3f} y0={origin.y0:.3f} epsg={TARGET_EPSG}")

    # Milvus setup.
    col_name = _collection_name(EMBEDDING_YEAR)
    sink = MilvusSink(collection_name=col_name, dim=EMB_DIM)
    sink.connect()
    sink.ensure_collection()
    existing = sink.num_entities()
    job_id = _job_id(col_name)
    ckpt_store = CheckpointStore(CHECKPOINT_DB_PATH)
    ckpt_db = ckpt_store.connect()
    ckpt = ckpt_store.read(ckpt_db, job_id)
    print(
        f"Milvus collection loaded: {col_name} entities={existing} "
        f"checkpoint_job={job_id} checkpoint_db={CHECKPOINT_DB_PATH} "
        f"next_block=({ckpt.next_by},{ckpt.next_bx}) ckpt_written={ckpt.total_written}"
    )

    # Coordinate transform for lat/lon output.
    to_wgs84 = Transformer.from_crs(TARGET_EPSG, "EPSG:4326", always_xy=True)

    # Ingestion loop.
    t0 = time.time()
    total_rows_seen = 0
    total_rows_written = 0
    total_pixels = int(ds.sizes["X"]) * int(ds.sizes["Y"]) if hasattr(ds, "sizes") else None
    num_y_blocks, num_x_blocks = _block_grid_shape(ds)
    print(f"Block grid: y_blocks={num_y_blocks} x_blocks={num_x_blocks}")

    for by, bx, block in _iter_blocks(ds):
        if by < ckpt.next_by or (by == ckpt.next_by and bx < ckpt.next_bx):
            continue

        # Materialize embeddings for this block as (Y, X, C).
        # xee exposes a singleton `time` dim; select it before transposing.
        arr = (
            block.to_array()
            .isel(time=0)
            .transpose("Y", "X", "variable")
            .values  # type: ignore[attr-defined]
        )
        if arr.size == 0:
            continue

        yv = np.asarray(block["Y"].values)
        xv = np.asarray(block["X"].values)

        # Compute integer grid indices and packed ids.
        ix = np.rint((xv - origin.x0) / SCALE_METERS).astype(np.int64)
        iy = np.rint((yv - origin.y0) / SCALE_METERS).astype(np.int64)
        ix2d, iy2d = np.meshgrid(ix, iy)
        ids = _pack_id(ix2d.reshape(-1), iy2d.reshape(-1))

        # Flatten embeddings.
        emb = arr.reshape(-1, EMB_DIM).astype(np.float32)

        # Drop rows with NaNs (common on edges / no-data).
        good = np.isfinite(emb).all(axis=1)

        if not np.any(good):
            total_rows_seen += int(ids.size)
            elapsed = time.time() - t0
            rate = total_rows_written / elapsed if elapsed > 0 else 0.0
            print(
                f"block y={by} x={bx} rows={ids.size} written=0 total_written={total_rows_written} rate={rate:.1f}/s"
            )
            continue

        ids_g = ids[good]
        emb_g = emb[good]

        # Lat/lon for pixel centers.
        x2d, y2d = np.meshgrid(xv, yv)
        lon, lat = to_wgs84.transform(x2d.reshape(-1)[good], y2d.reshape(-1)[good])
        lat_g = np.asarray(lat, dtype=np.float32)
        lon_g = np.asarray(lon, dtype=np.float32)

        # Upsert in batches.
        batch_size = int(os.environ.get("MILVUS_BATCH_SIZE", "20000"))
        written_this_block = 0
        for start in range(0, ids_g.size, batch_size):
            end = min(start + batch_size, ids_g.size)
            sink.upsert_batch(
                ids=ids_g[start:end].tolist(),
                lat=lat_g[start:end].tolist(),
                lon=lon_g[start:end].tolist(),
                vectors=emb_g[start:end].tolist(),
            )
            written_this_block += (end - start)

        sink.flush()

        total_rows_seen += int(ids.size)
        total_rows_written += int(written_this_block)
        elapsed = time.time() - t0
        rate = total_rows_written / elapsed if elapsed > 0 else 0.0
        pct_str = "pct=unknown"
        eta_str = "eta=unknown"
        if total_pixels is not None and total_rows_seen > 0 and rate > 0:
            fill_ratio = total_rows_written / total_rows_seen
            est_total = max(1.0, float(total_pixels) * float(fill_ratio))
            pct = min(1.0, float(total_rows_written) / est_total)
            remaining = max(0.0, est_total - float(total_rows_written))
            pct_str = f"pct={pct*100:.2f}%"
            eta_str = f"eta={_fmt_eta(remaining / rate)}"
        print(
            f"block y={by} x={bx} rows={ids.size} written={written_this_block} "
            f"total_written={total_rows_written} elapsed={elapsed:.1f}s rate={rate:.1f}/s {pct_str} {eta_str}"
        )

        # Update checkpoint to the next block after a successful flush.
        if bx + 1 < num_x_blocks:
            nb = (by, bx + 1)
        else:
            nb = (by + 1, 0)
        ckpt_store.write(
            ckpt_db,
            job_id,
            Checkpoint(next_by=nb[0], next_bx=nb[1], total_written=existing + total_rows_written),
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(
            "If this is an Earth Engine registration/project issue, see the one-time steps in setup-gcp.sh.",
            file=sys.stderr,
        )
        raise

