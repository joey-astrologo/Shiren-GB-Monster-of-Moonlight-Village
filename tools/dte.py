#!/usr/bin/env python3
"""Dual Tile Encoding / byte-pair compression for the script.

Two variants, both measured because they cost very different amounts of
renderer code:

  plain      a code expands to exactly two LITERAL characters. The expander is
             one table lookup that emits two bytes. Codes never nest, so the
             maximum possible saving is 50%.
  recursive  a code may expand to other codes (classic BPE). Compresses harder
             but the expander needs a small stack and a depth bound.

Pairs may never span a control code or a string boundary: a DTE byte is
expanded blind into the render buffer, so anything the renderer has to *act*
on has to stay a byte of its own. Segments passed in here are therefore
already split at those points.

The table built here is trained on the very text it will encode -- that is
correct for DTE, not overfitting. The one thing that does not transfer is
corpus SIZE: a fixed number of pairs covers proportionally more of a small
text, so yields measured on a sample overstate the yield on a full script.
Use `yield_curve_by_size` before trusting a number.
"""
import sys
from collections import Counter

FIRST_CODE = 256  # symbol ids >= this are DTE codes, not literals


def _pair_counts(segs, literal_only, first_code):
    """Non-overlapping adjacent-pair counts across all segments."""
    c = Counter()
    for s in segs:
        i = 0
        n = len(s)
        while i < n - 1:
            a, b = s[i], s[i + 1]
            if literal_only and (a >= first_code or b >= first_code):
                i += 1
                continue
            c[(a, b)] += 1
            i += 2  # non-overlapping: aaa yields one aa, not two
    return c


def _replace(segs, pair, code):
    a, b = pair
    out = []
    for s in segs:
        r = []
        i = 0
        n = len(s)
        while i < n:
            if i < n - 1 and s[i] == a and s[i + 1] == b:
                r.append(code)
                i += 2
            else:
                r.append(s[i])
                i += 1
        out.append(r)
    return out


def build(segments, npairs, recursive=False, first_code=FIRST_CODE):
    """Greedily assign `npairs` codes. Returns (table, encoded_segments).

    table[i] is the (a, b) expansion of code first_code + i.
    """
    segs = [list(s) for s in segments]
    table = []
    for k in range(npairs):
        counts = _pair_counts(segs, literal_only=not recursive, first_code=first_code)
        if not counts:
            break
        # ties broken on the pair itself so runs are reproducible
        pair, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        if n < 2:  # a pair used once saves nothing and costs a table entry
            break
        code = first_code + k
        segs = _replace(segs, pair, code)
        table.append(pair)
    return table, segs


def expand(seq, table, first_code=FIRST_CODE):
    """Decode: the reference implementation the ROM expander must match."""
    out = []
    stack = list(reversed(seq))
    while stack:
        s = stack.pop()
        if s >= first_code:
            a, b = table[s - first_code]
            stack.append(b)
            stack.append(a)
        else:
            out.append(s)
    return out


def max_depth(table, first_code=FIRST_CODE):
    """Worst-case expansion depth -- sizes the expander's stack."""
    memo = {}

    def d(s):
        if s < first_code:
            return 0
        if s in memo:
            return memo[s]
        memo[s] = 1  # guard; the table is built bottom-up so it cannot cycle
        a, b = table[s - first_code]
        memo[s] = 1 + max(d(a), d(b))
        return memo[s]

    return max((d(first_code + i) for i in range(len(table))), default=0)


def measure(segments, npairs, recursive=False, first_code=FIRST_CODE):
    before = sum(len(s) for s in segments)
    table, enc = build(segments, npairs, recursive, first_code)
    after = sum(len(s) for s in enc)
    for orig, e in zip(segments, enc):
        assert expand(e, table, first_code) == list(orig), 'round-trip failed'
    return {
        'before': before,
        'after': after,
        'saved': before - after,
        'pct': 100.0 * (before - after) / before if before else 0.0,
        'pairs': len(table),
        'depth': max_depth(table, first_code),
        'table': table,
        'encoded': enc,
    }
