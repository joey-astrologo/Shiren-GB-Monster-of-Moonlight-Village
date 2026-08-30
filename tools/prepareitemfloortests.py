#!/usr/bin/env python3
"""Stage isolated, no-Lua Item/Floor manual-test ROM/SRAM pairs.

Every output ROM has a unique basename and a same-basename ``.srm``.  This prevents a
manual Mesen run from resolving to Joey's ordinary Shiren save.  Source SRAM is accepted
only when its SHA-256 still matches the tracked fixture manifest.
"""

import argparse
import csv
import hashlib
import os
import shutil


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'saves')
MANIFEST = os.path.join(ROOT, 'tests', 'fixtures', 'manifest.tsv')

CASES = (
    ('01_item_pages', 'shiren_en_item_menu.srm', 'Log 1',
     'Four carried pages: entry, rapid paging, indicators, sorting, and Status return.'),
    ('02_floor_pages', 'shiren_en_item_menu_wood_arrow.srm', 'Log 1',
     'Items-appended Floor page plus Floor Action/Info and both shape directions.'),
    ('03_floor_names', 'shiren_log3_unidentified_naming.srm', 'Log 3',
     'Screen-20 and Items-appended Floor Name entry plus all three return histories.'),
    ('04_carried_name', 'shiren_en_log3_carried_unidentified_naming.srm', 'Log 3',
     'Carried unidentified Willow Staff Name entry and cancel/success returns.'),
    ('05_pot_put', 'shiren_en_log2_storage_pot_menu.srm', 'Log 2',
     'Storage Pot Put selector, field action, rebuilt Items, and both B returns.'),
    ('06_equipment', 'shiren_en_log2_weapon_VWF_break.srm', 'Log 2',
     'Real equipped/fused Nagamaki row and zero-seal marker on Status -> Items.'),
    ('07_shield_info', 'shiren_en_log_1_shield_VWF.srm', 'Log 1',
     'Two-star shield list, Info/seal paging, and return to Items.'),
    ('08_shop_floor', 'shiren_log3_store_item_screen.srm', 'Log 3',
     'No-cheat shop Floor/Action/Info/Floor cycle with Price/G/value rows.'),
    ('09_unidentified_pot', 'shiren_en_log3_unidentified_pot_crash.srm', 'Log 3',
     'Seven-row unidentified-Pot Floor Action, Info/See, and parent restoration.'),
)


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def expected_hashes():
    with open(MANIFEST, encoding='utf-8', newline='') as handle:
        return {row['filename']: row['sha256'] for row in
                csv.DictReader(handle, delimiter='\t')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', nargs='?', default=os.path.join(ROOT, 'build',
                                                               'shiren_en.gb'))
    parser.add_argument('--output', help='output directory; defaults to a ROM-hash path')
    args = parser.parse_args()

    rom = os.path.abspath(args.rom)
    if not os.path.isfile(rom):
        raise SystemExit('prepareitemfloortests: missing ROM: ' + rom)
    rom_sha = digest(rom)
    output = args.output or os.path.join(
        ROOT, 'build', 'manual-tests', 'item-floor-' + rom_sha[:12])
    output = os.path.abspath(output)
    os.makedirs(output, exist_ok=True)

    known = expected_hashes()
    rows = []
    for tag, filename, log, purpose in CASES:
        source = os.path.join(FIXTURES, filename)
        if not os.path.isfile(source):
            raise SystemExit('prepareitemfloortests: missing fixture: ' + source)
        actual = digest(source)
        expected = known.get(filename)
        if actual != expected:
            raise SystemExit('prepareitemfloortests: fixture hash mismatch for %s: %s '
                             '(expected %s)' % (filename, actual, expected))
        case_dir = os.path.join(output, tag)
        os.makedirs(case_dir, exist_ok=True)
        base = 'shiren_' + tag
        rom_out = os.path.join(case_dir, base + '.gb')
        srm_out = os.path.join(case_dir, base + '.srm')
        shutil.copy2(rom, rom_out)
        shutil.copy2(source, srm_out)
        rows.append((tag, log, purpose, os.path.relpath(rom_out, ROOT),
                     os.path.relpath(srm_out, ROOT), actual))

    manifest = os.path.join(output, 'cases.tsv')
    with open(manifest, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(('case', 'load', 'purpose', 'rom', 'srm', 'srm_sha256'))
        writer.writerows(rows)

    print('prepareitemfloortests: staged %d isolated cases in %s' %
          (len(rows), output))
    print('prepareitemfloortests: ROM SHA-256 %s' % rom_sha)
    print('prepareitemfloortests: case manifest %s' % manifest)
    for tag, log, _purpose, rom_out, srm_out, _sha in rows:
        print('  %-21s %-5s  %s  %s' % (tag, log, rom_out, srm_out))


if __name__ == '__main__':
    main()
