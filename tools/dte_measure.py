#!/usr/bin/env python3
"""Measure what DTE would buy us, using the SNES Shiren English script as the corpus.

Why that corpus: it is the same franchise, the same register, and the same
content categories (dialogue, dungeon messages, monster names, item names) as
the GB script we have to fit. Its digram statistics are the closest thing to
ground truth available without translating 40 KB by hand first.

usage: dte_measure.py [path-to-shiren-revamp-fixes]
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dte

SNES = '/Users/joey/Documents/Workplace/Shiren/shiren-revamp-fixes'

# every command line that is not `text` acts on the renderer, so a DTE pair
# may not span it
TEXT_RE = re.compile(r'^\s*text\s+"(.*)"\s*$')
CMD_RE = re.compile(r'^\s*([a-z_]+)')


def parse(path):
    """-> list of (label, [segment, ...]); segments are barrier-free text runs."""
    units = []
    label = None
    segs = []
    cur = []

    def flush():
        if cur:
            segs.append(''.join(cur))
            cur.clear()

    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith(';'):
            continue
        if line.rstrip().endswith(':') and not line.startswith(' '):
            flush()
            if label and segs:
                units.append((label, segs))
            label, segs = line.strip()[:-1], []
            continue
        m = TEXT_RE.match(line)
        if m:
            body = m.group(1)
            # \l line break and @ terminator are control bytes -> barriers
            for part in re.split(r'\\l|@', body):
                if part:
                    cur.append(part.replace('\\"', '"'))
                flush()
            continue
        if CMD_RE.match(line):
            flush()
    flush()
    if label and segs:
        units.append((label, segs))
    return units


def load_corpus():
    cats = {}
    for fn in sorted(os.listdir(os.path.join(SNES, 'text'))):
        if not fn.endswith('.asm'):
            continue
        cats[fn[:-4]] = parse(os.path.join(SNES, 'text', fn))
    return cats


def to_syms(segs):
    """Map characters onto a dense literal id space.

    Raw ord() will not do: the corpus contains full-width ［］ (ord 65339),
    which would collide with the DTE code space.
    """
    alpha = sorted({c for s in segs for c in s})
    ix = {c: i for i, c in enumerate(alpha)}
    return [[ix[c] for c in s] for s in segs], len(alpha)


def flat(units):
    out = []
    for _, segs in units:
        out.extend(segs)
    return out


def report(title, segs, pairs=(64, 96, 120, 140)):
    syms, fc = to_syms(segs)
    total = sum(len(s) for s in syms)
    print(f'\n=== {title} ===')
    print(f'{len(segs)} segments, {total} chars '
          f'({total/1024:.1f} KiB), mean seg {total/max(len(segs),1):.1f}, '
          f'{fc} distinct chars -> {224-fc} codes free for DTE')
    print(f'{"pairs":>6} {"plain":>16} {"recursive":>16}')
    for n in pairs:
        p = dte.measure(syms, n, recursive=False, first_code=fc)
        r = dte.measure(syms, n, recursive=True, first_code=fc)
        print(f'{n:>6} {p["pct"]:>9.1f}% d{p["depth"]:<4} '
              f'{r["pct"]:>9.1f}% d{r["depth"]:<4}')
    return syms, fc


def main():
    cats = load_corpus()
    print('corpus files:')
    for k, u in cats.items():
        n = sum(len(s) for _, segs in u for s in segs)
        print(f'  {k:22s} {len(u):5d} units  {n:7d} chars')

    allsegs = []
    for u in cats.values():
        allsegs.extend(flat(u))

    charset = Counter(c for s in allsegs for c in s)
    print(f'\ndistinct characters used: {len(charset)}')
    odd = [c for c in charset if not (c.isalnum() or c in ' .,!?\'"-:;()/%&*#+')]
    if odd:
        print('  non-basic:', ''.join(sorted(odd))[:80])

    # --- headline: whole corpus, both variants
    syms, fc = report('ALL TEXT', allsegs)

    # --- how much of the yield is an artefact of corpus size
    print('\n=== yield vs corpus size (120 pairs) ===')
    print(f'{"KiB":>8} {"plain":>10} {"recursive":>10}')
    import random
    rng = random.Random(1)
    shuffled = list(syms)
    rng.shuffle(shuffled)
    for target in (4096, 8192, 16384, 32768, 65536, 131072, 10**9):
        sub, n = [], 0
        for s in shuffled:
            if n >= target:
                break
            sub.append(s)
            n += len(s)
        if not sub:
            continue
        p = dte.measure(sub, 120, recursive=False, first_code=fc)
        r = dte.measure(sub, 120, recursive=True, first_code=fc)
        print(f'{n/1024:>8.1f} {p["pct"]:>9.1f}% {r["pct"]:>9.1f}%')
        if target > 10**8:
            break

    # --- per category: names compress differently from prose
    for name in ('dialogue', 'dungeonmessages', 'enemynames', 'itemnames'):
        if name in cats:
            report(name, flat(cats[name]), pairs=(120,))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SNES = sys.argv[1]
    main()
