# Apply variants to any `.mcaddon`

## 1. Unpack

```text
MyPack.mcaddon  →  rename to .zip  →  extract
MyPack/
  SomeBehaviourPack/manifest.json
  SomeResourcePack/manifest.json
```

If the zip has a single outer folder, open that folder until you see the two packs.

## 2. Run the kit

### Preferred: texture allow-list

1. Create `process_only.xlsx` next to the pack (or anywhere).  
2. Column A = texture filenames to upgrade only, e.g. `brushedbrick_001.png`.  
3. Run interactive (asks first):

```bash
py -3 tools/run_generator.py
```

Or CLI:

```bash
py -3 tools/apply_variants.py --addon-dir "path/to/MyPack" --ns yournamespace --process-only process_only.xlsx --pack-version 1.0.0
```

**Do not use `--all` unless you really want every full-cube block.**

### Explicit BP/RP paths

```bash
py -3 tools/apply_variants.py ^
  --bp "path/to/SomeBehaviourPack" ^
  --rp "path/to/SomeResourcePack" ^
  --ns yournamespace ^
  --process-only "path/to/process_only.xlsx"
```

Block-stem list instead of textures:

```bash
py -3 tools/apply_variants.py --bp BP --rp RP --ns yournamespace --bases kit/examples/bases.example.txt
```

## 3. Re-pack

Zip so the archive root contains **two folders**, each with its own `manifest.json`:

```text
MyPack_variants.mcaddon  (zip)
  SomeBehaviourPack/
    manifest.json
    blocks/
    scripts/main.js
    ...
  SomeResourcePack/
    manifest.json
    models/blocks/
    ...
```

## 4. Install

- Double-click the `.mcaddon`, **or**  
- Copy BP → `development_behavior_packs`, RP → `development_resource_packs`  
- Enable **both** on a 1.26+ world  

### Common error

`Multiple manifests found at the same directory level`  
→ You installed the parent folder or merged both packs. Install BP and RP as **separate** packs.

## What the tool changes

- Upgrades full cubes to format **1.26.30**  
- Generates stairs, slab, fence, wall, fence gate  
- Installs shared geometries  
- Writes production `scripts/main.js`  
- Recipes + loot + lang + `blocks.json`  
- **Removes fence posts**  
- Bumps pack version / min engine / server module  
- **Final step: new unique UUIDs** for BP + RP (and BP→RP dependency) so the pack never conflicts with the original addon or Rob Mod  

Textures are **not** regenerated — your existing `terrain_texture.json` and PNGs stay.

### UUID-only re-stamp

```bash
py -3 tools/apply_variants.py --bp path/to/BP --rp path/to/RP --uuids-only
```
