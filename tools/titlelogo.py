#!/usr/bin/env python3
"""Build and install the approved viewer-supplied English title-screen design.

The canonical source is ``title screen candidate.webp``: an exact 160x144 four-colour
canvas. The build embeds its deduplicated 2bpp tiles and complete visible map; it does not
depend on a file outside the repo.

The overlay runs after the native title map finishes loading with the LCD off. Fade,
palette, PUSH START input and the transition into the file menu remain native.
"""
import base64
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm
import titlelogo_viewer


BANKSZ = 0x4000
FAR_BANK = 0x3E
FAR_UPLOAD = 0x05                 # bank 62's pool reader already owns far entry $03
DATA_ORG = 0x7000                 # asserted unused tail of the final text-pool bank

MAP_WIDTH = 20
MAP_HEIGHT = 18
MAP_AT = 0x9800
TILE_COUNT = titlelogo_viewer.TILE_COUNT
TILE_BYTES = TILE_COUNT * 16
MAP_BYTES = MAP_WIDTH * MAP_HEIGHT

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


def compile_graphics(font=None):
    """Return the canonical deduplicated tiles and 20x18 title map."""
    del font                              # retained for the other graphics-build API
    if hashlib.sha256(REFERENCE_PACK).hexdigest() != REFERENCE_PACK_SHA256:
        raise SystemExit('titlelogo: embedded reference pack checksum changed')
    if len(REFERENCE_PACK) != TILE_BYTES + MAP_BYTES:
        raise SystemExit('titlelogo: embedded reference pack is %d bytes, expected %d'
                         % (len(REFERENCE_PACK), TILE_BYTES + MAP_BYTES))

    tile_blob = REFERENCE_PACK[:TILE_BYTES]
    tilemap = REFERENCE_PACK[TILE_BYTES:]
    # Signed BG tile mode splits sequential IDs at $7F/$80: IDs $00-$7F live at $9000,
    # while $80-$9F live at $8800. Two contiguous copies reproduce all 160 tiles.
    groups = ((0x00, tile_blob[:0x80 * 16]),
              (0x80, tile_blob[0x80 * 16:]))
    tiles = {tile: tile_blob[tile * 16:(tile + 1) * 16]
             for tile in range(TILE_COUNT)}
    return {'map': tilemap, 'groups': groups, 'tiles': tiles,
            'unique': TILE_COUNT, 'source_sha': REFERENCE_SOURCE_SHA256}


def _uploader(code_org, groups, group_addresses, map_org):
    calls = []
    for (tile, data), address in zip(groups, group_addresses):
        calls.append("""
        ld hl,$%04X
        ld de,$%04X
        ld bc,$%04X
        call copy
""" % (address, _vram_addr(tile), len(data)))
    source = """
upload:
        push af
        push bc
        push de
        push hl
%s
        ld hl,$%04X
        ld de,$%04X
        ld c,$%02X
map_row:
        ld b,$%02X
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
""" % (''.join(calls), map_org, MAP_AT, MAP_HEIGHT, MAP_WIDTH)
    return gbasm.assemble(source, code_org)


def install(buf, font, titlecard_built, notes=None):
    """Install the approved full-screen title raster in bank 62."""
    if len(buf) < 0x100000:
        raise SystemExit('titlelogo: requires the 1 MiB expanded ROM')
    if not titlecard_built or not titlecard_built.get('logo_far'):
        raise SystemExit('titlelogo: titlecard wrapper was not built with logo dispatch')

    built = compile_graphics(font)
    cursor = DATA_ORG
    group_addresses = []
    for _tile, data in built['groups']:
        group_addresses.append(cursor)
        cursor += len(data)
    map_org = cursor
    cursor += len(built['map'])
    code_org = (cursor + 0x0F) & ~0x0F
    code, labels = _uploader(code_org, built['groups'], group_addresses, map_org)
    end_addr = code_org + len(code)
    if end_addr > 0x8000:
        raise SystemExit('titlelogo: title asset overruns bank %d by %d bytes'
                         % (FAR_BANK, end_addr - 0x8000))

    bank = _off(FAR_BANK, 0x4000)
    pointer_at = bank + FAR_UPLOAD - 1
    if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
        raise SystemExit('titlelogo: far entry $%02X in bank %d is already occupied'
                         % (FAR_UPLOAD, FAR_BANK))
    tail_at = bank + DATA_ORG - 0x4000
    tail_end = bank + end_addr - 0x4000
    if any(value != 0xFF for value in buf[tail_at:tail_end]):
        raise SystemExit('titlelogo: pool-bank tail $%04X-$%04X is not free'
                         % (DATA_ORG, end_addr - 1))

    upload = labels['upload']
    buf[pointer_at:pointer_at + 2] = bytes((upload & 0xFF, upload >> 8))
    for address, (_tile, data) in zip(group_addresses, built['groups']):
        at = bank + address - 0x4000
        buf[at:at + len(data)] = data
    map_at = bank + map_org - 0x4000
    buf[map_at:map_at + len(built['map'])] = built['map']
    code_at = bank + code_org - 0x4000
    buf[code_at:code_at + len(code)] = code

    out = [
        'titlelogo: approved viewer-supplied Mystery Dungeon / Shiren / The Wanderer / '
        'Monster of Moonlight Village / GB four-colour full-screen title; native fade '
        'and PUSH START behavior preserved',
        'titlelogo: %d deduplicated tiles; bank %d $%04X-$%04X; source SHA-256 %s'
        % (built['unique'], FAR_BANK, DATA_ORG, end_addr - 1,
           REFERENCE_SOURCE_SHA256[:12]),
    ]
    if notes is not None:
        notes.extend(out)
    built.update({'data_org': DATA_ORG, 'group_addresses': tuple(group_addresses),
                  'map_org': map_org, 'code_org': code_org, 'end_addr': end_addr,
                  'labels': labels})
    return built
