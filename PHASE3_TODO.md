# Phase 3 — Status

**Done.** The desktop's call surface routes entirely through `BaseModel`,
every method the controller invokes has a working `BaseModelClient`
counterpart, and the parity contract test covers each refactored seam.

The desktop is now runnable end-to-end against the HTTP API:

```sh
# Terminal 1 — start the API server
python -m storymaster.api.main

# Terminal 2 — pair a device (mobile flow gives you a bearer token), then:
STORYMASTER_BACKEND=http \
STORYMASTER_API_URL=http://127.0.0.1:8765 \
STORYMASTER_API_TOKEN=<paired-device-token> \
python -m storymaster.main
```

`STORYMASTER_BACKEND=local` (the default) keeps the legacy direct-SQLite path
intact.

## Verification

```sh
# 0 expected.
grep -c 'with Session(self.model.engine)' \
    storymaster/controller/common/main_page_controller.py

# 121 expected — Python suite.
PYTHONPATH=. pytest tests/api/ tests/model/common/ -q
```

## Methods missing from `BaseModelClient` (not called by controller)

These exist on `BaseModel` but no `BaseModelClient` counterpart yet. The
controller doesn't call them directly today, so leaving the gap is safe.
They're worth filling in if/when they end up on a hot path.

```sh
PYTHONPATH=. python -c "
from storymaster.model.common.common_model import BaseModel
from storymaster.model.common.base_model_client import BaseModelClient
base = {m for m in dir(BaseModel) if not m.startswith('_')}
client = {m for m in dir(BaseModelClient) if not m.startswith('_')}
for name in sorted(base - client - {'as_dict', 'generate_connection'}):
    print(name)
"
```

Most of the gap is character-arc work (Phase 7 will cover this UI-side, and
the API endpoints already exist under `/api/v1/.../arcs`) and table-introspection
helpers the desktop uses for its dynamic Lorekeeper UI (`get_all_table_names`,
`get_column_types`, `get_foreign_key_info`) — the web frontend already gets
those via `GET /api/v1/lorekeeper/schema`.

## Latency consideration (still relevant)

`mouseReleaseEvent` for node drags fires once per release (verified). HTTP
PATCH per release is fine. If anything ever wires position saves to
`mouseMoveEvent` instead, the bulk-position endpoint
(`PATCH /api/v1/storylines/{id}/nodes/positions`) is already there to absorb
the burst.
