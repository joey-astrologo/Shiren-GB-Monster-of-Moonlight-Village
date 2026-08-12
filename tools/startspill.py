#!/usr/bin/env python3
"""Plane-exact battery for title, difficulty-adjacent, and save-log VWF rows.

The original menu battery starts from a dungeon state, so it cannot prove the WRAM
rows drawn before gameplay.  This test boots both a blank cartridge and save-backed
cartridges, hooks the integrated menu renderer, and verifies every supported start-flow
row at the drawer epilogue: record ownership, shadow cells, and both VRAM bitplanes. It
must exercise all three erase-confirmation logs separately: Dot's narrow ``1`` fits a
different physical tile count from ``2``/``3``, which is how Log 1 once hid a raw fallback
on Log 2 and Log 3. With ``--wide-ram`` it also opens the Rank/Pass popup so box 45 cannot
remain outside the allowlist unnoticed.

    python3 tools/startspill.py build/shiren_en.gb \
        --ram saves/shiren_en_menu.srm \
        --wide-ram saves/shiren_en_ranking_repaired.srm
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
import menuromcensus                                           # noqa: E402
import menuspill                                               # noqa: E402
import menuvwf                                                 # noqa: E402


TARGETS = {
    # label: (x, y, allowed row counts, width, low flag bits, raw source cells)
    'title': (0, 1, set(range(3, 9)), 11, 0x02, 1),
    'selector': (5, 9, {1, 2, 3}, 9, 0x02, 1),
    'summary': (4, 4, {3}, 14, 0x04, 0),
    'confirm': (3, 7, {2}, 15, 0x00, 0),
    'rankpass': (3, 8, {2}, 6, 0x02, 1),
}
ROW_EPILOG = menuromcensus.ROW_EPILOG
SHADOW = 0xC300
BGMAP = 0x9800
VISIBLE_COLS = 20
VISIBLE_ROWS = 18


class Pending:
    def __init__(self, label, key, row, shape, source, raw, cells):
        self.label = label
        self.key = key
        self.row = row
        self.shape = shape
        self.source = source
        self.raw = raw
        self.cells = tuple(cells)


class Audit:
    def __init__(self, profile, scenario):
        self.profile = profile
        self.scenario = scenario
        self.pending = None
        self.frame = 0
        self.calls = collections.Counter()
        self.exact = 0
        self.visible = 0
        self.problems = []
        self.live = {}
        self.reported_collisions = set()

    @staticmethod
    def classify(shape):
        x, y, rows, width, flags = shape
        for label, (want_x, want_y, allowed_rows, want_width, want_flags, raw) in \
                TARGETS.items():
            if ((x, y, width, flags & 0x1F) ==
                    (want_x, want_y, want_width, want_flags) and
                    rows in allowed_rows):
                return label, raw
        return None, None

    def at_entry(self, pb):
        shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
        label, raw = self.classify(shape)
        if (not menuvwf.CONTEXT_STATIC_ROWS and
                label in ('summary', 'confirm', 'rankpass')):
            return
        if label is None:
            return
        if self.pending is not None:
            self.problems.append('f%d: nested target row call' % self.frame)
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        # A save-summary place row longer than its 14-cell legacy stride is copied to
        # private staging by the row-0 helper. Row 1 redirects there immediately after
        # this entry hook; audit the same complete source the renderer will consume.
        summary_redirect = (label == 'summary' and pb.register_file.D == 1 and
                            pb.memory[0xC647] == 1)
        if summary_redirect:
            source = 0xC648
        if not 0xC616 <= source < 0xC69A:
            self.problems.append('f%d: %s source $%04X is outside staging' %
                                 (self.frame, label, source))
            return
        cells = []
        # Summary and erase-confirmation row 0 are one 16-character logical header.
        # The legacy fixed-cell drawer split it at the 14/15-cell descriptor width;
        # proportional rendering is expected to consume the whole header terminator.
        # Title rows use the proportional renderer's 18-source-cell staging contract,
        # not their 11-cell physical width.  Fay's Puzzles is the deliberate regression:
        # 13 source glyphs compose into eight tiles and fit the same box.
        source_cells = (19 if summary_redirect else
                        8 if label == 'rankpass' and pb.register_file.D == 1 else
                        18 if label == 'title' else
                        16 if label in ('summary', 'confirm') and
                        pb.register_file.D == 0 else shape[3])
        for at in range(source, source + source_cells):
            value = pb.memory[at]
            if value == 0xFF:
                break
            cells.append(value)
        if label == 'summary' and pb.register_file.D == 1 and 0xB4 in cells:
            self.problems.append('f%d: summary floor row retained native $B4 instead of '
                                 'the English F glyph' % self.frame)
        if len(cells) <= raw:
            # Empty confirmation rows are intentionally left raw.
            return
        self.calls[label] += 1
        # Once the game starts redrawing this destination, its outgoing pixels are no
        # longer a settled-screen claim.  The exact epilogue check below reinstates the
        # row only after both queue passes and the new shadow cells are complete.
        self.live.pop(pb.register_file.HL, None)
        self.pending = Pending(label, pb.register_file.HL, pb.register_file.D,
                               shape, source, raw, cells)
        if os.environ.get('STARTSPILL_CENSUS') and label in ('confirm', 'rankpass'):
            self.trace_tile_census(pb, self.pending)

    def trace_tile_census(self, pb, pending):
        """Print settled visible references outside the row about to be replaced."""
        first = pending.key + 1 - SHADOW
        ignored = set(range(first, first + pending.shape[3]))
        references = collections.defaultdict(list)
        for row in range(VISIBLE_ROWS):
            for col in range(VISIBLE_COLS):
                pos = 32 * row + col
                if pos in ignored:
                    continue
                tile = pb.memory[BGMAP + pos]
                if pb.memory[SHADOW + pos] == tile:
                    references[tile].append((col, row))
        interesting = [tile for tile in range(0x80, 0xA0) if tile in references]
        print('census %-24s f%-4d %s r%d scroll=(%d,%d) refs80-9f=%s records=%s' %
              (self.scenario, self.frame, pending.label, pending.row,
               pb.memory[0xFF43], pb.memory[0xFF42],
               ' '.join('$%02X:%s' %
                        (tile, ','.join('%d/%d' % pos for pos in references[tile]))
                        for tile in interesting) or '-',
               menuspill.records(pb, self.profile)))

    def at_epilog(self, pb):
        pending = self.pending
        if pending is None:
            return
        self.pending = None
        problems_before = len(self.problems)
        static = pending.label in ('summary', 'confirm', 'rankpass')
        if static:
            if pending.label == 'rankpass':
                base = menuvwf.CONFIRM_POOL_ROWS[pending.row]
                cap = menuvwf.RANKPASS_POOL_CAPS[pending.row]
            else:
                digit = pb.memory[0xC616]
                if digit not in (2, 3, 4):
                    self.problems.append('f%d: %s has invalid staged Log digit $%02X' %
                                         (self.frame, pending.label, digit))
                    return
                selected = (menuvwf.SUMMARY_ALT_POOL_ROWS if digit == 3 else
                            menuvwf.SUMMARY_POOL_ROWS)
            if pending.label == 'summary':
                base = selected[pending.row]
                cap = menuvwf.SUMMARY_POOL_CAPS[pending.row]
            elif pending.label == 'confirm':
                base = menuvwf.CONFIRM_POOL_ROWS[pending.row]
                cap = menuvwf.CONFIRM_POOL_CAPS[pending.row]
            key, raw = pending.key, pending.raw
        else:
            recs = [record for record in menuspill.records(pb, self.profile)
                    if record[0] == pending.key]
            if not recs:
                self.problems.append('f%d: %s row %d did not allocate a VWF record' %
                                     (self.frame, pending.label, pending.row))
                return
            key, base, cap, raw = recs[-1]
        if os.environ.get('STARTSPILL_TRACE'):
            print('trace %-24s f%-4d %s r%d key=$%04X source=$%04X base=$%02X cap=%d '
                  'records=%d cells=%s' %
                  (self.scenario, self.frame, pending.label, pending.row, key,
                   pending.source, base, cap, len(menuspill.records(pb, self.profile)),
                   bytes(pending.cells).hex()))
        if raw != pending.raw:
            self.problems.append('f%d: %s row %d raw prefix is %d, expected %d' %
                                 (self.frame, pending.label, pending.row,
                                  raw, pending.raw))
            return
        codes = pending.cells[raw:]
        try:
            pixels = menuspill.compose(codes, self.profile)
        except (AssertionError, KeyError) as error:
            self.problems.append('f%d: %s row %d cannot be recomposed: %s' %
                                 (self.frame, pending.label, pending.row, error))
            return
        if len(pixels) > cap:
            self.problems.append('f%d: %s row %d paints %d tiles into cap %d' %
                                 (self.frame, pending.label, pending.row,
                                  len(pixels), cap))
            return
        prefix = bytes(pending.cells[:raw])
        tile_ids = bytes(base + i for i in range(len(pixels)))
        padding = pending.shape[3] - raw - len(pixels)
        if padding < 0:
            self.problems.append('f%d: %s row %d exceeds its %d-cell box' %
                                 (self.frame, pending.label, pending.row,
                                  pending.shape[3]))
            return
        want_shadow = b'\xBE' + prefix + tile_ids + bytes(padding) + b'\xBF'
        got_shadow = bytes(pb.memory[key:key + len(want_shadow)])
        if got_shadow != want_shadow:
            self.problems.append('f%d: %s row %d shadow differs: want %s got %s' %
                                 (self.frame, pending.label, pending.row,
                                  want_shadow.hex(), got_shadow.hex()))
        for index, want in enumerate(pixels):
            tile = base + index
            at = menuspill.tile_data_addr(tile)
            got = bytes(pb.memory[at:at + 16])
            for plane in (0, 1):
                if bytes(want[plane::2]) != got[plane::2]:
                    self.problems.append(
                        'f%d: %s row %d tile $%02X plane %d differs' %
                        (self.frame, pending.label, pending.row, tile, plane))
        if len(self.problems) == problems_before:
            self.exact += 1
            self.live[key] = (pending.label, tile_ids, pixels, raw, not static)

    def check_visible(self, pb):
        static_owners = {}
        static_tiles = set()
        for key, (_label, tile_ids, pixels, raw, recorded) in self.live.items():
            if not tile_ids:
                continue
            if recorded:
                record = next((record for record in menuspill.records(pb, self.profile)
                               if record[0] == key), None)
                if record is None:
                    continue
                _key, _base, _cap, raw = record
            first = key + 1 + raw - SHADOW
            if bytes(pb.memory[SHADOW + first:SHADOW + first + len(tile_ids)]) != tile_ids:
                continue
            if bytes(pb.memory[0x9800 + first:0x9800 + first + len(tile_ids)]) != tile_ids:
                continue
            for index, want in enumerate(pixels):
                at = menuspill.tile_data_addr(tile_ids[index])
                got = bytes(pb.memory[at:at + 16])
                if got != bytes(want):
                    self.problems.append(
                        'f%d: visible %s row at $%04X tile $%02X was overwritten: '
                        'want %s got %s' %
                        (self.frame, _label, key, tile_ids[index],
                         bytes(want).hex(), got.hex()))
                    break
            self.visible += 1
            if not recorded:
                first = key + 1 + raw - SHADOW
                for index, tile in enumerate(tile_ids):
                    static_owners[(first + index, tile)] = _label
                    static_tiles.add(tile)

        # Summary allocation deliberately reserves the complete $DE-$F8 range. Check
        # even currently unused tiles for owners *outside* the three summary interiors.
        # Inside cells may briefly retain the outgoing row while its replacement is being
        # composed, so the ordinary exact-owner check remains the authority there.
        summary_active = any(label == 'summary'
                             for label, _tiles, _pixels, _raw, _recorded
                             in self.live.values())
        summary_pool = set(range(menuvwf.SUMMARY_POOL_ROWS[0],
                                 menuvwf.SUMMARY_POOL_ROWS[0] +
                                 sum(menuvwf.SUMMARY_POOL_CAPS)))
        summary_cells = {(col, row) for row in (5, 7, 9)
                         for col in range(5, 19)}

        # Static start-flow slices are deliberately outside the ordinary allocator.
        # Prove that repainting one cannot alter another settled on-screen cell that
        # happens to carry the same native tile ID.
        for row in range(VISIBLE_ROWS):
            for col in range(VISIBLE_COLS):
                pos = 32 * row + col
                tile = pb.memory[BGMAP + pos]
                if (summary_active and tile in summary_pool and
                        (col, row) not in summary_cells):
                    collision = ('summary', pos, tile)
                    if collision not in self.reported_collisions:
                        self.reported_collisions.add(collision)
                        self.problems.append(
                            'f%d: reserved summary tile $%02X has outside owner at '
                            '(%d,%d)' % (self.frame, tile, col, row))
                if tile not in static_tiles or pb.memory[SHADOW + pos] != tile:
                    continue
                if (pos, tile) in static_owners:
                    continue
                collision = (pos, tile)
                if collision in self.reported_collisions:
                    continue
                self.reported_collisions.add(collision)
                self.problems.append(
                    'f%d: static pool tile $%02X at (%d,%d) has no target-row owner' %
                    (self.frame, tile, col, row))


def run_scenario(PyBoy, rom_path, profile, scenario, frames, script, ram=None,
                 png=None, audit_class=Audit):
    with tempfile.TemporaryDirectory(prefix='startspill-') as tmp:
        work = os.path.join(tmp, 'start.gb')
        shutil.copyfile(rom_path, work)
        if ram:
            shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        audit = audit_class(profile, scenario)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'],
                         lambda _ctx: audit.at_entry(pb), None)
        pb.hook_register(ROW_EPILOG[0], ROW_EPILOG[1],
                         lambda _ctx: audit.at_epilog(pb), None)
        if os.environ.get('STARTSPILL_TRACE'):
            def trace_selector(_ctx=None):
                source = (pb.register_file.B << 8) | pb.register_file.C
                shape = bytes(pb.memory[0xC69A:0xC69F])
                cells = (bytes(pb.memory[source:source + 6])
                         if 0xC000 <= source < 0xE000 else b'')
                print('trace %-24s f%-4d selector helper bc=$%04X shape=%s cells=%s' %
                      (scenario, audit.frame, source, shape.hex(), cells.hex()))
            pb.hook_register(menuvwf.SELECTOR_BANK, menuvwf.SELECTOR_AT,
                             trace_selector, None)
            _confirm_code, confirm_labels = menuvwf.gbasm.assemble(
                menuvwf.CONFIRM_SRC, menuvwf.CONFIRM_AT)

            def trace_confirm(label):
                def callback(_ctx=None):
                    source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
                    cells = (bytes(pb.memory[source:source + 6])
                             if 0xC000 <= source < 0xE000 else b'')
                    print('trace %-24s f%-4d confirm %-12s d=%d source=$%04X '
                          'hl=$%04X de=$%04X a=$%02X shape=%s tiles=%d raw=%d cells=%s' %
                          (scenario, audit.frame, label, pb.register_file.D, source,
                           pb.register_file.HL,
                           (pb.register_file.D << 8) | pb.register_file.E,
                           pb.register_file.A,
                           bytes(pb.memory[0xC69A:0xC69F]).hex(),
                           pb.memory[0xC0D3], pb.memory[0xC0D0], cells.hex()))
                return callback

            for label in ('confirmalloc', 'carankpass', 'cacheck', 'caloop', 'cabad'):
                pb.hook_register(menuvwf.CONFIRM_BANK, confirm_labels[label],
                                 trace_confirm(label), None)
        for frame in range(frames):
            audit.frame = frame
            for button in script.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            audit.check_visible(pb)
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
        if audit.pending is not None:
            audit.problems.append('target row never reached its epilogue')
        return audit


def boot_script(extra=None):
    script = {60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',)}
    script.update(extra or {})
    return script


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', required=True,
                        help='save fixture used for Adventure/log-summary coverage')
    parser.add_argument('--wide-ram',
                        help='optional one-log fixture whose title menu has eight rows')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for path in (args.rom, args.ram, args.wide_ram):
        if path and not os.path.exists(path):
            raise SystemExit('startspill: missing %s' % path)
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)

    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('startspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    # Defer namerun until PyBoy has imported stdlib dis; tools/dis.py otherwise shadows
    # it when this script's tools directory is first on sys.path.
    sys.path.insert(0, HERE)
    from namerun import NAV_FRESH                              # noqa: E402
    sys.path.pop(0)

    # Blank cart: stop on the three-row start menu, before New Log is selected.
    fresh = {frame: (button,) for frame, button in NAV_FRESH.items()
             if frame < 1320}
    audits = [run_scenario(
        PyBoy, args.rom, profile, 'blank-cart title', 1310, fresh,
        png=(os.path.join(args.png_dir, 'title_blank.png') if args.png_dir else None))]

    selector_script = {frame: (button,) for frame, button in NAV_FRESH.items()
                       if frame < 1450}
    audits.append(run_scenario(
        PyBoy, args.rom, profile, 'blank-cart Log selector', 1440, selector_script,
        png=(os.path.join(args.png_dir, 'log_selector.png') if args.png_dir else None)))

    # Saved cart: Adventure opens the three log summaries.  Cursor movement redraws all
    # three records, which exercises the exact-width source-row path repeatedly.
    summaries = boot_script({300: ('a',), 350: ('down',), 390: ('down',)})
    audits.append(run_scenario(
        PyBoy, args.rom, profile, 'saved title/log summaries', 430, summaries,
        ram=args.ram,
        png=(os.path.join(args.png_dir, 'log_summaries.png') if args.png_dir else None)))

    # The full three-log fixture puts Erase Log directly below Adventure. Exercise every
    # log separately: Log 1's narrow digit needs eight physical tiles on row 0, while
    # Log 2/3 need nine. Testing only the first log caused a false green on the exact raw
    # fallback Joey photographed on 2026-08-08.
    erase_routes = (
        ('Log 1', {300: ('down',), 350: ('a',), 430: ('a',)}, 540,
         'erase_confirmation.png'),
        ('Log 2', {300: ('down',), 350: ('a',), 390: ('down',), 450: ('a',)}, 560,
         'erase_confirmation_log2.png'),
        ('Log 3', {300: ('down',), 350: ('a',), 390: ('down',), 420: ('down',),
                   480: ('a',)}, 590, 'erase_confirmation_log3.png'),
    )
    for log, route, frames, filename in erase_routes:
        audits.append(run_scenario(
            PyBoy, args.rom, profile, 'erase confirmation %s' % log, frames,
            boot_script(route), ram=args.ram,
            png=(os.path.join(args.png_dir, filename) if args.png_dir else None)))

    if args.wide_ram:
        audits.append(run_scenario(
            PyBoy, args.rom, profile, 'eight-row saved title', 320, boot_script(),
            ram=args.wide_ram,
            png=(os.path.join(args.png_dir, 'title_eight_rows.png')
                 if args.png_dir else None)))
        # Exact real route used by rankspill: move from Adventure to Rank/Pass, then
        # stop on the two-row popup before selecting Rank. Box 45 was missing from the
        # renderer allowlist even though its parent title rows were proportional.
        rankpass = {
            700: ('start',), 760: ('start',), 820: ('start',), 880: ('start',),
            1230: ('down',), 1270: ('down',), 1310: ('down',), 1350: ('down',),
            1390: ('down',), 1460: ('a',),
        }
        audits.append(run_scenario(
            PyBoy, args.rom, profile, 'Rank/Pass popup', 1760, rankpass,
            ram=args.wide_ram,
            png=(os.path.join(args.png_dir, 'rank_pass_popup.png')
                 if args.png_dir else None)))

    problems = ['%s: %s' % (audit.scenario, problem)
                for audit in audits for problem in audit.problems]
    calls = sum((audit.calls for audit in audits), collections.Counter())
    if not calls['title']:
        problems.append('no title rows reached the proportional renderer')
    if not calls['selector']:
        problems.append('no Log selector rows reached the proportional renderer')
    if menuvwf.CONTEXT_STATIC_ROWS:
        if not calls['summary']:
            problems.append('no save-summary rows reached the proportional renderer')
        if calls['confirm'] != 6:
            problems.append('erase-confirmation coverage reached %d rows, expected 6 '
                            '(two rows x three logs)' % calls['confirm'])
        if args.wide_ram and calls['rankpass'] != 2:
            problems.append('Rank/Pass coverage reached %d rows, expected 2' %
                            calls['rankpass'])
    elif calls['summary'] or calls['confirm'] or calls['rankpass']:
        problems.append('disabled context-static rows still reached VWF: %s' %
                        dict(calls))
    if not sum(audit.visible for audit in audits):
        problems.append('no composed start-flow row became visible')
    for problem in problems[:20]:
        print('  ' + problem)
    print('startspill: %d title, %d selector, %d summary, %d confirm, %d Rank/Pass '
          'row call(s); '
          '%d epilogue-exact and %d visible plane check(s); %d problem(s)' %
          (calls['title'], calls['selector'], calls['summary'], calls['confirm'],
           calls['rankpass'],
           sum(audit.exact for audit in audits),
           sum(audit.visible for audit in audits), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
