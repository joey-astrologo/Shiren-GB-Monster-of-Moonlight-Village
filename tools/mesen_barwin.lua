-- mesen_barwin.lua
-- Find what writes the status bar. No tile-value guessing.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Original Japanese ROM. Get into a dungeon, walk a step or two, paste the SUMMARY.
--
-- The Tilemap Viewer settled two things earlier attempts got wrong:
--   * the status bar is the WINDOW layer, tilemap $9C00 -- not the background at $9800
--   * the window uses tileset base $1000, so its tile NUMBERS differ from the character
--     codes. Every value-filtered watch I wrote was therefore looking for the wrong
--     numbers, which is why they kept coming back empty.
--
-- So this filters on ADDRESS only: the first two rows of the window tilemap, which is
-- the whole bar (HP row and the 1F / Lv / fullness row). Whatever writes there is what
-- we need, whatever tile numbers it happens to use.

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, n in ipairs(names) do
    if tbl[n] ~= nil then return tbl[n], n end
  end
  return nil, nil
end

local cpuT, cpuName = pick(emu.cpuType, { "gameboy", "gb" })
local memT, memName = pick(emu.memType, { "gameboyMemory", "gbMemory", "gameboy" })
emu.log("cpuType -> " .. tostring(cpuName) .. "   memType -> " .. tostring(memName))

local LO, HI = 0x9C00, 0x9C3F      -- rows 0 and 1 of the window tilemap = the bar

local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onBar(address, value)
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"] or 0
  local b  = (st["cpu.b"] or 0) * 256 + (st["cpu.c"] or 0)
  local d  = (st["cpu.d"] or 0) * 256 + (st["cpu.e"] or 0)
  local h  = (st["cpu.h"] or 0) * 256 + (st["cpu.l"] or 0)
  hits = hits + 1
  local key = string.format("%04X:%04X", pc, address)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1
  local pbank = (pc < 0x4000) and 0 or curBank
  local row = string.format(
    "  pc b%-2d $%04X  -> $%04X = $%02X   bc=$%04X de=$%04X hl=$%04X",
    pbank, pc, address, value, b, d, h)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("=========== STATUS BAR WRITER SUMMARY ===========")
  emu.log(string.format("bar tilemap writes: %d   distinct (pc,addr): %d", hits, uniq))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
  emu.log("bc/de/hl are logged too -- one of them points at the source text.")
  emu.log("=================================================")
  emu.log("")
end

local ok = false
if cpuT ~= nil and memT ~= nil then
  ok = pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write,
             0x2000, 0x3FFF, cpuT, memT)
end
if not ok then pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write, 0x2000, 0x3FFF) end

local ok2 = false
if cpuT ~= nil and memT ~= nil then
  ok2 = pcall(emu.addMemoryCallback, onBar, emu.callbackType.write, LO, HI, cpuT, memT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onBar, emu.callbackType.write, LO, HI)
end
if not ok2 then
  emu.log("FAILED to register the window tilemap watch")
else
  emu.log("armed: watching window tilemap $9C00-$9C3F (the status bar), address-filtered only")
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 600 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Dungeon, walk a step so the bar redraws, then paste.")
