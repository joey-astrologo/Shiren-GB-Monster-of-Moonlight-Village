-- mesen_unlock_all_awards.lua
-- Temporarily expose all 40 Awards rows on the title-menu Awards screen.
--
-- HOW TO USE
--   1. Back up the .srm or use a disposable save state.
--   2. At the title menu, load this script in Mesen's Script Window and press Run (F5).
--   3. Open Rank/Pass -> Pass -> the desired Log.
--   4. Use Up/Down to inspect all eight pages (five awards per page).
--   5. Back out to the main title menu. The script restores the original bytes there.
--
-- SAFETY
--   This does not touch inventory, level, dungeon objects, SRAM, or the expanded player-
--   name record. It changes only the selected log's live WRAM award bitfield at
--   $C57D/$C58D/$C59D while the Awards route is active, and restores its exact original
--   bytes only after screen 15 (the real main title menu) is dispatched again.
--   Still use a backup: closing the emulator or stopping the script while the Awards
--   screen is open can prevent the normal restoration callback from running.

local DISPATCH = 0x48AA
local DISPATCH_BANK = 4
local FLAG_BASES = { 0xC57D, 0xC58D, 0xC59D }
local FLAG_BYTES = 5
local LABEL = "Unlock All Awards"

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

local originals = {}
local active = false

local function selected_log()
  local log = rd(0xC6AB)
  if log == nil or log < 0 or log >= #FLAG_BASES then return nil end
  return log + 1
end

local function unlock(log)
  if originals[log] == nil then
    originals[log] = {}
    for offset = 0, FLAG_BYTES - 1 do
      local value = rd(FLAG_BASES[log] + offset)
      if value == nil then
        emu.log(LABEL .. ": FAILED reading live award bytes; nothing changed")
        originals[log] = nil
        return false
      end
      originals[log][offset + 1] = value
    end
  end
  local base = FLAG_BASES[log]
  for offset = 0, FLAG_BYTES - 1 do
    if not wr(base + offset, 0xFF) then
      emu.log(string.format("%s: FAILED writing $%04X", LABEL, base + offset))
      return false
    end
  end
  active = true
  return true
end

local function restore()
  if not active then return end
  for log, base in ipairs(FLAG_BASES) do
    if originals[log] ~= nil then
      for offset = 0, FLAG_BYTES - 1 do
        wr(base + offset, originals[log][offset + 1])
      end
    end
  end
  originals = {}
  active = false
  emu.log(LABEL .. ": original award bytes restored")
end

local function on_dispatch()
  -- Reject an identically addressed routine in any other switchable ROM bank.
  if rd(0x4000) ~= DISPATCH_BANK then return end
  local ok, state = pcall(emu.getState)
  if not ok or state == nil then return end
  local screen = state["cpu.a"] or -1
  if screen == 30 or screen == 32 or screen == 34 then
    local log = selected_log()
    if log ~= nil then
      local first = not active
      if unlock(log) and first then
        emu.log(string.format(
          "%s: all 40 rows temporarily available for Log %d; use Up/Down", LABEL, log))
      end
    end
  elseif screen == 15 and active then
    -- Do not restore on intermediate dispatches. Screen 34 prepares eight pages from
    -- these flags and may dispatch helpers before it becomes visible; restoring there
    -- leaves the page count and row source inconsistent and produces a white-screen hang.
    restore()
  end
end

local armed = false
if cpuT ~= nil then
  armed = pcall(emu.addMemoryCallback, on_dispatch, emu.callbackType.exec,
                DISPATCH, DISPATCH, cpuT)
end
if not armed then
  armed = pcall(emu.addMemoryCallback, on_dispatch, emu.callbackType.exec,
                DISPATCH, DISPATCH)
end

if armed then
  emu.log(LABEL .. ": armed. Open Rank/Pass from the title menu.")
else
  emu.log(LABEL .. ": FAILED to hook bank 4 $48AA")
end
