#!/usr/bin/env python3
"""Find the WRAM byte that times out a dungeon message.

Joey confirmed by A/B that the "messages vanish too fast" bug is present with DTE on and
absent with --no-dte, so DTE expanding untranslated Japanese changes something the message
system derives from the text. Find WHAT before changing the DTE design.

A timeout counter has a signature: it gets loaded with some value and then decrements once
per frame down to zero. Record a window of WRAM every frame and look for bytes with long
strictly-decreasing runs, then report the value each run STARTED at -- that starting value
is what should differ between the two builds.
"""
import argparse, os, sys, collections

def _import_pyboy():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    m = sys.modules.get('dis')
    if m is not None and not hasattr(m, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('--state', default='saves/dungeon.state')
ap.add_argument('--frames', type=int, default=1200)
ap.add_argument('--lo', type=lambda s: int(s, 16), default=0xC000)
ap.add_argument('--hi', type=lambda s: int(s, 16), default=0xE000)
ap.add_argument('--min-run', type=int, default=12)
args = ap.parse_args()

PyBoy = _import_pyboy()
pb = PyBoy(args.rom, window='null')
pb.set_emulation_speed(0)
with open(args.state, 'rb') as f:
    pb.load_state(f)

# Walk: movement is what produces the self-expiring messages.
sched = {}
f = 60
for _ in range(20):
    for btn in ('right', 'down', 'left', 'up'):
        sched.setdefault(f, []).append(btn)
        f += 26

addrs = list(range(args.lo, args.hi))
hist = {a: [] for a in addrs}
for i in range(args.frames):
    for btn in sched.get(i, ()):
        pb.button(btn, 6)
    pb.tick()
    mem = pb.memory[args.lo:args.hi]
    for k, a in enumerate(addrs):
        hist[a].append(mem[k])
pb.stop(save=False)

found = []
for a in addrs:
    v = hist[a]
    run, start_val, best = 1, v[0], []
    for i in range(1, len(v)):
        if v[i] == v[i - 1] - 1:
            run += 1
        else:
            if run >= args.min_run:
                best.append((run, start_val, i - run))
            run, start_val = 1, v[i]
    if run >= args.min_run:
        best.append((run, start_val, len(v) - run))
    if best:
        found.append((a, best))

print('%s: %d addresses with a decreasing run of >=%d frames'
      % (os.path.basename(args.rom), len(found), args.min_run))
for a, best in sorted(found, key=lambda t: -max(r for r, _, _ in t[1]))[:14]:
    runs = ', '.join('%d frames from %d @f%d' % (r, s, w) for r, s, w in best[:4])
    print('  $%04X  x%-2d  %s' % (a, len(best), runs))
