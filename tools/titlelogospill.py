#!/usr/bin/env python3
"""Fresh-boot regression for the English title-screen logo.

The supplied ROM is compared with a temporary control whose two producer hooks are
restored to the native title producer call. Every generated tile, visible map cell and
pixel of the fresh (variant 0, "Monsters of Moonlight Village") title must match the
approved raster, and both cartridges must still settle on the same file menu after Start.
The English-aligned SGB attribute file must be installed. Save-dependent title variants
are ``titlevariantspill.py``'s job; the Fin card is ``moonlighttitlespill.py``'s.

usage: titlelogospill.py ROM [--png FILE]
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
    far_call = bytes((0xD7, titlelogo.FAR_UPLOAD, titlelogo.FAR_BANK))
    for bank, addr in ((titlelogo.OPENING_HOOK_BANK, titlelogo.OPENING_HOOK_AT),
                       (titlelogo.ENDING_HOOK_BANK, titlelogo.ENDING_HOOK_AT)):
        at = titlelogo._off(bank, addr)
        if bytes(data[at:at + 3]) != far_call:
            raise SystemExit('titlelogospill: %s has no English title hook at %d:$%04X'
                             % (rom, bank, addr))
        data[at:at + 3] = titlelogo.NATIVE_PRODUCER_CALL
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


def _check_title(problems, title, native, built, label, variant='monsters'):
    expected = titlelogo.variant_graphics(built, variant)
    exact = total = 0
    for tile, want in expected['tiles'].items():
        start = _tile_offset(tile)
        actual = title['tiles'][start:start + 16]
        total += 16
        exact += sum(a == b for a, b in zip(actual, want))
        if actual != want:
            problems.append('%s title tile $%02X differs in %d/16 byte(s)'
                            % (label, tile, sum(a != b for a, b in zip(actual, want))))
            break

    for row in range(titlelogo.MAP_HEIGHT):
        actual = title['map'][row * 32:row * 32 + 20]
        want = expected['map'][row * 20:(row + 1) * 20]
        if actual != want:
            problems.append('%s title map row %d differs' % (label, row))
            break

    shades = {255: 0, 153: 1, 85: 2, 0: 3}
    pixels = bytes(shades[value[0]] for value in title['image'].convert('RGB').getdata())
    if pixels != built['rasters'][variant]:
        problems.append('%s title screen differs from the approved %s raster'
                        % (label, variant))
    if title['image'].tobytes() == native['image'].tobytes():
        problems.append('%s English title is pixel-identical to the Japanese control' %
                        label)
    if not title['lcdc'] & 0x80 or title['bgp'] != 0xE4:
        problems.append('%s settled title display state is LCDC=$%02X BGP=$%02X'
                        % (label, title['lcdc'], title['bgp']))
    return exact, total


def _check_sgb_attributes(problems, rom):
    data = open(rom, 'rb').read()
    at = titlelogo._off(titlelogo.SGB_ATTR_BANK, titlelogo.SGB_ATTR_ADDR)
    actual = data[at:at + len(titlelogo.SGB_ATTRIBUTE_PACK)]
    if actual != titlelogo.SGB_ATTRIBUTE_PACK:
        problems.append('English title SGB 20x18 attribute map differs from the '
                        'approved palette layout')


def run(rom, png=None):
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

    built = titlelogo.compile_graphics(dotfont.load_approved())
    problems = []
    _check_sgb_attributes(problems, rom)
    exact, total = _check_title(problems, title, native, built, 'fresh')
    if menu['image'].tobytes() != native_menu['image'].tobytes():
        problems.append('fresh file menu after PUSH START differs from native control')

    print('titlelogospill: fresh route, %d/%d generated tile byte(s) exact; %d shared + %d '
          'subtitle tile(s); map and approved Monsters raster exact; English 20x18 SGB '
          'attributes exact; file-menu transition exact; %d problem(s)' %
          (exact, total, built['shared'], built['per_variant'], len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('titlelogospill: missing %s' % args.rom)
    raise SystemExit(run(args.rom, args.png))


if __name__ == '__main__':
    main()
