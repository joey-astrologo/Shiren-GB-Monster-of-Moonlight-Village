#!/usr/bin/env python3
"""dte-scan the item CATEGORY boxes by driving the screen that draws them.

`gbrun.py --dte-scan` records what an expanding copy loop was SEEN to read, which is the
only evidence `script/dte_ok.tsv` accepts. Boxes 33/34 could never be scanned because no
button script reaches their screen -- so reach it the other way: bank 4's menu-screen
dispatcher at 4:$48AA takes a screen index in `a` (table of 35 at $48C3), and index 27 is
$4CD0, the routine that shows box 33 or 34 according to $C6E3.

Forcing the index makes the REAL routine draw the REAL box through the REAL drawer; only
the navigation that got us there is synthetic. The rows the drawer reads are therefore
observed exactly as any other allowlist entry is.

    boxscan.py <rom> --state saves/dungeon.state --page 0|1
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
ap.add_argument('--frames', type=int, default=500)
ap.add_argument('--press', default='b:120,a:260')
ap.add_argument('--nth', type=int, default=2)
ap.add_argument('--page', type=int, default=0)
ap.add_argument('--png')
args = ap.parse_args()

PyBoy = _import_pyboy()
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dte_rom
_, labels = dte_rom.build_expander()
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != os.path.join(ROOT, 'tools')]

relocmap = {}
mf = os.path.join(ROOT, 'build/relocmap.tsv')
if os.path.exists(mf):
    for line in open(mf, encoding='utf-8'):
        t = line.split('#')[0].strip()
        if '\t' in t:
            built, orig = t.split('\t')[:2]
            relocmap[built.strip()] = orig.strip()

pb = PyBoy(args.rom, window='null')
pb.set_emulation_speed(0)
with open(args.state, 'rb') as f:
    pb.load_state(f)

seen = {}
n = {'d': 0}

def reg16(name):
    rf = pb.register_file
    if name == 'hl':
        return rf.HL
    hi, lo = name.upper()
    return (getattr(rf, hi) << 8) | getattr(rf, lo)

def make(site, reg):
    def cb(ctx):
        src = reg16(reg)
        if not 0x4000 <= src <= 0x7FFF:
            return
        bank = pb.memory[0x4000]
        built = '%d:$%04X' % (bank, src)
        seen.setdefault(relocmap.get(built, built), site)
    return cb

for bank, addr, name, reg in dte_rom.SCAN_SITES:
    a = labels[addr] if isinstance(addr, str) else addr
    pb.hook_register(bank, a, make('%d:$%04X %s' % (bank, a, name), reg), None)

def on_dispatch(ctx):
    n['d'] += 1
    if n['d'] == args.nth:
        pb.memory[0xC6E3] = args.page
        pb.register_file.A = 27

pb.hook_register(4, 0x48AA, on_dispatch, None)

sched = {}
for i, p in enumerate([p for p in args.press.split(',') if p]):
    btn, at = (p.split(':') + [str(60 * (i + 1))])[:2]
    sched.setdefault(int(at), []).append(btn)
for f in range(args.frames):
    for btn in sched.get(f, ()):
        pb.button(btn)
    pb.tick()
if args.png:
    pb.screen.image.save(args.png)
pb.stop(save=False)

box = {k: v for k, v in seen.items() if 'box row drawer' in v}
print('%d strings observed, %d of them box rows' % (len(seen), len(box)))
for k in sorted(box):
    print('%s\t%s' % (k, box[k]))
