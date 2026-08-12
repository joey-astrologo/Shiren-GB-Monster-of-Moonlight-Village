#!/usr/bin/env python3
"""Locate 16-bit little-endian string pointer tables.

Two things this has to get right, both of which an earlier version got wrong:

* CROSS-BANK. A table does not have to live in the same bank as its strings -- the
  trap-message table in bank 6 points into bank 13. Resolving pointers only against
  the containing bank made ~45% of strings look unreferenced.

* ALIGNMENT. Scanning forward and accepting the first offset that yields "enough"
  entries can lock onto a position one byte off and clip the table. The weapons table
  read as 145 entries at $4537 when the true table is 156 entries at $4539. Always
  take the LONGEST run, never the first acceptable one.

usage: findtables.py <rom> [--min N] [--verbose]
"""
import sys, os, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec

BANKSZ = 0x4000
TERM = codec.TERMINATOR
# Must come from codec, which is the canonical table. An earlier version imported this
# from textdump, which predates the punctuation and control-code work -- dialogue then
# scored 0.73-0.89 against the 0.9 threshold and silently truncated every long table
# (the 156-entry table at bank 13 $554C read as 14 entries).
VALID = set(codec.CHARS) | set(codec.COMBINING) | set(codec.CONTROL)


def bank_of(off):
    return off // BANKSZ


def addr_of(off):
    b = bank_of(off)
    return off % BANKSZ + (0x4000 if b else 0)


def string_at(rom, off, limit=520):
    # 520 matches extract.MAX_STRING. An earlier limit of 96 silently TRUNCATED any
    # table-sourced string longer than that -- the extracted text was a prefix of the
    # real one, so insertion would have written a short string over a long one.
    out = bytearray()
    while off < len(rom) and len(out) < limit and rom[off] != TERM:
        out.append(rom[off])
        off += 1
    return bytes(out)


def string_starts(rom, min_valid=0.9):
    """Offsets that begin a plausible string, i.e. sit just after a terminator."""
    starts = set()
    for i in range(1, len(rom)):
        if rom[i - 1] != TERM or rom[i] == TERM:
            continue
        s = string_at(rom, i)
        if len(s) < 2:
            continue
        if sum(1 for b in s if b in VALID) / len(s) >= min_valid:
            starts.add(i)
    return starts


def text_banks(starts, threshold=20):
    c = collections.Counter(bank_of(o) for o in starts)
    return sorted(b for b, n in c.items() if n >= threshold)


def plausible_start(rom, off, min_valid=0.9):
    """Looser test for the FIRST entry of a table.

    The first string of a block is not preceded by a terminator -- it simply follows
    whatever data comes before. Requiring `$FF` for every entry silently dropped those
    strings (e.g. bank 11 $5330, the first main-menu item, sits after a kana byte).
    """
    s = string_at(rom, off)
    if len(s) < 2:
        return False
    return sum(1 for b in s if b in VALID) / len(s) >= min_valid


def run_from(rom, pos, tbank, starts):
    """How many consecutive LE16 entries from pos resolve to string starts in tbank."""
    n, q = 0, pos
    limit = len(rom) - 1
    while q < limit:
        v = rom[q] | (rom[q + 1] << 8)
        if not (0x4000 <= v < 0x8000):
            break
        off = tbank * BANKSZ + (v - 0x4000)
        if off not in starts and not (n == 0 and plausible_start(rom, off)):
            break
        n += 1
        q += 2
    return n


def scan(rom, minlen=6):
    """-> list of dicts: {pos, target_bank, count}. Longest run wins; no overlaps."""
    starts = string_starts(rom)
    banks = text_banks(starts)
    found = []
    for tbank in banks:
        pos = 0
        limit = len(rom) - 1
        while pos < limit:
            n = run_from(rom, pos, tbank, starts)
            if n >= minlen:
                # take the best alignment in this neighbourhood, not the first hit
                best_pos, best_n = pos, n
                for back in range(1, 4):
                    if pos - back < 0:
                        break
                    m = run_from(rom, pos - back, tbank, starts)
                    if m > best_n:
                        best_pos, best_n = pos - back, m
                found.append({'pos': best_pos, 'target_bank': tbank, 'count': best_n})
                pos = best_pos + best_n * 2
            else:
                pos += 1
    # drop overlaps, keeping the longer table
    found.sort(key=lambda t: (-t['count'], t['pos']))
    taken, out = [], []
    for t in found:
        a, b = t['pos'], t['pos'] + t['count'] * 2
        if any(a < y and x < b for x, y in taken):
            continue
        taken.append((a, b))
        out.append(t)
    out.sort(key=lambda t: t['pos'])
    return out


def entries(rom, t):
    """-> list of (ptr_offset, pointer, string_offset)."""
    out = []
    for i in range(t['count']):
        p = t['pos'] + i * 2
        v = rom[p] | (rom[p + 1] << 8)
        out.append((p, v, t['target_bank'] * BANKSZ + (v - 0x4000)))
    return out


def main():
    a = sys.argv[1:]
    rom = open(a[0], 'rb').read()
    minlen = int(a[a.index('--min') + 1]) if '--min' in a else 6
    verbose = '--verbose' in a
    from textdump import decode

    tabs = scan(rom, minlen)
    total = 0
    print("Pointer tables (>= %d entries), longest-run and cross-bank aware:\n" % minlen)
    for t in tabs:
        total += t['count']
        ents = entries(rom, t)
        same = 'same bank' if bank_of(t['pos']) == t['target_bank'] else \
               'CROSS-BANK -> b%d' % t['target_bank']
        print("  b%-2d $%04X (0x%06X)  %4d entries  %-16s  %s"
              % (bank_of(t['pos']), addr_of(t['pos']), t['pos'], t['count'], same,
                 decode(string_at(rom, ents[0][2]))[:30]))
        if verbose:
            for k, (_, v, off) in enumerate(ents[:5]):
                print("        [%3d] $%04X -> 0x%06X  %s"
                      % (k, v, off, decode(string_at(rom, off))[:40]))
    print("\n%d tables, %d pointer entries" % (len(tabs), total))
    cross = sum(1 for t in tabs if bank_of(t['pos']) != t['target_bank'])
    print("%d of them are cross-bank (invisible to the old scanner)" % cross)


if __name__ == '__main__':
    main()
