#!/usr/bin/env python3
"""Measure whether one proportional-composer pass fits inside one frame of CPU time.

Runtime shifting trades ROM space for CPU work.  A passing screenshot does not prove the
work fits its scheduler slot, so this hooks the opt-in renderer's entry and final restore
and records both the outer PyBoy frame and LCD scanline.  A pass may legitimately begin
late in one frame and return early in the next; that is alignment, not a frame's worth of
CPU time.  Boundary crossings remain visible in the report, while the hard failure is an
actual duration of 154 scanlines or more, an unfinished call, or an orphaned return.

usage: proptiming.py build/shiren_en.gb [--frames 3000] [--seeds 4]
"""
import argparse
import collections
import os
import random
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import gbasm
import propvwf
import vwf
from gbrun import _import_pyboy, PRESS_FRAMES, WALK_SEQ


def labels(uniform=False):
    if uniform:
        scan_at = vwf.CODE_ORG
        pentab_at = scan_at + (vwf.SCANNER_END - vwf.SCANNER_AT) + 2
        pentab_end = pentab_at + len(vwf.pentable())
        _, found = gbasm.assemble(vwf._renderer_src(pentab_at, pentab_end, scan_at),
                                  pentab_end)
        return found
    render_at = (propvwf.SCAN_ORG +
                 (propvwf.SCANNER_END - propvwf.SCANNER_AT) + 2)
    _, found = gbasm.assemble(propvwf._renderer_src(propvwf.SCAN_ORG), render_at)
    return found


def run(rom, state, seed, frames, entry, done, map_entry=None, map_done=None):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as src:
        pb.load_state(src)
    rng = random.Random(seed)
    frame = {'n': 0}
    starts = []
    spans = []
    durations = []
    examples = []
    map_starts = []
    map_spans = []
    by_half = collections.defaultdict(list)
    per_frame = collections.Counter()

    def begin(_ctx):
        half = (pb.memory[0xCF06] >> 4) & 3
        staged = bytes(pb.memory[addr] for addr in range(0xCF07, 0xCF38))
        starts.append((frame['n'], pb.memory[0xFF44], half, staged))
        per_frame[frame['n']] += 1

    def finish(_ctx):
        if not starts:
            spans.append(('orphan', frame['n']))
            return
        begun, begun_ly, half, staged = starts.pop(0)
        span = frame['n'] - begun
        duration = span * 154 + pb.memory[0xFF44] - begun_ly
        spans.append(span)
        durations.append(duration)
        by_half[half].append(span)
        if span and len(examples) < 4:
            examples.append((half, duration, staged.hex()))

    def map_begin(_ctx):
        map_starts.append((frame['n'], pb.memory[0xFF44]))

    def map_finish(_ctx):
        if map_starts:
            begun, begun_ly = map_starts.pop(0)
            span = frame['n'] - begun
            map_spans.append((span, span * 154 + pb.memory[0xFF44] - begun_ly))
        else:
            map_spans.append('orphan')

    pb.hook_register(propvwf.FAR_BANK, entry, begin, None)
    pb.hook_register(propvwf.FAR_BANK, done, finish, None)
    if map_entry is not None:
        pb.hook_register(propvwf.FAR_BANK, map_entry, map_begin, None)
        pb.hook_register(propvwf.FAR_BANK, map_done, map_finish, None)
    for current in range(frames):
        frame['n'] = current
        if current >= 60 and (current - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        pb.tick()
    pb.stop(save=False)
    numeric = [span for span in spans if isinstance(span, int)]
    map_numeric = [value for value in map_spans if isinstance(value, tuple)]
    return {
        'calls': len(numeric),
        'crossing': sum(span != 0 for span in numeric),
        'max_span': max(numeric, default=0),
        'max_duration': max(durations, default=0),
        'over_budget': sum(duration >= 154 or duration < 0
                           for duration in durations),
        'max_per_frame': max(per_frame.values(), default=0),
        'unfinished': len(starts),
        'orphan': len(spans) - len(numeric),
        'by_half': {half: (len(values), sum(value != 0 for value in values))
                    for half, values in sorted(by_half.items())},
        'examples': examples,
        'map_calls': len(map_numeric),
        'map_crossing': sum(span != 0 for span, _duration in map_numeric),
        'map_max_span': max((span for span, _duration in map_numeric), default=0),
        'map_max_duration': max((duration for _span, duration in map_numeric), default=0),
        'map_over_budget': sum(duration >= 154 or duration < 0
                               for _span, duration in map_numeric),
        'map_unfinished': len(map_starts),
        'map_orphan': sum(not isinstance(span, tuple) for span in map_spans),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--states', default='saves/town.state,saves/dungeon.state')
    parser.add_argument('--frames', type=int, default=3000)
    parser.add_argument('--seeds', type=int, default=4)
    parser.add_argument('--uniform', action='store_true',
                        help='measure the installed uniform-6px renderer instead')
    args = parser.parse_args()
    found = labels(args.uniform)
    bad = 0
    for state in [path for path in args.states.split(',') if os.path.exists(path)]:
        for seed in range(args.seeds):
            result = run(args.rom, state, seed, args.frames,
                         found['entry'], found['done'],
                         None if args.uniform else found['buildmap'],
                         None if args.uniform else found['bmdone'])
            bad += (result['over_budget'] + result['unfinished'] + result['orphan']
                    + result['map_over_budget'] + result['map_unfinished']
                    + result['map_orphan'])
            print('  %-14s seed %d: %4d passes, %d crossed boundary, max %d/154 '
                  'scanlines, over budget %d, max/frame %d, unfinished %d, halves %s' %
                  (os.path.basename(state), seed, result['calls'], result['crossing'],
                   result['max_duration'], result['over_budget'],
                   result['max_per_frame'], result['unfinished'],
                   result['by_half']))
            if not args.uniform:
                print('    reveal maps: %d calls, %d crossed boundary, max %d/154 '
                      'scanlines, over budget %d, unfinished %d' %
                      (result['map_calls'], result['map_crossing'],
                       result['map_max_duration'], result['map_over_budget'],
                       result['map_unfinished']))
            for half, duration, staged in result['examples']:
                print('    crossed half %d (%d scanlines) staged CF07..CF37: %s' %
                      (half, duration, staged))
    if bad:
        print('FAIL: %d renderer pass(es) exceeded the one-frame execution budget or '
              'did not pair' % bad)
        return 1
    if args.uniform:
        print('OK: every 72px renderer pass used less than one frame of CPU time.')
    else:
        print('OK: every 72px renderer and second-pass reveal map used less than one '
              'frame of CPU time.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
