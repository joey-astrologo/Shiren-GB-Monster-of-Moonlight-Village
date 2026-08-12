-- mesen_strread.lua  (v3 -- watches the DATA, not the code)
--
-- HOW TO RUN: Debug > Script Window > open this file > Run (F5).
-- Use the ORIGINAL Japanese ROM (build/base.gb).
--
-- WHY v3 IS DIFFERENT. v1 hooked $028B; v2 hooked all seven message entry points at
-- $028B-$031B. Both caught dungeon and combat text and NOTHING in town, because both
-- guessed WHERE the code lives. This one makes no such guess: it watches the string
-- BYTES. The game cannot display a line without reading it, so a read breakpoint on
-- the first byte of each unaccounted string is guaranteed to catch the reader.
--
-- The table below is every CPU address at which one of the ~289 unaccounted
-- village/story strings begins. When any of them is READ, we log the program counter.
-- That PC is the routine we have been unable to find statically.
--
-- Addresses are ambiguous across banks (bank 11 and 14 share the $4000-$7FFF window),
-- so the bank recorded is a best guess. Resolution happens offline against script.json.

local WATCH = {
  [0x459A]=13,
  [0x45DF]=13,
  [0x45F3]=13,
  [0x4604]=13,
  [0x462D]=13,
  [0x46F1]=13,
  [0x4A80]=13,
  [0x4C0F]=14,
  [0x4C15]=13,
  [0x4C7B]=14,
  [0x4C85]=13,
  [0x4C91]=13,
  [0x4D07]=14,
  [0x4D19]=14,
  [0x4D3F]=13,
  [0x4E84]=13,
  [0x4EA4]=13,
  [0x4EB6]=13,
  [0x4EF2]=13,
  [0x4F40]=13,
  [0x4F4C]=14,
  [0x4F62]=13,
  [0x4F8F]=14,
  [0x4FB9]=14,
  [0x5037]=14,
  [0x5047]=14,
  [0x5106]=14,
  [0x5127]=14,
  [0x5146]=14,
  [0x51D3]=14,
  [0x51D8]=13,
  [0x51DE]=14,
  [0x5213]=14,
  [0x5220]=14,
  [0x525F]=14,
  [0x5281]=14,
  [0x529F]=14,
  [0x52C7]=14,
  [0x535C]=14,
  [0x537F]=14,
  [0x538C]=14,
  [0x53D3]=14,
  [0x53FB]=14,
  [0x541F]=14,
  [0x5459]=11,
  [0x5488]=14,
  [0x549F]=14,
  [0x54D4]=14,
  [0x54E1]=14,
  [0x551D]=14,
  [0x5562]=14,
  [0x5596]=14,
  [0x55D8]=14,
  [0x5611]=14,
  [0x5636]=14,
  [0x566D]=14,
  [0x56B2]=14,
  [0x56DB]=11,
  [0x56EF]=14,
  [0x571F]=11,
  [0x572A]=14,
  [0x5741]=11,
  [0x574D]=11,
  [0x574F]=14,
  [0x5770]=11,
  [0x57E7]=14,
  [0x57F6]=11,
  [0x5840]=14,
  [0x5875]=14,
  [0x58B7]=11,
  [0x58CC]=14,
  [0x58E5]=11,
  [0x58F6]=14,
  [0x58F8]=11,
  [0x5902]=14,
  [0x5924]=14,
  [0x5940]=11,
  [0x598A]=14,
  [0x5996]=14,
  [0x59A3]=11,
  [0x59E2]=14,
  [0x5A22]=11,
  [0x5A50]=11,
  [0x5A59]=14,
  [0x5A74]=11,
  [0x5AB1]=14,
  [0x5AD1]=11,
  [0x5AE6]=11,
  [0x5B87]=11,
  [0x5B89]=14,
  [0x5B9B]=14,
  [0x5BB2]=14,
  [0x5BC2]=14,
  [0x5BD1]=11,
  [0x5BD6]=14,
  [0x5BE1]=14,
  [0x5C1B]=14,
  [0x5C5A]=14,
  [0x5C73]=14,
  [0x5E92]=14,
  [0x5EB3]=14,
  [0x5ECC]=14,
  [0x60E5]=14,
  [0x6107]=14,
  [0x6127]=14,
  [0x615B]=14,
  [0x61BD]=14,
  [0x61F4]=14,
  [0x6256]=14,
  [0x6275]=11,
  [0x628A]=11,
  [0x6291]=14,
  [0x629E]=11,
  [0x62B0]=11,
  [0x62B6]=14,
  [0x62C3]=11,
  [0x62C6]=14,
  [0x62D5]=11,
  [0x62F8]=14,
  [0x6317]=14,
  [0x632D]=11,
  [0x6338]=14,
  [0x6340]=11,
  [0x6359]=11,
  [0x6386]=14,
  [0x6391]=11,
  [0x639F]=11,
  [0x63C7]=11,
  [0x63ED]=11,
  [0x6404]=14,
  [0x6415]=11,
  [0x6421]=11,
  [0x6431]=11,
  [0x643E]=14,
  [0x6461]=14,
  [0x6465]=11,
  [0x6473]=11,
  [0x649A]=11,
  [0x64A7]=14,
  [0x64EE]=11,
  [0x6510]=14,
  [0x6547]=11,
  [0x6548]=14,
  [0x6564]=14,
  [0x6580]=14,
  [0x65B9]=14,
  [0x65C4]=14,
  [0x65D0]=14,
  [0x65DD]=14,
  [0x661D]=14,
  [0x662C]=11,
  [0x6638]=14,
  [0x6656]=14,
  [0x6678]=14,
  [0x66A7]=11,
  [0x66AC]=14,
  [0x66BA]=11,
  [0x66DD]=14,
  [0x66F1]=11,
  [0x6713]=11,
  [0x671F]=14,
  [0x6745]=11,
  [0x6754]=14,
  [0x6765]=14,
  [0x678D]=14,
  [0x67A8]=11,
  [0x67E0]=14,
  [0x67EB]=14,
  [0x6826]=11,
  [0x6856]=11,
  [0x6875]=11,
  [0x688A]=14,
  [0x689B]=11,
  [0x68C6]=14,
  [0x690F]=11,
  [0x6920]=14,
  [0x6921]=11,
  [0x692B]=11,
  [0x693C]=11,
  [0x6950]=14,
  [0x695A]=11,
  [0x695B]=14,
  [0x6963]=11,
  [0x69AC]=11,
  [0x69BA]=11,
  [0x69D8]=11,
  [0x6A42]=11,
  [0x6A81]=11,
  [0x6A97]=11,
  [0x6B04]=11,
  [0x6B3B]=11,
  [0x6B69]=11,
  [0x6B77]=11,
  [0x6BB2]=11,
  [0x6BDF]=11,
  [0x6C04]=11,
  [0x6C15]=11,
  [0x6CBE]=11,
  [0x6CE4]=11,
  [0x6D05]=11,
  [0x6D2B]=11,
  [0x6DF5]=11,
  [0x6E00]=11,
  [0x6E2E]=11,
  [0x6E42]=11,
  [0x6E58]=11,
  [0x6E64]=11,
  [0x6E94]=11,
  [0x6EB9]=11,
  [0x6F44]=11,
  [0x6F8B]=11,
  [0x6FC6]=11,
  [0x6FE5]=11,
  [0x703D]=11,
  [0x7072]=11,
  [0x709C]=11,
  [0x7151]=11,
  [0x717E]=11,
  [0x71DE]=11,
  [0x7216]=11,
  [0x7257]=11,
  [0x7264]=11,
  [0x7280]=11,
  [0x72CE]=11,
  [0x730D]=11,
  [0x732C]=11,
  [0x7360]=11,
  [0x737F]=11,
  [0x738E]=11,
  [0x73B0]=11,
  [0x73C1]=11,
  [0x73E5]=11,
  [0x741D]=11,
  [0x7493]=11,
  [0x7535]=11,
  [0x755F]=11,
  [0x7575]=11,
  [0x7581]=11,
  [0x75B3]=11,
  [0x75E1]=11,
  [0x761C]=11,
  [0x7639]=11,
  [0x7648]=11,
  [0x7682]=11,
  [0x76A4]=11,
  [0x77A6]=11,
  [0x7803]=11,
  [0x785F]=11,
  [0x78F6]=11,
  [0x7941]=14,
  [0x7964]=11,
  [0x796C]=14,
  [0x7998]=11,
  [0x79A9]=14,
  [0x79CC]=11,
  [0x79EA]=11,
  [0x79F8]=14,
  [0x7A1E]=14,
  [0x7A31]=11,
  [0x7A52]=11,
  [0x7A5F]=14,
  [0x7A75]=14,
  [0x7A94]=14,
  [0x7ABC]=14,
  [0x7AD7]=14,
  [0x7AE2]=11,
  [0x7B16]=11,
  [0x7B2B]=14,
  [0x7B3C]=11,
  [0x7B58]=11,
  [0x7B5C]=14,
  [0x7B7C]=14,
  [0x7B7F]=11,
  [0x7BA1]=14,
  [0x7BB5]=11,
  [0x7BC2]=14,
  [0x7BF2]=14,
  [0x7C03]=14,
  [0x7C36]=11,
  [0x7D0A]=11,
  [0x7D50]=11,
  [0x7D79]=11,
  [0x7E98]=14,
  [0x7EA0]=14,
  [0x7EB5]=14,
  [0x7EE6]=14,
}

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

local LO, HI = 0x4590, 0x7EF0
local curBank = 1
local seen, rows = {}, {}
local hits, uniq = 0, 0

local function onBankWrite(address, value)
  if address >= 0x2000 and address < 0x4000 then curBank = value end
end

local rejected = 0

local function onRead(address, value)
  if WATCH[address] == nil then return end        -- only string-start bytes
  -- CPU addresses are bank-ambiguous: $4000-$7FFF shows whichever bank is mapped.
  -- v3 printed a STATIC guess, so font-tile and tilemap reads at the same CPU address
  -- looked like dialogue reads. Only keep reads where the live bank matches.
  if curBank ~= WATCH[address] then
    rejected = rejected + 1
    return
  end
  local ok, st = pcall(emu.getState)
  if not ok or st == nil then return end
  local pc = st["cpu.pc"] or 0
  hits = hits + 1
  local key = string.format("%04X:%04X", pc, address)
  if seen[key] then return end
  seen[key] = true
  uniq = uniq + 1
  local pbank = (pc < 0x4000) and 0 or curBank
  local row = string.format("  READER pc b%-2d $%04X   read b%d:$%04X   (bank CONFIRMED)",
                            pbank, pc, curBank, address)
  rows[#rows + 1] = row
  emu.log("NEW " .. row)
end

local function summary()
  emu.log("")
  emu.log("=========== STRING READ TRACE SUMMARY ===========")
  emu.log(string.format("confirmed reads: %d   distinct (pc,addr): %d   rejected (wrong bank): %d",
                        hits, uniq, rejected))
  emu.log("")
  for _, r in ipairs(rows) do emu.log(r) end
  emu.log("")
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
  ok2 = pcall(emu.addMemoryCallback, onRead, emu.callbackType.read, LO, HI, cpuT, memT)
end
if not ok2 then
  ok2 = pcall(emu.addMemoryCallback, onRead, emu.callbackType.read, LO, HI)
end
if not ok2 then
  emu.log("FAILED to register the read watch")
else
  emu.log(string.format("armed: read watch $%04X-$%04X, filtered to %d string starts",
                        LO, HI, 286))
end

local frames = 0
pcall(emu.addEventCallback, function()
  frames = frames + 1
  if frames % 1800 == 0 and uniq > 0 then summary() end
end, emu.eventType.endFrame)

emu.log("v4: only logs reads where the LIVE bank matches. Talk to town NPCs.")
