#!/usr/bin/env python3
"""Live verifier for structured menu fragments and Fay restoration.

    python3 tools/structspill.py build/structvwf_control.gb build/shiren_en.gb \
        --png-dir build/structvwf

The control must be a matching ``--dot-font --no-structvwf`` build.  The check opens the
status screen, reaches Fay's Puzzles through the real blank-cart menu and redraws task 6,
and reaches the fresh-cart name keyboard. Optional save fixtures also exercise the
saved-summary -> Fay and both Rank/Pass branches -> Fay tile lifetimes. It requires:

* exact custom Weapon/Shield IDs and Dot planes at the approved label cells;
* statusvwf changes only its declared status labels/values; Fay number/star cells remain;
* the integrated selectable name grid reaches its real entry once, starts on A, and
  retains the native underline cursor planes/reference;
* Fay's entry restore to recover every borrowed heading/star/checkbox/separator plane,
  regardless of which mutually exclusive VWF rows used those IDs first.
"""

import argparse
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy
import menuspill
import menuvwf
import structvwf
import statusvwf


STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
DISPATCH = (4, 0x48AA)
NAME_ENTRY = (4, 0x4B02)
FEI_REDRAW = (4, 0x700E)
FEI_MOVE = (4, 0x6F90)
SHADOW = 0xC300
BGMAP = 0x9800
SHADOW_BYTES = 32 * 18
# $CA is loaded by the name screen's native graphics path, not the ordinary $37680 font
# upload, so its canonical runtime planes come from the Japanese control measurement.
NAME_CURSOR_2BPP = bytes.fromhex('0000fefefe827c7c0000000000000000')


def tile_vram(tile_id):
    return 0x9000 + 16 * tile_id if tile_id < 0x80 else 0x8800 + 16 * (tile_id - 0x80)


def expected_2bpp(tile):
    return b''.join(bytes((row, row)) for row in tile)


def status_snapshot(PyBoy, rom, png=None):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(STATE, 'rb') as src:
        pb.load_state(src)
    for frame in range(130):
        if frame == 60:
            pb.button('b', PRESS_FRAMES)
        pb.tick()
    result = {
        'shadow': bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES]),
        'map': bytes(pb.memory[0x9800:0x9800 + SHADOW_BYTES]),
        'image': pb.screen.image.copy(),
        'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                  for tile in set(sum(structvwf.BOX2_TILES.values(), ()))},
    }
    if png:
        result['image'].save(png)
    pb.stop(save=False)
    return result


def fei_snapshot(PyBoy, rom, png=None, poison_restore=False):
    """Reach Fay through the real blank-cart menu and move to task 6.

    Forcing dispatcher 17 is enough to photograph the screen, but it does not install
    the quiz input callback.  The real title route is therefore part of the proof: Down
    from task 1 must enter 4:$6F90 and redraw the mirrored row through 4:$700E.
    """
    with tempfile.TemporaryDirectory(prefix='structspill-fei-') as tmp:
        work = os.path.join(tmp, 'fei.gb')
        shutil.copyfile(rom, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        dispatched = []
        moves = []
        redraw = []
        restores = []
        frame = [0]

        def dispatch(_context):
            dispatched.append((frame[0], pb.register_file.A))

        def redrawn(_context):
            redraw.append(frame[0])

        def moved(_context):
            moves.append((frame[0], pb.register_file.D, pb.register_file.A))

        pb.hook_register(*DISPATCH, dispatch, None)
        pb.hook_register(*FEI_MOVE, moved, None)
        pb.hook_register(*FEI_REDRAW, redrawn, None)
        if poison_restore:
            def poison(_context):
                restores.append(frame[0])
                # Simulate an unknown prior VWF screen borrowing every Fay-owned ID.
                # The entry boundary, rather than a route allowlist, must repair it.
                for ordinal, tile in enumerate(structvwf.FEI_RESTORE_TILES):
                    at = tile_vram(tile)
                    for byte in range(16):
                        pb.memory[at + byte] = (0x5A + ordinal + byte) & 0xFF
            pb.hook_register(structvwf.FEI_RESTORE_BANK, structvwf.FEI_RESTORE_AT,
                             poison, None)
        nav = {700: 'start', 760: 'start', 820: 'start', 880: 'start',
               1250: 'down', 1290: 'down', 1350: 'a', 1550: 'down'}
        initial = None
        for current in range(1800):
            frame[0] = current
            if current in nav:
                pb.button(nav[current], PRESS_FRAMES)
            pb.tick()
            if current == 1500:
                initial = (bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES]),
                           bytes(pb.memory[0x9800:0x9800 + SHADOW_BYTES]),
                           pb.screen.image.copy())
        final = (bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES]),
                 bytes(pb.memory[0x9800:0x9800 + SHADOW_BYTES]),
                 pb.screen.image.copy())
        tiles = {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                 for tile in (set(sum(structvwf.QUIZ_TILES.values(), ())) |
                              {0x8A, 0xA4, 0xAF, 0xC4})}
        if png:
            initial[2].save(png)
            final[2].save(png.replace('.png', '_redraw.png'))
        pb.stop(save=False)
    return {'initial': initial, 'final': final, 'tiles': tiles,
            'dispatch': dispatched, 'moves': moves, 'redraw': redraw,
            'restores': restores}


def grid_snapshot(PyBoy, rom, png=None):
    with tempfile.TemporaryDirectory(prefix='structspill-grid-') as tmp:
        work = os.path.join(tmp, 'grid.gb')
        shutil.copyfile(rom, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        entered = []
        frame = [0]

        def at_entry(_context=None):
            entered.append(frame[0])

        pb.hook_register(*NAME_ENTRY, at_entry, None)
        starts = {700, 760, 820, 880}
        # Drive the default New Log -> Log 1 -> Easy choices until the real name-entry
        # hook fires.  A fixed third-A timestamp is not stable across component-control
        # builds: disabling structured VWF changes when the difficulty screen accepts
        # input even though the resulting keyboard is identical.
        for frame[0] in range(2800):
            if frame[0] in starts:
                pb.button('start', 4)
            elif (frame[0] >= 1320 and not entered and
                  (frame[0] - 1320) % 120 == 0):
                pb.button('a', 4)
            pb.tick()
            if entered and frame[0] >= entered[0] + 240:
                break
        image = pb.screen.image.copy()
        shadow = bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES])
        result = {
            'image': image,
            'shadow': shadow,
            'row': pb.memory[0xC6F5],
            'entry': tuple(entered),
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in (0x89, 0x8A, 0xCA)},
        }
        if png:
            image.save(png)
        pb.stop(save=False)
    return result


def fei_after_summary_snapshot(PyBoy, rom, ram, png=None, force_completed=False):
    """Open saved-log summaries, return to title, then enter Fay and select task 6.

    This is the lifetime route the clean-cart fixture cannot cover.  The old summary
    pool painted through native $A4/$AF and left the quiz without checkboxes or range
    separators even though Fay's own header tests were green.  Completed puzzles use
    $C4 rather than the empty-box $A4, so that native plane is part of the same route.
    """
    with tempfile.TemporaryDirectory(prefix='structspill-fei-saved-') as tmp:
        work = os.path.join(tmp, 'fei.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        dispatch, redraw = [], []
        frame = [0]
        def at_dispatch(_ctx):
            index = pb.register_file.A
            dispatch.append((frame[0], index))
            if force_completed and index == 17:
                pb.memory[0xD61B] |= 0x80

        pb.hook_register(*DISPATCH, at_dispatch, None)
        pb.hook_register(*FEI_REDRAW, lambda _ctx: redraw.append(frame[0]), None)
        script = {
            700: 'start', 760: 'start', 820: 'start', 880: 'start',
            1300: 'a', 1550: 'b',
            1700: 'down', 1740: 'down', 1780: 'down', 1820: 'down', 1860: 'down',
            1950: 'a', 2150: 'down',
        }
        last_c4 = None
        for current in range(2350):
            frame[0] = current
            if force_completed and current == 1940:
                # The first result bit is consumed MSB-first from $D61B by 4:$7126.
                # Force one completed quiz in the temporary fixture so tile $C4 is
                # visibly referenced, rather than merely checking its dormant planes.
                pb.memory[0xD61B] |= 0x80
            if current in script:
                pb.button(script[current], PRESS_FRAMES)
            pb.tick()
            if os.environ.get('STRUCTSPILL_TRACE'):
                now_c4 = bytes(pb.memory[tile_vram(0xC4):tile_vram(0xC4) + 16])
                if now_c4 != last_c4:
                    print('trace C4 f%d mode=%d row=%d base=$%02X shape=%s planes=%s' %
                          (current, pb.memory[0xC1B1], pb.register_file.D,
                           pb.memory[0xC0DB],
                           bytes(pb.memory[0xC69A:0xC69F]).hex(), now_c4.hex()))
                    last_c4 = now_c4
        bg = bytes(pb.memory[BGMAP:BGMAP + SHADOW_BYTES])
        result = {
            'map': bg,
            'dispatch': dispatch,
            'redraw': redraw,
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in (0xA4, 0xAF, 0xC4)},
        }
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
    return result


def fei_after_rankpass_snapshot(PyBoy, rom, ram, choice, png=None,
                                force_completed=False):
    """Take either Rank/Pass child, return, then enter Fay and select task 6."""
    if choice not in ('Rank', 'Pass'):
        raise ValueError(choice)
    with tempfile.TemporaryDirectory(prefix='structspill-fei-%s-' % choice.lower()) as tmp:
        work = os.path.join(tmp, 'fei.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        dispatch, redraw, restores = [], [], []
        c4_rows = []
        pending_rows = []
        frame = [0]
        def at_dispatch(_ctx):
            index = pb.register_file.A
            dispatch.append((frame[0], index))
            if force_completed and index == 17:
                pb.memory[0xD61B] |= 0x80

        pb.hook_register(*DISPATCH, at_dispatch, None)
        pb.hook_register(*FEI_REDRAW, lambda _ctx: redraw.append(frame[0]), None)
        pb.hook_register(structvwf.FEI_RESTORE_BANK, structvwf.FEI_RESTORE_AT,
                         lambda _ctx: restores.append(
                             (frame[0], pb.memory[0xFF40], pb.memory[0xFF44])), None)
        profile = menuspill.renderer_profile(rom)

        def menu_entry(_ctx):
            pending_rows.append((frame[0],
                                 tuple(pb.memory[a] for a in range(0xC69A, 0xC69F)),
                                 pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8),
                                 pb.register_file.D))

        def menu_epilog(_ctx):
            if not pending_rows:
                return
            row = pending_rows.pop()
            base, tiles = pb.memory[0xC0DB], pb.memory[0xC0D3]
            if base <= 0xC4 < base + tiles:
                c4_rows.append(row + (base, tiles))

        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], menu_entry, None)
        pb.hook_register(31, 0x411F, menu_epilog, None)
        script = {
            700: 'start', 760: 'start', 820: 'start', 880: 'start',
            1230: 'down', 1270: 'down', 1310: 'down', 1350: 'down', 1390: 'down',
            1460: 'a',
            2200: 'b', 2400: 'b',
            2600: 'down', 2640: 'down', 2720: 'a', 2920: 'down',
        }
        if choice == 'Rank':
            script[1800] = 'a'
        else:
            # Select Pass and exercise its real "No passwords." child (screen 19).
            script[1700] = 'down'
            script[1800] = 'a'
        for current in range(3200):
            frame[0] = current
            if current in script:
                pb.button(script[current], PRESS_FRAMES)
            pb.tick()
        bg = bytes(pb.memory[BGMAP:BGMAP + SHADOW_BYTES])
        result = {
            'map': bg,
            'dispatch': dispatch,
            'redraw': redraw,
            'restores': restores,
            'c4_rows': c4_rows,
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in structvwf.FEI_RESTORE_TILES},
        }
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
    return result


def changed_outside(before, after, allowed):
    return [index for index, (a, b) in enumerate(zip(before, after))
            if a != b and index not in allowed]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('control')
    parser.add_argument('built')
    parser.add_argument('--png-dir')
    parser.add_argument('--ram', help='saved-title fixture for the summary -> Fay leak route')
    parser.add_argument('--rank-ram',
                        help='saved-title fixture for the Rankings -> Fay leak route')
    args = parser.parse_args()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    PyBoy = _import_pyboy()
    problems = []

    def out(name):
        return os.path.join(args.png_dir, name) if args.png_dir else None

    status_ctl = status_snapshot(PyBoy, args.control, out('status_control.png'))
    status_vwf = status_snapshot(PyBoy, args.built, out('status_vwf.png'))
    status_rows = ((11 * 32 + 1, 18), (13 * 32 + 1, 18))
    status_allowed = set()
    for row, first, cells in ((2, 14, 5), (4, 17, 2), (6, 15, 4),
                              (11, 1, 18), (12, 5, 4), (12, 15, 4),
                              (13, 1, 18), (14, 5, 4), (14, 15, 4)):
        status_allowed.update(row * 32 + first + cell for cell in range(cells))
    bad = changed_outside(status_ctl['shadow'], status_vwf['shadow'], status_allowed)
    if bad:
        problems.append('status changed %d shadow cells outside box-2 labels: %s'
                        % (len(bad), bad[:12]))
    expected_status = (
        bytes(statusvwf.WEAPON_TILES) + bytes((0,)) * 4 + bytes((structvwf.DIVIDER,))
        + bytes(range(0x0B, 0x11)) + bytes((0,)) * 3,
        bytes(statusvwf.SHIELD_TILES) + bytes((0,)) * 4 + bytes((structvwf.DIVIDER,))
        + bytes(range(0x04, 0x0B)) + bytes((0,)) * 2,
    )
    for (start, cells), expected in zip(status_rows, expected_status):
        got = status_vwf['shadow'][start:start + cells]
        if got != expected:
            problems.append('status row at shadow +$%03X is %s, expected %s'
                            % (start, got.hex(' '), expected.hex(' ')))

    fei_ctl = fei_snapshot(PyBoy, args.control, out('fei_control.png'))
    fei_vwf = fei_snapshot(PyBoy, args.built, out('fei_vwf.png'),
                           poison_restore=True)
    fei_start = 1 * 32 + 1
    fei_allowed = {fei_start + cell for cell in (0, 1, 7, 8, 9, 10, 11, 12)}
    quiz_static = (bytes(structvwf.QUIZ_TILES['No']) + bytes((structvwf.SPACE,)) * 5
                   + bytes(structvwf.QUIZ_TILES['Rating'])
                   + bytes((structvwf.SPACE,)) * 2)
    for phase in ('initial', 'final'):
        for layer, field in (('shadow', 0), ('BG map', 1)):
            bad = changed_outside(fei_ctl[phase][field], fei_vwf[phase][field],
                                  fei_allowed)
            if bad:
                problems.append('Fay %s changed %d %s cells outside static words: %s'
                                % (phase, len(bad), layer, bad[:12]))
        # The redraw queue updates the real BG map, not the game's shadow copy, so this
        # is also what proves the bank-4 mirror rather than merely the entry-time box.
        got = bytearray(fei_vwf[phase][1][fei_start:fei_start + len(quiz_static)])
        # The game owns task-number cell 4; compare every static cell around it.
        got[4] = structvwf.SPACE
        if bytes(got) != quiz_static:
            problems.append('Fay %s static header is %s, expected %s around task cell 4'
                            % (phase, bytes(got).hex(' '), quiz_static.hex(' ')))
    if not any(index == 17 for _frame, index in fei_vwf['dispatch']):
        problems.append('real blank-cart route never dispatched Fay screen 17')
    if not fei_vwf['redraw']:
        problems.append('Fay task-change redraw at 4:$700E never fired')
    if len(fei_vwf['restores']) != 1:
        problems.append('poisoned clean Fay route executed %d entry restores, expected 1'
                        % len(fei_vwf['restores']))
    if fei_vwf['initial'][1][fei_start + 4] == fei_vwf['final'][1][fei_start + 4]:
        problems.append('Fay task-number cell did not change after the real Down input')

    font = structvwf.dotfont.load_approved()
    for text, ids in tuple(structvwf.BOX2_TILES.items()) + tuple(structvwf.QUIZ_TILES.items()):
        raster = structvwf._render(text, font)
        actual = status_vwf['tiles'] if text in structvwf.BOX2_TILES else fei_vwf['tiles']
        for tile_id, tile in zip(ids, raster):
            want = expected_2bpp(tile)
            if actual[tile_id] != want:
                problems.append('%s tile $%02X differs from Dot raster' % (text, tile_id))

    # Do not compare this screen with the component control.  ``--no-structvwf`` also
    # omits statusvwf, so it is not a functional control for the integrated screen-8
    # transition.  nameflowspill/unidentifiednamespill own full-raster route equality;
    # this structural test freezes the real entry and the borrowed native cursor here.
    grid_vwf = grid_snapshot(PyBoy, args.built, out('grid_vwf.png'))
    if len(grid_vwf['entry']) != 1:
        problems.append('built ROM reached name entry %d times, expected 1' %
                        len(grid_vwf['entry']))
    if grid_vwf['row'] != 1:
        problems.append('name-entry keyboard starts on row %d, expected row 1 (A)' %
                        grid_vwf['row'])

    if grid_vwf['tiles'][0xCA] != NAME_CURSOR_2BPP:
        problems.append('name-entry underline tile $CA was overwritten')
    if 0xCA not in grid_vwf['shadow']:
        problems.append('name-entry row-1 cursor does not reference underline tile $CA')

    saved_fei = None
    if args.ram:
        saved_fei_control = fei_after_summary_snapshot(
            PyBoy, args.control, args.ram, force_completed=True)
        saved_fei = fei_after_summary_snapshot(
            PyBoy, args.built, args.ram, out('fei_after_summary.png'),
            force_completed=True)
        if not any(index == 17 for _frame, index in saved_fei['dispatch']):
            problems.append('saved summary route never dispatched Fay screen 17')
        if not saved_fei['redraw']:
            problems.append('saved summary route never redrew task 6')
        for tile in (0xA4, 0xAF, 0xC4):
            if saved_fei['tiles'][tile] != saved_fei_control['tiles'][tile]:
                problems.append('saved summary route changed Fay native tile $%02X '
                                'from the matching fixed-fragment control' % tile)
        if saved_fei['map'].count(0xA4) < 40:
            problems.append('saved summary route retained only %d Fay checkbox cells' %
                            saved_fei['map'].count(0xA4))
        if saved_fei['map'].count(0xAF) < 10:
            problems.append('saved summary route retained only %d Fay range separators' %
                            saved_fei['map'].count(0xAF))
        if saved_fei['map'].count(0xC4) < 1:
            problems.append('forced completed-quiz route never referenced tile $C4')

    rankpass_fei = {}
    if args.rank_ram:
        for choice, filename in (('Rank', 'fei_after_rankings.png'),
                                 ('Pass', 'fei_after_pass.png')):
            route = fei_after_rankpass_snapshot(
                PyBoy, args.built, args.rank_ram, choice, out(filename),
                force_completed=True)
            rankpass_fei[choice] = route
            if not any(index == 17 for _frame, index in route['dispatch']):
                problems.append('%s route never returned to Fay screen 17; dispatches %s'
                                % (choice, route['dispatch']))
            if choice == 'Pass' and not any(index == 19 for _frame, index in
                                            route['dispatch']):
                problems.append('Pass route never dispatched the No passwords screen 19')
            if not route['redraw']:
                problems.append('%s route never redrew task 6' % choice)
            if len(route['restores']) != 1:
                problems.append('%s route entered Fay with %d restore call(s), expected 1'
                                % (choice, len(route['restores'])))
            for tile in structvwf.FEI_RESTORE_TILES:
                if route['tiles'][tile] != fei_vwf['tiles'][tile]:
                    problems.append('%s route left Fay tile $%02X overwritten: '
                                    '%s != clean %s; prompt map %s'
                                    % (choice, tile, route['tiles'][tile].hex(),
                                       fei_vwf['tiles'][tile].hex(),
                                       route['map'][16 * 32:17 * 32].hex()))
            if route['map'].count(0xA4) < 40:
                problems.append('%s route retained only %d Fay checkbox cells'
                                % (choice, route['map'].count(0xA4)))
            if route['map'].count(0xAF) < 10:
                problems.append('%s route retained only %d Fay range separators'
                                % (choice, route['map'].count(0xAF)))
            if route['map'].count(0xC4) < 1:
                problems.append('%s route never referenced the forced completed checkbox'
                                % choice)
            # Rankings has dedicated safe tiles and should not borrow `$C4`; Pass is
            # deliberately hostile because "No passwords." uses the common one-row
            # pool. The unconditional Fay restore makes that sequential reuse safe.
            if choice == 'Rank' and route['c4_rows']:
                problems.append('Rankings route composed through native tile $C4: %s'
                                % (route['c4_rows'],))

    print('structspill: status labels/maps exact; changes confined to declared VWF fields')
    print('  Fay: real screen-17 dispatch, movement callbacks %s, task redraw %d; '
          'number/star cells preserved'
          % (fei_vwf['moves'], len(fei_vwf['redraw'])))
    print('  custom Dot tiles: %d box-2 + %d Fay plane-exact'
          % (sum(map(len, structvwf.BOX2_TILES.values())),
             sum(map(len, structvwf.QUIZ_TILES.values()))))
    print('  Fay entry: all %d borrowed tile planes survive deliberate pre-entry poison'
          % len(structvwf.FEI_RESTORE_TILES))
    print('  name keyboard: starts on A; pixel/shadow and native $CA cursor exact')
    if saved_fei:
        print('  saved summary -> Fay: %d empty + %d completed checkboxes, %d range '
              'separators, native planes exact'
              % (saved_fei['map'].count(0xA4), saved_fei['map'].count(0xC4),
                 saved_fei['map'].count(0xAF)))
    for choice, route in rankpass_fei.items():
        print('  %s -> Fay: %d empty + %d completed checkboxes, %d range separators; '
              '%d borrowed tile planes restored at entry'
              % (choice, route['map'].count(0xA4), route['map'].count(0xC4),
                 route['map'].count(0xAF), len(structvwf.FEI_RESTORE_TILES)))
    print('  problems: %d' % len(problems))
    for problem in problems:
        print('    ' + problem)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
