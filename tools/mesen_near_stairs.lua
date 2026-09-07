-- mesen_near_stairs.lua
-- Put Shiren one safe step from the real stairs on each generated dungeon floor.
--
-- This is a live testing helper for reaching late dungeon floors and endings quickly.
-- It scans the game's actual 32x32 floor grid; no stair coordinate is hardcoded.  The
-- script then calls the native actor relocation routine (bank 5 $5568), which clears
-- Shiren's old occupancy cell, fills the new one, refreshes his terrain state, and
-- updates both actor coordinates together.
--
-- HOW TO USE
--   1. Back up the .srm, or use a disposable emulator save state.
--   2. Enter Moonlight Exit (or another dungeon), close every menu, and stand still.
--   3. In Mesen: Debug > Script Window, open this file, then press Run (F5).
--   4. Wait for the log line beginning "READY", then press the direction it names once.
--      The normal step recenters/redraws the distant room and puts Shiren on the stairs.
--   5. Choose Proceed. Leave this script running: after the next floor has settled it
--      will place Shiren beside that floor's stairs and print the next direction.
--   6. Stop the script before resuming normal play. Its live floor changes are not
--      written into the .srm unless the game itself subsequently saves the run.
--
-- EXPECTED VISUAL NOTE
--   Relocation can cover most of the map, but the camera still belongs to the old room
--   until the named step is accepted. The screen may therefore appear unchanged briefly;
--   the ordinary step performs the game's normal camera and room redraw.
--
-- SAFETY / MEASURED FORMAT (mgbdis + live fixtures, 2026-09-07)
--   actor slots             0-$11 monsters, $12 Shiren
--   $A006/$A019/$A02C       species / X / Y arrays
--   $A052/$A065             current / maximum HP arrays
--   $B000/$B400/$B800       terrain / occupancy / feature 32x32 planes
--   $B800 == $83            the current floor's real stairs/exit feature
--   $B400 bit 7 set         no actor occupies that cell
--   5:$5568                 native actor relocation and occupancy update
--   5:$76C8                 native actor renderer
--
-- The destination must be an empty ordinary cell ($B800=$80) with the same terrain byte
-- as the stair cell. This rejects walls, actors, traps, items, Gitan and other features.
-- If the map has zero/multiple stair markers, or no safe cardinal neighbor, nothing is
-- changed and the reason is logged. The temporary WRAM trampoline restores registers,
-- shared $FF90-$FF93 scratch bytes, and its original bytes after it runs.

local LABEL = "Near Stairs"

local PLAYER_SLOT = 0x12
local ACTOR_SPECIES = 0xA006
local ACTOR_X = 0xA019
local ACTOR_Y = 0xA02C
local ACTOR_HP = 0xA052
local ACTOR_MAX_HP = 0xA065

local MAP_WIDTH = 32
local MAP_CELLS = MAP_WIDTH * MAP_WIDTH
local TERRAIN = 0xB000
local OCCUPANCY = 0xB400
local FEATURE = 0xB800
local STAIRS_FEATURE = 0x83
local EMPTY_FEATURE = 0x80

local RELOCATE = 0x5568
local RENDERER = 0x76C8
local REQUIRED_BANK = 5
local WRAPPER = 0xD780
local COMPLETE = 0xD7F0
local COMPLETE_VALUE = 0xA5

-- Floor construction exposes partially initialized arrays for a short time. Requiring
-- the exact same complete candidate on several bank-5 frames avoids relocating into it.
local STABLE_OBSERVATIONS = 12

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

local cpuT, cpuName = pick(emu.cpuType, { "gameboy", "gb" })
local memT, memName = pick(emu.memType,
                           { "gameboyMemory", "gbMemory", "gameboy" })
emu.log(LABEL .. ": cpuType=" .. tostring(cpuName)
        .. " memType=" .. tostring(memName))

local function rd(address)
  if memT ~= nil then
    local ok, value = pcall(emu.read, address, memT)
    if ok and value ~= nil then return value end
  end
  local ok, value = pcall(emu.read, address)
  if ok and value ~= nil then return value end
  return nil
end

local function wr(address, value)
  if memT ~= nil then
    local ok = pcall(emu.write, address, value, memT)
    if ok then return true end
  end
  return pcall(emu.write, address, value)
end

local function cpu_state()
  local ok, state = pcall(emu.getState)
  if not ok or type(state) ~= "table" then return nil end
  if type(state["cpu.pc"]) ~= "number"
      or type(state["cpu.sp"]) ~= "number" then
    return nil
  end
  return state
end

local phase = "watching"
local stable_key = nil
local stable_count = 0
local wrapper_original = nil
local complete_original = nil
local target_x, target_y = nil, nil
local stair_x, stair_y = nil, nil
local step_name = nil
local reported_problem = nil

local function report_once(problem)
  if problem ~= reported_problem then
    emu.log(LABEL .. ": waiting: " .. problem)
    reported_problem = problem
  end
end

local function reset_candidate()
  stable_key = nil
  stable_count = 0
end

local function restore_wrapper()
  if wrapper_original ~= nil then
    for i, value in ipairs(wrapper_original) do
      wr(WRAPPER + i - 1, value)
    end
    wrapper_original = nil
  end
  if complete_original ~= nil then
    wr(COMPLETE, complete_original)
    complete_original = nil
  end
end

local function fail(message)
  restore_wrapper()
  phase = "watching"
  reset_candidate()
  report_once(message)
end

local function live_player()
  local species = rd(ACTOR_SPECIES + PLAYER_SLOT)
  local hp = rd(ACTOR_HP + PLAYER_SLOT)
  local max_hp = rd(ACTOR_MAX_HP + PLAYER_SLOT)
  local x = rd(ACTOR_X + PLAYER_SLOT)
  local y = rd(ACTOR_Y + PLAYER_SLOT)
  if species == nil or hp == nil or max_hp == nil or x == nil or y == nil then
    return nil, nil, "cannot read the live Shiren actor"
  end
  if species ~= 0 or hp == 0 or max_hp == 0 then
    return nil, nil, "enter a live dungeon floor with every menu closed"
  end
  if x < 1 or x >= MAP_WIDTH - 1 or y < 1 or y >= MAP_WIDTH - 1 then
    return nil, nil, "Shiren's coordinates are outside the floor grid"
  end
  local occupancy = rd(OCCUPANCY + y * MAP_WIDTH + x)
  if occupancy == nil or occupancy >= 0x80
      or occupancy % 0x20 ~= PLAYER_SLOT then
    return nil, nil, "Shiren's actor and floor occupancy are not settled yet"
  end
  return x, y, nil
end

local function find_stairs()
  local found = nil
  local count = 0
  for index = 0, MAP_CELLS - 1 do
    if rd(FEATURE + index) == STAIRS_FEATURE then
      found = index
      count = count + 1
    end
  end
  if count == 0 then return nil, nil, "the generated floor has no stairs marker yet" end
  if count ~= 1 then
    return nil, nil, string.format("the floor exposes %d stairs markers, expected one", count)
  end
  return found % MAP_WIDTH, math.floor(found / MAP_WIDTH), nil
end

local DIRECTIONS = {
  -- Destination is relative to the stairs; `step` is how Shiren then enters them.
  { dx = -1, dy =  0, step = "RIGHT" },
  { dx =  1, dy =  0, step = "LEFT"  },
  { dx =  0, dy = -1, step = "DOWN"  },
  { dx =  0, dy =  1, step = "UP"    },
}

local function safe_neighbor(sx, sy)
  local stair_index = sy * MAP_WIDTH + sx
  local stair_terrain = rd(TERRAIN + stair_index)
  if stair_terrain == nil then return nil, nil, nil end

  for _, direction in ipairs(DIRECTIONS) do
    local x = sx + direction.dx
    local y = sy + direction.dy
    if x >= 1 and x < MAP_WIDTH - 1 and y >= 1 and y < MAP_WIDTH - 1 then
      local index = y * MAP_WIDTH + x
      local terrain = rd(TERRAIN + index)
      local occupancy = rd(OCCUPANCY + index)
      local feature = rd(FEATURE + index)
      if terrain == stair_terrain and occupancy ~= nil and feature ~= nil
          and occupancy % 0x100 >= 0x80 and feature == EMPTY_FEATURE then
        return x, y, direction.step
      end
    end
  end
  return nil, nil, nil
end

local function install_wrapper(state)
  local scratch = { rd(0xFF90), rd(0xFF91), rd(0xFF92), rd(0xFF93) }
  for _, value in ipairs(scratch) do
    if value == nil then
      fail("cannot preserve the game's $FF90-$FF93 scratch bytes")
      return false
    end
  end

  local resume = state["cpu.pc"]
  local wrapper = {
    0xF5, 0xC5, 0xD5, 0xE5,                  -- push af / bc / de / hl
    0x3E, PLAYER_SLOT, 0xEA, 0x90, 0xFF,    -- actor = Shiren
    0x3E, target_x, 0xEA, 0x92, 0xFF,       -- destination X
    0x3E, target_y, 0xEA, 0x93, 0xFF,       -- destination Y
    0xCD, RELOCATE % 0x100,
          math.floor(RELOCATE / 0x100),       -- call native 5:$5568
    0x3E, PLAYER_SLOT, 0x06, 0x01,
    0xCD, RENDERER % 0x100,
          math.floor(RENDERER / 0x100),       -- enqueue Shiren's new actor position
  }

  -- Restore shared scratch before returning to the interrupted native instruction.
  for index, value in ipairs(scratch) do
    table.insert(wrapper, 0x3E)                -- ld a,value
    table.insert(wrapper, value)
    table.insert(wrapper, 0xEA)                -- ld ($FF8F+index),a
    table.insert(wrapper, (0x8F + index) % 0x100)
    table.insert(wrapper, 0xFF)
  end
  local tail = {
    0x3E, COMPLETE_VALUE, 0xEA,
          COMPLETE % 0x100, math.floor(COMPLETE / 0x100), -- mark wrapper complete
    0xE1, 0xD1, 0xC1, 0xF1,                  -- pop hl / de / bc / af
    0xC3, resume % 0x100, math.floor(resume / 0x100), -- jp interrupted PC
  }
  for _, value in ipairs(tail) do table.insert(wrapper, value) end

  wrapper_original = {}
  for i = 1, #wrapper do
    local old = rd(WRAPPER + i - 1)
    if old == nil then
      fail(string.format("cannot read temporary WRAM at $%04X", WRAPPER + i - 1))
      return false
    end
    wrapper_original[i] = old
  end
  complete_original = rd(COMPLETE)
  if complete_original == nil or not wr(COMPLETE, 0) then
    fail("cannot reserve the temporary WRAM completion marker")
    return false
  end
  for i, value in ipairs(wrapper) do
    if not wr(WRAPPER + i - 1, value) then
      fail(string.format("cannot write temporary WRAM at $%04X", WRAPPER + i - 1))
      return false
    end
  end

  local ok, err = pcall(emu.setState, { ["cpu.pc"] = WRAPPER })
  if not ok then
    fail("emu.setState() failed: " .. tostring(err))
    return false
  end
  phase = "running"
  return true
end

local function finish_wrapper()
  -- The wrapper writes this only after the native relocation/renderer have returned and
  -- shared scratch has been restored. It is then safe to reclaim every temporary byte.
  if rd(COMPLETE) ~= COMPLETE_VALUE then return end
  restore_wrapper()
  phase = "verifying"
  reset_candidate()
end

local function verify_relocation()
  if rd(0x4000) ~= REQUIRED_BANK then return end
  local moved = (rd(ACTOR_X + PLAYER_SLOT) == target_x
                 and rd(ACTOR_Y + PLAYER_SLOT) == target_y)
  phase = "watching"
  if not moved then
    report_once("native relocation returned without moving Shiren")
    return
  end

  reported_problem = nil
  emu.log(string.format(
    "%s: READY at (%d,%d), stairs (%d,%d). Press %s once, then choose Proceed.",
    LABEL, target_x, target_y, stair_x, stair_y, step_name))
end

local function on_frame()
  if phase == "running" then
    finish_wrapper()
    return
  end
  if phase == "verifying" then
    verify_relocation()
    return
  end

  -- $4000 is the bank marker used throughout the repository's Mesen helpers. Calling
  -- $5568 is valid only while bank 5 is mapped; the same context exposes SRAM bank 0.
  if rd(0x4000) ~= REQUIRED_BANK then return end

  local x, y, player_problem = live_player()
  if player_problem ~= nil then
    reset_candidate()
    report_once(player_problem)
    return
  end
  local sx, sy, stair_problem = find_stairs()
  if stair_problem ~= nil then
    reset_candidate()
    report_once(stair_problem)
    return
  end

  -- Already beside or on the stairs: do not fight ordinary player movement.
  if math.abs(x - sx) + math.abs(y - sy) <= 1 then
    reset_candidate()
    reported_problem = nil
    return
  end

  local tx, ty, step = safe_neighbor(sx, sy)
  if tx == nil then
    reset_candidate()
    report_once("no empty, feature-free cardinal tile borders the stairs")
    return
  end

  local key = string.format("%d,%d:%d,%d:%d,%d", x, y, sx, sy, tx, ty)
  if key ~= stable_key then
    stable_key = key
    stable_count = 1
    return
  end
  stable_count = stable_count + 1
  if stable_count < STABLE_OBSERVATIONS then return end

  local state = cpu_state()
  if state == nil then
    fail("Mesen did not expose cpu.pc/cpu.sp through emu.getState()")
    return
  end
  target_x, target_y = tx, ty
  stair_x, stair_y = sx, sy
  step_name = step
  reported_problem = nil
  install_wrapper(state)
end

local armed = pcall(emu.addEventCallback, on_frame, emu.eventType.endFrame)
if armed then
  emu.log(LABEL .. ": armed. Close the menu and stand still on a dungeon floor.")
else
  emu.log(LABEL .. ": FAILED to install the end-of-frame callback")
end
