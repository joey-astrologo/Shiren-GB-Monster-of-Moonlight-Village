-- mesen_spawn_healing_bunny.lua
-- Spawn one Fluffy Bunny on the floor immediately right of Shiren.
--
-- For testing the heal message, which the game assembles from two records:
--
--   13:$4D7D  Fluffy Bunny<br>healed <var>      (JP: いやしウサギは<var>に)
--   13:$4D88  with a spell.                     (JP: かいふくのじゅもんをとなえた)
--
-- It fires when the bunny heals ANOTHER monster, so bring the bunny to a wounded one --
-- the target's name is substituted into `healed <var>`, and its LENGTH is what stresses
-- that line. The longest in the game are 14 characters (Lantern Puffer, Teasing Monkey).
--
-- HOW TO USE
--   1. Use a disposable emulator save state. Ordinary Quit/save RAM does not serialize
--      floor actors, so it cannot preserve this spawn.
--   2. Enter a dungeon and stand with an OPEN, UNOCCUPIED floor tile directly to
--      Shiren's right. This helper detects actors there but cannot see walls.
--   3. In Debug > Script Window, load this file and press Run (F5).
--   4. The log reports the actor slot, position and HP.
--
-- SPECIES NUMBERING (measured 2026-08-17)
--   The monster name tables live at 11:$4FC2 / $5040 / $50BE for tiers 1/2/3, and the
--   constructor's species argument indexes them directly. Two independent anchors fix
--   that root: mesen_spawn_mouse_don.lua's proven `$30 tier 3 = Mouse Don`, and a
--   misfire of this script at `$11 tier 1`, which produced Taur and Baby Tank exactly as
--   the tables predict. Fluffy Bunny is `$12` at every tier -- an earlier reading of
--   `$11` came from a table root ten bytes high and spawned the wrong family.
--
-- Like mesen_spawn_mouse_don.lua this calls the game's own actor constructor at
-- 5:$4A75; it does not copy an actor, fake a sprite, or write stats itself. Species, HP,
-- AI and tier are all loaded through the ROM tables a natural spawn uses.
--
-- MEASURED RUNTIME FORMAT (2026-08-12, from mesen_spawn_mouse_don.lua)
--   actor slots             0-$11 monsters, $12 Shiren
--   $A006 + slot            current species ($12 = Fluffy Bunny at every tier)
--   $A019/$A02C + slot      X/Y
--   $A052/$A065 + slot      current/max HP (zero current HP = reusable slot)
--   $A078 + slot            level/tier
--   $A116 + slot            original species

local LABEL = "Healing Bunny"

-- ---- what to spawn -------------------------------------------------------------
local BUNNY_SPECIES = 0x12         -- Fluffy Bunny, the same index at all three tiers
local TIER = 0x01                  -- 1-3; the bunny exists at every tier
-- --------------------------------------------------------------------------------

local ACTOR_COUNT = 18
local PLAYER_SLOT = 0x12

local ACTOR_SPECIES = 0xA006
local ACTOR_X = 0xA019
local ACTOR_Y = 0xA02C
local ACTOR_HP = 0xA052
local ACTOR_MAX_HP = 0xA065
local ACTOR_TIER = 0xA078
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
local memT, memName = pick(emu.memType, { "gameboyMemory", "gbMemory", "gameboy" })
emu.log(LABEL .. ": cpuType=" .. tostring(cpuName) .. " memType=" .. tostring(memName))

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
  if type(state["cpu.pc"]) ~= "number" or type(state["cpu.sp"]) ~= "number" then
    return nil
  end
  return state
end

local queue = {
  { name = "Fluffy Bunny", species = BUNNY_SPECIES, dx = 1 },
}
local current = nil
local phase = "armed"
local target_slot, target_x, target_y = nil, nil, nil
local original_sp = nil
local wrapper_original = nil
local scratch_original = nil     -- $FF90/$FF91, saved across the spawn
local constructed = false

local function restore_wrapper()
  if wrapper_original ~= nil then
    for i, value in ipairs(wrapper_original) do
      wr(WRAPPER + i - 1, value)
    end
    wrapper_original = nil
  end
  -- $FF90 is the constructor's tier argument, but it is ALSO shared scratch: the heal
  -- routine at 15:$6703 reads $FF90/$FF91 as a 16-bit pointer. Leaving our tier byte
  -- there would let this helper corrupt the very message it exists to test, so both
  -- bytes go back exactly as they were.
  if scratch_original ~= nil then
    wr(0xFF90, scratch_original[1])
    wr(0xFF91, scratch_original[2])
    scratch_original = nil
  end
end

local function fail(message)
  restore_wrapper()
  phase = "done"
  emu.log(LABEL .. ": " .. message .. "; nothing further spawned")
end

local function verify_actor()
  local hp = rd(ACTOR_HP + target_slot)
  if hp == nil then return false, "cannot read the constructed actor" end
  if hp == 0 then return false, "native constructor left the actor at zero HP" end
  if rd(ACTOR_SPECIES + target_slot) ~= current.species
      or rd(ACTOR_BASE_SPECIES + target_slot) ~= current.species then
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

local function begin_next()
  current = table.remove(queue, 1)
  if current == nil then
    phase = "done"
    return false
  end

  local player_hp = rd(ACTOR_HP + PLAYER_SLOT)
  local player_x = rd(ACTOR_X + PLAYER_SLOT)
  local player_y = rd(ACTOR_Y + PLAYER_SLOT)
  if player_hp == nil or player_x == nil or player_y == nil
      or player_hp == 0 or rd(ACTOR_SPECIES + PLAYER_SLOT) ~= 0 then
    fail("live Shiren dungeon actor not recognized")
    return false
  end
  if player_x < 1 or player_x + current.dx >= 0x3F
      or player_y < 1 or player_y >= 0x3F then
    fail("Shiren's dungeon coordinates are outside the recognized range")
    return false
  end

  target_x = player_x + current.dx
  target_y = player_y
  for slot = 0, PLAYER_SLOT do
    if rd(ACTOR_HP + slot) ~= 0
        and rd(ACTOR_X + slot) == target_x
        and rd(ACTOR_Y + slot) == target_y then
      fail(string.format("the tile %d right of Shiren is occupied", current.dx))
      return false
    end
  end

  -- Match the game's own free-slot search: highest non-player slot with zero current HP.
  target_slot = nil
  for slot = ACTOR_COUNT - 1, 0, -1 do
    if rd(ACTOR_HP + slot) == 0 then
      target_slot = slot
      break
    end
  end
  if target_slot == nil then
    fail("all 18 monster actor slots are live")
    return false
  end
  return true
end

local function install_wrapper(state)
  local wrapper = {
    0xF5, 0xC5, 0xD5, 0xE5,                 -- push af / bc / de / hl
    0x3E, TIER, 0xEA, 0x90, 0xFF,           -- ld a,tier / ld ($FF90),a
    0x3E, target_slot,                      -- ld a,actor slot
    0x06, target_x,                         -- ld b,x
    0x0E, target_y,                         -- ld c,y
    0x16, current.species,                  -- ld d,species
    0x1E, DIRECTION_LEFT,                   -- ld e,6 (face toward Shiren)
    0xCD, CONSTRUCTOR % 0x100,
          math.floor(CONSTRUCTOR / 0x100),  -- call $4A75
    0xE1, 0xD1, 0xC1, 0xF1,                 -- pop hl / de / bc / af
    0xC3, RENDERER % 0x100,
          math.floor(RENDERER / 0x100),     -- jp $76C8
  }
  scratch_original = { rd(0xFF90), rd(0xFF91) }
  if scratch_original[1] == nil or scratch_original[2] == nil then
    scratch_original = nil
    fail("cannot read the $FF90 scratch pair")
    return false
  end
  wrapper_original = {}
  for i = 1, #wrapper do
    local old = rd(WRAPPER + i - 1)
    if old == nil then
      fail(string.format("cannot read temporary WRAM at $%04X", WRAPPER + i - 1))
      return false
    end
    wrapper_original[i] = old
  end
  for i, value in ipairs(wrapper) do
    if not wr(WRAPPER + i - 1, value) then
      fail(string.format("cannot write temporary WRAM at $%04X", WRAPPER + i - 1))
      return false
    end
  end
  original_sp = state["cpu.sp"]
  constructed = false
  emu.setState({ ["cpu.pc"] = WRAPPER })
  phase = "running"
  return true
end

local function inject()
  if phase == "done" then return end

  -- $4000-$7FFF is banked. This address is useful only while bank 5 is mapped; its
  -- renderer also establishes the SRAM-bank-0 context the actor arrays need.
  if rd(0x4000) ~= RENDERER_BANK then return end

  local state = cpu_state()
  if state == nil then
    fail("Mesen did not expose cpu.pc/cpu.sp through emu.getState()")
    return
  end

  if phase == "running" then
    -- The constructor calls $76C8 while its registers are still on our wrapper's stack.
    -- Observe that call, but do not erase executable wrapper bytes yet.
    if state["cpu.sp"] ~= original_sp then
      if state["cpu.e"] == target_slot then constructed = true end
      return
    end
    if not constructed then return end
    local ok, problem = verify_actor()
    if not ok then
      fail(problem)
      return
    end
    local hp = rd(ACTOR_HP + target_slot)
    local max_hp = rd(ACTOR_MAX_HP + target_slot)
    restore_wrapper()
    emu.log(string.format("%s: %s (species $%02X) in slot %d at (%d,%d), HP %d/%d",
                          LABEL, current.name, current.species, target_slot,
                          target_x, target_y, hp, max_hp))
    phase = "armed"
    return
  end

  if not begin_next() then return end
  install_wrapper(state)
end

emu.addMemoryCallback(inject, emu.callbackType.exec, RENDERER, RENDERER, cpuT)
emu.log(LABEL .. string.format(": armed, species $%02X at tier %d",
                               BUNNY_SPECIES, TIER))
