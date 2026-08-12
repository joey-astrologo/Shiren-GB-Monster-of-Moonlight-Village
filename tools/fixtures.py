#!/usr/bin/env python3
"""Verify, stage and regenerate the public regression fixtures.

The repository tracks only curated battery-backed SRAM under ``tests/fixtures/saves``.
Existing emulator tools continue to read ``saves/``; ``stage`` creates ignored relative
symlinks there on a fresh clone and refuses to replace a differing local file. PyBoy
machine states remain untracked and are regenerated from the current ROM with ``states``.
"""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = ROOT / 'tests' / 'fixtures' / 'manifest.tsv'
TRACKED = MANIFEST.parent / 'saves'
LOCAL = ROOT / 'saves'
SRAM_SIZE = 4 * 0x2000
EXPECTED_PLAYER = 'Shiren'

# Four adventure-log record templates in SRAM bank 2. Even an empty log carries the
# default name template, so these fields provide a deterministic privacy check.
LOG_NAME_OFFSETS = tuple(2 * 0x2000 + 0x700 + 2 + i * 0x780 for i in range(4))

# Two 19-entry Rankings tables in SRAM bank 3. A fixture may have no entries, but any
# stored six-byte name must be empty or the public default name.
RANK_NAME_OFFSETS = tuple(
    3 * 0x2000 + (base - 0xA000) + i * 12
    for base in (0xBE10, 0xBEF8) for i in range(19))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def encoded_player():
    sys.path.insert(0, str(HERE))
    from latinfont import EN_CODES
    sys.path.pop(0)
    return bytes(EN_CODES[ch] for ch in EXPECTED_PLAYER)


def load_manifest():
    with MANIFEST.open(encoding='utf-8', newline='') as source:
        rows = list(csv.DictReader(source, delimiter='\t'))
    expected = {'filename', 'sha256', 'player_name', 'purpose'}
    if not rows or set(rows[0]) != expected:
        raise SystemExit('fixtures: malformed manifest header in %s' % MANIFEST)
    names = [row['filename'] for row in rows]
    if len(names) != len(set(names)):
        raise SystemExit('fixtures: duplicate filename in manifest')
    for name in names:
        if Path(name).name != name or not name.endswith('.srm'):
            raise SystemExit('fixtures: unsafe/non-SRAM manifest name %r' % name)
    return rows


def ascii_privacy_problems(data):
    runs, current = [], bytearray()
    for value in data + b'\x00':
        if 0x20 <= value <= 0x7E:
            current.append(value)
        else:
            if len(current) >= 6:
                runs.append(bytes(current))
            current.clear()
    markers = (b'/Users/', b'\\Users\\', b'/home/', b'file://')
    email = re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
    return [run for run in runs
            if any(marker in run for marker in markers) or email.search(run)]


def verify(quiet=False):
    rows = load_manifest()
    player = encoded_player()
    allowed_rank_names = {b'\x00' * 6, player}
    problems = []
    for row in rows:
        path = TRACKED / row['filename']
        if not path.is_file():
            problems.append('%s is missing' % path)
            continue
        data = path.read_bytes()
        if len(data) != SRAM_SIZE:
            problems.append('%s is %d bytes, expected %d' %
                            (row['filename'], len(data), SRAM_SIZE))
        actual = hashlib.sha256(data).hexdigest()
        if actual != row['sha256']:
            problems.append('%s SHA-256 %s, expected %s' %
                            (row['filename'], actual, row['sha256']))
        if row['player_name'] != EXPECTED_PLAYER:
            problems.append('%s declares player %r, expected %s' %
                            (row['filename'], row['player_name'], EXPECTED_PLAYER))
        for offset in LOG_NAME_OFFSETS:
            if data[offset:offset + 6] != player:
                problems.append('%s log-name field $%04X is not %s' %
                                (row['filename'], offset, EXPECTED_PLAYER))
        for offset in RANK_NAME_OFFSETS:
            if data[offset:offset + 6] not in allowed_rank_names:
                problems.append('%s ranking-name field $%04X is not empty/%s' %
                                (row['filename'], offset, EXPECTED_PLAYER))
        for run in ascii_privacy_problems(data):
            problems.append('%s contains path/email-like ASCII %r' %
                            (row['filename'], run[:80]))
    if problems:
        for problem in problems[:40]:
            print('  ' + problem)
        raise SystemExit('fixtures: %d verification/privacy problem(s)' % len(problems))
    if not quiet:
        print('fixtures: %d curated SRAM files, %d bytes; hashes exact; player names '
              '%s; no path/email metadata' %
              (len(rows), len(rows) * SRAM_SIZE, EXPECTED_PLAYER))
    return rows


def stage(quiet=False):
    rows = verify(quiet=True)
    LOCAL.mkdir(exist_ok=True)
    linked = existing = 0
    for row in rows:
        source = TRACKED / row['filename']
        target = LOCAL / row['filename']
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise SystemExit('fixtures: refusing unrelated symlink %s' % target)
            existing += 1
        elif target.exists():
            if not target.is_file() or digest(target) != row['sha256']:
                raise SystemExit('fixtures: refusing to replace differing local file %s' %
                                 target)
            existing += 1
        else:
            target.symlink_to(os.path.relpath(source, target.parent))
            linked += 1
    if not quiet:
        print('fixtures: staged %d link(s), %d identical/existing file(s) in %s' %
              (linked, existing, LOCAL))


def require_states():
    missing = [str(LOCAL / name) for name in
               ('town.state', 'dungeon.state', 'floorname.state', 'sign.state')
               if not (LOCAL / name).is_file()]
    if missing:
        raise SystemExit('fixtures: missing generated state(s): %s\n'
                         'run: python3 tools/fixtures.py states build/shiren_en.gb '
                         '--png-dir build/fixture-state-shots' % ', '.join(missing))
    print('fixtures: all four generated machine states present')


def generate_states(rom, png_dir=None):
    stage(quiet=True)
    rom = Path(rom)
    if not rom.is_file():
        raise SystemExit('fixtures: missing ROM %s' % rom)
    command = [sys.executable, str(HERE / 'mkstate.py'), str(rom),
               str(TRACKED / 'shiren_en_ranking_repaired.srm'),
               '--out-dir', str(LOCAL)]
    if png_dir:
        png_dir = Path(png_dir)
        png_dir.mkdir(parents=True, exist_ok=True)
        command += ['--png-dir', str(png_dir)]
    subprocess.run(command, check=True)
    require_states()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    sub.add_parser('stage')
    preflight = sub.add_parser('preflight')
    preflight.add_argument('--require-states', action='store_true')
    states = sub.add_parser('states')
    states.add_argument('rom')
    states.add_argument('--png-dir')
    args = parser.parse_args()

    if args.command == 'verify':
        verify(args.quiet)
    elif args.command == 'stage':
        stage(args.quiet)
    elif args.command == 'preflight':
        stage(args.quiet)
        if args.require_states:
            require_states()
    elif args.command == 'states':
        generate_states(args.rom, args.png_dir)


if __name__ == '__main__':
    main()
