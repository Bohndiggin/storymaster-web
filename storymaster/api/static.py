"""Serve the production React bundle from `web/dist` under `/`.

In dev, the React app runs separately on :5173 with a proxy to the FastAPI
server, so this module is a no-op (it just returns False from
`mount_static_files` if the dist directory doesn't exist).

In production deploys we expect a build artifact at `web/dist/` next to the
project root.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


def _dist_dir() -> Path:
    # storymaster/api/static.py → repo root → web/dist
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def mount_static_files(app: FastAPI) -> bool:
    """Mount `web/dist` so the FastAPI app serves the SPA shell at `/`.

    Returns True if the dist directory was found and mounted; False otherwise
    (the dev workflow runs Vite separately, so the no-op path is the common
    case during development).
    """
    dist = _dist_dir()
    if not dist.is_dir():
        return False

    index_html = dist / "index.html"
    if not index_html.is_file():
        return False

    # Static assets (JS/CSS bundles, fonts, etc.) live under /assets/...
    # Anything else falls through to the SPA fallback below.
    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # API routes were registered earlier via include_router and take
        # precedence over this catch-all. Anything that lands here is a
        # client-side route — return index.html and let React Router handle it.
        if full_path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not found")
        target = dist / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(index_html)

    return True
