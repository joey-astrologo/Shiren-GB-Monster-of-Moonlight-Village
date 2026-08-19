#!/usr/bin/env python3
"""How much framed script is in the ROM that `extract.py` never covered.

    coverage.py [rom] [script.json] [--max N] [--list] [--bank N]

THE HOLE THIS CLOSES. Every other check in the battery verifies that what we extracted
round-trips, renders, fits and does not corrupt anything. **Nothing checked that what we
extracted is all there is.** So a bank could be "100% translated", green on every line of
`docs/ENGINEERING_RULES.md`, and still speak Japanese on screen -- which is exactly what happened after
session 5: 355 bank-11/14 strings translated, whole battery green, and the shop, the Kuyo
Pass road picker and a third of the village prose were never in `script.json` at all.

`1261 strings` was never a total. It is what the extractor happened to find. Joey raised
this gap twice and got an argument instead of a number, and that was possible only because
no tool could produce a number.

WHAT IT MEASURES. Stretches of consecutive script bytes, in a non-graphics bank, that no
extracted string covers.  This is BYTE coverage, not an enumeration of every address the
event engine may enter.  The rescued-child exit proved the distinction: 14:$5AFD and
14:$70BE were already covered by parent strings, but runtime resumed inside those parents
and bypassed their English redirects.  Runtime-observed interior entries are therefore an
explicit second gate shared with ``extract.py``; ``gbrun.py --dte-scan`` is what discovers
new ones. Classified, not totalled -- the raw figure is ~22 KB and most of it is not text:

  dialogue   FRAMED: `$FF` on both sides, every byte decodes, and it carries a quote `「`
             or a `<br>`/`<end>`/`<brk>`. This is the shape `extract.py` knows how to find,
             so it is gated at ZERO and stays there.
  embedded   the same, but NOT `$FF`-framed -- a stretch of text sitting inside a run that
             also contains bytes which cannot be script. This class held 532 bytes of real
             dialogue until 2026-08-05. Its ten remaining script-bank hits have now been
             tied to code, pointer tables, graphics or animation records; see
             EMBEDDED_NON_TEXT. Exact address+byte declarations exempt those false
             positives, while every new or changed hit fails the build.
  other      decodes cleanly, carries no dialogue marker. Mostly coincidence: bank 10's
             numeric item-stat table is 12 KB of it, reading as `なカなカなカ...`, and
             banks 3, 7, 25-31 are the same shape. A short menu label with no control code
             would also land here, so this column is a place to LOOK, not a defect count.
  truncated  a run only PARTLY covered by an extracted string. Always a bug: it means a
             string was extracted at the wrong offset or the wrong length, and the tail is
             on screen in Japanese. See `docs/TRAPS.md`, the truncated-fragment note.

THE RULE THIS FILE WILL NOT BREAK. The script-byte set is imported from `codec`, never
restated here. The 7.9 KB gap this tool was written to measure was caused by exactly that
mistake: `regions.py` kept a hand-written copy of the character table, frozen at what
`textdump.py` knew on day one, and it was missing `<brk>`, `、`, `<cEC>`, `『』（）`, `：`
and 33 other values. Those bytes are ~2% of a prose block, which was enough to hold every
block in bank 14 under the 0.97 density threshold, so the region never opened and a walker
that only walks detected regions never saw the text. A duplicated table drifts; an imported
one cannot. See [[shiren-gb-layout-duplicated-in-code]] for the same failure in the ROM.

Exit 1 if the dialogue class is over `--max` (default 0).
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec
import intro
from regions import GFX_BANKS, FONT
from extract import TEXT_BANKS, DESC_LEN, RUNTIME_INTERIOR_ENTRIES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANKSZ = 0x4000

# Imported, never restated -- see the docstring. A byte is script if the canonical codec
# can decode it: a character, a combining dakuten, or a control code. NOTE that "a control
# code" is $E0-$F4, the union of the two dispatch paths, not bank 13's 17.
SCRIPT_BYTES = set(codec.CHARS) | set(codec.COMBINING) | set(codec.CONTROL)

# `「` opens quoted speech; $ED/$EE/$EF are <end>/<brk>/<br>, the composer's message and
# line breaks. A run carrying one of these is being fed to the text composer.
DIALOGUE_MARKS = {0x9A, 0xED, 0xEE, 0xEF}

# Shorter than this and a coincidental decode is likely: 8 script bytes in a row happens
# in data often enough to swamp the report, and no real dialogue line is that short.
MIN_RUN = 8

# The `embedded` noise floor: a stretch needs one real Japanese WORD in it. Data that
# decodes as kana alternates (`イすイはイやイ`) or spaces out (` ］ ～ − ▼ `) and rarely
# reaches six in a row. Stated as a floor, NOT as a classifier -- it does not separate the
# two cleanly at any value, which is why the embedded class is listed in full rather than
# counted. 11:$56C3 (`おかあさーん`) sits below it because `ー` is not a kana.
EMBEDDED_MIN_KANA = 6

# Every remaining `embedded` hit in a script bank, tied to the code that consumes it.
# Address alone is not an exemption: the bytes must match too, so different data appearing
# at a reviewed address is an unreviewed hit. A declaration may harmlessly disappear when
# scanning a transformed ROM; a new or changed hit may not silently inherit its reason.
#
# It was 22, twelve of them real prose totalling 532 bytes, and this comment used to say
# they were text inline in an event bytecode that would have to be reverse-engineered
# before a byte could move. **That was wrong, and it was wrong in the direction that costs
# most: it made a one-line fix look like a research project.** They are ordinary strings,
# and one rule was discarding them -- `extract.impossible()` rejected any block holding a
# byte in $F1-$FE, because the bank-13 dispatch table at 13:$4126 has 17 entries. Banks 11
# and 14 dispatch through 13:$68CF, which has TWENTY-ONE: $F1-$F4 are ordinary control
# codes there, with ordinary handlers. See extract.impossible() and codec.CONTROL_MAX.
EMBEDDED_NON_TEXT = {
    '3:$7F64': (
        bytes.fromhex('09 09 09 89 4f 4a 31 9a 4f 45 45 77 58 58 53'),
        'inside the 16-byte animation/state records rooted at 3:$7F07; the reader at '
        '3:$74ED selects a record with `swap c` and the loop at 3:$756D advances by $10',
    ),
    '4:$514F': (
        bytes.fromhex('56 6f 73 a2 6e 26 59 41 59 3f 6e ef 6d'),
        'misaligned bytes inside the 36-entry jump-pointer table at 4:$5130; '
        '4:$5118 indexes a little-endian target and 4:$5123 executes `jp hl`',
    ),
    '4:$5285': (
        bytes.fromhex('21 e0 8d 11 9a 52 06 05 0e 08 1a 22 22 13 0d 20'),
        'executable graphics copier called at 4:$526F; it copies a 5x8 block from '
        '4:$529A, doubling bytes into VRAM $8DE0',
    ),
    '11:$45E6': (
        bytes.fromhex(
            '42 08 43 17 43 24 43 2e 43 39 43 45 43 52 43 5d 43 6b 43 76 43 '
            '81 43 8c 43 9a 43 a4 43 b2 43'),
        'inside the item-name little-endian pointer table rooted at 11:$4537',
    ),
    '11:$5067': (
        bytes.fromhex(
            '4c 04 4d 0d 4d 16 4d 16 4d 1e 4d 27 4d 2e 4d 39 4d 43 4d 4c 4d '
            '55 4d 5f 4d 69 4d 74 4d 74 4d 7b 4d 84 4d 8b 4d 94 4d 9a 4d 9a '
            '4d 9a 4d 9a 4d 9a 4d a4 4d a4 4d a4 4d a4 4d a4 4d ae 4d'),
        'inside the second bank-11 text-pointer table rooted at 11:$4FC4',
    ),
    '13:$55BD': (
        bytes.fromhex('5c ed 5c 22 5d 56 5d 56 5d 6f 5d 9e 5d b4 5d'),
        'inside the 157-entry item-help pointer table at 13:$554A-$5683',
    ),
    '13:$55CD': (
        bytes.fromhex('5d ef 5d 05 5e 1d 5e 55 5e 6f 5e 8a 5e a9 5e'),
        'inside the 157-entry item-help pointer table at 13:$554A-$5683',
    ),
    '13:$5613': (
        bytes.fromhex('62 e0 62 07 63 07 63 1e 63 42 63 66 63 9a 63 b3 63'),
        'inside the 157-entry item-help pointer table at 13:$554A-$5683',
    ),
    '30:$7884': (
        bytes.fromhex('7f 51 67 ed 72 e2 3d 30 3f 1d 1f 0f 0f'),
        'inside the 128-byte graphics block at 30:$7873-$78F2; 30:$7861 copies it '
        'to VRAM $95C0',
    ),
    '31:$689E': (
        bytes.fromhex(
            '7f 00 01 05 2d 6c 6c 64 44 4c 6f 67 60 60 71 7f 38 80 80 90 '
            '9a 9b 9b 1b 9b 92 f2 b2'),
        'inside the indexed frame/graphics tables rooted at 31:$6554/$657F; readers '
        'at 31:$62C5 and 31:$6315 queue doubled bytes for VBlank transfer',
    ),
}

# Runs that carry a dialogue marker but hold no Japanese. Declared one by one, with the
# reason, rather than waived by a byte-count allowance -- an allowance of "18 bytes" would
# equally excuse 18 bytes of real prose appearing somewhere else later.
ALLOW = {
    '14:$46DA': 'the shop price keypad: ` <br> 0123456789>| <br> `, 17 bytes, ZERO '
                'Japanese characters. block_strings rejects it on kana=0.00 and 10 digits, '
                'and that rejection is correct -- it is a layout template, not a line. '
                'Extracting it would put an untranslatable row on the translator worklist.',
}


def loc(off):
    return '%d:$%04X' % (off // BANKSZ, off % BANKSZ + 0x4000)


def covered_map(rom, strings, boxes=()):
    """Bytes ACCOUNTED FOR: claimed by an extracted string, or a box descriptor.

    Descriptors have to be in here even though they are not text. A menu box's 7-byte
    geometry record sits immediately before its rows, inside the same `$FF`-delimited run
    -- `31:$41E2` is `00 0a 02 12 04 e9 41` (y, x, rows, width, flags, and the $41E9 text
    pointer), which decodes perfectly well as ` <nop>...`. Counting those bytes as missing
    reported all 11 of bank 31's boxes as truncated extractions on the first run of this
    tool, and they are nothing of the kind. `extract.py` drops them by the same rule.
    """
    cov = bytearray(len(rom))
    for r in strings:
        for i in range(r['offset'], min(len(rom), r['offset'] + r['bytes'] + 1)):
            cov[i] = 1
    for b in boxes:
        for i in range(b['desc'], min(len(rom), b['desc'] + DESC_LEN)):
            cov[i] = 1
    return cov


def max_kana_run(data):
    """Longest unbroken stretch of kana, dakuten included.

    The noise floor for the `embedded` class, and it has to count $79/$7A as part of a
    word: they are the combining marks, so `かぜにとばされた` is one 8-kana run and not
    `か` + `ぜ...`. Getting that wrong hid `14:$46EE` below the threshold.
    """
    best = cur = 0
    for b in data:
        cur = cur + 1 if (0x0B <= b <= 0x78 or b in codec.COMBINING) else 0
        best = max(best, cur)
    return best


def scan(rom, cov):
    """-> list of (offset, data, klass) for every uncovered/partial script stretch."""
    out = []
    for bank in range(len(rom) // BANKSZ):
        if bank in GFX_BANKS:
            continue
        base, end = bank * BANKSZ, (bank + 1) * BANKSZ
        # Maximal stretches of script bytes, NOT $FF-delimited runs. The difference is the
        # whole `embedded` class: `14:$4031`, the shop's opening line, is preceded by
        # `... $C1 $F1 $C9` with no terminator between, so a run-based scan sees one run
        # that contains impossible bytes and skips it -- which is what the first version
        # of this file did, and it reported "no unextracted dialogue" with the shop's
        # `てんしゅ「いらっしゃいませ」` sitting right there.
        i = base
        while i < end:
            if rom[i] not in SCRIPT_BYTES or FONT[0] <= i < FONT[1]:
                i += 1
                continue
            j = i
            while j < end and rom[j] in SCRIPT_BYTES:
                j += 1
            data, at = rom[i:j], i
            i = j
            if len(data) < MIN_RUN:
                continue
            hit = cov[at:j]
            if all(hit):
                continue
            framed = (at == base or rom[at - 1] == codec.TERMINATOR) and \
                     (j < end and rom[j] == codec.TERMINATOR)
            # `truncated` and `other` are FRAMED-ONLY claims, deliberately. An unframed
            # stretch that is partly covered is just an extracted string meeting the code
            # next to it, which is normal, and an unframed stretch with no dialogue marker
            # is every incidental run of kana-looking bytes in the ROM -- 5,791 of them,
            # 137 KB, which drowns the report. Only text that announces itself with a
            # break token is worth reading unframed.
            if not framed:
                if (not any(hit) and any(b in DIALOGUE_MARKS for b in data)
                        and max_kana_run(data) >= EMBEDDED_MIN_KANA):
                    out.append((at, data, 'embedded'))
            elif any(hit):
                out.append((at, data, 'truncated'))
            elif any(b in DIALOGUE_MARKS for b in data):
                out.append((at, data, 'dialogue'))
            else:
                out.append((at, data, 'other'))
    return out


def main():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    flag = {x.split('=')[0]: (x.split('=') + [''])[1] for x in sys.argv[1:] if x.startswith('--')}
    rom_path = args[0] if args else os.path.join(ROOT, 'build/base.gb')
    sc_path = args[1] if len(args) > 1 else os.path.join(ROOT, 'script/script.json')
    limit = int(flag.get('--max') or 0)
    only = int(flag.get('--bank') or -1)

    rom = open(rom_path, 'rb').read()
    sc = json.load(open(sc_path, encoding='utf-8'))
    expected_runtime = {loc(off) for off in RUNTIME_INTERIOR_ENTRIES}
    declared_runtime = {entry['loc']
                        for entry in sc.get('runtime_interior_entries', [])}
    records_by_loc = {record['loc']: record for record in sc['strings']}
    missing_runtime = sorted(
        wanted for wanted in expected_runtime
        if wanted not in declared_runtime or wanted not in records_by_loc
        or not records_by_loc[wanted].get('runtime_entry'))
    intro_path = os.path.join(ROOT, 'script', 'intro.tsv')
    intro_report = intro.coverage(rom, intro_path)
    runs = scan(rom, covered_map(rom, sc['strings'], sc.get('boxes', ())))

    per = collections.defaultdict(collections.Counter)
    for at, data, klass in runs:
        per[at // BANKSZ][klass] += 1
        per[at // BANKSZ][klass + '_b'] += len(data) + 1

    print('%s: %d strings, %d script bytes' % (os.path.basename(sc_path),
                                               len(sc['strings']), sc['script_bytes']))
    print('runtime entries: %d observed interior start(s), %s'
          % (len(expected_runtime), 'ALL MANIFESTED' if not missing_runtime else
             'MISSING ' + ' '.join(missing_runtime)))
    print('intro.tsv: {lines} translated lines, {runs} third-alphabet runs '
          '({decorative} decorative), {programs} VM programs / {bytes} bytes; '
          'ALL ACCOUNTED FOR'.format(**intro_report))
    print()
    print('bank | dialogue runs/bytes | embedded runs/bytes |  other runs/bytes | trunc')
    for bank in sorted(per):
        c = per[bank]
        if not c:
            continue
        print('  %2d |   %4d / %6d     |   %4d / %6d      |  %4d / %6d    |  %d'
              % (bank, c['dialogue'], c['dialogue_b'], c['embedded'], c['embedded_b'],
                 c['other'], c['other_b'], c['truncated']))

    tot, outside = collections.Counter(), collections.Counter()
    for bank, c in per.items():
        tot.update(c)
        if bank not in TEXT_BANKS:
            outside.update({k: v for k, v in c.items()
                            if k.startswith('dialogue') or k.startswith('embedded')})
    print()
    print('UNEXTRACTED DIALOGUE : %d runs, %d bytes   <-- the number that matters'
          % (tot['dialogue'], tot['dialogue_b']))
    print('embedded/unframed    : %d runs, %d bytes   (%d in script banks)'
          % (tot['embedded'], tot['embedded_b'],
             tot['embedded'] - outside['embedded']))
    print('other clean-decoding : %d runs, %d bytes   (mostly data; bank 10 is a stat table)'
          % (tot['other'], tot['other_b']))
    print('truncated extractions: %d runs, %d bytes   (always a bug)'
          % (tot['truncated'], tot['truncated_b']))

    # Printed every run, never filtered away. The gate below only counts banks that hold
    # script, and "only these banks hold script" is exactly the kind of assumption that hid
    # the 7.9 KB gap for five sessions -- so the hits it excuses are listed in full, every
    # time, for a human to disagree with.
    if outside:
        print()
        print('%d dialogue-classed run(s), %d bytes, OUTSIDE the script banks %s -- NOT '
              'gated, listed so the exemption stays visible:'
              % (outside['dialogue'], outside['dialogue_b'],
                 ','.join(str(b) for b in sorted(TEXT_BANKS))))
        for at, data, klass in runs:
            if klass == 'dialogue' and at // BANKSZ not in TEXT_BANKS:
                print('    %-12s %3d  %s' % (loc(at), len(data), codec.decode(data)[:48]))

    if flag.get('--list') is not None or only >= 0:
        print()
        for at, data, klass in runs:
            if klass == 'other' and flag.get('--list') != 'all':
                continue
            if only >= 0 and at // BANKSZ != only:
                continue
            print('  %-12s %-10s %3d  %s' % (loc(at), klass, len(data),
                                             codec.decode(data)[:64]))

    allowed = collections.Counter()
    for at, data, klass in runs:
        if klass == 'dialogue' and loc(at) in ALLOW:
            allowed['n'] += 1
            allowed['b'] += len(data) + 1
    if allowed:
        print()
        print('%d declared non-text run(s), %d bytes, exempt by name:' % (allowed['n'],
                                                                          allowed['b']))
        for at, data, klass in runs:
            if klass == 'dialogue' and loc(at) in ALLOW:
                print('    %-12s %s' % (loc(at), ALLOW[loc(at)]))

    embedded_runs = [(at, data) for at, data, klass in runs
                     if klass == 'embedded' and at // BANKSZ in TEXT_BANKS]
    reviewed_embedded = []
    unreviewed_embedded = []
    for at, data in embedded_runs:
        place = loc(at)
        declaration = EMBEDDED_NON_TEXT.get(place)
        if declaration is not None and data == declaration[0]:
            reviewed_embedded.append((at, data, declaration[1]))
        else:
            unreviewed_embedded.append((at, data))
    if reviewed_embedded:
        print()
        print('%d script-bank embedded/unframed hit(s), explicitly reviewed as non-text:'
              % len(reviewed_embedded))
        for at, data, reason in reviewed_embedded:
            print('    %-12s %3d  %s' % (loc(at), len(data), reason))
    if unreviewed_embedded:
        print()
        print('%d UNREVIEWED script-bank embedded/unframed hit(s), listed in full:'
              % len(unreviewed_embedded))
        for at, data in unreviewed_embedded:
            print('    %-12s %3d  %s' % (loc(at), len(data), codec.decode(data)[:52]))

    print()
    bad = (tot['dialogue_b'] - outside['dialogue_b'] - allowed['b']) + tot['truncated_b']
    if missing_runtime:
        print('FAIL: runtime-observed interior entries are absent from script.json: %s'
              % ' '.join(missing_runtime))
        return 1
    if bad > limit:
        print('FAIL: %d bytes of dialogue in the ROM that script.json does not contain '
              '(allowance %d).' % (bad, limit))
        print('This is an EXTRACTION defect, not a translation one. Do not hand-add locs '
              'to en.tsv -- fix the discovery rule in extract.py/regions.py, re-extract, '
              'and re-run the whole battery (logicdiff.py especially).')
        return 1
    if unreviewed_embedded:
        print('FAIL: %d script-bank embedded/unframed hit(s) have no exact reviewed '
              'non-text classification.' % len(unreviewed_embedded))
        print('Trace each runtime reader. Extract genuine text; otherwise add an exact '
              'address+byte declaration with the structural reason.')
        return 1
    print('OK: every $FF-framed run that decodes as script and carries a quote or a break '
          'token is byte-covered; every script-bank embedded hit is classified; and every '
          'known runtime interior start is manifested.')
    print('This does NOT prove that no unknown runtime entry point exists; route scans '
          'remain the discovery mechanism.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
