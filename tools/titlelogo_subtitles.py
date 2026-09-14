"""Embedded approved scroll subtitles for the illustrated English title.

Joey's approved overlays are 160x144 PNGs that are transparent except for one opaque
73x27 rectangle at (24,86), the interior of the title scroll. Each uses exactly the
three Super Game Boy logo/scroll palette colours: yellow ``(214,206,115)``, orange
``(214,132,49)`` and red ``(214,49,16)``, which are Game Boy shades 0, 1 and 2 under
that palette. ``PACK`` stores the three rectangles as one shade byte per pixel, in
``SUBTITLES`` order, so the build does not depend on files outside the repository.
"""
import base64
import hashlib
import zlib


BOX = (24, 86, 73, 27)                                   # x, y, width, height
SUBTITLES = (
    ('monsters', 'ShirenGBTitleScreenMonsters.png', 'd4d29dbc13fc63da86d21c509c7575ddecde30214aabdbd9ff962b510f51e010'),
    ('escape', 'ShirenGBTitleScreenEscape.png', '32a69de6bd2bd8952bda92ab5664bbb8a6ba4f029f0c60ebc359110e14f5f976'),
    ('lover', 'ShirenGBTitleScreenLover.png', 'f15fd7086a40ec55df237b8386a966d086aa707f1d1a4a8d3a2fad09b38ec608'),
)
PACK_SHA256 = '89a057ff7c9340256b8156f963bd2e81fa70a3bbbf0fba176b9080e26225eb76'

PACK = zlib.decompress(base64.b64decode(
    'eNrtWImWwyAIdOb/P7obBMQrurvdo6+2LyZVHAFhiE3pX34IaZ8EhCEQ7mc2k0hr+jVWOKyB8NHHawBXQ1Hx'
    'aqlrIOXHPOKqsDONcslNVKPbC5lzjeVRx7l+sjGD/pVnZCDagyiDrJpCZcnOrVmfCsjcT9Mf1S1L9qbZyoKg'
    'QOoe9ZXOdVN8tAWCzxntDdMrfrgIOzSi0F3eBeIgtFn2i5M8GwExAtG2HiXi2hmWGbcaeYu5RoxppPkFkb2S'
    'Tn9p9sHijRoTZJkPi+tkDWLOELDES0UsQ2lH3R2Ams4qTXwwyXK6Fi2vJ0Cete55BNOKfV2edRqlBshdzdhf'
    'A0HZDVEjsgZKAcjcTGfCZdx/hrVnycFvi4TwW4hgQ+ml5Rsif89K3FFyg3P3SJlrz3KfTZemKYmI/rCwRaws'
    'FsYuM+MxL9KWOp7M5iJk84xABgRHV4v2WmHEFOo7q2sOVF5TxC4jvlqKqvoMiDbRWEBrt7qrBtIlxtz95a38'
    'TaBTsk/JPiX7lOxXLtk/QXLpCTvOXRxuAVmZ9KLtLyHg5nIlucrhV5Iad0frFVDmKYaz9ORoneb8Xfit8u3k'
    'aD15b7NoDf9JMN0erd8kmk/JPiX7lOz3K9kPuXAInQ=='))

if len(PACK) != len(SUBTITLES) * BOX[2] * BOX[3]:
    raise AssertionError('title subtitle pack length changed')
if hashlib.sha256(PACK).hexdigest() != PACK_SHA256:
    raise AssertionError('title subtitle pack checksum changed')
if any(value > 2 for value in PACK):
    raise AssertionError('title subtitles must use shades 0-2 only')


def raster(key):
    """-> the 73x27 shade raster (row-major bytes) for a SUBTITLES key."""
    index = [entry[0] for entry in SUBTITLES].index(key)
    size = BOX[2] * BOX[3]
    return PACK[index * size:(index + 1) * size]
