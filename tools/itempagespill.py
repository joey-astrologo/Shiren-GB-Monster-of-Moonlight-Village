#!/usr/bin/env python3
"""Replay the multi-page item-menu transition from cartridge RAM.

``saves/shiren_en_item_menu.srm`` contains one populated log with enough inventory for
four or five pages.  This route boots that log normally, opens Menu -> Items, pages
right and left, returns to Main, then re-enters Items through the real input handlers.
It records every item-row draw and can write every rendered frame around a page
transition for visual/timing diagnosis.

The untouched Japanese game keeps the LCD enabled and publishes complete rows in a few
progressive steps.  English may use a different buffering layout, but it must preserve
that visible contract: every item-name row is either the complete outgoing row or the
complete incoming row.  An old/new row mixture is therefore legal; a white LCD-off
frame or a row whose glyph pixels match neither endpoint is not.

The older ``menuspill --ram`` fixture has three logs and uses fixed title-menu timings.
Those timings do not select the one-log V4F fixture, so this route deliberately owns the
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
from floorinfospill import (                                      # noqa: E402
    row_backtracks as full_row_backtracks,
    row_states as full_row_states,
    visual_rows,
)


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ITEM_TEXT_ROWS = (4, 6, 8, 10, 12)
ITEM_TRANSIENT_RUN = (0x25, 0x30)
ITEM_HIGH_OWNERS = tuple(sorted(menuvwf.ITEM_HIGH_SLICES))


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(row)
        row.append(value)
    return tuple(row)


def item_row_keys(image):
    """Rendered name-cell pixels for the five item rows.

    Compare the framebuffer, not post-frame VRAM: that catches a glyph plane being
    replaced while the outgoing tilemap still names it.  The crop is the full 15-cell
    text region (after the marker and cursor cells), so no glyph tile is exempted.
    """
    rgb = image.convert('RGB')
    return tuple(rgb.crop((24, row * 8, 144, row * 8 + 8)).tobytes()
                 for row in ITEM_TEXT_ROWS)


def row_states(image, old_rows, new_rows):
    states = []
    for got, old, new in zip(item_row_keys(image), old_rows, new_rows):
        if got == old == new:
            states.append('=')
        elif got == old:
            states.append('O')
        elif got == new:
            states.append('N')
        else:
            states.append('X')
    return ''.join(states)


def row_backtracks(observations):
    """Rows which returned to the old raster after first showing the new raster."""
    seen_new = set()
    backtracks = []
    for at, states in observations:
        for row, state in enumerate(states):
            if state == 'N':
                seen_new.add(row)
            elif state == 'O' and row in seen_new:
                backtracks.append((at, row))
    return backtracks


def run(rom_path, ram_path, png_dir=None, frames=3900):
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
        capture_until = [-1]
        captured = set()
        main_item_press = [None]
        main_before = [None]
        pre_item_frames = []
        pre_item_lcd_off = []
        return_press = [None]
        return_before = [None]
        return_frames = []
        return_lcd_off = []
        reentry_press = [None]
        reentry_before = [None]
        reentry_frames = []
        reentry_lcd_off = []

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))
            # Screen 0 is the in-dungeon main menu.  Select its default Items entry only
            # after this save has actually reached it; fixed post-boot timing is brittle.
            if (pb.register_file.A == 0 and main_item_press[0] is None and
                    not any(button == 'a' for at, button in scheduled.items()
                            if at > frame[0])):
                at = frame[0] + 80
                scheduled[at] = 'a'
                main_item_press[0] = at
            elif (pb.register_file.A == 0 and return_press[0] is not None and
                  frame[0] >= return_press[0] and reentry_press[0] is None):
                # Re-enter after the page-rotated Items -> Main leg.  A persistent
                # allocator must avoid the exact high slice now owned by Main, not
                # assume the same initial layout a second time.
                at = frame[0] + 80
                scheduled[at] = 'a'
                reentry_press[0] = at

        def far_entry(_ctx=None):
            if pb.register_file.A == 0xFD and pb.register_file.D & 0x80:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE:
                return
            rownum = pb.register_file.D
            if not 0 <= rownum < 5:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if rownum == 0:
                opening = not pages and main_before[0] is not None
                reopening = (reentry_before[0] is not None and
                             reentry_press[0] is not None and
                             frame[0] >= reentry_press[0])
                current[0] = {
                    'start': frame[0], 'rows': {}, 'keys': {},
                    'old_image': (main_before[0] if opening else
                                  reentry_before[0] if reopening else
                                  pb.screen.image.copy()),
                    'frames': (list(pre_item_frames) if opening else
                               list(reentry_frames) if reopening else []),
                    'lcd_off_frames': (list(pre_item_lcd_off) if opening else
                                       list(reentry_lcd_off) if reopening else []),
                    'cursor_seen': False,
                    'full_lifecycle': opening or reopening,
                }
                pages.append(current[0])
                capture_until[0] = max(capture_until[0], frame[0] + 70)
            if current[0] is None:
                return
            current[0]['rows'][rownum] = row
            current[0]['keys'][rownum] = pb.register_file.HL
            if rownum == 4:
                current[0]['complete'] = frame[0]
                # Walk four pages to the right, then one page left.  Schedule relative
                # to the real row-4 completion so renderer timing changes cannot swallow
                # a press or accidentally overlap a draw.
                if len(page_presses) < 3:
                    button = 'right'
                elif len(page_presses) == 3:
                    button = 'left'
                elif len(page_presses) == 4:
                    button = 'right'
                else:
                    button = None
                if button is not None:
                    at = frame[0] + 90
                    scheduled[at] = button
                    page_presses.append((at, button))
                elif return_press[0] is None:
                    # Leave the final settled page through the native B handler so
                    # Items -> Main receives the same full-screen lifecycle oracle as
                    # the opening Main -> Items transition.
                    at = frame[0] + 90
                    scheduled[at] = 'b'
                    return_press[0] = at

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)

        for current_frame in range(frames):
            frame[0] = current_frame
            button = scheduled.get(current_frame)
            if current_frame == main_item_press[0]:
                # Capture the actual settled Main endpoint before its confirming A
                # press.  The first proportional row hook is a couple of frames later;
                # retaining this prefix prevents corruption before that hook from
                # escaping the lifecycle oracle.
                main_before[0] = pb.screen.image.copy()
            if current_frame == return_press[0]:
                return_before[0] = pb.screen.image.copy()
            if current_frame == reentry_press[0]:
                reentry_before[0] = pb.screen.image.copy()
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if main_before[0] is not None and not pages:
                snapshot = pb.screen.image.copy()
                pre_item_frames.append((current_frame, snapshot))
                if not pb.memory[0xFF40] & 0x80:
                    pre_item_lcd_off.append(current_frame)
            if pages and current_frame <= capture_until[0]:
                transition = len(pages) - 1
                snapshot = pb.screen.image.copy()
                pages[-1]['frames'].append((current_frame, snapshot))
                if not pb.memory[0xFF40] & 0x80:
                    pages[-1]['lcd_off_frames'].append(current_frame)
                lo, hi = ITEM_TRANSIENT_RUN
                live_records = menuspill.records(pb, profile)
                pages[-1]['settled_transient_refs'] = [
                    (row, col, pb.memory[0x9800 + 32 * row + col])
                    for row in range(18) for col in range(20)
                    if lo <= pb.memory[0x9800 + 32 * row + col] < hi]
                pages[-1]['settled_transient_records'] = [
                    record for record in live_records
                    if record[1] < hi and record[1] + record[2] > lo]
                pages[-1]['settled_records'] = live_records
                pages[-1]['settled_state'] = pb.memory[menuvwf.ITEM_STATE_AT]
                pages[-1]['settled_low_row'] = pb.memory[menuvwf.ITEM_LOW_ROW_AT]
                pages[-1]['settled_owners'] = tuple(
                    pb.memory[address]
                    for address in range(menuvwf.ITEM_ROWS_AT,
                                         menuvwf.ITEM_FREE_AT + 1))
                # Item row 0 begins at shadow $C380: border, equipped-marker cell,
                # then the native cursor cell. Left/Right paging keeps selection at 0.
                if pb.memory[0xFF40] & 0x80 and pb.memory[0xC382] == 0x81:
                    pages[-1]['cursor_seen'] = True
                key = (transition, current_frame)
                if png_dir and key not in captured:
                    captured.add(key)
                    snapshot.save(os.path.join(
                        png_dir, 'transition%02d_f%04d.png' % key))
            if (return_before[0] is not None and
                    current_frame <= return_press[0] + 70):
                snapshot = pb.screen.image.copy()
                return_frames.append((current_frame, snapshot))
                if not pb.memory[0xFF40] & 0x80:
                    return_lcd_off.append(current_frame)
            if (reentry_before[0] is not None and
                    current_frame <= reentry_press[0] + 70):
                snapshot = pb.screen.image.copy()
                reentry_frames.append((current_frame, snapshot))
                if not pb.memory[0xFF40] & 0x80:
                    reentry_lcd_off.append(current_frame)

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
        if (return_press[0] is None or
                not any(at >= return_press[0] and index == 0
                        for at, index in dispatches)):
            problems.append('Items -> Main B route never dispatched native screen 0')
        if (reentry_press[0] is None or
                not any(at >= reentry_press[0] and index == 1
                        for at, index in dispatches)):
            problems.append('second Main -> Items route never dispatched native screen 1')

        for index, page in enumerate(pages):
            samples = page['frames']
            if not samples:
                problems.append('transition %d has no rendered-frame samples' % index)
                continue
            if page['lcd_off_frames']:
                problems.append('transition %d disables the LCD at %s'
                                % (index, ' '.join('f%d' % at
                                                   for at in page['lcd_off_frames'][:12])))
            if not page['cursor_seen']:
                problems.append('transition %d never restores the row-0 cursor at $C382'
                                % index)
            state = page.get('settled_state')
            if state != menuvwf.ITEM_STATE_SETTLED:
                problems.append('transition %d settles with Item lifecycle $%02X, expected $%02X'
                                % (index, state if state is not None else 0xFF,
                                   menuvwf.ITEM_STATE_SETTLED))
            low_row = page.get('settled_low_row')
            if low_row != 0xFF:
                problems.append('transition %d leaves transient-row owner $%02X, expected $FF'
                                % (index, low_row if low_row is not None else 0x00))
            owners = page.get('settled_owners', ())
            if tuple(sorted(owners)) != ITEM_HIGH_OWNERS:
                problems.append('transition %d settles with Item owners %s, expected permutation %s'
                                % (index,
                                   '/'.join('$%02X' % owner for owner in owners) or 'missing',
                                   '/'.join('$%02X' % owner for owner in ITEM_HIGH_OWNERS)))
            refs = page.get('settled_transient_refs', ())
            if refs:
                problems.append(
                    'transition %d leaves transient $25-$2F visible at %s'
                    % (index, ' '.join('r%d,c%d=$%02X' % ref for ref in refs[:12])))
            records = page.get('settled_transient_records', ())
            if records:
                problems.append(
                    'transition %d leaves transient $25-$2F allocator record(s) %s'
                    % (index, ' '.join('$%04X:$%02X+%d' % record[:3]
                                       for record in records)))
            settled_records = page.get('settled_records', ())
            for rownum, staged in sorted(page['rows'].items()):
                codes = staged[2:]
                # Empty native fallback rows expose an unterminated all-zero staging
                # tail. They reserve an owner but paint no proportional glyph record.
                if not any(codes):
                    continue
                key = page['keys'].get(rownum)
                owner = owners[rownum] if len(owners) == 6 else None
                expected = (key, owner, menuvwf.ITEM_ROW_TILES, 2)
                if expected not in settled_records:
                    problems.append(
                        'transition %d painted row %d has no settled record '
                        '$%04X:$%02X+%d raw2; staged %s (records %s)'
                        % (index, rownum, key if key is not None else 0,
                           owner if owner is not None else 0,
                           menuvwf.ITEM_ROW_TILES,
                           ' '.join('$%02X' % code for code in staged),
                           ' '.join('$%04X:$%02X+%d/r%d' % record
                                    for record in settled_records) or 'none'))
            old_rows = item_row_keys(page['old_image'])
            new_rows = item_row_keys(samples[-1][1])
            if old_rows == new_rows:
                problems.append('transition %d produced no rendered item-row change' % index)
            observations = []
            for at, image in samples:
                states = row_states(image, old_rows, new_rows)
                if not observations or observations[-1][1] != states:
                    observations.append((at, states))
            page['row_states'] = observations
            first_new = next((i for i, (_at, image) in enumerate(samples)
                              if all(state in '=N' for state in
                                     row_states(image, old_rows, new_rows))), None)
            if first_new is None:
                problems.append('transition %d never reaches its five settled rows'
                                % index)
            bad = [(at, states) for at, states in observations if 'X' in states]
            if bad:
                problems.append('transition %d exposes blended/incomplete item row(s) %s'
                                % (index, ' '.join('f%d:%s' % event
                                                   for event in bad[:12])))
            backtracks = row_backtracks(observations)
            if backtracks:
                problems.append('transition %d returns published row(s) to old pixels %s'
                                % (index, ' '.join('f%d:r%d' % event
                                                   for event in backtracks[:12])))

            # Transition 0 is Main -> Items.  Its outgoing VWF labels occupy rows
            # outside the five item-name crops, so a rolling slice can corrupt them
            # while every item crop still looks valid.  Compare all 18 rendered rows
            # for this lifecycle boundary.  Page flips retain the narrower oracle
            # because their native cursor/pager writers update independently.
            if page.get('full_lifecycle'):
                full_old = visual_rows(page['old_image'])
                full_new = visual_rows(samples[-1][1])
                if full_old == full_new:
                    problems.append('Main -> Items transition %d produced no rendered '
                                    'screen change' % index)
                full_observations = []
                for at, image in samples:
                    states = full_row_states(image, full_old, full_new)
                    if (not full_observations or
                            full_observations[-1][1] != states):
                        full_observations.append((at, states))
                page['full_row_states'] = full_observations
                full_first_new = next(
                    (i for i, (_at, image) in enumerate(samples)
                     if all(state in '=N' for state in
                            full_row_states(image, full_old, full_new))), None)
                if full_first_new is None:
                    problems.append('Main -> Items transition %d never reaches its 18 '
                                    'settled rows' % index)
                bad = [(at, states) for at, states in full_observations
                       if 'X' in states]
                if bad:
                    problems.append(
                        'Main -> Items transition %d exposes blended/incomplete '
                        'screen row(s) %s'
                        % (index, ' '.join('f%d:%s' % event
                                           for event in bad[:12])))
                backtracks = full_row_backtracks(full_observations)
                if backtracks:
                    problems.append(
                        'Main -> Items transition %d returns published screen row(s) '
                        'to old pixels %s'
                        % (index, ' '.join('f%d:r%d' % event
                                           for event in backtracks[:12])))

        return_states = []
        if return_before[0] is None or not return_frames:
            problems.append('Items -> Main has no rendered-frame samples')
        else:
            if return_lcd_off:
                problems.append('Items -> Main disables the LCD at %s'
                                % ' '.join('f%d' % at for at in return_lcd_off[:12]))
            old = visual_rows(return_before[0])
            new = visual_rows(return_frames[-1][1])
            if old == new:
                problems.append('Items -> Main produced no rendered change')
            for at, image in return_frames:
                states = full_row_states(image, old, new)
                if not return_states or return_states[-1][1] != states:
                    return_states.append((at, states))
            first_new = next(
                (i for i, (_at, image) in enumerate(return_frames)
                 if all(state in '=N' for state in
                        full_row_states(image, old, new))), None)
            if first_new is None:
                problems.append('Items -> Main never reaches its 18 settled rows')
            bad = [(at, states) for at, states in return_states
                   if 'X' in states]
            if bad:
                problems.append(
                    'Items -> Main exposes blended/incomplete screen row(s) %s'
                    % ' '.join('f%d:%s' % event for event in bad[:12]))
            backtracks = full_row_backtracks(return_states)
            if backtracks:
                problems.append(
                    'Items -> Main returns published screen row(s) to old pixels %s'
                    % ' '.join('f%d:r%d' % event
                               for event in backtracks[:12]))

        pb.stop(save=False)

    print('itempagespill: dispatches %s' %
          ' '.join('f%d:%d' % event for event in dispatches))
    print('itempagespill: page draws %s' %
          ' '.join('f%d-%d' % (page['start'], page.get('complete', -1))
                   for page in pages))
    print('itempagespill: LCD-off frame counts %s' %
          ' '.join(str(len(page['lcd_off_frames'])) for page in pages))
    print('itempagespill: settled transient $25-$2F refs/records %s' % ' '.join(
          '%d/%d' % (len(page.get('settled_transient_refs', ())),
                     len(page.get('settled_transient_records', ())))
          for page in pages))
    print('itempagespill: rendered row states %s' % ' | '.join(
          ' '.join('f%d:%s' % event for event in page.get('row_states', ()))
          for page in pages))
    print('itempagespill: Main -> Items full-screen row states %s' % ' | '.join(
          't%d %s' % (index, ' '.join('f%d:%s' % event
                                      for event in page.get('full_row_states', ())))
          for index, page in enumerate(pages) if page.get('full_lifecycle')))
    print('itempagespill: Items -> Main full-screen row states %s' %
          ' '.join('f%d:%s' % event for event in return_states))
    print('itempagespill: direction presses %s; %d unique complete page(s)' %
          (' '.join('f%d:%s' % event for event in page_presses), len(unique)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('itempagespill: %d problem(s)' % len(problems))
    print('itempagespill: LCD-on item transitions contain only complete old/new rows')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3900)
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('itempagespill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png_dir, args.frames)


if __name__ == '__main__':
    main()
