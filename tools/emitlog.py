#!/usr/bin/env python3
"""Log every byte the DTE expander actually EXPANDS at runtime, and where it came from.

The build-time check only sees strings in script.json. The composer's second loop reads
from $CF8F -- a WRAM buffer the game assembles at runtime -- so bytes can reach the
expander that no static check can see. That is the same class of hazard as the box drawer
reading the player's name out of SRAM.

Hooks dte_emit (0:$0092) and records the byte in `a` plus the source pointer, split by
whether the source is ROM or WRAM. Anything expanded from WRAM is content the build cannot
vet.

    emitlog.py <rom> [--state S] [--press ...]
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Do NOT import dte_rom here: it drags tools/ onto sys.path, tools/dis.py shadows the
# stdlib `dis`, and pyboy's import chain then dies on COMPILER_FLAG_NAMES. Read the ranges
# out of the file textually instead.
import re as _re
_src = open(os.path.join(ROOT, 'tools', 'dte_rom.py'), encoding='utf-8').read()
_m = _re.search(r'^DTE_RANGES = \((.*)\)$', _src, _re.M)
RANGES = [(int(a, 16), int(b, 16))
          for a, b in _re.findall(r'\(0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\)', _m.group(1))]
CODES = {c for lo, hi in RANGES for c in range(lo, hi + 1)}
print('code space: %s = %d codes'
      % (' '.join('$%02X-$%02X' % r for r in RANGES), len(CODES)))

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
ap.add_argument('--frames', type=int, default=2000)
args = ap.parse_args()

PyBoy = _import_pyboy()
pb = PyBoy(args.rom, window='null')
pb.set_emulation_speed(0)
with open(args.state, 'rb') as f:
    pb.load_state(f)

expanded = collections.Counter()
by_src = collections.Counter()
calls = {'n': 0}

def on_emit(ctx):
    calls['n'] += 1
    a = pb.register_file.A
    if a not in CODES:
        return                      # a literal; dte_emit passes it through
    hl = pb.register_file.HL
    where = ('ROM$%X' % (hl >> 12)) if hl < 0x8000 else ('WRAM$%X' % (hl >> 8))
    expanded[a] += 1
    by_src[where] += 1

pb.hook_register(0, 0x0092, on_emit, None)

# Bash on a lot of buttons: messages come from encounters and items, not from walking a
# corridor, and a fixed walk produced zero composer activity in an earlier attempt.
seq = ['a', 'b', 'right', 'down', 'left', 'up', 'start', 'select']
f = 60
sched = {}
for i in range(220):
    sched.setdefault(f, []).append(seq[i % len(seq)])
    f += 8
for i in range(args.frames):
    for btn in sched.get(i, ()):
        pb.button(btn, 5)
    pb.tick()
pb.stop(save=False)

print('%s: dte_emit called %d times' % (os.path.basename(args.rom), calls['n']))
print('   bytes actually EXPANDED: %d' % sum(expanded.values()))
if expanded:
    print('   by source: %s' % dict(by_src))
    print('   codes: %s' % ' '.join('$%02X x%d' % (b, n)
                                    for b, n in expanded.most_common(12)))
