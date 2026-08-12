-- mesen_spawn_mouse_don.lua
-- Spawn one genuine level-3 Mouse Don on the floor immediately right of Shiren.
--
-- This is a live diagnostic helper for the anomalous Mouse Don EXP reward.  It calls
-- the game's native actor constructor (bank 5 $4A75); it does not copy another monster,
-- fake a sprite, or write an EXP value itself.  HP, AI, stats, species and reward are all
-- loaded through the same ROM tables as a naturally generated Mouse Don.
--
-- HOW TO USE
--   1. Use a disposable emulator save state if you want to preserve the setup. Ordinary
--      Quit/save RAM does not serialize floor actors, so it cannot preserve this spawn.
--   2. Enter a dungeon and stand with an OPEN, UNOCCUPIED floor tile directly to Shiren's
--      right.  This helper detects actors there, but cannot distinguish floor from wall.
--   3. In Debug > Script Window, load this file and press Run (F5).
--   4. Wait a moment.  The log will report the new actor slot, HP and loaded EXP reward.
--   5. Kill it in the same session to exercise the live reward path.
--
-- EXPECTED DIAGNOSTIC
--   The uncorrupted Japanese table gives a level-3 Mouse Don 40 EXP ($000028).  A build
--   with the currently investigated high-byte corruption instead reports 131112
--   ($020028).  The script deliberately preserves whichever value the ROM loads.
--
-- MEASURED RUNTIME FORMAT (2026-08-12)
--   actor slots             0-$11 monsters, $12 Shiren
--   $A006 + slot            current species ($30 = Mouse family)
--   $A019/$A02C + slot      X/Y
--   $A052/$A065 + slot      current/max HP (zero current HP = reusable slot)
--   $A078 + slot            level/tier ($03 = Mouse Don)
--   $A0B1/$A0C4/$A0D7       24-bit EXP reward, low/mid/high byte
--   $A116 + slot            original species
--
-- Bank 5 $76C8 is an actor-render path which runs with SRAM bank 0 available.  A tiny,
-- temporary WRAM trampoline preserves every register, invokes the native constructor,
-- then resumes the interrupted instruction.  The original trampoline bytes are restored
-- before this helper reports success.

local LABEL = "Mouse Don"
local ACTOR_COUNT = 18
local PLAYER_SLOT = 0x12
local SPECIES = 0x30
local TIER = 0x03

local ACTOR_SPECIES = 0xA006
local ACTOR_X = 0xA019
local ACTOR_Y = 0xA02C
local ACTOR_HP = 0xA052
local ACTOR_MAX_HP = 0xA065
local ACTOR_TIER = 0xA078
local ACTOR_EXP_LO = 0xA0B1
local ACTOR_EXP_MID = 0xA0C4
local ACTOR_EXP_HI = 0xA0D7
local ACTOR_BASE_SPECIES = 0xA116

local RENDERER = 0x76C8
local RENDERER_BANK = 5
local CONSTRUCTOR = 0x4A75
local WRAPPER = 0xD780
local DIRECTION_LEFT = 0x06

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

local function actor_exp(slot)
  local lo = rd(ACTOR_EXP_LO + slot)
  local mid = rd(ACTOR_EXP_MID + slot)
  local hi = rd(ACTOR_EXP_HI + slot)
  if lo == nil or mid == nil or hi == nil then return nil end
  return lo + mid * 0x100 + hi * 0x10000
end

local phase = "armed"
local target_slot = nil
local target_x = nil
local target_y = nil
local original_sp = nil
local wrapper_original = nil
local constructed = false

local function restore_wrapper()
  if wrapper_original == nil then return end
  for i, value in ipairs(wrapper_original) do
    wr(WRAPPER + i - 1, value)
  end
  wrapper_original = nil
end

local function fail(message)
  restore_wrapper()
  phase = "done"
  emu.log(LABEL .. ": " .. message .. "; nothing spawned")
end

local function verify_actor()
  if rd(ACTOR_HP + target_slot) == nil then
    return false, "cannot read the constructed actor"
  end
  if rd(ACTOR_HP + target_slot) == 0 then
    return false, "native constructor left the actor at zero HP"
  end
  if rd(ACTOR_SPECIES + target_slot) ~= SPECIES
      or rd(ACTOR_BASE_SPECIES + target_slot) ~= SPECIES then
    return false, "native constructor returned the wrong species"
  end
  if rd(ACTOR_TIER + target_slot) ~= TIER then
    return false, "native constructor returned the wrong tier"
  end
  if rd(ACTOR_X + target_slot) ~= target_x
      or rd(ACTOR_Y + target_slot) ~= target_y then
    return false, "native constructor returned the wrong position"
  end
  return true, nil
end

local function inject()
  if phase == "done" then return end

  -- $4000-$7FFF is banked.  This address is useful only while bank 5 is mapped; its
  -- renderer also establishes the SRAM-bank-0 context required by the actor arrays.
  if rd(0x4000) ~= RENDERER_BANK then return end

  local state = cpu_state()
  if state == nil then
    fail("Mesen did not expose cpu.pc/cpu.sp through emu.getState()")
    return
  end

  if phase == "running" then
    -- The constructor itself calls $76C8 while its registers are still on our wrapper's
    -- stack.  Observe that call, but do not erase executable wrapper bytes yet.
    if state["cpu.sp"] ~= original_sp then
      if state["cpu.e"] == target_slot then
        constructed = true
      end
      return
    end

    -- The wrapper has now restored the interrupted registers and jumped back to the
    -- original $76C8.  It is finally safe to restore the scratch bytes.
    if not constructed then return end
    local ok, problem = verify_actor()
    if not ok then
      fail(problem)
      return
    end
    local hp = rd(ACTOR_HP + target_slot)
    local max_hp = rd(ACTOR_MAX_HP + target_slot)
    local reward = actor_exp(target_slot)
    restore_wrapper()
    phase = "done"
    emu.log(string.format(
      "%s: spawned in actor slot %d at (%d,%d), HP %d/%d, loaded EXP %d ($%06X)",
      LABEL, target_slot, target_x, target_y, hp, max_hp, reward, reward))
    if reward ~= 40 then
      emu.log(string.format(
        "%s: NOTE: native level-3 reward should be 40; this ROM supplied %d",
        LABEL, reward))
    end
    return
  end

  local player_hp = rd(ACTOR_HP + PLAYER_SLOT)
  local player_x = rd(ACTOR_X + PLAYER_SLOT)
  local player_y = rd(ACTOR_Y + PLAYER_SLOT)
  if player_hp == nil or player_x == nil or player_y == nil
      or player_hp == 0 or rd(ACTOR_SPECIES + PLAYER_SLOT) ~= 0 then
    fail("live Shiren dungeon actor not recognized")
    return
  end
  if player_x < 1 or player_x >= 0x3F or player_y < 1 or player_y >= 0x3F then
    fail("Shiren's dungeon coordinates are outside the recognized range")
    return
  end

  target_x = player_x + 1
  target_y = player_y
  for slot = 0, PLAYER_SLOT do
    if rd(ACTOR_HP + slot) ~= 0
        and rd(ACTOR_X + slot) == target_x
        and rd(ACTOR_Y + slot) == target_y then
      fail("the tile immediately right of Shiren is occupied")
      return
    end
  end

  -- Match the game's own free-slot search: highest non-player slot with zero current HP.
  for slot = ACTOR_COUNT - 1, 0, -1 do
    if rd(ACTOR_HP + slot) == 0 then
      target_slot = slot
      break
    end
  end
  if target_slot == nil then
    fail("all 18 monster actor slots are live")
    return
  end

  -- Preserve the interrupted AF/BC/DE/HL, install tier 3, construct species $30, restore
  -- the registers, and resume the exact renderer instruction whose callback we used.
  local wrapper = {
    0xF5, 0xC5, 0xD5, 0xE5,             -- push af / bc / de / hl
    0x3E, TIER, 0xEA, 0x90, 0xFF,       -- ld a,3 / ld ($FF90),a
    0x3E, target_slot,                   -- ld a,actor slot
    0x06, target_x,                      -- ld b,x
    0x0E, target_y,                      -- ld c,y
    0x16, SPECIES,                       -- ld d,$30 (Mouse family)
    0x1E, DIRECTION_LEFT,                -- ld e,6 (face toward Shiren)
    0xCD, CONSTRUCTOR % 0x100,
          math.floor(CONSTRUCTOR / 0x100), -- call $4A75
    0xE1, 0xD1, 0xC1, 0xF1,             -- pop hl / de / bc / af
    0xC3, RENDERER % 0x100,
          math.floor(RENDERER / 0x100),  -- jp $76C8
  }

  wrapper_original = {}
  for i = 1, #wrapper do
    local old = rd(WRAPPER + i - 1)
    if old == nil then
      fail(string.format("cannot read temporary WRAM at $%04X", WRAPPER + i - 1))
      return
    end
    wrapper_original[i] = old
  end
  for i, value in ipairs(wrapper) do
    if not wr(WRAPPER + i - 1, value) then
      fail(string.format("cannot write temporary WRAM at $%04X", WRAPPER + i - 1))
      return
    end
  end

  original_sp = state["cpu.sp"]
  phase = "running"
  local ok, err = pcall(emu.setState, { ["cpu.pc"] = WRAPPER })
  if not ok then
    fail("emu.setState() failed: " .. tostring(err))
  end
end

local armed = false
if cpuT ~= nil then
  armed = pcall(emu.addMemoryCallback, inject, emu.callbackType.exec,
                RENDERER, RENDERER, cpuT)
end
if not armed then
  armed = pcall(emu.addMemoryCallback, inject, emu.callbackType.exec,
                RENDERER, RENDERER)
end

if armed then
  emu.log(LABEL .. ": armed. Stand with open floor immediately right of Shiren.")
else
  emu.log(LABEL .. ": FAILED to hook bank 5 $76C8")
end
