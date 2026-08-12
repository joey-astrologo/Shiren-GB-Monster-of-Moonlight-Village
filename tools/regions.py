#!/usr/bin/env python3
"""Shared map of what each part of the ROM *is*, so other tools can skip non-code.

Computed rather than hardcoded, so it stays correct as the table improves.
"""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import codec

BANKSZ = 0x4000

# TAKEN FROM `codec`, WHICH IS CANONICAL. NEVER RESTATE THIS SET HERE.
#
# It used to be a hand-written copy: `set(textdump.table())` plus a literal list of 24
# control bytes. `textdump.py` is the day-one exploratory decoder and its table never grew
# past kana, digits, space and `ー`; `codec.py` is the one that has been corrected all
# project long. So this file's idea of "a text byte" froze in week one while the real one
# gained the punctuation block, the bracket pairs, the second digit set, the Latin stat
# letters and 5 of the 17 control codes. 39 byte values in total.
#
# THAT COST 7.9 KB OF THE SCRIPT AND FIVE SESSIONS. The missing values are not rare ones:
# `<brk>` occurs 120 times in bank 14, `、` 110, `<cEC>` 47, plus `『』（）：［＋−`. They are
# only ~2% of a prose block -- and `script_regions` needs 97%, so ~2% of unrecognised bytes
# is precisely enough to hold a block of real dialogue under the bar. Every 128-byte block
# in bank 14's shop, its monster-house warning and the Kuyo Pass road picker scored 0.90 to
# 0.97 while being 48-71% kana. The region never opened; `extract.py`'s block walker only
# walks detected regions; and `immediate_refs` matches operands against strings already
# found, so it could not discover them either. The text was in a bank the extractor
# covered, between strings it had found, and nothing could reach it.
#
# The docstring above this said "Computed rather than hardcoded, so it stays correct as the
# table improves." It was computed -- from the wrong table.
CHARS = set(codec.CHARS) | set(codec.COMBINING)
CTRL = set(codec.CONTROL) | {codec.TERMINATOR}
TEXTBYTES = CHARS | CTRL

# Banks whose contents are bulk tile graphics (clear bitplane signatures).
GFX_BANKS = set(range(16, 25))

# Font block in bank 13 (syllabary starts 0x037600; glyphs extend either side).
FONT = (0x036800, 0x038000)


def script_regions(rom, blk=0x80, min_size=0x180, ok_thresh=0.97, kana_thresh=0.45):
    """Contiguous runs that read as script (characters + control codes, kana-dense).

    Two tests per block, and they are not the same kind of claim. `ok` is near-absolute --
    every byte decodes as script -- while `kana` is a density heuristic whose only job is
    to reject data that happens to decode. That asymmetry is what the bridge rule below
    rests on.
    """
    n = (len(rom) + blk - 1) // blk
    ok = [0.0] * n
    kana = [0.0] * n
    for i in range(n):
        b = rom[i * blk:(i + 1) * blk]
        if not b:
            break
        ok[i] = sum(1 for x in b if x in TEXTBYTES) / len(b)
        kana[i] = sum(1 for x in b if 0x0B <= x < 0x79) / len(b)

    good = [ok[i] >= ok_thresh and kana[i] >= kana_thresh for i in range(n)]

    # THE BRIDGE RULE. A block of PURE script bytes wedged between two text blocks is
    # text, whatever its kana density. Only `kana` may be waived, never `ok`.
    #
    # The shop is why this exists. Bank 14 opens with `てんしゅ「いらっしゃいませ」` at
    # $4031 and its blocks $4080 and $4100 pass both tests -- but $4180 is the price-entry
    # digit strip, ` <br> 0123456789▌▶<br> `, which is 100% script bytes and 34% kana. It
    # split the shop off into a 256-byte island, `min_size` discarded the island, and the
    # five lines that take a player's money were never extracted.
    #
    # Lowering `min_size` to 0x100 would also reach them, and it was measured: it buys
    # those 5 real strings and 8 pieces of junk, including a 198-byte kerning table at
    # 29:$50AF. Banks 27 and 29 are NOT in logicdiff's PURE_LOGIC list, so nothing in the
    # battery would have caught build.py rewriting them. The bridge buys the 5 and none of
    # the 8, because it only ever fills a gap that real text already brackets.
    for i in range(1, n - 1):
        if not good[i] and ok[i] >= ok_thresh and good[i - 1] and good[i + 1]:
            good[i] = True

    runs, cur = [], None
    for i in range(n):
        if good[i]:
            cur = [i * blk, (i + 1) * blk] if cur is None else [cur[0], (i + 1) * blk]
        else:
            if cur:
                runs.append(tuple(cur))
            cur = None
    if cur:
        runs.append(tuple(cur))
    return [r for r in runs if r[1] - r[0] >= min_size]


def excluded(rom, pad=0x80):
    """Byte ranges a code-scanner should not sweep. `pad` widens script edges, since
    block-granular detection clips the start and end of each run."""
    out = []
    for b in GFX_BANKS:
        out.append((b * BANKSZ, (b + 1) * BANKSZ))
    out.append(FONT)
    for s, e in script_regions(rom):
        out.append((max(0, s - pad), min(len(rom), e + pad)))
    out.sort()
    merged = []
    for s, e in out:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [tuple(m) for m in merged]


def build_mask(rom):
    """bytearray, 1 = skip this byte."""
    mask = bytearray(len(rom))
    for s, e in excluded(rom):
        for i in range(s, e):
            mask[i] = 1
    return mask


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    ex = excluded(rom)
    tot = sum(e - s for s, e in ex)
    print("%d excluded ranges, %d bytes (%.1f%% of ROM) -- gfx banks, font, script"
          % (len(ex), tot, tot / len(rom) * 100))
    print("Remaining sweepable (candidate code): %d bytes (%.1f KiB)"
          % (len(rom) - tot, (len(rom) - tot) / 1024))
