#!/usr/bin/env python3
"""Production battery for the separately encoded prologue and ending cinematics.

This checks the translator contract, exact ROM installation, both VM variants, every
scene-pack upload, original pause lengths, natural completion, and the clip-0 skip path.
The ending variant is selected at the cinematic object's measured variant byte so it can
be exercised deterministically without clearing the post-game Moonshadow Village Exit.

    python3 tools/introspill.py build/_base_expanded.gb build/shiren_en.gb
    python3 tools/introspill.py ... --png-dir build/introspill
"""
import argparse
import csv
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont
import intro
from gbrun import PRESS_FRAMES, _import_pyboy


FORCE_ENTRY = (31, 0x4D50)
DONE = (31, 0x4D4F)
DELAY = (31, 0x5254)
CLEAR = (31, 0x5341)
DRAW = (31, 0x51FC)
MAX_FRAMES = 4800


def require(condition, message, problems):
    if not condition:
        problems.append(message)


def controls(tokens):
    return [(token.opcode, token.args) for token in tokens if token.kind == 'command']


def parse_compiled(data):
    out = []
    pos = 0
    while pos < len(data):
        value = data[pos]
        if value == 0:
            return out if pos + 1 == len(data) else [('BYTES_AFTER_END', b'')]
        if value <= 0x4C:
            pos += 1
            continue
        if value not in intro.ARITY:
            return [('BAD', bytes((value,)))]
        n = intro.ARITY[value]
        out.append((value, bytes(data[pos + 1:pos + 1 + n])))
        pos += 1 + n
    return [('NO_END', b'')]


def rows_from_text(text):
    lines = [line for line in text.splitlines(True)
             if line.strip() and not line.lstrip().startswith('#')]
    return list(csv.DictReader(io.StringIO(''.join(lines)), delimiter='\t'))


def write_rows(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as out:
        out.write('# Opening cinematic. Edit only the english column; <br> forces a line '
                  'break and <page> is a measured screen transition.\n')
        writer = csv.DictWriter(out, fieldnames=intro.TSV_COLUMNS, delimiter='\t',
                                lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def expect_error(source, rows, label, want, tmp, font):
    path = os.path.join(tmp, label + '.tsv')
    write_rows(path, rows)
    try:
        translations = intro.load_tsv(path, source)
        intro.compile_intro(source, translations, font)
    except SystemExit as exc:
        return want in str(exc), str(exc)
    return False, 'accepted invalid TSV'


def translator_checks(source, tsv_path, font, canonical):
    problems = []
    text = open(tsv_path, encoding='utf-8').read()
    require(intro.extract_tsv(source, tsv_path) == text,
            'canonical TSV does not round-trip through extraction', problems)
    rows = rows_from_text(text)

    with tempfile.TemporaryDirectory(prefix='introspill-tsv-') as tmp:
        cases = []

        changed = [dict(row) for row in rows]
        changed[-1]['english'] = 'All right. Let us run!'
        changed_path = os.path.join(tmp, 'edited.tsv')
        write_rows(changed_path, changed)
        edited_t = intro.load_tsv(changed_path, source)
        edited = intro.compile_intro(source, edited_t, font)
        require(edited['lines'][(1, 5, 0)] == 'All right. Let us run!',
                'edited English did not reach the layout', problems)
        changed_packs = [i for i, (a, b) in enumerate(zip(canonical['packs'],
                                                         edited['packs'])) if a != b]
        require(changed_packs == [11],
                'one edited line changed packs %s, expected only pack 11' % changed_packs,
                problems)
        test_rom = bytearray(source)
        intro.install(test_rom, changed_path, font=font, source_rom=source)
        pack_at = intro._off(intro.FAR_BANK,
                             intro.PACK_ORG + 11 * intro.PACK_SLOT_BYTES)
        pack_len = len(edited['packs'][11])
        require(bytes(test_rom[pack_at:pack_at + pack_len]) == edited['packs'][11],
                'edited TSV did not install its changed pack', problems)

        missing = [dict(row) for row in rows[:-1]]
        cases.append(('missing_line', missing, 'missing line'))
        blank = [dict(row) for row in rows]
        blank[0]['english'] = ''
        cases.append(('blank_english', blank, 'has no English translation'))
        drift = [dict(row) for row in rows]
        drift[0]['source_hex'] += '00'
        cases.append(('source_drift', drift, 'source drift'))
        malformed = [dict(row) for row in rows]
        malformed[7]['english'] = 'Look there!<page'
        cases.append(('malformed_control', malformed, 'malformed control syntax'))
        unknown_control = [dict(row) for row in rows]
        unknown_control[0]['english'] = 'Mother:<pause> My child...'
        cases.append(('unknown_control', unknown_control, 'unknown control'))
        wrong_pages = [dict(row) for row in rows]
        wrong_pages[7]['english'] = 'Look there! You can see Mount Sasara!'
        cases.append(('missing_page', wrong_pages, 'needs 2 page'))
        unknown_glyph = [dict(row) for row in rows]
        unknown_glyph[0]['english'] = 'Mother: My child ♥'
        cases.append(('unknown_glyph', unknown_glyph, 'has no approved-font glyph'))
        overflow = [dict(row) for row in rows]
        overflow[0]['english'] = 'M' * 80
        cases.append(('overflow', overflow, 'limit 152px'))

        for label, bad_rows, want in cases:
            ok, detail = expect_error(source, bad_rows, label, want, tmp, font)
            require(ok, '%s guard failed: %s' % (label, detail), problems)
    return problems, len(cases) + 3


def installation_checks(source, built_rom, canonical):
    problems = []
    generated = bytearray(source)
    intro.install(generated, os.path.join(ROOT, 'script', 'intro.tsv'),
                  font=dotfont.load_approved(), source_rom=source)

    bank_at = intro._off(intro.FAR_BANK, 0x4000)
    require(bytes(generated[bank_at:bank_at + intro.BANKSZ]) ==
            bytes(built_rom[bank_at:bank_at + intro.BANKSZ]),
            'normal build bank 63 differs from a direct canonical TSV install', problems)
    for lo, hi, name in ((0x4D46, 0x4D49, 'cleanup hook'),
                         (0x4FAF, 0x4FB2, 'initial-pack call'),
                         # markers.install owns the asserted retired slot $51E0-$51F7;
                         # intro's live timer/reader wrappers end at $51DF.
                         (0x51BA, 0x51E0, 'timer/reader hooks'),
                         (0x5254, 0x526A, 'delay hook')):
        at = intro._off(31, lo)
        require(bytes(generated[at:at + hi - lo]) == bytes(built_rom[at:at + hi - lo]),
                'normal build %s differs from direct install' % name, problems)
    mode8 = slice(0x1087, 0x11A8)
    require(bytes(built_rom[mode8]) == bytes(source[mode8]),
            'native mode-8 VBlank handler was changed', problems)

    for clip in range(2):
        source_controls = controls(intro.parse_program(source, clip))
        compiled_controls = parse_compiled(canonical['programs'][clip])
        require(compiled_controls == source_controls,
                'clip %d control stream changed during translation' % clip, problems)
    return problems


def run_variant(PyBoy, rom_path, source, canonical, clip, translated,
                press_at=None, png_dir=None):
    pb = PyBoy(rom_path, window='null')
    pb.set_emulation_speed(0)
    frame = [0]
    setup = []
    done = []
    delays = []
    clears = []
    first_pack = []
    first_pack_detail = []
    pack_checks = []
    panel_reference = {}
    panel_unstable = set()
    panel_first_change = {}
    panel_frames = {}
    row_checks = []
    row_check_detail = []
    active_panel = [None]
    waiting_draw = [None]
    clear_to_draw = []
    uploads = []
    reads = [0]
    done_state = []

    if translated:
        target_ptrs = {canonical['program_addresses'][clip] +
                       canonical['after'][clip][delay] - 1: index
                       for index, (_clear, delay, _pack) in
                       enumerate(intro.TRANSITIONS[clip])}
        read_site = (intro.FAR_BANK, canonical['labels']['read'])
        upload_site = (0, 0x1087)
        final_capture_ptr = (canonical['program_addresses'][0] +
                             canonical['after'][0][0x5DB9] - 1) if clip == 0 else None
    else:
        start = intro.PROGRAMS[clip][0]
        target_ptrs = {delay - start + 1: index
                       for index, (_clear, delay, _pack) in
                       enumerate(intro.TRANSITIONS[clip])}
        read_site = (31, 0x51C9)
        upload_site = None
        final_capture_ptr = 0x5DB9 - intro.PROGRAMS[0][0] + 1 if clip == 0 else None

    def force(_ctx):
        de = (pb.register_file.D << 8) | pb.register_file.E
        pb.memory[de + 0x10] = clip
        setup.append(frame[0])

    def finished(_ctx):
        done.append(frame[0])
        destinations = tuple(pb.memory[base] | (pb.memory[base + 1] << 8)
                             for base in (0xC006, 0xC01C, 0xC032, 0xC048, 0xC05E))
        done_state.append((destinations, pb.memory[intro.S_LEFT]))

    def delay(_ctx):
        de = (pb.register_file.D << 8) | pb.register_file.E
        pointer = pb.memory[de + 0x2E] | (pb.memory[de + 0x2F] << 8)
        if pointer == final_capture_ptr:
            if png_dir and translated:
                pb.screen.image.save(os.path.join(png_dir, 'clip0_scene6.png'))
            return
        if pointer not in target_ptrs:
            return
        index = target_ptrs[pointer]
        delays.append((frame[0], index))
        # The hook runs during the emulated frame.  Take the visual baseline after that
        # frame completes so the final typewriter tile is already visible.
        panel_reference[index] = None
        panel_frames[index] = 0
        active_panel[0] = index
        if png_dir and translated:
            pb.screen.image.save(os.path.join(
                png_dir, 'clip%d_scene%d.png' % (clip, index + 1)))

    def clear(_ctx):
        clears.append(frame[0])
        number = len(clears)
        active_panel[0] = None
        if number <= 5:
            waiting_draw[0] = (number - 1, frame[0])
        if png_dir and translated and clip == 1 and number == 6:
            pb.screen.image.save(os.path.join(png_dir, 'clip1_scene6.png'))
        if translated and number <= 5:
            want = canonical['packs'][clip * intro.PACKS_PER_CLIP + number]
            got = intro.vram_pack(pb.memory, number)
            pack_checks.append(got == want)

    def draw(_ctx):
        if waiting_draw[0] is not None:
            index, clear_frame = waiting_draw[0]
            clear_to_draw.append((index, frame[0] - clear_frame))
            waiting_draw[0] = None
        if translated and not first_pack:
            want = canonical['packs'][clip * intro.PACKS_PER_CLIP]
            got = intro.vram_pack(pb.memory, 0)
            period_at = 0x8B00 + canonical['period_code'] * 16
            period = bytes(pb.memory[period_at:period_at + 16])
            period_ok = clip == 0 or period == canonical['period']
            differences = [index for index, (got_byte, want_byte) in
                           enumerate(zip(got, want)) if got_byte != want_byte]
            first_pack_detail.append((differences[:8], period_ok))
            first_pack.append(got == want and period_ok)

    def read(_ctx):
        reads[0] += 1

    def upload(_ctx):
        bases = (0xC006, 0xC01C, 0xC032, 0xC048, 0xC05E)
        destinations = tuple(pb.memory[base] | (pb.memory[base + 1] << 8)
                             for base in bases)
        dest = destinations[0]
        if not intro.is_buffer_vram(dest):
            return
        payload = b''.join(bytes(pb.memory[base + 2:base + 22]) for base in bases)
        uploads.append((frame[0], dest, payload,
                        pb.memory[0xFF44], pb.memory[0xFF41] & 3, destinations))

    pb.hook_register(*FORCE_ENTRY, force, None)
    pb.hook_register(*DONE, finished, None)
    pb.hook_register(*DELAY, delay, None)
    pb.hook_register(*CLEAR, clear, None)
    pb.hook_register(*DRAW, draw, None)
    pb.hook_register(*read_site, read, None)
    if upload_site is not None:
        pb.hook_register(*upload_site, upload, None)

    for current in range(MAX_FRAMES):
        frame[0] = current
        if press_at is not None and current == press_at:
            pb.button('a', PRESS_FRAMES)
        pb.tick()
        index = active_panel[0]
        if index is not None:
            panel_frames[index] += 1
            panel = pb.screen.image.crop((0, 104, 160, 144)).tobytes()
            if panel_reference[index] is None:
                panel_reference[index] = panel
                if translated:
                    expected_rows = []
                    actual_rows = []
                    for row, base in ((0, 0xC01E), (1, 0xC04A)):
                        codes = canonical['row_codes'].get((clip, index, row), b'')
                        rendered = bytes(code + 0xB0 for code in codes)
                        # Clip 1 reveals three dramatic dots at columns 2-4 before its
                        # second row starts at column 5.  The stagger is native bytecode,
                        # not part of the translator's row string.
                        if (clip, index, row) == (1, 0, 1):
                            rendered = (b'\xFC\xFC' +
                                        bytes((canonical['period_code'] + 0xB0,)) * 3 +
                                        rendered)
                        expected_rows.append(rendered + b'\xFC' * (20 - len(rendered)))
                        actual_rows.append(bytes(pb.memory[base:base + 20]))
                    expected_blank = b'\xFC' * 20
                    actual_blanks = (bytes(pb.memory[0xC008:0xC01C]),
                                     bytes(pb.memory[0xC034:0xC048]))
                    ok = (actual_rows == expected_rows and
                          actual_blanks == (expected_blank, expected_blank))
                    row_checks.append(ok)
                    if not ok:
                        row_check_detail.append((index, actual_rows, expected_rows,
                                                 actual_blanks))
                if png_dir and translated:
                    pb.screen.image.save(os.path.join(
                        png_dir, 'clip%d_pause%d_reference.png' % (clip, index + 1)))
            elif panel != panel_reference[index]:
                panel_unstable.add(index)
                if index not in panel_first_change:
                    panel_first_change[index] = panel_frames[index]
                    if png_dir and translated:
                        pb.screen.image.save(os.path.join(
                            png_dir, 'clip%d_pause%d_changed.png' % (clip, index + 1)))
        if done:
            break
    pb.stop(save=False)
    return {'setup': setup, 'done': done, 'delays': delays, 'clears': clears,
            'first_pack': first_pack, 'pack_checks': pack_checks, 'reads': reads[0],
            'first_pack_detail': first_pack_detail,
            'panel_stable': [index not in panel_unstable for index in range(5)],
            'panel_frames': panel_frames, 'panel_first_change': panel_first_change,
            'row_checks': row_checks, 'row_check_detail': row_check_detail,
            'clear_to_draw': clear_to_draw,
            'uploads': uploads, 'done_state': done_state}


def expected_uploads(canonical, clip):
    """Return exact native-record destination/payload tuples for each VBlank pass."""
    sequence = canonical['seq0'] if clip == 0 else canonical['seq1']
    out = []
    stride = intro.UPLOAD_RECORDS * 4
    for pos in range(0, len(sequence), stride):
        destinations = []
        payloads = []
        for record in range(intro.UPLOAD_RECORDS):
            at = pos + record * 4
            dest = sequence[at] | (sequence[at + 1] << 8)
            source = sequence[at + 2] | (sequence[at + 3] << 8)
            payload = None
            for address, pack in zip(canonical['pack_addresses'], canonical['packs']):
                offset = source - address
                if 0 <= offset and offset + intro.UPLOAD_RECORD_BYTES <= len(pack):
                    payload = pack[offset:offset + intro.UPLOAD_RECORD_BYTES]
                    break
            if payload is None:
                raise AssertionError(
                    'introspill: sequence source $%04X is outside its packs' % source)
            destinations.append(dest)
            payloads.append(payload)
        out.append((tuple(destinations), b''.join(payloads)))
    return out


def runtime_checks(source_path, built_path, source, canonical, png_dir=None):
    problems = []
    PyBoy = _import_pyboy()
    natural = {}
    for clip in range(2):
        pair = []
        for translated, path in ((False, source_path), (True, built_path)):
            result = run_variant(PyBoy, path, source, canonical, clip, translated,
                                 png_dir=png_dir)
            pair.append(result)
            values = []
            by_start = {token.start: token for token in intro.parse_program(source, clip)}
            for _clear, delay, _pack in intro.TRANSITIONS[clip]:
                values.append(by_start[delay].args[0])
            got = [clear - delay[0]
                   for delay, clear in zip(result['delays'], result['clears'])]
            require(got == values,
                    'clip %d %s pause lengths %s, expected %s'
                    % (clip, 'English' if translated else 'source', got, values), problems)
            require(len(result['clears']) == 5 + (1 if clip == 1 else 0),
                    'clip %d %s clear count is %d'
                    % (clip, 'English' if translated else 'source',
                       len(result['clears'])), problems)
            require(bool(result['done']), 'clip %d %s did not return'
                    % (clip, 'English' if translated else 'source'), problems)
            require(result['panel_stable'] == [True] * 5,
                    'clip %d %s changed outgoing text before clear: %s'
                    % (clip, 'English' if translated else 'source',
                       (result['panel_stable'], result['panel_first_change'],
                        result['panel_frames'])),
                    problems)
            if translated:
                require(result['first_pack'] == [True],
                        'clip %d initial pack mismatch: %s'
                        % (clip, result['first_pack_detail']), problems)
                require(result['pack_checks'] == [True] * 5,
                        'clip %d transition pack mismatch: %s'
                        % (clip, result['pack_checks']), problems)
                require(result['row_checks'] == [True] * 5,
                        'clip %d settled tilemap rows differ from compiled slices: %s'
                        % (clip, result['row_check_detail']), problems)
                require(result['reads'] == len(canonical['programs'][clip]),
                        'clip %d read %d translated bytes, expected %d'
                        % (clip, result['reads'], len(canonical['programs'][clip])),
                        problems)
                expected = expected_uploads(canonical, clip)
                actual = [(targets, payload)
                          for _frame, _dest, payload, _ly, _mode, targets
                          in result['uploads']]
                require(actual == expected,
                        'clip %d native mode-8 passes differ: got %d, expected %d'
                        % (clip, len(actual), len(expected)), problems)
                unsafe = [(frame, ly, mode)
                          for frame, _dest, _payload, ly, mode, _targets
                          in result['uploads'] if not (144 <= ly <= 153 and mode == 1)]
                require(not unsafe,
                        'clip %d hidden copies ran outside VBlank: %s'
                        % (clip, unsafe[:8]), problems)
                require(len(result['done_state']) == 1 and
                        result['done_state'][0][1] == 0,
                        'clip %d cleanup did not stop native record staging: %s'
                        % (clip, result['done_state']), problems)
            else:
                require(result['reads'] == intro.PROGRAMS[clip][1] -
                        intro.PROGRAMS[clip][0],
                        'clip %d read %d source bytes' % (clip, result['reads']), problems)
        natural[clip] = pair
        require(pair[1]['clear_to_draw'] == pair[0]['clear_to_draw'],
                'clip %d English clear-to-next-text gaps %s differ from source %s'
                % (clip, pair[1]['clear_to_draw'], pair[0]['clear_to_draw']), problems)

    for clip in range(2):
        for translated, path in ((False, source_path), (True, built_path)):
            pressed = run_variant(PyBoy, path, source, canonical, clip, translated,
                                  press_at=1000)
            normal = natural[clip][1 if translated else 0]
            if clip == 0:
                expected = [1013] if translated else [1012]
                require(pressed['done'] == expected,
                        'clip 0 %s A-skip returned at %s, expected frame %d'
                        % ('English' if translated else 'source', pressed['done'],
                           expected[0]), problems)
                if translated:
                    require(len(pressed['done_state']) == 1 and
                            pressed['done_state'][0][1] == 0,
                            'clip 0 English A-skip did not stop native staging: %s'
                            % (pressed['done_state'],), problems)
            else:
                require(pressed['done'] == normal['done'],
                        'clip 1 %s changed behavior on A input: %s vs %s'
                        % ('English' if translated else 'source', pressed['done'],
                           normal['done']), problems)

    # Skip once the first hidden-buffer transfer is active as well as before it starts.
    active = []
    for translated, path in ((False, source_path), (True, built_path)):
        normal = natural[0][1 if translated else 0]
        press_at = normal['delays'][0][0] + 1
        pressed = run_variant(PyBoy, path, source, canonical, 0, translated,
                              press_at=press_at)
        require(bool(pressed['done']),
                'clip 0 %s active-pause A-skip did not return'
                % ('English' if translated else 'source'), problems)
        active.append((press_at, pressed))
        if translated:
            require(len(pressed['done_state']) == 1 and
                    pressed['done_state'][0][1] == 0,
                    'clip 0 active-pause A-skip did not stop native staging: %s'
                    % (pressed['done_state'],), problems)
    if all(result['done'] for _press, result in active):
        offsets = [result['done'][0] - press for press, result in active]
        require(offsets[0] == offsets[1],
                'clip 0 active-pause A-skip response differs source/English: %s'
                % offsets, problems)

    return problems, natural


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('built')
    parser.add_argument('--tsv', default=os.path.join(ROOT, 'script', 'intro.tsv'))
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)

    source = open(args.source, 'rb').read()
    built_rom = open(args.built, 'rb').read()
    font = dotfont.load_approved()
    translations = intro.load_tsv(args.tsv, source)
    canonical = intro.compile_intro(source, translations, font)

    problems, translator_n = translator_checks(source, args.tsv, font, canonical)
    problems += installation_checks(source, built_rom, canonical)
    runtime_problems, natural = runtime_checks(args.source, args.built, source,
                                                canonical, args.png_dir)
    problems += runtime_problems

    print('introspill: 12 TSV lines / 37 source runs / 2 VM programs')
    print('  translator: %d round-trip/edit/error checks' % translator_n)
    for clip in range(2):
        src, eng = natural[clip]
        values = [clear - delay[0] for delay, clear in zip(eng['delays'], eng['clears'])]
        print('  clip %d: source/English return %d/%d, %d clears, pauses %s, '
              '5 outgoing panels stable, 35 native mode-8 passes exact'
              % (clip, src['done'][0] if src['done'] else -1,
                 eng['done'][0] if eng['done'] else -1, len(eng['clears']),
                 '/'.join(str(value) for value in values)))
    print('  input: clip 0 A-skip source/English frame 1012/1013; '
          'clip 1 intentionally unskippable in both')
    print('  problems: %d' % len(problems))
    for problem in problems:
        print('    ' + problem)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
