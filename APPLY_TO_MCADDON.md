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

From this repo:

```bash
py -3 tools/apply_variants.py --addon-dir "path/to/MyPack" --ns yournamespace --all --pack-version 1.0.0
```

Or explicit paths:

```bash
py -3 tools/apply_variants.py ^
  --bp "path/to/SomeBehaviourPack" ^
  --rp "path/to/SomeResourcePack" ^
  --ns yournamespace ^
  --all
```

Subset only:

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

Textures are **not** regenerated — your existing `terrain_texture.json` and PNGs stay.
