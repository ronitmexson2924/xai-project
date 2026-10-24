from fastapi import FastAPI

from app import __version__

app = FastAPI(title="PCG Engine", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


# Mit (M1): include routers from app.api here, under the /api/v1 prefix.
