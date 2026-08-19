#!/usr/bin/env python3
"""Which copy loop reads which POINTER TABLE? Measured, then generalised per table.

WHY THIS EXISTS. The relocatable redirect replaces a string's bytes with a four-byte
record, and a reader that has not been taught the record draws two stray glyphs instead of
the line. So a string may only be redirected if every reader that can reach it is hooked --
and "which reader reads this string" is exactly the question this project has answered by
reading code and been wrong about twice (bank 11's menu labels turned out to be copied by
11:$52C6, a site no earlier list named; the box drawer was described as reading WRAM
because bc, not hl, holds its source).

WHY PER TABLE AND NOT PER STRING. A scripted walk sees a few dozen of the 860 relocatable
strings, so per-string attribution would redirect almost nothing. But a pointer TABLE is
indexed by one loop: observe any single entry of `11:$52E0` being read at `11:$52D5` and
the whole 37-entry table is attributed. There are 25 tables against 860 strings, so this
generalises from what a walk can actually reach to what the build needs to decide.

The generalisation is the one assumption here and it is stated rather than hidden: a table
is read by the loop that indexes it. What would break it is a table read by two different
loops, which is why the output reports EVERY site seen against a table, not just the first,
and why `build.py` requires all of them to be hooked rather than any.

    readers.py build/shiren_en.gb --seeds 8            # report
    readers.py build/shiren_en.gb --seeds 8 --write    # -> script/readers.tsv
"""
import argparse
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES   # noqa: E402

BANKSZ = 0x4000
OUT = 'script/readers.tsv'

# Every site that reads text bytes out of ROM, and the register holding the SOURCE at that
# address. Hooked one instruction INTO the loop, where the pointer is loaded and not yet
# advanced. `13:$40DB` is the composer; the rest are the `2A 12 13 FE FF 20` idiom and the
# two control-aware loops.
SITES = [
    (13, 0x40DB, 'composer 18-cell loop', 'hl'),
    (13, 0x6893, 'composer uncapped loop', 'hl'),
    (13, 0x6AE5, 'control-aware loop', 'hl'),
    # Table 13:$554A's three readers. They are here so the claim in script/build-inputs/reloc_ok.tsv --
    # that the first two are transparent to a record run and only the third needs a hook --
    # can be re-measured rather than re-argued. Note the renderer stops seeing redirected
    # reads once its hook is installed: the trampoline serves those, so a run against a
    # HOOKED build should show it reading plain strings only.
    (13, 0x7DBD, 'help queue-address walker', 'hl'),
    (13, 0x7E2F, 'help unit skip', 'hl'),
    (13, 0x7E51, 'help renderer', 'hl'),
    (11, 0x51F0, 'bank 11 table copy A', 'hl'),
    (11, 0x52D5, 'bank 11 menu label copy', 'hl'),
    (11, 0x52BC, 'bank 11 raw copy until $FF', 'hl'),
    (11, 0x7E63, 'bank 11 table copy B', 'hl'),
    (14, 0x7C1E, 'bank 14 table copy', 'hl'),
    (30, 0x7E8A, 'item verb staging', 'hl'),
    (4, 0x7458, 'bank 4 table copy', 'hl'),
    (31, 0x40E4, 'menu box row drawer', 'bc'),
]


def pointer_map(rom, strings):
    """-> {current cpu address in bank -> {table offsets that point at it}}.

    Read out of the BUILT rom, not out of script.json: `build.py` repoints every reference
    when it repacks a bank, so the address a table entry holds today is not the address the
    string was extracted from. Tables themselves do not move.
    """
    out = collections.defaultdict(set)
    for r in strings:
        for ref in r['refs']:
            at = ref['operand_at']
            ptr = rom[at] | rom[at + 1] << 8
            key = ref['table'] if ref['kind'] == 'table' else ref['operand_at']
            out[(r['bank'], ptr)].add((ref['kind'], key))
    return out


def _reg(pb, name):
    rf = pb.register_file
    if name == 'hl':
        return rf.HL
    hi, lo = name.upper()
    return (getattr(rf, hi) << 8) | getattr(rf, lo)


def trace(rom, frames, state, seed):
    """-> {(site bank, site addr): {(source bank, source addr)}}"""
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)

    seen = collections.defaultdict(set)

    def make(site):
        def cb(ctx):
            src = _reg(pb, site[3])
            if 0x4000 <= src < 0x8000:
                # The source lives in whatever bank the READER runs in: these loops are
                # all bank-local, which is the whole reason the redirect is needed.
                seen[(site[0], site[1])].add((site[0], src))
        return cb

    def starts(seen):
        """Drop the mid-string addresses.

        These hooks sit INSIDE the loop, so they fire once per byte and record $456F,
        $4570, $4571... An address whose predecessor was also seen at the same site is a
        continuation, not somewhere a reader was pointed at. Filtering here rather than
        moving the hooks keeps one hook point per loop -- several of them have no
        instruction before the loop that is not shared with another path.
        """
        return {site: {a for a in addrs if (a[0], a[1] - 1) not in addrs}
                for site, addrs in seen.items()}

    for site in SITES:
        try:
            pb.hook_register(site[0], site[1], make(site), None)
        except Exception:
            pass                      # a site may have been relocated by a build hook

    rng = random.Random(seed)
    for f in range(frames):
        if f >= 60 and (f - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ + ['a', 'b', 'start']), PRESS_FRAMES)
        pb.tick()
    pb.stop(save=False)
    return starts(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--frames', type=int, default=4000)
    ap.add_argument('--seeds', type=int, default=8)
    ap.add_argument('--script', default='script/script.json')
    ap.add_argument('--write', action='store_true', help='write ' + OUT)
    a = ap.parse_args()

    rom = open(a.rom, 'rb').read()
    strings = json.load(open(a.script, encoding='utf-8'))['strings']
    pmap = pointer_map(rom, strings)
    names = {(b, addr): name for b, addr, name, _ in SITES}

    # table key -> {site}, and the raw hits, so an unattributed read is visible too
    tables = collections.defaultdict(set)
    unmatched = collections.defaultdict(set)
    total = 0
    for state in ('saves/town.state', 'saves/dungeon.state'):
        if not os.path.exists(state):
            continue
        for seed in range(a.seeds):
            seen = trace(a.rom, a.frames, state, seed)
            for site, srcs in seen.items():
                total += len(srcs)
                for key in srcs:
                    if key in pmap:
                        for t in pmap[key]:
                            tables[t].add(site)
                    else:
                        unmatched[site].add(key)
            print('  %-22s seed %d: %d site(s), %d table(s) attributed'
                  % (os.path.basename(state), seed, len(seen), len(tables)), flush=True)

    print('\nTABLE -> READER (%d source addresses observed)' % total)
    rows = []
    for (kind, key), sites in sorted(tables.items(), key=lambda kv: str(kv[0])):
        where = ('%d:$%04X' % (key // BANKSZ, 0x4000 + key % BANKSZ)) if kind == 'table' \
            else '%d:$%04X' % (key // BANKSZ, 0x4000 + key % BANKSZ)
        for site in sorted(sites):
            rows.append((kind, where, '%d:$%04X' % site, names.get(site, '?')))
            print('   %-6s %-12s read by %-12s %s' % rows[-1])

    if unmatched:
        print('\nread but NOT a known reference target -- these are strings no table '
              'points at,\nor addresses this map does not model:')
        for site, srcs in sorted(unmatched.items()):
            shown = ' '.join('%d:$%04X' % s for s in sorted(srcs)[:6])
            print('   %-12s %-24s %d address(es): %s'
                  % ('%d:$%04X' % site, names.get(site, '?'), len(srcs), shown))

    if a.write:
        with open(OUT, 'w', encoding='utf-8') as f:
            f.write('# generated by tools/readers.py -- table -> the copy loop that '
                    'indexes it\n')
            f.write('kind\ttable\tsite\tname\n')
            for row in rows:
                f.write('%s\t%s\t%s\t%s\n' % row)
        print('\nwrote %s (%d rows)' % (OUT, len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
