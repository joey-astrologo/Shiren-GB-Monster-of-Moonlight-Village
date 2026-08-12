-- mesen_spawn_progress_bracers.lua
-- Add a No-Hunger Bracer and a Happy Bracer to Shiren's dungeon inventory.
--
-- HOW TO USE
--   1. Back up the save RAM beside your ROM, or use a disposable save state. Mesen can
--      flush this live SRAM change back to disk.
--   2. Load build/shiren_en.gb in Mesen and enter a dungeon.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Open Item. If Item was already visible, close and reopen it.
--
-- The helper adds each missing bracer once. It leaves an existing copy alone and refuses
-- to overwrite inventory entries or live dungeon objects. If there is not enough room for
-- every missing bracer, it changes nothing.
--
-- MEASURED FORMAT (2026-08-11)
--   Bank 6 $4B29 builds the display list from canonical SRAM-bank-0 structures:
--
--     $A3B0-$A3C3       twenty inventory object indices; $FF is the first free slot
--     $A406 + 8*index   128 canonical dungeon object records
--
--   The original bank-11 item-name pointer table at $4537 places No-Hunger Bracer
--   ($4151) at zero-based item ID $25 and Happy Bracer ($41A5) at ID $2D. Supplied save
--   fixtures contain these exact ordinary, uncursed, carried records:
--
--     25 00 00 84 00 00 FF FF   No-Hunger Bracer
--     2D 03 00 84 00 00 FF FF   Happy Bracer
--
--   This deliberately does not forge the temporary WRAM display list. Equipping,
--   dropping, and both bracers' real effects therefore follow canonical game objects.

local INVENTORY_IDS = 0xA3B0
local INVENTORY_SLOTS = 20
local OBJECTS = 0xA406
local OBJECT_BYTES = 8
local OBJECT_COUNT = 128
local SENTINEL = 0xFF

local BUILDER = 0x4B29
local BUILDER_BANK = 6
local LABEL = "Progress Bracers"
local ITEMS = {
  {
    name = "No-Hunger Bracer",
    id = 0x25,
    bytes = { 0x25, 0x00, 0x00, 0x84, 0x00, 0x00, 0xFF, 0xFF },
  },
  {
    name = "Happy Bracer",
    id = 0x2D,
    bytes = { 0x2D, 0x03, 0x00, 0x84, 0x00, 0x00, 0xFF, 0xFF },
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

  -- $4000-$7FFF is banked. Every switchable ROM bank stores its own number at $4000,
  -- so reject an unrelated $4B29 from another bank.
  if rd(0x4000) ~= BUILDER_BANK then return end

  -- This routine executes with SRAM enabled and bank 0 selected. Hooking it avoids
  -- changing MBC state behind the game.
  local present = {}
  local free_slot = nil
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
    local item_id = rd(OBJECTS + object_index * OBJECT_BYTES)
    if item_id == nil then
      emu.log(LABEL .. ": FAILED reading a canonical object")
      finished = true
      return
    end
    present[item_id] = slot
  end

  local missing = {}
  for _, item in ipairs(ITEMS) do
    if present[item.id] ~= nil then
      emu.log(string.format("%s: %s already present in inventory slot %d",
                            LABEL, item.name, present[item.id] + 1))
    else
      missing[#missing + 1] = item
    end
  end

  if #missing == 0 then
    emu.log(LABEL .. ": both bracers are already present")
    finished = true
    return
  end

  if free_slot == nil or free_slot + #missing > INVENTORY_SLOTS then
    emu.log(string.format("%s: need %d free inventory slot(s); nothing overwritten",
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
    emu.log(string.format("%s: need %d free dungeon object(s); nothing overwritten",
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
      emu.log(LABEL .. ": FAILED appending a canonical object index; rolling back")
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
                          LABEL, item.name, free_objects[i].index,
                          free_slot + i))
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
