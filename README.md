# Rob's Bedrock Variants

Portable, **working** reference + mass-apply kit for vanilla-compatible custom block variants on **Minecraft Bedrock 1.26+**.

**Status (production-proven on Rob Mod Bedrock v1.7.1):**

| Variant | Status |
|---------|--------|
| Full block | Working |
| Stairs (corners L/R) | Working |
| Slab (single / double / sides top&bottom / on full) | Working |
| Fence (all axes, E↔W mesh swap) | Working |
| Wall (short/tall, E↔W mesh swap) | Working |
| Fence gate (open / redstone / in-wall) | Working |
| Fence post | **Removed** — duplicate of fence |

## Start here

| Doc | Use |
|-----|-----|
| **[kit/README.md](./kit/README.md)** | Portable kit + CLI to apply to **any** pack / `.mcaddon` |
| **[APPLY_TO_MCADDON.md](./APPLY_TO_MCADDON.md)** | Step-by-step unpack → apply → rezip |
| **[WORKING_VARIANT_REFERENCE.md](./WORKING_VARIANT_REFERENCE.md)** | Full technical playbook (also under `docs/`) |

## Desktop app (Windows)

### One-file install (recommended)

1. Double-click **`Install RB Variants.exe`** (~40 MB single file)
2. It extracts into **`RBVariants\`** next to the installer
3. Runs **`RB Variant Maker.exe`**
4. Browse unpacked addon → options → Generate (writes a **new** folder named after the namespace)

No Python install required. Share only the installer.

Rebuild:

```bash
py -3 tools/build_installer.py
```

### Extracted app folder

```text
RBVariants\
  RB Variant Maker.exe
  kit\
  _internal\
```

Keep that whole folder together if copying without the installer.

### Interactive terminal (Python)

Asks **“Did you want to include a file that lists textures only to process?”** before generating:

```bash
py -3 tools/run_generator.py
```

Or double-click `tools/RobmodVariantsGenerator.bat` if Python is installed.

Use a `process_only.xlsx` next to your pack (column A = texture filenames, e.g. `brushedbrick_001.png`).  
**Only those textures** get stairs/slab/fence/wall/gate — not every file under `/blocks`.

### CLI

```bash
# Texture allow-list only (preferred)
py -3 tools/apply_variants.py --bp path/to/BP --rp path/to/RP --ns yournamespace --process-only process_only.xlsx
```

```bash
# All full-cube blocks (heavy — avoid unless intentional)
py -3 tools/apply_variants.py --bp path/to/BP --rp path/to/RP --ns yournamespace --all
```

```bash
py -3 tools/apply_variants.py --addon-dir path/to/unpacked_mcaddon --ns yournamespace --process-only process_only.xlsx
```

```bash
# Final-step only: new unique pack UUIDs (BP + RP linked)
py -3 tools/apply_variants.py --bp BP --rp RP --uuids-only
```

Each full apply **regenerates pack UUIDs** by default (`--keep-uuids` to skip).

Kit contents:

```
kit/
  geometries/          # 94 shared .geo.json models
  templates/main.js    # production script (__NS__ placeholder)
  examples/
tools/
  apply_variants.py    # mass applier
  build_trial.py
  import_bvs_geos.py
```

## Trial pack (single material demo)

```
trial/rmbv_bp + trial/rmbv_rp
releases/brbrick_001_variants_trial.mcaddon
```

```bash
py -3 tools/build_trial.py
```

Install: enable **both** BP and RP (never one folder with two manifests).

## Engine

- Block `format_version`: **1.26.30**  
- `@minecraft/server`: **2.0.0**  
- `min_engine_version`: **[1, 26, 0]**  

## Hard rules

1. `ambient_occlusion` = float `1.0` (not bool)  
2. Tags = `minecraft:tags` array  
3. Stairs: L↔R mesh swap; fence/wall: **E↔W** mesh swap only  
4. Selection Y ≤ 16; collision may be 24  
5. Recipes need `unlock`  
6. No fence posts  

## Repo

https://github.com/RobbieB1980/Robmod-Bedrock-Variants  

Authors: RobbieB / Grok Build.
