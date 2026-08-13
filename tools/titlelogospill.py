#!/usr/bin/env python3
"""Fresh and completion-unlocked boot regression for the English title-screen logo.

The supplied ROM is compared with a temporary control whose bank-62 title-logo far entry
returns without drawing. Every generated tile and visible map cell must match the
approved viewer-supplied full-screen reference, and both cartridges must still settle on
the same file menu after Start.  ``--ram`` adds the native save-dependent alternate title
route; both native layouts must be replaced by the same English raster.

usage: titlelogospill.py ROM [--ram FILE] [--png FILE]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dotfont                                                    # noqa: E402
import titlelogo                                                  # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                     # noqa: E402


TITLE_FRAME = 850
MENU_FRAME = 1050
TITLE_ROUTE = {700: 'start'}
MENU_ROUTE = {700: 'start', 760: 'start', 820: 'start', 880: 'start'}


def _checksums(data):
    header = 0
    for i in range(0x134, 0x14D):
        header = (header - data[i] - 1) & 0xFF
    data[0x14D] = header
    data[0x14E] = data[0x14F] = 0
    total = sum(data) & 0xFFFF
    data[0x14E] = total >> 8
    data[0x14F] = total & 0xFF


def _native_control(rom, path):
    data = bytearray(open(rom, 'rb').read())
    bank = titlelogo._off(titlelogo.FAR_BANK, 0x4000)
    pointer = bank + titlelogo.FAR_UPLOAD - 1
    if bytes(data[pointer:pointer + 2]) == b'\xFF\xFF':
        raise SystemExit('titlelogospill: %s has no English title-logo far entry' % rom)
    # $6FFF is immediately before the module's asserted $7000 allocation.
    return_addr = 0x6FFF
    return_at = bank + return_addr - 0x4000
    if data[return_at] != 0xFF:
        raise SystemExit('titlelogospill: bank %d:$%04X is not free for control return'
                         % (titlelogo.FAR_BANK, return_addr))
    data[return_at] = 0xC9
    data[pointer:pointer + 2] = bytes((return_addr & 0xFF, return_addr >> 8))
    _checksums(data)
    open(path, 'wb').write(data)


def _run(PyBoy, rom, frame, route, ram=None):
    if ram:
        shutil.copyfile(ram, rom + '.ram')
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    for current in range(frame + 1):
        if current in route:
            pb.button(route[current], PRESS_FRAMES)
        pb.tick()
    result = {
        'image': pb.screen.image.copy(),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'map': bytes(pb.memory[0x9800:0x9C00]),
        'lcdc': pb.memory[0xFF40],
        'bgp': pb.memory[0xFF47],
    }
    pb.stop(save=False)
    return result


def _tile_offset(tile):
    address = titlelogo._vram_addr(tile)
    return address - 0x8800


def _check_title(problems, title, native, built, label):
    exact = total = 0
    for tile, expected in built['tiles'].items():
        start = _tile_offset(tile)
        actual = title['tiles'][start:start + 16]
        total += 16
        exact += sum(a == b for a, b in zip(actual, expected))
        if actual != expected:
            problems.append('%s title tile $%02X differs in %d/16 byte(s)'
                            % (label, tile,
                               sum(a != b for a, b in zip(actual, expected))))
            break

    for row in range(titlelogo.MAP_HEIGHT):
        actual = title['map'][row * 32:row * 32 + 20]
        expected = built['map'][row * 20:(row + 1) * 20]
        if actual != expected:
            problems.append('%s title map row %d differs' % (label, row))
            break

    if title['image'].tobytes() == native['image'].tobytes():
        problems.append('%s English title is pixel-identical to the Japanese control' %
                        label)
    if not title['lcdc'] & 0x80 or title['bgp'] != 0xE4:
        problems.append('%s settled title display state is LCDC=$%02X BGP=$%02X'
                        % (label, title['lcdc'], title['bgp']))
    return exact, total


def run(rom, ram=None, png=None):
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='titlelogospill-') as tmp:
        target = os.path.join(tmp, 'target.gb')
        control = os.path.join(tmp, 'control.gb')
        shutil.copyfile(rom, target)
        _native_control(rom, control)
        title = _run(PyBoy, target, TITLE_FRAME, TITLE_ROUTE)
        native = _run(PyBoy, control, TITLE_FRAME, TITLE_ROUTE)
        menu = _run(PyBoy, target, MENU_FRAME, MENU_ROUTE)
        native_menu = _run(PyBoy, control, MENU_FRAME, MENU_ROUTE)
        if png:
            title['image'].save(png)

        progressed = native_progressed = None
        progressed_menu = native_progressed_menu = None
        if ram:
            progressed_target = os.path.join(tmp, 'progressed_target.gb')
            progressed_control = os.path.join(tmp, 'progressed_control.gb')
            shutil.copyfile(rom, progressed_target)
            _native_control(rom, progressed_control)
            progressed = _run(PyBoy, progressed_target, TITLE_FRAME, TITLE_ROUTE, ram)
            native_progressed = _run(PyBoy, progressed_control, TITLE_FRAME,
                                     TITLE_ROUTE, ram)
            progressed_menu = _run(PyBoy, progressed_target, MENU_FRAME,
                                   MENU_ROUTE, ram)
            native_progressed_menu = _run(PyBoy, progressed_control, MENU_FRAME,
                                          MENU_ROUTE, ram)

    built = titlelogo.compile_graphics(dotfont.load_approved())
    problems = []
    exact, total = _check_title(problems, title, native, built, 'fresh')
    if menu['image'].tobytes() != native_menu['image'].tobytes():
        problems.append('fresh file menu after PUSH START differs from native control')

    routes = 1
    if progressed is not None:
        routes += 1
        if native_progressed['image'].tobytes() == native['image'].tobytes():
            problems.append('progressed fixture did not select the alternate native title')
        progressed_exact, progressed_total = _check_title(
            problems, progressed, native_progressed, built, 'progressed-save')
        exact += progressed_exact
        total += progressed_total
        if progressed['image'].tobytes() != title['image'].tobytes():
            problems.append('fresh and progressed-save English title rasters differ')
        if progressed_menu['image'].tobytes() != native_progressed_menu['image'].tobytes():
            problems.append('progressed-save file menu after PUSH START differs from '
                            'native control')

    print('titlelogospill: %d route(s), %d/%d generated tile byte(s) exact; %d unique '
          'tile(s); full 160x144 reference maps exact; file-menu transitions exact; '
          '%d problem(s)' %
          (routes, exact, total, built['unique'], len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('titlelogospill: missing %s' % args.rom)
    if args.ram and not os.path.exists(args.ram):
        raise SystemExit('titlelogospill: missing %s' % args.ram)
    raise SystemExit(run(args.rom, args.ram, args.png))


if __name__ == '__main__':
    main()
