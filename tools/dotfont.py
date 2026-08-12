#!/usr/bin/env python3
"""Load the approved proportional font from its source and specification.

This is the single machine-readable path from a reviewed source asset to ROM glyph
bytes. It supports both the historical Dot Gothic GB Studio sheet and the project's
reviewable JSON row format. In either case it verifies the source hash before loading
the approved glyphs and advances.

Loading is deliberately separate from installing.  Width audits can use the exact same
glyphs and advances as a later ROM patch without changing one byte of a build.
"""
import hashlib
import json
import os

from PIL import Image

from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SPEC = os.path.join(ROOT, 'assets', 'fonts', 'thin_pixel_7_compact.json')

BACKGROUND = (224, 248, 207)
INK = (7, 24, 33)
TRIM = (255, 0, 255)
SHEET_SIZE = (128, 112)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as src:
        for block in iter(lambda: src.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def _source_path(spec, spec_path):
    declared = spec['source']['file']
    if os.path.isabs(declared):
        return declared
    # Project specs use project-relative paths.  Keeping this resolution here makes the
    # provenance field readable and prevents each caller from interpreting it differently.
    return os.path.join(ROOT, declared)


def extract_gb_studio(sheet, ch):
    """Return ``(8 one-bit rows, advance)`` for one default-ASCII sheet cell."""
    index = ord(ch) - 32
    if not 0 <= index < 224:
        raise SystemExit('Dot Gothic sheet cannot map %r through default ASCII' % ch)
    left = index % 16 * 8
    top = index // 16 * 8
    cell = sheet.crop((left, top, left + 8, top + 8)).convert('RGB')
    colors = set(cell.getdata())
    unsupported = colors - {BACKGROUND, INK, TRIM}
    if unsupported:
        raise SystemExit('Dot Gothic glyph %r uses unsupported shade(s): %s'
                         % (ch, sorted(unsupported)))

    trim_columns = [x for x in range(8)
                    if any(cell.getpixel((x, y)) == TRIM for y in range(8))]
    advance = min(trim_columns) if trim_columns else 8
    if any(cell.getpixel((x, y)) != TRIM
           for x in range(advance, 8) for y in range(8)):
        raise SystemExit('Dot Gothic glyph %r has irregular magenta width metadata' % ch)

    rows = bytearray(8)
    for y in range(8):
        for x in range(advance):
            if cell.getpixel((x, y)) == INK:
                rows[y] |= 0x80 >> x
    return bytes(rows), advance


def ink_span(glyph):
    """Return the inclusive ink-column span, or ``None`` for a blank glyph."""
    columns = [x for x in range(8)
               if any(row & (0x80 >> x) for row in glyph)]
    return (min(columns), max(columns)) if columns else None


def _pixel(glyph, x, y):
    return 1 if glyph[y] & (0x80 >> x) else 0


def _set_pixel(glyph, x, y, value):
    rows = bytearray(glyph)
    mask = 0x80 >> x
    rows[y] = (rows[y] | mask) if value else (rows[y] & ~mask)
    return bytes(rows)


def extract_rows(source, expected_format):
    """Return glyph bytes from the project-original, human-editable JSON format."""
    with open(source, encoding='utf-8') as src:
        data = json.load(src)
    if data.get('format') != expected_format:
        raise SystemExit('Font row source format %r does not match approved %r' %
                         (data.get('format'), expected_format))
    declared = data.get('glyphs', {})
    missing = sorted(set(EN_CODES) - set(declared))
    extra = sorted(set(declared) - set(EN_CODES))
    if missing or extra:
        raise SystemExit('Font row source glyph set mismatch; missing=%r extra=%r' %
                         (missing, extra))

    glyphs = {}
    for ch, rows in declared.items():
        if (not isinstance(rows, list) or len(rows) != 8 or
                any(not isinstance(row, str) or len(row) != 8 or
                    set(row) - {'.', '#'} for row in rows)):
            raise SystemExit('Font glyph %r must contain eight 8-column .# rows' % ch)
        glyphs[ch] = bytes(sum((0x80 >> x) for x, pixel in enumerate(row)
                               if pixel == '#') for row in rows)
    return glyphs


class ApprovedFont:
    def __init__(self, spec, spec_path, source_path, glyphs, advances):
        self.spec = spec
        self.spec_path = spec_path
        self.source_path = source_path
        self.glyphs = glyphs
        self.advances = advances

    @property
    def name(self):
        return self.spec['name']

    def advance(self, ch):
        return self.advances[ch]

    def advance_code(self, code, unknown=8):
        ch = CODE_TO_EN.get(code)
        return self.advances[ch] if ch is not None else unknown

    def text_width(self, text):
        """Pen movement in pixels, including the final glyph's declared spacing."""
        return sum(self.advances[ch] for ch in text)

    def text_extent(self, text):
        """Painted pixel extent, excluding blank spacing after the final glyph."""
        if not text:
            return 0
        tail = ink_span(self.glyphs[text[-1]])
        tail_width = tail[1] + 1 if tail else self.advances[text[-1]]
        return self.text_width(text[:-1]) + tail_width

    def patch(self, rom):
        """Write the approved English glyphs into the ROM's existing font page."""
        out = bytearray(rom)
        for ch, code in EN_CODES.items():
            off = FONT_BASE + code * GLYPH_BYTES
            out[off:off + GLYPH_BYTES] = self.glyphs[ch]
        return bytes(out)


CODE_TO_EN = {code: ch for ch, code in EN_CODES.items()}


def load_approved(spec_path=DEFAULT_SPEC, source_path=None):
    """Verify and load the approved source, edits, advances, and ROM glyph bytes."""
    spec_path = os.path.abspath(spec_path)
    with open(spec_path, encoding='utf-8') as src:
        spec = json.load(src)
    source_path = os.path.abspath(source_path or _source_path(spec, spec_path))
    digest = _sha256(source_path)
    expected = spec['source']['sha256']
    if digest != expected:
        raise SystemExit('Font source SHA-256 %s, approved spec requires %s'
                         % (digest, expected))

    source_format = spec['source'].get('format', 'gb-studio-variable-png')
    if source_format == 'shiren-gb-8x8-rows-v1':
        glyphs = extract_rows(source_path, source_format)
        advances = {ch: int(width) for ch, width in spec['advances'].items()}
        missing = sorted(set(EN_CODES) - set(advances))
        extra = sorted(set(advances) - set(EN_CODES))
        if missing or extra:
            raise SystemExit('Font advance set mismatch; missing=%r extra=%r' %
                             (missing, extra))
    elif source_format == 'gb-studio-variable-png':
        sheet = Image.open(source_path)
        if sheet.size != SHEET_SIZE:
            raise SystemExit('GB Studio font sheet must be %s, got %s'
                             % (SHEET_SIZE, sheet.size))
        extracted = {ch: extract_gb_studio(sheet, ch) for ch in EN_CODES}
        glyphs = {ch: pair[0] for ch, pair in extracted.items()}
        advances = {ch: pair[1] for ch, pair in extracted.items()}

        for edit in spec.get('pixel_edits', []):
            ch, x, y = edit['glyph'], edit['x'], edit['y']
            before = _pixel(glyphs[ch], x, y)
            if before != edit['from']:
                raise SystemExit('Font spec expected %r pixel (%d,%d)=%d, found %d'
                                 % (ch, x, y, edit['from'], before))
            glyphs[ch] = _set_pixel(glyphs[ch], x, y, edit['to'])
        advances.update({ch: int(width)
                         for ch, width in spec.get('advance_overrides', {}).items()})
    else:
        raise SystemExit('Unsupported approved font source format %r' % source_format)

    for ch in EN_CODES:
        width = advances[ch]
        if not 1 <= width <= 8:
            raise SystemExit('%s %r has invalid %dpx advance' %
                             (spec['name'], ch, width))
        span = ink_span(glyphs[ch])
        if span and span[1] >= width:
            raise SystemExit('%s %r inks through column %d but advances %dpx'
                             % (spec['name'], ch, span[1], width))

    # A font may declare a strict per-glyph width reference. The production Thin Pixel-7
    # adaptation instead carries a comparison_reference and is accepted by the complete
    # corpus/geometry audit: a full-bar I cannot satisfy Moonlit Sans's 2px I advance even
    # though every measured runtime consumer fits.
    reference_path = spec.get('width_reference')
    if reference_path:
        reference = load_approved(os.path.join(ROOT, reference_path))
        for ch in EN_CODES:
            if advances[ch] > reference.advances[ch]:
                raise SystemExit('%s %r advances %dpx; width reference permits %dpx' %
                                 (spec['name'], ch, advances[ch],
                                  reference.advances[ch]))
            span = ink_span(glyphs[ch])
            reference_span = ink_span(reference.glyphs[ch])
            extent = span[1] + 1 if span else advances[ch]
            reference_extent = (reference_span[1] + 1 if reference_span
                                else reference.advances[ch])
            if extent > reference_extent:
                raise SystemExit('%s %r paints %dpx; width reference permits %dpx' %
                                 (spec['name'], ch, extent, reference_extent))

    return ApprovedFont(spec, spec_path, source_path, glyphs, advances)


if __name__ == '__main__':
    font = load_approved()
    print('%s: %d glyphs; source %s; SHA-256 verified'
          % (font.name, len(font.glyphs), os.path.relpath(font.source_path, ROOT)))
