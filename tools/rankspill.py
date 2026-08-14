#!/usr/bin/env python3
"""Integrated emulator battery for the proportional rankings-name renderer.

It reaches the board through the real title-screen Rank route, then substitutes five
12-byte records only when the real page drawer starts.  The approved run stresses wide,
narrow, mixed-case and sparse picker glyphs.  A second run puts the unsupported legacy
wave code in one record and proves the WHOLE page delegates byte-for-byte to a matching
``--dot-font --no-menuvwf`` native control.  The narrower ``--no-rankvwf`` control is
still used for approved-name component checks, but cannot be the legacy oracle because
its generic menu VWF header may itself collide with arbitrary native name codes.

A third, bounded fixture selects record one as the first visible row and puts its legacy
code only in the fifth selected record.  This proves prevalidation follows the native
``C6AC * 12`` page offset: treating ``C6AC`` as a byte offset misses that marker.

The checks are plane-exact and queue-aware: all five private tiles per row, five shadow
IDs in each six-cell name field, the complete four-tile ``Village``/``Dragon`` reserved
floor markers, every remaining fixed cell, every queue
fingerprint/destination, VBlank consumer timing, park restoration and visible pool
ownership are verified.  Legacy fallback is a whole-page contract: its complete visible
shadow, BG map, resolved tile planes, framebuffer, display state and visible sprite
semantics must equal the native control.  A clean run that never reaches all five rows
fails.

usage: rankspill.py ROM --control CONTROL --native-control NATIVE [options]
"""
import argparse
import os
import shutil
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gbasm                                                   # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                  # noqa: E402
from latinfont import EN_CODES                                 # noqa: E402
import menuspill                                                # noqa: E402
import menuvwf                                                  # noqa: E402
import rankvwf                                                  # noqa: E402


STAGE = 0xD61B
STAGE_END = 0xD6FF
COUNT = 0xC6E2
PAGE_INDEX = 0xC6AC
SHADOW = 0xC300
BGMAP = 0x9800
SHADOW_END = 0xC540
DESTS = (0xC38D, 0xC3ED, 0xC44D, 0xC4AD, 0xC50D)
QUEUE_START, QUEUE_END = 0xC006, 0xC0CC
UPLOAD_START = (0, 0x11A8)
VISIBLE_ROWS, VISIBLE_COLS = 18, 20

BUTTONS = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1230: 'down', 1270: 'down', 1310: 'down', 1350: 'down', 1390: 'down',
    1460: 'a', 1800: 'a',
}

APPROVED_TEXT = ('Shiren', 'WWWWWW', 'iiiiii', 'Abcdef', '+-[]?.')
APPROVED = tuple(bytes(EN_CODES[ch] for ch in text) for text in APPROVED_TEXT)
DIFFICULTY_TEXT = ('Easy ', 'Norm.', 'Hard ')
DIFFICULTIES = tuple(bytes(EN_CODES[ch] for ch in DIFFICULTY_TEXT[i % 3])
                     for i in range(rankvwf.ROWS))
LEGACY = (
    bytes((EN_CODES['A'], EN_CODES['b'], 0xAF, EN_CODES['c'], 0xFF, 0x00)),
    APPROVED[1], APPROVED[2], APPROVED[3], APPROVED[4],
)
NONZERO_PAGE = 1
# Index zero is deliberately outside the selected window.  The unsupported code is in
# global record five, i.e. the last row selected by C6AC=1.  Low score bytes stay in the
# approved code range so an erroneous byte-offset scan beginning at D61C does not reject
# the fixture for an unrelated field.
NONZERO_LEGACY = (APPROVED[0],) * 5 + (LEGACY[0],)


def _record(name, ordinal, score_base=100000, floor=None):
    assert len(name) == 6
    score = score_base + ordinal
    count = (ordinal + 1) | ((ordinal % 3) << 14)
    floor = ordinal if floor is None else floor
    return (name + score.to_bytes(3, 'little') + bytes((floor,))
            + count.to_bytes(2, 'little'))


def records(names, score_base=100000):
    # Rows 0/1 deliberately exercise the native reserved floor values.  They must render
    # as the full proportional English labels Village/Dragon, never as those kana codes'
    # English-font aliases (`gm`/`n.C`).  Later rows keep ordinary numeric-floor coverage.
    data = b''.join(_record(name, i, score_base,
                            i if i < 2 else i + 1)
                    for i, name in enumerate(names))
    assert len(data) == len(names) * rankvwf.RECORD_STRIDE
    return data


def queue(pb):
    return bytes(pb.memory[QUEUE_START:QUEUE_END])


def queue_dests(pb):
    return tuple(pb.memory[a] | (pb.memory[a + 1] << 8)
                 for a in (0xC006, 0xC048, 0xC08A))


def tile_addr(tile):
    return menuspill.tile_data_addr(tile)


def cell_differences(got, want):
    differences = []
    for row in range(VISIBLE_ROWS):
        for col in range(VISIBLE_COLS):
            offset = row * 32 + col
            if got[offset] != want[offset]:
                differences.append((row, col, got[offset], want[offset]))
    return differences


def format_cell_differences(differences):
    return ' '.join('r%dc%d=$%02X/$%02X' % item for item in differences)


def resolved_planes(result):
    resolved = []
    for row in range(VISIBLE_ROWS):
        for col in range(VISIBLE_COLS):
            tile = result['bg'][row * 32 + col]
            start = tile_addr(tile) - 0x8000
            resolved.append(result['vram'][start:start + 16])
    return tuple(resolved)


def resolved_differences(got, want):
    differences = []
    for index, (got_plane, want_plane) in enumerate(
            zip(resolved_planes(got), resolved_planes(want))):
        if got_plane != want_plane:
            row, col = divmod(index, VISIBLE_COLS)
            offset = row * 32 + col
            differences.append((row, col, got['bg'][offset], want['bg'][offset]))
    return differences


def frame_differences(got, want):
    points = []
    for pixel in range(160 * 144):
        offset = pixel * 3
        if got[offset:offset + 3] != want[offset:offset + 3]:
            points.append((pixel % 160, pixel // 160))
    return points


def visible_sprites(result):
    """Resolve visible OAM entries to positions, attributes and physical planes."""
    height = 16 if result['display'][0] & 0x04 else 8
    sprites = []
    for index in range(40):
        start = index * 4
        y, x, tile, attributes = result['oam'][start:start + 4]
        if not (0 < y < 160 and 0 < x < 168):
            continue
        if height == 16:
            tile &= 0xFE
        plane_start = tile * 16
        planes = result['vram'][plane_start:plane_start + height * 2]
        sprites.append((y, x, attributes, planes))
    return tuple(sprites)


def check_legacy_board(problems, label, legacy, control):
    shadow_diffs = cell_differences(legacy['shadow'], control['shadow'])
    if shadow_diffs:
        problems.append('%s full visible shadow differs in %d cell(s): %s' %
                        (label, len(shadow_diffs),
                         format_cell_differences(shadow_diffs)))

    map_diffs = cell_differences(legacy['bg'], control['bg'])
    if map_diffs:
        problems.append('%s full visible BG map differs in %d cell(s): %s' %
                        (label, len(map_diffs), format_cell_differences(map_diffs)))

    plane_diffs = resolved_differences(legacy, control)
    if plane_diffs:
        problems.append('%s full visible resolved planes differ in %d cell(s): %s' %
                        (label, len(plane_diffs),
                         format_cell_differences(plane_diffs)))

    pixel_diffs = frame_differences(legacy['frame'], control['frame'])
    if pixel_diffs:
        xs = [point[0] for point in pixel_diffs]
        ys = [point[1] for point in pixel_diffs]
        problems.append('%s full framebuffer differs in %d pixel(s), bounds '
                        '(%d,%d)-(%d,%d), first %s' %
                        (label, len(pixel_diffs), min(xs), min(ys), max(xs) + 1,
                         max(ys) + 1, pixel_diffs[:12]))

    if legacy['display'] != control['display']:
        problems.append('%s display registers differ: patched %s control %s' %
                        (label, legacy['display'], control['display']))
    got_sprites = visible_sprites(legacy)
    want_sprites = visible_sprites(control)
    if got_sprites != want_sprites:
        problems.append('%s visible OAM semantics differ: %d patched / %d control '
                        'sprite(s)' % (label, len(got_sprites), len(want_sprites)))
    return len(got_sprites), len(want_sprites)


def run(PyBoy, rom, ram, names, patched, png=None, page_index=0,
        score_base=100000):
    payload = records(names, score_base)
    if not 0 <= page_index <= 0xFF:
        raise ValueError('page index %d is outside one byte' % page_index)
    if page_index + rankvwf.ROWS > len(names):
        raise ValueError('page %d needs %d records, fixture has %d' %
                         (page_index, rankvwf.ROWS, len(names)))
    if len(payload) > STAGE_END - STAGE:
        raise ValueError('%d-byte fixture exceeds bounded rank stage' % len(payload))
    with tempfile.TemporaryDirectory(prefix='rankspill-') as tmp:
        work = os.path.join(tmp, 'rank.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)

        state = {'frame': 0, 'page': 0}
        result = {
            'entries': [], 'raw': 0, 'returns': [], 'arms': [], 'uploads': [],
            'park_before': [], 'park_after': [], 'validations': [],
            'selected_pages': [], 'problems': [],
        }
        pending = []

        def at_page(_ctx=None):
            if state['page'] == 0:
                for i, value in enumerate(payload):
                    pb.memory[STAGE + i] = value
                # The count was measured before this late, non-invasive substitution.
                pb.memory[COUNT] = len(names)
                pb.memory[PAGE_INDEX] = page_index
            result['selected_pages'].append(pb.memory[PAGE_INDEX])
            state['page'] += 1

        def at_validate(_ctx=None):
            result['validations'].append({
                'de': (pb.register_file.D << 8) | pb.register_file.E,
                'mode': pb.register_file.A,
                'page': pb.memory[PAGE_INDEX],
                'product': pb.memory[0xFF90],
            })

        def at_entry(_ctx=None):
            result['entries'].append((state['frame'], pb.register_file.HL,
                                      pb.memory[0xFF44], pb.memory[0xFF40]))

        def at_raw(_ctx=None):
            result['raw'] += 1

        def at_uploader(_ctx=None):
            result['park_before'].append((pb.memory[0xC000], pb.memory[0xC001]))

        def at_arm(_ctx=None):
            rec = {
                'frame': state['frame'],
                'crc': zlib.crc32(queue(pb)) & 0xFFFFFFFF,
                'queue': queue(pb),
                'dests': queue_dests(pb),
                'base': pb.memory[rankvwf.S_BASE],
                'c11a': pb.memory[0xC11A],
            }
            result['arms'].append(rec)
            pending.append(rec)

        def at_upload(_ctx=None):
            if not pending:
                return                         # another renderer's queue transfer
            rec = pending.pop(0)
            got = {
                'frame': state['frame'], 'ly': pb.memory[0xFF44],
                'stat': pb.memory[0xFF41], 'c11a': pb.memory[0xC11A],
                'crc': zlib.crc32(queue(pb)) & 0xFFFFFFFF,
                'dests': queue_dests(pb),
            }
            result['uploads'].append(got)
            if got['crc'] != rec['crc'] or got['dests'] != rec['dests']:
                result['problems'].append('queue changed between arm and VBlank consumer')

        def at_return(_ctx=None):
            dest = pb.register_file.HL
            result['returns'].append((dest, bytes(pb.memory[dest:dest + 6])))
            if patched and len(result['park_after']) < len(result['park_before']):
                result['park_after'].append((pb.memory[0xC000], pb.memory[0xC001]))

        pb.hook_register(31, 0x4662, at_page, None)
        pb.hook_register(31, rankvwf.RAW_ENTRY, at_raw, None)
        pb.hook_register(31, 0x4A5B, at_return, None)
        if patched:
            _, upload_labels = gbasm.assemble(rankvwf.UPLOAD_SRC, rankvwf.UPLOAD_AT)
            pb.hook_register(rankvwf.FAR_BANK, rankvwf.ENTRY_AT, at_entry, None)
            pb.hook_register(rankvwf.AUX_BANK, rankvwf.VALIDATE_AT, at_validate, None)
            pb.hook_register(rankvwf.AUX_BANK, upload_labels['upload'], at_uploader, None)
            pb.hook_register(rankvwf.AUX_BANK, upload_labels['armed'], at_arm, None)
            pb.hook_register(*UPLOAD_START, at_upload, None)

        last_picture = None
        for frame in range(1880):
            state['frame'] = frame
            button = BUTTONS.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if png and frame >= 1840:
                image = pb.screen.image.copy()
                if image.convert('L').getextrema()[0] < 240:
                    last_picture = image

        if png and last_picture is not None:
            last_picture.save(png)
        settled = pb.screen.image.copy().convert('RGB')
        result['page_calls'] = state['page']
        result['shadow'] = bytes(pb.memory[SHADOW:SHADOW_END])
        result['bg'] = bytes(pb.memory[BGMAP:BGMAP + 32 * 18])
        result['vram'] = bytes(pb.memory[0x8000:0x9800])
        result['frame'] = settled.tobytes()
        result['display'] = tuple(pb.memory[addr]
                                  for addr in (0xFF40, 0xFF42, 0xFF43, 0xFF4A,
                                              0xFF4B, 0xFF47, 0xFF48, 0xFF49))
        result['oam'] = bytes(pb.memory[0xFE00:0xFEA0])
        result['tiles'] = {
            tile: bytes(pb.memory[tile_addr(tile):tile_addr(tile) + 16])
            for tile in range(rankvwf.STATIC_POOL_BASE,
                              rankvwf.SPECIAL_POOL_END)
        }
        pb.stop(save=False)
        return result


def add_once(problems, message):
    if message not in problems:
        problems.append(message)


def check(rom, control, native_control, ram, png):
    PyBoy = _import_pyboy()
    profile = menuspill.renderer_profile(rom)
    approved = run(PyBoy, rom, ram, APPROVED, True, png)
    approved_control = run(PyBoy, control, ram, APPROVED, False)
    legacy = run(PyBoy, rom, ram, LEGACY, True)
    legacy_control = run(PyBoy, native_control, ram, LEGACY, False)
    nonzero = run(PyBoy, rom, ram, NONZERO_LEGACY, True,
                  page_index=NONZERO_PAGE, score_base=1)
    nonzero_control = run(PyBoy, native_control, ram, NONZERO_LEGACY, False,
                          page_index=NONZERO_PAGE, score_base=1)
    problems = approved['problems'] + legacy['problems'] + nonzero['problems']

    if approved['page_calls'] != 1 or len(approved['entries']) != 5:
        problems.append('approved coverage: page=%d entries=%d, expected 1/5'
                        % (approved['page_calls'], len(approved['entries'])))
    if approved['raw'] != 0 or approved_control['raw'] != 5:
        problems.append('approved dispatch: patched raw=%d control raw=%d, expected 0/5'
                        % (approved['raw'], approved_control['raw']))
    if len(approved['arms']) != 5 or len(approved['uploads']) != 5:
        problems.append('approved queue coverage: %d arm(s), %d upload(s), expected 5/5'
                        % (len(approved['arms']), len(approved['uploads'])))

    # The native result arrow owns tile $81, so the screen-scoped static allocation no
    # longer shares the no-rankvwf control's private header IDs.  Prove the production
    # map and planes semantically instead of requiring those private IDs to be equal.
    header = 0xC326 - SHADOW
    header_ids = bytes(range(rankvwf.HEADER_POOL_BASE,
                             rankvwf.HEADER_POOL_BASE + 5))
    if approved['shadow'][header:header + 8] != header_ids + b'\0\0\0':
        problems.append('proportional header map is %s, expected %s + three blanks'
                        % (approved['shadow'][header:header + 8].hex(),
                           header_ids.hex()))
    header_tiles = menuspill.compose([EN_CODES[ch] for ch in 'Rankings'], profile)
    if len(header_tiles) != 5:
        problems.append('Rankings raster needs %d tiles, expected 5' % len(header_tiles))
    for i, want_tile in enumerate(header_tiles):
        got_tile = approved['tiles'][rankvwf.HEADER_POOL_BASE + i]
        if got_tile != bytes(want_tile):
            problems.append('header tile $%02X differs: want %s got %s'
                            % (rankvwf.HEADER_POOL_BASE + i,
                               bytes(want_tile).hex(), got_tile.hex()))

    expected_ids = []
    special_text = ('Village', 'Dragon')
    for row, (dest, codes) in enumerate(zip(DESTS, APPROVED)):
        base = rankvwf.POOL_BASE + row * rankvwf.TILES_PER_ROW
        ids = bytes(range(base, base + rankvwf.TILES_PER_ROW))
        expected_ids.append(ids)
        got = approved['shadow'][dest - SHADOW:dest - SHADOW + rankvwf.TILES_PER_ROW]
        if got != ids:
            problems.append('row %d shadow: want %s got %s'
                            % (row, ids.hex(), got.hex()))
        want = menuspill.compose(list(codes), profile)
        want += [bytearray(16) for _ in range(rankvwf.TILES_PER_ROW - len(want))]
        for i in range(rankvwf.TILES_PER_ROW):
            got_tile = approved['tiles'][base + i]
            if got_tile != bytes(want[i]):
                problems.append('row %d tile $%02X differs: want %s got %s'
                                % (row, base + i, bytes(want[i]).hex(), got_tile.hex()))

        # The fixed ranking drawer places the ordinal suffix ten cells before the name.
        # English tile $A0 is colon, and Fay once repainted it as the first Rating
        # fragment.  Keep the suffix semantic as well as pixel-stable: 1., 2., ...
        suffix = dest - SHADOW - 10
        if approved['shadow'][suffix] != EN_CODES['.']:
            problems.append('row %d ordinal suffix is $%02X, expected period $%02X'
                            % (row, approved['shadow'][suffix], EN_CODES['.']))

        # The native fixed-field drawer used Japanese suffix tiles after the floor and
        # attempt count. Keep their English replacements explicit so a VWF pool upload
        # cannot silently turn them back into unrelated graphics.
        attempt_suffix = dest - SHADOW + 32
        if approved['shadow'][attempt_suffix] != EN_CODES['x']:
            problems.append('row %d attempt suffix is $%02X, expected x $%02X'
                            % (row, approved['shadow'][attempt_suffix], EN_CODES['x']))
        if row < len(special_text):
            first = dest - SHADOW + 33
            base = rankvwf.SPECIAL_POOL_BASE + row * rankvwf.SPECIAL_TILES
            got = approved['shadow'][first:first + rankvwf.SPECIAL_TILES]
            want = bytes(range(base, base + rankvwf.SPECIAL_TILES))
            if got != want:
                problems.append('row %d special floor map is %s, expected %s for %s'
                                % (row, got.hex(), want.hex(), special_text[row]))
            want_tiles = menuspill.compose(
                [EN_CODES[ch] for ch in special_text[row]], profile)
            if len(want_tiles) != rankvwf.SPECIAL_TILES:
                problems.append('%s raster needs %d tiles, expected %d'
                                % (special_text[row], len(want_tiles),
                                   rankvwf.SPECIAL_TILES))
            for i, want_tile in enumerate(want_tiles):
                got_tile = approved['tiles'][base + i]
                if got_tile != bytes(want_tile):
                    problems.append('row %d %s tile $%02X differs: want %s got %s'
                                    % (row, special_text[row], base + i,
                                       bytes(want_tile).hex(), got_tile.hex()))
        else:
            floor_suffix = dest - SHADOW + 36
            if approved['shadow'][floor_suffix] != EN_CODES['F']:
                problems.append('row %d floor suffix is $%02X, expected F $%02X'
                                % (row, approved['shadow'][floor_suffix], EN_CODES['F']))

        difficulty = dest - SHADOW + 22
        difficulty_base = (rankvwf.EASY_POOL_BASE, rankvwf.NORM_POOL_BASE,
                           rankvwf.HARD_POOL_BASE)[row % 3]
        got_difficulty = approved['shadow'][difficulty:difficulty + 5]
        want_difficulty = bytes(range(difficulty_base, difficulty_base + 3)) + b'\0\0'
        if got_difficulty != want_difficulty:
            problems.append('row %d proportional difficulty is %s, expected %s'
                            % (row, got_difficulty.hex(), want_difficulty.hex()))
        want_tiles = menuspill.compose(
            [EN_CODES[ch] for ch in DIFFICULTY_TEXT[row % 3].rstrip()], profile)
        want_tiles += [bytearray(16) for _ in range(3 - len(want_tiles))]
        for i, want_tile in enumerate(want_tiles):
            got_tile = approved['tiles'][difficulty_base + i]
            if got_tile != bytes(want_tile):
                problems.append('row %d difficulty tile $%02X differs: want %s got %s'
                                % (row, difficulty_base + i,
                                   bytes(want_tile).hex(), got_tile.hex()))

    excluded = set(range(header, header + 8))
    for dest, codes in zip(DESTS, APPROVED):
        excluded.update(range(dest - SHADOW, dest - SHADOW + rankvwf.NAME_BYTES))
        difficulty = dest - SHADOW + 22
        excluded.update(range(difficulty, difficulty + 5))
    for dest in DESTS[:len(special_text)]:
        excluded.update(range(dest - SHADOW + 33,
                              dest - SHADOW + 33 + rankvwf.SPECIAL_TILES))
    for i, (got, raw) in enumerate(zip(approved['shadow'], approved_control['shadow'])):
        if i not in excluded and got != raw:
            problems.append('fixed shadow cell $%04X changed: patched $%02X control $%02X'
                            % (SHADOW + i, got, raw))
            break

    owners = {}
    for row, dest in enumerate(DESTS):
        first = dest - SHADOW
        for i, tile in enumerate(expected_ids[row]):
            owners[first + i] = tile
    pool_end = rankvwf.POOL_BASE + rankvwf.ROWS * rankvwf.TILES_PER_ROW
    for row, dest in enumerate(DESTS[:len(special_text)]):
        first = dest - SHADOW + 33
        base = rankvwf.SPECIAL_POOL_BASE + row * rankvwf.SPECIAL_TILES
        for i in range(rankvwf.SPECIAL_TILES):
            owners[first + i] = base + i
    for row in range(18):
        for col in range(20):
            offset = row * 32 + col
            tile = approved['bg'][offset]
            in_name_pool = rankvwf.POOL_BASE <= tile < pool_end
            in_special_pool = rankvwf.SPECIAL_POOL_BASE <= tile < rankvwf.SPECIAL_POOL_END
            if (in_name_pool or in_special_pool) and owners.get(offset) != tile:
                problems.append('visible pool tile $%02X at row %d col %d has no owner'
                                % (tile, row, col))

    for i, (arm, upload) in enumerate(zip(approved['arms'], approved['uploads'])):
        base = rankvwf.POOL_BASE + i * rankvwf.TILES_PER_ROW
        # The native 4+4+1 consumer receives overlapping 0..3, 1..4 and 4 windows.
        expected_dest = (tile_addr(base), tile_addr(base + 1),
                         tile_addr(base + rankvwf.TILES_PER_ROW - 1))
        if arm['base'] != base or arm['dests'] != expected_dest:
            problems.append('queue row %d: base/dests %s %s, expected $%02X %s'
                            % (i, arm['base'], arm['dests'], base, expected_dest))
        row_tiles = menuspill.compose(list(APPROVED[i]), profile)
        row_tiles += [bytearray(16)
                      for _ in range(rankvwf.TILES_PER_ROW - len(row_tiles))]
        slot1 = b''.join(bytes(tile) for tile in row_tiles[0:4])
        slot2 = b''.join(bytes(tile) for tile in row_tiles[1:5])
        tile4 = bytes(row_tiles[4])
        queued = arm['queue']
        if queued[2:66] != slot1 or queued[68:132] != slot2 or \
                queued[134:150] != tile4:
            problems.append('queue row %d: payload is not exact 0..3 / 1..4 / 4 '
                            'overlap' % i)
        if arm['c11a'] != 0x0A or upload['c11a'] != 0x0A:
            problems.append('queue row %d: C11A was not $0A at arm/consume' % i)
        if not (144 <= upload['ly'] <= 153) or upload['stat'] & 3 != 1:
            problems.append('queue row %d consumed outside VBlank: LY=%d STAT=$%02X'
                            % (i, upload['ly'], upload['stat']))
    if approved['park_before'] != approved['park_after']:
        problems.append('one-cell queue park was not restored per row: %s -> %s'
                        % (approved['park_before'], approved['park_after']))

    if (legacy['page_calls'] != 1 or legacy_control['page_calls'] != 1 or
            len(legacy['entries']) != 5 or legacy['raw'] != 5 or
            legacy_control['raw'] != 5 or legacy['arms']):
        problems.append('legacy coverage: pages=%d/%d entries=%d raw=%d/%d arms=%d, '
                        'expected 1/1, 5, 5/5, 0' %
                        (legacy['page_calls'], legacy_control['page_calls'],
                         len(legacy['entries']), legacy['raw'], legacy_control['raw'],
                         len(legacy['arms'])))
    legacy_sprites, control_sprites = check_legacy_board(
        problems, 'legacy page 0', legacy, legacy_control)

    if (nonzero['page_calls'] != 1 or nonzero_control['page_calls'] != 1 or
            nonzero['selected_pages'] != [NONZERO_PAGE] or
            nonzero_control['selected_pages'] != [NONZERO_PAGE] or
            len(nonzero['entries']) != 5 or nonzero['raw'] != 5 or
            nonzero_control['raw'] != 5 or nonzero['arms']):
        problems.append('legacy page %d coverage: pages=%d/%d selected=%s/%s '
                        'entries=%d raw=%d/%d arms=%d, expected 1/1, [%d]/[%d], '
                        '5, 5/5, 0' %
                        (NONZERO_PAGE, nonzero['page_calls'],
                         nonzero_control['page_calls'], nonzero['selected_pages'],
                         nonzero_control['selected_pages'], len(nonzero['entries']),
                         nonzero['raw'], nonzero_control['raw'], len(nonzero['arms']),
                         NONZERO_PAGE, NONZERO_PAGE))
    expected_validation = [{
        'de': STAGE + NONZERO_PAGE * rankvwf.RECORD_STRIDE,
        'mode': 2,
        'page': NONZERO_PAGE,
        'product': NONZERO_PAGE * rankvwf.RECORD_STRIDE,
    }]
    if nonzero['validations'] != expected_validation:
        problems.append('legacy page %d prevalidation is %s, expected %s' %
                        (NONZERO_PAGE, nonzero['validations'], expected_validation))
    nonzero_sprites, nonzero_control_sprites = check_legacy_board(
        problems, 'legacy page %d' % NONZERO_PAGE, nonzero, nonzero_control)

    for problem in problems[:20]:
        print('  ' + problem)
    print('rankspill: approved %d rows, %d plane-exact private tiles, %d VBlank '
          'queue transfers; legacy page 0 %d/%d and page %d %d/%d raw fallbacks, '
          'visible OAM %d/%d and %d/%d; %d problem(s)'
          % (len(approved['entries']), rankvwf.ROWS * rankvwf.TILES_PER_ROW,
             len(approved['uploads']), legacy['raw'], legacy_control['raw'],
             NONZERO_PAGE, nonzero['raw'], nonzero_control['raw'], legacy_sprites,
             control_sprites, nonzero_sprites, nonzero_control_sprites, len(problems)))
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--control', required=True,
                        help='matching --dot-font --no-rankvwf build')
    parser.add_argument('--native-control', required=True,
                        help='matching --dot-font --no-menuvwf build')
    parser.add_argument('--ram', default=os.path.join(ROOT, 'saves',
                                                       'shiren_en_ranking_repaired.srm'))
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.control, args.native_control, args.ram):
        if not os.path.exists(path):
            raise SystemExit('rankspill: missing %s' % path)
    native = open(args.native_control, 'rb').read()
    entry_at = menuvwf.FAR_BANK * 0x4000 + menuvwf.FAR_INDEX - 1
    entry = native[entry_at] | (native[entry_at + 1] << 8)
    if entry != 0xFFFF:
        raise SystemExit('rankspill: --native-control menu VWF entry is $%04X, '
                         'expected disabled $FFFF (--dot-font --no-menuvwf)' % entry)
    return check(args.rom, args.control, args.native_control, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
