#!/usr/bin/env python3
"""Decode a mesen_rendertrace.lua log into readable text.

The Lua side deliberately dumps raw bytes rather than decoding in-emulator: the
character table lives in codec.py and must not be duplicated where it can drift.

Two kinds of line get decoded:

  TEXT   the $CF07 line buffer read at the composer. These are character codes,
         so codec.decode applies directly.
  CELLS  a horizontal run of tilemap entries. The mapping is the open question --
         FINDINGS.md says tilemap entries hold the raw code, but the font is also
         uploaded to VRAM $9000 in font-tile order, where index = code + 16. Both
         readings are printed; whichever produces Japanese is the right one, and
         that answer is itself the finding.

usage: decodetrace.py <logfile>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec

TEXT_RE = re.compile(r'^f(\d+)\s+TEXT\s+([0-9A-Fa-f ]+)$')
CELL_RE = re.compile(r'^f(\d+)\s+CELLS\s+\$([0-9A-Fa-f]{4}):(\d+)\s+([0-9A-Fa-f ]+)$')
EVT_RE = re.compile(r'^f(\d+)\s+((?:compose|struct|tilerun|fontload)=.*)$')


def dec(b):
    try:
        return codec.decode(bytes(b))
    except Exception as e:
        return f'<undecodable: {e}>'


def printable(s):
    """Fraction of characters that are kana, digits or ASCII -- a plausibility score."""
    if not s:
        return 0.0
    good = sum(1 for c in s
               if '぀' <= c <= 'ヿ' or c.isalnum() or c in ' 、。・「」！？…')
    return good / len(s)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
        line = line.strip()

        m = TEXT_RE.match(line)
        if m:
            f, hx = m.groups()
            b = bytes.fromhex(hx)
            print(f'f{f:<7} WINDOW  {dec(b)}')
            continue

        m = CELL_RE.match(line)
        if m:
            f, addr, n, hx = m.groups()
            b = bytes.fromhex(hx)
            raw = dec(b)
            # tile index = code + 16 for glyph DATA at $7680; if the tilemap indexes
            # the VRAM copy in the same order, subtract 16 to recover the code
            shifted = dec(bytes((x - 16) & 0xFF for x in b))
            layer = 'window' if int(addr, 16) >= 0x9C00 else 'bg'
            pr, ps = printable(raw), printable(shifted)
            best = raw if pr >= ps else shifted
            tag = 'raw' if best is raw else 'idx-16'
            print(f'f{f:<7} CELLS   ${addr} {layer:<6} n={n:<3} [{tag}] {best}')
            # Only flag a genuine tie -- both readings usually score above zero, so a
            # plain "both are plausible" test cries wolf on every line.
            if abs(pr - ps) < 0.15 and max(pr, ps) > 0.5:
                print(f'{"":14}  ambiguous -- raw={raw!r} idx-16={shifted!r}')
            continue

        m = EVT_RE.match(line)
        if m:
            print(f'f{m.group(1):<7} {m.group(2)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
