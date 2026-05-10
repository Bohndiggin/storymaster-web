"""HTTP-backed twin of `BaseModel`.

Same public surface, but each method goes over the wire instead of running a
SQLAlchemy session. Returns dataclass DTOs (`storymaster.model.common.dto`)
that the existing controller code can read via attribute access without
caring whether the backend is local or remote.

Authentication is whatever the injected `transport` is set up with — a
session cookie (set by a prior login) or a bearer token. The class itself
doesn't manage auth; that's the entry point's job (`storymaster/main.py`).

Not implemented yet:
- Methods that require admin privileges (create_user, delete_user) — those
  go through the CLI, not the running app.
- Tables outside the canonical Lorekeeper / Litographer / Storyline surface;
  callers get a clear NotImplementedError instead of a silent miss.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Protocol, runtime_checkable

from storymaster.model.common.dto import (
    ArcPointDTO,
    ArcTypeDTO,
    DTOBase,
    LitographyArcDTO,
    LitographyNodeDTO,
    LitographyNotesDTO,
    LitographyPlotDTO,
    LitographyPlotSectionDTO,
    NodeConnectionDTO,
    SettingDTO,
    StorylineDTO,
    UserDTO,
)
from storymaster.model.database.schema.base import (
    NodeType,
    NoteType,
    PlotSectionType,
)


# Tables we route through the generic Lorekeeper entity endpoint. Mirrors
# `LOREKEEPER_TABLES` in storymaster.api.routers.lorekeeper.
_LOREKEEPER_TABLES: frozenset[str] = frozenset(
    {
        "class",
        "background",
        "race",
        "sub_race",
        "alignment",
        "stat",
        "actor",
        "actor_a_on_b_relations",
        "actor_to_race",
        "actor_to_class",
        "actor_to_stat",
        "actor_to_skills",
        "skills",
        "faction",
        "faction_a_on_b_relations",
        "faction_members",
        "location_",
        "location_to_faction",
        "location_dungeon",
        "location_city",
        "location_city_districts",
        "residents",
        "location_flora_fauna",
        "location_a_on_b_relations",
        "location_geographic_relations",
        "location_political_relations",
        "location_economic_relations",
        "location_hierarchy",
        "history",
        "history_actor",
        "history_location",
        "history_faction",
        "history_object",
        "history_world_data",
        "object_",
        "object_to_owner",
        "world_data",
    }
)


@runtime_checkable
class _Response(Protocol):
    status_code: int

    def json(self) -> Any: ...

    def raise_for_status(self) -> Any: ...


@runtime_checkable
class _Transport(Protocol):
    """Minimal HTTP client surface. Both `requests.Session` and
    `fastapi.testclient.TestClient` implement this."""

    def get(self, url: str, **kwargs: Any) -> _Response: ...
    def post(self, url: str, **kwargs: Any) -> _Response: ...
    def patch(self, url: str, **kwargs: Any) -> _Response: ...
    def delete(self, url: str, **kwargs: Any) -> _Response: ...


class BaseModelClient:
    """HTTP twin of BaseModel. See module docstring."""

    # Server-managed columns we strip from write payloads regardless of caller.
    _SERVER_FIELDS: frozenset[str] = frozenset(
        {"id", "created_at", "updated_at", "deleted_at", "version", "sync_uuid"}
    )

    def __init__(self, user_id: int, transport: _Transport) -> None:
        self.user_id = user_id
        self._http = transport
        # Compatibility shim: the controller occasionally reads
        # `self.model.current_setting_id`. Mirror BaseModel's behavior.
        self.current_setting_id: int | None = None

    # ------------------------------------------------------------------
    # Connection / sanity
    # ------------------------------------------------------------------

    @property
    def engine(self) -> Any:
        raise RuntimeError(
            "BaseModelClient has no SQLAlchemy engine. "
            "Refactor the caller to use a BaseModel method instead of "
            "Session(self.model.engine)."
        )

    # ------------------------------------------------------------------
    # Storyline / Setting
    # ------------------------------------------------------------------

    def get_all_storylines(self) -> list[StorylineDTO]:
        return [StorylineDTO.from_dict(r) for r in self._get_json("/api/v1/storylines")]

    def get_all_settings(self) -> list[SettingDTO]:
        return [SettingDTO.from_dict(r) for r in self._get_json("/api/v1/settings")]

    def get_storyline_by_id(self, storyline_id: int) -> StorylineDTO | None:
        return self._maybe_dto(
            StorylineDTO, f"/api/v1/storylines/{storyline_id}"
        )

    def get_setting_by_id(self, setting_id: int) -> SettingDTO | None:
        return self._maybe_dto(SettingDTO, f"/api/v1/settings/{setting_id}")

    def update_storyline(
        self, storyline_id: int, name: str | None = None, description: str | None = None
    ) -> bool:
        payload = _drop_none({"name": name, "description": description})
        r = self._http.patch(f"/api/v1/storylines/{storyline_id}", json=payload)
        return 200 <= r.status_code < 300

    def update_setting(
        self, setting_id: int, name: str | None = None, description: str | None = None
    ) -> bool:
        payload = _drop_none({"name": name, "description": description})
        r = self._http.patch(f"/api/v1/settings/{setting_id}", json=payload)
        return 200 <= r.status_code < 300

    def delete_storyline(self, storyline_id: int) -> bool:
        r = self._http.delete(f"/api/v1/storylines/{storyline_id}")
        return r.status_code == 204

    def delete_setting(self, setting_id: int) -> bool:
        r = self._http.delete(f"/api/v1/settings/{setting_id}")
        return r.status_code == 204

    def get_settings_for_storyline(self, storyline_id: int) -> list[SettingDTO]:
        return [
            SettingDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/storylines/{storyline_id}/settings")
        ]

    def link_storyline_to_setting(self, storyline_id: int, setting_id: int) -> bool:
        r = self._http.post(
            f"/api/v1/storylines/{storyline_id}/settings",
            json={"setting_id": setting_id},
        )
        return r.status_code == 204

    def unlink_storyline_from_setting(
        self, storyline_id: int, setting_id: int
    ) -> bool:
        r = self._http.delete(
            f"/api/v1/storylines/{storyline_id}/settings/{setting_id}"
        )
        return r.status_code == 204

    # ------------------------------------------------------------------
    # Litographer
    # ------------------------------------------------------------------

    def get_litography_nodes(self, storyline_id: int) -> list[LitographyNodeDTO]:
        return self.get_nodes_for_storyline(storyline_id)

    def get_nodes_for_storyline(self, storyline_id: int) -> list[LitographyNodeDTO]:
        return [
            LitographyNodeDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/storylines/{storyline_id}/nodes")
        ]

    def get_node_connections(self, storyline_id: int) -> list[NodeConnectionDTO]:
        return [
            NodeConnectionDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/storylines/{storyline_id}/connections")
        ]

    def create_node_connection(
        self, output_node_id: int, input_node_id: int
    ) -> NodeConnectionDTO:
        # The HTTP endpoint requires the storyline ID in the path; look it up
        # via the output node so callers can stay node-only (matches BaseModel).
        node = self._fetch_node(output_node_id)
        r = self._http.post(
            f"/api/v1/storylines/{node.storyline_id}/connections",
            json={"output_node_id": output_node_id, "input_node_id": input_node_id},
        )
        if r.status_code == 201:
            return NodeConnectionDTO.from_dict(r.json())
        # Idempotency: if the connection already existed (server returns 422
        # on dup constraints in some cases), look it up.
        existing = next(
            (
                c
                for c in self.get_node_connections(node.storyline_id)
                if c.output_node_id == output_node_id and c.input_node_id == input_node_id
            ),
            None,
        )
        if existing is not None:
            return existing
        r.raise_for_status()
        # Should be unreachable.
        raise RuntimeError(f"create_node_connection failed: {r.status_code}")

    def delete_node_connection(self, connection_id: int) -> bool:
        r = self._http.delete(f"/api/v1/connections/{connection_id}")
        return r.status_code == 204

    def get_input_connections_for_node(
        self, node_id: int
    ) -> list[NodeConnectionDTO]:
        data = self._get_json(f"/api/v1/nodes/{node_id}/connections")
        return [NodeConnectionDTO.from_dict(c) for c in data.get("input", [])]

    def get_output_connections_for_node(
        self, node_id: int
    ) -> list[NodeConnectionDTO]:
        data = self._get_json(f"/api/v1/nodes/{node_id}/connections")
        return [NodeConnectionDTO.from_dict(c) for c in data.get("output", [])]

    # ------------------------------------------------------------------
    # Plots & sections (Phase 3a parity surface)
    # ------------------------------------------------------------------

    def get_plots_for_storyline(self, storyline_id: int) -> list[LitographyPlotDTO]:
        return [
            LitographyPlotDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/storylines/{storyline_id}/plots")
        ]

    def get_plot(self, plot_id: int) -> LitographyPlotDTO | None:
        return self._maybe_dto(LitographyPlotDTO, f"/api/v1/plots/{plot_id}")

    def create_plot(
        self, storyline_id: int, title: str, description: str | None = None
    ) -> LitographyPlotDTO:
        r = self._http.post(
            f"/api/v1/storylines/{storyline_id}/plots",
            json={"title": title, "description": description},
        )
        r.raise_for_status()
        return LitographyPlotDTO.from_dict(r.json())

    def delete_plot_cascade(self, plot_id: int) -> bool:
        # The HTTP DELETE relies on the server cascading via SQLAlchemy
        # relationships. For now the API simply deletes the plot row; the
        # ORM-level cascade rules don't include nodes-only-in-this-plot the
        # way `BaseModel.delete_plot_cascade` does. Document the divergence
        # so callers don't expect identical behavior across backends.
        r = self._http.delete(f"/api/v1/plots/{plot_id}")
        return r.status_code == 204

    def get_plot_sections(self, plot_id: int) -> list[LitographyPlotSectionDTO]:
        return [
            LitographyPlotSectionDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/plots/{plot_id}/sections")
        ]

    def get_plot_section(
        self, section_id: int
    ) -> LitographyPlotSectionDTO | None:
        return self._maybe_dto(
            LitographyPlotSectionDTO, f"/api/v1/plot-sections/{section_id}"
        )

    def create_plot_section(
        self,
        plot_id: int,
        section_type: PlotSectionType = PlotSectionType.FLAT,
    ) -> LitographyPlotSectionDTO:
        value = section_type.value if isinstance(section_type, PlotSectionType) else section_type
        r = self._http.post(
            f"/api/v1/plots/{plot_id}/sections",
            json={"plot_section_type": value},
        )
        r.raise_for_status()
        return LitographyPlotSectionDTO.from_dict(r.json())

    def update_plot_section_type(
        self, section_id: int, section_type: PlotSectionType
    ) -> bool:
        value = section_type.value if isinstance(section_type, PlotSectionType) else section_type
        r = self._http.patch(
            f"/api/v1/plot-sections/{section_id}",
            json={"plot_section_type": value},
        )
        return 200 <= r.status_code < 300

    def delete_plot_section(self, section_id: int) -> bool:
        r = self._http.delete(f"/api/v1/plot-sections/{section_id}")
        return r.status_code == 204

    def get_nodes_in_plot_section(
        self, section_id: int, storyline_id: int  # noqa: ARG002 - kept for parity
    ) -> list[LitographyNodeDTO]:
        # Server already scopes by the section's owning plot's storyline; the
        # `storyline_id` arg is accepted for BaseModel-signature parity.
        return [
            LitographyNodeDTO.from_dict(r)
            for r in self._get_json(f"/api/v1/plot-sections/{section_id}/nodes")
        ]

    def add_node_to_plot_section(self, node_id: int, section_id: int) -> bool:
        r = self._http.post(
            f"/api/v1/plot-sections/{section_id}/nodes",
            json={"node_id": node_id, "plot_section_id": section_id},
        )
        return r.status_code == 201

    def move_node_to_plot_section(
        self, node_id: int, new_section_id: int
    ) -> None:
        r = self._http.patch(
            f"/api/v1/nodes/{node_id}/section",  # PUT method
            json={"node_id": node_id, "plot_section_id": new_section_id},
        ) if False else self._http_put(
            f"/api/v1/nodes/{node_id}/section",
            {"node_id": node_id, "plot_section_id": new_section_id},
        )
        if not (200 <= r.status_code < 300):
            r.raise_for_status()

    def get_section_for_node(self, node_id: int):
        """First section link for a node, or None. Mirrors BaseModel —
        returns an object with `.litography_plot_section_id` attribute."""
        rows = self._get_json(f"/api/v1/nodes/{node_id}/sections")
        if not rows:
            return None
        # Use a tiny DTO-like object so attribute access works at the call site.
        first = rows[0]

        class _Link:
            litography_plot_section_id = first.get("litography_plot_section_id")
            node_id = first.get("node_id")
            id = first.get("id")

        return _Link()

    # ------------------------------------------------------------------
    # Notes (Phase 3b)
    # ------------------------------------------------------------------

    def get_notes_for_node(
        self, node_id: int, storyline_id: int
    ) -> list[LitographyNotesDTO]:
        # The HTTP API returns ALL notes for a storyline; filter client-side
        # to match BaseModel.get_notes_for_node's per-node scope. The set is
        # small in practice — fixing this server-side is a Phase 6 cleanup.
        rows = self._get_json(f"/api/v1/storylines/{storyline_id}/notes")
        return [
            LitographyNotesDTO.from_dict(r)
            for r in rows
            if r.get("linked_node_id") == node_id
        ]

    def count_notes_for_node(self, node_id: int, storyline_id: int) -> int:
        return len(self.get_notes_for_node(node_id, storyline_id))

    def create_litography_note(
        self,
        node_id: int,
        title: str,
        description: str | None,
        note_type: NoteType | str,
        storyline_id: int,
    ) -> LitographyNotesDTO:
        value = note_type.value if isinstance(note_type, NoteType) else note_type
        r = self._http.post(
            f"/api/v1/storylines/{storyline_id}/notes",
            json={
                "title": title,
                "description": description,
                "note_type": value,
                "linked_node_id": node_id,
            },
        )
        r.raise_for_status()
        return LitographyNotesDTO.from_dict(r.json())

    def update_litography_note(
        self,
        note_id: int,
        storyline_id: int,  # noqa: ARG002 - kept for parity; the server does its own auth
        *,
        title: str | None = None,
        description: str | None = None,
        note_type: NoteType | str | None = None,
    ) -> bool:
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description
        if note_type is not None:
            body["note_type"] = note_type.value if isinstance(note_type, NoteType) else note_type
        r = self._http.patch(f"/api/v1/notes/{note_id}", json=body)
        return 200 <= r.status_code < 300

    def delete_litography_note(self, note_id: int, storyline_id: int) -> bool:  # noqa: ARG002
        r = self._http.delete(f"/api/v1/notes/{note_id}")
        return r.status_code == 204

    # ------------------------------------------------------------------
    # Note ↔ entity associations
    # ------------------------------------------------------------------

    def get_note_associations(self, note_id: int) -> dict[str, list]:
        return self._get_json(f"/api/v1/notes/{note_id}/associations")

    def create_note_association(
        self, note_id: int, entity_type: str, entity_id: int
    ) -> bool:
        r = self._http.post(
            f"/api/v1/notes/{note_id}/associations",
            json={"entity_type": entity_type, "entity_id": entity_id},
        )
        return r.status_code == 201

    def delete_note_association(
        self, note_id: int, entity_type: str, entity_id: int
    ) -> bool:
        r = self._http.delete(
            f"/api/v1/notes/{note_id}/associations/{entity_type}/{entity_id}"
        )
        return r.status_code == 204

    # ------------------------------------------------------------------
    # Lore aggregator + cascade delete
    # ------------------------------------------------------------------

    def get_lore_entities_for_setting(self, setting_id: int) -> dict[str, list]:
        """Single round trip — uses the existing `/entities` index endpoint.

        Returns the same dict keys (plurals) as BaseModel; values here are
        plain dicts (not ORM rows), but the controller call sites only ever
        iterate / read attributes via getattr, so DTO-style dicts work."""
        index = self._get_json(f"/api/v1/settings/{setting_id}/entities")
        plural_for: dict[str, str] = {
            "actor": "actors",
            "background": "backgrounds",
            "class": "classes",
            "faction": "factions",
            "history": "histories",
            "location_": "locations",
            "object_": "objects",
            "race": "races",
            "skills": "skills",
            "sub_race": "sub_races",
            "world_data": "world_data",
        }
        out: dict[str, list] = {v: [] for v in plural_for.values()}
        for entry in index:
            plural = plural_for.get(entry["entity_type"])
            if plural is None:
                continue
            out[plural].append(entry)
        return out

    def delete_node_with_associations(
        self, node_id: int, storyline_id: int  # noqa: ARG002 - server scopes via node ownership
    ) -> bool:
        # The DELETE endpoint on `/nodes/{id}` cascades via SQLAlchemy
        # relationships (notes have a FK with cascade behavior; connections
        # we delete explicitly). For BaseModelClient parity we accept a
        # trailing 204 as success.
        r = self._http.delete(f"/api/v1/nodes/{node_id}")
        return r.status_code == 204

    def get_node_in_storyline(
        self, node_id: int, storyline_id: int  # noqa: ARG002
    ) -> LitographyNodeDTO | None:
        return self._maybe_dto(LitographyNodeDTO, f"/api/v1/nodes/{node_id}")

    # ------------------------------------------------------------------
    # Storyline ↔ Setting derivation (Phase 3c)
    # ------------------------------------------------------------------

    def get_first_setting_id_for_storyline(
        self, storyline_id: int
    ) -> int | None:
        rows = self._get_json(f"/api/v1/storylines/{storyline_id}/settings")
        return rows[0]["id"] if rows else None

    def get_first_storyline_id_for_setting(
        self, setting_id: int
    ) -> int | None:
        # No dedicated endpoint; derive from the per-storyline link table by
        # listing the user's storylines and probing each. For "few storylines
        # per user" deployments this is fine; replace with a dedicated route
        # if listings ever exceed a few dozen.
        for storyline in self.get_all_storylines():
            sid = self.get_first_setting_id_for_storyline(int(storyline.id))  # type: ignore[arg-type]
            if sid == setting_id:
                return int(storyline.id)  # type: ignore[arg-type]
        return None

    # ------------------------------------------------------------------
    # Storyweaver entity dispatchers
    # ------------------------------------------------------------------

    def search_storyweaver_entities(
        self, setting_id: int, query: str | None = None
    ) -> list[dict]:
        path = f"/api/v1/settings/{setting_id}/storyweaver/entities"
        kwargs = {"params": {"q": query}} if query else {}
        r = self._http.get(path, **kwargs)
        r.raise_for_status()
        return r.json()

    def create_storyweaver_entity(
        self, entity_type: str, entity_name: str, setting_id: int
    ) -> str | None:
        r = self._http.post(
            f"/api/v1/settings/{setting_id}/storyweaver/entities",
            json={"entity_type": entity_type, "entity_name": entity_name},
        )
        if r.status_code == 422:
            return None
        r.raise_for_status()
        return r.json().get("id")

    def get_storyweaver_entity_details(
        self, entity_type: str, entity_id: int
    ) -> tuple[str, str] | None:
        r = self._http.get(
            f"/api/v1/storyweaver/entities/{entity_type}/{entity_id}/details"
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.json()
        return body["name"], body["details"]

    # `requests.Session` exposes .put; `TestClient` does too. We didn't add
    # `put` to the Transport protocol because nothing else uses it; stash a
    # helper that goes through whichever transport we got.
    def _http_put(self, path: str, body: Any):
        put = getattr(self._http, "put", None)
        if put is None:
            raise RuntimeError(
                "Transport does not support PUT — pass a requests.Session or TestClient."
            )
        return put(path, json=body)

    # ------------------------------------------------------------------
    # Generic table dispatchers (matches BaseModel's surface so the
    # controller's table-name-driven code paths Just Work).
    # ------------------------------------------------------------------

    def add_row(
        self,
        table_name: str,
        data_dict: dict[str, Any],
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ) -> dict[str, Any]:
        data = {k: v for k, v in data_dict.items() if k not in self._SERVER_FIELDS}

        if table_name == "storyline":
            r = self._http.post("/api/v1/storylines", json=_subset(data, {"name", "description"}))
            r.raise_for_status()
            return r.json()

        if table_name == "setting":
            r = self._http.post("/api/v1/settings", json=_subset(data, {"name", "description"}))
            r.raise_for_status()
            return r.json()

        if table_name == "storyline_to_setting":
            sid = int(data["storyline_id"])
            self.link_storyline_to_setting(sid, int(data["setting_id"]))
            return {"storyline_id": sid, "setting_id": int(data["setting_id"])}

        if table_name == "litography_node":
            sid = storyline_id or int(data.get("storyline_id"))
            payload = _subset(
                data, {"name", "description", "node_type", "x_position", "y_position"}
            )
            payload.setdefault("name", "Untitled Node")
            r = self._http.post(f"/api/v1/storylines/{sid}/nodes", json=payload)
            r.raise_for_status()
            return r.json()

        if table_name == "litography_plot":
            sid = storyline_id or int(data.get("storyline_id"))
            payload = _subset(data, {"title", "description"})
            r = self._http.post(f"/api/v1/storylines/{sid}/plots", json=payload)
            r.raise_for_status()
            return r.json()

        if table_name == "litography_notes":
            sid = storyline_id or int(data.get("storyline_id"))
            payload = _subset(data, {"title", "description", "note_type", "linked_node_id"})
            r = self._http.post(f"/api/v1/storylines/{sid}/notes", json=payload)
            r.raise_for_status()
            return r.json()

        if table_name in _LOREKEEPER_TABLES:
            sid = setting_id or self._derive_setting_id(storyline_id, data)
            r = self._http.post(
                f"/api/v1/settings/{sid}/entities/{table_name}", json=data
            )
            r.raise_for_status()
            return r.json()

        raise NotImplementedError(
            f"BaseModelClient.add_row: no HTTP route registered for table {table_name!r}. "
            "Either map it in base_model_client._LOREKEEPER_TABLES (if it has setting_id) "
            "or add a dedicated branch."
        )

    def update_row(self, table_name: str, data_dict: dict[str, Any]) -> dict[str, Any]:
        if "id" not in data_dict:
            raise ValueError("Data for update must include an 'id' field.")
        row_id = int(data_dict["id"])
        data = {
            k: v for k, v in data_dict.items() if k not in self._SERVER_FIELDS or k == "id"
        }
        del data["id"]

        if table_name == "storyline":
            r = self._http.patch(
                f"/api/v1/storylines/{row_id}", json=_subset(data, {"name", "description"})
            )
        elif table_name == "setting":
            r = self._http.patch(
                f"/api/v1/settings/{row_id}", json=_subset(data, {"name", "description"})
            )
        elif table_name == "litography_node":
            r = self._http.patch(
                f"/api/v1/nodes/{row_id}",
                json=_subset(
                    data,
                    {"name", "description", "node_type", "x_position", "y_position"},
                ),
            )
        elif table_name == "litography_notes":
            r = self._http.patch(
                f"/api/v1/notes/{row_id}",
                json=_subset(data, {"title", "description", "note_type", "linked_node_id"}),
            )
        elif table_name == "litography_plot":
            r = self._http.patch(
                f"/api/v1/plots/{row_id}",
                json=_subset(data, {"title", "description"}),
            )
        elif table_name in _LOREKEEPER_TABLES:
            sid = data.get("setting_id") or self.current_setting_id
            if sid is None:
                # Fall back: fetch the row to discover its setting_id, then PATCH.
                # Rare path; the server still owns the source of truth.
                raise ValueError(
                    f"update_row({table_name!r}): need setting_id either in data "
                    "or as current_setting_id on the client."
                )
            r = self._http.patch(
                f"/api/v1/settings/{int(sid)}/entities/{table_name}/{row_id}",
                json=data,
            )
        else:
            raise NotImplementedError(
                f"BaseModelClient.update_row: no HTTP route for {table_name!r}"
            )
        r.raise_for_status()
        return r.json() if r.status_code != 204 else {}

    def get_all_rows_as_dicts(
        self,
        table_name: str,
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if table_name == "storyline":
            return self._get_json("/api/v1/storylines")
        if table_name == "setting":
            return self._get_json("/api/v1/settings")
        if table_name == "litography_node":
            sid = storyline_id
            if sid is None:
                raise ValueError("litography_node listings require a storyline_id")
            return self._get_json(f"/api/v1/storylines/{sid}/nodes")
        if table_name in _LOREKEEPER_TABLES:
            sid = setting_id or self._derive_setting_id(storyline_id, {})
            return self._get_json(f"/api/v1/settings/{sid}/entities/{table_name}")
        raise NotImplementedError(
            f"BaseModelClient.get_all_rows_as_dicts: no HTTP route for {table_name!r}"
        )

    def get_row_by_id(self, table_name: str, row_id: int) -> dict[str, Any] | None:
        if table_name == "storyline":
            return self._maybe_json(f"/api/v1/storylines/{row_id}")
        if table_name == "setting":
            return self._maybe_json(f"/api/v1/settings/{row_id}")
        if table_name == "litography_node":
            return self._maybe_json(f"/api/v1/nodes/{row_id}")
        if table_name in _LOREKEEPER_TABLES:
            sid = self.current_setting_id
            if sid is None:
                raise ValueError(
                    "BaseModelClient.get_row_by_id needs current_setting_id set "
                    f"to look up a {table_name!r} row."
                )
            return self._maybe_json(
                f"/api/v1/settings/{sid}/entities/{table_name}/{row_id}"
            )
        raise NotImplementedError(
            f"BaseModelClient.get_row_by_id: no HTTP route for {table_name!r}"
        )

    # ------------------------------------------------------------------
    # User helpers (mostly read-only; mutation is via the admin CLI)
    # ------------------------------------------------------------------

    def get_current_user(self) -> UserDTO | None:
        return self._maybe_dto(UserDTO, "/api/auth/me")

    def get_user_by_id(self, user_id: int) -> UserDTO | None:
        # No public GET /users/{id} (admin-only territory). Fall back to /me
        # if it matches, else None — keeps backward compat for the controller.
        me = self.get_current_user()
        if me is not None and me.id == user_id:
            return me
        return None

    def switch_user(self, new_user_id: int) -> bool:
        if new_user_id == self.user_id:
            return True
        raise NotImplementedError(
            "BaseModelClient cannot switch users in-place; the desktop must "
            "re-authenticate with new credentials and rebuild the client."
        )

    def create_user(self, username: str) -> UserDTO:
        raise NotImplementedError(
            "Use `storymaster-create-admin` to create users; the running app "
            "does not have permission to do so."
        )

    def delete_user(self, user_id: int) -> None:
        raise NotImplementedError(
            "Use `storymaster-create-admin` (or the admin CLI) to delete users."
        )

    # ------------------------------------------------------------------
    # Schema introspection (best-effort over HTTP)
    # ------------------------------------------------------------------

    def get_table_class(self, table_name: str) -> Any:
        # Returning the SQLAlchemy class doesn't make sense for a remote
        # client. Callers that needed that should use the schema endpoint.
        raise NotImplementedError(
            "BaseModelClient.get_table_class returns ORM classes; the HTTP "
            "client doesn't have those. Use /api/v1/lorekeeper/schema instead."
        )

    def get_table_data(
        self,
        table_name: str,
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ) -> tuple[list[str], list[tuple]]:
        """Mirror BaseModel.get_table_data shape: (headers, rows-as-tuples)."""
        rows = self.get_all_rows_as_dicts(
            table_name, storyline_id=storyline_id, setting_id=setting_id
        )
        if not rows:
            return [], []
        headers = list(rows[0].keys())
        data = [tuple(row.get(h) for h in headers) for row in rows]
        return headers, data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_json(self, path: str) -> Any:
        r = self._http.get(path)
        r.raise_for_status()
        return r.json()

    def _maybe_json(self, path: str) -> dict[str, Any] | None:
        r = self._http.get(path)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def _maybe_dto(self, cls: type[DTOBase], path: str):
        data = self._maybe_json(path)
        return cls.from_dict(data) if data is not None else None

    def _fetch_node(self, node_id: int) -> LitographyNodeDTO:
        data = self._maybe_json(f"/api/v1/nodes/{node_id}")
        if data is None:
            raise LookupError(f"Node {node_id} not found or not accessible")
        return LitographyNodeDTO.from_dict(data)

    def _derive_setting_id(
        self, storyline_id: int | None, data: dict[str, Any]
    ) -> int:
        if "setting_id" in data and data["setting_id"]:
            return int(data["setting_id"])
        if self.current_setting_id is not None:
            return self.current_setting_id
        if storyline_id is not None:
            settings = self.get_settings_for_storyline(storyline_id)
            if settings:
                return int(settings[0].id)  # type: ignore[arg-type]
        raise ValueError(
            "No setting context available. Pass setting_id, set "
            "current_setting_id on the client, or pass a storyline_id with a "
            "linked setting."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _subset(d: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    keyset = set(keys)
    return {k: v for k, v in d.items() if k in keyset}
