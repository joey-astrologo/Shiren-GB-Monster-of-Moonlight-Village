#!/usr/bin/env python3
"""Plane-exact battery for proportional rows read directly from bank 31.

``menuromcensus.py`` establishes which box rows are ROM-sourced.  This tool checks the
other half of the contract on an integrated build: every descriptor marked by
``menuvwf.ROM_FLAG_BIT`` must take the proportional path, advance its source pointer
exactly, emit the expected shadow cells, and upload the approved Dot pixels to its
context-scoped static pool byte-for-byte in both planes.

The battery runs the ordinary dungeon menu, the blank-cart title/difficulty flow,
Joey's saved-menu flow, all 35 forced dispatcher entries, and category page two. It
also checks every LCD-on frame. If two simultaneously visible rows reuse a tile, or any
later writer changes a live tile's pixels, the earlier row no longer matches and the
run fails. This is the regression fixture for the co-residency bug found in the first
ROM-row prototype.

    python3 tools/menuromspill.py build/shiren_en.gb \
        --ram saves/shiren_en_menu.srm
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import extract                                                  # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuromcensus                                             # noqa: E402
import menushot                                                  # noqa: E402
import menuspill                                                 # noqa: E402
import menuvwf                                                   # noqa: E402


STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
SHADOW = 0xC300
BGMAP = 0x9800
VISIBLE_ROWS = 18
VISIBLE_COLS = 20
ROW_EPILOG = menuromcensus.ROW_EPILOG


def _off(bank, addr):
    return bank * 0x4000 + (addr - 0x4000)


def rom_slice(rows, row, boxes):
    """Return the static (base, cap) selected by menurow's ROM allocator."""
    if set(boxes) & {46, 50} and rows == 2 and 0 <= row < 2:
        return ((menuvwf.DIFFICULTY_POOL_BASE, menuvwf.DIFFICULTY_ROW0_CAP),
                (menuvwf.DIFFICULTY_POOL_BASE + menuvwf.DIFFICULTY_ROW0_CAP,
                 menuvwf.DIFFICULTY_ROW1_CAP))[row]
    if 48 in boxes and rows == 2 and 0 <= row < 2:
        return ((menuvwf.DIFFICULTY_ALT_ROW0_BASE, menuvwf.DIFFICULTY_ROW0_CAP),
                (menuvwf.DIFFICULTY_ALT_ROW1_BASE,
                 menuvwf.DIFFICULTY_ROW1_CAP))[row]
    if rows == 3 and 0 <= row < 3:
        return ((0xCB, 3), (0xCF, 4), (0xD3, 3))[row]
    if 41 in boxes and rows == 1 and row == 0:
        return menuvwf.ROM_RANK_HEADER_BASE, menuvwf.ROM_RANK_HEADER_CAP
    if 32 in boxes and rows == 1 and row == 0:
        return menuvwf.ROM_FEI_PROMPT_BASE, menuvwf.ROM_FEI_PROMPT_CAP
    if rows == 1 and row == 0:
        return menuvwf.ROM_ONE_BASE, 9
    if rows == 2 and 0 <= row < 2:
        if 24 in boxes:
            # Continue/New Game is still a ROM-backed row, but it is drawn over the
            # completed-Log Orochi badge at $CB-$CE.  Its exact screen-local allocator
            # therefore uses the confirmation slices rather than the generic $CB pool.
            return ((menuvwf.CONFIRM_POOL_ROWS[0], menuvwf.CONFIRM_POOL_CAPS[0]),
                    (menuvwf.CONFIRM_POOL_ROWS[1], menuvwf.CONFIRM_POOL_CAPS[1]))[row]
        if 47 in boxes:
            return ((menuvwf.RANK_CATEGORY_ROW0_BASE, 4),
                    (menuvwf.RANK_CATEGORY_ROW1_BASE, 8))[row]
        return ((menuvwf.ROM_POOL_BASE, 8),
                (menuvwf.ROM_POOL_BASE + 8, 11))[row]
    if rows == 5 and 0 <= row < 5:
        bases = (menuvwf.ROM_POOL_BASE, menuvwf.ROM_POOL_BASE + 4,
                 menuvwf.ROM_POOL_BASE + 8, menuvwf.ROM_POOL_BASE + 12,
                 menuvwf.ROM_POOL_BASE + 16)
        caps = (4, 4, 4, 4, 3)
        return bases[row], caps[row]
    raise ValueError('unsupported ROM row geometry %d/%d' % (row, rows))


class ExpectedRow:
    def __init__(self, boxes, key, src, next_src, row, shape, prefix, codes,
                 base, cap, pixels):
        self.boxes = tuple(boxes)
        self.key = key
        self.src = src
        self.next_src = next_src
        self.row = row
        self.shape = tuple(shape)
        self.prefix = tuple(prefix)
        self.codes = tuple(codes)
        self.base = base
        self.cap = cap
        self.pixels = tuple(bytes(tile) for tile in pixels)

    @property
    def text_at(self):
        return self.key + 1 + len(self.prefix)

    @property
    def tile_ids(self):
        return tuple(self.base + i for i in range(len(self.pixels)))

    @property
    def shadow_bytes(self):
        width = self.shape[3]
        padding = width - len(self.prefix) - len(self.pixels)
        if padding < 0:
            raise AssertionError('row exceeds its descriptor width')
        return (b'\xBE' + bytes(self.prefix) + bytes(self.tile_ids) +
                bytes(padding) + b'\xBF')


class Audit:
    def __init__(self, rom, profile, scenario):
        self.rom = rom
        self.profile = profile
        self.scenario = scenario
        self.descriptors = extract.box_descriptors(rom)
        self.pending = None
        self.active_boxes = ()
        self.rows = {}
        self.seen_boxes = set()
        self.calls = 0
        self.exact_checks = 0
        self.visible_checks = 0
        self.problems = []
        self.frame = 0

    def boxes_for(self, shape, src):
        x, y, _rows, width, flags = shape
        return tuple(d['id'] for d in self.descriptors
                     if (d['x'], d['y'], d['width'], d['flags'], d['text'])
                     == (x, y, width, flags, src))

    def parse_source(self, src, width, flags):
        at = _off(31, src)
        data = []
        long_source = bool(flags & menuvwf.ROM_LONG_SOURCE_BIT)
        limit = menuvwf.ROM_SOURCE_CAP if long_source else width
        terminated = False
        for _ in range(limit):
            value = self.rom[at]
            at += 1
            if value == 0xFF:
                terminated = True
                break
            data.append(value)
        if long_source and not terminated:
            raise ValueError('long ROM row at $%04X has no terminator within %d glyphs'
                             % (src, menuvwf.ROM_SOURCE_CAP))
        return data, 0x4000 + (at - 31 * 0x4000)

    def at_entry(self, pb):
        shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
        src = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        if not shape[4] & menuvwf.ROM_FLAG_BIT:
            return
        if self.pending is not None:
            self.problems.append('f%d: nested marked row call' % self.frame)
            return
        row = pb.register_file.D
        if row == 0:
            self.active_boxes = self.boxes_for(shape, src)
        boxes = self.active_boxes
        if not boxes:
            self.problems.append('f%d: marked row has no descriptor identity' % self.frame)
        if not 0x4000 <= src < 0x8000:
            self.problems.append('f%d: marked source is $%04X, not bank 31' %
                                 (self.frame, src))
            return
        data, next_src = self.parse_source(src, shape[3], shape[4])
        if not data:
            self.problems.append('f%d: marked row has no source cells' %
                                 self.frame)
            return
        base, cap = rom_slice(shape[2], row, boxes)
        keep_first = data[0] == 0 or bool(shape[4] & menuvwf.ROM_RAW_PREFIX_BIT)
        prefix = data[:1] if keep_first else ()
        codes = data[len(prefix):]
        pixels = menuspill.compose(codes, self.profile)
        if len(pixels) > cap:
            self.problems.append('f%d: box %s row %d paints %d tiles into cap %d' %
                                 (self.frame, '/'.join(map(str, boxes)), row,
                                  len(pixels), cap))
        self.pending = ExpectedRow(boxes, pb.register_file.HL, src, next_src, row,
                                   shape, prefix, codes, base, cap, pixels)

    def _check_pixels(self, pb, expected, label):
        problems = []
        for tile_index, want in enumerate(expected.pixels):
            tile = expected.base + tile_index
            at = menuspill.tile_data_addr(tile)
            got = bytes(pb.memory[at:at + 16])
            for plane in (0, 1):
                want_plane = want[plane::2]
                got_plane = got[plane::2]
                if want_plane != got_plane:
                    problems.append('%s: box %s row %d tile $%02X plane %d differs: '
                                    'want %s got %s' %
                                    (label, '/'.join(map(str, expected.boxes)),
                                     expected.row, tile, plane, want_plane.hex(),
                                     got_plane.hex()))
        return problems

    def at_epilog(self, pb):
        expected = self.pending
        if expected is None:
            return
        self.pending = None
        self.calls += 1
        self.seen_boxes.update(expected.boxes)
        got_next = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        if got_next != expected.next_src:
            self.problems.append('f%d: box %s row %d source ends at $%04X, expected '
                                 '$%04X' %
                                 (self.frame, '/'.join(map(str, expected.boxes)),
                                  expected.row, got_next, expected.next_src))
        want_shadow = expected.shadow_bytes
        got_shadow = bytes(pb.memory[expected.key:expected.key + len(want_shadow)])
        if got_shadow != want_shadow:
            self.problems.append('f%d: box %s row %d shadow differs: want %s got %s' %
                                 (self.frame, '/'.join(map(str, expected.boxes)),
                                  expected.row, want_shadow.hex(), got_shadow.hex()))
        self.problems += self._check_pixels(pb, expected, 'f%d exact' % self.frame)
        self.exact_checks += 1
        self.rows[expected.key] = expected

    def check_visible(self, pb):
        lcdc = pb.memory[0xFF40]
        if not lcdc & 0x80 or lcdc & 0x10 or not self.rows:
            return
        # The atomic title finalizer publishes from rborder immediately before the
        # ordinary row epilogue. PyBoy can therefore sample one complete visible frame
        # while that final row is still `pending` from this audit's point of view. Treat
        # it as the current owner at its key; otherwise the just-published difficulty
        # row is falsely blamed on the outgoing row for exactly one frame.
        current_rows = dict(self.rows)
        if self.pending is not None:
            current_rows[self.pending.key] = self.pending
        owners = {}
        for expected in current_rows.values():
            ids = expected.tile_ids
            shadow = bytes(pb.memory[expected.text_at:expected.text_at + len(ids)])
            if shadow != bytes(ids):
                continue
            first = expected.text_at - SHADOW
            visible = bytes(pb.memory[BGMAP + first:BGMAP + first + len(ids)])
            if visible != bytes(ids):
                continue
            for i, tile in enumerate(ids):
                owners[(first + i, tile)] = expected
            pixel_problems = self._check_pixels(pb, expected,
                                                'f%d visible' % self.frame)
            if pixel_problems and 24 in expected.boxes:
                # The native Continue transition clears this borrowed screen-local
                # slice shortly before replacing the obsolete popup map.  Those cells
                # are invisible by then: the complete rendered frame is uniformly
                # blank.  Accept only that exact all-zero retirement, never a partially
                # repainted row or a visible blank popup.
                zero = all(bytes(pb.memory[menuspill.tile_data_addr(tile):
                                           menuspill.tile_data_addr(tile) + 16]) ==
                           bytes(16) for tile in ids)
                extrema = pb.screen.image.getextrema() if zero else ()
                if zero and all(low == high for low, high in extrema):
                    pixel_problems = []
            if pixel_problems:
                self.problems += pixel_problems
            self.visible_checks += 1

        bg = bytes(pb.memory[BGMAP:BGMAP + 32 * VISIBLE_ROWS])
        shadow = bytes(pb.memory[SHADOW:SHADOW + 32 * VISIBLE_ROWS])
        owned_pool_tiles = {tile for _pos, tile in owners}
        for row in range(VISIBLE_ROWS):
            for col in range(VISIBLE_COLS):
                pos = 32 * row + col
                tile = bg[pos]
                static_pool = tile in owned_pool_tiles
                difficulty_active = any(set(expected.boxes) & {46, 48, 50}
                                        for expected in current_rows.values())
                difficulty_pool = difficulty_active and (
                    (menuvwf.DIFFICULTY_POOL_BASE <= tile <
                     menuvwf.DIFFICULTY_POOL_BASE + menuvwf.DIFFICULTY_ROW0_CAP +
                     menuvwf.DIFFICULTY_ROW1_CAP) or
                    (menuvwf.DIFFICULTY_ALT_ROW0_BASE <= tile <
                     menuvwf.DIFFICULTY_ALT_ROW0_BASE +
                     menuvwf.DIFFICULTY_ROW0_CAP) or
                    (menuvwf.DIFFICULTY_ALT_ROW1_BASE <= tile <
                     menuvwf.DIFFICULTY_ALT_ROW1_BASE +
                     menuvwf.DIFFICULTY_ROW1_CAP))
                if not (static_pool or difficulty_pool):
                    continue
                # Only exact row-owned IDs count as pool cells.  The saved-summary
                # double buffer and Fay prompt deliberately share a high-page lifetime
                # block sequentially; startspill/structspill own that transition, while
                # this audit rejects every simultaneous unowned reference.
                if shadow[pos] != tile:       # map publication is mid-transition
                    continue
                if (pos, tile) not in owners:
                    self.problems.append('f%d: visible pool tile $%02X at (%d,%d) has '
                                         'no live ROM-row owner' %
                                         (self.frame, tile, col, row))


def attach(pb, audit, force=None, force_memory=None, force_hooks=None):
    forced = {'done': False}

    def at_dispatch(_ctx=None):
        if force is not None and not forced['done']:
            for addr, value in (force_memory or {}).items():
                pb.memory[addr] = value
            pb.register_file.A = force
            forced['done'] = True

    pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH, at_dispatch, None)
    for (bank, addr), writes in (force_hooks or {}).items():
        def write_memory(_ctx=None, writes=writes):
            for target, value in writes.items():
                pb.memory[target] = value
        pb.hook_register(bank, addr, write_memory, None)
    pb.hook_register(menuvwf.FAR_BANK, audit.profile['entry'],
                     lambda _ctx: audit.at_entry(pb), None)
    pb.hook_register(ROW_EPILOG[0], ROW_EPILOG[1],
                     lambda _ctx: audit.at_epilog(pb), None)
    return forced


def run_frames(pb, audit, script, frames):
    for frame in range(frames):
        audit.frame = frame
        for button in script.get(frame, ()):
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        audit.check_visible(pb)


def drive_state(PyBoy, rom_path, profile, scenario, script, frames, force=None,
                force_memory=None, force_hooks=None):
    rom = open(rom_path, 'rb').read()
    pb = PyBoy(rom_path, window='null')
    pb.set_emulation_speed(0)
    with open(STATE, 'rb') as state:
        pb.load_state(state)
    audit = Audit(rom, profile, scenario)
    forced = attach(pb, audit, force, force_memory, force_hooks)
    run_frames(pb, audit, script, frames)
    pb.stop(save=False)
    if audit.pending is not None:
        audit.problems.append('marked row never reached its epilogue')
    if force is not None and not forced['done']:
        audit.problems.append('forced dispatcher never fired')
    return audit


def drive_saved(PyBoy, rom_path, profile, ram):
    rom = open(rom_path, 'rb').read()
    with tempfile.TemporaryDirectory(prefix='menuromspill-') as tmp:
        work = os.path.join(tmp, 'menu.gb')
        shutil.copyfile(rom_path, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = Audit(rom, profile, 'Joey floor-7 save')
        attach(pb, audit)
        script = {
            60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
            300: ('a',), 350: ('down',), 390: ('down',), 430: ('a',), 500: ('a',),
            1700: ('b',), 1780: ('a',), 1840: ('right',), 1900: ('right',),
            1960: ('left',), 2020: ('a',), 2080: ('b',),
        }
        run_frames(pb, audit, script, 2140)
        pb.stop(save=False)
        return audit


def drive_fresh_difficulty(PyBoy, rom_path, profile):
    """Blank-cart title flow, including all three live difficulty descriptions."""
    # Keep this deferred until after PyBoy's stdlib imports; tools/dis.py otherwise
    # shadows Python's dis module while importing namerun.
    sys.path.insert(0, HERE)
    from namerun import NAV_FRESH                              # noqa: E402
    sys.path.pop(0)
    rom = open(rom_path, 'rb').read()
    with tempfile.TemporaryDirectory(prefix='menuromspill-fresh-') as tmp:
        work = os.path.join(tmp, 'fresh.gb')
        shutil.copyfile(rom_path, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = Audit(rom, profile, 'fresh title/difficulty')
        attach(pb, audit)
        script = {frame: (button,) for frame, button in NAV_FRESH.items()
                  if frame < 1600}
        script[1520] = ('down',)
        script[1600] = ('down',)
        run_frames(pb, audit, script, 1700)
        pb.stop(save=False)
        return audit


def verify_build(rom_path):
    rom = open(rom_path, 'rb').read()
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('menuromspill: requires the Dot proportional renderer')
    descriptors = extract.box_descriptors(rom)
    marked = {d['id'] for d in descriptors if d['flags'] & menuvwf.ROM_FLAG_BIT}
    expected = set(menuvwf.ROM_BOXES)
    if marked != expected:
        raise SystemExit('menuromspill: marked boxes are %s, expected %s' %
                         (sorted(marked), sorted(expected)))
    unsafe = marked & {2, 30}
    if unsafe:
        raise SystemExit('menuromspill: composite/conflicting boxes marked: %s' %
                         sorted(unsafe))
    raw_prefix = {d['id'] for d in descriptors
                  if d['flags'] & menuvwf.ROM_RAW_PREFIX_BIT}
    # Box 5 is the dynamic Floor item header.  It deliberately reuses bit 5 to select
    # item mode with one raw cell, but is not a ROM_BOXES static-pool row and therefore
    # does not belong in ROM_RAW_PREFIX_BOXES' one-cell policy tuple.
    # Keep this expectation independent from menuvwf's policy tuple. Box 14 (`Items`)
    # must not re-enter the raw-prefix set: its forced-screen-1 mutation is synthetic,
    # and preserving that `I` visibly splits the ordinary heading into fixed + VWF text.
    # Box 17 (`Pot`) also composes its complete word: its former raw `$1A` P tile is
    # legitimately repainted by Status VWF before the Pot title becomes visible.
    expected_raw = {5} if not menuvwf.ROM_BOXES else {5, 8}
    if raw_prefix != expected_raw:
        raise SystemExit('menuromspill: raw-prefix boxes are %s, expected %s' %
                         (sorted(raw_prefix), sorted(expected_raw)))
    long_source = {d['id'] for d in descriptors
                   if d['flags'] & menuvwf.ROM_LONG_SOURCE_BIT}
    if long_source != set(menuvwf.ROM_LONG_SOURCE_BOXES):
        raise SystemExit('menuromspill: long-source boxes are %s, expected %s' %
                         (sorted(long_source), sorted(menuvwf.ROM_LONG_SOURCE_BOXES)))
    return profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', help='optional Joey floor-7 cartridge-RAM fixture')
    args = parser.parse_args()
    if args.ram and not os.path.exists(args.ram):
        raise SystemExit('missing RAM fixture: %s' % args.ram)

    if not menuvwf.ROM_BOXES:
        verify_build(args.rom)
        print('menuromspill: context-static ROM rows disabled; no unsafe pool to audit')
        return

    profile = verify_build(args.rom)
    PyBoy = _import_pyboy()
    audits = [drive_state(
        PyBoy, args.rom, profile, 'ordinary dungeon menu',
        {60: ('b',), 120: ('a',), 180: ('right',), 240: ('right',),
         300: ('left',), 360: ('a',), 420: ('b',)}, 480)]
    audits.append(drive_fresh_difficulty(PyBoy, args.rom, profile))
    if args.ram:
        audits.append(drive_saved(PyBoy, args.rom, profile, args.ram))
    for index in range(menushot.TABLE_LEN):
        audits.append(drive_state(PyBoy, args.rom, profile,
                                  'forced screen %02d' % index,
                                  {60: ('b',)}, 150, force=index))
    # Screen 1/11 choose box 18 (Floor) only when the current floor-item slot is empty.
    # Let the fixture stage its valid item record first, then force the real branch at
    # 4:$495F; setting C6AC before 4:$5AFD would instead ask the fixture for an absent
    # C5FF sentinel record and stall before either header can be audited.
    audits.append(drive_state(PyBoy, args.rom, profile,
                              'forced empty Floor-item screen', {60: ('b',)}, 150,
                              force=1,
                              force_hooks={(4, 0x495F): {0xC6AC: 0xFF}}))
    # Screen 21 returns box 24 only when the selected save-entry flag at
    # C549 + swap(C6DD) + $0E is clear. Exercise that genuine table branch explicitly.
    audits.append(drive_state(PyBoy, args.rom, profile,
                              'forced continue-from-village screen', {60: ('b',)}, 150,
                              force=21, force_memory={0xC6DD: 0, 0xC557: 0}))
    audits.append(drive_state(PyBoy, args.rom, profile,
                              'forced screen 27 page 1', {60: ('b',)}, 150,
                              force=27, force_memory={0xC6E3: 1}))

    seen = set().union(*(audit.seen_boxes for audit in audits))
    problems = ['%s: %s' % (audit.scenario, problem)
                for audit in audits for problem in audit.problems]
    missing = set(menuvwf.ROM_BOXES) - seen
    if missing:
        problems.append('marked boxes never drawn: %s' % sorted(missing))
    calls = sum(audit.calls for audit in audits)
    exact = sum(audit.exact_checks for audit in audits)
    visible = sum(audit.visible_checks for audit in audits)
    if not calls or not exact or not visible:
        problems.append('coverage is empty: calls=%d exact=%d visible=%d' %
                        (calls, exact, visible))
    for problem in problems[:16]:
        print('  ' + problem)
    print('menuromspill: %d marked row call(s), %d epilogue-exact check(s), '
          '%d live-frame plane check(s), boxes %s, %d problem(s)' %
          (calls, exact, visible, ' '.join(map(str, sorted(seen))), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
