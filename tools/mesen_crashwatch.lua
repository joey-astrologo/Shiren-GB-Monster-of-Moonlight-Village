-- mesen_crashwatch.lua -- catch WHY the game halts, and say who called into garbage.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5), then play until it
-- hangs. It prints the moment the CPU falls into `rst $38` and, crucially, the RETURN
-- ADDRESSES on the stack -- which is what names the routine that jumped into nothing.
--
-- WHY $0038. On a DMG an unmapped/blank read returns $FF, and $FF is `rst $38`, which
-- calls $0038 -- which is itself $FF, so it recurses until the stack eats itself. So a
-- game "freezing" almost always means the CPU is spinning at $0038, and the interesting
-- information is not that it is there, it is HOW it got there. This script reconstructs
-- that from the stack rather than guessing.
--
-- IMPORTANT, and it cost this project a session before: DO NOT put an exec breakpoint on
-- $0038 to catch this. Once the ROM is spinning there the callback fires every few
-- cycles and the emulator becomes unusable. This script samples at end-of-frame instead,
-- which is cheap and catches the spin just as reliably.
--
-- What it prints on the first bad frame:
--   * PC, SP and the mapped ROM bank
--   * the top of the stack decoded as return addresses, newest first
--   * a short PC history from the frames leading up to it
--   * whether the LCD was still on (a black screen with the LCD on is a different bug)
--
-- Cross-reference an address with:  python3 tools/dis.py build/shiren_en.gb <addr> 20 --bank N

local function pick(tbl, names)
  if tbl == nil then return nil, nil end
  for _, n in ipairs(names) do
    if tbl[n] ~= nil then return tbl[n], n end
  end
  return nil, nil
end

local cpuT = pick(emu.cpuType, { "gameboy", "gb" })
local memT = pick(emu.memType, { "gameboyMemory", "gbMemory", "gameboy" })

-- The mapped ROM bank is tracked by watching MBC writes, NOT read out of emu.getState():
-- the state table has no bank field on this core, and $4000-$7FFF is bank-ambiguous.
local curBank = 1
local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local HIST = 24
local hist, histN = {}, 0
local fired = false
local frame = 0
local sameCount, lastPC = 0, -1

local function readByte(addr)
  local ok, v = pcall(emu.read, addr, memT)
  if not ok or v == nil then
    ok, v = pcall(emu.read, addr)
  end
  return (ok and v) or 0
end

local function word(addr)
  return readByte(addr) + readByte(addr + 1) * 256
end

local function bankOf(pc)
  if pc < 0x4000 then return 0 end
  if pc >= 0x8000 then return -1 end        -- RAM/echo: executing outside ROM entirely
  return curBank
end

local function label(pc)
  -- The few resident addresses this project cares about, so the dump reads as prose.
  if pc >= 0x0062 and pc <= 0x00FF then return " <- DTE expander / loop2 / dte_box" end
  if pc >= 0x3FEC and pc <= 0x3FFF then return " <- dte_box_hi (bank 0 tail)" end
  if pc == 0x0038 then return " <- rst $38 (executing $FF)" end
  if pc == 0x028B then return " <- message-queue push" end
  return ""
end

local function report(why, pc, sp)
  emu.log("")
  emu.log("================ HALT DETECTED ================")
  emu.log(string.format("  reason : %s", why))
  emu.log(string.format("  frame  : %d", frame))
  emu.log(string.format("  PC     : $%04X   (bank %d)%s", pc, bankOf(pc), label(pc)))
  emu.log(string.format("  SP     : $%04X", sp))
  emu.log(string.format("  bank   : %d mapped at $4000", curBank))
  local lcdc = readByte(0xFF40)
  emu.log(string.format("  LCDC   : $%02X  (LCD %s)   WY=%d",
                        lcdc, (lcdc >= 128) and "ON" or "OFF", readByte(0xFF4A)))
  emu.log("")
  emu.log("  stack, newest first -- these are RETURN addresses; the first one that is a")
  emu.log("  plausible instruction start is the routine that called into nothing:")
  for i = 0, 11 do
    local a = sp + i * 2
    if a <= 0xFFFE then
      local v = word(a)
      emu.log(string.format("    [SP+%2d] $%04X%s", i * 2, v, label(v)))
    end
  end
  emu.log("")
  emu.log("  PC sampled at end-of-frame, oldest first:")
  local n = math.min(histN, HIST)
  for i = 1, n do
    local idx = ((histN - n + i - 1) % HIST) + 1
    emu.log(string.format("    %s", hist[idx]))
  end
  emu.log("")
  emu.log("  Next: disassemble the first plausible return address, e.g.")
  emu.log("    python3 tools/dis.py build/shiren_en.gb 0x<addr> 20 --bank <bank>")
  emu.log("  If it lands mid-instruction or in data, something repointed a live byte --")
  emu.log("  that is the failure mode this ROM has had twice. See HANDOFF.md TRAPS.")
  emu.log("==============================================")
  emu.log("")
end

local function onFrame()
  frame = frame + 1
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  -- Mesen's state table is FLAT with dotted keys: st["cpu.pc"], NOT st.cpu.pc.
  local pc = st["cpu.pc"] or 0
  local sp = st["cpu.sp"] or 0

  histN = histN + 1
  hist[((histN - 1) % HIST) + 1] =
    string.format("frame %6d  PC $%04X (bank %d)%s", frame, pc, bankOf(pc), label(pc))

  if fired then return end

  if pc == 0x0038 then
    fired = true
    report("PC is at $0038 -- the CPU is executing $FF (rst $38 recursion)", pc, sp)
    return
  end
  if pc >= 0x8000 and pc < 0xA000 then
    fired = true
    report("PC is in VRAM -- execution left the ROM entirely", pc, sp)
    return
  end
  -- A frozen-but-not-crashed loop: the same PC at end of frame for seconds on end.
  if pc == lastPC then
    sameCount = sameCount + 1
    if sameCount == 180 then
      fired = true
      report("PC unchanged for 180 frames -- a stuck loop rather than an $FF crash", pc, sp)
    end
  else
    lastPC, sameCount = pc, 0
  end
end

pcall(function()
  local ok = pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write,
                   0x2000, 0x3FFF, cpuT, memT)
  if not ok then
    pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write, 0x2000, 0x3FFF)
  end
end)

local armed = pcall(emu.addEventCallback, onFrame, emu.eventType.endFrame)
if not armed then
  emu.log("FAILED to register the end-of-frame callback -- check the Mesen version")
else
  emu.log("crashwatch armed. Play until it hangs; the report prints here automatically.")
  emu.log("Sampling at end-of-frame, so it will NOT bog the emulator down the way an")
  emu.log("exec breakpoint on $0038 does.")
end
