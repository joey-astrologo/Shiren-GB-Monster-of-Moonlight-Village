#!/usr/bin/env python3
"""Trace proportional-composer work through the real VBlank tile-data upload.

``proptiming.py`` deliberately treats every renderer pass that crosses a PyBoy frame as
something to investigate.  Crossing alone does not say whether the queue was corrupted,
overwritten, or merely armed one VBlank later.  This probe follows each pass through:

    far renderer entry -> far renderer return -> queue destinations -> $C11A arm
        -> bank-0 $11A8/$11C5 VBlank consumer

The queue's three complete 66-byte records are fingerprinted when armed and immediately
before the consumer reads them.  A mismatch is a real race; an extra frame with an exact
fingerprint is latency.  Run the shipping renderer with ``--uniform`` to establish the
control schedule.

usage:
    python3 tools/propupload.py build/shiren_en.gb --frames 3000 --seeds 4
    python3 tools/propupload.py build/shiren_en.gb --uniform --frames 3000 --seeds 4
"""
import argparse
import collections
import os
import random
import sys
import zlib

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import propvwf
import proptiming
from gbrun import _import_pyboy, PRESS_FRAMES, WALK_SEQ


QUEUE_START = 0xC006
QUEUE_END = 0xC0CC                  # three complete 66-byte tile-data records
DESTINATIONS_READY = (13, 0x4411)  # after $C006/$C048/$C08A are written
UPLOAD_START = (0, 0x11A8)         # C11A=$0A dispatcher target
TILE_CONSUMER = (0, 0x11C5)

# Every measured caller arms the same tile-data consumer after $43B8 returns.  Hook after
# each store, so memory already contains $0A when the callback fingerprints the queue.
ARMED = ((13, 0x4367), (13, 0x5254), (13, 0x6AAF))
CALLERS = ((13, 0x4328), (13, 0x433A), (13, 0x524B),
           (13, 0x6A97), (13, 0x6AA3))


def _queue(pb):
    return bytes(pb.memory[addr] for addr in range(QUEUE_START, QUEUE_END))


def _fingerprint(pb):
    data = _queue(pb)
    return zlib.crc32(data) & 0xFFFFFFFF


def _dests(pb):
    return tuple(pb.memory[addr] | (pb.memory[addr + 1] << 8)
                 for addr in (0xC006, 0xC048, 0xC08A))


def run(rom, state, seed, frames, entry, done):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as src:
        pb.load_state(src)
    rng = random.Random(seed)
    outer = {'frame': 0}
    records = []
    active = []
    ready = []
    armed = []
    caller = {'at': None}
    stray_uploads = 0
    tile_starts = 0

    def stamp():
        return (outer['frame'], pb.memory[0xFF44], pb.memory[0xFF04])

    def at_caller(addr):
        caller['at'] = addr

    def begin(_ctx):
        rec = {
            'caller': caller['at'],
            'half': (pb.memory[0xCF06] >> 4) & 3,
            'begin': stamp(),
        }
        caller['at'] = None
        records.append(rec)
        active.append(rec)

    def finish(_ctx):
        if not active:
            records.append({'orphan_done': stamp()})
            return
        rec = active.pop(0)
        rec['done'] = stamp()
        ready.append(rec)

    def destinations(_ctx):
        if not ready:
            return
        rec = ready[-1]
        rec['destinations'] = stamp()
        rec['dests'] = _dests(pb)

    def arm(_ctx):
        if not ready:
            return
        rec = ready.pop(0)
        rec['arm'] = stamp()
        rec['armed_c11a'] = pb.memory[0xC11A]
        rec['armed_crc'] = _fingerprint(pb)
        rec['armed_dests'] = _dests(pb)
        armed.append(rec)

    def upload(_ctx):
        nonlocal stray_uploads
        if not armed:
            stray_uploads += 1
            return
        rec = armed.pop(0)
        rec['upload'] = stamp()
        rec['upload_crc'] = _fingerprint(pb)
        rec['upload_dests'] = _dests(pb)
        rec['upload_c11a'] = pb.memory[0xC11A]

    def tile_start(_ctx):
        nonlocal tile_starts
        tile_starts += 1

    for _, addr in CALLERS:
        pb.hook_register(13, addr, lambda _ctx, a=addr: at_caller(a), None)
    pb.hook_register(propvwf.FAR_BANK, entry, begin, None)
    pb.hook_register(propvwf.FAR_BANK, done, finish, None)
    pb.hook_register(*DESTINATIONS_READY, destinations, None)
    for bank, addr in ARMED:
        pb.hook_register(bank, addr, arm, None)
    pb.hook_register(*UPLOAD_START, upload, None)
    pb.hook_register(*TILE_CONSUMER, tile_start, None)

    for current in range(frames):
        outer['frame'] = current
        if current >= 60 and (current - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        pb.tick()
    pb.stop(save=False)

    complete = [rec for rec in records if 'upload' in rec]
    corrupt = [rec for rec in complete
               if rec['armed_crc'] != rec['upload_crc']
               or rec['armed_dests'] != rec['upload_dests']]
    bad_c11a = [rec for rec in complete
                if rec['armed_c11a'] != 0x0A or rec['upload_c11a'] != 0x0A]
    render_delays = collections.Counter(
        rec['done'][0] - rec['begin'][0] for rec in complete)
    upload_delays = collections.Counter(
        rec['upload'][0] - rec['arm'][0] for rec in complete)
    total_delays = collections.Counter(
        rec['upload'][0] - rec['begin'][0] for rec in complete)
    by_half = {}
    for half in sorted(set(rec['half'] for rec in complete)):
        subset = [rec for rec in complete if rec['half'] == half]
        by_half[half] = {
            'calls': len(subset),
            'render': dict(sorted(collections.Counter(
                rec['done'][0] - rec['begin'][0] for rec in subset).items())),
            'arm_upload': dict(sorted(collections.Counter(
                rec['upload'][0] - rec['arm'][0] for rec in subset).items())),
            'begin_upload': dict(sorted(collections.Counter(
                rec['upload'][0] - rec['begin'][0] for rec in subset).items())),
        }
    return {
        'records': len(records),
        'complete': len(complete),
        'corrupt': len(corrupt),
        'bad_c11a': len(bad_c11a),
        'unfinished_render': len(active),
        'unarmed': len(ready),
        'unuploaded': len(armed),
        'stray_uploads': stray_uploads,
        'tile_starts': tile_starts,
        'render_delays': dict(sorted(render_delays.items())),
        'upload_delays': dict(sorted(upload_delays.items())),
        'total_delays': dict(sorted(total_delays.items())),
        'by_half': by_half,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--states', default='saves/town.state,saves/dungeon.state')
    parser.add_argument('--frames', type=int, default=3000)
    parser.add_argument('--seeds', type=int, default=4)
    parser.add_argument('--uniform', action='store_true')
    args = parser.parse_args()
    found = proptiming.labels(args.uniform)
    hard_failures = 0
    for state in [path for path in args.states.split(',') if os.path.exists(path)]:
        for seed in range(args.seeds):
            result = run(args.rom, state, seed, args.frames,
                         found['entry'], found['done'])
            # One record may remain armed at the exact frame cutoff; payload corruption,
            # a wrong dispatcher value, or a pass that never reached its arm are failures.
            hard_failures += (result['corrupt'] + result['bad_c11a']
                              + result['unfinished_render'] + result['unarmed'])
            print('  %-14s seed %d: %d/%d uploaded; corrupt %d; '
                  'render %s; arm->upload %s; begin->upload %s; halves %s' %
                  (os.path.basename(state), seed, result['complete'], result['records'],
                   result['corrupt'], result['render_delays'], result['upload_delays'],
                   result['total_delays'], result['by_half']))
            if result['stray_uploads'] or result['tile_starts'] != result['complete']:
                print('    context: %d stray upload(s), %d tile-consumer start(s), '
                      '%d still armed at cutoff' %
                      (result['stray_uploads'], result['tile_starts'],
                       result['unuploaded']))
    if hard_failures:
        print('FAIL: %d queue-integrity/scheduling failure(s)' % hard_failures)
        return 1
    print('OK: every completed composer queue reached the VBlank consumer byte-exact.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
