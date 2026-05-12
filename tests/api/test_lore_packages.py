"""Lore-package discovery + import.

The fixtures in `tests/_web_fixtures.py` provision an isolated SQLite per test;
each test creates a fresh setting and imports against it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _new_setting(client, name: str = "World") -> int:
    r = client.post("/api/v1/settings", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_list_includes_real_packs(login_as):
    client, _ = login_as("alice")
    r = client.get("/api/v1/lore-packages")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    # Sanity-check a couple of packs that ship with the repo.
    assert "fantasy_races" in slugs
    assert "fantasy_classes" in slugs


def test_import_fantasy_races_remaps_subrace_parent(login_as):
    """parent_race_id in the JSON references the package's own race rows.

    After import, the new SubRace rows should reference the new Race ids,
    not the (now-stale) ids that were in the JSON.
    """
    client, _ = login_as("alice")
    sid = _new_setting(client)

    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "fantasy_races"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] > 0
    assert "race" in body["imported_by_table"]
    assert "sub_race" in body["imported_by_table"]

    races = client.get(f"/api/v1/settings/{sid}/entities/race").json()
    sub_races = client.get(f"/api/v1/settings/{sid}/entities/sub_race").json()

    elf = next(r for r in races if r["name"] == "Elf")
    high_elf = next(s for s in sub_races if s["name"] == "High Elf")
    # Must point at the *new* Elf row id, not whatever was in the JSON.
    assert high_elf["parent_race_id"] == elf["id"]


def test_import_is_idempotent_via_duplicate_skip(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)

    first = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "fantasy_races"},
    ).json()

    second = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "fantasy_races"},
    ).json()

    assert second["imported"] == 0
    assert second["skipped_duplicates"] >= first["imported"]

    races = client.get(f"/api/v1/settings/{sid}/entities/race").json()
    names = [r["name"] for r in races]
    assert names.count("Elf") == 1


def test_import_unknown_package_returns_404(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "this_does_not_exist"},
    )
    assert r.status_code == 404


def test_import_rejects_path_traversal(login_as, tmp_path: Path, monkeypatch):
    """Even with an attacker-controlled directory, '..'-style slugs are rejected."""
    client, _ = login_as("alice")
    sid = _new_setting(client)

    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "../etc/passwd"},
    )
    assert r.status_code == 422


def test_import_into_unowned_setting_is_404(login_as):
    alice_client, _ = login_as("alice")
    bob_client, _ = login_as("bob", password="hunter3")
    bob_sid = _new_setting(bob_client)

    r = alice_client.post(
        f"/api/v1/settings/{bob_sid}/lore-packages/import",
        json={"package": "fantasy_races"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_imports_user_pack(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    pack = {
        "_package_info": {"display_name": "Uploads test"},
        "race": [
            {"id": 1, "name": "Tabaxi", "description": "Cat-like humanoids", "setting_id": 1}
        ],
        "sub_race": [
            {"parent_race_id": 1, "name": "Snow Tabaxi", "description": "Hardy.", "setting_id": 1}
        ],
    }
    files = {"file": ("my_pack.json", json.dumps(pack).encode("utf-8"), "application/json")}
    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/upload", files=files
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["imported_by_table"] == {"race": 1, "sub_race": 1}

    # FK was remapped to the new race row, not the literal 1 from the JSON.
    races = client.get(f"/api/v1/settings/{sid}/entities/race").json()
    subs = client.get(f"/api/v1/settings/{sid}/entities/sub_race").json()
    assert subs[0]["parent_race_id"] == races[0]["id"]


def test_upload_rejects_invalid_json(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    files = {"file": ("bad.json", b"{this is not json", "application/json")}
    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/upload", files=files
    )
    assert r.status_code == 422


def test_upload_rejects_non_object(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    files = {"file": ("arr.json", b'["wrong"]', "application/json")}
    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/upload", files=files
    )
    assert r.status_code == 422


def test_upload_remaps_self_referential_junction_fks(login_as):
    """actor_a_on_b_relations references the package's own actors via
    actor_a_id / actor_b_id — those must be remapped to the new actor ids."""
    client, _ = login_as("alice")
    sid = _new_setting(client)
    pack = {
        "_package_info": {"display_name": "Rels test"},
        "actor": [
            {"id": 10, "first_name": "Alice"},
            {"id": 11, "first_name": "Bob"},
        ],
        "actor_a_on_b_relations": [
            {"actor_a_id": 10, "actor_b_id": 11, "overall": "Rivals"},
        ],
    }
    files = {"file": ("rels.json", json.dumps(pack).encode("utf-8"), "application/json")}
    r = client.post(f"/api/v1/settings/{sid}/lore-packages/upload", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["imported_by_table"].get("actor_a_on_b_relations") == 1

    actors = client.get(f"/api/v1/settings/{sid}/entities/actor").json()
    by_name = {a["first_name"]: a["id"] for a in actors}
    rels = client.get(
        f"/api/v1/settings/{sid}/entities/actor_a_on_b_relations"
    ).json()
    assert len(rels) == 1
    assert rels[0]["actor_a_id"] == by_name["Alice"]
    assert rels[0]["actor_b_id"] == by_name["Bob"]


def test_upload_remaps_location_city_district_fks(login_as):
    """location_city_districts references the package's own locations via
    location_id (the city) AND district_id (the sub-location). Both must be
    remapped to the new location ids — district_id was originally missing from
    the FK pattern map, so its rows imported with stale ids and broke the FK."""
    client, _ = login_as("alice")
    sid = _new_setting(client)
    pack = {
        "_package_info": {"display_name": "Districts test"},
        "location_": [
            {"id": 500, "name": "Capital City"},
            {"id": 501, "name": "Old Quarter"},
        ],
        "location_city": [
            {"location_id": 500, "government": "Republic"},
        ],
        "location_city_districts": [
            {"location_id": 500, "district_id": 501},
        ],
    }
    files = {
        "file": ("districts.json", json.dumps(pack).encode("utf-8"), "application/json")
    }
    r = client.post(f"/api/v1/settings/{sid}/lore-packages/upload", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["imported_by_table"].get("location_city_districts") == 1

    locations = client.get(f"/api/v1/settings/{sid}/entities/location_").json()
    by_name = {loc["name"]: loc["id"] for loc in locations}
    districts = client.get(
        f"/api/v1/settings/{sid}/entities/location_city_districts"
    ).json()
    assert len(districts) == 1
    assert districts[0]["location_id"] == by_name["Capital City"]
    assert districts[0]["district_id"] == by_name["Old Quarter"]


def test_upload_into_unowned_setting_is_404(login_as):
    alice_client, _ = login_as("alice")
    bob_client, _ = login_as("bob", password="hunter3")
    bob_sid = _new_setting(bob_client)
    files = {
        "file": (
            "p.json",
            json.dumps({"_package_info": {}, "race": []}).encode("utf-8"),
            "application/json",
        )
    }
    r = alice_client.post(
        f"/api/v1/settings/{bob_sid}/lore-packages/upload", files=files
    )
    assert r.status_code == 404


def test_import_uses_env_override(login_as, tmp_path: Path, monkeypatch):
    """A custom packages dir via env replaces the bundled location."""
    pkg_dir = tmp_path / "packs"
    pkg_dir.mkdir()
    (pkg_dir / "tiny_pack.json").write_text(
        json.dumps(
            {
                "_package_info": {
                    "display_name": "Tiny Pack",
                    "description": "Test override",
                    "category": "Test",
                    "version": "0.1",
                },
                "race": [{"name": "Goblin", "description": "wee folk", "setting_id": 1}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STORYMASTER_LORE_PACKAGES_DIR", str(pkg_dir))

    client, _ = login_as("alice")
    sid = _new_setting(client)

    listing = client.get("/api/v1/lore-packages").json()
    assert {p["slug"] for p in listing} == {"tiny_pack"}

    r = client.post(
        f"/api/v1/settings/{sid}/lore-packages/import",
        json={"package": "tiny_pack"},
    )
    assert r.status_code == 200
    assert r.json()["imported_by_table"] == {"race": 1}
