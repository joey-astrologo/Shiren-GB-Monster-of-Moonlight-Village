#!/usr/bin/env python3
"""Run each relocatable trampoline in the BUILT rom and compare it with the loop it replaced.

A reference check proves a record names the right text. It does not prove the patched ROM
DELIVERS that text: the trampoline, the far call, the stub table, the text-bank reader and
the mode all sit between the record and the destination buffer, and every one of them can
be wrong in a way that reads back perfectly on disk.

So this runs the real bytes. For every redirected string it executes the trampoline under
tools/gbemu.py with `hl` pointing at the record, then executes the ORIGINAL six-or-nine-byte
loop against the untouched Japanese ROM, and asserts the two produce the same destination
bytes and the same advanced `de`. Anything the redirect does differently -- one byte more,
one byte fewer, a clobbered register -- shows up here rather than as a message that never
ends.

    reloc_verify.py build/shiren_en.gb <base.gb>

COVERAGE SHRINKS AS TRANSLATION GROWS, and that is not a fault -- it is the reference.
A translated string has no Japanese to compare against, so it is skipped and counted.
The glossary alone took bank 11 from 21 comparable reads to 6. This verifies the
MECHANISM, not the text, so run it against a build with as little translated as possible
when you want real coverage:

    python3 tools/build.py build/_base_expanded.gb script/en.tsv /tmp/raw.gb --no-glossary
    python3 tools/reloc_verify.py /tmp/raw.gb build/base.gb        # 21 reads, 0 mismatches

(Not an EMPTY translation file: box 12's rows are unevenly spaced in Japanese and the
build refuses before it gets here. en.tsv minus the glossary is the least-translated ROM
this pipeline actually produces.)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm                                                    # noqa: E402
import gbemu                                                    # noqa: E402
import pool as textpool                                         # noqa: E402

BANKSZ = 0x4000
DEST = 0xC500                   # a scratch destination, well clear of anything the ROM uses


def _banks(rom):
    return {n: bytearray(rom[n * BANKSZ:(n + 1) * BANKSZ]) for n in range(len(rom) // BANKSZ)}


def run_tramp(rom, bank, at, addr, size):
    """Execute the patched site with hl = `addr`. -> (destination bytes, de, bc).

    A `ret` is planted where the site falls through to, in both this and the reference
    below, because these loops are fragments inside a routine whose prologue has already
    pushed -- `11:$51F0` is followed by `pop hl / pop bc / pop af`. Stopping at the same
    byte in both is what makes the two runs comparable.
    """
    banks = _banks(rom)
    banks[bank][at - BANKSZ + size] = 0xC9
    cpu = gbemu.Cpu(banks, bank=bank)
    cpu.h, cpu.l = addr >> 8, addr & 0xFF
    cpu.de = DEST
    cpu.b, cpu.c = 0x12, 0x34               # bc must come back untouched
    cpu.call(at)
    n = cpu.de - DEST
    return bytes(cpu.ram[DEST - 0x8000:DEST - 0x8000 + n]), cpu.de, (cpu.b << 8) | cpu.c


def run_original(base, bank, at, addr, size):
    """Execute the ORIGINAL loop from the untouched ROM, same entry conditions."""
    banks = _banks(base)
    banks[bank][at - BANKSZ + size] = 0xC9
    cpu = gbemu.Cpu(banks, bank=bank)
    cpu.h, cpu.l = addr >> 8, addr & 0xFF
    cpu.de = DEST
    cpu.b, cpu.c = 0x12, 0x34
    cpu.call(at)
    n = cpu.de - DEST
    return bytes(cpu.ram[DEST - 0x8000:DEST - 0x8000 + n]), cpu.de, (cpu.b << 8) | cpu.c


RENDER_ENTRY = 0x7E49           # the routine 13:$7E4C's hook sits inside
INDEX_SEL, PAGE_SEL, UNIT_SEL = 0xCF7A, 0xCF7B, 0xC6BC


def record_text(rom, bank, ptr, lines):
    """-> the pool text the first `lines` records at `bank:ptr` name, concatenated.

    Used to tell a REDIRECT apart from a TRANSLATION. The reference run below reads the
    Japanese out of the untouched ROM, so it can only be compared against a redirect that
    carries the same bytes; once a redirected string is translated the two differ ON
    PURPOSE, and comparing them would report the translation as a fault.

    `lines` is not a safety margin, it is the whole correctness of this walk: redirected
    strings sit back to back, so a run that stopped at "the next byte is not a marker"
    would read straight on into the following string's records and never terminate at the
    right place. The count comes from the ORIGINAL string, which is what the run mirrors.
    """
    out = bytearray()
    off = bank * BANKSZ + ptr - BANKSZ
    for _ in range(lines):
        if off + textpool.RECORD_LEN > len(rom) or rom[off] != textpool.MARK:
            break
        entry = rom[off + 1] | rom[off + 2] << 8
        e = textpool.INDEX_BANK * BANKSZ + entry - BANKSZ
        at = rom[e + 2] * BANKSZ + (rom[e] | rom[e + 1] << 8) - BANKSZ
        while at < len(rom):
            out.append(rom[at])
            if rom[at] in textpool.TERMINATORS:
                break
            at += 1
        off += textpool.RECORD_LEN
    return bytes(out)


def run_render(rom, index, unit):
    """Run 13:$7E49 exactly as `4:$49BC` does: 120 zeroed bytes at [de], index in $CF7A.

    This is the whole routine and not just the hooked site, because the hook replaces a
    `call` in the middle of it -- the trampoline resolves and renders, and then $7E51,
    which was NOT replaced, still has to run once and write the destination terminator.
    Only entering at the top exercises that handshake.
    """
    banks = _banks(rom)
    cpu = gbemu.Cpu(banks, bank=13)
    cpu.ram[INDEX_SEL - 0x8000] = index & 0xFF
    cpu.ram[PAGE_SEL - 0x8000] = 0x80           # bit 7: read table $554A, not $5537
    cpu.ram[UNIT_SEL - 0x8000] = unit
    cpu.ram[DEST - 0x8000:DEST - 0x8000 + 120] = b'\x00' * 120
    cpu.de = DEST
    cpu.call(RENDER_ENTRY)
    return bytes(cpu.ram[DEST - 0x8000:DEST - 0x8000 + (cpu.de - DEST)]), cpu.de


def check_render(rom, base, strings, table, verbose):
    """Compare the hooked 13:$7E49 with the untouched one, unit by unit."""
    bad = checked = skipped = 0
    for r in strings:
        for ref in r['refs']:
            if ref.get('table') != table:
                continue
            ptr = rom[ref['operand_at']] | rom[ref['operand_at'] + 1] << 8
            if rom[13 * BANKSZ + ptr - BANKSZ] != textpool.MARK:
                continue                        # not redirected: nothing to check here
            # build.py redirects `final + TERMINATOR`, so an UNtranslated string's pool
            # text is its Japanese plus one $FF -- that is the shape to compare against.
            jp = base[r['offset']:r['offset'] + r['bytes']]
            want_pool = jp + bytes([0xFF])
            if record_text(rom, 13, ptr, len(textpool.split_lines(want_pool))) != want_pool:
                skipped += 1                    # translated, so the reference cannot match
                continue
            index = (ref['operand_at'] - ref['table']) // 2
            units = sum(1 for b in jp if b in (0xEE, 0xFF)) or 1
            for unit in range(units):
                got, want = run_render(rom, index, unit), run_render(base, index, unit)
                checked += 1
                if got != want:
                    bad += 1
                    if bad <= 8:
                        print('MISMATCH 13:$7E49 %s unit %d (index %d)'
                              % (r['loc'], unit, index))
                        print('   redirect: de=%04X %s' % (got[1], got[0].hex()))
                        print('   original: de=%04X %s' % (want[1], want[0].hex()))
            break
    if verbose or skipped:
        print('reloc_verify: 13:$7E49 rendered %d unit(s); %d string(s) skipped as '
              'translated (no Japanese reference to compare against)' % (checked, skipped))
    return bad, checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('base', help='the untouched Japanese ROM, for the reference loop')
    ap.add_argument('--script', default='script/script.json')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    rom = open(a.rom, 'rb').read()
    base = open(a.base, 'rb').read()
    strings = json.load(open(a.script, encoding='utf-8'))['strings']
    by_bank = {}
    for r in strings:
        by_bank.setdefault(r['bank'], []).append(r)

    bad = checked = skipped = 0
    for bank, at, size, mode, what in textpool.RELOC_SITES:
        if mode is None:
            continue            # 13:$407E replaces a call, not a loop: no reference loop
        if mode == textpool.MODE_RENDER:
            # 13:$7E4C also replaces a call, but its routine has a real entry point that
            # can be driven, so this one IS checkable -- see check_render.
            n, c = check_render(rom, base, by_bank.get(13, []),
                                textpool.RENDER_TABLE, a.verbose)
            bad += n
            checked += c
            continue
        # Every address in this bank that now holds a record, plus a plain string as a
        # control -- the plain arm has to keep behaving too.
        for r in by_bank.get(bank, []):
            for ref in r['refs']:
                ptr = rom[ref['operand_at']] | rom[ref['operand_at'] + 1] << 8
                off = bank * BANKSZ + (ptr - BANKSZ)
                if rom[off] != textpool.MARK:
                    continue
                # The reference run reads the JAPANESE out of the untouched ROM, so a
                # translated string differs from it ON PURPOSE. check_render has said so
                # since it was written; this arm did not, and it went unnoticed only
                # because bank 11 had almost nothing translated. The glossary landed 391
                # names into it at once and the tool reported 396 mismatches on a build
                # whose --no-glossary control was clean -- which is worse than useless,
                # because a real redirect fault would have been the 397th line.
                jp = base[r['offset']:r['offset'] + r['bytes']]
                want_pool = jp + bytes([0xFF])
                if record_text(rom, bank, ptr,
                               len(textpool.split_lines(want_pool))) != want_pool:
                    skipped += 1
                    break
                got = run_tramp(rom, bank, at, ptr, size)
                want = run_original(base, bank, at, r['offset'] % BANKSZ + BANKSZ,
                                    size)
                checked += 1
                if got[0] != want[0] or got[1] != want[1] or got[2] != want[2]:
                    bad += 1
                    if bad <= 8:
                        print('MISMATCH %d:$%04X reading %s (%s)' % (bank, at, r['loc'], what))
                        print('   redirect: de=%04X bc=%04X %s'
                              % (got[1], got[2], got[0].hex()))
                        print('   original: de=%04X bc=%04X %s'
                              % (want[1], want[2], want[0].hex()))
                break
    print('reloc_verify: %d redirected read(s) checked, %d mismatch(es), %d skipped as '
          'translated (no Japanese reference to compare against)'
          % (checked, bad, skipped))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
