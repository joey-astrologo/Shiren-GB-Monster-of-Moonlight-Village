#!/usr/bin/env python3
"""Plane-exact stress test for the five-row proportional clear-condition list.

The real condition selector depends on completed-save flags, so this fixture enters its
real bank-4 screen handler through the normal menu dispatcher, replaces only the flag-
dependent row stager at ``4:$4D63``, and then lets the real box-44 descriptor, bank-31
drawer, proportional allocator, VBlank queue, shadow map, and borders run unchanged.

Two pages are tested:

* the five widest current translations, proving the 56/57-tile primary-run edge;
* a synthetic 21-glyph row, proving the approved source-count edge through this exact
  screen path independently of the current English wording.

    python3 tools/conditionspill.py build/shiren_en.gb
    python3 tools/conditionspill.py build/shiren_en.gb --png-dir build/conditionspill

Exit 1 if any row falls back, crosses an allocator run, or differs in either bitplane.
"""
import argparse
import json
import os

from gbrun import _import_pyboy, PRESS_FRAMES
import build
import dialogue_preview as dialogue
import menuspill


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
SCRIPT = os.path.join(ROOT, 'script', 'script.json')
EN = os.path.join(ROOT, 'script', 'en.tsv')
DISPATCH = (4, 0x48AA)
CONDITION_STAGER_CALL = (4, 0x4D63)
CONDITION_STAGER_RETURN = 0x4D66
STAGING = 0xC616
SHAPE = (0, 6, 5, 18, 0)


def translations(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#') or '\t' not in line:
            continue
        loc, text = line.split('\t', 1)
        out[loc] = text
    return out


def condition_rows(profile, ranked=True):
    manifest = json.load(open(SCRIPT, encoding='utf-8'))
    translated = translations(EN)
    rows = []
    for row in manifest['strings']:
        if not dialogue.is_clear_condition(row):
            continue
        text = translated[row['loc']]
        codes = list(build.encode_en(text, row['bank']))
        tiles = len(menuspill.compose(codes, profile))
        rows.append((tiles, row['loc'], text, codes))
    if ranked:
        rows.sort(key=lambda item: (-item[0], item[1]))
    if len(rows) != 40:
        raise SystemExit('conditionspill: expected 40 translated condition rows, found %d'
                         % len(rows))
    return rows


def run_case(PyBoy, rom, profile, label, rows, png=None):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(STATE, 'rb') as state:
        pb.load_state(state)

    payload = b''.join(bytes(codes) + b'\xFF' for _tiles, _loc, _text, codes in rows)
    if len(payload) > 0x84:
        raise SystemExit('conditionspill: %s staging needs %d/132 bytes'
                         % (label, len(payload)))

    dispatches = {'n': 0}
    skipped = {'n': 0}
    seen = []
    drawn = {}

    def at_dispatch(_ctx=None):
        dispatches['n'] += 1
        if dispatches['n'] == 1:
            pb.register_file.A = 34

    def at_stager(_ctx=None):
        skipped['n'] += 1
        for index, value in enumerate(payload):
            pb.memory[STAGING + index] = value
        for index in range(len(payload), 0x84):
            pb.memory[STAGING + index] = 0
        # Skip only ``call $79E4``. The following real ``ld a,$2C / rst $08`` draws
        # box 44 and installs all ordinary descriptor metadata.
        pb.register_file.PC = CONDITION_STAGER_RETURN

    def at_row(_ctx=None):
        shape = tuple(pb.memory[addr] for addr in range(0xC69A, 0xC69F))
        if shape != SHAPE:
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        codes = []
        for addr in range(source, source + 32):
            value = pb.memory[addr]
            if value == 0xFF:
                break
            codes.append(value)
        key = pb.register_file.HL
        seen.append((pb.register_file.D, key, tuple(codes)))
        drawn[key] = codes

    pb.hook_register(*DISPATCH, at_dispatch, None)
    pb.hook_register(*CONDITION_STAGER_CALL, at_stager, None)
    pb.hook_register(menuspill.FAR_BANK, profile['entry'], at_row, None)

    for frame in range(360):
        if frame == 60:
            pb.button('b', PRESS_FRAMES)
        pb.tick()

    problems = []
    if skipped['n'] != 1:
        problems.append('flag-dependent stager interception fired %d time(s), expected 1'
                        % skipped['n'])
    if sorted(row for row, _key, _codes in seen) != list(range(5)):
        problems.append('condition row calls were %s, expected 0-4'
                        % sorted(row for row, _key, _codes in seen))

    recs = menuspill.records(pb, profile)
    target_recs = [record for record in recs if record[0] in drawn]
    if len(target_recs) != 5:
        problems.append('%d/5 condition rows allocated proportionally' % len(target_recs))
    by_key = {key: (base, cap, raw) for key, base, cap, raw in target_recs}
    for _rownum, key, codes in seen:
        record = by_key.get(key)
        if record is None:
            continue
        base, cap, raw = record
        need = menuspill.capneed(len(menuspill.compose(codes, profile)))
        if raw != 0:
            problems.append('row $%04X retained %d raw prefix cell(s)' % (key, raw))
        if cap != need:
            problems.append('row $%04X cap %d, expected %d' % (key, cap, need))
        if not any(lo <= base and base + cap <= hi for lo, hi in profile['runs']):
            problems.append('row $%04X slice $%02X+%d crosses an allocator run'
                            % (key, base, cap))

    checked = [0]
    problems += menuspill.settled_check(pb, profile, label, checked, drawn)
    bad = menuspill.frame_invariant(pb, profile)
    if bad:
        problems.append('%d visible pool cell(s) lack an exact owner; first %s'
                        % (len(bad), bad[0]))
    if checked[0] != 5:
        problems.append('%d/5 settled rows verified plane-exact' % checked[0])
    if png:
        pb.screen.image.save(png)
    pb.stop(save=False)
    return problems, checked[0], sum(cap for _key, _base, cap, _raw in target_recs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('conditionspill: requires the Dot proportional renderer')
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)

    rows = condition_rows(profile)
    ordered = condition_rows(profile, ranked=False)
    widest = rows[:5]
    source_text = 'i' * dialogue.HELP_WIDTH
    source_codes = list(build.encode_en(source_text, 14))
    source_edge = (len(menuspill.compose(source_codes, profile)),
                   '<synthetic-source-edge>', source_text, source_codes)
    source_page = [source_edge] + widest[:4]
    cases = [('widest-five', widest), ('source-21', source_page)]
    cases += [('all-%02d-%02d' % (start + 1, start + 5), ordered[start:start + 5])
              for start in range(0, 40, 5)]

    PyBoy = _import_pyboy()
    problems = []
    for label, page in cases:
        png = (os.path.join(args.png_dir, label + '.png') if args.png_dir else None)
        case_problems, checked, tiles = run_case(
            PyBoy, args.rom, profile, label, page, png)
        print('  %-14s %d row(s) plane-exact, %d allocator tiles, %d problem(s)%s'
              % (label, checked, tiles, len(case_problems),
                 ' -> ' + png if png else ''))
        problems += ['%s: %s' % (label, problem) for problem in case_problems]

    for problem in problems[:20]:
        print('  ' + problem)
    print('conditionspill: %d problem(s)' % len(problems))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
