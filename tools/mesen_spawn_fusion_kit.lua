-- mesen_spawn_fusion_kit.lua
-- Add a Fusion Pot[2] and a Manji Kabura+1 bearing the Cyclops Bane seal.
--
-- HOW TO USE
--   1. Back up the save RAM beside the ROM, or use a disposable save state. Mesen may
--      flush these live battery-RAM changes to disk.
--   2. Enter a dungeon in build/shiren_en.gb.
--   3. In Mesen, open Debug > Script Window, load this file, and press Run (F5).
--   4. Open Item. If Item was already visible, close and reopen it.
--
-- The script appends each exact fixture once. It never overwrites a full inventory or a
-- live dungeon object, and rolls back if both objects cannot be installed safely.
--
-- MEASURED FORMAT (2026-08-14)
--   $A3B0-$A3C3       twenty canonical inventory object indices; $FF is free
--   $A406 + 8*index   128 canonical dungeon object records in SRAM bank 0
--
-- The original item-name table at bank 11 $4537 maps Manji Kabura ($403B) to item $06
-- and Fusion Pot ($44E9) to item $87. The supplied fusion save establishes:
--
--   87 02 00 04 00 00 FF FF   Fusion Pot[2]
--
-- A normal Cyclops Bane in the menu fixture carries ability mask $0004, while the fused
-- Cyclops Bane in saves/shiren_en_log3_cyclops_name.srm has byte-3 flag $40 added. Thus
-- the second record applies that real Cyclops Bane seal and fused-item state to a Manji
-- Kabura. It should display as `Manji Kabura+1` followed by the native fused-item mark.
--
--   06 01 00 C4 04 00 FF FF   Manji Kabura+1, Cyclops Bane seal
--
-- These are canonical objects, not forged WRAM menu rows, so Item, Info, Drop, and the
-- Fusion Pot all see the same objects.

local INVENTORY_IDS = 0xA3B0
local INVENTORY_SLOTS = 20
local OBJECTS = 0xA406
local OBJECT_BYTES = 8
local OBJECT_COUNT = 128
local SENTINEL = 0xFF

local BUILDER = 0x4B29
local BUILDER_BANK = 6
local LABEL = "Fusion Kit"
local ITEMS = {
  {
    name = "Fusion Pot[2]",
    bytes = { 0x87, 0x02, 0x00, 0x04, 0x00, 0x00, 0xFF, 0xFF },
  },
  {
    name = "Manji Kabura+1 (Cyclops Bane seal)",
    bytes = { 0x06, 0x01, 0x00, 0xC4, 0x04, 0x00, 0xFF, 0xFF },
  },
}

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, name in ipairs(names) do
    if tbl[name] ~= nil then return tbl[name], name end
  end
  return nil, nil
end

local cpuT, cpuName = pick(emu.cpuType, { "gameboy", "gb" })
local memT, memName = pick(emu.memType, { "gameboyMemory", "gbMemory", "gameboy" })
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

local function same_record(address, bytes)
  for i = 1, #bytes do
    if rd(address + i - 1) ~= bytes[i] then return false end
  end
  return true
end

local function read_record(address)
  local bytes = {}
  for offset = 0, OBJECT_BYTES - 1 do
    local value = rd(address + offset)
    if value == nil then return nil end
    bytes[#bytes + 1] = value
  end
  return bytes
end

local function write_record(address, bytes)
  for i = 1, #bytes do
    if not wr(address + i - 1, bytes[i]) then
      emu.log(string.format("%s: FAILED writing $%04X", LABEL, address + i - 1))
      return false
    end
  end
  return true
end

local function restore_records(records)
  for _, record in ipairs(records) do
    write_record(record.address, record.original)
  end
end

local finished = false

local function inject()
  if finished then return end

  -- $4000-$7FFF is banked; each switchable bank stores its number at $4000.
  if rd(0x4000) ~= BUILDER_BANK then return end

  -- Bank 6 $4B29 runs while SRAM bank 0 is enabled and selected. Hooking here avoids
  -- changing MBC state behind the game.
  local free_slot = nil
  local present = {}
  for slot = 0, INVENTORY_SLOTS - 1 do
    local object_index = rd(INVENTORY_IDS + slot)
    if object_index == nil then
      emu.log(LABEL .. ": FAILED reading the canonical inventory")
      finished = true
      return
    end
    if object_index == SENTINEL then
      free_slot = slot
      break
    end
    if object_index >= OBJECT_COUNT then
      emu.log(string.format("%s: invalid object $%02X in inventory slot %d",
                            LABEL, object_index, slot + 1))
      finished = true
      return
    end
    local address = OBJECTS + object_index * OBJECT_BYTES
    for item_number, item in ipairs(ITEMS) do
      if same_record(address, item.bytes) then
        present[item_number] = slot
      end
    end
  end

  local missing = {}
  for item_number, item in ipairs(ITEMS) do
    if present[item_number] ~= nil then
      emu.log(string.format("%s: %s already present in inventory slot %d",
                            LABEL, item.name, present[item_number] + 1))
    else
      missing[#missing + 1] = item
    end
  end
  if #missing == 0 then
    emu.log(LABEL .. ": both fixtures are already present")
    finished = true
    return
  end

  if free_slot == nil or free_slot + #missing > INVENTORY_SLOTS then
    emu.log(string.format("%s: need %d free inventory slot(s); nothing changed",
                          LABEL, #missing))
    finished = true
    return
  end
  for offset = 0, #missing - 1 do
    if rd(INVENTORY_IDS + free_slot + offset) ~= SENTINEL then
      emu.log(LABEL .. ": free inventory space is not contiguous; nothing changed")
      finished = true
      return
    end
  end

  local free_objects = {}
  for object_index = 0, OBJECT_COUNT - 1 do
    local address = OBJECTS + object_index * OBJECT_BYTES
    if rd(address) == SENTINEL then
      local original = read_record(address)
      if original == nil then
        emu.log(LABEL .. ": FAILED reading a free canonical object")
        finished = true
        return
      end
      free_objects[#free_objects + 1] = {
        index = object_index,
        address = address,
        original = original,
      }
      if #free_objects == #missing then break end
    end
  end
  if #free_objects < #missing then
    emu.log(string.format("%s: need %d free dungeon object(s); nothing changed",
                          LABEL, #missing))
    finished = true
    return
  end

  local written_records = {}
  for i, item in ipairs(missing) do
    local target = free_objects[i]
    written_records[#written_records + 1] = target
    if not write_record(target.address, item.bytes) then
      restore_records(written_records)
      finished = true
      return
    end
  end

  local written_slots = 0
  for i, target in ipairs(free_objects) do
    if not wr(INVENTORY_IDS + free_slot + i - 1, target.index) then
      emu.log(LABEL .. ": FAILED appending an inventory index; rolling back")
      for offset = 0, written_slots - 1 do
        wr(INVENTORY_IDS + free_slot + offset, SENTINEL)
      end
      restore_records(written_records)
      finished = true
      return
    end
    written_slots = written_slots + 1
  end

  for i, item in ipairs(missing) do
    emu.log(string.format("%s: %s object %d added to inventory slot %d",
                          LABEL, item.name, free_objects[i].index, free_slot + i))
  end
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
  emu.log(LABEL .. ": armed. Open Item in a dungeon (close/reopen if visible).")
else
  emu.log(LABEL .. ": FAILED to hook bank 6 $4B29")
end
