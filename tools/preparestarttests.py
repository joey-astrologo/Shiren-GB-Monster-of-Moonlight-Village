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
CASES = (
    ('erase_orochi', 'shiren_en_fays_puzzles.srm'),
    ('rank_direct', 'shiren_en_path_select.srm'),
    ('rank_category', 'shiren_en_logs_passwords.srm'),
    ('pass_selector', 'shiren_en_log_1_password.srm'),
)


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def expected_hashes():
    wanted = {source for _case, source in CASES}
    found = {}
    with open(MANIFEST, encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            if row['filename'] in wanted:
                found[row['filename']] = row['sha256']
    missing = sorted(wanted - set(found))
    if missing:
        raise SystemExit('preparestarttests: fixture(s) absent from manifest: ' +
                         ', '.join(missing))
    return found


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

    wanted = expected_hashes()
    staged = []
    for case, source_name in CASES:
        source = os.path.join(FIXTURES, source_name)
        if not os.path.isfile(source):
            raise SystemExit('preparestarttests: missing fixture: ' + source)
        source_sha = digest(source)
        if source_sha != wanted[source_name]:
            raise SystemExit('preparestarttests: fixture hash mismatch for %s: %s '
                             '(expected %s)' %
                             (source_name, source_sha, wanted[source_name]))

        # Every route has a distinct emulator identity. Re-running one case can reset
        # only its matching battery save and cannot inherit another route's selectors.
        base = 'shiren_start_s4_' + case
        rom_out = os.path.join(output, base + '.gb')
        srm_out = os.path.join(output, base + '.srm')
        shutil.copy2(rom, rom_out)
        shutil.copy2(source, srm_out)
        staged.append((case, rom_out, srm_out, source_sha))

    print('preparestarttests: staged %d isolated Start cases in %s' %
          (len(staged), output))
    print('preparestarttests: ROM SHA-256 %s' % rom_sha)
    for case, rom_out, srm_out, source_sha in staged:
        print('preparestarttests: %-13s SRAM SHA-256 %s' % (case, source_sha))
        print('preparestarttests: %-13s ROM  %s' %
              (case, os.path.relpath(rom_out, ROOT)))
        print('preparestarttests: %-13s SRAM %s' %
              (case, os.path.relpath(srm_out, ROOT)))


if __name__ == '__main__':
    main()
