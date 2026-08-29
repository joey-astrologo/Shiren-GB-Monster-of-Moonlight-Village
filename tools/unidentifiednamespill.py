#!/usr/bin/env python3
"""Regression for naming a floor/inventory unidentified Willow Staff.

Log 3 in ``saves/shiren_log3_unidentified_naming.srm`` starts directly above an
unidentified Willow Staff.  The route opens Menu -> Floor, selects Name from the
six-action item box, and compares the resulting keyboard with fresh New Log name
entry. It then takes the staff, names it ``Stun`` from Items, regionally returns to
complete empty Items chrome before any list text, and backs out to Status. A generated
native-inventory matrix repeats that return with one through four pages and target rows
one through five. That full lifetime is intentionally
different from ``nameflowspill.py``: the dungeon Floor/action VWF can borrow almost
every raw tile used by the keyboard, while the complete native font restore can in
turn overwrite every low-page private status tile.

``tests/fixtures/saves/shiren_en_log3_carried_unidentified_naming.srm`` is the matching
manual-test fixture. ``makeitemnametest.py`` produced it through the real Take action,
without Lua or direct memory writes, and this regression also drives its shorter
Status -> Items -> page 2 row 4 -> Name route.

    python3 tools/unidentifiednamespill.py build/shiren_en.gb
    python3 tools/unidentifiednamespill.py build/shiren_en.gb \
        --png build/unidentified_name.png
    python3 tools/unidentifiednamespill.py build/shiren_en.gb \
        --png-dir build/name_return_frames
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
import menuvwf                                                 # noqa: E402
import statusvwf                                               # noqa: E402
from latinfont import EN_CODES                                 # noqa: E402


FRESH_ENTRY = (4, 0x4B02)
FLOOR_ENTRY = (4, 0x4B20)
DISPATCH = (4, 0x48AA)
SHADOW = 0xC300
SHADOW_BYTES = 32 * 18
INVENTORY = 0xA3B0
OBJECTS = 0xA406

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

CARRIED_NAME = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    3000: 'b', 3400: 'a', 3800: 'right',
    4000: 'down', 4080: 'down', 4160: 'down', 4380: 'a',
    4680: 'down', 4760: 'down', 4840: 'down', 5080: 'a',
}
CARRIED_END_CURSOR = dict(CARRIED_NAME)
CARRIED_END_CURSOR[5400] = ('start', 5)
FRESH_END_CURSOR = dict(FRESH)
FRESH_END_CURSOR[1800] = ('start', 5)
CARRIED_EMPTY_CANCEL = dict(CARRIED_NAME)
CARRIED_EMPTY_CANCEL[5400] = ('b', 5)
# Prove that the returned Items handler is live, not merely visually settled.
CARRIED_EMPTY_CANCEL[5500] = ('up', 5)
# Then exercise the ordinary Items -> Status exit so private Status planes are checked too.
CARRIED_EMPTY_CANCEL[5600] = ('b', 5)

# Supplied Log 3 -> Floor/Take -> Items -> Name -> type ``Stun`` -> End (Start is the
# native shortcut which selects the on-screen End action) -> Items -> status.  The
# generated timing also drives synthetic one- through four-page layouts below; every
# page, row, character and End still enters through the game's real input handlers.
def stun_roundtrip(item_count=9, target_slot=8):
    if not 1 <= item_count <= 20 or not 0 <= target_slot < item_count:
        raise ValueError('invalid inventory Name matrix case')
    script = {
        60: 'start', 120: 'start', 180: 'start', 240: 'start',
        300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
        3000: 'b', 3400: 'down', 3600: 'a', 3900: 'a',
        4300: 'b', 4500: 'a',
    }
    page = target_slot // 5
    row = target_slot % 5
    last_page_at = None
    for index in range(page):
        at = 4700 + 120 * index
        script[at] = 'right'
        last_page_at = at
    row_at = 4900 if last_page_at is None else last_page_at + 200
    for index in range(row):
        script[row_at + 80 * index] = 'down'
    action_at = row_at + 80 * row + 140
    script[action_at] = 'a'
    for index in range(3):
        script[action_at + 300 + 80 * index] = 'down'
    name_at = action_at + 600
    script[name_at] = 'a'
    type_at = name_at + 300
    cursor = {
        type_at: (4, 3),             # S
        type_at + 120: (5, 6),       # t
        type_at + 240: (5, 7),       # u
        type_at + 360: (3, 10),      # n
    }
    for at in cursor:
        script[at] = 'a'
    end_at = type_at + 500
    script[end_at] = ('start', 5)
    script[end_at + 100] = ('a', 5)
    script[end_at + 400] = ('b', 5)
    return script, cursor, end_at + 800


STUN_ROUNDTRIP, STUN_CURSOR, STUN_FRAMES = stun_roundtrip()
STUN = bytes(EN_CODES[ch] for ch in 'Stun')
NAME_MATRIX = ((1, 0), (7, 6), (13, 12), (19, 18), (20, 19))

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


def expected_item_chrome():
    """Visible BG rows 0..15 after the shared Items-entry regional clear."""
    bg = bytearray(16 * 32)

    def box(x, y, width, bottom):
        bg[y * 32 + x:y * 32 + x + width + 2] = \
            bytes((0xB8,)) + bytes((0xBC,)) * width + bytes((0xB9,))
        for row in range(y + 1, bottom):
            bg[row * 32 + x] = 0xBE
            bg[row * 32 + x + width + 1] = 0xBF
        bg[bottom * 32 + x:bottom * 32 + x + width + 2] = \
            bytes((0xBA,)) + bytes((0xBD,)) * width + bytes((0xBB,))

    box(0, 0, 4, 2)
    box(0, 3, 18, 13)
    return bytes(bg)


EXPECTED_ITEM_CHROME = expected_item_chrome()
ITEM_SHAPE = (0, 3, 5, 18, 0x02)


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def snapshot(PyBoy, rom_path, script, frames, ram=None, png=None,
             cursor_overrides=None, status_runtime=None, checkpoint=None,
             inventory_case=None, transition_png_dir=None, transition_from=None):
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
        dispatch_states = []
        end_calls = []
        native_cancel_calls = []
        status_draws = []
        status_uploads = []
        status_fallbacks = []
        status_fallback_states = []
        status_explicit_blanks = []
        item_entries = []
        item_entry_blanks = []
        item_entry_batches = []
        item_entry_done = []
        status_name_accepts = []
        item_name_gates = []
        item_name_cancel_gates = []
        item_rows = []
        native_name_restores = []
        regional_name_starts = []
        regional_name_blanks = []
        regional_name_fonts = []
        regional_name_samples = []
        transition_samples = []
        inventory_builds = []
        inventory_injected = [inventory_case is None]
        checkpoints = {}

        def machine_state():
            depth = pb.memory[0xC534]
            return {
                'frame': frame[0],
                'lcdc': pb.memory[0xFF40],
                'ly': pb.memory[0xFF44],
                'depth': depth,
                'stack': tuple(pb.memory[0xC535 + index]
                               for index in range(depth + 1)),
                'txn': tuple(pb.memory[0xC1B3 + index] for index in range(5)),
                'context': tuple(pb.memory[address] for address in
                                 (0xC6A3, 0xC6A6, 0xC6AA, 0xC6AC,
                                  0xC6BB, 0xC6DE, 0xC11A,
                                  0xC6F3, 0xC6F5, 0xC6F6, 0xC6F7)),
                'shape': tuple(pb.memory[0xC69A + index] for index in range(5)),
            }

        def display_state():
            return {
                'frame': frame[0],
                'lcdc': pb.memory[0xFF40],
                'ly': pb.memory[0xFF44],
                'bg': bytes(pb.memory[0x9800:0x9C00]),
                'window': bytes(pb.memory[0x9C00:0xA000]),
                'tiles': bytes(pb.memory[0x8800:0x9800]),
            }

        def fresh_entry(_context=None):
            fresh_entries.append((frame[0], pb.memory[0xFF40]))

        def floor_entry(_context=None):
            floor_entries.append((frame[0], pb.memory[0xFF40]))

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))
            state = machine_state()
            state['screen'] = pb.register_file.A
            dispatch_states.append(state)

        pb.hook_register(FRESH_ENTRY[0], FRESH_ENTRY[1], fresh_entry, None)
        pb.hook_register(FLOOR_ENTRY[0], FLOOR_ENTRY[1], floor_entry, None)
        pb.hook_register(DISPATCH[0], DISPATCH[1], dispatch, None)
        pb.hook_register(44, 0x4066, lambda _context=None:
                         native_name_restores.append(machine_state()), None)
        pb.hook_register(4, 0x6026, lambda _context=None: end_calls.append(frame[0]), None)
        pb.hook_register(4, 0x5F0B, lambda _context=None:
                         native_cancel_calls.append(machine_state()), None)
        def inventory_build(_context=None):
            indices = []
            for slot in range(20):
                index = pb.memory[INVENTORY + slot]
                if index == 0xFF:
                    break
                indices.append(index)
            if inventory_case is not None and not inventory_injected[0]:
                item_count, target_slot = inventory_case
                target = next((index for index in indices
                               if pb.memory[OBJECTS + 8 * index] == 0x78), None)
                if target is not None:
                    templates = [index for index in indices if index != target]
                    free = [index for index in range(128)
                            if index not in indices and
                            pb.memory[OBJECTS + 8 * index] == 0xFF]
                    fillers = list(templates[:item_count - 1])
                    while len(fillers) < item_count - 1 and free and templates:
                        new = free.pop(0)
                        source = templates[len(fillers) % len(templates)]
                        for offset in range(8):
                            pb.memory[OBJECTS + 8 * new + offset] = \
                                pb.memory[OBJECTS + 8 * source + offset]
                        fillers.append(new)
                    if len(fillers) == item_count - 1:
                        layout = fillers[:target_slot] + [target] + fillers[target_slot:]
                        for slot in range(20):
                            pb.memory[INVENTORY + slot] = \
                                layout[slot] if slot < item_count else 0xFF
                        indices = layout
                        inventory_injected[0] = True
            inventory_builds.append((
                frame[0], tuple(indices),
                tuple(bytes(pb.memory[OBJECTS + 8 * index:
                                      OBJECTS + 8 * index + 8])
                      for index in indices)))

        pb.hook_register(6, 0x4B29, inventory_build, None)
        if status_runtime is not None:
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusdraw'],
                             lambda _context=None: status_draws.append(
                                 (frame[0], pb.memory[0xFF40], pb.memory[0xFF44])), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['uploadlivedone'],
                             lambda _context=None: status_uploads.append(
                                 (frame[0], pb.memory[0xFF44],
                                  pb.memory[statusvwf.S_CAP])), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusready'],
                             lambda _context=None: (
                                 status_fallbacks.append(
                                     (frame[0], pb.memory[0xFF40], pb.memory[0xFF44])),
                                 status_fallback_states.append(machine_state())), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusdisable'],
                             lambda _context=None: status_explicit_blanks.append(
                                 (frame[0], pb.memory[0xFF40], pb.memory[0xFF44],
                                  pb.memory[0xC6A3], pb.memory[0xC1B3],
                                  pb.memory[0xC1B6],
                                  tuple(pb.memory[0xC535 + index]
                                        for index in range(pb.memory[0xC534] + 1)))), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementry'],
                             lambda _context=None: item_entries.append(machine_state()), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementryblank'],
                             lambda _context=None: item_entry_blanks.append(
                                 (machine_state(), display_state())), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementrybatchdone'],
                             lambda _context=None: item_entry_batches.append(
                                 (frame[0], pb.memory[0xFF44], pb.memory[0xC1B3])), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementryblankdone'],
                             lambda _context=None: item_entry_done.append(
                                 (machine_state(), display_state())), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['statusnameaccepted'],
                             lambda _context=None: status_name_accepts.append(
                                 machine_state()), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementryname'],
                             lambda _context=None: item_name_gates.append(
                                 machine_state()), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementrynamecancel'],
                             lambda _context=None: item_name_cancel_gates.append(
                                 machine_state()), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['nameentry'],
                             lambda _context=None: regional_name_starts.append(
                                 (machine_state(), display_state())), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['nameentryblankdone'],
                             lambda _context=None: regional_name_blanks.append(
                                 (machine_state(), display_state())), None)
            pb.hook_register(statusvwf.FAR_BANK, status_runtime['nameentryfontdone'],
                             lambda _context=None: regional_name_fonts.append(
                                 (machine_state(), display_state())), None)
            profile = menuspill.renderer_profile(rom_path)
            pb.hook_register(menuvwf.FAR_BANK, profile['entry'],
                             lambda _context=None: item_rows.append(
                                 (frame[0], pb.register_file.D,
                                  tuple(pb.memory[0xC69A + index]
                                        for index in range(5)))), None)
        for frame[0] in range(frames):
            if cursor_overrides and frame[0] in cursor_overrides:
                pb.memory[0xC6F5], pb.memory[0xC6F0] = cursor_overrides[frame[0]]
            action = script.get(frame[0])
            if action:
                button, duration = action if isinstance(action, tuple) else (action, PRESS_FRAMES)
                pb.button(button, duration)
            pb.tick()
            if regional_name_starts and (not regional_name_fonts or
                                         frame[0] <= regional_name_fonts[-1][0]['frame'] + 80):
                bg = bytes(pb.memory[0x9800:0x9C00])
                visible = bytes(bg[row * 32 + col]
                                for row in range(16) for col in range(20))
                regional_name_samples.append((
                    frame[0], pb.memory[0xFF40], white_frame(pb.screen.image), visible))
                if transition_png_dir:
                    pb.screen.image.save(os.path.join(
                        transition_png_dir, 'name_entry_f%04d.png' % frame[0]))
            if end_calls or (transition_from is not None and frame[0] >= transition_from):
                transition_samples.append((frame[0], pb.memory[0xFF40],
                                           white_frame(pb.screen.image)))
                if transition_png_dir:
                    if end_calls and frame[0] <= end_calls[0] + 50:
                        pb.screen.image.save(os.path.join(
                            transition_png_dir, 'name_return_f%04d.png' % frame[0]))
                    elif (not end_calls and transition_from is not None and
                          frame[0] <= transition_from + 80):
                        pb.screen.image.save(os.path.join(
                            transition_png_dir, 'name_cancel_f%04d.png' % frame[0]))
            if checkpoint is not None and frame[0] == checkpoint:
                checkpoints[checkpoint] = {
                    tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                    for tile in STATUS_TILES
                }

        shadow = bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES])
        keyboard = visible_keyboard(shadow)
        bg = bytes(pb.memory[0x9800:0x9C00])
        visible_bg_keyboard = visible_keyboard(bg)
        tile_ids = set(keyboard) | set(visible_bg_keyboard)
        result = {
            'image': pb.screen.image.copy(),
            'shadow': shadow,
            'keyboard': keyboard,
            'bg': bg,
            'visible_bg_keyboard': visible_bg_keyboard,
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in tile_ids},
            'row': pb.memory[0xC6F5],
            'col': pb.memory[0xC6F0],
            'mode': pb.memory[0xC6F3],
            'lcdc': pb.memory[0xFF40],
            'fresh_entries': fresh_entries,
            'floor_entries': floor_entries,
            'dispatches': dispatches,
            'dispatch_states': dispatch_states,
            'end_calls': end_calls,
            'native_cancel_calls': native_cancel_calls,
            'status_draws': status_draws,
            'status_uploads': status_uploads,
            'status_fallbacks': status_fallbacks,
            'status_fallback_states': status_fallback_states,
            'status_explicit_blanks': status_explicit_blanks,
            'item_entries': item_entries,
            'item_entry_blanks': item_entry_blanks,
            'item_entry_batches': item_entry_batches,
            'item_entry_done': item_entry_done,
            'status_name_accepts': status_name_accepts,
            'item_name_gates': item_name_gates,
            'item_name_cancel_gates': item_name_cancel_gates,
            'item_rows': item_rows,
            'native_name_restores': native_name_restores,
            'regional_name_starts': regional_name_starts,
            'regional_name_blanks': regional_name_blanks,
            'regional_name_fonts': regional_name_fonts,
            'regional_name_samples': regional_name_samples,
            'transition_samples': transition_samples,
            'inventory_builds': inventory_builds,
            'inventory_injected': inventory_injected[0],
            'checkpoints': checkpoints,
            'status_tiles': {
                tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                for tile in STATUS_TILES
            },
            'status_problems': menuspill.status_fragment_problems(pb),
            'name': bytes(pb.memory[0xC6E3:0xC6E3 + 7]),
            'selector': pb.memory[0xC6AC],
        }
        if png:
            result['image'].save(png)
        pb.stop(save=False)
        return result


def name_return_problems(run, label, expected_record_count=None):
    """Validate the exact Name -> disposable Status -> Items -> Status lifetime."""
    problems = []
    if len(run['end_calls']) != 1:
        problems.append('%s reached End %d times, expected once' %
                        (label, len(run['end_calls'])))
        return problems
    end_at = run['end_calls'][0]
    after = lambda entries, frame_of: [entry for entry in entries
                                       if frame_of(entry) >= end_at]

    screens = [screen for frame, screen in run['dispatches'] if frame >= end_at]
    if screens[:3] != [0, 1, 0]:
        problems.append('%s post-End dispatches are %s, expected 0,1,0' %
                        (label, screens[:3]))

    accepts = after(run['status_name_accepts'], lambda entry: entry['frame'])
    gates = after(run['item_name_gates'], lambda entry: entry['frame'])
    if len(accepts) != 1:
        problems.append('%s admitted %d Name status handoffs, expected one' %
                        (label, len(accepts)))
    if len(gates) != 1:
        problems.append('%s reached %d Name Item-entry gates, expected one' %
                        (label, len(gates)))
    if accepts and accepts[0]['txn'][0] != 0:
        problems.append('%s pre-handoff transaction is $%02X, expected idle' %
                        (label, accepts[0]['txn'][0]))
    if gates and gates[0]['txn'][0] != 0x0D:
        problems.append('%s Item-entry transaction is $%02X, expected $0D' %
                        (label, gates[0]['txn'][0]))
    if expected_record_count is not None:
        expected_packed = expected_record_count << 5
        for phase, entries in (('pre-handoff', accepts), ('Item-entry', gates)):
            if entries and entries[0]['txn'][2] != expected_packed:
                problems.append('%s %s retained-row pack is $%02X, expected $%02X' %
                                (label, phase, entries[0]['txn'][2], expected_packed))

    blanks = after(run['status_explicit_blanks'], lambda entry: entry[0])
    if blanks:
        problems.append('%s executed Status LCD-off at %s' %
                        (label, ' '.join('f%d' % entry[0] for entry in blanks)))

    entries = after(run['item_entry_blanks'], lambda entry: entry[0]['frame'])
    done = after(run['item_entry_done'], lambda entry: entry[0]['frame'])
    batches = after(run['item_entry_batches'], lambda entry: entry[0])
    if len(entries) != 1 or len(done) != 1:
        problems.append('%s began/completed %d/%d regional Item entries, expected 1/1' %
                        (label, len(entries), len(done)))
    else:
        origin_machine, origin = entries[0]
        done_machine, complete = done[0]
        if origin_machine['txn'][0] != 0x0D or done_machine['txn'][0] != 0x0D:
            problems.append('%s regional entry lost state $0D (%s -> %s)' %
                            (label, origin_machine['txn'][0], done_machine['txn'][0]))
        if not origin['lcdc'] & 0x80 or not complete['lcdc'] & 0x80:
            problems.append('%s regional entry disabled the LCD' % label)
        if not 0x90 <= complete['ly'] <= 0x99:
            problems.append('%s chrome completed outside VBlank at LY=$%02X' %
                            (label, complete['ly']))
        visible = {row * 32 + col for row in range(16) for col in range(20)}
        wrong = next((offset for offset in visible
                      if complete['bg'][offset] != EXPECTED_ITEM_CHROME[offset]), None)
        changed = next((offset for offset in range(0x400)
                        if offset not in visible and
                        origin['bg'][offset] != complete['bg'][offset]), None)
        if wrong is not None:
            problems.append('%s empty Items chrome differs at BG +$%03X' %
                            (label, wrong))
        if changed is not None:
            problems.append('%s changed locked BG +$%03X' % (label, changed))
        if complete['window'] != origin['window']:
            problems.append('%s changed the persistent Window map' % label)
        if complete['tiles'] != origin['tiles']:
            problems.append('%s repainted tile planes before empty chrome completed' %
                            label)
        rows = [entry for entry in run['item_rows']
                if entry[0] >= end_at and entry[2] == ITEM_SHAPE and 0 <= entry[1] < 5]
        if not rows:
            problems.append('%s never rendered its returned Items rows' % label)
        elif rows[0][0] < done_machine['frame']:
            problems.append('%s rendered Item text at f%d before chrome completed f%d' %
                            (label, rows[0][0], done_machine['frame']))

    if len(batches) != 4:
        problems.append('%s used %d regional batches, expected four' %
                        (label, len(batches)))
    else:
        late = next((entry for entry in batches if not 0x90 <= entry[1] <= 0x99), None)
        if late:
            problems.append('%s regional batch f%d ended at LY=$%02X' %
                            (label, late[0], late[1]))
        states = tuple(entry[2] for entry in batches)
        if states != (0x0D,) * 4:
            problems.append('%s regional batch states are %s, expected four $0D' %
                            (label, states))

    lcd_off = [frame for frame, lcdc, _white in run['transition_samples']
               if frame >= end_at and not lcdc & 0x80]
    whites = [frame for frame, _lcdc, white in run['transition_samples']
              if frame >= end_at and white]
    if lcd_off:
        problems.append('%s produced LCD-off frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in lcd_off[:12])))
    if whites:
        problems.append('%s produced uniform frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in whites[:12])))
    return problems


def name_cancel_problems(run, label):
    """Validate empty carried Name -> disposable Status -> Items cancellation."""
    problems = []
    screens = [screen for _frame, screen in run['dispatches']]
    try:
        name_at = screens.index(9)
    except ValueError:
        problems.append('%s never dispatched Name screen 9' % label)
        return problems
    if screens[name_at:name_at + 3] != [9, 0, 1]:
        problems.append('%s dispatches are %s, expected 9,0,1' %
                        (label, screens[name_at:name_at + 3]))
    if run['end_calls']:
        problems.append('%s entered the End finalizer during B cancel' % label)
    if len(run['native_cancel_calls']) != 1:
        problems.append('%s reached native $5F0B cancel %d times, expected once' %
                        (label, len(run['native_cancel_calls'])))
    if run['name'] != b'\x88' * 7:
        problems.append('%s name buffer is %s, expected empty $88 cells' %
                        (label, run['name'].hex(' ')))

    accepts = [entry for entry in run['status_name_accepts']
               if entry['frame'] >= run['dispatch_states'][name_at]['frame']]
    gates = [entry for entry in run['item_name_cancel_gates']
             if entry['frame'] >= run['dispatch_states'][name_at]['frame']]
    success_gates = [entry for entry in run['item_name_gates']
                     if entry['frame'] >= run['dispatch_states'][name_at]['frame']]
    if len(accepts) != 1:
        problems.append('%s admitted %d Status handoffs, expected one' %
                        (label, len(accepts)))
    if len(gates) != 1:
        problems.append('%s reached %d cancel Item gates, expected one' %
                        (label, len(gates)))
    if success_gates:
        problems.append('%s reached the success Item gate during cancel' % label)
    if accepts:
        if accepts[0]['txn'][0] != 0:
            problems.append('%s pre-handoff transaction is $%02X, expected idle' %
                            (label, accepts[0]['txn'][0]))
        if accepts[0]['context'][7:9] != (0, 1):
            problems.append('%s pre-handoff Name mode/row is %s, expected 0/1' %
                            (label, accepts[0]['context'][7:9]))
    if gates:
        if gates[0]['txn'][0] != 0x0E:
            problems.append('%s cancel Item transaction is $%02X, expected $0E' %
                            (label, gates[0]['txn'][0]))
        if gates[0]['context'][7:9] != (0, 1):
            problems.append('%s Item-gate Name mode/row is %s, expected 0/1' %
                            (label, gates[0]['context'][7:9]))

    if run['status_explicit_blanks']:
        problems.append('%s executed Status LCD-off at %s' %
                        (label, ' '.join('f%d' % entry[0]
                                         for entry in run['status_explicit_blanks'])))
    boundary = accepts[0]['frame'] if accepts else 0
    item_gate_at = gates[0]['frame'] if gates else 1 << 30
    status_draws = [entry for entry in run['status_draws']
                    if boundary <= entry[0] <= item_gate_at]
    if status_draws:
        problems.append('%s rendered disposable Status at %s' %
                        (label, status_draws))

    entries = [entry for entry in run['item_entry_blanks']
               if entry[0]['frame'] >= boundary]
    done = [entry for entry in run['item_entry_done']
            if entry[0]['frame'] >= boundary]
    batches = [entry for entry in run['item_entry_batches'] if entry[0] >= boundary]
    if len(entries) != 1 or len(done) != 1:
        problems.append('%s began/completed %d/%d regional Item entries, expected 1/1' %
                        (label, len(entries), len(done)))
    else:
        origin_machine, origin = entries[0]
        done_machine, complete = done[0]
        if origin_machine['txn'][0] != 0x0E or done_machine['txn'][0] != 0x0E:
            problems.append('%s regional entry lost state $0E (%s -> %s)' %
                            (label, origin_machine['txn'][0], done_machine['txn'][0]))
        if not origin['lcdc'] & 0x80 or not complete['lcdc'] & 0x80:
            problems.append('%s disabled the LCD during regional entry' % label)
        if not 0x90 <= complete['ly'] <= 0x99:
            problems.append('%s chrome completed outside VBlank at LY=$%02X' %
                            (label, complete['ly']))
        visible = {row * 32 + col for row in range(16) for col in range(20)}
        wrong = next((offset for offset in visible
                      if complete['bg'][offset] != EXPECTED_ITEM_CHROME[offset]), None)
        changed = next((offset for offset in range(0x400)
                        if offset not in visible and
                        origin['bg'][offset] != complete['bg'][offset]), None)
        if wrong is not None:
            problems.append('%s empty Items chrome differs at BG +$%03X' %
                            (label, wrong))
        if changed is not None:
            problems.append('%s changed locked BG +$%03X' % (label, changed))
        if complete['window'] != origin['window']:
            problems.append('%s changed the persistent Window map' % label)
        if complete['tiles'] != origin['tiles']:
            problems.append('%s repainted tile planes before chrome completed' % label)
        rows = [entry for entry in run['item_rows']
                if entry[0] >= boundary and entry[2] == ITEM_SHAPE and 0 <= entry[1] < 5]
        if not rows:
            problems.append('%s never rendered returned Items rows' % label)
        elif rows[0][0] < done_machine['frame']:
            problems.append('%s rendered Item text at f%d before chrome completed f%d' %
                            (label, rows[0][0], done_machine['frame']))

    if len(batches) != 4:
        problems.append('%s used %d regional batches, expected four' %
                        (label, len(batches)))
    else:
        states = tuple(entry[2] for entry in batches)
        if states != (0x0E,) * 4:
            problems.append('%s regional batch states are %s, expected four $0E' %
                            (label, states))
        late = next((entry for entry in batches if not 0x90 <= entry[1] <= 0x99), None)
        if late:
            problems.append('%s regional batch f%d ended at LY=$%02X' %
                            (label, late[0], late[1]))

    lcd_off = [frame for frame, lcdc, _white in run['transition_samples']
               if not lcdc & 0x80]
    whites = [frame for frame, _lcdc, white in run['transition_samples'] if white]
    if lcd_off:
        problems.append('%s produced LCD-off frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in lcd_off[:12])))
    if whites:
        problems.append('%s produced uniform frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in whites[:12])))
    if run['selector'] != 7:
        problems.append('%s post-return Up left selector %d, expected 7' %
                        (label, run['selector']))
    return problems


def name_entry_problems(run, label):
    """Validate carried Items -> Name ownership before the keyboard initializer runs."""
    problems = []
    starts = run['regional_name_starts']
    blanks = run['regional_name_blanks']
    fonts = run['regional_name_fonts']
    if (len(starts), len(blanks), len(fonts)) != (1, 1, 1):
        problems.append('%s regional start/blank/font counts are %d/%d/%d' %
                        (label, len(starts), len(blanks), len(fonts)))
        return problems
    start_machine, origin = starts[0]
    blank_machine, blank = blanks[0]
    font_machine, font = fonts[0]
    if start_machine['depth'] != 3 or start_machine['stack'] != (0, 1, 2, 9):
        problems.append('%s admitted stack %s, expected 0,1,2,9' %
                        (label, start_machine['stack']))
    if not origin['lcdc'] & 0x80 or not blank['lcdc'] & 0x80 or not font['lcdc'] & 0x80:
        problems.append('%s disabled LCD at a regional boundary' % label)
    visible_offsets = {row * 32 + col for row in range(16) for col in range(20)}
    dirty = next((offset for offset in visible_offsets if blank['bg'][offset]), None)
    locked = next((offset for offset in range(0x400)
                   if offset not in visible_offsets and
                   origin['bg'][offset] != blank['bg'][offset]), None)
    if dirty is not None:
        problems.append('%s blank boundary retains BG +$%03X=$%02X' %
                        (label, dirty, blank['bg'][dirty]))
    if locked is not None:
        problems.append('%s changed locked BG +$%03X while retiring Items' %
                        (label, locked))
    if blank['window'] != origin['window'] or font['window'] != origin['window']:
        problems.append('%s changed the persistent status Window' % label)
    if font['bg'] != blank['bg']:
        changed = next(offset for offset in range(0x400)
                       if font['bg'][offset] != blank['bg'][offset])
        problems.append('%s exposed BG +$%03X during native font batches' %
                        (label, changed))
    if font_machine['txn'][0] != 0:
        problems.append('%s left transaction $%02X after retiring the Item owner' %
                        (label, font_machine['txn'][0]))
    samples = [entry for entry in run['regional_name_samples']
               if start_machine['frame'] <= entry[0] <= font_machine['frame'] + 80]
    lcd_off = [frame for frame, lcdc, _white, _visible in samples if not lcdc & 0x80]
    whites = [frame for frame, _lcdc, white, _visible in samples if white]
    if lcd_off:
        problems.append('%s produced LCD-off frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in lcd_off[:12])))
    if whites:
        problems.append('%s produced uniform full-screen frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in whites[:12])))
    after_blank = [entry for entry in samples if entry[0] >= blank_machine['frame']]
    borders = set(range(0xB8, 0xC0))
    border_at = next((frame for frame, _lcdc, _white, visible in after_blank
                      if any(tile in borders for tile in visible)), None)
    text_at = next((frame for frame, _lcdc, _white, visible in after_blank
                    if any(tile and tile not in borders for tile in visible)), None)
    if border_at is None or text_at is None:
        problems.append('%s never published complete Name chrome/text' % label)
    elif text_at < border_at:
        problems.append('%s exposed text at f%d before chrome at f%d' %
                        (label, text_at, border_at))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_log3_unidentified_naming.srm'))
    parser.add_argument('--manual-ram', default=os.path.join(
        ROOT, 'tests/fixtures/saves/shiren_en_log3_carried_unidentified_naming.srm'))
    parser.add_argument('--png')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for path in (args.rom, args.ram, args.manual_ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiednamespill: missing %s' % path)

    PyBoy = _import_pyboy()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    fresh = snapshot(PyBoy, args.rom, FRESH, 1900)
    routed = snapshot(PyBoy, args.rom, WILLOW_STAFF_NAME, 4700,
                      args.ram, args.png)
    font = statusvwf.propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in statusvwf.SLOT_CODES)
    _status_code, status_labels = gbasm.assemble(
        statusvwf._source(widths), statusvwf.CODE_AT)
    roundtrip = snapshot(
        PyBoy, args.rom, STUN_ROUNDTRIP, STUN_FRAMES, args.ram,
        cursor_overrides=STUN_CURSOR,
        status_runtime=status_labels, checkpoint=4400,
        transition_png_dir=args.png_dir)
    manual = snapshot(
        PyBoy, args.rom, CARRIED_NAME, 5600, args.manual_ram,
        status_runtime=status_labels)
    manual_end_cursor = snapshot(
        PyBoy, args.rom, CARRIED_END_CURSOR, 5500, args.manual_ram,
        status_runtime=status_labels)
    fresh_end_cursor = snapshot(PyBoy, args.rom, FRESH_END_CURSOR, 1900)
    empty_cancel = snapshot(
        PyBoy, args.rom, CARRIED_EMPTY_CANCEL, 5750, args.manual_ram,
        status_runtime=status_labels, transition_png_dir=args.png_dir,
        transition_from=5380)
    problems = []

    problems.extend(name_entry_problems(manual, 'manual carried fixture entry'))
    if manual['native_name_restores']:
        problems.append('manual carried fixture used %d native restores, expected zero' %
                        len(manual['native_name_restores']))
    if not manual['dispatches'] or manual['dispatches'][-1][1] != 9:
        problems.append('manual carried fixture did not settle on Name screen 9')
    if manual['keyboard'] != fresh['keyboard']:
        problems.append('manual carried fixture keyboard differs from fresh Start naming')
    if manual_end_cursor['visible_bg_keyboard'] != fresh_end_cursor['visible_bg_keyboard']:
        problems.append('manual End cursor BG map differs from fresh Start naming')
    end_tiles = set(manual_end_cursor['visible_bg_keyboard'])
    if not set((0xC7, 0xC8, 0xC9)).issubset(end_tiles):
        problems.append('manual End cursor did not expose native $C7-$C9 underline')
    end_plane_diffs = [tile for tile in sorted(end_tiles)
                       if manual_end_cursor['tiles'].get(tile) !=
                       fresh_end_cursor['tiles'].get(tile)]
    if end_plane_diffs:
        problems.append('manual End cursor planes differ from fresh for %s' %
                        ' '.join('$%02X' % tile for tile in end_plane_diffs))
    if manual_end_cursor['native_name_restores']:
        problems.append('manual End cursor used native restore after regional entry')
    problems.extend(name_cancel_problems(empty_cancel, 'manual empty-Name B cancel'))
    problems.extend('empty-Name B cancel: ' + problem
                    for problem in empty_cancel['status_problems'])

    if len(fresh['fresh_entries']) != 1:
        problems.append('fresh route reached fresh name entry %d times, expected once' %
                        len(fresh['fresh_entries']))
    if fresh['floor_entries']:
        problems.append('fresh route unexpectedly reached Floor name entry')
    if len(fresh['native_name_restores']) != 1 or fresh['regional_name_starts']:
        problems.append('fresh Start naming used %d native / %d regional restores' %
                        (len(fresh['native_name_restores']),
                         len(fresh['regional_name_starts'])))
    if len(routed['floor_entries']) != 1:
        problems.append('Willow Staff route reached Floor name entry %d times, expected once' %
                        len(routed['floor_entries']))
    if routed['fresh_entries']:
        problems.append('Willow Staff route unexpectedly reached fresh name entry')
    if len(routed['native_name_restores']) != 1 or routed['regional_name_starts']:
        problems.append('Floor naming used %d native / %d regional restores' %
                        (len(routed['native_name_restores']),
                         len(routed['regional_name_starts'])))
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
    screens = [screen for _frame, screen in roundtrip['dispatches']]
    try:
        name_at = screens.index(9)
        if screens[name_at:name_at + 4] != [9, 0, 1, 0]:
            problems.append('rename return dispatches are %s, expected 9,0,1,0' %
                            screens[name_at:name_at + 4])
    except ValueError:
        problems.append('inventory rename never dispatched name screen 9')

    problems.extend(name_return_problems(roundtrip, 'inventory rename', 4))
    problems.extend(name_entry_problems(roundtrip, 'inventory rename entry'))
    if roundtrip['native_name_restores']:
        problems.append('Floor Take + inventory route used %d native restores, expected '
                        'none before carried naming' %
                        len(roundtrip['native_name_restores']))
    end_at = roundtrip['end_calls'][0] if roundtrip['end_calls'] else STUN_FRAMES
    after_name_draws = [entry for entry in roundtrip['status_draws']
                        if entry[0] >= end_at]
    if len(after_name_draws) != 1 or not after_name_draws[0][1] & 0x80:
        problems.append('post-Name status painters are %s, expected only the final '
                        'LCD-on Items -> Status draw' % (after_name_draws,))
    after_name_uploads = [entry for entry in roundtrip['status_uploads']
                          if entry[0] >= end_at]
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

    matrix_results = []
    for item_count, target_slot in NAME_MATRIX:
        script, cursor, frames = stun_roundtrip(item_count, target_slot)
        case = snapshot(
            PyBoy, args.rom, script, frames, args.ram,
            cursor_overrides=cursor, status_runtime=status_labels,
            inventory_case=(item_count, target_slot))
        page = target_slot // 5 + 1
        row = target_slot % 5
        label = '%d-item page-%d row-%d Name' % (item_count, page, row + 1)
        if not case['inventory_injected']:
            problems.append('%s fixture was not injected' % label)
        if case['name'][:len(STUN) + 1] != STUN + b'\xFF':
            problems.append('%s stored %s, expected Stun + terminator' %
                            (label, case['name'].hex(' ')))
        record_count = min(5, item_count - 5 * (target_slot // 5))
        problems.extend(name_return_problems(case, label, record_count))
        problems.extend(name_entry_problems(case, label + ' entry'))
        if case['native_name_restores']:
            problems.append('%s used %d native restores before carried naming, expected '
                            'none' % (label, len(case['native_name_restores'])))
        problems.extend('%s: %s' % (label, problem)
                        for problem in case['status_problems'])
        matrix_results.append((item_count, page, row + 1, record_count))

    for problem in problems:
        print('  ' + problem)
    floor_entry = routed['floor_entries'][0] if routed['floor_entries'] else None
    print('unidentifiednamespill: Willow Staff Floor -> Name + inventory Stun -> '
          'Items -> status + empty-Name B -> responsive Items; Name matrix %s; entry=%s; '
          '%d keyboard / %d status tile plane(s); %d problem(s)' %
          (' '.join('%di/p%d/r%d/%drec' % result for result in matrix_results),
           floor_entry, len(all_tiles), len(STATUS_TILES), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
