"""Top-level FastAPI application.

Wires together:
- the auth router (login/logout/me with server-side sessions)
- the existing sync/pair routes from `storymaster.sync_server.main`

Phase-2 CRUD routers will be `include_router`'d here as they land.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storymaster.api.auth import router as auth_router
from storymaster.api.routers.arcs import router as arcs_router
from storymaster.api.routers.documents import router as documents_router
from storymaster.api.routers.litography import router as litography_router
from storymaster.api.routers.lorekeeper import router as lorekeeper_router
from storymaster.api.routers.notes import router as notes_router
from storymaster.api.routers.storylines import router as storylines_router
from storymaster.api.routers.storyweaver import router as storyweaver_router
from storymaster.api.static import mount_static_files
from storymaster.sync_server.config import config
from storymaster.sync_server.main import app as _sync_app


def create_app() -> FastAPI:
    app = FastAPI(
        title="Storymaster API",
        description="Unified API for Storymaster web, desktop, and mobile sync clients.",
        version="2.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(storylines_router)
    app.include_router(litography_router)
    app.include_router(lorekeeper_router)
    app.include_router(arcs_router)
    app.include_router(notes_router)
    app.include_router(storyweaver_router)
    app.include_router(documents_router)

    # Splice in the existing sync_server routes (/api/pair/*, /api/sync/*,
    # /api/devices/*). They keep their bearer-token auth via SyncDevice; the
    # device-owned-by-user FK is enforced at the device pairing layer in Phase 3.
    #
    # The sync server's bare `/` health check is rerouted to `/api/health`
    # so the SPA mount can own `/` in production. Mobile clients calling `/`
    # for connectivity should switch to `/api/health` (kept identical).
    for route in _sync_app.router.routes:
        path = getattr(route, "path", None)
        if path == "/":
            new_path = "/api/health"
            route.path = new_path
            if hasattr(route, "path_format"):
                route.path_format = new_path
            if hasattr(route, "path_regex"):
                from starlette.routing import compile_path

                pattern, fmt, conv = compile_path(new_path)
                route.path_regex = pattern
                route.path_format = fmt
                route.param_convertors = conv
        app.router.routes.append(route)

    # SPA static-file mount comes last so the catch-all `/{path:path}` route
    # doesn't shadow API endpoints. No-op if `web/dist` doesn't exist (dev).
    mount_static_files(app)

    return app


def _cors_origins() -> list[str]:
    raw = os.getenv("STORYMASTER_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    # Cookies-with-credentials require an explicit origin list, so the wildcard
    # only makes sense for the existing token-authed sync clients. We keep the
    # legacy default for compatibility but recommend setting the env in deploy.
    return config.CORS_ORIGINS


app = create_app()
