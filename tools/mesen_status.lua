-- mesen_status.lua
-- Find exactly which bytes the STATUS SCREEN reads for its labels.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use the ORIGINAL Japanese ROM (build/base.gb) so offsets match script.json.
--
-- THE PROBLEM. Most script sits between $FF terminators, so a label's start is obvious.
-- The status screen does not: おかね, なんいど and まんぷくど are packed into composites
-- with layout bytes and no terminator in front of them. Guessing a boundary risks
-- writing over the column layout, so instead we watch which addresses actually get read.
--
-- WHAT TO DO
--   1. Load a save and get in-game.
--   2. Open the STATUS / PAUSE screen (the one with Weapon / Shield / Str / Exp).
--   3. Let it sit a moment, then close and reopen it once.
--   4. Paste the SUMMARY.
--
-- Every distinct (pc, address) is logged once, so the list stays short. Reads are
-- confirmed against the live ROM bank -- $4000-$7FFF shows whichever bank is mapped, and
-- an earlier version of this trick reported a static guess and produced 262 unusable rows.

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

-- Windows worth watching, with the bank each must be read from to count.
-- WIDE MODE. The first pass proved $41DC (nanido) is never read and that my guessed
-- manpukudo windows in banks 13/14 were wrong. Rather than guess again, log every read
-- in the banked window from ANY bank and let the offline pass work out which bytes are
-- text. Deduped by (pc, bank, address), so the list stays finite.
local WATCH = nil
local LO, HI = 0x4000, 0x7FFF

local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onRead(address, value)

  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"] or 0
  hits = hits + 1
  local key = string.format("%04X:%04X", pc, address)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1
  local pbank = (pc < 0x4000) and 0 or curBank
  local row = string.format("  pc b%-2d $%04X   reads b%d:$%04X", pbank, pc, curBank, address)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("============ STATUS SCREEN READ SUMMARY ============")
  emu.log(string.format("reads in watched windows: %d   distinct (pc,addr): %d", hits, uniq))
  emu.log("")
  local lo = 0xFFFF
  for _, r in ipairs(rows) do
    emu.log(r)
    local a = tonumber(r:match("reads b%d+:%$(%x+)"), 16)
    if a and a < lo then lo = a end
  end
  if uniq > 0 then
    emu.log("")
    emu.log(string.format("lowest address read: $%04X -- likely a label start", lo))
  end
  emu.log("====================================================")
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
  ok2 = pcall(emu.addMemoryCallback, onRead, emu.callbackType.read, LO, HI, cpuT, memT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onRead, emu.callbackType.read, LO, HI)
end
if not ok2 then
  emu.log("FAILED to register the read watch")
else
  emu.log("armed: watching the status-screen label windows (bank-confirmed)")
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 900 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Open the STATUS / PAUSE screen, wait a beat, close and reopen it, then paste.")
