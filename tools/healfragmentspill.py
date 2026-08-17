#!/usr/bin/env python3
"""Forbid authored line breaks in queued message FRAGMENTS.

A fragment is not dialogue.  Native code composes these lines from several records that
it pushes one after another through the queue appender at ``0:$028B``, interleaving
runtime substitutions between them.  The Fluffy Bunny heal line is the clearest case::

    15:$670B  ld bc,$4D7D / call $028B   "Fluffy Bunny healed <var>"
    15:$6713  call $26B3                 the target actor's name
    15:$6716  ld bc,$4D88 / call $028B   "with a spell."

The English translation of the first record once carried an authored ``<br>``.  In play
that produced garbled Latin text, then a blank dialogue box, then an unrelated actor
animation, then the healer displacing across its target -- the queue consumer losing its
place, not merely a line that looked wrong.

The evidence that identified it is the invariant this file enforces.  Every ``ld bc,nn``
immediately followed by ``call $028B`` is located across the whole ROM, and every bank-13
record those sites name is decoded.  There are 179 distinct such records, and the
Japanese base has an authored break in NONE of them.  A break was never part of this ABI;
one string had acquired the only one in the game.

The consumer also wraps by itself, so a break is not needed for width, and the second
assertion here pins that reasoning to a proven line rather than to a guessed cap: with
the widest monster name substituted at every ``<var>``, the heal line must stay within
the widest fragment the path ALREADY carries in shipped play.  ``<var> robbed <var>``
reaches 179px; the heal line's worst case is 167px.  Deriving the budget from a live line
means it cannot drift out of step with the renderer the way a hard-coded number would.

Static by design, and layout-independent.  It needs no fixture, because floor actors are
not serialized by ordinary saves and a healer beside a wounded monster cannot be captured
in SRAM.  It also deliberately does not read a built English ROM: the redirect-all layout
moves these records out of bank 13 entirely, so a bank-13 read there would inspect
unrelated bytes and silently pass.  The call sites are enumerated from the untranslated
Japanese control instead -- where the addresses are exactly the keys ``script/en.tsv`` is
written in -- and the text is taken from the translation source.  The invariant then holds
for every placement at once.
"""
import argparse
import csv
import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import codec                                                       # noqa: E402
import propvwf                                                     # noqa: E402

BANK_SIZE = 0x4000
TEXT_BANK = 13
BR = codec.REV_CONTROL['br']
BRK = codec.REV_CONTROL['brk']
END = codec.REV_CONTROL['end']
TERMINATORS = (0xFF, END)
APPENDER = 0x028B                       # 0:$028B, the queue appender
# `ld bc,nnnn` (01 lo hi) directly followed by `call $028B` (CD 8B 02).
PATTERN = bytes((0xCD, APPENDER & 0xFF, APPENDER >> 8))
GLOSSARY = os.path.join(ROOT, 'script', 'glossary.tsv')
EN_TSV = os.path.join(ROOT, 'script', 'en.tsv')
CONTROL = os.path.join(ROOT, 'build', '_base_expanded.gb')
NAMED_KINDS = ('monster', 'npc')
BREAK_TOKENS = ('<br>', '<brk>')
TOKEN_RE = re.compile(r'<[^>]*>')

# Located by CONTENT, never by address: script/en.tsv is keyed by Japanese addresses,
# and the build relocates these records, so a literal address here would read whatever
# happened to land at the Japanese offset in the English ROM.
HEAL_SUBJECT_TEXT = 'healed <var>'
HEAL_PREDICATE_TEXT = 'with a spell.'

DECODE = {code: ch for ch, code in propvwf.EN_CODES.items()}
TOKENS = {code: '<%s>' % name for name, code in codec.REV_CONTROL.items()}


def call_sites(rom):
    """Every (bank, address, target) whose `ld bc,nn` feeds the queue appender."""
    out = []
    for bank in range(len(rom) // BANK_SIZE):
        base = bank * BANK_SIZE
        origin = 0x0000 if bank == 0 else 0x4000
        window = rom[base:base + BANK_SIZE]
        for offset in range(len(window) - 5):
            if window[offset] != 0x01:
                continue
            if window[offset + 3:offset + 6] != PATTERN:
                continue
            target = window[offset + 1] | window[offset + 2] << 8
            out.append((bank, origin + offset, target))
    return out


def translations(path):
    """`13:$XXXX` -> English text, exactly as the translator wrote it."""
    out = {}
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            if line.startswith('#') or '\t' not in line:
                continue
            key, _, text = line.rstrip('\n').partition('\t')
            bank, _, address = key.partition(':')
            if not address.startswith('$'):
                continue
            try:
                out[(int(bank), int(address[1:], 16))] = text
            except ValueError:
                continue
    return out


def widest_name():
    widest = ''
    with open(GLOSSARY, encoding='utf-8') as handle:
        for row in csv.reader(handle, delimiter='\t'):
            if not row or row[0].startswith('#') or len(row) < 4:
                continue
            if row[1] in NAMED_KINDS and len(row[3]) > len(widest):
                widest = row[3]
    return widest


def substituted(text, name):
    """Worst-case visible line: every runtime substitution is the widest name."""
    return text.replace('<var>', name)


def run(control_path, en_path):
    control = open(control_path, 'rb').read()
    english = translations(en_path)
    problems = []

    # Enumerated from the JAPANESE control, whose addresses are the keys en.tsv uses.
    sites = call_sites(control)
    targets = sorted({target for _, _, target in sites if 0x4000 <= target < 0x8000})
    if not targets:
        raise SystemExit('healfragmentspill: found no queued-fragment call sites in '
                         + control_path)

    translated = {target: english[(TEXT_BANK, target)]
                  for target in targets if (TEXT_BANK, target) in english}

    # ---- 1. no authored break in ANY translated fragment reachable through the appender
    broken = []
    for target in sorted(translated):
        text = translated[target]
        if any(token in text for token in BREAK_TOKENS):
            broken.append((target, text))
    for target, text in broken:
        sources = ['%d:$%04X' % (bank, address)
                   for bank, address, value in sites if value == target]
        problems.append(
            '13:$%04X %r carries an authored break, pushed from %s. Queued fragments are '
            'composed by native code with substitutions between them; a break is not part '
            'of that ABI and no fragment in the Japanese base has one.'
            % (target, text, ', '.join(sorted(set(sources)))))

    # ---- 2. the heal pair must still be reached, and still be within a proven width
    found = {}
    for label, needle in (('heal subject', HEAL_SUBJECT_TEXT),
                          ('heal predicate', HEAL_PREDICATE_TEXT)):
        matches = [target for target, text in translated.items() if needle in text]
        if len(matches) != 1:
            problems.append('%d translated fragment(s) contain %r, expected exactly 1: the '
                            'heal pair is no longer identifiable on the queued path'
                            % (len(matches), needle))
        else:
            found[label] = matches[0]

    name = widest_name()
    if not name:
        problems.append('no monster/npc names in %s to size the worst case' % GLOSSARY)
    elif not broken and 'heal subject' in found:
        import dotfont
        font = dotfont.load_approved()

        def measurable(text):
            """Plain text plus <var> only: anything else is layout, not a visible line."""
            return not TOKEN_RE.search(substituted(text, name))

        heal_target = found['heal subject']
        heal = substituted(translated[heal_target], name)
        heal_px = font.text_extent(heal)
        # The budget is the widest OTHER fragment the path already carries in shipped
        # play, so it tracks the renderer instead of a hard-coded cap.
        others = [(font.text_extent(substituted(text, name)), target, text)
                  for target, text in translated.items()
                  if target != heal_target and measurable(text)]
        if not others:
            problems.append('no other measurable fragment to size the heal line against')
        else:
            reference_px, _, reference_text = max(others)
            if heal_px > reference_px:
                problems.append(
                    'heal subject worst case %r is %dpx, wider than the widest fragment '
                    'the path already carries (%r at %dpx). Nothing proves the consumer '
                    'wraps that far, and a break is not an available remedy here.'
                    % (heal, heal_px, substituted(reference_text, name), reference_px))
            else:
                print('healfragmentspill: heal worst case %r = %dpx, within the %dpx '
                      'already carried by %r'
                      % (heal, heal_px, reference_px, substituted(reference_text, name)))

    for problem in problems:
        print('  ' + problem)
    print('healfragmentspill: %d appender call site(s), %d distinct fragment record(s), '
          '%d translated, %d with authored breaks; %d problem(s)'
          % (len(sites), len(targets), len(translated), len(broken), len(problems)))
    if problems:
        raise SystemExit('healfragmentspill: %d problem(s)' % len(problems))
    print('healfragmentspill: no queued fragment carries an authored break, and the '
          'Fluffy Bunny heal line stays inside a width the path already proves')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('control', nargs='?', default=CONTROL,
                        help='expanded, otherwise-unpatched Japanese ROM')
    parser.add_argument('--en', default=EN_TSV)
    args = parser.parse_args()
    for path in (args.control, args.en):
        if not os.path.exists(path):
            raise SystemExit('healfragmentspill: missing %s' % path)
    run(args.control, args.en)


if __name__ == '__main__':
    main()
