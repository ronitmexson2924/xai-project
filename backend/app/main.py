import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__, xai
from app.api import api_router
from app.api.errors import UNPROCESSABLE
from app.api.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.auth import router as auth_router
from app.config import check_production_settings, settings
from app.db.session import SessionLocal

logger = logging.getLogger("pcg")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.environment == "production" and (problems := check_production_settings(settings)):
        raise RuntimeError("unsafe production settings: " + "; ".join(problems))
    if settings.environment != "test":
        # import and exercise the explainers in the background, so the first report is not slow
        threading.Thread(target=xai.warm_up, name="xai-warm-up", daemon=True).start()
    yield


app = FastAPI(
    title="PCG Engine",
    version=__version__,
    lifespan=lifespan,
    # the interactive docs are for development; production serves only the API
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
)

# the last one added runs first: body limit, CORS and rate limit sit inside the security headers,
# so their own responses (413, 429) carry the headers too
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # bearer tokens, not cookies
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if errors:
        where = ".".join(str(p) for p in errors[0].get("loc", ()) if p != "body")
        msg = f"{where}: {errors[0]['msg']}" if where else errors[0]["msg"]
    else:
        msg = "Invalid request payload"
    return JSONResponse(
        status_code=UNPROCESSABLE,
        content={"error": {"code": "VALIDATION_ERROR", "message": msg}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a stack trace or SQL to the client; log it on the server."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong"}},
    )


def _status(status_word: str) -> dict[str, str]:
    """A health answer; the version only outside production, where it helps attackers more than
    operators."""
    if settings.environment == "production":
        return {"status": status_word}
    return {"status": status_word, "version": __version__}


@app.get("/health")
def health() -> dict[str, str]:
    return _status("ok")


@app.get("/health/ready")
def ready() -> JSONResponse:
    """Readiness: the database answers."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database not reachable")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content=_status("ready"))


app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")
