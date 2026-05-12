#!/usr/bin/env python3
"""Convert an OPML worldbuilding outline into a Storymaster lore pack.

The OPML files used here are nested outlines (Workflowy / Dynalist export
shape) where each `<outline text="…" _note="…">` is one node and structure is
purely hierarchy. We map the four well-known top-level sections to the four
biggest Lorekeeper tables:

- "Important peeps" / "NPCs" / "Characters" → ``actor`` (first_name = text)
- "Locations"                                 → ``location_``
- "Story lines" / "Storylines"                → ``history``
- everything else                             → ``world_data``

For each row, the row name is the immediate outline text and the description
is a markdown rendering of the subtree under it (so prompts like "Why/Who/What"
plus any free-form ``_note`` annotations are preserved verbatim).

Usage:
    python3 scripts/opml_to_lore_pack.py INPUT.opml OUTPUT.json \
        [--display-name "Pack title"]

The output is a normal lore pack — upload it via Lorekeeper → Import lore
packages → Upload, or drop it into ``world_building_packages/``.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--display-name", help="Override the pack's display_name")
    ap.add_argument(
        "--description", help="Override the pack's description", default=None
    )
    args = ap.parse_args()

    tree = ET.parse(args.input)
    body = tree.getroot().find("body")
    if body is None:
        print("OPML missing <body>", file=sys.stderr)
        return 1

    title_elt = tree.getroot().find("head/title")
    pack_title = (
        args.display_name
        or (title_elt.text if title_elt is not None else None)
        or args.input.stem.replace("_", " ").title()
    )

    actors: list[dict] = []
    locations: list[dict] = []
    histories: list[dict] = []
    world_data: list[dict] = []

    for top in body.findall("outline"):
        bucket = bucket_for(top.get("text", ""))
        target = {
            "actor": actors,
            "location_": locations,
            "history": histories,
            "world_data": world_data,
        }[bucket]
        for child in top.findall("outline"):
            row = build_row(bucket, child)
            if row is not None:
                target.append(row)

    if not (actors or locations or histories or world_data):
        print("Nothing to import — every top-level outline was empty.", file=sys.stderr)
        return 1

    pack = {
        "_package_info": {
            "display_name": pack_title,
            "description": args.description
            or f"Imported from {args.input.name}",
            "category": "User Upload",
            "version": "1.0",
            "author": "OPML import",
        },
        "actor": actors,
        "location_": locations,
        "history": histories,
        "world_data": world_data,
    }

    args.output.write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} — "
        f"actor: {len(actors)}, location_: {len(locations)}, "
        f"history: {len(histories)}, world_data: {len(world_data)}"
    )
    return 0


def bucket_for(top_text: str) -> str:
    """Pick a target table by the top-level outline title."""
    t = top_text.lower()
    if any(k in t for k in ("important peep", "npc", "character", "people")):
        return "actor"
    if "location" in t or "place" in t:
        return "location_"
    if "story" in t or "plot" in t or "adventure" in t or "campaign" in t:
        return "history"
    return "world_data"


def build_row(bucket: str, node: ET.Element) -> Optional[dict]:
    """Turn a depth-2 outline node into a Lorekeeper row dict."""
    raw_name = (node.get("text") or "").strip()
    if not raw_name:
        return None  # skip nameless placeholders
    body = render_markdown(node, depth=0)
    note = (node.get("_note") or "").strip()
    description = combine_description(note, body)

    if bucket == "actor":
        # `actor` has no `name` column. Names in worldbuilding outlines are
        # often single nicknames or descriptive phrases ("That tiefling",
        # "The Necromancer") that don't split cleanly into first/last, so we
        # keep them whole in first_name.
        row: dict = {"first_name": raw_name}
        if description:
            row["notes"] = description
        return row

    if not description:
        # Pure structural categories with no content aren't very useful — keep
        # them anyway so the user sees the same tree they had before.
        description = ""
    return {"name": raw_name, "description": description}


def combine_description(note: str, body: str) -> str:
    parts: list[str] = []
    if note:
        parts.append(html.unescape(note).strip())
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip()


def render_markdown(node: ET.Element, depth: int) -> str:
    """Render this node's *children* as a nested markdown bullet list."""
    lines: list[str] = []
    for child in node.findall("outline"):
        write_node(child, depth, lines)
    return "\n".join(lines).rstrip()


def write_node(node: ET.Element, depth: int, lines: list[str]) -> None:
    text = (node.get("text") or "").strip()
    note = (node.get("_note") or "").strip()
    if not text and not note:
        return  # entirely empty placeholder
    indent = "  " * depth
    if text:
        line = f"{indent}- {text}"
        if note:
            line += f" — {html.unescape(note).strip()}"
        lines.append(line)
    elif note:
        # Anonymous node with only a note — render as a free-floating line.
        lines.append(f"{indent}- {html.unescape(note).strip()}")
    for child in node.findall("outline"):
        write_node(child, depth + 1, lines)


if __name__ == "__main__":
    sys.exit(main())
