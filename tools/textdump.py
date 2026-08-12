#!/usr/bin/env python3
"""Decode ROM bytes as game text using the font-derived table.

usage: textdump.py <rom> <hex-offset> <length> [--base N] [--raw]
"""
import sys

BASE = -16   # code = font_tile_index + BASE

ORDER = {}
ORDER[16] = ' '
for i, c in enumerate('0123456789'):
    ORDER[17 + i] = c
for i, c in enumerate('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'):
    ORDER[27 + i] = c
for i, c in enumerate('ぁぃぅぇぉゃゅょっ'):
    ORDER[73 + i] = c
for i, c in enumerate('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'):
    ORDER[82 + i] = c
for i, c in enumerate('ァィゥェォッャュョ'):
    ORDER[128 + i] = c

# Verified against real strings rather than read off the font grid:
#   0x79 dakuten / 0x7A handakuten both COMBINE with the preceding kana
#   (て+79 -> で in うでわ; ふ+7A -> ぷ in まんぷく)
COMBINING = {0x79: '゙', 0x7A: '゚'}   # combining ゛ / ゜
EXTRA = {0x7B: 'ー', 0xFF: '\n'}


def table(base=BASE):
    t = {i + base: c for i, c in ORDER.items()}
    t.update(EXTRA)
    return t


def decode(data, base=BASE):
    t = table(base)
    out = []
    for b in data:
        if b in COMBINING:
            out.append(COMBINING[b])       # attaches to the kana just emitted
            continue
        c = t.get(b)
        out.append(c if c is not None else '{%02X}' % b)
    return ''.join(out)


def is_text_byte(b, base=BASE):
    return b in table(base) or b in COMBINING


def main():
    a = sys.argv[1:]
    rom = open(a[0], 'rb').read()
    off, ln = int(a[1], 16), int(a[2], 16)
    base = int(a[a.index('--base') + 1]) if '--base' in a else BASE
    data = rom[off:off + ln]
    W = 24
    for i in range(0, len(data), W):
        chunk = data[i:i + W]
        print("%06X  %-*s  %s" % (off + i, W * 3, chunk.hex(' '), decode(chunk, base)))


if __name__ == '__main__':
    main()
