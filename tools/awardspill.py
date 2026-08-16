#!/usr/bin/env python3
"""Trace and verify the real save-backed Awards screen.

Unlike ``conditionspill.py``, this fixture starts at the title screen, selects the
Rank/Pass menu, chooses Pass, and lets the game's own completed-condition bitfield
and row stager run.  It exists because injecting already-expanded rows after that stager
can prove the compositor while missing a failure on the route a player actually uses.

    python3 tools/awardspill.py build/shiren_en.gb \
        --ram saves/shiren_en_log_1_password.srm \
        --png build/awardspill.png [--trace]
"""
import argparse
import csv
import os
import shutil
import tempfile

from gbrun import _import_pyboy, PRESS_FRAMES
import conditionspill
import menuspill
import menuvwf


DISPATCH = (4, 0x48AA)
STAGER = (4, 0x79E4)
ROW_DRAWER = (31, menuvwf.ROW_DRAWER)
ROW_EPILOG = (31, menuvwf.ROW_EPILOG)
PAGE_LEFT = (4, 0x7AC8)
PAGE_RIGHT = (4, 0x7AE7)
STAGING = 0xC616
SHADOW = 0xC300
SHAPE_AWARDS = (0, 6, 5, 18, 0)
SHAPE_TITLE = (7, 3, 1, 4, 0)
SHAPE_PASS_LOG = (5, 9, 9, 2)  # x, y, width, flags; row count is live-log count
FLAG_BASES = (0xC57D, 0xC58D, 0xC59D)
PASSWORD_BASES = (0xC579, 0xC589, 0xC599)
PASSWORD_TABLE = (4, 0x79C4)
TITLE_TEXT = 'Pass'
TITLE_CODES = tuple(menuvwf.propvwf.EN_CODES[ch] for ch in TITLE_TEXT)
# The native flag scanner's logical order starts with the four ordinary clear/password
# conditions stored at the tail of bank 14, then continues through the main record list.
# Address order is therefore not flag order.
FLAG_TO_ROW = (
    35, 36, 37, 38,             # Normal/Hard clear and no-carry-in passwords
    0, 1, 2, 3, 4, 5, 6,        # companions and Moonlight escape
    8, 29,                       # 90000 Gitan, then the 999999-Gitan record
    9, 10, 11, 12, 13, 14,      # Gitan/fullness/strength/HP/level records
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28,
    31, 30, 32, 33, 34,          # special defeats and the far-shot Fusion Pot record
    7,                            # 1000 adventures
    39,                           # rescued Baby Mamel
)

# The four repeated Start presses tolerate the title/copyright timing on both ordinary
# and shuffled builds. Five Down presses select Rank/Pass; the popup starts on Rank,
# so one more Down selects Pass.
BUTTONS = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1230: 'down', 1270: 'down', 1310: 'down', 1350: 'down', 1390: 'down',
    1460: 'a', 1700: 'down', 1800: 'a', 2000: 'a',
}
# A title with three populated logs has only six rows, so Rank/Pass is reached after
# three Down presses.  The ordinary one-log fixture has eight rows and retains the
# five-Down schedule above.
MULTI_LOG_BUTTONS = {1350: None, 1390: None}


def _codes(pb, source, limit=32):
    out = []
    if not 0xC000 <= source < 0xE000:
        return tuple(out)
    for addr in range(source, min(source + limit, 0xE000)):
        value = pb.memory[addr]
        if value == 0xFF:
            break
        out.append(value)
    return tuple(out)


def run(PyBoy, rom, ram, profile, frames, png=None, trace=False,
        award_index=None, password_seed=None, unlock_all=False,
        extra_buttons=None, pass_logs_override=None):
    with tempfile.TemporaryDirectory(prefix='awardspill-') as tmp:
        work = os.path.join(tmp, 'awards.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        injections = []
        seeds = []
        stages = []
        drawers = []
        screen_rows = []
        paged_awards = []
        pass_log_lists = []
        pass_selector = []
        proportional = []
        pending = []
        page_callbacks = []

        def at_dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))
            if pb.register_file.A == 32:
                if pass_logs_override is not None:
                    values = tuple(pass_logs_override) + (0xFF,)
                    for offset in range(4):
                        pb.memory[0xC6E3 + offset] = (values[offset]
                                                     if offset < len(values) else 0xFF)
                logs = []
                for address in range(0xC6E3, 0xC6E7):
                    value = pb.memory[address]
                    if value == 0xFF:
                        break
                    logs.append(value)
                pass_log_lists.append((frame[0], tuple(logs)))
            # The log picker computes the page count before screen 34 is drawn.  For the
            # all-unlocked pagination fixture, publish the five bytes as screen 32 opens
            # so its native count and arrow setup see the same state as the later stager.
            if pb.register_file.A in (30, 32) and unlock_all:
                log = pb.memory[0xC6AB]
                if log < len(FLAG_BASES):
                    base = FLAG_BASES[log]
                    for offset in range(5):
                        pb.memory[base + offset] = 0xFF
                    injections.append((frame[0], log, base, 'all-precount'))
            if pb.register_file.A != 34:
                return
            log = pb.memory[0xC6AB]
            if log >= len(FLAG_BASES):
                return
            password_base = PASSWORD_BASES[log]
            seeds.append((frame[0], log,
                          tuple(pb.memory[password_base:password_base + 12])))
            if award_index is None and not unlock_all:
                return
            if password_seed is not None:
                for offset, value in enumerate(password_seed):
                    pb.memory[password_base + offset] = value
            base = FLAG_BASES[log]
            for offset in range(5):
                pb.memory[base + offset] = 0xFF if unlock_all else 0
            if not unlock_all:
                pb.memory[base + award_index // 8] = 1 << (award_index & 7)
            injections.append((frame[0], log, base,
                               'all' if unlock_all else award_index))

        def at_stager(_ctx=None):
            stages.append((frame[0], pb.memory[0xC6AB], pb.memory[0xC6DE],
                           tuple(pb.memory[0xC57D:0xC5AD])))

        def row_record(kind):
            shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            record = (frame[0], kind, pb.register_file.D, pb.register_file.HL,
                      shape, source, _codes(pb, source))
            if kind == 'drawer' and frame[0] >= 1990:
                screen_rows.append(record)
            if (shape[0], shape[1], shape[3], shape[4]) == SHAPE_PASS_LOG:
                pass_selector.append(record)
            if shape == SHAPE_AWARDS:
                if kind == 'drawer':
                    paged_awards.append((frame[0], pb.memory[0xC6DE], record[2],
                                         record[6]))
                if kind == 'drawer':
                    drawers.append(record)
                    pending.append(record)
                else:
                    proportional.append(record)
            if trace:
                print('  f%d %-12s row=%d hl=$%04X src=$%04X shape=%s cells=%s'
                      % (record[0], kind, record[2], record[3], record[5],
                         record[4], bytes(record[6]).hex()))

        epilogues = []
        def at_epilog(_ctx=None):
            if not pending:
                return
            record = pending.pop(0)
            key = record[3]
            epilogues.append((frame[0], key,
                              bytes(pb.memory[key:key + SHAPE_AWARDS[3] + 2]),
                              tuple(menuspill.records(pb, profile))))

        pb.hook_register(*DISPATCH, at_dispatch, None)
        pb.hook_register(*PAGE_LEFT,
                         lambda _ctx: page_callbacks.append((frame[0], 'left')), None)
        pb.hook_register(*PAGE_RIGHT,
                         lambda _ctx: page_callbacks.append((frame[0], 'right')), None)
        pb.hook_register(*STAGER, at_stager, None)
        pb.hook_register(*ROW_DRAWER, lambda _ctx: row_record('drawer'), None)
        if profile is not None:
            pb.hook_register(menuvwf.FAR_BANK, profile['entry'],
                             lambda _ctx: row_record('proportional'), None)
            pb.hook_register(*ROW_EPILOG, at_epilog, None)

        last = None
        buttons = dict(BUTTONS)
        if extra_buttons:
            buttons.update(extra_buttons)
        for current in range(frames):
            frame[0] = current
            button = buttons.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current >= frames - 120:
                last = pb.screen.image.copy()
        if png and last is not None:
            os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
            last.save(png)
        result = {
            'dispatches': dispatches, 'injections': injections, 'seeds': seeds,
            'stages': stages, 'drawers': drawers,
            'proportional': proportional, 'epilogues': epilogues,
            'screen_rows': screen_rows,
            'pass_log_lists': pass_log_lists,
            'pass_selector': pass_selector,
            'paged_awards': paged_awards,
            'page_callbacks': page_callbacks,
            'final_records': (tuple(menuspill.records(pb, profile))
                              if profile is not None else ()),
            'final_bad': (tuple(menuspill.frame_invariant(pb, profile))
                          if profile is not None else ()),
            'final_page': pb.memory[0xC6DE],
            'final_page_count': pb.memory[0xC6BE],
            'final_colors': (len(set(last.convert('RGB').getdata()))
                             if last is not None else 0),
            'final_transition_state': pb.memory[0xC0D7],
            'final_lcdc': pb.memory[0xFF40],
        }
        pb.stop(save=False)
        return result


def _password_table(path):
    bank, addr = PASSWORD_TABLE
    offset = bank * 0x4000 + addr - 0x4000
    with open(path, 'rb') as src:
        src.seek(offset)
        return tuple(src.read(32))


def _title_record(result):
    rows = [record for record in result['screen_rows']
            if record[4] == SHAPE_TITLE]
    if not rows:
        return None
    # The native producer writes its four visible code bytes without terminating the
    # shared staging buffer. Compare only the descriptor's four-character payload; the
    # English ``Pass`` producer does terminate, but must obey the same visible contract.
    titles = {tuple(record[6][:SHAPE_TITLE[3]]) for record in rows}
    if len(titles) != 1:
        return None
    return titles.pop()


def _award_record(result):
    rows = [record for record in result['screen_rows']
            if record[4] == SHAPE_AWARDS and record[2] == 0]
    if len(rows) != 1:
        return None
    return tuple(rows[0][6])


def _code_text(codes):
    inverse = {code: char for char, code in menuvwf.propvwf.EN_CODES.items()}
    return ''.join(inverse.get(code, '?') for code in codes)


def _pass_selector_problems(result, label, expected_logs):
    """Require one complete proportional row for every generated Pass log."""
    problems = []
    lists = result['pass_log_lists']
    if len(lists) != 1:
        return ['%s staged %d Pass log list(s), expected 1' % (label, len(lists))]
    logs = lists[0][1]
    if logs != tuple(expected_logs):
        problems.append('%s exposed logs %s, expected %s'
                        % (label, logs, tuple(expected_logs)))
    expected = tuple((0,) + tuple(menuvwf.propvwf.EN_CODES[ch] for ch in 'Log') +
                     (log + 2,) for log in logs)
    drawer_rows = tuple(tuple(record[6]) for record in result['pass_selector']
                        if record[1] == 'drawer')
    proportional_rows = tuple(tuple(record[6]) for record in result['pass_selector']
                              if record[1] == 'proportional')
    if drawer_rows != expected:
        problems.append('%s rows were %s, expected %s'
                        % (label, drawer_rows, expected))
    if proportional_rows != expected:
        problems.append('%s sent %s through VWF, expected %s'
                        % (label, proportional_rows, expected))
    if result['final_transition_state'] != 0:
        problems.append('%s left title transaction state $%02X active'
                        % (label, result['final_transition_state']))
    if not result['final_lcdc'] & 0x80:
        problems.append('%s left the LCD disabled ($FF40=$%02X)'
                        % (label, result['final_lcdc']))
    return problems


def matrix(PyBoy, rom, control, ram, profile, frames, password_seed,
           csv_path=None, all_png=None):
    """Exercise each of the 40 award bits and the translated heading.

    Each isolated award must select its intended English row and display the exact
    ``Pass`` heading. The untouched control's generated four-kana value is retained in
    the CSV only as a diagnostic for the underlying state; the patch no longer displays
    that value.
    """
    rows = conditionspill.condition_rows(profile, ranked=False)
    built_table = _password_table(rom)
    control_table = _password_table(control)
    problems = []
    if built_table != control_table:
        problems.append('the 32-character password alphabet differs from the control ROM')

    output = []
    for index, row_index in enumerate(FLAG_TO_ROW):
        _tiles, loc, text, codes = rows[row_index]
        translated = run(PyBoy, rom, ram, profile, frames,
                         award_index=index, password_seed=password_seed)
        original = run(PyBoy, control, ram, None, frames,
                       award_index=index, password_seed=password_seed)
        built_title = _title_record(translated)
        control_code = _title_record(original)
        shown_award = _award_record(translated)
        expected_award = tuple(codes)
        translated_injections = [(log, base, flag) for _frame, log, base, flag
                                 in translated['injections']]
        original_injections = [(log, base, flag) for _frame, log, base, flag
                               in original['injections']]
        if translated_injections != [(0, FLAG_BASES[0], index)]:
            problems.append('%s: translated route did not inject the isolated flag once'
                            % loc)
        if original_injections != [(0, FLAG_BASES[0], index)]:
            problems.append('%s: control route did not inject the isolated flag once'
                            % loc)
        if shown_award != expected_award:
            problems.append('%s: staged award %s, expected %s'
                            % (loc, shown_award, expected_award))
        if built_title != TITLE_CODES:
            problems.append('%s: title staged %s, expected `%s` %s'
                            % (loc, built_title, TITLE_TEXT, TITLE_CODES))
        if control_code is None or len(control_code) != 4:
            problems.append('%s: control route did not draw one four-character native code'
                            % loc)
            control_code = ()
        if any(code not in built_table for code in control_code):
            problems.append('%s: native code contains a byte outside its alphabet: %s'
                            % (loc, control_code))
        output.append((loc, text, _code_text(control_code)))

    # The ordinary menu exposes five unlocked awards per page.  Exercise its real Down
    # pagination across all eight pages with every bit set; this catches page-local tile
    # exhaustion and logical flag/string-order mistakes that isolated rows cannot.
    next_page = {2200 + 200 * page: 'down' for page in range(7)}
    all_result = run(PyBoy, rom, ram, profile, 3600, png=all_png,
                     password_seed=password_seed, unlock_all=True,
                     extra_buttons=next_page)
    expected_rows = [tuple(rows[row_index][3]) for row_index in FLAG_TO_ROW]
    shown_rows = [tuple(codes) for _frame, _page, _row, codes
                  in all_result['paged_awards']]
    staged_pages = [page for _frame, _log, page, _flags in all_result['stages']]
    if staged_pages != list(range(8)):
        problems.append('all-unlocked native pages were %s, expected 0-7'
                        % staged_pages)
    if shown_rows != expected_rows:
        mismatch = next((index for index, pair in enumerate(
                         zip(shown_rows, expected_rows)) if pair[0] != pair[1]), None)
        problems.append('all-unlocked rows differ from native flag order%s'
                        % (' at index %d' % mismatch if mismatch is not None else ''))
    if len(all_result['drawers']) != 40:
        problems.append('all-unlocked route drew %d/40 award rows'
                        % len(all_result['drawers']))
    if len(all_result['proportional']) != 40:
        problems.append('all-unlocked route sent %d/40 award rows through VWF'
                        % len(all_result['proportional']))
    if len(all_result['epilogues']) != 40:
        problems.append('all-unlocked route completed %d/40 award rows'
                        % len(all_result['epilogues']))

    if _title_record(all_result) != TITLE_CODES:
        problems.append('all-unlocked route did not keep the exact `%s` heading'
                        % TITLE_TEXT)
    if all_result['final_colors'] <= 1:
        problems.append('all-unlocked route ended on a blank/white screen')

    if csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8', newline='') as dst:
            writer = csv.writer(dst)
            # Generated by the untouched Japanese control for a synthetic log whose only
            # award bit is the row under test. It is diagnostic state, not a permanent
            # one-to-one password and is not displayed by the English ROM.
            writer.writerow(('location', 'award', 'isolated_native_code'))
            writer.writerows(output)
    return output, problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', required=True)
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=2300)
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--multi-log', action='store_true',
                        help='use the three-populated-log title route and verify the '
                             'generated Pass log selector')
    parser.add_argument('--matrix', action='store_true',
                        help='isolate all 40 award flags and verify their passwords')
    parser.add_argument('--control', default='build/_base_expanded.gb',
                        help='untouched ROM used for byte-exact password comparison')
    parser.add_argument(
        '--csv',
        help='write all 40 labels plus each isolated-state diagnostic password as CSV')
    parser.add_argument('--all-png', help='capture page 8 of the all-unlocked route')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('awardspill: missing %s' % path)
    if args.matrix and not os.path.exists(args.control):
        raise SystemExit('awardspill: missing control ROM %s' % args.control)
    if args.multi_log and args.matrix:
        raise SystemExit('awardspill: --multi-log and --matrix are separate routes')
    if (args.csv or args.all_png) and not args.matrix:
        raise SystemExit('awardspill: --csv/--all-png require --matrix')

    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('awardspill: requires the approved proportional renderer')
    result = run(_import_pyboy(), args.rom, args.ram, profile, args.frames,
                 args.png, args.trace,
                 extra_buttons=(MULTI_LOG_BUTTONS if args.multi_log else None))
    problems = []
    if not any(index == 34 for _frame, index in result['dispatches']):
        problems.append('real title route never dispatched Awards screen 34; got %s'
                        % (result['dispatches'],))
    if len(result['stages']) != 1:
        problems.append('real condition stager ran %d time(s), expected 1'
                        % len(result['stages']))
    if not result['drawers']:
        problems.append('no Awards rows reached the ordinary box-44 drawer')
    if len(result['proportional']) != len(result['drawers']):
        problems.append('%d/%d Awards rows entered the proportional path'
                        % (len(result['proportional']), len(result['drawers'])))
    if len(result['epilogues']) != len(result['drawers']):
        problems.append('%d/%d Awards rows reached the drawer epilogue'
                        % (len(result['epilogues']), len(result['drawers'])))
    title = _title_record(result)
    if title != TITLE_CODES:
        problems.append('small heading staged %s, expected exact `%s` %s'
                        % (title, TITLE_TEXT, TITLE_CODES))
    if result['final_colors'] <= 1:
        problems.append('ordinary Awards route ended on a blank/white screen')
    max_selector = None
    if args.multi_log:
        problems += _pass_selector_problems(
            result, 'two-log Pass selector', (0, 2))
        # The supplied SRAM naturally exercises Logs 1 and 3. Override only the live
        # selector list in a second run to cover its maximum three-row form as well;
        # stop before choosing a synthetic log so no unrelated award state is assumed.
        max_selector = run(
            _import_pyboy(), args.rom, args.ram, profile, 1900,
            extra_buttons=MULTI_LOG_BUTTONS, pass_logs_override=(0, 1, 2))
        problems += _pass_selector_problems(
            max_selector, 'three-log Pass selector', (0, 1, 2))

    print('awardspill: dispatches %s' % result['dispatches'])
    if args.multi_log and result['pass_log_lists']:
        logs = result['pass_log_lists'][0][1]
        print('  Pass selector: %d eligible log(s) %s; %d drawer, %d proportional row(s)'
              % (len(logs), tuple(log + 1 for log in logs),
                 sum(record[1] == 'drawer' for record in result['pass_selector']),
                 sum(record[1] == 'proportional'
                     for record in result['pass_selector'])))
    if max_selector is not None and max_selector['pass_log_lists']:
        logs = max_selector['pass_log_lists'][0][1]
        print('  max selector: %d eligible log(s) %s; %d drawer, %d proportional row(s)'
              % (len(logs), tuple(log + 1 for log in logs),
                 sum(record[1] == 'drawer' for record in max_selector['pass_selector']),
                 sum(record[1] == 'proportional'
                     for record in max_selector['pass_selector'])))
    if result['stages']:
        at, log, page, flags = result['stages'][0]
        print('  real stager: f%d log=%d page=%d; flag bytes %s'
              % (at, log, page, bytes(flags).hex()))
    print('  Awards rows: %d drawer, %d proportional, %d epilogue; %d problem(s)%s'
          % (len(result['drawers']), len(result['proportional']),
             len(result['epilogues']), len(problems),
             ' -> ' + args.png if args.png else ''))
    if args.trace:
        for at, key, shadow, records in result['epilogues']:
            print('  epilogue f%d key=$%04X shadow=%s records=%s'
                  % (at, key, shadow.hex(), records))
        print('  final VWF records: %s' % (result['final_records'],))
        print('  final unowned pool cells: %s' % (result['final_bad'][:10],))

    if args.matrix:
        if len(result['seeds']) != 1:
            problems.append('could not capture one canonical password-input record')
            password_seed = (0,) * 12
        else:
            password_seed = result['seeds'][0][2]
        rows, matrix_problems = matrix(
            _import_pyboy(), args.rom, args.control, args.ram, profile,
            min(args.frames, 2150), password_seed, args.csv, args.all_png)
        native_codes = [code for _loc, _award, code in rows]
        print('  award matrix: %d rows, exact `%s` heading; %d distinct native '
              'diagnostic codes: %s%s'
              % (len(rows), TITLE_TEXT, len(set(native_codes)), ','.join(native_codes),
                 ' -> ' + args.csv if args.csv else ''))
        problems += matrix_problems
    for problem in problems:
        print('  ' + problem)
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
