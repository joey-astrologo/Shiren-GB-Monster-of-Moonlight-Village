#!/usr/bin/env python3
"""Grow the ROM to a larger power-of-two size and update the size byte.

GB ROM size must be a power of two and the $148 byte must match the real file length,
or the cart is misread. New space is filled with $FF (blank flash) and left unused, so
an expanded build should behave EXACTLY like the original -- which makes it a clean
checkpoint: if it misbehaves, expansion itself is at fault, not the text work.

usage: expand.py <rom> <out.gb> [--size-code 5]
   size codes: 4 = 512 KiB (32 banks), 5 = 1 MiB (64), 6 = 2 MiB (128)
"""
import sys

SIZES = {4: (512, 32), 5: (1024, 64), 6: (2048, 128)}
MAX_BANKS = {0x03: 32, 0x13: 128, 0x1B: 512}
TYPES = {0x03: 'MBC1+RAM+BATTERY', 0x13: 'MBC3+RAM+BATTERY', 0x1B: 'MBC5+RAM+BATTERY'}


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
    code = int(a[a.index('--size-code') + 1]) if '--size-code' in a else 5
    buf = bytearray(open(src, 'rb').read())

    kib, banks = SIZES[code]
    target = kib * 1024
    cart = buf[0x147]
    print("cart type : $%02X %s" % (cart, TYPES.get(cart, '?')))
    if len(buf) > target:
        print("ERROR: ROM is already %d bytes, cannot shrink to %d" % (len(buf), target))
        return 1
    cap = MAX_BANKS.get(cart)
    if cap and banks > cap:
        print("ERROR: %s addresses at most %d banks, want %d" % (TYPES[cart], cap, banks))
        return 1

    old = len(buf)
    buf.extend(b'\xFF' * (target - old))
    buf[0x148] = code
    h, g = fix_checksums(buf)
    open(dst, 'wb').write(bytes(buf))

    print("size      : %d KiB (%d banks) -> %d KiB (%d banks)"
          % (old // 1024, old // 0x4000, kib, banks))
    print("added     : %d KiB of blank space, banks %d-%d"
          % ((target - old) // 1024, old // 0x4000, banks - 1))
    print("checksums : header $%02X, global $%04X" % (h, g))
    print("wrote %s" % dst)
    print("\nNew banks are unused, so this should play identically to the original.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
