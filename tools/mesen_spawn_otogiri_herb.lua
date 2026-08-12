-- mesen_spawn_otogiri_herb.lua
-- Add one genuine Otogiri Herb to Shiren's dungeon inventory.
--
-- Otogiri Herb is the game's strongest direct healing herb: it restores lots of HP and
-- cures status ailments. Revival Herb is a separate automatic-revival item, not a heal.
--
-- HOW TO USE
--   1. Back up the save RAM beside your ROM, or use a disposable save state. Mesen can
--      flush this live SRAM change back to disk.
--   2. Load build/shiren_en.gb in Mesen and enter the dungeon with Shiren.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Open Item. If Item was already visible, close and reopen it.
--
-- The script adds the herb once, leaves an existing Otogiri Herb alone, and refuses to
-- overwrite a full inventory or a live dungeon object.
--
-- MEASURED FORMAT (2026-08-11)
--   Bank 6 $4B29 builds the display list from canonical SRAM-bank-0 structures:
--
--     $A3B0-$A3C3       twenty inventory object indices; $FF is the first free slot
--     $A406 + 8*index   128 canonical dungeon object records
--
--   The bank-11 item-name table at $4537 maps Otogiri Herb (`おとぎりそう`, $4237) to
--   zero-based item ID $3E. Multiple independent save fixtures carry this exact record:
--
--     3E 01 00 04 00 00 FF FF
--
--   This modifies the canonical object and inventory tables, never the temporary WRAM
--   display list. Eating, dropping, saving, and the real healing effect therefore follow
--   the normal game path.

local INVENTORY_IDS = 0xA3B0
local INVENTORY_SLOTS = 20
local OBJECTS = 0xA406
local OBJECT_BYTES = 8
local OBJECT_COUNT = 128
local SENTINEL = 0xFF

local BUILDER = 0x4B29
local BUILDER_BANK = 6
local LABEL = "Otogiri Herb"
local ITEM_ID = 0x3E
local ITEM = { 0x3E, 0x01, 0x00, 0x04, 0x00, 0x00, 0xFF, 0xFF }

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

local finished = false

local function inject()
  if finished then return end

  -- $4000-$7FFF is banked. Every switchable ROM bank stores its own number at $4000,
  -- so reject an unrelated $4B29 in another bank.
  if rd(0x4000) ~= BUILDER_BANK then return end

  -- This routine runs with SRAM enabled and bank 0 selected, so no MBC state is changed
  -- behind the game while the canonical structures are inspected and updated.
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
    if item_id == ITEM_ID then
      emu.log(string.format("%s: already present in inventory slot %d",
                            LABEL, slot + 1))
      finished = true
      return
    end
  end

  if free_slot == nil then
    emu.log(LABEL .. ": inventory is full; nothing overwritten")
    finished = true
    return
  end

  local free_object = nil
  local original = nil
  for object_index = 0, OBJECT_COUNT - 1 do
    local address = OBJECTS + object_index * OBJECT_BYTES
    if rd(address) == SENTINEL then
      local record = read_record(address)
      if record == nil then
        emu.log(LABEL .. ": FAILED reading a free canonical object")
        finished = true
        return
      end
      free_object = object_index
      original = record
      break
    end
  end
  if free_object == nil then
    emu.log(LABEL .. ": all 128 dungeon objects are live; nothing overwritten")
    finished = true
    return
  end

  local object_address = OBJECTS + free_object * OBJECT_BYTES
  if not write_record(object_address, ITEM) then
    finished = true
    return
  end
  if not wr(INVENTORY_IDS + free_slot, free_object) then
    emu.log(LABEL .. ": FAILED appending the inventory index; rolling back")
    write_record(object_address, original)
    finished = true
    return
  end

  emu.log(string.format("%s: genuine object %d added to inventory slot %d",
                        LABEL, free_object, free_slot + 1))
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
