"""ASGI entry point: uvicorn app.main:app."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.services.lastfm import LastFMError, LastFMService

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
# HTTPX's INFO request logs include query parameters; suppress credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_app(service=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.lastfm = service if service is not None else LastFMService(os.getenv("LASTFM_API_KEY"))
        yield
        await app.state.lastfm.close()

    app = FastAPI(title="TONESCAPE", version="1.0.0", lifespan=lifespan, debug=False)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https://lastfm.freetls.fastly.net https://lastfm-img2.akamaized.net https://userserve-ak.last.fm; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'; form-action 'self'"
        return response

    @app.exception_handler(LastFMError)
    async def lastfm_error(request, exc):
        headers = {"Retry-After": "30"} if exc.status == 429 else None
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse({"error": {"code": "invalid_input", "message": "Enter a song or artist name within the allowed length (search: 200, artist: 200, track: 300 characters)."}}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        # Do not log exception text or request URLs: upstream failures may carry keys.
        logging.getLogger(__name__).error("Unhandled application error: %s", type(exc).__name__)
        return JSONResponse({"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}}, status_code=500)

    @app.get("/", include_in_schema=False)
    async def landing():
        return FileResponse(ROOT / "templates" / "index.html")

    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "lastfm_configured": bool(request.app.state.lastfm.api_key)}

    @app.get("/api/search")
    async def search(request: Request, q: Annotated[str, Query(min_length=1, max_length=200)], mode: Literal["track", "artist"] = "track"):
        query = clean(q)
        tracks = await request.app.state.lastfm.search(query, mode)
        return {"query": query, "mode": mode, "tracks": tracks}

    @app.get("/api/analyze")
    async def analyze(request: Request, artist: Annotated[str, Query(min_length=1, max_length=200)], track: Annotated[str, Query(min_length=1, max_length=300)]):
        return await request.app.state.lastfm.analyze(clean(artist), clean(track))

    return app


def clean(value):
    value = value.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise LastFMError("invalid_input", "Please enter a non-empty song or artist name without control characters.", 422)
    return value


app = create_app()
