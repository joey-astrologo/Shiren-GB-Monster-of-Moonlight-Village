#!/usr/bin/env python3
"""Change the cartridge type (and optionally ROM size), then fix both checksums.

Why MBC3 and not MBC5, for this game specifically:

  The bank-switch routine at bank 0 $07A8 does `ld d,$3F` / `ld [de],a`, so every ROM
  bank write lands in $3F00-$3FFF. Confirmed live: 6137 writes, 100% of them in that
  page.

    MBC1  $2000-$3FFF is all ROM bank  -> works today
    MBC3  $2000-$3FFF is all ROM bank  -> works unchanged, 7 bits, up to 2 MB
    MBC5  $2000-$2FFF low 8, $3000-$3FFF is bank BIT 8  -> would break every switch

  The routine also writes swap(bank) to $40xx, which MBC3 sees as a RAM bank select.
  That is transient: the very next writes restore the real RAM bank from $FFC2 to
  $5000, with interrupts disabled throughout, so nothing observes the bogus value.

  The $7000 writes of 0 then 1 are MBC1's mode register. On MBC3 that address is the
  RTC latch, and cart type $13 has no RTC, so they are ignored.

usage: setmapper.py <rom> <out.gb> [--type 13] [--romsize N]
"""
import sys

TYPES = {
    0x00: 'ROM only', 0x01: 'MBC1', 0x02: 'MBC1+RAM', 0x03: 'MBC1+RAM+BATTERY',
    0x0F: 'MBC3+TIMER+BATTERY', 0x10: 'MBC3+TIMER+RAM+BATTERY', 0x11: 'MBC3',
    0x12: 'MBC3+RAM', 0x13: 'MBC3+RAM+BATTERY',
    0x19: 'MBC5', 0x1A: 'MBC5+RAM', 0x1B: 'MBC5+RAM+BATTERY',
}
RAM = {0: 'none', 1: '2KB', 2: '8KB', 3: '32KB (4 banks)', 4: '128KB', 5: '64KB'}
# max ROM banks each mapper can address
MAX_BANKS = {0x03: 32, 0x13: 128, 0x1B: 512}


def fix_checksums(buf):
    h = 0
    for i in range(0x134, 0x14D):
        h = (h - buf[i] - 1) & 0xFF
    buf[0x14D] = h
    buf[0x14E] = buf[0x14F] = 0
    g = sum(buf) & 0xFFFF
    buf[0x14E] = (g >> 8) & 0xFF
    buf[0x14F] = g & 0xFF
    return h, g


def main():
    a = sys.argv[1:]
    src, dst = a[0], a[1]
    new_type = int(a[a.index('--type') + 1], 16) if '--type' in a else 0x13
    buf = bytearray(open(src, 'rb').read())

    old_type = buf[0x147]
    rom_size = buf[0x148]
    banks = 2 << rom_size
    print("cart type : $%02X %-20s -> $%02X %s"
          % (old_type, TYPES.get(old_type, '?'), new_type, TYPES.get(new_type, '?')))
    print("ROM size  : $%02X = %d KiB, %d banks" % (rom_size, 32 << rom_size, banks))
    print("RAM size  : $%02X = %s" % (buf[0x149], RAM.get(buf[0x149], '?')))

    if '--romsize' in a:
        buf[0x148] = int(a[a.index('--romsize') + 1])
        banks = 2 << buf[0x148]
        print("ROM size  : set to $%02X = %d KiB, %d banks" % (buf[0x148], 32 << buf[0x148], banks))

    cap = MAX_BANKS.get(new_type)
    if cap and banks > cap:
        print("ERROR: %s addresses at most %d banks, ROM declares %d"
              % (TYPES[new_type], cap, banks))
        return 1
    if cap:
        print("headroom  : %s can address %d banks; using %d (%.0f%% free)"
              % (TYPES[new_type], cap, banks, 100 * (1 - banks / cap)))

    buf[0x147] = new_type
    h, g = fix_checksums(buf)
    open(dst, 'wb').write(bytes(buf))
    print("checksums : header $%02X, global $%04X" % (h, g))
    print("wrote %s (%d bytes)" % (dst, len(buf)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
