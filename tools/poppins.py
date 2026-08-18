#!/usr/bin/env python3
"""The approved Poppins supersample/phase-search text renderer.

This is the renderer which produced the frozen ending-credit strips in
``assets/graphics/ending_credits_poppins.json``.  It lived in ``floorcardgen.py``
until the arrival cards moved to approved source rasters and dropped their font
path; it is kept here verbatim so auditions stay byte-comparable with the asset.
"""
from PIL import Image, ImageDraw, ImageFont


SCALE = 8
CAP = 12
FONT_SHA256 = '90373e7d838d32468438fc3e152dca0bdb12edcab99ea639f158790b1ba1fd05'


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


def render(font_path, text, cap=CAP):
    """Reproduce the supplied clean supersample/phase-search renderer."""
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
    mask = best[1].point(lambda value: 255 if value >= 128 else 0, mode='1')
    return _trim(mask)

