import os
import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Checkpoint:
    next_by: int
    next_bx: int
    total_written: int


class CheckpointStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        self.ensure_schema(conn)
        return conn

    def ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingest_checkpoints (
                job_id TEXT PRIMARY KEY,
                next_by INTEGER NOT NULL,
                next_bx INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                total_written INTEGER NOT NULL
            )
            """
        )
        conn.commit()

    def read(self, conn: sqlite3.Connection, job_id: str) -> Checkpoint:
        row = conn.execute(
            "SELECT next_by, next_bx, total_written FROM ingest_checkpoints WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return Checkpoint(next_by=0, next_bx=0, total_written=0)
        return Checkpoint(next_by=int(row[0]), next_bx=int(row[1]), total_written=int(row[2]))

    def write(self, conn: sqlite3.Connection, job_id: str, checkpoint: Checkpoint) -> None:
        now = int(time.time())
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO ingest_checkpoints (job_id, next_by, next_bx, updated_at, total_written)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    next_by=excluded.next_by,
                    next_bx=excluded.next_bx,
                    updated_at=excluded.updated_at,
                    total_written=excluded.total_written
                """,
                (
                    job_id,
                    int(checkpoint.next_by),
                    int(checkpoint.next_bx),
                    now,
                    int(checkpoint.total_written),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

