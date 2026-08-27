#!/usr/bin/env python3
"""Replay the screen-20 Floor action/Info transitions from cartridge RAM.

``saves/shiren_en_item_menu_wood_arrow.srm`` has Log 1 standing on a Wood Arrow.
The route opens Menu -> Floor, selects Info, advances its two pages, and returns to
the action picker. Every transition must keep the LCD enabled. Entry must retain the
complete Action box until complete Info chrome and its first row replace it together;
page changes may replace only whole rows and may never expose an empty Info body.

``--fusion`` replaces that one ground record with an identified Fusion Pot[2], drives
its real six-row Action box and all five Info pages, and additionally checks the settled
footer rasters plus the two BG rows which the taller outgoing Action box had occupied.

``--seal`` instead installs a Manji Kabura+1 with one seal on the ground, proving the
same screen-20 parent owns a real screen-5 seal child and its return.

``--fusion-kit`` reproduces the two canonical inventory records appended by
``mesen_spawn_fusion_kit.lua`` at the same bank-6 builder boundary. It can be combined
with ``--fusion`` to cover a standing Fusion Pot while the Lua kit is carried.

``--fusion-kit-history`` additionally opens the spawned carried Pot's Action menu and
returns to gameplay before entering Status -> Floor -> Info on the standing Wood Arrow.
That history guards the stale private-Action admission state which originally restored
the full-screen blank despite the visible Floor picker being complete.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
import dotfont                                                    # noqa: E402
import gbasm                                                     # noqa: E402
import statusvwf                                                  # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b', 2700: 'down', 2780: 'a',
    2860: 'down', 2900: 'down', 2940: 'down',
    3000: 'a', 3400: 'a', 3800: 'a',
}
TRANSITIONS = (
    ('action-to-info-1', 3000),
    ('info-1-to-info-2', 3400),
    ('info-2-to-action', 3800),
)
WOOD_ARROW = bytes(menuspill.encode('Wood Arrow'))
FUSION_POT = bytes(menuspill.encode('Fusion Pot[2]'))
INVENTORY = 0xA3B0
OBJECTS = 0xA406
FUSION_KIT_RECORDS = (
    (0x87, 0x02, 0x00, 0x04, 0x00, 0x00, 0xFF, 0xFF),
    (0x06, 0x01, 0x00, 0xC4, 0x04, 0x00, 0xFF, 0xFF),
)
INFO_TEXT_ROWS = (4, 6, 8, 10, 12)
# The two-tile down arrow replaces this portion of box 7's bottom border. On the final
# page those cells return to border tiles, so they are content rather than invariant
# chrome during a page transition.
INFO_PAGER_CELLS = frozenset(((13, 9), (13, 10)))


def staged_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def tile_planes(snapshot, tile):
    start = menuspill.tile_data_addr(tile) - 0x8800
    return snapshot['tiles'][start:start + 16]


def target_chrome_complete(snapshot, target):
    """Every structural cell in the settled target is already visible."""
    for row in range(16):
        for col in range(20):
            if (row, col) in INFO_PAGER_CELLS:
                continue
            index = row * 32 + col
            wanted = target['bg'][index]
            if 0xB8 <= wanted <= 0xBF and snapshot['bg'][index] != wanted:
                return False
    return True


def chrome_mismatches(snapshot, target):
    return tuple((row, col, snapshot['bg'][row * 32 + col], wanted)
                 for row in range(16) for col in range(20)
                 if (row, col) not in INFO_PAGER_CELLS
                 for wanted in (target['bg'][row * 32 + col],)
                 if 0xB8 <= wanted <= 0xBF
                 and snapshot['bg'][row * 32 + col] != wanted)


def target_body_text_visible(snapshot, target):
    """A settled target body glyph is visible, comparing raster planes not IDs."""
    for row in range(3, 14):
        for col in range(1, 19):
            index = row * 32 + col
            wanted = target['bg'][index]
            if not wanted or 0xB8 <= wanted <= 0xBF:
                continue
            wanted_planes = tile_planes(target, wanted)
            if not any(wanted_planes):
                continue
            current = snapshot['bg'][index]
            if tile_planes(snapshot, current) == wanted_planes:
                return True
    return False


def info_row_raster(snapshot, row):
    """Return the 18-cell body raster for one of box 7's five text rows."""
    start = row * 32 + 1
    return b''.join(tile_planes(snapshot, snapshot['bg'][start + col])
                    for col in range(18))


def info_ink_rows(snapshot):
    """Count Info text rows which currently contain at least one foreground pixel."""
    return sum(any(info_row_raster(snapshot, row)) for row in INFO_TEXT_ROWS)


def incomplete_info_rows(snapshot, outgoing, target):
    """Find rows which are neither a whole old row, whole new row, nor wholly blank."""
    bad = []
    blank = bytes(18 * 16)
    for number, row in enumerate(INFO_TEXT_ROWS):
        current = info_row_raster(snapshot, row)
        allowed = (blank, info_row_raster(outgoing, row),
                   info_row_raster(target, row))
        if current not in allowed:
            bad.append(number)
    return tuple(bad)


def run(rom_path, ram_path, png_dir=None, frames=3900, trace=False, fusion=False,
        fusion_kit=False, fusion_kit_history=False, seal=False):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('floorinfospill: requires the Dot proportional renderer')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)

    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='floorinfospill-') as tmp:
        run_rom = os.path.join(tmp, 'floorinfo.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        boot = dict(BOOT)
        transitions = TRANSITIONS
        if fusion_kit_history:
            fusion_kit = True
            for at in tuple(key for key in boot if key >= 2620):
                del boot[at]
            boot.update({
                2620: 'b', 2700: 'a',
                2820: 'right', 2920: 'right', 3020: 'right',
                3120: 'down', 3180: 'down', 3240: 'down', 3320: 'a',
                3380: 'down', 3440: 'down', 3500: 'down', 3560: 'a',
                3700: 'b', 3780: 'down', 3860: 'a',
                3940: 'down', 4000: 'down', 4060: 'down', 4140: 'a',
                4540: 'a', 4940: 'b',
            })
            transitions = (
                ('action-to-info-1', 4140),
                ('info-1-to-info-2', 4540),
                ('info-2-to-action', 4940),
            )
            frames = max(frames, 5050)
        if fusion:
            for at in tuple(key for key in boot if key >= 2860):
                del boot[at]
            boot.update({2860: 'down', 2900: 'down', 2940: 'down',
                         2980: 'down', 3020: 'down', 3080: 'a',
                         3480: 'a', 3880: 'a', 4280: 'a', 4680: 'a',
                         5080: 'b'})
            transitions = (
                ('action-to-info-1', 3080),
                ('info-1-to-info-2', 3480),
                ('info-2-to-info-3', 3880),
                ('info-3-to-info-4', 4280),
                ('info-4-to-info-5', 4680),
                ('info-5-to-action', 5080),
            )
            frames = max(frames, 5200)
        if seal:
            for at in tuple(key for key in boot if key >= 3400):
                del boot[at]
            boot[3400] = 'b'
            transitions = (
                ('action-to-info-1', 3000),
                ('info-1-to-action', 3400),
            )
        dispatches = []
        calls = []
        samples = {name: [] for name, _at in transitions}
        lcd_off = {name: [] for name, _at in transitions}
        white = {name: [] for name, _at in transitions}
        settled_states = {}
        injected = [not (fusion or fusion_kit or seal)]
        injection_state = []
        info_attempts = []
        lifecycle = []
        legacy_blankers = []
        status_blankers = []

        def inject_fusion(_ctx=None):
            if injected[0]:
                return
            carried = []
            for slot in range(20):
                index = pb.memory[INVENTORY + slot]
                if index == 0xFF:
                    break
                carried.append(index)
            ground = [index for index in range(128)
                      if index not in set(carried) and
                      pb.memory[OBJECTS + 8 * index] != 0xFF]
            if len(ground) != 1:
                return
            ground_before = bytes(pb.memory[OBJECTS + 8 * ground[0]:
                                            OBJECTS + 8 * ground[0] + 8])
            if fusion:
                record = (0x87, 2, 0, 0x80, 0, 0, 0xFF, 0xFF)
                for offset, value in enumerate(record):
                    pb.memory[OBJECTS + 8 * ground[0] + offset] = value
            elif seal:
                # Same identified/sealed Manji as the Lua kit, with the carried-object
                # bit removed while retaining its equipment/seal state.
                record = (0x06, 1, 0, 0xC0, 4, 0, 0xFF, 0xFF)
                for offset, value in enumerate(record):
                    pb.memory[OBJECTS + 8 * ground[0] + offset] = value
            added = []
            if fusion_kit:
                if len(carried) + len(FUSION_KIT_RECORDS) > 20:
                    return
                free = [index for index in range(128)
                        if index not in set(carried) and index not in ground and
                        pb.memory[OBJECTS + 8 * index] == 0xFF]
                if len(free) < len(FUSION_KIT_RECORDS):
                    return
                for slot, (index, record) in enumerate(
                        zip(free, FUSION_KIT_RECORDS), len(carried)):
                    for offset, value in enumerate(record):
                        pb.memory[OBJECTS + 8 * index + offset] = value
                    pb.memory[INVENTORY + slot] = index
                    added.append(index)
            injection_state.append((len(carried), tuple(added), ground[0],
                                    ground_before))
            injected[0] = True

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            calls.append((frame[0], pb.register_file.D, pb.register_file.HL,
                          pb.memory[0xC1B1], shape, source,
                          staged_row(pb, source)))

        pb.hook_register(6, 0x4B29, inject_fusion, None)
        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        _info_code, info_labels = gbasm.assemble(
            menuvwf.INFO_LIFECYCLE_SRC, menuvwf.INFO_LIFECYCLE_AT)

        def info_attempt(_ctx=None):
            depth = pb.memory[0xC534]
            info_attempts.append((
                frame[0], pb.memory[0xC1B3], pb.memory[0xC1B6],
                pb.memory[0xC6A3], pb.memory[0xC6DE], pb.memory[0xC6AC],
                pb.memory[0xC6BB], pb.memory[0xC69C],
                tuple(pb.memory[0xC535 + index] for index in range(depth + 1))))

        pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['infotry'],
                         info_attempt, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels['fidisable'],
                         lambda _ctx=None: legacy_blankers.append(frame[0]), None)
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         lambda _ctx=None: status_blankers.append(frame[0]), None)
        def life(label):
            def capture(_ctx=None):
                depth = pb.memory[0xC534]
                lifecycle.append((
                    frame[0], label, pb.register_file.A, pb.memory[0xC1B3],
                    pb.memory[0xC1B6], pb.memory[0xC6A3], pb.memory[0xC1B1],
                    pb.memory[0xC0D9], pb.memory[0xC0DA],
                    tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)),
                    pb.register_file.D, pb.register_file.HL,
                    tuple(pb.memory[0xC535 + index]
                          for index in range(depth + 1)),
                    pb.memory[0xC0DB], pb.memory[0xC0D3], pb.memory[0xC0DD],
                    tuple(bytes(pb.memory[0x9881 + row * 0x40:
                                          0x9881 + row * 0x40 + 18])
                          for row in range(5))))
            return capture
        for label in ('infoboxdone', 'infopreupload', 'infopreuploadblankrows',
                      'infotilefastdone', 'infoentrychromedone',
                      'infopublishrowdone', 'infopop', 'inforeturn', 'info20chrome',
                      'info20chromedone',
                      'inforeturn20publish'):
            pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels[label],
                             life(label), None)
        for current in range(frames):
            frame[0] = current
            button = boot.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            for name, at in transitions:
                if at <= current <= at + 70:
                    snapshot = pb.screen.image.copy()
                    state = {
                        'bg': bytes(pb.memory[0x9800:0x9C00]),
                        'tiles': bytes(pb.memory[0x8800:0x9800]),
                        'transaction': pb.memory[0xC1B3],
                    }
                    samples[name].append((current, snapshot, state))
                    if not pb.memory[0xFF40] & 0x80:
                        lcd_off[name].append(current)
                    if len(set(snapshot.convert('RGB').getdata())) == 1:
                        white[name].append(current)
                    if png_dir:
                        snapshot.save(os.path.join(
                            png_dir, '%s_f%04d.png' % (name, current)))
                if current == at + 70:
                    settled_states[name] = {
                        'bg': bytes(pb.memory[0x9800:0x9C00]),
                        'tiles': bytes(pb.memory[0x8800:0x9800]),
                    }

        final_state = pb.memory[0xC1B3]
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=False)

    indices = [index for _at, index in dispatches]
    expected = ((20, 5, 0, 20) if seal else
                (20,) + (4,) * 5 + (0, 20) if fusion else
                (1, 1, 1, 1, 2, 0, 20, 4, 4, 0, 20)
                if fusion_kit_history else (20, 4, 4, 0, 20))
    cursor = 0
    for index in indices:
        if cursor < len(expected) and index == expected[cursor]:
            cursor += 1
    if cursor != len(expected):
        problems.append('dispatch sequence %s does not contain %s'
                        % (indices, list(expected)))
    if final_state != 0:
        problems.append('regional lifecycle ended in state $%02X, expected zero' %
                        final_state)
    if not final_lcdc & 0x80:
        problems.append('regional lifecycle left the LCD disabled')
    if legacy_blankers:
        problems.append('regional lifecycle reached the explicit Info LCD blanker at %s' %
                        ' '.join('f%d' % at for at in legacy_blankers))
    if status_blankers:
        problems.append('regional lifecycle reached the explicit Status LCD blanker at %s' %
                        ' '.join('f%d' % at for at in status_blankers))

    expected_name = FUSION_POT if fusion else WOOD_ARROW
    headers = [row for _at, _d, _key, _mode, shape, _source, row in calls
               if shape[:4] == (0, 0, 1, 18) and
               (seal or row == bytes([0]) + expected_name)]
    if not headers:
        problems.append('real route never composed the one-prefix %s header' %
                        ('Manji Kabura+1' if seal else
                         'Fusion Pot[2]' if fusion else 'Wood Arrow'))
    if not injected[0]:
        problems.append('could not install requested ground/inventory mutation')
    if fusion_kit_history:
        first_attempt = next((event for event in info_attempts
                              if event[0] >= transitions[0][1]), None)
        if first_attempt is None or first_attempt[2] != 1:
            problems.append('Lua-history route did not reach Floor Info with stale '
                            'Action admission one')
        first_box = next((event for event in lifecycle
                          if event[0] >= transitions[0][1] and
                          event[1] == 'infoboxdone'), None)
        if first_box is None or first_box[4] != 0:
            problems.append('Lua-history route did not retire stale Action admission '
                            'before Info publication')

    if fusion:
        font = dotfont.load_approved()
        info_names = [name for name, _at in transitions
                      if not name.endswith('-to-action')]
        for page, name in enumerate(info_names, 1):
            state = settled_states.get(name)
            if state is None:
                problems.append('%s has no settled tile-map sample' % name)
                continue
            start = 13 * 32 + 16
            footer = state['bg'][start:start + 3]
            expected_footer = bytes((page + 1, 0xB0, 6))
            if footer != expected_footer:
                problems.append('%s footer is %s, expected %s' %
                                (name, footer.hex(' '),
                                 expected_footer.hex(' ')))
            for digit, code, label in ((page, page + 1, 'current'),
                                       (5, 6, 'total')):
                tile_at = menuspill.tile_data_addr(code) - 0x8800
                pixels = state['tiles'][tile_at:tile_at + 16]
                expected_pixels = bytes(value
                                        for row in font.glyphs[str(digit)]
                                        for value in (row, row))
                if pixels != expected_pixels:
                    problems.append('%s %s digit pixels differ from approved %d' %
                                    (name, label, digit))
            for row in (14, 15):
                got = state['bg'][row * 32:row * 32 + 20]
                if got != bytes(20):
                    problems.append('%s retained Action cells on BG row %d: %s' %
                                    (name, row, got.hex(' ')))

    continuity = {}
    for name, _at in transitions:
        transition = samples[name]
        if not transition:
            problems.append('%s has no frame samples' % name)
            continue
        target = settled_states.get(name)
        if target is None:
            problems.append('%s has no settled target state' % name)
            continue
        entering = name.startswith('action-to-info-')
        leaving = name.endswith('-to-action')
        page_change = not entering and not leaving
        finish_label = ('info20chromedone' if leaving else
                        'infoentrychromedone' if entering else 'infoboxdone')
        owned_at = next((event[0] for event in lifecycle
                         if event[1] == finish_label and
                         transition[0][0] <= event[0] <= transition[-1][0]), None)
        if owned_at is None:
            problems.append('%s never reaches its regional ownership helper' % name)
            continue
        observed = [sample for sample in transition if sample[0] >= owned_at]
        bad = [at for at, _image, state in observed
               if target_body_text_visible(state, target)
               and not target_chrome_complete(state, target)]
        if bad:
            problems.append('%s exposes target text before complete chrome on %s'
                            % (name, ' '.join('f%d' % at for at in bad[:16])))
        if lcd_off[name]:
            problems.append('%s disables the LCD on frame(s) %s'
                            % (name, lcd_off[name][:16]))
        if white[name]:
            problems.append('%s renders a uniform full-screen frame on frame(s) %s'
                            % (name, white[name][:16]))

        outgoing = transition[0][2]
        if entering:
            # The small Action picker may lose its labels while their shared tile pixels
            # are recycled, but its complete perimeter must remain until complete Info
            # chrome and a real first row replace it in the same publication.
            broken = [at for at, _image, state in transition
                      if not target_chrome_complete(state, outgoing)
                      and not target_chrome_complete(state, target)]
            if broken:
                problems.append('%s exposes neither complete Action nor Info chrome on %s'
                                % (name, ' '.join('f%d' % at
                                                  for at in broken[:16])))
            empty = [at for at, _image, state in transition
                     if target_chrome_complete(state, target)
                     and info_ink_rows(state) == 0]
            if empty:
                problems.append('%s exposes complete Info chrome with an empty body on %s'
                                % (name, ' '.join('f%d' % at
                                                  for at in empty[:16])))

        if page_change:
            # The allocator can reuse tiles from any old row. The pre-upload scan may
            # therefore retire more than the destination row, but it must do so only as
            # whole rows, and at least one complete old/new row must remain throughout.
            empty = [at for at, _image, state in transition
                     if info_ink_rows(state) == 0]
            if empty:
                problems.append('%s exposes an empty Info body on %s'
                                % (name, ' '.join('f%d' % at
                                                  for at in empty[:16])))
            torn = [(at, incomplete_info_rows(state, outgoing, target))
                    for at, _image, state in transition
                    if incomplete_info_rows(state, outgoing, target)]
            continuity[name] = (len(empty), len(torn))
            if torn:
                problems.append('%s exposes incomplete row rasters: %s'
                                % (name, ' '.join('f%d=%s' % event
                                                  for event in torn[:16])))

        if leaving:
            if not any(target_chrome_complete(state, target)
                       and not target_body_text_visible(state, target)
                       for _at, _image, state in observed):
                problems.append('%s never exposes complete empty parent chrome before text'
                                % name)
        else:
            first_body = next((at for at, _image, state in observed
                               if target_body_text_visible(state, target)), None)
            if first_body is None:
                problems.append('%s never exposes target body text' % name)
            elif first_body - owned_at > 2:
                problems.append('%s delays target Info text for %d frames after ownership'
                                % (name, first_body - owned_at))

    print('floorinfospill: dispatches %s' %
          ' '.join('f%d:%d' % event for event in dispatches))
    print('floorinfospill: LCD-off counts %s' %
          ' '.join('%s=%d' % (name, len(lcd_off[name]))
                   for name, _at in transitions))
    print('floorinfospill: uniform-frame counts %s' %
          ' '.join('%s=%d' % (name, len(white[name]))
                   for name, _at in transitions))
    if continuity:
        print('floorinfospill: page continuity %s' %
              ' '.join('%s=%d-empty/%d-torn' %
                       (name, counts[0], counts[1])
                       for name, counts in continuity.items()))
    if trace:
        print('  injected inventory %s' % (injection_state,))
        print('  info attempts %s' % (info_attempts,))
        print('  lifecycle %s' % (lifecycle,))
        for call in calls:
            at, rownum, key, mode, shape, source, row = call
            if 2750 <= at <= 3850:
                print('  f%d d%d key=$%04X mode%d shape=%s src=$%04X row=%s'
                      % (at, rownum, key, mode, shape, source, row.hex(' ')))
        for name, _at in transitions:
            target = settled_states.get(name)
            if target is None:
                continue
            for at, _image, state in samples[name]:
                if target_body_text_visible(state, target) and not target_chrome_complete(state, target):
                    print('  %s f%d chrome mismatch %s' %
                          (name, at, chrome_mismatches(state, target)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('floorinfospill: %d problem(s)' % len(problems))
    label = ('Manji Kabura+1 seal' if seal else
             'Fusion Pot[2]' if fusion else 'Wood Arrow')
    if fusion_kit_history:
        label += ' after Lua Fusion Pot Action'
    elif fusion_kit:
        label += ' + Lua fusion kit'
    print('floorinfospill: real %s action/Info transitions are atomic' % label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu_wood_arrow.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3900)
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--fusion', action='store_true')
    parser.add_argument('--seal', action='store_true')
    parser.add_argument('--fusion-kit', action='store_true')
    parser.add_argument('--fusion-kit-history', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('floorinfospill: missing RAM fixture: %s' % args.ram)
    if args.fusion and args.fusion_kit_history:
        parser.error('--fusion-kit-history uses the standing Wood Arrow; do not combine '
                     'it with --fusion')
    if args.fusion and args.seal:
        parser.error('--fusion and --seal replace the same ground object')
    if args.seal and args.fusion_kit_history:
        parser.error('--fusion-kit-history requires the standing Wood Arrow')
    run(args.rom, args.ram, args.png_dir, args.frames, args.trace, args.fusion,
        args.fusion_kit, args.fusion_kit_history, args.seal)


if __name__ == '__main__':
    main()
