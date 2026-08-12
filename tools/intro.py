#!/usr/bin/env python3
"""Extract, validate, compile, and install the prologue/ending cinematic translation.

The cinematics are not part of ``script.json``.  The bank-31 prologue and post-game ending
share their own 77-entry alphabet and small VM.  This module is the production path for
that third encoding:

* ``--extract`` emits the canonical, translator-editable TSV metadata;
* :func:`install` consumes that TSV during the normal build;
* :func:`coverage` makes the third alphabet part of the extraction-completeness gate.

English is rendered with the approved proportional-font advances at build time.  The generated
program still feeds one tile at a time to the original cinematic typewriter, but each tile
is an 8-pixel slice of a proportional line rather than one fixed-width character.  Codes
`$45/$46` retain their native dakuten/handakuten overlay behavior and `$4C`/tile `$FC`
remains the live panel fill.  The other 73 codes are split into non-overlapping 34/39-tile
buffers for even and odd scenes.  The next pack is staged through the cinematic's own
mode-$08 VBlank records during the existing pause.
The five static tilemap records become a 100-byte hidden-buffer transfer for seven frames,
then are parked as self-copies until the terminal delay tick restores their native tilemap
destinations.  The handler moves exactly its original 100-byte budget, so the outgoing
text and frame-counted delay both stay intact.
"""
import argparse
import csv
import hashlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codec
import dotfont
import gbasm


BANKSZ = 0x4000
SOURCE_BANK = 31
TABLE_BANK = 13
TABLE_AT = 0x7FAA
TABLE_LEN = 0x4D

PROGRAMS = (
    (0x5C62, 0x5DBE,
     'dc14f134a264843b56c02dbf91d15586a041fb33a7384710e29692898c80ef90'),
    (0x5DBE, 0x5FA9,
     '830453f1699f0b8fa10dfe1617e0670c3c10f5d0d1f72c2f9925f32a6551d263'),
)

# Statically derived from the live handler/category tables at 31:$51A2/$53BC.
ARITY = {0x4D: 1, 0x4E: 2, 0x4F: 3, 0x50: 3, 0x51: 1,
         0x52: 0, 0x53: 6, 0x54: 0, 0x55: 0}
CATEGORY_EXPECT = bytes((0x86, 0x88, 0x8A, 0x8C, 0x8E, 0x90, 0x92, 0x94, 0x96))

# Bank 63 is deliberately removed from pool.TEXT_BANKS.  One dedicated bank keeps the
# cinematic program, code and raster packs independent of how much prose is translated.
FAR_BANK = 0x3F
FAR_READ = 0x03
FAR_INIT = 0x05
FAR_DELAY = 0x07
FAR_TICK = 0x09
CODE_ORG = 0x4010
PROGRAM_ORG = 0x4600
PACK_ORG = 0x4A00
PACKS_PER_CLIP = 6
PACK_SLOT_BYTES = 40 * 16
CLIP_PACK_BYTES = PACKS_PER_CLIP * PACK_SLOT_BYTES
SEQ0_ORG = 0x6800
UPLOAD_BATCHES = 7
UPLOAD_RECORDS = 5
UPLOAD_RECORD_BYTES = 20
UPLOAD_BYTES = 100

LEFT_MARGIN = 8
LINE_TEXT_PX = 160 - LEFT_MARGIN
TILES_PER_ROW = 20
# Code $00 is END and $4D-$55 are VM opcodes.  Codes $45/$46 are drawable-looking
# dakuten/handakuten overlays, not ordinary advancing glyphs; assigning raster slices to
# them moves those slices to the overlay row.  `$4C`/tile `$FC` is the live black-panel
# fill.  These pools therefore use all 73 genuinely ordinary codes and no others.
BUFFER_CODES = (
    tuple(range(0x01, 0x23)),
    tuple(range(0x23, 0x45)) + tuple(range(0x47, 0x4C)),
)
BUFFER_TILES = tuple(len(codes) for codes in BUFFER_CODES)
# (logical pack offset, VRAM destination, byte length).  The odd pool is fragmented
# around the two live overlay tiles at $8F50/$8F60.
BUFFER_SEGMENTS = (
    ((0, 0x8B10, 34 * 16),),
    ((0, 0x8D30, 34 * 16), (34 * 16, 0x8F70, 5 * 16)),
)
BUFFER_DEST = tuple(segments[0][1] for segments in BUFFER_SEGMENTS)

# Shared scratch proved free by tools/wramfree.py.  The intro runs before the dialogue or
# menu proportional renderers that use the same bytes.
S_SEQ = 0xC0CC
S_LEFT = 0xC0CE

TSV_COLUMNS = ('id', 'clip', 'scene', 'loc', 'source_ranges', 'source_hex',
               'japanese', 'english')


def _off(bank, addr):
    return bank * BANKSZ + (addr - (0x4000 if bank else 0))


class Token:
    def __init__(self, kind, start, data=b'', opcode=None, args=b''):
        self.kind = kind
        self.start = start
        self.data = bytes(data)
        self.opcode = opcode
        self.args = bytes(args)

    @property
    def end(self):
        if self.kind == 'text':
            return self.start + len(self.data)
        if self.kind == 'end':
            return self.start + 1
        return self.start + 1 + len(self.args)


def parse_program(rom, clip):
    """Parse one source program using the measured VM arities."""
    start, limit, _digest = PROGRAMS[clip]
    pos = _off(SOURCE_BANK, start)
    addr = start
    tokens = []
    while addr < limit:
        value = rom[pos]
        if value == 0:
            tokens.append(Token('end', addr, opcode=0))
            if addr + 1 != limit:
                raise SystemExit('intro: clip %d ends at 31:$%04X, expected 31:$%04X'
                                 % (clip, addr, limit - 1))
            return tokens
        if value <= 0x4C:
            at = addr
            data = bytearray()
            while addr < limit and 0 < rom[pos] <= 0x4C:
                data.append(rom[pos])
                pos += 1
                addr += 1
            tokens.append(Token('text', at, data=data))
            continue
        if value not in ARITY:
            raise SystemExit('intro: unknown opcode $%02X at 31:$%04X' % (value, addr))
        n = ARITY[value]
        if addr + 1 + n > limit:
            raise SystemExit('intro: truncated opcode $%02X at 31:$%04X' % (value, addr))
        args = rom[pos + 1:pos + 1 + n]
        tokens.append(Token('command', addr, opcode=value, args=args))
        pos += 1 + n
        addr += 1 + n
    raise SystemExit('intro: clip %d has no $00 terminator' % clip)


def _decode_text(data, table):
    import unicodedata
    out = []
    mark = ''
    for value in data:
        code = table[value]
        if code in (0x79, 0x7A):
            if mark:
                raise SystemExit('intro: consecutive combining marks in source text')
            mark = '゙' if code == 0x79 else '゚'
            continue
        char = codec.decode(bytes((code,))) if code else ' '
        out.append(unicodedata.normalize('NFC', char + mark) if mark else char)
        mark = ''
    if mark:
        raise SystemExit('intro: dangling combining mark in source text')
    return ''.join(out)


# Each event names its exact source ranges, the text runs replaced by English, and the
# screen/row slots available to its pages.  A slot is (clip, screen, row, injection run).
# Controls between runs remain byte-identical.  Event 08 deliberately exposes its real
# page transition through <page> instead of hiding it in assembly.
EVENTS = (
    dict(id='intro_01', clip=0, scene=1, loc='31:$5CEF',
         ranges=((0x5CEF, 0x5D05),),
         runs=(0x5CEF, 0x5CF6, 0x5CFC),
         pages=(((0, 0, 0, 0x5CEF),),)),
    dict(id='intro_02', clip=0, scene=2, loc='31:$5D1A',
         ranges=((0x5D1A, 0x5D47),),
         runs=(0x5D1A, 0x5D22, 0x5D38),
         pages=(((0, 1, 0, 0x5D1A), (0, 1, 1, 0x5D38)),)),
    dict(id='intro_03', clip=0, scene=3, loc='31:$5D4E',
         ranges=((0x5D4E, 0x5D63),),
         runs=(0x5D4E, 0x5D55),
         pages=(((0, 2, 0, 0x5D4E),),)),
    dict(id='intro_04', clip=0, scene=4, loc='31:$5D6A',
         ranges=((0x5D6A, 0x5D79),),
         runs=(0x5D6A,),
         pages=(((0, 3, 0, 0x5D6A),),)),
    dict(id='intro_05', clip=0, scene=5, loc='31:$5D80',
         ranges=((0x5D80, 0x5DA0),),
         runs=(0x5D80, 0x5D90),
         pages=(((0, 4, 0, 0x5D80), (0, 4, 1, 0x5D90)),)),
    dict(id='intro_06', clip=0, scene=6, loc='31:$5DA7',
         ranges=((0x5DA7, 0x5DB9),),
         runs=(0x5DA7,),
         pages=(((0, 5, 0, 0x5DA7),),)),
    dict(id='intro_07', clip=1, scene=1, loc='31:$5E04',
         ranges=((0x5E04, 0x5E27),),
         runs=(0x5E04, 0x5E0D, 0x5E1B),
         pages=(((1, 0, 0, 0x5E04),),)),
    dict(id='intro_08', clip=1, scene=2, loc='31:$5E46',
         ranges=((0x5E46, 0x5E4D), (0x5E59, 0x5E67)),
         runs=(0x5E46, 0x5E59),
         pages=(((1, 0, 1, 0x5E46),), ((1, 1, 0, 0x5E59),))),
    dict(id='intro_09', clip=1, scene=3, loc='31:$5E6E',
         ranges=((0x5E6E, 0x5E9A),),
         runs=(0x5E6E, 0x5E84, 0x5E87),
         pages=(((1, 2, 0, 0x5E6E), (1, 2, 1, 0x5E87)),)),
    dict(id='intro_10', clip=1, scene=4, loc='31:$5EA7',
         ranges=((0x5EA7, 0x5ED8),),
         runs=(0x5EA7, 0x5EB0, 0x5EC1, 0x5ED4),
         pages=(((1, 3, 0, 0x5EA7), (1, 3, 1, 0x5EC1)),)),
    dict(id='intro_11', clip=1, scene=5, loc='31:$5EE1',
         ranges=((0x5EE1, 0x5F19),),
         runs=(0x5EE1, 0x5EE9, 0x5EEC, 0x5EEF, 0x5EF3, 0x5F02, 0x5F13),
         pages=(((1, 4, 0, 0x5EE1), (1, 4, 1, 0x5F02)),)),
    dict(id='intro_12', clip=1, scene=6, loc='31:$5F24',
         ranges=((0x5F24, 0x5F34),),
         runs=(0x5F24, 0x5F2C),
         pages=(((1, 5, 0, 0x5F24),),)),
)

DECORATIVE_RUNS = {0x5E2B, 0x5E32, 0x5E35, 0x5E3F}
DECORATIVE_DOTS = {0x5E32, 0x5E35, 0x5E3F}

# Each named delay immediately precedes a clear.  The replacement delay handler recognizes
# its relocated post-delay pointer and stages the next hidden pack through mode-$08's five
# native 20-byte VBlank records before that clear.  Clear opcodes and delay arguments stay
# byte-for-byte.
TRANSITIONS = {
    0: ((0x5D17, 0x5D15, 1), (0x5D49, 0x5D47, 2),
        (0x5D65, 0x5D63, 3), (0x5D7D, 0x5D7B, 4),
        (0x5DA4, 0x5DA2, 5)),
    1: ((0x5E55, 0x5E53, 1), (0x5E6A, 0x5E68, 2),
        (0x5E9D, 0x5E9B, 3), (0x5EDC, 0x5EDA, 4),
        (0x5F20, 0x5F1E, 5)),
}
FINAL_CLEARS = {0: (), 1: (0x5F55,)}


def _source_programs(rom):
    if len(rom) < (SOURCE_BANK + 1) * BANKSZ:
        raise SystemExit('intro: ROM is too small')
    for start, end, expected in PROGRAMS:
        data = bytes(rom[_off(SOURCE_BANK, start):_off(SOURCE_BANK, end)])
        got = hashlib.sha256(data).hexdigest()
        if got != expected:
            raise SystemExit('intro: source drift in 31:$%04X-$%04X: SHA-256 %s, '
                             'expected %s' % (start, end - 1, got, expected))
    got = bytes(rom[_off(SOURCE_BANK, 0x5409):
                    _off(SOURCE_BANK, 0x5409) + 9])
    if got != CATEGORY_EXPECT:
        raise SystemExit('intro: VM category table changed: $4D-$55 is %s, expected %s'
                         % (got.hex(), CATEGORY_EXPECT.hex()))
    return tuple(parse_program(rom, clip) for clip in range(2))


def source_rows(rom):
    programs = _source_programs(rom)
    table = bytes(rom[_off(TABLE_BANK, TABLE_AT):_off(TABLE_BANK, TABLE_AT) + TABLE_LEN])
    token_by_start = {token.start: token for program in programs for token in program}
    rows = []
    claimed = set()
    for event in EVENTS:
        pieces = []
        hexes = []
        labels = []
        for start, end in event['ranges']:
            labels.append('31:$%04X-$%04X' % (start, end - 1))
            hexes.append(bytes(rom[_off(SOURCE_BANK, start):_off(SOURCE_BANK, end)]).hex())
            text = bytearray()
            for token in token_by_start.values():
                if token.kind == 'text' and start <= token.start and token.end <= end:
                    text += token.data
                    claimed.add(token.start)
            pieces.append(_decode_text(text, table).strip())
        rows.append({
            'id': event['id'], 'clip': str(event['clip']), 'scene': str(event['scene']),
            'loc': event['loc'], 'source_ranges': ','.join(labels),
            'source_hex': '/'.join(hexes), 'japanese': '<page>'.join(pieces),
        })

    translated = {run for event in EVENTS for run in event['runs']}
    if claimed != translated:
        raise SystemExit('intro: event source census differs: claimed %s, expected %s'
                         % (sorted(claimed), sorted(translated)))
    all_text = {token.start for program in programs for token in program
                if token.kind == 'text'}
    if all_text != translated | DECORATIVE_RUNS:
        raise SystemExit('intro: unclassified third-alphabet run(s): %s'
                         % sorted(all_text - translated - DECORATIVE_RUNS))
    return rows


def load_tsv(path, rom):
    canonical = {row['id']: row for row in source_rows(rom)}
    lines = [line for line in open(path, encoding='utf-8')
             if line.strip() and not line.lstrip().startswith('#')]
    if not lines:
        raise SystemExit('intro: %s has no TSV rows' % path)
    reader = csv.DictReader(io.StringIO(''.join(lines)), delimiter='\t')
    if tuple(reader.fieldnames or ()) != TSV_COLUMNS:
        raise SystemExit('intro: %s columns are %s, expected %s'
                         % (path, reader.fieldnames, TSV_COLUMNS))
    loaded = {}
    for number, row in enumerate(reader, 2):
        key = row['id'].strip()
        if not key:
            raise SystemExit('intro: %s:%d has no id' % (path, number))
        if key in loaded:
            raise SystemExit('intro: duplicate %s in %s' % (key, path))
        if key not in canonical:
            raise SystemExit('intro: unknown line %s in %s' % (key, path))
        for field in TSV_COLUMNS[1:-1]:
            if row[field] != canonical[key][field]:
                raise SystemExit('intro: source drift in %s field %s: TSV has %r, '
                                 'source extraction has %r'
                                 % (key, field, row[field], canonical[key][field]))
        english = row['english'].strip()
        if not english:
            raise SystemExit('intro: %s has no English translation' % key)
        loaded[key] = english
    missing = sorted(set(canonical) - set(loaded))
    if missing:
        raise SystemExit('intro: missing line(s) in %s: %s' % (path, ', '.join(missing)))
    return loaded


CONTROL_RE = re.compile(r'<([^<>]+)>')


def _split_controls(text, event):
    # Every angle-bracket expression is syntax here.  Treating a typo as literal text
    # would make a translator's malformed <page> silently appear on screen.
    scrubbed = CONTROL_RE.sub('', text)
    if '<' in scrubbed or '>' in scrubbed:
        raise SystemExit('intro: %s has malformed control syntax: %r' % (event['id'], text))
    for control in CONTROL_RE.findall(text):
        if control not in ('br', 'page'):
            raise SystemExit('intro: %s uses unknown control <%s>' % (event['id'], control))
    pages = text.split('<page>')
    if len(pages) != len(event['pages']):
        raise SystemExit('intro: %s needs %d page(s), English supplies %d; use <page>'
                         % (event['id'], len(event['pages']), len(pages)))
    return pages


def _wrap_segment(text, font, event):
    words = text.strip().split()
    if not words:
        raise SystemExit('intro: %s has an empty line/page' % event['id'])
    lines = []
    current = ''
    for word in words:
        if any(ch not in font.glyphs for ch in word):
            bad = ''.join(sorted(set(ch for ch in word if ch not in font.glyphs)))
            raise SystemExit('intro: %s has no approved-font glyph for %r' % (event['id'], bad))
        candidate = word if not current else current + ' ' + word
        if current and font.text_extent(candidate) > LINE_TEXT_PX:
            lines.append(current)
            current = word
        else:
            current = candidate
        if font.text_extent(current) > LINE_TEXT_PX:
            raise SystemExit('intro: %s word/line is %dpx, limit %dpx: %r'
                             % (event['id'], font.text_extent(current),
                                LINE_TEXT_PX, current))
    lines.append(current)
    return lines


def layout(translations, font):
    """Return ``{(clip, screen, row): text}`` and ``{run_addr: line key}``."""
    lines = {}
    anchors = {}
    for event in EVENTS:
        pages = _split_controls(translations[event['id']], event)
        for page_text, slots in zip(pages, event['pages']):
            explicit = page_text.split('<br>')
            wrapped = []
            for segment in explicit:
                wrapped.extend(_wrap_segment(segment, font, event))
            if len(wrapped) > len(slots):
                widths = ', '.join('%dpx %r' % (font.text_extent(line), line)
                                   for line in wrapped)
                raise SystemExit('intro: %s wraps to %d line(s), but page has %d: %s'
                                 % (event['id'], len(wrapped), len(slots), widths))
            for text, (clip, screen, row, anchor) in zip(wrapped, slots):
                key = (clip, screen, row)
                if key in lines:
                    raise SystemExit('intro: duplicate layout slot %s' % (key,))
                lines[key] = text
                anchors[anchor] = key
    expected = {(clip, screen, row)
                for event in EVENTS for page in event['pages']
                for clip, screen, row, _anchor in page}
    if set(lines) != expected:
        missing = sorted(expected - set(lines))
        raise SystemExit('intro: translation leaves layout slot(s) empty: %s' % missing)
    return lines, anchors


def _render_row(text, font):
    pixels = [0] * 8
    pen = LEFT_MARGIN
    for char in text:
        glyph = font.glyphs[char]
        for y, row in enumerate(glyph):
            for x in range(8):
                if row & (0x80 >> x):
                    at = pen + x
                    if at >= 160:
                        raise SystemExit('intro: rendered line crosses 160px: %r' % text)
                    pixels[y] |= 1 << (159 - at)
        pen += font.advance(char)
    extent = LEFT_MARGIN + font.text_extent(text)
    count = max(1, (extent + 7) // 8)
    if count > TILES_PER_ROW:
        raise SystemExit('intro: rendered line needs %d tiles: %r' % (count, text))
    tiles = []
    for tile in range(TILES_PER_ROW):
        raw = bytearray()
        for y in range(8):
            ink = (pixels[y] >> (152 - tile * 8)) & 0xFF
            plane = (~ink) & 0xFF       # native cinematic font is white $FF, black zero
            raw += bytes((plane, plane))
        tiles.append(bytes(raw))
    return b''.join(tiles), count


def buffer_spec(screen):
    """Return ``(codes, tile capacity, VRAM segments, logical byte length)``."""
    parity = screen & 1
    codes = BUFFER_CODES[parity]
    return (codes, len(codes), BUFFER_SEGMENTS[parity], len(codes) * 16)


def vram_pack(memory, screen):
    """Read one logical raster pack from its possibly fragmented VRAM buffer."""
    return b''.join(bytes(memory[dest:dest + size])
                    for _offset, dest, size in BUFFER_SEGMENTS[screen & 1])


def is_buffer_vram(address):
    return any(dest <= address < dest + size
               for segments in BUFFER_SEGMENTS for _offset, dest, size in segments)


def build_packs(lines, anchors, font):
    packs = []
    row_codes = {}
    period = _period_tile(font)
    period_code = None
    for clip in range(2):
        for screen in range(PACKS_PER_CLIP):
            codes, capacity, _segments, size = buffer_spec(screen)
            pack = bytearray(b'\xFF' * size)
            used = 0
            for row in range(2):
                key = (clip, screen, row)
                text = lines.get(key, '')
                if not text:
                    continue
                raster, count = _render_row(text, font)
                if used + count > capacity:
                    raise SystemExit(
                        'intro: clip %d screen %d needs %d double-buffer tiles; '
                        'this %s-screen buffer holds %d'
                        % (clip, screen + 1, used + count,
                           'odd' if screen & 1 else 'even', capacity))
                at = used * 16
                pack[at:at + count * 16] = raster[:count * 16]
                row_codes[key] = bytes(codes[used:used + count])
                used += count

            # Clip 1 reveals three dramatic dots between its first two lines.  Give them
            # one otherwise-unused tile in that same even-scene buffer.
            if clip == 1 and screen == 0:
                if used >= capacity:
                    raise SystemExit('intro: clip 1 screen 1 leaves no tile for its dots')
                period_code = codes[used]
                at = used * 16
                pack[at:at + 16] = period
            packs.append(bytes(pack))
    replacements = {run: b'' for event in EVENTS for run in event['runs']}
    # Program 1 reveals three dramatic dots one at a time before "Look over there!".
    # Retaining the three runs preserves their measured stagger.
    if period_code is None:
        raise SystemExit('intro: failed to allocate the decorative period tile')
    replacements.update({run: bytes((period_code,)) for run in DECORATIVE_DOTS})
    for anchor, key in anchors.items():
        replacements[anchor] = row_codes[key]
    return packs, replacements, period, period_code, row_codes


def _period_tile(font):
    raw = bytearray()
    for row in font.glyphs['.']:
        plane = (~row) & 0xFF
        raw += bytes((plane, plane))
    if len(raw) != 16:
        raise SystemExit('intro: approved-font period is not an 8x8 glyph')
    return bytes(raw)


def _compile_program(tokens, clip, replacements):
    expected_clears = {clear for clear, _delay, _pack in TRANSITIONS[clip]} | \
                      set(FINAL_CLEARS[clip])
    seen_clears = set()
    out = bytearray()
    after = {}
    for token in tokens:
        if token.kind == 'text':
            out += replacements.get(token.start, token.data)
        elif token.kind == 'end':
            out.append(0)
        else:
            if token.opcode == 0x52:
                if token.start not in expected_clears:
                    raise SystemExit('intro: unplanned clear at 31:$%04X' % token.start)
                seen_clears.add(token.start)
            out.append(token.opcode)
            out += token.args
        after[token.start] = len(out)
    if seen_clears != expected_clears:
        raise SystemExit('intro: missing clear(s) in clip %d: %s'
                         % (clip, sorted(expected_clears - seen_clears)))
    return bytes(out), after


def _sequence(pack_addresses, clip):
    out = bytearray()
    for _clear, _delay, next_pack in TRANSITIONS[clip]:
        source = pack_addresses[clip * PACKS_PER_CLIP + next_pack]
        records = []
        for pack_offset, target, size in BUFFER_SEGMENTS[next_pack & 1]:
            offsets = list(range(0, size - UPLOAD_RECORD_BYTES + 1,
                                 UPLOAD_RECORD_BYTES))
            if offsets[-1] + UPLOAD_RECORD_BYTES < size:
                offsets.append(size - UPLOAD_RECORD_BYTES)
            for offset in offsets:
                records.append((target + offset, source + pack_offset + offset))
        total = UPLOAD_BATCHES * UPLOAD_RECORDS
        if len(records) > total:
            raise SystemExit('intro: screen %d needs %d native upload records; limit %d'
                             % (next_pack + 1, len(records), total))
        records += [records[-1]] * (total - len(records))
        for dest, src in records:
            out += bytes((dest & 0xFF, dest >> 8, src & 0xFF, src >> 8))
    return bytes(out)


def _code_src(program0, program1, pack0, pack1, arm_table):
    return f"""
read:
        push af
        push bc
        push hl
        ld hl,$002E
        add hl,de
        ld a,[hl+]
        ld c,a
        ld b,[hl]
        ld a,b
        or c
        jr nz,rhave
        ld hl,$0010
        add hl,de
        ld a,[hl]
        and $01
        jr nz,rclip1
        ld bc,${program0:04X}
        jr rhave
rclip1:
        ld bc,${program1:04X}
rhave:
        ld a,[bc]
        push af
        inc bc
        ld hl,$002E
        add hl,de
        ld a,c
        ld [hl+],a
        ld [hl],b
        pop af
        ld hl,$0032
        add hl,de
        ld [hl],a
        pop hl
        pop bc
        pop af
        ret

init:
        push af
        push bc
        push de
        push hl
        ld hl,$0010
        add hl,de
        ld a,[hl]
        and $01
        jr nz,iclip1
        ld hl,${pack0:04X}
        jr iload
iclip1:
        ld hl,${pack1:04X}
iload:
        ld de,${BUFFER_DEST[0]:04X}
        ld bc,${BUFFER_TILES[0] * 16:04X}
icopy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec bc
        ld a,b
        or c
        jr nz,icopy
        pop hl
        pop de
        pop bc
        pop af
        ret

delay:
        push af
        push bc
        push de
        push hl
        call read
        ld hl,$0032
        add hl,de
        ld a,[hl]
        ld hl,$0031
        add hl,de
        ld [hl],a
        ld hl,$002E
        add hl,de
        ld a,[hl+]
        ld c,a
        ld b,[hl]
        ld de,${arm_table:04X}
dsearch:
        ld a,[de]
        inc de
        ld l,a
        ld a,[de]
        inc de
        ld h,a
        or l
        jr z,dnone
        ld a,l
        cp c
        jr nz,dskip
        ld a,h
        cp b
        jr z,dfound
dskip:
        inc de
        inc de
        jr dsearch
dfound:
        ld a,[de]
        inc de
        ld [${S_SEQ:04X}],a
        ld a,[de]
        ld [${S_SEQ + 1:04X}],a
        ld a,${UPLOAD_BATCHES:02X}
        ld [${S_LEFT:04X}],a
dnone:
        pop hl
        pop de
        pop bc
        pop af
        ret

tick:
        push af
        push bc
        push de
        push hl
        call service
        pop hl
        pop de
        pop bc
        pop af
        push hl
        ld hl,$0031
        add hl,de
        dec [hl]
        jr nz,tnotdone
        call unpark
        scf
        jr tdone
tnotdone:
        scf
        ccf
tdone:
        pop hl
        ret

service:
        ld a,[${S_LEFT:04X}]
        or a
        ret z
        bit 7,a
        jr nz,spark
        ld a,[${S_SEQ:04X}]
        ld l,a
        ld a,[${S_SEQ + 1:04X}]
        ld h,a
        call stage100
        ld a,l
        ld [${S_SEQ:04X}],a
        ld a,h
        ld [${S_SEQ + 1:04X}],a
        ld hl,${S_LEFT:04X}
        dec [hl]
        ret nz
        ld [hl],$80
        ret
spark:
        call park
        ret

stage100:
        di
        ld a,[hl+]
        ld [$C006],a
        ld a,[hl+]
        ld [$C007],a
        ld a,[hl+]
        ld e,a
        ld a,[hl+]
        ld d,a
        push hl
        ld hl,$C008
        ld b,$14
st0:
        ld a,[de]
        inc de
        ld [hl+],a
        dec b
        jr nz,st0
        pop hl

        ld a,[hl+]
        ld [$C01C],a
        ld a,[hl+]
        ld [$C01D],a
        ld a,[hl+]
        ld e,a
        ld a,[hl+]
        ld d,a
        push hl
        ld hl,$C01E
        ld b,$14
st1:
        ld a,[de]
        inc de
        ld [hl+],a
        dec b
        jr nz,st1
        pop hl

        ld a,[hl+]
        ld [$C032],a
        ld a,[hl+]
        ld [$C033],a
        ld a,[hl+]
        ld e,a
        ld a,[hl+]
        ld d,a
        push hl
        ld hl,$C034
        ld b,$14
st2:
        ld a,[de]
        inc de
        ld [hl+],a
        dec b
        jr nz,st2
        pop hl

        ld a,[hl+]
        ld [$C048],a
        ld a,[hl+]
        ld [$C049],a
        ld a,[hl+]
        ld e,a
        ld a,[hl+]
        ld d,a
        push hl
        ld hl,$C04A
        ld b,$14
st3:
        ld a,[de]
        inc de
        ld [hl+],a
        dec b
        jr nz,st3
        pop hl

        ld a,[hl+]
        ld [$C05E],a
        ld a,[hl+]
        ld [$C05F],a
        ld a,[hl+]
        ld e,a
        ld a,[hl+]
        ld d,a
        push hl
        ld hl,$C060
        ld b,$14
st4:
        ld a,[de]
        inc de
        ld [hl+],a
        dec b
        jr nz,st4
        pop hl
        ei
        ret

park:
        di
        ld a,$08
        ld [$C006],a
        ld a,$C0
        ld [$C007],a
        ld a,$1E
        ld [$C01C],a
        ld a,$C0
        ld [$C01D],a
        ld a,$34
        ld [$C032],a
        ld a,$C0
        ld [$C033],a
        ld a,$4A
        ld [$C048],a
        ld a,$C0
        ld [$C049],a
        ld a,$60
        ld [$C05E],a
        ld a,$C0
        ld [$C05F],a
        ei
        ret

unpark:
        di
        ld a,$A0
        ld [$C006],a
        ld a,$99
        ld [$C007],a
        ld a,$C0
        ld [$C01C],a
        ld a,$99
        ld [$C01D],a
        ld a,$E0
        ld [$C032],a
        ld a,$99
        ld [$C033],a
        xor a
        ld [$C048],a
        ld a,$9A
        ld [$C049],a
        ld a,$60
        ld [$C05E],a
        ld a,$C0
        ld [$C05F],a
        xor a
        ld [${S_LEFT:04X}],a
        ei
        ret
"""


def compile_intro(source_rom, translations, font):
    programs = _source_programs(source_rom)
    lines, anchors = layout(translations, font)
    packs, replacements, period, period_code, row_codes = \
        build_packs(lines, anchors, font)
    compiled_with_maps = tuple(_compile_program(programs[clip], clip, replacements)
                               for clip in range(2))
    compiled = tuple(item[0] for item in compiled_with_maps)
    after = tuple(item[1] for item in compiled_with_maps)
    program_addresses = (PROGRAM_ORG, PROGRAM_ORG + len(compiled[0]))
    if program_addresses[1] + len(compiled[1]) > PACK_ORG:
        raise SystemExit('intro: relocated programs overflow $%04X-$%04X'
                         % (PROGRAM_ORG, PACK_ORG - 1))
    pack_addresses = [PACK_ORG + i * PACK_SLOT_BYTES for i in range(len(packs))]
    seq0 = _sequence(pack_addresses, 0)
    seq1_addr = SEQ0_ORG + len(seq0)
    seq1 = _sequence(pack_addresses, 1)
    arm_addr = seq1_addr + len(seq1)
    arm = bytearray()
    for clip in range(2):
        seq_base = SEQ0_ORG if clip == 0 else seq1_addr
        for index, (_clear, delay, _pack) in enumerate(TRANSITIONS[clip]):
            post_delay = program_addresses[clip] + after[clip][delay]
            sequence = seq_base + index * UPLOAD_BATCHES * UPLOAD_RECORDS * 4
            arm += bytes((post_delay & 0xFF, post_delay >> 8,
                          sequence & 0xFF, sequence >> 8))
    arm += b'\x00\x00\x00\x00'
    end_addr = arm_addr + len(arm)
    if end_addr > 0x8000:
        raise SystemExit('intro: sequence tables overflow bank %d' % FAR_BANK)
    code, labels = gbasm.assemble(
        _code_src(program_addresses[0], program_addresses[1],
                  pack_addresses[0], pack_addresses[PACKS_PER_CLIP],
                  arm_addr), CODE_ORG)
    if CODE_ORG + len(code) > PROGRAM_ORG:
        raise SystemExit('intro: %d-byte runtime overruns program arena' % len(code))
    return {
        'code': code, 'labels': labels, 'programs': compiled,
        'program_addresses': program_addresses, 'packs': packs,
        'pack_addresses': pack_addresses, 'seq0': seq0, 'seq1': seq1,
        'seq1_addr': seq1_addr, 'arm': bytes(arm), 'arm_addr': arm_addr,
        'period': period, 'period_code': period_code, 'end_addr': end_addr,
        'after': after, 'lines': lines, 'row_codes': row_codes,
    }


def _expect(buf, bank, addr, want, what):
    at = _off(bank, addr)
    got = bytes(buf[at:at + len(want)])
    if got != want:
        raise SystemExit('intro: %s changed at %d:$%04X: got %s, expected %s'
                         % (what, bank, addr, got.hex(), want.hex()))


def install(buf, tsv_path, font=None, source_rom=None, notes=None):
    """Install translated programs and proportional cinematic packs in a 1 MiB build."""
    font = font or dotfont.load_approved()
    source_rom = bytes(source_rom if source_rom is not None else buf)
    translations = load_tsv(tsv_path, source_rom)
    built = compile_intro(source_rom, translations, font)

    if len(buf) < 0x100000:
        raise SystemExit('intro: requires the 1 MiB expanded ROM')
    bank = _off(FAR_BANK, 0x4000)
    if any(value != 0xFF for value in buf[bank:bank + BANKSZ]):
        bad = next(i for i, value in enumerate(buf[bank:bank + BANKSZ]) if value != 0xFF)
        raise SystemExit('intro: reserved bank %d is not free at $%04X'
                         % (FAR_BANK, 0x4000 + bad))
    buf[bank] = FAR_BANK
    buf[bank + 1] = 0
    for index, label in ((FAR_READ, 'read'), (FAR_INIT, 'init'),
                         (FAR_DELAY, 'delay'), (FAR_TICK, 'tick')):
        at = bank + index - 1
        address = built['labels'][label]
        buf[at:at + 2] = bytes((address & 0xFF, address >> 8))
    at = bank + CODE_ORG - 0x4000
    buf[at:at + len(built['code'])] = built['code']
    for address, program in zip(built['program_addresses'], built['programs']):
        at = bank + address - 0x4000
        buf[at:at + len(program)] = program
    for address, pack in zip(built['pack_addresses'], built['packs']):
        at = bank + address - 0x4000
        buf[at:at + len(pack)] = pack
    for address, data in ((SEQ0_ORG, built['seq0']),
                          (built['seq1_addr'], built['seq1']),
                          (built['arm_addr'], built['arm'])):
        at = bank + address - 0x4000
        buf[at:at + len(data)] = data

    # The old reader's 47 bytes become a far-read stub plus local init/cleanup wrappers.
    # The wrappers call their same-bank originals before/after crossing to bank 63.
    old_reader = bytes(source_rom[_off(31, 0x51C9):_off(31, 0x51F8)])
    _expect(buf, 31, 0x51C9, old_reader, 'cinematic byte reader')
    reader_stub = bytes((0xD7, FAR_READ, FAR_BANK, 0xC9))
    wrapper_at = 0x51D0
    wrapper = bytes((0xCD, 0xB9, 0x4F, 0xD7, FAR_INIT, FAR_BANK, 0xC9))
    clean_wrapper_at = 0x51D8
    clean_wrapper = bytes((0xCD, 0xF9, 0x4B, 0xAF,
                           0xEA, S_LEFT & 0xFF, S_LEFT >> 8, 0xC9))
    patch = bytearray(b'\xFF' * len(old_reader))
    patch[:len(reader_stub)] = reader_stub
    offset = wrapper_at - 0x51C9
    patch[offset:offset + len(wrapper)] = wrapper
    offset = clean_wrapper_at - 0x51C9
    patch[offset:offset + len(clean_wrapper)] = clean_wrapper
    buf[_off(31, 0x51C9):_off(31, 0x51F8)] = patch

    _expect(buf, 31, 0x4FAF, bytes.fromhex('cd b9 4f'), 'post-font graphics call')
    buf[_off(31, 0x4FAF):_off(31, 0x4FB2)] = \
        bytes((0xCD, wrapper_at & 0xFF, wrapper_at >> 8))

    old_delay = bytes(source_rom[_off(31, 0x5254):_off(31, 0x526A)])
    _expect(buf, 31, 0x5254, old_delay, 'cinematic delay handler')
    delay_stub = bytes((0xD7, FAR_DELAY, FAR_BANK, 0xC9))
    buf[_off(31, 0x5254):_off(31, 0x526A)] = \
        delay_stub + b'\xFF' * (len(old_delay) - len(delay_stub))

    old_tick = bytes(source_rom[_off(31, 0x51BA):_off(31, 0x51C9)])
    _expect(buf, 31, 0x51BA, old_tick, 'cinematic delay countdown')
    tick_stub = bytes((0xD7, FAR_TICK, FAR_BANK, 0xC9))
    buf[_off(31, 0x51BA):_off(31, 0x51C9)] = \
        tick_stub + b'\xFF' * (len(old_tick) - len(tick_stub))

    _expect(buf, 31, 0x4D46, bytes.fromhex('cd f9 4b'), 'cinematic cleanup call')
    buf[_off(31, 0x4D46):_off(31, 0x4D49)] = \
        bytes((0xCD, clean_wrapper_at & 0xFF, clean_wrapper_at >> 8))

    out = [
        'intro: 12 TSV lines compiled into two relocated programs (%d/%d bytes)' %
        (len(built['programs'][0]), len(built['programs'][1])),
        'intro: 12 %s screen packs in non-overlapping 34/39-tile buffers; '
        'hidden-buffer uploads reuse seven native mode-8 VBlank passes per transition'
        % font.name,
        'intro: runtime/program/packs at bank %d $%04X-$%04X' %
        (FAR_BANK, CODE_ORG, built['end_addr'] - 1),
    ]
    if notes is not None:
        notes.extend(out)
    return built


def coverage(rom, tsv_path):
    rows = source_rows(rom)
    translations = load_tsv(tsv_path, rom)
    text_runs = sum(1 for clip in range(2) for token in parse_program(rom, clip)
                    if token.kind == 'text')
    return {'programs': 2, 'bytes': sum(end - start for start, end, _ in PROGRAMS),
            'runs': text_runs, 'lines': len(rows), 'translated': len(translations),
            'decorative': len(DECORATIVE_RUNS)}


def extract_tsv(rom, existing=None):
    old = {}
    if existing and os.path.exists(existing):
        lines = [line for line in open(existing, encoding='utf-8')
                 if line.strip() and not line.lstrip().startswith('#')]
        if lines:
            for row in csv.DictReader(io.StringIO(''.join(lines)), delimiter='\t'):
                old[row.get('id', '')] = row.get('english', '')
    out = io.StringIO()
    out.write('# Opening cinematic. Edit only the english column; <br> forces a line '
              'break and <page> is a measured screen transition.\n')
    writer = csv.DictWriter(out, fieldnames=TSV_COLUMNS, delimiter='\t',
                            lineterminator='\n')
    writer.writeheader()
    for row in source_rows(rom):
        row = dict(row)
        row['english'] = old.get(row['id'], '')
        writer.writerow(row)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--extract', action='store_true')
    parser.add_argument('--check')
    parser.add_argument('--existing')
    parser.add_argument('--output')
    args = parser.parse_args()
    rom = open(args.rom, 'rb').read()
    if args.extract:
        rendered = extract_tsv(rom, args.existing)
        if args.output:
            with open(args.output, 'w', encoding='utf-8', newline='') as out:
                out.write(rendered)
            print('intro: wrote %s' % args.output)
        else:
            sys.stdout.write(rendered)
        return 0
    if args.check:
        report = coverage(rom, args.check)
        print('intro: {programs} programs, {bytes} bytes, {runs} text runs, '
              '{lines} canonical lines, {decorative} decorative runs; ALL ACCOUNTED FOR'
              .format(**report))
        return 0
    parser.error('choose --extract or --check TSV')


if __name__ == '__main__':
    raise SystemExit(main())
