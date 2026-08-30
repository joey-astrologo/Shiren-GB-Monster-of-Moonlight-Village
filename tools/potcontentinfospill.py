#!/usr/bin/env python3
"""Trace and guard contained-item Action -> Info -> Pot-content returns.

The bundled Log-2 Storage Pot save starts with an empty Pot on the floor.  This route
takes it, puts the carried Big Onigiri inside, opens the real populated Pot viewer,
selects the contained item, opens its Action picker, chooses the final ``Info`` row, and
returns with B.  Inputs after Items opens are scheduled from real dispatcher/row-
completion events so a transition-speed change cannot silently miss the screen under
test.  The SRAM is copied into a temporary directory and is never modified in place.
"""

import argparse
import os
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import statusvwf                                                   # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    # Screen 15 now publishes the full start-menu composite before accepting input.
    # The old 300-frame press landed while that transaction still owned the screen and
    # made this regression silently stop at the title menu.
    700: 'a', 1000: 'down', 1200: 'a', 1500: 'a',   # Adventure -> Log 2
    2200: 'b', 2280: 'down', 2360: 'a', 2460: 'a',   # Menu -> Floor -> Take
    2700: 'a', 2800: 'a', 2900: 'a',                 # pickup/description messages
    3000: 'b', 3120: 'a',                            # Menu -> Items
}
ACTION_PREFIX = (13, 1)
ACTION_SUFFIX = (5, 0x02)
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
FRAMES = 6400


def run(rom, ram=RAM, trace=False, png_dir=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('potcontentinfospill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    problems = []

    with tempfile.TemporaryDirectory(prefix='potcontentinfospill-') as tmp:
        work = os.path.join(tmp, 'pot-content-info.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(BOOT)
        dispatches = []
        row_completions = []
        lcd_writes = []
        lcd_off_frames = []
        viewer_press = [None]
        action_press = [None]
        info_press = [None]
        return_press = [None]
        info_screen = [None]
        return_viewer = [None]
        return_idle = [None]
        item_completions = []
        outer_action_completions = []
        pot_see_press = [None]
        ownership_attempts = []
        pop_attempts = []
        return_attempts = []
        potentry_transitions = []
        applied_inputs = []
        early_chrome = []
        action_top = [None]
        info_top = [None]
        viewer_exit_press = [None]
        items_exit_press = [None]
        status_exit_press = [None]
        field_ready = [None]
        reopen_press = [None]
        reopen_accept = [None]
        exit_phase = [0]

        def top_action_state():
            refs = bytes(pb.memory[0x984E:0x9853])
            planes = tuple(
                (tile, bytes(pb.memory[menuspill.tile_data_addr(tile):
                                       menuspill.tile_data_addr(tile) + 16]))
                for tile in refs if tile)
            return refs, planes

        def stack():
            depth = pb.memory[0xC534]
            return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            dispatches.append((frame[0], screen, stack(), pb.memory[0xC1B3],
                               pb.memory[0xC1B6], pb.memory[0xC6AC],
                               pb.memory[0xC6BB]))
            if screen in (12, 13) and viewer_press[0] is None:
                viewer_press[0] = frame[0] + 90
                schedule[viewer_press[0]] = 'a'
            elif screen in (4, 5) and info_screen[0] is None:
                info_screen[0] = screen
                return_press[0] = frame[0] + 300
                schedule[return_press[0]] = 'b'
            elif (screen in (12, 13) and info_screen[0] is not None and
                  return_viewer[0] is None):
                return_viewer[0] = (frame[0], screen)
                viewer_exit_press[0] = frame[0] + 180
                schedule[viewer_exit_press[0]] = 'b'
                exit_phase[0] = 1
            elif screen == 1 and exit_phase[0] == 1:
                items_exit_press[0] = frame[0] + 140
                schedule[items_exit_press[0]] = 'b'
                exit_phase[0] = 2
            elif screen == 0 and exit_phase[0] == 2:
                status_exit_press[0] = frame[0] + 140
                schedule[status_exit_press[0]] = 'b'
                exit_phase[0] = 3
            elif (screen == 0 and exit_phase[0] == 4 and
                  reopen_press[0] is not None and frame[0] >= reopen_press[0]):
                reopen_accept[0] = frame[0]
                exit_phase[0] = 5

        def item_row(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            row_completions.append((frame[0], pb.register_file.D, shape,
                                    pb.memory[0xC6A3], stack()))
            if shape == ITEM_SHAPE and pb.register_file.D == 4 and frame[0] >= 3000:
                if item_completions and item_completions[-1] == frame[0]:
                    return
                item_completions.append(frame[0])
                if len(item_completions) == 1:
                    # Storage Pot is row four in the newly acquired inventory.
                    at = frame[0] + 60
                    for _index in range(3):
                        schedule[at] = 'down'
                        at += 60
                    schedule[at] = 'a'
                elif len(item_completions) == 2:
                    # Put selector begins on Big Onigiri.
                    schedule[frame[0] + 80] = 'a'
                elif len(item_completions) == 3:
                    # Put's native return redraws the same Pot Action picker. Its real
                    # row-completion event below selects See from that restored picker.
                    pass
                return
            if not (shape[:2] == ACTION_PREFIX and shape[3:] == ACTION_SUFFIX):
                return
            count = shape[2]
            if pb.register_file.D != count - 1:
                return
            if viewer_press[0] is None:
                if outer_action_completions and outer_action_completions[-1] == frame[0]:
                    return
                outer_action_completions.append(frame[0])
            if viewer_press[0] is None and len(outer_action_completions) == 1:
                # The first Storage Pot Action selects Put.
                schedule[frame[0] + 60] = 'down'
                schedule[frame[0] + 120] = 'a'
                return
            if viewer_press[0] is None and len(outer_action_completions) == 2:
                # The reopened Action picker starts on See.
                pot_see_press[0] = frame[0] + 80
                schedule[pot_see_press[0]] = 'a'
                return
            if viewer_press[0] is None or action_press[0] is not None:
                return
            # This is the contained item's Action picker: choose its final Info row.
            # Capture the private top row shortly before the press, after its queued
            # tile upload has settled; row completion itself is one frame too early.
            at = frame[0] + 60
            action_press[0] = at
            for _index in range(count - 1):
                schedule[at] = 'down'
                at += 60
            info_press[0] = at
            schedule[info_press[0]] = 'a'

        def lifecycle_attempt(target):
            def callback(_ctx=None):
                target.append((frame[0], pb.register_file.A, pb.register_file.D,
                               pb.register_file.HL, pb.memory[0xC6A3], stack(),
                               pb.memory[0xC6A6], pb.memory[0xC6DE],
                               pb.memory[0xC6AA], pb.memory[0xC6AC],
                               pb.memory[0xC6BB], pb.memory[0xC6BC],
                               pb.memory[0xC6BD], pb.memory[0xC1B1],
                               pb.memory[0xC1B3], pb.memory[0xC1B4],
                               pb.memory[0xC1B5], pb.memory[0xC1B6],
                               pb.memory[0xC1B7],
                               tuple(pb.memory[address]
                                     for address in range(0xC69A, 0xC69F))))
            return callback

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        labels = menuvwf.info_lifecycle_labels()
        def potentry_transition(name):
            def callback(_ctx=None):
                potentry_transitions.append(
                    (frame[0], name, pb.memory[0xC6A3], stack(),
                     pb.memory[0xC1B3], pb.memory[0xC1B1],
                     pb.memory[0xC1B4], pb.memory[0xC1B5],
                     pb.memory[0xC1B6], pb.memory[0xC1B8],
                     pb.memory[0xC6A6], pb.memory[0xC6DE],
                     pb.memory[0xC6AA], pb.memory[0xC6BB],
                     pb.memory[0xC0D5], pb.memory[0xC0D9],
                     pb.memory[0xC0DA], pb.memory[0xFF40],
                     tuple(pb.memory[address]
                           for address in range(0xC69A, 0xC69F))))
            return callback

        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infotry'],
                         lifecycle_attempt(ownership_attempts), None)
        pb.hook_register(menuvwf.ACTION_POP_BANK, menuvwf.ACTION_POP_AT,
                         lifecycle_attempt(pop_attempts), None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturn'],
                         lifecycle_attempt(return_attempts), None)
        for name in ('potentrybegin', 'potentryactive', 'potentrybad',
                     'potentrypublish', 'potentrypublishdone'):
            pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels[name],
                             potentry_transition(name), None)
        pb.hook_register(
            menuvwf.ACTION_BLANK_BANK, labels['potreturnchromedone'],
            lambda _ctx=None: early_chrome.append(
                (frame[0], pb.memory[0xC6BB],
                 bytes(pb.memory[0x9800:0x9A00]))), None)
        # Sampling LCDC after every emulated frame is deliberately sufficient here.
        # Registering a debugger hook at every static LCDC writer makes PyBoy yield at
        # each hit, stretching the title transition by hundreds of host frames and
        # causing this route's scheduled input to be ignored before it reaches the menu.

        for current in range(FRAMES):
            frame[0] = current
            button = schedule.get(current)
            if button:
                applied_inputs.append((current, button, pb.memory[0xC6A3],
                                       pb.memory[0xFF40]))
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if (info_press[0] is not None and current == info_press[0] - 30):
                action_top[0] = top_action_state()
            if (return_press[0] is not None and current == return_press[0] - 30):
                info_top[0] = top_action_state()
            if (return_viewer[0] is not None and return_idle[0] is None and
                    pb.memory[0xC6A3] in (12, 13) and
                    pb.memory[0xC1B3] == 0):
                return_idle[0] = current
            if (exit_phase[0] == 3 and status_exit_press[0] is not None and
                    current >= status_exit_press[0] + 60 and
                    pb.memory[0xC6A3] == 0xFF and pb.memory[0xFF40] & 0x80):
                field_ready[0] = current
                reopen_press[0] = current + 80
                schedule[reopen_press[0]] = 'b'
                exit_phase[0] = 4
            if (info_press[0] is not None and current >= info_press[0] and
                    (status_exit_press[0] is None or
                     current < status_exit_press[0]) and
                    not pb.memory[0xFF40] & 0x80):
                lcd_off_frames.append(current)
            if png_dir and info_press[0] is not None and \
                    info_press[0] - 5 <= current <= info_press[0] + 80:
                os.makedirs(png_dir, exist_ok=True)
                pb.screen.image.save(os.path.join(
                    png_dir, 'entry_f%04d.png' % current))
            if png_dir and return_press[0] is not None and \
                    return_press[0] - 5 <= current <= return_press[0] + 100:
                pb.screen.image.save(os.path.join(
                    png_dir, 'return_f%04d.png' % current))

        final_lcdc = pb.memory[0xFF40]
        final_screen = pb.memory[0xC6A3]
        final_state = pb.memory[0xC1B3]
        final_stack = stack()
        pb.stop(save=False)

    off_writes = [event for event in lcd_writes
                  if action_press[0] is not None and event[0] >= action_press[0] and
                  not event[3] & 0x80]
    if viewer_press[0] is None:
        problems.append('never entered the real Pot-content viewer')
    if action_press[0] is None:
        problems.append('never completed the contained-item Action picker')
    if info_screen[0] not in (4, 5):
        problems.append('never entered contained-item Info screen 4/5')
    if return_viewer[0] is None:
        problems.append('Info B did not return to the Pot-content viewer')
    if return_idle[0] is None:
        problems.append('restored Pot page never retired contained-Info state $17')
    if action_top[0] is None or info_top[0] is None:
        problems.append('did not capture the exposed contained-Action top row')
    elif action_top[0] != info_top[0]:
        problems.append('Info repainted the exposed contained-Action top verb')
    elif not any(menuvwf.ACTION_POOL_BASE <= tile < menuvwf.ACTION_POOL_BASE + 4
                 for tile in action_top[0][0]):
        problems.append('contained-Action top verb did not use its private slice')
    info_return_chrome = [event for event in early_chrome
                          if return_press[0] is not None and
                          event[0] >= return_press[0] and
                          (viewer_exit_press[0] is None or
                           event[0] < viewer_exit_press[0])]
    if len(info_return_chrome) != 1:
        problems.append('contained Info return committed empty Pot chrome %d times' %
                        len(info_return_chrome))
    else:
        _at, body_rows, bg = info_return_chrome[0]
        expected = bytearray(0x200)
        expected[0:5] = bytes((0xB8, 0xBC, 0xBC, 0xBC, 0xB9))
        expected[0x20] = 0xBE
        expected[0x24] = 0xBF
        expected[0x40:0x45] = bytes((0xBA, 0xBD, 0xBD, 0xBD, 0xBB))
        expected[0x60:0x74] = bytes((0xB8,)) + bytes((0xBC,)) * 18 + \
            bytes((0xB9,))
        for row in range(body_rows):
            at = 0x80 + row * 0x20
            expected[at] = 0xBE
            expected[at + 19] = 0xBF
        at = 0x80 + body_rows * 0x20
        expected[at:at + 20] = bytes((0xBA,)) + bytes((0xBD,)) * 18 + \
            bytes((0xBB,))
        visible_differences = [
            (row * 0x20 + col, bg[row * 0x20 + col],
             expected[row * 0x20 + col])
            for row in range(16) for col in range(20)
            if bg[row * 0x20 + col] != expected[row * 0x20 + col]]
        if visible_differences:
            problems.append('contained Info return exposed non-empty/stale cells in '
                            'its Pot chrome commit')
            if trace:
                print('  early Pot chrome differences %r' %
                      (visible_differences[:40],))
    if lcd_off_frames:
        problems.append('nested Info transaction disabled LCD on frame(s) %s' %
                        lcd_off_frames[:24])
    if not final_lcdc & 0x80:
        problems.append('route ended with LCDC=$%02X' % final_lcdc)
    if final_state != 0:
        problems.append('route ended with stale lifecycle state $%02X' % final_state)
    if (field_ready[0] is None or reopen_accept[0] is None or exit_phase[0] != 5):
        problems.append('Pot/Items/Status exit did not regain field input and reopen '
                        'Status')

    print('potcontentinfospill: dispatches %s; Action/info presses %s/%s; '
          'return %s/idle f%s; off writes %s; %d LCD-off frame(s); '
          'final screen/stack/state %d/%s/$%02X; '
          'field/reopen f%s/f%s; %d problem(s)' %
          (' '.join('f%d:%d:%s' % (at, screen, stack_value)
                    for at, screen, stack_value, _state, _admit, _sel, _rows
                    in dispatches),
           action_press[0], info_press[0], return_viewer[0], return_idle[0],
           ' '.join('f%d:%02d:$%04X:s%d:%s' %
                    (at, bank, address, screen, stack_value)
                    for at, bank, address, _value, screen, stack_value,
                    _state, _admit in off_writes),
           len(lcd_off_frames), final_screen, final_stack, final_state,
           field_ready[0], reopen_accept[0], len(problems)))
    if trace:
        print('  early Pot chrome commits %r' %
              ([(at, rows, hash(bg)) for at, rows, bg in early_chrome],))
        print('  item completions %r; outer actions %r; See %r' %
              (item_completions, outer_action_completions, pot_see_press[0]))
        print('  relevant row completions %r' %
              ([event for event in row_completions if event[0] >= 3000],))
        print('  relevant LCD writes %r' %
              ([event for event in lcd_writes
                if action_press[0] is not None and event[0] >= action_press[0] and
                (event[1:3] != (0, 0x0737) or not event[3] & 0x80)],))
        print('  ownership attempts %r' % (ownership_attempts,))
        print('  pop attempts %r' % (pop_attempts,))
        print('  return attempts %r' % (return_attempts,))
        print('  Pot entry transitions %r' %
              ([event for event in potentry_transitions
                if event[2] in (12, 13) or event[4] in (0x0C, 0x17)],))
        print('  dispatches %r' % (dispatches,))
        print('  applied inputs %r' % (applied_inputs,))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('potcontentinfospill: missing %s' % path)
    return run(args.rom, args.ram, args.trace, args.png_dir)


if __name__ == '__main__':
    raise SystemExit(main())
