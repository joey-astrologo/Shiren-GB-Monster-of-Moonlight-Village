#!/usr/bin/env python3
"""Decode the OPENING CINEMATIC, which is written in a third character encoding.

    introtext.py <rom> [start] [end]        default 5C63 5FA0, bank 31

WHY THIS FILE EXISTS. Joey booted the ROM on 2026-08-06, pressed nothing, and watched the
opening story play in Japanese -- with `coverage.py` reporting zero unextracted dialogue
and HANDOFF_NEXT.md saying the script was finished. Both were honest. The cinematic has
never been in `script.json` because it does not use `codec.py`'s character table.

THE TABLE IS AT `13:$7FAA`, 77 entries, intro byte -> font code. It is the game's whole
character inventory packed densely -- space, あ-ん contiguous, っゃょ, the 17 katakana the
game owns, ！？, the dakuten pair, 「」・、。 -- so `あ` is $01 here and $0B in `codec`.
Read through `codec` the text decodes as fluent-looking nonsense (`おさなごを` becomes
`ぇうくおを`), which scores WELL on every "is this text" heuristic the extractor has. It
was never rejected. It was never asked about.

COMBINING MARKS PRECEDE THE KANA HERE, the opposite of the main script: `むら ゙ ひと` is
むらびと and `コッ ゚ハ` is コッパ. The renderer draws the mark into the tilemap row ABOVE, so
a line occupies two rows. FINDINGS.md records the main script's rule; this is the other one.

Bytes over $4C are the VM's opcodes and are printed as `<XX>`.

TWO ARITIES ARE NOW MEASURED, and measured the only way that settles it -- by drawing the
line on the real screen and reconciling it against the bytes. `$4D` takes ONE argument
byte; `$4E` takes TWO. The mother's line is `「わた <4E> 00 05 しのこ ゙か ・・・」` and the
screen draws `「わたしのこが・・・」`, which only reconciles if `4E 00 05` is one opcode.
Charging `$4E` one argument instead silently promotes `お` into the text and yields
`わたおしのこが`, which is wrong and reads almost right -- the exact failure mode of
[[shiren-gb-arity-is-path-dependent]]. THE REST ARE STILL UNMEASURED. Every remaining
opcode is assumed to take none, which is enough to lift the text out cleanly but is NOT
enough to write bytes back. Measure them before inserting.

The FONT LOADER is `13:$7F69`: it walks the table with `cp $4D` (77 entries), blits each
glyph into VRAM in table order, and advances by $10 -- so a cinematic tilemap value is
just `$B0 + table index`, and `$4C` is the space.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import codec
rom=open(sys.argv[1],'rb').read()
T=rom[13*0x4000+(0x7FAA-0x4000):][:0x4C+1]
def dec(b):
    out=[]
    for x in b:
        if x <= 0x4C:
            c=T[x]
            out.append(codec.decode(bytes([c])) if c else ' ')
        else:
            out.append('<%02X>' % x)
    return ''.join(out)
base=31*0x4000
a0 = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x5C63
a1 = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x5FA0
blob=rom[base+(a0-0x4000):base+(a1-0x4000)]
# split on the run-separator opcodes to make it readable
line=[]; addr=a0
for i,x in enumerate(blob):
    line.append(x)
    if x==0xC8 or (len(line)>=64):
        print('31:$%04X %s' % (addr, dec(bytes(line))))
        addr=a0+i+1; line=[]
if line: print('31:$%04X %s' % (addr, dec(bytes(line))))
