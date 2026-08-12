#!/usr/bin/env python3
"""Recompute which byte values the DTE code space may safely use.

The composer expands EVERY line it draws -- it has no gate, unlike the box drawer -- so any
byte in the DTE code space is expanded into two even when it is untranslated Japanese that
was never compressed. That changes cell counts, cell counts drive line wrapping, and the
dungeon's self-dismissing messages became too fast to read. See dte_rom's docstring.

So a DTE code must be a byte that NO untranslated string contains. That set grows every
time a string is translated, which is why this is a tool and not a constant: run it after a
batch of translation to see what has opened up.

    dte_ranges.py [--tsv script/en.tsv]

Reports the safe ranges, and what each candidate would cost in expander bytes -- the range
test is generated from DTE_RANGES and bank 0's padding is EXACTLY 158 bytes, so the number
of ranges is as much of a constraint as the number of codes.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dte_rom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def as_ranges(vals):
    out, s, p = [], None, None
    for v in sorted(vals):
        if s is None:
            s = v
        elif v != p + 1:
            out.append((s, p))
            s = v
        p = v
    if s is not None:
        out.append((s, p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tsv', default=os.path.join(ROOT, 'script', 'en.tsv'))
    ap.add_argument('--manifest', default=os.path.join(ROOT, 'script', 'script.json'))
    args = ap.parse_args()

    m = json.load(open(args.manifest, encoding='utf-8'))
    translated = set()
    for line in open(args.tsv, encoding='utf-8'):
        t = line.split('#')[0].strip()
        if '\t' in t:
            translated.add(t.split('\t')[0].strip())

    used, n_jp = set(), 0
    for r in m['strings']:
        if r['loc'] in translated:
            continue
        n_jp += 1
        used.update(bytes.fromhex(r['hex']))

    # What the renderers forbid regardless of content, from dte_rom's own rules.
    forbidden = set(range(0xE0, 0x100)) | {0x79, 0x7A, 0x00} | set(range(0xB3, 0xB7))
    try:
        from latinfont import EN_CODES
        forbidden |= set(EN_CODES.values())
    except ImportError:
        pass

    safe = sorted(set(range(0x40, 0xE0)) - used - forbidden)
    cur = set(dte_rom.DTE_CODES)

    print('%d untranslated strings; %d distinct byte values in use' % (n_jp, len(used)))
    print('\nSAFE code bytes (%d): %s'
          % (len(safe), ' '.join('$%02X-$%02X(%d)' % (a, b, b - a + 1)
                                 for a, b in as_ranges(safe))))
    print('\ncurrent DTE_RANGES: %s = %d codes'
          % (' '.join('$%02X-$%02X' % r for r in dte_rom.DTE_RANGES), len(cur)))

    bad = sorted(cur & used)
    if bad:
        print('  *** %d current code(s) ARE used by untranslated Japanese: %s'
              % (len(bad), ' '.join('$%02X' % b for b in bad[:16])))
        print('  *** the build should be failing -- see build.check for the message')
    else:
        print('  OK: no untranslated string can be expanded')

    gain = sorted(set(safe) - cur)
    if gain:
        print('\nnewly safe since the ranges were last set (%d): %s'
              % (len(gain), ' '.join('$%02X-$%02X(%d)' % (a, b, b - a + 1)
                                     for a, b in as_ranges(gain))))
        print('Widening is only worth it if the range COUNT does not grow: the expander is')
        print('158 bytes at three ranges and bank 0 padding holds exactly 158. A fourth')
        print('range costs 8 more and does not fit -- take codes by MERGING, not adding.')
    else:
        print('\nnothing new is safe yet; translate more before widening the ranges')


if __name__ == '__main__':
    main()
