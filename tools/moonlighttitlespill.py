#!/usr/bin/env python3
"""Compare the real Moonlight post-credit title with its native Fin-card control.

The SRAM route is unmodified: finish floor 49 and let the cinematic and credits run.
Require the approved opening artwork without PUSH START, the native Fin's exact
pixels/position, register-transparent LCD-off installation, and the original hold.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import titlelogo
from endingcreditspill import BOOT, ADVANCE_UNTIL
from gbrun import PRESS_FRAMES, _import_pyboy
from titlelogospill import _checksums


RAM = os.path.join(ROOT, 'saves', 'shiren_en-moonlight-ending.srm')
HOOK_AT = 31 * 0x4000 + 0x799B - 0x4000
NATIVE_CALL = bytes.fromhex('d7 0b 1e')
FIN_BOX = (15, 13, 4, 4)
FIN_PIXELS = (120, 104, 152, 136)


def _native_control(rom, path):
    data = bytearray(open(rom, 'rb').read())
    if data[HOOK_AT:HOOK_AT + 3] not in (NATIVE_CALL, bytes.fromhex('d7 05 3e')):
        raise SystemExit('moonlighttitlespill: unrecognized post-credit title hook')
    data[HOOK_AT:HOOK_AT + 3] = NATIVE_CALL
    _checksums(data)
    with open(path, 'wb') as out:
        out.write(data)


def _replay(PyBoy, rom, ram, cgb):
    shutil.copyfile(ram, rom + '.ram')
    pb = PyBoy(rom, window='null', cgb=cgb)
    pb.set_emulation_speed(0)
    entries, returns, captures, hold_lcdc = [], [], [], []
    due = [None]

    def ready(_ctx):
        regs = pb.register_file
        entries.append({
            'frame': pb.frame_count,
            'lcdc': pb.memory[0xFF40],
            'registers': tuple(getattr(regs, name) for name in
                               ('A', 'F', 'B', 'C', 'D', 'E', 'HL', 'SP')),
        })
        due[0] = pb.frame_count + 100

    def returned(_ctx):
        returns.append(pb.frame_count)

    def waiting(_ctx):
        if entries:
            entries[-1]['wait'] = pb.frame_count

    pb.hook_register(31, 0x799E, ready, None)
    pb.hook_register(31, 0x79AB, waiting, None)
    pb.hook_register(31, 0x79AE, returned, None)
    for frame in range(17000):
        for button in BOOT.get(frame, ()):
            pb.button(button, PRESS_FRAMES)
        if 2660 <= frame < ADVANCE_UNTIL and (frame - 2660) % 60 == 0:
            pb.button('a', PRESS_FRAMES)
        if entries and pb.frame_count == entries[-1].get('wait', -1000) + 120:
            pb.button('a', PRESS_FRAMES)
        pb.tick()
        if due[0] and pb.frame_count >= due[0] and not returns:
            hold_lcdc.append(pb.memory[0xFF40])
            if not captures:
                captures.append({
                    'image': pb.screen.image.copy().convert('RGB'),
                    'tiles': bytes(pb.memory[0x8800:0x9800]),
                    'map': b''.join(bytes(pb.memory[0x9800 + y * 32:
                                                   0x9800 + y * 32 + 20])
                                    for y in range(18)),
                    'display': tuple(pb.memory[addr] for addr in
                                     (0xFF40, 0xFF42, 0xFF43, 0xFF47, 0xFF4A, 0xFF4B)),
                })
        if returns:
            break
    pb.stop(save=False)
    return entries, returns, captures, hold_lcdc


def _tile(capture, index):
    at = titlelogo._vram_addr(index) - 0x8800
    return capture['tiles'][at:at + 16]


def _raster(tilemap, tiles, cgb):
    palette = (((255, 255, 255), (123, 255, 49), (0, 99, 197), (0, 0, 0))
               if cgb else tuple((shade,) * 3 for shade in (255, 153, 85, 0)))
    pixels = bytearray()
    for y in range(144):
        for x in range(160):
            tile = tiles[tilemap[(y // 8) * 20 + x // 8]]
            lo, hi = tile[(y % 8) * 2:(y % 8) * 2 + 2]
            bit = 7 - x % 8
            pixels.extend(palette[((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)])
    return bytes(pixels)


def run(rom, ram, png_dir=None):
    PyBoy = _import_pyboy()
    artwork = titlelogo.compile_graphics()
    problems = []
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='moonlighttitlespill-') as tmp:
        for cgb in (False, True):
            label = 'CGB' if cgb else 'DMG'
            target = os.path.join(tmp, label + '.gb')
            control = os.path.join(tmp, label + '-native.gb')
            shutil.copyfile(rom, target)
            _native_control(rom, control)
            actual = _replay(PyBoy, target, ram, cgb)
            native = _replay(PyBoy, control, ram, cgb)
            if any(len(result[0]) != 1 or len(result[1]) != 1 or
                   len(result[2]) != 1 for result in (actual, native)):
                failure = label + ': post-credit card/hold was not reached exactly once'
                print('moonlighttitlespill: ' + failure)
                problems.append(failure)
                continue
            entry, returned, (shot,), hold = actual
            native_entry, native_returned, (native_shot,), _ = native
            failures = []
            expected_map = bytearray(artwork['map'])
            blank = next(tile for tile, data in artwork['tiles'].items() if data == bytes(16))
            expected_map[15 * 20 + 6:15 * 20 + 14] = bytes((blank,)) * 8
            expected_tiles = dict(artwork['tiles'])
            x, y, width, height = FIN_BOX
            for row in range(height):
                for col in range(width):
                    index = row * width + col
                    at = (y + row) * 20 + x + col
                    original_id = native_shot['map'][at]
                    if original_id != 0x2D + index:
                        failures.append('native Fin source map changed')
                    tile_id = artwork['unique'] + index
                    expected_tiles[tile_id] = _tile(native_shot, original_id)
                    expected_map[at] = tile_id
            if shot['map'] != expected_map:
                failures.append('ending map differs from English title + native Fin')
            if any(_tile(shot, tile) != want for tile, want in expected_tiles.items()):
                failures.append('English title / preserved Fin tile planes differ')
            if shot['image'].tobytes() != _raster(expected_map, expected_tiles, cgb):
                failures.append('full 160x144 ending raster differs')
            if (shot['image'].crop(FIN_PIXELS).tobytes() !=
                    native_shot['image'].crop(FIN_PIXELS).tobytes()):
                failures.append('Fin pixels or position changed')
            if entry[0]['lcdc'] & 0x80:
                failures.append('title was installed outside the native LCD-off interval')
            if entry[0]['registers'] != native_entry[0]['registers']:
                failures.append('title wrapper changed native return registers')
            if shot['display'] != native_shot['display']:
                failures.append('native settled palette/scroll/LCDC changed')
            duration = returned[0] - entry[0]['frame']
            native_duration = native_returned[0] - native_entry[0]['frame']
            if abs(duration - native_duration) > 1:
                failures.append('native card hold changed: %d vs %d frames' %
                                (duration, native_duration))
            if len(hold) < 100 or any(not lcdc & 0x80 for lcdc in hold):
                failures.append('settled card did not stay visible through the hold')
            if png_dir:
                shot['image'].save(os.path.join(png_dir, label.lower() + '_title.png'))
            print('moonlighttitlespill: %s; English title + native Fin; '
                  'hold %d/%d native frames; %d problem(s)' %
                  (label, duration, native_duration, len(failures)))
            for failure in failures:
                print('  ' + failure)
            problems.extend(failures)
    return int(bool(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    return run(args.rom, args.ram, args.png_dir)


if __name__ == '__main__':
    raise SystemExit(main())
