#!/usr/bin/env python3
"""Project DTE onto the real per-bank budgets and report the break-even point.

The question this answers is not "how much does DTE save" (dte_measure.py does
that) but "does it save enough, in every bank separately". Strings cannot cross
banks, so a global surplus is worthless if one bank is still over.

The output that matters is the last column: the English expansion ratio at
which each bank stops fitting. Compare it against how verbose we actually
intend to be -- a VWF build has no reason to abbreviate, so its ratio is
higher than a fixed-width build's.

usage: dte_project.py [--rate 0.347]
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Free filler in each bank, over and above the bytes the Japanese strings
# currently occupy. Derived from `docs/TRAPS.md`'s "Available" column minus the
# measured Japanese byte count; --use-filler stays OFF, so treat these as the
# only reclaimable space.
MIN_REAL = 100  # banks smaller than this are one-off strings, not a budget

# Banks 4 and 31 are 0: their old figures came from `docs/TRAPS.md`'s table, which was
# computed before the 2026-07-28 re-extraction. That table counted ~1.4 KiB of binary
# data in those two banks as script. Bank 4 went 686 -> 3 bytes and bank 31
# 1090 -> ~250, so any "spare" derived from the old baseline is meaningless.
EXTRA_FREE = {11: 613, 13: 361, 14: 207, 30: 15, 31: 0, 4: 0}

# Bank 13's kanji glyphs become dead weight once the script is Latin. Not
# counted below -- it is margin, not budget, until someone measures it.


def main():
    rate = 0.347  # plain DTE, 120 pairs, from dte_measure.py on the SNES corpus
    ratio = 1.46  # English bytes per Japanese byte, fixed-width abbreviated
    for i, a in enumerate(sys.argv):
        if a == '--rate':
            rate = float(sys.argv[i + 1])
        if a == '--ratio':
            ratio = float(sys.argv[i + 1])

    d = json.load(open(os.path.join(ROOT, 'script/script.json')))
    jp = collections.Counter()
    for s in d['strings']:
        jp[s['bank']] += s['bytes']

    print(f'DTE rate {rate:.1%}, English expansion {ratio:.2f}x\n')
    hdr = (f'{"bank":>5} {"jp":>7} {"avail":>7} {"raw en":>7} {"+DTE":>7} '
           f'{"slack":>7}  {"break-even ratio":>16}')
    print(hdr)
    print('-' * len(hdr))

    worst = None
    for b in sorted(jp, key=lambda k: -jp[k]):
        avail = jp[b] + EXTRA_FREE.get(b, 0)
        raw = jp[b] * ratio
        enc = raw * (1 - rate)
        slack = avail - enc
        # largest expansion ratio this bank can still absorb
        be = avail / (jp[b] * (1 - rate))
        flag = '' if slack >= 0 else '  OVER'
        print(f'{b:>5} {jp[b]:>7} {avail:>7} {raw:>7.0f} {enc:>7.0f} '
              f'{slack:>7.0f}  {be:>16.2f}{flag}')
        # Banks 3 and 6 hold 16 and 7 bytes -- one or two strings, and bank 3's
        # decode plainly as junk. Too small to plan around and trivially fixed
        # by hand, so they must not drive the headline.
        if jp[b] >= MIN_REAL and (worst is None or be < worst[1]):
            worst = (b, be)

    print(f'\ntightest real bank: {worst[0]} — fits English up to {worst[1]:.2f}x '
          f'at a {rate:.1%} DTE rate  (banks under {MIN_REAL} B ignored)')

    print('\nbreak-even DTE rate needed, by assumed English expansion:')
    print(f'{"ratio":>7} {"rate needed":>12}  {"tightest bank":>14}')
    for r in (1.40, 1.50, 1.60, 1.70, 1.80, 2.00):
        need = 0.0
        tb = None
        for b in jp:
            if jp[b] < MIN_REAL:
                continue
            avail = jp[b] + EXTRA_FREE.get(b, 0)
            n = 1 - avail / (jp[b] * r)
            if n > need:
                need, tb = n, b
        print(f'{r:>7.2f} {max(need,0):>11.1%}  {tb:>14}')


if __name__ == '__main__':
    main()
