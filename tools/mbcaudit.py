#!/usr/bin/env python3
"""Candidate list of `ld [nnnn],a` writes into $3000-3FFF -- the MBC1->MBC5 hazard.

Linear-sweep disassembly using real opcode lengths, so an EA byte is only reported
when it is reached as an *instruction boundary* on a decode path. This is far tighter
than raw byte matching, but linear sweep still drifts through data, so the output is a
SHORT LIST TO VERIFY in Mesen -- not proof.

usage: mbcaudit.py <rom> [--skip-bank N ...]
"""
import sys, collections

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from regions import build_mask, excluded

L = [1] * 256
for op, n in {0x01: 3, 0x06: 2, 0x08: 3, 0x0E: 2, 0x10: 2, 0x11: 3, 0x16: 2, 0x18: 2,
              0x1E: 2, 0x20: 2, 0x21: 3, 0x26: 2, 0x28: 2, 0x2E: 2, 0x30: 2, 0x31: 3,
              0x36: 2, 0x38: 2, 0x3E: 2, 0xC2: 3, 0xC3: 3, 0xC4: 3, 0xC6: 2, 0xCA: 3,
              0xCB: 2, 0xCC: 3, 0xCD: 3, 0xCE: 2, 0xD2: 3, 0xD4: 3, 0xD6: 2, 0xDA: 3,
              0xDC: 3, 0xDE: 2, 0xE0: 2, 0xE6: 2, 0xE8: 2, 0xEA: 3, 0xEE: 2, 0xF0: 2,
              0xF6: 2, 0xF8: 2, 0xFA: 3, 0xFE: 2}.items():
    L[op] = n
INVALID = {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}

BANKSZ = 0x4000


def sweep(rom, start, end, mask):
    """Linear sweep; yields (offset, opcode) at instruction boundaries.
    Stops dead on entering a masked (non-code) range rather than drifting through it."""
    i = start
    while i < end:
        if mask[i]:
            i += 1
            continue
        op = rom[i]
        if op in INVALID:
            i += 1
            continue
        yield i, op
        i += L[op]


def main():
    rom = open(sys.argv[1], 'rb').read()
    skip = set()
    a = sys.argv[1:]
    while '--skip-bank' in a:
        k = a.index('--skip-bank')
        skip.add(int(a[k + 1]))
        del a[k:k + 2]

    mask = build_mask(rom)
    ex_bytes = sum(e - s for s, e in excluded(rom))
    print("Excluding %d bytes (%.0f%%) of graphics / font / script from the sweep.\n"
          % (ex_bytes, ex_bytes / len(rom) * 100))

    hits = collections.defaultdict(set)
    for bank in range(len(rom) // BANKSZ):
        if bank in skip:
            continue
        s, e = bank * BANKSZ, (bank + 1) * BANKSZ
        # sweep from several phases; only keep hits found from EVERY phase that
        # reaches them, which suppresses most data drift
        seen = []
        for phase in range(4):
            found = set()
            for off, op in sweep(rom, s + phase, e - 3, mask):
                if op == 0xEA:
                    tgt = rom[off + 1] | (rom[off + 2] << 8)
                    if 0x3000 <= tgt < 0x4000:
                        found.add((off, tgt))
            seen.append(found)
        consensus = set.intersection(*seen) if seen else set()
        for off, tgt in consensus:
            hits[bank].add((off, tgt))

    total = sum(len(v) for v in hits.values())
    print("Candidate `ld [$3xxx],a` sites (agreed by all 4 sweep phases):\n")
    for bank in sorted(hits):
        for off, tgt in sorted(hits[bank]):
            addr = off % BANKSZ + (0x4000 if bank else 0)
            print("  bank %2d:$%04X  (file 0x%06X)  ld [$%04X],a" % (bank, addr, off, tgt))
    print("\n%d candidate sites in %d banks." % (total, len(hits)))
    print("Verify in Mesen with a write breakpoint on $3000-$3FFF before trusting an")
    print("MBC5 conversion; sites that are really data will never trigger.")


main()
