#!/usr/bin/env python3
"""Exercise every textual VWF glyph through item-list and item-information paths.

The proportional dialogue composer has an instruction-level exhaustive self-test in
``propvwf.py --selftest``.  This companion drives the two independent menu consumers in
PyBoy.  It divides the complete admitted textual repertoire across five rows, injects
those rows only after the game has staged a real screen, and compares the live VRAM
planes against the installed shared pre-shift table.

`$81` is intentionally absent from the textual rows: it is the native cursor cell and
remains raw outside the VWF payload.  Existing item/Floor route checks cover that raw
cell.  Tilde is intentionally absent from the shipped font contract.  Everything else
in ``propvwf.DOT_CODES``—letters, digits, punctuation, parentheses, `$88` unidentified
star and `$8A` plating star—must allocate and render proportionally in both paths.
"""
import argparse
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
import propvwf                                                    # noqa: E402


STAGING = menuspill.STAGING
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
INFO_SHAPE = (0, 3, 5, 18, 0x00)
TEXT_CODES = tuple(code for code in propvwf.DOT_CODES if code != 0x81)
# Start with a round-robin distribution to mix narrow/wide/core/sparse codes.  Move one
# glyph out of row 1 so every synthetic Item row respects the runtime's exact 11-tile
# slice contract; all rows remain below both source-character ceilings.
_ROUND_ROBIN = tuple(tuple(TEXT_CODES[index::5]) for index in range(5))
ROWS = (_ROUND_ROBIN[0], _ROUND_ROBIN[1][1:], _ROUND_ROBIN[2],
        _ROUND_ROBIN[3] + _ROUND_ROBIN[1][:1], _ROUND_ROBIN[4])


def packed_rows(raw):
    out = bytearray()
    for codes in ROWS:
        if raw:
            out += bytes((0, 0))
        out += bytes(codes) + b'\xFF'
    return bytes(out)


def read_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(out)
        out.append(value)
    return tuple(out)


def run_case(rom, profile, kind, png=None):
    if kind not in ('item', 'info'):
        raise ValueError(kind)
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open('saves/dungeon.state', 'rb') as state:
        pb.load_state(state)

    shape = ITEM_SHAPE if kind == 'item' else INFO_SHAPE
    raw = 2 if kind == 'item' else 0
    payload = packed_rows(raw)
    rewritten = [False]
    events = {}
    dispatches = []

    def dispatch(_ctx=None):
        dispatches.append(pb.register_file.A)
        if kind != 'info' or len(dispatches) != 1:
            return
        # Real box-7 item-information dispatch, as used by menuspill's help battery.
        pb.memory[0xCF7A] = 4
        pb.memory[0xCF7B] = 0x80
        pb.memory[0xC6BC] = 0
        pb.register_file.A = 4

    def far_entry(_ctx=None):
        current_shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        row_number = pb.register_file.D
        if current_shape != shape or not 0 <= row_number < 5:
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        if row_number == 0 and not rewritten[0]:
            if source != STAGING:
                return
            for offset, value in enumerate(payload):
                pb.memory[STAGING + offset] = value
            rewritten[0] = True
        if rewritten[0]:
            events[row_number] = (pb.register_file.HL, source, read_row(pb, source))

    pb.hook_register(4, 0x48AA, dispatch, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
    script = ({60: 'b', 120: 'a'} if kind == 'item' else {120: 'b'})
    frames = 360 if kind == 'item' else 600
    for frame in range(frames):
        button = script.get(frame)
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()

    problems = []
    if not rewritten[0]:
        problems.append('%s five-row payload was never injected' % kind)
    records = menuspill.records(pb, profile)
    for row_number, codes in enumerate(ROWS):
        event = events.get(row_number)
        if event is None:
            problems.append('%s row %d never reached the renderer' % (kind, row_number))
            continue
        key, _source, staged = event
        expected = ((0, 0) + codes if raw else codes)
        if staged != expected:
            problems.append('%s row %d staged %s, expected %s'
                            % (kind, row_number,
                               ' '.join('$%02X' % code for code in staged),
                               ' '.join('$%02X' % code for code in expected)))
            continue
        matching = [record for record in records
                    if record[0] == key and record[3] == raw]
        if not matching:
            problems.append('%s row %d fell back to fixed width' % (kind, row_number))
            continue
        allowed_runs = menuspill.INFO_LOW_RUN if kind == 'info' else None
        if not menuspill.visible_row_matches(
                pb, profile, key, list(codes), raw=raw,
                allowed_runs=allowed_runs):
            problems.append('%s row %d visible planes differ' % (kind, row_number))
    if png:
        pb.screen.image.save(png)
        print('menuglyphspill: wrote ' + png)
    pb.stop(save=False)
    print('  %-4s: %d/5 row calls, %d allocator record(s), %d problem(s)'
          % (kind, len(events), len(records), len(problems)))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists('saves/dungeon.state'):
        raise SystemExit('menuglyphspill: missing saves/dungeon.state')
    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('menuglyphspill: requires the proportional renderer')
    partition = tuple(code for row in ROWS for code in row)
    if (any(len(row) > 18 for row in ROWS) or
            len(partition) != len(TEXT_CODES) or
            len(set(partition)) != len(partition) or
            set(partition) != set(TEXT_CODES)):
        raise SystemExit('menuglyphspill: internal repertoire partition is invalid')
    tile_counts = tuple(len(menuspill.compose(row, profile)) for row in ROWS)
    if any(count > 11 for count in tile_counts):
        raise SystemExit('menuglyphspill: synthetic Item rows exceed the 11-tile '
                         'runtime contract: %s' % (tile_counts,))

    problems = []
    for kind in ('item', 'info'):
        shot = None
        if args.png:
            stem, ext = os.path.splitext(args.png)
            shot = stem + '_' + kind + (ext or '.png')
        problems += ['%s: %s' % (kind, problem)
                     for problem in run_case(args.rom, profile, kind, shot)]
    print('menuglyphspill: %d textual codes across both paths; raw `$81` cursor covered '
          'by route tests; %d problem(s)' % (len(TEXT_CODES), len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('menuglyphspill: failed')
    print('menuglyphspill: every admitted textual glyph is VWF in Items and item Info')


if __name__ == '__main__':
    main()
