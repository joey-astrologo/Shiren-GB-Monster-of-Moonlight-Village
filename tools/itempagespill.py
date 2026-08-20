#!/usr/bin/env python3
"""Replay the multi-page item-menu transition from cartridge RAM.

``saves/shiren_en_item_menu.srm`` contains one populated log with enough inventory for
four or five pages.  This route boots that log normally, opens Menu -> Items, then pages
right and left through the real input handler.  It records every item-row draw and can
write every rendered frame around a page transition for visual/timing diagnosis.

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


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(row)
        row.append(value)
    return tuple(row)


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

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))
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
                    'old_image': pb.screen.image.copy(), 'frames': [],
                    'lcd_off_frames': [], 'cursor_seen': False,
                }
                pages.append(current[0])
                capture_until[0] = max(capture_until[0], frame[0] + 70)
            if current[0] is None:
                return
            current[0]['rows'][rownum] = row
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

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)

        for current_frame in range(frames):
            frame[0] = current_frame
            button = scheduled.get(current_frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if pages and current_frame <= capture_until[0]:
                transition = len(pages) - 1
                snapshot = pb.screen.image.copy()
                pages[-1]['frames'].append((current_frame, snapshot))
                if not pb.memory[0xFF40] & 0x80:
                    pages[-1]['lcd_off_frames'].append(current_frame)
                # Item row 0 begins at shadow $C380: border, equipped-marker cell,
                # then the native cursor cell. Left/Right paging keeps selection at 0.
                if pb.memory[0xFF40] & 0x80 and pb.memory[0xC382] == 0x81:
                    pages[-1]['cursor_seen'] = True
                key = (transition, current_frame)
                if png_dir and key not in captured:
                    captured.add(key)
                    snapshot.save(os.path.join(
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

        def visual_key(image):
            """Text-transition pixels, excluding animated sprites and the static HUD."""
            rgb = image.convert('RGB')
            # Item names cross the playfield, but the underlying Shiren sprite is the
            # only independently animated object in the menu rectangle.  Mask just its
            # measured centre region; all five left/right name extents remain covered.
            rgb.paste((0, 0, 0), (64, 40, 112, 104))
            rgb.paste((0, 0, 0), (0, 128, 160, 144))
            # The native cursor and page-arrow writers run after the item/header box
            # renderer.  Their appearance is not a text transition and must not make a
            # fully composed page look partial. These are their measured tile cells.
            rgb.paste((0, 0, 0), (16, 32, 24, 40))
            rgb.paste((0, 0, 0), (120, 24, 152, 32))
            return rgb.tobytes()

        for index, page in enumerate(pages):
            samples = page['frames']
            if not samples:
                problems.append('transition %d has no rendered-frame samples' % index)
                continue
            if not page['lcd_off_frames']:
                problems.append('transition %d never enters the white LCD-off state'
                                % index)
            if not page['cursor_seen']:
                problems.append('transition %d never restores the row-0 cursor at $C382'
                                % index)
            old = visual_key(page['old_image'])
            new = visual_key(samples[-1][1])
            first_new = next((i for i, (_at, image) in enumerate(samples)
                              if visual_key(image) == new), None)
            if first_new is None:
                problems.append('transition %d never reaches its settled image' % index)
                continue
            bad = []
            for at, image in samples[:first_new + 1]:
                key = visual_key(image)
                colours = set(image.convert('RGB').getdata())
                if key not in (old, new) and len(colours) != 1:
                    bad.append(at)
            if bad:
                problems.append('transition %d has blended/partial text frame(s) %s; '
                                'expected only old, blank-LCD, or complete new screen'
                                % (index, ' '.join('f%d' % at for at in bad[:12])))

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
    print('itempagespill: direction presses %s; %d unique complete page(s)' %
          (' '.join('f%d:%s' % event for event in page_presses), len(unique)))
    print('itempagespill: indicator %s; active/inactive tiles retain two-pixel border' %
          indicator.hex(' '))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('itempagespill: %d problem(s)' % len(problems))
    print('itempagespill: real multi-page item route has atomic text transitions')


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
