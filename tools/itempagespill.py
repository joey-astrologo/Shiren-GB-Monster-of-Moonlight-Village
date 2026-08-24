#!/usr/bin/env python3
"""Replay the multi-page item-menu transition from cartridge RAM.

``saves/shiren_en_item_menu.srm`` contains one populated log with enough inventory for
four carried pages plus the standing-item Floor page. This route boots that log normally, opens Menu -> Items, then pages
right and left and invokes Start-sort through the real input handler. It records every
item-row draw and audits the regional transaction at frame granularity: LCD-on ownership,
old/blank/new row states,
locked map cells, locked structural tile planes, and the fixed-width empty rows on the
short final page.

The older ``menuspill --ram`` fixture has three logs and uses fixed title-menu timings.
Those timings do not select the one-log regional fixture, so this route deliberately owns the
item-page transition acceptance claim.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
import gbasm                                                      # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
PAGE_INDICATOR_AT = 0x9800 + 3 * 32 + 15
PAGE_TILES = {
    0xC5: bytes.fromhex('00 00 FF FF FF FF 00 00 00 00 18 18 18 18 00 00'),
    0xC6: bytes.fromhex('00 00 FF FF FF FF 18 18 3C 24 7E 42 3C 24 18 18'),
}
STRUCTURAL_TILES = (0x81, 0x83, 0x84, 0x85, *range(0xB8, 0xC0), 0xC5, 0xC6)


def transition_snapshot(pb):
    """Memory that defines visible ownership, captured after one emulated frame."""
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'shadow': bytes(pb.memory[0xC300:0xC700]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'state': pb.memory[0xC1B3],
        'lcd': bool(pb.memory[0xFF40] & 0x80),
        'window': bool(pb.memory[0xFF40] & 0x20),
        'ly': pb.memory[0xFF44],
        'selector': pb.memory[0xC6AC],
        'floor_latch': pb.memory[0xC1B7],
    }


def tile_planes(snapshot, tile):
    address = menuspill.tile_data_addr(tile)
    start = address - 0x8800
    return snapshot['tiles'][start:start + 16]


def row_signature(snapshot, row):
    """Exact tile references plus both physical bitplanes for one name interior."""
    start = (4 + 2 * row) * 32 + 3
    refs = snapshot['bg'][start:start + 16]
    return refs, tuple(tile_planes(snapshot, tile) for tile in refs)


def row_blank(snapshot, row):
    start = (4 + 2 * row) * 32 + 3
    return snapshot['bg'][start:start + 16] == bytes(16)


def visual_name_signature(image, row):
    """Rendered pixels at the left of a name, away from the roaming menu sprite."""
    y = (4 + 2 * row) * 8
    return image.crop((24, y, 64, y + 8)).convert('RGB').tobytes()


def visual_name_blank(image, row):
    pixels = image.crop((24, (4 + 2 * row) * 8,
                         64, (4 + 2 * row) * 8 + 8)).convert('RGB').getdata()
    return len(set(pixels)) == 1


def row_publishing(snapshot, settled, row):
    """True for an in-VBlank blank-to-new map copy that cannot reach scanout partial."""
    refs, planes = row_signature(snapshot, row)
    new_refs, new_planes = row_signature(settled, row)
    saw_blank = False
    for ref, plane, new_ref, new_plane in zip(refs, planes, new_refs, new_planes):
        if ref == 0:
            saw_blank = True
        elif ref != new_ref or plane != new_plane:
            return False
    return saw_blank and refs != bytes(16)


def row_blanking(snapshot, outgoing, row):
    """True for an in-VBlank old-to-blank map copy."""
    refs, planes = row_signature(snapshot, row)
    old_refs, old_planes = row_signature(outgoing, row)
    saw_blank = False
    for ref, plane, old_ref, old_plane in zip(refs, planes, old_refs, old_planes):
        if ref == 0:
            saw_blank = True
        elif ref != old_ref or plane != old_plane:
            return False
    return saw_blank and refs != bytes(16)


def locked_map_changes(before, after, kind, floor_expand=False):
    """Return visible cells changed outside the regional transaction's write set."""
    allowed = {(3, col) for col in range(15, 19)}
    for row in range(5):
        # The visible transaction owns the marker-coupled left border, marker,
        # cursor, and name cells. The cursor is separately published by native code.
        allowed.update((4 + 2 * row, col) for col in range(0, 19))
    if floor_expand:
        # The one-row Floor rectangle is becoming the five-row Items rectangle.
        allowed.update((row, col) for row in range(3, 14) for col in range(20))
    changed = []
    for row in range(18):
        for col in range(20):
            index = row * 32 + col
            if (row, col) not in allowed and before[index] != after[index]:
                changed.append((kind, row, col, before[index], after[index]))
    return changed


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(row)
        row.append(value)
    return tuple(row)


def run(rom_path, ram_path, png_dir=None, frames=3900, settle_frames=90,
        test_wrap=True):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('itempagespill: requires the Dot proportional renderer')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)

    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='itempagespill-') as tmp:
        run_rom = os.path.join(tmp, 'itempages.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        pages = []
        current = [None]
        scheduled = dict(BOOT)
        page_presses = []
        sort_presses = []
        right_wrap_pending = [False]
        right_wrap_dispatches = []
        capture_until = [-1]
        captured = set()
        scoped_lcd_off = []
        scoped_regional_begins = []
        scoped_legacy_fallbacks = []
        pre_gate_queues = []
        sort_snapshots = []
        sort_blank_frame = [None]

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))
            # Native right wrap is deliberately two-stage for this real four-page save:
            # the first Right selects $FF and draws the one-row standing-item Floor page,
            # while the next Right selects page 1 and restores the ordinary five-row shape. Drive both
            # physical inputs so the transient all-$BC page marker is regression-tested.
            if (right_wrap_pending[0] and pb.register_file.A == 1 and
                    pb.memory[0xC6AC] == 0xFF):
                at = frame[0] + settle_frames
                scheduled[at] = 'right'
                page_presses.append((at, 'right'))
                right_wrap_dispatches.append(frame[0])
                right_wrap_pending[0] = False
            # Screen 0 is the in-dungeon main menu.  Select its default Items entry only
            # after this save has actually reached it; fixed post-boot timing is brittle.
            if pb.register_file.A == 0 and not any(button == 'a'
                                                    for at, button in scheduled.items()
                                                    if at > frame[0]):
                scheduled[frame[0] + 80] = 'a'

        def far_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE:
                return
            rownum = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if rownum == 0:
                current[0] = {
                    'start': frame[0], 'rows': {},
                    'old': transition_snapshot(pb),
                    'old_image': pb.screen.image.copy(), 'frames': [],
                    'lcd_off_frames': [], 'cursor_seen': False,
                    'regional_begins': [], 'legacy_fallbacks': [],
                    'fixed_empty_rows': [], 'state_trace': [],
                    'regional_origin': None, 'shadow_blanked': None,
                    'visible_blanked': None,
                    'row_commits': [],
                }
                pages.append(current[0])
                capture_until[0] = max(capture_until[0], frame[0] + 70)
            if current[0] is None:
                return
            current[0]['rows'][rownum] = row
            if rownum == 4:
                current[0]['complete'] = frame[0]
                # Cross the equipped page-1/page-2 boundary in both directions, then
                # continue to pages 3 and 4 and sort that real mixed inventory with
                # Start. Schedule relative to the real row-4
                # completion so renderer timing changes cannot swallow a press or
                # accidentally overlap a draw.
                directions = (('right', 'left', 'right', 'right', 'right', 'right')
                              if test_wrap else
                              ('right', 'left', 'right', 'right', 'right', 'left'))
                if len(page_presses) < len(directions):
                    button = directions[len(page_presses)]
                elif not sort_presses:
                    button = 'start'
                else:
                    button = None
                if button is not None:
                    at = frame[0] + settle_frames
                    scheduled[at] = button
                    if button == 'start':
                        sort_presses.append((at, button))
                    else:
                        page_presses.append((at, button))
                        if test_wrap and len(page_presses) == len(directions):
                            right_wrap_pending[0] = True

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)

        _region_code, region_labels = gbasm.assemble(
            menuvwf.ITEM_REGION_SRC, menuvwf.ITEM_REGION_AT)

        def region_event(field):
            def record(_ctx=None):
                if page_presses and frame[0] >= page_presses[0][0] - 2:
                    if field == 'regional_begins':
                        scoped_regional_begins.append(frame[0])
                    elif field == 'legacy_fallbacks':
                        scoped_legacy_fallbacks.append(frame[0])
                if current[0] is not None and frame[0] <= capture_until[0]:
                    current[0][field].append(frame[0])
                    if field == 'regional_begins':
                        current[0]['regional_origin'] = transition_snapshot(pb)
            return record

        def region_snapshot(field):
            def record(_ctx=None):
                if current[0] is not None and frame[0] <= capture_until[0]:
                    current[0][field] = transition_snapshot(pb)
            return record

        def row_commit(_ctx=None):
            if current[0] is not None and frame[0] <= capture_until[0]:
                current[0]['row_commits'].append(
                    (frame[0], pb.memory[0xFF44], pb.register_file.D))

        # irshadow is reached only after the visible page-indicator gate succeeds.
        # irfaillcd is the conservative LCD-off branch, not the mode-3 entry itself:
        # fixed-width empty rows enter mode 3 and are deliberately recovered before it.
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irshadow'],
                         region_event('regional_begins'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irpredrain'],
                         lambda _ctx=None: pre_gate_queues.append(
                             (frame[0], pb.memory[0xC11A])), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irvisible'],
                         region_snapshot('shadow_blanked'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irarmed'],
                         region_snapshot('visible_blanked'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irfaillcd'],
                         region_event('legacy_fallbacks'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irfixedempty'],
                         region_event('fixed_empty_rows'), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['ircopy'],
                         row_commit, None)

        for current_frame in range(frames):
            frame[0] = current_frame
            button = scheduled.get(current_frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if page_presses and current_frame >= page_presses[0][0] - 2 and \
                    not pb.memory[0xFF40] & 0x80:
                scoped_lcd_off.append(current_frame)
            if sort_presses and sort_presses[0][0] - 2 <= current_frame <= \
                    sort_presses[0][0] + 30:
                sort_snapshots.append((current_frame, pb.screen.image.copy(),
                                       transition_snapshot(pb)))
                if png_dir:
                    pb.screen.image.save(os.path.join(
                        png_dir, 'sort_f%04d.png' % current_frame))
            if pages and current_frame <= capture_until[0]:
                transition = len(pages) - 1
                image = pb.screen.image.copy()
                snapshot = transition_snapshot(pb)
                pages[-1]['frames'].append((current_frame, image, snapshot))
                pages[-1]['state_trace'].append((current_frame, snapshot['state']))
                if not snapshot['lcd']:
                    pages[-1]['lcd_off_frames'].append(current_frame)
                # Item row 0 begins at shadow $C380: border, equipped-marker cell,
                # then the native cursor cell. Left/Right paging keeps selection at 0.
                if pb.memory[0xFF40] & 0x80 and pb.memory[0xC382] == 0x81:
                    pages[-1]['cursor_seen'] = True
                key = (transition, current_frame)
                if png_dir and key not in captured:
                    captured.add(key)
                    image.save(os.path.join(
                        png_dir, 'transition%02d_f%04d.png' % key))

        signatures = []
        for page in pages:
            if set(page['rows']) == set(range(5)):
                signatures.append(tuple(page['rows'][row] for row in range(5)))
            else:
                problems.append('page beginning f%d captured rows %s, expected 0-4'
                                % (page['start'], sorted(page['rows'])))
        unique = []
        for signature in signatures:
            if signature not in unique:
                unique.append(signature)
        if len(unique) < 4:
            problems.append('reached %d unique item pages, expected at least 4'
                            % len(unique))
        if not any(index == 0 for _at, index in dispatches):
            problems.append('real route never dispatched the in-dungeon main menu')
        if not page_presses:
            problems.append('real route never scheduled an item-page direction press')
        if not sort_presses:
            problems.append('real route never scheduled Start-sort')
        expected_wraps = 1 if test_wrap else 0
        if len(right_wrap_dispatches) != expected_wraps:
            problems.append('real route observed %d standing-Floor wrap dispatches, '
                            'expected %d' % (len(right_wrap_dispatches), expected_wraps))
        expected_regional = len(page_presses) + len(sort_presses)
        if len(scoped_regional_begins) != expected_regional:
            problems.append('Items route began %d scoped regional transactions, '
                            'expected %d for its direction/sort inputs' %
                            (len(scoped_regional_begins), expected_regional))
        if scoped_legacy_fallbacks:
            problems.append('Items route reached scoped LCD-off fallback at %s' %
                            ' '.join('f%d' % at for at in scoped_legacy_fallbacks))
        if right_wrap_dispatches and not any(
                right_wrap_dispatches[0] <= at <= right_wrap_dispatches[0] + 5
                for at in scoped_regional_begins):
            problems.append('standing-Floor $FF page did not begin a regional '
                            'transaction')
        if scoped_lcd_off:
            problems.append('Items route disabled LCD at %s' %
                            ' '.join('f%d' % at for at in scoped_lcd_off))

        transition_traces = []
        for index, page in enumerate(pages):
            samples = page['frames']
            if not samples:
                problems.append('transition %d has no rendered-frame samples' % index)
                continue
            if not page['cursor_seen']:
                problems.append('transition %d never restores the row-0 cursor at $C382'
                                % index)

            if index == 0:
                if page['regional_begins']:
                    problems.append('initial Items entry incorrectly began a regional '
                                    'page transaction at %s'
                                    % ' '.join('f%d' % at
                                               for at in page['regional_begins']))
                continue

            if len(page['regional_begins']) != 1:
                problems.append('page flip %d began %d regional transactions, expected 1'
                                % (index, len(page['regional_begins'])))
            if page['legacy_fallbacks']:
                problems.append('page flip %d reached LCD-off fallback at %s'
                                % (index, ' '.join('f%d' % at
                                                   for at in page['legacy_fallbacks'])))
            if page['lcd_off_frames']:
                problems.append('page flip %d disabled the LCD at %s'
                                % (index, ' '.join('f%d' % at
                                                   for at in page['lcd_off_frames'])))

            empty_rows = sum(all(value == 0 for value in page['rows'].get(row, ())[:19])
                             and len(page['rows'].get(row, ())) >= 19
                             for row in range(5))
            if len(page['fixed_empty_rows']) != empty_rows:
                problems.append('page flip %d recovered %d fixed empty row(s), expected %d'
                                % (index, len(page['fixed_empty_rows']), empty_rows))
            committed_rows = [row for _at, _ly, row in page['row_commits']]
            if committed_rows != list(range(5)):
                problems.append('page flip %d committed rows %s, expected 0 1 2 3 4'
                                % (index, ' '.join(str(row)
                                                   for row in committed_rows)))
            late_commit = next(((at, ly, row) for at, ly, row in page['row_commits']
                                if ly < 0x90), None)
            if late_commit is not None:
                at, ly, row = late_commit
                problems.append('page flip %d committed row %d outside VBlank at f%d '
                                '(LY=$%02X)' % (index, row, at, ly))

            old = page['old']
            new = samples[-1][2]
            old_image = page['old_image']
            new_image = samples[-1][1]
            new_rows = tuple(visual_name_signature(new_image, row) for row in range(5))
            old_rows = tuple(visual_name_signature(old_image, row) for row in range(5))
            observations = []
            first_new = None
            for sample_index, (at, image, _memory) in enumerate(samples):
                states = []
                for row in range(5):
                    signature = visual_name_signature(image, row)
                    old_match = signature == old_rows[row]
                    new_match = signature == new_rows[row]
                    blank = visual_name_blank(image, row)
                    if old_match and new_match:
                        state = '='
                    elif new_match:
                        state = 'N'
                    elif blank:
                        state = 'B'
                    elif old_match:
                        state = 'O'
                    else:
                        state = 'X'
                    states.append(state)
                states = ''.join(states)
                observations.append((at, states))
                if first_new is None and all(state in 'N=' for state in states):
                    first_new = sample_index
            # Start-sort can redraw the same visible order. In that case the first
            # sample is already equal to the final page; audit through the regional
            # blank and the subsequent return instead of stopping immediately.
            if old_rows == new_rows:
                first_blank = next((sample_index for sample_index, (_at, states)
                                    in enumerate(observations) if 'B' in states), None)
                if first_blank is not None:
                    first_new = next((sample_index for sample_index, (_at, states)
                                      in enumerate(observations[first_blank + 1:],
                                                   first_blank + 1)
                                      if all(state in 'N=' for state in states)), None)
            if first_new is None:
                problems.append('page flip %d never reaches five settled rows' % index)
                continue
            audit = observations[:first_new + 1]
            reached_new = [False] * 5
            for at, states in audit:
                if 'X' in states:
                    problems.append('page flip %d has an unowned rendered row at f%d (%s)'
                                    % (index, at, states))
                    break
                regressed = next((row for row, state in enumerate(states)
                                  if reached_new[row] and state not in 'N='), None)
                if regressed is not None:
                    problems.append('page flip %d row %d regresses after becoming new '
                                    'at f%d (%s)' % (index, regressed, at, states))
                    break
                for row, state in enumerate(states):
                    if state == 'N':
                        reached_new[row] = True

            for at, _image, memory in samples[:first_new + 1]:
                partial_marker = None
                for row in range(5):
                    offset = (4 + 2 * row) * 32
                    pair = memory['bg'][offset:offset + 2]
                    old_pair = old['bg'][offset:offset + 2]
                    new_pair = new['bg'][offset:offset + 2]
                    if pair not in (old_pair, new_pair, bytes((0xBE, 0x00))):
                        partial_marker = (row, pair, old_pair, new_pair)
                        break
                if partial_marker is not None:
                    row, pair, old_pair, new_pair = partial_marker
                    problems.append('page flip %d exposes partial marker row %d at f%d: '
                                    '%s (old %s, blank be00, new %s)' %
                                    (index, row, at, pair.hex(), old_pair.hex(),
                                     new_pair.hex()))
                    break

            old_structural = {tile: tile_planes(old, tile)
                              for tile in STRUCTURAL_TILES}
            blank_targets = {(4 + 2 * row) * 32 + col
                             for row in range(5) for col in (1, *range(3, 19))}
            borders = {(4 + 2 * row) * 32 for row in range(5)}
            region_targets = blank_targets | borders
            origin = page['regional_origin']
            shadow_blanked = page['shadow_blanked']
            visible_blanked = page['visible_blanked']
            floor_expand = False
            if origin is None or shadow_blanked is None or visible_blanked is None:
                problems.append('page flip %d did not capture all regional blank '
                                'boundaries' % index)
            else:
                floor_expand = (origin['floor_latch'] == 1 and
                                origin['selector'] != 0xFF)
                if not origin['lcd'] or not shadow_blanked['lcd'] or not visible_blanked['lcd']:
                    problems.append('page flip %d disabled LCD across regional blank '
                                    'boundary' % index)
                if floor_expand and not 0x90 <= visible_blanked['ly'] <= 0x99:
                    problems.append('page flip %d Floor expansion ended outside VBlank '
                                    '(LY=$%02X)' %
                                    (index, visible_blanked['ly']))
                elif not floor_expand and visible_blanked['ly'] < 0x90:
                    problems.append('page flip %d published regional blank outside '
                                    'VBlank (LY=$%02X)' %
                                    (index, visible_blanked['ly']))
                if shadow_blanked['bg'] != origin['bg']:
                    problems.append('page flip %d changed visible BG before its '
                                    'regional VBlank publication' % index)
                if visible_blanked['shadow'] != shadow_blanked['shadow']:
                    problems.append('page flip %d changed shadow map while publishing '
                                    'the regional blank' % index)
                if floor_expand:
                    top = bytes((0xB8,)) + bytes((0xBC,)) * 18 + bytes((0xB9,))
                    side = bytes((0xBE,)) + bytes(18) + bytes((0xBF,))
                    bottom = bytes((0xBA,)) + bytes((0xBD,)) * 18 + bytes((0xBB,))
                    for label, after in (('shadow', shadow_blanked['shadow']),
                                         ('visible BG', visible_blanked['bg'])):
                        expected = {3: top, 13: bottom}
                        expected.update((row, side) for row in range(4, 13))
                        bad = next(((row, after[row * 32:row * 32 + 20], want)
                                    for row, want in sorted(expected.items())
                                    if after[row * 32:row * 32 + 20] != want), None)
                        if bad is not None:
                            row, actual, want = bad
                            problems.append('page flip %d Floor expansion %s row %d '
                                            'is %s, expected %s' %
                                            (index, label, row, actual.hex(' '),
                                             want.hex(' ')))
                else:
                    for label, before, after, plane in (
                            ('shadow', origin['shadow'], shadow_blanked['shadow'], 'shadow'),
                            ('visible BG', origin['bg'], visible_blanked['bg'], 'BG')):
                        retained = next((offset for offset in blank_targets
                                         if after[offset] != 0),
                                        None)
                        bad_border = next((offset for offset in borders
                                           if after[offset] != 0xBE), None)
                        changed = next((offset for offset in range(0x400)
                                        if offset not in region_targets and
                                        before[offset] != after[offset]), None)
                        if retained is not None:
                            problems.append('page flip %d left %s target +$%03X nonblank' %
                                            (index, label, retained))
                        if bad_border is not None:
                            problems.append('page flip %d left %s border +$%03X as $%02X, '
                                            'expected $BE' %
                                            (index, label, bad_border, after[bad_border]))
                        if changed is not None:
                            problems.append('page flip %d changed locked %s cell +$%03X '
                                            'during blank' % (index, plane, changed))
            for at, _image, memory in samples[:first_new + 1]:
                changed = locked_map_changes(old['bg'], memory['bg'], 'BG',
                                             floor_expand=floor_expand)
                if changed:
                    kind, row, col, before, after = changed[0]
                    problems.append('page flip %d changed locked %s cell (%d,%d) at '
                                    'f%d: $%02X->$%02X'
                                    % (index, kind, row, col, at, before, after))
                    break
                changed_tile = next((tile for tile in STRUCTURAL_TILES
                                     if tile_planes(memory, tile) != old_structural[tile]),
                                    None)
                if changed_tile is not None:
                    problems.append('page flip %d changed locked structural tile $%02X '
                                    'at f%d' % (index, changed_tile, at))
                    break
                if memory['window'] != old['window']:
                    problems.append('page flip %d changed Window enable state at f%d'
                                    % (index, at))
                    break
                if memory['state'] not in (0, 1):
                    problems.append('page flip %d entered transaction state %d at f%d'
                                    % (index, memory['state'], at))
                    break

            changes = []
            for observation in audit:
                if not changes or changes[-1][1] != observation[1]:
                    changes.append(observation)
            transition_traces.append((index, changes))

        if sort_snapshots and pages:
            occupied = [row for row in range(5)
                        if not visual_name_blank(pages[-1]['old_image'], row)]
            fully_blanked = next((at for at, image, _memory in sort_snapshots
                                  if occupied and
                                  all(visual_name_blank(image, row)
                                      for row in occupied)), None)
            sort_blank_frame[0] = fully_blanked
            if fully_blanked is None:
                problems.append('Start-sort never exposes the intended whole item-region '
                                'blank for visual review')

        indicator = bytes(pb.memory[PAGE_INDICATOR_AT:PAGE_INDICATOR_AT + 4])
        if indicator.count(0xC6) != 1 or any(tile not in PAGE_TILES for tile in indicator):
            problems.append('page indicator map is %s, expected one active $C6 and '
                            'three inactive $C5 cells' % indicator.hex(' '))
        for tile, want in PAGE_TILES.items():
            address = 0x8800 + 16 * (tile - 0x80)
            got = bytes(pb.memory[address:address + 16])
            if got != want:
                problems.append('page indicator tile $%02X is %s, expected solid-border %s'
                                % (tile, got.hex(' '), want.hex(' ')))

        pb.stop(save=False)

    print('itempagespill: dispatches %s' %
          ' '.join('f%d:%d' % event for event in dispatches))
    print('itempagespill: page draws %s' %
          ' '.join('f%d-%d' % (page['start'], page.get('complete', -1))
                   for page in pages))
    print('itempagespill: white-frame counts %s' %
          ' '.join(str(len(page['lcd_off_frames'])) for page in pages))
    print('itempagespill: scoped regional begins %d; fallbacks %d; LCD-off frames %d; '
          'pre-gate queue max $%02X; sort samples %d; regional blank %s' %
          (len(scoped_regional_begins), len(scoped_legacy_fallbacks),
           len(scoped_lcd_off), max((value for _at, value in pre_gate_queues), default=0),
           len(sort_snapshots),
           'missing' if sort_blank_frame[0] is None else 'f%d' % sort_blank_frame[0]))
    for index, trace in transition_traces:
        print('itempagespill: regional flip %d %s' %
              (index, ', '.join('f%d:%s' % observation for observation in trace)))
    print('itempagespill: direction presses %s; sort presses %s; '
          '%d unique complete page(s)' %
          (' '.join('f%d:%s' % event for event in page_presses),
           ' '.join('f%d:%s' % event for event in sort_presses), len(unique)))
    print('itempagespill: indicator %s; active/inactive tiles retain two-pixel border' %
          indicator.hex(' '))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('itempagespill: %d problem(s)' % len(problems))
    print('itempagespill: real multi-page route keeps each regional transaction owned')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3900)
    parser.add_argument('--settle-frames', type=int, default=90,
                        help='frames from row-4 completion to the next paging input')
    parser.add_argument('--no-wrap', action='store_true',
                        help='avoid the standing-Floor then page-1 two-input wrap')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('itempagespill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png_dir, args.frames, args.settle_frames,
        not args.no_wrap)


if __name__ == '__main__':
    main()
