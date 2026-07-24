#!/usr/bin/env python3
"""Generate trial mcaddon assets for brbrickblock_001 variants."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "rmbv_bp"
RP = ROOT / "rmbv_rp"
TEX = "rmbv_brbrickblock_001"
NS = "rmbv"
BLOCK = "brbrickblock_001"
ID_FULL = f"{NS}:{BLOCK}"
ID_STAIRS = f"{NS}:{BLOCK}_stairs"
ID_SLAB = f"{NS}:{BLOCK}_slab"
ID_FENCE = f"{NS}:{BLOCK}_fence"
ID_WALL = f"{NS}:{BLOCK}_wall"
ID_GATE = f"{NS}:{BLOCK}_fence_gate"

# Reasonable stone-like defaults for a testable trial (source used 1000 placeholders)
DESTROY = 1.5
EXPLODE = 6.0
FRICTION = 0.6
SOUND = "stone"
FORMAT = "1.26.30"


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def face_uv(u: float, v: float, w: float = 16, h: float = 16) -> dict:
    return {"uv": [u, v], "uv_size": [w, h]}


def cube(origin, size, uv_box=None) -> dict:
    """Create a cube with per-face UVs covering the source texture proportionally."""
    ox, oy, oz = origin
    sx, sy, sz = size
    # Map each face to the full 16x16 texture (spec: use complete original texture)
    uv = {
        "north": face_uv(0, 0),
        "south": face_uv(0, 0),
        "east": face_uv(0, 0),
        "west": face_uv(0, 0),
        "up": face_uv(0, 0),
        "down": face_uv(0, 0),
    }
    if uv_box:
        uv = uv_box
    return {"origin": [ox, oy, oz], "size": [sx, sy, sz], "uv": uv}


def make_geometry(identifier: str, cubes: list[dict], bounds_h: float = 1.5) -> dict:
    return {
        "format_version": "1.21.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": identifier,
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 2,
                    "visible_bounds_height": bounds_h,
                    "visible_bounds_offset": [0, bounds_h / 2, 0],
                },
                "bones": [{"name": "root", "pivot": [0, 0, 0], "cubes": cubes}],
            }
        ],
    }


def box(o, s):
    return {"origin": list(o), "size": list(s)}


def selection_from_boxes(boxes) -> dict | bool:
    """Build a single selection box (Bedrock does not allow multi-box selection).

    Selection boxes are limited to the 16×16×16 unit cube: origin in
    (-8,0,-8)..(8,16,8) and origin+size within that range. Collision may
    extend to Y=24; selection must be clamped to Y=16.
    """
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
        # Prefer ints in JSON when values are whole numbers
        return int(v) if float(v).is_integer() else v

    return {
        "origin": [num(min_x), num(min_y), num(min_z)],
        "size": [num(sx), num(sy), num(sz)],
    }


# ---------------------------------------------------------------------------
# Geometries
# ---------------------------------------------------------------------------

def write_geometries() -> None:
    """Write block geometries.

    Prefer Block Variant Studio export (all_model.geo.json) via import_bvs_geos:
    pivot-relative split, stair L/R correction, full fence/wall expansion + UVs.
    Falls back to procedural cubes if the export is missing.
    """
    bvs_source = ROOT.parent / "all_model.geo.json"
    if bvs_source.is_file():
        import sys

        tools_dir = Path(__file__).resolve().parent
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        from import_bvs_geos import import_geos

        models = RP / "models" / "blocks"
        stats = import_geos(bvs_source, models, clean=True)
        print(
            f"Geometries from BVS export: direct={stats['direct']} "
            f"fence={stats['fence']} wall={stats['wall']} "
            f"skipped={stats['skipped']} ({bvs_source.name})"
        )
        return

    print("WARNING: all_model.geo.json not found — using procedural geometries")
    models = RP / "models" / "blocks"

    # --- Stairs: default facing NORTH (high half toward -Z / north) ---
    # bottom straight
    dump(
        models / "stairs_straight_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_straight_bottom",
            [
                cube((-8, 0, -8), (16, 8, 16)),
                cube((-8, 8, -8), (16, 8, 8)),  # north half upper
            ],
        ),
    )
    dump(
        models / "stairs_straight_top.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_straight_top",
            [
                cube((-8, 8, -8), (16, 8, 16)),
                cube((-8, 0, -8), (16, 8, 8)),
            ],
        ),
    )
    # inner corner: full bottom + L-shaped top (N + W high for inner_left when facing north)
    # inner_left for north-facing: fills north and west upper quarters
    dump(
        models / "stairs_inner_left_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_inner_left_bottom",
            [
                cube((-8, 0, -8), (16, 8, 16)),
                cube((-8, 8, -8), (16, 8, 8)),  # north
                cube((-8, 8, 0), (8, 8, 8)),  # west-south remaining
            ],
        ),
    )
    dump(
        models / "stairs_inner_right_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_inner_right_bottom",
            [
                cube((-8, 0, -8), (16, 8, 16)),
                cube((-8, 8, -8), (16, 8, 8)),  # north
                cube((0, 8, 0), (8, 8, 8)),  # east-south
            ],
        ),
    )
    dump(
        models / "stairs_outer_left_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_outer_left_bottom",
            [
                cube((-8, 0, -8), (16, 8, 16)),
                cube((-8, 8, -8), (8, 8, 8)),  # NW quarter only
            ],
        ),
    )
    dump(
        models / "stairs_outer_right_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_outer_right_bottom",
            [
                cube((-8, 0, -8), (16, 8, 16)),
                cube((0, 8, -8), (8, 8, 8)),  # NE quarter only
            ],
        ),
    )
    # top (upside-down) mirrors
    dump(
        models / "stairs_inner_left_top.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_inner_left_top",
            [
                cube((-8, 8, -8), (16, 8, 16)),
                cube((-8, 0, -8), (16, 8, 8)),
                cube((-8, 0, 0), (8, 8, 8)),
            ],
        ),
    )
    dump(
        models / "stairs_inner_right_top.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_inner_right_top",
            [
                cube((-8, 8, -8), (16, 8, 16)),
                cube((-8, 0, -8), (16, 8, 8)),
                cube((0, 0, 0), (8, 8, 8)),
            ],
        ),
    )
    dump(
        models / "stairs_outer_left_top.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_outer_left_top",
            [
                cube((-8, 8, -8), (16, 8, 16)),
                cube((-8, 0, -8), (8, 8, 8)),
            ],
        ),
    )
    dump(
        models / "stairs_outer_right_top.geo.json",
        make_geometry(
            "geometry.rmbv.stairs_outer_right_top",
            [
                cube((-8, 8, -8), (16, 8, 16)),
                cube((0, 0, -8), (8, 8, 8)),
            ],
        ),
    )

    # --- Slabs ---
    dump(
        models / "slab_bottom.geo.json",
        make_geometry(
            "geometry.rmbv.slab_bottom",
            [cube((-8, 0, -8), (16, 8, 16))],
            1.0,
        ),
    )
    dump(
        models / "slab_top.geo.json",
        make_geometry(
            "geometry.rmbv.slab_top",
            [cube((-8, 8, -8), (16, 8, 16))],
            1.0,
        ),
    )

    # --- Fence: post + optional arms (separate geos for combinations via bones in one geo) ---
    # Post 4x16x4 centered (x/z 6-10 => -2..2 in model space from center: origin -2,0,-2 size 4,16,4)
    def fence_cubes(n, e, s, w):
        cubes = [cube((-2, 0, -2), (4, 16, 4))]
        # rails: two horizontal bars per direction at y ~6-9 and 12-15, thickness 2, from post to edge
        # Vanilla-ish: lower rail y 6-9, upper 12-15
        if n:
            cubes.append(cube((-1, 6, -8), (2, 3, 6)))
            cubes.append(cube((-1, 12, -8), (2, 3, 6)))
        if s:
            cubes.append(cube((-1, 6, 2), (2, 3, 6)))
            cubes.append(cube((-1, 12, 2), (2, 3, 6)))
        if e:
            cubes.append(cube((2, 6, -1), (6, 3, 2)))
            cubes.append(cube((2, 12, -1), (6, 3, 2)))
        if w:
            cubes.append(cube((-8, 6, -1), (6, 3, 2)))
            cubes.append(cube((-8, 12, -1), (6, 3, 2)))
        return cubes

    for mask in range(16):
        n = bool(mask & 8)
        e = bool(mask & 4)
        s = bool(mask & 2)
        w = bool(mask & 1)
        name = f"fence_{int(n)}{int(e)}{int(s)}{int(w)}"
        dump(
            models / f"{name}.geo.json",
            make_geometry(f"geometry.rmbv.{name}", fence_cubes(n, e, s, w), 1.5),
        )

    # --- Wall: post + short/tall arms ---
    def wall_cubes(post, n, e, s, w):
        # post: 8x16x8 centered? Vanilla wall post ~4 wide sometimes; use 8x14x8 for center post
        cubes = []
        if post:
            cubes.append(cube((-4, 0, -4), (8, 16, 8)))
        # short arms height 14, tall 16; width 8, from center to edge
        arms = {
            "n": n,
            "e": e,
            "s": s,
            "w": w,
        }
        for d, state in arms.items():
            if state == "none":
                continue
            h = 14 if state == "short" else 16
            if d == "n":
                cubes.append(cube((-4, 0, -8), (8, h, 4)))
            elif d == "s":
                cubes.append(cube((-4, 0, 4), (8, h, 4)))
            elif d == "e":
                cubes.append(cube((4, 0, -4), (4, h, 8)))
            elif d == "w":
                cubes.append(cube((-8, 0, -4), (4, h, 8)))
        if not cubes:
            cubes.append(cube((-4, 0, -4), (8, 16, 8)))
        return cubes

    # Generate a practical subset + generic post-only; full wall uses bone-like named geos for common + script-driven
    # For walls we use one multi-bone geometry and... actually Bedrock can't hide bones from block states without permutations.
    # Generate all combinations would be huge (3^4 * 2 = 162). Use simplified: connection trait style with short only for trial visual,
    # and script sets tall when block above is solid.
    # Practical approach: 16 connection patterns * post on/off * short vs all-tall flag is still large.
    # Generate: for each of 16 NESW bool connections, post true/false, height short/tall for all connected arms.
    for mask in range(16):
        n = "short" if mask & 8 else "none"
        e = "short" if mask & 4 else "none"
        s = "short" if mask & 2 else "none"
        w = "short" if mask & 1 else "none"
        for post in (True, False):
            if not post and mask in (0,):
                continue  # empty
            # skip no-post when not straight through
            name = f"wall_p{int(post)}_{int(bool(mask&8))}{int(bool(mask&4))}{int(bool(mask&2))}{int(bool(mask&1))}_short"
            dump(
                models / f"{name}.geo.json",
                make_geometry(
                    f"geometry.rmbv.{name}",
                    wall_cubes(post, n, e, s, w),
                    1.5,
                ),
            )
            name_t = name.replace("_short", "_tall")
            nt = "tall" if mask & 8 else "none"
            et = "tall" if mask & 4 else "none"
            st = "tall" if mask & 2 else "none"
            wt = "tall" if mask & 1 else "none"
            dump(
                models / f"{name_t}.geo.json",
                make_geometry(
                    f"geometry.rmbv.{name_t}",
                    wall_cubes(post, nt, et, st, wt),
                    1.5,
                ),
            )

    # --- Fence gate ---
    # Closed NS: posts at sides, bars across. Facing north means gate plane is EW.
    # Posts at x=±6 area, bars in middle
    dump(
        models / "gate_closed.geo.json",
        make_geometry(
            "geometry.rmbv.gate_closed",
            [
                cube((-8, 5, -1), (2, 11, 2)),  # west post
                cube((6, 5, -1), (2, 11, 2)),  # east post
                cube((-6, 6, -1), (12, 3, 2)),  # lower bar
                cube((-6, 12, -1), (12, 3, 2)),  # upper bar
                cube((-1, 6, -1), (2, 9, 2)),  # center brace
            ],
            1.5,
        ),
    )
    dump(
        models / "gate_open.geo.json",
        make_geometry(
            "geometry.rmbv.gate_open",
            [
                cube((-8, 5, -1), (2, 11, 2)),
                cube((6, 5, -1), (2, 11, 2)),
                # open: bars swung (simplified - posts only + thin open panels along sides)
                cube((-8, 6, -8), (2, 3, 7)),
                cube((-8, 12, -8), (2, 3, 7)),
                cube((6, 6, -8), (2, 3, 7)),
                cube((6, 12, -8), (2, 3, 7)),
            ],
            1.5,
        ),
    )
    dump(
        models / "gate_closed_inwall.geo.json",
        make_geometry(
            "geometry.rmbv.gate_closed_inwall",
            [
                cube((-8, 2, -1), (2, 11, 2)),
                cube((6, 2, -1), (2, 11, 2)),
                cube((-6, 3, -1), (12, 3, 2)),
                cube((-6, 9, -1), (12, 3, 2)),
                cube((-1, 3, -1), (2, 9, 2)),
            ],
            1.5,
        ),
    )
    dump(
        models / "gate_open_inwall.geo.json",
        make_geometry(
            "geometry.rmbv.gate_open_inwall",
            [
                cube((-8, 2, -1), (2, 11, 2)),
                cube((6, 2, -1), (2, 11, 2)),
                cube((-8, 3, -8), (2, 3, 7)),
                cube((-8, 9, -8), (2, 3, 7)),
                cube((6, 3, -8), (2, 3, 7)),
                cube((6, 9, -8), (2, 3, 7)),
            ],
            1.5,
        ),
    )


def material_instances() -> dict:
    # format_version 1.26.20+: ambient_occlusion must be float 0.0–10.0 (not bool).
    # Boolean true causes "invalid numeric value" and rejects the whole block.
    return {
        "*": {
            "texture": TEX,
            "render_method": "opaque",
            "ambient_occlusion": 1.0,
            "face_dimming": True,
        }
    }


def base_components(extra: dict | None = None) -> dict:
    c = {
        "minecraft:material_instances": material_instances(),
        "minecraft:destructible_by_mining": {"seconds_to_destroy": DESTROY},
        "minecraft:destructible_by_explosion": {"explosion_resistance": EXPLODE},
        "minecraft:friction": FRICTION,
        "minecraft:flammable": {
            "catch_chance_modifier": 0,
            "destroy_chance_modifier": 0,
        },
        "minecraft:light_emission": 0,
        "minecraft:light_dampening": 15,
        "minecraft:map_color": "#A65E3B",
    }
    if extra:
        # format_version 1.26+: tags use "minecraft:tags": ["a","b"]
        # Legacy "tag:name": {} components are rejected by the schema.
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
            # preserve order, drop dupes
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
    # Geometry default faces north; rotate Y so cardinal matches
    return {"north": 0.0, "east": -90.0, "south": 180.0, "west": 90.0}[direction]


def rot_comp(direction: str) -> dict:
    return {"minecraft:transformation": {"rotation": [0, dir_yaw(direction), 0]}}


def stairs_collision(corner: str, half: str) -> list:
    """Collision boxes matching stair shape (bottom, north-facing base)."""
    if half == "bottom":
        base = [box((-8, 0, -8), (16, 8, 16))]
        if corner == "none":
            return base + [box((-8, 8, -8), (16, 8, 8))]
        if corner == "inner_left":
            return base + [
                box((-8, 8, -8), (16, 8, 8)),
                box((-8, 8, 0), (8, 8, 8)),
            ]
        if corner == "inner_right":
            return base + [
                box((-8, 8, -8), (16, 8, 8)),
                box((0, 8, 0), (8, 8, 8)),
            ]
        if corner == "outer_left":
            return base + [box((-8, 8, -8), (8, 8, 8))]
        if corner == "outer_right":
            return base + [box((0, 8, -8), (8, 8, 8))]
    else:
        base = [box((-8, 8, -8), (16, 8, 16))]
        if corner == "none":
            return base + [box((-8, 0, -8), (16, 8, 8))]
        if corner == "inner_left":
            return base + [
                box((-8, 0, -8), (16, 8, 8)),
                box((-8, 0, 0), (8, 8, 8)),
            ]
        if corner == "inner_right":
            return base + [
                box((-8, 0, -8), (16, 8, 8)),
                box((0, 0, 0), (8, 8, 8)),
            ]
        if corner == "outer_left":
            return base + [box((-8, 0, -8), (8, 8, 8))]
        if corner == "outer_right":
            return base + [box((0, 0, -8), (8, 8, 8))]
    return base


def flip_stair_corner(corner: str) -> str:
    """Map trait corner → mesh/collision corner.

    Working robmodbr script intentionally swaps left↔right vs vanilla CCW
    naming so the rendered L matches in-world (Bedrock X-mirror). The same
    swap is required when driving meshes from minecraft:corner trait values.
    """
    return {
        "none": "none",
        "inner_left": "inner_right",
        "inner_right": "inner_left",
        "outer_left": "outer_right",
        "outer_right": "outer_left",
    }.get(corner, corner)


def stairs_geo(corner: str, half: str) -> str:
    # corner is already flip_stair_corner()'d by the caller
    mapping = {
        ("none", "bottom"): "geometry.rmbv.stairs_straight_bottom",
        ("none", "top"): "geometry.rmbv.stairs_straight_top",
        ("inner_left", "bottom"): "geometry.rmbv.stairs_inner_left_bottom",
        ("inner_right", "bottom"): "geometry.rmbv.stairs_inner_right_bottom",
        ("outer_left", "bottom"): "geometry.rmbv.stairs_outer_left_bottom",
        ("outer_right", "bottom"): "geometry.rmbv.stairs_outer_right_bottom",
        ("inner_left", "top"): "geometry.rmbv.stairs_inner_left_top",
        ("inner_right", "top"): "geometry.rmbv.stairs_inner_right_top",
        ("outer_left", "top"): "geometry.rmbv.stairs_outer_left_top",
        ("outer_right", "top"): "geometry.rmbv.stairs_outer_right_top",
    }
    return mapping[(corner, half)]


def write_full_block() -> None:
    # menu_category.group must be a real item group (or omitted).
    # "itemGroup.name.construction" is invalid — construction is a tab, not a group.
    # Invalid groups can prevent the auto block-item from registering (no /give, no creative).
    dump(
        BP / "blocks" / f"{BLOCK}.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_FULL,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.stoneBrick",
                    },
                },
                "components": base_components(
                    {
                        "minecraft:geometry": "minecraft:geometry.full_block",
                        "minecraft:collision_box": True,
                        "minecraft:selection_box": True,
                        "tag:rmbv:source_block": {},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}.json",
                    }
                ),
            },
        },
    )


def write_stairs() -> None:
    permutations = []
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
                permutations.append(
                    {
                        "condition": (
                            f"q.block_state('minecraft:cardinal_direction') == '{direction}'"
                            f" && q.block_state('minecraft:vertical_half') == '{half}'"
                            f" && q.block_state('minecraft:corner') == '{corner}'"
                        ),
                        "components": {
                            "minecraft:geometry": stairs_geo(mesh_corner, half),
                            "minecraft:collision_box": coll,
                            "minecraft:selection_box": selection_from_boxes(coll),
                            **rot_comp(direction),
                        },
                    }
                )

    dump(
        BP / "blocks" / f"{BLOCK}_stairs.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_STAIRS,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.stairs",
                    },
                    "traits": {
                        "minecraft:placement_position": {
                            "enabled_states": ["minecraft:vertical_half"]
                        },
                        "minecraft:placement_direction": {
                            "enabled_states": [
                                "minecraft:corner_and_cardinal_direction"
                            ],
                            "blocks_to_corner_with": [
                                {
                                    "tags": "q.any_tag('minecraft:cornerable_stairs')"
                                }
                            ],
                        },
                    },
                },
                "components": base_components(
                    {
                        "tag:minecraft:cornerable_stairs": {},
                        "tag:rmbv:stairs": {},
                        "minecraft:geometry": "geometry.rmbv.stairs_straight_bottom",
                        "minecraft:collision_box": stairs_collision("none", "bottom"),
                        "minecraft:selection_box": selection_from_boxes(
                            stairs_collision("none", "bottom")
                        ),
                        "minecraft:support": {"shape": "stair"},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}_stairs.json",
                    }
                ),
                "permutations": permutations,
            },
        },
    )


def write_slab() -> None:
    bottom_box = box((-8, 0, -8), (16, 8, 16))
    top_box = box((-8, 8, -8), (16, 8, 16))
    # Explicit full AABB (boolean true can fail solid-face placement for some builds)
    full_box = box((-8, 0, -8), (16, 16, 16))

    dump(
        BP / "blocks" / f"{BLOCK}_slab.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_SLAB,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.slab",
                    },
                    "states": {
                        "rmbv:slab_type": ["bottom", "top", "double"]
                    },
                    "traits": {
                        "minecraft:placement_position": {
                            "enabled_states": ["minecraft:vertical_half"]
                        }
                    },
                },
                "components": base_components(
                    {
                        "tag:rmbv:slab": {},
                        "tag:rmbv:slab_brbrickblock_001": {},
                        "minecraft:geometry": "geometry.rmbv.slab_bottom",
                        "minecraft:collision_box": bottom_box,
                        "minecraft:selection_box": bottom_box,
                        # 1.26+: custom components are applied as direct component keys
                        # (minecraft:custom_components array was removed from schema)
                        "rmbv:slab_stacking": {},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}_slab.json",
                    }
                ),
                # Last matching permutation wins — double must be last.
                "permutations": [
                    {
                        "condition": "q.block_state('rmbv:slab_type') == 'bottom'",
                        "components": {
                            "minecraft:geometry": "geometry.rmbv.slab_bottom",
                            "minecraft:collision_box": bottom_box,
                            "minecraft:selection_box": bottom_box,
                            "minecraft:light_dampening": 0,
                        },
                    },
                    {
                        "condition": "q.block_state('rmbv:slab_type') == 'top'",
                        "components": {
                            "minecraft:geometry": "geometry.rmbv.slab_top",
                            "minecraft:collision_box": top_box,
                            "minecraft:selection_box": top_box,
                            "minecraft:light_dampening": 0,
                        },
                    },
                    {
                        "condition": "q.block_state('rmbv:slab_type') == 'double'",
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


def fence_collision(n, e, s, w) -> list:
    # 1.5 block height (24 pixels)
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


def write_fence() -> None:
    """Script-driven conn mask (rmbv:conn 0–15).

    BIT: north=0, south=1, east=2, west=3 (world space from script).

    Screenshot evidence (pairs with arms pointing *outward*): Bedrock displays
    these BVS meshes with X mirrored, so world east must use the west arm mesh
    and vice versa. Z (N/S) is already correct in the geo files — do not swap.
    """
    permutations = []
    for mask in range(16):
        n = bool(mask & (1 << 0))
        s = bool(mask & (1 << 1))
        e = bool(mask & (1 << 2))
        w = bool(mask & (1 << 3))
        # E↔W mesh swap only (X-mirror). Name pattern fence_{N}{E}{S}{W}.
        name = f"geometry.rmbv.fence_{int(n)}{int(w)}{int(s)}{int(e)}"
        coll = fence_collision(n, w, s, e)
        permutations.append(
            {
                "condition": f"q.block_state('rmbv:conn') == {mask}",
                "components": {
                    "minecraft:geometry": name,
                    "minecraft:collision_box": coll,
                    "minecraft:selection_box": selection_from_boxes(coll),
                },
            }
        )

    root_coll = fence_collision(False, False, False, False)
    dump(
        BP / "blocks" / f"{BLOCK}_fence.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_FENCE,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.fence",
                    },
                    "states": {
                        "rmbv:conn": list(range(16)),
                    },
                },
                "components": base_components(
                    {
                        "tag:minecraft:has_fence_connections": {},
                        "tag:rmbv:fence": {},
                        "minecraft:connection_rule": {
                            "accepts_connections_from": "only_fences"
                        },
                        "minecraft:support": {"shape": "fence"},
                        "minecraft:geometry": "geometry.rmbv.fence_0000",
                        "minecraft:collision_box": root_coll,
                        "minecraft:selection_box": selection_from_boxes(root_coll),
                        "minecraft:light_dampening": 0,
                        "rmbv:fence_update": {},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}_fence.json",
                    }
                ),
                "permutations": permutations,
            },
        },
    )


def wall_collision(post, n, e, s, w, tall: bool) -> list:
    h = 24  # barrier height
    boxes = []
    if post:
        boxes.append(box((-4, 0, -4), (8, h, 8)))
    arm_h = h
    if n != "none":
        boxes.append(box((-4, 0, -8), (8, arm_h, 4)))
    if s != "none":
        boxes.append(box((-4, 0, 4), (8, arm_h, 4)))
    if e != "none":
        boxes.append(box((4, 0, -4), (4, arm_h, 8)))
    if w != "none":
        boxes.append(box((-8, 0, -4), (4, arm_h, 8)))
    if not boxes:
        boxes.append(box((-4, 0, -4), (8, h, 8)))
    return boxes


def write_wall() -> None:
    permutations = []
    for mask in range(16):
        for post in (True, False):
            if not post and mask == 0:
                continue
            for height in ("short", "tall"):
                n = height if mask & 8 else "none"
                e = height if mask & 4 else "none"
                s = height if mask & 2 else "none"
                w = height if mask & 1 else "none"
                # For mixed short/tall per side we approximate: all arms same height tier
                # Real short/tall per-side uses states below; geo name uses connection bools
                geo = f"geometry.rmbv.wall_p{int(post)}_{int(bool(mask&8))}{int(bool(mask&4))}{int(bool(mask&2))}{int(bool(mask&1))}_{height}"
                coll = wall_collision(post, n, e, s, w, height == "tall")
                cond = (
                    f"q.block_state('rmbv:wall_n') == '{n if n != 'none' else 'none'}'"
                    f" && q.block_state('rmbv:wall_e') == '{e if e != 'none' else 'none'}'"
                    f" && q.block_state('rmbv:wall_s') == '{s if s != 'none' else 'none'}'"
                    f" && q.block_state('rmbv:wall_w') == '{w if w != 'none' else 'none'}'"
                    f" && q.block_state('rmbv:wall_post') == {'true' if post else 'false'}"
                )
                # Problem: states are per-side short|tall|none but we only generate uniform height geos.
                # Fix: use individual side states properly with simplified visual:
                # For trial, store height per side but only two visual tiers when ANY side is tall.
                permutations.append(
                    {
                        "condition": cond,
                        "components": {
                            "minecraft:geometry": geo,
                            "minecraft:collision_box": coll,
                            "minecraft:selection_box": coll,
                        },
                    }
                )

    # Also need mixed short/tall permutations - for trial simplify: each side independent via states
    # Rebuild with proper per-side states - geometries only for uniform. Mixed uses short geo as fallback.
    # Actually rewrite wall more carefully with 3^4*2 = 162 perms is large but OK for trial one block.

    perms2 = []
    sides = ("none", "short", "tall")
    count = 0
    for n in sides:
        for e in sides:
            for s in sides:
                for w in sides:
                    for post in (True, False):
                        if not post and n == e == s == w == "none":
                            continue
                        # Pick geo: if any tall use tall mask of connected, else short
                        mask = (
                            (8 if n != "none" else 0)
                            | (4 if e != "none" else 0)
                            | (2 if s != "none" else 0)
                            | (1 if w != "none" else 0)
                        )
                        height = (
                            "tall"
                            if any(x == "tall" for x in (n, e, s, w))
                            else "short"
                        )
                        # Screenshots: N–S wall lines join; E–W lines leave gaps
                        # (arms point outward). BVS meshes are X-mirrored in-game:
                        # world east connection must use west arm mesh and vice versa.
                        # N/S (Z) geos match world — do not swap.
                        gn = 1 if n != "none" else 0
                        ge = 1 if w != "none" else 0  # E↔W swap
                        gs = 1 if s != "none" else 0
                        gw = 1 if e != "none" else 0  # E↔W swap
                        if gn == ge == gs == gw == 0 and post:
                            geo = "geometry.rmbv.wall_p1_0000_short"
                        else:
                            geo = (
                                f"geometry.rmbv.wall_p{int(post)}_"
                                f"{gn}{ge}{gs}{gw}_{height}"
                            )
                        # Collision follows same E↔W visual swap
                        coll = wall_collision(
                            post, n, w, s, e, height == "tall"
                        )
                        perms2.append(
                            {
                                "condition": (
                                    f"q.block_state('rmbv:wall_n') == '{n}'"
                                    f" && q.block_state('rmbv:wall_e') == '{e}'"
                                    f" && q.block_state('rmbv:wall_s') == '{s}'"
                                    f" && q.block_state('rmbv:wall_w') == '{w}'"
                                    f" && q.block_state('rmbv:wall_post') == {'true' if post else 'false'}"
                                ),
                                "components": {
                                    "minecraft:geometry": geo,
                                    "minecraft:collision_box": coll,
                                    "minecraft:selection_box": selection_from_boxes(coll),
                                },
                            }
                        )
                        count += 1

    root_wall = wall_collision(True, "none", "none", "none", "none", False)
    dump(
        BP / "blocks" / f"{BLOCK}_wall.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_WALL,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.walls",
                    },
                    "states": {
                        "rmbv:wall_n": ["none", "short", "tall"],
                        "rmbv:wall_e": ["none", "short", "tall"],
                        "rmbv:wall_s": ["none", "short", "tall"],
                        "rmbv:wall_w": ["none", "short", "tall"],
                        "rmbv:wall_post": [True, False],
                    },
                },
                "components": base_components(
                    {
                        "tag:rmbv:wall": {},
                        "minecraft:geometry": "geometry.rmbv.wall_p1_0000_short",
                        "minecraft:collision_box": root_wall,
                        "minecraft:selection_box": selection_from_boxes(root_wall),
                        "minecraft:light_dampening": 0,
                        "rmbv:wall_update": {},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}_wall.json",
                    }
                ),
                "permutations": perms2,
            },
        },
    )
    print(f"Wall permutations: {count}")


def write_gate() -> None:
    closed_coll = [box((-8, 0, -2), (16, 24, 4))]
    open_coll = [
        box((-8, 0, -2), (2, 24, 4)),
        box((6, 0, -2), (2, 24, 4)),
    ]
    permutations = []
    for direction in ("north", "east", "south", "west"):
        for open_ in (False, True):
            for in_wall in (False, True):
                if open_ and in_wall:
                    geo = "geometry.rmbv.gate_open_inwall"
                elif open_:
                    geo = "geometry.rmbv.gate_open"
                elif in_wall:
                    geo = "geometry.rmbv.gate_closed_inwall"
                else:
                    geo = "geometry.rmbv.gate_closed"
                coll = open_coll if open_ else closed_coll
                permutations.append(
                    {
                        "condition": (
                            f"q.block_state('minecraft:cardinal_direction') == '{direction}'"
                            f" && q.block_state('rmbv:open') == {'true' if open_ else 'false'}"
                            f" && q.block_state('rmbv:in_wall') == {'true' if in_wall else 'false'}"
                        ),
                        "components": {
                            "minecraft:geometry": geo,
                            "minecraft:collision_box": coll,
                            "minecraft:selection_box": selection_from_boxes(coll),
                            **rot_comp(direction),
                        },
                    }
                )

    dump(
        BP / "blocks" / f"{BLOCK}_fence_gate.json",
        {
            "format_version": FORMAT,
            "minecraft:block": {
                "description": {
                    "identifier": ID_GATE,
                    "menu_category": {
                        "category": "construction",
                        "group": "minecraft:itemGroup.name.fenceGates",
                    },
                    "states": {
                        "rmbv:open": [False, True],
                        "rmbv:powered": [False, True],
                        "rmbv:in_wall": [False, True],
                    },
                    "traits": {
                        "minecraft:placement_direction": {
                            "enabled_states": ["minecraft:cardinal_direction"]
                        }
                    },
                },
                "components": base_components(
                    {
                        "tag:rmbv:fence_gate": {},
                        "tag:minecraft:has_fence_connections": {},
                        "minecraft:connection_rule": {
                            "accepts_connections_from": "all"
                        },
                        "minecraft:geometry": "geometry.rmbv.gate_closed",
                        "minecraft:collision_box": closed_coll,
                        "minecraft:selection_box": selection_from_boxes(closed_coll),
                        "minecraft:light_dampening": 0,
                        "minecraft:redstone_consumer": {
                            "min_power": 1,
                            "propagates_power": False,
                        },
                        "rmbv:fence_gate": {},
                        "minecraft:loot": f"loot_tables/blocks/{BLOCK}_fence_gate.json",
                    }
                ),
                "permutations": permutations,
            },
        },
    )


def write_loot_and_recipes() -> None:
    simple_ids = [
        (BLOCK, ID_FULL, 1),
        (f"{BLOCK}_stairs", ID_STAIRS, 1),
        (f"{BLOCK}_slab", ID_SLAB, 1),
        (f"{BLOCK}_fence", ID_FENCE, 1),
        (f"{BLOCK}_wall", ID_WALL, 1),
        (f"{BLOCK}_fence_gate", ID_GATE, 1),
    ]
    for file_stem, identifier, count in simple_ids:
        dump(
            BP / "loot_tables" / "blocks" / f"{file_stem}.json",
            {
                "pools": [
                    {
                        "rolls": 1,
                        "entries": [
                            {
                                "type": "item",
                                "name": identifier,
                                "weight": 1,
                                "functions": [
                                    {
                                        "function": "set_count",
                                        "count": count,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        )

    # Recipes (1.20+ require unlock data)
    unlock_full = [{"item": ID_FULL}]

    dump(
        BP / "recipes" / f"{BLOCK}_stairs.json",
        {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{BLOCK}_stairs"},
                "tags": ["crafting_table"],
                "pattern": ["#  ", "## ", "###"],
                "key": {"#": {"item": ID_FULL}},
                "unlock": unlock_full,
                "result": {"item": ID_STAIRS, "count": 4},
            },
        },
    )
    dump(
        BP / "recipes" / f"{BLOCK}_slab.json",
        {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{BLOCK}_slab"},
                "tags": ["crafting_table"],
                "pattern": ["###"],
                "key": {"#": {"item": ID_FULL}},
                "unlock": unlock_full,
                "result": {"item": ID_SLAB, "count": 6},
            },
        },
    )
    dump(
        BP / "recipes" / f"{BLOCK}_fence.json",
        {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{BLOCK}_fence"},
                "tags": ["crafting_table"],
                "pattern": ["#S#", "#S#"],
                "key": {
                    "#": {"item": ID_FULL},
                    "S": {"item": "minecraft:stick"},
                },
                "unlock": unlock_full,
                "result": {"item": ID_FENCE, "count": 3},
            },
        },
    )
    dump(
        BP / "recipes" / f"{BLOCK}_wall.json",
        {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{BLOCK}_wall"},
                "tags": ["crafting_table"],
                "pattern": ["###", "###"],
                "key": {"#": {"item": ID_FULL}},
                "unlock": unlock_full,
                "result": {"item": ID_WALL, "count": 6},
            },
        },
    )
    dump(
        BP / "recipes" / f"{BLOCK}_fence_gate.json",
        {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{BLOCK}_fence_gate"},
                "tags": ["crafting_table"],
                "pattern": ["S#S", "S#S"],
                "key": {
                    "#": {"item": ID_FULL},
                    "S": {"item": "minecraft:stick"},
                },
                "unlock": unlock_full,
                "result": {"item": ID_GATE, "count": 1},
            },
        },
    )


def write_resource_meta() -> None:
    dump(
        RP / "textures" / "terrain_texture.json",
        {
            "resource_pack_name": "rmbv_trial",
            "texture_name": "atlas.terrain",
            "padding": 8,
            "num_mip_levels": 0,
            "texture_data": {
                TEX: {"textures": ["textures/blocks/brushedbrick_001"]}
            },
        },
    )

    blocks_json = {
        "format_version": "1.21.40",
    }
    for bid in (ID_FULL, ID_STAIRS, ID_SLAB, ID_FENCE, ID_WALL, ID_GATE):
        blocks_json[bid] = {"sound": SOUND}
    dump(RP / "blocks.json", blocks_json)

    lang = "\n".join(
        [
            f"tile.{ID_FULL}.name=Brushed Brick Block 001",
            f"tile.{ID_STAIRS}.name=Brushed Brick Stairs 001",
            f"tile.{ID_SLAB}.name=Brushed Brick Slab 001",
            f"tile.{ID_FENCE}.name=Brushed Brick Fence 001",
            f"tile.{ID_WALL}.name=Brushed Brick Wall 001",
            f"tile.{ID_GATE}.name=Brushed Brick Fence Gate 001",
            "pack.name=Rob Mod BR Variants Trial",
            "pack.description=Trial: brbrickblock_001 stairs/slab/fence/wall/gate (vanilla-compatible traits)",
            "",
        ]
    )
    (RP / "texts" / "en_US.lang").write_text(lang, encoding="utf-8")
    (RP / "texts" / "languages.json").write_text(
        json.dumps(["en_US"], indent=2) + "\n", encoding="utf-8"
    )


def write_manifests() -> None:
    bp_header = "fd282690-f32b-4d87-a4f7-a20232c1d574"
    bp_data = "c4fbaafb-d89d-4ea6-b588-9fa25cc8340d"
    bp_script = "00883d01-14e9-4fa1-aa1c-b53d1ee95c7e"
    rp_header = "7d226c7e-3411-4e9d-92a3-bab9cb83ce4a"
    rp_res = "f31fd83c-fa34-402f-81fa-fed057fcdda5"
    pack_ver = [1, 0, 7]

    dump(
        BP / "manifest.json",
        {
            "format_version": 2,
            "header": {
                "name": "Rob Mod BR Variants Trial BP",
                "description": "Trial behaviour pack: brbrickblock_001 variants only. Does not modify original Rob Mod.",
                "uuid": bp_header,
                "version": pack_ver,
                "min_engine_version": [1, 26, 0],
            },
            "modules": [
                {
                    "type": "data",
                    "uuid": bp_data,
                    "version": pack_ver,
                },
                {
                    "type": "script",
                    "language": "javascript",
                    "uuid": bp_script,
                    "version": pack_ver,
                    "entry": "scripts/main.js",
                },
            ],
            "dependencies": [
                {
                    "uuid": rp_header,
                    "version": pack_ver,
                },
                {
                    "module_name": "@minecraft/server",
                    "version": "2.0.0",
                },
            ],
            "metadata": {
                "authors": ["RobbieB", "Grok Build Trial"],
                "product_type": "addon",
            },
        },
    )

    dump(
        RP / "manifest.json",
        {
            "format_version": 2,
            "header": {
                "name": "Rob Mod BR Variants Trial RP",
                "description": "Trial resource pack: brbrickblock_001 variant geometries and textures.",
                "uuid": rp_header,
                "version": pack_ver,
                "min_engine_version": [1, 26, 0],
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": rp_res,
                    "version": pack_ver,
                }
            ],
            "capabilities": ["pbr"],
            "metadata": {
                "authors": ["RobbieB", "Grok Build Trial"],
                "product_type": "addon",
            },
        },
    )


def write_scripts() -> None:
    main_js = r'''import {
  system,
  world,
  BlockPermutation,
  GameMode,
  ItemStack,
} from "@minecraft/server";

const SLAB_ID = "rmbv:brbrickblock_001_slab";
const FULL_ID = "rmbv:brbrickblock_001";
const FENCE_ID = "rmbv:brbrickblock_001_fence";
const WALL_ID = "rmbv:brbrickblock_001_wall";
const GATE_ID = "rmbv:brbrickblock_001_fence_gate";
const CONN_STATE = "rmbv:conn";
// Same bit layout as working robmodbr pack
const BIT = { north: 0, south: 1, east: 2, west: 3 };
const CONN_DIRS = ["north", "south", "east", "west"];

const DIR_OFFSET = {
  north: { x: 0, y: 0, z: -1 },
  south: { x: 0, y: 0, z: 1 },
  east: { x: 1, y: 0, z: 0 },
  west: { x: -1, y: 0, z: 0 },
  up: { x: 0, y: 1, z: 0 },
  down: { x: 0, y: -1, z: 0 },
};

const FACE_TO_DIR = {
  Up: "up",
  up: "up",
  Down: "down",
  down: "down",
  North: "north",
  north: "north",
  South: "south",
  south: "south",
  East: "east",
  east: "east",
  West: "west",
  west: "west",
};

function neighbor(block, dir) {
  if (!block || !block.isValid) return undefined;
  const d = DIR_OFFSET[dir];
  if (!d) return undefined;
  const { x, y, z } = block.location;
  return block.dimension.getBlock({ x: x + d.x, y: y + d.y, z: z + d.z });
}

function canFenceConnect(other) {
  if (!other || !other.isValid || other.isAir || other.isLiquid) return false;
  const id = other.typeId;
  if (id === FENCE_ID || id === GATE_ID) return true;
  if (id.includes("fence_gate") || id.includes("fencegate")) return true;
  if (id.includes("fence")) return true;
  return false;
}

function setFenceMask(block, mask) {
  try {
    block.setPermutation(
      BlockPermutation.resolve(FENCE_ID, { [CONN_STATE]: mask })
    );
  } catch (err) {
    console.warn(`rmbv setFenceMask failed: ${err}`);
  }
}

function updateFence(block) {
  if (!block || !block.isValid || block.typeId !== FENCE_ID) return;
  let mask = 0;
  if (canFenceConnect(neighbor(block, "north"))) mask |= 1 << BIT.north;
  if (canFenceConnect(neighbor(block, "south"))) mask |= 1 << BIT.south;
  if (canFenceConnect(neighbor(block, "east"))) mask |= 1 << BIT.east;
  if (canFenceConnect(neighbor(block, "west"))) mask |= 1 << BIT.west;
  try {
    const cur = block.permutation.getState(CONN_STATE);
    if (cur === mask) return;
  } catch (_) {}
  setFenceMask(block, mask);
}

function updateFenceNeighborhood(block) {
  if (!block || !block.isValid) return;
  updateFence(block);
  for (const d of CONN_DIRS) {
    const n = neighbor(block, d);
    if (n && n.typeId === FENCE_ID) updateFence(n);
  }
}

function isSolidForWall(block) {
  if (!block || !block.isValid) return false;
  if (block.isAir || block.isLiquid) return false;
  const id = block.typeId;
  if (id === WALL_ID) return true;
  if (id === GATE_ID) return true;
  if (id.endsWith("_fence") || id.includes("fence")) return true;
  // Treat most full blocks as connectable
  try {
    if (block.permutation?.getState) {
      // custom walls
    }
  } catch (_) {}
  // Exclude known non-solid-ish
  if (
    id.includes("slab") ||
    id.includes("stairs") ||
    id.includes("button") ||
    id.includes("pressure_plate") ||
    id.includes("torch") ||
    id.includes("sign") ||
    id.includes("carpet") ||
    id.includes("rail")
  ) {
    return false;
  }
  return true;
}

function isWallBlock(block) {
  return block && block.isValid && block.typeId === WALL_ID;
}

function sideConnection(self, neighbor, aboveNeighbor) {
  if (!neighbor || !neighbor.isValid || neighbor.isAir) return "none";
  if (isWallBlock(neighbor) || neighbor.typeId === GATE_ID) {
    // tall if block above the wall connection needs it (solid above neighbor or self)
    const tall =
      (aboveNeighbor && isSolidForWall(aboveNeighbor)) ||
      false;
    return tall ? "tall" : "short";
  }
  if (isSolidForWall(neighbor)) {
    // solid full blocks connect short, tall if solid above neighbor
    return aboveNeighbor && isSolidForWall(aboveNeighbor) ? "tall" : "short";
  }
  return "none";
}

function recomputeWall(block) {
  if (!block || !block.isValid || block.typeId !== WALL_ID) return;
  const dim = block.dimension;
  const { x, y, z } = block.location;

  const n = dim.getBlock({ x, y, z: z - 1 });
  const e = dim.getBlock({ x: x + 1, y, z });
  const s = dim.getBlock({ x, y, z: z + 1 });
  const w = dim.getBlock({ x: x - 1, y, z });
  const above = dim.getBlock({ x, y: y + 1, z });

  const wall_n = sideConnection(block, n, n && dim.getBlock({ x: n.x, y: y + 1, z: n.z }));
  const wall_e = sideConnection(block, e, e && dim.getBlock({ x: e.x, y: y + 1, z: e.z }));
  const wall_s = sideConnection(block, s, s && dim.getBlock({ x: s.x, y: y + 1, z: s.z }));
  const wall_w = sideConnection(block, w, w && dim.getBlock({ x: w.x, y: y + 1, z: w.z }));

  // Post: usually true; false only for clean straight short section
  let post = true;
  const vals = [wall_n, wall_e, wall_s, wall_w];
  const connected = vals.filter((v) => v !== "none");
  const straightNS =
    wall_n !== "none" &&
    wall_s !== "none" &&
    wall_e === "none" &&
    wall_w === "none" &&
    wall_n === "short" &&
    wall_s === "short";
  const straightEW =
    wall_e !== "none" &&
    wall_w !== "none" &&
    wall_n === "none" &&
    wall_s === "none" &&
    wall_e === "short" &&
    wall_w === "short";
  const forcePost = above && isSolidForWall(above);
  if ((straightNS || straightEW) && !forcePost) {
    post = false;
  }
  if (connected.length === 0) post = true;

  try {
    block.setPermutation(
      BlockPermutation.resolve(WALL_ID, {
        "rmbv:wall_n": wall_n,
        "rmbv:wall_e": wall_e,
        "rmbv:wall_s": wall_s,
        "rmbv:wall_w": wall_w,
        "rmbv:wall_post": post,
      })
    );
  } catch (err) {
    console.warn(`rmbv wall update failed: ${err}`);
  }
}

function updateNearbyWalls(block) {
  if (!block || !block.isValid) return;
  const dim = block.dimension;
  const { x, y, z } = block.location;
  const positions = [
    { x, y, z },
    { x, y, z: z - 1 },
    { x: x + 1, y, z },
    { x, y, z: z + 1 },
    { x: x - 1, y, z },
    { x, y: y + 1, z },
    { x, y: y - 1, z },
  ];
  for (const p of positions) {
    const b = dim.getBlock(p);
    if (b && b.typeId === WALL_ID) recomputeWall(b);
  }
}

function updateGateInWall(block) {
  if (!block || !block.isValid || block.typeId !== GATE_ID) return;
  const dir = block.permutation.getState("minecraft:cardinal_direction") ?? "north";
  const dim = block.dimension;
  const { x, y, z } = block.location;
  // Walls on sides perpendicular to facing
  let a, b;
  if (dir === "north" || dir === "south") {
    a = dim.getBlock({ x: x - 1, y, z });
    b = dim.getBlock({ x: x + 1, y, z });
  } else {
    a = dim.getBlock({ x, y, z: z - 1 });
    b = dim.getBlock({ x, y, z: z + 1 });
  }
  const inWall =
    !!(a && (a.typeId === WALL_ID || a.typeId.includes("wall"))) &&
    !!(b && (b.typeId === WALL_ID || b.typeId.includes("wall")));

  const open = !!block.permutation.getState("rmbv:open");
  const powered = !!block.permutation.getState("rmbv:powered");
  try {
    block.setPermutation(
      BlockPermutation.resolve(GATE_ID, {
        "minecraft:cardinal_direction": dir,
        "rmbv:open": open,
        "rmbv:powered": powered,
        "rmbv:in_wall": inWall,
      })
    );
  } catch (err) {
    console.warn(`rmbv gate in_wall failed: ${err}`);
  }
}

system.beforeEvents.startup.subscribe((init) => {
  // --- Slab stacking (logic in playerInteractWithBlock) ---
  init.blockComponentRegistry.registerCustomComponent("rmbv:slab_stacking", {});

  // --- Fence connections (script-driven rmbv:conn) ---
  init.blockComponentRegistry.registerCustomComponent("rmbv:fence_update", {
    onPlace(event) {
      system.run(() => updateFenceNeighborhood(event.block));
    },
    onPlayerBreak(event) {
      const loc = event.block.location;
      const dim = event.dimension ?? event.block.dimension;
      system.run(() => {
        for (const d of CONN_DIRS) {
          const off = DIR_OFFSET[d];
          const b = dim.getBlock({
            x: loc.x + off.x,
            y: loc.y + off.y,
            z: loc.z + off.z,
          });
          if (b && b.typeId === FENCE_ID) updateFence(b);
        }
      });
    },
  });

  // --- Wall update ---
  init.blockComponentRegistry.registerCustomComponent("rmbv:wall_update", {
    onPlace(event) {
      system.run(() => {
        updateNearbyWalls(event.block);
        updateFenceNeighborhood(event.block);
      });
    },
    onPlayerBreak(event) {
      const loc = event.block.location;
      const dim = event.dimension ?? event.block.dimension;
      system.run(() => {
        // Neighbours need update after break
        const positions = [
          { x: loc.x, y: loc.y, z: loc.z - 1 },
          { x: loc.x + 1, y: loc.y, z: loc.z },
          { x: loc.x, y: loc.y, z: loc.z + 1 },
          { x: loc.x - 1, y: loc.y, z: loc.z },
          { x: loc.x, y: loc.y + 1, z: loc.z },
        ];
        for (const p of positions) {
          const b = dim.getBlock(p);
          if (b && b.typeId === WALL_ID) recomputeWall(b);
          if (b && b.typeId === FENCE_ID) updateFence(b);
        }
      });
    },
  });

  // --- Fence gate ---
  init.blockComponentRegistry.registerCustomComponent("rmbv:fence_gate", {
    onPlace(event) {
      system.run(() => {
        updateGateInWall(event.block);
        updateNearbyWalls(event.block);
      });
    },
    onPlayerInteract(event) {
      const block = event.block;
      if (!block || block.typeId !== GATE_ID) return;
      const powered = !!block.permutation.getState("rmbv:powered");
      if (powered) return; // redstone-locked open/closed follows power only when unpowered toggle allowed
      // Vanilla: player can still toggle when not powered; when powered gate stays forced
      // Spec: unpowered gates toggle
      const open = !!block.permutation.getState("rmbv:open");
      const dir =
        block.permutation.getState("minecraft:cardinal_direction") ?? "north";
      const inWall = !!block.permutation.getState("rmbv:in_wall");
      const next = !open;
      system.run(() => {
        try {
          block.setPermutation(
            BlockPermutation.resolve(GATE_ID, {
              "minecraft:cardinal_direction": dir,
              "rmbv:open": next,
              "rmbv:powered": powered,
              "rmbv:in_wall": inWall,
            })
          );
          block.dimension.playSound(
            next ? "open.fence_gate" : "close.fence_gate",
            block.location
          );
        } catch (err) {
          console.warn(`rmbv gate toggle failed: ${err}`);
        }
      });
    },
    onRedstoneUpdate(event) {
      const block = event.block;
      if (!block || block.typeId !== GATE_ID) return;
      const power = event.power ?? event.redstonePower ?? 0;
      const poweredNow = power > 0;
      const wasPowered = !!block.permutation.getState("rmbv:powered");
      const wasOpen = !!block.permutation.getState("rmbv:open");
      const dir =
        block.permutation.getState("minecraft:cardinal_direction") ?? "north";
      const inWall = !!block.permutation.getState("rmbv:in_wall");

      let open = wasOpen;
      if (poweredNow && !wasPowered) {
        open = true;
      } else if (!poweredNow && wasPowered) {
        open = false;
      }

      system.run(() => {
        try {
          block.setPermutation(
            BlockPermutation.resolve(GATE_ID, {
              "minecraft:cardinal_direction": dir,
              "rmbv:open": open,
              "rmbv:powered": poweredNow,
              "rmbv:in_wall": inWall,
            })
          );
          if (open !== wasOpen) {
            block.dimension.playSound(
              open ? "open.fence_gate" : "close.fence_gate",
              block.location
            );
          }
        } catch (err) {
          console.warn(`rmbv gate redstone failed: ${err}`);
        }
      });
    },
  });
});

function faceIsUp(face) {
  return face === "Up" || face === "up";
}
function faceIsDown(face) {
  return face === "Down" || face === "down";
}
function slabEffective(block) {
  const slabType = block.permutation.getState("rmbv:slab_type");
  if (slabType === "double") return "double";
  if (slabType === "top" || slabType === "bottom") return slabType;
  const half = block.permutation.getState("minecraft:vertical_half");
  return half === "top" ? "top" : "bottom";
}
function isCreative(player) {
  try {
    const mode = player.getGameMode();
    return mode === GameMode.Creative || String(mode).toLowerCase() === "creative";
  } catch (_) {
    return false;
  }
}
function consumeSlab(player) {
  if (!player || isCreative(player)) return;
  try {
    const inv = player.getComponent("minecraft:inventory");
    const container = inv?.container;
    const slot = player.selectedSlotIndex;
    if (!container) return;
    const stack = container.getItem(slot);
    if (stack && stack.typeId === SLAB_ID) {
      if (stack.amount > 1) {
        stack.amount -= 1;
        container.setItem(slot, stack);
      } else {
        container.setItem(slot, undefined);
      }
    }
  } catch (err) {
    console.warn(`rmbv slab consume failed: ${err}`);
  }
}
function setDoubleSlab(block) {
  block.setPermutation(
    BlockPermutation.resolve(SLAB_ID, {
      "rmbv:slab_type": "double",
      "minecraft:vertical_half": "bottom",
    })
  );
}
function tryFillSlab(block, face, player) {
  if (!block || !block.isValid || block.typeId !== SLAB_ID) return false;
  const effective = slabEffective(block);
  if (effective === "double") return false;
  const ok =
    (faceIsUp(face) && effective === "bottom") ||
    (faceIsDown(face) && effective === "top");
  if (!ok) return false;
  try {
    setDoubleSlab(block);
    consumeSlab(player);
    block.dimension.playSound("use.stone", block.location);
    return true;
  } catch (err) {
    console.warn(`rmbv tryFillSlab failed: ${err}`);
    return false;
  }
}
/** If a slab was placed into the empty half of a neighbour single slab, merge. */
function tryMergeAfterPlace(placed) {
  if (!placed || !placed.isValid || placed.typeId !== SLAB_ID) return;
  if (slabEffective(placed) === "double") return;
  const dim = placed.dimension;
  const { x, y, z } = placed.location;
  const half = placed.permutation.getState("minecraft:vertical_half") ?? "bottom";
  // Placed as top half above a bottom slab → merge into block below
  if (half === "top") {
    const below = dim.getBlock({ x, y: y - 1, z });
    if (below && below.typeId === SLAB_ID && slabEffective(below) === "bottom") {
      try {
        setDoubleSlab(below);
        placed.setType("minecraft:air");
      } catch (err) {
        console.warn(`rmbv merge below failed: ${err}`);
      }
      return;
    }
  }
  // Placed as bottom half below a top slab → merge into block above
  if (half === "bottom") {
    const above = dim.getBlock({ x, y: y + 1, z });
    if (above && above.typeId === SLAB_ID && slabEffective(above) === "top") {
      try {
        setDoubleSlab(above);
        placed.setType("minecraft:air");
      } catch (err) {
        console.warn(`rmbv merge above failed: ${err}`);
      }
    }
  }
}

function placeSlabAt(dim, pos, half, player) {
  const target = dim.getBlock(pos);
  if (!target || !target.isValid || (!target.isAir && !target.isLiquid)) return false;
  try {
    target.setPermutation(
      BlockPermutation.resolve(SLAB_ID, {
        "rmbv:slab_type": half === "top" ? "top" : "bottom",
        "minecraft:vertical_half": half === "top" ? "top" : "bottom",
      })
    );
    consumeSlab(player);
    dim.playSound("use.stone", pos);
    return true;
  } catch (err) {
    console.warn(`rmbv placeSlabAt failed: ${err}`);
    return false;
  }
}

/** Place against a double-slab full cube (engine often won't solid-place on custom double). */
function tryPlaceAgainstDouble(block, face, player) {
  if (!block || slabEffective(block) !== "double") return false;
  const dir = FACE_TO_DIR[face] ?? String(face).toLowerCase();
  const off = DIR_OFFSET[dir];
  if (!off) return false;
  const { x, y, z } = block.location;
  const pos = { x: x + off.x, y: y + off.y, z: z + off.z };
  // Clicking top → bottom slab above; underside → top slab below; sides → bottom
  let half = "bottom";
  if (dir === "down") half = "top";
  return placeSlabAt(block.dimension, pos, half, player);
}

// Slab stacking + place against double (custom doubles often reject vanilla place)
world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
  try {
    if (event.isFirstEvent === false) return;
  } catch (_) {}
  const { block, player, itemStack, blockFace } = event;
  if (!itemStack || itemStack.typeId !== SLAB_ID) return;
  if (!block) return;
  const face = blockFace ?? event.face;
  const loc = { x: block.location.x, y: block.location.y, z: block.location.z };
  const dim = block.dimension;

  // Holding slab against full source block also allows side/top place via script
  if (block.typeId === FULL_ID) {
    event.cancel = true;
    system.run(() => {
      const b = dim.getBlock(loc);
      if (!b) return;
      const dir = FACE_TO_DIR[face] ?? String(face).toLowerCase();
      const off = DIR_OFFSET[dir];
      if (!off) return;
      const pos = { x: loc.x + off.x, y: loc.y + off.y, z: loc.z + off.z };
      let half = "bottom";
      if (dir === "down") half = "top";
      placeSlabAt(dim, pos, half, player);
    });
    return;
  }

  if (block.typeId !== SLAB_ID) return;

  if (slabEffective(block) === "double") {
    event.cancel = true;
    system.run(() => {
      tryPlaceAgainstDouble(dim.getBlock(loc), face, player);
    });
    return;
  }

  const effective = slabEffective(block);
  const canStack =
    (faceIsUp(face) && effective === "bottom") ||
    (faceIsDown(face) && effective === "top");
  if (!canStack) return;
  event.cancel = true;
  system.run(() => {
    tryFillSlab(dim.getBlock(loc), face, player);
  });
});

// Double slab drops handled by breaking: intercept
world.afterEvents.playerBreakBlock.subscribe((event) => {
  if (event.brokenBlockPermutation?.type?.id !== SLAB_ID) return;
  const type = event.brokenBlockPermutation.getState("rmbv:slab_type");
  if (type !== "double") return;
  // Loot table drops 1; spawn extra slab
  try {
    const dim = event.dimension;
    const loc = event.block.location;
    dim.spawnItem(
      new ItemStack(SLAB_ID, 1),
      { x: loc.x + 0.5, y: loc.y + 0.5, z: loc.z + 0.5 }
    );
  } catch (err) {
    console.warn(`rmbv double slab drop failed: ${err}`);
  }
});

// Keep walls/gates/slabs/fences in sync when any neighbour changes
world.afterEvents.playerPlaceBlock.subscribe((event) => {
  system.run(() => {
    const block = event.block;
    // Sync slab_type from placement trait half on first place, then try merge
    if (block && block.typeId === SLAB_ID) {
      try {
        const half =
          block.permutation.getState("minecraft:vertical_half") ?? "bottom";
        const current = block.permutation.getState("rmbv:slab_type");
        if (current !== "double") {
          block.setPermutation(
            BlockPermutation.resolve(SLAB_ID, {
              "rmbv:slab_type": half === "top" ? "top" : "bottom",
              "minecraft:vertical_half": half === "top" ? "top" : "bottom",
            })
          );
        }
        tryMergeAfterPlace(block);
      } catch (err) {
        console.warn(`rmbv slab place sync failed: ${err}`);
      }
    }

    if (block && block.typeId === FENCE_ID) {
      updateFenceNeighborhood(block);
    } else {
      updateFenceNeighborhood(block);
    }

    updateNearbyWalls(block);
    const dim = block.dimension;
    const { x, y, z } = block.location;
    for (const p of [
      { x, y, z },
      { x: x - 1, y, z },
      { x: x + 1, y, z },
      { x, y, z: z - 1 },
      { x, y, z: z + 1 },
    ]) {
      const b = dim.getBlock(p);
      if (b && b.typeId === GATE_ID) updateGateInWall(b);
    }
  });
});

world.afterEvents.playerBreakBlock.subscribe((event) => {
  system.run(() => {
    const dim = event.dimension;
    const loc = event.block.location;
    for (const p of [
      { x: loc.x, y: loc.y, z: loc.z },
      { x: loc.x - 1, y: loc.y, z: loc.z },
      { x: loc.x + 1, y: loc.y, z: loc.z },
      { x: loc.x, y: loc.y, z: loc.z - 1 },
      { x: loc.x, y: loc.y, z: loc.z + 1 },
      { x: loc.x, y: loc.y + 1, z: loc.z },
    ]) {
      const b = dim.getBlock(p);
      if (b && b.typeId === WALL_ID) recomputeWall(b);
      if (b && b.typeId === GATE_ID) updateGateInWall(b);
      if (b && b.typeId === FENCE_ID) updateFence(b);
    }
  });
});

console.log("[rmbv] brbrickblock_001 variants trial scripts loaded");
'''
    (BP / "scripts" / "main.js").write_text(main_js, encoding="utf-8")


def write_readme() -> None:
    text = """# Rob Mod BR Variants Trial — brbrickblock_001

Standalone trial add-on. **Does not modify** `256xrobmodbr-1.1.0-addon-1.21.x`.

## Contents

| Block | ID |
|-------|-----|
| Full block | `rmbv:brbrickblock_001` |
| Stairs | `rmbv:brbrickblock_001_stairs` |
| Slab | `rmbv:brbrickblock_001_slab` |
| Fence | `rmbv:brbrickblock_001_fence` |
| Wall | `rmbv:brbrickblock_001_wall` |
| Fence gate | `rmbv:brbrickblock_001_fence_gate` |

Namespace `rmbv` avoids clashing with the original `robmodbr:` pack if both are enabled.

## Requirements

- Minecraft Bedrock **1.26.0+** (traits: stair corners, fence connections, multi collision boxes)
- Enable this behaviour pack **and** resource pack on the world
- Cheats optional; scripts needed for slab stacking, walls, gates

## Install

1. Double-click `brbrick_001_variants_trial.mcaddon`, or
2. Copy `rmbv_bp` and `rmbv_rp` into `development_behavior_packs` / `development_resource_packs`

## Test checklist

1. Creative inventory → Construction: all 6 blocks
2. Stairs: 4 directions, top/bottom, corners with neighbouring stairs
3. Slab: top/bottom; right-click empty half with slab to double; break double → 2 items
4. Fence: connects to self; 1.5-block collision
5. Wall: place lines/corners; post drops on straight runs; tall when solid above neighbour
6. Gate: interact open/close; redstone open; lowers between walls
7. Recipes: craft from full block at crafting table

## Rebuild

From the trial folder (requires `../all_model.geo.json` from Block Variant Studio):

```
py -3 tools/build_trial.py
```

Geometries only:

```
py -3 tools/import_bvs_geos.py --clean
```

## Geometry source

Meshes come from **Block Variant Studio** export `all_model.geo.json` (workspace root):

- Split gallery → one `.geo.json` per variant; origins re-centred to bone pivot
- Stair outer/inner **left↔right** corrected (Bedrock export X-mirror)
- Fence → all 16 connections; walls → full pack matrix; cropped UVs preserved
- Falls back to procedural cubes if the export is missing

## Notes

- Texture is a copy of original `brushedbrick_001` (256² + PBR normal).
- Mining time uses **1.5s / explosion 6** (playable trial); original placeholder was 1000.
- Wall short/tall per side is script-driven; mixed-side tall visuals may approximate with a uniform height geo when any arm is tall.
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def package_mcaddon() -> None:
    out = ROOT / "brbrick_001_variants_trial.mcaddon"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, arc_root in ((BP, "rmbv_bp"), (RP, "rmbv_rp")):
            for path in folder.rglob("*"):
                if path.is_file():
                    zf.write(path, f"{arc_root}/{path.relative_to(folder).as_posix()}")
    print(f"Packed: {out}")


def main() -> None:
    write_geometries()
    write_full_block()
    write_stairs()
    write_slab()
    write_fence()
    write_wall()
    write_gate()
    write_loot_and_recipes()
    write_resource_meta()
    write_manifests()
    write_scripts()
    write_readme()
    package_mcaddon()
    print("Done.")


if __name__ == "__main__":
    main()
