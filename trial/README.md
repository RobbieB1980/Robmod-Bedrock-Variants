# Rob Mod BR Variants Trial — brbrickblock_001

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
