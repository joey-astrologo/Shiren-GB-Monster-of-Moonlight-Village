-- mesen_max_level_hp.lua
-- Put Shiren at maximum level and maximum HP, for reaching late-game content quickly.
--
-- HOW TO USE
--   1. Back up the .srm, or use a disposable emulator save state.
--   2. Get INTO A DUNGEON, standing still with the MENU CLOSED. The actor arrays this
--      writes only hold a live run; at the title menu they are stale and the script
--      refuses rather than corrupt them.
--   3. In Debug > Script Window, load this file and press Run (F5).
--   4. Take one step, or open the menu, so the status bar redraws with the new values.
--
-- WHY 99 AND 255
--   Both fields are one byte per actor, but the status bar's level field is two digits:
--   level 100 draws as `Lv 0` and level 255 as `Lv55`, because the drawing code prints
--   the value modulo 100. 99 is therefore the highest level that both stores and DISPLAYS
--   correctly. HP is drawn in a three-digit field, so the byte maximum of 255 shows
--   properly as `Hp255/255`. Raise these past those values and the bar starts lying.
--
-- RUNTIME FORMAT
--   The layout is the one measured in mesen_spawn_healing_bunny.lua -- parallel per-actor
--   arrays of 19 slots, monsters in 0-$11 and Shiren in $12:
--
--     $A052 + slot   current HP
--     $A065 + slot   max HP
--     $A078 + slot   level  (the same byte is a monster's TIER; for Shiren it is level)
--
--   Confirmed independently here by writing each byte and reading the drawn bar back:
--   $A052+$12 = $A064 drove `Hp 50/ 15`, $A065+$12 = $A077 drove `Hp  4/ 50`, and
--   $A078+$12 = $A08A drove `Lv 50`.
--
-- WHY THE MENU MUST BE CLOSED
--   $A000-$BFFF is a banked window. While the status/menu screen is open the game maps a
--   different SRAM bank there, and all three addresses read 0 even though the run is fine
--   -- measured here: values written before opening the menu still drive the bar, but
--   reading them back through the menu returns zeroes. Writing then would land in the
--   wrong bank. The zero-max-HP check below refuses in exactly that case, so it guards
--   the open-menu mistake as well as the no-run one.
--
-- SAFETY
--   Only Shiren's three bytes are touched -- no monster slot, no inventory, no dungeon
--   object, no save-record field. Nothing is hooked and nothing needs restoring, so
--   stopping the script leaves no residue. The change is not written to the .srm until
--   the game next saves, but it IS live immediately, so a Quit/save afterwards makes it
--   permanent. That is the only way this reaches your save file.
--
--   Levelling up normally after this may recompute stats from the game's own tables;
--   this helper does not touch the level-up curve, only the current values.

-- ---- what to set ---------------------------------------------------------------
local MAX_LEVEL = 99               -- highest level the two-digit bar can display
local MAX_HP = 255                 -- byte maximum; the bar's HP field fits three digits
-- --------------------------------------------------------------------------------

local LABEL = "Max Level/HP"

local PLAYER_SLOT = 0x12
local ACTOR_HP = 0xA052
local ACTOR_MAX_HP = 0xA065
local ACTOR_LEVEL = 0xA078

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

local hp_at = ACTOR_HP + PLAYER_SLOT
local max_at = ACTOR_MAX_HP + PLAYER_SLOT
local level_at = ACTOR_LEVEL + PLAYER_SLOT

local was_hp, was_max, was_level = rd(hp_at), rd(max_at), rd(level_at)

if was_hp == nil or was_max == nil or was_level == nil then
  emu.log(LABEL .. ": cannot read Shiren's actor slot; nothing changed")
  return
end

-- A live run always has a non-zero max HP. Zero means these addresses are not showing a
-- player right now -- no run at all, or the menu is open and a different SRAM bank is
-- mapped into the window -- and writing there would land somewhere unrelated.
if was_max == 0 then
  emu.log(LABEL .. ": max HP reads 0, so this is not a live player slot. Stand in a "
          .. "dungeon with the menu closed and run again; nothing changed")
  return
end

emu.log(string.format("%s: before  Lv %d   HP %d/%d", LABEL, was_level, was_hp, was_max))

wr(level_at, MAX_LEVEL)
wr(max_at, MAX_HP)
wr(hp_at, MAX_HP)

local now_hp, now_max, now_level = rd(hp_at), rd(max_at), rd(level_at)
emu.log(string.format("%s: after   Lv %d   HP %d/%d", LABEL, now_level, now_hp, now_max))

if now_level ~= MAX_LEVEL or now_max ~= MAX_HP or now_hp ~= MAX_HP then
  emu.log(LABEL .. ": the writes did not stick -- the game may have overwritten them "
          .. "on the next frame. Try again while standing still in a dungeon.")
else
  emu.log(LABEL .. ": done. Take a step or open the menu to redraw the status bar.")
end
