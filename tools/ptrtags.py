#!/usr/bin/env python3
"""Census of the dialogue resume pointer at 13:$7589 -- which tag bits are actually used.

`13:$7589` is the ONE gate every in-place dialogue line goes through. It loads the stored
pointer from $CF7F/$CF80 into hl and dispatches on `bit 7,h`: clear -> bank 11's stager,
set -> bank 14's. That leaves bit 6 apparently unused, and the whole redirect plan rests
on "apparently".

This hooks 13:$7593 -- the `bit 7,h`, where hl is loaded and not yet fixed up -- and
records every distinct pointer the game really produces, across both save states and a
sweep of seeded walks. A single run proves nothing (see the crash that only two of twelve
seeds reached), so the default is a sweep.

    ptrtags.py build/shiren_en.gb --seeds 12

Output is the census by (bit7, bit6) tag. Bit 6 must be 0 in EVERY observation for the
pool tags $40-$7F and $C0-$FF to be safe to claim.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES   # noqa: E402

GATE = (13, 0x7593)          # `bit 7,h`: hl = the stored pointer, before any fixup


def rom_has_pool(path):
    """True if tools/pool.py has been installed -- bank 33 carries its own bank id."""
    with open(path, 'rb') as f:
        f.seek(0x21 * 0x4000)
        return f.read(1) == b'\x21'


def census(rom, frames, state=None, seed=None):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)
    seen = collections.Counter()

    def cb(ctx):
        seen[pb.register_file.HL] += 1

    pb.hook_register(GATE[0], GATE[1], cb, None)
    rng = __import__('random').Random(seed) if seed is not None else None
    for f in range(frames):
        if rng is not None and f >= 60 and (f - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        pb.tick()
    pb.stop(save=False)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--frames', type=int, default=3000)
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--states', default='saves/town.state,saves/dungeon.state')
    a = ap.parse_args()

    total = collections.Counter()
    for st in [s for s in a.states.split(',') if s and os.path.exists(s)]:
        for seed in range(a.seeds):
            total += census(a.rom, a.frames, state=st, seed=seed)
            print('  %-22s seed %2d -> %4d distinct so far'
                  % (os.path.basename(st), seed, len(total)))

    by_tag = collections.Counter()
    for ptr, n in total.items():
        by_tag[(ptr >> 15) & 1, (ptr >> 14) & 1] += n
    print('\n%d distinct pointers, %d observations' % (len(total), sum(total.values())))
    print('tag (bit15,bit14)   meaning              observations')
    names = {(0, 0): 'bank 11 (set 6,h)', (1, 0): 'bank 14 (xor $C0)',
             (0, 1): 'FREE -> pool A', (1, 1): 'FREE -> pool B'}
    for tag in ((0, 0), (1, 0), (0, 1), (1, 1)):
        print('   %d,%d              %-20s %d' % (tag[0], tag[1], names[tag], by_tag[tag]))
    # Run this on a rom that ALREADY has the pool installed and bit 14 is set all over the
    # place -- by tools/pool.py, on purpose. That is the mechanism working, not a finding.
    # The question this tool answers is only meaningful about a rom without the redirect.
    pooled = rom_has_pool(a.rom)
    bad = [p for p in total if (p >> 14) & 1]
    print('\nbit 14 set in %d of %d distinct pointers' % (len(bad), len(total)))
    if bad and pooled:
        print('  ...and this rom HAS the pool installed, so those are its own redirect')
        print('  pointers. Re-run against a build without tools/pool.py to test the claim.')
        return 0
    if bad:
        print('  NOT SAFE. examples:', ' '.join('$%04X' % p for p in sorted(bad)[:16]))
    lo = sorted(p & 0xFF for p in total)
    print('low bytes seen $%02X-$%02X' % (lo[0], lo[-1]) if lo else 'no observations')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
