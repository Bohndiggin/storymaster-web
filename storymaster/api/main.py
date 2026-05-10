"""Uvicorn entry point. Replaces the old `start_sync_server.py`."""

import os

import uvicorn

from storymaster.sync_server.config import config


def main() -> None:
    host = os.getenv("STORYMASTER_HOST", config.HOST)
    port = int(os.getenv("STORYMASTER_PORT", str(config.PORT)))
    reload = os.getenv("STORYMASTER_RELOAD", "").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "storymaster.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
