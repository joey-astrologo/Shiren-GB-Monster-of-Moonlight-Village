#!/usr/bin/env python3
"""Every byte build.py rewrites outside a text arena, and whether it is explained.

    logicdiff.py build/shiren_en.gb build/_base_expanded.gb

THE HOLE THIS CLOSES, and it is the widest one this project has had. On 2026-08-04 THREE
separate false pointer tables were rewriting game DATA on every build:

    10:$46B0, 10:$46C6   25 bytes of the numeric item stats. An equipped Hyakki Shield
                         read `Shield 0` where the Japanese ROM reads 9, and unequipping
                         it ran POT code -- a pot animation and "A Pot can't go in a Pot."
    9:$6FCD              10 bytes of bank 9, and it kept `11:$5848` in the script, a
                         nested "string" that would have failed BADREF in the prose session

None of it was visible to anything else. `--shuffle`, 12 crash seeds, 1116 verified
references and a green build were all clean throughout, because corrupting a stat table
crashes nothing, moves no string and breaks no reference. **The reference verification
proves a STRING is reachable. It cannot prove the site was ever a pointer.** Joey found
both by playing, and the second only because he checked the Japanese ROM side by side.

WHAT COUNTS AS EXPLAINED. A rewritten byte outside a text arena must be one of:

  * a message-queue push -- `ld bc,nn` whose `call $028B` follows, directly or through the
    `jr` chain extract.py counts (233 direct, 9 chained)
  * a byte inside a string this ROM still lists, or a reference operand pointing at one
  * a declared patch: script/tile_patches.tsv (the fullness strip at 2:$7D42), the code
    patchers name6, rank6, vwf and itemfix, which own known address ranges, the Fay's
    Puzzles header row build.py mirrors into bank 4 (see build.QUIZ_ROW_AT), the status
    Path padding table build.py patches in bank 4 (see build.PATH_PADDING_AT), and the
    three-byte title-card decompression hook at 9:$4115

Anything else is a pointer that was never a pointer. **Banks 7, 8, 9, 10 and 12 hold no
script at all, so their unexplained count must be ZERO** -- that is the check with no
judgement in it, and it is the one that would have caught all three.
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANKSZ = 0x4000

# Banks with no script in them. extract.TEXT_BANKS is (3, 4, 6, 11, 13, 14, 30, 31); these
# are the game-logic banks that are left, minus bank 0 and the patcher-owned high banks.
PURE_LOGIC = (7, 8, 9, 10, 12)


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/shiren_en.gb')
    b = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build/_base_expanded.gb')
    new, old = open(a, 'rb').read(), open(b, 'rb').read()
    strings = json.load(open(os.path.join(ROOT, 'script/script.json'),
                             encoding='utf-8'))['strings']

    known = set()
    for r in strings:
        known.update(range(r['offset'], r['offset'] + r['bytes'] + 1))
        for x in r['refs']:
            op = x.get('operand_at')
            if op is not None:
                known.update((op, op + 1))

    def is_push(i):
        """`ld bc,nn` at i-1 or i-2, reaching `call $028B` directly or over a `jr`."""
        for start in (i - 1, i - 2):
            if start < 0 or old[start] != 0x01:
                continue
            if old[start + 3:start + 6] == b'\xCD\x8B\x02':
                return True
            if old[start + 3] == 0x18 and old[start + 5:start + 8] == b'\xCD\x8B\x02':
                return True
        return False

    # build.py mirrors box 30's translated header into a PRE-RENDERED TILEMAP ROW in
    # bank 4, because the quiz redraws its header from there rather than from the box.
    # Declared here so it does not swell bank 4's "unexplained" column -- an explained
    # write that reads as unexplained is how this check loses its meaning.
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import build as B                                                   # noqa: E402
    known.update(range(B.QUIZ_ROW_AT, B.QUIZ_ROW_AT + B.QUIZ_ROW_CELLS))
    known.update(range(B.PATH_PADDING_AT,
                       B.PATH_PADDING_AT + len(B.PATH_PADDING_NEW)))

    # The English copyright/title card replaces exactly one three-byte call in bank 9.
    # Keep bank 9 under zero-tolerance scrutiny while exempting only that declared hook;
    # titlecardspill separately verifies its old bytes, new far call and full raster.
    titlecard_hook = 9 * BANKSZ + (0x4115 - 0x4000)
    known.update(range(titlecard_hook, titlecard_hook + 3))

    counts, unexplained = collections.Counter(), collections.defaultdict(list)
    for i in range(min(len(old), len(new))):
        if old[i] == new[i]:
            continue
        bank = i // BANKSZ
        counts[bank] += 1
        if i not in known and not is_push(i):
            unexplained[bank].append(i)

    bad = 0
    print('bank | rewritten | unexplained')
    for bank in sorted(counts):
        u = unexplained.get(bank, [])
        tag = ''
        if bank in PURE_LOGIC:
            tag = '  <-- NO SCRIPT; UNEXPLAINED MUST BE ZERO'
            bad += len(u)
        print('  %2d |    %6d | %6d%s' % (bank, counts[bank], len(u), tag))
        if bank in PURE_LOGIC and u:
            for i in u[:8]:
                print('        %d:$%04X  %02X -> %02X'
                      % (bank, i % BANKSZ + 0x4000, old[i], new[i]))
    print()
    if bad:
        print('FAIL: %d unexplained byte(s) rewritten in a bank that holds no script. '
              'Something is being '
              'treated as a pointer that is not one -- suspect the reference list, not the '
              'bank. See tools/extract.py MIN_DISTINCT and FALSE_TABLES.' % bad)
        return 1
    print('OK: banks %s have zero unexplained rewrites.'
          % ', '.join(str(b) for b in PURE_LOGIC))
    print('Note: banks 2, 5, 6 legitimately carry message-queue pushes and the fullness tile '
          'patch; their "unexplained" column counts what this script cannot model, not '
          'necessarily damage. The zero-tolerance claim is the PURE_LOGIC banks only.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
