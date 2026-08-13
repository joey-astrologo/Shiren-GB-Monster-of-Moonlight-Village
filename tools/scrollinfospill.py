#!/usr/bin/env python3
"""Regression for the five-choice Scroll Floor/Info return.

Log 2 in ``shiren_en_log2_scroll_menu.srm`` stands on a Scroll. The shared Floor
route opens Info and returns with B. Info's old bottom edge at row 11 must become an
interior spacer, with the Scroll picker's sole bottom edge restored on row 13.
"""
import argparse
import os

from storagepotinfospill import run


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_scroll_menu.srm')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('scrollinfospill: missing %s' % path)
    return run(args.rom, args.ram, args.png, action_count=5, label='scrollinfospill')


if __name__ == '__main__':
    raise SystemExit(main())
