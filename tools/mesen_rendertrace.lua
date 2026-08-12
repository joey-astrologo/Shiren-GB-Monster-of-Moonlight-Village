-- mesen_rendertrace.lua -- which renderer draws which screen?
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use build/base.gb (the Japanese original).
--
-- WHY THIS EXISTS. Four sites in bank 13 load the font base $7680, and they are not
-- all the same kind of thing:
--
--   13:$4418  per-character composer, `de` runs over tile DATA   -> VWF-able
--   13:$75DD  struct-driven single character, one caller         -> VWF-able
--   13:$75A9  fixed tile-run copier (blank/decoration)           -> not text
--   13:$7643  uploads 128 tiles to VRAM $9000 + 68 to $8800      -> STATIC FONT
--
-- That last one matters. A font preloaded into VRAM means some text is drawn by
-- writing TILEMAP INDICES -- fixed 8x8 cells, one glyph per cell, which no amount of
-- VWF work in the composer will affect. This script answers which screens use which
-- path, because that is exactly the scope of the VWF job.
--
-- Guessing where code lives has failed repeatedly on this ROM (see FINDINGS.md), so
-- this is a positive test: run it, walk every screen, read off what actually fired.
--
-- WHAT TO DO: load, run, then visit in any order --
--   title / file select, difficulty select, name entry, village, an NPC conversation,
--   the dungeon, the item menu, the item ACTION menu (the 4-cell one), the status
--   screen, the results screen.
-- You do NOT need to note frame numbers. The log records the text itself, so the
-- content identifies the screen. Paste the whole log; decode it with
--   python3 tools/decodetrace.py <logfile>
--
-- v2: emu.getState() returns a FLAT table with dotted keys ("cpu.pc", "cpu.d"), not
-- nested tables -- v1 indexed st.cpu and crashed on every hit. Bank is tracked from
-- MBC writes rather than read from state, matching mesen_strread.lua.
--
-- v3: the tilemap COUNT in v2 was useless -- the dungeon map is drawn with tilemap
-- writes too, so a sustained 4800/window was terrain, not text. v3 logs the shape
-- instead: horizontal RUNS of consecutive cells (what text looks like) with their
-- bytes, plus the $CF07 line buffer on every compose. Both decode offline.

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

local BANK13 = 13
local SITES = {
  [0x4418] = 'compose',   -- per-character tile composer
  [0x75DD] = 'struct',    -- struct-driven single char
  [0x75A9] = 'tilerun',   -- fixed run copy (not text)
  [0x7643] = 'fontload',  -- static font -> VRAM
}

local curBank = 1
local hits = {}
local frame = 0
local tmwrites = {}     -- tilemap address -> last value written this window
local tmcount = 0
local lastline = ''

-- v3: a raw tilemap COUNT cannot answer the question -- the dungeon map is drawn with
-- tilemap writes too, so 4800/window was terrain, not text. What separates text from
-- terrain is shape: text is a horizontal RUN of consecutive cells written together.
-- So collect the runs and dump their bytes; they get decoded offline against codec.py
-- rather than embedding the character table in Lua.

local function hexof(addr, n)
  local out = {}
  for i = 0, n - 1 do
    local ok, v = pcall(emu.read, addr + i, memT)
    if not ok or v == nil then break end
    if v == 0xFF then break end          -- terminator
    out[#out + 1] = string.format('%02X', v)
  end
  return table.concat(out, ' ')
end

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local function onExec(address, value)
  local name = SITES[address]
  if name == nil then return end
  -- $4000-$7FFF is bank-ambiguous; bank 11 and 14 share the window with 13.
  if curBank ~= BANK13 then return end
  hits[name] = (hits[name] or 0) + 1
  -- The composer's source is the $CF07 line buffer. Reading it here is what makes the
  -- log self-labelling: the text on screen identifies the screen, so nobody has to
  -- correlate frame numbers by hand.
  if name == 'compose' then
    local s = hexof(0xCF07, 24)
    if s ~= '' and s ~= lastline then
      lastline = s
      emu.log(string.format('f%-7d TEXT  %s', frame, s))
    end
  end
end

local function onTilemapWrite(address, value)
  tmwrites[address] = value
  tmcount = tmcount + 1
end

local function onFrame()
  frame = frame + 1
  if frame % 60 ~= 0 then return end

  local parts = {}
  for _, name in ipairs({ 'compose', 'struct', 'tilerun', 'fontload' }) do
    local n = hits[name] or 0
    if n > 0 then
      parts[#parts + 1] = string.format('%s=%d', name, n)
      hits[name] = 0
    end
  end

  -- horizontal runs of >=4 consecutive cells written this window
  local addrs = {}
  for a in pairs(tmwrites) do addrs[#addrs + 1] = a end
  table.sort(addrs)
  local runs, dropped, i = {}, 0, 1
  while i <= #addrs do
    local j = i
    while j < #addrs and addrs[j + 1] == addrs[j] + 1 do j = j + 1 end
    local len = j - i + 1
    if len >= 4 then
      -- v4: filter by CONTENT, not by run count. v3 suppressed any window with more
      -- than 8 runs as "map redraw" -- but opening a menu also redraws the map, so
      -- the item action menu was thrown away every single time. Terrain runs are
      -- low metatile indices ($04 $06 $05 $07); text runs are character codes:
      -- $00 space, $01-$0A digits, $0B-$78 kana, $79/$7A dakuten, plus punctuation.
      local textish, n = 0, 0
      for k = i, j do
        local v = tmwrites[addrs[k]]
        n = n + 1
        if v == 0x00 or (v >= 0x0B and v <= 0x7B) or (v >= 0x9A and v <= 0xB5) then
          textish = textish + 1
        end
      end
      if textish / n >= 0.6 then
        local bytes = {}
        for k = i, math.min(j, i + 23) do
          bytes[#bytes + 1] = string.format('%02X', tmwrites[addrs[k]])
        end
        runs[#runs + 1] = string.format('$%04X:%d %s', addrs[i], len,
                                        table.concat(bytes, ' '))
      else
        dropped = dropped + 1
      end
    end
    i = j + 1
  end

  if #parts > 0 then
    emu.log(string.format('f%-7d %s  (tilemap %d writes)',
                          frame, table.concat(parts, '  '), tmcount))
  end
  for _, r in ipairs(runs) do
    emu.log(string.format('f%-7d  CELLS %s', frame, r))
  end
  if #runs == 0 and dropped > 0 then
    -- say nothing per-frame; terrain is the common case and drowns the log
  end

  tmwrites = {}
  tmcount = 0
end

-- Register defensively: the 4-argument form is rejected on some builds, so fall back
-- to the 2-argument form rather than failing silently.
local function watch(fn, kind, lo, hi)
  local ok = pcall(emu.addMemoryCallback, fn, kind, lo, hi, cpuT, memT)
  if not ok then ok = pcall(emu.addMemoryCallback, fn, kind, lo, hi) end
  return ok
end

watch(onBankWrite, emu.callbackType.write, 0x2000, 0x3FFF)
local okx = false
for addr, _ in pairs(SITES) do
  okx = watch(onExec, emu.callbackType.exec, addr, addr) or okx
end
local okt = watch(onTilemapWrite, emu.callbackType.write, 0x9800, 0x9FFF)

pcall(emu.addEventCallback, onFrame, emu.eventType.endFrame)

emu.log(string.format('armed: exec=%s tilemap=%s', tostring(okx), tostring(okt)))
emu.log('rendertrace v2 running -- walk every screen, then paste the log.')
emu.log('compose/struct = VWF-able.  fontload + tilemap = fixed-width path.')
