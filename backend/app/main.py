"""Solace AI backend — FastAPI app serving the API and the static frontend."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import auth, queries

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Solace AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "solace", "version": app.version}


@app.get("/api/v1/config", tags=["meta"])
def public_config() -> dict:
    return {"allow_open_registration": settings.allow_open_registration}


# --- favicon (an inline "S" monogram) + no-content routes to silence browser icon 404s ---
_FAVICON = (
    b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    b"<rect width='32' height='32' rx='7' fill='#17456e'/>"
    b"<text x='16' y='23' font-family='Georgia,serif' font-size='20' fill='#f3efe3' "
    b"text-anchor='middle'>S</text></svg>"
)


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg() -> Response:
    return Response(_FAVICON, media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def _no_icon() -> Response:
    return Response(status_code=204)


# --- API routers (registered before the static mount so they take precedence) ---
app.include_router(auth.router)
app.include_router(queries.router)

# --- static frontend (single-page) mounted last as the catch-all ---
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
