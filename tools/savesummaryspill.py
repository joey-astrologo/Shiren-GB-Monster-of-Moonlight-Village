#!/usr/bin/env python3
"""Plane-exact save-summary regression for long and fixed-width locations.

These SRAM-backed scenarios exercise distinct producers for Log 1's location row:

* a numberless ``Dragon's Maw`` that used to retain four native indent cells;
* ``19F Dragon's Maw``, whose tail used to spill into and consume the difficulty row;
* `` 5F Koma Cave``, which used to fall back to the fixed-width menu font;
* the table's final place key, forced at the real producer, which must render the full
  nine-tile ``Moonlight Exit`` row rather than the former ``Moon Exit`` spelling;
* the real `` 1F Moonlight Exit`` save and a producer-level ``50F`` override, which
  prove both ends of the reachable floor range fit the widened eleven-tile slice.

The shared start-flow audit proves the shadow map and both VRAM bitplanes at the drawer
epilogue. This wrapper additionally checks the exact logical payload and that the save's
difficulty still reaches row 2 after a long location is composed.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy                              # noqa: E402
import menuspill                                             # noqa: E402
import menuvwf                                               # noqa: E402
import propvwf                                               # noqa: E402
import startspill                                            # noqa: E402


FIXTURES = (
    ('numberless Dragon\'s Maw', 'shiren_en_log_1_talk_to_koppa.srm',
     "Dragon's Maw", 'Hard', None, None, None),
    ('numbered Dragon\'s Maw', 'shiren_en_log_1_dragons_maw.srm',
     "19F Dragon's Maw", 'Hard', None, None, None),
    ('numbered Koma Cave', 'shiren_en_log_1_fixed_width_save_info.srm',
     ' 5F Koma Cave', 'Hard', None, None, None),
    ('forced Moonlight Exit', 'shiren_en_log_1_talk_to_koppa.srm',
     'Moonlight Exit', 'Hard', 0x15, None, 9),
    ('numbered Moonlight Exit', 'shiren_en_log1_moonlight_exit.srm',
     ' 1F Moonlight Exit', 'Expert', None, None, 11),
    ('floor-50 Moonlight Exit', 'shiren_en_log1_moonlight_exit.srm',
     '50F Moonlight Exit', 'Expert', 0x15, '50F ', 11),
)


def encode(text):
    return bytes(propvwf.EN_CODES[ch] for ch in text)


class SummaryAudit(startspill.Audit):
    def __init__(self, profile, scenario):
        super().__init__(profile, scenario)
        self.summary_rows = []

    def at_entry(self, pb):
        super().at_entry(pb)
        pending = self.pending
        if pending is not None and pending.label == 'summary':
            self.summary_rows.append((pending.row, bytes(pending.cells), pending.source))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('savesummaryspill: missing %s' % args.rom)
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)

    paths = []
    for label, filename, expected, difficulty, force_key, force_prefix, expected_tiles \
            in FIXTURES:
        path = os.path.join(ROOT, 'saves', filename)
        if not os.path.exists(path):
            raise SystemExit('savesummaryspill: missing %s' % path)
        paths.append((label, path, expected, difficulty, force_key, force_prefix,
                      expected_tiles))

    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('savesummaryspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    audits = []
    problems = []
    for label, ram, expected, expected_difficulty, force_key, force_prefix, \
            expected_tiles in paths:
        png = None
        if args.png_dir:
            safe = ''.join(ch.lower() if ch.isalnum() else '_' for ch in label).strip('_')
            png = os.path.join(args.png_dir, safe + '.png')
        hook_setup = None
        if force_key is not None or force_prefix is not None:
            def hook_setup(pb, _audit, key=force_key, prefix=force_prefix):
                def force_place(_ctx=None):
                    if key is not None:
                        pb.register_file.A = key
                    if prefix is not None:
                        at = (pb.register_file.D << 8) | pb.register_file.E
                        for offset, value in enumerate(encode(prefix)):
                            pb.memory[at + offset] = value
                pb.hook_register(4, menuvwf.SUMMARY_PRODUCER_AT, force_place, None)

        audit = startspill.run_scenario(
            PyBoy, args.rom, profile, label, 340,
            startspill.boot_script({300: ('a',)}), ram=ram, png=png,
            audit_class=SummaryAudit, hook_setup=hook_setup)
        audits.append(audit)
        rows = {row: (cells, source) for row, cells, source in audit.summary_rows}
        if set(rows) != {0, 1, 2}:
            problems.append('%s reached summary rows %s, expected 0/1/2' %
                            (label, sorted(rows)))
            continue
        cells, source = rows[1]
        wanted = encode(expected)
        if cells != wanted:
            problems.append('%s row 1 source $%04X differs: want %s got %s' %
                            (label, source, wanted.hex(), cells.hex()))
        if expected_tiles is not None:
            tiles = menuspill.compose(cells, profile)
            if len(tiles) != expected_tiles:
                problems.append('%s paints %d tiles, expected %d for the complete '
                                'Moonlight Exit row' %
                                (label, len(tiles), expected_tiles))
        difficulty, source = rows[2]
        while difficulty and difficulty[0] == propvwf.EN_CODES[' ']:
            difficulty = difficulty[1:]
        while difficulty and difficulty[-1] == propvwf.EN_CODES[' ']:
            difficulty = difficulty[:-1]
        wanted = encode(expected_difficulty)
        if difficulty != wanted:
            problems.append('%s row 2 source $%04X differs: want %s (%s), got %s' %
                            (label, source, expected_difficulty, wanted.hex(),
                             difficulty.hex()))

    problems.extend('%s: %s' % (audit.scenario, problem)
                    for audit in audits for problem in audit.problems)
    for problem in problems[:20]:
        print('  ' + problem)
    print('savesummaryspill: %d fixture(s), %d exact row(s), %d visible plane '
          'check(s), %d problem(s)' %
          (len(audits), sum(audit.exact for audit in audits),
           sum(audit.visible for audit in audits), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
