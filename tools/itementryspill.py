#!/usr/bin/env python3
"""Prove Status -> Items entry/re-entry and its first page change stay LCD-on.

The real 18-item SRAM is exercised independently from each of its four Item pages:
leave to the root Status screen, reopen Items, then page once in a non-sentinel
direction.  The entry controller must retire only visible BG rows 0..15 over four
complete VBlanks, commit the empty header/list-box chrome before any item text, preserve
the enabled two-row Window, and hand the incoming screen to the existing row/final-map
publishers. The following page change must use the narrow five-row transaction and may
never reach the LCD-off fallback.
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
import gbasm                                                       # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import statusvwf                                                   # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)


def expected_chrome():
    """Visible BG rows 0..15 immediately after the entry-owned clear."""
    bg = bytearray(16 * 32)

    def box(x, y, width, bottom):
        bg[y * 32 + x:y * 32 + x + width + 2] = \
            bytes((0xB8,)) + bytes((0xBC,)) * width + bytes((0xB9,))
        for row in range(y + 1, bottom):
            bg[row * 32 + x] = 0xBE
            bg[row * 32 + x + width + 1] = 0xBF
        bg[bottom * 32 + x:bottom * 32 + x + width + 2] = \
            bytes((0xBA,)) + bytes((0xBD,)) * width + bytes((0xBB,))

    box(0, 0, 4, 2)
    box(0, 3, 18, 13)
    return bytes(bg)


EXPECTED_CHROME = expected_chrome()


def status_labels():
    font = statusvwf.propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in statusvwf.SLOT_CODES)
    _code, labels = gbasm.assemble(statusvwf._source(widths), statusvwf.CODE_AT)
    return labels


def state(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'lcdc': pb.memory[0xFF40],
        'ly': pb.memory[0xFF44],
    }


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def run_page(PyBoy, rom, ram, target, status_runtime, region_runtime, png_dir=None,
             frames=3800):
    problems = []
    with tempfile.TemporaryDirectory(prefix='itementryspill-') as tmp:
        run_rom = os.path.join(tmp, 'itementry.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(BOOT)
        opened = [False]
        b_at = [None]
        status_at = [None]
        reopen_at = [None]
        direction_at = [None]
        reentry_complete = [None]
        first_reentry_row = [None]
        post_complete = [None]
        entry_origins = []
        entry_done = []
        entry_batches = []
        regional_begins = []
        fallbacks = []
        samples = []

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            if screen == 0 and b_at[0] is None and not opened[0]:
                schedule[frame[0] + 80] = 'a'
                opened[0] = True
            elif screen == 0 and b_at[0] is not None and status_at[0] is None:
                status_at[0] = frame[0]
                reopen_at[0] = frame[0] + 120
                schedule[reopen_at[0]] = 'a'

        def item_row(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE or pb.register_file.D != 4:
                return
            selector = pb.memory[0xC6AC]
            page = selector // 5 + 1 if selector < pb.memory[0xC6AA] else 0
            if b_at[0] is None:
                at = frame[0] + 60
                if page < target:
                    schedule[at] = 'right'
                elif page == target:
                    schedule[at] = 'b'
                    b_at[0] = at
                return
            if reopen_at[0] is None or frame[0] <= reopen_at[0]:
                return
            if first_reentry_row[0] is None:
                first_reentry_row[0] = (frame[0], pb.register_file.D)
            if direction_at[0] is None:
                reentry_complete[0] = (frame[0], selector)
                direction_at[0] = frame[0] + 20
                schedule[direction_at[0]] = 'right'
            elif frame[0] > direction_at[0] and post_complete[0] is None:
                post_complete[0] = (frame[0], selector)

        def entry_begin(_ctx=None):
            if status_at[0] is None:
                return
            entry_origins.append((frame[0], state(pb),
                                  tuple(pb.memory[0xC534 + i] for i in range(3)),
                                  pb.memory[0xC6A3], pb.memory[0xC6A6]))

        def entry_batch(_ctx=None):
            if status_at[0] is None:
                return
            entry_batches.append((frame[0], pb.memory[0xFF44]))

        def entry_finish(_ctx=None):
            if status_at[0] is None:
                return
            entry_done.append((frame[0], state(pb)))

        def region_begin(_ctx=None):
            if direction_at[0] is not None and frame[0] >= direction_at[0] - 2:
                regional_begins.append(frame[0])

        def fallback(_ctx=None):
            if reopen_at[0] is not None and frame[0] >= reopen_at[0] - 2:
                fallbacks.append(frame[0])

        profile = menuspill.renderer_profile(rom)
        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementryblank'],
                         entry_begin, None)
        pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementrybatchdone'],
                         entry_batch, None)
        pb.hook_register(statusvwf.FAR_BANK, status_runtime['itementryblankdone'],
                         entry_finish, None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_runtime['irshadow'],
                         region_begin, None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_runtime['irfaillcd'],
                         fallback, None)

        for frame[0] in range(frames):
            action = schedule.get(frame[0])
            if action:
                pb.button(action, PRESS_FRAMES)
            pb.tick()
            if reopen_at[0] is not None and frame[0] >= reopen_at[0] - 2:
                samples.append((frame[0], state(pb), pb.screen.image.copy()))
                if png_dir and (reopen_at[0] <= frame[0] <= reopen_at[0] + 30 or
                                any(frame[0] == at for at, _snapshot in entry_done) or
                                (post_complete[0] and frame[0] == post_complete[0][0])):
                    pb.screen.image.save(os.path.join(
                        png_dir, 'page%d_reentry_f%04d.png' % (target, frame[0])))

        if len(entry_origins) != 1 or len(entry_done) != 1:
            problems.append('page %d accepted %d entry origins and %d completions' %
                            (target, len(entry_origins), len(entry_done)))
        else:
            _origin_at, origin, stack, screen, replay = entry_origins[0]
            done_at, done = entry_done[0]
            if stack != (1, 0, 1) or screen != 1 or replay != 0:
                problems.append('page %d entry proof is stack=%s screen=%d replay=%d' %
                                (target, stack, screen, replay))
            if not origin['lcdc'] & 0x80 or not done['lcdc'] & 0x80:
                problems.append('page %d disabled LCD across entry blank' % target)
            if not 0x90 <= done['ly'] <= 0x99:
                problems.append('page %d chrome commit ended outside VBlank at LY=$%02X' %
                                (target, done['ly']))
            visible = {row * 32 + col for row in range(16) for col in range(20)}
            wrong_chrome = next((offset for offset in visible
                                 if done['bg'][offset] != EXPECTED_CHROME[offset]), None)
            changed = next((offset for offset in range(0x400)
                            if offset not in visible and
                            origin['bg'][offset] != done['bg'][offset]), None)
            if wrong_chrome is not None:
                problems.append('page %d entry chrome differs at BG +$%03X: '
                                'got $%02X expected $%02X' %
                                (target, wrong_chrome, done['bg'][wrong_chrome],
                                 EXPECTED_CHROME[wrong_chrome]))
            if changed is not None:
                problems.append('page %d entry changed locked BG +$%03X' %
                                (target, changed))
            if done['window'] != origin['window']:
                problems.append('page %d entry changed the persistent Window map' % target)
            if done['tiles'] != origin['tiles']:
                problems.append('page %d entry changed tile planes before Item drawing' %
                                target)
            if done_at < _origin_at:
                problems.append('page %d entry completion precedes its origin' % target)
            if first_reentry_row[0] is None or first_reentry_row[0][0] < done_at:
                problems.append('page %d item text began before chrome completion: %s '
                                'versus f%d' %
                                (target, first_reentry_row[0], done_at))

        if len(entry_batches) != 4:
            problems.append('page %d entry used %d VBlank batches, expected 4' %
                            (target, len(entry_batches)))
        late = next(((at, ly) for at, ly in entry_batches if not 0x90 <= ly <= 0x99), None)
        if late:
            problems.append('page %d entry batch ended outside VBlank at f%d LY=$%02X' %
                            (target, late[0], late[1]))
        if reentry_complete[0] is None:
            problems.append('page %d did not complete its Status -> Items redraw' % target)
        elif reentry_complete[0][1] != 0:
            problems.append('page %d re-entered with selector %d, expected native reset 0' %
                            (target, reentry_complete[0][1]))
        if post_complete[0] is None:
            problems.append('page %d did not complete its post-entry page change' % target)
        if len(regional_begins) != 1:
            problems.append('page %d post-entry change began %d regional transactions' %
                            (target, len(regional_begins)))
        if fallbacks:
            problems.append('page %d re-entry/page change reached fallback at %s' %
                            (target, ' '.join('f%d' % at for at in fallbacks)))
        lcd_off = [at for at, snapshot, _image in samples
                   if not snapshot['lcdc'] & 0x80]
        whites = [at for at, _snapshot, image in samples if white_frame(image)]
        if lcd_off:
            problems.append('page %d re-entry/page change disabled LCD at %s' %
                            (target, ' '.join('f%d' % at for at in lcd_off)))
        if whites:
            problems.append('page %d re-entry/page change produced all-white frames at %s' %
                            (target, ' '.join('f%d' % at for at in whites)))

        result = {
            'page': target,
            'status': status_at[0],
            'reopen': reopen_at[0],
            'batches': tuple(entry_batches),
            'chrome': (None if not entry_done else
                       (entry_done[0][0], entry_done[0][1]['ly'])),
            'reentry': reentry_complete[0],
            'post': post_complete[0],
            'regional': tuple(regional_begins),
            'fallbacks': tuple(fallbacks),
            'lcd_off': len(lcd_off),
            'white': len(whites),
            'problems': problems,
        }
        pb.stop(save=False)
        return result


def run(rom, ram, png_dir=None, frames=3800):
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('itementryspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    status_runtime = status_labels()
    _code, region_runtime = gbasm.assemble(menuvwf.ITEM_REGION_SRC,
                                           menuvwf.ITEM_REGION_AT)
    results = [run_page(PyBoy, rom, ram, page, status_runtime, region_runtime,
                        png_dir, frames) for page in range(1, 5)]
    problems = [problem for result in results for problem in result['problems']]
    for result in results:
        batches = ' '.join('f%d:$%02X' % event for event in result['batches'])
        chrome = ('missing' if result['chrome'] is None else
                  'f%d:$%02X' % result['chrome'])
        print('itementryspill: page %d Status f%s -> Items f%s; batches %s; chrome %s; '
              'reentry/post %s/%s; regional/fallback %d/%d; LCD-off %d, white %d' %
              (result['page'], result['status'], result['reopen'], batches,
               chrome,
               result['reentry'], result['post'], len(result['regional']),
               len(result['fallbacks']), result['lcd_off'], result['white']))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('itementryspill: %d problem(s)' % len(problems))
    print('itementryspill: pages 1-4 re-enter through a chrome-first, '
          'Window-preserving regional blank')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3800)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('itementryspill: missing %s' % path)
    run(args.rom, args.ram, args.png_dir, args.frames)


if __name__ == '__main__':
    main()
