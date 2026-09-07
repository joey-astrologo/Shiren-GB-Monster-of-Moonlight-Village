#!/usr/bin/env python3
"""Regress build failures, ROM-specific maps, and preview/wrapper source budgets.

Uses isolated translation copies and temporary ROMs; requires the extracted script and
expanded base. --state additionally repeats the live scan that exposed map clobbering.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_LOC = '14:$4255'
BOUNDARY_TEXT = 'Throw all unwanted items here.<end><brk> They cannot be retrieved.'


def run(tool, *args):
    return subprocess.run([sys.executable, str(ROOT / 'tools' / tool),
                           *(str(arg) for arg in args)], cwd=ROOT,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def require(ok, detail):
    if not ok:
        raise AssertionError(detail)


def translated_copy(path, loc, text):
    lines = (ROOT / 'script/en.tsv').read_text(encoding='utf-8').splitlines()
    require(sum(line.startswith(loc + '\t') for line in lines) == 1,
            'fixture translation must have exactly one ' + loc)
    path.write_text('\n'.join(loc + '\t' + text if line.startswith(loc + '\t')
                              else line for line in lines) + '\n', encoding='utf-8')
    return path


def build(tsv, rom, *flags):
    return run('build.py', ROOT / 'build/_base_expanded.gb', tsv, rom,
               '--dot-font', '--report', rom.with_suffix('.worklist.tsv'), *flags)


def map_path(rom):
    return Path(str(rom) + '.relocmap.tsv')


def rejection(directory):
    tsv = translated_copy(directory / 'invalid.tsv', '14:$51D3',
                          'Keyaki: Shiren! Wait up!')
    rom = directory / 'invalid.gb'
    result = build(tsv, rom)
    require('token_lost' in result.stdout, result.stdout)
    require(result.returncode != 0, 'token_lost build returned success')
    require(not rom.exists() and not map_path(rom).exists(),
            'failed build published an artifact')
    require('token_lost' in rom.with_suffix('.worklist.tsv').read_text(),
            'failed build did not write its worklist')
    # Failure must also preserve an existing successful output and its matching map.
    rom.write_bytes(b'existing ROM')
    map_path(rom).write_bytes(b'existing map')
    result = build(tsv, rom)
    require(result.returncode != 0, 'replacement build returned success')
    require(rom.read_bytes() == b'existing ROM' and
            map_path(rom).read_bytes() == b'existing map',
            'failed build overwrote an existing output')


def preview(directory):
    tsv = translated_copy(directory / 'boundary.tsv', BOUNDARY_LOC, BOUNDARY_TEXT)
    result = run('dialogue_preview.py', BOUNDARY_LOC, '--en', tsv, '--check')
    require(result.returncode != 0 and 'line_too_long' in result.stdout and
            'line_too_wide_px' in result.stdout, result.stdout)
    rom = directory / 'boundary.gb'
    result = build(tsv, rom)
    require(result.returncode != 0 and not rom.exists(), result.stdout)
    report = rom.with_suffix('.worklist.tsv').read_text()
    require('31 glyphs' in report and '147px' in report, report)


def wrapper(directory):
    draft = directory / 'draft.tsv'
    draft.write_text(BOUNDARY_LOC + '\t' + BOUNDARY_TEXT.replace('<end>', '') + '\n')
    result = run('wrap_en.py', draft)
    require(result.returncode == 0, result.stdout)
    rows = [line for line in result.stdout.splitlines()
            if line.startswith(BOUNDARY_LOC + '\t')]
    require(len(rows) == 1, result.stdout)
    wrapped = rows[0].split('\t', 1)[1]
    require('<br>' in wrapped.split('<end>')[0],
            'wrapper did not reserve the source first-line indent')
    require(not wrapped.startswith(' '), 'wrapper authored the builder-owned indent')
    tsv = translated_copy(directory / 'wrapped.tsv', BOUNDARY_LOC, wrapped)
    result = run('dialogue_preview.py', BOUNDARY_LOC, '--en', tsv, '--check')
    require(result.returncode == 0, result.stdout)
    result = build(tsv, directory / 'wrapped.gb')
    require(result.returncode == 0, result.stdout)


def maps(directory, state):
    normal, redirect = directory / 'normal.gb', directory / 'redirect.gb'
    result = build(ROOT / 'script/en.tsv', normal)
    require(result.returncode == 0, result.stdout)
    require(map_path(normal).exists(), 'normal build did not write its own map')
    original_map = map_path(normal).read_bytes()
    require(hashlib.sha256(normal.read_bytes()).hexdigest().encode() in original_map,
            'map is not bound to the ROM hash')
    # A stale shared map must never be consulted, including by the continuation reader.
    (directory / 'relocmap.tsv').write_text('invalid legacy map\n')
    scan_args = ('--dte-scan', '--state', state, '--frames', '1800', '--walk-seed', '1')
    before = run('gbrun.py', normal, *scan_args) if state else None
    if before:
        require(before.returncode == 0 and '13:$4B66' in before.stdout, before.stdout)
    result = build(ROOT / 'script/en.tsv', redirect, '--redirect-all')
    require(result.returncode == 0, result.stdout)
    require(map_path(normal).read_bytes() == original_map,
            'redirect-all build clobbered the normal map')
    require(map_path(redirect).read_bytes() != original_map, 'layouts need distinct maps')
    if state:
        after = run('gbrun.py', normal, *scan_args)
        require(after.returncode == 0 and after.stdout == before.stdout, after.stdout)
    # Fail before emulator startup rather than interpreting a map from another ROM.
    map_path(normal).write_bytes(map_path(redirect).read_bytes())
    result = run('gbrun.py', normal, '--dte-scan', '--frames', '1')
    require(result.returncode != 0 and 'hash mismatch' in result.stdout, result.stdout)
    result = run('boxscan.py', normal, '--frames', '1')
    require(result.returncode != 0 and 'hash mismatch' in result.stdout, result.stdout)
    map_path(normal).unlink()
    result = run('gbrun.py', normal, '--dte-scan', '--frames', '1')
    require(result.returncode != 0 and 'missing' in result.stdout and
            str(map_path(normal)) in result.stdout, result.stdout)


def native_control(directory):
    rom = directory / 'native.gb'
    result = build(ROOT / 'script/en.tsv', rom, '--native-box-fallback')
    require(result.returncode != 0 and not rom.exists(),
            'native fallback was accepted on a production renderer')
    result = build(ROOT / 'script/en.tsv', rom, '--no-menuvwf')
    require(result.returncode != 0 and 'box_too_wide' in result.stdout and
            not rom.exists(), 'native box fallback was not explicitly requested')
    flags = ('--no-menuvwf', '--native-box-fallback')
    result = build(ROOT / 'script/en.tsv', rom, *flags)
    require(result.returncode == 0 and 'diagnostic native fallback' in result.stdout,
            result.stdout)
    require(not rom.with_suffix('.worklist.tsv').exists(),
            'successful build retained the failed build worklist')
    original = rom.read_bytes()
    tsv = translated_copy(directory / 'invalid-native.tsv', '14:$51D3',
                          'Keyaki: Shiren! Wait up!')
    result = build(tsv, rom, *flags)
    require(result.returncode != 0 and rom.read_bytes() == original,
            'diagnostic fallback admitted a lost control token')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', help='generated dungeon state for the live map scan')
    args = parser.parse_args()
    cases = [('failed-build outputs', rejection), ('preview indent', preview),
             ('wrapper indent', wrapper), ('ROM maps', lambda d: maps(d, args.state)),
             ('native diagnostic control', native_control)]
    bad = 0
    with tempfile.TemporaryDirectory(prefix='shiren-toolchain-') as temporary:
        for index, (label, check) in enumerate(cases):
            directory = Path(temporary) / str(index)
            directory.mkdir()
            try:
                check(directory)
                print('toolchaincheck: PASS ' + label, flush=True)
            except AssertionError as error:
                bad += 1
                print('toolchaincheck: FAIL %s: %s' % (label, error), flush=True)
    print('toolchaincheck: %d case(s), %d failure(s)' % (len(cases), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
