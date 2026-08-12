#!/usr/bin/env python3
"""Photograph the equipment SEAL screen -- box $13, the lines under a melded weapon.

WHY THIS EXISTS. Session 9 translated 20 strings that no check in HANDOFF_NEXT.md section 1
can see a player read, and session A1 is the reason that is not good enough: 25 strings
were byte-perfect through the pool, green on every check, and rendered Japanese on screen.
`--check` measures the translation against a model of the box. This measures the box.

WHY IT IS NOT `helpshot.py --nth 5`. Bank 4's menu dispatcher (4:$48AA, index in `a`) has
this screen at index 5, `4:$49F5` -- one past the help renderer helpshot forces. Forcing
the index alone HANGS, which is what HANDOFF_NEXT.md recorded and stopped at. The reason
is `11:$7E40`, not the dispatcher:

    ld a,[$C6BC] -> b        the seal slot to start at
    ld c,$04                 four rows under the name, one per seal
    hl = $C6BE + b           the item's seal ids, $FF-terminated
    a = [hl]; cp $FF; sla a; hl = $5463 + a      <- the 20-entry table
    copy [hl]..$FF into [de], terminator included

$C6BE is the equipped item's seal array, and a save state that is not sitting on a melded
item leaves junk there. A junk id is doubled and added to $5463, so the copy starts at an
arbitrary address and runs to the next $FF anywhere in bank 11 -- past the end of the 120
bytes `4:$49F5` cleared at $C616, into live WRAM. It is not the screen that hangs, it is
the byte after it. So this tool SUPPLIES the context rather than forcing the index into
whatever the state happens to hold: $C6BE gets real seal ids, $C6BD their count (4:$4A35
compares `[$C6BC]+4` against it to decide whether to draw the scroll arrow), $C6BC the
scroll offset.

    sealshot.py build/shiren_en.gb --seals 0,1,2,3 --png build/seals.png
    sealshot.py build/shiren_en.gb --all            every one of the 20, five screens

The buffer is read at `4:$4A0D`, the instruction the far call returns to, before the box
is drawn -- the same trick and the same reason as helpshot.py's `4:$49BF`: the inventory
redraws over $C616 within a few frames.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gbrun import _import_pyboy                                     # noqa: E402
import codec                                                        # noqa: E402
import dialogue_preview as dialogue                                 # noqa: E402
import dotfont                                                       # noqa: E402
from latinfont import EN_CODES                                      # noqa: E402

# The Latin alphabet is written over the kana tiles, so codec.decode -- the Japanese
# table -- shows an English line as kana. Same inversion dialogue_preview.py uses.
EN_CHARS = {v: k for k, v in sorted(EN_CODES.items(), reverse=True)}

SEAL_COUNT = 20             # 11:$5463, the table 11:$7E40 indexes


def decode_row(b):
    """-> (text, cells). CELLS, not bytes -- 31:$4124 draws a dakuten OVER the preceding
    cell and skips the width countdown, so `ステータスをうばう...` is 19 bytes and 18 cells.
    Counting bytes reports the shipped Japanese as one cell over its own box, which is the
    same mistake the composer geometry used to make about the item descriptions.
    """
    text = ''.join(EN_CHARS.get(c, codec.decode(bytes([c])) or '.') for c in b)
    return text, sum(1 for c in b if c not in codec.COMBINING)


def shoot(rom, state, seals, png=None, frames=600, nth=1, press='b:120,a:260', delay=40):
    """-> the 120-byte buffer the renderer staged, or None if it never rendered."""
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)

    n = {'d': 0}
    shot = {'buf': None, 'frame': None}

    def on_dispatch(ctx):
        n['d'] += 1
        if n['d'] != nth:
            return
        # The context 11:$7E40 reads. Without this the copy loop walks off the table.
        pb.memory[0xC6BC] = 0                       # start at the first seal
        pb.memory[0xC6BD] = len(seals)              # 4:$4A35's "is there more" total
        for i, s in enumerate(seals):
            pb.memory[0xC6BE + i] = s
        pb.memory[0xC6BE + len(seals)] = 0xFF       # the terminator the loop stops on
        pb.register_file.A = 5

    def on_staged(ctx):
        if shot['buf'] is None:
            shot['buf'] = bytes(pb.memory[0xC616:0xC616 + 120])

    pb.hook_register(4, 0x48AA, on_dispatch, None)
    pb.hook_register(4, 0x4A0D, on_staged, None)

    sched = {}
    for i, p in enumerate([p for p in press.split(',') if p]):
        btn, at = (p.split(':') + [str(60 * (i + 1))])[:2]
        sched.setdefault(int(at), []).append(btn)
    for f in range(frames):
        for btn in sched.get(f, ()):
            pb.button(btn)
        pb.tick()
        if shot['frame'] is None and shot['buf'] is not None:
            shot['frame'] = f
        if shot['frame'] is not None and f == shot['frame'] + delay and png:
            pb.screen.image.save(png)
    pb.stop(save=False)
    return shot['buf']


def report(buf, seals):
    """Print staged rows under the current 21-glyph/144px Dot seal contract."""
    rows, p = [], 0
    while p < len(buf) and len(rows) < 5:
        end = buf.find(b'\xFF', p)
        if end < 0:
            break
        rows.append(buf[p:end])
        p = end + 1
        if p < len(buf) and buf[p] == 0xFF:
            break
    over = 0
    font = dotfont.load_approved()
    print('    +' + '-' * dialogue.HELP_WIDTH + '+')
    for i, row in enumerate(rows):
        text, cells = decode_row(row)
        flag = ''
        _advance, extent, unknown = dialogue.dot_metrics(row, font, bank=11)
        if i > 0 and (cells > dialogue.HELP_WIDTH or extent > dialogue.LINE_PX or unknown):
            flag = '  << %d/%d glyphs, %d/%dpx%s' % (
                cells, dialogue.HELP_WIDTH, extent, dialogue.LINE_PX,
                ', native code' if unknown else '')
            over += i > 0          # row 0 is the item name, staged by 4:$5736, not ours
        label = 'name' if i == 0 else 'seal %d' % seals[i - 1] if i - 1 < len(seals) else '?'
        print('    |%-*s|  %-7s%s' % (dialogue.HELP_WIDTH,
                                      text[:dialogue.HELP_WIDTH], label, flag))
    print('    +' + '-' * dialogue.HELP_WIDTH + '+')
    return over


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    ap.add_argument('--seals', default='0,1,2,3',
                    help='comma-separated seal ids, up to 4 (the box draws four)')
    ap.add_argument('--all', action='store_true',
                    help='every one of the 20, four at a time')
    ap.add_argument('--frames', type=int, default=600)
    ap.add_argument('--nth', type=int, default=1)
    ap.add_argument('--press', default='b:120,a:260')
    ap.add_argument('--png')
    ap.add_argument('--delay', type=int, default=40)
    args = ap.parse_args()

    if args.all:
        groups = [list(range(i, min(i + 4, SEAL_COUNT))) for i in range(0, SEAL_COUNT, 4)]
    else:
        groups = [[int(s, 0) for s in args.seals.split(',') if s.strip()]]

    over = 0
    for g in groups:
        png = args.png
        if png and len(groups) > 1:
            root, ext = os.path.splitext(png)
            png = '%s_%02d%s' % (root, g[0], ext)
        buf = shoot(args.rom, args.state, g, png, args.frames, args.nth,
                    args.press, args.delay)
        print('seals %s%s' % (','.join(str(s) for s in g),
                              '  -> %s' % png if png else ''))
        if buf is None:
            print('    NOT RENDERED -- the dispatcher never reached index 5')
            return 1
        over += report(buf, g)
        print()
    if over:
        print('%d row(s) exceed the 21-glyph/144px Dot seal contract' % over)
    return 1 if over else 0


if __name__ == '__main__':
    sys.exit(main())
