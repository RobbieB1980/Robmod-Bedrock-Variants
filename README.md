# Robmod Bedrock Variants

Portable, **working** reference for vanilla-compatible custom block variants on **Minecraft Bedrock 1.26+**:

| Variant | Status (trial) |
|---------|----------------|
| Full block | Working |
| Stairs (corners L/R) | Working |
| Slab (single / double / place on double) | Working |
| Fence (all axes join) | Working |
| Wall (all axes join) | Working |
| Fence gate (open / redstone / in-wall) | Working |

Use this repo as the basis to apply the same patterns to **Rob Mod** or any other Bedrock pack.

## Start here

**[WORKING_VARIANT_REFERENCE.md](./WORKING_VARIANT_REFERENCE.md)** — complete portable playbook:

- Schema rules so blocks appear in `/give` and creative  
- Material instances, tags, custom components (1.26.30)  
- Stairs L↔R mesh swap  
- Fence & wall **E↔W mesh swap** (Bedrock X-mirror)  
- Script-driven fence `conn` bits and wall short/tall/post  
- Slab stacking + place-against-double  
- Recipes with unlock, collision vs selection limits  
- How to mass-apply to a full mod  

Same file also lives at [`docs/WORKING_VARIANT_REFERENCE.md`](./docs/WORKING_VARIANT_REFERENCE.md).

## Trial pack (verified)

Concrete working example for one material (`rmbv:brbrickblock_001`):

```
trial/
  rmbv_bp/     # behaviour: blocks, recipes, loot, scripts
  rmbv_rp/     # resource: models, textures, lang
  README.md
tools/
  build_trial.py
  import_bvs_geos.py
releases/
  brbrick_001_variants_trial.mcaddon
```

### Install trial

1. Double-click `releases/brbrick_001_variants_trial.mcaddon`, **or**  
2. Copy `trial/rmbv_bp` → `development_behavior_packs` and `trial/rmbv_rp` → `development_resource_packs`  
3. Enable **both** packs on a world (Bedrock 1.26+)  
4. `/give @s rmbv:brbrickblock_001` (and `_stairs`, `_slab`, `_fence`, `_wall`, `_fence_gate`)

### Rebuild trial

From the repo root (optional BVS export `all_model.geo.json` next to project for geos):

```bash
py -3 tools/build_trial.py
```

## Engine

- Block `format_version`: **1.26.30**  
- `@minecraft/server`: **2.0.0**  
- min_engine_version: **1.26.0**

## Apply to a full mod

1. Read `WORKING_VARIANT_REFERENCE.md`  
2. Point an assistant (or follow the procedure section) at your full BP/RP  
3. Replace `{ns}` / `{base}` / `{tex}` placeholders for every full block  
4. Share one script that loops all fence/wall/slab/gate ids  

Do **not** copy trial UUIDs into a published pack without regenerating them.

## License / credit

Trial tooling and reference produced for Rob Mod Bedrock variant work.  
Authors noted in pack manifests: RobbieB / Grok Build Trial.

## Repo

https://github.com/Profe550rCha0s/Robmod-Bedrock-Variants
