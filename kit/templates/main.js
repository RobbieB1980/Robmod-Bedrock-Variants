import {
  system,
  world,
  BlockPermutation,
  GameMode,
  ItemStack,
} from "@minecraft/server";

const NS = "__NS__";
const NS_COLON = "__NS__:";
const CONN_STATE = "__NS__:conn";
const SLAB_TYPE = "__NS__:slab_type";
const WALL_N = "__NS__:wall_n";
const WALL_E = "__NS__:wall_e";
const WALL_S = "__NS__:wall_s";
const WALL_W = "__NS__:wall_w";
const WALL_POST = "__NS__:wall_post";
const GATE_OPEN = "__NS__:open";
const GATE_POWERED = "__NS__:powered";
const GATE_IN_WALL = "__NS__:in_wall";
const DIR_STATE = "minecraft:cardinal_direction";
const HALF_STATE = "minecraft:vertical_half";
// Legacy stairs (blocks not yet upgraded)
const SHAPE_STATE = "__NS__:shape";

const BIT = { north: 0, south: 1, east: 2, west: 3 };
const CONN_DIRS = ["north", "south", "east", "west"];
const OPPOSITE = { north: "south", south: "north", east: "west", west: "east" };
const CCW = { north: "west", west: "south", south: "east", east: "north" };
const CW = { north: "east", east: "south", south: "west", west: "north" };

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

function isOur(id) {
  return typeof id === "string" && id.startsWith(NS_COLON);
}
function isStair(id) {
  return isOur(id) && id.endsWith("_stairs");
}
function isSlab(id) {
  return isOur(id) && id.endsWith("_slab");
}
function isFence(id) {
  return isOur(id) && id.endsWith("_fence") && !id.endsWith("_fence_gate");
}
function isWall(id) {
  return isOur(id) && id.endsWith("_wall");
}
function isGate(id) {
  return isOur(id) && id.endsWith("_fence_gate");
}
function isOurBase(id) {
  if (!isOur(id)) return false;
  return (
    !id.endsWith("_stairs") &&
    !id.endsWith("_slab") &&
    !id.endsWith("_fence") &&
    !id.endsWith("_wall") &&
    !id.endsWith("_fence_gate")
  );
}
function slabToBase(id) {
  return id.endsWith("_slab") ? id.slice(0, -5) : id;
}

function neighbor(block, dir) {
  if (!block || !block.isValid) return undefined;
  const d = DIR_OFFSET[dir];
  if (!d) return undefined;
  const { x, y, z } = block.location;
  try {
    return block.dimension.getBlock({ x: x + d.x, y: y + d.y, z: z + d.z });
  } catch {
    return undefined;
  }
}

function safeState(block, state) {
  try {
    return block.permutation.getState(state);
  } catch {
    return undefined;
  }
}

function hasState(block, state) {
  return safeState(block, state) !== undefined;
}

function canFenceConnect(other) {
  if (!other || !other.isValid) return false;
  try {
    if (other.isAir || other.isLiquid) return false;
  } catch (_) {}
  const id = other.typeId;
  if (isFence(id) || isGate(id)) return true;
  if (id.includes("fence_gate") || id.includes("fencegate")) return true;
  if (id.includes("fence")) return true;
  return false;
}

function setFenceMask(block, mask) {
  try {
    block.setPermutation(
      BlockPermutation.resolve(block.typeId, { [CONN_STATE]: mask })
    );
  } catch (err) {
    console.warn(`[__NS__] setFenceMask failed: ${err}`);
  }
}

function updateFence(block) {
  if (!block || !block.isValid || !isFence(block.typeId)) return;
  if (!hasState(block, CONN_STATE)) return;
  let mask = 0;
  if (canFenceConnect(neighbor(block, "north"))) mask |= 1 << BIT.north;
  if (canFenceConnect(neighbor(block, "south"))) mask |= 1 << BIT.south;
  if (canFenceConnect(neighbor(block, "east"))) mask |= 1 << BIT.east;
  if (canFenceConnect(neighbor(block, "west"))) mask |= 1 << BIT.west;
  if (safeState(block, CONN_STATE) === mask) return;
  setFenceMask(block, mask);
}

function updateFenceNeighborhood(block) {
  if (!block || !block.isValid) return;
  updateFence(block);
  for (const d of CONN_DIRS) {
    const n = neighbor(block, d);
    if (n && isFence(n.typeId)) updateFence(n);
  }
}

function isSolidForWall(block) {
  if (!block || !block.isValid) return false;
  try {
    if (block.isAir || block.isLiquid) return false;
  } catch (_) {}
  const id = block.typeId;
  if (isWall(id) || isGate(id)) return true;
  if (isFence(id)) return true;
  if (
    id.includes("slab") ||
    id.includes("stairs") ||
    id.includes("button") ||
    id.includes("pressure_plate") ||
    id.includes("torch") ||
    id.includes("sign") ||
    id.includes("rail")
  ) {
    return false;
  }
  if (isOurBase(id)) return true;
  try {
    if (typeof block.isSolid === "boolean") return block.isSolid;
  } catch (_) {}
  return true;
}

function sideConnection(neighborBlock, aboveNeighbor) {
  if (!neighborBlock || !neighborBlock.isValid) return "none";
  try {
    if (neighborBlock.isAir) return "none";
  } catch (_) {}
  if (isWall(neighborBlock.typeId) || isGate(neighborBlock.typeId)) {
    return aboveNeighbor && isSolidForWall(aboveNeighbor) ? "tall" : "short";
  }
  if (isSolidForWall(neighborBlock)) {
    return aboveNeighbor && isSolidForWall(aboveNeighbor) ? "tall" : "short";
  }
  return "none";
}

function recomputeWallModern(block) {
  if (!block || !block.isValid || !isWall(block.typeId)) return;
  if (!hasState(block, WALL_N)) return;
  const dim = block.dimension;
  const { x, y, z } = block.location;
  const nB = dim.getBlock({ x, y, z: z - 1 });
  const eB = dim.getBlock({ x: x + 1, y, z });
  const sB = dim.getBlock({ x, y, z: z + 1 });
  const wB = dim.getBlock({ x: x - 1, y, z });
  const above = dim.getBlock({ x, y: y + 1, z });

  const wall_n = sideConnection(nB, nB && dim.getBlock({ x: nB.x, y: y + 1, z: nB.z }));
  const wall_e = sideConnection(eB, eB && dim.getBlock({ x: eB.x, y: y + 1, z: eB.z }));
  const wall_s = sideConnection(sB, sB && dim.getBlock({ x: sB.x, y: y + 1, z: sB.z }));
  const wall_w = sideConnection(wB, wB && dim.getBlock({ x: wB.x, y: y + 1, z: wB.z }));

  let post = true;
  const straightNS =
    wall_n === "short" &&
    wall_s === "short" &&
    wall_e === "none" &&
    wall_w === "none";
  const straightEW =
    wall_e === "short" &&
    wall_w === "short" &&
    wall_n === "none" &&
    wall_s === "none";
  const forcePost = above && isSolidForWall(above);
  if ((straightNS || straightEW) && !forcePost) post = false;
  if ([wall_n, wall_e, wall_s, wall_w].every((v) => v === "none")) post = true;

  try {
    block.setPermutation(
      BlockPermutation.resolve(block.typeId, {
        [WALL_N]: wall_n,
        [WALL_E]: wall_e,
        [WALL_S]: wall_s,
        [WALL_W]: wall_w,
        [WALL_POST]: post,
      })
    );
  } catch (err) {
    console.warn(`[__NS__] wall update failed: ${err}`);
  }
}

/** Legacy walls still using __NS__:conn 0–15 */
function recomputeWallLegacy(block) {
  if (!block || !block.isValid || !isWall(block.typeId)) return;
  if (!hasState(block, CONN_STATE) || hasState(block, WALL_N)) return;
  let mask = 0;
  for (const d of CONN_DIRS) {
    const n = neighbor(block, d);
    if (!n) continue;
    if (isWall(n.typeId) || isFence(n.typeId) || isOurBase(n.typeId)) {
      mask |= 1 << BIT[d];
    } else {
      try {
        if (!n.isAir && !n.isLiquid && n.isSolid) mask |= 1 << BIT[d];
      } catch (_) {}
    }
  }
  if (safeState(block, CONN_STATE) === mask) return;
  try {
    block.setPermutation(
      BlockPermutation.resolve(block.typeId, { [CONN_STATE]: mask })
    );
  } catch (err) {
    console.warn(`[__NS__] legacy wall failed: ${err}`);
  }
}

function recomputeWall(block) {
  if (!block || !isWall(block.typeId)) return;
  if (hasState(block, WALL_N)) recomputeWallModern(block);
  else recomputeWallLegacy(block);
}

function updateNearbyWalls(block) {
  if (!block || !block.isValid) return;
  const dim = block.dimension;
  const { x, y, z } = block.location;
  for (const p of [
    { x, y, z },
    { x, y, z: z - 1 },
    { x: x + 1, y, z },
    { x, y, z: z + 1 },
    { x: x - 1, y, z },
    { x, y: y + 1, z },
    { x, y: y - 1, z },
  ]) {
    const b = dim.getBlock(p);
    if (b && isWall(b.typeId)) recomputeWall(b);
  }
}

function updateGateInWall(block) {
  if (!block || !block.isValid || !isGate(block.typeId)) return;
  const dir = safeState(block, DIR_STATE) ?? "north";
  const dim = block.dimension;
  const { x, y, z } = block.location;
  let a, b;
  if (dir === "north" || dir === "south") {
    a = dim.getBlock({ x: x - 1, y, z });
    b = dim.getBlock({ x: x + 1, y, z });
  } else {
    a = dim.getBlock({ x, y, z: z - 1 });
    b = dim.getBlock({ x, y, z: z + 1 });
  }
  const inWall =
    !!(a && (isWall(a.typeId) || a.typeId.includes("wall"))) &&
    !!(b && (isWall(b.typeId) || b.typeId.includes("wall")));
  const open = !!safeState(block, GATE_OPEN);
  const powered = !!safeState(block, GATE_POWERED);
  try {
    block.setPermutation(
      BlockPermutation.resolve(block.typeId, {
        [DIR_STATE]: dir,
        [GATE_OPEN]: open,
        [GATE_POWERED]: powered,
        [GATE_IN_WALL]: inWall,
      })
    );
  } catch (err) {
    console.warn(`[__NS__] gate in_wall failed: ${err}`);
  }
}

// --- Legacy stair shape (only for non-upgraded stairs with __NS__:shape) ---
function isMatchingStair(block, typeId, half) {
  if (!block || block.typeId !== typeId) return false;
  return safeState(block, HALF_STATE) === half;
}
function isPerp(a, b) {
  if (!a || !b) return false;
  const aNS = a === "north" || a === "south";
  const bNS = b === "north" || b === "south";
  return aNS !== bNS;
}
function calculateShape(block) {
  const typeId = block.typeId;
  const half = safeState(block, HALF_STATE);
  const facing = safeState(block, DIR_STATE);
  if (!half || !facing) return "straight";
  const sides = {
    north: neighbor(block, "north"),
    south: neighbor(block, "south"),
    east: neighbor(block, "east"),
    west: neighbor(block, "west"),
  };
  const order = [CCW[facing], CW[facing], OPPOSITE[facing], facing];
  let hitDir = null;
  let hitFacing = null;
  for (const dir of order) {
    const nb = sides[dir];
    if (!isMatchingStair(nb, typeId, half)) continue;
    const nf = safeState(nb, DIR_STATE);
    if (!isPerp(facing, nf)) continue;
    hitDir = dir;
    hitFacing = nf;
    break;
  }
  if (!hitDir) return "straight";
  if (hitDir === CCW[facing]) return "inner_right";
  if (hitDir === CW[facing]) return "inner_left";
  if (hitFacing === CCW[facing]) return "inner_right";
  if (hitFacing === CW[facing]) return "inner_left";
  return "inner_left";
}
function setShape(block, shape) {
  if (!block || !isStair(block.typeId) || !hasState(block, SHAPE_STATE)) return;
  if (safeState(block, SHAPE_STATE) === shape) return;
  try {
    block.setPermutation(block.permutation.withState(SHAPE_STATE, shape));
  } catch {
    try {
      block.setPermutation(
        BlockPermutation.resolve(block.typeId, {
          [DIR_STATE]: safeState(block, DIR_STATE) ?? "north",
          [HALF_STATE]: safeState(block, HALF_STATE) ?? "bottom",
          [SHAPE_STATE]: shape,
        })
      );
    } catch (_) {}
  }
}
function updateLegacyStairs(block) {
  if (!block || !isStair(block.typeId) || !hasState(block, SHAPE_STATE)) return;
  setShape(block, calculateShape(block));
  for (const d of CONN_DIRS) {
    const n = neighbor(block, d);
    if (n && isStair(n.typeId) && hasState(n, SHAPE_STATE)) {
      setShape(n, calculateShape(n));
    }
  }
}

system.beforeEvents.startup.subscribe((init) => {
  init.blockComponentRegistry.registerCustomComponent(`${NS}:slab_stacking`, {});

  init.blockComponentRegistry.registerCustomComponent(`${NS}:fence_update`, {
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
          if (b && isFence(b.typeId)) updateFence(b);
        }
      });
    },
  });

  init.blockComponentRegistry.registerCustomComponent(`${NS}:wall_update`, {
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
        for (const p of [
          { x: loc.x, y: loc.y, z: loc.z - 1 },
          { x: loc.x + 1, y: loc.y, z: loc.z },
          { x: loc.x, y: loc.y, z: loc.z + 1 },
          { x: loc.x - 1, y: loc.y, z: loc.z },
          { x: loc.x, y: loc.y + 1, z: loc.z },
        ]) {
          const b = dim.getBlock(p);
          if (b && isWall(b.typeId)) recomputeWall(b);
          if (b && isFence(b.typeId)) updateFence(b);
        }
      });
    },
  });

  init.blockComponentRegistry.registerCustomComponent(`${NS}:fence_gate`, {
    onPlace(event) {
      system.run(() => {
        updateGateInWall(event.block);
        updateNearbyWalls(event.block);
        updateFenceNeighborhood(event.block);
      });
    },
    onPlayerInteract(event) {
      const block = event.block;
      if (!block || !isGate(block.typeId)) return;
      const powered = !!safeState(block, GATE_POWERED);
      if (powered) return;
      const open = !!safeState(block, GATE_OPEN);
      const dir = safeState(block, DIR_STATE) ?? "north";
      const inWall = !!safeState(block, GATE_IN_WALL);
      const next = !open;
      const typeId = block.typeId;
      system.run(() => {
        try {
          block.setPermutation(
            BlockPermutation.resolve(typeId, {
              [DIR_STATE]: dir,
              [GATE_OPEN]: next,
              [GATE_POWERED]: powered,
              [GATE_IN_WALL]: inWall,
            })
          );
          block.dimension.playSound(
            next ? "open.fence_gate" : "close.fence_gate",
            block.location
          );
          updateFenceNeighborhood(block);
        } catch (err) {
          console.warn(`[__NS__] gate toggle failed: ${err}`);
        }
      });
    },
    onRedstoneUpdate(event) {
      const block = event.block;
      if (!block || !isGate(block.typeId)) return;
      const power = event.power ?? event.redstonePower ?? 0;
      const poweredNow = power > 0;
      const wasPowered = !!safeState(block, GATE_POWERED);
      const wasOpen = !!safeState(block, GATE_OPEN);
      const dir = safeState(block, DIR_STATE) ?? "north";
      const inWall = !!safeState(block, GATE_IN_WALL);
      let open = wasOpen;
      if (poweredNow && !wasPowered) open = true;
      else if (!poweredNow && wasPowered) open = false;
      const typeId = block.typeId;
      system.run(() => {
        try {
          block.setPermutation(
            BlockPermutation.resolve(typeId, {
              [DIR_STATE]: dir,
              [GATE_OPEN]: open,
              [GATE_POWERED]: poweredNow,
              [GATE_IN_WALL]: inWall,
            })
          );
          if (open !== wasOpen) {
            block.dimension.playSound(
              open ? "open.fence_gate" : "close.fence_gate",
              block.location
            );
          }
          updateFenceNeighborhood(block);
        } catch (err) {
          console.warn(`[__NS__] gate redstone failed: ${err}`);
        }
      });
    },
  });
});

/** Normalize Direction enum / string → up|down|north|south|east|west */
function normalizeFace(face) {
  if (face === undefined || face === null) return undefined;
  if (FACE_TO_DIR[face]) return FACE_TO_DIR[face];
  let s = String(face);
  if (s.includes(".")) s = s.split(".").pop();
  s = s.toLowerCase();
  if (
    s === "up" ||
    s === "down" ||
    s === "north" ||
    s === "south" ||
    s === "east" ||
    s === "west"
  ) {
    return s;
  }
  return undefined;
}

function slabEffective(block) {
  const slabType = safeState(block, SLAB_TYPE);
  if (slabType === "double") return "double";
  if (slabType === "top" || slabType === "bottom") return slabType;
  const half = safeState(block, HALF_STATE);
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

function consumeSlab(player, slabId) {
  if (!player || isCreative(player)) return;
  try {
    const inv = player.getComponent("minecraft:inventory");
    const container = inv?.container;
    const slot = player.selectedSlotIndex;
    if (!container) return;
    const stack = container.getItem(slot);
    if (stack && stack.typeId === slabId) {
      if (stack.amount > 1) {
        stack.amount -= 1;
        container.setItem(slot, stack);
      } else {
        container.setItem(slot, undefined);
      }
    }
  } catch (err) {
    console.warn(`[__NS__] slab consume failed: ${err}`);
  }
}

function setDoubleSlab(block) {
  block.setPermutation(
    BlockPermutation.resolve(block.typeId, {
      [SLAB_TYPE]: "double",
      [HALF_STATE]: "bottom",
    })
  );
}

function completeToDouble(block, player, slabId) {
  if (!block) return false;
  try {
    if (!block.isValid) return false;
  } catch (_) {}
  if (block.typeId !== slabId) return false;
  if (!hasState(block, SLAB_TYPE)) return false;
  if (slabEffective(block) === "double") return false;
  try {
    setDoubleSlab(block);
    consumeSlab(player, slabId);
    block.dimension.playSound("use.stone", block.location);
    return true;
  } catch (err) {
    console.warn(`[__NS__] completeToDouble failed: ${err}`);
    return false;
  }
}

function tryMergeAfterPlace(placed) {
  if (!placed || !isSlab(placed.typeId)) return;
  if (!hasState(placed, SLAB_TYPE)) return;
  if (slabEffective(placed) === "double") return;
  const dim = placed.dimension;
  const { x, y, z } = placed.location;
  const half = safeState(placed, HALF_STATE) ?? "bottom";
  if (half === "top") {
    const below = dim.getBlock({ x, y: y - 1, z });
    if (
      below &&
      below.typeId === placed.typeId &&
      slabEffective(below) === "bottom"
    ) {
      try {
        setDoubleSlab(below);
        placed.setType("minecraft:air");
      } catch (err) {
        console.warn(`[__NS__] merge below failed: ${err}`);
      }
      return;
    }
  }
  if (half === "bottom") {
    const above = dim.getBlock({ x, y: y + 1, z });
    if (
      above &&
      above.typeId === placed.typeId &&
      slabEffective(above) === "top"
    ) {
      try {
        setDoubleSlab(above);
        placed.setType("minecraft:air");
      } catch (err) {
        console.warn(`[__NS__] merge above failed: ${err}`);
      }
    }
  }
}

function isEmptyBlock(block) {
  if (!block) return true;
  try {
    if (block.isAir) return true;
  } catch (_) {}
  try {
    if (block.isLiquid) return true;
  } catch (_) {}
  let id;
  try {
    id = block.typeId;
  } catch (_) {
    return true;
  }
  if (!id || id === "minecraft:air") return true;
  if (
    id === "minecraft:water" ||
    id === "minecraft:lava" ||
    id === "minecraft:flowing_water" ||
    id === "minecraft:flowing_lava"
  ) {
    return true;
  }
  return false;
}

function canMergeOpposite(target, half, slabId) {
  if (!target || isEmptyBlock(target)) return false;
  if (target.typeId !== slabId || !hasState(target, SLAB_TYPE)) return false;
  const eff = slabEffective(target);
  if (eff === "double") return false;
  return (
    (half === "bottom" && eff === "top") || (half === "top" && eff === "bottom")
  );
}

function canPlaceOrMergeSlab(target, half, slabId) {
  if (!target || isEmptyBlock(target)) return true;
  return canMergeOpposite(target, half, slabId);
}

function resolveSlabPerm(slabId, half) {
  return BlockPermutation.resolve(slabId, {
    [SLAB_TYPE]: half === "top" ? "top" : "bottom",
    [HALF_STATE]: half === "top" ? "top" : "bottom",
  });
}

function placeSlabAt(dim, pos, half, player, slabId) {
  let target;
  try {
    target = dim.getBlock(pos);
  } catch {
    target = undefined;
  }

  try {
    if (target && canMergeOpposite(target, half, slabId)) {
      setDoubleSlab(target);
      consumeSlab(player, slabId);
      try {
        dim.playSound("use.stone", pos);
      } catch (_) {}
      return true;
    }

    if (target && !isEmptyBlock(target)) return false;

    const perm = resolveSlabPerm(slabId, half);
    let placed = false;
    try {
      if (typeof dim.setBlockPermutation === "function") {
        dim.setBlockPermutation(pos, perm);
        placed = true;
      }
    } catch (_) {}
    if (!placed && target) {
      try {
        target.setPermutation(perm);
        placed = true;
      } catch (_) {}
    }
    if (!placed && target) {
      try {
        target.setType(slabId);
        target.setPermutation(perm);
        placed = true;
      } catch (_) {}
    }
    if (!placed) return false;

    consumeSlab(player, slabId);
    try {
      dim.playSound("use.stone", pos);
    } catch (_) {}
    return true;
  } catch (err) {
    console.warn(`[__NS__] placeSlabAt failed: ${err}`);
    return false;
  }
}

function copyVec3(v) {
  if (!v || typeof v.y !== "number") return undefined;
  return {
    x: typeof v.x === "number" ? v.x : 0,
    y: v.y,
    z: typeof v.z === "number" ? v.z : 0,
  };
}

/** 0–1 height of hit within block (0=bottom, 1=top). */
function localYFromFaceLocation(faceLocation, blockLoc) {
  if (!faceLocation || typeof faceLocation.y !== "number") return undefined;
  const y = faceLocation.y;
  // Relative 0–1 (Script API)
  if (y >= 0 && y <= 1.0001) return y;
  // Pixels 0–16
  if (y > 1 && y <= 16.0001) return y / 16;
  // Absolute world Y
  if (blockLoc && typeof blockLoc.y === "number") {
    const local = y - blockLoc.y;
    if (local >= -0.05 && local <= 1.05) {
      return Math.min(1, Math.max(0, local));
    }
  }
  const frac = y - Math.floor(y);
  return frac;
}

/**
 * March the look ray until it enters the block AABB; return local Y of first hit.
 * Works without faceLocation and for every face.
 */
function localYFromRayMarch(blockLoc, head, view) {
  if (!blockLoc || !head || !view) return undefined;
  const bx = blockLoc.x;
  const by = blockLoc.y;
  const bz = blockLoc.z;
  let wasOutside = true;
  for (let t = 0.02; t <= 12; t += 0.02) {
    const px = head.x + view.x * t;
    const py = head.y + view.y * t;
    const pz = head.z + view.z * t;
    const inside =
      px >= bx - 0.001 &&
      px <= bx + 1.001 &&
      py >= by - 0.001 &&
      py <= by + 1.001 &&
      pz >= bz - 0.001 &&
      pz <= bz + 1.001;
    if (inside && wasOutside) {
      return Math.min(1, Math.max(0, py - by));
    }
    wasOutside = !inside;
  }
  return undefined;
}

/**
 * Vanilla slab half rules for the *destination cell*:
 * - Click UP face   → bottom slab in cell above
 * - Click DOWN face → top slab in cell below
 * - Click SIDE      → top if hit Y ≥ 0.5 else bottom (same cell neighbour)
 */
function halfForPlacement(faceDir, faceLocation, blockLoc, head, view) {
  if (faceDir === "up") return "bottom";
  if (faceDir === "down") return "top";

  let localY = localYFromFaceLocation(faceLocation, blockLoc);
  if (localY === undefined) {
    localY = localYFromRayMarch(blockLoc, head, view);
  }
  // Prefer slightly more than 0.5 bias so "aim upper half" is easy
  if (localY === undefined) return "bottom";
  return localY >= 0.5 ? "top" : "bottom";
}

/**
 * Best-effort hit info: raycast first (most accurate faceLocation), then event.
 */
function resolveHit(player, event) {
  const eventFace = normalizeFace(event.blockFace ?? event.face);
  const eventLoc = {
    x: event.block.location.x,
    y: event.block.location.y,
    z: event.block.location.z,
  };
  let head;
  let view;
  try {
    const h = player.getHeadLocation();
    const v = player.getViewDirection();
    head = { x: h.x, y: h.y, z: h.z };
    view = { x: v.x, y: v.y, z: v.z };
  } catch (_) {}

  // Primary: view raycast (reliable faceLocation on most 1.26 builds)
  try {
    if (typeof player.getBlockFromViewDirection === "function") {
      const hit = player.getBlockFromViewDirection({
        maxDistance: 10,
        includePassableBlocks: true,
      });
      if (hit && hit.block) {
        const faceDir = normalizeFace(hit.face) ?? eventFace;
        const loc = {
          x: hit.block.location.x,
          y: hit.block.location.y,
          z: hit.block.location.z,
        };
        return {
          block: hit.block,
          faceDir,
          loc,
          faceLocation: copyVec3(hit.faceLocation) ?? copyVec3(event.faceLocation),
          head,
          view,
        };
      }
    }
  } catch (_) {}

  return {
    block: event.block,
    faceDir: eventFace,
    loc: eventLoc,
    faceLocation: copyVec3(event.faceLocation),
    head,
    view,
  };
}

function neighborPos(loc, faceDir) {
  const off = DIR_OFFSET[faceDir];
  if (!off) return undefined;
  return { x: loc.x + off.x, y: loc.y + off.y, z: loc.z + off.z };
}

/**
 * Script-place a slab into the cell adjacent to the clicked face.
 * Used for full blocks + double slabs (custom solids reject vanilla place).
 */
function placeAdjacentFromHit(hit, player, slabId) {
  if (!hit.faceDir) return false;
  const dest = neighborPos(hit.loc, hit.faceDir);
  if (!dest) return false;
  const half = halfForPlacement(
    hit.faceDir,
    hit.faceLocation,
    hit.loc,
    hit.head,
    hit.view
  );
  return placeSlabAt(hit.block.dimension, dest, half, player, slabId);
}

world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
  try {
    if (event.isFirstEvent === false) return;
  } catch (_) {}
  const { block, player, itemStack } = event;
  if (!itemStack || !isSlab(itemStack.typeId)) return;
  if (!block) return;

  const slabId = itemStack.typeId;
  // Only modern slabs (have slab_type state on the block definition)
  // Legacy packs without that state keep full vanilla behaviour.

  const hit = resolveHit(player, event);
  if (!hit.faceDir) return;

  const clicked = hit.block;
  const dim = clicked.dimension;
  const baseId = slabToBase(slabId);

  // ========== Matching modern slab ==========
  if (clicked.typeId === slabId && hasState(clicked, SLAB_TYPE)) {
    const effective = slabEffective(clicked);

    // --- Double: treat as full solid cube ---
    if (effective === "double") {
      event.cancel = true;
      const faceDir = hit.faceDir;
      const faceLocation = hit.faceLocation;
      const loc = { ...hit.loc };
      const head = hit.head;
      const view = hit.view;
      system.run(() => {
        const dest = neighborPos(loc, faceDir);
        if (!dest) return;
        const half = halfForPlacement(faceDir, faceLocation, loc, head, view);
        placeSlabAt(dim, dest, half, player, slabId);
      });
      return;
    }

    // --- Single ---
    const faceDir = hit.faceDir;
    const faceLocation = hit.faceLocation;
    const loc = { ...hit.loc };
    const head = hit.head;
    const view = hit.view;
    const halfWanted = halfForPlacement(
      faceDir,
      faceLocation,
      loc,
      head,
      view
    );

    // Click empty half face → stack to double
    // (up on bottom slab, down on top slab)
    if (
      (faceDir === "up" && effective === "bottom") ||
      (faceDir === "down" && effective === "top")
    ) {
      event.cancel = true;
      system.run(() => {
        const b = dim.getBlock(loc);
        if (b) completeToDouble(b, player, slabId);
      });
      return;
    }

    // Side click aiming at the empty half → stack to double in place
    if (
      faceDir !== "up" &&
      faceDir !== "down" &&
      ((effective === "bottom" && halfWanted === "top") ||
        (effective === "top" && halfWanted === "bottom"))
    ) {
      event.cancel = true;
      system.run(() => {
        const b = dim.getBlock(loc);
        if (b) completeToDouble(b, player, slabId);
      });
      return;
    }

    // Place into neighbouring cell (outer faces / side of occupied half)
    const dest = neighborPos(loc, faceDir);
    if (!dest) return;
    let destBlock;
    try {
      destBlock = dim.getBlock(dest);
    } catch {
      destBlock = undefined;
    }
    // half for neighbour: for up/down outer faces use halfWanted;
    // for sides use halfWanted (top or bottom at same Y)
    if (canPlaceOrMergeSlab(destBlock, halfWanted, slabId)) {
      event.cancel = true;
      system.run(() => {
        placeSlabAt(dim, dest, halfWanted, player, slabId);
      });
    }
    return;
  }

  // ========== Any of our full solid blocks (or matching base) ==========
  // Custom solids need script place so top/side half works.
  if (isOurBase(clicked.typeId) || clicked.typeId === baseId) {
    event.cancel = true;
    const faceDir = hit.faceDir;
    const faceLocation = hit.faceLocation;
    const loc = { ...hit.loc };
    const head = hit.head;
    const view = hit.view;
    system.run(() => {
      const dest = neighborPos(loc, faceDir);
      if (!dest) return;
      const half = halfForPlacement(faceDir, faceLocation, loc, head, view);
      placeSlabAt(dim, dest, half, player, slabId);
    });
    return;
  }

  // ========== Other blocks: only merge into existing opposite single ==========
  const dest = neighborPos(hit.loc, hit.faceDir);
  if (!dest) return;
  let destBlock;
  try {
    destBlock = dim.getBlock(dest);
  } catch {
    destBlock = undefined;
  }
  const half = halfForPlacement(
    hit.faceDir,
    hit.faceLocation,
    hit.loc,
    hit.head,
    hit.view
  );
  if (canMergeOpposite(destBlock, half, slabId)) {
    event.cancel = true;
    system.run(() => {
      placeSlabAt(dim, dest, half, player, slabId);
    });
  }
});

world.afterEvents.playerBreakBlock.subscribe((event) => {
  const perm = event.brokenBlockPermutation;
  const id = perm?.type?.id;
  if (!id || !isSlab(id)) return;
  let type;
  try {
    type = perm.getState(SLAB_TYPE);
  } catch {
    return;
  }
  if (type !== "double") return;
  try {
    const dim = event.dimension;
    const loc = event.block.location;
    dim.spawnItem(new ItemStack(id, 1), {
      x: loc.x + 0.5,
      y: loc.y + 0.5,
      z: loc.z + 0.5,
    });
  } catch (err) {
    console.warn(`[__NS__] double slab drop failed: ${err}`);
  }
});

world.afterEvents.playerPlaceBlock.subscribe((event) => {
  system.run(() => {
    const block = event.block;
    if (!block) return;

    if (isSlab(block.typeId) && hasState(block, SLAB_TYPE)) {
      try {
        const half = safeState(block, HALF_STATE) ?? "bottom";
        const current = safeState(block, SLAB_TYPE);
        if (current !== "double") {
          block.setPermutation(
            BlockPermutation.resolve(block.typeId, {
              [SLAB_TYPE]: half === "top" ? "top" : "bottom",
              [HALF_STATE]: half === "top" ? "top" : "bottom",
            })
          );
        }
        tryMergeAfterPlace(block);
      } catch (err) {
        console.warn(`[__NS__] slab place sync failed: ${err}`);
      }
    }

    if (isStair(block.typeId) && hasState(block, SHAPE_STATE)) {
      updateLegacyStairs(block);
    }

    updateFenceNeighborhood(block);
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
      if (b && isGate(b.typeId)) updateGateInWall(b);
      if (b && isStair(b.typeId) && hasState(b, SHAPE_STATE)) updateLegacyStairs(b);
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
      if (!b) continue;
      if (isWall(b.typeId)) recomputeWall(b);
      if (isGate(b.typeId)) updateGateInWall(b);
      if (isFence(b.typeId)) updateFence(b);
      if (isStair(b.typeId) && hasState(b, SHAPE_STATE)) updateLegacyStairs(b);
    }
  });
});

console.log("[__NS__] vanilla-compatible variants script loaded (v1.7.0)");
