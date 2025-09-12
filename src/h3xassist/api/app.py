"""FastAPI application for H3xAssist control plane."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from h3xassist.api.dependencies import (
    calendar_sync,
    postprocess_service,
    recording_manager,
    scheduler,
)
from h3xassist.api.routers import calendar, profiles, recordings, service, settings, websocket
from h3xassist.models.api import ErrorResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from fastapi import HTTPException, Response

logger = logging.getLogger(__name__)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to disable all caching."""

    async def dispatch(
        self, request: Request, call_next: "Callable[[Request], Awaitable[Response]]"
    ) -> "Response":
        response = await call_next(request)
        # Add headers to prevent caching
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Surrogate-Control"] = "no-store"
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> "AsyncGenerator[None, None]":
    """Application lifespan manager."""
    # Startup
    logger.info("Starting H3xAssist API server")

    # Cleanup orphaned audio sinks from previous sessions
    try:
        from h3xassist.audio.virtual import cleanup_orphaned_sinks

        removed = await cleanup_orphaned_sinks()
        if removed > 0:
            logger.info("Cleaned up %d orphaned audio sinks from previous session", removed)
    except Exception as e:
        logger.warning("Failed to cleanup orphaned audio sinks: %s", e)

    await calendar_sync.start()
    scheduler.start()
    recording_manager.start()
    postprocess_service.start()

    yield

    await calendar_sync.stop()
    await scheduler.stop()
    await recording_manager.stop()
    await postprocess_service.stop()

    # Shutdown
    logger.info("Shutting down H3xAssist API server")


app = FastAPI(
    title="H3xAssist API",
    description="Control plane for H3xAssist meeting recording and processing",
    version="0.1.0",
    lifespan=lifespan,
)

# Add no-cache middleware
app.add_middleware(NoCacheMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(recordings.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(service.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")

# Static files directory
STATIC_DIR = Path(__file__).parent.parent.parent.parent / "h3xassist-web" / "out"

# Mount static files if directory exists
if STATIC_DIR.exists():
    # Mount Next.js static assets
    if (STATIC_DIR / "_next").exists():
        app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next")

    # Mount other static files (favicon, PWA assets, etc)
    static_files = [
        "favicon.ico",
        "next.svg",
        "vercel.svg",
        "file.svg",
        "globe.svg",
        "window.svg",
        # PWA files
        "manifest.json",
        "icon.svg",
        "icon-192.png",
        "icon-512.png",
        "apple-touch-icon.png",
    ]

    for file in static_files:
        if (STATIC_DIR / file).exists():

            @app.get(f"/{file}", response_model=None, include_in_schema=False)
            async def serve_static_file(file: str = file) -> FileResponse:
                # Set proper content type for manifest
                if file == "manifest.json":
                    return FileResponse(STATIC_DIR / file, media_type="application/manifest+json")
                return FileResponse(STATIC_DIR / file)


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400, content=ErrorResponse(error=str(exc), code=400).model_dump()
    )


@app.exception_handler(404)
async def not_found_handler(_request: Request, _exc: "HTTPException") -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404, content=ErrorResponse(error="Not found", code=404).model_dump()
    )


# Health check
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "h3xassist-api"}


# Root path - serve index.html
@app.get("/", response_model=None, include_in_schema=False)
async def serve_root() -> FileResponse | JSONResponse:
    """Serve the main SPA page."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "error": "Web interface not built",
            "message": "Run 'cd h3xassist-web && pnpm build' to build the frontend",
        },
    )


# SPA routing - serve index.html for non-API routes
@app.get("/{full_path:path}", response_model=None, include_in_schema=False)
async def serve_spa(_request: Request, full_path: str) -> FileResponse | JSONResponse:
    """Serve SPA for non-API routes."""
    # API routes should be handled by routers
    if full_path.startswith("api/") or full_path.startswith("health"):
        # Let FastAPI handle 404 for actual API routes
        return JSONResponse(
            status_code=404, content=ErrorResponse(error="Not found", code=404).model_dump()
        )

    # Check for exact file match
    static_file = STATIC_DIR / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)

    # Check for directory with index.html (Next.js structure)
    dir_index = STATIC_DIR / full_path / "index.html"
    if dir_index.exists():
        return FileResponse(dir_index)

    # Check without trailing slash
    if full_path and not full_path.endswith("/"):
        dir_index_alt = STATIC_DIR / f"{full_path}/index.html"
        if dir_index_alt.exists():
            return FileResponse(dir_index_alt)

    # Default to root index.html for SPA routing
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    # If no static build exists, show helpful message
    return JSONResponse(
        status_code=503,
        content={
            "error": "Web interface not built",
            "message": "Run 'cd h3xassist-web && pnpm build' to build the frontend",
        },
    )
