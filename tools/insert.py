#!/usr/bin/env python3
"""Build a patched ROM: Latin font + English strings + fixed checksums.

Deliberately limited to SAME-OR-SHORTER replacements, padded with spaces to the exact
original byte length. That keeps every pointer valid, so this needs no repointing and
no ROM expansion -- the two hardest pieces of the project are not on the critical path
for proving the pipeline works.

usage: insert.py <rom> <translations.tsv> <out.gb>
       translations.tsv:  id <TAB> english
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec
from latinfont import EN_CODES, patch as patch_font


def encode_en(text):
    """English -> game bytes, using the post-patch code page."""
    out = bytearray()
    for ch in text:
        if ch not in EN_CODES:
            raise ValueError('no glyph for %r' % ch)
        out.append(EN_CODES[ch])
    return bytes(out)


COMBINING_BYTES = set(codec.COMBINING)


def glyph_width(data):
    """Screen cells a string occupies.

    NOT the same as len(data). Dakuten/handakuten are separate bytes that combine with
    the preceding kana, so they cost a byte but no cell -- confirmed by the game's own
    width routine at bank 13 $40DB, which skips the counter decrement when the next byte
    is $79/$7A. Sizing English against byte length instead of this over-estimates the
    available room and overflows the text box.
    """
    return sum(1 for b in data if b not in COMBINING_BYTES)


def fix_checksums(buf):
    """Header byte at $14D and 16-bit global at $14E-$14F. Both must be right or the
    boot ROM refuses to start on real hardware."""
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
    rom_path, tsv_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rom = open(rom_path, 'rb').read()
    manifest = json.load(open('script/script.json', encoding='utf-8'))
    by_id = {r['id']: r for r in manifest['strings']}

    trans = []
    with open(tsv_path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            sid, en = line.split('\t', 1)
            trans.append((int(sid), en))

    buf = bytearray(patch_font(rom))
    applied, skipped = 0, []
    for sid, en in trans:
        r = by_id.get(sid)
        if r is None:
            skipped.append((sid, en, 'no such id'))
            continue
        orig = bytes.fromhex(r['hex'])
        # Menu entries reserve byte 0 as a space for the selection cursor, which is
        # redrawn over that cell -- a letter placed there is destroyed.
        lead = orig[:1] == bytes([EN_CODES[' ']])
        text = (' ' if lead else '') + en
        try:
            data = encode_en(text)
        except ValueError as exc:
            skipped.append((sid, en, str(exc)))
            continue
        budget = glyph_width(orig)
        if len(data) > budget:
            skipped.append((sid, en, 'needs %d cells, box holds %d%s'
                            % (len(data), budget, ' (incl. cursor space)' if lead else '')))
            continue
        off = r['offset']
        # English is one byte per cell, so data never exceeds the original byte length.
        # Terminate right after the text; any bytes left over before the original
        # terminator are dead and unreachable, since every string here is reached by
        # its own pointer rather than by a sequential walk.
        buf[off:off + len(data)] = data
        buf[off + len(data)] = codec.TERMINATOR
        applied += 1

    h, g = fix_checksums(buf)
    open(out_path, 'wb').write(bytes(buf))

    print("applied %d/%d translations" % (applied, len(trans)))
    for sid, en, why in skipped:
        print("   SKIPPED id=%d %r : %s" % (sid, en, why))
    print("checksums fixed: header $%02X, global $%04X" % (h, g))
    print("size %d bytes (unchanged: %s)" % (len(buf), len(buf) == len(rom)))
    print("wrote %s" % out_path)

    # verify by decoding straight back out of the patched ROM
    print("\nverification -- reading the patched bytes back:")
    inv = {v: k for k, v in EN_CODES.items()}
    for sid, en in trans[:8]:
        r = by_id.get(sid)
        if not r:
            continue
        raw = buf[r['offset']:r['offset'] + r['bytes']]
        raw = raw.split(bytes([codec.TERMINATOR]))[0]      # stop at the terminator
        txt = ''.join(inv.get(b, '?') for b in raw)
        print("   id=%-5d %-11s %-14r %d cells (box holds %d)"
              % (sid, r['loc'], txt, len(raw), glyph_width(bytes.fromhex(r['hex']))))


if __name__ == '__main__':
    main()
