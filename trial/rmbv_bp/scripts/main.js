import {
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
