from __future__ import annotations

from fastapi import FastAPI


app = FastAPI(title="Creature Hunter")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Optional API: re-enable observation reads ---
# You said you are not ingesting via the FastAPI API for now, but if you want
# to temporarily re-enable `GET /observations/{uuid}` you can uncomment the
# block below.
#
# from fastapi import Depends, HTTPException
# from sqlalchemy.orm import Session
#
# from db.models import Occurrence, Taxon
# from db.schemas import ObservationResponse
# from db.session import get_db
# from db.serializers import serialize_observation
#
# @app.get("/observations/{uuid}", response_model=ObservationResponse)
# def get_observation(uuid: str, db: Session = Depends(get_db)) -> ObservationResponse:
#     occ = db.get(Occurrence, uuid)
#     if not occ:
#         raise HTTPException(status_code=404, detail="Observation not found")
#     taxon = db.get(Taxon, occ.taxon_species_guid)
#     return serialize_observation(occ, taxon)

