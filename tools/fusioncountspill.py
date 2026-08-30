#!/usr/bin/env python3
"""Exercise every real fused-equipment count through Item and Info.

Joey's ``shiren_en_log3_fusion_name.srm`` was captured from Log 3 with a canonical
``Manji Kabura+2`` carrying two seals.  A cold boot restores an older in-dungeon
checkpoint over SRAM bank 0, so this test first validates the supplied Log-3 working
record directly, then reproduces it through the canonical item builder in
``saves/dungeon.state``.

Nine canonical Manji Kabura objects carry masks with popcounts 1 through 9.  The first
five are checked on item page 1, the other four on page 2, and count 9 is selected and
opened in Info.  Its three groups of four seal descriptions must publish footer digits
1/3, 2/3, and 3/3 with exact approved-font pixels.  This proves the game itself emits
suffix codes $8C-$94 and that every one receives a VWF record with exact visible planes.
$95 is asserted to be rejected: the original weapon/shield masks contain at most nine
usable seal bits.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
import gbasm                                                      # noqa: E402
import dotfont                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log3_fusion_name.srm')
STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
INVENTORY = 0xA3B0
OBJECTS = 0xA406
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
INFO_SHAPE = (0, 3, 5, 18, 0x00)
MANJI = 0x06
RASEN_FUUMA = 0x20
BONUS = 2
FLAGS = 0xC4
WEAPON_MASK = 0x01FF
SHIELD_MASK = 0x06FD
EXPECTED_LOG3_OBJECT = bytes((MANJI, BONUS, 0, FLAGS, 0x06, 0, 0xFF, 0xFF))
NAME = tuple(menuspill.encode('Manji Kabura+2'))
PAGE_COUNT_CASES = (1, 6, 11, 16)


def row_at(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return tuple(out)


def fixture_problems(path):
    data = open(path, 'rb').read()
    problems = []
    if len(data) != 0x8000:
        return ['Log-3 fusion SRAM is %d bytes, expected 32768' % len(data)]
    first = data[INVENTORY - 0xA000]
    if first == 0xFF or first >= 128:
        problems.append('Log-3 first inventory object index is invalid: $%02X' % first)
        return problems
    start = OBJECTS - 0xA000 + 8 * first
    record = data[start:start + 8]
    if record != EXPECTED_LOG3_OBJECT:
        problems.append('Log-3 first object is %s, expected Manji Kabura+2/two seals %s'
                        % (record.hex(' '), EXPECTED_LOG3_OBJECT.hex(' ')))
    return problems


def expected_indicator(pages, active):
    """The exact native 4:$4EB4 page-marker shape inside box 4's top border."""
    if pages == 1:
        return bytes((0xBC,)) * 4
    return bytes((0xC6 if slot == active else 0xC5) if slot < pages else 0xBC
                 for slot in range(4))


def pager_digit_pixels(digit):
    """Approved 1bpp digit duplicated into the Game Boy's two bitplanes."""
    return bytes(value for row in dotfont.load_approved().glyphs[str(digit)]
                 for value in (row, row))


def seal_footer_state(pb, offset, count):
    """Capture the settled screen-5 footer map and the rasters it resolves through."""
    current_tile = pb.memory[0x99B0]
    total_tile = pb.memory[0x99B2]
    current_at = menuspill.tile_data_addr(current_tile)
    total_at = menuspill.tile_data_addr(total_tile)
    return {
        'offset': offset,
        'count': count,
        'visible': bytes(pb.memory[0x99B0:0x99B3]),
        'shadow': bytes(pb.memory[0xC4B0:0xC4B3]),
        'current_pixels': bytes(pb.memory[current_at:current_at + 16]),
        'total_pixels': bytes(pb.memory[total_at:total_at + 16]),
    }


def seal_footer_problems(label, publishes, settled, step_handlers, group_handlers):
    expected_pages = ((0, 9), (4, 9), (8, 9))
    problems = []
    if tuple(event[1:] for event in publishes) != expected_pages:
        problems.append('%s seal publish sequence is %s, expected %s; '
                        'step/group handlers %s/%s' %
                        (label, tuple(event[1:] for event in publishes),
                         expected_pages, step_handlers, group_handlers))
    if tuple((state['offset'], state['count']) for state in settled) != expected_pages:
        problems.append('%s settled seal sequence is %s, expected %s' %
                        (label, tuple((state['offset'], state['count'])
                                      for state in settled), expected_pages))
    for state in settled:
        page = state['offset'] // 4 + 1
        total = (state['count'] - 1) // 4 + 1
        expected_footer = bytes((page + 1, 0xB0, total + 1))
        if state['visible'] != expected_footer or state['shadow'] != expected_footer:
            problems.append('%s seal page %d footer visible/shadow is %s/%s, '
                            'expected %s' %
                            (label, page, state['visible'].hex(' '),
                             state['shadow'].hex(' '), expected_footer.hex(' ')))
        if state['current_pixels'] != pager_digit_pixels(page):
            problems.append('%s seal page %d current digit pixels are %s, expected %s' %
                            (label, page, state['current_pixels'].hex(' '),
                             pager_digit_pixels(page).hex(' ')))
        if state['total_pixels'] != pager_digit_pixels(total):
            problems.append('%s seal page %d total digit pixels are %s, expected %s' %
                            (label, page, state['total_pixels'].hex(' '),
                             pager_digit_pixels(total).hex(' ')))
    if tuple(page for _at, page in group_handlers) != (0, 4):
        problems.append('%s seal group handler offsets are %s, expected (0, 4)' %
                        (label, tuple(page for _at, page in group_handlers)))
    if step_handlers:
        problems.append('%s seal paging unexpectedly used one-description handler %s' %
                        (label, step_handlers))
    return problems


def page_count_case(PyBoy, rom, state_path, item_count, profile, region_labels):
    """Exercise page cycles and Start-sort with a shortest 1-, 2-, 3-, or 4-page list."""
    pages = (item_count + 4) // 5
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state_path, 'rb') as source:
        pb.load_state(source)

    frame = [0]
    injected = [False]
    row0_draws = []
    regional_begins = []
    regional_fallbacks = []
    regional_origins = []
    blank_boundaries = []
    lcd_off = []
    bad_states = []
    indicators = {}
    selectors = {}
    dispatches = []

    def inject(_context=None):
        if injected[0]:
            return
        free = [index for index in range(128)
                if pb.memory[OBJECTS + 8 * index] == 0xFF]
        if len(free) < item_count:
            return
        for ordinal, object_index in enumerate(free[:item_count]):
            # Valid carried Manji Kabura objects with canonical 1..9 seal masks keep
            # every row on the real Item formatter while producing nonempty short pages.
            seal_count = ordinal % 9 + 1
            mask = (1 << seal_count) - 1
            record = (MANJI, BONUS, 0, FLAGS, mask & 0xFF, mask >> 8, 0xFF, 0xFF)
            for offset, value in enumerate(record):
                pb.memory[OBJECTS + 8 * object_index + offset] = value
            pb.memory[INVENTORY + ordinal] = object_index
        pb.memory[INVENTORY + item_count] = 0xFF
        injected[0] = True

    def far_entry(_context=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        if frame[0] >= 250 and shape == ITEM_SHAPE and pb.register_file.D == 0:
            row0_draws.append(frame[0])

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(4, 0x48AA,
                     lambda _ctx=None: dispatches.append((frame[0], pb.register_file.A)),
                     None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)

    def regional_begin(_ctx=None):
        regional_begins.append(frame[0])
        regional_origins.append((bytes(pb.memory[0x9800:0x9C00]),
                                 bytes(pb.memory[0xC300:0xC700])))

    def blank_boundary(_ctx=None):
        blank_boundaries.append((frame[0], pb.memory[0xFF44],
                                 bytes(pb.memory[0x9800:0x9C00]),
                                 bytes(pb.memory[0xC300:0xC700])))

    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irshadow'],
                     regional_begin, None)
    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irarmed'],
                     blank_boundary, None)
    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irfaillcd'],
                     lambda _ctx=None: regional_fallbacks.append(frame[0]), None)

    actions = ['right'] * pages + ['left'] * pages + ['start']
    action_events = [(280 + 110 * index, action)
                     for index, action in enumerate(actions)]
    schedule = {60: 'b', 120: 'a', **dict(action_events)}
    sample_expectations = {220: 0}
    active = 0
    for at, action in action_events:
        if action == 'right':
            active = (active + 1) % pages
        elif action == 'left':
            active = (active - 1) % pages
        sample_expectations[at + 80] = active
    final_frame = action_events[-1][0] + 100
    for frame[0] in range(final_frame):
        button = schedule.get(frame[0])
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        if 260 <= frame[0] < final_frame - 1:
            if not pb.memory[0xFF40] & 0x80:
                lcd_off.append(frame[0])
            if pb.memory[0xC1B3] not in (0, 1):
                bad_states.append((frame[0], pb.memory[0xC1B3]))
        if frame[0] in sample_expectations:
            indicators[frame[0]] = bytes(pb.memory[0x986F:0x9873])
            selectors[frame[0]] = pb.memory[0xC6AC]

    actual_item_count = pb.memory[0xC6AA]
    pb.stop(save=False)
    problems = []
    if not injected[0]:
        problems.append('%d-item fixture was not injected' % item_count)
    if actual_item_count != item_count:
        problems.append('%d-item fixture reports native count %d' %
                        (item_count, actual_item_count))
    expected = {at: expected_indicator(pages, active_page)
                for at, active_page in sample_expectations.items()}
    for at, want in expected.items():
        got = indicators.get(at)
        if got != want:
            problems.append('%d-page indicator at f%d is %s, expected %s' %
                            (pages, at, 'missing' if got is None else got.hex(' '),
                             want.hex(' ')))
    if len(row0_draws) != len(actions):
        problems.append('%d-page boundary/sort cycle produced %d redraws, expected %d '
                        '(dispatches %s)' %
                        (pages, len(row0_draws), len(actions),
                         ' '.join('f%d:%d' % event for event in dispatches)))
    if len(regional_begins) != len(row0_draws):
        problems.append('%d-page paging/sort began %d/%d regional redraws' %
                        (pages, len(regional_begins), len(row0_draws)))
    if len(regional_origins) != len(blank_boundaries):
        problems.append('%d-page paging/sort captured %d regional origins and %d '
                        'blank boundaries' %
                        (pages, len(regional_origins), len(blank_boundaries)))
    blank_targets = {(4 + 2 * row) * 32 + col
                     for row in range(5) for col in range(1, 19)}
    borders = {(4 + 2 * row) * 32 for row in range(5)}
    region_targets = blank_targets | borders
    for (old_bg, old_shadow), (at, ly, new_bg, new_shadow) in zip(
            regional_origins, blank_boundaries):
        if ly < 0x90:
            problems.append('%d-page regional blank occurred outside VBlank at f%d '
                            '(LY=$%02X)' % (pages, at, ly))
            break
        for plane, old_map, new_map in (('BG', old_bg, new_bg),
                                        ('shadow', old_shadow, new_shadow)):
            retained = next((offset for offset in blank_targets
                             if new_map[offset] != 0), None)
            bad_border = next((offset for offset in borders
                               if new_map[offset] != 0xBE), None)
            changed = next((offset for offset in range(0x400)
                            if offset not in region_targets and
                            old_map[offset] != new_map[offset]),
                           None)
            if retained is not None:
                problems.append('%d-page %s regional target +$%03X is nonzero at f%d' %
                                (pages, plane, retained, at))
                break
            if bad_border is not None:
                problems.append('%d-page %s regional border +$%03X is $%02X, '
                                'expected $BE at f%d' %
                                (pages, plane, bad_border, new_map[bad_border], at))
                break
            if changed is not None:
                problems.append('%d-page %s regional blank changed lock +$%03X at f%d' %
                                (pages, plane, changed, at))
                break
    if regional_fallbacks:
        problems.append('%d-page paging/sort reached fallback at %s' %
                        (pages, ' '.join('f%d' % at for at in regional_fallbacks)))
    if lcd_off:
        problems.append('%d-page paging/sort disabled LCD at %s' %
                        (pages, ' '.join('f%d' % at for at in lcd_off)))
    if bad_states:
        problems.append('%d-page paging/sort entered states %s' %
                        (pages, ' '.join('f%d:$%02X' % event for event in bad_states)))
    return {
        'pages': pages,
        'count': item_count,
        'draws': row0_draws,
        'begins': regional_begins,
        'indicators': indicators,
        'selectors': selectors,
        'dispatches': dispatches,
    }, problems


def short_page_cursor_case(PyBoy, rom, state_path, profile, region_labels):
    """A row-4 selection must clamp visibly when page 2 contains only one item."""
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state_path, 'rb') as source:
        pb.load_state(source)

    injected = [False]
    regional_begins = []

    def inject(_context=None):
        if injected[0]:
            return
        free = [index for index in range(128)
                if pb.memory[OBJECTS + 8 * index] == 0xFF]
        if len(free) < 6:
            return
        for ordinal, object_index in enumerate(free[:6]):
            record = (MANJI, BONUS, 0, FLAGS, 1 << (ordinal % 9), 0,
                      0xFF, 0xFF)
            for offset, value in enumerate(record):
                pb.memory[OBJECTS + 8 * object_index + offset] = value
            pb.memory[INVENTORY + ordinal] = object_index
        pb.memory[INVENTORY + 6] = 0xFF
        injected[0] = True

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irshadow'],
                     lambda _ctx=None: regional_begins.append(frame), None)
    schedule = {
        60: 'b', 120: 'a',
        280: 'down', 340: 'down', 400: 'down', 460: 'down',
        540: 'right',
    }
    lcd_off = []
    for frame in range(701):
        button = schedule.get(frame)
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        if 520 <= frame and not pb.memory[0xFF40] & 0x80:
            lcd_off.append(frame)

    selector = pb.memory[0xC6AC]
    row = pb.memory[0xC6A5]
    visible = tuple(pb.memory[0x9882 + 0x40 * index] for index in range(5))
    shadow = tuple(pb.memory[0xC382 + 0x40 * index] for index in range(5))
    count = pb.memory[0xC6AA]
    pb.stop(save=False)

    problems = []
    if not injected[0] or count != 6:
        problems.append('short-page cursor fixture reports %d items after injection' %
                        count)
    if (selector, row) != (5, 0):
        problems.append('short-page cursor settled at selector/row $%02X/%d, '
                        'expected $05/0' % (selector, row))
    expected = (0x81, 0, 0, 0, 0)
    if visible != expected or shadow != expected:
        problems.append('short-page cursor visible/shadow are %s/%s, expected %s' %
                        (bytes(visible).hex(' '), bytes(shadow).hex(' '),
                         bytes(expected).hex(' ')))
    if len(regional_begins) != 1:
        problems.append('short-page cursor used %d regional redraws, expected one' %
                        len(regional_begins))
    if lcd_off:
        problems.append('short-page cursor disabled LCD at %s' %
                        ' '.join('f%d' % at for at in lcd_off))
    return {
        'selector': selector,
        'row': row,
        'visible': visible,
        'regional': len(regional_begins),
    }, problems


def shield_pager_case(PyBoy, rom, state_path, info_labels, png_dir=None):
    """Drive a canonical all-nine-seal shield through all three screen-5 groups."""
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state_path, 'rb') as source:
        pb.load_state(source)

    frame = [0]
    injected = [False]
    publishes = []
    pending = []
    settled = []
    step_handlers = []
    group_handlers = []
    explicit_blanks = []
    lcd_off = []
    uniform = []
    screen_at_info = [None]
    schedule = {
        60: 'b', 120: 'a',                    # Main -> Items
        280: 'a',                              # shield Action
        360: 'down', 400: 'down', 440: 'down', 500: 'a',  # Info
    }

    def inject(_ctx=None):
        if injected[0]:
            return
        object_index = next((index for index in range(128)
                             if pb.memory[OBJECTS + 8 * index] == 0xFF), None)
        if object_index is None:
            return
        record = (RASEN_FUUMA, 1, 0, FLAGS,
                  SHIELD_MASK & 0xFF, SHIELD_MASK >> 8, 0xFF, 0xFF)
        for offset, value in enumerate(record):
            pb.memory[OBJECTS + 8 * object_index + offset] = value
        pb.memory[INVENTORY] = object_index
        pb.memory[INVENTORY + 1] = 0xFF
        injected[0] = True

    def info_publish(_ctx=None):
        if pb.memory[0xC6A3] != 5:
            return
        offset = pb.memory[0xC6BC]
        count = pb.memory[0xC6BD]
        if screen_at_info[0] is None:
            screen_at_info[0] = pb.memory[0xC6A3]
        publishes.append((frame[0], offset, count))
        pending.append((frame[0] + 20, offset, count))
        schedule[frame[0] + 70] = 'right' if offset + 4 < count else 'b'

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['infopublish'],
                     info_publish, None)
    pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['fidisable'],
                     lambda _ctx=None: explicit_blanks.append(frame[0]), None)
    pb.hook_register(4, 0x5926,
                     lambda _ctx=None: step_handlers.append(
                         (frame[0], pb.memory[0xC6BC])), None)
    pb.hook_register(4, 0x5941,
                     lambda _ctx=None: group_handlers.append(
                         (frame[0], pb.memory[0xC6BC])), None)

    for frame[0] in range(1100):
        button = schedule.get(frame[0])
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        if frame[0] >= 480:
            if not pb.memory[0xFF40] & 0x80:
                lcd_off.append(frame[0])
            if len(set(pb.screen.image.convert('RGB').getdata())) == 1:
                uniform.append(frame[0])
        while pending and frame[0] >= pending[0][0]:
            _at, offset, count = pending.pop(0)
            settled.append(seal_footer_state(pb, offset, count))
            if png_dir:
                os.makedirs(png_dir, exist_ok=True)
                pb.screen.image.save(os.path.join(
                    png_dir, 'shield_seal_page%d.png' % (offset // 4 + 1)))

    final_screen = pb.memory[0xC6A3]
    final_lcdc = pb.memory[0xFF40]
    pb.stop(save=False)
    problems = []
    if not injected[0]:
        problems.append('all-seal shield fixture was not injected')
    if screen_at_info[0] != 5:
        problems.append('all-seal shield reached screen %s, expected screen 5' %
                        screen_at_info[0])
    problems += seal_footer_problems(
        'count-9 shield', publishes, settled, step_handlers, group_handlers)
    if explicit_blanks:
        problems.append('count-9 shield reached explicit Info LCD blanker at %s' %
                        ' '.join('f%d' % at for at in explicit_blanks))
    if lcd_off or uniform:
        problems.append('count-9 shield produced LCD-off/uniform frames %s/%s' %
                        (lcd_off[:16], uniform[:16]))
    if final_screen != 1 or not final_lcdc & 0x80:
        problems.append('count-9 shield B return ended on screen %d/LCDC=$%02X, '
                        'expected live Items screen 1' % (final_screen, final_lcdc))
    return {
        'pages': tuple((state['offset'] // 4 + 1,
                        (state['count'] - 1) // 4 + 1)
                       for state in settled),
        'groups': group_handlers,
        'final_screen': final_screen,
    }, problems


def run(rom, ram=None, state=STATE, png_dir=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('fusioncountspill: requires the proportional renderer')
    fixture_checked = ram is not None
    problems = fixture_problems(ram) if fixture_checked else []
    if max(bin(WEAPON_MASK).count('1'), bin(SHIELD_MASK).count('1')) != 9:
        problems.append('canonical equipment-mask maximum is no longer nine seals')
    if menuspill.eligible((menuvwf.FUSED_LAST + 1,)):
        problems.append('impossible fusion suffix $%02X was admitted'
                        % (menuvwf.FUSED_LAST + 1))

    PyBoy = _import_pyboy()
    _region_code, region_labels = gbasm.assemble(
        menuvwf.ITEM_REGION_SRC, menuvwf.ITEM_REGION_AT)
    matrix = []
    for item_count in PAGE_COUNT_CASES:
        result, failures = page_count_case(
            PyBoy, rom, state, item_count, profile, region_labels)
        matrix.append(result)
        problems += failures
    cursor_case, cursor_failures = short_page_cursor_case(
        PyBoy, rom, state, profile, region_labels)
    problems += cursor_failures
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as source:
        pb.load_state(source)

    injected = [False]
    events = {}
    snapshots = {}
    frame = [0]
    regional_begins = []
    regional_fallbacks = []
    page_flip_lcd_off = []
    info_lcd_off = []
    info_white = []
    info_attempts = []
    pop_calls = []
    admitted_pops = []
    explicit_info_blanks = []
    settled_indicator = [None]
    seal_publishes = []
    seal_pending = []
    seal_settled = []
    seal_step_handlers = []
    seal_group_handlers = []

    def inject(_context=None):
        if injected[0]:
            return
        free = [index for index in range(128)
                if pb.memory[OBJECTS + 8 * index] == 0xFF]
        if len(free) < 9:
            return
        for count, object_index in enumerate(free[:9], 1):
            mask = (1 << count) - 1
            record = (MANJI, BONUS, 0, FLAGS, mask & 0xFF, mask >> 8, 0xFF, 0xFF)
            for offset, value in enumerate(record):
                pb.memory[OBJECTS + 8 * object_index + offset] = value
            pb.memory[INVENTORY + count - 1] = object_index
        pb.memory[INVENTORY + 9] = 0xFF
        injected[0] = True

    def far_entry(_context=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        if shape not in (ITEM_SHAPE, INFO_SHAPE):
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        codes = row_at(pb, source)
        fused = [code for code in codes if code in menuvwf.FUSED_CODES]
        if len(fused) != 1:
            return
        # FUSED_FIRST is the ZERO-seal code, so the count is the plain offset. It used to
        # be the one-seal code, and this read `+ 1`; admitting $8B shifted the base.
        count = fused[0] - menuvwf.FUSED_FIRST
        events[(shape, count)] = (pb.register_file.HL, codes)

    def snapshot(label, counts, shape, raw):
        records = menuspill.records(pb, profile)
        failures = []
        for count in counts:
            event = events.get((shape, count))
            if event is None:
                failures.append('count %d never reached %s renderer' % (count, label))
                continue
            key, staged = event
            expected = NAME + (menuvwf.FUSED_FIRST + count,)
            if raw == 2:
                if staged != (0, 0) + expected:
                    failures.append('count %d staged %s, expected %s' %
                                    (count, bytes(staged).hex(' '),
                                     bytes((0, 0) + expected).hex(' ')))
            elif staged != (0x7D,) + expected + (0x7D,):
                failures.append('count %d Info title staged %s' %
                                (count, bytes(staged).hex(' ')))
            matches = [record for record in records
                       if record[0] == key and record[3] == raw]
            if not matches:
                failures.append('count %d has no %s VWF record' % (count, label))
            visible = staged[raw:] if raw else staged
            if not menuspill.visible_row_matches(pb, profile, key, list(visible), raw=raw):
                failures.append('count %d %s planes differ' % (count, label))
        snapshots[label] = failures

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irshadow'],
                     lambda _ctx=None: regional_begins.append(frame[0]), None)
    pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irfaillcd'],
                     lambda _ctx=None: regional_fallbacks.append(frame[0]), None)
    _info_code, info_labels = gbasm.assemble(
        menuvwf.INFO_LIFECYCLE_SRC, menuvwf.INFO_LIFECYCLE_AT)

    def info_attempt(_ctx=None):
        depth = pb.memory[0xC534]
        info_attempts.append((
            frame[0], pb.memory[0xC1B3], pb.memory[0xC1B6],
            pb.memory[0xC6A3], pb.memory[0xC6DE], pb.memory[0xC6AC],
            tuple(pb.memory[0xC535 + index] for index in range(depth + 1))))

    pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['infotry'],
                     info_attempt, None)
    pb.hook_register(
        menuvwf.ACTION_BLANK_BANK, info_labels['fidisable'],
        lambda _ctx=None: explicit_info_blanks.append((
            frame[0], pb.memory[0xC6A3], pb.memory[0xC1B1],
            pb.memory[0xC1B3], pb.memory[0xC1B6])), None)
    pb.hook_register(4, 0x485A,
                     lambda _ctx=None: pop_calls.append((
                         frame[0], pb.register_file.A, pb.register_file.HL,
                         pb.memory[0xC6A3], pb.memory[0xC1B3],
                         tuple(pb.memory[0xC535 + index]
                               for index in range(pb.memory[0xC534] + 1)))), None)
    pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['infopop'],
                     lambda _ctx=None: admitted_pops.append((
                         frame[0], pb.register_file.HL, pb.memory[0xC6A3],
                         pb.memory[0xC1B3], pb.memory[0xC1B6])), None)

    def info_publish(_ctx=None):
        if pb.memory[0xC6A3] != 5:
            return
        offset = pb.memory[0xC6BC]
        count = pb.memory[0xC6BD]
        seal_publishes.append((frame[0], offset, count))
        seal_pending.append((frame[0] + 20, offset, count))
        # Screen 5's group handler advances by the four descriptions visible on one
        # page. Keep the final page stable long enough to sample, then leave with B.
        schedule[frame[0] + 70] = 'right' if offset + 4 < count else 'b'

    pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['infopublish'],
                     info_publish, None)
    # mgbdis: 4:$5926 advances one description; 4:$5941 advances one four-row group.
    pb.hook_register(4, 0x5926,
                     lambda _ctx=None: seal_step_handlers.append(
                         (frame[0], pb.memory[0xC6BC])), None)
    pb.hook_register(4, 0x5941,
                     lambda _ctx=None: seal_group_handlers.append(
                         (frame[0], pb.memory[0xC6BC])), None)
    schedule = {
        60: 'b', 120: 'a',                    # Main -> Items
        280: 'right',                         # counts 6-9
        400: 'down', 440: 'down', 480: 'down', 540: 'a',  # select count 9
        620: 'down', 660: 'down', 700: 'down', 760: 'a',  # Info
    }
    screen_at_info = None
    for frame[0] in range(1400):
        button = schedule.get(frame[0])
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        if 280 <= frame[0] < 360 and not pb.memory[0xFF40] & 0x80:
            page_flip_lcd_off.append(frame[0])
        if 700 <= frame[0] < 1350:
            if not pb.memory[0xFF40] & 0x80:
                info_lcd_off.append(frame[0])
            if len(set(pb.screen.image.convert('RGB').getdata())) == 1:
                info_white.append(frame[0])
        while seal_pending and frame[0] >= seal_pending[0][0]:
            _at, offset, count = seal_pending.pop(0)
            seal_settled.append(seal_footer_state(pb, offset, count))
        if frame[0] == 220:
            settled_indicator[0] = bytes(pb.memory[0x986F:0x9873])
            snapshot('Items page 1', range(1, 6), ITEM_SHAPE, 2)
        elif frame[0] == 360:
            snapshot('Items page 2', range(6, 10), ITEM_SHAPE, 2)
        elif frame[0] == 900:
            screen_at_info = pb.memory[0xC6A3]
            snapshot('count-9 Info title', (9,), INFO_SHAPE, 0)
        if png_dir and 800 <= frame[0] <= 1250:
            os.makedirs(png_dir, exist_ok=True)
            pb.screen.image.save(os.path.join(
                png_dir, 'seal_info_f%04d.png' % frame[0]))

    if not injected[0]:
        problems.append('nine canonical equipment objects were not injected')
    if len(regional_begins) != 1:
        problems.append('two-page Items flip began %d regional transactions, expected 1'
                        % len(regional_begins))
    if regional_fallbacks:
        problems.append('two-page Items flip reached LCD-off fallback at %s'
                        % ' '.join('f%d' % at for at in regional_fallbacks))
    if page_flip_lcd_off:
        problems.append('two-page Items flip disabled LCD at %s'
                        % ' '.join('f%d' % at for at in page_flip_lcd_off))
    if info_lcd_off:
        problems.append('sealed count-9 Info/return disabled LCD at %s; attempts %s'
                        % (' '.join('f%d' % at for at in info_lcd_off),
                           ' '.join('f%d:s%d/p%d/id%d/de$%02X/sel$%02X/%s' %
                                    (at, state, phase, screen, context, selector,
                                     ','.join(str(value) for value in stack))
                                    for at, state, phase, screen, context, selector, stack
                                    in info_attempts)))
    if explicit_info_blanks:
        problems.append('sealed count-9 route reached explicit Info LCD blanker at %s' %
                        (explicit_info_blanks,))
    if info_white:
        problems.append('sealed count-9 Info/return rendered uniform frame(s) %s' %
                        ' '.join('f%d' % at for at in info_white))
    if screen_at_info != 5:
        problems.append('sealed count-9 route reached screen %s, expected screen 5' %
                        screen_at_info)
    problems += seal_footer_problems(
        'count-9 weapon', seal_publishes, seal_settled,
        seal_step_handlers, seal_group_handlers)
    if not pop_calls:
        problems.append('sealed count-9 B never reached the native popper')
    if not admitted_pops:
        problems.append('sealed count-9 B never reached the regional Info pop gate; '
                        'native calls %s' % (pop_calls,))
    if pb.memory[0xC6A3] != 1:
        problems.append('sealed count-9 B settled on screen %d, expected Items screen 1'
                        % pb.memory[0xC6A3])
    for label, failures in snapshots.items():
        problems += ['%s: %s' % (label, failure) for failure in failures]
    if set(snapshots) != {'Items page 1', 'Items page 2', 'count-9 Info title'}:
        problems.append('one or more settled checkpoints were not sampled')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
        pb.screen.image.save(os.path.join(png_dir, 'fusion_count9_info.png'))
    pb.stop(save=False)
    shield_case, shield_failures = shield_pager_case(
        PyBoy, rom, state, info_labels, png_dir=png_dir)
    problems += shield_failures

    fixture = ('Log-3 Manji+2 fixture; ' if fixture_checked else
               'Log-3 fixture not present; ')
    indicator_text = ('missing' if settled_indicator[0] is None else
                      settled_indicator[0].hex(' '))
    matrix_text = ', '.join('%dp/%di=%d/%d sel=%s' %
                            (case['pages'], case['count'], len(case['begins']),
                             len(case['draws']),
                             '/'.join('$%02X' % value for _at, value in
                                      sorted(case['selectors'].items())))
                            for case in matrix)
    print('fusioncountspill: %scanonical counts 1-9 across two Items pages; '
          'indicator %s; regional begins/fallbacks/lcd-off %d/%d/%d; '
          'matrix %s; short-page cursor $%02X/r%d (%d regional); '
          'count-9 pages weapon [%s], shield [%s], explicit blanks %d; %d problem(s)'
          % (fixture, indicator_text, len(regional_begins),
             len(regional_fallbacks), len(page_flip_lcd_off), matrix_text,
             cursor_case['selector'], cursor_case['row'],
             cursor_case['regional'],
             ' '.join('%d/%d' % (state['offset'] // 4 + 1,
                                  (state['count'] - 1) // 4 + 1)
                      for state in seal_settled),
             ' '.join('%d/%d' % page for page in shield_case['pages']),
             len(explicit_info_blanks), len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('fusioncountspill: failed')
    print('fusioncountspill: every possible fusion count $8C-$94 is plane-exact VWF; '
          'weapon and non-contiguous-mask shield own footer digits 1/3 through 3/3; '
          '$95 is rejected')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram')
    parser.add_argument('--state', default=STATE)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.ram is not None and not os.path.exists(args.ram):
        raise SystemExit('fusioncountspill: missing Log-3 SRAM: ' + args.ram)
    if args.ram is None and os.path.exists(RAM):
        args.ram = RAM
    if not os.path.exists(args.state):
        raise SystemExit('fusioncountspill: missing dungeon state: ' + args.state)
    run(args.rom, args.ram, args.state, args.png_dir)


if __name__ == '__main__':
    main()
