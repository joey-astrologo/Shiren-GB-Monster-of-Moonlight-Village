-- mesen_spawn_accurate99.lua
-- Add a genuine True Rapier+99 (item $09) to Shiren's dungeon inventory.
--
-- HOW TO USE
--   1. Back up the save RAM beside your ROM (`.sav`/`.srm`, depending on Mesen's setup),
--      or load a disposable save state. This helper changes the live battery-backed RAM.
--   2. Load build/shiren_en.gb in Mesen and enter a dungeon.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Open the Item menu. If it was already open, close and reopen it.
--   5. True Rapier+99 is appended once. It can be equipped, dropped, and picked up
--      through the game's normal item code.
--
-- Stop and rerun the script to inject another sword. It refuses to overwrite a full
-- inventory or a live dungeon object. Mesen may flush the modified battery RAM to disk,
-- which is why step 1 matters; restoring the backup removes the test item completely.
--
-- MEASURED FORMAT (2026-08-09)
--   Bank 6 $4B29 builds the six-byte display list at $C549 from the canonical structures
--   in SRAM bank 0:
--
--     $A3B0-$A3C3       twenty inventory object indices; $FF marks the first free slot
--     $A406 + 8*index   128 canonical dungeon object records
--
--   A carried Nagamaki is `01 00 00 84 00 00 FF FF`. True Rapier is item $09,
--   byte 1 is its signed modifier, and bit $04 marks it as carried. Therefore +99 is:
--
--     09 63 00 84 00 00 FF FF
--        ^^    ^^
--        |     +-- normal weapon flags plus carried bit
--        +-------- positive modifier 99
--
--   This is deliberately NOT a patch to $C549. That WRAM list is only a display copy;
--   forging it makes the row look right while Equip/Drop follows a different real object.

local INVENTORY_IDS = 0xA3B0
local INVENTORY_SLOTS = 20
local OBJECTS = 0xA406
local OBJECT_BYTES = 8
local OBJECT_COUNT = 128
local SENTINEL = 0xFF

local BUILDER = 0x4B29            -- bank 6, canonical inventory -> display-list builder
local BUILDER_BANK = 6
local TRUE_RAPIER = { 0x09, 0x63, 0x00, 0x84, 0x00, 0x00, 0xFF, 0xFF }

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

local cpuT, cpuName = pick(emu.cpuType, { "gameboy", "gb" })
local memT, memName = pick(emu.memType, { "gameboyMemory", "gbMemory", "gameboy" })
emu.log("True Rapier+99: cpuType=" .. tostring(cpuName)
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

local function same_record(address, bytes)
  for i = 1, #bytes do
    if rd(address + i - 1) ~= bytes[i] then return false end
  end
  return true
end

local function write_record(address, bytes)
  for i = 1, #bytes do
    if not wr(address + i - 1, bytes[i]) then
      emu.log(string.format("True Rapier+99: FAILED writing $%04X", address + i - 1))
      return false
    end
  end
  return true
end

local finished = false

local function inject()
  if finished then return end

  -- Execution addresses in $4000-$7FFF are banked. Every switchable bank in this ROM
  -- stores its own number at $4000, so reject another bank's unrelated $4B29.
  if rd(0x4000) ~= BUILDER_BANK then return end

  -- This routine runs with SRAM enabled and bank 0 selected. Doing the work here avoids
  -- changing MBC state behind the game and ensures the mapped $A000-$BFFF addresses below
  -- are the canonical dungeon inventory, not another save structure.
  local free_slot = nil
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object_index = rd(INVENTORY_IDS + slot)
    if object_index == nil then
      emu.log("True Rapier+99: FAILED reading the canonical inventory")
      finished = true
      return
    end
    if object_index == SENTINEL then
      free_slot = slot
      break
    end
    if object_index < OBJECT_COUNT then
      local address = OBJECTS + object_index * OBJECT_BYTES
      if same_record(address, TRUE_RAPIER) then
        emu.log(string.format("True Rapier+99: already present in inventory slot %d", slot + 1))
        finished = true
        return
      end
    end
  end

  if free_slot == nil then
    emu.log("True Rapier+99: inventory is full; nothing overwritten")
    finished = true
    return
  end

  local free_object = nil
  for object_index = 0, OBJECT_COUNT - 1 do
    local address = OBJECTS + object_index * OBJECT_BYTES
    if rd(address) == SENTINEL then
      free_object = object_index
      break
    end
  end
  if free_object == nil then
    emu.log("True Rapier+99: all 128 dungeon objects are live; nothing overwritten")
    finished = true
    return
  end

  local object_address = OBJECTS + free_object * OBJECT_BYTES
  if not write_record(object_address, TRUE_RAPIER) then
    finished = true
    return
  end
  if not wr(INVENTORY_IDS + free_slot, free_object) then
    emu.log("True Rapier+99: FAILED appending the canonical object index")
    -- Make the partly-created object free again so it cannot leak into another list.
    wr(object_address, SENTINEL)
    finished = true
    return
  end

  -- The slot after the insertion was already $FF. Leave the byte after slot 20 alone:
  -- a full inventory has no in-bounds sentinel cell.
  emu.log(string.format(
      "True Rapier+99: genuine object %d added to inventory slot %d",
      free_object, free_slot + 1))
  finished = true
end

local armed = false
if cpuT ~= nil then
  armed = pcall(emu.addMemoryCallback, inject, emu.callbackType.exec,
                BUILDER, BUILDER, cpuT)
end
if not armed then
  armed = pcall(emu.addMemoryCallback, inject, emu.callbackType.exec, BUILDER, BUILDER)
end

if armed then
  emu.log("True Rapier+99: armed. Open Item in a dungeon (close/reopen if already visible).")
else
  emu.log("True Rapier+99: FAILED to hook bank 6 $4B29")
end
