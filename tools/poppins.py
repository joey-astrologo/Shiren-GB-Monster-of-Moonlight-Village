#!/usr/bin/env python3
"""The supersample/phase-search text renderer the credit cards are drawn with.

This is the renderer which produced the frozen ending-credit strips in
``assets/graphics/ending_credits_inter.json``.  It lived in ``floorcardgen.py``
until the arrival cards moved to approved source rasters and dropped their font
path; the algorithm is kept verbatim so auditions stay byte-comparable with the asset.

``FONT_SHA256`` is whichever font is currently approved -- Inter SemiBold since the
credits moved to the anti-aliased style; the module keeps its original name because the
renderer, not the font, is what lives here.
"""
from PIL import Image, ImageDraw, ImageFont


SCALE = 8
CAP = 12
FONT_SHA256 = '78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3'

# Coverage cuts for the anti-aliased style, measured against the native roll: the
# Japanese cards spend roughly 0.85 dim pixels per bright one (see endingcreditstyle).
AA_LOW = 64
AA_HIGH = 192


def _font_size(font_path, cap=CAP):
    best = None
    distance = 1 << 30
    for size in range(6, 300):
        font = ImageFont.truetype(font_path, size)
        box = font.getbbox('H')
        error = abs((box[3] - box[1]) - cap * SCALE)
        if error < distance:
            best, distance = size, error
    return best


def _trim(mask):
    pixels = mask.load()
    xs = []
    ys = []
    for y in range(mask.height):
        for x in range(mask.width):
            if pixels[x, y]:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise ValueError('cannot trim an empty mask')
    return mask.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))


def coverage(font_path, text, cap=CAP):
    """Return the untrimmed grayscale coverage the phase search settled on.

    ``render`` throws this away at a 50% threshold.  The native Japanese credits instead
    spend their two ink colors on coverage, so an anti-aliased style needs the grays.
    """
    font = ImageFont.truetype(font_path, _font_size(font_path, cap))
    best = None
    for dy in range(SCALE):
        for dx in range(SCALE):
            high = Image.new('L', (4000, 700), 0)
            draw = ImageDraw.Draw(high)
            x = float(200 + dx)
            for ch in text:
                draw.text((x, 200 + dy), ch, 255, font=font)
                x += font.getlength(ch)
            box = high.getbbox()
            high = high.crop((box[0] - 4 * SCALE, box[1] - 4 * SCALE,
                              box[2] + 4 * SCALE, box[3] + 4 * SCALE))
            box = high.getbbox()
            left = (box[0] // SCALE) * SCALE
            top = (box[1] // SCALE) * SCALE
            right = ((box[2] + SCALE - 1) // SCALE) * SCALE
            bottom = ((box[3] + SCALE - 1) // SCALE) * SCALE
            high = high.crop((left, top, right, bottom))
            low = high.resize((high.width // SCALE, high.height // SCALE),
                              Image.Resampling.BOX)
            score = sum(min(value, 255 - value) for value in low.getdata())
            if best is None or score < best[0]:
                best = score, low
    return best[1]


def render(font_path, text, cap=CAP):
    """Reproduce the supplied clean supersample/phase-search renderer."""
    mask = coverage(font_path, text, cap).point(
        lambda value: 255 if value >= 128 else 0, mode='1')
    return _trim(mask)


def render_levels(font_path, text, cap=CAP, low=AA_LOW, high=AA_HIGH):
    """Return ``(partial, full)`` 1-bit masks -- the two ink levels of an AA glyph.

    ``low`` is where a pixel starts taking the dimmer color, ``high`` where it takes the
    full one, both in 0-255 coverage.  Both masks share one crop box so they paste at the
    same origin.
    """
    grey = coverage(font_path, text, cap)
    box = grey.point(lambda value: 255 if value >= low else 0, mode='1').getbbox()
    if box is None:
        raise ValueError('cannot trim an empty mask')
    grey = grey.crop(box)
    return (grey.point(lambda value: 255 if low <= value < high else 0, mode='1'),
            grey.point(lambda value: 255 if value >= high else 0, mode='1'))

