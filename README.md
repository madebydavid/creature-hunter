# Creature Hunter

Docker Compose stack with:
- Milvus (standalone) backed by etcd + MinIO
- A FastAPI backend container

## Prerequisites

- Docker + Docker Compose v2 (`docker compose ...`)

## Environment setup

Copy the example env file and adjust as needed:

```bash
cp .env.example .env
```

Generate your GCP service account key file by running:

```bash
./setup-gcp.sh
```

This should create `./key.json` (git-ignored). Docker Compose provides it to the backend as a file-based secret, and the backend sets `GOOGLE_APPLICATION_CREDENTIALS` to `/run/secrets/gcp-key.json`.

### `.env` variables (example)

The template lives in `.env.example`:

```env
# etcd
ETCD_AUTO_COMPACTION_MODE=revision
ETCD_AUTO_COMPACTION_RETENTION=1000
ETCD_QUOTA_BACKEND_BYTES=4294967296
ETCD_SNAPSHOT_COUNT=50000

# minio
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# postgres
POSTGRES_DB=creature_hunter
POSTGRES_USER=creature_hunter
POSTGRES_PASSWORD=change_me
```

## Build containers

```bash
docker compose build
```

## Start containers

```bash
docker compose up -d
```

## CLI (`python -m cli`)

Admin / data tasks use [Typer](https://typer.tiangolo.com/) from the backend container (working directory `/app`):

```bash
docker compose exec backend python -m cli --help
```

### AlphaEarth hello-world (`load-data`)

Once the stack is up, run the AlphaEarth embedding smoke test:

```bash
docker compose exec backend python -m cli load-data
```

**Checkpoints:** by default the SQLite checkpoint file is created next to the `load_data` command module (`checkpoints.sqlite`). For Docker bind mounts or a stable path, set **`CHECKPOINT_DB_PATH`** (e.g. `/data/checkpoints.sqlite`).

### NBN occurrences sample (`find-occurrences`)

Fetch a small sample of public NBN Atlas occurrences (no GCP required):

```bash
docker compose exec backend python -m cli find-occurrences
```

## Services

| Service | Purpose | Ports |
| --- | --- | --- |
| `etcd` | Milvus metadata store | (internal) |
| `minio` | S3-compatible object storage | `9000` (API), `9001` (console) |
| `milvus` | Vector database | `19530` (gRPC), `9091` (health) |
| `postgres` | Observations relational store | (internal) |
| `backend` | FastAPI app | `8000` |

## Database migrations (Alembic)

This repo stores observation records in Postgres using Alembic migrations.

1. Ensure your local env file exists (contains the Postgres credentials):

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up -d
```

3. Apply migrations (create the initial `taxon` + `occurrence` tables):

```bash
docker compose exec backend alembic upgrade head
```

To create a new migration after changing the ORM models:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

## Notes

- `.env` is git-ignored. Commit changes by editing `.env.example` only.
- Cursor ignore patterns for env files are stored in `.cursor/ignore` (the root `.cursorignore` filename was blocked by workspace permissions).
