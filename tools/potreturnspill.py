#!/usr/bin/env python3
"""Verify carried-Pot See entry and return publish windows before text.

The Log-2 action-pot fixture opens a real screen-12 Back Pot. ``--full-page`` uses the
four-page Dragon's Maw inventory and opens its screen-13 hidden Pot. ``--exact-five``
installs the reported Egg/Egg/Happy Bracer/Fusion Pot/Manji Kabura inventory, whose
screen-12 producer legitimately leaves the private-Action admission latch at zero. All
three routes select See and leave the contents viewer with B. Entry must retire the
Items/Action region, publish empty Pot title/body chrome, and only then expose Pot text.
Once the screen-1 replay begins, no cell from the final Items rows may become visible
until the complete title and body box perimeters are already present. The title must
remain either wholly absent or match its pre-Pot `Items` parent exactly, and the LCD must
remain enabled throughout both directions.
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
import menuvwf                                                    # noqa: E402
import statusvwf                                                  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_2_action_pots.srm')
FULL_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_dragons_maw.srm')
INVENTORY = 0xA3B0
OBJECTS = 0xA406
ACTION_POT_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 480: 'a',       # Adventure -> Log 2
    2620: 'b', 2740: 'a',                            # Menu -> Items
    3000: 'down', 3200: 'a', 3400: 'a',              # Back Pot -> See
    3800: 'b',                                       # See -> Items
}
FULL_PAGE_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',                    # Adventure -> Log 1
    2620: 'b', 2720: 'a',                            # Menu -> Items
    2820: 'right', 2900: 'right', 2980: 'right',     # full page 4
    3300: 'a', 3400: 'a',                            # hidden Pot -> See
    3800: 'b',                                       # See -> Items
}
EXACT_FIVE_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',                    # Adventure -> Log 1
    2620: 'b', 2720: 'a',                            # Menu -> Items
    2820: 'down', 2880: 'down', 2940: 'down',        # Fusion Pot in row 4
    3100: 'a', 3300: 'a',                            # Action -> See
    3700: 'b',                                       # See -> Items
}
RETURN_AT = 3800
FRAMES = 4300


def chrome_complete(bg):
    """Exact screen-1 Items title/body perimeter in the visible BG map."""
    title_top = bytes((0xB8,) + (0xBC,) * 4 + (0xB9,))
    title_bottom = bytes((0xBA,) + (0xBD,) * 4 + (0xBB,))
    body_bottom = bytes((0xBA,) + (0xBD,) * 18 + (0xBB,))
    if bg[0:6] != title_top:
        return False
    if bg[32] != 0xBE or bg[37] != 0xBF:
        return False
    if bg[64:70] != title_bottom:
        return False
    top = bg[3 * 32:3 * 32 + 20]
    if (top[0] != 0xB8 or top[19] != 0xB9 or
            top[1:15] != bytes((0xBC,) * 14) or
            any(cell not in (0xBC, 0xC5, 0xC6) for cell in top[15:19])):
        return False
    for row in range(4, 13):
        # Equipped rows replace the ordinary left side with the native marker-coupled
        # $83/$85 border; it is complete chrome, not a missing side.
        if (bg[row * 32] not in (0xBE, 0x83, 0x85) or
                bg[row * 32 + 19] != 0xBF):
            return False
    return bg[13 * 32:13 * 32 + 20] == body_bottom


def item_cells(bg):
    """The five visible item-name interiors, excluding marker/cursor columns."""
    return tuple(bg[(4 + 2 * row) * 32 + 3:(4 + 2 * row) * 32 + 19]
                 for row in range(5))


def pot_chrome_complete(bg, rows):
    """Exact compact-title plus capacity-sized Pot body perimeter."""
    if not 1 <= rows <= 5:
        return False
    title_top = bytes((0xB8,) + (0xBC,) * 3 + (0xB9,))
    title_bottom = bytes((0xBA,) + (0xBD,) * 3 + (0xBB,))
    body_top = bytes((0xB8,) + (0xBC,) * 18 + (0xB9,))
    body_bottom = bytes((0xBA,) + (0xBD,) * 18 + (0xBB,))
    if bg[0:5] != title_top or any(bg[5:20]):
        return False
    if bg[32] != 0xBE or bg[36] != 0xBF or any(bg[37:52]):
        return False
    if bg[64:69] != title_bottom or any(bg[69:84]):
        return False
    if bg[3 * 32:3 * 32 + 20] != body_top:
        return False
    for row in range(4, 4 + rows):
        if bg[row * 32] != 0xBE or bg[row * 32 + 19] != 0xBF:
            return False
    return bg[(4 + rows) * 32:(4 + rows) * 32 + 20] == body_bottom


def pot_title_pixels(image):
    """Resolved `Pot` title interior, excluding chrome and the sprite-only right edge."""
    return image.convert('RGB').crop((8, 8, 32, 16)).tobytes()


def pot_text_visible(image):
    """Whether the compact-title interior contains visible ink."""
    pixels = image.convert('RGB').crop((8, 8, 32, 16)).getdata()
    return len(set(pixels)) > 1


def visual_item_rows(image):
    """Stable left-hand name pixels, away from the roaming dungeon sprite."""
    return tuple(image.crop((24, (4 + 2 * row) * 8,
                              64, (4 + 2 * row) * 8 + 8))
                 .convert('RGB').tobytes() for row in range(5))


def resolved_region(bg, tiles, rows, cols):
    """Resolved tile pixels, so equivalent dynamic IDs compare equal."""
    out = []
    for row in rows:
        for col in cols:
            tile = bg[row * 32 + col]
            start = (0x800 + tile * 16 if tile < 0x80 else
                     (tile - 0x80) * 16)
            out.append(tiles[start:start + 16])
    return tuple(out)


def run(rom, ram=RAM, png_dir=None, trace=False, exact_five=False):
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='potreturnspill-') as tmp:
        work = os.path.join(tmp, 'pot-return.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        script = (EXACT_FIVE_SCRIPT if exact_five else
                  (FULL_PAGE_SCRIPT if os.path.basename(ram) ==
                   os.path.basename(FULL_RAM) else ACTION_POT_SCRIPT))
        return_at = 3700 if exact_five else RETURN_AT
        dispatches = []
        samples = []
        entry_samples = []
        entry_attempts = []
        pop_attempts = []
        parent_title = [None]
        injected = [not exact_five]
        page_blanks = []
        page_blank_details = []
        pot_entry_attempts = []
        pot_entry_lifecycle = []
        regional_fallbacks = []
        regional_blanks = []
        status_blanks = []

        def inject_exact_five(_context=None):
            if injected[0]:
                return
            indices = [pb.memory[INVENTORY + slot] for slot in range(5)]
            if any(index == 0xFF for index in indices) or len(set(indices)) != 5:
                return
            records = (
                (0x3B, 0, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Egg
                (0x3B, 0, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Egg
                (0x2D, 3, 0, 0x84, 0, 0, 0xFF, 0xFF),  # Happy Bracer
                (0x87, 2, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Fusion Pot[2]
                (0x06, 1, 0, 0xC4, 4, 0, 0xFF, 0xFF),  # Manji Kabura+1/seal
            )
            for index, record in zip(indices, records):
                for offset, value in enumerate(record):
                    pb.memory[OBJECTS + 8 * index + offset] = value
            pb.memory[INVENTORY + 5] = 0xFF
            injected[0] = True

        def dispatch(_context=None):
            depth = pb.memory[0xC534]
            dispatches.append((frame[0], pb.register_file.A,
                               tuple(pb.memory[0xC535 + index]
                                     for index in range(depth + 1)),
                               pb.memory[0xC1B3]))
            if pb.register_file.A == 2 and parent_title[0] is None:
                parent_title[0] = (
                    bytes(pb.memory[0x9800:0x9C00]),
                    bytes(pb.memory[0x8800:0x9800]))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(6, 0x4B29, inject_exact_five, None)
        page_labels, region_labels = menuvwf.item_transition_labels()
        def page_blank(_ctx=None):
            depth = pb.memory[0xC534]
            page_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6]))
            page_blank_details.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6], pb.memory[0xC1B1], pb.register_file.D,
                pb.register_file.HL, pb.memory[0xC0D5],
                pb.memory[0xC0D9] | (pb.memory[0xC0DA] << 8),
                pb.memory[0xC6AA], pb.memory[0xC6AC], pb.memory[0xC6BB],
                depth,
                tuple(pb.memory[0xC535 + index]
                      for index in range(depth + 1)),
                tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)),
                tuple(pb.memory[address] for address in
                      (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B))))
        pb.hook_register(menuvwf.ITEM_PAGE_BANK, page_labels['pbdisable'],
                         page_blank, None)
        info_labels = menuvwf.info_lifecycle_labels()
        def pot_entry_attempt(_ctx=None):
            depth = pb.memory[0xC534]
            pot_entry_attempts.append((
                frame[0], pb.register_file.A, pb.register_file.D,
                pb.register_file.HL, pb.memory[0xC6A3],
                pb.memory[0xC1B3], pb.memory[0xC1B6], pb.memory[0xC1B7],
                pb.memory[0xC1B1], pb.memory[0xC0D5],
                pb.memory[0xC0D9] | (pb.memory[0xC0DA] << 8),
                pb.memory[0xC6A6], pb.memory[0xC6DE],
                pb.memory[0xC6AA], pb.memory[0xC6AC], pb.memory[0xC6BB],
                depth,
                tuple(pb.memory[0xC535 + index]
                      for index in range(depth + 1)),
                tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)),
                tuple(pb.memory[address] for address in
                      (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B))))
        pb.hook_register(menuvwf.ACTION_BLANK_BANK,
                         info_labels['potentrybegin'], pot_entry_attempt, None)
        for label in ('potentrychrome', 'potentrypublish', 'potentrypublished'):
            pb.hook_register(
                menuvwf.ACTION_BLANK_BANK, info_labels[label],
                lambda _ctx=None, name=label: pot_entry_lifecycle.append((
                    frame[0], name, pb.memory[0xC6A3], pb.memory[0xC1B3],
                    pb.memory[0xC1B6], pb.memory[0xC6BB])), None)
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
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(
            statusvwf.FAR_BANK, status_labels['statusdisable'],
            lambda _ctx=None: status_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6])), None)
        def item_entry(_context=None):
            depth = pb.memory[0xC534]
            entry_attempts.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC6A6],
                pb.memory[0xC1B3], depth,
                tuple(pb.memory[0xC535 + index] for index in range(depth + 1)),
                pb.memory[0xC6AA], pb.memory[0xC6AC],
                tuple(pb.memory[address] for address in
                      (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B))))
        pb.hook_register(0x35, 0x4083, item_entry, None)
        def pop_entry(_context=None):
            depth = pb.memory[0xC534]
            pop_attempts.append((
                frame[0], pb.register_file.A, pb.register_file.HL,
                pb.memory[0xC6A3], pb.memory[0xC6A6], pb.memory[0xC6DE],
                pb.memory[0xC6AA], pb.memory[0xC6AC], pb.memory[0xC1B6], depth,
                tuple(pb.memory[0xC535 + index] for index in range(depth + 1)),
                tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)),
                tuple(pb.memory[address] for address in
                      (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B))))
        pb.hook_register(menuvwf.ACTION_POP_BANK, menuvwf.ACTION_POP_AT,
                         pop_entry, None)
        for frame[0] in range(FRAMES):
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            entry_at = 3300 if exact_five else 3400
            if entry_at <= frame[0] <= entry_at + 80:
                entry_samples.append((
                    frame[0], bytes(pb.memory[0x9800:0x9C00]),
                    bool(pb.memory[0xFF40] & 0x80), pb.memory[0xC6A3],
                    pb.memory[0xC1B3], pb.memory[0xC1B6],
                    pb.memory[0xC6BB], pb.screen.image.copy()))
                if png_dir:
                    os.makedirs(png_dir, exist_ok=True)
                    pb.screen.image.save(os.path.join(
                        png_dir, 'entry_f%04d.png' % frame[0]))
            if return_at <= frame[0] <= return_at + 100:
                image = pb.screen.image.copy()
                bg = bytes(pb.memory[0x9800:0x9C00])
                tiles = bytes(pb.memory[0x8800:0x9800])
                samples.append((frame[0], bg, tiles,
                                bool(pb.memory[0xFF40] & 0x80),
                                pb.memory[0xC6A3], pb.memory[0xC1B3],
                                pb.memory[0xC1B6], image))
                if png_dir:
                    os.makedirs(png_dir, exist_ok=True)
                    image.save(os.path.join(png_dir, 'return_f%04d.png' % frame[0]))

        final_bg = bytes(pb.memory[0x9800:0x9C00])
        final_tiles = bytes(pb.memory[0x8800:0x9800])
        final_image = pb.screen.image.copy()
        final_rows = visual_item_rows(final_image)
        final_cells = item_cells(final_bg)
        if png_dir:
            final_image.save(os.path.join(png_dir, 'final.png'))
        pb.stop(save=False)

    screens = [screen for _at, screen, _stack, _state in dispatches]
    if not any(screen in (12, 13) for screen in screens):
        problems.append('real route never dispatched carried-Pot screen 12/13')
    if not injected[0]:
        problems.append('exact five-row inventory could not be injected')
    if not any(at > return_at and screen == 1 for at, screen, _stack, _state in dispatches):
        problems.append('B never returned through Items screen 1')
    off = [at for at, _bg, _tiles, lcd, _screen, _state, _admission, _image
           in samples if not lcd]
    if off:
        problems.append('See -> Items disabled the LCD on frame(s) %s' % off[:16])
    expected_page_blanks = ()
    if tuple(event[1:] for event in page_blanks) != expected_page_blanks:
        problems.append('Pot viewer Item-page blank states are %s, expected %s' %
                        (tuple(event[1:] for event in page_blanks),
                         expected_page_blanks))
    if regional_blanks:
        problems.append('Pot viewer wrote the regional LCD-off site at %s' %
                        (regional_blanks,))
    entry_off = [at for at, _bg, lcd, _screen, _state, _admission, _rows, _image
                 in entry_samples if not lcd]
    if entry_off:
        problems.append('Items -> Pot See disabled the LCD on frame(s) %s' %
                        entry_off[:16])
    viewer_samples = [sample for sample in entry_samples
                      if sample[3] in (12, 13) and 1 <= sample[6] <= 5]
    chrome_frames = [sample[0] for sample in viewer_samples
                     if pot_chrome_complete(sample[1], sample[6])]
    # PyBoy exposes the post-CPU BG map alongside the just-scanned image. During the
    # final handoff, shadow publication can therefore advance the map one scan ahead of
    # the image. Prove chrome and the settled `Pot` raster independently, then compare
    # order. Exact raster equality also rejects the outgoing `Items` title as Pot text.
    settled_title = (pot_title_pixels(viewer_samples[-1][7])
                     if viewer_samples else None)
    text_frames = [sample[0] for sample in viewer_samples
                   if settled_title is not None and
                   pot_title_pixels(sample[7]) == settled_title]
    if not chrome_frames:
        problems.append('Items -> Pot See never published complete Pot chrome')
    elif not text_frames or not pot_text_visible(viewer_samples[-1][7]):
        problems.append('Items -> Pot See never published Pot title/body text')
    elif chrome_frames[0] >= text_frames[0]:
        problems.append('Pot text first appears at f%d without an earlier empty-chrome '
                        'frame (first chrome f%d)' %
                        (text_frames[0], chrome_frames[0]))
    actual_lifecycle = tuple(label for _at, label, screen, _state, _admission, _rows
                             in pot_entry_lifecycle if screen in (12, 13))
    if (actual_lifecycle.count('potentrychrome') != 1 or
            actual_lifecycle.count('potentrypublished') != 1 or
            not actual_lifecycle or actual_lifecycle[-1] != 'potentrypublished' or
            len(actual_lifecycle) < 3 or
            actual_lifecycle[-2] != 'potentrypublish' or
            any(label not in ('potentrychrome', 'potentrypublish',
                              'potentrypublished') for label in actual_lifecycle)):
        problems.append('carried-Pot entry lifecycle has invalid attempt/publication '
                        'order %s' % (actual_lifecycle,))
    if status_blanks:
        problems.append('Pot return wrote the Status LCD-off site at %s' %
                        (status_blanks,))
    if not chrome_complete(final_bg):
        problems.append('settled Items screen has incomplete box chrome')
    if parent_title[0] is None:
        problems.append('route never captured the pre-Pot Items title')
    else:
        old_bg, old_tiles = parent_title[0]
        old_title = resolved_region(old_bg, old_tiles, range(3), range(6))
        new_title = resolved_region(final_bg, final_tiles, range(3), range(6))
        if new_title != old_title:
            problems.append('settled Items title pixels differ from the pre-Pot title')

    exposed = []
    first_text = None
    first_empty_chrome = None
    title_states = []
    for at, bg, tiles, _lcd, screen, state, _admission, image in samples:
        if screen != 1:
            continue
        current = visual_item_rows(image)
        # Match actual scanout pixels, not reused tile IDs: Pot and Items deliberately
        # borrow the same VWF slots while their maps overlap during the hand-off.
        has_final_text = any(any(refs) and row == final_row
                             for row, final_row, refs in
                             zip(current, final_rows, final_cells))
        if has_final_text and first_text is None:
            first_text = at
        if (not has_final_text and chrome_complete(bg) and
                first_empty_chrome is None):
            first_empty_chrome = at
        if has_final_text and not chrome_complete(bg):
            exposed.append(at)
        title_states.append((at, resolved_region(bg, tiles, range(3), range(6))))
    if first_text is None:
        problems.append('return never exposed restored Items text')
    if first_empty_chrome is None:
        problems.append('return never exposed complete empty Items chrome before text')
    elif first_text is not None and first_empty_chrome >= first_text:
        problems.append('complete empty Items chrome did not precede restored text')
    if exposed:
        problems.append('restored Items text preceded complete chrome on frame(s) %s'
                        % exposed[:16])
    if parent_title[0] is not None and first_empty_chrome is not None:
        old_bg, old_tiles = parent_title[0]
        complete_title = resolved_region(old_bg, old_tiles, range(3), range(6))
        blank_title = next((value for at, value in title_states
                            if at == first_empty_chrome), None)
        mixed_titles = [at for at, value in title_states
                        if at >= first_empty_chrome and
                        value not in (blank_title, complete_title)]
        if mixed_titles:
            problems.append('Items title exposed a partial/mixed raster on frame(s) %s'
                            % mixed_titles[:16])

        if trace:
            print('  dispatches %s' % (dispatches,))
            print('  Pot-entry blank details %s' % (page_blank_details,))
            print('  regional Pot-entry attempts %s' % (pot_entry_attempts,))
            print('  carried-Pot entry lifecycle %s; first chrome/text %s/%s' %
                  (pot_entry_lifecycle,
                   chrome_frames[0] if chrome_frames else None,
                   text_frames[0] if text_frames else None))
            print('  entry frames %s' % ([(sample[0], sample[3], sample[6],
                                           pot_chrome_complete(sample[1], sample[6]),
                                           pot_text_visible(sample[7]))
                                          for sample in entry_samples
                                          if 3400 <= sample[0] <= 3420],))
            print('  Item-entry attempts %s' % (entry_attempts,))
            print('  pop attempts %s' % (pop_attempts,))
            print('  first empty chrome %s; first restored text %s; '
                  'incomplete-text frames %s' %
                  (first_empty_chrome, first_text, exposed))
            print('  final body top %s; sides %s' %
                  (final_bg[3 * 32:3 * 32 + 20].hex(' '),
                   [(final_bg[row * 32], final_bg[row * 32 + 19])
                    for row in range(4, 13)]))
            for at, bg, _tiles, lcd, screen, state, admission, _image in samples:
                if at <= return_at + 40:
                    print('  f%d lcd=%d screen=%d state=$%02X admit=$%02X '
                          'chrome=%d rows=%s' %
                          (at, lcd, screen, state, admission, chrome_complete(bg),
                           '/'.join(row.hex() for row in item_cells(bg))))

    print('potreturnspill: dispatches %s; Item-page blank %s; regional branch/write '
          '%s/%s; '
          'empty chrome %s; first Items text %s; '
          '%d problem(s)'
          % (' '.join('f%d:%d' % (at, screen)
                      for at, screen, _stack, _state in dispatches),
             page_blanks, regional_fallbacks, regional_blanks,
             'f%d' % first_empty_chrome if first_empty_chrome is not None else 'none',
             'f%d' % first_text if first_text is not None else 'none',
             len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--full-page', action='store_true',
                        help='use the full page-4 hidden-Pot regression save')
    parser.add_argument('--exact-five', action='store_true',
                        help='use Egg/Egg/Happy/Fusion/Manji five-row inventory')
    args = parser.parse_args()
    if args.full_page or args.exact_five:
        args.ram = FULL_RAM
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('potreturnspill: missing %s' % path)
    return run(args.rom, args.ram, args.png_dir, args.trace, args.exact_five)


if __name__ == '__main__':
    raise SystemExit(main())
