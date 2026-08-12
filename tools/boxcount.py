#!/usr/bin/env python3
"""Where does the English use more text boxes than the Japanese?

**READ THIS FIRST: the press-cost claim this file was written on is RETRACTED.** It was
built on 2026-08-05 to explain Joey's *"I have to push A twice"*, on the reasoning that a
box waits iff it holds an `<end>` (`$ED` sets `$CFC4` at `13:$4155`; `13:$40B8` tests it
and waits at `13:$5445` -> `13:$541B`), so every extra box must cost a press.

**That was the wrong diagnosis and the arithmetic does not survive measurement.** The real
defect was a trailing `<end>`, which draws the final box a SECOND time -- see
`lint_en`'s `end_trailing` / `end_resumes_text` checks. And when the box-count theory was
finally tested head-on, by putting a two-box and a one-box rendering of the same text into
the same NPC and counting entries to the wait loop at `13:$541B`:

    two boxes, first carrying <end>    1 wait, 2 presses to dismiss
    one box, no <end> at all           1 wait, 2 presses to dismiss

**No difference.** So an extra box is NOT an extra press, and the 32 prose edits made on
the strength of it were reverted -- they cost real wording and bought nothing measurable.

WHAT IT IS STILL GOOD FOR. The structural divergence is real and worth knowing when the
prose is reviewed: we render 261 box breaks where the Japanese renders 120. That is a
PACING question -- how many screens a speech is broken across -- not a defect, and this
reports it as such. It is deliberately NOT in the standing battery, because it measures a
preference rather than a bug.

    boxcount.py                 # the ranked report
    boxcount.py --tsv FILE      # the same, for working through

**The lesson is the one this session learned twice: measure the claim, not the model.** A
static count over the script agreed with itself perfectly and was still wrong, because
nothing had ever put a controller in front of it.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogue_preview as dialogue

SCRIPT = 'script/script.json'
EN = 'script/en.tsv'


def boxes(text):
    """-> [box text], split the way the composer does."""
    return text.split('<brk>')


def waits(text):
    """-> boxes that carry an <end>. NOT a press count -- see the docstring's retraction."""
    return sum(1 for b in boxes(text) if '<end>' in b)


def load():
    sc = json.load(open(SCRIPT))
    by = {s['loc']: s for s in sc['strings']}
    en = {}
    for line in open(EN, encoding='utf-8'):
        if line.startswith('#') or '\t' not in line:
            continue
        loc, txt = line.rstrip('\n').split('\t', 1)
        en[loc.strip()] = txt
    return by, en


def plain(text):
    """-> the text with every token gone, which is what has to fit the boxes."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', text)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tsv')
    ap.add_argument('--top', type=int, default=40)
    a = ap.parse_args()

    by, en = load()
    rows = []
    for loc, txt in en.items():
        j = by.get(loc)
        if not j or not j['jp']:
            continue
        jw, ew = waits(j['jp']), waits(txt)
        if ew <= jw:
            continue
        # There is deliberately no "characters to cut" estimate. Under Dot, source glyphs
        # and painted pixels are independent; reducing both to one scalar would revive the
        # assumption this reset removed.
        rows.append((ew - jw, 'SILENT' if not jw else 'EXTRA',
                     loc, jw, ew, plain(txt)))
    rows.sort(key=lambda r: (r[1] != 'SILENT', -r[0]))

    silent = [r for r in rows if r[1] == 'SILENT']
    print('boxcount: %d string(s) use more boxes than the Japanese, %d extra box(es) in all' % (len(rows), sum(r[0] for r in rows)))
    print('          a PACING report, not a defect list; %d SILENT (the Japanese message '
          'carries no <end> at all)\n' % len(silent))
    print('  +box class   loc          text')
    for d, cls, loc, jw, ew, body in rows[:a.top]:
        print('  %+2d   %-6s  %-12s %s' % (d, cls, loc, body[:52]))
    if len(rows) > a.top:
        print('  ... %d more' % (len(rows) - a.top))
    if a.tsv:
        with open(a.tsv, 'w', encoding='utf-8') as f:
            f.write('# loc\tclass\textra_boxes\tjp_boxes\ten_boxes\ten\n')
            for d, cls, loc, jw, ew, body in rows:
                f.write('%s\t%s\t%d\t%d\t%d\t%s\n'
                        % (loc, cls, d, jw, ew, en[loc]))
        print('\nwrote %s' % a.tsv)



if __name__ == '__main__':
    main()
