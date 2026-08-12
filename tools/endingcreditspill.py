#!/usr/bin/env python3
"""Save-backed regression for the complete 22-card English ending credits.

Joey's Hard-ending Log 1 fixture enters the credits through real story/ending code.  The
test observes all 22 far-uploader calls, then checks both 640-byte tile strips after
each upload, the six credit-band map rows, continued forest animation, and the native
post-credit ``End`` screen.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import endingcredits                                               # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                       # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_trigger_ending.srm')
FRAMES = 22000
ADVANCE_UNTIL = 14000
BOOT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 420: ('a',), 480: ('a',),
    2550: ('right',), 2600: ('a',),
}


def _far_entry(rom, bank):
    with open(rom, 'rb') as src:
        data = src.read()
    at = endingcredits._off(bank, 0x4000) + \
        endingcredits.FAR_UPLOAD - 1
    entry = data[at] | (data[at + 1] << 8)
    if entry == 0xFFFF:
        raise SystemExit('endingcreditspill: ROM has no English-credit far entry')
    return entry


def _expected_map():
    role_top = bytes(range(0x80, 0xC0, 2))
    role_bottom = bytes(range(0x81, 0xC0, 2))
    name_top = bytes(range(0xB0, 0xF0, 2))
    name_bottom = bytes(range(0xB1, 0xF0, 2))
    return (bytes((0x80,)) * 32, role_top, role_bottom,
            name_top, name_bottom, bytes((0x80,)) * 32)


def _mapped_strip(tile_data, tile_base, top_map, bottom_map):
    """Reconstruct the displayed 20x2 strip in row-major audition order."""
    out = bytearray()
    for row in (top_map, bottom_map):
        for tile in row[:endingcredits.TILES_PER_ROW]:
            index = tile - tile_base
            if not 0 <= index < endingcredits.TILES_PER_ROW * 2:
                return None
            at = index * endingcredits.TILE_BYTES
            out.extend(tile_data[at:at + endingcredits.TILE_BYTES])
    return bytes(out)


def run(rom, ram, png=None):
    PyBoy = _import_pyboy()
    cards = endingcredits.graphics()
    source_cards = endingcredits.source_graphics()
    problems = []
    with tempfile.TemporaryDirectory(prefix='endingcreditspill-') as tmp:
        work = os.path.join(tmp, 'ending.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame_now = [0]
        calls = []
        pending = []
        captures = []

        def upload_hook(base):
            def at_upload(_ctx=None):
                index = base + pb.register_file.A
                calls.append((frame_now[0], index))
                # The uploader returns before the native palette fade has completed and
                # before the second strip is visibly settled.  Capture in the long stable
                # dwell, not merely when VRAM already contains the bytes.
                pending.append((frame_now[0] + 80, index))
            return at_upload

        for group, bank in enumerate(endingcredits.FAR_BANKS):
            pb.hook_register(bank, _far_entry(rom, bank),
                             upload_hook(group * endingcredits.CARDS_PER_BANK), None)

        for frame in range(FRAMES):
            frame_now[0] = frame
            for button in BOOT.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            if 2660 <= frame < ADVANCE_UNTIL and (frame - 2660) % 60 == 0:
                pb.button('a', PRESS_FRAMES)
            pb.tick()

            for due, index in tuple(pending):
                if frame < due:
                    continue
                pending.remove((due, index))
                captures.append({
                    'frame': frame,
                    'index': index,
                    'role': bytes(pb.memory[endingcredits.ROLE_VRAM:
                                            endingcredits.ROLE_VRAM +
                                            endingcredits.STRIP_BYTES]),
                    'name': bytes(pb.memory[endingcredits.NAME_VRAM:
                                            endingcredits.NAME_VRAM +
                                            endingcredits.STRIP_BYTES]),
                    'map': tuple(bytes(pb.memory[0x9980 + row * 32:
                                                 0x9980 + (row + 1) * 32])
                                 for row in range(6)),
                    'forest': pb.screen.image.copy().crop((0, 0, 160, 84)).tobytes(),
                    'credit_window': pb.screen.image.copy().convert('RGB').crop(
                        (0, 96, 160, 128)).tobytes(),
                    'image': pb.screen.image.copy(),
                })

        final = pb.screen.image.copy().convert('RGB')
        final_pc = (pb.memory[0x4000], pb.register_file.PC)
        if png and captures:
            captures[-1]['image'].save(png)
            print('endingcreditspill: wrote %s' % png)
        pb.stop(save=False)

    order = [index for _frame, index in calls]
    if order != list(range(endingcredits.CARD_COUNT)):
        problems.append('credit upload order is %s, expected 0 through %d' %
                        (order, endingcredits.CARD_COUNT - 1))
    if pending:
        problems.append('%d card capture(s) never settled' % len(pending))
    if len(captures) != endingcredits.CARD_COUNT:
        problems.append('captured %d/%d settled cards' %
                        (len(captures), endingcredits.CARD_COUNT))

    expected_map = _expected_map()
    exact = total = displayed_exact = displayed_total = 0
    for capture in captures:
        index = capture['index']
        if not 0 <= index < len(cards):
            problems.append('uploader received invalid card %d' % index)
            continue
        expected = cards[index]
        actual = capture['role'] + capture['name']
        exact += sum(a == b for a, b in zip(actual, expected))
        total += len(expected)
        if actual != expected:
            problems.append('card %d differs in %d/%d tile byte(s)' %
                            (index, sum(a != b for a, b in zip(actual, expected)),
                             len(expected)))
        if capture['map'] != expected_map:
            bad = next(row for row in range(6)
                       if capture['map'][row] != expected_map[row])
            problems.append('card %d credit map row %d differs' % (index, bad + 12))
        displayed_role = _mapped_strip(capture['role'], 0x80,
                                       capture['map'][1], capture['map'][2])
        displayed_name = _mapped_strip(capture['name'], 0xB0,
                                       capture['map'][3], capture['map'][4])
        displayed = (displayed_role or b'') + (displayed_name or b'')
        source = source_cards[index]
        displayed_exact += sum(a == b for a, b in zip(displayed, source))
        displayed_total += len(source)
        if displayed != source:
            problems.append('card %d displayed raster differs in %d/%d tile bytes' %
                            (index, sum(a != b for a, b in zip(displayed, source)),
                             len(source)))
        expected_window = endingcredits.card_window(index)
        if capture['credit_window'] != expected_window:
            problems.append('card %d on-screen credit rows differ from approved raster'
                            % index)

    # The native scene continues moving behind stable cards; using two different cards
    # avoids treating the intentionally static black credit band as animation evidence.
    if len(captures) >= 2 and captures[0]['forest'] == captures[1]['forest']:
        problems.append('native forest did not animate between credit cards')

    # The ordinary post-credit screen is black with a compact green End glyph at center.
    # Require that shape rather than a frame-exact hash so native fade timing may breathe.
    colors = list(final.getdata())
    black = sum(color == (0, 0, 0) for color in colors)
    green = sum(color == (123, 255, 49) for color in colors)
    if black < 22000 or not 150 <= green <= 1000:
        problems.append('post-credit screen did not reach native End state '
                        '(black=%d green=%d, PC b%02X:$%04X)' %
                        (black, green, final_pc[0], final_pc[1]))

    print('endingcreditspill: %d/%d translated cards in order; '
          '%d/%d uploaded and %d/%d displayed tile byte(s) exact; '
          'six-row map exact; animated forest; native End reached; %d problem(s)' %
          (len(captures), endingcredits.CARD_COUNT, exact, total,
           displayed_exact, displayed_total, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('endingcreditspill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
