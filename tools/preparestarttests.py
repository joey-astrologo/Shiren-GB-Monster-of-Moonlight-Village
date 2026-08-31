#!/usr/bin/env python3
"""Stage an isolated ROM/SRAM pair for Start-menu visual checkpoints.

The output basename is unique and its SRAM is hash-verified against the tracked fixture
manifest.  Mesen can therefore be reset between destructive Copy/Erase routes without
touching Joey's normal save or inheriting state from a Lua-created inventory.
"""

import argparse
import csv
import hashlib
import os
import shutil


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'saves')
MANIFEST = os.path.join(ROOT, 'tests', 'fixtures', 'manifest.tsv')
SOURCE_SRM = 'shiren_en_path_select.srm'


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def expected_hash():
    with open(MANIFEST, encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            if row['filename'] == SOURCE_SRM:
                return row['sha256']
    raise SystemExit('preparestarttests: fixture is absent from manifest: ' + SOURCE_SRM)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', nargs='?', default=os.path.join(ROOT, 'build',
                                                               'shiren_en.gb'))
    parser.add_argument('--output', help='output directory; defaults to a ROM-hash path')
    args = parser.parse_args()

    rom = os.path.abspath(args.rom)
    if not os.path.isfile(rom):
        raise SystemExit('preparestarttests: missing ROM: ' + rom)
    rom_sha = digest(rom)
    output = os.path.abspath(args.output or os.path.join(
        ROOT, 'build', 'manual-tests', 'start-' + rom_sha[:12]))
    os.makedirs(output, exist_ok=True)

    source = os.path.join(FIXTURES, SOURCE_SRM)
    if not os.path.isfile(source):
        raise SystemExit('preparestarttests: missing fixture: ' + source)
    source_sha = digest(source)
    wanted = expected_hash()
    if source_sha != wanted:
        raise SystemExit('preparestarttests: fixture hash mismatch: %s (expected %s)' %
                         (source_sha, wanted))

    base = 'shiren_start_s2'
    rom_out = os.path.join(output, base + '.gb')
    srm_out = os.path.join(output, base + '.srm')
    shutil.copy2(rom, rom_out)
    shutil.copy2(source, srm_out)

    print('preparestarttests: staged isolated Start case in %s' % output)
    print('preparestarttests: ROM SHA-256 %s' % rom_sha)
    print('preparestarttests: SRAM SHA-256 %s' % source_sha)
    print('preparestarttests: ROM %s' % os.path.relpath(rom_out, ROOT))
    print('preparestarttests: SRAM %s' % os.path.relpath(srm_out, ROOT))


if __name__ == '__main__':
    main()
