#!/usr/bin/env python3
"""Save-dependent opening titles: selector, approved subtitle artwork and SGB attributes.

Native title producer ``30:$7F0C`` has three opening variants, chosen at ``31:$489E`` from
bits 2-3 of each occupied log's progress byte. The English build draws the illustrated
title for each, with Joey's approved scroll subtitle:

    0  before Hard is cleared       Monsters of Moonlight Village
    1  Hard cleared (Orochi)        Escape from Moonlight Village
    2  Moonlight Exit cleared       Lover of Moonlight Village

Every route below boots an unmodified curated SRAM fixture and requires:

* the variant A entering the producer hook at ``31:$48A1``;
* the settled 160x144 screen to equal that variant's approved raster pixel for pixel
  (``titlelogo.approved_raster``: embedded base title + embedded approved subtitle);
* the 90-byte SGB ATTR_TRN file actually in VRAM ``$8000`` when ``29:$411F`` sends the
  ATTR_TRN packet ``29:$479D`` to be the English attribute map. PyBoy is not a Super Game
  Boy, so ``$FFCD`` is forced non-zero only for the title's ``29:$401A`` setup call;
* the log summaries to be built exactly once per title (``15:$4F90`` takes 12-42 frames,
  and a second pass delayed the title past frame-timed input routes); and
* HRAM ``$FF90-$FF92`` at the producer hook to hold exactly the native selector's scratch
  (each present log's progress byte, else zero).

Expected variants are cross-checked against the progress bytes read straight from each
``.srm`` (presence at SRAM bank 3 ``$BFF3+``, progress at bank 2 ``$AE92 + $780 * log``).

The ending route replays ``shiren_en-moonlight-ending.srm`` through the credits and
requires the English attribute map for the case-3 Fin card's own SGB setup
(``31:$7993``); ``moonlighttitlespill.py`` owns the Fin card's pixels.

usage: titlevariantspill.py ROM [--no-ending] [--png-dir DIR]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import titlelogo                                                  # noqa: E402
from endingcreditspill import ADVANCE_UNTIL, BOOT                 # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                     # noqa: E402
from titlelogospill import TITLE_FRAME, TITLE_ROUTE               # noqa: E402


SAVES = os.path.join(ROOT, 'saves')
ROUTES = (
    ('fresh', None, 0),
    ('before-hard', 'shiren_en_log_1_trigger_ending.srm', 0),
    ('v0.96-report', 'shiren_en096_broken_title_screen.srm', 0),
    ('hard-cleared', 'shiren_en_log_1_orochi_symbol.srm', 1),
    ('moonlight-49f', 'shiren_en-moonlight-ending.srm', 1),
    ('moonlight-cleared', 'shiren_en-moonlight-clear-icon.srm', 2),
)
ENDING_RAM = 'shiren_en-moonlight-ending.srm'
ENDING_FRAMES = 17000
SGB_FRAME_LIMIT = 3000

PRODUCER_CALL = (31, 0x48A1)
TITLE_SETUP = (31, 0x4891)          # first byte after the native SGB-index choice
ENDING_SETUP = (31, 0x7993)
ENDING_SETUP_OLD = bytes.fromhex('d7 17 1d')
SGB_SETUP = (29, 0x401A)
SGB_SETUP_EXIT = (29, 0x4059)
SGB_PACKET = (29, 0x411F)
ATTR_TRN_PACKET = 0x479D
SGB_FLAG = 0xFFCD
SELECTOR_SCRATCH = (0xFF90, 0xFF91, 0xFF92)
SUMMARY_BUILDER = (15, 0x4F90)
SRAM_BANK = 0x2000
PRESENCE_AT = (3, 0xBFF2)
PROGRESS_AT = (2, 0xAE80, 0x780, 18)
ATTR_BYTES = 90


def _off(bank, addr):
    return bank * 0x4000 + addr - (0x4000 if bank else 0)


def _srm_progress(ram):
    """-> per-log progress byte, or None for an empty log, read from the battery file."""
    if not ram:
        return [None, None, None]
    data = open(ram, 'rb').read()
    bank, base = PRESENCE_AT
    pbank, pbase, stride, within = PROGRESS_AT
    out = []
    for log in range(3):
        present = data[bank * SRAM_BANK + base - 0xA000 + 1 + log]
        progress = data[pbank * SRAM_BANK + pbase - 0xA000 + stride * log + within]
        out.append(progress if present else None)
    return out


def _variant(progress):
    bits = 0
    for value in progress:
        if value is not None:
            bits |= value
    variant = (bits & 0x0C) >> 2
    return 2 if variant == 3 else variant


def _title(PyBoy, rom, ram, sgb):
    """Boot to the settled title; return screen, selector result and SGB observations."""
    if ram:
        shutil.copyfile(ram, rom + '.ram')
    elif os.path.exists(rom + '.ram'):
        os.remove(rom + '.ram')
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    seen = {'variant': [], 'attr': [], 'scratch': [], 'builds': 0}
    in_title_setup = [False]

    def producer(_ctx):
        in_title_setup[0] = False
        seen['variant'].append(pb.register_file.A)
        seen['scratch'].append(tuple(pb.memory[a] for a in SELECTOR_SCRATCH))

    def builder(_ctx):
        if not seen['variant']:
            seen['builds'] += 1

    # The SGB setup and the selector both sit between the native index choice and the
    # producer call, in either order, so that span is the title-setup window.
    def title_setup(_ctx):
        in_title_setup[0] = True

    def sgb_setup(_ctx):
        if sgb and in_title_setup[0]:
            pb.memory[SGB_FLAG] = 1

    def sgb_exit(_ctx):
        if sgb and in_title_setup[0]:
            pb.memory[SGB_FLAG] = 0

    def packet(_ctx):
        if in_title_setup[0] and pb.register_file.HL == ATTR_TRN_PACKET:
            seen['attr'].append(bytes(pb.memory[0x8000 + i] for i in range(ATTR_BYTES)))

    pb.hook_register(*PRODUCER_CALL, producer, None)
    pb.hook_register(*SUMMARY_BUILDER, builder, None)
    pb.hook_register(*TITLE_SETUP, title_setup, None)
    pb.hook_register(*SGB_SETUP, sgb_setup, None)
    pb.hook_register(*SGB_SETUP_EXIT, sgb_exit, None)
    pb.hook_register(*SGB_PACKET, packet, None)
    # A forced SGB setup also runs the border upload and its packet waits, so that run
    # continues until the setup call has returned; its screen is not compared.
    for frame in range(SGB_FRAME_LIMIT if sgb else TITLE_FRAME + 1):
        if frame in TITLE_ROUTE:
            pb.button(TITLE_ROUTE[frame], PRESS_FRAMES)
        pb.tick()
        if sgb and seen['variant']:
            break
    seen['image'] = pb.screen.image.copy().convert('RGB')
    pb.stop(save=False)
    return seen


def _ending_attr(PyBoy, rom, ram):
    """Replay the Moonlight ending; return the ATTR_TRN file of the case-3 SGB setup."""
    shutil.copyfile(ram, rom + '.ram')
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    state = {'armed': False, 'attr': None}

    def ending_setup(_ctx):
        state['armed'] = True

    def sgb_setup(_ctx):
        if state['armed']:
            pb.memory[SGB_FLAG] = 1

    def sgb_exit(_ctx):
        if state['armed']:
            pb.memory[SGB_FLAG] = 0
            state['armed'] = False

    def packet(_ctx):
        if state['armed'] and pb.register_file.HL == ATTR_TRN_PACKET:
            state['attr'] = bytes(pb.memory[0x8000 + i] for i in range(ATTR_BYTES))

    pb.hook_register(*ENDING_SETUP, ending_setup, None)
    pb.hook_register(*SGB_SETUP, sgb_setup, None)
    pb.hook_register(*SGB_SETUP_EXIT, sgb_exit, None)
    pb.hook_register(*SGB_PACKET, packet, None)
    for frame in range(ENDING_FRAMES):
        for button in BOOT.get(frame, ()):
            pb.button(button, PRESS_FRAMES)
        if 2660 <= frame < ADVANCE_UNTIL and (frame - 2660) % 60 == 0:
            pb.button('a', PRESS_FRAMES)
        pb.tick()
        if state['attr'] is not None:
            break
    pb.stop(save=False)
    return state['attr']


def _pack_name(pack):
    if pack == titlelogo.SGB_ATTRIBUTE_PACK:
        return 'English'
    if pack == titlelogo.SGB_NATIVE_ATTRIBUTE_PACK:
        return 'native Japanese'
    return 'unknown'


def run(rom, ending=True, png_dir=None):
    PyBoy = _import_pyboy()
    data = open(rom, 'rb').read()
    at = _off(*ENDING_SETUP)
    if data[at - 2:at + 3] != b'\x3E\x0C' + ENDING_SETUP_OLD:
        raise SystemExit('titlevariantspill: Moonlight case-3 SGB setup moved')
    problems = []
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    shades = {255: 0, 153: 1, 85: 2, 0: 3}
    with tempfile.TemporaryDirectory(prefix='titlevariantspill-') as tmp:
        for label, name, expected in ROUTES:
            ram = os.path.join(SAVES, name) if name else None
            if ram and not os.path.exists(ram):
                raise SystemExit('titlevariantspill: missing %s' % ram)
            work = os.path.join(tmp, 'route.gb')
            shutil.copyfile(rom, work)
            seen = _title(PyBoy, work, ram, sgb=False)
            shutil.copyfile(rom, work)
            sgb = _title(PyBoy, work, ram, sgb=True)
            image = seen['image']
            if png_dir:
                image.save(os.path.join(png_dir, label + '.png'))

            progress = _srm_progress(ram)
            if _variant(progress) != expected:
                raise SystemExit('titlevariantspill: %s progress %s implies variant %d, '
                                 'route table says %d'
                                 % (name, progress, _variant(progress), expected))
            variants = sorted(set(seen['variant']))
            if variants != [expected]:
                problems.append('%s: title selector returned %s, expected %d'
                                % (label, variants, expected))
            subtitle = titlelogo.VARIANT_FOR_A[expected]
            pixels = bytes(shades[value[0]] for value in image.getdata())
            if pixels != titlelogo.approved_raster(subtitle):
                problems.append('%s: screen differs from the approved %s title raster'
                                % (label, subtitle))

            want_pack = titlelogo.SGB_ATTRIBUTE_PACK
            if len(sgb['attr']) != 1:
                problems.append('%s: observed %d SGB title ATTR_TRN transfers, expected 1'
                                % (label, len(sgb['attr'])))
            elif sgb['attr'][0] != want_pack:
                problems.append('%s: SGB title attribute map is %s, expected %s'
                                % (label, _pack_name(sgb['attr'][0]),
                                   _pack_name(want_pack)))
            scratch = tuple(0 if value is None else value for value in progress)
            for kind, run_seen in (('DMG', seen), ('SGB', sgb)):
                if run_seen['builds'] != 1:
                    problems.append('%s: %s title built the log summaries %d times, '
                                    'expected once' % (label, kind, run_seen['builds']))
                if run_seen['scratch'] != [scratch]:
                    problems.append('%s: %s producer saw $FF90-$FF92 %s, expected the '
                                    'selector scratch %s'
                                    % (label, kind, run_seen['scratch'], scratch))
            print('titlevariantspill: %-17s variant %s, %s title, SGB %s attributes'
                  % (label, variants, subtitle,
                     _pack_name(sgb['attr'][0]) if sgb['attr'] else 'none'))

        if ending:
            ram = os.path.join(SAVES, ENDING_RAM)
            work = os.path.join(tmp, 'ending.gb')
            shutil.copyfile(rom, work)
            attr = _ending_attr(PyBoy, work, ram)
            if attr is None:
                problems.append('ending: Moonlight case-3 SGB ATTR_TRN was not reached')
            elif attr != titlelogo.SGB_ATTRIBUTE_PACK:
                problems.append('ending: Fin card SGB attribute map is %s, expected English'
                                % _pack_name(attr))
            print('titlevariantspill: ending            Fin card SGB %s attributes'
                  % (_pack_name(attr) if attr else 'none'))

    print('titlevariantspill: %d title route(s)%s; %d problem(s)'
          % (len(ROUTES), ' + Moonlight ending' if ending else '', len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--no-ending', action='store_true')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('titlevariantspill: missing %s' % args.rom)
    raise SystemExit(run(args.rom, not args.no_ending, args.png_dir))


if __name__ == '__main__':
    main()
