# Creature Hunter (skeleton)

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
```

## Build containers

```bash
docker compose build
```

## Start containers

```bash
docker compose up -d
```

## Run AlphaEarth hello-world

Once the stack is up, run the AlphaEarth embedding smoke test inside the backend container:

```bash
docker compose exec backend python load_data.py
```

## Services

| Service | Purpose | Ports |
| --- | --- | --- |
| `etcd` | Milvus metadata store | (internal) |
| `minio` | S3-compatible object storage | `9000` (API), `9001` (console) |
| `milvus` | Vector database | `19530` (gRPC), `9091` (health) |
| `backend` | FastAPI app | `8000` |

## Notes

- `.env` is git-ignored. Commit changes by editing `.env.example` only.
- Cursor ignore patterns for env files are stored in `.cursor/ignore` (the root `.cursorignore` filename was blocked by workspace permissions).
