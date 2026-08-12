#!/usr/bin/env python3
"""Lift the opening cinematic's TEXT out, as readable lines with their addresses.

    introlines.py            -> `loc <TAB> japanese`, the seed for script/intro_draft.tsv

`introtext.py` shows the program with its opcodes; this shows only what a player reads.
Two things make it different from a naive byte dump, and both were wrong on the first try:

  * COMBINING MARKS PRECEDE THEIR KANA here (the main script's follow), so the mark has to
    be applied FORWARD. Rendered backwards `むら ゙ ひと` displays as むら゙ひと and a reviewer
    reads it as a typo rather than as むらびと.
  * `$4D` TAKES ONE ARGUMENT BYTE AND `$4E` TAKES TWO. Charge `$4E` one and its second
    argument is promoted into the text: `わたしのこが` becomes `わたおしのこが`, which is
    wrong and reads ALMOST right. Measured against the real screen, not inferred.

Every other opcode is charged zero arguments. That is enough to lift text out cleanly --
the whole program reads as fluent Japanese under it, which is the falsifier -- and NOT
enough to write bytes back. Measure the rest before inserting.
"""
import sys, os, unicodedata
ROOT='/Users/joey/Documents/Workplace/Shiren GB 1'
sys.path.insert(0, os.path.join(ROOT,'tools'))
import codec
rom=open(os.path.join(ROOT,'build/_base_expanded.gb'),'rb').read()
T=rom[13*0x4000+(0x7FAA-0x4000):][:0x4D]
ARITY={0x4D:1,0x4E:2,0x4F:1,0x50:1}
base=31*0x4000; lo,hi=0x5C63,0x5FA0
blob=rom[base+(lo-0x4000):base+(hi-0x4000)]
def render(idxs):
    out=[]; mark=''
    for x in idxs:
        c=T[x]
        if c in (0x79,0x7A):                 # the mark PRECEDES its kana here
            mark = '゙' if c==0x79 else '゚'
            continue
        ch = codec.decode(bytes([c])) if c else ' '
        out.append(unicodedata.normalize('NFC', ch+mark) if mark else ch)
        mark=''
    return ''.join(out)
out=[]; cur=[]; start=None; i=0
while i < len(blob):
    x=blob[i]
    if x<=0x4C:
        if start is None: start=lo+i
        cur.append(x); i+=1
    else:
        if cur:
            s=render(cur).strip()
            if len(s)>=3: out.append((start,s))
            cur=[]; start=None
        i += 1+ARITY.get(x,0)
if cur:
    s=render(cur).strip()
    if len(s)>=3: out.append((start,s))
for a,s in out: print('31:$%04X\t%s' % (a,s))
