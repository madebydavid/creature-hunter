import json
import os
from typing import Sequence

import ee
import xarray as xr


ANNUAL_EMBEDDING_COLLECTION = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "In this repo it should be set in the backend container automatically."
        )
    return value


def load_key_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def init_ee(*, key_file: str, service_account: str, project: str) -> None:
    credentials = ee.ServiceAccountCredentials(service_account, key_file)
    ee.Initialize(
        credentials=credentials,
        project=project,
        url="https://earthengine-highvolume.googleapis.com",
    )


def annual_date_window(year: int) -> tuple[str, str]:
    return (f"{year}-01-01", f"{year}-12-31")


def band_names(dim: int) -> list[str]:
    return [f"A{i:02d}" for i in range(dim)]


def build_annual_embedding_image(
    *,
    year: int,
    bbox_wgs84: tuple[float, float, float, float],
    bands: Sequence[str],
) -> ee.Image:
    aoi = ee.Geometry.Rectangle(bbox_wgs84, proj="EPSG:4326", geodesic=False)
    start_date, end_date = annual_date_window(year)
    return (
        ee.ImageCollection(ANNUAL_EMBEDDING_COLLECTION)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .select(list(bands))
        .mosaic()
        .clip(aoi)
    )


def open_xarray_dataset(
    *,
    image: ee.Image,
    bbox_wgs84: tuple[float, float, float, float],
    projection: str,
    scale_m: int,
    chunks: dict,
) -> xr.Dataset:
    try:
        from xee import EarthEngineBackendEntrypoint
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Failed to import xee EarthEngine backend. Verify `xee` is installed."
        ) from e

    proj = ee.Projection(projection).atScale(scale_m)

    # Force Earth Engine to serve pixels on the requested grid.
    image = image.reproject(proj)

    return xr.open_dataset(
        image,
        engine=EarthEngineBackendEntrypoint,
        projection=proj,
        geometry=bbox_wgs84,
        scale=scale_m,
        chunks=chunks,
    )
