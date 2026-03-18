import json
import os
import sys

import ee
import xarray as xr


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "In this repo it should be set in the backend container automatically."
        )
    return value


def _load_key_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    key_file = _require_env("GOOGLE_APPLICATION_CREDENTIALS")
    key = _load_key_json(key_file)

    service_account = os.environ.get("SERVICE_ACCOUNT_EMAIL") or key.get("client_email")
    project = os.environ.get("GCP_PROJECT_ID") or key.get("project_id")

    if not service_account:
        raise RuntimeError("Could not determine service account email (client_email).")
    if not project:
        raise RuntimeError("Could not determine project id (project_id).")

    credentials = ee.ServiceAccountCredentials(service_account, key_file)
    ee.Initialize(
        credentials=credentials,
        project=project,
        url="https://earthengine-highvolume.googleapis.com",
    )

    print(f"EE initialized. service_account={service_account} project={project}")

    # Hard-coded tiny bbox AOI (lon/lat). Small area keeps the hello-world quick.
    aoi = ee.Geometry.Polygon(
        [
            [
                [-122.50, 37.70],
                [-122.50, 37.80],
                [-122.35, 37.80],
                [-122.35, 37.70],
                [-122.50, 37.70],
            ]
        ],
        proj="EPSG:4326",
        geodesic=False,
    )

    im = (
        ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
        .filterDate("2023-12-30", "2024-01-02")
        .filterBounds(aoi)
        .select([f"A{i:02d}" for i in range(64)])
        .mosaic()
        .clip(aoi)
    )

    try:
        from xee import EarthEngineBackendEntrypoint
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Failed to import xee EarthEngine backend. "
            "Verify `xee` is installed in the backend container."
        ) from e

    geometry_coords = aoi.bounds().getInfo()["coordinates"]

    ds = xr.open_dataset(
        im,
        engine=EarthEngineBackendEntrypoint,
        projection=ee.Projection("EPSG:32610"),
        geometry=geometry_coords,
        scale=100,
        chunks={"time": 1, "X": 512, "Y": 512},
    )

    print("Opened xarray dataset:")
    print(f"  dims={dict(ds.dims)}")
    print(f"  data_vars={list(ds.data_vars)}")
    print(f"  coords={list(ds.coords)}")

    # Force a small read to confirm data access.
    sample = ds.to_array().isel(X=0, Y=0).values
    print(f"Sample values at (X=0,Y=0): shape={getattr(sample, 'shape', None)}")
    print(sample)

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

