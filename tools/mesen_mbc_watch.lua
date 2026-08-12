-- mesen_mbc_watch.lua
-- Shiren GB: characterize every MBC register write the game makes, to decide
-- whether an MBC1 -> MBC5 conversion (needed to expand past 512 KiB) is safe.
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- ALL OUTPUT APPEARS IN THE LOG PANE AT THE BOTTOM OF THE SCRIPT WINDOW.
-- You should immediately see "armed" lines there; if not, the script isn't
-- running (errors also show in that pane).
--
-- WHAT TO DO: just play normally for ~15 minutes. Cover a spread of content:
--   title screen -> village -> talk to a few NPCs -> enter the dungeon ->
--   use items -> take stairs a few floors -> save / suspend -> reload.
-- Bank switching happens constantly, so this exercises it heavily.
-- Then paste the SUMMARY block (it prints every ~10s, and grows as it learns).
--
-- WHY: on the GB, all writes to $0000-$7FFF are MBC control writes (ROM is not
-- writable). MBC1 and MBC5 divide that space differently:
--
--   range        MBC1                  MBC5                    verdict
--   $0000-1FFF   RAM enable            RAM enable              same
--   $2000-2FFF   ROM bank (low 5)      ROM bank (low 8)        same
--   $3000-3FFF   ROM bank (low 5)      ROM bank BIT 8          *** HAZARD ***
--   $4000-5FFF   RAM bank / ROM hi     RAM bank (4-bit)        same for values 0-3
--   $6000-7FFF   banking mode select   ignored                 same if mode always 0
--
-- So we need three questions answered:
--   Q1  Does anything ever write to $3000-3FFF?   (must be no, or those sites need patching)
--   Q2  Do $4000-5FFF writes only ever carry 0-3? (must be yes; game has 4 SRAM banks)
--   Q3  Is MBC1 advanced mode ($6000-7FFF, value 1) ever selected? (must be no)

--------------------------------------------------------------------------
-- API probing: Mesen's enum names vary by version, so pick whatever exists
-- rather than hardcoding and failing with an unhelpful nil error.
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

--------------------------------------------------------------------------
-- state
--------------------------------------------------------------------------
local sites = {}        -- key "PC@bank" -> { addr, val, count, pc, bank }
local siteCount = 0
local totals = { ramEnable = 0, romBank = 0, romBankHi = 0, ramBank = 0, mode = 0 }
local romBankAddrs = {} -- every distinct address used for ROM bank select
local ramBankVals = {}  -- every distinct value written to $4000-5FFF
local modeVals = {}     -- every distinct value written to $6000-7FFF
local hazardSites = {}  -- writes landing in $3000-3FFF
local hazardCount = 0
local curBank = 1       -- our own mirror of the ROM bank register

local function getPC()
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return -1 end
  return st["cpu.pc"] or (st.cpu and st.cpu.pc) or -1
end

--------------------------------------------------------------------------
-- the watch
--------------------------------------------------------------------------
local function onMbcWrite(address, value)
  local pc = getPC()

  -- classify by MBC register range
  if address < 0x2000 then
    totals.ramEnable = totals.ramEnable + 1
  elseif address < 0x4000 then
    totals.romBank = totals.romBank + 1
    romBankAddrs[address] = (romBankAddrs[address] or 0) + 1
    curBank = value                      -- mirror it, so we can label callers
    if address >= 0x3000 then
      totals.romBankHi = totals.romBankHi + 1
      hazardCount = hazardCount + 1
      local k = string.format("%04X@%04X", pc, address)
      if not hazardSites[k] then
        hazardSites[k] = true
        emu.log(string.format(
          "*** HAZARD: write $%04X = %02X from PC=$%04X (bank %d) -- MBC5 would read this as ROM bank bit 8",
          address, value, pc, curBank))
      end
    end
  elseif address < 0x6000 then
    totals.ramBank = totals.ramBank + 1
    ramBankVals[value] = (ramBankVals[value] or 0) + 1
  else
    totals.mode = totals.mode + 1
    modeVals[value] = (modeVals[value] or 0) + 1
    if value ~= 0 then
      emu.log(string.format(
        "*** NOTE: MBC1 mode register set to %d from PC=$%04X -- advanced banking mode in use",
        value, pc))
    end
  end

  -- remember each distinct calling site once
  -- (PC alone is ambiguous across banks, so tag with the bank we believe is mapped)
  local key = string.format("%04X:%d:%04X", pc, (pc >= 0x4000 and curBank or 0), address)
  local s = sites[key]
  if s == nil then
    siteCount = siteCount + 1
    sites[key] = { addr = address, val = value, count = 1, pc = pc,
                   bank = (pc >= 0x4000 and curBank or 0) }
  else
    s.count = s.count + 1
  end
end

--------------------------------------------------------------------------
-- summary
--------------------------------------------------------------------------
local function keysSorted(t)
  local out = {}
  for k in pairs(t) do out[#out + 1] = k end
  table.sort(out)
  return out
end

local function summary()
  emu.log("")
  emu.log("================ MBC WRITE SUMMARY ================")
  emu.log(string.format("distinct call sites: %d", siteCount))
  emu.log(string.format("counts: ramEnable=%d romBank=%d ramBank=%d mode=%d",
    totals.ramEnable, totals.romBank, totals.ramBank, totals.mode))

  emu.log("-- Q1: addresses used for ROM bank select ($2000-$3FFF)")
  for _, a in ipairs(keysSorted(romBankAddrs)) do
    emu.log(string.format("     $%04X  x%d%s", a, romBankAddrs[a],
      a >= 0x3000 and "   <-- IN HAZARD RANGE" or ""))
  end
  if totals.romBank == 0 then emu.log("     (none seen yet)") end

  emu.log("-- Q2: values written to RAM bank select ($4000-$5FFF)")
  for _, v in ipairs(keysSorted(ramBankVals)) do
    emu.log(string.format("     value %d  x%d%s", v, ramBankVals[v],
      v > 3 and "   <-- >3, would not fit MBC1 RAM banking" or ""))
  end
  if totals.ramBank == 0 then emu.log("     (none seen yet)") end

  emu.log("-- Q3: values written to mode select ($6000-$7FFF)")
  for _, v in ipairs(keysSorted(modeVals)) do
    emu.log(string.format("     value %d  x%d%s", v, modeVals[v],
      v ~= 0 and "   <-- advanced mode" or ""))
  end
  if totals.mode == 0 then emu.log("     (none seen yet)") end

  -- self-assessment, so the result needs no interpretation to be useful
  local verdict
  if totals.romBank == 0 then
    verdict = "INCONCLUSIVE - no ROM bank writes seen yet; play longer"
  elseif hazardCount > 0 then
    verdict = string.format("HAZARD PRESENT - %d writes to $3000-3FFF; those sites need "
      .. "redirecting to $2000-2FFF before an MBC5 conversion", hazardCount)
  else
    local badRam, badMode = false, false
    for v in pairs(ramBankVals) do if v > 3 then badRam = true end end
    for v in pairs(modeVals) do if v ~= 0 then badMode = true end end
    if badRam or badMode then
      verdict = "MOSTLY CLEAN, but check the flagged RAM-bank / mode lines above"
    else
      verdict = "CLEAN so far - all ROM bank writes in $2000-2FFF, RAM bank <=3, mode always 0. "
             .. "MBC1 -> MBC5 looks like a drop-in swap."
    end
  end
  emu.log("VERDICT: " .. verdict)
  emu.log("(dynamic trace only covers code paths actually executed - keep playing to widen coverage)")
  emu.log("===================================================")
  emu.log("")
end

--------------------------------------------------------------------------
-- register
--------------------------------------------------------------------------
local ok, err
if cpuT ~= nil and memT ~= nil then
  ok, err = pcall(emu.addMemoryCallback, onMbcWrite, emu.callbackType.write,
                  0x0000, 0x7FFF, cpuT, memT)
end
if not ok then
  -- older/simpler signature without cpu/mem type
  ok, err = pcall(emu.addMemoryCallback, onMbcWrite, emu.callbackType.write, 0x0000, 0x7FFF)
end
if not ok then
  emu.log("FAILED to register memory callback: " .. tostring(err))
  emu.log("Check the cpuType/memType names logged above against this Mesen build.")
else
  emu.log("armed: watching all writes to $0000-$7FFF (the MBC registers)")
end

-- periodic summary so you never have to stop playing to get output
local frames = 0
local okEv = pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 600 == 0 then summary() end
end, emu.eventType.endFrame)
if not okEv then
  emu.log("note: periodic summary unavailable; summary() still runs at script stop")
end

emu.log("Play normally for ~15 min: village, NPCs, dungeon, items, stairs, save/reload.")
emu.log("A SUMMARY block prints every ~10 seconds. Paste the last one.")
