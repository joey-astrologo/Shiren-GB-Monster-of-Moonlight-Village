-- mesen_spawn_confusion_scroll.lua
-- Add one genuine Confusion Scroll to Shiren's dungeon inventory.
--
-- HOW TO USE
--   1. Back up the save RAM beside the ROM, or use a disposable save state. Mesen may
--      flush this live battery-RAM modification back to disk.
--   2. Load build/shiren_en.gb in Mesen and enter a dungeon.
--   3. Open Debug > Script Window, load this file, and press Run (F5).
--   4. Open Item. If Item was already visible, close and reopen it.
--   5. Read the Confusion Scroll in a room containing multiple monsters, then let nearby
--      confused monsters take turns and watch whether monster-on-monster hits print text.
--
-- The helper adds the scroll once. It refuses to overwrite a full inventory or any live
-- dungeon object.
--
-- MEASURED FORMAT (2026-08-13)
--   Bank 6 $4B29 builds the display list from canonical SRAM-bank-0 structures:
--
--     $A3B0-$A3C3       twenty inventory object indices; $FF is the first free slot
--     $A406 + 8*index   128 canonical dungeon object records
--
--   The bank-11 item-name table at $4537 maps Confusion Scroll
--   (`こんらんのまきもの`, $439A) to zero-based item ID $64. Ordinary identified,
--   carried scrolls use byte 1=$01 and byte 3=$04:
--
--     64 01 00 04 00 00 FF FF
--
--   This writes the canonical object and inventory tables, not the temporary WRAM
--   display list, so Read, consumption and the real confusion effect use normal code.

local INVENTORY_IDS = 0xA3B0
local INVENTORY_SLOTS = 20
local OBJECTS = 0xA406
local OBJECT_BYTES = 8
local OBJECT_COUNT = 128
local SENTINEL = 0xFF

local BUILDER = 0x4B29
local BUILDER_BANK = 6
local LABEL = "Confusion Scroll"
local ITEM = { 0x64, 0x01, 0x00, 0x04, 0x00, 0x00, 0xFF, 0xFF }

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

  -- $4000-$7FFF is banked. Each switchable ROM bank stores its own number at $4000,
  -- so do not mistake another bank's unrelated $4B29 for the inventory builder.
  if rd(0x4000) ~= BUILDER_BANK then return end

  -- This native routine runs with SRAM enabled and bank 0 selected, allowing the helper
  -- to modify canonical data without changing MBC state behind the game.
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
    if object_index < OBJECT_COUNT then
      local address = OBJECTS + object_index * OBJECT_BYTES
      if same_record(address, ITEM) then
        emu.log(string.format("%s: already present in inventory slot %d",
                              LABEL, slot + 1))
        finished = true
        return
      end
    end
  end

  if free_slot == nil then
    emu.log(LABEL .. ": inventory is full; nothing overwritten")
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
    wr(object_address, SENTINEL)
    finished = true
    return
  end

  -- Preserve the sentinel after the appended slot unless the inventory is now full.
  if free_slot + 1 < INVENTORY_SLOTS then
    wr(INVENTORY_IDS + free_slot + 1, SENTINEL)
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
  armed = pcall(emu.addMemoryCallback, inject, emu.callbackType.exec,
                BUILDER, BUILDER)
end

if armed then
  emu.log(LABEL .. ": armed. Open Item in a dungeon (close/reopen if visible).")
else
  emu.log(LABEL .. ": FAILED to hook bank 6 $4B29")
end
