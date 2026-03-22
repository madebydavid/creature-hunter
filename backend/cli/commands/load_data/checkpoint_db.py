from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db.models import EmbeddingIngestCheckpoint


@dataclass(frozen=True)
class Checkpoint:
    next_by: int
    next_bx: int
    total_written: int


def read_checkpoint(db: Session, job_id: str) -> Checkpoint:
    row = db.get(EmbeddingIngestCheckpoint, job_id)
    if row is None:
        return Checkpoint(next_by=0, next_bx=0, total_written=0)
    return Checkpoint(
        next_by=row.next_block_y,
        next_bx=row.next_block_x,
        total_written=int(row.total_written),
    )


def write_checkpoint(db: Session, job_id: str, checkpoint: Checkpoint) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    stmt = insert(EmbeddingIngestCheckpoint).values(
        job_id=job_id,
        next_block_y=checkpoint.next_by,
        next_block_x=checkpoint.next_bx,
        total_written=checkpoint.total_written,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmbeddingIngestCheckpoint.job_id],
        set_={
            "next_block_y": stmt.excluded.next_block_y,
            "next_block_x": stmt.excluded.next_block_x,
            "total_written": stmt.excluded.total_written,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    db.execute(stmt)
