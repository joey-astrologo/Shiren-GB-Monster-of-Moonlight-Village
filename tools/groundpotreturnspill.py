#!/usr/bin/env python3
"""Trace and guard ground-Pot See -> Floor/Action returns.

The bundled Log-3 save reaches the only seven-row ground-Pot Action picker without Lua.
This is not the carried-Pot ``0,1,2,12/13 -> Items`` lifetime: See retains screen 7 as
its parent.  B must keep the viewer intact until complete screen-7 box-5/box-6 chrome is
available, then reveal only complete Action rows, with the hardware Window unchanged.
``--screen20`` drives the independent bundled Storage Pot route and applies the same
contract to its saved six-row box-39 parent. ``--items-first`` first opens and closes
Items, proving its completed redraw-tail phase cannot leak into either later Floor path.
For screen 7 the fixture then presses B from the restored Floor page, requires the exact
LCD-on Status handoff, and proves prompt input by moving back to Items. Screen 20 does
not run that final step because its native B destination is the dungeon field.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import gbasm                                                       # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import potreturnspill                                              # noqa: E402
import statusvwf                                                   # noqa: E402


SCREEN7_RAM = os.path.join(ROOT, 'saves',
                           'shiren_en_log3_unidentified_pot_crash.srm')
SCREEN7_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'down', 2800: 'a',       # Menu -> alternate Floor screen 7
    2880: 'down', 3000: 'a',                 # seven-row Action -> See
    3500: 'b',                               # See -> screen-7 parent
    3900: 'b',                               # screen-7 Floor -> Status
    4100: 'up', 4140: 'a',                   # prove Status input -> Items
}
SCREEN7_ITEMS_FIRST_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'a',                       # Status -> Items
    3200: 'b',                                  # Items -> Status
    3400: 'down', 3500: 'a',                    # Status -> alternate Floor screen 7
    3600: 'down', 3720: 'a',                    # seven-row Action -> See
    4220: 'b',                                  # See -> screen-7 parent
    4620: 'b',                                  # screen-7 Floor -> Status
    4820: 'up', 4860: 'a',                      # prove Status input -> Items
}
SCREEN20_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
SCREEN20_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 500: 'a',
    2200: 'b', 2280: 'down', 2360: 'a',       # Menu -> Floor screen 20
    2480: 'down', 2600: 'a',                 # six-row Action -> empty-Pot See
    3000: 'b',                               # See -> screen-20 parent
}
SCREEN20_ITEMS_FIRST_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 500: 'a',
    2200: 'b', 2280: 'a',                       # Status -> Items
    2800: 'b',                                  # Items -> Status
    3000: 'down', 3120: 'a',                    # Status -> Floor screen 20
    3240: 'down', 3360: 'a',                    # six-row Action -> empty-Pot See
    3760: 'b',                                  # See -> screen-20 parent
}


def stack(pb):
    depth = pb.memory[0xC534]
    return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))


def snapshot(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'image': pb.screen.image.copy(),
        'lcdc': pb.memory[0xFF40],
        'screen': pb.memory[0xC6A3],
        'state': pb.memory[0xC1B3],
        'phase': pb.memory[0xC1B6],
        'stack': stack(pb),
        'shape': tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)),
        'rows': pb.memory[0xC6BB],
    }


def resolved(state, rows=range(16), cols=range(20), layer='bg'):
    out = []
    for row in rows:
        for col in cols:
            tile = state[layer][row * 32 + col]
            start = (0x800 + tile * 16 if tile < 0x80 else (tile - 0x80) * 16)
            out.append(state['tiles'][start:start + 16])
    return tuple(out)


def visible_cells(state, layer='bg', rows=range(16)):
    """Return visible tile IDs together with their currently resolved planes."""
    out = []
    for row in rows:
        for col in range(20):
            tile = state[layer][row * 32 + col]
            start = (0x800 + tile * 16 if tile < 0x80 else (tile - 0x80) * 16)
            out.append((tile, state['tiles'][start:start + 16]))
    return tuple(out)


def uniform_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def chrome_problems(bg, target, rows, parent_action_top=None):
    """Return incomplete cells for visible box 5 and the exact Action box."""
    problems = []
    if bg[0:20] != bytes((0xB8,) + (0xBC,) * 18 + (0xB9,)):
        problems.append('title-top')
    if bg[32] != 0xBE:
        problems.append('title-left')
    # Screen 20 owns the full-width box-5 title.  Screen 7 instead overlaps that
    # row with box 6, whose top-right corner legitimately occupies column 19.
    if target == 20 and bg[51] != 0xBF:
        problems.append('title-right')
    if target == 20 and bg[64:84] != bytes(
            (0xBA,) + (0xBD,) * 18 + (0xBB,)):
        problems.append('title-bottom')
    y = 1 if target == 7 else 3
    action_top = bg[y * 32 + 13:y * 32 + 20]
    plain_action_top = bytes((0xB8,) + (0xBC,) * 5 + (0xB9,))
    # Screen 20's item-page indicator intentionally replaces five cells of this
    # top edge after the empty box is published.  Both the uninterrupted edge and
    # the exact outgoing indicator edge are complete parent chrome.
    accepted_action_tops = (plain_action_top, parent_action_top)
    if action_top not in accepted_action_tops:
        problems.append('action-top')
    bottom = y + 2 * rows
    for row in range(y + 1, bottom):
        if bg[row * 32 + 13] != 0xBE or bg[row * 32 + 19] != 0xBF:
            problems.append('action-side-%d' % row)
    if bg[bottom * 32 + 13:bottom * 32 + 20] != bytes(
            (0xBA,) + (0xBD,) * 5 + (0xBB,)):
        problems.append('action-bottom')
    return problems


def chrome_complete(bg, target, rows, parent_action_top=None):
    return not chrome_problems(bg, target, rows, parent_action_top)


def text_groups(state, target, rows):
    y = 1 if target == 7 else 3
    title = resolved(state, (1,), range(1, 13 if target == 7 else 19))
    actions = tuple(resolved(state, (y + 1 + 2 * index,), range(14, 19))
                    for index in range(rows))
    return (title,) + actions


def run(rom, ram=None, png_dir=None, trace=False, screen20=False,
        items_first=False):
    if screen20:
        target = 20
        leave_at = input_at = None
        ram = ram or SCREEN20_RAM
        if items_first:
            script = SCREEN20_ITEMS_FIRST_SCRIPT
            parent_at, entry_at, return_at, settled_at, frames = \
                3359, 3360, 3760, 4060, 4260
        else:
            script = SCREEN20_SCRIPT
            parent_at, entry_at, return_at, settled_at, frames = \
                2599, 2600, 3000, 3300, 3500
    else:
        target = 7
        ram = ram or SCREEN7_RAM
        if items_first:
            script = SCREEN7_ITEMS_FIRST_SCRIPT
            parent_at, entry_at, return_at, settled_at, leave_at, input_at, frames = \
                3719, 3720, 4220, 4520, 4620, 4860, 5060
        else:
            script = SCREEN7_SCRIPT
            parent_at, entry_at, return_at, settled_at, leave_at, input_at, frames = \
                2999, 3000, 3500, 3800, 3900, 4140, 4340
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='groundpotreturnspill-') as tmp:
        work = os.path.join(tmp, 'ground-pot.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        samples = []
        return_calls = []
        explicit_blanks = []
        pop_attempts = []
        pot_entry_attempts = []
        pot_entry_lifecycle = []
        entry_samples = []
        item_exit_states = []
        status_entries = []
        status_uploads = []
        status_fallbacks = []
        leave_samples = []
        leave_outgoing = [None]
        parent = [None]
        viewer = [None]

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A, stack(pb),
                               pb.memory[0xC1B3], pb.memory[0xC1B6],
                               tuple(pb.memory[address]
                                     for address in range(0xC69A, 0xC69F)),
                               pb.memory[0xC6BB], pb.memory[0xC6AC],
                               pb.memory[0xC6DE], pb.memory[0xC1B1]))

        def blank(owner):
            def capture(_context=None):
                explicit_blanks.append((frame[0], owner, pb.memory[0xC6A3],
                                        pb.memory[0xC1B3], pb.memory[0xC1B6],
                                        stack(pb)))
            return capture

        def action_pop(_context=None):
            pop_attempts.append({
                'frame': frame[0],
                'a': pb.register_file.A,
                'hl': pb.register_file.HL,
                'screen': pb.memory[0xC6A3],
                'stack': stack(pb),
                'state': pb.memory[0xC1B3],
                'phase': pb.memory[0xC1B6],
                'shape': tuple(pb.memory[address]
                               for address in range(0xC69A, 0xC69F)),
                'c6a6': pb.memory[0xC6A6],
                'c6aa': pb.memory[0xC6AA],
                'c6ac': pb.memory[0xC6AC],
                'c6bb': pb.memory[0xC6BB],
                'c6de': pb.memory[0xC6DE],
                'c1b1': pb.memory[0xC1B1],
                'lcdc': pb.memory[0xFF40],
                'scy': pb.memory[0xFF42],
                'scx': pb.memory[0xFF43],
                'wy': pb.memory[0xFF4A],
                'wx': pb.memory[0xFF4B],
            })

        pb.hook_register(4, 0x48AA, dispatch, None)
        pop_labels = gbasm.assemble(menuvwf.ACTION_POP_SRC,
                                    menuvwf.ACTION_POP_AT)[1]
        pb.hook_register(menuvwf.ACTION_POP_BANK, pop_labels['actionpop'],
                         action_pop, None)
        page_labels, region_labels = menuvwf.item_transition_labels()
        info_labels = menuvwf.info_lifecycle_labels()

        def pot_entry_attempt(_context=None):
            depth = pb.memory[0xC534]
            pot_entry_attempts.append({
                'frame': frame[0],
                'a': pb.register_file.A,
                'd': pb.register_file.D,
                'hl': pb.register_file.HL,
                'screen': pb.memory[0xC6A3],
                'state': pb.memory[0xC1B3],
                'phase': pb.memory[0xC1B6],
                'floor': pb.memory[0xC1B7],
                'render_phase': pb.memory[0xC1B1],
                'c0d5': pb.memory[0xC0D5],
                'shadow': pb.memory[0xC0D9] | (pb.memory[0xC0DA] << 8),
                'context': pb.memory[0xC6A6],
                'flags': pb.memory[0xC6DE],
                'count': pb.memory[0xC6AA],
                'selector': pb.memory[0xC6AC],
                'rows': pb.memory[0xC6BB],
                'depth': depth,
                'stack': tuple(pb.memory[0xC535 + index]
                               for index in range(depth + 1)),
                'shape': tuple(pb.memory[address]
                               for address in range(0xC69A, 0xC69F)),
                'display': tuple(pb.memory[address] for address in
                                 (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B)),
            })

        pb.hook_register(menuvwf.ACTION_BLANK_BANK,
                         info_labels['potentrybegin'], pot_entry_attempt, None)
        for label in ('potentrychrome', 'potentrypublish', 'potentrypublished'):
            pb.hook_register(
                menuvwf.ACTION_BLANK_BANK, info_labels[label],
                lambda _context=None, name=label: pot_entry_lifecycle.append((
                    frame[0], name, pb.memory[0xC6A3], pb.memory[0xC1B3],
                    pb.memory[0xC1B6], pb.memory[0xC6BB])), None)
        status_labels = statusvwf.runtime_labels()

        def status_entry(_context=None):
            if leave_at is None or frame[0] < leave_at:
                return
            status_entries.append({
                'frame': frame[0],
                'stack': tuple(pb.memory[0xC534 + index] for index in range(4)),
                'screen': pb.memory[0xC6A3],
                'state': pb.memory[0xC1B3],
                'phase': pb.memory[0xC1B6],
                'floor': pb.memory[0xC1B7],
                'context': pb.memory[0xC6A6],
                'selector': pb.memory[0xC6AC],
                'rows': pb.memory[0xC6BB],
                'flags': pb.memory[0xC6DE],
                'shape': tuple(pb.memory[address]
                               for address in range(0xC69A, 0xC69F)),
                'display': tuple(pb.memory[address] for address in
                                 (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B)),
            })

        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusentry'],
                         status_entry, None)
        pb.hook_register(
            statusvwf.FAR_BANK, status_labels['itemexitaccepted'],
            lambda _context=None: item_exit_states.append((
                frame[0], pb.memory[0xC1B6], pb.memory[0xC1B7])), None)
        pb.hook_register(
            statusvwf.FAR_BANK, status_labels['uploadlivedone'],
            lambda _context=None: status_uploads.append((
                frame[0], pb.memory[0xFF44], pb.memory[statusvwf.S_CAP]))
            if leave_at is not None and frame[0] >= leave_at else None, None)
        pb.hook_register(
            statusvwf.FAR_BANK, status_labels['statusready'],
            lambda _context=None: status_fallbacks.append(frame[0])
            if leave_at is not None and frame[0] >= leave_at else None, None)
        pb.hook_register(menuvwf.ITEM_PAGE_BANK, page_labels['pbdisable'],
                         blank('itempage'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irdisable'],
                         blank('itemregion'), None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['fidisable'],
                         blank('info'), None)
        if trace:
            def return_call(_context=None):
                return_calls.append((frame[0], pb.register_file.A,
                                     pb.register_file.B, pb.register_file.C,
                                     pb.register_file.D, pb.register_file.E,
                                     pb.memory[0xC6A3], pb.memory[0xC1B3],
                                     pb.memory[0xC1B6], pb.memory[0xC1B1],
                                     pb.memory[0xC11A]))
            pb.hook_register(menuvwf.ACTION_BLANK_BANK,
                             info_labels['inforeturn'], return_call, None)
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         blank('status'), None)

        for frame[0] in range(frames):
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame[0] == parent_at:
                parent[0] = snapshot(pb)
            if frame[0] == return_at - 1:
                viewer[0] = snapshot(pb)
            if entry_at <= frame[0] <= entry_at + 100:
                entry_samples.append((frame[0], snapshot(pb)))
            if return_at <= frame[0] <= return_at + 160:
                state = snapshot(pb)
                samples.append((frame[0], state))
                if png_dir:
                    os.makedirs(png_dir, exist_ok=True)
                    state['image'].save(os.path.join(
                        png_dir, 'return_f%04d.png' % frame[0]))
            if frame[0] == settled_at:
                settled = snapshot(pb)
            if leave_at is not None and frame[0] == leave_at - 1:
                leave_outgoing[0] = snapshot(pb)
            if leave_at is not None and leave_at <= frame[0] <= leave_at + 180:
                leave_samples.append((frame[0], snapshot(pb)))

        pb.stop(save=False)

    if parent[0] is None or viewer[0] is None:
        problems.append('missing parent or viewer checkpoint')
        parent_text = ()
        parent_row_count = 0
    else:
        parent_row_count = parent[0]['rows']
        parent_text = text_groups(parent[0], target, parent_row_count)
    action_y = 1 if target == 7 else 3
    parent_action_top = (parent[0]['bg'][action_y * 32 + 13:
                                            action_y * 32 + 20]
                         if parent[0] is not None else None)
    returned = [(at, state) for at, state in samples if state['screen'] == target]
    if not returned:
        problems.append('See B never returned to screen %d' % target)
    expected_entry = ({
        'screen': 13, 'state': 0, 'phase': 4, 'floor': 0,
        'render_phase': 1, 'c0d5': 1, 'shadow': 0xC380,
        'context': 0, 'flags': 0x81, 'count': 5, 'selector': 0,
        'rows': 5, 'depth': 2, 'stack': (0, 20, 13),
        'shape': (0, 3, 5, 18, 2),
        'display': (0xE7, 0, 0, 0x80, 7),
    } if screen20 else {
        'screen': 12, 'state': 0, 'phase': 0, 'floor': 0,
        'render_phase': 1, 'c0d5': 1, 'shadow': 0xC380,
        'context': 0, 'flags': 0x01, 'count': 4, 'selector': 0,
        'rows': 4, 'depth': 2, 'stack': (0, 7, 12),
        'shape': (0, 3, 4, 18, 2),
        'display': (0xE7, 0, 0, 0x80, 7),
    })
    first_entry = pot_entry_attempts[0] if pot_entry_attempts else None
    actual_entry = (None if first_entry is None else
                    {key: first_entry[key] for key in expected_entry})
    if actual_entry != expected_entry:
        problems.append('first Floor -> Pot entry predicate is %s, expected %s' %
                        (actual_entry, expected_entry))
    if items_first:
        screens = tuple(event[1] for event in dispatches)
        child = 13 if screen20 else 12
        expected_history = (1, 0, target, child)
        if not any(screens[index:index + len(expected_history)] == expected_history
                   for index in range(len(screens) - len(expected_history) + 1)):
            problems.append('Items-first dispatch history is %s, expected ordered %s' %
                            (screens, expected_history))
        prior_item_exits = [event for event in item_exit_states if event[0] < entry_at]
        if len(prior_item_exits) != 1 or prior_item_exits[0][1:] != (0, 0):
            problems.append('accepted Items -> Status exit state(s) %s, expected one '
                            'phase/latch zero pair' % (prior_item_exits,))
    entry_blanks = [event for event in explicit_blanks
                    if entry_at <= event[0] < return_at]
    if entry_blanks:
        problems.append('Floor -> See executed explicit blanker(s) %s' % entry_blanks)
    entry_off = [at for at, state in entry_samples
                 if not state['lcdc'] & 0x80]
    if entry_off:
        problems.append('Floor -> See disabled the LCD on frame(s) %s' % entry_off[:16])
    viewer_entry = [(at, state) for at, state in entry_samples
                    if state['screen'] in (12, 13) and 1 <= state['rows'] <= 5]
    chrome_frames = [at for at, state in viewer_entry
                     if potreturnspill.pot_chrome_complete(
                         state['bg'], state['rows'])]
    settled_pot_title = (potreturnspill.pot_title_pixels(viewer_entry[-1][1]['image'])
                         if viewer_entry else None)
    pot_text_frames = [at for at, state in viewer_entry
                       if settled_pot_title is not None and
                       potreturnspill.pot_title_pixels(state['image']) ==
                       settled_pot_title]
    if not chrome_frames:
        problems.append('Floor -> See never exposed complete Pot chrome')
    elif not pot_text_frames or not potreturnspill.pot_text_visible(
            viewer_entry[-1][1]['image']):
        problems.append('Floor -> See never exposed Pot title/body text')
    elif chrome_frames[0] >= pot_text_frames[0]:
        problems.append('Pot text first appears at f%d without earlier empty chrome '
                        '(first chrome f%d)' %
                        (pot_text_frames[0], chrome_frames[0]))
    lifecycle = tuple(label for _at, label, screen, _state, _phase, _rows
                      in pot_entry_lifecycle if screen in (12, 13))
    if (lifecycle.count('potentrychrome') != 1 or
            lifecycle.count('potentrypublished') != 1 or
            not lifecycle or lifecycle[-1] != 'potentrypublished' or
            len(lifecycle) < 3 or lifecycle[-2] != 'potentrypublish'):
        problems.append('Floor -> Pot entry lifecycle order is %s' % (lifecycle,))
    lcd_off = [at for at, state in samples if not state['lcdc'] & 0x80]
    if lcd_off:
        problems.append('See return disabled the LCD on frame(s) %s' % lcd_off[:16])

    first_chrome = next((at for at, state in returned
                         if chrome_complete(state['bg'], target,
                                            parent_row_count,
                                            parent_action_top)), None)
    first_text = next((at for at, state in returned
                       if parent_text and any(
                           group == wanted and any(any(tile) for tile in wanted)
                           for group, wanted in
                           zip(text_groups(state, target, parent_row_count),
                               parent_text))), None)
    exposed = [at for at, state in returned
               if parent_text and
               any(group == wanted and any(any(tile) for tile in wanted)
                   for group, wanted in
                   zip(text_groups(state, target, parent_row_count), parent_text)) and
               not chrome_complete(state['bg'], target, parent_row_count,
                                   parent_action_top)]
    if first_chrome is None:
        problems.append('return never exposed complete screen-%d chrome' % target)
    if first_text is None:
        problems.append('return never exposed restored Action text')
    if exposed:
        problems.append('restored Action text preceded complete chrome on frame(s) %s'
                        % exposed[:16])
    if first_chrome is not None and first_text is not None and first_chrome > first_text:
        problems.append('complete screen-%d chrome appeared after restored Action text'
                        % target)

    # Once settled, the exact parent tilemaps and resolved pixels must be restored.
    if parent[0] is not None:
        for label, old, new in (
                ('BG tilemap', parent[0]['bg'], settled['bg']),
                ('Window tilemap', parent[0]['window'], settled['window']),
                ('BG pixels', resolved(parent[0]), resolved(settled)),
                ('Window pixels', resolved(parent[0], range(2), range(20), 'window'),
                 resolved(settled, range(2), range(20), 'window'))):
            # Screen 20 rebuilds its proportional Action labels and may legally choose
            # different private tile IDs. Its chrome is checked above and its complete
            # resolved BG raster is checked below, so byte-identical BG references are
            # not an invariant for that parent.
            if target == 20 and label == 'BG tilemap':
                continue
            if old != new:
                problems.append('settled return differs from outgoing %s' % label)

    return_blanks = [event for event in explicit_blanks if event[0] >= return_at]
    if return_blanks:
        problems.append('See return executed explicit blanker(s) %s' % return_blanks)

    leave_status_at = None
    leave_chrome_at = None
    leave_text_at = None
    if leave_at is not None:
        post_leave_dispatches = [event for event in dispatches if event[0] >= leave_at]
        if not post_leave_dispatches or post_leave_dispatches[0][1] != 0:
            problems.append('screen-7 Floor B did not dispatch Status first: %s' %
                            (post_leave_dispatches,))
        else:
            leave_status_at = post_leave_dispatches[0][0]

        if len(status_entries) != 1:
            problems.append('screen-7 Floor B reached Status entry %d times, expected one' %
                            len(status_entries))
        else:
            expected = {
                'stack': (0, 0, 7, status_entries[0]['stack'][3]),
                'screen': 0, 'state': 0, 'phase': 0, 'floor': 0,
                'context': 1, 'selector': 0xFF, 'rows': 4, 'flags': 1,
                'shape': (0, 10, 2, 18, 4),
            }
            for key, wanted in expected.items():
                if status_entries[0][key] != wanted:
                    problems.append('screen-7 Status entry %s is %r, expected %r' %
                                    (key, status_entries[0][key], wanted))
            display = status_entries[0]['display']
            if (display[0] & 0xF8, *display[1:]) != (0xE0, 0, 0, 0x80, 7):
                problems.append('screen-7 Status display predicate is %s' % (display,))

        accepted_floor_exits = [event for event in item_exit_states
                                if event[0] >= leave_at]
        if len(accepted_floor_exits) != 1 or accepted_floor_exits[0][1:] != (0, 0):
            problems.append('screen-7 Floor exit acceptance is %s, expected one '
                            'phase/latch zero pair' % (accepted_floor_exits,))
        if status_fallbacks:
            problems.append('screen-7 Floor exit reached Status fallback at %s' %
                            status_fallbacks)

        caps = tuple(cap for _at, _ly, cap in status_uploads)
        expected_caps = (6, 7, 5, 2, 4, 4, 4, 4, 4)
        if caps != expected_caps:
            problems.append('screen-7 Status upload caps are %s, expected %s' %
                            (caps, expected_caps))
        for at, ly, cap in status_uploads:
            if not 0x90 <= ly <= 0x99:
                problems.append('screen-7 cap-%d upload ended outside VBlank at f%d '
                                '(LY=$%02X)' % (cap, at, ly))

        lcd_off = [at for at, state in leave_samples if not state['lcdc'] & 0x80]
        white = [at for at, state in leave_samples if uniform_frame(state['image'])]
        if lcd_off:
            problems.append('screen-7 Floor exit disabled the LCD on frame(s) %s' %
                            lcd_off[:16])
        if white:
            problems.append('screen-7 Floor exit exposed uniform frame(s) %s' %
                            white[:16])

        if leave_outgoing[0] is None or not leave_samples:
            problems.append('missing screen-7 Floor exit snapshots')
        else:
            old = leave_outgoing[0]
            final = leave_samples[-1][1]
            private = ({tile for base, cap in statusvwf.PRIVATE_RUNS.values()
                        for tile in range(base, base + cap)} |
                       set(statusvwf.WEAPON_TILES + statusvwf.SHIELD_TILES))
            refs = ({old['bg'][row * 32 + col]
                     for row in range(16) for col in range(20)} |
                    {old['window'][row * 32 + col]
                     for row in range(2) for col in range(20)})
            collision = sorted(private & refs)
            if collision:
                problems.append('screen-7 Floor visibly references Status-owned tiles %s' %
                                ' '.join('$%02X' % tile for tile in collision))

            old_bg = visible_cells(old)
            new_bg = visible_cells(final)
            empty_bg = tuple(
                (tile, old['tiles'][(0x800 + tile * 16
                                     if tile < 0x80 else
                                     (tile - 0x80) * 16):
                                    (0x800 + tile * 16
                                     if tile < 0x80 else
                                     (tile - 0x80) * 16) + 16])
                for tile in statusvwf.STATUS_EMPTY_MAP)
            old_window = visible_cells(old, 'window', range(2))
            invalid = []
            for at, state in leave_samples:
                if visible_cells(state, 'window', range(2)) != old_window:
                    invalid.append((at, 'Window'))
                current = visible_cells(state)
                for index, value in enumerate(current):
                    if value not in (old_bg[index], empty_bg[index], new_bg[index]):
                        invalid.append((at, 'BG cell %d' % index))
                        break
                if len(invalid) >= 8:
                    break
            if invalid:
                problems.append('screen-7 Floor exit exposed non-owned states: %s' %
                                ', '.join('f%d %s' % event for event in invalid))

            chrome = [index for index, value in enumerate(new_bg)
                      if value[0] == 0xB6 or 0xB8 <= value[0] <= 0xBF]
            text = [index for index, value in enumerate(new_bg)
                    if value != old_bg[index] and value[0] not in
                    (0, 0xB6, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC,
                     0xBD, 0xBE, 0xBF)]
            leave_chrome_at = next((
                at for at, state in leave_samples
                if all(visible_cells(state)[index] == new_bg[index]
                       for index in chrome)), None)
            leave_text_at = next((
                at for at, state in leave_samples
                if any(visible_cells(state)[index] == new_bg[index]
                       for index in text)), None)
            if leave_chrome_at is None:
                problems.append('screen-7 Floor exit never completed Status chrome')
            if leave_text_at is None:
                problems.append('screen-7 Floor exit never exposed Status text')
            if (leave_chrome_at is not None and leave_text_at is not None and
                    leave_chrome_at > leave_text_at):
                problems.append('screen-7 Status text appeared at f%d before complete '
                                'chrome at f%d' % (leave_text_at, leave_chrome_at))

        accepted_input = [event for event in dispatches
                          if event[0] >= input_at and event[1] == 1]
        if not accepted_input or accepted_input[0][0] > input_at + 20:
            problems.append('screen-7 Status input did not open Items promptly: %s' %
                            (accepted_input,))

    if trace:
        print('  dispatches %r' % (dispatches,))
        print('  explicit blanks %r' % (explicit_blanks,))
        print('  pop attempts %r' % (pop_attempts,))
        print('  Pot entry attempts %r' % (pot_entry_attempts,))
        print('  Pot entry lifecycle %r; first chrome/text %s/%s' %
              (pot_entry_lifecycle,
               chrome_frames[0] if chrome_frames else None,
               pot_text_frames[0] if pot_text_frames else None))
        print('  return calls %r' % (return_calls,))
        print('  parent %r' % ({key: parent[0][key] for key in
                               ('screen', 'state', 'phase', 'stack', 'shape')},))
        print('  viewer %r' % ({key: viewer[0][key] for key in
                               ('screen', 'state', 'phase', 'stack', 'shape')},))
        for at, state in samples[:80]:
            if at % 2 == 0 or state['screen'] == target:
                print('  f%d screen=%d state=$%02X phase=$%02X stack=%s shape=%s '
                      'chrome=%d rows=%s' %
                      (at, state['screen'], state['state'], state['phase'],
                       state['stack'], state['shape'],
                       chrome_complete(state['bg'], target, parent_row_count,
                                       parent_action_top),
                       tuple(any(any(tile) for tile in group)
                             for group in text_groups(
                                 state, target, parent_row_count))))
                if state['screen'] == target and not chrome_complete(
                        state['bg'], target, parent_row_count, parent_action_top):
                    print('    chrome problems %s' % chrome_problems(
                        state['bg'], target, parent_row_count,
                        parent_action_top))
                    y = 1 if target == 7 else 3
                    print('    action top %s' % state['bg'][
                        y * 32 + 13:y * 32 + 20].hex(' '))

    print('groundpotreturnspill: screen %d%s; dispatches %s; blankers %s; entry '
          'chrome/text %s/%s; return chrome/text %s/%s; '
          'leave Status/chrome/text %s/%s/%s; %d problem(s)' %
          (target, ' after Items' if items_first else '',
           ' '.join('f%d:%d' % (event[0], event[1]) for event in dispatches),
           explicit_blanks,
           'f%d' % chrome_frames[0] if chrome_frames else 'none',
           'f%d' % pot_text_frames[0] if pot_text_frames else 'none',
           'f%d' % first_chrome if first_chrome is not None else 'none',
           'f%d' % first_text if first_text is not None else 'none',
           'f%d' % leave_status_at if leave_status_at is not None else '-',
           'f%d' % leave_chrome_at if leave_chrome_at is not None else '-',
           'f%d' % leave_text_at if leave_text_at is not None else '-',
           len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram')
    parser.add_argument('--png-dir')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--screen20', action='store_true')
    parser.add_argument('--items-first', action='store_true')
    args = parser.parse_args()
    ram = args.ram or (SCREEN20_RAM if args.screen20 else SCREEN7_RAM)
    for path in (args.rom, ram):
        if not os.path.exists(path):
            raise SystemExit('groundpotreturnspill: missing %s' % path)
    return run(args.rom, ram, args.png_dir, args.trace, args.screen20,
               args.items_first)


if __name__ == '__main__':
    raise SystemExit(main())
