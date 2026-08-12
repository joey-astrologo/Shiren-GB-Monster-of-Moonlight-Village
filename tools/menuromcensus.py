#!/usr/bin/env python3
"""Measure ROM- and WRAM-sourced rows reaching bank 31's original menu drawer.

This is the prerequisite for extending ``menuvwf`` beyond its WRAM-staged allowlist.
It hooks the untouched drawer in a ``--no-menuvwf`` control, records the source pointer
before and after every real row draw, and reads the completed shadow row at the epilogue.
That makes DTE expansion, exact-width unterminated rows, dynamic row counts and leading
layout cells observations rather than guesses.

Coverage combines the ordinary dungeon flow, Joey's saved inventory, all 35 forced
bank-4 dispatcher entries, the second page of dispatch 27's category table, and a blank
cartridge's real title -> New Log -> difficulty route.  The latter walks Easy, Normal and
Hard without confirming one, so all three lower explanation boxes are observed in their
actual co-resident context with box 29. The forced path changes only the dispatcher
index/page byte; the real screen routine, box descriptors, DTE hook and row drawer still
do all rendering.

    python3 tools/menuromcensus.py build/menurom_control.gb \
        --ram saves/shiren_en_menu.srm

The command fails only if the ROM is not an original-drawer control or a claimed flow
never reaches the drawer.  Finding rows which are not yet VWF candidates is expected.
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

import dte_rom                                                  # noqa: E402
import extract                                                  # noqa: E402
import menushot                                                 # noqa: E402
import menuvwf                                                  # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                  # noqa: E402
from latinfont import EN_CODES                                  # noqa: E402


ROW_ENTRY = (31, 0x40D8)
ROW_EPILOG = (31, 0x411F)
STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
SHADOW = 0xC300
CODE_TO_EN = {code: char for char, code in EN_CODES.items()}
DTE_CODES = set(dte_rom.DTE_CODES)


def _off(bank, addr):
    return bank * 0x4000 + (addr - 0x4000)


def source_kind(addr):
    if 0x4000 <= addr < 0x8000:
        return 'ROM31'
    if 0xC000 <= addr < 0xE000:
        return 'WRAM'
    if 0xA000 <= addr < 0xC000:
        return 'SRAM'
    return '$%04X' % addr


def render(codes):
    """Readable but lossless-ish form of a completed fixed-cell interior."""
    out = []
    for code in codes:
        if code in CODE_TO_EN:
            out.append(CODE_TO_EN[code])
        elif code == 0xB6:
            out.append('|')
        elif code == 0xC0:
            out.append('<dakuten>')
        elif code == 0xC1:
            out.append('<handakuten>')
        else:
            out.append('<%02X>' % code)
    return ''.join(out).rstrip()


class Row:
    def __init__(self, scenario, frame, dispatch, boxes, rownum, shape, key, src,
                 next_src, raw, interior):
        self.scenario = scenario
        self.frame = frame
        self.dispatch = dispatch
        self.boxes = tuple(boxes)
        self.rownum = rownum
        self.shape = tuple(shape)
        self.key = key
        self.src = src
        self.next_src = next_src
        self.raw = tuple(raw)
        self.interior = tuple(interior)
        # Filled at the end of the outer emulator frame.  The drawer epilogue is the
        # cleanest source measurement, but menu code can still overwrite cursor or
        # dynamic cells later in that same frame.  Keeping both snapshots tells us
        # which apparent layout cells truly have to remain independently writable.
        self.post_frame = None

    @property
    def kind(self):
        return source_kind(self.src)

    @property
    def text(self):
        return render(self.interior)

    @property
    def dte(self):
        return any(code in DTE_CODES for code in self.raw)

    @property
    def signature(self):
        return (self.dispatch, self.boxes, self.rownum, self.shape, self.src,
                self.next_src, self.raw, self.interior)

    @property
    def changed_cells(self):
        if self.post_frame is None:
            return ()
        return tuple(i for i, (before, after) in
                     enumerate(zip(self.interior, self.post_frame)) if before != after)


class Audit:
    def __init__(self, rom, scenario):
        self.rom = rom
        self.scenario = scenario
        self.frame = 0
        self.dispatch = None
        self.pending = None
        self.rows = []
        self.problems = []
        self.active_boxes = ()
        self.descriptors = extract.box_descriptors(rom)

    def boxes_for(self, shape, src):
        x, y, rows, width, flags = shape
        # bit-1 boxes replace their row count at runtime; all other descriptor fields
        # remain exact.  Duplicate aliases are retained rather than guessed apart.
        return tuple(d['id'] for d in self.descriptors
                     if (d['x'], d['y'], d['width'], d['flags'], d['text'])
                     == (x, y, width, flags, src))

    def at_dispatch(self, pb):
        self.dispatch = pb.register_file.A

    def at_entry(self, pb):
        if self.pending is not None:
            self.problems.append('nested/unfinished row at frame %d' % self.frame)
        shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
        src = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        rownum = pb.register_file.D
        if rownum == 0:
            self.active_boxes = self.boxes_for(shape, src)
        self.pending = (self.frame, self.dispatch, self.active_boxes, rownum,
                        shape, pb.register_file.HL, src)

    def at_epilog(self, pb):
        if self.pending is None:
            self.problems.append('row epilogue without entry at frame %d' % self.frame)
            return
        frame, dispatch, boxes, rownum, shape, key, src = self.pending
        self.pending = None
        next_src = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        width = shape[3]
        interior = bytes(pb.memory[key + 1:key + 1 + width])
        # The original drawer advances monotonically within one address arena.  If it
        # ever does not, preserve the addresses and report an empty raw slice rather
        # than reading an invented wraparound range.
        raw = (bytes(pb.memory[src:next_src])
               if src <= next_src and next_src - src <= 0x100 else b'')
        self.rows.append(Row(self.scenario, frame, dispatch, boxes, rownum, shape,
                             key, src, next_src, raw, interior))

    def at_frame_end(self, pb):
        """Capture writes made after each row drawer returned in this CPU frame."""
        for row in self.rows:
            if row.frame == self.frame and row.post_frame is None:
                width = row.shape[3]
                row.post_frame = tuple(pb.memory[row.key + 1:row.key + 1 + width])


def attach(pb, audit, force=None, forced=None, force_memory=None):
    def at_dispatch(_ctx=None):
        audit.at_dispatch(pb)
        if force is not None and not forced['done']:
            for addr, value in (force_memory or {}).items():
                pb.memory[addr] = value
            pb.register_file.A = force
            audit.dispatch = force
            forced['done'] = True

    pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH, at_dispatch, None)
    pb.hook_register(ROW_ENTRY[0], ROW_ENTRY[1],
                     lambda _ctx: audit.at_entry(pb), None)
    pb.hook_register(ROW_EPILOG[0], ROW_EPILOG[1],
                     lambda _ctx: audit.at_epilog(pb), None)


def drive_state(PyBoy, rom_path, scenario, script, frames, force=None,
                force_memory=None):
    blob = open(rom_path, 'rb').read()
    pb = PyBoy(rom_path, window='null')
    pb.set_emulation_speed(0)
    with open(STATE, 'rb') as f:
        pb.load_state(f)
    forced = {'done': False}
    audit = Audit(blob, scenario)
    attach(pb, audit, force=force, forced=forced, force_memory=force_memory)

    for frame in range(frames):
        audit.frame = frame
        for button in script.get(frame, ()):
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        audit.at_frame_end(pb)
    pb.stop(save=False)
    if force is not None and not forced['done']:
        audit.problems.append('forced dispatcher never fired')
    # Several dispatcher entries are context-dependent transitions and legitimately
    # draw no box when forced from the dungeon fixture.  Reaching the dispatcher is the
    # coverage claim in that mode; ordinary/saved flows do claim a drawer result.
    if not audit.rows and force is None:
        audit.problems.append('drawer never reached')
    return audit


def drive_saved(PyBoy, rom_path, ram):
    blob = open(rom_path, 'rb').read()
    with tempfile.TemporaryDirectory(prefix='menuromcensus-') as tmp:
        work = os.path.join(tmp, 'menu.gb')
        shutil.copyfile(rom_path, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = Audit(blob, 'Joey floor-7 save')
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
            audit.at_frame_end(pb)
        pb.stop(save=False)
        if not audit.rows:
            audit.problems.append('drawer never reached')
        return audit


def drive_fresh_difficulty(PyBoy, rom_path):
    """Blank-cart title flow, including all three live difficulty descriptions."""
    # PyBoy must be imported before tools/dis.py can shadow the stdlib `dis`; defer the
    # route import for the same reason as mkstate.new_log_at_the_sign().
    sys.path.insert(0, HERE)
    from namerun import NAV_FRESH                              # noqa: E402
    sys.path.pop(0)
    blob = open(rom_path, 'rb').read()
    with tempfile.TemporaryDirectory(prefix='menuromcensus-fresh-') as tmp:
        work = os.path.join(tmp, 'fresh.gb')
        shutil.copyfile(rom_path, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = Audit(blob, 'fresh title/difficulty')
        attach(pb, audit)

        # NAV_FRESH reaches Easy at f1600 by pressing A.  Stop short of that final A;
        # instead move the cursor twice so the real screen redraws Normal and Hard and
        # selects boxes 48 and 50 through the game's own state.
        script = {frame: (button,) for frame, button in NAV_FRESH.items()
                  if frame < 1600}
        script[1520] = ('down',)
        script[1600] = ('down',)
        for frame in range(1700):
            audit.frame = frame
            for button in script.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            audit.at_frame_end(pb)
        pb.stop(save=False)
        if not audit.rows:
            audit.problems.append('drawer never reached')
        return audit


def report(audits, all_sources=False):
    unique = collections.OrderedDict()
    examples = collections.defaultdict(list)
    mutation_examples = collections.defaultdict(list)
    for audit in audits:
        for row in audit.rows:
            unique.setdefault(row.signature, row)
            ex = examples[row.signature]
            tag = '%s f%d' % (row.scenario, row.frame)
            if tag not in ex and len(ex) < 3:
                ex.append(tag)
            if row.changed_cells:
                mutation = (tag, row.post_frame, row.changed_cells)
                if mutation not in mutation_examples[row.signature]:
                    mutation_examples[row.signature].append(mutation)

    all_rows = list(unique.values())
    rows = all_rows if all_sources else [row for row in all_rows if row.kind == 'ROM31']
    rows.sort(key=lambda r: (r.kind != 'ROM31', r.boxes or (999,), r.rownum,
                             r.src, r.scenario))
    print('unique live rows: %d ROM31 shown (%d WRAM and %d other observed%s)' %
          (sum(r.kind == 'ROM31' for r in all_rows),
           sum(r.kind == 'WRAM' for r in all_rows),
           sum(r.kind not in ('ROM31', 'WRAM') for r in all_rows),
           ', included below' if all_sources else '; use --all-sources to list'))
    print('src        next       box   row  shape x,y,n,w,fl  dte  text')
    print('---------- ---------- ----- ---- ----------------- ---- -------------------------')
    for row in rows:
        box = '/'.join(str(i) for i in row.boxes) if row.boxes else '?'
        shape = '%d,%d,%d,%d,%02X' % row.shape
        print('%-10s $%04X     %-5s %-4d %-17s %-4s %r' %
              (('$%04X' % row.src) + '/' + row.kind, row.next_src, box, row.rownum,
               shape, 'yes' if row.dte else 'no', row.text))
        print('             raw %-47s seen %s' %
              (' '.join('%02X' % b for b in row.raw), ', '.join(examples[row.signature])))
        for tag, post_frame, changed_cells in mutation_examples[row.signature][:3]:
            print('             post %-46r changed cells %-8s seen %s' %
                  (render(post_frame), ' '.join(str(i) for i in changed_cells), tag))

    rom_boxes = sorted({box for row in rows if row.kind == 'ROM31' for box in row.boxes})
    wram_boxes = sorted({box for row in rows if row.kind == 'WRAM' for box in row.boxes})
    print('\nROM box ids observed : %s' % (' '.join(map(str, rom_boxes)) or '(unmapped)'))
    print('WRAM box ids observed: %s' % (' '.join(map(str, wram_boxes)) or '(unmapped)'))
    print('coverage scenarios   : %d; drawer calls %d; unique signatures %d' %
          (len(audits), sum(len(a.rows) for a in audits), len(all_rows)))
    mutations = [row for audit in audits for row in audit.rows if row.changed_cells]
    print('same-frame mutations : %d row calls (cursor, dynamic insert, or teardown)' %
          len(mutations))
    dark = [a.scenario for a in audits
            if a.scenario.startswith('forced screen ') and not a.rows]
    if dark:
        print('forced entries with no row draw: %s' %
              ', '.join(name.rsplit(' ', 1)[-1] for name in dark))


def verify_control(path):
    blob = open(path, 'rb').read()
    at = _off(ROW_ENTRY[0], ROW_ENTRY[1])
    got = blob[at:at + len(menuvwf.OLD_ENTRY)]
    if got != menuvwf.OLD_ENTRY:
        raise SystemExit('%s is not a --no-menuvwf control at 31:$40D8' % path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', help='fresh --dot-font --no-menuvwf control ROM')
    parser.add_argument('--ram', help='optional Joey menu cartridge-RAM fixture')
    parser.add_argument('--all-sources', action='store_true',
                        help='also list the already-censused WRAM-staged rows')
    args = parser.parse_args()
    verify_control(args.rom)
    if args.ram and not os.path.exists(args.ram):
        raise SystemExit('missing RAM fixture: %s' % args.ram)

    PyBoy = _import_pyboy()
    audits = [drive_state(
        PyBoy, args.rom, 'ordinary dungeon menu',
        {60: ('b',), 120: ('a',), 180: ('right',), 240: ('right',),
         300: ('left',), 360: ('a',), 420: ('b',)}, 480)]
    audits.append(drive_fresh_difficulty(PyBoy, args.rom))
    if args.ram:
        audits.append(drive_saved(PyBoy, args.rom, args.ram))
    # The first dispatcher arrival is the forced target.  Stop before a second button
    # can open a normal item screen and contaminate every target with box 14.
    force_script = {60: ('b',)}
    for idx in range(menushot.TABLE_LEN):
        audits.append(drive_state(PyBoy, args.rom, 'forced screen %02d' % idx,
                                  force_script, 150, force=idx))
    # Dispatcher 27 selects box 33 or 34 from this page byte.  The ordinary forced
    # sweep sees page zero only; set it at the dispatcher boundary so the real routine
    # draws the second five-category table as well.
    audits.append(drive_state(PyBoy, args.rom, 'forced screen 27 page 1',
                              force_script, 150, force=27,
                              force_memory={0xC6E3: 1}))

    report(audits, all_sources=args.all_sources)
    problems = ['%s: %s' % (audit.scenario, problem)
                for audit in audits for problem in audit.problems]
    if problems:
        print('\nMEASUREMENT PROBLEMS:')
        for problem in problems:
            print('  ' + problem)
    else:
        print('\nmeasurement complete: every claimed flow reached the original drawer')
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
