from fastapi import FastAPI

from reindex_server import __version__

app = FastAPI(title="ReIndex API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}

