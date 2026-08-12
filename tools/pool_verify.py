#!/usr/bin/env python3
"""Watch the pool redirect fire in a real run, and photograph the result.

Hooks bank 33's copy loop at the point where a line has been staged into $CF8F, decodes
what landed there, and saves a screenshot of the frame it was drawn on. A record in the
ROM proves nothing on its own -- what has to be true is that the composer, which knows
nothing about any of this, draws pool text exactly as it draws in-place text.

    pool_verify.py build/pool_spike.gb --seeds 12
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec                                                    # noqa: E402
import pool                                                     # noqa: E402
import dte_rom                                                  # noqa: E402
from latinfont import EN_CODES                                  # noqa: E402
from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES         # noqa: E402

DEC = {v: k for k, v in EN_CODES.items()}
DISPATCH = (pool.POOL_A, 0x4010)


def _hookpoints(rom):
    """-> (redirect-taken addr, line-staged addr) inside the installed dispatcher."""
    import gbasm
    code, _ = gbasm.assemble(pool.dispatch_src(), pool.CODE_ORG)
    # `ld a,[$CF91]` is the first instruction of the redirect arm; the `ld a,h` that
    # follows the copy loop is where a staged line is complete.
    taken = pool.CODE_ORG + code.index(bytes.fromhex('fa91cf'))
    staged = pool.CODE_ORG + code.index(bytes.fromhex('7cea80cf'))
    return taken, staged


def dte_table(rom_path):
    """The pair table as the ROM holds it: bank 32 $4100 = LEFT[code], $4200 = RIGHT[code].

    Pool text is compressed like any other string, so the bytes sitting in $CF8F are DTE
    codes and reading them raw prints nonsense. An earlier run of this tool showed
    `|?nkeep??Ah,?|` and that is the expander doing its job, not the redirect failing.
    """
    with open(rom_path, 'rb') as f:
        f.seek(dte_rom.TABLE_BANK * 0x4000 + 0x0100)
        left = f.read(0x100)
        f.seek(dte_rom.TABLE_BANK * 0x4000 + 0x0200)
        right = f.read(0x100)
    return {c: (left[c], right[c]) for c in dte_rom.DTE_CODES if left[c] != 0xFF}


def show(data, table, depth=0):
    out = []
    for b in data:
        if b == 0xFF:
            break
        if b in table and depth < 8:
            out.append(show(bytes(table[b]), table, depth + 1))
        elif b in codec.CONTROL:
            out.append('<%s>' % codec.CONTROL[b])
        else:
            out.append(DEC.get(b, '<$%02X>' % b))
    return ''.join(out)


def run(rom, state, seed, frames, png_dir):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)
    taken, staged = _hookpoints(rom)
    table = dte_table(rom)
    log = {'taken': 0, 'lines': []}
    want = {'shot': None}

    def on_taken(ctx):
        log['taken'] += 1

    def on_staged(ctx):
        if not log['taken']:
            return                      # an in-place line: not what this is watching
        data = bytes(pb.memory[pool.STAGE_BUF:pool.STAGE_BUF + 96])
        log['lines'].append(show(data, table))
        want['shot'] = True

    pb.hook_register(DISPATCH[0], taken, on_taken, None)
    pb.hook_register(DISPATCH[0], staged, on_staged, None)

    rng = __import__('random').Random(seed)
    shots = 0
    for f in range(frames):
        if f >= 60 and (f - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        pb.tick()
        # The box is DRAWN some frames after the line is staged, so shooting on the
        # stage frame photographs the previous screen. Spread the shots out.
        if want['shot'] and shots < 12 and f % 7 == 0:
            name = os.path.join(png_dir, 'pool_%s_s%d_%03d.png'
                                % (os.path.basename(state).split('.')[0], seed, shots))
            pb.screen.image.save(name)
            shots += 1
            if shots >= 12:
                want['shot'] = False
    pb.stop(save=False)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--seeds', type=int, default=12)
    ap.add_argument('--frames', type=int, default=3000)
    ap.add_argument('--states', default='saves/town.state,saves/dungeon.state')
    ap.add_argument('--png-dir', default='build')
    a = ap.parse_args()

    for st in [s for s in a.states.split(',') if os.path.exists(s)]:
        for seed in range(a.seeds):
            log = run(a.rom, st, seed, a.frames, a.png_dir)
            if log['taken']:
                print('%s seed %d: redirect taken %d time(s), %d pool line(s)'
                      % (os.path.basename(st), seed, log['taken'], len(log['lines'])))
                for ln in log['lines'][:12]:
                    print('    |%s|' % ln)
                return 0
            print('%s seed %d: no redirect' % (os.path.basename(st), seed))
    print('\nthe redirected string was never reached by these inputs')
    return 1


if __name__ == '__main__':
    sys.exit(main())
