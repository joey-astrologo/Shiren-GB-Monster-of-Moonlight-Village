#!/usr/bin/env python3
"""Regress shop headings and every priced-Item row slot.

The native formatter always assigns three dynamically painted price tiles to an Item
row: `$D0-$D2` for row 0, then `$D3-$D5`, `$D6-$D8`, `$D9-$DB`, and `$DC-$DE` for rows
1-4. They are tile IDs, not text codes; the tile pixels hold prices up to the shop
calculation's five-digit cap. Joey's first Log-3 fixture exercises row-0 Strength Herb
at 500G. The second keeps Invincible Herb at 3000G on row 4, which proves both the row-4
slot and the widened shop-name staging contract: the native 13-letter name field used to
discard its final `rb` before VWF ran.
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm                                                # noqa: E402
import gbemu                                                # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES               # noqa: E402
from latinfont import EN_CODES                              # noqa: E402
import itemfix                                              # noqa: E402
import lint_en                                              # noqa: E402
import menuspill                                            # noqa: E402
import menuvwf                                              # noqa: E402
import dotfont                                              # noqa: E402


RAM = 'saves/shiren_en_log3_shop.srm'
INVINCIBLE_RAM = 'saves/shiren_en_log3_invincible_herb_price.srm'
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ITEM_KEY = 0xC380
NAME = tuple(EN_CODES[ch] for ch in 'Strength Herb')
NAME_PADDING = bytes([0] * (menuvwf.SHOP_CONTENT_CELLS - 2 - len(NAME)))
RAW_PRICE = bytes((0xD0, 0xD1, 0xD2))
LONG_TEXT = 'Invincible Herb'
LONG_NAME = tuple(EN_CODES[ch] for ch in LONG_TEXT)
LONG_PADDING = bytes([0] * (menuvwf.SHOP_CONTENT_CELLS - 2 - len(LONG_NAME)))
LONG_PRICE = bytes((0xDC, 0xDD, 0xDE))
LONG_KEY = 0xC480
PRICE_SLOTS = tuple(bytes(range(base, base + 3)) for base in range(0xD0, 0xDF, 3))
PRICE_TABLE_BANK = 15
PRICE_TABLE_AT = 0x7854
PRICE_TABLE_ITEMS = 145
INVINCIBLE_ITEM = 66
MAX_BASE_PRICE = 62000
MAX_ORDINARY_BASE_PRICE = 50000
SHOP_BUY_CAP = 65000
SHOP_SELL_CAP = 32000
SHOP_NAME_PIXELS = 13 * 8
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 350: 'down', 400: 'down', 460: 'a', 530: 'a',
    2050: 'b', 2130: 'down', 2210: 'a',
    2440: 'a',
    2700: 'b', 2780: 'a',
}


def staged_row(pb, source, limit=32):
    """Read one variable-length staging row through its real terminator."""
    row = bytearray()
    for offset in range(limit):
        value = pb.memory[source + offset]
        row.append(value)
        if value == 0xFF:
            break
    return bytes(row)


def helper_problems(rom_path):
    rom = open(rom_path, 'rb').read()
    problems = []
    code, labels = gbasm.assemble(menuvwf._shop_suffix_src(), menuvwf.SHOP_SUFFIX_AT)
    start = menuvwf.SHOP_SUFFIX_BANK * 0x4000
    bank0 = rom[:0x4000]
    bank = rom[start:start + 0x4000]
    installed = bank[menuvwf.SHOP_SUFFIX_AT - 0x4000:
                     menuvwf.SHOP_SUFFIX_AT - 0x4000 + len(code)]
    if installed != code:
        problems.append('installed shop-price helper differs from asserted source')
        return problems
    for index, label in ((menuvwf.SHOP_SCAN_INDEX, 'scanhigh'),
                         (menuvwf.SHOP_COPY_INDEX, 'copyprice')):
        at = index - 1
        target = bank[at] | (bank[at + 1] << 8)
        if target != labels[label]:
            problems.append('bank %d far index $%02X points to $%04X, expected $%04X' %
                            (menuvwf.SHOP_SUFFIX_BANK, index, target, labels[label]))

    # The producer must retain the complete 18-glyph VWF source allowance before the
    # price suffix.  Verify every opcode as well as the shared immediate so an accidental
    # partial patch cannot silently change the clamp's control flow.
    for address, opcode in menuvwf.SHOP_CONTENT_PATCHES:
        at = 4 * 0x4000 + address - 0x4000
        got = rom[at:at + 2]
        want = bytes((opcode, menuvwf.SHOP_CONTENT_CELLS))
        if got != want:
            problems.append('shop content clamp at 4:$%04X is %s, expected %s' %
                            (address, got.hex(' '), want.hex(' ')))

    # Exercise the real producer clamp, not only its patched immediates. It must preserve
    # all 18 allowed name codes and pad shorter rows to the same bounded pre-price end.
    producer_bank = rom[4 * 0x4000:5 * 0x4000]
    source = 0xC220
    for name_length in (1, 13, 15, 16, 18):
        cpu = gbemu.Cpu({0: bank0, 4: producer_bank}, bank=4)
        name = bytes([EN_CODES['W']] * name_length)
        content = bytes((0, 0)) + name
        cpu.write(source - 1, 0xFF)
        for offset, value in enumerate(content):
            cpu.write(source + offset, value)
        cpu.de = source + len(content)
        cpu.bc, cpu.hl = 0xBEEF, 0xCAFE
        cpu.call(0x45B7)
        expected_end = source + menuvwf.SHOP_CONTENT_CELLS
        got = bytes(cpu.read(source + offset)
                    for offset in range(menuvwf.SHOP_CONTENT_CELLS))
        want = content + bytes(menuvwf.SHOP_CONTENT_CELLS - len(content))
        if cpu.de != expected_end or got != want:
            problems.append('%d-char shop producer ended at $%04X with %s, expected '
                            '$%04X / %s' %
                            (name_length, cpu.de, got.hex(' '), expected_end,
                             want.hex(' ')))
        if (cpu.bc, cpu.hl) != (0xBEEF, 0xCAFE):
            problems.append('%d-char shop producer clobbered BC/HL' % name_length)

    # Each physical item row owns one exact three-tile slot. Vary the preceding name
    # length independently; the scanner must not infer price location or size from it.
    for row, suffix in enumerate(PRICE_SLOTS):
        source = 0xC220
        for name_length in (1, 13, 15, 18):
            cpu = gbemu.Cpu({0: bank0, menuvwf.SHOP_SUFFIX_BANK: bank},
                            bank=menuvwf.SHOP_SUFFIX_BANK)
            for offset, value in enumerate(suffix + bytes([0xFF])):
                cpu.write(source + offset, value)
            cpu.a = suffix[0]
            cpu.b, cpu.c = (source + 1) >> 8, (source + 1) & 0xFF
            cpu.de = (row << 8) | name_length
            cpu.hl = 0xBEEF
            cpu.write(0xC1B1, 1)
            cpu.write(0xC0D0, 2)
            cpu.call(labels['scanhigh'])
            result_bc = (cpu.b << 8) | cpu.c
            if (not cpu.f & gbemu.C_FLAG or cpu.a != 0 or
                    result_bc != source + len(suffix) + 1):
                problems.append('row-%d price after %d-char name returned '
                                'A=$%02X BC=$%04X F=$%02X' %
                                (row, name_length, cpu.a, result_bc, cpu.f))
            if cpu.de != ((row << 8) | name_length) or cpu.hl != 0xBEEF:
                problems.append('row-%d price after %d-char name clobbered DE/HL' %
                                (row, name_length))

        cpu = gbemu.Cpu({0: bank0, menuvwf.SHOP_SUFFIX_BANK: bank},
                        bank=menuvwf.SHOP_SUFFIX_BANK)
        for offset, value in enumerate(suffix + bytes([0xFF])):
            cpu.write(source + offset, value)
        border = 0xC440
        cpu.write(0xC0E7, len(suffix))
        cpu.write(0xC0CC, (source + len(suffix) + 1) & 0xFF)
        cpu.write(0xC0CD, (source + len(suffix) + 1) >> 8)
        cpu.b, cpu.c = 0xB1, 0x23
        cpu.de, cpu.hl = 0xD456, border
        cpu.call(labels['copyprice'])
        got = bytes(cpu.read(border - len(suffix) + i) for i in range(len(suffix)))
        if got != suffix:
            problems.append('row-%d price copy emitted %s, expected %s' %
                            (row, got.hex(' '), suffix.hex(' ')))
        if ((cpu.b << 8) | cpu.c, cpu.de, cpu.hl) != (0xB123, 0xD456, border):
            problems.append('row-%d price copy clobbered BC/DE/HL' % row)

    # Wrong starts, short/long runs, and nonascending runs must all fall back.
    for row, malformed in ((0, (0xD1, 0xD2, 0xD3, 0xFF)),
                           (0, (0xD0, 0xD1, 0xFF)),
                           (0, (0xD0, 0xD1, 0xD2, 0xD3, 0xFF)),
                           (4, (0xDC, 0xDE, 0xDF, 0xFF))):
        cpu = gbemu.Cpu({0: bank0, menuvwf.SHOP_SUFFIX_BANK: bank},
                        bank=menuvwf.SHOP_SUFFIX_BANK)
        source = 0xC220
        for offset, value in enumerate(malformed):
            cpu.write(source + offset, value)
        cpu.a, cpu.d, cpu.e = malformed[0], row, 14
        cpu.b, cpu.c = (source + 1) >> 8, (source + 1) & 0xFF
        cpu.write(0xC1B1, 1)
        cpu.write(0xC0D0, 2)
        cpu.call(labels['scanhigh'])
        if cpu.f & gbemu.C_FLAG:
            problems.append('malformed shop suffix %s was accepted' %
                            bytes(malformed).hex(' '))
    return problems


def name_contract_problems():
    """Prove every ordinary runtime item variant fits beside a three-tile price."""
    font = dotfont.load_approved()
    items = [entry for entry in lint_en.load_glossary('script/glossary.tsv')
             if entry['cls'] == 'item']
    problems = []
    if len(items) != PRICE_TABLE_ITEMS:
        return ['item glossary has %d entries, expected %d' %
                (len(items), PRICE_TABLE_ITEMS)]
    variants = []
    for index, entry in enumerate(items):
        suffixes = ['']
        if index < 34:
            suffixes.extend(sign + str(value)
                            for sign in ('+', '-') for value in range(1, 100))
        elif lint_en.carries_counter(entry['en']):
            suffixes.extend('[%d]' % value for value in range(1, 100))
        for suffix in suffixes:
            text = entry['en'] + suffix
            variants.append(text)
            if len(text) > menuvwf.SHOP_CONTENT_CELLS - 2:
                problems.append('%r needs %d shop source cells, maximum is %d' %
                                (text, len(text), menuvwf.SHOP_CONTENT_CELLS - 2))
                continue
            padded = text + ' ' * (menuvwf.SHOP_CONTENT_CELLS - 2 - len(text))
            extent = font.text_extent(padded)
            if extent > SHOP_NAME_PIXELS:
                problems.append('%r paints %dpx after shop padding, maximum before '
                                'price is %dpx' % (text, extent, SHOP_NAME_PIXELS))
    if LONG_TEXT not in variants:
        problems.append('Invincible Herb is absent from the enumerated item variants')
    return problems


def literal_problems(rom_path):
    rom = open(rom_path, 'rb').read()
    problems = []
    at = 4 * 0x4000 + itemfix.SHOP_VALUE_AT - 0x4000
    if rom[at:at + len(itemfix.SHOP_VALUE_EN)] != itemfix.SHOP_VALUE_EN:
        problems.append('4:$4AFA does not contain the packed `Price`/`G` headings')
    at = 4 * 0x4000 + itemfix.SHOP_GITAN_POINTER_AT - 0x4000
    if rom[at:at + 3] != itemfix.SHOP_GITAN_POINTER_NEW:
        problems.append('4:$4AE0 does not select the repacked `G` heading')
    return problems


def price_contract_problems(rom_path):
    """Prove the ROM's base-price table and the two shop calculation clamps."""
    rom = open(rom_path, 'rb').read()
    problems = []
    table = PRICE_TABLE_BANK * 0x4000 + PRICE_TABLE_AT - 0x4000
    prices = []
    for item in range(PRICE_TABLE_ITEMS):
        at = table + item * 4
        prices.append((int.from_bytes(rom[at:at + 2], 'little'),
                       int.from_bytes(rom[at + 2:at + 4], 'little')))
    if prices[INVINCIBLE_ITEM] != (3000, 100):
        problems.append('Invincible Herb price pair is %r, expected (3000, 100)' %
                        (prices[INVINCIBLE_ITEM],))
    if max(buy for buy, _sell in prices) != MAX_BASE_PRICE:
        problems.append('base purchase-price maximum is not %d' % MAX_BASE_PRICE)
    if prices[32][0] != MAX_ORDINARY_BASE_PRICE:
        problems.append('Rasen Fuuma base price is %d, expected %d' %
                        (prices[32][0], MAX_ORDINARY_BASE_PRICE))

    bank = PRICE_TABLE_BANK * 0x4000
    buy_cap = bank + 0x767B - 0x4000
    sell_cap = bank + 0x7646 - 0x4000
    if rom[buy_cap:buy_cap + 3] != bytes((0x21, 0xE8, 0xFD)):
        problems.append('shop purchase-price clamp is not %d' % SHOP_BUY_CAP)
    if rom[sell_cap:sell_cap + 3] != bytes((0x21, 0x00, 0x7D)):
        problems.append('shop sale-price clamp is not %d' % SHOP_SELL_CAP)
    return problems


def synthetic_slot_problems(rom_path):
    """Render all five native price slots through the real Item path."""
    profile = menuspill.renderer_profile(rom_path)
    PyBoy = _import_pyboy()
    pb = PyBoy(rom_path, window='null')
    pb.set_emulation_speed(0)
    with open('saves/dungeon.state', 'rb') as state:
        pb.load_state(state)

    rows = (((EN_CODES['A'],), PRICE_SLOTS[0]),
            ((EN_CODES['B'],), PRICE_SLOTS[1]),
            ((EN_CODES['C'],), PRICE_SLOTS[2]),
            ((EN_CODES['D'],), PRICE_SLOTS[3]),
            (LONG_NAME, PRICE_SLOTS[4]))
    payload = b''.join(bytes((0, 0)) + bytes(name) + suffix + b'\xFF'
                       for name, suffix in rows)
    rewritten = [False]
    keys = {}

    def far_entry(_context=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        row = pb.register_file.D
        if shape != ITEM_SHAPE or not 0 <= row < 5:
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        if row == 0 and not rewritten[0] and source == menuspill.STAGING:
            for offset, value in enumerate(payload):
                pb.memory[menuspill.STAGING + offset] = value
            rewritten[0] = True
        if rewritten[0]:
            keys[row] = pb.register_file.HL

    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
    for frame in range(360):
        button = {60: 'b', 120: 'a'}.get(frame)
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()

    problems = []
    if not rewritten[0] or len(keys) != 5:
        problems.append('five-slot synthetic Item page rendered keys %r' % keys)
    for row, (name, suffix) in enumerate(rows):
        key = keys.get(row)
        if key is None:
            continue
        records = [record for record in menuspill.records(pb, profile)
                   if record[0] == key and record[3] == 2]
        if not records:
            problems.append('synthetic price slot %d fell back to fixed width' % row)
        if not menuspill.visible_row_matches(pb, profile, key, list(name), raw=2):
            problems.append('synthetic price slot %d has incorrect VWF planes' % row)
        shadow_price = bytes(pb.memory[key + 16:key + 19])
        bg = menuspill.BGMAP + key - menuspill.SHADOW
        bg_price = bytes(pb.memory[bg + 16:bg + 19])
        if shadow_price != suffix or bg_price != suffix:
            problems.append('slot-%d synthetic price shadow/BG is %s/%s, expected %s' %
                            (row, shadow_price.hex(' '), bg_price.hex(' '),
                             suffix.hex(' ')))
    pb.stop(save=False)
    return problems


def route_problems(rom_path, ram_path, png=None):
    profile = menuspill.renderer_profile(rom_path)
    problems = []
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='shopspill-') as tmp:
        run_rom = os.path.join(tmp, 'shop.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        staged = None

        def item_row(_context=None):
            nonlocal staged
            shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE or pb.register_file.D != 0:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if row[2:2 + len(NAME)] == bytes(NAME) and row[-1] == 0xFF:
                staged = row

        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        for frame in range(2910):
            button = BOOT.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame == 2300:
                top = bytes(pb.memory[0x9860:0x986A])
                want = bytes([0xB8]) + bytes(EN_CODES[ch] for ch in 'Price') + \
                    bytes([0xBC] * 3 + [0xB9])
                if top != want:
                    problems.append('Floor shop heading is %s, expected `Price` map %s' %
                                    (top.hex(' '), want.hex(' ')))
                cash = bytes(pb.memory[0x99A0:0x99AA])
                want = bytes([0xB8, EN_CODES['G']] + [0xBC] * 7 + [0xB9])
                if cash != want:
                    problems.append('Floor cash heading is %s, expected `G` map %s' %
                                    (cash.hex(' '), want.hex(' ')))

        if staged is None:
            problems.append('priced Strength Herb never reached the Item VWF hook')
        else:
            expected = (bytes((0, 0)) + bytes(NAME) + NAME_PADDING + RAW_PRICE +
                        bytes([0xFF]))
            if staged != expected:
                problems.append('priced row staged %s, expected %s' %
                                (staged.hex(' '), expected.hex(' ')))
        records = [record for record in menuspill.records(pb, profile)
                   if record[0] == ITEM_KEY and record[3] == 2]
        if not records:
            problems.append('priced Strength Herb has no raw=2 VWF allocation record')
        if not menuspill.visible_row_matches(pb, profile, ITEM_KEY,
                                             list(NAME) + list(NAME_PADDING), raw=2):
            problems.append('priced Strength Herb visible planes differ from composition')
        shadow_suffix = bytes(pb.memory[ITEM_KEY + 16:ITEM_KEY + 19])
        bg_suffix = bytes(pb.memory[0x9880 + 16:0x9880 + 19])
        if shadow_suffix != RAW_PRICE or bg_suffix != RAW_PRICE:
            problems.append('raw price suffix shadow/BG is %s/%s, expected %s' %
                            (shadow_suffix.hex(' '), bg_suffix.hex(' '),
                             RAW_PRICE.hex(' ')))
        invariant = menuspill.frame_invariant(pb, profile)
        if invariant:
            problems.append('settled Items screen has %d allocator invariant violation(s)'
                            % len(invariant))
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
    return problems


def invincible_route_problems(rom_path, ram_path, expected_price=3000, png=None):
    """Replay Joey's exact row-4 failure, optionally overriding its ROM-table price."""
    profile = menuspill.renderer_profile(rom_path)
    problems = []
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='shop-invincible-') as tmp:
        run_rom = os.path.join(tmp, 'shop.gb')
        shutil.copyfile(rom_path, run_rom)
        if expected_price != 3000:
            data = bytearray(open(run_rom, 'rb').read())
            table = PRICE_TABLE_BANK * 0x4000 + PRICE_TABLE_AT - 0x4000
            at = table + INVINCIBLE_ITEM * 4
            data[at:at + 2] = expected_price.to_bytes(2, 'little')
            with open(run_rom, 'wb') as out:
                out.write(data)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        staged = None
        observed_prices = []

        def item_row(_context=None):
            nonlocal staged
            shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE or pb.register_file.D != 4:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if row[2:2 + len(LONG_NAME)] == bytes(LONG_NAME) and row[-1] == 0xFF:
                staged = row

        def price_done(_context=None):
            if (pb.register_file.C == INVINCIBLE_ITEM and
                    pb.register_file.B & 0x7F == 3):
                observed_prices.append(pb.memory[0xD73C] |
                                       (pb.memory[0xD73D] << 8))

        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        pb.hook_register(PRICE_TABLE_BANK, 0x77C9, price_done, None)
        for frame in range(2910):
            button = BOOT.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        expected = (bytes((0, 0)) + bytes(LONG_NAME) + LONG_PADDING + LONG_PRICE +
                    bytes([0xFF]))
        if expected_price not in observed_prices:
            problems.append('native Invincible Herb formatter produced %r, expected %d' %
                            (observed_prices, expected_price))
        if staged is None:
            problems.append('%dG Invincible Herb never reached the Item VWF hook' %
                            expected_price)
        elif staged != expected:
            problems.append('Invincible Herb staged %s, expected %s' %
                            (staged.hex(' '), expected.hex(' ')))
        records = [record for record in menuspill.records(pb, profile)
                   if record[0] == LONG_KEY and record[3] == 2]
        if not records:
            problems.append('%dG Invincible Herb has no raw=2 VWF allocation record' %
                            expected_price)
        visible_codes = list(LONG_NAME) + list(LONG_PADDING)
        if not menuspill.visible_row_matches(pb, profile, LONG_KEY,
                                             visible_codes, raw=2):
            problems.append('%dG Invincible Herb visible planes differ from composition' %
                            expected_price)
        shadow_suffix = bytes(pb.memory[LONG_KEY + 16:LONG_KEY + 19])
        bg = menuspill.BGMAP + LONG_KEY - menuspill.SHADOW
        bg_suffix = bytes(pb.memory[bg + 16:bg + 19])
        if shadow_suffix != LONG_PRICE or bg_suffix != LONG_PRICE:
            problems.append('row-4 price slot shadow/BG is %s/%s, expected %s' %
                            (shadow_suffix.hex(' '), bg_suffix.hex(' '),
                             LONG_PRICE.hex(' ')))
        invariant = menuspill.frame_invariant(pb, profile)
        if invariant:
            problems.append('%dG Invincible Herb screen has %d allocator violation(s)' %
                            (expected_price, len(invariant)))
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--invincible-ram', default=INVINCIBLE_RAM)
    parser.add_argument('--png')
    parser.add_argument('--invincible-png')
    parser.add_argument('--max-png')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('shopspill: missing fixture %s' % args.ram)
    if not os.path.exists(args.invincible_ram):
        raise SystemExit('shopspill: missing fixture %s' % args.invincible_ram)
    problems = literal_problems(args.rom)
    problems.extend(name_contract_problems())
    problems.extend(price_contract_problems(args.rom))
    problems.extend(helper_problems(args.rom))
    problems.extend(synthetic_slot_problems(args.rom))
    problems.extend(route_problems(args.rom, args.ram, args.png))
    problems.extend(invincible_route_problems(args.rom, args.invincible_ram,
                                              3000, args.invincible_png))
    problems.extend(invincible_route_problems(args.rom, args.invincible_ram,
                                              SHOP_BUY_CAP, args.max_png))
    print('shopspill: Price/G; five D0-DE row slots; complete `%s`; '
          '500G row 0 + 3000G row 4 exact; '
          'controlled %dG maximum route exact; base max %d; %d problem(s)' %
          (LONG_TEXT, SHOP_BUY_CAP, MAX_BASE_PRICE, len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('shopspill: failed')


if __name__ == '__main__':
    main()
