#!/usr/bin/env python3
"""Sweep the WHOLE ROM for text in the CINEMATIC's alphabet. The check coverage.py cannot be.

    introsweep.py

WHY. `coverage.py` answers "is what we extracted all there is" by decoding through
`codec.py`. The opening cinematic uses a second character table (`13:$7FAA`), so it was
invisible to that check BY CONSTRUCTION -- not by a bad threshold. Joey asked the right
follow-up on 2026-08-06: if one encoding hid a whole cinematic, how do we know there is
not an ending in another one? This is the sweep that answers it in the alphabet we now
know about, and it is gated the same way coverage.py gates the main script -- a run only
counts as prose if it CARRIES PUNCTUATION (`！？「」・、。`), because raw kana density alone
matches acres of graphics data.

WHAT IT FOUND, 2026-08-06: 319 runs pass the gate and exactly six read as sentences, all
of them in bank 31 between `$5D37` and `$5EF3` -- the cinematic already known about.
Everything else is tile data that happens to decode. Paired with two other facts, that is
as close to "there is no second cinematic" as this project can currently get:

  * the scene-end opcode `<4D><C8>` occurs SEVEN times in the ROM and all seven are inside
    `31:$5C63`-`$5FA0`, so there is one program of this kind and not two;
  * `13:$7FAA` is the ROM's ONLY character table. Searching every `ld hl,nn / add hl,bc|de
    / ld a,[hl]` site gives 56 candidate lookups, and scoring each for the ascending run
    that a character inventory must contain leaves exactly one. `4:$79C4` is the nearest
    miss -- 32 entries, `and $1F`, five bits per character -- and its records come from
    RAM, so it decodes player data and not stored script.

**None of that proves a negative**, and the honest limit is worth stating: this finds text
in THIS alphabet. A third table would need this same treatment. What makes that unlikely
rather than unknown is the table search above, which is alphabet-independent.
"""
import sys, os
ROOT='/Users/joey/Documents/Workplace/Shiren GB 1'
sys.path.insert(0, os.path.join(ROOT,'tools'))
import codec
rom=open(os.path.join(ROOT,'build/_base_expanded.gb'),'rb').read()
T=rom[13*0x4000+(0x7FAA-0x4000):][:0x4D]
KANA=set(range(0x01,0x2F))                 # あ-ん + っゃょ
PUNCT={0x43,0x44,0x47,0x48,0x49,0x4A,0x4B} # ！？「」・、。 -- the gate
def dec(b): return ''.join((codec.decode(bytes([T[x]])) if T[x] else ' ') for x in b)
runs=[];i=0
while i < len(rom):
    j=i
    while j<len(rom) and rom[j]<=0x4C: j+=1
    n=j-i
    if n>=8:
        seg=rom[i:j]
        k=sum(1 for x in seg if x in KANA)
        if k/n>=0.50 and any(x in PUNCT for x in seg) and k>=6:
            runs.append((i,seg))
    i=max(j,i)+1
print('%d run(s) decode as CINEMATIC-ALPHABET prose and carry punctuation\n' % len(runs))
for o,s in runs:
    b=o//0x4000; a=o%0x4000+(0x4000 if b else 0)
    print('  %2d:$%04X  %3d  %s' % (b,a,len(s),dec(s)))
