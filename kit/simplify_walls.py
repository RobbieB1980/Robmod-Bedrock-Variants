#!/usr/bin/env python3
"""
Simplify Bedrock custom wall blocks: drop short/tall height split.

Before: wall_n/e/s/w ∈ {none, short, tall} × wall_post → 162 permutations each
After:  wall_n/e/s/w ∈ {none, tall}        × wall_post →  32 permutations each

Use this on a generated BP `blocks/` folder (or an entire pack root that
contains `*/blocks/*_wall.json`). Keeps packs under Bedrock's soft limit of
65536 custom block permutations.

Usage:
  py -3 kit/simplify_walls.py "Rob's Block/robsblock_BP"
  py -3 kit/simplify_walls.py "path/to/MyPack_BP/blocks"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SIDE_KEYS = ("wall_n", "wall_e", "wall_s", "wall_w")


def is_side_state(key: str) -> bool:
    return key.split(":")[-1] in SIDE_KEYS


def simplify_wall_file(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data["minecraft:block"]
    states = block["description"].get("states") or {}
    for k, v in list(states.items()):
        if is_side_state(k):
            states[k] = ["none", "tall"]

    perms = block.get("permutations") or []
    before = len(perms)
    block["permutations"] = [
        p for p in perms if "== 'short'" not in p.get("condition", "")
    ]
    after = len(block["permutations"])

    comps = block.get("components") or {}
    geo = comps.get("minecraft:geometry")
    if isinstance(geo, str) and geo.endswith("_short"):
        comps["minecraft:geometry"] = geo[: -len("_short")] + "_tall"

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return before, after


def find_wall_files(root: Path) -> list[Path]:
    if root.is_file() and root.name.endswith("_wall.json"):
        return [root]
    if root.is_dir():
        # Direct blocks folder or pack root
        direct = sorted(root.glob("*_wall.json"))
        if direct:
            return direct
        nested = sorted(root.rglob("*_wall.json"))
        return nested
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "path",
        type=Path,
        help="BP pack root, blocks/ folder, or a single *_wall.json",
    )
    args = ap.parse_args()
    root = args.path
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 1

    files = find_wall_files(root)
    if not files:
        print(f"No *_wall.json under {root}", file=sys.stderr)
        return 1

    total_before = total_after = 0
    for path in files:
        before, after = simplify_wall_file(path)
        total_before += before
        total_after += after

    n = len(files)
    print(f"Simplified {n} wall file(s)")
    print(f"  permutation entries: {total_before} → {total_after}")
    print(f"  state product per wall: 162 → 32")
    print(f"  estimated wall budget: {n * 162} → {n * 32}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
