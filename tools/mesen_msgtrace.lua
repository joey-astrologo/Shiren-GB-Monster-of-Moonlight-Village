-- mesen_msgtrace.lua  (v2)
-- Shiren GB: log every call into the message system, to find how the ~290 unaccounted
-- village/story strings are addressed.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- ALL OUTPUT APPEARS IN THE LOG PANE AT THE BOTTOM OF THE SCRIPT WINDOW.
-- Use the ORIGINAL Japanese ROM (build/base.gb) so pointers match script/script.json.
--
-- WHY v2: v1 hooked only $028B and caught nothing in town -- only dungeon and combat
-- text. That was the useful part of the failure: $028B is NOT the only printer. There
-- is a whole block of entry points at $028B/$02A2/$02B1/$02CD/$02F0/$030C, each taking
-- different registers, plus what looks like a message-TYPE dispatcher at $031B that
-- indexes a jump table at $0396. Town dialogue must use one of the others.
--
-- v1 also reported a bogus bank: it mirrored the last write to $2000-$3FFF, but $028B
-- only QUEUES the pointer and the read happens later, after a bank switch. So the bank
-- at call time is not the string's bank. It is still logged, but only as a hint --
-- pointers are resolved offline against script.json instead.

--------------------------------------------------------------------------
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

-- Every known entry point into the message system, with what each consumes.
local ENTRY = {
  [0x028B] = "bc",        -- -> $23A4   (dungeon/combat text; all v1 caught)
  [0x02A2] = "-",         -- -> $23CF
  [0x02B1] = "a,bc",      -- -> $23D3   3 params: possibly bank + pointer
  [0x02CD] = "de",        -- -> $23E0
  [0x02F0] = "a,de",      -- -> $23C0
  [0x030C] = "-",         -- -> $23ED
  [0x031B] = "a=type",    -- message-type dispatcher, jump table at $0396
}
local LO, HI = 0x028B, 0x031B

--------------------------------------------------------------------------
local curBank = 1
local seen, rows = {}, {}
local calls, uniq = 0, 0

local function rd(addr)
  local ok, v = pcall(emu.read, addr, memT)
  if ok and v ~= nil then return v end
  return 0
end

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onEntry()
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"]
  local kind = ENTRY[pc]
  if kind == nil then return end          -- only fire on actual entry points

  local a = st["cpu.a"] or 0
  local b = st["cpu.b"] or 0
  local c = st["cpu.c"] or 0
  local d = st["cpu.d"] or 0
  local e = st["cpu.e"] or 0
  local sp = st["cpu.sp"]

  local caller = -1
  if sp ~= nil then
    caller = (rd(sp) + rd(sp + 1) * 256 - 3) & 0xFFFF
  end

  calls = calls + 1
  local key = string.format("%04X:%04X:%02X%02X%02X%02X%02X", pc, caller, a, b, c, d, e)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1

  local cbank = (caller < 0x4000) and 0 or curBank
  local row = string.format(
    "  entry $%04X (%-6s)  caller b%-2d $%04X   a=%02X bc=$%02X%02X de=$%02X%02X   bank~%d",
    pc, kind, cbank, caller, a, b, c, d, e, curBank)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

--------------------------------------------------------------------------
local function summary()
  emu.log("")
  emu.log("============== MESSAGE TRACE v2 SUMMARY ==============")
  emu.log(string.format("total entry calls: %d   distinct: %d", calls, uniq))
  local byentry = {}
  for _, r in ipairs(rows) do
    local e = r:match("entry %$(%x+)")
    byentry[e] = (byentry[e] or 0) + 1
  end
  local parts = {}
  for k, v in pairs(byentry) do parts[#parts + 1] = "$" .. k .. ":" .. v end
  emu.log("distinct per entry point: " .. table.concat(parts, "  "))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
  emu.log("======================================================")
  emu.log("")
end

--------------------------------------------------------------------------
local ok = false
if cpuT ~= nil and memT ~= nil then
  ok = pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write,
             0x2000, 0x3FFF, cpuT, memT)
end
if not ok then
  pcall(emu.addMemoryCallback, onBankWrite, emu.callbackType.write, 0x2000, 0x3FFF)
end

local ok2 = false
if cpuT ~= nil then
  ok2 = pcall(emu.addMemoryCallback, onEntry, emu.callbackType.exec, LO, HI, cpuT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onEntry, emu.callbackType.exec, LO, HI)
end
if not ok2 then
  emu.log("FAILED to hook the message entry block")
else
  emu.log(string.format("armed: exec hook over $%04X-$%04X, filtered to %d entry points",
                        LO, HI, 7))
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 1800 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Talk to ONE town NPC first -- if nothing logs, tell me and we hook deeper.")
