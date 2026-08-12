#!/usr/bin/env python3
"""Latin 8x8 font for the English patch, written into the ROM's existing kana tiles.

An English script contains no kana, so the 46 hiragana + 46 katakana slots are free.
That means the alphabet costs ZERO extra ROM -- we overwrite tiles in place at
0x37680 + code*8 rather than growing the font. No expansion, no repointing.

Code page after patching:
    0x00        space          (unchanged)
    0x01-0x0A   digits 0-9     (unchanged)
    0x0B-0x24   A-Z
    0x25-0x3E   a-z
    0x3F-0x42   . , ' -
Everything from 0x7C up (?!()「」etc.) is left alone and still usable.

usage: latinfont.py <rom> [--preview out.png]
"""
import sys

FONT_BASE = 0x37680          # file offset of code 0x00, proven from `ld hl,$7680`
GLYPH_BYTES = 8

# 5x7 glyphs in an 8x8 cell. Descenders (g j p q y) sit one row higher so they fit.
G = {
    'A': ['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'B': ['####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.'],
    'C': ['.###.', '#...#', '#....', '#....', '#....', '#...#', '.###.'],
    'D': ['####.', '#...#', '#...#', '#...#', '#...#', '#...#', '####.'],
    'E': ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
    'F': ['#####', '#....', '#....', '####.', '#....', '#....', '#....'],
    'G': ['.###.', '#...#', '#....', '#.###', '#...#', '#...#', '.###.'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'I': ['.###.', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    'J': ['..###', '...#.', '...#.', '...#.', '...#.', '#..#.', '.##..'],
    'K': ['#...#', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'M': ['#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '#...#'],
    'N': ['#...#', '##..#', '#.#.#', '#..##', '#...#', '#...#', '#...#'],
    'O': ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    'Q': ['.###.', '#...#', '#...#', '#...#', '#.#.#', '#..#.', '.##.#'],
    'R': ['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#'],
    'S': ['.####', '#....', '#....', '.###.', '....#', '....#', '####.'],
    'T': ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'],
    'U': ['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'V': ['#...#', '#...#', '#...#', '#...#', '#...#', '.#.#.', '..#..'],
    'W': ['#...#', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#'],
    'X': ['#...#', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '#...#'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
    'Z': ['#####', '....#', '...#.', '..#..', '.#...', '#....', '#####'],

    'a': ['.....', '.....', '.###.', '....#', '.####', '#...#', '.####'],
    'b': ['#....', '#....', '####.', '#...#', '#...#', '#...#', '####.'],
    'c': ['.....', '.....', '.###.', '#....', '#....', '#....', '.###.'],
    'd': ['....#', '....#', '.####', '#...#', '#...#', '#...#', '.####'],
    'e': ['.....', '.....', '.###.', '#...#', '#####', '#....', '.###.'],
    'f': ['..##.', '.#...', '.#...', '####.', '.#...', '.#...', '.#...'],
    'g': ['.....', '.####', '#...#', '#...#', '.####', '....#', '.###.'],
    'h': ['#....', '#....', '####.', '#...#', '#...#', '#...#', '#...#'],
    'i': ['..#..', '.....', '.##..', '..#..', '..#..', '..#..', '.###.'],
    'j': ['...#.', '.....', '...#.', '...#.', '...#.', '#..#.', '.##..'],
    'k': ['#....', '#....', '#..#.', '#.#..', '##...', '#.#..', '#..#.'],
    'l': ['.##..', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    'm': ['.....', '.....', '##.#.', '#.#.#', '#.#.#', '#...#', '#...#'],
    'n': ['.....', '.....', '####.', '#...#', '#...#', '#...#', '#...#'],
    'o': ['.....', '.....', '.###.', '#...#', '#...#', '#...#', '.###.'],
    'p': ['.....', '####.', '#...#', '#...#', '####.', '#....', '#....'],
    'q': ['.....', '.####', '#...#', '#...#', '.####', '....#', '....#'],
    'r': ['.....', '.....', '#.##.', '##...', '#....', '#....', '#....'],
    's': ['.....', '.....', '.####', '#....', '.###.', '....#', '####.'],
    't': ['.#...', '.#...', '####.', '.#...', '.#...', '.#..#', '..##.'],
    'u': ['.....', '.....', '#...#', '#...#', '#...#', '#...#', '.####'],
    'v': ['.....', '.....', '#...#', '#...#', '#...#', '.#.#.', '..#..'],
    'w': ['.....', '.....', '#...#', '#...#', '#.#.#', '#.#.#', '.#.#.'],
    'x': ['.....', '.....', '#...#', '.#.#.', '..#..', '.#.#.', '#...#'],
    'y': ['.....', '#...#', '#...#', '#...#', '.####', '....#', '.###.'],
    'z': ['.....', '.....', '#####', '...#.', '..#..', '.#...', '#####'],

    '.': ['.....', '.....', '.....', '.....', '.....', '.##..', '.##..'],
    ',': ['.....', '.....', '.....', '.....', '.##..', '.##..', '.#...'],
    "'": ['.##..', '.##..', '.#...', '.....', '.....', '.....', '.....'],
    '-': ['.....', '.....', '.....', '#####', '.....', '.....', '.....'],

    # THE DIGITS AND PUNCTUATION ARE DRAWN HERE FOR VWF, and that is the only reason
    # they are here. The ROM's own glyphs for them are fine at fixed width and WRONG at a
    # 6px advance: measured out of the built ROM, digits ink columns 1..6 (six wide and
    # shifted a column right), `+` inks 0..6, `~` inks 0..7, and `( ) : !` are centred at
    # columns 3..4. A 6px pen would clip the first three and leave the rest floating a
    # pixel-and-a-half off their own advance. Every glyph below inks columns 0..4 only,
    # left-aligned, which is what the letters above already do.
    #
    # This is VISIBLE OUTSIDE THE COMPOSER. The tilemap paths draw from the same font
    # (that is why the menus are in Latin at all), so numbers on the status bar, in menus
    # and on the rankings board become left-aligned and a pixel narrower. It is a
    # deliberate cosmetic change and it wants Joey's eye, not a checker's.
    '0': ['.###.', '#...#', '#..##', '#.#.#', '##..#', '#...#', '.###.'],
    '1': ['..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    '2': ['.###.', '#...#', '....#', '...#.', '..#..', '.#...', '#####'],
    '3': ['#####', '...#.', '..##.', '....#', '....#', '#...#', '.###.'],
    '4': ['...#.', '..##.', '.#.#.', '#..#.', '#####', '...#.', '...#.'],
    '5': ['#####', '#....', '####.', '....#', '....#', '#...#', '.###.'],
    '6': ['..##.', '.#...', '#....', '####.', '#...#', '#...#', '.###.'],
    '7': ['#####', '....#', '...#.', '..#..', '.#...', '.#...', '.#...'],
    '8': ['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.'],
    '9': ['.###.', '#...#', '#...#', '.####', '....#', '...#.', '.##..'],

    '?': ['.###.', '#...#', '....#', '...#.', '..#..', '.....', '..#..'],
    '!': ['..#..', '..#..', '..#..', '..#..', '..#..', '.....', '..#..'],
    '(': ['...#.', '..#..', '.#...', '.#...', '.#...', '..#..', '...#.'],
    ')': ['.#...', '..#..', '...#.', '...#.', '...#.', '..#..', '.#...'],
    ':': ['.....', '..#..', '..#..', '.....', '..#..', '..#..', '.....'],
    '/': ['....#', '....#', '...#.', '..#..', '.#...', '#....', '#....'],
    '[': ['.###.', '.#...', '.#...', '.#...', '.#...', '.#...', '.###.'],
    ']': ['.###.', '...#.', '...#.', '...#.', '...#.', '...#.', '.###.'],
    '+': ['.....', '..#..', '..#..', '#####', '..#..', '..#..', '.....'],
    '~': ['.....', '.....', '.#..#', '#.#.#', '#..#.', '.....', '.....'],
}

# The widest column any glyph above may ink. The VWF pen advances 6px, so a glyph that
# reaches column 5 would touch its neighbour and one that reaches column 6 or 7 would be
# overwritten by it. Asserted at patch time rather than trusted.
MAX_INK_COL = 4

# char -> game code
EN_CODES = {}
for _i in range(26):
    EN_CODES[chr(ord('A') + _i)] = 0x0B + _i
    EN_CODES[chr(ord('a') + _i)] = 0x25 + _i
for _i, _c in enumerate(".,'-"):
    EN_CODES[_c] = 0x3F + _i
EN_CODES[' '] = 0x00
for _i in range(10):
    EN_CODES[str(_i)] = 0x01 + _i

# Punctuation that already exists in the ROM above 0x7C and is NOT overwritten by the
# patch -- free to reuse, no glyph work needed.
EN_CODES.update({
    '?': 0x80, '!': 0xB2, '(': 0x9E, ')': 0x9F, ':': 0xA0, '/': 0xB0,
    '[': 0x7E, ']': 0x7F, '+': 0x7C, '~': 0xAF,
})


def tile(ch):
    """-> 8 bytes, 1bpp, bit7 = leftmost pixel."""
    rows = G[ch]
    out = bytearray()
    for r in rows:
        b = 0
        for x, c in enumerate(r):
            if c == '#':
                b |= 0x80 >> x
        out.append(b)
    out.append(0)                     # 8th row blank (row spacing)
    assert len(out) == GLYPH_BYTES
    return bytes(out)


def ink_columns(glyph):
    """-> (leftmost, rightmost) inked column of an 8-byte 1bpp tile, or None if blank."""
    mask = 0
    for b in glyph:
        mask |= b
    cols = [7 - i for i in range(8) if mask >> i & 1]
    return (min(cols), max(cols)) if cols else None


def patch(rom):
    """-> new bytes with the Latin glyphs written over the kana tiles."""
    buf = bytearray(rom)
    for ch, code in EN_CODES.items():
        if ch not in G:
            continue                  # space only, now that the digits are drawn here too
        off = FONT_BASE + code * GLYPH_BYTES
        glyph = tile(ch)
        span = ink_columns(glyph)
        assert span is None or span[1] <= MAX_INK_COL, (
            '%r (code $%02X) inks column %d; the VWF pen is 6px so nothing may reach '
            'past column %d' % (ch, code, span[1], MAX_INK_COL))
        buf[off:off + GLYPH_BYTES] = glyph
    return bytes(buf)


def audit(rom):
    """-> [(ch, code, rightmost inked column)] for every English code that a 6px pen
    would clip. Reads the BUILT rom, so it catches a glyph the patch never wrote as well
    as one it wrote wrongly."""
    bad = []
    for ch, code in sorted(EN_CODES.items(), key=lambda kv: kv[1]):
        off = FONT_BASE + code * GLYPH_BYTES
        span = ink_columns(rom[off:off + GLYPH_BYTES])
        if span and span[1] > MAX_INK_COL:
            bad.append((ch, code, span[1]))
    return bad


def main():
    rom = open(sys.argv[1], 'rb').read()
    if '--audit' in sys.argv:
        bad = audit(rom)
        for ch, code, col in bad:
            print('  %-3r $%02X inks column %d' % (ch, code, col))
        print('%d glyph(s) too wide for a 6px pen' % len(bad))
        raise SystemExit(1 if bad else 0)
    out = patch(rom)
    changed = sum(1 for a, b in zip(rom, out) if a != b)
    print("patched %d glyphs, %d bytes changed" % (len(G), changed))
    if '--preview' in sys.argv:
        dest = sys.argv[sys.argv.index('--preview') + 1]
        tmp = dest + '.gb'
        open(tmp, 'wb').write(out)
        import subprocess, os
        lo = FONT_BASE + 0x0B * GLYPH_BYTES
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'tilepng.py'),
                        tmp, '%x' % lo, '56', dest, '--cols', '14', '--zoom', '6'], check=True)
        os.remove(tmp)


if __name__ == '__main__':
    main()
