#!/usr/bin/env python3
"""Relative search: find text by matching the *deltas* between character indices,
which are known from the font layout even though the absolute byte base is not.

usage: relsearch.py <rom> <word> [<word> ...]
"""
import sys, collections

# Character order read directly off the font at 0x37600 (tile index -> char).
ORDER = {}
ORDER[16] = ' '
for i, c in enumerate('0123456789'):
    ORDER[17 + i] = c
for i, c in enumerate('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'):
    ORDER[27 + i] = c
for i, c in enumerate('ぁぃぅぇぉゃゅょっ'):
    ORDER[73 + i] = c
for i, c in enumerate('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'):
    ORDER[82 + i] = c
for i, c in enumerate('ァィゥェォッャュョー'):
    ORDER[128 + i] = c

IDX = {c: i for i, c in ORDER.items()}


def search(rom, word):
    idx = [IDX[c] for c in word]
    deltas = [idx[i + 1] - idx[i] for i in range(len(idx) - 1)]
    hits = []
    n = len(rom)
    for p in range(n - len(word)):
        b0 = rom[p]
        ok = True
        for k, d in enumerate(deltas):
            if rom[p + k + 1] - rom[p + k] != d:
                ok = False
                break
        if ok:
            base = b0 - idx[0]          # implied code of tile index 0
            if -256 < base < 256:
                hits.append((p, base))
    return hits


def main():
    rom = open(sys.argv[1], 'rb').read()
    tally = collections.Counter()
    for word in sys.argv[2:]:
        hits = search(rom, word)
        print("%-10s %d hits" % (word, len(hits)))
        for p, base in hits[:12]:
            bank = p // 0x4000
            addr = p % 0x4000 + (0x4000 if bank else 0)
            print("   0x%06X  bank %2d:$%04X   implied base %+d  bytes %s"
                  % (p, bank, addr, base, rom[p:p + len(word)].hex(' ')))
        for p, base in hits:
            tally[base] += 1
        print()
    print("Implied-base tally across all words (most consistent base wins):")
    for base, c in tally.most_common(10):
        print("   base %+4d : %d hits   => code(space)=0x%02X code(あ)=0x%02X code(ア)=0x%02X"
              % (base, c, (16 + base) & 0xFF, (27 + base) & 0xFF, (82 + base) & 0xFF))


main()
