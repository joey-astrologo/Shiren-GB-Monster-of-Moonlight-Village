#!/usr/bin/env python3
"""Measure the tile residency of the main/item/action menu-VWF allowlist.

This audit was the Step-4B prerequisite for the integrated proportional renderer: can
main-menu, item-list and action-menu rows share the fragmented tiles that remain after
the $82-$9D reference census? It stays as the independent raw-drawer control model.

This tool watches the ORIGINAL bank-31 row drawer in a --no-menuvwf control ROM and
models every row that the intended allowlist would compose:

  * main menu:  x0, y0, w5, dynamic;
  * item list:  x0, y3, w18, dynamic;
  * action menu: x13, w5, dynamic.

Because it observes the raw drawer, it sees rows even though the current far hook has
them disabled.  It tracks which text cells remain on the shadow tilemap as boxes cover
one another and reports two different lower bounds:

  * visible slices -- capneed() space belonging to rows with at least one visible cell;
  * fresh-row peak -- visible slices plus the row being composed before its old cells
    are replaced.  This is the capacity needed to remove page-flip tile jumble without
    overwriting tile data still referenced by the old tilemap.

The synthetic flow uses the same five 17-character counter rows as menuspill --long,
then opens the real action menu over them.  It is the bounded worst-case test; passing
only the ordinary inventory is not a capacity proof.

Run on the game-owned control so raw shadow bytes can prove liveness:

    python3 tools/menuresidency.py build/nomenuvwf.gb \
        --ram saves/shiren_en_menu.srm

This is a measurement tool.  Exceeding 73 is a reported verdict, not a process error;
the command fails only when a flow never reaches the rows it claims to measure.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES                   # noqa: E402
import menushot                                                   # noqa: E402
import menuvwf                                                    # noqa: E402
import dotfont                                                    # noqa: E402
from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES            # noqa: E402


ROW_DRAWER = (31, 0x40D8)
FONT_UPLOAD = (13, menuvwf.FONT_UPLOAD)
SHADOW = 0xC300
BGMAP = 0x9800
VERIFIED_CAPACITY = 72
# $43-$7B plus the census-unseen $87, $8B-$95 and $9A-$9D. The total is 73, but
# isolated $87 cannot satisfy capneed's four-tile minimum, so only 72 are allocatable.
# A row's tilemap cells
# increment their tile index, so one cap must fit wholly inside one run unless the
# eventual renderer gains a non-contiguous row map.
VERIFIED_RUNS = (57, 11, 4, 1)
ELIGIBLE_EXTRA = {0x7C, 0x7E, 0x7F}

# The installed control must still have the original drawer entry.  Hooking a patched
# ROM would observe the far routine before it changed the shadow and invalidate the raw
# liveness check below.
CONTROL_ENTRY = menuvwf.OLD_ENTRY

LONG_ROWS = [
    # The five widest REAL counter-bearing names under the approved Dot font.
    # Each paints into 11 tiles at a two-digit count; this is the actual bounded
    # proportional worst page, not the older representative 11/11/10/10/10 page.
    'Warehouse Pot[99]',
    'Stopgap Staff[99]',
    'Weakening Pot[99]',
    'Sorcery Staff[99]',
    'Unlucky Staff[99]',
]


def _off(bank, addr):
    return bank * 0x4000 + (addr - 0x4000)


CODE_TO_EN = {code: char for char, code in EN_CODES.items()}


def decode(codes):
    return ''.join(CODE_TO_EN.get(c, '<%02X>' % c) for c in codes)


def capneed(tiles):
    """The queue footprint used by tools/menuvwf.py, not merely visible tiles."""
    if tiles <= 4:
        return 4
    if tiles <= 8:
        return 8
    return tiles


class Metrics:
    """The tile extent the candidate renderer would publish for one row."""

    def __init__(self, font=None):
        self.font = font
        self.name = 'Dot Gothic painted extent' if font else 'uniform 6px advance'

    def tiles(self, codes):
        if self.font is None:
            return (6 * len(codes) + 7) >> 3
        pen = extent = 0
        for code in codes:
            ch = CODE_TO_EN.get(code)
            width = self.font.advance_code(code, unknown=8)
            if ch is None:
                ink_width = width
            else:
                span = dotfont.ink_span(self.font.glyphs[ch])
                ink_width = span[1] + 1 if span else width
            extent = pen + ink_width
            pen += width
        return (extent + 7) >> 3


def metrics_for_rom(rom):
    """Detect the approved Dot page; anything else remains the uniform control."""
    blob = open(rom, 'rb').read()
    font = dotfont.load_approved()
    approved = all(
        blob[FONT_BASE + code * GLYPH_BYTES:
             FONT_BASE + (code + 1) * GLYPH_BYTES] == font.glyphs[ch]
        for ch, code in EN_CODES.items())
    return Metrics(font if approved else None)


def packable(caps, runs=VERIFIED_RUNS):
    """Can indivisible contiguous row slices fit the measured free VRAM runs?"""
    caps = sorted(caps, reverse=True)
    free = sorted(runs, reverse=True)

    def place(i):
        if i == len(caps):
            return True
        cap = caps[i]
        tried = set()
        for j, room in enumerate(free):
            if room < cap or room in tried:
                continue
            tried.add(room)
            free[j] -= cap
            if place(i + 1):
                return True
            free[j] += cap
        return False

    return place(0)


def shape_of(mem):
    return tuple(mem[a] for a in range(0xC69A, 0xC69F))  # x,y,rows,width,flags


def prefix_for(shape):
    x, y, _rows, width, flags = shape
    if not flags & 2:
        return None
    if (x, y, width) == (0, 0, 5):
        return 1, 'main'
    if (x, y, width) == (0, 3, 18):
        return 2, 'items'
    if x == 13 and width == 5:
        return 1, 'action'
    return None


def read_row(pb, src, limit=40):
    if not 0xC000 <= src < 0xE000:
        return None
    out = []
    for at in range(src, min(src + limit, 0xE000)):
        b = pb.memory[at]
        if b == 0xFF:
            return out
        out.append(b)
    return None


class Draw:
    def __init__(self, ident, frame, epoch, dispatch, key, rownum, shape, kind,
                 prefix, raw, codes, metrics, synthetic=False):
        self.ident = ident
        self.frame = frame
        self.epoch = epoch
        self.dispatch = dispatch
        self.key = key
        self.rownum = rownum
        self.shape = shape
        self.kind = kind
        self.prefix = prefix
        self.raw = tuple(raw)
        self.codes = tuple(codes)
        self.synthetic = synthetic
        self.tiles = metrics.tiles(codes)
        self.cap = capneed(self.tiles)

    @property
    def text(self):
        return decode(self.codes)

    @property
    def text_cells(self):
        first = self.key + 1 + self.prefix
        return {first + i: code for i, code in enumerate(self.codes)}

    @property
    def vwf_cells(self):
        """Shadow positions the composed tile indices would occupy."""
        first = self.key + 1 + self.prefix
        return tuple(first + i for i in range(self.tiles))

    @property
    def span(self):
        # left border + descriptor width interior cells + right border
        return range(self.key, self.key + self.shape[3] + 2)


class Audit:
    def __init__(self, name, metrics):
        self.name = name
        self.metrics = metrics
        self.frame = 0
        self.epoch = 0
        self.dispatch = None
        self.draws = []
        self.owner = {}
        self.draw_by_id = {}
        # caps, full text tiles, reclaimable-tail tiles, frame, ((row, live-prefix),)
        self.visible_peak = (0, 0, 0, None, ())
        self.fresh_peak = (0, None, None, ())     # caps, frame, new row, old rows
        self.fragment_failure = (0, None, '', ()) # caps, frame, context, rows
        self.redraws = []
        self.problems = []
        self._batch = None

    def reset(self):
        self.epoch += 1
        self.owner.clear()
        self._batch = None

    def live_ids(self, pb=None, include_current=False):
        ids = set()
        for at, ident in self.owner.items():
            draw = self.draw_by_id.get(ident)
            if draw is None:
                continue
            code = draw.text_cells.get(at)
            if code is None:
                continue
            if draw.synthetic or pb is None:
                ids.add(ident)
                continue
            offset = at - SHADOW
            row, col = divmod(offset, 32)
            visible = (0 <= row < 18 and 0 <= col < 20
                       and pb.memory[at] == code
                       and pb.memory[BGMAP + offset] == code)
            if visible or (include_current and draw.frame == self.frame):
                ids.add(ident)
        return ids

    def live_rows(self, pb=None, include_current=False):
        return [self.draw_by_id[i]
                for i in sorted(self.live_ids(pb, include_current))]

    def _measure_visible(self, pb):
        rows = self.live_rows(pb)
        caps = sum(r.cap for r in rows)
        tiles = sum(r.tiles for r in rows)
        # An action box covers the RIGHT side of underlying item rows.  If closing it
        # redraws those rows, a future overlay-aware allocator could reclaim each fully
        # hidden slice tail.  Keep the prefix through the last still-owned VWF cell.
        tails = []
        for draw in rows:
            owned = [i for i, at in enumerate(draw.vwf_cells)
                     if self.owner.get(at) == draw.ident]
            tails.append(max(owned) + 1 if owned else 0)
        tail_tiles = sum(tails)
        if caps > self.visible_peak[0]:
            self.visible_peak = (caps, tiles, tail_tiles, self.frame,
                                 tuple(zip(rows, tails)))
        if not packable([r.cap for r in rows]) and caps > self.fragment_failure[0]:
            self.fragment_failure = (caps, self.frame, 'visible', tuple(rows))

    def prune_against_shadow(self, pb):
        # Do not delete an owner merely because the BG consumer has not copied its
        # freshly drawn shadow row yet.  live_ids() gates on BOTH maps dynamically,
        # so stale shadow bytes are excluded but become live once the real copy lands.
        self._measure_visible(pb)

    def add(self, pb, synthetic_rows=None):
        shape = shape_of(pb.memory)
        target = prefix_for(shape)
        key = pb.register_file.HL
        rownum = pb.register_file.D
        src = (pb.memory[0xC6A0] << 8) | pb.memory[0xC69F]
        raw = read_row(pb, src)

        # Every drawer row owns its rectangle, even when it is not VWF-eligible.  This
        # is how an overlay retires only the item cells it actually covers.
        if target is None:
            width = shape[3]
            for at in range(key, key + width + 2):
                self.owner[at] = None
            return

        prefix, kind = target
        synthetic = (synthetic_rows is not None and kind == 'items'
                     and 0 <= rownum < len(synthetic_rows))
        if synthetic:
            codes = [EN_CODES[c] for c in synthetic_rows[rownum]]
            raw = ([0x84, 0] if rownum == 0 else [0, 0]) + codes
        elif raw is None:
            for at in range(key, key + shape[3] + 2):
                self.owner[at] = None
            return
        marker_ok = (prefix == 1 and raw[:1] == [0]) or (
            prefix == 2 and len(raw) >= 2 and raw[0] in (0, 0x84, 0x86, 0x87)
            and raw[1] == 0)
        codes = raw[prefix:]
        tiles = self.metrics.tiles(codes)
        eligible = (marker_ok and 1 <= len(codes) <= 18
                    and all(c < 0x43 or c in ELIGIBLE_EXTRA for c in codes)
                    and tiles <= shape[3] - prefix)
        if not eligible:
            for at in range(key, key + shape[3] + 2):
                self.owner[at] = None
            return

        ident = len(self.draws)
        draw = Draw(ident, self.frame, self.epoch, self.dispatch, key, rownum,
                    shape, kind, prefix, raw, codes, self.metrics,
                    synthetic=synthetic)

        # A row allocated earlier in this same draw frame is resident even if the
        # game's shadow-to-BG consumer has not displayed it yet.
        old_rows = self.live_rows(pb, include_current=True)
        old_caps = sum(r.cap for r in old_rows)
        same = next((r for r in old_rows if r.key == key and r.codes == draw.codes
                     and r.cap >= draw.cap), None)
        fresh_rows = old_rows if same is not None else old_rows + [draw]
        fresh = sum(r.cap for r in fresh_rows)
        if fresh > self.fresh_peak[0]:
            self.fresh_peak = (fresh, self.frame, draw, tuple(old_rows))
        if (not packable([r.cap for r in fresh_rows])
                and fresh > self.fragment_failure[0]):
            self.fragment_failure = (fresh, self.frame, 'fresh-row', tuple(fresh_rows))

        self.draws.append(draw)
        self.draw_by_id[ident] = draw
        for at in draw.span:
            self.owner[at] = ident

        if rownum == 0 or self._batch is None or self._batch[0] != kind:
            self._batch = [kind, self.frame, []]
            self.redraws.append(self._batch)
        self._batch[2].append(draw)

    def report(self):
        print('\n%s' % self.name)
        print('-' * len(self.name))
        print('measurement  : %s' % self.metrics.name)
        # Consecutive duplicates are cursor/redraw traffic; print each distinct row set
        # once so the report stays readable while preserving measured capacities.
        seen = set()
        for kind, frame, rows in self.redraws:
            sig = (kind, tuple((r.rownum, r.text, r.cap) for r in rows))
            if sig in seen:
                continue
            seen.add(sig)
            text = '; '.join('%d:%s [%d/%d]' % (r.rownum, r.text, r.tiles, r.cap)
                             for r in rows)
            print('f%-4d %-6s %s' % (frame, kind, text))

        vcaps, vtiles, vtail, vframe, vrows = self.visible_peak
        fcaps, fframe, new, old = self.fresh_peak
        print('visible peak : %d cap tiles (%d carrying pixels), frame %s' %
              (vcaps, vtiles, vframe if vframe is not None else 'n/a'))
        if vrows:
            print('               ' + ', '.join('%s:%s=%d (prefix %d/%d)' %
                                                (r.kind, r.text, r.cap, tail, r.tiles)
                                                for r, tail in vrows))
            print('               overlay-tail lower bound: %d tile(s)' % vtail)
        print('fresh-row peak: %d cap tiles, frame %s%s' %
              (fcaps, fframe if fframe is not None else 'n/a',
               ' while composing %s:%s' % (new.kind, new.text) if new else ''))
        if old:
            print('               old visible: ' + ', '.join(
                '%s:%s=%d' % (r.kind, r.text, r.cap) for r in old))
        badcaps, badframe, badcontext, badrows = self.fragment_failure
        if badrows:
            print('run packing   : FAIL at frame %d (%s, %d tiles): %s' %
                  (badframe, badcontext, badcaps,
                   ' + '.join(str(r.cap) for r in badrows)))
        else:
            print('run packing   : all measured peaks fit runs 57 + 11 + 4 + 1')
        verdict = max(vcaps, fcaps)
        failed = verdict > VERIFIED_CAPACITY or bool(badrows)
        print('%d-usable-tile verdict: %s (aggregate lower bound %d%s)' %
              (VERIFIED_CAPACITY,
               'DOES NOT FIT' if failed else 'WITHIN MEASURED BOUND', verdict,
               '; contiguous-slice packing also fails' if badrows else ''))


def attach(pb, audit, synthetic_rows=None):
    pb.hook_register(FONT_UPLOAD[0], FONT_UPLOAD[1],
                     lambda _ctx: audit.reset(), None)
    pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH,
                     lambda _ctx: setattr(audit, 'dispatch', pb.register_file.A), None)
    def at_row(_ctx=None):
        rows = synthetic_rows() if synthetic_rows is not None else None
        audit.add(pb, rows)

    pb.hook_register(ROW_DRAWER[0], ROW_DRAWER[1], at_row, None)


def drive_state(PyBoy, rom, name, script, frames, metrics, rewrite_long=False):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(os.path.join(ROOT, 'saves', 'dungeon.state'), 'rb') as f:
        pb.load_state(f)
    audit = Audit(name, metrics)
    synthetic_seen = {'rows': set()}

    def synthetic_rows():
        if not rewrite_long or not 496 <= audit.frame <= 650:
            return None
        synthetic_seen['rows'].add(pb.register_file.D)
        return LONG_ROWS

    # A 17-character item plus its two raw prefix cells is wider than the original
    # fixed-cell drawer.  Mutating the staging block in a control ROM would therefore
    # make that drawer consume two logical rows at a time.  Model the measured calls'
    # text instead, while preserving their real destination geometry and overlay order.
    attach(pb, audit, synthetic_rows if rewrite_long else None)

    for frame in range(frames):
        audit.frame = frame
        for button in script.get(frame, ()):
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        audit.prune_against_shadow(pb)
    pb.stop(save=False)
    if rewrite_long and synthetic_seen['rows'] != set(range(5)):
        audit.problems.append('synthetic model saw item row calls %s, expected 0-4'
                              % sorted(synthetic_seen['rows']))
    return audit


def drive_saved(PyBoy, rom, ram, metrics):
    with tempfile.TemporaryDirectory(prefix='menuresidency-') as tmp:
        work = os.path.join(tmp, 'menu.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = Audit('Joey floor-7 save: real pages and action overlay', metrics)
        attach(pb, audit)
        script = {
            60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
            300: ('a',), 350: ('down',), 390: ('down',), 430: ('a',), 500: ('a',),
            1700: ('b',), 1780: ('a',), 1840: ('right',), 1900: ('right',),
            1960: ('left',), 2020: ('a',), 2080: ('b',),
        }
        for frame in range(2140):
            audit.frame = frame
            for button in script.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            audit.prune_against_shadow(pb)
        pb.stop(save=False)
        return audit


def verify_control(rom):
    blob = open(rom, 'rb').read()
    at = _off(ROW_DRAWER[0], ROW_DRAWER[1])
    got = blob[at:at + len(CONTROL_ENTRY)]
    if got != CONTROL_ENTRY:
        raise SystemExit('%s is not a --no-menuvwf control: 31:$40D8 is %s, want %s'
                         % (rom, got.hex(), CONTROL_ENTRY.hex()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom', help='--no-menuvwf control ROM')
    ap.add_argument('--ram', help='optional cartridge-RAM fixture for Joey save flow')
    args = ap.parse_args()
    verify_control(args.rom)
    if args.ram and not os.path.exists(args.ram):
        raise SystemExit('missing RAM fixture: %s' % args.ram)

    PyBoy = _import_pyboy()
    metrics = metrics_for_rom(args.rom)
    print('renderer model: %s' % metrics.name)
    ordinary = {
        60: ('b',), 120: ('a',), 180: ('right',), 240: ('right',),
        300: ('left',), 360: ('a',), 420: ('b',),
    }
    synthetic = {
        60: ('b',), 120: ('a',), 260: ('a',), 320: ('b',),
        380: ('b',), 400: ('b',), 440: ('b',), 500: ('a',),
        580: ('a',), 650: ('b',),
    }
    audits = [
        drive_state(PyBoy, args.rom, 'ordinary dungeon flow', ordinary, 480, metrics),
        drive_state(PyBoy, args.rom,
                    'synthetic packed page plus real action overlay', synthetic, 700,
                    metrics, rewrite_long=True),
    ]
    if args.ram:
        audits.append(drive_saved(PyBoy, args.rom, args.ram, metrics))

    problems = []
    for audit in audits:
        audit.report()
        if not audit.draws:
            problems.append('%s: no target rows observed' % audit.name)
        problems += ['%s: %s' % (audit.name, p) for p in audit.problems]
    if problems:
        print('\nMEASUREMENT PROBLEMS:')
        for problem in problems:
            print('  ' + problem)
    else:
        print('\ncoverage: ordinary + synthetic%s; raw drawer and shadow liveness observed'
              % (' + Joey save' if args.ram else ''))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
