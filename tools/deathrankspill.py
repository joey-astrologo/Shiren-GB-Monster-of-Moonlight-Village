#!/usr/bin/env python3
"""Death-result Rankings regression against the matching native drawer.

Log 2 in ``shiren_en_log2_about_to_die.srm`` starts at one HP with an enemy directly
behind Shiren.  Attacking the wall lets that enemy kill him and opens the Rankings result
page.  This LCD-off route is materially different from the title-menu Rankings route:
name planes are copied synchronously, so their five private tile IDs must also be
published into the shadow map before the completed board is revealed.

The supplied ``--native-control`` is the matching ``--dot-font --no-menuvwf`` build.  It
proves the stored names and native result layout independently.  The test requires all five
``Shiren`` records, their proportional planes and map IDs, the native current-result
arrow at row 10/column 0, and byte/plane equality for every non-VWF cell.  That catches
both the formerly blank name columns and the ``Rankings`` plane collision which turned
the left-edge arrow into stray letters.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gbasm                                                    # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                   # noqa: E402
from latinfont import EN_CODES                                  # noqa: E402
import menuspill                                                 # noqa: E402
import rankvwf                                                  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_about_to_die.srm')
BUTTONS = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 500: 'a',
    2200: 'a',                       # attack the wall; the enemy kills Shiren
}
FINAL_FRAME = 3000
SHADOW = 0xC300
DESTS = tuple(0xC38D + row * 0x60 for row in range(rankvwf.ROWS))
NAME = bytes(EN_CODES[ch] for ch in 'Shiren')
CURRENT_MARKER = (10, 0, 0x81)

HEADER_CELLS = {(1, col) for col in range(6, 14)}
NAME_CELLS = {(4 + row * 3, col)
              for row in range(rankvwf.ROWS) for col in range(13, 19)}
DIFFICULTY_CELLS = {(5 + row * 3, col)
                    for row in range(rankvwf.ROWS) for col in range(3, 8)}
VISIBLE_CELLS = {(row, col) for row in range(18) for col in range(20)}


def _snapshot(pb):
    lcdc = pb.memory[0xFF40]
    map9800 = bytes(pb.memory[0x9800:0x9C00])
    map9c00 = bytes(pb.memory[0x9C00:0xA000])
    return {
        'image': pb.screen.image.copy(),
        'lcdc': lcdc,
        'selected_map': map9c00 if lcdc & 0x08 else map9800,
        'shadow': bytes(pb.memory[SHADOW:SHADOW + 0x400]),
        'vram': bytes(pb.memory[0x8000:0x9800]),
        'display': tuple(pb.memory[address]
                         for address in (0xFF42, 0xFF43, 0xFF4A, 0xFF4B,
                                         0xFF47, 0xFF48, 0xFF49)),
    }


def _plane(snapshot, tile):
    start = menuspill.tile_data_addr(tile) - 0x8000
    return snapshot['vram'][start:start + 16]


def _cell_plane(snapshot, row, col):
    return _plane(snapshot, snapshot['selected_map'][row * 32 + col])


def _emulate(PyBoy, rom, ram, instrument):
    with tempfile.TemporaryDirectory(prefix='deathrankspill-') as tmp:
        work = os.path.join(tmp, 'death.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=False)
        pb.set_emulation_speed(0)

        state = {'frame': 0}
        pages, entries, direct, queue = [], [], [], []

        def at_page(_ctx=None):
            page = pb.memory[0xC6AC]
            records = tuple(bytes(pb.memory[0xD61B + page * 12 + row * 12:
                                            0xD61B + page * 12 + row * 12 + 6])
                            for row in range(rankvwf.ROWS))
            pages.append((state['frame'], page, records))

        pb.hook_register(rankvwf.RANK_BANK, 0x4662, at_page, None)
        if instrument:
            _, transition = gbasm.assemble(rankvwf.TRANSITION_SRC,
                                           rankvwf.TRANSITION_AT)
            _, upload = gbasm.assemble(rankvwf.UPLOAD_SRC, rankvwf.UPLOAD_AT)
            pb.hook_register(rankvwf.FAR_BANK, rankvwf.ENTRY_AT,
                             lambda _ctx: entries.append(
                                 (state['frame'], pb.register_file.HL,
                                  bytes(pb.memory[0xC6E3:0xC6E9]))), None)
            pb.hook_register(rankvwf.TRANSITION_BANK, transition['rankdirect'],
                             lambda _ctx: direct.append(state['frame']), None)
            pb.hook_register(rankvwf.AUX_BANK, upload['arm'],
                             lambda _ctx: queue.append(state['frame']), None)

        for frame in range(FINAL_FRAME + 1):
            state['frame'] = frame
            button = BUTTONS.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        snapshot = _snapshot(pb)
        snapshot.update(pages=pages, entries=entries, direct=direct, queue=queue,
                        pc=pb.register_file.PC)
        pb.stop(save=False)
        return snapshot


def run(rom, native_control, ram, png=None):
    profile = menuspill.renderer_profile(rom)
    PyBoy = _import_pyboy()
    approved = _emulate(PyBoy, rom, ram, True)
    native = _emulate(PyBoy, native_control, ram, False)
    problems = []

    for label, result in (('production', approved), ('control', native)):
        if len(result['pages']) != 1:
            problems.append('%s page drawer ran %d times, expected 1'
                            % (label, len(result['pages'])))
        elif result['pages'][0][1] != 3:
            problems.append('%s selected page %d, expected nonzero page 3'
                            % (label, result['pages'][0][1]))
        elif result['pages'][0][2] != (NAME,) * rankvwf.ROWS:
            problems.append('%s staged records are not five exact Shiren names: %s'
                            % (label, ' / '.join(row.hex()
                                                for row in result['pages'][0][2])))

    if len(approved['entries']) != rankvwf.ROWS or \
            len(approved['direct']) != rankvwf.ROWS:
        problems.append('production rows: %d entry / %d LCD-off direct, expected %d/%d'
                        % (len(approved['entries']), len(approved['direct']),
                           rankvwf.ROWS, rankvwf.ROWS))
    if approved['queue']:
        problems.append('LCD-off death result armed the VBlank queue at frame(s) %s'
                        % ' '.join(map(str, approved['queue'])))
    for index, entry in enumerate(approved['entries']):
        if entry[1] != DESTS[index] or entry[2] != NAME:
            problems.append('row %d entry destination/name is $%04X/%s, expected $%04X/%s'
                            % (index, entry[1], entry[2].hex(), DESTS[index], NAME.hex()))

    for row, dest in enumerate(DESTS):
        base = rankvwf.POOL_BASE + row * rankvwf.TILES_PER_ROW
        want_ids = bytes(range(base, base + rankvwf.TILES_PER_ROW))
        offset = dest - SHADOW
        got_shadow = approved['shadow'][offset:offset + rankvwf.TILES_PER_ROW]
        got_map = approved['selected_map'][offset:offset + rankvwf.TILES_PER_ROW]
        if got_shadow != want_ids:
            problems.append('row %d shadow name IDs are %s, expected %s'
                            % (row, got_shadow.hex(), want_ids.hex()))
        if got_map != want_ids:
            problems.append('row %d visible name IDs are %s, expected %s'
                            % (row, got_map.hex(), want_ids.hex()))
        want_tiles = menuspill.compose(list(NAME), profile)
        want_tiles += [bytearray(16)
                       for _ in range(rankvwf.TILES_PER_ROW - len(want_tiles))]
        for index, want in enumerate(want_tiles):
            got = _plane(approved, base + index)
            if got != bytes(want):
                problems.append('row %d tile $%02X differs after LCD-off direct copy'
                                % (row, base + index))
                break

    marker_row, marker_col, marker_tile = CURRENT_MARKER
    for label, result in (('production', approved), ('control', native)):
        got = result['selected_map'][marker_row * 32 + marker_col]
        if got != marker_tile:
            problems.append('%s current-result marker is tile $%02X, expected native $%02X'
                            % (label, got, marker_tile))
    if _cell_plane(approved, marker_row, marker_col) != \
            _cell_plane(native, marker_row, marker_col):
        problems.append('native current-result arrow plane differs from control '
                        '(header tile collision)')

    # Only native Village/Dragon sentinel values are replaced by a proportional marker.
    # Numeric floors remain part of the byte/plane-exact native comparison.
    special_cells = set()
    for rank_row in range(rankvwf.ROWS):
        map_row = 5 + rank_row * 3
        first_code = native['selected_map'][map_row * 32 + 15]
        if first_code in (0x2B, 0x32):
            special_cells.update((map_row, col) for col in range(14, 18))
    vwf_cells = HEADER_CELLS | NAME_CELLS | DIFFICULTY_CELLS | special_cells
    for row, col in sorted(VISIBLE_CELLS - vwf_cells):
        offset = row * 32 + col
        if approved['selected_map'][offset] != native['selected_map'][offset]:
            problems.append('native map cell row %d col %d changed: $%02X vs control $%02X'
                            % (row, col, approved['selected_map'][offset],
                               native['selected_map'][offset]))
            break
        if _cell_plane(approved, row, col) != _cell_plane(native, row, col):
            problems.append('native resolved cell row %d col %d differs from control'
                            % (row, col))
            break
    if approved['display'] != native['display']:
        problems.append('settled display registers differ: %s vs control %s'
                        % (approved['display'], native['display']))
    if not approved['lcdc'] & 0x80:
        problems.append('production Rankings settled with LCD disabled '
                        '(PC=$%04X LCDC=$%02X)' % (approved['pc'], approved['lcdc']))

    if png:
        approved['image'].save(png)
        stem, ext = os.path.splitext(png)
        native['image'].save(stem + '.control' + (ext or '.png'))
        print('deathrankspill: wrote %s and control image' % png)
    print('deathrankspill: pages %d/%d; rows %d entry / %d direct / %d queue; '
          'five stored names; %d problem(s)'
          % (len(approved['pages']), len(native['pages']), len(approved['entries']),
             len(approved['direct']), len(approved['queue']), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--native-control', required=True)
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.native_control, args.ram):
        if not os.path.exists(path):
            raise SystemExit('deathrankspill: missing %s' % path)
    return run(args.rom, args.native_control, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
