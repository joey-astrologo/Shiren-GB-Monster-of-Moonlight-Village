#!/usr/bin/env python3
"""Photograph the help/tutorial screen, which no walk seed reaches, and snapshot what the
renderer put in its buffer.

Bank 4's menu dispatcher (4:$48AA, index in `a`, 35-entry table at $48C3) has the help
renderer's caller at index 4 -- `4:$49A7`, the routine that zeroes 120 bytes at $C616 and
far-calls 13:$7E49. Forcing the index makes the REAL routine draw through the REAL
renderer; only the navigation is synthetic. $CF7A picks the topic, $CF7B bit 7 selects
table $554A over the $5537 fallback, $C6BC picks the unit within the topic.

The buffer is read at `4:$49BF`, the instruction the far call returns to, because the
inventory redraws over $C616 within a few frames otherwise.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gbrun import _import_pyboy                                     # noqa: E402
import codec                                                        # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
ap.add_argument('--frames', type=int, default=600)
ap.add_argument('--nth', type=int, default=1)
ap.add_argument('--topic', type=int, default=0)
ap.add_argument('--unit', type=int, default=0)
ap.add_argument('--press', default='b:120,a:260')
ap.add_argument('--png')
ap.add_argument('--delay', type=int, default=40)
args = ap.parse_args()

PyBoy = _import_pyboy()
pb = PyBoy(args.rom, window='null')
pb.set_emulation_speed(0)
with open(args.state, 'rb') as f:
    pb.load_state(f)

n = {'d': 0}
shot = {'buf': None, 'frame': None}


def on_dispatch(ctx):
    n['d'] += 1
    if n['d'] == args.nth:
        pb.memory[0xCF7A] = args.topic
        pb.memory[0xCF7B] = 0x80
        pb.memory[0xC6BC] = args.unit
        pb.register_file.A = 4


def on_rendered(ctx):
    if shot['buf'] is None:
        shot['buf'] = bytes(pb.memory[0xC616:0xC616 + 120])


pb.hook_register(4, 0x48AA, on_dispatch, None)
pb.hook_register(4, 0x49BF, on_rendered, None)

sched = {}
for i, p in enumerate([p for p in args.press.split(',') if p]):
    btn, at = (p.split(':') + [str(60 * (i + 1))])[:2]
    sched.setdefault(int(at), []).append(btn)
for f in range(args.frames):
    for btn in sched.get(f, ()):
        pb.button(btn)
    pb.tick()
    if shot['frame'] is None and shot['buf'] is not None:
        shot['frame'] = f
    if shot['frame'] is not None and f == shot['frame'] + args.delay and args.png:
        pb.screen.image.save(args.png)
pb.stop(save=False)

buf = shot['buf']
print('dispatches: %d   rendered: %s' % (n['d'], buf is not None))
if buf is None:
    sys.exit(1)
end = buf.find(b'\xFF\xFF')
body = buf[:end + 1 if end > 0 else 120]
print('buffer: %s' % body.hex(' '))
print('text  : %r' % codec.decode(body))
