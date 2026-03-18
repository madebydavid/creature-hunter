from fastapi import FastAPI

app = FastAPI(title="Creature Hunter")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

