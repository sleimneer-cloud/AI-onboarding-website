from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def _build_test_app(dist_dir: Path) -> FastAPI:
    settings = Settings(_env_file=None, app_env="test", frontend_dist_dir=dist_dir)
    return create_app(settings)


async def test_frontend_build_and_client_routes_are_served(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<h1>IX Value Loop</h1>", encoding="utf-8")
    (assets_dir / "app.css").write_text("body { color: #111; }", encoding="utf-8")

    transport = ASGITransport(app=_build_test_app(dist_dir))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/")).text == "<h1>IX Value Loop</h1>"
        assert (await client.get("/employee/dashboard")).text == "<h1>IX Value Loop</h1>"

        asset_response = await client.get("/assets/app.css")
        assert asset_response.status_code == 200
        assert "body { color: #111; }" in asset_response.text


async def test_spa_fallback_does_not_hide_server_or_asset_404s(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<h1>IX Value Loop</h1>", encoding="utf-8")

    transport = ASGITransport(app=_build_test_app(dist_dir))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/unknown")).status_code == 404
        assert (await client.get("/assets/missing.js")).status_code == 404
        assert (await client.post("/employee/dashboard")).status_code == 405


async def test_backend_starts_without_frontend_build(tmp_path: Path) -> None:
    transport = ASGITransport(app=_build_test_app(tmp_path / "missing-dist"))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/")).status_code == 404
