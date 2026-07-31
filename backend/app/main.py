from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api.health import router as health_router
from app.core.config import Settings, get_settings

RESERVED_SERVER_PATHS = ("api", "health", "ready", "docs", "redoc", "openapi.json")


def _is_server_path(path: str) -> bool:
    first_segment = path.split("/", 1)[0]
    return first_segment in RESERVED_SERVER_PATHS


def _safe_static_candidate(dist_dir: Path, requested_path: str) -> Path | None:
    candidate = (dist_dir / requested_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None
    return candidate


def _register_frontend_routes(app: FastAPI, settings: Settings) -> None:
    dist_dir = settings.frontend_dist_dir.resolve()
    index_file = dist_dir / "index.html"

    @app.get("/", include_in_schema=False)
    async def frontend_root() -> FileResponse:
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Frontend build not found.")
        return FileResponse(index_file)

    @app.get("/{requested_path:path}", include_in_schema=False)
    async def frontend_fallback(requested_path: str) -> FileResponse:
        if _is_server_path(requested_path):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = _safe_static_candidate(dist_dir, requested_path)
        if candidate is not None and candidate.is_file():
            return FileResponse(candidate)

        if requested_path == "assets" or requested_path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Asset not found.")

        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Frontend build not found.")
        return FileResponse(index_file)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    public_docs = resolved_settings.app_env in {"local", "test"}

    app = FastAPI(
        title="IX Value Loop API",
        version=resolved_settings.app_version,
        docs_url="/docs" if public_docs else None,
        redoc_url="/redoc" if public_docs else None,
        openapi_url="/openapi.json" if public_docs else None,
    )
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: resolved_settings

    app.include_router(health_router)
    _register_frontend_routes(app, resolved_settings)
    return app


app = create_app()
