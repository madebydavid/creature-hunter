import os

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility


class MilvusSink:
    def __init__(self, *, collection_name: str, dim: int):
        self.collection_name = collection_name
        self.dim = dim
        self.collection: Collection | None = None

    def connect(self) -> None:
        host = os.environ.get("MILVUS_HOST", "localhost")
        port = os.environ.get("MILVUS_PORT", "19530")
        connections.connect(alias="default", host=host, port=port)

    def ensure_collection(self) -> Collection:
        name = self.collection_name
        if not utility.has_collection(name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="lat", dtype=DataType.FLOAT),
                FieldSchema(name="lon", dtype=DataType.FLOAT),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            ]
            schema = CollectionSchema(fields=fields, description="SEUK 10m annual embeddings")
            col = Collection(name=name, schema=schema)
            col.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "HNSW",
                    "metric_type": "IP",
                    "params": {"M": 16, "efConstruction": 200},
                },
            )
        else:
            col = Collection(name=name)
        col.load()
        self.collection = col
        return col

    def num_entities(self) -> int:
        if not self.collection:
            raise RuntimeError("Collection not initialized")
        return int(self.collection.num_entities)

    def upsert_batch(self, *, ids, lat, lon, vectors) -> None:
        if not self.collection:
            raise RuntimeError("Collection not initialized")
        self.collection.upsert([ids, lat, lon, vectors])

    def flush(self) -> None:
        if not self.collection:
            raise RuntimeError("Collection not initialized")
        self.collection.flush()

