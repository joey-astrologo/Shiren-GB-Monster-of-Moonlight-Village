#!/usr/bin/env python3
"""Regression for the Log-2 three-choice Gitan Floor/Info return.

The fixture stands immediately above Gitan. After Floor -> Info is dismissed with A,
the native Take/Toss/Info box ends on row 9. Info's former row-11 bottom edge must be
blank rather than surviving as a detached horizontal bar.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from storagepotinfospill import run  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_gitan_menu_boarder.srm')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('gitanmenuborderspill: missing %s' % path)
    return run(args.rom, args.ram, args.png, action_count=3,
               label='gitanmenuborderspill', dismiss_button='a')


if __name__ == '__main__':
    raise SystemExit(main())
