#!/usr/bin/env python3
"""Prove that translation patches preserve every native enemy stat and EXP table.

Each of the three enemy tiers is stored as SEVEN 101-byte structure-of-arrays planes in
ROM bank 31.  The last three of each tier are the low, middle and high reward bytes (909
bytes / 303 rewards total); the first four carry the rest of the actor's constructed
stats.  Comparing only live SRAM is insufficient: floor actors are not serialized by
normal Quit saves, while a ROM collision corrupts every future actor constructed from
these tables.  This gate therefore compares the ROM against the expanded,
otherwise-unpatched Japanese control ROM.

Two checks, because they fail differently:

* the 303 rewards are reconstructed from their split planes and compared as VALUES, so a
  representation change cannot hide a semantic one -- tier-3 Mouse Don must award 40 EXP,
  the exact value the old ending-credit placement at 31:$7440 corrupted to 131,112;
* the COMPLETE never-allocate span from docs/ROM_BANK_MAP.md is compared byte for byte.

The span check was added on 2026-08-16 after reports of out-of-scale enemy damage.  The
reward gate covered 909 of the 2,175 declared bytes, so the twelve non-EXP stat planes --
exactly the ones that would change damage rather than experience -- had no gate at all.
They were clean, but nothing was enforcing it, and the credit placement that motivated
this file landed only a few hundred bytes away.
"""
import argparse
import hashlib
from pathlib import Path


BANK_SIZE = 0x4000
BANK = 31
COUNT = 101
# Bank 31:$6A74 selects these exact planes from runtime tier $D749 and species
# index $D74A before storing the 24-bit reward in $D753-$D755.
TIERS = (
    (0x6DC8, 0x6E2D, 0x6E92),
    (0x70A6, 0x710B, 0x7170),
    (0x7384, 0x73E9, 0x744E),
)
CONTROL_SHA256 = '43e5a11b009066ef422d3e7904dabd63b13d3a6c4cec098d4ea0179c810040c6'
MOUSE_DON_ID = 0x30
MOUSE_DON_EXP = 40

# The four planes preceding each tier's EXP triple. Listed so a failure can name the
# plane rather than only an offset; the span check below is what actually enforces them.
STAT_PLANES = (
    (0x6C34, 0x6C99, 0x6CFE, 0x6D63),
    (0x6F12, 0x6F77, 0x6FDC, 0x7041),
    (0x71F0, 0x7255, 0x72BA, 0x731F),
)
# docs/ROM_BANK_MAP.md, "Native banks: strict no-touch": the readers that construct an
# actor and the complete data they read. Inclusive, and deliberately wider than the
# planes above -- the declared rule is the authority, not the tables this file happens
# to enumerate.
NEVER_ALLOCATE = (
    (0x6980, 0x6AD9, 'native actor/stat readers'),
    (0x6ADA, 0x74B2, 'native actor/stat data, including every enemy tier'),
)


def rom_offset(address):
    return BANK * BANK_SIZE + address - 0x4000


def classify(cpu):
    """Name the plane and enemy index a bank-31 address falls in, for failure output."""
    for tier, planes in enumerate(STAT_PLANES):
        for index, base in enumerate(planes):
            if base <= cpu < base + COUNT:
                return ('tier %d stat plane %d, enemy $%02X'
                        % (tier + 1, index, cpu - base))
    for tier, planes in enumerate(TIERS):
        for index, base in enumerate(planes):
            if base <= cpu < base + COUNT:
                return ('tier %d EXP %s-byte, enemy $%02X'
                        % (tier + 1, 'lmh'[index], cpu - base))
    return 'outside the enumerated planes'


def table_bytes(rom):
    return b''.join(rom[rom_offset(address):rom_offset(address) + COUNT]
                    for tier in TIERS for address in tier)


def rewards(raw):
    result = []
    tier_bytes = COUNT * 3
    for tier in range(len(TIERS)):
        block = raw[tier * tier_bytes:(tier + 1) * tier_bytes]
        low = block[:COUNT]
        middle = block[COUNT:COUNT * 2]
        high = block[COUNT * 2:]
        result.append(tuple(low[index] | middle[index] << 8 | high[index] << 16
                            for index in range(COUNT)))
    return tuple(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('control', help='expanded, otherwise-unpatched Japanese ROM')
    parser.add_argument('candidate', help='translated ROM to verify')
    args = parser.parse_args()

    control_rom = Path(args.control).read_bytes()
    candidate_rom = Path(args.candidate).read_bytes()
    needed = rom_offset(TIERS[-1][-1]) + COUNT
    if len(control_rom) < needed or len(candidate_rom) < needed:
        raise SystemExit('enemyexp: ROM is too small for bank-31 EXP arrays')

    control = table_bytes(control_rom)
    candidate = table_bytes(candidate_rom)
    digest = hashlib.sha256(control).hexdigest()
    if digest != CONTROL_SHA256:
        raise SystemExit('enemyexp: control EXP tables changed: %s' % digest)

    expected = rewards(control)
    actual = rewards(candidate)
    if expected[2][MOUSE_DON_ID] != MOUSE_DON_EXP:
        raise SystemExit('enemyexp: control tier-3 Mouse Don reward is %d, expected %d' %
                         (expected[2][MOUSE_DON_ID], MOUSE_DON_EXP))

    changed = [(tier, index) for tier in range(len(TIERS))
               for index in range(COUNT)
               if expected[tier][index] != actual[tier][index]]
    if changed:
        total = len(TIERS) * COUNT
        print('enemyexp: FAIL: %d/%d enemy-tier rewards differ from native ROM' %
              (len(changed), total))
        for tier, index in changed[:16]:
            suffix = ' (Mouse Don)' if tier == 2 and index == MOUSE_DON_ID else ''
            before, after = expected[tier][index], actual[tier][index]
            print('  tier %d enemy $%02X%s: %d ($%06X) -> %d ($%06X)' %
                  (tier + 1, index, suffix, before, before, after, after))
        if len(changed) > 16:
            print('  ... and %d more' % (len(changed) - 16))
        raise SystemExit(1)

    if candidate != control:
        # Defensive: this should be implied by the reconstructed-value comparison, but
        # keep the raw layout invariant explicit in case the representation changes.
        raise SystemExit('enemyexp: EXP table bytes changed without value mismatch')

    # ---- the complete declared never-allocate span, not just the reward planes
    guarded = 0
    for low, high, label in NEVER_ALLOCATE:
        start, stop = rom_offset(low), rom_offset(high) + 1
        if len(candidate_rom) < stop:
            raise SystemExit('enemyexp: ROM is too small for 31:$%04X-$%04X' % (low, high))
        guarded += stop - start
        differing = [address for address in range(start, stop)
                     if control_rom[address] != candidate_rom[address]]
        if differing:
            print('enemyexp: FAIL: %d byte(s) differ inside 31:$%04X-$%04X (%s)'
                  % (len(differing), low, high, label))
            for address in differing[:16]:
                cpu = address - BANK * BANK_SIZE + 0x4000
                print('  31:$%04X  $%02X -> $%02X   %s'
                      % (cpu, control_rom[address], candidate_rom[address],
                         classify(cpu)))
            if len(differing) > 16:
                print('  ... and %d more' % (len(differing) - 16))
            raise SystemExit(1)

    print('enemyexp: PASS: all %d rewards across all %d enemy tiers match native ROM; '
          'tier-3 Mouse Don = %d EXP; %d never-allocate byte(s) byte-identical '
          '(%d stat planes + %d EXP planes)' %
          (len(TIERS) * COUNT, len(TIERS), actual[2][MOUSE_DON_ID], guarded,
           sum(len(planes) for planes in STAT_PLANES),
           sum(len(planes) for planes in TIERS)))


if __name__ == '__main__':
    main()
