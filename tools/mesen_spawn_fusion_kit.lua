-- mesen_spawn_fusion_kit.lua
-- Add a Fusion Pot[2] plus configurable +1 weapon and shield fixtures bearing every
-- category-appropriate seal.
--
-- HOW TO USE
--   1. Back up the save RAM beside the ROM, or use a disposable save state. Mesen may
--      flush these live battery-RAM changes to disk.
--   2. Enter a dungeon in build/shiren_en.gb.
--   3. In Mesen, open Debug > Script Window, load this file, and press Run (F5).
--   4. Open Item. If Item was already visible, close and reopen it.
--
-- WEAPON TO SPAWN
--   Edit only FUSED_WEAPON_ID below. The weapon IDs are:
--
--     0x00  Club                 0x09  True Rapier
--     0x01  Nagamaki             0x0A  Minotaur Axe
--     0x02  New Weapon 3         0x0B  Kama Itachi
--     0x03  Katana               0x0C  Cyclops Bane
--     0x04  Dragonkiller         0x0D  Drain Slayer
--     0x05  Doutanuki            0x0E  Kajin Fuuma
--     0x06  Manji Kabura         0x0F  Kabura Sutegi
--     0x07  Sickle               0x10  Mamel Sword
--     0x08  Pickaxe              0x11  New Weapon 2
--
--   New Weapon 2/3 are internal placeholder entries; use the named ordinary weapons
--   for normal gameplay testing. To add several different source weapons, change the
--   value, reload/run the script, and reopen Item after each run. An exact weapon already
--   present is not duplicated.
--
-- SHIELD TO SPAWN
--   Edit only FUSED_SHIELD_ID below. The shield IDs are:
--
--     0x12  Leather Shield       0x1B  Evasion Shield
--     0x13  Bronze Shield        0x1C  Hyakki Shield
--     0x14  Wooden Shield        0x1D  One-Use Shield
--     0x15  Iron Shield          0x1E  Blast Shield
--     0x16  Dragon Shield        0x1F  Walrus Shield
--     0x17  Fuuma Shield         0x20  Rasen Fuuma
--     0x18  Battle Counter       0x21  Mamel Shield
--     0x19  Heavy Shield         0x22  New Shield 2
--     0x1A  Echo Shield
--
--   New Shield 2 is an internal placeholder entry. As with the weapon, changing the ID
--   changes only the base item; the all-seals shield mask remains installed.
--
-- The script appends each exact fixture once. It never overwrites a full inventory or a
-- live dungeon object, and rolls back if every missing fixture cannot be installed safely.
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
-- Object bytes 4-5 are the little-endian weapon-seal mask. The native weapon mask has
-- nine usable bits, $01FF; setting all of them produces every weapon seal. Byte-3 $C4
-- retains the canonical equipment, carried-object, and fused-item flags. The default
-- record is therefore:
--
--   06 01 00 C4 FF 01 FF FF   Manji Kabura+1, all nine weapon seals
--
-- Shield bytes 4-5 use a different non-contiguous nine-bit mask, $06FD. The canonical
-- default shield record is:
--
--   20 01 00 C4 FD 06 FF FF   Rasen Fuuma+1, all nine shield seals
--
-- The equipment Info screen displays four seal descriptions per page, so nine seals
-- should produce three seal pages for both categories. Changing either configurable ID
-- changes only the base equipment; the masks remain $01FF for weapons and $06FD for
-- shields.
--
-- These are canonical objects, not forged WRAM menu rows, so Item, Info, Drop, and the
-- Fusion Pot all see the same objects.

-- Change this one value to select the spawned weapon. Default: Manji Kabura ($06).
local FUSED_WEAPON_ID = 0x0A
local ALL_WEAPON_SEALS_LO = 0xFF
local ALL_WEAPON_SEALS_HI = 0x01
-- Change this one value to select the spawned shield. Default: Rasen Fuuma ($20).
local FUSED_SHIELD_ID = 0x20
local ALL_SHIELD_SEALS_LO = 0xFD
local ALL_SHIELD_SEALS_HI = 0x06

local WEAPON_NAMES = {
  [0x00] = "Club",
  [0x01] = "Nagamaki",
  [0x02] = "New Weapon 3",
  [0x03] = "Katana",
  [0x04] = "Dragonkiller",
  [0x05] = "Doutanuki",
  [0x06] = "Manji Kabura",
  [0x07] = "Sickle",
  [0x08] = "Pickaxe",
  [0x09] = "True Rapier",
  [0x0A] = "Minotaur Axe",
  [0x0B] = "Kama Itachi",
  [0x0C] = "Cyclops Bane",
  [0x0D] = "Drain Slayer",
  [0x0E] = "Kajin Fuuma",
  [0x0F] = "Kabura Sutegi",
  [0x10] = "Mamel Sword",
  [0x11] = "New Weapon 2",
}

local SHIELD_NAMES = {
  [0x12] = "Leather Shield",
  [0x13] = "Bronze Shield",
  [0x14] = "Wooden Shield",
  [0x15] = "Iron Shield",
  [0x16] = "Dragon Shield",
  [0x17] = "Fuuma Shield",
  [0x18] = "Battle Counter",
  [0x19] = "Heavy Shield",
  [0x1A] = "Echo Shield",
  [0x1B] = "Evasion Shield",
  [0x1C] = "Hyakki Shield",
  [0x1D] = "One-Use Shield",
  [0x1E] = "Blast Shield",
  [0x1F] = "Walrus Shield",
  [0x20] = "Rasen Fuuma",
  [0x21] = "Mamel Shield",
  [0x22] = "New Shield 2",
}

local FUSED_WEAPON_NAME = WEAPON_NAMES[FUSED_WEAPON_ID]
if FUSED_WEAPON_NAME == nil then
  error(string.format("Fusion Kit: invalid FUSED_WEAPON_ID $%02X; use $00-$11",
                      FUSED_WEAPON_ID))
end
local FUSED_SHIELD_NAME = SHIELD_NAMES[FUSED_SHIELD_ID]
if FUSED_SHIELD_NAME == nil then
  error(string.format("Fusion Kit: invalid FUSED_SHIELD_ID $%02X; use $12-$22",
                      FUSED_SHIELD_ID))
end

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
    name = FUSED_WEAPON_NAME .. "+1 (all 9 seals)",
    bytes = {
      FUSED_WEAPON_ID, 0x01, 0x00, 0xC4,
      ALL_WEAPON_SEALS_LO, ALL_WEAPON_SEALS_HI, 0xFF, 0xFF,
    },
  },
  {
    name = FUSED_SHIELD_NAME .. "+1 (all 9 seals)",
    bytes = {
      FUSED_SHIELD_ID, 0x01, 0x00, 0xC4,
      ALL_SHIELD_SEALS_LO, ALL_SHIELD_SEALS_HI, 0xFF, 0xFF,
    },
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
    emu.log(LABEL .. ": all fixtures are already present")
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
