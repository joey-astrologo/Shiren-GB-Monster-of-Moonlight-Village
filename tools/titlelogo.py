#!/usr/bin/env python3
"""Build and install the approved viewer-supplied English title-screen design.

The canonical source is ``title screen candidate.webp``: an exact 160x144 four-colour
canvas. The build embeds its deduplicated 2bpp tiles and complete visible map; it does not
depend on a file outside the repo. Joey's approved scroll subtitles replace only the
73x27 scroll interior at (24,86) (``titlelogo_subtitles.py``):

    A  native title (save progress)             English subtitle
    0  怪物  normal                               Monsters of Moonlight Village
    1  脱出  Hard cleared, Moonlight Exit unlocked Escape from Moonlight Village
    2  恋人  Moonlight Exit cleared                Lover of Moonlight Village
    3  Moonlight Exit post-credit Fin card        Lover of Moonlight Village

Both native producer calls -- the opening route ``31:$48A1`` (A = the variant from the
selector at ``31:$489E``) and Moonlight ending case 3 ``31:$799B`` (A=3) -- far-call
the bank-62 uploader instead. It runs the native producer with the same A, then, with the
LCD still off, uploads the 203 tiles every variant shares and the complete map. A bank-61
subtitle routine then uploads that variant's scroll tiles and its 9x2 scroll cells. The
Fin card also keeps its native Fin tiles and clears PUSH START. Fade, palette, PUSH START
input, the hold and every transition remain native.
"""
import base64
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm
import titlelogo_subtitles
import titlelogo_viewer


BANKSZ = 0x4000
FAR_BANK = 0x3E
FAR_UPLOAD = 0x05                 # bank 62's pool reader already owns far entry $03
DATA_ORG = 0x7000                 # asserted unused tail of the final text-pool bank
SUBTITLE_BANK = 0x3D
SUBTITLE_FAR = 0x0F
SUBTITLE_ORG = 0x7800             # after titlecard's asserted bank-61 tail

MAP_WIDTH = 20
MAP_HEIGHT = 18
MAP_AT = 0x9800
TILE_COUNT = titlelogo_viewer.TILE_COUNT
TILE_BYTES = TILE_COUNT * 16
MAP_BYTES = MAP_WIDTH * MAP_HEIGHT

# A selects the subtitle; the Fin card (A=3) is the 恋人 artwork, as in the Japanese ROM.
VARIANTS = ('monsters', 'escape', 'lover')
VARIANT_FOR_A = ('monsters', 'escape', 'lover', 'lover')

NATIVE_PRODUCER_CALL = bytes.fromhex('d7 0b 1e')
OPENING_HOOK_BANK = 31
OPENING_HOOK_AT = 0x48A1
OPENING_HOOK_CONTEXT = bytes.fromhex('cd 2d 49')         # the variant selector call
ENDING_HOOK_BANK = 31
ENDING_HOOK_AT = 0x799B
ENDING_HOOK_OLD = NATIVE_PRODUCER_CALL
# The ending's native loader supplies contiguous Fin tiles $2D-$3C at $92D0 and map
# (15,13)..(18,16). They are preserved beyond every variant's tile allocation.
FIN_SOURCE = 0x92D0
FIN_TILE_COUNT = 16
FIN_MAP_AT = MAP_AT + 13 * 32 + 15
PROMPT_MAP_AT = MAP_AT + 15 * 32 + 6

# The SGB host colours the 160x144 Game Boy picture in 8x8-cell units.  The native
# title's 90-byte ATTR_TRN file still followed the Japanese logo after the English
# pixels were installed: its red region crossed `Mystery Dungeon` / `The Wanderer`,
# while the lower-left of the large English S fell back to the neutral palette.
#
# These rows are the English title's complete 20x18 palette map.  Palette 0 is the
# neutral yellow/black title palette, 1 is the orange/red logo and scroll palette,
# 2 is the green GB palette, and 3 is the blue scroll staff / PUSH START palette.
# The last two pixel rows of the large logo share row 8 with `The Wanderer` and the GB
# crest; that cell row deliberately belongs to the foreground labels.  The substantial
# lower curve of the S is on row 7 and is now wholly palette 1.
SGB_ATTR_BANK = 29
SGB_ATTR_ADDR = 0x44FA
SGB_ATTR_ROWS = (
    '11111111111111111111',
    '00000000000000000000',
    '00000000000000000000',
    '00111110110000000000',
    '00111111110000000000',
    '00111111111111111100',
    '01111111111111111100',
    '01111111111111111100',
    '00000000000000222220',
    '00000000000002222222',
    '01111111111112222222',
    '03311111111112222222',
    '03311111111112222222',
    '03311111111110000000',
    '01111111111110000000',
    '00000033333333000000',
    '00000000000000000000',
    '11111111111111111111',
)


def _pack_sgb_attributes(rows):
    if len(rows) != MAP_HEIGHT or any(len(row) != MAP_WIDTH for row in rows):
        raise AssertionError('titlelogo: SGB attribute map must be exactly 20x18')
    cells = [int(value) for row in rows for value in row]
    if any(value not in range(4) for value in cells):
        raise AssertionError('titlelogo: SGB attribute cells must be palettes 0-3')
    return bytes((cells[i] << 6) | (cells[i + 1] << 4) |
                 (cells[i + 2] << 2) | cells[i + 3]
                 for i in range(0, len(cells), 4))


SGB_ATTRIBUTE_PACK = _pack_sgb_attributes(SGB_ATTR_ROWS)
SGB_NATIVE_ATTRIBUTE_PACK = bytes.fromhex(
    '555555555500000000000540000000555540000055555551505555555555555555555500'
    '5555555400555555540005556aaa1555556aaa3d55556aaa3d55556aaa3d555540001555'
    '554000000ffff00000000000005555555555'
)
if len(SGB_ATTRIBUTE_PACK) != 90 or len(SGB_NATIVE_ATTRIBUTE_PACK) != 90:
    raise AssertionError('titlelogo: SGB attribute file must be exactly 90 bytes')

TITLE_FINAL_HL = 0x9C00
TITLE_FINAL_DE = 0x7499

REFERENCE_SOURCE_SHA256 = titlelogo_viewer.SOURCE_SHA256
REFERENCE_PACK_SHA256 = titlelogo_viewer.PACK_SHA256
_PREVIOUS_REFERENCE_PACK = base64.b64decode(
    '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'
)
REFERENCE_PACK = titlelogo_viewer.PACK


def _off(bank, addr):
    return bank * BANKSZ + (addr - (BANKSZ if bank else 0))


def _vram_addr(tile):
    return 0x9000 + tile * 16 if tile < 0x80 else 0x8800 + (tile - 0x80) * 16




def _tile_at(raster, cell_x, cell_y):
    out = bytearray()
    for y in range(8):
        lo = hi = 0
        for x in range(8):
            shade = raster[(cell_y * 8 + y) * 160 + cell_x * 8 + x]
            bit = 7 - x
            lo |= (shade & 1) << bit
            hi |= ((shade >> 1) & 1) << bit
        out += bytes((lo, hi))
    return bytes(out)


def _raster(tiles, tilemap):
    """Expand 2bpp tiles and a 20x18 map to one shade byte per visible pixel."""
    out = bytearray(160 * 144)
    for cell_y in range(MAP_HEIGHT):
        for cell_x in range(MAP_WIDTH):
            data = tiles[tilemap[cell_y * MAP_WIDTH + cell_x]]
            for y in range(8):
                lo, hi = data[y * 2:y * 2 + 2]
                for x in range(8):
                    bit = 7 - x
                    out[(cell_y * 8 + y) * 160 + cell_x * 8 + x] = (
                        ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1))
    return bytes(out)


def approved_raster(variant):
    """-> the approved 160x144 shade raster for a VARIANTS key (base + subtitle)."""
    base_tiles = [REFERENCE_PACK[i * 16:(i + 1) * 16] for i in range(TILE_COUNT)]
    raster = bytearray(_raster(base_tiles, REFERENCE_PACK[TILE_BYTES:]))
    box_x, box_y, width, height = titlelogo_subtitles.BOX
    subtitle = titlelogo_subtitles.raster(variant)
    for y in range(height):
        start = (box_y + y) * 160 + box_x
        raster[start:start + width] = subtitle[y * width:(y + 1) * width]
    return bytes(raster)


def compile_graphics(font=None):
    """Return the shared tiles/map and each variant's scroll tiles and scroll cells."""
    del font                              # retained for the other graphics-build API
    if hashlib.sha256(REFERENCE_PACK).hexdigest() != REFERENCE_PACK_SHA256:
        raise SystemExit('titlelogo: embedded reference pack checksum changed')
    if len(REFERENCE_PACK) != TILE_BYTES + MAP_BYTES:
        raise SystemExit('titlelogo: embedded reference pack is %d bytes, expected %d'
                         % (len(REFERENCE_PACK), TILE_BYTES + MAP_BYTES))

    rasters = {key: approved_raster(key) for key in VARIANTS}
    cells = [(x, y) for y in range(MAP_HEIGHT) for x in range(MAP_WIDTH)]
    cell_tiles = {key: [_tile_at(rasters[key], x, y) for x, y in cells] for key in VARIANTS}
    differing = [index for index in range(len(cells))
                 if len({cell_tiles[key][index] for key in VARIANTS}) > 1]
    if not differing:
        raise SystemExit('titlelogo: approved subtitles do not differ')
    col0 = min(cells[i][0] for i in differing)
    col1 = max(cells[i][0] for i in differing)
    row0 = min(cells[i][1] for i in differing)
    row1 = max(cells[i][1] for i in differing)
    patch = (col0, row0, col1 - col0 + 1, row1 - row0 + 1)
    in_patch = [index for index, (x, y) in enumerate(cells)
                if col0 <= x <= col1 and row0 <= y <= row1]

    # Shared tiles: every tile outside the differing cells, in map scan order, so the
    # blank tile keeps a low ID. Subtitle tiles not already shared follow per variant.
    common = []
    for index in range(len(cells)):
        if index in differing:
            continue
        data = cell_tiles[VARIANTS[0]][index]
        if data not in common:
            common.append(data)
    variant_tiles = {}
    for key in VARIANTS:
        extra = []
        for index in differing:
            data = cell_tiles[key][index]
            if data not in common and data not in extra:
                extra.append(data)
        variant_tiles[key] = extra
    shared = len(common)
    per_variant = max(len(extra) for extra in variant_tiles.values())
    fin_base = shared + per_variant
    if shared < 0x80 or fin_base + FIN_TILE_COUNT > 0x100:
        raise SystemExit('titlelogo: title tiles need IDs $%02X-$%02X plus the Fin'
                         % (shared, fin_base - 1))
    blank = common.index(bytes(16)) if bytes(16) in common else None
    if blank is None:
        raise SystemExit('titlelogo: ending prompt clear requires a blank shared tile')

    def tile_id(key, index):
        data = cell_tiles[key][index]
        if data in common:
            return common.index(data)
        return shared + variant_tiles[key].index(data)

    tilemap = bytes(tile_id(VARIANTS[0], index) for index in range(len(cells)))
    variant_cells = {key: bytes(tile_id(key, index) for index in in_patch)
                     for key in VARIANTS}
    padded = {key: b''.join(variant_tiles[key]) +
              bytes(16) * (per_variant - len(variant_tiles[key])) for key in VARIANTS}

    groups = ((0x00, b''.join(common[:0x80])), (0x80, b''.join(common[0x80:])))
    built = {'map': tilemap, 'groups': groups, 'shared': shared,
             'per_variant': per_variant, 'fin_base': fin_base, 'blank': blank,
             'patch': patch, 'variant_tiles': padded, 'variant_cells': variant_cells,
             'rasters': rasters, 'source_sha': REFERENCE_SOURCE_SHA256}
    for key in VARIANTS:
        view = variant_graphics(built, key)
        if _raster(view['tiles'], view['map']) != rasters[key]:
            raise AssertionError('titlelogo: %s tiles do not reproduce the approved raster'
                                 % key)
    return built


def variant_graphics(built, key):
    """-> {'tiles': {id: data}, 'map': 360 bytes} as the uploaders leave VRAM for a key."""
    tiles = {}
    for base, blob in built['groups']:
        for i in range(len(blob) // 16):
            tiles[base + i] = blob[i * 16:(i + 1) * 16]
    blob = built['variant_tiles'][key]
    for i in range(built['per_variant']):
        tiles[built['shared'] + i] = blob[i * 16:(i + 1) * 16]
    tilemap = bytearray(built['map'])
    col0, row0, width, height = built['patch']
    cells = built['variant_cells'][key]
    for row in range(height):
        for col in range(width):
            tilemap[(row0 + row) * MAP_WIDTH + col0 + col] = cells[row * width + col]
    return {'tiles': tiles, 'map': bytes(tilemap)}


def _uploader(code_org, built, group_addresses, map_org):
    calls = []
    for (tile, data), address in zip(built['groups'], group_addresses):
        calls.append("""
        ld hl,$%04X
        ld de,$%04X
        ld bc,$%04X
        call copy
""" % (address, _vram_addr(tile), len(data)))
    fin_base = built['fin_base']
    source = f"""
upload:
        push af
        push bc
        push de
        push hl
        rst $10
        db $0B,$1E                  ; the native producer with the incoming variant
        ld a,[$FF40]
        and $80
        jr nz,done                  ; never replace a visible screen
        db $F8,$07                  ; ld hl,sp+7: incoming A above saved HL/DE/BC/F
        ld a,[hl]
        cp $03
        jr nz,draw_title
        ld hl,${FIN_SOURCE:04X}
        ld de,${_vram_addr(fin_base):04X}
        ld bc,${FIN_TILE_COUNT * 16:04X}
        call copy
draw_title:
{''.join(calls)}
        ld hl,${map_org:04X}
        ld de,${MAP_AT:04X}
        ld c,${MAP_HEIGHT:02X}
map_row:
        ld b,${MAP_WIDTH:02X}
map_cell:
        ld a,[hl+]
        ld [de],a
        inc de
        dec b
        jr nz,map_cell
        ld a,e
        add a,$0C
        ld e,a
        jr nc,map_next
        inc d
map_next:
        dec c
        jr nz,map_row
        db $F8,$07
        ld a,[hl]
        rst $10
        db ${SUBTITLE_FAR:02X},${SUBTITLE_BANK:02X}
        db $F8,$07
        ld a,[hl]
        cp $03
        jr nz,done
        ld hl,${PROMPT_MAP_AT:04X}
        ld b,$08
        ld a,${built['blank']:02X}
clear_prompt:
        ld [hl+],a
        dec b
        jr nz,clear_prompt
        ld hl,${FIN_MAP_AT:04X}
        ld de,$001C
        ld a,${fin_base:02X}
        ld c,$04
fin_row:
        ld b,$04
fin_cell:
        ld [hl+],a
        inc a
        dec b
        jr nz,fin_cell
        add hl,de
        dec c
        jr nz,fin_row
done:
        pop hl
        pop de
        pop bc
        pop af
        ret

copy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec bc
        ld a,b
        or c
        jr nz,copy
        ret
"""
    return gbasm.assemble(source, code_org)


def _subtitle_source(built):
    col0, row0, width, height = built['patch']
    record = built['per_variant'] * 16 + width * height
    records = []
    for key in VARIANTS:
        data = built['variant_tiles'][key] + built['variant_cells'][key]
        records.append('        db ' + ','.join('$%02X' % value for value in data))
    return f"""
subtitle:                           ; A = title variant 0-3 (3, the Fin card, is 恋人)
        push af
        push bc
        push de
        push hl
        cp $03
        jr c,pick
        ld a,$02
pick:
        ld hl,records
        ld bc,${record:04X}
        and a
        jr z,found
skip:
        add hl,bc
        dec a
        jr nz,skip
found:
        ld de,${_vram_addr(built['shared']):04X}
        ld bc,${built['per_variant'] * 16:04X}
tile_copy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec bc
        ld a,b
        or c
        jr nz,tile_copy
        ld de,${MAP_AT + row0 * 32 + col0:04X}
        ld b,${height:02X}
cell_row:
        ld c,${width:02X}
cell_copy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec c
        jr nz,cell_copy
        ld a,e
        add a,${32 - width:02X}
        ld e,a
        jr nc,cell_next
        inc d
cell_next:
        dec b
        jr nz,cell_row
        pop hl
        pop de
        pop bc
        pop af
        ret
records:
{chr(10).join(records)}
"""


def install(buf, font, titlecard_built, notes=None):
    """Install the approved title rasters in banks 62 and 61."""
    if len(buf) < 0x100000:
        raise SystemExit('titlelogo: requires the 1 MiB expanded ROM')
    if not titlecard_built or not titlecard_built.get('logo_far'):
        raise SystemExit('titlelogo: titlecard wrapper was not built with logo dispatch')

    built = compile_graphics(font)
    opening_at = _off(OPENING_HOOK_BANK, OPENING_HOOK_AT)
    if (bytes(buf[opening_at - 3:opening_at + 3]) !=
            OPENING_HOOK_CONTEXT + NATIVE_PRODUCER_CALL):
        raise SystemExit('titlelogo: opening title producer call changed')
    hook_at = _off(ENDING_HOOK_BANK, ENDING_HOOK_AT)
    if bytes(buf[hook_at - 2:hook_at + 3]) != b'\x3E\x03' + ENDING_HOOK_OLD:
        raise SystemExit('titlelogo: Moonlight case-3 native title producer changed')

    cursor = DATA_ORG
    group_addresses = []
    for _tile, data in built['groups']:
        group_addresses.append(cursor)
        cursor += len(data)
    map_org = cursor
    cursor += len(built['map'])
    code_org = (cursor + 0x0F) & ~0x0F
    code, labels = _uploader(code_org, built, group_addresses, map_org)
    end_addr = code_org + len(code)
    if end_addr > 0x8000:
        raise SystemExit('titlelogo: title asset overruns bank %d by %d bytes'
                         % (FAR_BANK, end_addr - 0x8000))
    subtitle_code, subtitle_labels = gbasm.assemble(_subtitle_source(built), SUBTITLE_ORG)
    subtitle_end = SUBTITLE_ORG + len(subtitle_code)
    if titlecard_built['end_addr'] > SUBTITLE_ORG or subtitle_end > 0x8000:
        raise SystemExit('titlelogo: bank %d subtitle tail $%04X-$%04X does not fit'
                         % (SUBTITLE_BANK, SUBTITLE_ORG, subtitle_end - 1))

    for bank_id, far, start, end in ((FAR_BANK, FAR_UPLOAD, DATA_ORG, end_addr),
                                     (SUBTITLE_BANK, SUBTITLE_FAR, SUBTITLE_ORG,
                                      subtitle_end)):
        bank = _off(bank_id, 0x4000)
        pointer_at = bank + far - 1
        if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
            raise SystemExit('titlelogo: far entry $%02X in bank %d is already occupied'
                             % (far, bank_id))
        if any(value != 0xFF for value in buf[bank + start - 0x4000:bank + end - 0x4000]):
            raise SystemExit('titlelogo: bank %d tail $%04X-$%04X is not free'
                             % (bank_id, start, end - 1))

    bank = _off(FAR_BANK, 0x4000)
    upload = labels['upload']
    buf[bank + FAR_UPLOAD - 1:bank + FAR_UPLOAD + 1] = bytes((upload & 0xFF, upload >> 8))
    for address, (_tile, data) in zip(group_addresses, built['groups']):
        at = bank + address - 0x4000
        buf[at:at + len(data)] = data
    map_at = bank + map_org - 0x4000
    buf[map_at:map_at + len(built['map'])] = built['map']
    code_at = bank + code_org - 0x4000
    buf[code_at:code_at + len(code)] = code

    subtitle_bank = _off(SUBTITLE_BANK, 0x4000)
    entry = subtitle_labels['subtitle']
    buf[subtitle_bank + SUBTITLE_FAR - 1:subtitle_bank + SUBTITLE_FAR + 1] = bytes(
        (entry & 0xFF, entry >> 8))
    at = subtitle_bank + SUBTITLE_ORG - 0x4000
    buf[at:at + len(subtitle_code)] = subtitle_code

    far_call = bytes((0xD7, FAR_UPLOAD, FAR_BANK))
    buf[opening_at:opening_at + 3] = far_call
    buf[hook_at:hook_at + 3] = far_call

    # Keep the native four SGB palettes and border, but align their per-cell assignment
    # with the English picture.  $44FA is referenced only by the native title/SGB setup
    # routines and is transferred as one complete ATTR_TRN file.  Every variant and the
    # Fin card share the English layout: the subtitles use the scroll palette only.
    attr_at = _off(SGB_ATTR_BANK, SGB_ATTR_ADDR)
    actual_attr = bytes(buf[attr_at:attr_at + len(SGB_NATIVE_ATTRIBUTE_PACK)])
    if actual_attr != SGB_NATIVE_ATTRIBUTE_PACK:
        raise SystemExit('titlelogo: native SGB title attribute map at %d:$%04X changed '
                         '(SHA-256 %s)' %
                         (SGB_ATTR_BANK, SGB_ATTR_ADDR,
                          hashlib.sha256(actual_attr).hexdigest()[:12]))
    buf[attr_at:attr_at + len(SGB_ATTRIBUTE_PACK)] = SGB_ATTRIBUTE_PACK

    col0, row0, width, height = built['patch']
    out = [
        'titlelogo: approved viewer-supplied Mystery Dungeon / Shiren / The Wanderer / GB '
        'four-colour full-screen title; native fade and PUSH START behavior preserved',
        'titlelogo: %d shared tiles; bank %d $%04X-$%04X; source SHA-256 %s'
        % (built['shared'], FAR_BANK, DATA_ORG, end_addr - 1, REFERENCE_SOURCE_SHA256[:12]),
        'titlelogo: approved scroll subtitles Monsters/Escape/Lover of Moonlight Village '
        'by title variant; %d tiles and %dx%d cells each at bank %d $%04X-$%04X'
        % (built['per_variant'], width, height, SUBTITLE_BANK, SUBTITLE_ORG,
           subtitle_end - 1),
        'titlelogo: English-aligned 20x18 SGB palette attributes at %d:$%04X; native '
        'palettes and border preserved' % (SGB_ATTR_BANK, SGB_ATTR_ADDR),
        'titlelogo: Moonlight post-credit title is the Lover artwork without PUSH START; '
        'native 4x4 Fin retained at (120,104), tiles $%02X-$%02X; native LCD-off load, '
        'palette, hold and input retained' %
        (built['fin_base'], built['fin_base'] + FIN_TILE_COUNT - 1),
    ]
    if notes is not None:
        notes.extend(out)
    built.update({'data_org': DATA_ORG, 'group_addresses': tuple(group_addresses),
                  'map_org': map_org, 'code_org': code_org, 'end_addr': end_addr,
                  'labels': labels, 'subtitle_labels': subtitle_labels,
                  'subtitle_end': subtitle_end, 'sgb_attribute_pack': SGB_ATTRIBUTE_PACK})
    return built
