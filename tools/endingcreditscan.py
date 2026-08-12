#!/usr/bin/env python3
"""Replay Joey's Hard-ending SRAM and make a sampled screen timeline.

This is a research/audition helper, not the final credits regression. It advances the
dialogue with A for a bounded interval, then leaves the ending/credits to run naturally.
"""
import argparse
import hashlib
import os
import shutil
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_trigger_ending.srm')
BOOT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 420: ('a',), 480: ('a',),
    2550: ('right',), 2600: ('a',),
}


def run(rom, ram, output, frames=36000, advance_until=16000, sample_every=120,
        captures_dir=None, capture_from=0, capture_to=0, trace_decompress=False,
        inspect_frames=()):
    PyBoy = _import_pyboy()
    captures = []
    with tempfile.TemporaryDirectory(prefix='endingcreditscan-') as tmp:
        work = os.path.join(tmp, 'ending.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame_now = [0]
        decompresses = []

        if trace_decompress:
            def at_decompress(_ctx=None):
                if frame_now[0] < capture_from:
                    return
                regs = pb.register_file
                de = (regs.D << 8) | regs.E
                hl = regs.HL
                stack = tuple(pb.memory[(regs.SP + offset) & 0xFFFF] |
                              (pb.memory[(regs.SP + offset + 1) & 0xFFFF] << 8)
                              for offset in range(0, 12, 2))
                queue_dest = (pb.memory[0xC006] | (pb.memory[0xC007] << 8)
                              if hl < 0xC04A else
                              pb.memory[0xC048] | (pb.memory[0xC049] << 8))
                decompresses.append((frame_now[0], pb.memory[0x4000], de, hl,
                                     pb.memory[0xC161], queue_dest, stack))
            pb.hook_register(0, 0x3ABD, at_decompress, None)

        for frame in range(frames):
            frame_now[0] = frame
            for button in BOOT.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            if 2660 <= frame < advance_until and (frame - 2660) % 60 == 0:
                pb.button('a', PRESS_FRAMES)
            pb.tick()
            if frame in inspect_frames:
                lcd = [pb.memory[address] for address in range(0xFF40, 0xFF4C)]
                bg9800 = bytes(pb.memory[address] for address in range(0x9800, 0x9C00))
                bg9c00 = bytes(pb.memory[address] for address in range(0x9C00, 0xA000))
                oam = bytes(pb.memory[address] for address in range(0xFE00, 0xFEA0))
                print('endingcreditscan: inspect f%d b%02X:%04X lcd=%s' %
                      (frame, pb.memory[0x4000], pb.register_file.PC,
                       ' '.join('%02X' % value for value in lcd)))
                for label, tilemap in (('9800', bg9800), ('9C00', bg9c00)):
                    rows = []
                    for row in range(18):
                        values = tilemap[row * 32:(row + 1) * 32][:20]
                        rows.append('%02d:%s' %
                                    (row, ' '.join('%02X' % value for value in values)))
                    print('  %s\n    %s' % (label, '\n    '.join(rows)))
                active_oam = [oam[index:index + 4].hex(' ')
                              for index in range(0, len(oam), 4)
                              if oam[index] or oam[index + 1]]
                print('  OAM %s' % (' | '.join(active_oam) or '(none)'))
                wram = bytes(pb.memory[address] for address in range(0xC000, 0xE000))
                credit_tiles = bytes(pb.memory[address]
                                     for address in range(0x8800, 0x8D80))
                populated = []
                for tile_index in range(0, len(credit_tiles), 16):
                    tile = credit_tiles[tile_index:tile_index + 16]
                    if any(tile):
                        matches = []
                        start = 0
                        while True:
                            found = wram.find(tile, start)
                            if found < 0:
                                break
                            matches.append('$%04X' % (0xC000 + found))
                            start = found + 1
                        populated.append('%02X=%s@%s' %
                                         (0x80 + tile_index // 16,
                                          hashlib.sha1(tile).hexdigest()[:6],
                                          ','.join(matches) or '-'))
                print('  credit tiles %s' % ' '.join(populated))
            if frame >= 2400 and frame % sample_every == 0:
                image = pb.screen.image.copy().convert('RGB')
                digest = hashlib.sha1(image.tobytes()).hexdigest()[:8]
                captures.append((frame, pb.memory[0x4000], pb.register_file.PC,
                                 digest, image))
                if (captures_dir and capture_from <= frame and
                        (capture_to <= 0 or frame <= capture_to)):
                    os.makedirs(captures_dir, exist_ok=True)
                    image.resize((640, 576), Image.Resampling.NEAREST).save(
                        os.path.join(captures_dir, 'frame_%05d.png' % frame))
        pb.stop(save=False)

    if trace_decompress:
        last = None
        print('endingcreditscan: decompressor entries (frame bank source destination end)')
        for record in decompresses:
            if record[3] not in (0xC008, 0xC04A):
                continue
            signature = record[1:5]
            if signature != last:
                print('  f%-5d b%02X $%04X -> $%04X end-low=$%02X vram=$%04X stack=%s' %
                      (record[0], record[1], record[2], record[3], record[4],
                       record[5],
                       ','.join('$%04X' % value for value in record[6])))
                last = signature

    cell_w, cell_h = 160, 156
    cols = 5
    rows = (len(captures) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell_w, rows * cell_h), 'white')
    draw = ImageDraw.Draw(sheet)
    for index, (frame, bank, pc, digest, image) in enumerate(captures):
        x = index % cols * cell_w
        y = index // cols * cell_h
        sheet.paste(image, (x, y + 12))
        draw.text((x + 2, y + 1), 'f%d b%02X:%04X %s' %
                  (frame, bank, pc, digest), fill='black')
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    sheet.save(output)
    print('endingcreditscan: %d samples, frames 2400-%d; wrote %s'
          % (len(captures), frames - 1, output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--output', default=os.path.join(ROOT, 'build',
                                                         'ending_timeline.png'))
    parser.add_argument('--frames', type=int, default=36000)
    parser.add_argument('--advance-until', type=int, default=16000)
    parser.add_argument('--sample-every', type=int, default=120)
    parser.add_argument('--captures-dir')
    parser.add_argument('--capture-from', type=int, default=0)
    parser.add_argument('--capture-to', type=int, default=0)
    parser.add_argument('--trace-decompress', action='store_true')
    parser.add_argument('--inspect-frame', action='append', type=int, default=[])
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('endingcreditscan: missing %s' % path)
    run(args.rom, args.ram, args.output, args.frames, args.advance_until,
        args.sample_every, args.captures_dir, args.capture_from,
        args.capture_to, args.trace_decompress, tuple(args.inspect_frame))


if __name__ == '__main__':
    main()
