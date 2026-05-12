"""World-building lore-package import.

JSON files in `world_building_packages/` (project root) describe content packs
that get imported into a target Setting. Each row is rewritten:

- `setting_id` is replaced with the target setting.
- `id` is regenerated to avoid clashes with existing rows.
- Foreign keys (`race_id`, `parent_race_id`, `class_id`, ...) are remapped
  through the per-table `original_id -> new_id` mapping so inter-row
  references in the package stay correct.
- Duplicates (same `name` + `setting_id`) are skipped.

Tables are imported in dependency order so a parent row exists by the time a
child row references it via FK.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from storymaster.model.common.common_model import BaseModel


# ---------------------------------------------------------------------------
# Package directory discovery
# ---------------------------------------------------------------------------

PACKAGES_ENV = "STORYMASTER_LORE_PACKAGES_DIR"


def get_packages_dir() -> Optional[Path]:
    """Resolve the world_building_packages directory.

    Order:
    1. `STORYMASTER_LORE_PACKAGES_DIR` env (deploy override).
    2. Repo-root `world_building_packages/` (dev + Docker image).
    3. CWD/world_building_packages (fallback).
    """
    override = os.getenv(PACKAGES_ENV)
    if override:
        p = Path(override)
        if p.is_dir():
            return p

    # storymaster/api/lore_packages.py -> .../storymaster-web/
    repo_root = Path(__file__).resolve().parents[2]
    candidate = repo_root / "world_building_packages"
    if candidate.is_dir():
        return candidate

    cwd = Path.cwd() / "world_building_packages"
    if cwd.is_dir():
        return cwd

    return None


# ---------------------------------------------------------------------------
# Tables we permit imports into. Matches lorekeeper's allowlist plus arc_type
# (arc types live alongside the world-building tables in the JSON packs).
# ---------------------------------------------------------------------------

IMPORTABLE_TABLES: frozenset[str] = frozenset(
    {
        "alignment",
        "background",
        "class",
        "race",
        "sub_race",
        "stat",
        "skills",
        "actor",
        "actor_a_on_b_relations",
        "actor_to_skills",
        "actor_to_race",
        "actor_to_class",
        "actor_to_stat",
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
        "arc_type",
    }
)

# Order matters — parents before children so FK remapping has the new IDs ready.
TABLE_ORDER: tuple[str, ...] = (
    "alignment",
    "background",
    "class",
    "race",
    "sub_race",
    "stat",
    "skills",
    "actor",
    "faction",
    "location_",
    "history",
    "object_",
    "world_data",
    "arc_type",
    "actor_a_on_b_relations",
    "actor_to_skills",
    "actor_to_race",
    "actor_to_class",
    "actor_to_stat",
    "faction_a_on_b_relations",
    "faction_members",
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
    "history_actor",
    "history_location",
    "history_faction",
    "history_object",
    "history_world_data",
    "object_to_owner",
)

# FK column → referenced table (resolved against id_mapping at import time).
FK_PATTERNS: dict[str, str] = {
    "actor_id": "actor",
    "faction_id": "faction",
    "location_id": "location_",
    "race_id": "race",
    "sub_race_id": "sub_race",
    "parent_race_id": "race",
    "class_id": "class",
    "skill_id": "skills",
    "stat_id": "stat",
    "background_id": "background",
    "alignment_id": "alignment",
    "history_id": "history",
    "object_id": "object_",
    "world_data_id": "world_data",
    "arc_type_id": "arc_type",
    # Self-referential junctions: actor↔actor, faction↔faction, location↔location.
    "actor_a_id": "actor",
    "actor_b_id": "actor",
    "faction_a_id": "faction",
    "faction_b_id": "faction",
    "location_a_id": "location_",
    "location_b_id": "location_",
    "parent_location_id": "location_",
    "child_location_id": "location_",
    "district_id": "location_",
}


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageMeta:
    """Metadata + on-disk pointer for a discoverable package."""

    slug: str  # filename minus `.json`
    display_name: str
    description: str
    category: str
    version: str
    path: Path


@dataclass(frozen=True)
class ImportResult:
    """Per-import counts. `imported_by_table` only includes non-zero buckets."""

    package_slug: str
    imported: int
    skipped_duplicates: int
    imported_by_table: dict[str, int]


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def list_packages() -> list[PackageMeta]:
    packages_dir = get_packages_dir()
    if packages_dir is None:
        return []
    out: list[PackageMeta] = []
    for entry in sorted(packages_dir.iterdir()):
        if entry.suffix != ".json" or not entry.is_file():
            continue
        meta = _read_package_meta(entry)
        if meta is not None:
            out.append(meta)
    return out


def _read_package_meta(path: Path) -> Optional[PackageMeta]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    info = data.get("_package_info") or {}
    slug = path.stem
    return PackageMeta(
        slug=slug,
        display_name=info.get("display_name") or slug.replace("_", " ").title(),
        description=info.get("description") or "",
        category=info.get("category") or "General",
        version=info.get("version") or "1.0",
        path=path,
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def import_package(db: Session, slug: str, target_setting_id: int) -> ImportResult:
    """Import the bundled package identified by `slug` into `target_setting_id`.

    The caller owns the session — we add rows and flush, but commit is the
    caller's responsibility (so the FastAPI handler's transaction stays in
    charge). On any error mid-import the caller should `rollback()`.
    """
    packages_dir = get_packages_dir()
    if packages_dir is None:
        raise FileNotFoundError("world_building_packages directory not found")

    safe_slug = _sanitize_slug(slug)
    if safe_slug != slug:
        raise ValueError(f"Invalid package slug: {slug!r}")

    path = packages_dir / f"{safe_slug}.json"
    if not path.is_file() or path.parent != packages_dir:
        raise FileNotFoundError(f"Package not found: {slug}")

    with path.open("r", encoding="utf-8") as f:
        package_data = json.load(f)

    return import_package_data(db, package_data, target_setting_id, slug=safe_slug)


def import_package_data(
    db: Session,
    package_data: Any,
    target_setting_id: int,
    *,
    slug: str = "uploaded",
) -> ImportResult:
    """Import an in-memory package dict (e.g. from a user upload).

    Same transactional contract as :func:`import_package`: rows are added and
    flushed but not committed — the caller decides whether to commit or roll
    back so a bad row near the end doesn't half-apply.
    """
    if not isinstance(package_data, dict):
        raise ValueError("Package JSON must be an object keyed by table name")

    id_mapping: dict[str, dict[int, int]] = {}
    counts: dict[str, int] = {}
    skipped = 0

    seen: set[str] = set()
    # Process tables in dependency order, then catch any leftover tables.
    sequence: list[str] = list(TABLE_ORDER)
    for k in package_data:
        if k.startswith("_") or k in seen or k in TABLE_ORDER:
            continue
        sequence.append(k)
        seen.add(k)

    for table_name in sequence:
        rows = package_data.get(table_name)
        if not isinstance(rows, list) or not rows:
            continue
        if table_name not in IMPORTABLE_TABLES:
            continue
        cls = BaseModel._table_to_class_map.get(table_name)
        if cls is None:
            continue
        imported, dup = _import_rows(db, cls, table_name, rows, target_setting_id, id_mapping)
        if imported:
            counts[table_name] = imported
        skipped += dup

    db.flush()

    return ImportResult(
        package_slug=slug,
        imported=sum(counts.values()),
        skipped_duplicates=skipped,
        imported_by_table=counts,
    )


def _import_rows(
    db: Session,
    cls: Any,
    table_name: str,
    rows: list[dict[str, Any]],
    target_setting_id: int,
    id_mapping: dict[str, dict[int, int]],
) -> tuple[int, int]:
    columns = {c.name for c in cls.__table__.columns}
    has_setting = "setting_id" in columns
    has_name = "name" in columns

    table_map = id_mapping.setdefault(table_name, {})
    imported = 0
    skipped = 0

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        # Skip rows that are entirely empty/sentinel — these litter some packs.
        if not any(
            v not in ("", 0, 1, 0.0, 1.0, False, True, None) for v in raw.values()
        ):
            continue

        row = dict(raw)
        original_id = row.pop("id", None)

        if has_setting:
            row["setting_id"] = target_setting_id

        # Remap any FK fields the package brought along.
        for fk_col, ref_table in FK_PATTERNS.items():
            if fk_col in row and row[fk_col] is not None:
                ref_map = id_mapping.get(ref_table)
                if ref_map and row[fk_col] in ref_map:
                    row[fk_col] = ref_map[row[fk_col]]
                elif fk_col not in columns:
                    # FK doesn't exist on this table — drop it instead of
                    # raising so older/wider packages still import partially.
                    row.pop(fk_col)

        # Drop any fields the model doesn't know about (server-managed +
        # package-only metadata both fall out here).
        row = {k: v for k, v in row.items() if k in columns}

        # Empty strings → NULL for nullable string columns.
        for k, v in list(row.items()):
            if v == "":
                row[k] = None

        # Duplicate by name within the target setting.
        if has_name and has_setting and row.get("name"):
            existing = (
                db.query(cls)
                .filter(cls.name == row["name"], cls.setting_id == target_setting_id)
                .first()
            )
            if existing is not None:
                skipped += 1
                if original_id is not None:
                    table_map[original_id] = existing.id
                continue

        instance = cls(**row)
        db.add(instance)
        db.flush()  # populate `id` for downstream FK remapping
        if original_id is not None:
            table_map[original_id] = instance.id
        imported += 1

    return imported, skipped


_SAFE_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


def _sanitize_slug(slug: str) -> str:
    """Reject anything that isn't a flat lowercase package filename.

    Packages live in a single flat directory; rejecting `/`, `.`, and uppercase
    keeps the path-traversal surface zero.
    """
    if not slug or len(slug) > 128:
        return ""
    if any(c not in _SAFE_SLUG_CHARS for c in slug):
        return ""
    return slug


__all__ = [
    "PACKAGES_ENV",
    "ImportResult",
    "PackageMeta",
    "get_packages_dir",
    "import_package",
    "import_package_data",
    "list_packages",
]
