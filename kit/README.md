# Portable apply kit (final, production-proven)

Use this kit to add **vanilla-compatible** stairs / slab / fence / wall / fence gate variants to **any** Minecraft Bedrock behaviour + resource pack (1.26+).

Proven on **Rob Mod Bedrock Edition v1.7.1** (hundreds of materials).

## What you get

| Path | Purpose |
|------|---------|
| `geometries/` | 94 BVS-derived `.geo.json` models (stairs L/R, fence 16, wall matrix, slab, gate) |
| `templates/main.js` | Production script with `__NS__` placeholder (slab raycast, fence/wall/gate) |
| `examples/config.example.json` | Sample settings |
| `../tools/apply_variants.py` | CLI mass-applier |
| `../WORKING_VARIANT_REFERENCE.md` | Full technical playbook |

**Not included on purpose:** fence posts (duplicate of fence with no arms).

## Variants generated per full block

| ID | Notes |
|----|--------|
| `{ns}:{base}` | Full cube (schema fixes) |
| `{ns}:{base}_stairs` | Vanilla corner trait + L↔R mesh swap |
| `{ns}:{base}_slab` | bottom / top / double + script stacking |
| `{ns}:{base}_fence` | `conn` 0–15, E↔W mesh swap |
| `{ns}:{base}_wall` | short/tall per side + post |
| `{ns}:{base}_fence_gate` | open / redstone / in-wall |

Plus recipes, loot tables, lang, `blocks.json`, shared geometries, one `scripts/main.js`.

## Quick start (unpacked packs)

```bash
# From the Robmod-Bedrock-Variants repo root:
py -3 tools/apply_variants.py ^
  --bp "path/to/YourBP" ^
  --rp "path/to/YourRP" ^
  --ns yournamespace ^
  --all ^
  --pack-version 1.0.0
```

Only some blocks:

```bash
py -3 tools/apply_variants.py --bp BP --rp RP --ns myns --bases kit/examples/bases.example.txt
```

From texture list (Excel column of `.png` names, mapped via `terrain_texture.json`):

```bash
py -3 tools/apply_variants.py --bp BP --rp RP --ns myns --excel "files to create variants.xlsx"
```

Unpacked `.mcaddon` folder (auto-find BP/RP):

```bash
py -3 tools/apply_variants.py --addon-dir "path/to/unpacked" --ns myns --all
```

### Apply to an `.mcaddon` file

1. Rename `Something.mcaddon` → `Something.zip` and extract  
2. Run `apply_variants.py` on the BP + RP folders (or `--addon-dir`)  
3. Zip the two pack folders again and rename to `.mcaddon`  
   - Zip root must be: `YourBP/manifest.json` and `YourRP/manifest.json`  
   - **Do not** put both manifests in one folder  

## Requirements

- Python 3.10+  
- `openpyxl` only if using `--excel`: `py -3 -m pip install openpyxl`  
- Target pack: Bedrock **1.26+**, script module `@minecraft/server` **2.0.0** (tool sets this)

## After apply — install correctly

| Correct | Wrong |
|---------|--------|
| BP → `development_behavior_packs/YourBP` | Parent folder containing both packs into one development slot |
| RP → `development_resource_packs/YourRP` | Merging BP+RP files into one directory |
| Enable **both** on the world | |

## Hard rules (do not reverse)

- `ambient_occlusion` must be a **float** (`1.0`), not `true`  
- Tags: `minecraft:tags` array only  
- Fence/wall **E↔W mesh swap**; stairs **L↔R mesh swap**  
- Selection boxes max Y **16**; collision may use **24**  
- Recipes need `unlock`  
- No fence posts — use fence  

## Smoke test

1. `/give @s yournamespace:yourblock` (+ `_stairs` `_slab` `_fence` `_wall` `_fence_gate`)  
2. Stairs corners, slab double + side top/bottom aim, fence all axes, wall short/tall, gate open/redstone  

## Rebuild geometries from Block Variant Studio (optional)

If you have `all_model.geo.json` from BVS:

```bash
py -3 tools/import_bvs_geos.py --clean
# then copy trial/rmbv_rp/models/blocks → kit/geometries
```
