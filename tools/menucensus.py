#!/usr/bin/env python3
"""Census live menu-screen references to a proposed VRAM tile pool.

Step 4B of HANDOFF_MENUVWF proposes reclaiming tile indices $82-$9D.  The Latin
encoder does not use that range for ordinary English glyphs, but that does NOT make
the VRAM tiles free: the game also uses raw tile indices for cursors, equipped-row
markers, field blanks, stars, alternate digits and arrows.

This tool measures references, rather than inferring them from the character table.
It watches every LCD-on frame in two complementary scenarios:

  * a real main-menu -> item-list -> page-flip -> action-menu flow;
  * all 35 bank-4 menu dispatcher entries, forced one at a time by the same technique
    as menushot.py and wramfree.py.  The real screen routine and real drawer still run.

Each sample reads every visible BG and window tile plus every visible OBJ.  OBJ mode
matters: in 8x16 mode an even/odd pair is live even though OAM ignores bit 0.  A tile
is reported if its effective VRAM index is inside the requested range.  The forced
screen census starts only after the target dispatcher entry fires, so dungeon terrain
before the menu opens cannot become a false reference.

Run this on BOTH the game-only control and the integrated build.  The control proves
which references belong to the game; the integrated build proves menuvwf has not
silently hidden one.

    python3 tools/menucensus.py build/nomenuvwf.gb build/shiren_en.gb

The command exits nonzero only if a scenario failed to run and therefore measured
nothing.  Finding live tiles is the expected output of a census, not a tool failure.
"""
import argparse
import collections
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES                 # noqa: E402
import codec                                                   # noqa: E402
import menushot                                                 # noqa: E402


DEFAULT_LO = 0x82
DEFAULT_HI = 0x9D
FONT_UPLOAD = (13, 0x7643)
STATE = os.path.join(ROOT, 'saves', 'dungeon.state')


# Names established elsewhere in the repo.  codec.CHARS supplies the printable ones;
# these fill in structural tiles that deliberately are not encodable English text.
STRUCTURAL = {
    0x83: 'equipped left border',
    0x84: 'equipped E marker',
    0x85: 'equipped left border (alternate)',
    0x86: 'equipped E marker (alternate)',
    0x88: 'name-entry field blank',
}
STATIC_RESERVED = {0x83, 0x84, 0x85, 0x86}
DRAWER_BANK = 31
DRAWER_MARKER_AT = 0x40E5
DRAWER_MARKER_BYTES = bytes.fromhex('fe8420043e83180afe8620043e851802')


def tile_name(tile):
    if tile in STRUCTURAL:
        return STRUCTURAL[tile]
    ch = codec.CHARS.get(tile)
    return repr(ch) if ch is not None else 'unlabelled'


class Census:
    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi
        self.hits = collections.defaultdict(lambda: {
            'count': 0, 'layers': set(), 'scenarios': set(), 'examples': []})
        self.samples = collections.Counter()

    def _record(self, tile, layer, scenario, frame, where):
        if not self.lo <= tile <= self.hi:
            return
        hit = self.hits[tile]
        hit['count'] += 1
        hit['layers'].add(layer)
        hit['scenarios'].add(scenario)
        example = '%s f%d %s' % (scenario, frame, where)
        if len(hit['examples']) < 6 and example not in hit['examples']:
            hit['examples'].append(example)

    def sample(self, pb, scenario, frame):
        lcdc = pb.memory[0xFF40]
        if not lcdc & 0x80:
            return
        # Menu screens use signed BG tile addressing ($8800/$9000).  The floor-name
        # banner uses unsigned addressing and deliberately fills numeric indices
        # $80-$A7 with a transient 160x16 graphic.  Those tiles are reloaded after a
        # menu closes and are not simultaneous pool consumers; admitting that mode
        # makes every proposed tile look live for the wrong renderer.
        if lcdc & 0x10:
            return
        self.samples[scenario] += 1

        # BG: account for scroll and for a partial tile at either edge.  Menu screens
        # normally use SCX=SCY=0 and $9800, but the census should not assume that.
        bg_base = 0x9C00 if lcdc & 0x08 else 0x9800
        scx, scy = pb.memory[0xFF43], pb.memory[0xFF42]
        cols = 20 + bool(scx & 7)
        rows = 18 + bool(scy & 7)
        for sy in range(rows):
            my = ((scy >> 3) + sy) & 31
            for sx in range(cols):
                mx = ((scx >> 3) + sx) & 31
                addr = bg_base + 32 * my + mx
                tile = pb.memory[addr]
                self._record(tile, 'BG', scenario, frame,
                             '$%04X (map %d,%d)' % (addr, mx, my))

        # Window: unlike BG it does not scroll.  Only cells intersecting the physical
        # 160x144 display are live.  WX is stored with a hardware +7 bias.
        if lcdc & 0x20:
            win_base = 0x9C00 if lcdc & 0x40 else 0x9800
            wx, wy = pb.memory[0xFF4B] - 7, pb.memory[0xFF4A]
            for row in range(18):
                y = wy + 8 * row
                if y >= 144 or y + 7 < 0:
                    continue
                for col in range(20):
                    x = wx + 8 * col
                    if x >= 160 or x + 7 < 0:
                        continue
                    addr = win_base + 32 * row + col
                    tile = pb.memory[addr]
                    self._record(tile, 'WIN', scenario, frame,
                                 '$%04X (map %d,%d)' % (addr, col, row))

        # Sprites always address $8000 tile data.  In 8x16 mode OAM bit 0 is ignored
        # and both tiles in the pair are live, so account for both explicitly.
        obj16 = bool(lcdc & 0x04)
        for i in range(40):
            at = 0xFE00 + 4 * i
            y, x, raw = pb.memory[at], pb.memory[at + 1], pb.memory[at + 2]
            if not (0 < x < 168 and 0 < y < 160):
                continue
            effective = (raw & 0xFE, (raw & 0xFE) + 1) if obj16 else (raw,)
            for tile in effective:
                self._record(tile, 'OBJ', scenario, frame,
                             'OAM %d raw $%02X%s' %
                             (i, raw, ' (8x16 pair)' if obj16 else ''))

    def report(self, rom):
        print('\n%s  proposed pool $%02X-$%02X' % (rom, self.lo, self.hi))
        print('tile  state   meaning                              layers  scenarios')
        print('----  ------  -----------------------------------  ------  ---------')
        for tile in range(self.lo, self.hi + 1):
            hit = self.hits.get(tile)
            if hit:
                scenarios = sorted(hit['scenarios'])
                shown = ', '.join(scenarios[:5])
                if len(scenarios) > 5:
                    shown += ', +%d more' % (len(scenarios) - 5)
                print('$%02X   LIVE    %-35s  %-6s  %s' %
                      (tile, tile_name(tile), ','.join(sorted(hit['layers'])), shown))
                for ex in hit['examples'][:2]:
                    print('              ' + ex)
            elif tile in STATIC_RESERVED:
                print('$%02X   reserve %-35s  %s' %
                      (tile, tile_name(tile), '31:$40E5 marker/border branch'))
            else:
                print('$%02X   unseen  %-35s' % (tile, tile_name(tile)))
        live = sorted(self.hits)
        occupied = sorted(set(live) | (STATIC_RESERVED & set(range(self.lo, self.hi + 1))))
        free = [t for t in range(self.lo, self.hi + 1) if t not in occupied]
        print('LIVE set  : %s' % (' '.join('$%02X' % t for t in live) or '(none)'))
        print('reserved  : %s (the alternate $86 marker was not in this save, but the '
              'live drawer maps it to $85)' %
              (' '.join('$%02X' % t for t in sorted(STATIC_RESERVED)) or '(none)'))
        print('unseen set: %s' % (' '.join('$%02X' % t for t in free) or '(none)'))
        print('verdict   : %s' %
              ('NOT SAFE as one contiguous pool (%d/%d tiles live or reserved)'
               % (len(occupied), self.hi - self.lo + 1) if occupied else
               'no live reference observed; safe only within the measured scenarios'))


def new_pyboy(PyBoy, rom):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(STATE, 'rb') as f:
        pb.load_state(f)
    return pb


def real_flow(PyBoy, rom, census):
    """Exercise real redraws and page changes; sample only after the menu font upload."""
    pb = new_pyboy(PyBoy, rom)
    active = {'yes': False, 'uploads': 0}

    def on_upload(_ctx=None):
        active['yes'] = True
        active['uploads'] += 1

    pb.hook_register(FONT_UPLOAD[0], FONT_UPLOAD[1], lambda _ctx: on_upload(), None)
    script = {
        60: 'b',       # main menu
        120: 'a',      # item list
        180: 'right',  # page 2
        240: 'right',  # page 3 / wrap on a shorter inventory
        300: 'left',   # another full redraw
        360: 'a',      # action menu
        420: 'b',      # close overlay; item list redraws
    }
    phase = 'real flow: dungeon idle'
    for frame in range(480):
        if frame in script:
            phase = 'real flow: %s' % script[frame]
            pb.button(script[frame], PRESS_FRAMES)
        pb.tick()
        if active['yes']:
            census.sample(pb, phase, frame)
    pb.stop(save=False)
    if not active['uploads'] or not any(k.startswith('real flow:') for k in census.samples):
        return ['real flow: menu font upload never fired; measured nothing']
    return []


def saved_flow(PyBoy, rom, ram, census):
    """Boot Joey's real menu save, resume log 3, and exercise its equipped pages.

    A temporary ROM+RAM pair keeps the fixture reproducible and prevents PyBoy from
    changing either the checked-in build output or the supplied save.
    """
    with tempfile.TemporaryDirectory(prefix='menucensus-') as tmp:
        work = os.path.join(tmp, 'menu.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        active = {'yes': False, 'uploads': 0}
        phase = {'name': 'saved flow: boot'}
        clock = {'frame': 0, 'last_dispatch': -1000}

        def on_upload(_ctx=None):
            active['yes'] = True
            active['uploads'] += 1

        def on_dispatch(_ctx=None):
            phase['name'] = 'saved flow: screen %02d' % pb.register_file.A
            clock['last_dispatch'] = clock['frame']

        pb.hook_register(FONT_UPLOAD[0], FONT_UPLOAD[1], lambda _ctx: on_upload(), None)
        pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH,
                         lambda _ctx: on_dispatch(), None)

        # Four title dismissals, Adventure, down to log 3, select, Continue.  The
        # floor-7 arrival and NPC bubble settle by f1700; then B/A reaches the exact
        # inventory Joey used for menuvwf_joey_p1/p2/p3.png.
        script = {
            60: 'start', 120: 'start', 180: 'start', 240: 'start',
            300: 'a', 350: 'down', 390: 'down', 430: 'a', 500: 'a',
            1700: 'b', 1780: 'a', 1840: 'right', 1900: 'right',
            1960: 'left', 2020: 'a', 2080: 'b',
        }
        for frame in range(2140):
            clock['frame'] = frame
            if frame in script:
                phase['name'] = 'saved flow: %s' % script[frame]
                pb.button(script[frame], PRESS_FRAMES)
            pb.tick()
            # The white transition after Continue leaves old menu/floor tilemap bytes
            # behind while no menu is visible.  A font upload is an epoch marker, not
            # an "a menu is up forever" flag.  Attribute only frames close to a real
            # bank-4 screen dispatch; page flips and overlay redraws re-enter it.
            if active['yes'] and frame - clock['last_dispatch'] <= 96:
                census.sample(pb, phase['name'], frame)
        pb.stop(save=False)
        if not active['uploads']:
            return ['saved flow: menu font upload never fired; measured nothing']
        if not any(k.startswith('saved flow:') for k in census.samples):
            return ['saved flow: no LCD-on menu frame sampled']
    return []


def forced_screens(PyBoy, rom, census):
    """Force all dispatcher indices; sample from the first forced dispatch onward."""
    problems = []
    for idx in range(menushot.TABLE_LEN):
        pb = new_pyboy(PyBoy, rom)
        fired = {'n': 0}

        def at_dispatch(_ctx=None, idx=idx):
            fired['n'] += 1
            if fired['n'] == 1:
                pb.register_file.A = idx

        pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH,
                         lambda _ctx: at_dispatch(), None)
        scenario = 'forced screen %02d' % idx
        for frame in range(340):
            if frame == 60:
                pb.button('b', PRESS_FRAMES)
            if frame == 160:
                pb.button('a', PRESS_FRAMES)
            pb.tick()
            if fired['n']:
                census.sample(pb, scenario, frame)
        pb.stop(save=False)
        if not fired['n']:
            problems.append('%s: dispatcher never fired' % scenario)
        # Some dispatcher entries are context-dependent transition routines and leave
        # the LCD off when forced from a dungeon fixture.  That is a measured outcome,
        # not permission to call their tiles free; the real saved flow above supplies
        # title/file-menu context as an independent path.
    return problems


def run(rom, lo, hi, ram=None):
    PyBoy = _import_pyboy()
    census = Census(lo, hi)
    problems = []
    blob = open(rom, 'rb').read()
    marker_off = DRAWER_BANK * 0x4000 + (DRAWER_MARKER_AT - 0x4000)
    got = blob[marker_off:marker_off + len(DRAWER_MARKER_BYTES)]
    if got != DRAWER_MARKER_BYTES:
        problems.append('%s: 31:$40E5 marker/border branch changed: want %s got %s'
                        % (rom, DRAWER_MARKER_BYTES.hex(), got.hex()))
    problems += real_flow(PyBoy, rom, census)
    if ram:
        problems += saved_flow(PyBoy, rom, ram, census)
    problems += forced_screens(PyBoy, rom, census)
    census.report(rom)
    if problems:
        print('MEASUREMENT PROBLEMS:')
        for p in problems:
            print('  ' + p)
    else:
        dark = [i for i in range(menushot.TABLE_LEN)
                if not census.samples['forced screen %02d' % i]]
        print('coverage  : real flow%s + all %d forced dispatcher entries ran'
              % (' + saved-menu flow' if ram else '', menushot.TABLE_LEN))
        if dark:
            print('            forced entries with LCD off throughout: %s'
                  % ', '.join(str(i) for i in dark))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom', nargs='+')
    ap.add_argument('--lo', type=lambda s: int(s, 16), default=DEFAULT_LO)
    ap.add_argument('--hi', type=lambda s: int(s, 16), default=DEFAULT_HI)
    ap.add_argument('--ram', help='cart RAM fixture to boot for the real saved-menu flow')
    args = ap.parse_args()
    if not 0 <= args.lo <= args.hi <= 0xFF:
        raise SystemExit('tile range must be inside 00-FF')
    missing = [p for p in args.rom if not os.path.exists(p)]
    if args.ram and not os.path.exists(args.ram):
        missing.append(args.ram)
    if missing:
        raise SystemExit('missing ROM(s): %s' % ', '.join(missing))
    problems = []
    for rom in args.rom:
        problems += run(rom, args.lo, args.hi, args.ram)
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
