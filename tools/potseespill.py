#!/usr/bin/env python3
"""Replay Floor -> See for empty Storage Pots in the Log-1 and Log-2 fixtures.

The pot-content viewer is a separate path from the translated item-help table.  This
fixture keeps its empty-row source and rendered VWF planes observable so untranslated
kana cannot silently reappear under the Latin font. The Log-2 route additionally proves
the compact Pot title's exact five-cell geometry after leaving the wider Floor header.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import codec                                                     # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import itemfix                                                   # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
import potreturnspill                                             # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_pot_see_action.srm')
STORAGE_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
LOG1_SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 420: ('a',), 480: ('a',),
    2620: ('b',), 2700: ('down',), 2780: ('a',),       # Menu -> Floor
    2860: ('down',), 3000: ('a',),                    # See
}
LOG2_SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 360: ('down',), 420: ('a',), 500: ('a',),
    2200: ('b',), 2280: ('down',), 2360: ('a',),       # Menu -> Floor
    2480: ('down',), 2600: ('a',),                    # See
}
FRAMES = 3400
CONTENT_SOURCE = 0xC616
TARGET = bytes(menuspill.encode(itemfix.EMPTY_POT_ROW))
POT_TARGET = bytes(menuspill.encode('Pot'))


def staged_row(pb, source, limit=48):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def run(rom, ram=RAM, png=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('potseespill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='potseespill-') as tmp:
        work = os.path.join(tmp, 'pot-see.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        calls = []
        content_calls = []
        title_calls = []
        page_blanks = []
        regional_fallbacks = []
        regional_blanks = []
        entry_samples = []
        pot_entry_lifecycle = []

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_context=None):
            # Log 2 reaches See earlier than the original Log-1 fixture.
            if frame[0] < 2500:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            call = (frame[0], pb.register_file.D, pb.register_file.HL,
                    shape, source, staged_row(pb, source))
            calls.append(call)
            # Pot capacity changes the body height, but its first content row always
            # begins at y=3 and spans the same 18-cell interior.
            if (shape[0], shape[1], shape[3]) == (0, 3, 18) and pb.register_file.D == 0:
                content_calls.append(call)
            if shape == (0, 0, 1, 3, 0x40) and pb.register_file.D == 0:
                title_calls.append(call)

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        page_labels, region_labels = menuvwf.item_transition_labels()
        pb.hook_register(
            menuvwf.ITEM_PAGE_BANK, page_labels['pbdisable'],
            lambda _ctx=None: page_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6])), None)
        pb.hook_register(
            menuvwf.ITEM_REGION_BANK, region_labels['irfaillcd'],
            lambda _ctx=None: regional_fallbacks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6])), None)
        pb.hook_register(
            menuvwf.ITEM_REGION_BANK, region_labels['irdisable'],
            lambda _ctx=None: regional_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6])), None)
        info_labels = menuvwf.info_lifecycle_labels()
        for label in ('potentrychrome', 'potentrypublish', 'potentrypublished'):
            pb.hook_register(
                menuvwf.ACTION_BLANK_BANK, info_labels[label],
                lambda _ctx=None, name=label: pot_entry_lifecycle.append((
                    frame[0], name, pb.memory[0xC6A3], pb.memory[0xC1B3],
                    pb.memory[0xC1B6], pb.memory[0xC6BB])), None)
        script = LOG2_SCRIPT if os.path.basename(ram) == os.path.basename(STORAGE_RAM) else LOG1_SCRIPT
        for frame[0] in range(FRAMES):
            for button in script.get(frame[0], ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame[0] >= 2500 and pb.memory[0xC6A3] in (12, 13):
                entry_samples.append((
                    frame[0], bytes(pb.memory[0x9800:0x9C00]),
                    bool(pb.memory[0xFF40] & 0x80), pb.memory[0xC6A3],
                    pb.memory[0xC1B3], pb.memory[0xC1B6],
                    pb.memory[0xC6BB], pb.screen.image.copy()))

        final = pb.screen.image.copy()
        if png:
            final.save(png)
            print('potseespill: wrote %s' % png)
        if not content_calls:
            problems.append('See never composed its empty content row')
        else:
            at, _rownum, key, _shape, source, row = content_calls[-1]
            want = bytes((0, 0)) + TARGET
            if source != CONTENT_SOURCE:
                problems.append('empty row source is $%04X, expected $%04X'
                                % (source, CONTENT_SOURCE))
            if row != want:
                problems.append('empty row at f%d is %s, expected %s'
                                % (at, row.hex(' '), want.hex(' ')))
            elif not menuspill.visible_row_matches(pb, profile, key, TARGET, raw=2):
                problems.append('visible empty row is not plane-exact centered `%s`'
                                % itemfix.EMPTY_POT_TEXT)
        if trace:
            for at, rownum, key, shape, source, row in calls:
                print('  f%d d%d key=$%04X shape=%s src=$%04X row=%s jp=%r'
                      % (at, rownum, key, shape, source, row.hex(' '),
                         codec.decode(row)))

        # Pot is box 17: x=0, y=0, one text row, three interior cells. The preceding
        # Floor header is much wider, so its row-2 bottom edge must be fully erased
        # outside the compact five-cell title box.
        tilemap = bytes(pb.memory[0x9800:0x9A40])
        top = bytes((0xB8, 0xBC, 0xBC, 0xBC, 0xB9))
        bottom = bytes((0xBA, 0xBD, 0xBD, 0xBD, 0xBB))
        row0 = tilemap[0:20]
        row1 = tilemap[32:52]
        row2 = tilemap[64:84]
        if row0[:5] != top or any(row0[5:]):
            problems.append('Pot title top/tail is %s' % row0.hex(' '))
        if row1[0] != 0xBE or row1[4] != 0xBF or any(row1[5:]):
            problems.append('Pot title text/tail is %s' % row1.hex(' '))
        if row2[:5] != bottom or any(row2[5:]):
            problems.append('Pot title bottom/tail is %s' % row2.hex(' '))
        if not title_calls:
            problems.append('Pot title never reached the proportional row renderer')
        else:
            key = title_calls[-1][2]
            expected_tiles = menuspill.compose(POT_TARGET, profile)
            for index, expected_pixels in enumerate(expected_tiles):
                tile = row1[1 + index]
                tile_at = menuspill.tile_data_addr(tile)
                if bytes(pb.memory[tile_at:tile_at + 16]) != bytes(expected_pixels):
                    problems.append('Pot title tile %d pixels differ' % index)
            if any(row1[1 + len(expected_tiles):4]):
                problems.append('Pot title retains cells after proportional `Pot`: %s'
                                % row1.hex(' '))
        if trace:
            print('  title row=%s records=%s'
                  % (row1.hex(' '), menuspill.records(pb, profile)))
        pb.stop(save=False)

    indices = [index for _at, index in dispatches]
    if 20 not in indices:
        problems.append('real route never dispatched Floor screen 20')
    if 13 not in indices:
        problems.append('real route never dispatched Pot See screen 13')
    if not calls:
        problems.append('See never entered the proportional row renderer')
    expected_page_blanks = ()
    if tuple(event[1:] for event in page_blanks) != expected_page_blanks:
        problems.append('Pot See Item-page blank states are %s, expected %s' %
                        (tuple(event[1:] for event in page_blanks),
                         expected_page_blanks))
    if regional_blanks:
        problems.append('Pot See wrote the regional LCD-off site at %s' %
                        (regional_blanks,))
    entry_off = [sample[0] for sample in entry_samples if not sample[2]]
    if entry_off:
        problems.append('Floor -> Pot See disabled the LCD on frame(s) %s' %
                        entry_off[:16])
    viewer_samples = [sample for sample in entry_samples if 1 <= sample[6] <= 5]
    chrome_frames = [sample[0] for sample in viewer_samples
                     if potreturnspill.pot_chrome_complete(sample[1], sample[6])]
    settled_title = (potreturnspill.pot_title_pixels(viewer_samples[-1][7])
                     if viewer_samples else None)
    text_frames = [sample[0] for sample in viewer_samples
                   if settled_title is not None and
                   potreturnspill.pot_title_pixels(sample[7]) == settled_title]
    if not chrome_frames:
        problems.append('Floor -> Pot See never exposed complete Pot chrome')
    elif not text_frames or not potreturnspill.pot_text_visible(
            viewer_samples[-1][7]):
        problems.append('Floor -> Pot See never exposed Pot title/body text')
    elif chrome_frames[0] >= text_frames[0]:
        problems.append('Pot text first appears at f%d without earlier empty chrome '
                        '(first chrome f%d)' %
                        (text_frames[0], chrome_frames[0]))
    lifecycle = tuple(label for _at, label, screen, _state, _phase, _rows
                      in pot_entry_lifecycle if screen in (12, 13))
    if (lifecycle.count('potentrychrome') != 1 or
            lifecycle.count('potentrypublished') != 1 or
            not lifecycle or lifecycle[-1] != 'potentrypublished' or
            len(lifecycle) < 3 or lifecycle[-2] != 'potentrypublish'):
        problems.append('Floor -> Pot entry lifecycle order is %s' % (lifecycle,))
    if trace:
        print('  Pot entry lifecycle %s; first chrome/text %s/%s' %
              (pot_entry_lifecycle,
               chrome_frames[0] if chrome_frames else None,
               text_frames[0] if text_frames else None))
    print('potseespill: dispatches %s; %d See-era row call(s); Item-page blank %s; '
          'regional branch/write %s/%s; empty chrome/text %s/%s; compact title exact; '
          '%d problem(s)'
          % (' '.join('f%d:%d' % event for event in dispatches), len(calls),
             page_blanks, regional_fallbacks, regional_blanks,
             chrome_frames[0] if chrome_frames else None,
             text_frames[0] if text_frames else None, len(problems)))
    for problem in problems:
        print('  ' + problem)
    if not problems:
        print('potseespill: shared empty-Pot viewer is plane-exact `%s`'
              % itemfix.EMPTY_POT_TEXT)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('potseespill: missing %s' % path)
    return run(args.rom, args.ram, args.png, args.trace)


if __name__ == '__main__':
    raise SystemExit(main())
