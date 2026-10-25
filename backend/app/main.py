import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.api.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.auth import router as auth_router
from app.config import settings
from app.learner_model.service import StaleTraitsError

log = logging.getLogger("pcg")


def check_production_settings() -> None:
    if settings.environment == "production" and (problems := settings.production_problems()):
        raise RuntimeError("unsafe production settings: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    check_production_settings()
    yield


production = settings.environment == "production"
app = FastAPI(
    title="PCG Engine",
    version=__version__,
    lifespan=lifespan,
    # the interactive docs are for development; the schema stays for the frontend's codegen
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
)

# middleware runs outermost-last: size and rate limits before anything touches the database
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth is a bearer header, never a cookie
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


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
        where = ".".join(str(p) for p in errors[0].get("loc", ())[1:])
        msg = f"{where}: {errors[0]['msg']}" if where else errors[0]["msg"]
    else:
        msg = "Invalid request payload"
    return _error(422, "VALIDATION_ERROR", msg)


@app.exception_handler(LookupError)
async def lookup_handler(_: Request, exc: LookupError) -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "The requested resource was not found")


@app.exception_handler(StaleTraitsError)
async def stale_handler(_: Request, exc: StaleTraitsError) -> JSONResponse:
    return _error(status.HTTP_409_CONFLICT, "CONFLICT", "Please retry: your profile was updating")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # never leak a stack trace or SQL to the client; the log keeps the details
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Something went wrong")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")
