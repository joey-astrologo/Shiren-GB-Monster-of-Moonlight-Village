-- mesen_bardraw.lua
-- Find the code that draws the status bar (HP / floor / Lv / fullness).
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use the ORIGINAL Japanese ROM (build/base.gb).
--
-- WHAT TO DO: get into a dungeon so the bottom status bar is visible, walk a few
-- steps so it redraws, then paste the SUMMARY. Ten seconds is plenty.
--
-- WHY THIS AND NOT ANOTHER STRING WATCH. All seven occurrences of まんぷくど in the ROM
-- sit inside prose sentences ("max fullness", "fullness became N%") -- none is a
-- standalone label. So the bar does not read a string; it assembles the text itself,
-- the same way `HP` is drawn from the H and P glyph codes. Watching string bytes can
-- therefore never find it. What CAN find it is the moment those tiles reach the screen.
--
-- v2: watch the WRAM TILEMAP BUFFER, not VRAM. The first run found bank 4 $4496, but
-- that turned out to be a generic blitter -- `ld hl,$9800 / ld de,$C300` copying an
-- 18x32 screen from WRAM to VRAM. The label is composed into that buffer earlier, so
-- watching VRAM only ever finds the copy. $9800+n comes from $C300+n, so the tile seen
-- at $9863 was written to $C363 by whatever actually draws it.
--
-- HOW IT WORKS. Tile index = character code + 16, proven from the game's own
-- `ld hl,$7680` font base. So the kana in まんぷくど become these tile numbers:
--     ま $29 -> $39     ん $38 -> $48     く $12 -> $22
--     ふ $26 -> $36     と $1E -> $2E
-- We watch writes into the tilemaps ($9800-$9FFF) and log only those whose VALUE is one
-- of those tiles. That fires exactly when the label is drawn, and the PC is the routine
-- we need.

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

-- Tiles for BOTH labels the game assembles itself rather than reading as strings:
--   まんぷくど (fullness, bottom bar)  and  なんいど (difficulty, status box).
-- `Diff` IS correctly written at 31:$41DC, but the trace showed that address is never
-- read -- so the difficulty label is drawn the same way the fullness one is. Watching
-- both sets of tiles means a single run locates both routines.
-- CORRECTED. These were all 16 too high, which is why earlier runs barely fired.
-- tile = code + 16 holds for GLYPH DATA in the font ($7680 + code*8), but the tilemap
-- stores the raw code. Verified from the trace: bc=$41D1 logged tile $0F, and 31:$41D0
-- holds `0f 10 22` = おかね -- so the tile written IS the code, and the character comes
-- from bc-1.
local WANT = {
  [0x29] = "ma",  [0x38] = "n",   [0x12] = "ku",  [0x26] = "fu",  [0x1E] = "to",
  [0x1F] = "na",  [0x0C] = "i",   [0x0D] = "u",
}

local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onVram(address, value)
  if WANT[value] == nil then return end
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"] or 0
  hits = hits + 1
  local key = string.format("%04X:%02X", pc, value)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1
  local pbank = (pc < 0x4000) and 0 or curBank
  local row = string.format("  WRITER pc b%-2d $%04X   tile $%02X (%s) -> $%04X",
                            pbank, pc, value, WANT[value], address)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("=========== STATUS BAR DRAW SUMMARY ===========")
  emu.log(string.format("matching tile writes: %d   distinct (pc,tile): %d", hits, uniq))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
  emu.log("Each PC above writes one of the fullness-label tiles. That is the routine.")
  emu.log("===============================================")
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
  ok2 = pcall(emu.addMemoryCallback, onVram, emu.callbackType.write, 0xC300, 0xC6FF, cpuT, memT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onVram, emu.callbackType.write, 0xC300, 0xC6FF)
end
if not ok2 then
  emu.log("FAILED to register the tilemap write watch")
else
  emu.log("armed: watching the WRAM tilemap buffer $C300-$C6FF for label tiles")
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 600 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Get into a dungeon so the status bar shows, walk a few steps, then paste.")
