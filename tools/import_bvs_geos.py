#!/usr/bin/env python3
"""
Import Block Variant Studio gallery export (all_model.geo.json) into production
per-variant Bedrock block geometries for the rmbv trial pack.

Corrections applied:
  - Split multi-bone gallery into one geometry file per variant
  - Bake cube origins relative to each bone pivot (centered block space)
  - Swap stair outer/inner left↔right (Blockbench Bedrock X-mirror naming)
  - Expand fence_1111 parts → all 16 connection geos
  - Expand wall_p1_1111 short/tall parts → full wall matrix used by the pack
  - format_version 1.21.0, identifier geometry.rmbv.<name>
  - Preserve cropped UVs from the BVS export
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT_SOURCE = WORKSPACE / "all_model.geo.json"
DEFAULT_OUT = ROOT / "rmbv_rp" / "models" / "blocks"
NS = "rmbv"
FORMAT = "1.21.0"

# File name written ← bone name in export (fixes X-mirror left/right swap)
STAIR_BONE_FOR_FILE: dict[str, str] = {
    "stairs_outer_left_bottom": "stairs_outer_right_bottom",
    "stairs_outer_right_bottom": "stairs_outer_left_bottom",
    "stairs_outer_left_top": "stairs_outer_right_top",
    "stairs_outer_right_top": "stairs_outer_left_top",
    "stairs_inner_left_bottom": "stairs_inner_right_bottom",
    "stairs_inner_right_bottom": "stairs_inner_left_bottom",
    "stairs_inner_left_top": "stairs_inner_right_top",
    "stairs_inner_right_top": "stairs_inner_left_top",
}

DIRECT_BONES = [
    "slab_bottom",
    "slab_top",
    "stairs_straight_bottom",
    "stairs_straight_top",
    "stairs_outer_left_bottom",
    "stairs_outer_right_bottom",
    "stairs_outer_left_top",
    "stairs_outer_right_top",
    "stairs_inner_left_bottom",
    "stairs_inner_right_bottom",
    "stairs_inner_left_top",
    "stairs_inner_right_top",
    "gate_closed",
    "gate_open",
    "gate_closed_inwall",
    "gate_open_inwall",
]

SKIP_BONES = {"bvs_gallery", "full_block_reference"}


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_bones(source: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    geos = raw.get("minecraft:geometry") or []
    if not geos:
        raise SystemExit(f"No minecraft:geometry in {source}")
    bones: dict[str, dict[str, Any]] = {}
    for bone in geos[0].get("bones") or []:
        name = bone.get("name")
        if not name:
            continue
        bones[name] = bone
    return bones


def pivot_of(bone: dict[str, Any]) -> list[float]:
    p = bone.get("pivot") or [0, 0, 0]
    return [float(p[0]), float(p[1]), float(p[2])]


def recenter_cubes(bone: dict[str, Any]) -> list[dict[str, Any]]:
    """Return cubes with origins relative to bone pivot (Bedrock block-centred)."""
    px, py, pz = pivot_of(bone)
    out: list[dict[str, Any]] = []
    for cube in bone.get("cubes") or []:
        origin = cube.get("origin") or [0, 0, 0]
        size = cube.get("size") or [0, 0, 0]
        uv = cube.get("uv")
        entry: dict[str, Any] = {
            "origin": [
                round(float(origin[0]) - px, 4),
                round(float(origin[1]) - py, 4),
                round(float(origin[2]) - pz, 4),
            ],
            "size": [float(size[0]), float(size[1]), float(size[2])],
        }
        if uv is not None:
            entry["uv"] = uv
        out.append(entry)
    return out


def make_geometry(
    identifier: str,
    cubes: list[dict[str, Any]],
    bounds_h: float = 1.5,
) -> dict[str, Any]:
    return {
        "format_version": FORMAT,
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
                "bones": [
                    {
                        "name": "root",
                        "pivot": [0, 0, 0],
                        "cubes": cubes,
                    }
                ],
            }
        ],
    }


def write_geo(out_dir: Path, name: str, cubes: list[dict[str, Any]], bounds_h: float = 1.5) -> None:
    dump(
        out_dir / f"{name}.geo.json",
        make_geometry(f"geometry.{NS}.{name}", cubes, bounds_h),
    )


def cube_key(c: dict[str, Any]) -> tuple:
    o, s = c["origin"], c["size"]
    return (round(o[0], 2), round(o[1], 2), round(o[2], 2), round(s[0], 2), round(s[1], 2), round(s[2], 2))


def classify_fence_parts(cubes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Split fence_1111 cubes into post + N/E/S/W rail pairs."""
    parts: dict[str, list[dict[str, Any]]] = {
        "post": [],
        "n": [],
        "e": [],
        "s": [],
        "w": [],
    }
    for c in cubes:
        ox, oy, oz = c["origin"]
        sx, sy, sz = c["size"]
        # Post: 4×16×4 at (-2,0,-2)
        if abs(sx - 4) < 0.1 and abs(sy - 16) < 0.1 and abs(sz - 4) < 0.1:
            parts["post"].append(c)
            continue
        # NS rails: size ~2×3×6
        if abs(sx - 2) < 0.1 and abs(sz - 6) < 0.1:
            if oz < -1:
                parts["n"].append(c)
            else:
                parts["s"].append(c)
            continue
        # EW rails: size ~6×3×2
        if abs(sz - 2) < 0.1 and abs(sx - 6) < 0.1:
            if ox >= 0:
                parts["e"].append(c)
            else:
                parts["w"].append(c)
            continue
        # Fallback: treat as post
        parts["post"].append(c)
    if not parts["post"]:
        raise SystemExit("Could not find fence post in fence_1111")
    return parts


def classify_wall_parts(cubes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Split wall_p1_1111_* cubes into post + N/E/S/W arms."""
    parts: dict[str, list[dict[str, Any]]] = {
        "post": [],
        "n": [],
        "e": [],
        "s": [],
        "w": [],
    }
    for c in cubes:
        ox, oy, oz = c["origin"]
        sx, sy, sz = c["size"]
        # Post 8×16×8 at (-4,0,-4)
        if abs(sx - 8) < 0.1 and abs(sy - 16) < 0.1 and abs(sz - 8) < 0.1 and abs(ox + 4) < 0.5:
            parts["post"].append(c)
            continue
        # N/S arms: 6 wide in X, extend in Z
        if abs(sx - 6) < 0.1 and abs(sz - 8) < 0.1:
            if oz < -1:
                parts["n"].append(c)
            else:
                parts["s"].append(c)
            continue
        # E/W arms: 6 deep in Z, extend in X
        if abs(sz - 6) < 0.1 and abs(sx - 8) < 0.1:
            if ox >= 0:
                parts["e"].append(c)
            else:
                parts["w"].append(c)
            continue
        parts["post"].append(c)
    return parts


def set_arm_height(cubes: list[dict[str, Any]], height: float) -> list[dict[str, Any]]:
    """Return copies of arm cubes with size[1] set to height (short=14 / tall=16)."""
    out = []
    for c in cubes:
        nc = json.loads(json.dumps(c))
        nc["size"][1] = height
        # Adjust UV north/east/south/west height if present (keep u, stretch v size)
        uv = nc.get("uv")
        if isinstance(uv, dict):
            for face in ("north", "east", "south", "west"):
                f = uv.get(face)
                if not f:
                    continue
                # uv_size format from Blockbench export
                if "uv_size" in f and len(f["uv_size"]) >= 2:
                    # Keep width, set height proportionally to 14 or 16 tex units
                    f["uv_size"][1] = height if height <= 16 else 16
                    if height < 16 and "uv" in f and len(f["uv"]) >= 2:
                        # short wall: start V a bit lower (match BVS short vTop=2)
                        f["uv"][1] = 2
                        f["uv_size"][1] = 14
                    elif height >= 16 and "uv" in f and len(f["uv"]) >= 2:
                        f["uv"][1] = 0
                        f["uv_size"][1] = 16
        out.append(nc)
    return out


def expand_fences(parts: dict[str, list[dict[str, Any]]], out_dir: Path) -> int:
    n_written = 0
    for mask in range(16):
        n = bool(mask & 8)
        e = bool(mask & 4)
        s = bool(mask & 2)
        w = bool(mask & 1)
        name = f"fence_{int(n)}{int(e)}{int(s)}{int(w)}"
        cubes: list[dict[str, Any]] = []
        cubes.extend(json.loads(json.dumps(parts["post"])))
        if n:
            cubes.extend(json.loads(json.dumps(parts["n"])))
        if e:
            cubes.extend(json.loads(json.dumps(parts["e"])))
        if s:
            cubes.extend(json.loads(json.dumps(parts["s"])))
        if w:
            cubes.extend(json.loads(json.dumps(parts["w"])))
        write_geo(out_dir, name, cubes, 1.5)
        n_written += 1
    return n_written


def expand_walls(
    short_parts: dict[str, list[dict[str, Any]]],
    tall_parts: dict[str, list[dict[str, Any]]],
    out_dir: Path,
) -> int:
    """Match build_trial matrix: 16 masks × post on/off × short/tall (skip empty no-post)."""
    n_written = 0
    for mask in range(16):
        has_n = bool(mask & 8)
        has_e = bool(mask & 4)
        has_s = bool(mask & 2)
        has_w = bool(mask & 1)
        for post in (True, False):
            if not post and mask == 0:
                continue
            for tall in (False, True):
                parts = tall_parts if tall else short_parts
                height = 16.0 if tall else 14.0
                cubes: list[dict[str, Any]] = []
                if post:
                    cubes.extend(json.loads(json.dumps(parts["post"])))
                if has_n:
                    cubes.extend(set_arm_height(parts["n"], height))
                if has_e:
                    cubes.extend(set_arm_height(parts["e"], height))
                if has_s:
                    cubes.extend(set_arm_height(parts["s"], height))
                if has_w:
                    cubes.extend(set_arm_height(parts["w"], height))
                if not cubes:
                    cubes.extend(json.loads(json.dumps(short_parts["post"])))
                name = (
                    f"wall_p{int(post)}_"
                    f"{int(has_n)}{int(has_e)}{int(has_s)}{int(has_w)}_"
                    f"{'tall' if tall else 'short'}"
                )
                write_geo(out_dir, name, cubes, 1.5)
                n_written += 1
    return n_written


def import_geos(source: Path, out_dir: Path, clean: bool = False) -> dict[str, int]:
    if not source.is_file():
        raise SystemExit(f"Source not found: {source}")

    bones = load_bones(source)
    stats = {"direct": 0, "fence": 0, "wall": 0, "skipped": 0}

    if clean and out_dir.is_dir():
        for p in out_dir.glob("*.geo.json"):
            p.unlink()

    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Direct bones (stairs with L/R swap, slabs, gates) ---
    for file_name in DIRECT_BONES:
        bone_name = STAIR_BONE_FOR_FILE.get(file_name, file_name)
        bone = bones.get(bone_name)
        if not bone:
            print(f"  WARN: missing bone {bone_name!r} for {file_name}")
            stats["skipped"] += 1
            continue
        cubes = recenter_cubes(bone)
        if not cubes:
            print(f"  WARN: no cubes on {bone_name}")
            stats["skipped"] += 1
            continue
        bounds = 1.0 if file_name.startswith("slab_") else 1.5
        write_geo(out_dir, file_name, cubes, bounds)
        stats["direct"] += 1

    # --- Fence expansion from fence_1111 ---
    fence_bone = bones.get("fence_1111")
    if not fence_bone:
        raise SystemExit("Missing fence_1111 bone — needed to expand all fence combos")
    fence_parts = classify_fence_parts(recenter_cubes(fence_bone))
    stats["fence"] = expand_fences(fence_parts, out_dir)

    # --- Wall expansion from wall_p1_1111_short / tall ---
    wall_short_bone = bones.get("wall_p1_1111_short")
    wall_tall_bone = bones.get("wall_p1_1111_tall")
    if not wall_short_bone:
        raise SystemExit("Missing wall_p1_1111_short bone")
    if not wall_tall_bone:
        # Fall back to short for both, height adjusted in expand
        wall_tall_bone = wall_short_bone
    short_parts = classify_wall_parts(recenter_cubes(wall_short_bone))
    tall_parts = classify_wall_parts(recenter_cubes(wall_tall_bone))
    if not short_parts["post"]:
        raise SystemExit("Could not classify wall post from wall_p1_1111_short")
    # Ensure each direction has at least one arm sample
    for d in ("n", "e", "s", "w"):
        if not short_parts[d]:
            raise SystemExit(f"Missing wall arm {d} in wall_p1_1111_short")
        if not tall_parts[d]:
            tall_parts[d] = short_parts[d]
        if not tall_parts["post"]:
            tall_parts["post"] = short_parts["post"]
    stats["wall"] = expand_walls(short_parts, tall_parts, out_dir)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Import BVS all_model.geo.json into trial RP models")
    ap.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to all_model.geo.json (default: {DEFAULT_SOURCE})",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output models/blocks directory (default: {DEFAULT_OUT})",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing *.geo.json in out dir before writing",
    )
    args = ap.parse_args()

    print(f"Source: {args.source}")
    print(f"Out:    {args.out}")
    stats = import_geos(args.source, args.out, clean=args.clean)
    total = sum(stats.values()) - stats["skipped"]
    n_files = len(list(args.out.glob("*.geo.json")))
    print(
        f"Wrote geos — direct={stats['direct']} fence={stats['fence']} "
        f"wall={stats['wall']} skipped={stats['skipped']} total_ops={total}"
    )
    print(f"Files in out: {n_files}")


if __name__ == "__main__":
    main()
