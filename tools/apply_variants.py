#!/usr/bin/env python3
"""
Apply working Robmod-Bedrock-Variants patterns to ANY Bedrock behaviour/resource pack.

Proven on Rob Mod Bedrock (robmodbr) v1.7.1 — stairs, slabs, fence, wall, fence gate.
Does NOT create fence posts (fence alone is enough).

Examples
--------
  # All full-cube blocks in a pack
  py -3 tools/apply_variants.py --bp path/to/BP --rp path/to/RP --ns mynamespace --all

  # Only listed base names (one stem per line, e.g. brbrickblock_001)
  py -3 tools/apply_variants.py --bp BP --rp RP --ns myns --bases bases.txt

  # Excel column of texture filenames (maps via terrain_texture + material_instances)
  py -3 tools/apply_variants.py --bp BP --rp RP --ns myns --excel textures.xlsx

  # After unpacking an .mcaddon into a folder with BP+RP subdirs:
  py -3 tools/apply_variants.py --addon-dir unpacked_mod --ns myns --all
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GEO_DIR = REPO / "kit" / "geometries"
DEFAULT_SCRIPT_TEMPLATE = REPO / "kit" / "templates" / "main.js"

FORMAT = "1.26.30"
MIN_ENGINE = [1, 26, 0]
SERVER_API = "2.0.0"

VARIANT_SUFFIXES = (
    "_stairs",
    "_slab",
    "_fence",
    "_wall",
    "_fencepost",
    "_fence_gate",
)


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def box(o, s):
    return {"origin": list(o), "size": list(s)}


def selection_from_boxes(boxes) -> dict | bool:
    if boxes is True or boxes is False:
        return boxes
    if isinstance(boxes, dict):
        boxes = [boxes]
    if not boxes:
        return True
    min_x = min(b["origin"][0] for b in boxes)
    min_y = min(b["origin"][1] for b in boxes)
    min_z = min(b["origin"][2] for b in boxes)
    max_x = max(b["origin"][0] + b["size"][0] for b in boxes)
    max_y = max(b["origin"][1] + b["size"][1] for b in boxes)
    max_z = max(b["origin"][2] + b["size"][2] for b in boxes)
    min_x = max(-8.0, min_x)
    min_y = max(0.0, min_y)
    min_z = max(-8.0, min_z)
    max_x = min(8.0, max_x)
    max_y = min(16.0, max_y)
    max_z = min(8.0, max_z)
    sx = max(0.0, max_x - min_x)
    sy = max(0.0, max_y - min_y)
    sz = max(0.0, max_z - min_z)
    if sx == 0 or sy == 0 or sz == 0:
        return True

    def num(v: float):
        return int(v) if float(v).is_integer() else v

    return {
        "origin": [num(min_x), num(min_y), num(min_z)],
        "size": [num(sx), num(sy), num(sz)],
    }


def find_bp_rp(addon_dir: Path) -> tuple[Path, Path]:
    """Locate behaviour + resource pack folders under an unpacked addon."""
    addon_dir = addon_dir.resolve()
    bps, rps = [], []
    for p in addon_dir.iterdir():
        if not p.is_dir():
            continue
        man = p / "manifest.json"
        if not man.is_file():
            continue
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
        except Exception:
            continue
        modules = data.get("modules") or []
        types = {m.get("type") for m in modules}
        if "data" in types or "script" in types:
            bps.append(p)
        if "resources" in types:
            rps.append(p)
    # Fallback: common names
    if not bps:
        for name in ("BP", "bp", "behavior_pack", "behaviour_pack"):
            if (addon_dir / name).is_dir():
                bps.append(addon_dir / name)
    if not rps:
        for name in ("RP", "rp", "resource_pack"):
            if (addon_dir / name).is_dir():
                rps.append(addon_dir / name)
    if len(bps) != 1 or len(rps) != 1:
        raise SystemExit(
            f"Could not uniquely find BP+RP under {addon_dir}. "
            f"Found BP candidates={bps}, RP candidates={rps}. "
            f"Pass --bp and --rp explicitly."
        )
    return bps[0], rps[0]


def list_full_bases(bp: Path) -> list[str]:
    blocks = bp / "blocks"
    if not blocks.is_dir():
        return []
    bases = []
    for f in sorted(blocks.glob("*.json")):
        if any(f.stem.endswith(s) for s in VARIANT_SUFFIXES):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        comps = data.get("minecraft:block", {}).get("components", {})
        geo = comps.get("minecraft:geometry")
        if geo and geo != "minecraft:geometry.full_block":
            continue  # skip cross plants etc.
        bases.append(f.stem)
    return bases


def bases_from_excel(excel: Path, bp: Path, rp: Path) -> list[str]:
    try:
        import openpyxl
    except ImportError as e:
        raise SystemExit("openpyxl required for --excel: py -3 -m pip install openpyxl") from e

    wb = openpyxl.load_workbook(excel, read_only=True, data_only=True)
    stems = []
    for row in wb.active.iter_rows(values_only=True):
        v = row[0] if row else None
        if not v:
            continue
        s = str(v).strip()
        if not s.lower().endswith(".png"):
            continue
        if s.lower().endswith("_normal.png") or "NORM" in s:
            continue
        stems.append(Path(s).stem if ("/" in s or "\\" in s) else s[:-4])
    wb.close()

    tt_path = rp / "textures" / "terrain_texture.json"
    if not tt_path.is_file():
        print("WARNING: no terrain_texture.json — cannot map excel textures; falling back to stem match")
        return sorted({s for s in stems if (bp / "blocks" / f"{s}.json").exists()})

    tt = json.loads(tt_path.read_text(encoding="utf-8"))
    fname_to_keys: dict[str, list[str]] = defaultdict(list)
    for key, val in tt.get("texture_data", {}).items():
        t = val.get("textures")
        paths = t if isinstance(t, list) else [t]
        for p in paths:
            if not p:
                continue
            fname_to_keys[Path(str(p).replace("\\", "/")).stem].append(key)

    key_to_blocks: dict[str, set[str]] = defaultdict(set)
    for f in (bp / "blocks").glob("*.json"):
        if any(f.stem.endswith(s) for s in VARIANT_SUFFIXES):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        comps = data.get("minecraft:block", {}).get("components", {})
        if comps.get("minecraft:geometry") not in (None, "minecraft:geometry.full_block"):
            continue
        mi = comps.get("minecraft:material_instances") or {}
        for conf in mi.values():
            if isinstance(conf, dict) and "texture" in conf:
                key_to_blocks[conf["texture"]].add(f.stem)

    bases: set[str] = set()
    for stem in stems:
        keys = fname_to_keys.get(stem, [])
        found: set[str] = set()
        for k in keys:
            found |= key_to_blocks.get(k, set())
            base_key = re.sub(r"_(up|down|north|south|east|west)$", "", k)
            if base_key != k:
                for bk, bs in key_to_blocks.items():
                    if bk == base_key or bk.startswith(base_key + "_"):
                        found |= bs
        bases |= found
    return sorted(bases)


def bases_from_file(path: Path) -> list[str]:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(Path(line).stem if line.endswith(".json") else line)
    return lines


def extract_material_instances(src: dict) -> dict:
    mi = (
        src.get("minecraft:block", {})
        .get("components", {})
        .get("minecraft:material_instances")
        or {}
    )
    out: dict = {}
    for face, conf in mi.items():
        if not isinstance(conf, dict):
            continue
        entry = dict(conf)
        ao = entry.get("ambient_occlusion")
        if ao is True:
            entry["ambient_occlusion"] = 1.0
        elif ao is False:
            entry["ambient_occlusion"] = 0.0
        if "render_method" not in entry:
            entry["render_method"] = "opaque"
        if "ambient_occlusion" not in entry:
            entry["ambient_occlusion"] = 1.0
        if "face_dimming" not in entry:
            entry["face_dimming"] = True
        out[face] = entry
    if not out:
        out = {
            "*": {
                "texture": "unknown",
                "render_method": "opaque",
                "ambient_occlusion": 1.0,
                "face_dimming": True,
            }
        }
    return out


def extract_stats(src: dict) -> dict:
    comps = src.get("minecraft:block", {}).get("components", {})
    return {
        "destroy": comps.get("minecraft:destructible_by_mining", {}).get(
            "seconds_to_destroy", 1.5
        ),
        "explode": comps.get("minecraft:destructible_by_explosion", {}).get(
            "explosion_resistance", 6.0
        ),
        "friction": comps.get("minecraft:friction", 0.6),
        "flammable": comps.get(
            "minecraft:flammable",
            {"catch_chance_modifier": 0, "destroy_chance_modifier": 0},
        ),
        "light": comps.get("minecraft:light_emission", 0),
        "map_color": comps.get("minecraft:map_color", "#A0A0A0"),
    }


def base_components(materials: dict, stats: dict, ns: str, extra: dict | None = None) -> dict:
    c = {
        "minecraft:material_instances": materials,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": stats["destroy"]},
        "minecraft:destructible_by_explosion": {"explosion_resistance": stats["explode"]},
        "minecraft:friction": stats["friction"],
        "minecraft:flammable": stats["flammable"],
        "minecraft:light_emission": stats["light"],
        "minecraft:light_dampening": 15,
        "minecraft:map_color": stats["map_color"],
    }
    if extra:
        tags: list[str] = []
        cleaned: dict = {}
        for k, v in extra.items():
            if k.startswith("tag:"):
                tags.append(k[len("tag:") :])
            elif k == "minecraft:tags":
                if isinstance(v, list):
                    tags.extend(v)
                else:
                    cleaned[k] = v
            else:
                cleaned[k] = v
        if tags:
            seen: set[str] = set()
            ordered: list[str] = []
            for t in tags:
                if t not in seen:
                    seen.add(t)
                    ordered.append(t)
            cleaned["minecraft:tags"] = ordered
        c.update(cleaned)
    return c


def dir_yaw(direction: str) -> float:
    return {"north": 0.0, "east": -90.0, "south": 180.0, "west": 90.0}[direction]


def rot_comp(direction: str) -> dict:
    return {"minecraft:transformation": {"rotation": [0, dir_yaw(direction), 0]}}


def stairs_collision(corner: str, half: str) -> list:
    if half == "bottom":
        base = [box((-8, 0, -8), (16, 8, 16))]
        if corner == "none":
            return base + [box((-8, 8, -8), (16, 8, 8))]
        if corner == "inner_left":
            return base + [box((-8, 8, -8), (16, 8, 8)), box((-8, 8, 0), (8, 8, 8))]
        if corner == "inner_right":
            return base + [box((-8, 8, -8), (16, 8, 8)), box((0, 8, 0), (8, 8, 8))]
        if corner == "outer_left":
            return base + [box((-8, 8, -8), (8, 8, 8))]
        if corner == "outer_right":
            return base + [box((0, 8, -8), (8, 8, 8))]
    else:
        base = [box((-8, 8, -8), (16, 8, 16))]
        if corner == "none":
            return base + [box((-8, 0, -8), (16, 8, 8))]
        if corner == "inner_left":
            return base + [box((-8, 0, -8), (16, 8, 8)), box((-8, 0, 0), (8, 8, 8))]
        if corner == "inner_right":
            return base + [box((-8, 0, -8), (16, 8, 8)), box((0, 0, 0), (8, 8, 8))]
        if corner == "outer_left":
            return base + [box((-8, 0, -8), (8, 8, 8))]
        if corner == "outer_right":
            return base + [box((0, 0, -8), (8, 8, 8))]
    return base


def flip_stair_corner(corner: str) -> str:
    return {
        "none": "none",
        "inner_left": "inner_right",
        "inner_right": "inner_left",
        "outer_left": "outer_right",
        "outer_right": "outer_left",
    }.get(corner, corner)


def stairs_geo(geo: str, corner: str, half: str) -> str:
    mapping = {
        ("none", "bottom"): f"{geo}.stairs_straight_bottom",
        ("none", "top"): f"{geo}.stairs_straight_top",
        ("inner_left", "bottom"): f"{geo}.stairs_inner_left_bottom",
        ("inner_right", "bottom"): f"{geo}.stairs_inner_right_bottom",
        ("outer_left", "bottom"): f"{geo}.stairs_outer_left_bottom",
        ("outer_right", "bottom"): f"{geo}.stairs_outer_right_bottom",
        ("inner_left", "top"): f"{geo}.stairs_inner_left_top",
        ("inner_right", "top"): f"{geo}.stairs_inner_right_top",
        ("outer_left", "top"): f"{geo}.stairs_outer_left_top",
        ("outer_right", "top"): f"{geo}.stairs_outer_right_top",
    }
    return mapping[(corner, half)]


def fence_collision(n, e, s, w) -> list:
    boxes = [box((-2, 0, -2), (4, 24, 4))]
    if n:
        boxes.append(box((-2, 0, -8), (4, 24, 6)))
    if s:
        boxes.append(box((-2, 0, 2), (4, 24, 6)))
    if e:
        boxes.append(box((2, 0, -2), (6, 24, 4)))
    if w:
        boxes.append(box((-8, 0, -2), (6, 24, 4)))
    return boxes


def wall_collision(post, n, e, s, w) -> list:
    h = 24
    boxes = []
    if post:
        boxes.append(box((-4, 0, -4), (8, h, 8)))
    if n != "none":
        boxes.append(box((-4, 0, -8), (8, h, 4)))
    if s != "none":
        boxes.append(box((-4, 0, 4), (8, h, 4)))
    if e != "none":
        boxes.append(box((4, 0, -4), (4, h, 8)))
    if w != "none":
        boxes.append(box((-8, 0, -4), (4, h, 8)))
    if not boxes:
        boxes.append(box((-4, 0, -4), (8, h, 8)))
    return boxes


def build_stairs_perms(geo: str) -> list:
    perms = []
    for direction in ("north", "east", "south", "west"):
        for half in ("bottom", "top"):
            for corner in (
                "none",
                "inner_left",
                "inner_right",
                "outer_left",
                "outer_right",
            ):
                mesh_corner = flip_stair_corner(corner)
                coll = stairs_collision(mesh_corner, half)
                perms.append(
                    {
                        "condition": (
                            f"q.block_state('minecraft:cardinal_direction') == '{direction}'"
                            f" && q.block_state('minecraft:vertical_half') == '{half}'"
                            f" && q.block_state('minecraft:corner') == '{corner}'"
                        ),
                        "components": {
                            "minecraft:geometry": stairs_geo(geo, mesh_corner, half),
                            "minecraft:collision_box": coll,
                            "minecraft:selection_box": selection_from_boxes(coll),
                            **rot_comp(direction),
                        },
                    }
                )
    return perms


def build_fence_perms(ns: str, geo: str) -> list:
    perms = []
    for mask in range(16):
        n = bool(mask & (1 << 0))
        s = bool(mask & (1 << 1))
        e = bool(mask & (1 << 2))
        w = bool(mask & (1 << 3))
        name = f"{geo}.fence_{int(n)}{int(w)}{int(s)}{int(e)}"  # E↔W mesh swap
        coll = fence_collision(n, w, s, e)
        perms.append(
            {
                "condition": f"q.block_state('{ns}:conn') == {mask}",
                "components": {
                    "minecraft:geometry": name,
                    "minecraft:collision_box": coll,
                    "minecraft:selection_box": selection_from_boxes(coll),
                },
            }
        )
    return perms


def build_wall_perms(ns: str, geo: str) -> list:
    sides = ("none", "short", "tall")
    perms = []
    for n in sides:
        for e in sides:
            for s in sides:
                for w in sides:
                    for post in (True, False):
                        if not post and n == e == s == w == "none":
                            continue
                        height = (
                            "tall"
                            if any(x == "tall" for x in (n, e, s, w))
                            else "short"
                        )
                        gn = 1 if n != "none" else 0
                        ge = 1 if w != "none" else 0  # E↔W
                        gs = 1 if s != "none" else 0
                        gw = 1 if e != "none" else 0
                        if gn == ge == gs == gw == 0 and post:
                            g = f"{geo}.wall_p1_0000_short"
                        else:
                            g = f"{geo}.wall_p{int(post)}_{gn}{ge}{gs}{gw}_{height}"
                        coll = wall_collision(post, n, w, s, e)
                        perms.append(
                            {
                                "condition": (
                                    f"q.block_state('{ns}:wall_n') == '{n}'"
                                    f" && q.block_state('{ns}:wall_e') == '{e}'"
                                    f" && q.block_state('{ns}:wall_s') == '{s}'"
                                    f" && q.block_state('{ns}:wall_w') == '{w}'"
                                    f" && q.block_state('{ns}:wall_post') == {'true' if post else 'false'}"
                                ),
                                "components": {
                                    "minecraft:geometry": g,
                                    "minecraft:collision_box": coll,
                                    "minecraft:selection_box": selection_from_boxes(coll),
                                },
                            }
                        )
    return perms


def build_gate_perms(ns: str, geo: str) -> list:
    closed_coll = [box((-8, 0, -2), (16, 24, 4))]
    open_coll = [box((-8, 0, -2), (2, 24, 4)), box((6, 0, -2), (2, 24, 4))]
    perms = []
    for direction in ("north", "east", "south", "west"):
        for open_ in (False, True):
            for in_wall in (False, True):
                if open_ and in_wall:
                    g = f"{geo}.gate_open_inwall"
                elif open_:
                    g = f"{geo}.gate_open"
                elif in_wall:
                    g = f"{geo}.gate_closed_inwall"
                else:
                    g = f"{geo}.gate_closed"
                coll = open_coll if open_ else closed_coll
                perms.append(
                    {
                        "condition": (
                            f"q.block_state('minecraft:cardinal_direction') == '{direction}'"
                            f" && q.block_state('{ns}:open') == {'true' if open_ else 'false'}"
                            f" && q.block_state('{ns}:in_wall') == {'true' if in_wall else 'false'}"
                        ),
                        "components": {
                            "minecraft:geometry": g,
                            "minecraft:collision_box": coll,
                            "minecraft:selection_box": selection_from_boxes(coll),
                            **rot_comp(direction),
                        },
                    }
                )
    return perms


def write_loot(bp: Path, stem: str, identifier: str) -> None:
    dump(
        bp / "loot_tables" / "blocks" / f"{stem}.json",
        {
            "pools": [
                {
                    "rolls": 1,
                    "entries": [
                        {
                            "type": "item",
                            "name": identifier,
                            "weight": 1,
                            "functions": [{"function": "set_count", "count": 1}],
                        }
                    ],
                }
            ]
        },
    )


def write_recipes(bp: Path, ns: str, base: str) -> None:
    id_full = f"{ns}:{base}"
    unlock = [{"item": id_full}]
    specs = [
        (f"{base}_stairs", ["#  ", "## ", "###"], {"#": {"item": id_full}}, 4),
        (f"{base}_slab", ["###"], {"#": {"item": id_full}}, 6),
        (
            f"{base}_fence",
            ["#S#", "#S#"],
            {"#": {"item": id_full}, "S": {"item": "minecraft:stick"}},
            3,
        ),
        (f"{base}_wall", ["###", "###"], {"#": {"item": id_full}}, 6),
        (
            f"{base}_fence_gate",
            ["S#S", "S#S"],
            {"#": {"item": id_full}, "S": {"item": "minecraft:stick"}},
            1,
        ),
    ]
    for stem, pattern, key, count in specs:
        dump(
            bp / "recipes" / f"{stem}.json",
            {
                "format_version": "1.21.0",
                "minecraft:recipe_shaped": {
                    "description": {"identifier": f"{ns}:{stem}"},
                    "tags": ["crafting_table"],
                    "pattern": pattern,
                    "key": key,
                    "unlock": unlock,
                    "result": {"item": f"{ns}:{stem}", "count": count},
                },
            },
        )


def write_block_set(
    bp: Path,
    ns: str,
    geo: str,
    base: str,
    materials: dict,
    stats: dict,
    stairs_perms,
    fence_perms,
    wall_perms,
    gate_perms,
) -> None:
    id_full = f"{ns}:{base}"
    id_stairs = f"{ns}:{base}_stairs"
    id_slab = f"{ns}:{base}_slab"
    id_fence = f"{ns}:{base}_fence"
    id_wall = f"{ns}:{base}_wall"
    id_gate = f"{ns}:{base}_fence_gate"

    dump(
        bp / "blocks" / f"{base}.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_full,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.stoneBrick",
                    },
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        "minecraft:geometry": "minecraft:geometry.full_block",
                        "minecraft:collision_box": True,
                        "minecraft:selection_box": True,
                        f"tag:{ns}:source_block": {},
                        "minecraft:loot": f"loot_tables/blocks/{base}.json",
                    },
                ),
            },
        },
    )

    dump(
        bp / "blocks" / f"{base}_stairs.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_stairs,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.stairs",
                    },
                    "traits": {
                        "minecraft:placement_position": {
                            "enabled_states": ["minecraft:vertical_half"]
                        },
                        "minecraft:placement_direction": {
                            "enabled_states": ["minecraft:corner_and_cardinal_direction"],
                            "blocks_to_corner_with": [
                                {"tags": "q.any_tag('minecraft:cornerable_stairs')"}
                            ],
                        },
                    },
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        "tag:minecraft:cornerable_stairs": {},
                        f"tag:{ns}:stairs": {},
                        "minecraft:geometry": f"{geo}.stairs_straight_bottom",
                        "minecraft:collision_box": stairs_collision("none", "bottom"),
                        "minecraft:selection_box": selection_from_boxes(
                            stairs_collision("none", "bottom")
                        ),
                        "minecraft:support": {"shape": "stair"},
                        "minecraft:loot": f"loot_tables/blocks/{base}_stairs.json",
                    },
                ),
                "permutations": stairs_perms,
            },
        },
    )

    bottom_box = box((-8, 0, -8), (16, 8, 16))
    top_box = box((-8, 8, -8), (16, 8, 16))
    full_box = box((-8, 0, -8), (16, 16, 16))
    dump(
        bp / "blocks" / f"{base}_slab.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_slab,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.slab",
                    },
                    "states": {f"{ns}:slab_type": ["bottom", "top", "double"]},
                    "traits": {
                        "minecraft:placement_position": {
                            "enabled_states": ["minecraft:vertical_half"]
                        }
                    },
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        f"tag:{ns}:slab": {},
                        f"tag:{ns}:slab_{base}": {},
                        "minecraft:geometry": f"{geo}.slab_bottom",
                        "minecraft:collision_box": bottom_box,
                        "minecraft:selection_box": bottom_box,
                        f"{ns}:slab_stacking": {},
                        "minecraft:loot": f"loot_tables/blocks/{base}_slab.json",
                    },
                ),
                "permutations": [
                    {
                        "condition": f"q.block_state('{ns}:slab_type') == 'bottom'",
                        "components": {
                            "minecraft:geometry": f"{geo}.slab_bottom",
                            "minecraft:collision_box": bottom_box,
                            "minecraft:selection_box": bottom_box,
                            "minecraft:light_dampening": 0,
                        },
                    },
                    {
                        "condition": f"q.block_state('{ns}:slab_type') == 'top'",
                        "components": {
                            "minecraft:geometry": f"{geo}.slab_top",
                            "minecraft:collision_box": top_box,
                            "minecraft:selection_box": top_box,
                            "minecraft:light_dampening": 0,
                        },
                    },
                    {
                        "condition": f"q.block_state('{ns}:slab_type') == 'double'",
                        "components": {
                            "minecraft:geometry": "minecraft:geometry.full_block",
                            "minecraft:collision_box": full_box,
                            "minecraft:selection_box": full_box,
                            "minecraft:light_dampening": 15,
                        },
                    },
                ],
            },
        },
    )

    root_coll = fence_collision(False, False, False, False)
    dump(
        bp / "blocks" / f"{base}_fence.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_fence,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.fence",
                    },
                    "states": {f"{ns}:conn": list(range(16))},
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        "tag:minecraft:has_fence_connections": {},
                        f"tag:{ns}:fence": {},
                        "minecraft:connection_rule": {
                            "accepts_connections_from": "only_fences"
                        },
                        "minecraft:support": {"shape": "fence"},
                        "minecraft:geometry": f"{geo}.fence_0000",
                        "minecraft:collision_box": root_coll,
                        "minecraft:selection_box": selection_from_boxes(root_coll),
                        "minecraft:light_dampening": 0,
                        f"{ns}:fence_update": {},
                        "minecraft:loot": f"loot_tables/blocks/{base}_fence.json",
                    },
                ),
                "permutations": fence_perms,
            },
        },
    )

    root_wall = wall_collision(True, "none", "none", "none", "none")
    dump(
        bp / "blocks" / f"{base}_wall.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_wall,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.walls",
                    },
                    "states": {
                        f"{ns}:wall_n": ["none", "short", "tall"],
                        f"{ns}:wall_e": ["none", "short", "tall"],
                        f"{ns}:wall_s": ["none", "short", "tall"],
                        f"{ns}:wall_w": ["none", "short", "tall"],
                        f"{ns}:wall_post": [True, False],
                    },
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        f"tag:{ns}:wall": {},
                        "minecraft:geometry": f"{geo}.wall_p1_0000_short",
                        "minecraft:collision_box": root_wall,
                        "minecraft:selection_box": selection_from_boxes(root_wall),
                        "minecraft:light_dampening": 0,
                        f"{ns}:wall_update": {},
                        "minecraft:loot": f"loot_tables/blocks/{base}_wall.json",
                    },
                ),
                "permutations": wall_perms,
            },
        },
    )

    closed_coll = [box((-8, 0, -2), (16, 24, 4))]
    dump(
        bp / "blocks" / f"{base}_fence_gate.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": id_gate,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.fenceGates",
                    },
                    "states": {
                        f"{ns}:open": [False, True],
                        f"{ns}:powered": [False, True],
                        f"{ns}:in_wall": [False, True],
                    },
                    "traits": {
                        "minecraft:placement_direction": {
                            "enabled_states": ["minecraft:cardinal_direction"]
                        }
                    },
                },
                "components": base_components(
                    materials,
                    stats,
                    ns,
                    {
                        f"tag:{ns}:fence_gate": {},
                        "tag:minecraft:has_fence_connections": {},
                        "minecraft:connection_rule": {
                            "accepts_connections_from": "all"
                        },
                        "minecraft:geometry": f"{geo}.gate_closed",
                        "minecraft:collision_box": closed_coll,
                        "minecraft:selection_box": selection_from_boxes(closed_coll),
                        "minecraft:light_dampening": 0,
                        "minecraft:redstone_consumer": {
                            "min_power": 1,
                            "propagates_power": False,
                        },
                        f"{ns}:fence_gate": {},
                        "minecraft:loot": f"loot_tables/blocks/{base}_fence_gate.json",
                    },
                ),
                "permutations": gate_perms,
            },
        },
    )

    for stem, ident in [
        (base, id_full),
        (f"{base}_stairs", id_stairs),
        (f"{base}_slab", id_slab),
        (f"{base}_fence", id_fence),
        (f"{base}_wall", id_wall),
        (f"{base}_fence_gate", id_gate),
    ]:
        write_loot(bp, stem, ident)
    write_recipes(bp, ns, base)

    # Remove legacy fencepost if present
    fp = bp / "blocks" / f"{base}_fencepost.json"
    if fp.is_file():
        fp.unlink()


def install_geometries(geo_src: Path, rp: Path, geo_prefix: str) -> int:
    """Copy kit geos and rewrite identifiers to geometry.{ns}.* (geo_prefix)."""
    out = rp / "models" / "blocks"
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    # Accept geometry.rmbv.X or geometry.anything.X
    for src in sorted(geo_src.glob("*.geo.json")):
        data = json.loads(src.read_text(encoding="utf-8"))
        for g in data.get("minecraft:geometry") or []:
            desc = g.get("description") or {}
            ident = desc.get("identifier", "")
            # geometry.rmbv.fence_0000 → geometry.NS.fence_0000
            m = re.match(r"geometry\.[^.]+\.(.+)$", ident)
            if m:
                desc["identifier"] = f"{geo_prefix}.{m.group(1)}"
            elif ident.startswith("geometry."):
                # geometry.rmbv_something fallback
                tail = ident.split(".", 1)[-1]
                if "." in tail:
                    desc["identifier"] = f"{geo_prefix}.{tail.split('.', 1)[-1]}"
                else:
                    desc["identifier"] = f"{geo_prefix}.{tail}"
        dump(out / src.name, data)
        count += 1
    return count


def write_script(bp: Path, ns: str, template: Path) -> None:
    text = template.read_text(encoding="utf-8")
    text = text.replace("__NS__", ns)
    out = bp / "scripts" / "main.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def update_blocks_json(rp: Path, ns: str, bases: list[str]) -> None:
    path = rp / "blocks.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"format_version": "1.21.40"}
    for base in bases:
        full_key = f"{ns}:{base}"
        sound = "stone"
        if full_key in data and isinstance(data[full_key], dict):
            sound = data[full_key].get("sound", sound)
        for suffix in ("", "_stairs", "_slab", "_fence", "_wall", "_fence_gate"):
            data[f"{ns}:{base}{suffix}"] = {"sound": sound}
        # drop fencepost
        data.pop(f"{ns}:{base}_fencepost", None)
    if "format_version" not in data:
        data = {"format_version": "1.21.40", **data}
    dump(path, data)


def update_lang(rp: Path, ns: str, bases: list[str]) -> None:
    path = rp / "texts" / "en_US.lang"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    by_key: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        if "fencepost" in line.lower():
            continue  # strip fencepost names
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            order.append(line)
            continue
        k, v = line.split("=", 1)
        by_key[k] = v
        order.append(k)

    def pretty(base: str) -> str:
        existing = by_key.get(f"tile.{ns}:{base}.name")
        if existing:
            return existing
        return base.replace("_", " ").title()

    for base in bases:
        name = pretty(base)
        pairs = {
            f"tile.{ns}:{base}.name": name,
            f"tile.{ns}:{base}_stairs.name": f"{name} Stairs",
            f"tile.{ns}:{base}_slab.name": f"{name} Slab",
            f"tile.{ns}:{base}_fence.name": f"{name} Fence",
            f"tile.{ns}:{base}_wall.name": f"{name} Wall",
            f"tile.{ns}:{base}_fence_gate.name": f"{name} Fence Gate",
        }
        for k, v in pairs.items():
            if k not in by_key:
                order.append(k)
            by_key[k] = v

    out_lines = []
    seen = set()
    for item in order:
        if item in by_key:
            if item in seen:
                continue
            seen.add(item)
            out_lines.append(f"{item}={by_key[item]}")
        else:
            out_lines.append(item)
    for k, v in by_key.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def bump_manifests(bp: Path, rp: Path, version: list[int]) -> None:
    for path, is_bp in ((bp / "manifest.json", True), (rp / "manifest.json", False)):
        if not path.is_file():
            print(f"WARNING: missing {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        data["header"]["version"] = version
        data["header"]["min_engine_version"] = MIN_ENGINE
        for mod in data.get("modules", []):
            mod["version"] = version
        if is_bp:
            for dep in data.get("dependencies", []):
                if "uuid" in dep:
                    dep["version"] = version
                if dep.get("module_name") == "@minecraft/server":
                    dep["version"] = SERVER_API
            # Ensure script module exists
            types = {m.get("type") for m in data.get("modules", [])}
            if "script" not in types:
                data.setdefault("modules", []).append(
                    {
                        "description": "Variant scripts (fence/wall/slab/gate)",
                        "type": "script",
                        "language": "javascript",
                        "uuid": "a7c3e91f-4b2d-4e8a-9f1c-6d5e8b0a2c34",
                        "version": version,
                        "entry": "scripts/main.js",
                    }
                )
            has_server = any(
                d.get("module_name") == "@minecraft/server"
                for d in data.get("dependencies", [])
            )
            if not has_server:
                data.setdefault("dependencies", []).append(
                    {"module_name": "@minecraft/server", "version": SERVER_API}
                )
        dump(path, data)


def remove_all_fenceposts(bp: Path, rp: Path, ns: str) -> int:
    n = 0
    blocks = bp / "blocks"
    if blocks.is_dir():
        for p in blocks.glob("*_fencepost.json"):
            p.unlink()
            n += 1
    bj = rp / "blocks.json"
    if bj.is_file():
        data = json.loads(bj.read_text(encoding="utf-8"))
        for k in list(data.keys()):
            if "fencepost" in k.lower():
                del data[k]
                n += 1
        dump(bj, data)
    lang = rp / "texts" / "en_US.lang"
    if lang.is_file():
        lines = [
            l
            for l in lang.read_text(encoding="utf-8").splitlines()
            if "fencepost" not in l.lower()
        ]
        lang.write_text("\n".join(lines) + "\n", encoding="utf-8")
    geo = rp / "models" / "blocks"
    if geo.is_dir():
        for p in geo.glob("*fencepost*"):
            p.unlink()
            n += 1
    return n


def parse_version(s: str) -> list[int]:
    parts = [int(x) for x in s.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return parts[:3]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Apply Robmod-Bedrock-Variants patterns to a Bedrock pack"
    )
    ap.add_argument("--bp", type=Path, help="Behaviour pack folder")
    ap.add_argument("--rp", type=Path, help="Resource pack folder")
    ap.add_argument(
        "--addon-dir",
        type=Path,
        help="Unpacked .mcaddon / folder containing BP+RP subdirs",
    )
    ap.add_argument("--ns", required=True, help="Namespace (e.g. robmodbr, mymod)")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Upgrade all full-cube blocks in BP/blocks",
    )
    ap.add_argument("--bases", type=Path, help="Text file of base block stems")
    ap.add_argument("--excel", type=Path, help="Excel list of texture pngs to map")
    ap.add_argument(
        "--geo-dir",
        type=Path,
        default=DEFAULT_GEO_DIR,
        help=f"Geometry source dir (default: {DEFAULT_GEO_DIR})",
    )
    ap.add_argument(
        "--script-template",
        type=Path,
        default=DEFAULT_SCRIPT_TEMPLATE,
        help="main.js template with __NS__ placeholder",
    )
    ap.add_argument(
        "--geo-prefix",
        default=None,
        help="Geometry identifier prefix (default: geometry.<ns>)",
    )
    ap.add_argument(
        "--pack-version",
        default="1.0.0",
        help="Pack version to write into manifests (default 1.0.0)",
    )
    ap.add_argument(
        "--no-script", action="store_true", help="Do not overwrite scripts/main.js"
    )
    ap.add_argument(
        "--no-geometries", action="store_true", help="Do not install geometry files"
    )
    ap.add_argument(
        "--remove-fencepost-only",
        action="store_true",
        help="Only remove fencepost assets; do not generate variants",
    )
    args = ap.parse_args(argv)

    if args.addon_dir:
        bp, rp = find_bp_rp(args.addon_dir)
    else:
        if not args.bp or not args.rp:
            ap.error("Provide --bp and --rp, or --addon-dir")
        bp, rp = args.bp.resolve(), args.rp.resolve()

    ns = args.ns
    geo_prefix = args.geo_prefix or f"geometry.{ns}"
    version = parse_version(args.pack_version)

    print(f"BP: {bp}")
    print(f"RP: {rp}")
    print(f"NS: {ns}  geo: {geo_prefix}")

    if args.remove_fencepost_only:
        n = remove_all_fenceposts(bp, rp, ns)
        print(f"Removed fencepost-related entries (~{n} ops)")
        return

    if args.all:
        bases = list_full_bases(bp)
    elif args.bases:
        bases = bases_from_file(args.bases)
    elif args.excel:
        bases = bases_from_excel(args.excel, bp, rp)
    else:
        ap.error("Provide --all, --bases, or --excel (or --remove-fencepost-only)")

    # Keep only existing full blocks
    bases = [b for b in bases if (bp / "blocks" / f"{b}.json").is_file()]
    if not bases:
        raise SystemExit("No target full blocks found.")
    print(f"Targets: {len(bases)} full blocks")

    if not args.no_geometries:
        if not args.geo_dir.is_dir():
            raise SystemExit(f"Geometry dir missing: {args.geo_dir}")
        n = install_geometries(args.geo_dir, rp, geo_prefix)
        print(f"Installed {n} geometries → {geo_prefix}.*")

    print("Building permutation templates…")
    stairs_perms = build_stairs_perms(geo_prefix)
    fence_perms = build_fence_perms(ns, geo_prefix)
    wall_perms = build_wall_perms(ns, geo_prefix)
    gate_perms = build_gate_perms(ns, geo_prefix)
    print(
        f"  stairs={len(stairs_perms)} fence={len(fence_perms)} "
        f"wall={len(wall_perms)} gate={len(gate_perms)}"
    )

    print("Writing block sets…")
    for i, base in enumerate(bases, 1):
        src = json.loads((bp / "blocks" / f"{base}.json").read_text(encoding="utf-8"))
        materials = extract_material_instances(src)
        stats = extract_stats(src)
        write_block_set(
            bp,
            ns,
            geo_prefix,
            base,
            materials,
            stats,
            stairs_perms,
            fence_perms,
            wall_perms,
            gate_perms,
        )
        if i % 50 == 0 or i == len(bases):
            print(f"  {i}/{len(bases)}")

    print("Updating blocks.json, lang, manifests…")
    update_blocks_json(rp, ns, bases)
    update_lang(rp, ns, bases)
    remove_all_fenceposts(bp, rp, ns)
    bump_manifests(bp, rp, version)

    if not args.no_script:
        if not args.script_template.is_file():
            raise SystemExit(f"Script template missing: {args.script_template}")
        write_script(bp, ns, args.script_template)
        print(f"Wrote scripts/main.js (ns={ns})")

    print("Done.")
    print(
        "Install BP+RP separately (not the parent folder). "
        "Enable both packs. Bedrock 1.26+ required."
    )


if __name__ == "__main__":
    main()
