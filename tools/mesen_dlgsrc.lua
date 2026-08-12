-- mesen_dlgsrc.lua
-- Find where village dialogue pointers COME FROM.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use the ORIGINAL Japanese ROM (build/base.gb).
--
-- WHAT WE ALREADY KNOW. Village dialogue is reached like this:
--     event code pushes a pointer into the message queue ($3C5C)
--       -> bank 13 $67D5 takes the high byte in `a`, pulls the low byte from the
--          queue ($3C7B), and stores the pair at $CF7F/$CF80
--       -> bank 11 $569E / bank 14 $4010 read one line at a time from there
-- The pointer never exists as a constant in the ROM, so it cannot be found statically.
--
-- WHAT THIS ANSWERS. We hook the instant AFTER the pointer is stored, then read it back
-- out of $CF7F/$CF80 and recover the CALLER from the stack. The caller is the event code
-- that chose this conversation -- which is what an inserter would have to patch in order
-- to relocate these strings.
--
-- Setup sites (all bank 13, from a static scan for writes to $CF7F/$CF80):
--     $67E6/$67EA  -> hook $67ED
--     $6818/$681C  -> hook $681F
--     $6CAC/$6CB0  -> hook $6CB3
-- The line-readers at bank 11 $56B9/$56BD and bank 14 $4026/$402A also write these
-- addresses, but only to advance their own position, so they are deliberately NOT hooked.

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

local SETUP = { [0x67ED] = true, [0x681F] = true, [0x6CB3] = true }
local SETUP_BANK = 13

local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function rd(a)
  local ok, v = pcall(emu.read, a, memT)
  if ok and v ~= nil then return v end
  return 0
end

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onSetup()
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"]
  if not SETUP[pc] then return end
  if curBank ~= SETUP_BANK then return end        -- banked address: confirm the bank

  local ptr = rd(0xCF7F) + rd(0xCF80) * 256
  local sp = st["cpu.sp"]
  -- $67D5 pushes af,bc,de,hl before reaching here, so the return address is at sp+8
  local caller = -1
  if sp ~= nil then
    caller = (rd(sp + 8) + rd(sp + 9) * 256 - 3) & 0xFFFF
  end

  hits = hits + 1
  local key = string.format("%04X:%04X:%04X", pc, caller, ptr)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1

  local row = string.format("  setup $%04X   ptr $%04X   caller $%04X   (bank at call: %d)",
                            pc, ptr, caller, curBank)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("========= DIALOGUE POINTER SOURCE SUMMARY =========")
  emu.log(string.format("setups seen: %d   distinct: %d", hits, uniq))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
  emu.log("===================================================")
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
  ok2 = pcall(emu.addMemoryCallback, onSetup, emu.callbackType.exec, 0x67ED, 0x6CB3, cpuT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onSetup, emu.callbackType.exec, 0x67ED, 0x6CB3)
end
if not ok2 then
  emu.log("FAILED to hook the dialogue setup sites")
else
  emu.log("armed: watching bank 13 dialogue setup at $67ED / $681F / $6CB3")
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 1800 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("Talk to a few town NPCs. Each NEW line names the event code behind a conversation.")
