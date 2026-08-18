#!/usr/bin/env python3
"""Capture the ORIGINAL Japanese ending-credit roll as a reference contact sheet.

``endingcreditsaudition.py`` auditions the replacement cards by rendering them from
Poppins.  There is no equivalent for the cards being replaced: the Japanese card is not a
stored raster either.  Bank 31's native driver uploads and shows each one at runtime, so
the only faithful way to see one is to let the game draw it.

The Japanese ROM cannot simply be driven there.  ``saves/shiren_en_log_1_trigger_ending.srm``
and the frame-timed boot sequence were captured against the English build; on
``build/base.gb`` the very same input lands in Fay's Puzzles instead of the Hard-ending
route, because the English intro and title cards do not consume the same frames.  So this
drives ``build.py --no-endingcredits``, which leaves the native roll in place ("ending
credits stay Japanese") while keeping the route the fixture needs untouched.

Cards are found by hooking the native show-card routine at 31:$7AB1 -- the same routine
``endingcredits.py``'s English sequencer calls -- and capturing once the card has settled.
That routine runs 24 times: the roll's fade-in and the post-roll end mark leave the credit
band empty, so the 22 real cards are the calls which actually inked it.

This is a reference sheet for translation work, not a test.  ``endingcreditspill.py`` is
what proves the shipped English cards.

usage: endingcreditscanjp.py [OUTPUT.png] [--rom ROM] [--cards-dir DIR] [--scale N]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import endingcredits                                              # noqa: E402
from endingcreditspill import ADVANCE_UNTIL, BOOT, FRAMES, RAM    # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                     # noqa: E402


EXPANDED = os.path.join(ROOT, 'build', '_base_expanded.gb')
SCRIPT = os.path.join(ROOT, 'script', 'en.tsv')
DEFAULT_ROM = os.path.join(ROOT, 'build', 'ending_credits_native.gb')
DEFAULT_OUTPUT = os.path.join(ROOT, 'build', 'ending_credits_japanese.png')

# 31:$7AB1 draws the card the driver just uploaded.  It returns before the palette fade
# has finished, so capture in the long stable dwell, exactly as endingcreditspill does.
SHOW_CARD = (31, 0x7AB1)
SETTLE = 80
# The credit text window, not endingcredits.CREDIT_BAND_TOP: 84 is where the audition
# mock-up's black band starts, but on screen the forest still animates down to y=96, so a
# crop taken from 84 never reads as blank.  96-127 is what card_window() documents and
# what endingcreditspill compares.
CREDIT_WINDOW = (0, 96, 160, 128)
MIN_CARD_INK = 64


def build_native_rom(path):
    """Build a ROM whose ending credits are still the Japanese originals."""
    for required in (EXPANDED, SCRIPT):
        if not os.path.exists(required):
            raise SystemExit('endingcreditscanjp: missing %s -- run `sh build.sh` first'
                             % required)
    print('endingcreditscanjp: building %s (--no-endingcredits)'
          % os.path.relpath(path, ROOT))
    result = subprocess.run(
        [sys.executable, os.path.join(HERE, 'build.py'), EXPANDED, SCRIPT, path,
         '--dot-font', '--no-endingcredits'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        raise SystemExit('endingcreditscanjp: --no-endingcredits build failed')


def _band_ink(image):
    """Return how many credit-band pixels differ from the band's background."""
    band = image.crop(CREDIT_WINDOW)
    counts = Counter(band.getdata())
    background, _ = counts.most_common(1)[0]
    return sum(count for color, count in counts.items() if color != background)


def capture(rom, ram, frames=FRAMES, advance_until=ADVANCE_UNTIL):
    """Return ``(inked cards, blank calls, final screen)`` from one native roll."""
    PyBoy = _import_pyboy()
    shots = []
    with tempfile.TemporaryDirectory(prefix='endingcreditscanjp-') as tmp:
        work = os.path.join(tmp, 'ending.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame_now = [0]
        pending = []

        def at_show(_ctx=None):
            pending.append(frame_now[0] + SETTLE)

        pb.hook_register(SHOW_CARD[0], SHOW_CARD[1], at_show, None)

        for frame in range(frames):
            frame_now[0] = frame
            for button in BOOT.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            if 2660 <= frame < advance_until and (frame - 2660) % 60 == 0:
                pb.button('a', PRESS_FRAMES)
            pb.tick()
            for due in tuple(pending):
                if frame < due:
                    continue
                pending.remove(due)
                shots.append((frame, pb.screen.image.copy().convert('RGB')))
        final = pb.screen.image.copy().convert('RGB')
        pb.stop(save=False)

    if pending:
        raise SystemExit('endingcreditscanjp: %d card capture(s) never settled -- the '
                         'roll did not finish inside %d frames' % (len(pending), frames))
    cards = [(frame, image) for frame, image in shots
             if _band_ink(image) >= MIN_CARD_INK]
    blanks = [frame for frame, image in shots if _band_ink(image) < MIN_CARD_INK]
    return cards, blanks, final


def _slug(text):
    return re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_') or 'card'


def contact_sheet(cards, scale, columns):
    """Lay the native cards out under the English role/name each one is replaced by."""
    cell = (160 * scale, 144 * scale + 14)
    rows = (len(cards) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * cell[0], rows * cell[1]), 'white')
    draw = ImageDraw.Draw(sheet)
    for index, (_frame, image) in enumerate(cards):
        x = index % columns * cell[0]
        y = index // columns * cell[1]
        sheet.paste(image.resize((160 * scale, 144 * scale), Image.Resampling.NEAREST),
                    (x, y + 14))
        # The label is deliberately the English replacement: PIL's built-in font cannot
        # draw the Japanese it would otherwise repeat, and the sheet exists to be read
        # against the cards endingcreditsaudition.py produces.
        if index < endingcredits.CARD_COUNT:
            role, name = endingcredits.CARDS[index]
            draw.text((x + 3, y + 3), '%02d %s / %s' % (index, role, name), fill='black')
        else:
            draw.text((x + 3, y + 3), '%02d (unexpected extra card)' % index, fill='red')
    return sheet


def run(rom, ram, output, cards_dir=None, scale=4, columns=4):
    cards, blanks, final = capture(rom, ram)
    print('endingcreditscanjp: %d inked card(s), %d blank show-card call(s)%s'
          % (len(cards), len(blanks),
             ' at %s' % ', '.join('f%d' % frame for frame in blanks) if blanks else ''))

    for index, (frame, _image) in enumerate(cards):
        if index < endingcredits.CARD_COUNT:
            record = endingcredits.CARD_RECORDS[index]
            print('  %2d. f%-6d %s / %s   (recorded native: %s / %s)'
                  % (index, frame, record['role'], record['name'],
                     record['native_role'], record['native_name']))
        else:
            print('  %2d. f%-6d (unexpected extra card)' % (index, frame))

    sheet = contact_sheet(cards, scale, columns)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    sheet.save(output)
    print('endingcreditscanjp: wrote %s (%dx)' % (output, scale))

    if cards_dir:
        os.makedirs(cards_dir, exist_ok=True)
        for index, (_frame, image) in enumerate(cards):
            label = ('%02d_%s' % (index, _slug(endingcredits.CARDS[index][1]))
                     if index < endingcredits.CARD_COUNT else '%02d_extra' % index)
            image.resize((160 * scale, 144 * scale),
                         Image.Resampling.NEAREST).save(
                os.path.join(cards_dir, 'card_%s.png' % label))
        # The end mark after the roll is deliberately never intercepted, so it belongs
        # in a Japanese reference set.
        final.resize((160 * scale, 144 * scale),
                     Image.Resampling.NEAREST).save(
            os.path.join(cards_dir, 'end_mark.png'))
        print('endingcreditscanjp: wrote %d card(s) and end_mark.png to %s'
              % (len(cards), cards_dir))

    if len(cards) != endingcredits.CARD_COUNT:
        raise SystemExit('endingcreditscanjp: captured %d native card(s), expected %d'
                         % (len(cards), endingcredits.CARD_COUNT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', nargs='?', default=DEFAULT_OUTPUT)
    parser.add_argument('--rom', default=DEFAULT_ROM,
                        help='a --no-endingcredits build; built on demand if absent')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--cards-dir',
                        help='also write one PNG per native card, plus the end mark')
    parser.add_argument('--scale', type=int, default=4)
    parser.add_argument('--columns', type=int, default=4)
    args = parser.parse_args()
    if args.scale < 1:
        raise SystemExit('endingcreditscanjp: --scale must be positive')
    if args.columns < 1:
        raise SystemExit('endingcreditscanjp: --columns must be positive')
    if not os.path.exists(args.ram):
        raise SystemExit('endingcreditscanjp: missing %s' % args.ram)
    if not os.path.exists(args.rom):
        build_native_rom(args.rom)
    run(args.rom, args.ram, args.output, args.cards_dir, args.scale, args.columns)


if __name__ == '__main__':
    main()
