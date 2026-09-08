#!/usr/bin/env python3
"""Regress dialogue control arguments and text-pool/helper ownership boundaries."""
import argparse
from pathlib import Path

import build
import dte_rom
import gbemu
import pool
import structvwf


ROOT = Path(__file__).resolve().parents[1]


def control_arguments():
    # An existing item-award translation. A valid retrained pair used to absorb its
    # selector into $B8, while blind decompression still reported a perfect round-trip.
    table = [(build.EN_CODES[' '], build.EN_CODES['.'])]
    pair = bytes([dte_rom.DTE_CODES[0]])
    plain = build.encode_en('<name> received <cE3:00>.', 11) + b'\xff'
    base = (ROOT / 'build/base.gb').read_bytes()
    for bank in (11, 14):
        packed = dte_rom.compress(plain, table, bank=bank)
        where = packed.index(0xE3)
        cpu = gbemu.Cpu({0: base[:0x4000],
                         13: base[13 * 0x4000:14 * 0x4000]}, bank=13)
        cpu.ram[0x4800:0x4800 + len(packed)] = packed
        cpu.b, cpu.c = 0xC8, where + 1
        cpu.pc = 0x6942                 # native dialogue item-substitution handler
        for _ in range(8):
            if cpu.pc == 0x695E:        # entry to the native selector resolver
                break
            cpu.step()
        assert cpu.pc == 0x695E and cpu.a == 0, (
            'native E3 selector corrupted', bank, packed.hex(), cpu.a)
        assert dte_rom.expand_bytes(packed, table, bank=bank) == plain
        assert dte_rom.training_segments(b'\xe3\x00\x3f', bank=bank) == []
        assert dte_rom.expand_bytes(b'\xe3' + pair, table, bank=bank) != b'\xe3\x00\x3f', (
            'round-trip verifier hid a compressed control argument', bank)

        # Over-reading a zero-argument control can hide the next control and leave
        # ITS argument compressible. This checks adjacent controls, not just E3.
        for control in (0xE7, 0xF0):
            data = bytes([control, 0xE0, 0x00, 0x3F, 0xFF])
            assert dte_rom.compress(data, table, bank=bank) == data
            data = bytes([control, 0x00, 0x3F])
            assert dte_rom.compress(data, table, bank=bank) == bytes([control]) + pair

    # Message E3 has no selector, while E7/F0 each consume an argument there.
    assert dte_rom.compress(b'\xe3\x00\x3f', table, bank=13) == b'\xe3' + pair
    for control in (0xE7, 0xF0):
        data = bytes([control, 0x00, 0x3F])
        assert dte_rom.compress(data, table, bank=13) == data

    # Literal arguments may themselves equal a DTE code. They must never expand.
    for bank in (11, 13, 14):
        for argument in range(256):
            data = bytes([0xE0, argument, 0x00, 0x3F])
            packed = dte_rom.compress(data, table, bank=bank)
            assert packed == data[:2] + pair, (bank, argument, packed.hex())
            assert dte_rom.expand_bytes(packed, table, bank=bank) == data


def allocation_boundaries():
    # Public allocator API, valid 20-character / 120px rows, and plenty of index room.
    arena = pool.Pool()
    row = build.encode_en('A' * 20) + b'\xff'
    while not arena.data[structvwf.FEI_RESTORE_BANK]:
        record = arena.add(row)
    index = pool.record_entry(record) - arena.index_base
    address = arena.index[index] | arena.index[index + 1] << 8
    assert address >= structvwf.FEI_RESTORE_LIMIT, (
        'text overlaps Fay restore helper', hex(address))
    assert arena.index_at < 0x8000
    rom = pool._test_rom(arena)
    assert pool.record_text(record, rom) == row

    # Fill every available text window through _add_text so the smaller index does
    # not hide later-bank reservations. Expected windows come from the ownership map.
    origins = {37: 0x42A0, 38: 0x4200, 40: 0x4200, 41: 0x4110,
               46: 0x4400, 61: 0x42C0, 62: 0x5490, 60: 0x4700}
    limits = {53: 0x4100, 58: 0x4100, 59: 0x4100,
              60: 0x5000, 61: 0x7000, 62: 0x7000}
    windows = {bank: (origins.get(bank, 0x4100), limits.get(bank, 0x8000))
               for bank in pool.TEXT_BANKS}
    for text_org in (0x4100, 0x7FF0):
        arena = pool.Pool(text_org=text_org)
        initial = arena.capacity()
        expected = sum(max(0, hi - max(lo, text_org)) for lo, hi in windows.values())
        assert initial == expected, ('capacity includes reserved bytes', initial, expected)
        placed = []
        while True:
            try:
                bank, address = arena._add_text(b'\x01' * 17)
            except SystemExit:
                break
            lo, hi = windows[bank]
            assert max(lo, text_org) <= address and address + 17 <= hi, (bank, hex(address))
            placed.append((bank, address, 17))
        # Prove tiny remainders remain usable and the reported capacity is real.
        while True:
            try:
                bank, address = arena._add_text(b'\x02')
            except SystemExit:
                break
            lo, hi = windows[bank]
            assert max(lo, text_org) <= address < hi, (bank, hex(address))
            placed.append((bank, address, 1))
        assert sum(size for _, _, size in placed) == initial == arena.used()
        before = b'\xa5' * 0x100000
        after = arena.write(before)
        for bank, (lo, hi) in windows.items():
            offset = bank * 0x4000 - 0x4000
            assert after[offset + 0x4000:offset + lo] == before[offset + 0x4000:offset + lo]
            assert after[offset + hi:offset + 0x8000] == before[offset + hi:offset + 0x8000]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('controls', 'allocation'))
    args = parser.parse_args()
    checks = {'controls': control_arguments, 'allocation': allocation_boundaries}
    for name, check in checks.items():
        if args.case is None or args.case == name:
            check()
            print('romtextcheck: %s OK' % name)


if __name__ == '__main__':
    main()
