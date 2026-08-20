"""Keep the item-menu page indicators inside a complete two-pixel top border.

The item box uses tile $BC for its horizontal edge, whose top stroke is two pixels
thick. The active/inactive page-indicator tiles replace four of those edge cells, but
their native graphics preserve only the first stroke row. The result is the visibly
half-height border above the green icon and three page dots.

Both graphics are dedicated to this indicator. Preserve every icon/dot pixel and add
only the missing second black row (both Game Boy bitplanes set).
"""

BANKSZ = 0x4000
BANK = 13
TILES = (
    (0x7CB0,
     bytes.fromhex('00 00 FF FF 00 00 00 00 00 00 18 18 18 18 00 00'),
     bytes.fromhex('00 00 FF FF FF FF 00 00 00 00 18 18 18 18 00 00')),
    (0x7CC0,
     bytes.fromhex('00 00 FF FF 00 00 18 18 3C 24 7E 42 3C 24 18 18'),
     bytes.fromhex('00 00 FF FF FF FF 18 18 3C 24 7E 42 3C 24 18 18')),
)


def _off(address):
    return BANK * BANKSZ + address - 0x4000


def install(buf, notes):
    for address, native, solid in TILES:
        at = _off(address)
        got = bytes(buf[at:at + len(native)])
        if got != native:
            raise SystemExit(
                'pageicon: expected native page-indicator tile at %d:$%04X, found %s' %
                (BANK, address, got.hex(' ')))
        buf[at:at + len(solid)] = solid
    notes.append('pageicon: item-page active/inactive tiles at 13:$7CB0/$7CC0 retain '
                 'the complete two-pixel box border')
