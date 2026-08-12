#!/usr/bin/env python3
"""Prove every identity-hidden item uses the translated shared Info literals.

Known items select the 157-pointer table at ``13:$554A`` with ``$CF7B`` bit 7. Every
unidentified appearance instead takes the other arm of ``13:$7E0D``, which returns the
body literal at ``13:$5537``. The category/topic index and page unit are deliberately
ignored on that arm. The separate name formatter selects the shared title literal at
``4:$5773``. This checks that title in place, then executes the built ROM's real ``13:$7E49`` staging
routine with representative extreme values for both selectors and checks the resulting
WRAM row byte-for-byte.

This is a semantic regression, not another font sample. ``menuglyphspill.py`` already
drives every admitted character through the item Info renderer plane-exact; this test
proves the identity-hidden branch supplies the intended English title/body pair for every
item category. ``identityhiddenspill.py`` adds the real menu-route and visible-plane proof.
"""
import argparse
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import gbemu                                                     # noqa: E402
import itemfix                                                   # noqa: E402
import dotfont                                                   # noqa: E402


BANKSZ = 0x4000
RENDER_ENTRY = 0x7E49
DEST = 0xC500
INDEX_SEL = 0xCF7A
PAGE_SEL = 0xCF7B
UNIT_SEL = 0xC6BC


def banks(rom):
    return {n: bytearray(rom[n * BANKSZ:(n + 1) * BANKSZ])
            for n in range(len(rom) // BANKSZ)}


def render(rom, topic, unit):
    cpu = gbemu.Cpu(banks(rom), bank=13)
    cpu.ram[INDEX_SEL - 0x8000] = topic
    cpu.ram[PAGE_SEL - 0x8000] = 0x00       # identity hidden: use $5537, not $554A
    cpu.ram[UNIT_SEL - 0x8000] = unit
    cpu.ram[DEST - 0x8000:DEST - 0x8000 + 120] = b'\x00' * 120
    cpu.de = DEST
    cpu.call(RENDER_ENTRY)
    staged = bytes(cpu.ram[DEST - 0x8000:DEST - 0x8000 + 20])
    return staged, cpu.de


def run(path):
    rom = open(path, 'rb').read()
    direct = 13 * BANKSZ + itemfix.UNIDENTIFIED_HELP_AT - BANKSZ
    expected_literal = itemfix.UNIDENTIFIED_HELP_EN + b'\xFF'
    got_literal = rom[direct:direct + len(expected_literal)]
    problems = []
    font = dotfont.load_approved()
    source_glyphs = len(itemfix.UNIDENTIFIED_HELP_EN)
    pixels = sum(font.advance_code(code) for code in itemfix.UNIDENTIFIED_HELP_EN)
    if source_glyphs > 21:
        problems.append('%d source glyphs exceed the item-Info guard of 21' % source_glyphs)
    if pixels > 144:
        problems.append('%dpx exceeds the item-Info row width of 144px' % pixels)

    title_at = 4 * BANKSZ + itemfix.UNIDENTIFIED_TITLE_AT - BANKSZ
    expected_title = itemfix.UNIDENTIFIED_TITLE_EN + b'\xFF'
    got_title = rom[title_at:title_at + len(expected_title)]
    if got_title != expected_title:
        problems.append('4:$5773 is %s, expected %s' %
                        (got_title.hex(' '), expected_title.hex(' ')))
    if got_literal != expected_literal:
        problems.append('13:$5537 is %s, expected %s' %
                        (got_literal.hex(' '), expected_literal.hex(' ')))

    # The hidden-identity arm ignores both selectors. Exercise zero, table-edge-like and
    # maximal values so a future refactor that accidentally indexes either becomes loud.
    cases = ((0, 0), (1, 1), (121, 3), (255, 255))
    expected_row = itemfix.UNIDENTIFIED_HELP_EN + b'\xFF\x00'
    for topic, unit in cases:
        staged, de = render(rom, topic, unit)
        if staged != expected_row:
            problems.append('topic %d unit %d staged %s, expected %s' %
                            (topic, unit, staged.hex(' '), expected_row.hex(' ')))
        if de != DEST + len(itemfix.UNIDENTIFIED_HELP_EN):
            problems.append('topic %d unit %d returned de=$%04X, expected $%04X' %
                            (topic, unit, de,
                             DEST + len(itemfix.UNIDENTIFIED_HELP_EN)))

    print('unidentifiedhelp: title `%s`; body `%s` = %d glyphs / %dpx; '
          '%d selector cases; %d problem(s)' %
          (itemfix.UNIDENTIFIED_TITLE_TEXT, itemfix.UNIDENTIFIED_HELP_TEXT,
           source_glyphs, pixels,
           len(cases), len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('unidentifiedhelp: failed')
    print('unidentifiedhelp: every identity-hidden category reaches the shared English '
          'Info title and body')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    args = parser.parse_args()
    run(args.rom)


if __name__ == '__main__':
    main()
