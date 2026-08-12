#!/usr/bin/env python3
"""Rankings/native-graphics lifetime regression for the cleared-Orochi save.

This is deliberately a two-ROM test.  ``ROM`` is the proportional production build;
``--native-control`` is the matching ``--dot-font --no-menuvwf`` build.  The latter
keeps the native Rankings drawer and graphics while removing both title-menu VWF layers,
so it is an oracle for every non-VWF pixel on the Rankings category and result screens.

The route is the complete release-blocker reproduction:

* Adventure -> Log 1 (record the real coloured Orochi badge);
* Kuyo Rankings -> Log 1;
* Village Exit Rankings -> Log 1;
* Kuyo Rankings -> Log 1 again.

At each settled Rankings screen the test compares the complete visible region by
resolved tile planes and framebuffer pixels, masking only cells independently proved to
contain the expected proportional text.  The real Kuyo Orochi status badge and every
other native cell remain unmasked.  Every returned Adventure page must be byte-exact to
the initial visible map, resolved planes, pixels and real badge.  The badge planes are
also checked on every frame in which its map is selected, rejecting restoration that
happens after a corrupt frame has already been revealed.

The old version of this test watched unrelated tiles $5B/$5C/$63/$64 at x=16.  The real
badge is $CB/$CD/$CC/$CE at rows 9-10, columns 5-6, crop (40,72)-(56,88).
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                 # noqa: E402
from latinfont import EN_CODES                                # noqa: E402
import menuspill                                               # noqa: E402
import menuvwf                                                 # noqa: E402
import rankvwf                                                 # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_orochi_symbol.srm')

# The timings are intentionally spacious.  They use only real input and work unchanged
# in normal, shuffled and redirect-all layouts.
BUTTONS = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1080: 'a', 1160: 'b',

    # Rank/Pass -> Rank -> Kuyo.
    1230: 'down', 1270: 'down', 1310: 'down', 1350: 'down', 1390: 'down',
    1460: 'a', 1800: 'a', 1900: 'a',
    # Kuyo -> title -> Adventure -> Log 1.
    2400: 'b', 2500: 'b', 2600: 'b',
    2700: 'up', 2740: 'up', 2780: 'up', 2820: 'up', 2860: 'up',
    2940: 'a',

    # Rank/Pass -> Rank -> Village Exit.
    3300: 'b',
    3370: 'down', 3410: 'down', 3450: 'down', 3490: 'down', 3530: 'down',
    3600: 'a', 3850: 'a', 3950: 'down', 4020: 'a',
    # Village Exit -> title -> Adventure -> Log 1.
    4400: 'b', 4500: 'b', 4600: 'b',
    4700: 'up', 4740: 'up', 4780: 'up', 4820: 'up', 4860: 'up',
    4940: 'a',

    # Repeat Rank/Pass -> Rank -> Kuyo.
    5300: 'b',
    5370: 'down', 5410: 'down', 5450: 'down', 5490: 'down', 5530: 'down',
    5600: 'a', 5850: 'a', 5950: 'a',
    # Kuyo -> title -> Adventure -> Log 1 a third time.
    6350: 'b', 6450: 'b', 6550: 'b',
    6650: 'up', 6690: 'up', 6730: 'up', 6770: 'up', 6810: 'up',
    6900: 'a',
}

CHECKPOINTS = {
    1100: 'initial_log',
    1850: 'kuyo_selector_1',
    2000: 'kuyo_rankings_1',
    3200: 'returned_log_1',
    3970: 'village_selector',
    4150: 'village_rankings',
    5150: 'returned_log_2',
    5900: 'kuyo_selector_2',
    6100: 'kuyo_rankings_2',
    7100: 'returned_log_3',
}
FINAL_FRAME = max(CHECKPOINTS)

SELECTOR_LABELS = ('Kuyou', 'Village Exit')
RANK_NAME = 'Shiren'
SELECTOR_REGION = {(row, col) for row in range(7, 12) for col in range(5, 17)}
# The raw control's overlong fixed-cell second label leaves three text fragments in the
# spacer row.  That row belongs to the text renderer, not to a native graphic: mask it
# from the oracle comparison but independently require the production renderer to clear
# every one of its cells.
SELECTOR_VWF_ROWS = ((8, tuple(range(7, 16)), SELECTOR_LABELS[0]),
                     (9, tuple(range(7, 16)), ''),
                     (10, tuple(range(7, 16)), SELECTOR_LABELS[1]))
SELECTOR_VWF_CELLS = {(row, col) for row, cols, _text in SELECTOR_VWF_ROWS
                      for col in cols}

HEADER_VWF_ROW = (1, tuple(range(6, 14)), 'Rankings')

# The unified Rankings renderer owns three deduplicated difficulty rasters at $85-$8D.
# Derive each row's semantics from the matching native control: this save's Kuyo board
# is Hard/Easy/Easy/Easy/Easy, while Village has no difficulty fields at all.  A
# populated field owns five intentional text cells: three composed tiles and two blank
# trailing cells.  Native clear/status graphics remain unmasked at column 18.
DIFFICULTY_ROWS = (5, 8, 11, 14, 17)
DIFFICULTY_COLUMNS = tuple(range(3, 8))
DIFFICULTY_BY_FIRST_CODE = {0x0F: 'Easy', 0x18: 'Norm.', 0x12: 'Hard'}

# Name fields begin at column 13.  The first Kuyo row's sixth name cell is replaced by
# the live native Orochi badge at column 18, so it is emphatically NOT a VWF mask cell.
KUYO_NAME_ROWS = ((4, tuple(range(13, 18))),
                  (7, tuple(range(13, 19))),
                  (10, tuple(range(13, 19))),
                  (13, tuple(range(13, 19))),
                  (16, tuple(range(13, 19))))
VILLAGE_NAME_ROWS = ((4, tuple(range(13, 19))),)

EMBLEM_TILES = (0xCB, 0xCD, 0xCC, 0xCE)
EMBLEM_CELLS = ((9, 5, 0xCB), (9, 6, 0xCD),
                (10, 5, 0xCC), (10, 6, 0xCE))
EMBLEM_CROP = (40, 72, 56, 88)

# These are the actual native two-plane tiles from the authoritative save, not values
# learned from the production run under test.
GOLD_EMBLEM_PLANES = (
    bytes.fromhex('7f7ff9febccfe6bbdbfdfff796f3ceff'),
    bytes.fromhex('fefe9f7f3df367dddbbfffef69cf73ff'),
    bytes.fromhex('d9e6eef7f0bfabfbebffa7bf929c7f7f'),
    bytes.fromhex('9b6777ef0ffdd5dfd7ffe5fd4939fefe'),
)

# The Kuyo result embeds that same 16x16 cleared-Orochi graphic beside rank 1.  Later
# rows have native status marks at column 18; the complete-board oracle covers those,
# while naming them here gives useful diagnostics if only a status plane regresses.
KUYO_OROCHI_CELLS = ((4, 18), (4, 19), (5, 18), (5, 19))
KUYO_STATUS_CELLS = ((8, 18), (11, 18), (14, 18))

VISIBLE_ROWS = 18
VISIBLE_COLS = 20
VISIBLE_CELLS = {(row, col) for row in range(VISIBLE_ROWS)
                 for col in range(VISIBLE_COLS)}
ZERO_TILE = bytes(16)


def _visible_bytes(data):
    """Return the 20x18 cells from a 32-wide tilemap/shadow buffer."""
    return bytes(data[row * 32 + col]
                 for row in range(VISIBLE_ROWS)
                 for col in range(VISIBLE_COLS))


def _bg_tile_plane(vram, tile):
    """Resolve a BG tile through LCDC's signed $8800 tile-data mode."""
    address = menuspill.tile_data_addr(tile)
    start = address - 0x8000
    return vram[start:start + 16]


def _resolved_cell(snapshot, row, col):
    tile = snapshot['selected_map'][row * 32 + col]
    return _bg_tile_plane(snapshot['vram'], tile)


def _emblem_map(snapshot):
    return tuple(snapshot['map9800'][row * 32 + col]
                 for row, col, _tile in EMBLEM_CELLS)


def _emblem_planes(snapshot):
    return tuple(_bg_tile_plane(snapshot['vram'], tile) for tile in EMBLEM_TILES)


def _snapshot(pb):
    image = pb.screen.image.copy().convert('RGB')
    lcdc = pb.memory[0xFF40]
    map9800 = bytes(pb.memory[0x9800:0x9C00])
    map9c00 = bytes(pb.memory[0x9C00:0xA000])
    return {
        'image': image,
        'pixels': image.tobytes(),
        'badge_pixels': image.crop(EMBLEM_CROP).tobytes(),
        'map9800': map9800,
        'map9c00': map9c00,
        'selected_map': map9c00 if lcdc & 0x08 else map9800,
        'shadow': bytes(pb.memory[0xC300:0xC700]),
        'vram': bytes(pb.memory[0x8000:0x9800]),
        'oam': bytes(pb.memory[0xFE00:0xFEA0]),
        'lcdc': lcdc,
        'display': tuple(pb.memory[addr]
                         for addr in (0xFF42, 0xFF43, 0xFF4A, 0xFF4B,
                                     0xFF47, 0xFF48, 0xFF49)),
    }


def _badge_is_selected(pb):
    """True once the Adventure map containing the badge can be scanned out."""
    lcdc = pb.memory[0xFF40]
    if not lcdc & 0x80 or lcdc & 0x08:
        return False
    return tuple(pb.memory[0x9800 + row * 32 + col]
                 for row, col, _tile in EMBLEM_CELLS) == EMBLEM_TILES


def _live_badge_is_gold(pb):
    for tile, want in zip(EMBLEM_TILES, GOLD_EMBLEM_PLANES):
        at = menuspill.tile_data_addr(tile)
        if bytes(pb.memory[at:at + 16]) != want:
            return False
    return True


def _emulate(PyBoy, rom, ram, watch_badge):
    with tempfile.TemporaryDirectory(prefix='orochisymbolspill-') as tmp:
        work = os.path.join(tmp, 'orochi.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        # This cartridge is non-CGB ($0143=$42).  Force the one-bank DMG hardware
        # model so a bank-1-only renderer cannot make this regression pass by accident.
        pb = PyBoy(work, window='null', cgb=False)
        pb.set_emulation_speed(0)

        state = {'frame': 0}
        snapshots = {}
        page_calls = []
        badge_episodes = []
        corrupt_reveals = []
        corrupt_page_reveals = []
        badge_selected = False
        initial_reveal = None

        def at_page(_ctx=None):
            page_calls.append(state['frame'])

        pb.hook_register(rankvwf.RANK_BANK, 0x4662, at_page, None)

        for frame in range(FINAL_FRAME + 1):
            state['frame'] = frame
            button = BUTTONS.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

            if watch_badge and frame >= min(CHECKPOINTS):
                selected = _badge_is_selected(pb)
                if selected and not badge_selected:
                    badge_episodes.append(frame)
                    reveal = _snapshot(pb)
                    if initial_reveal is None:
                        initial_reveal = reveal
                    else:
                        map_exact = (_visible_bytes(reveal['map9800']) ==
                                     _visible_bytes(initial_reveal['map9800']))
                        planes_exact = (_visible_resolved(reveal) ==
                                        _visible_resolved(initial_reveal))
                        if not map_exact or not planes_exact:
                            corrupt_page_reveals.append(
                                (frame, len(badge_episodes), map_exact, planes_exact))
                if selected and not _live_badge_is_gold(pb):
                    if not corrupt_reveals or corrupt_reveals[-1][1] != len(badge_episodes):
                        corrupt_reveals.append((frame, len(badge_episodes)))
                badge_selected = selected

            if frame in CHECKPOINTS:
                snapshots[frame] = _snapshot(pb)

        pb.stop(save=False)
        return {
            'snapshots': snapshots,
            'page_calls': page_calls,
            'badge_episodes': badge_episodes,
            'corrupt_reveals': corrupt_reveals,
            'corrupt_page_reveals': corrupt_page_reveals,
        }


def _codes(text):
    return [EN_CODES[ch] for ch in text]


def _check_vwf_row(problems, snapshot, profile, label, row, columns, text):
    """Require one visible row to equal the allocator-independent Dot composition."""
    expected = [bytes(tile) for tile in menuspill.compose(_codes(text), profile)]
    if len(expected) > len(columns):
        problems.append('%s: proportional %r needs %d tiles, field has %d' %
                        (label, text, len(expected), len(columns)))
        return
    expected += [ZERO_TILE] * (len(columns) - len(expected))
    bad = []
    for col, want in zip(columns, expected):
        got = _resolved_cell(snapshot, row, col)
        if got != want:
            tile = snapshot['selected_map'][row * 32 + col]
            bad.append('(%d,%d)=$%02X' % (row, col, tile))
    if bad:
        problems.append('%s: proportional %r differs in %d cell(s): %s' %
                        (label, text, len(bad), ' '.join(bad[:8])))


def _check_settled_map(problems, snapshot, label):
    lcdc = snapshot['lcdc']
    if not lcdc & 0x80:
        problems.append('%s: LCD is disabled (LCDC=$%02X)' % (label, lcdc))
    if lcdc & 0x08:
        problems.append('%s: blank $9C00 map is still selected (LCDC=$%02X)' %
                        (label, lcdc))
    if lcdc & 0x10:
        problems.append('%s: unsigned BG tile mode unexpectedly active (LCDC=$%02X)' %
                        (label, lcdc))
    got_bg = _visible_bytes(snapshot['map9800'])
    got_shadow = _visible_bytes(snapshot['shadow'])
    if got_bg != got_shadow:
        first = next(i for i, pair in enumerate(zip(got_bg, got_shadow))
                     if pair[0] != pair[1])
        problems.append('%s: published BG differs from shadow first at (%d,%d)' %
                        (label, first // VISIBLE_COLS, first % VISIBLE_COLS))


def _semantic_mismatches(production, control, cells, masked):
    mismatches = []
    for row, col in sorted(cells - masked):
        got = _resolved_cell(production, row, col)
        want = _resolved_cell(control, row, col)
        if got != want:
            got_id = production['selected_map'][row * 32 + col]
            want_id = control['selected_map'][row * 32 + col]
            mismatches.append((row, col, got_id, want_id))
    return mismatches


def _pixel_mismatches(production, control, cells, masked):
    got = production['pixels']
    want = control['pixels']
    count = 0
    first = []
    for row, col in sorted(cells - masked):
        for y in range(row * 8, row * 8 + 8):
            for x in range(col * 8, col * 8 + 8):
                at = (y * 160 + x) * 3
                if got[at:at + 3] != want[at:at + 3]:
                    count += 1
                    if len(first) < 6:
                        first.append((x, y))
    return count, first


def _visible_sprites(snapshot):
    """Resolve visible OAM entries to positions, attributes and physical tile planes."""
    height = 16 if snapshot['lcdc'] & 0x04 else 8
    result = []
    for index in range(40):
        y, x, tile, attributes = snapshot['oam'][index * 4:index * 4 + 4]
        if not (0 < y < 160 and 0 < x < 168):
            continue
        if height == 16:
            tile &= 0xFE
        start = tile * 16
        planes = snapshot['vram'][start:start + height * 2]
        result.append((y, x, attributes, planes))
    return tuple(result)


def _compare_region(problems, production, control, label, cells, masked):
    if production['lcdc'] != control['lcdc']:
        problems.append('%s: LCDC differs from control ($%02X/$%02X)' %
                        (label, production['lcdc'], control['lcdc']))
    if production['display'] != control['display']:
        problems.append('%s: scroll/window/palette registers differ from control: '
                        '%s/%s' % (label, production['display'], control['display']))
    mismatches = _semantic_mismatches(production, control, cells, masked)
    if mismatches:
        detail = ' '.join('(%d,%d) $%02X/$%02X' % item
                          for item in mismatches[:8])
        problems.append('%s: %d native/resolved cell(s) differ from control: %s' %
                        (label, len(mismatches), detail))
    pixel_count, first_pixels = _pixel_mismatches(production, control, cells, masked)
    if pixel_count:
        problems.append('%s: %d unmasked framebuffer pixel(s) differ from control; '
                        'first %s' % (label, pixel_count, first_pixels))
    got_sprites = _visible_sprites(production)
    want_sprites = _visible_sprites(control)
    if got_sprites != want_sprites:
        problems.append('%s: visible OAM semantics differ (%d production / %d control)' %
                        (label, len(got_sprites), len(want_sprites)))
    return len(mismatches), pixel_count, len(got_sprites)


def _check_selector(problems, production, control, profile, label):
    for row, columns, text in SELECTOR_VWF_ROWS:
        _check_vwf_row(problems, production, profile, label, row, columns, text)
    return _compare_region(problems, production, control, label,
                           SELECTOR_REGION, SELECTOR_VWF_CELLS)


def _difficulty_vwf_rows(problems, control, label):
    rows = []
    for row in DIFFICULTY_ROWS:
        first_code = control['selected_map'][row * 32 + DIFFICULTY_COLUMNS[0]]
        if first_code == 0:
            continue
        text = DIFFICULTY_BY_FIRST_CODE.get(first_code)
        if text is None:
            problems.append('%s: native control difficulty row %d starts with '
                            'unknown code $%02X' % (label, row, first_code))
            continue
        rows.append((row, DIFFICULTY_COLUMNS, text))
    return tuple(rows)


def _board_mask(name_rows, difficulty_rows):
    row, columns, _text = HEADER_VWF_ROW
    mask = {(row, col) for col in columns}
    for difficulty_row, difficulty_columns, _text in difficulty_rows:
        mask.update((difficulty_row, col) for col in difficulty_columns)
    for name_row, name_columns in name_rows:
        mask.update((name_row, col) for col in name_columns)
    return mask


def _check_board(problems, production, control, profile, label, board):
    _check_settled_map(problems, production, label)
    _check_settled_map(problems, control, label + ' native control')
    row, columns, text = HEADER_VWF_ROW
    _check_vwf_row(problems, production, profile, label, row, columns, text)
    difficulty_rows = _difficulty_vwf_rows(problems, control, label)
    for difficulty_row, difficulty_columns, difficulty_text in difficulty_rows:
        _check_vwf_row(problems, production, profile, label,
                       difficulty_row, difficulty_columns, difficulty_text)

    name_rows = KUYO_NAME_ROWS if board == 'kuyo' else VILLAGE_NAME_ROWS
    for name_row, name_columns in name_rows:
        _check_vwf_row(problems, production, profile, label,
                       name_row, name_columns, RANK_NAME)

    if board == 'kuyo':
        for (status_row, status_col), want in zip(KUYO_OROCHI_CELLS,
                                                  GOLD_EMBLEM_PLANES):
            got = _resolved_cell(production, status_row, status_col)
            oracle = _resolved_cell(control, status_row, status_col)
            if oracle != want:
                problems.append('%s: native control Orochi status at (%d,%d) is not '
                                'the gold badge' % (label, status_row, status_col))
            if got != want:
                tile = production['selected_map'][status_row * 32 + status_col]
                problems.append('%s: Orochi status at (%d,%d), tile $%02X, has '
                                'corrupt native planes' %
                                (label, status_row, status_col, tile))
        for status_row, status_col in KUYO_STATUS_CELLS:
            if _resolved_cell(production, status_row, status_col) != \
                    _resolved_cell(control, status_row, status_col):
                problems.append('%s: native status graphic at (%d,%d) differs from '
                                'control' % (label, status_row, status_col))

    return _compare_region(problems, production, control, label,
                           VISIBLE_CELLS, _board_mask(name_rows, difficulty_rows))


def _visible_resolved(snapshot):
    return tuple(_resolved_cell(snapshot, row, col)
                 for row in range(VISIBLE_ROWS)
                 for col in range(VISIBLE_COLS))


def _check_initial_badge(problems, initial):
    expected_map = tuple(tile for _row, _col, tile in EMBLEM_CELLS)
    got_map = _emblem_map(initial)
    if got_map != expected_map:
        problems.append('initial Log 1 real Orochi map is %s, expected %s' %
                        (got_map, expected_map))
    got_planes = _emblem_planes(initial)
    for tile, got, want in zip(EMBLEM_TILES, got_planes, GOLD_EMBLEM_PLANES):
        if got != want:
            problems.append('initial Log 1 real Orochi tile $%02X is not gold: %s' %
                            (tile, got.hex()))


def _check_return(problems, initial, returned, label):
    expected_map = tuple(tile for _row, _col, tile in EMBLEM_CELLS)
    if _emblem_map(returned) != expected_map:
        problems.append('%s: real Orochi tilemap is %s, expected %s' %
                        (label, _emblem_map(returned), expected_map))
    for tile, got, want in zip(EMBLEM_TILES, _emblem_planes(returned),
                               GOLD_EMBLEM_PLANES):
        if got != want:
            problems.append('%s: real Orochi tile $%02X was not restored before reveal' %
                            (label, tile))
    if returned['badge_pixels'] != initial['badge_pixels']:
        problems.append('%s: visible real Orochi crop differs from initial' % label)

    initial_map = _visible_bytes(initial['map9800'])
    returned_map = _visible_bytes(returned['map9800'])
    if returned_map != initial_map:
        first = next(i for i, pair in enumerate(zip(initial_map, returned_map))
                     if pair[0] != pair[1])
        problems.append('%s: complete visible Adventure map differs first at (%d,%d)' %
                        (label, first // VISIBLE_COLS, first % VISIBLE_COLS))
    initial_shadow = _visible_bytes(initial['shadow'])
    returned_shadow = _visible_bytes(returned['shadow'])
    if returned_shadow != initial_shadow:
        first = next(i for i, pair in enumerate(zip(initial_shadow, returned_shadow))
                     if pair[0] != pair[1])
        problems.append('%s: complete visible Adventure shadow differs first at '
                        '(%d,%d)' %
                        (label, first // VISIBLE_COLS, first % VISIBLE_COLS))
    if _visible_resolved(returned) != _visible_resolved(initial):
        first = next(i for i, pair in enumerate(zip(_visible_resolved(initial),
                                                    _visible_resolved(returned)))
                     if pair[0] != pair[1])
        problems.append('%s: complete visible Adventure tile planes differ first at '
                        '(%d,%d)' %
                        (label, first // VISIBLE_COLS, first % VISIBLE_COLS))
    if returned['pixels'] != initial['pixels']:
        problems.append('%s: complete Adventure framebuffer differs from initial' % label)
    if returned['lcdc'] != initial['lcdc'] or returned['display'] != initial['display']:
        problems.append('%s: Adventure display registers differ from initial' % label)


def _check_repeat(problems, first, second, label):
    if _visible_bytes(first['selected_map']) != _visible_bytes(second['selected_map']):
        problems.append('%s: repeated visible tilemap is not exact' % label)
    if _visible_resolved(first) != _visible_resolved(second):
        problems.append('%s: repeated resolved tile planes are not exact' % label)
    if first['pixels'] != second['pixels']:
        problems.append('%s: repeated framebuffer is not exact' % label)
    if _visible_sprites(first) != _visible_sprites(second):
        problems.append('%s: repeated visible OAM semantics are not exact' % label)


def _save_pngs(png_dir, production, control):
    if not png_dir:
        return
    os.makedirs(png_dir, exist_ok=True)
    for prefix, result in (('', production), ('native_', control)):
        for frame, snapshot in sorted(result['snapshots'].items()):
            path = os.path.join(png_dir, '%s%s.png' %
                                (prefix, CHECKPOINTS[frame]))
            snapshot['image'].save(path)
            print('orochisymbolspill: wrote %s' % path)


def run(rom, native_control, ram, png_dir=None):
    problems = []
    rom_bytes = open(rom, 'rb').read()
    control_bytes = open(native_control, 'rb').read()
    if rom_bytes[0x143] != 0x42 or control_bytes[0x143] != 0x42:
        problems.append('ROM/control must both be the non-CGB SGB cartridge '
                        '($0143=$42), got $%02X/$%02X' %
                        (rom_bytes[0x143], control_bytes[0x143]))
    if len(rom_bytes) != len(control_bytes):
        problems.append('ROM/control sizes differ: %d/%d' %
                        (len(rom_bytes), len(control_bytes)))

    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        problems.append('production ROM is not the Dot proportional menu renderer')
    control_index = (menuvwf.FAR_BANK * 0x4000 + menuvwf.FAR_INDEX - 1)
    control_entry = (control_bytes[control_index] |
                     (control_bytes[control_index + 1] << 8))
    if control_entry != 0xFFFF:
        problems.append('--native-control menu-VWF far entry is %d:$%04X, expected '
                        'disabled $FFFF; rebuild it with --dot-font --no-menuvwf' %
                        (menuvwf.FAR_BANK, control_entry))

    PyBoy = _import_pyboy()
    production = _emulate(PyBoy, rom, ram, True)
    control = _emulate(PyBoy, native_control, ram, False)
    _save_pngs(png_dir, production, control)

    expected_frames = set(CHECKPOINTS)
    if set(production['snapshots']) != expected_frames:
        problems.append('production route missed checkpoints %s' %
                        sorted(expected_frames - set(production['snapshots'])))
    if set(control['snapshots']) != expected_frames:
        problems.append('native-control route missed checkpoints %s' %
                        sorted(expected_frames - set(control['snapshots'])))
    if len(production['page_calls']) != 3 or len(control['page_calls']) != 3:
        problems.append('Rankings page coverage is %d production / %d control, '
                        'expected 3/3' %
                        (len(production['page_calls']), len(control['page_calls'])))

    if production['corrupt_reveals']:
        problems.append('real Orochi planes were exposed corrupt before restoration at '
                        + ', '.join('frame %d (Log reveal %d)' % item
                                    for item in production['corrupt_reveals']))
    if production['corrupt_page_reveals']:
        problems.append('complete Adventure map/planes were not exact at first reveal: '
                        + ', '.join('frame %d (Log reveal %d, map=%s planes=%s)' % item
                                    for item in production['corrupt_page_reveals']))
    if len(production['badge_episodes']) != 4:
        problems.append('saw %d Adventure badge reveal episode(s), expected initial + '
                        'three returns' % len(production['badge_episodes']))

    if (set(production['snapshots']) == expected_frames and
            set(control['snapshots']) == expected_frames):
        p = {CHECKPOINTS[frame]: snapshot
             for frame, snapshot in production['snapshots'].items()}
        c = {CHECKPOINTS[frame]: snapshot
             for frame, snapshot in control['snapshots'].items()}

        _check_initial_badge(problems, p['initial_log'])
        for label in ('returned_log_1', 'returned_log_2', 'returned_log_3'):
            _check_return(problems, p['initial_log'], p[label], label)

        selector_stats = []
        for label in ('kuyo_selector_1', 'village_selector', 'kuyo_selector_2'):
            selector_stats.append(_check_selector(problems, p[label], c[label],
                                                  profile, label))

        board_stats = []
        board_stats.append(_check_board(problems, p['kuyo_rankings_1'],
                                        c['kuyo_rankings_1'], profile,
                                        'kuyo_rankings_1', 'kuyo'))
        board_stats.append(_check_board(problems, p['village_rankings'],
                                        c['village_rankings'], profile,
                                        'village_rankings', 'village'))
        board_stats.append(_check_board(problems, p['kuyo_rankings_2'],
                                        c['kuyo_rankings_2'], profile,
                                        'kuyo_rankings_2', 'kuyo'))

        _check_repeat(problems, p['kuyo_selector_1'], p['kuyo_selector_2'],
                      'Kuyo selector repeat')
        _check_repeat(problems, p['kuyo_rankings_1'], p['kuyo_rankings_2'],
                      'Kuyo Rankings repeat')
    else:
        selector_stats = []
        board_stats = []

    for problem in problems:
        print('  ' + problem)
    native_cell_diffs = sum(item[0] for item in selector_stats + board_stats)
    pixel_diffs = sum(item[1] for item in selector_stats + board_stats)
    visible_sprites = max((item[2] for item in selector_stats + board_stats), default=0)
    print('orochisymbolspill: Kuyo/Village/Kuyo pages %d; 3 category regions + '
          '3 complete boards; %d native cell / %d pixel mismatch(es); max %d visible '
          'OAM sprite(s); %d badge reveal(s), 3 returned Logs; %d problem(s)' %
          (len(production['page_calls']), native_cell_diffs, pixel_diffs,
           visible_sprites, len(production['badge_episodes']), len(problems)))
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--native-control', required=True,
                        help='matching --dot-font --no-menuvwf ROM')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for path in (args.rom, args.native_control, args.ram):
        if not os.path.exists(path):
            raise SystemExit('orochisymbolspill: missing %s' % path)
    return run(args.rom, args.native_control, args.ram, args.png_dir)


if __name__ == '__main__':
    raise SystemExit(main())
