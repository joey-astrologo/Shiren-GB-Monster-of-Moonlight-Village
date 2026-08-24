#!/usr/bin/env python3
"""Regression for naming a floor/inventory unidentified Willow Staff.

Log 3 in ``saves/shiren_log3_unidentified_naming.srm`` starts directly above an
unidentified Willow Staff.  The route opens Menu -> Floor, selects Name from the
six-action item box, and compares the resulting keyboard with fresh New Log name
entry.  It then takes the staff, names it ``Stun`` from the last inventory page,
returns to Items, and backs out to status.  That full lifetime is intentionally
different from ``nameflowspill.py``: the dungeon Floor/action VWF can borrow almost
every raw tile used by the keyboard, while the complete native font restore can in
turn overwrite every low-page private status tile.

    python3 tools/unidentifiednamespill.py build/shiren_en.gb
    python3 tools/unidentifiednamespill.py build/shiren_en.gb \
        --png build/unidentified_name.png
"""
import argparse
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gbrun import PRESS_FRAMES, _import_pyboy                  # noqa: E402
import gbasm                                                   # noqa: E402
import menuspill                                               # noqa: E402
import statusvwf                                               # noqa: E402
from latinfont import EN_CODES                                 # noqa: E402


FRESH_ENTRY = (4, 0x4B02)
FLOOR_ENTRY = (4, 0x4B20)
DISPATCH = (4, 0x48AA)
SHADOW = 0xC300
SHADOW_BYTES = 32 * 18

# Fresh cart -> Adventure -> New Game -> Easy -> name entry.
FRESH = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1320: 'a', 1450: 'a', 1600: 'a',
}

# Supplied Log 3 -> dungeon -> Menu -> Floor -> Name.  The Floor action order is
# Take / Wave / Toss / Swap / Name / Info for the Willow Staff.
WILLOW_STAFF_NAME = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    3000: 'b', 3400: 'down', 3600: 'a',
    3900: 'down', 3980: 'down', 4060: 'down', 4140: 'down',
    4260: 'a',
}

# Supplied Log 3 -> Floor/Take -> Items/last row -> Name -> type ``Stun`` -> End
# (Start is the native shortcut which selects the on-screen End action) -> Items ->
# status.  Direct row/column positioning only avoids hundreds of d-pad frames; every
# character and End still enters through the game's real A-button picker/finalizer.
STUN_ROUNDTRIP = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    3000: 'b', 3400: 'down', 3600: 'a', 3900: 'a',
    4300: 'b', 4500: 'a', 4700: 'left',
    4900: 'down', 4980: 'down', 5060: 'down', 5200: 'a',
    5500: 'down', 5580: 'down', 5660: 'down', 5800: 'a',
    6100: 'a', 6220: 'a', 6340: 'a', 6460: 'a',
    6600: ('start', 5), 6700: ('a', 5), 7000: ('b', 5),
}
STUN_CURSOR = {
    6100: (4, 3),       # S
    6220: (5, 6),       # t
    6340: (5, 7),       # u
    6460: (3, 10),      # n
}
STUN = bytes(EN_CODES[ch] for ch in 'Stun')

STATUS_TILES = tuple(sorted(
    {tile for base, cap in statusvwf.PRIVATE_RUNS.values()
     for tile in range(base, base + cap)} |
    set(statusvwf.WEAPON_TILES + statusvwf.SHIELD_TILES)))

# The item name field occupies the top three tile rows and deliberately differs
# from a fresh player-name field.  Rows 3..15 are the complete shared keyboard.
KEYBOARD_ROWS = range(3, 16)
def tile_vram(tile):
    """Physical VRAM address for an $8800-mode signed BG tile ID."""
    return 0x9000 + 16 * tile if tile < 0x80 else 0x8800 + 16 * (tile - 0x80)


def visible_keyboard(shadow):
    return bytes(shadow[row * 32 + col]
                 for row in KEYBOARD_ROWS for col in range(20))


def snapshot(PyBoy, rom_path, script, frames, ram=None, png=None,
             cursor_overrides=None, status_runtime=None, checkpoint=None):
    with tempfile.TemporaryDirectory(prefix='unidentifiednamespill-') as tmp:
        work = os.path.join(tmp, 'name.gb')
        shutil.copyfile(rom_path, work)
        if ram:
            shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        fresh_entries = []
        floor_entries = []
        dispatches = []
        end_calls = []
        status_draws = []
        status_uploads = []
        status_fallbacks = []
        checkpoints = {}

        def fresh_entry(_context=None):
            fresh_entries.append((frame[0], pb.memory[0xFF40]))

        def floor_entry(_context=None):
            floor_entries.append((frame[0], pb.memory[0xFF40]))

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))

        pb.hook_register(FRESH_ENTRY[0], FRESH_ENTRY[1], fresh_entry, None)
        pb.hook_register(FLOOR_ENTRY[0], FLOOR_ENTRY[1], floor_entry, None)
        pb.hook_register(DISPATCH[0], DISPATCH[1], dispatch, None)
        pb.hook_register(4, 0x6026, lambda _context=None: end_calls.append(frame[0]), None)
        if status_runtime is not None:
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusdraw'],
                             lambda _context=None: status_draws.append(
                                 (frame[0], pb.memory[0xFF40], pb.memory[0xFF44])), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['uploadlivedone'],
                             lambda _context=None: status_uploads.append(
                                 (frame[0], pb.memory[0xFF44],
                                  pb.memory[statusvwf.S_CAP])), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusready'],
                             lambda _context=None: status_fallbacks.append(
                                 (frame[0], pb.memory[0xFF40], pb.memory[0xFF44])), None)
        for frame[0] in range(frames):
            if cursor_overrides and frame[0] in cursor_overrides:
                pb.memory[0xC6F5], pb.memory[0xC6F0] = cursor_overrides[frame[0]]
            action = script.get(frame[0])
            if action:
                button, duration = action if isinstance(action, tuple) else (action, PRESS_FRAMES)
                pb.button(button, duration)
            pb.tick()
            if checkpoint is not None and frame[0] == checkpoint:
                checkpoints[checkpoint] = {
                    tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                    for tile in STATUS_TILES
                }

        shadow = bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES])
        keyboard = visible_keyboard(shadow)
        tile_ids = set(keyboard)
        result = {
            'image': pb.screen.image.copy(),
            'shadow': shadow,
            'keyboard': keyboard,
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in tile_ids},
            'row': pb.memory[0xC6F5],
            'col': pb.memory[0xC6F0],
            'mode': pb.memory[0xC6F3],
            'lcdc': pb.memory[0xFF40],
            'fresh_entries': fresh_entries,
            'floor_entries': floor_entries,
            'dispatches': dispatches,
            'end_calls': end_calls,
            'status_draws': status_draws,
            'status_uploads': status_uploads,
            'status_fallbacks': status_fallbacks,
            'checkpoints': checkpoints,
            'status_tiles': {
                tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                for tile in STATUS_TILES
            },
            'status_problems': menuspill.status_fragment_problems(pb),
            'name': bytes(pb.memory[0xC6E3:0xC6E3 + 7]),
        }
        if png:
            result['image'].save(png)
        pb.stop(save=False)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_log3_unidentified_naming.srm'))
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiednamespill: missing %s' % path)

    PyBoy = _import_pyboy()
    fresh = snapshot(PyBoy, args.rom, FRESH, 1900)
    routed = snapshot(PyBoy, args.rom, WILLOW_STAFF_NAME, 4700,
                      args.ram, args.png)
    font = statusvwf.propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in statusvwf.SLOT_CODES)
    _status_code, status_labels = gbasm.assemble(
        statusvwf._source(widths), statusvwf.CODE_AT)
    roundtrip = snapshot(
        PyBoy, args.rom, STUN_ROUNDTRIP, 7400, args.ram,
        cursor_overrides=STUN_CURSOR,
        status_runtime=status_labels, checkpoint=4400)
    problems = []

    if len(fresh['fresh_entries']) != 1:
        problems.append('fresh route reached fresh name entry %d times, expected once' %
                        len(fresh['fresh_entries']))
    if fresh['floor_entries']:
        problems.append('fresh route unexpectedly reached Floor name entry')
    if len(routed['floor_entries']) != 1:
        problems.append('Willow Staff route reached Floor name entry %d times, expected once' %
                        len(routed['floor_entries']))
    if routed['fresh_entries']:
        problems.append('Willow Staff route unexpectedly reached fresh name entry')
    if not any(screen == 20 for _frame, screen in routed['dispatches']):
        problems.append('Willow Staff route never dispatched Floor screen 20')
    if (routed['row'], routed['col']) != (fresh['row'], fresh['col']):
        problems.append('Willow Staff keyboard cursor is %s, fresh is %s' %
                        ((routed['row'], routed['col']), (fresh['row'], fresh['col'])))
    if not routed['lcdc'] & 0x80:
        problems.append('Willow Staff name screen left the LCD disabled')

    if routed['keyboard'] != fresh['keyboard']:
        diffs = [index for index, pair in enumerate(
            zip(routed['keyboard'], fresh['keyboard'])) if pair[0] != pair[1]]
        problems.append('keyboard shadow differs from fresh at %s' %
                        ' '.join('$%03X' % index for index in diffs[:12]))

    all_tiles = sorted(set(fresh['tiles']) | set(routed['tiles']))
    plane_diffs = [tile for tile in all_tiles
                   if fresh['tiles'].get(tile) != routed['tiles'].get(tile)]
    if plane_diffs:
        problems.append('keyboard glyph planes differ from fresh for %s' %
                        ' '.join('$%02X' % tile for tile in plane_diffs[:16]))

    if roundtrip['name'][:len(STUN) + 1] != STUN + b'\xFF':
        problems.append('inventory rename stored %s, expected Stun + terminator' %
                        roundtrip['name'].hex(' '))
    if len(roundtrip['end_calls']) != 1:
        problems.append('inventory rename reached End %d times, expected once' %
                        len(roundtrip['end_calls']))
    screens = [screen for _frame, screen in roundtrip['dispatches']]
    try:
        name_at = screens.index(9)
        if screens[name_at:name_at + 4] != [9, 0, 1, 0]:
            problems.append('rename return dispatches are %s, expected 9,0,1,0' %
                            screens[name_at:name_at + 4])
    except ValueError:
        problems.append('inventory rename never dispatched name screen 9')

    after_name_draws = [entry for entry in roundtrip['status_draws'] if entry[0] > 5800]
    if len(after_name_draws) != 2:
        problems.append('rename return ran status painter %d times, expected twice' %
                        len(after_name_draws))
    elif not (not (after_name_draws[0][1] & 0x80) and
              (after_name_draws[1][1] & 0x80)):
        problems.append('post-Name status painters are %s, expected LCD-off reconstruction '
                        'then LCD-on direct Items pop' % (after_name_draws,))
    after_name_fallbacks = [entry for entry in roundtrip['status_fallbacks']
                            if entry[0] > 5800]
    if len(after_name_fallbacks) != 1:
        problems.append('rename return used conservative status fallback %d times, '
                        'expected once for Name -> Items reconstruction' %
                        len(after_name_fallbacks))
    after_name_uploads = [entry for entry in roundtrip['status_uploads']
                          if entry[0] > 5800]
    expected_caps = (6, 7, 5, 2, 4, 4, 4, 4, 4)
    if tuple(cap for _frame, _ly, cap in after_name_uploads) != expected_caps:
        problems.append('direct renamed-Items exit upload caps are %s, expected %s' %
                        (tuple(cap for _frame, _ly, cap in after_name_uploads),
                         expected_caps))
    late_uploads = [entry for entry in after_name_uploads
                    if not 0x90 <= entry[1] <= 0x99]
    if late_uploads:
        problems.append('direct renamed-Items exit uploads escaped VBlank: %s' %
                        (late_uploads,))

    before = roundtrip['checkpoints'].get(4400)
    if before is None:
        problems.append('inventory route missed the pre-Name status checkpoint')
    else:
        changed = [tile for tile in STATUS_TILES
                   if before[tile] != roundtrip['status_tiles'][tile]]
        if changed:
            problems.append('rename return changed private status planes %s' %
                            ' '.join('$%02X' % tile for tile in changed[:16]))
    problems.extend('rename return: ' + problem
                    for problem in roundtrip['status_problems'])

    for problem in problems:
        print('  ' + problem)
    floor_entry = routed['floor_entries'][0] if routed['floor_entries'] else None
    print('unidentifiednamespill: Willow Staff Floor -> Name + inventory Stun -> '
          'Items -> status; entry=%s; %d keyboard / %d status tile plane(s); '
          '%d problem(s)' %
          (floor_entry, len(all_tiles), len(STATUS_TILES), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
