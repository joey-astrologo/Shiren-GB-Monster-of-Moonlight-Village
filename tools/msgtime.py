#!/usr/bin/env python3
"""Measure how long a self-expiring dungeon message stays on screen.

Joey reports that dungeon messages which time out on their own vanish too fast to read.
That is invisible to a screenshot, so it has to be measured.

STATUS: THIS APPROACH DOES NOT WORK YET, kept as a record of what was ruled out. Counting
non-blank tiles in the message rows fails because dungeon TERRAIN fills every row of
tilemap_background -- occupancy comes back 20/20 on all 18 rows for the entire run, so
there is no signal. A message drawn over the map does not change the count.

Do it from the message's own state instead: a timer or flag in the $CF00 page (the line
buffer is $CF07, and the composer reads flags at $CF06), or a hook on whatever tears the
box down. tools/gridprobe.py is the worked example of hooking one instruction and comparing
what the game computed against what the ROM actually holds.

Run the same script against two builds and compare. The prime suspect is DTE expanding
UNTRANSLATED Japanese -- the accepted cost -- because that changes cell counts, which
changes wrapping, which can change anything the game derives from message length.

    msgtime.py <rom> [--state S] [--frames N] [--press ...]
"""
import argparse, os, sys

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
ap.add_argument('--frames', type=int, default=1400)
ap.add_argument('--press', default='')
ap.add_argument('--rows', default='0,3', help='screen rows to watch, "lo,hi" inclusive')
args = ap.parse_args()

lo, hi = (int(x) for x in args.rows.split(','))

PyBoy = _import_pyboy()
pb = PyBoy(args.rom, window='null')
pb.set_emulation_speed(0)
with open(args.state, 'rb') as f:
    pb.load_state(f)

# Walk in a fixed pattern: movement is what produces the self-expiring messages, and a
# scripted walk is repeatable in a way that hand-driving Mesen is not.
sched = {}
if args.press:
    for p in args.press.split(','):
        btn, at = p.split(':')
        sched.setdefault(int(at), []).append(btn)
else:
    f = 60
    for _ in range(24):
        for btn in ('right', 'right', 'down', 'left', 'up'):
            sched.setdefault(f, []).append(btn)
            f += 22

# A blank cell is $00 or the space code; anything else in the message rows is text.
BLANK = {0x00, 0x0B, 0xFF}

occ = []
for i in range(args.frames):
    for btn in sched.get(i, ()):
        pb.button(btn, 6)
    pb.tick()
    n = 0
    for y in range(lo, hi + 1):
        for x in range(20):
            if pb.tilemap_background[x, y] not in BLANK:
                n += 1
    occ.append(n)
pb.stop(save=False)

# Runs of consecutive frames where the message area holds text.
runs, start = [], None
for i, n in enumerate(occ):
    if n > 0 and start is None:
        start = i
    elif n == 0 and start is not None:
        runs.append((start, i - start))
        start = None
if start is not None:
    runs.append((start, len(occ) - start))

runs = [r for r in runs if r[1] > 2]
print('%s: %d message runs in %d frames (rows %d-%d)'
      % (os.path.basename(args.rom), len(runs), args.frames, lo, hi))
if runs:
    lens = sorted(n for _, n in runs)
    print('   lifetimes (frames): %s' % lens)
    print('   min %d  median %d  max %d  mean %.1f'
          % (lens[0], lens[len(lens) // 2], lens[-1], sum(lens) / len(lens)))
