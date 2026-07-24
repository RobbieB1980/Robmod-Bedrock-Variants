# Working Vanilla-Compatible Block Variants — Portable Reference

**Source:** `brbrick_001_variants_trial` (verified working, pack **v1.0.7**)  
**Engine:** Minecraft Bedrock **1.26+** (`format_version` **1.26.30** on blocks)  
**Purpose:** Apply these patterns to **any** Bedrock behaviour/resource pack (full Rob Mod, other packs, generators).

Replace placeholders:

| Placeholder | Meaning | Trial example |
|-------------|---------|---------------|
| `{ns}` | Namespace | `rmbv` |
| `{base}` | Full block id stem | `brbrickblock_001` |
| `{tex}` | terrain_texture shortname | `rmbv_brbrickblock_001` |
| `{geo}` | Geometry prefix | `geometry.rmbv` |

IDs:

| Variant | Identifier |
|---------|------------|
| Full block | `{ns}:{base}` |
| Stairs | `{ns}:{base}_stairs` |
| Slab | `{ns}:{base}_slab` |
| Fence | `{ns}:{base}_fence` |
| Wall | `{ns}:{base}_wall` |
| Fence gate | `{ns}:{base}_fence_gate` |

World axes (Bedrock):

- **North** = −Z · **South** = +Z · **East** = +X · **West** = −X  
- Geometry origins are block-centred: centre (0,0,0), full cube roughly `origin [-8,0,-8]` `size [16,16,16]`.

---

## 1. Hard requirements (blocks will not register without these)

These caused total failure (no `/give`, no creative) until fixed.

### 1.1 `format_version`

```json
"format_version": "1.26.30"
```

Use **1.26.30** (or current stable matching the wiki) for all custom block JSONs that use traits / multi-box collision / modern components.

### 1.2 Material instances — `ambient_occlusion` is a **float**, not bool

```json
"minecraft:material_instances": {
  "*": {
    "texture": "{tex}",
    "render_method": "opaque",
    "ambient_occlusion": 1.0,
    "face_dimming": true
  }
}
```

- **Wrong:** `"ambient_occlusion": true` → content log: `invalid numeric value` → **block rejected**.
- **Right:** `0.0`–`10.0` float (use `1.0` for normal stone).

### 1.3 Tags — use `minecraft:tags` array only

```json
"minecraft:tags": [
  "minecraft:cornerable_stairs",
  "{ns}:stairs"
]
```

- **Wrong:** `"tag:{ns}:stairs": {}` → `not present in the Schema` → **block rejected**.
- Stairs that corner must include **`minecraft:cornerable_stairs`**.
- Fences/gates that vanilla fences connect to: include **`minecraft:has_fence_connections`**.

### 1.4 Custom components — direct keys, not array

```json
"{ns}:fence_update": {},
"{ns}:wall_update": {},
"{ns}:slab_stacking": {},
"{ns}:fence_gate": {}
```

- **Wrong:** `"minecraft:custom_components": ["{ns}:fence_update"]` → schema reject.
- Register the same names in script:

```js
system.beforeEvents.startup.subscribe((init) => {
  init.blockComponentRegistry.registerCustomComponent("{ns}:fence_update", { /* ... */ });
});
```

### 1.5 Creative menu / give

```json
"menu_category": {
  "category": "construction",
  "group": "minecraft:itemGroup.name.stoneBrick"
}
```

Valid groups (examples):

| Variant | `group` |
|---------|---------|
| Full block | `minecraft:itemGroup.name.stoneBrick` (or omit `group`) |
| Stairs | `minecraft:itemGroup.name.stairs` |
| Slab | `minecraft:itemGroup.name.slab` |
| Fence | `minecraft:itemGroup.name.fence` |
| Wall | `minecraft:itemGroup.name.walls` |
| Gate | `minecraft:itemGroup.name.fenceGates` |

**Invalid:** `minecraft:itemGroup.name.construction` — construction is a **tab**, not a group.

### 1.6 Collision vs selection

| Component | Multi-box array? | Max height (Y) |
|-----------|------------------|----------------|
| `minecraft:collision_box` | Yes (up to 16 boxes) | **24** |
| `minecraft:selection_box` | **No** — single object or bool only | **16** |

Always derive selection from collision with a **union AABB clamped to Y≤16**:

```text
origin.y + size.y ≤ 16 for selection
origin.y + size.y ≤ 24 for collision
```

Fence/wall collision may use height **24**; selection must clamp to **16**.

### 1.7 Recipes need unlock (1.20+)

```json
"unlock": [
  { "item": "{ns}:{base}" }
]
```

Without this: `1.20+ Recipes require unlock data`.

### 1.8 RP `blocks.json`

```json
{
  "format_version": "1.21.40",
  "{ns}:{base}": { "sound": "stone" },
  "{ns}:{base}_stairs": { "sound": "stone" },
  "{ns}:{base}_slab": { "sound": "stone" },
  "{ns}:{base}_fence": { "sound": "stone" },
  "{ns}:{base}_wall": { "sound": "stone" },
  "{ns}:{base}_fence_gate": { "sound": "stone" }
}
```

### 1.9 Manifest (BP)

- `min_engine_version`: `[1, 26, 0]` (or higher matching target)
- Script module + dependency `"@minecraft/server": "2.0.0"` (or current stable for your engine)
- BP depends on matching RP UUID/version

---

## 2. Shared base components (every variant)

Copy material/destruction/friction/etc. from the full block:

```json
"minecraft:material_instances": { "*": { "texture": "{tex}", "render_method": "opaque", "ambient_occlusion": 1.0, "face_dimming": true } },
"minecraft:destructible_by_mining": { "seconds_to_destroy": 1.5 },
"minecraft:destructible_by_explosion": { "explosion_resistance": 6.0 },
"minecraft:friction": 0.6,
"minecraft:flammable": { "catch_chance_modifier": 0, "destroy_chance_modifier": 0 },
"minecraft:light_emission": 0,
"minecraft:map_color": "#A65E3B",
"minecraft:loot": "loot_tables/blocks/{base}_VARIANT.json"
```

Light dampening: **15** full solids / double slab; **0** for fence, wall, gate, single slabs (or match design).

Lang (RP `texts/en_US.lang`):

```text
tile.{ns}:{base}.name=...
tile.{ns}:{base}_stairs.name=...
tile.{ns}:{base}_slab.name=...
tile.{ns}:{base}_fence.name=...
tile.{ns}:{base}_wall.name=...
tile.{ns}:{base}_fence_gate.name=...
```

---

## 3. Full block

Minimal solid cube:

```json
{
  "format_version": "1.26.30",
  "minecraft:block": {
    "description": {
      "identifier": "{ns}:{base}",
      "menu_category": {
        "category": "construction",
        "group": "minecraft:itemGroup.name.stoneBrick"
      }
    },
    "components": {
      "minecraft:geometry": "minecraft:geometry.full_block",
      "minecraft:collision_box": true,
      "minecraft:selection_box": true,
      "minecraft:light_dampening": 15,
      "minecraft:material_instances": { "...": "..." },
      "minecraft:tags": ["{ns}:source_block"],
      "minecraft:loot": "loot_tables/blocks/{base}.json"
    }
  }
}
```

---

## 4. Stairs (working)

### 4.1 Traits (vanilla corners)

```json
"traits": {
  "minecraft:placement_position": {
    "enabled_states": ["minecraft:vertical_half"]
  },
  "minecraft:placement_direction": {
    "enabled_states": ["minecraft:corner_and_cardinal_direction"],
    "blocks_to_corner_with": [
      { "tags": "q.any_tag('minecraft:cornerable_stairs')" }
    ]
  }
}
```

States exposed by traits:

- `minecraft:cardinal_direction`: north / south / east / west  
- `minecraft:vertical_half`: bottom / top  
- `minecraft:corner`: none / inner_left / inner_right / outer_left / outer_right  

### 4.2 Tags

```json
"minecraft:tags": ["minecraft:cornerable_stairs", "{ns}:stairs"],
"minecraft:support": { "shape": "stair" }
```

### 4.3 Geometry base orientation

All stair geos are authored **facing north** (high step toward −Z), then rotated per permutation:

| Facing | `minecraft:transformation.rotation` Y |
|--------|----------------------------------------|
| north | `0` |
| east | `-90` |
| south | `180` |
| west | `90` |

### 4.4 Left/right mesh swap (required)

Trait `minecraft:corner` left/right does **not** match these BVS/north-base meshes until swapped:

| Trait value | Use mesh/collision for |
|-------------|------------------------|
| `inner_left` | `inner_right` files |
| `inner_right` | `inner_left` files |
| `outer_left` | `outer_right` files |
| `outer_right` | `outer_left` files |
| `none` | straight |

North-base cube layout (after swap, mesh names as on disk):

| Mesh name | Upper step (bottom half) |
|-----------|---------------------------|
| `stairs_straight_bottom` | `[-8,8,-8] [16,8,8]` (north) |
| `stairs_inner_left_bottom` | north slab + west wing `[-8,8,0][8,8,8]` |
| `stairs_inner_right_bottom` | north slab + east wing `[0,8,0][8,8,8]` |
| `stairs_outer_left_bottom` | NW only `[-8,8,-8][8,8,8]` |
| `stairs_outer_right_bottom` | NE only `[0,8,-8][8,8,8]` |

Top half = vertical mirror of bottom (lower step in upper half of block).

### 4.5 Collision

Multi-box **collision** matching the mesh (after L/R flip).  
**Selection:** single union box (or full 16³); do not use multi-box selection.

### 4.6 Permutation pattern

```text
for direction in N,E,S,W:
  for half in bottom,top:
    for corner in none,inner_left,inner_right,outer_left,outer_right:
      mesh_corner = flip_lr(corner)
      condition: cardinal == direction && vertical_half == half && corner == corner
      components: geometry(mesh_corner), collision(mesh_corner), selection(union), transformation(yaw)
```

40 permutations total.

### 4.7 Recipe

```json
"pattern": ["#  ", "## ", "###"],
"key": { "#": { "item": "{ns}:{base}" } },
"unlock": [{ "item": "{ns}:{base}" }],
"result": { "item": "{ns}:{base}_stairs", "count": 4 }
```

---

## 5. Slab (working)

### 5.1 States + trait

```json
"states": {
  "{ns}:slab_type": ["bottom", "top", "double"]
},
"traits": {
  "minecraft:placement_position": {
    "enabled_states": ["minecraft:vertical_half"]
  }
}
```

### 5.2 Components

```json
"{ns}:slab_stacking": {},
"minecraft:tags": ["{ns}:slab", "{ns}:slab_{base}"]
```

### 5.3 Permutations (last wins — put **double last**)

| Condition | Geometry | Collision / selection |
|-----------|----------|------------------------|
| `slab_type == bottom` | `slab_bottom` | `[-8,0,-8][16,8,16]`, light_dampening 0 |
| `slab_type == top` | `slab_top` | `[-8,8,-8][16,8,16]`, light_dampening 0 |
| `slab_type == double` | `minecraft:geometry.full_block` | **explicit** `[-8,0,-8][16,16,16]` (not only `true`), light_dampening 15 |

### 5.4 Script behaviour (required)

Custom double slabs often **reject vanilla place** against their faces. Working trial logic:

1. **Stack empty half** (only these faces):  
   - Bottom slab + face **Up** → set double  
   - Top slab + face **Down** → set double  
   - Cancel interact, consume item (unless creative), play sound  

2. **Do not cancel** side clicks on **single** slabs — normal place works.

3. **Double slab + slab item:** script-place a slab into the adjacent cell on that face:  
   - Up → bottom slab above  
   - Down → top slab below  
   - Horizontal faces → bottom slab adjacent  

4. **Full base block + slab item:** same script place on that face (optional but useful).

5. **Merge after place:** if a top slab is placed in the cell above a bottom slab (or reverse), convert lower/upper to double and clear the extra cell.

6. **Break double:** loot table drops 1; script spawns **+1** slab item.

7. **On place:** sync `{ns}:slab_type` from `minecraft:vertical_half` when not double.

Use `isFirstEvent === false` early-return on interact to avoid double-handling.

### 5.5 Recipe

```json
"pattern": ["###"],
"result": { "item": "{ns}:{base}_slab", "count": 6 },
"unlock": [{ "item": "{ns}:{base}" }]
```

---

## 6. Fence (working)

### 6.1 Do **not** rely on `minecraft:connection` trait for visuals

Trait mapping was unreliable with these meshes. Use:

```json
"states": {
  "{ns}:conn": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
}
```

### 6.2 Components

```json
"{ns}:fence_update": {},
"minecraft:connection_rule": { "accepts_connections_from": "only_fences" },
"minecraft:support": { "shape": "fence" },
"minecraft:tags": ["minecraft:has_fence_connections", "{ns}:fence"]
```

### 6.3 Script bit layout (world space)

```js
const BIT = { north: 0, south: 1, east: 2, west: 3 };
// neighbor offsets: N (0,0,-1), S (0,0,+1), E (+1,0,0), W (-1,0,0)
// if neighbor is fence or fence_gate (any pack) → set bit
```

Update self + neighbours on place/break of fence, wall, gate, and any solid neighbour place/break as needed.

### 6.4 Geometry name map — **E↔W mesh swap only** (critical)

Geo files are named `fence_{N}{E}{S}{W}` with cubes in **model** space:

| Digit | Model arm (file content) |
|-------|---------------------------|
| N=1 | arm toward −Z |
| E=1 | arm toward +X |
| S=1 | arm toward +Z |
| W=1 | arm toward −X |

**In-game Bedrock X-mirror:** world east connection must use the **west** arm mesh and vice versa. **Do not** swap N/S for these BVS-derived fence geos.

```text
world bits from script: n, s, e, w  (booleans)
geometry id = fence_{n}{w}{s}{e}     // E and W digits swapped
collision   = arms for (n, w, s, e)  // same swap
```

Examples:

| World connections | Mask | Geometry file |
|-------------------|------|---------------|
| none | 0 | `fence_0000` |
| north only | 1 | `fence_1000` |
| south only | 2 | `fence_0010` |
| east only | 4 | `fence_0001` ← west mesh |
| west only | 8 | `fence_0100` ← east mesh |
| north+east | 5 | `fence_1001` |

### 6.5 Collision

Post `[-2,0,-2][4,24,4]` plus 6×24×4 arms per side (selection clamp Y to 16).

### 6.6 Recipe

```json
"pattern": ["#S#", "#S#"],
"key": { "#": { "item": "{ns}:{base}" }, "S": { "item": "minecraft:stick" } },
"result": { "item": "{ns}:{base}_fence", "count": 3 }
```

---

## 7. Wall (working)

### 7.1 States (script-driven)

```json
"states": {
  "{ns}:wall_n": ["none", "short", "tall"],
  "{ns}:wall_e": ["none", "short", "tall"],
  "{ns}:wall_s": ["none", "short", "tall"],
  "{ns}:wall_w": ["none", "short", "tall"],
  "{ns}:wall_post": [true, false]
}
```

### 7.2 Components

```json
"{ns}:wall_update": {},
"minecraft:tags": ["{ns}:wall"]
```

### 7.3 Script connection rules

For each cardinal neighbour:

- Wall or fence gate → short (tall if solid block above that neighbour)
- Solid full block → short/tall same way  
- Slab/stairs/etc. → none  

**Post:**

- `true` if no connections, or corner/T, or solid above  
- `false` only for clean straight short N–S or E–W run with no solid above  

### 7.4 Geometry name map — **E↔W mesh swap only**

Files: `wall_p{post}_{N}{E}{S}{W}_{short|tall}`

```text
world states: n,e,s,w each none|short|tall
height = tall if any side tall else short
gn = 1 if n != none else 0
ge = 1 if w != none else 0   // swapped
gs = 1 if s != none else 0
gw = 1 if e != none else 0   // swapped
geometry = wall_p{post}_{gn}{ge}{gs}{gw}_{height}
collision arms use (n, w, s, e) order (E↔W swapped vs world)
```

Screenshot-proven:

- N–S wall lines join with **no** N/S mesh swap  
- E–W wall lines need **E↔W** mesh swap (same X-mirror as fences)

### 7.5 Recipe

```json
"pattern": ["###", "###"],
"result": { "item": "{ns}:{base}_wall", "count": 6 }
```

---

## 8. Fence gate (working)

### 8.1 States + trait

```json
"states": {
  "{ns}:open": [false, true],
  "{ns}:powered": [false, true],
  "{ns}:in_wall": [false, true]
},
"traits": {
  "minecraft:placement_direction": {
    "enabled_states": ["minecraft:cardinal_direction"]
  }
}
```

### 8.2 Components

```json
"{ns}:fence_gate": {},
"minecraft:connection_rule": { "accepts_connections_from": "all" },
"minecraft:redstone_consumer": { "min_power": 1, "propagates_power": false },
"minecraft:tags": ["{ns}:fence_gate", "minecraft:has_fence_connections"]
```

### 8.3 Geos

| State | Geometry |
|-------|----------|
| closed, not in wall | `gate_closed` |
| closed, in wall | `gate_closed_inwall` |
| open, not in wall | `gate_open` |
| open, in wall | `gate_open_inwall` |

Rotate with cardinal direction (same yaw table as stairs).

### 8.4 Script

- **Interact:** if not powered, toggle `open`, play open/close sound  
- **Redstone:** power on → open+powered; power off → closed+unpowered  
- **in_wall:** true if blocks on both sides perpendicular to facing are walls  
- On place: update in_wall + nearby walls/fences  

Gate connection to fences depends on working fence `conn` updates (fence must join first).

### 8.5 Recipe

```json
"pattern": ["S#S", "S#S"],
"key": { "#": { "item": "{ns}:{base}" }, "S": { "item": "minecraft:stick" } },
"result": { "item": "{ns}:{base}_fence_gate", "count": 1 }
```

---

## 9. Geometry inventory (per material)

Produce these RP models under `models/blocks/` with ids `{geo}.NAME`:

**Slabs:** `slab_bottom`, `slab_top`  

**Stairs (10):**  
`stairs_straight_bottom/top`,  
`stairs_inner_left/right_bottom/top`,  
`stairs_outer_left/right_bottom/top`  

**Fence (16):** `fence_0000` … `fence_1111` (binary NESW in **filename**; remember E↔W when **binding** to world bits)  

**Wall:** `wall_p{0|1}_{NESW}_{short|tall}` matrix used by pack (post bit + 4 connections + height)  

**Gate (4):** `gate_closed`, `gate_open`, `gate_closed_inwall`, `gate_open_inwall`  

Texture: one full-block texture on all faces (`terrain_texture.json` → `{tex}`).

---

## 10. Script module checklist

| Feature | Custom component | Events |
|---------|------------------|--------|
| Fence connect | `{ns}:fence_update` | onPlace / onPlayerBreak + world place/break neighbour refresh |
| Wall connect | `{ns}:wall_update` | same |
| Slab stack/place | `{ns}:slab_stacking` | `playerInteractWithBlock` + `playerPlaceBlock` + double break drop |
| Gate | `{ns}:fence_gate` | interact, redstone, onPlace |

Register **all** components in `system.beforeEvents.startup` even if empty `{}` so the block JSON keys are valid.

---

## 11. Orientation cheat sheet (do not reverse without re-testing)

| System | N/S (Z) | E/W (X) |
|--------|---------|---------|
| Fence world→mesh | **1:1** | **swap** (east bit → west mesh file) |
| Wall world→mesh | **1:1** | **swap** |
| Stairs trait left/right | n/a | **swap L↔R mesh names** |
| Stairs facing | rotate Y | rotate Y |

Symptoms if wrong:

- Arms/posts **point outward** / gaps in middle → need E↔W swap (or remove an incorrect N/S swap)  
- Stair L looks mirrored → flip L/R map  
- Block missing from give/creative → schema section 1  

---

## 12. Applying to a full mod (procedure)

### Automated (recommended)

Use the portable kit — proven on Rob Mod Bedrock **v1.7.1**:

```bash
# Interactive — asks about process_only.xlsx first
py -3 tools/run_generator.py

# CLI — only textures listed in process_only.xlsx
py -3 tools/apply_variants.py --bp PATH/BP --rp PATH/RP --ns yournamespace --process-only process_only.xlsx
```

See **[kit/README.md](./kit/README.md)** and **[APPLY_TO_MCADDON.md](./APPLY_TO_MCADDON.md)**.

**`process_only.xlsx`:** column A texture names (`brushedbrick_001.png`, …). Only those materials get variants — not every file under `/blocks`.

Generates: full + stairs + slab + fence + wall + fence gate (recipes, loot, lang, geometries, script).  
**Does not** create fence posts (removed as duplicates of fence).  
**Final step:** regenerates unique BP/RP UUIDs (and BP→RP dependency) so the pack never clashes with the source addon — use `--uuids-only` to re-stamp, `--keep-uuids` to skip.

### Manual checklist

1. Set all custom blocks to `format_version` **1.26.30** (or current).  
2. Fix **every** block: AO float, `minecraft:tags`, direct custom components, valid `menu_category.group`.  
3. For each full block `{base}`, generate five variants with shared texture/stats.  
4. Import/generate geos once; reuse mapping tables from sections 4–8.  
5. One shared script using suffix checks (`endsWith("_fence")` etc.), not one-off constants.  
6. Add recipes with `unlock` for each variant.  
7. Bump pack version; enable BP+RP; content log clean of `block_definitions` errors.  
8. Smoke test **per axis** with screenshots (N/S/E/W view labels) for fence + wall lines before mass-generating hundreds of blocks.

### Script notes (production)

- Slab side top/bottom: use `getBlockFromViewDirection` + ray-march hit Y (do not default only to bottom).  
- Slab same-cell merge: placing opposite half into a single slab cell → double.  
- Selection box clamp Y ≤ 16 (legacy fence posts often failed this).  
- No fence posts.

---

## 13. Trial file map (concrete examples)

| Role | Path |
|------|------|
| Full block | `rmbv_bp/blocks/brbrickblock_001.json` |
| Stairs | `rmbv_bp/blocks/brbrickblock_001_stairs.json` |
| Slab | `rmbv_bp/blocks/brbrickblock_001_slab.json` |
| Fence | `rmbv_bp/blocks/brbrickblock_001_fence.json` |
| Wall | `rmbv_bp/blocks/brbrickblock_001_wall.json` |
| Gate | `rmbv_bp/blocks/brbrickblock_001_fence_gate.json` |
| Script | `rmbv_bp/scripts/main.js` |
| Generator | `tools/build_trial.py` |
| Geos | `rmbv_rp/models/blocks/*.geo.json` |
| Textures | `rmbv_rp/textures/terrain_texture.json` |
| Pack | `brbrick_001_variants_trial.mcaddon` (v1.0.7) |

---

## 14. Content-log failures already solved (quick lookup)

| Log message | Fix |
|-------------|-----|
| `ambient_occlusion: invalid numeric value` | Use float `1.0` |
| `tag:… not present in the Schema` | Use `minecraft:tags: []` |
| `minecraft:custom_components: not present in the Schema` | Direct `"{ns}:name": {}` |
| Item missing / recipe malformed | Block failed schema first; fix block |
| `Recipes require unlock data` | Add `unlock` array |
| Custom component not used | Block rejected or wrong component key |
| Arms outward / wall gaps | E↔W mesh swap; no N/S swap on these geos |
| Stair L wrong | L↔R mesh swap vs trait |

---

*End of portable reference. Verified against trial pack behaviour with in-game screenshots for fence/wall axes and playtests for stairs, slabs, and gates.*
