#!/usr/bin/env python3
"""Catalogue every LCDC writer and govern translation-added whole-LCD blankers.

The Japanese ROM writes ``$FF40`` from many shared hardware paths. A write site is not
automatically a blanker: some set bit 7, while many publish a cached LCDC value whose
runtime state depends on the caller. The English build also adds writers for new screen
transactions and conservative menu fallbacks.

This audit has two deliberately separate products:

* every ``ldh [$FF40],a`` / ``ld [$FF40],a`` site is emitted to TSV, so native and
  translation-owned control flow stays enumerable; and
* every translation-added site which *explicitly* clears bit 7 immediately before the
  write must appear in ``TRANSLATION_OFF`` below. An unclassified explicit blanker is a
  build failure.

Runtime fixtures remain responsible for proving which variable-value native writers
actually turn the LCD off on a particular route. Static provenance and dynamic route
coverage answer different questions and neither replaces the other.
"""
import argparse
import csv
import os


BANK_SIZE = 0x4000


# (bank, write address): (owner, route/purpose, current policy)
#
# ``keep`` means the route intentionally replaces an independent complete screen or
# reloads tile data while already dark. ``replace-menu`` is a conservative same-menu
# fallback: scoped menu callers must acquire regional ownership instead, and fixtures
# must reject reaching it. ``mixed`` means the physical instruction has both an
# intentional complete-screen caller and rejected same-menu callers; each caller needs
# a direct fixture. ``review`` is a complete-screen menu transaction whose final product
# is correct but whose whole-LCD policy has not been frozen with the user.
TRANSLATION_OFF = {
    (38, 0x408F): (
        'structvwf.feirestore',
        "Fay's Puzzle composite entry and native fixed-tile reload",
        'keep',
    ),
    (41, 0x40E1): (
        'menuvwf.starttransition',
        'title/file composite shadow-map replacement',
        'review',
    ),
    (43, 0x40B6): (
        'rankvwf.rankfinish',
        'completed Rankings whole-map publication',
        'review',
    ),
    (44, 0x4066): (
        'rankvwf.nativerestore',
        'complete native menu-font reload with caller LCDC restoration',
        'keep',
    ),
    (46, 0x42B5): (
        'rankvwf.screenrestore',
        'Rankings result/native-font restoration',
        'keep',
    ),
    (53, 0x42C6): (
        'statusvwf.statusentry',
        'Name -> disposable Status -> Items and other unknown LCD-on returns; exact screen-7 Floor -> Status is gated away',
        'replace-menu',
    ),
    (59, 0x406F): (
        'normalending.install',
        'Normal-ending full-screen art installation',
        'keep',
    ),
    (60, 0x4222): (
        'menuvwf.itemregion',
        'unreached rejected regional Item-row transaction to whole-map fallback',
        'replace-menu',
    ),
    (60, 0x4338): (
        'menuvwf.itempage',
        'rejected Pot viewer or Item page/sort transaction fallback',
        'replace-menu',
    ),
    (62, 0x4476): (
        'menuvwf.infolifecycle',
        'legacy Item/Floor Info or seal whole-map fallback',
        'replace-menu',
    ),
}


def _classify_before(buf, offset, bank_start):
    """Classify only locally provable A values immediately before an LCDC write."""
    before = buf[max(bank_start, offset - 8):offset]
    if before.endswith(b'\xCB\xBF'):
        return 'explicit-off'
    if before.endswith(b'\xCB\xFF'):
        return 'explicit-on'
    if before.endswith(b'\xAF'):
        return 'immediate-off-$00'
    if len(before) >= 2 and before[-2] == 0x3E:
        value = before[-1]
        return ('immediate-on-' if value & 0x80 else 'immediate-off-') + '$%02X' % value
    return 'variable'


def lcdc_writers(path):
    with open(path, 'rb') as handle:
        buf = handle.read()
    if len(buf) % BANK_SIZE:
        raise SystemExit('%s: ROM size is not bank-aligned' % path)
    found = []
    for bank in range(len(buf) // BANK_SIZE):
        bank_start = bank * BANK_SIZE
        origin = 0 if bank == 0 else 0x4000
        for rel in range(BANK_SIZE - 2):
            offset = bank_start + rel
            encoding = None
            if buf[offset:offset + 2] == b'\xE0\x40':
                encoding = 'ldh'
            elif buf[offset:offset + 3] == b'\xEA\x40\xFF':
                encoding = 'ld'
            if encoding is None:
                continue
            found.append({
                'bank': bank,
                'address': origin + rel,
                'encoding': encoding,
                'effect': _classify_before(buf, offset, bank_start),
            })
    return found


def _is_locally_off(effect):
    return effect == 'explicit-off' or effect.startswith('immediate-off-')


def audit(base_path, built_path):
    base = lcdc_writers(base_path)
    built = lcdc_writers(built_path)
    base_keys = {(site['bank'], site['address']) for site in base}
    rows = []
    for site in built:
        key = (site['bank'], site['address'])
        native = key in base_keys
        owner = route = policy = ''
        if key in TRANSLATION_OFF:
            owner, route, policy = TRANSLATION_OFF[key]
        elif native:
            owner = 'base ROM'
            route = 'native/shared LCDC writer; runtime value is caller-dependent'
            policy = 'native-observe'
        else:
            owner = 'translation-added writer'
            route = 'does not locally prove an LCD-off transition'
            policy = 'observe'
        row = dict(site)
        row.update({
            'origin': 'base' if native else 'translation',
            'owner': owner,
            'route': route,
            'policy': policy,
        })
        rows.append(row)

    actual_added_off = {
        (row['bank'], row['address']) for row in rows
        if row['origin'] == 'translation' and _is_locally_off(row['effect'])
    }
    expected_added_off = set(TRANSLATION_OFF)
    problems = []
    missing = expected_added_off - actual_added_off
    extra = actual_added_off - expected_added_off
    if missing:
        problems.append('manifested translation blanker(s) missing or no longer explicit: %s' %
                        ' '.join('%d:$%04X' % key for key in sorted(missing)))
    if extra:
        problems.append('UNCLASSIFIED translation blanker(s): %s' %
                        ' '.join('%d:$%04X' % key for key in sorted(extra)))
    return base, rows, problems


def write_tsv(path, rows):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fields = ('bank', 'address', 'encoding', 'effect', 'origin', 'owner', 'policy', 'route')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields, delimiter='\t')
        writer.writeheader()
        for row in rows:
            cooked = dict(row)
            cooked['bank'] = str(row['bank'])
            cooked['address'] = '$%04X' % row['address']
            writer.writerow(cooked)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base', help='matching unmodified Japanese ROM')
    parser.add_argument('built', help='current English ROM')
    parser.add_argument('--tsv', help='write the complete LCDC-writer catalogue here')
    args = parser.parse_args()
    base, rows, problems = audit(args.base, args.built)
    if args.tsv:
        write_tsv(args.tsv, rows)

    added = [row for row in rows if row['origin'] == 'translation']
    explicit = [row for row in added if _is_locally_off(row['effect'])]
    policies = {}
    for row in explicit:
        policies[row['policy']] = policies.get(row['policy'], 0) + 1
    print('lcdblankaudit: base/current writers %d/%d; translation-added %d; '
          'explicit added LCD-off %d' % (len(base), len(rows), len(added), len(explicit)))
    print('lcdblankaudit: explicit policies %s' %
          ' '.join('%s=%d' % item for item in sorted(policies.items())))
    for row in explicit:
        print('  %d:$%04X %-12s %-27s %s' %
              (row['bank'], row['address'], row['policy'], row['owner'], row['route']))
    if args.tsv:
        print('lcdblankaudit: complete catalogue: %s' % args.tsv)
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('lcdblankaudit: %d problem(s)' % len(problems))
    print('lcdblankaudit: every explicit translation-owned LCD blanker is classified')


if __name__ == '__main__':
    main()
