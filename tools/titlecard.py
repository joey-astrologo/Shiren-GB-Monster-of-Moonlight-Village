#!/usr/bin/env python3
"""Build and install Joey's approved pre-intro copyright-card mock-up.

The canonical source is ``title_x6 (1).png``: an exact 6x nearest-neighbour preview of a
160x144 three-colour Game Boy screen. Under the card's native palette, black maps to
colour index 3, its green shadow maps to index 2, and white maps to index 0. The build
embeds the resulting deduplicated 2bpp
tiles and complete visible map, so it does not depend on a file outside the repository.

The card is loaded after the native decompressor finishes while the LCD is off. Its native
fade, timing, skip behavior, transition into cinematic scene 0, and the later illustrated
title-screen dispatch remain unchanged.
"""
import base64
import hashlib
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm


BANKSZ = 0x4000
SOURCE_BANK = 9
# Bank 61 is a text-pool bank, but the finished script uses only the first three pool
# banks. The installer still guards this tail byte-for-byte, so future text growth fails
# loudly instead of overlapping the card. Entry $03 remains the pool reader; $05 is free.
FAR_BANK = 0x3D
FAR_UPLOAD = 0x05
DATA_ORG = 0x7000

HOOK_AT = 0x4115
NATIVE_DECOMPRESS = 0x3A96
FINAL_HL = 0x9C00
FINAL_DE = 0x7FC5

MAP_WIDTH = 20
MAP_HEIGHT = 18
MAP_AT = 0x9800
TILE_COUNT = 96
TILE_BYTES = TILE_COUNT * 16
MAP_BYTES = MAP_WIDTH * MAP_HEIGHT

REFERENCE_SOURCE_SHA256 = '6cd16ef024c1fc8e7681c9001b7e5b2353f98e7d2a4b5c2e35a2b819315f11f6'
REFERENCE_PACK_SHA256 = '199034f9e1561e09f20fd6907e42b1fa2c38fd738722d36a0a36d474bf396b8c'
REFERENCE_RASTER_SHA256 = '4f81fb86208f0296aca3c96875429c06e3df28f3b91e843f3cc7885eff63606d'
REFERENCE_PACK = zlib.decompress(base64.b64decode(
    'eNqtVNtv21QctudRcwn1RrmkYJpCgXId6QLEoV7MfdzH/X6r+pA31CoSpFpUr4oEQqrS10aN'
    '1D9ij3QiVaZmD178XBWtZpbml4jYO9N8rLg+nONL4kwaL/B9ipzvnJ9/53fzQejfsB8+PeR'
    '5+Of/X9mmqKQo5iWJS9EVCxAuFheumqZlWSCw/wOxHMPqug7WMIiXajtg5Jk9NcJN5MXlQL'
    'UQvUJRQrm8HO1rVzVzzporRv44jmWbhq4H0bie60IXHsADhH5VaYaaKbkYvi1ed6BT8gkhP'
    'omjgekQW9OhmX4+4TkNDbquJ+Z5kaJWthEiuQQkeSEEhjDII8pGLPtczi/nZUlGiCKQy7Ig'
    'UvRKBaH5IiYg1DER0kGcOFocFySxe14UPc6t5FJp6tAveElYEsJcSrCE9ymHxOt60KVo2n9'
    'DRjLBDZ1zXQC63U4n0pKkqradzUbaQaajWQ1nYG9C3Ta6fXvE55Pnxn+PNCexXKu7099vGi'
    'uV8dmcvLtHsLvX6XS7ALjuxl4PY2Mvm7VtVZUkMhM4U6NltNQ1dW2/pe50G5rm1b31+pnt'
    'pnE0MzObLpXkArpiaKbp7LRX2wk+WU+eE04IZRexMsPi2tmG3epyqZQ0iBc6uCF21M/R1Ih'
    '6xYi66ldEZk7SmXhN+C1+K64bFxo7cb1gTv40pOFkOH9kphwnvXAkF+2pGJVKRdVt3QY2A'
    'BC6XjRZHs5lRJ1IEZ1bGiCKgd+q18+sN85HfkL4tZ36OT0jiNPS5PE0aTcqGIZRKEwX0sUS'
    'JLoWIpcL/EUvN9WmEY+dxHX5unYt0qlNSSqXoRNVj3wsvJiox9/R/moowT+jS6hpP4Q+g9k'
    'vFjP9ekJoApJ3f17klFTrOb24v7aqtOOaGWPmo2mUcCenspmh/qzX12txnTiWqMb14VVqbq'
    'if+eRQ/CzLtjQL89rl6yR/smb1ACiCxdNCjvdtFeV8R+koSqLOi0RX9zcxq5caimaF9caZF'
    'zCDbyGTyZyNSLTp9xkA04L+dbPUG5+tbdRqSUEsB/4vXFQuYv/VUY7UWffvDR0w88wYftoZ'
    'PO+5nCAS4Bk+GDuLTyguni45wfWltJW/MduJauJHootgQKJ/2w24+ufqJb9TIdgW63/brjd8'
    'D7AstxnXeIyHekTdHPQN+hBz+JYR9tbbbr8jcedouMYdOXrX2N333Htfcvz+B3jqv+LBidTk'
    'Qw9PDa098uhj048/8eSw4VNPP3Ps2fTM8Uxs7bnnX8gKuRdnxf/pjBN56aWXX3n1tdffOP'
    'nmW2+/8y5Ze+/9Ux98+NHHn3z62edffPnV19/E7b/97vubn/oPDOO5JQ=='
))


def _off(bank, addr):
    return bank * BANKSZ + (addr - (BANKSZ if bank else 0))


def _vram_addr(tile):
    return 0x9000 + tile * 16 if tile < 0x80 else 0x8800 + (tile - 0x80) * 16


def _raster_indices(tile_blob, tilemap):
    """Expand the packed asset to one colour-index byte per visible pixel."""
    out = bytearray(MAP_WIDTH * 8 * MAP_HEIGHT * 8)
    stride = MAP_WIDTH * 8
    for map_y in range(MAP_HEIGHT):
        for map_x in range(MAP_WIDTH):
            tile = tilemap[map_y * MAP_WIDTH + map_x]
            data = tile_blob[tile * 16:(tile + 1) * 16]
            for y in range(8):
                lo, hi = data[y * 2:y * 2 + 2]
                for x in range(8):
                    bit = 7 - x
                    value = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
                    out[(map_y * 8 + y) * stride + map_x * 8 + x] = value
    return bytes(out)


def compile_graphics(font=None):
    """Return the canonical deduplicated tiles and complete 20x18 card map."""
    del font                              # retained for the shared graphics-build API
    if hashlib.sha256(REFERENCE_PACK).hexdigest() != REFERENCE_PACK_SHA256:
        raise SystemExit('titlecard: embedded reference pack checksum changed')
    if len(REFERENCE_PACK) != TILE_BYTES + MAP_BYTES:
        raise SystemExit('titlecard: embedded reference pack is %d bytes, expected %d'
                         % (len(REFERENCE_PACK), TILE_BYTES + MAP_BYTES))

    tile_blob = REFERENCE_PACK[:TILE_BYTES]
    tilemap = REFERENCE_PACK[TILE_BYTES:]
    if max(tilemap) >= TILE_COUNT:
        raise SystemExit('titlecard: map references tile %d outside 0-%d'
                         % (max(tilemap), TILE_COUNT - 1))
    raster = _raster_indices(tile_blob, tilemap)
    if hashlib.sha256(raster).hexdigest() != REFERENCE_RASTER_SHA256:
        raise SystemExit('titlecard: embedded raster checksum changed')

    groups = ((0x00, tile_blob),)
    tiles = {tile: tile_blob[tile * 16:(tile + 1) * 16]
             for tile in range(TILE_COUNT)}
    return {'map': tilemap, 'groups': groups, 'tiles': tiles, 'raster': raster,
            'unique': TILE_COUNT, 'source_sha': REFERENCE_SOURCE_SHA256}


def _hook():
    return gbasm.assemble("""
        rst $10
        db $05,$3D
    """, HOOK_AT)[0]


def _uploader(code_org, groups, group_addresses, map_org, logo_far=None):
    calls = []
    for (tile, data), address in zip(groups, group_addresses):
        calls.append("""
        ld hl,$%04X
        ld de,$%04X
        ld bc,$%04X
        call copy
""" % (address, _vram_addr(tile), len(data)))

    title_target = 'title_check' if logo_far else 'done'
    title_check = ''
    if logo_far:
        far_index, far_bank = logo_far
        title_check = f"""
title_check:
        ld a,d
        cp $74
        jr nz,done
        ld a,e
        cp $99
        jr nz,done
        ld a,[$FF40]
        and $80
        jr nz,done
        rst $10
        db ${far_index:02X},${far_bank:02X}
        jr done
"""

    source = """
upload:
        call $%04X
        push af
        push bc
        push de
        push hl

        ld a,h
        cp $%02X
        jr nz,done
        ld a,l
        and a
        jr nz,done
        ld a,d
        cp $%02X
        jr nz,%s
        ld a,e
        cp $%02X
        jr nz,%s
        ld a,[$FF40]
        and $80
        jr nz,done
        call draw
        jr done

%s
done:
        pop hl
        pop de
        pop bc
        pop af
        ret

draw:
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
""" % (NATIVE_DECOMPRESS, FINAL_HL >> 8, FINAL_DE >> 8, title_target,
       FINAL_DE & 0xFF, title_target, title_check, ''.join(calls), map_org, MAP_AT,
       MAP_HEIGHT, MAP_WIDTH)
    return gbasm.assemble(source, code_org)


def install(buf, font, markers_built, notes=None, logo_far=None):
    """Install the approved full-screen card in the guarded bank-61 tail."""
    if len(buf) < 0x100000:
        raise SystemExit('titlecard: requires the 1 MiB expanded ROM')
    if not markers_built:
        raise SystemExit('titlecard: requires the completed marker build')

    built = compile_graphics(font)
    cursor = DATA_ORG
    group_addresses = []
    for _tile, data in built['groups']:
        group_addresses.append(cursor)
        cursor += len(data)
    map_org = cursor
    cursor += len(built['map'])
    code_org = (cursor + 0x0F) & ~0x0F
    code, labels = _uploader(code_org, built['groups'], group_addresses, map_org, logo_far)
    end_addr = code_org + len(code)
    if end_addr > 0x8000:
        raise SystemExit('titlecard: card overruns bank %d by %d bytes'
                         % (FAR_BANK, end_addr - 0x8000))

    bank = _off(FAR_BANK, 0x4000)
    pointer_at = bank + FAR_UPLOAD - 1
    if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
        raise SystemExit('titlecard: far entry $%02X in bank %d is already occupied'
                         % (FAR_UPLOAD, FAR_BANK))
    tail_at = bank + DATA_ORG - 0x4000
    tail_end = bank + end_addr - 0x4000
    if any(value != 0xFF for value in buf[tail_at:tail_end]):
        raise SystemExit('titlecard: pool-bank tail $%04X-$%04X is not free'
                         % (DATA_ORG, end_addr - 1))

    hook = _hook()
    hook_at = _off(SOURCE_BANK, HOOK_AT)
    expected = bytes((0xCD, NATIVE_DECOMPRESS & 0xFF, NATIVE_DECOMPRESS >> 8))
    if bytes(buf[hook_at:hook_at + len(hook)]) != expected:
        raise SystemExit('titlecard: loader hook at %d:$%04X changed (got %s, expected %s)'
                         % (SOURCE_BANK, HOOK_AT,
                            bytes(buf[hook_at:hook_at + len(hook)]).hex(), expected.hex()))

    upload = labels['upload']
    buf[pointer_at:pointer_at + 2] = bytes((upload & 0xFF, upload >> 8))
    for address, (_tile, data) in zip(group_addresses, built['groups']):
        at = bank + address - 0x4000
        buf[at:at + len(data)] = data
    map_at = bank + map_org - 0x4000
    buf[map_at:map_at + len(built['map'])] = built['map']
    code_at = bank + code_org - 0x4000
    buf[code_at:code_at + len(code)] = code
    buf[hook_at:hook_at + len(hook)] = hook

    out = [
        'titlecard: approved full-screen Shiren GB / ©1996 Chunsoft / ©1996 Koichi '
        'Sugiyama mock-up; native fade, timing and scene-0 transition preserved',
        'titlecard: %d deduplicated tiles; bank %d $%04X-$%04X; source SHA-256 %s'
        % (built['unique'], FAR_BANK, DATA_ORG, end_addr - 1,
           REFERENCE_SOURCE_SHA256[:12]),
    ]
    if notes is not None:
        notes.extend(out)
    built.update({'data_org': DATA_ORG, 'group_addresses': tuple(group_addresses),
                  'map_org': map_org, 'code_org': code_org, 'end_addr': end_addr,
                  'labels': labels, 'hook': hook, 'logo_far': logo_far})
    return built
