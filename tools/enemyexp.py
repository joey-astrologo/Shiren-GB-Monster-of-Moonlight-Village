#!/usr/bin/env python3
"""Prove that translation patches preserve every native enemy EXP table.

Each of the three enemy tiers is stored as three 101-byte structure-of-arrays fields
in ROM bank 31 (low, middle and high reward bytes: 909 bytes / 303 rewards total).
Comparing only live SRAM is insufficient: floor actors are not serialized by normal
Quit saves, while a ROM collision corrupts every future actor constructed from this
table.  This gate therefore compares the complete ROM table against the expanded,
otherwise-unpatched Japanese control ROM.
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


def rom_offset(address):
    return BANK * BANK_SIZE + address - 0x4000


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

    print('enemyexp: PASS: all %d rewards across all %d enemy tiers match native ROM; '
          'tier-3 Mouse Don = %d EXP' %
          (len(TIERS) * COUNT, len(TIERS), actual[2][MOUSE_DON_ID]))


if __name__ == '__main__':
    main()
