-- mesen_srcptr.lua
-- Find the SOURCE of any text drawn by the bank 31 renderer -- specifically the
-- fullness label on the bottom bar.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use the ORIGINAL Japanese ROM (build/base.gb). Get into a dungeon so the bottom bar
-- shows, walk a few steps, then paste the SUMMARY.
--
-- WHY THIS IS THE LAST STEP. Bank 31 $4136 (`ld [hl+],a`) is the routine that writes
-- one character tile into the WRAM tilemap buffer, and it reads its text through `bc`.
-- So at that instant, bc IS the address of the character being drawn. Logging bc tells
-- us where the label lives -- no searching, no guessing.
--
-- The same routine draws dakuten as separate tiles on the row above (hl-33), which is
-- why marks cost a byte but no screen cell.
--
-- v2: NO FILTERS. v1 rejected everything for two reasons. It checked curBank == 31,
-- which is redundant ($4136 is in the banked window, so bank 31 must already be mapped)
-- and fails outright if the mirrored bank is stale. It also required the destination to
-- be >= $C500, assuming an 18x32 buffer at $C300 -- but the previous run showed writes
-- at $C61E, past the end of that. Rather than guess the bar's buffer a second time, log
-- every character the renderer draws and sort it out offline.
--
-- Deduped by source address, so the list stays bounded however long you play.

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

local WRITER = 0x4136       -- bank 31: ld [hl+],a
local BAR_LO = 0xC500       -- bottom two rows of the 18x32 buffer

local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onWrite()
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local h = (st["cpu.h"] or 0) * 256 + (st["cpu.l"] or 0)
  local b = (st["cpu.b"] or 0) * 256 + (st["cpu.c"] or 0)
  local a = st["cpu.a"] or 0
  hits = hits + 1
  local key = string.format("%04X", b)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1
  local row = string.format("  src bc=$%04X (bank %d)  tile $%02X  -> buf $%04X", b, curBank, a, h)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("========== TEXT SOURCE POINTER SUMMARY ==========")
  emu.log(string.format("bar-row character writes: %d   distinct: %d", hits, uniq))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
  emu.log("bc is the ROM address of each character drawn on the status bar.")
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
if cpuT ~= nil then
  ok2 = pcall(emu.addMemoryCallback, onWrite, emu.callbackType.exec, WRITER, WRITER, cpuT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onWrite, emu.callbackType.exec, WRITER, WRITER)
end
if not ok2 then
  emu.log("FAILED to hook the character writer")
else
  emu.log("armed: hooked $4136, logging EVERY character source (deduped by bc)")
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 600 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Dungeon, walk a few steps so the bar redraws, then paste.")
