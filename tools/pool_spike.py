#!/usr/bin/env python3
"""Prove the redirect on a real string: put natural English where 190 bytes never fit.

`14:$5047` is the innkeeper's wake-up speech, 190 bytes of Japanese and an in-place
string, so today's English is the abbreviated version Joey objected to:

    Innkeeper: You're / awake! You were / crying out so.

This writes the speech as ordinary English -- whatever length it comes out at -- into the
pool bank, leaves a 4-byte redirect record at `14:$5047`, and reports the ratio. The point
is not the prose; it is that the byte count stops being a constraint the prose has to obey.

    pool_spike.py build/shiren_en.gb build/pool_spike.gb
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec                                                    # noqa: E402
import build as build_py                                        # noqa: E402
import pool                                                     # noqa: E402
import dte_rom                                                  # noqa: E402

TARGET = '14:$5047'
TARGET_BANK, TARGET_ADDR, TARGET_BYTES = 14, 0x5047, 190

# Historical redirect fixture, authored to the original 18-cell control and therefore
# safely inside today's 30-glyph/144px Dot contract. Nothing is fitted to a byte count.
NATURAL = (
    "Innkeeper: Ah, you<br> are awake at last!<br> You were crying<end><brk>"
    " out so terribly in<br> your sleep. I was<br> worried sick.<end><brk>"
    "Where are you? Why,<br> this is Moonlight<br> Village, dear.<end><brk>"
    "You were set upon<br> by monsters up at<br> Kuyo Pass, were<end><brk>"
    " you not? When your<br> strength gives out<br> up there, you get<end><brk>"
    " thrown out down<br> here, and no<br> mistake.<end><brk>"
    "Anyway, you ought<br> to go and thank<br> Keyaki. She has<end><brk>"
    " been nursing you<br> this whole time.<end>"
)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    rom = open(src, 'rb').read()

    rom, info = pool.install(rom)

    blob = build_py.encode_en(NATURAL) + bytes([codec.TERMINATOR])

    # The composer expands DTE on EVERY line it copies, with no gate -- so a raw byte in
    # the code space would be read as a pair and draw two characters. Pool text is
    # ordinary composer input and has to respect that exactly like in-place text does.
    codes = set(dte_rom.DTE_CODES)
    clash = sorted({b for b in blob if b in codes})
    if clash:
        raise SystemExit('pool text contains DTE codes: %s'
                         % ' '.join('$%02X' % b for b in clash))

    p = pool.Pool()
    record = p.add(blob)
    rom = bytearray(p.write(rom))

    off = TARGET_BANK * 0x4000 + TARGET_ADDR - 0x4000
    was = bytes(rom[off:off + pool.RECORD_LEN])
    rom[off:off + pool.RECORD_LEN] = record
    open(dst, 'wb').write(bytes(rom))

    stored = record[1] | record[2] << 8
    print('%s: %d bytes of Japanese, in-place budget %d'
          % (TARGET, TARGET_BYTES, TARGET_BYTES))
    print('natural English: %d bytes = %.2fx -- would NOT have fitted'
          % (len(blob), len(blob) / TARGET_BYTES))
    print('record at %s: %s (was %s)' % (TARGET, record.hex(' '), was.hex(' ')))
    print('  -> stored pointer $%04X, tag (%d,%d)'
          % (stored, (stored >> 15) & 1, (stored >> 14) & 1))
    print(p.report())
    print('wrote', dst)


if __name__ == '__main__':
    main()
