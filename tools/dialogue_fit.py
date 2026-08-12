#!/usr/bin/env python3
"""Price natural English against the composer's real rules, per string and in aggregate.

This is the tool that answered "is there room for a proper translation, or does the budget
force machine-translation-grade text". The answer is measured rather than guessed, and the
measuring matters: an earlier note in HANDOFF.md put English at 1.8-2.0x of the Japanese
from general knowledge, and the real figure for this game's prose is 1.66x.

    dialogue_fit.py <natural.json> [--ranges max|current]

`natural.json` is {loc: "plain English"} -- written WITHOUT fitting. The tool applies the
layout a translator would otherwise do by hand (up to 30 staged Dot glyphs and 144 painted
pixels, `<br>`, three lines to a box, and the one-space continuation indent), then encodes,
compresses, and reports what each string would cost.

Hand-laying-out is exactly what to avoid when measuring: the TASK 2 sample was shaped by my
fitting rather than by what English costs, which is how it ended up unreadable.

IN-PLACE FITTING IS PER STRING. A string that comes in under budget cannot lend its slack
to one that comes in over, so the aggregate ratio flatters the result badly -- the sample
aggregates to 1.09x at the maximum code space while 12 of its 18 strings individually do
not fit. Read the per-string column, not the total.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import codec
import dte_rom
import build as B
import dialogue_preview as dialogue
import dotfont
from latinfont import EN_CODES

WIDTH = dialogue.WIDTH       # current Dot source stager; physical edge is separate
PIXELS = dialogue.LINE_PX
LINES_PER_BOX = 3


def layout(text, width=WIDTH, per_box=LINES_PER_BOX, font=None, pixels=PIXELS):
    """Plain English -> the token string the inserter takes. Word wrap, never mid-word.

    Production Dot text must satisfy both the source stager and painted screen edge. This
    storage-pricing helper therefore uses the same approved font rather than reviving the
    old 18/24 fixed-cell assumption.
    """
    font = dotfont.load_approved() if font is None else font
    words, lines, cur = text.split(), [], ''
    for w in words:
        indent = '' if not lines else ' '
        trial = (cur + ' ' + w).strip()
        staged = indent + trial
        if ((len(staged) > width or font.text_extent(staged) > pixels) and cur):
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    out = []
    for i, ln in enumerate(lines):
        out.append(('' if i == 0 else ' ') + ln)
        if i == len(lines) - 1:
            break
        out.append('<end><brk>' if (i + 1) % per_box == 0 else '<br>')
    return ''.join(out), lines


def max_ranges():
    """The widest three-range code space possible once NO Japanese remains.

    Three, not four: the expander's range test is generated from DTE_RANGES and bank 0's
    padding is EXACTLY 158 bytes, which three ranges fill. Codes are taken by MERGING.
    """
    used = (set(EN_CODES.values())
            | set(range(codec.CONTROL_MIN, codec.CONTROL_MAX + 1))
            | set(codec.COMBINING) | {codec.TERMINATOR})
    free = sorted(set(range(256)) - used)
    runs, s, p = [], None, None
    for v in free:
        if s is None:
            s = p = v
        elif v == p + 1:
            p = v
        else:
            runs.append((s, p))
            s = p = v
    runs.append((s, p))
    return tuple(sorted(sorted(runs, key=lambda t: t[0] - t[1])[:3]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('natural')
    ap.add_argument('--ranges', choices=('current', 'max'), default='current',
                    help="'max' prices the best case: every byte free because all "
                         "Japanese is gone. dte_ranges.py says what is safe TODAY.")
    args = ap.parse_args()

    saved = (dte_rom.DTE_RANGES, dte_rom.DTE_CODES)
    if args.ranges == 'max':
        dte_rom.DTE_RANGES = max_ranges()
        dte_rom.DTE_CODES = [c for lo, hi in dte_rom.DTE_RANGES
                             for c in range(lo, hi + 1)]
    try:
        tbl, _, st = dte_rom.encode_segments(dte_rom.training_corpus(),
                                             npairs=len(dte_rom.DTE_CODES))
        strings = {r['loc']: r for r in
                   json.load(open(os.path.join(ROOT, 'script/script.json'),
                                  encoding='utf-8'))['strings']}
        print('code space: %s = %d codes, corpus saving %.1f%%'
              % (' '.join('$%02X-$%02X' % t for t in dte_rom.DTE_RANGES),
                 len(dte_rom.DTE_CODES), st['pct']))
        print()
        print('%-11s %-5s %-5s %-5s %-6s %-8s %s'
              % ('loc', 'jp', 'raw', '+dte', 'ratio', 'placed', 'verdict'))
        jp_t = raw_t = pk_t = over = 0
        for loc, text in json.load(open(args.natural, encoding='utf-8')).items():
            r = strings.get(loc)
            if r is None:
                print('%-11s -- no such string' % loc)
                continue
            laid, lines = layout(text)
            raw = B.encode_en(laid)
            pk = dte_rom.compress(raw, tbl)
            if dte_rom.expand_bytes(pk, tbl) != raw:
                raise SystemExit('%s: compressed form does not expand back' % loc)
            jp = r['bytes']
            inplace = not r['refs'] or r.get('pin')
            fits = len(pk) <= jp
            jp_t += jp; raw_t += len(raw); pk_t += len(pk)
            if inplace and not fits:
                over += 1
            print('%-11s %-5d %-5d %-5d %-6.2f %-8s %s'
                  % (loc, jp, len(raw), len(pk), len(raw) / jp,
                     'inplace' if inplace else 'reloc',
                     'ok' if not inplace else
                     ('fits' if fits else 'OVER by %d' % (len(pk) - jp))))
        print()
        print('TOTAL  jp %d   raw %d (%.2fx)   +dte %d (%.2fx)'
              % (jp_t, raw_t, raw_t / jp_t, pk_t, pk_t / jp_t))
        print('%d in-place string(s) do NOT fit. In-place fitting is PER STRING -- the '
              'aggregate above cannot rescue them.' % over)
    finally:
        dte_rom.DTE_RANGES, dte_rom.DTE_CODES = saved


if __name__ == '__main__':
    main()
