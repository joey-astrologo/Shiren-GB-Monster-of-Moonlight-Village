#!/usr/bin/env python3
"""Trace every Start-menu review route through the real screen dispatcher.

This is the control fixture for replacing Start-menu LCD blanking.  Static disassembly
proves which native handler owns each screen, but several handlers feed their English
rows through the same bank-41 transition controller.  This fixture supplies the other
half of the proof: real input, an isolated copy of a known SRAM, the complete screen
stack at every dispatch, and the exact translation-added LCD-off/finalizer sites hit by
each player route.

The source ROM and SRAM are never opened for writing.  Every case boots a private copy
inside a temporary directory and exits with ``save=False``.

    python3 tools/startpathspill.py build/shiren_en.gb
    python3 tools/startpathspill.py build/shiren_en.gb --case rename --trace
"""
import argparse
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gbasm                                                     # noqa: E402
import dotfont                                                   # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                   # noqa: E402
import rankvwf                                                   # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402


DEFAULT_RAM = os.path.join(ROOT, 'saves', 'shiren_en_path_select.srm')
PASSWORD_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_password.srm')
MULTI_LOG_RAM = os.path.join(ROOT, 'saves', 'shiren_en_logs_passwords.srm')
DISPATCH = (4, 0x48AA)
ROW_ENTRY = (31, 0x40D8)

# Fresh mgbdis output from build/base.gb identifies these native dispatcher targets.
SCREEN_HANDLERS = {
    15: (4, 0x4C15),
    21: (4, 0x4C55),
    22: (4, 0x4C61),
    23: (4, 0x4C75),
    24: (4, 0x4C94),
    25: (4, 0x4CAB),
    26: (4, 0x4CCA),
    30: (4, 0x4D10),
    31: (4, 0x4D20),
    32: (4, 0x4D2B),
    33: (4, 0x4D39),
    34: (4, 0x4D4A),
}

# Translation-added sites established from the assembled English ROM with mgbdis.
SITES = {
    'start-off': (41, menuvwf.start_transition_labels()['stdisable']),
    'rank-off': (43, 0x40B6),
    'native-font-off': (
        rankvwf.MANAGER_BANK,
        rankvwf.manager_labels(dotfont.load_approved())['nativeoff'],
    ),
    'name-entry-off': (44, 0x4066),
    'start-transition': (41, 0x405A),
    'start-finish': (42, 0x405A),
    'rank-finish': (43, 0x408C),
    'native-cursor': (4, 0x4E2B),
    # Derive the commit hook from the installed source instead of duplicating its
    # address; growth of the helper therefore cannot make this proof fixture stale.
    'start-region': (
        menuvwf.START_REGION_BANK,
        gbasm.assemble(menuvwf.START_REGION_SRC,
                       menuvwf.START_REGION_AT)[1]['srcommit'],
    ),
    'start-s2-selector-region': (
        menuvwf.START_S2_SELECTOR_BANK,
        gbasm.assemble(menuvwf.START_S2_SELECTOR_SRC,
                       menuvwf.START_S2_SELECTOR_AT)[1]['s2commit'],
    ),
    'start-s2-confirm-region': (
        menuvwf.START_S2_CONFIRM_BANK,
        gbasm.assemble(menuvwf.START_S2_CONFIRM_SRC,
                       menuvwf.START_S2_CONFIRM_AT)[1]['s2ccommit'],
    ),
    'start-root-return-region': (
        menuvwf.START_ROOT_RETURN_BANK,
        menuvwf.start_root_return_labels()['srrcommit'],
    ),
    'start-difficulty-region': (
        menuvwf.START_DIFFICULTY_BANK,
        menuvwf.start_difficulty_labels()['sdcommit'],
    ),
    'start-rank-choice-region': (
        menuvwf.START_RANK_CHOICE_BANK,
        menuvwf.start_rank_choice_labels()['srccommit'],
    ),
}
REGIONAL_SITES = {
    'start-region', 'start-s2-selector-region', 'start-s2-confirm-region',
    'start-root-return-region', 'start-difficulty-region',
    'start-rank-choice-region',
}


BOOT = {700: 'start', 760: 'start', 820: 'start', 880: 'start'}


def buttons(*events):
    result = dict(BOOT)
    result.update(dict(events))
    return result


# All cases start from the supplied one-log path-select save.  The long gaps are
# deliberate: these traces describe state-machine edges, not input-repeat timing.
CASES = {
    'adventure': {
        'buttons': buttons((1250, 'a'), (1700, 'down'), (1900, 'up'),
                           (2200, 'b')),
        'frames': 2450,
        'screens': (23, 23, 23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 23, 23, 15),
    },
    'new': {
        'buttons': buttons((1250, 'down'), (1350, 'a'), (1650, 'a'),
                           (1950, 'down'), (2200, 'down'), (2500, 'b'),
                           (2800, 'b')),
        'frames': 3050,
        'screens': (22, 25, 25, 25, 15, 22, 15),
        'start_off_screens': (),
        'native_off_screens': (),
        'regional_screens': (22, 25, 25, 25, 15, 22, 15),
    },
    'copy': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1400, 'a'),
                           (1800, 'a'), (2200, 'a')),
        'frames': 2450,
        'screens': (23, 26, 15),
        'start_off_screens': (),
        'native_off_screens': (15,),
        'regional_screens': (23, 26),
    },
    'erase': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1370, 'down'),
                           (1460, 'a'), (1800, 'a'), (2200, 'down'), (2400, 'a')),
        'frames': 2650,
        'screens': (23, 24),
        'start_off_screens': (),
        'native_off_screens': (15,),
        'regional_screens': (23, 24),
    },
    'rename': {
        # Same established route as tools/namerun.py --rename, but the ROM/SRAM stay
        # private here and the test stops shortly after entering the native keyboard.
        'buttons': buttons((1250, 'down'), (1290, 'down'), (1330, 'down'),
                           (1370, 'down'), (1420, 'a'), (1600, 'a')),
        'frames': 1900,
        'screens': (23, 8),
        'start_off_screens': (),
        'regional_screens': (23,),
    },
    'rank-direct': {
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1350, 'down'), (1390, 'down'), (1460, 'a'),
                           (1750, 'a'), (2050, 'b'), (2350, 'b')),
        'frames': 2600,
        'screens': (30, 33, 15, 30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 30, 15),
    },
    'rank-category': {
        # A three-log title has six rows, so Rank/Pass is the fourth row.  More than
        # one eligible log sets $C6E1 and exposes conditional screen 31 before 33.
        'ram': MULTI_LOG_RAM,
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1400, 'a'), (1650, 'a'), (1900, 'a'),
                           (2250, 'b'), (2550, 'b'), (2850, 'b')),
        'frames': 3100,
        'screens': (30, 31, 33, 15, 30, 31, 15, 30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 31, 30, 31, 15, 30, 15),
    },
    'pass': {
        'ram': PASSWORD_RAM,
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1350, 'down'), (1390, 'down'), (1460, 'a'),
                           (1700, 'down'), (1800, 'a'), (2050, 'a'),
                           (2400, 'b'), (2700, 'b'), (3000, 'b')),
        'frames': 3250,
        'screens': (30, 32, 34, 15, 30, 32, 15, 30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 32, 30, 32, 15, 30, 15),
    },
    'replay': {
        'buttons': buttons((1210, 'down'), (1250, 'down'), (1290, 'down'),
                           (1330, 'down'), (1370, 'down'), (1410, 'down'),
                           (1500, 'a'), (1850, 'a')),
        'frames': 2300,
        'screens': (23,),
        'start_off_screens': (),
        'regional_screens': (23,),
    },
    # S2R freezes every direct file-child B return independently.  The forward cases
    # above cover deeper/committing behavior; these short cases make it impossible for
    # one shared root reconstruction to hide a context-specific regression.
    'return-adventure': {
        'buttons': buttons((1250, 'a'), (1750, 'b')),
        'frames': 2050,
        'screens': (23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 15),
        'native_off_screens': (),
    },
    'return-new': {
        'buttons': buttons((1250, 'down'), (1350, 'a'), (1750, 'b')),
        'frames': 2050,
        'screens': (22, 15),
        'start_off_screens': (),
        'regional_screens': (22, 15),
        'native_off_screens': (),
    },
    'return-copy-summary': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1400, 'a'),
                           (1800, 'b')),
        'frames': 2100,
        'screens': (23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 15),
        'native_off_screens': (),
    },
    'return-copy-destination': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1400, 'a'),
                           (1750, 'a'), (2100, 'b')),
        'frames': 2400,
        'screens': (23, 26, 15),
        'start_off_screens': (),
        # B first replays the root transaction, then restores the source-summary
        # parent.  Both child screens must therefore commit their own regions.
        'regional_screens': (23, 26, 15, 23),
        'native_off_screens': (),
    },
    'return-erase-summary': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1370, 'down'),
                           (1460, 'a'), (1850, 'b')),
        'frames': 2150,
        'screens': (23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 15),
        'native_off_screens': (),
    },
    'return-erase-confirmation': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1370, 'down'),
                           (1460, 'a'), (1800, 'a'), (2150, 'b')),
        'frames': 2450,
        'screens': (23, 24, 15),
        'start_off_screens': (),
        # B first replays the root transaction, then restores the summary parent.
        'regional_screens': (23, 24, 15, 23),
        'native_off_screens': (),
    },
    'return-rename-summary': {
        'buttons': buttons((1250, 'down'), (1290, 'down'), (1330, 'down'),
                           (1370, 'down'), (1450, 'a'), (1850, 'b')),
        'frames': 2150,
        'screens': (23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 15),
        'native_off_screens': (),
    },
    'return-replay': {
        'buttons': buttons((1210, 'down'), (1250, 'down'), (1290, 'down'),
                           (1330, 'down'), (1370, 'down'), (1410, 'down'),
                           (1500, 'a'), (1900, 'b')),
        'frames': 2200,
        'screens': (23, 15),
        'start_off_screens': (),
        'regional_screens': (23, 15),
        'native_off_screens': (),
    },
    # S4 freezes the retained Rank/Pass choice layers separately from their approved
    # independent final displays. These focused routes never enter screens 33/34, so
    # any LCD-off or uniform-white frame is unambiguously a choice-layer regression.
    'return-rank-pass': {
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1350, 'down'), (1390, 'down'), (1460, 'a'),
                           (1750, 'b')),
        'frames': 2050,
        'screens': (30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 15),
        'native_off_screens': (),
    },
    'return-rank-category': {
        'ram': MULTI_LOG_RAM,
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1400, 'a'), (1650, 'a'), (1900, 'b'),
                           (2200, 'b')),
        'frames': 2450,
        'screens': (30, 31, 15, 30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 31, 15, 30, 15),
        'native_off_screens': (),
    },
    'return-pass-selector': {
        'ram': PASSWORD_RAM,
        'buttons': buttons((1230, 'down'), (1270, 'down'), (1310, 'down'),
                           (1350, 'down'), (1390, 'down'), (1460, 'a'),
                           (1700, 'down'), (1800, 'a'), (2100, 'b'),
                           (2400, 'b')),
        'frames': 2650,
        'screens': (30, 32, 15, 30, 15),
        'start_off_screens': (),
        'regional_screens': (30, 32, 15, 30, 15),
        'native_off_screens': (),
    },
    # Post-S2R visual discovery: these are cancellation edges too, but they do not use
    # the direct B/file-child history above. Adventure has an intervening screen 21;
    # Erase selects No with A and therefore needs proof of the saved confirmation row.
    'return-adventure-choice': {
        'buttons': buttons((1250, 'a'), (1750, 'a'), (2150, 'b')),
        'frames': 2500,
        'screens': (23, 21, 15, 23),
        'start_off_screens': (),
        'regional_screens': (23, 15, 23),
        'native_off_screens': (),
    },
    'return-erase-no': {
        'buttons': buttons((1250, 'down'), (1310, 'down'), (1370, 'down'),
                           (1460, 'a'), (1800, 'a'), (2200, 'a')),
        'frames': 2550,
        'screens': (23, 24, 15, 23),
        'start_off_screens': (),
        'regional_screens': (23, 24, 15, 23),
        'native_off_screens': (),
    },
    'difficulty-cycle': {
        'buttons': buttons((1250, 'down'), (1350, 'a'), (1650, 'a'),
                           (1950, 'down'), (2200, 'down'), (2500, 'b')),
        'frames': 2800,
        'screens': (22, 25, 25, 25, 15, 22),
        'start_off_screens': (),
        'regional_screens': (22, 25, 25, 25, 15, 22),
        'native_off_screens': (),
    },
}


def stack(pb):
    depth = pb.memory[0xC534]
    if depth > 9:
        return ()
    return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))


def state(pb):
    return tuple(pb.memory[address] for address in range(0xC1B1, 0xC1B8))


def menu_state(pb):
    return tuple(pb.memory[address] for address in
                 (0xC6A3, 0xC6A4, 0xC6A5, 0xC6A6, 0xC6AA, 0xC6AB,
                  0xC6AC, 0xC6BB, 0xC6DE))


def is_subsequence(want, got):
    at = 0
    for value in got:
        if at < len(want) and value == want[at]:
            at += 1
    return at == len(want)


def run_case(PyBoy, rom, ram, label, case, trace=False):
    with tempfile.TemporaryDirectory(prefix='startpathspill-%s-' % label) as tmp:
        work = os.path.join(tmp, 'start.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        handlers = []
        sites = []
        rows = []
        root_cursor_commits = []
        root_rasters = []
        lcd_off_frames = []
        white_frames = []

        def effective_root_selector():
            saved_depth = pb.memory[0xC6A6]
            if saved_depth:
                return pb.memory[0xC53F + saved_depth - 1] & 0x0F
            return pb.memory[0xC6A5]

        def dispatch(_context=None):
            dispatches.append({
                'frame': frame[0],
                'incoming': pb.register_file.A,
                'stack': stack(pb),
                'state': state(pb),
                'menu': menu_state(pb),
                'saved': tuple(pb.memory[0xC53F + index] for index in range(5)),
                'input': pb.memory[0xFF84],
                'lcdc': pb.memory[0xFF40],
            })

        def handler(screen):
            def callback(_context=None):
                handlers.append((frame[0], screen, stack(pb), state(pb),
                                 pb.memory[0xFF40]))
            return callback

        def site(name):
            def callback(_context=None):
                sites.append((frame[0], name, pb.memory[0xC6A3], stack(pb),
                              state(pb), pb.memory[0xFF40]))
            return callback

        def row(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            rows.append((frame[0], pb.memory[0xC6A3], pb.register_file.D,
                         pb.register_file.HL, shape, stack(pb)))

        def root_cursor_commit(stage):
            def callback(_context=None):
                if pb.memory[0xC6A3] != 15:
                    return
                count = min(pb.memory[0xC69C], 8)
                root_cursor_commits.append((
                    frame[0], stage, effective_root_selector(), count,
                    tuple(pb.memory[0xC341 + row * 0x40]
                          for row in range(count)),
                    tuple(pb.memory[0x9841 + row * 0x40]
                          for row in range(count)),
                ))
                root_raster_commit()
            return callback

        def root_raster_commit(_context=None):
            if pb.memory[0xC6A3] != 15:
                return
            shadow = bytes(pb.memory[0xC300:0xC700])
            cursor_cells = {0x41 + row * 0x40 for row in range(8)}
            # Compare the resolved 20x18 pixels, not allocator IDs.  All possible
            # cursor-owned cells are normalized because the correct return restores
            # the selected file action rather than forcing Adventure.
            raster = []
            for row in range(18):
                for col in range(20):
                    offset = row * 32 + col
                    tile = 0 if offset in cursor_cells else shadow[offset]
                    at = menuspill.tile_data_addr(tile)
                    raster.append(bytes(pb.memory[at:at + 16]))
            root_rasters.append((frame[0], tuple(raster)))

        pb.hook_register(*DISPATCH, dispatch, None)
        pb.hook_register(*ROW_ENTRY, row, None)
        for screen, location in SCREEN_HANDLERS.items():
            pb.hook_register(*location, handler(screen), None)
        for name, location in SITES.items():
            pb.hook_register(*location, site(name), None)
        _finish_code, finish_labels = gbasm.assemble(
            menuvwf.START_FINISH_SRC, menuvwf.START_FINISH_AT)
        pb.hook_register(menuvwf.START_FINISH_BANK, finish_labels['sfcursorready'],
                         root_cursor_commit('shadow'), None)

        script = case['buttons']
        for frame[0] in range(case['frames']):
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if case.get('native_off_screens') == () and frame[0] >= 1200:
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off_frames.append(frame[0])
                elif pb.screen.image.convert('L').getextrema() == (255, 255):
                    white_frames.append(frame[0])
        final = (pb.memory[0xC6A3], stack(pb), state(pb), pb.memory[0xFF40])
        root_rows = pb.memory[0xC6BB]
        root_selector = pb.memory[0xC6A5]
        root_shadow_cursors = tuple(
            pb.memory[0xC341 + row * 0x40] for row in range(min(root_rows, 8)))
        root_bg_cursors = tuple(
            pb.memory[0x9841 + row * 0x40] for row in range(min(root_rows, 8)))
        pb.stop(save=False)

    screens = tuple(event['incoming'] for event in dispatches)
    problems = []
    if not is_subsequence(case['screens'], screens):
        problems.append('wanted screen subsequence %s, got %s' %
                        (case['screens'], screens))
    if not dispatches:
        problems.append('screen dispatcher was never reached')
    if not final[3] & 0x80:
        problems.append('route ended with LCD disabled (LCDC=$%02X)' % final[3])
    if final[0] == 15:
        if not 3 <= root_rows <= 8:
            problems.append('returned Start root has invalid row count %d' % root_rows)
        else:
            want_root_cursors = tuple(
                0x81 if row == root_selector else 0x00 for row in range(root_rows))
            if root_shadow_cursors != want_root_cursors:
                problems.append('returned Start shadow cursor cells want %s, got %s' %
                                (want_root_cursors, root_shadow_cursors))
            if root_bg_cursors != want_root_cursors:
                problems.append('returned Start BG cursor cells want %s, got %s' %
                                (want_root_cursors, root_bg_cursors))
    for at, stage, selector, count, shadow_cells, bg_cells in root_cursor_commits:
        want = tuple(0x81 if row == selector else 0x00 for row in range(count))
        got = bg_cells if stage == 'published' else shadow_cells
        if got != want:
            problems.append('f%d %s Start cursor commit wants %s, got %s' %
                            (at, stage, want, got))
    if case.get('native_off_screens') == ():
        if len(root_rasters) < 2:
            problems.append('S2R route captured %d complete Start-root raster(s), '
                            'expected initial plus return' % len(root_rasters))
        elif any(raster != root_rasters[0][1]
                 for _at, raster in root_rasters[1:]):
            bad = [at for at, raster in root_rasters[1:]
                   if raster != root_rasters[0][1]]
            problems.append('returned Start root differs from its initial resolved '
                            'raster at frame(s) %s' % bad)
        if lcd_off_frames:
            problems.append('S2R route disabled LCD after root settled at frame(s) %s' %
                            lcd_off_frames[:12])
        if white_frames:
            problems.append('S2R route exposed whole-white frame(s) %s' %
                            white_frames[:12])

    start_off_screens = tuple(event[2] for event in sites
                              if event[1] == 'start-off')
    if start_off_screens != case['start_off_screens']:
        problems.append('wanted Start LCD-off screens %s, got %s' %
                        (case['start_off_screens'], start_off_screens))
    native_off_screens = tuple(event[2] for event in sites
                               if event[1] == 'native-font-off')
    if ('native_off_screens' in case and
            native_off_screens != case['native_off_screens']):
        problems.append('wanted native-font LCD-off screens %s, got %s' %
                        (case['native_off_screens'], native_off_screens))
    regional_screens = tuple(event[2] for event in sites
                             if event[1] in REGIONAL_SITES)
    if regional_screens != case['regional_screens']:
        problems.append('wanted regional screens %s, got %s' %
                        (case['regional_screens'], regional_screens))

    causal = [event for event in sites if event[1].endswith('-off')]
    print('startpathspill: %-13s screens=%s; regional=%s; causal=%s; '
          '%d row(s); %d problem(s)' %
          (label, ','.join(str(value) for value in screens) or '-',
           ','.join(str(value) for value in regional_screens) or '-',
           ','.join('%s@%d' % (name, at) for at, name, *_rest in causal) or '-',
           len(rows), len(problems)))
    if trace:
        for event in dispatches:
            print('  f%-4d dispatch %-2d stack=%-18s state=%s menu=%s saved=%s '
                  'input=$%02X lcdc=$%02X' %
                  (event['frame'], event['incoming'], str(event['stack']),
                   ''.join('%02X' % value for value in event['state']),
                   ''.join('%02X' % value for value in event['menu']),
                   ''.join('%02X' % value for value in event['saved']),
                   event['input'],
                   event['lcdc']))
        for event in sites:
            at, name, screen, event_stack, event_state, lcdc = event
            print('  f%-4d %-15s screen=%-2d stack=%-18s state=%s lcdc=$%02X' %
                  (at, name, screen, str(event_stack),
                   ''.join('%02X' % value for value in event_state), lcdc))
        shapes = []
        for _at, screen, _row, _hl, shape, _stack in rows:
            key = (screen, shape)
            if key not in shapes:
                shapes.append(key)
        print('  row shapes ' + (' '.join('%d:%s' % item for item in shapes) or '-'))
        print('  handlers   ' + (' '.join('f%d:%d%s' % (at, screen, event_stack)
                                         for at, screen, event_stack, _state, _lcdc
                                         in handlers) or '-'))
        print('  final      screen=%d stack=%s state=%s lcdc=$%02X' %
              (final[0], final[1], ''.join('%02X' % value for value in final[2]),
               final[3]))
        if final[0] == 15:
            print('  root cursor rows=%d shadow=%s BG=%s' %
                  (root_rows,
                   ' '.join('%02X' % value for value in root_shadow_cursors),
                   ' '.join('%02X' % value for value in root_bg_cursors)))
        for at, stage, selector, count, shadow_cells, bg_cells in root_cursor_commits:
            print('  f%-4d root-cursor %-9s selector=%d rows=%d shadow=%s BG=%s' %
                  (at, stage, selector, count,
                   ' '.join('%02X' % value for value in shadow_cells),
                   ' '.join('%02X' % value for value in bg_cells)))
    for problem in problems:
        print('  ' + problem)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram',
                        help='override the case-specific SRAM (normally omit this)')
    parser.add_argument('--case', choices=('all',) + tuple(CASES), default='all')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    required_rams = {args.ram} if args.ram else {
        CASES[label].get('ram', DEFAULT_RAM)
        for label in (CASES if args.case == 'all' else (args.case,))
    }
    for path in (args.rom,) + tuple(sorted(required_rams)):
        if not os.path.exists(path):
            raise SystemExit('startpathspill: missing %s' % path)

    PyBoy = _import_pyboy()
    labels = tuple(CASES) if args.case == 'all' else (args.case,)
    problems = []
    for label in labels:
        ram = args.ram or CASES[label].get('ram', DEFAULT_RAM)
        problems.extend('%s: %s' % (label, problem)
                        for problem in run_case(PyBoy, args.rom, ram, label,
                                                CASES[label], args.trace))
    print('startpathspill: %d route(s), %d total problem(s)' %
          (len(labels), len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
