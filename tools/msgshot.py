#!/usr/bin/env python3
"""Draw ANY bank-11/14 message on the real screen, by substituting the queued pointer.

Reaching a `<cEC>` screen by playing is the practical obstacle -- a random walk never
lands on a signboard, and the shrine menus and the Kuyo Pass picker are further in still.
But every one of them arrives through the SAME routine: `13:$67D5` puts a tagged pointer
in `hl` and in `$CF7F/$CF80`, and everything downstream reads it from there. So triggering
one message and rewriting the pointer at `13:$67ED` -- after the stores, before the first
stage -- renders any other message instead, through the game's own renderer.

Tag: bank 11 is `set 6,h`, bank 14 is `xor $C0` on the high byte. `13:$6C73` reads `hl`,
not just the stores, so both have to be set.
"""
import argparse, os, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy                                      # noqa
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != TOOLS]
PyBoy = _import_pyboy()


def tag(bank, addr):
    hi, lo = addr >> 8, addr & 0xFF
    return ((hi ^ 0xC0) << 8 | lo) if bank == 14 else ((hi | 0x40) << 8 | lo)


def shot(rom, state, bank, addr, png, frames=150, press_at=5, scale=4):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)
    want = tag(bank, addr)
    done = []

    def cb(ctx):
        if done:
            return
        done.append(1)
        rf = pb.register_file
        rf.HL = want
        pb.memory[0xCF80] = want >> 8
        pb.memory[0xCF7F] = want & 0xFF
    pb.hook_register(13, 0x67ED, cb, None)

    for i in range(frames):
        if i == press_at:
            pb.button('a', 5)
        pb.tick()
    im = pb.screen.image
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale))
    im.save(png)
    pb.stop(save=False)
    return bool(done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('state')
    ap.add_argument('locs', nargs='+', help='e.g. 14:$4638')
    ap.add_argument('--out-dir', default='.')
    ap.add_argument('--frames', type=int, default=150)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for loc in args.locs:
        b, a = loc.split(':')
        b, a = int(b), int(a.lstrip('$'), 16)
        png = os.path.join(args.out_dir, '%s_%04X.png' % (b, a))
        hit = shot(args.rom, args.state, b, a, png, frames=args.frames)
        print('%-12s %s  %s' % (loc, 'substituted' if hit else 'NEVER REACHED $67ED', png))


main()
