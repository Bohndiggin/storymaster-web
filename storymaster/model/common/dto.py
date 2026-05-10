"""Lightweight DTO dataclasses returned by `BaseModelClient`.

These mirror the attribute access patterns the Litographer/Lorekeeper
controllers rely on (`node.x_position`, `node.node_type.value`, etc.) without
pulling in the SQLAlchemy ORM. The HTTP API returns JSON, and `_from_dict`
constructs the dataclass while coercing Enum-shaped strings into real Enum
members.

Goal: a controller written against a `BaseModel` that returns SQLAlchemy rows
should also work when wired to a `BaseModelClient` returning these dataclasses,
without ORM-specific code paths in the controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from typing import Any, ClassVar, Type, TypeVar

from storymaster.model.database.schema.base import (
    NodeType,
    NoteType,
    PlotSectionType,
)


T = TypeVar("T", bound="DTOBase")


@dataclass
class DTOBase:
    """Common audit fields. Subclasses define their own fields too."""

    sync_uuid: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    version: int | None = None

    # Per-subclass mapping: field-name -> Enum class for coercion on parse.
    _enum_fields: ClassVar[dict[str, type]] = {}

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """Build a dataclass instance from a JSON dict.

        Tolerant: extra keys are dropped, missing keys default to None.
        Enum-typed fields and ISO-8601 datetimes are coerced.
        """
        kwargs: dict[str, Any] = {}
        names = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key not in names:
                continue
            if key in cls._enum_fields and value is not None:
                value = cls._enum_fields[key](value)
            elif key in {"created_at", "updated_at", "deleted_at"} and isinstance(value, str):
                value = _parse_iso(value)
            kwargs[key] = value
        return cls(**kwargs)

    def as_dict(self) -> dict[str, Any]:
        """Mirror SQLAlchemy `BaseTable.as_dict()` so controller code that
        iterates `.as_dict().items()` doesn't care which backend it got."""
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, datetime):
                out[f.name] = value.isoformat()
            elif hasattr(value, "value"):  # Enum
                out[f.name] = value.value
            else:
                out[f.name] = value
        return out


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # Python 3.11 fromisoformat supports trailing 'Z' as of 3.11.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Concrete DTOs
# ---------------------------------------------------------------------------


@dataclass
class UserDTO(DTOBase):
    id: int | None = None
    username: str | None = None
    is_active: bool = True


@dataclass
class StorylineDTO(DTOBase):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    user_id: int | None = None


@dataclass
class SettingDTO(DTOBase):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    user_id: int | None = None


@dataclass
class LitographyNodeDTO(DTOBase):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    node_type: NodeType | None = None
    x_position: float = 0.0
    y_position: float = 0.0
    storyline_id: int | None = None

    _enum_fields = {"node_type": NodeType}


@dataclass
class NodeConnectionDTO(DTOBase):
    id: int | None = None
    output_node_id: int | None = None
    input_node_id: int | None = None


@dataclass
class LitographyNotesDTO(DTOBase):
    id: int | None = None
    title: str | None = None
    description: str | None = None
    note_type: NoteType | None = None
    linked_node_id: int | None = None
    storyline_id: int | None = None

    _enum_fields = {"note_type": NoteType}


@dataclass
class LitographyPlotDTO(DTOBase):
    id: int | None = None
    title: str | None = None
    description: str | None = None
    storyline_id: int | None = None


@dataclass
class LitographyPlotSectionDTO(DTOBase):
    id: int | None = None
    plot_section_type: PlotSectionType | None = None
    plot_id: int | None = None

    _enum_fields = {"plot_section_type": PlotSectionType}


@dataclass
class ArcTypeDTO(DTOBase):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    setting_id: int | None = None


@dataclass
class LitographyArcDTO(DTOBase):
    id: int | None = None
    title: str | None = None
    description: str | None = None
    arc_type_id: int | None = None
    storyline_id: int | None = None


@dataclass
class ArcPointDTO(DTOBase):
    id: int | None = None
    arc_id: int | None = None
    title: str | None = None
    order_index: int = 0
    description: str | None = None
    emotional_state: str | None = None
    character_relationships: str | None = None
    goals: str | None = None
    internal_conflict: str | None = None
    node_id: int | None = None
