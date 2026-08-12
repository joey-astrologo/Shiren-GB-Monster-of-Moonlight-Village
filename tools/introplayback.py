#!/usr/bin/env python3
# Build the ROM first, then capture the translated post-game ending with:
#
#     sh build.sh
#     python3 tools/introplayback.py
#
# To choose another ROM or output filename:
#
#     python3 tools/introplayback.py path/to/rom.gb --output path/to/ending.gif
#
# The command forces only the cinematic selector used by introspill; it does not modify
# the ROM or require a completed save file.  The resulting GIF is 160x144, runs at 10 fps,
# preserves the ending's original timing, and loops continuously.
"""Record the translated post-game ending as an animated GIF."""

import argparse
import os

from gbrun import _import_pyboy
from introspill import DONE, FORCE_ENTRY, MAX_FRAMES


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(ROOT, 'build', 'shiren_en.gb')
DEFAULT_OUTPUT = os.path.join(ROOT, 'build', 'forced_ending_playback.gif')
SAMPLE_EVERY = 6  # Game Boy frames per GIF frame: approximately 60 fps -> 10 fps.


def capture(rom_path, output_path):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom_path, window='null')
    pb.set_emulation_speed(0)

    frame = [0]
    started = []
    finished = []

    def force_ending(_context):
        de = (pb.register_file.D << 8) | pb.register_file.E
        pb.memory[de + 0x10] = 1
        if not started:
            started.append(frame[0])

    def finish(_context):
        if not finished:
            finished.append(frame[0])

    pb.hook_register(*FORCE_ENTRY, force_ending, None)
    pb.hook_register(*DONE, finish, None)

    images = []
    for current in range(MAX_FRAMES):
        frame[0] = current
        pb.tick()
        if started and ((current - started[0]) % SAMPLE_EVERY == 0 or finished):
            images.append(pb.screen.image.copy())
        if finished:
            break

    pb.stop(save=False)
    if not started:
        raise SystemExit('introplayback: ending hook was never reached')
    if not finished:
        raise SystemExit('introplayback: ending did not finish naturally')
    if not images:
        raise SystemExit('introplayback: no frames captured')

    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=100,
        loop=0,
        optimize=True,
    )
    print(
        'introplayback: ending frames %d-%d; %d samples at 10 fps; wrote %s'
        % (started[0], finished[0], len(images), output_path)
    )


def main():
    parser = argparse.ArgumentParser(
        description='Force and record the translated post-game ending as a looping GIF.')
    parser.add_argument('rom', nargs='?', default=DEFAULT_ROM,
                        help='built ROM to record (default: build/shiren_en.gb)')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='GIF destination (default: build/forced_ending_playback.gif)')
    args = parser.parse_args()

    if not os.path.isfile(args.rom):
        raise SystemExit('introplayback: ROM not found: %s; run sh build.sh first' % args.rom)
    capture(args.rom, args.output)


if __name__ == '__main__':
    main()
