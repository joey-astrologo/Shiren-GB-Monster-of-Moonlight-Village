#!/usr/bin/env python3
"""Proportional labels and live values for the in-dungeon status screen.

The native status producer in bank 4 finishes every dynamic field, then calls the
bank-31 Path copier at 4:$4FDD.  That boundary runs with LCDC.7 clear on every measured
entry.  Replace the three-byte copier call with one far call which first performs the
original copy and then composes the completed shadow fields directly into private BG
tiles.  The game's existing full-map publisher remains authoritative, so this adds no
VBlank waits and no visible intermediate map.

The private low-page IDs deliberately avoid $22/$24/$2A/$36, which the persistent
bottom status Window references while the menu is open.  Weapon/Shield retain the
source-stable fragments installed by structvwf; all other IDs are repainted on each
status draw before their shadow cells are published.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm
import propvwf
from latinfont import EN_CODES


BANKSZ = 0x4000
FAR_BANK = 0x35
FAR_INDEX = 0x05
POPUP_INDEX = 0x07
CODE_AT = 0x405A
HOOK = (4, 0x4FDD)
HOOK_OLD = bytes.fromhex('CF 11 1F')

# The four structured Weapon/Shield tiles are installed into the canonical menu font by
# structvwf.  The remaining slices are private to the settled dungeon status screen.
WEAPON_TILES = (0xA5, 0xA6, 0xA7, 0xA8)
SHIELD_TILES = (0xAA, 0xAD, 0xAE, 0xA9)
PRIVATE_RUNS = {
    'Experience': (0x04, 7),
    'Strength': (0x0B, 6),
    'Gitan': (0x11, 5),
    'Path': (0x16, 4),
    'Weapon value': (0x1A, 4),
    'Floor': (0x1E, 2),
    'Shield value': (0x25, 4),
    'Strength value': (0x2B, 4),
    'Experience value': (0x2F, 4),
}
WINDOW_LIVE_IDS = frozenset((0x22, 0x24, 0x2A, 0x36))

# The status values use native fixed-font digits $01-$0A, which are the same codes as
# English 0-9. Slash is native/English $B0; native F/G are $B4/$B5. Plus is sparse.
# Everything else needed by Path and the two full labels is in the contiguous core.
SLOT_CODES = tuple(range(propvwf.CORE_CODES)) + (EN_CODES['+'], EN_CODES['/'])
SLOT_PLUS = propvwf.CORE_CODES
SLOT_SLASH = propvwf.CORE_CODES + 1
SLOTS = len(SLOT_CODES)
SHIFT_STRIDE = SLOTS * 16

S_SRC = 0xC0C0
S_LEN = 0xC0C2
S_CAP = 0xC0C3
S_BASE = 0xC0C4
S_PEN = 0xC0C5
S_TOTAL = 0xC0C6
S_CODE = 0xC0C7
S_WIDTH = 0xC0C8
S_LEFT = 0xC0C9
S_ALIGN = 0xC0CA
BUFFER = 0xC008                 # six one-plane tiles; queue is idle/LCD is off here


def _off(bank, addr):
    return bank * BANKSZ + (addr - (0x4000 if bank else 0))


def _shifted_font(font):
    """Shift-major table: eight left rows then eight spill rows per dense slot."""
    out = bytearray()
    for shift in range(8):
        for code in SLOT_CODES:
            ch = next((ch for ch, value in EN_CODES.items() if value == code), None)
            if ch is None:
                raise SystemExit('statusvwf: no approved glyph for code $%02X' % code)
            glyph = font.glyphs[ch]
            width = font.advance(ch)
            spill_mask = (1 << (8 - width)) - 1 if width < 8 else 0
            if any(row & spill_mask for row in glyph):
                raise SystemExit('statusvwf: %r inks outside its %dpx advance' %
                                 (ch, width))
            out += bytes(row >> shift for row in glyph)
            out += bytes(((row << (8 - shift)) & 0xFF) if shift else 0
                         for row in glyph)
    return bytes(out)


def _source(widths):
    width_bytes = ','.join('$%02X' % value for value in widths)
    strength = ','.join('$%02X' % EN_CODES[ch] for ch in 'Strength')
    experience = ','.join('$%02X' % EN_CODES[ch] for ch in 'Experience')
    weapon = ','.join('$%02X' % value for value in WEAPON_TILES)
    shield = ','.join('$%02X' % value for value in SHIELD_TILES)
    return fr"""
statusentry:
  ; Preserve the exact native Path shadow copier this hook replaces.
  rst $08
  db $11,$1F
statusdraw:

  ; Static left-hand labels use structvwf's canonical four-tile fragments.
  ld hl,weapontiles
  ld de,$C461
  ld b,$04
  call copymap
  ld hl,$C465
  ld b,$04
  call clearcells
  ld hl,shieldtiles
  ld de,$C4A1
  ld b,$04
  call copymap
  ld hl,$C4A5
  ld b,$04
  call clearcells

  ; Full labels in the right half. They fit independently of the values below them.
  ld hl,strength
  ld b,$08
  ld c,$06
  ld d,$0B
  ld e,$00
  call field
  jr nc,strengthskip
  ld hl,$C46A
  call fieldmap
strengthskip:
  ld hl,$C470
  ld b,$03
  call clearcells

  ld hl,experience
  ld b,$0A
  ld c,$07
  ld d,$04
  ld e,$00
  call field
  jr nc,experienceskip
  ld hl,$C4AA
  call fieldmap
experienceskip:
  ld hl,$C4B1
  ld b,$02
  call clearcells

  ; Right-aligned dynamic values. Source spans are the native completed shadow cells;
  ; map destinations are compact slices immediately inside each field's right edge.
  ld hl,$C348
  ld b,$0B
  ld c,$05
  ld d,$11
  ld e,$01
  call field
  jr nc,gitanskip
  ld hl,$C34E
  call fieldmap
gitanskip:
  ld hl,$C388
  ld b,$0B
  ld c,$02
  ld d,$1E
  ld e,$01
  call field
  jr nc,floorskip
  ld hl,$C391
  call fieldmap
floorskip:
  ld hl,$C3C8
  ld b,$0B
  ld c,$04
  ld d,$16
  ld e,$01
  call field
  jr nc,pathskip
  ld hl,$C3CF
  call fieldmap
pathskip:
  ld hl,$C481
  ld b,$08
  ld c,$04
  ld d,$1A
  ld e,$01
  call field
  jr nc,weaponskip
  ld hl,$C485
  call fieldmap
weaponskip:
  ld hl,$C48A
  ld b,$09
  ld c,$04
  ld d,$2B
  ld e,$01
  call field
  jr nc,strvalueskip
  ld hl,$C48F
  call fieldmap
strvalueskip:
  ld hl,$C4C1
  ld b,$08
  ld c,$04
  ld d,$25
  ld e,$01
  call field
  jr nc,shieldskip
  ld hl,$C4C5
  call fieldmap
shieldskip:
  ld hl,$C4CA
  ld b,$09
  ld c,$04
  ld d,$2F
  ld e,$01
  call field
  jr nc,expvalueskip
  ld hl,$C4CF
  call fieldmap
expvalueskip:
  ret

; menuvwf's compact gate for the unique standing stair/trap popup. Preserve the row
; renderer's live registers. Trap changes the following shared Stay row to Back. Exit
; already stages Proceed, while ordinary stairs stage direction-specific Up/Down; rebuild
; every non-trap form as Proceed/Stay so all three gameplay producers share one wording.
popupgate:
  push bc
  push de
  push hl
  ld a,[$C69A]
  cp $03
  jr nz,popupbad
  ld a,[$C69B]
  cp $04
  jr nz,popupbad
  ld a,[$C69C]
  cp $02
  jr nz,popupbad
  ld a,[$C69D]
  cp $06
  jr nz,popupbad
  ld a,[$C69E]
  and a
  jr nz,popupbad
  ld a,b
  cp $C6
  jr nz,popupbad
  ld a,d
  cp $02
  jr nc,popupbad
  and a
  jr nz,popupgood
  ld a,[bc]
  and a
  jr nz,popupgood
  inc bc
  ld a,[bc]
  cp $%02X
  jr z,popupscan
  dec bc
  ld hl,popupstairs
  ld d,$0F
  jr popupcopy
popupscan:
  ld a,[bc]
  inc bc
  cp $FF
  jr nz,popupscan
  ld hl,popupback
  ld d,$06
popupcopy:
  ld a,[hl+]
  ld [bc],a
  inc bc
  dec d
  jr nz,popupcopy
popupgood:
  pop hl
  pop de
  pop bc
  ld a,$01
  ret
popupbad:
  pop hl
  pop de
  pop bc
  xor a
  ret

; HL=source, B=cells, C=tile cap, D=tile base, E=right-align flag.
; Returns carry set after painting private VRAM; carry clear leaves the native map intact.
field:
  ld a,l
  ld [${S_SRC:04X}],a
  ld a,h
  ld [${S_SRC + 1:04X}],a
  ld a,b
  ld [${S_LEN:04X}],a
  ld [${S_LEFT:04X}],a
  ld a,c
  ld [${S_CAP:04X}],a
  ld a,d
  ld [${S_BASE:04X}],a
  ld a,e
  ld [${S_ALIGN:04X}],a
  xor a
  ld [${S_TOTAL:04X}],a
measure:
  ld a,[$C0C9]
  and a
  jr z,measureddone
  dec a
  ld [$C0C9],a
  ld a,[hl+]
  call normalise
  jp nc,fieldbad
  and a
  jr z,measure
  push hl
  call getwidth
  pop hl
  ld b,a
  ld a,[${S_TOTAL:04X}]
  add a,b
  ld [${S_TOTAL:04X}],a
  jr measure
measureddone:
  ld a,[${S_CAP:04X}]
  add a,a
  add a,a
  add a,a
  ld b,a
  ld a,[${S_TOTAL:04X}]
  cp b
  jr c,measurefits
  jr z,measurefits
  jp fieldbad
measurefits:
  ld a,[${S_ALIGN:04X}]
  and a
  ld a,$00
  jr z,penready
  ld a,b
  ld c,a
  ld a,[${S_TOTAL:04X}]
  ld b,a
  ld a,c
  sub b
penready:
  ld [${S_PEN:04X}],a
  ; Clear cap+1 one-plane tiles. The extra spill tile makes the OR loop unconditional.
  ld a,[${S_CAP:04X}]
  inc a
  add a,a
  add a,a
  add a,a
  ld b,a
  xor a
  ld hl,${BUFFER:04X}
fieldclear:
  ld [hl+],a
  dec b
  jr nz,fieldclear
  ld a,[${S_SRC:04X}]
  ld l,a
  ld a,[${S_SRC + 1:04X}]
  ld h,a
  ld a,[${S_LEN:04X}]
  ld [${S_LEFT:04X}],a
compose:
  ld a,[${S_LEFT:04X}]
  and a
  jr z,upload
  dec a
  ld [${S_LEFT:04X}],a
  ld a,[hl+]
  push hl
  call normalise
  jr nc,composebad
  and a
  jr z,composenext
  ld [${S_CODE:04X}],a
  call getwidth
  ld [${S_WIDTH:04X}],a
  ; glyphs + shift*SHIFT_STRIDE + dense_slot*16
  ld a,[${S_PEN:04X}]
  and $07
  ld b,a
  ld hl,glyphs
  ld de,$%04X
shiftadd:
  ld a,b
  and a
  jr z,shiftready
  add hl,de
  dec b
  jr shiftadd
shiftready:
  ld a,[${S_CODE:04X}]
  ld c,a
  ld b,$00
  sla c
  rl b
  sla c
  rl b
  sla c
  rl b
  sla c
  rl b
  add hl,bc
  ; BUFFER + floor(pen/8)*8 == BUFFER + (pen & $F8)
  ld a,[${S_PEN:04X}]
  and $F8
  add a,${BUFFER & 0xFF:02X}
  ld e,a
  ld d,${BUFFER >> 8:02X}
  ld b,$10
orrows:
  ld a,[hl+]
  ld c,a
  ld a,[de]
  or c
  ld [de],a
  inc de
  dec b
  jr nz,orrows
  ld a,[${S_PEN:04X}]
  ld b,a
  ld a,[${S_WIDTH:04X}]
  add a,b
  ld [${S_PEN:04X}],a
composenext:
  pop hl
  jr compose
composebad:
  pop hl
fieldbad:
  and a
  ret

upload:
  ; All status-private bases are below $80: VRAM = $9000 + base*16.
  ld a,[${S_BASE:04X}]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  add a,$90
  ld h,a
  ld d,h
  ld e,l
  ld hl,${BUFFER:04X}
  ld a,[${S_CAP:04X}]
  add a,a
  add a,a
  add a,a
  ld b,a
uploadbyte:
  ld a,[hl+]
  ld [de],a
  inc de
  ld [de],a
  inc de
  dec b
  jr nz,uploadbyte
  scf
  ret

; Native status-cell normalisation -> dense font slot, carry set. A zero is a skip.
normalise:
  and a
  jr z,normok
  cp $43
  jr c,normok
  cp $7C
  jr z,normplus
  cp $7D
  jr z,normminus
  cp $B0
  jr z,normslash
  cp $B4
  jr z,normf
  cp $B5
  jr z,normg
  and a
  ret
normplus:
  ld a,$%02X
  jr normok
normslash:
  ld a,$%02X
  jr normok
normminus:
  ld a,$%02X
  jr normok
normf:
  ld a,$%02X
  jr normok
normg:
  ld a,$%02X
normok:
  scf
  ret

getwidth:
  ld l,a
  ld h,$00
  ld de,widths
  add hl,de
  ld a,[hl]
  ret

; Use the most recent field's contiguous base/cap at the caller-supplied shadow address.
fieldmap:
  ; Dynamic sources live in WRAM and would otherwise leave their leading fixed-cell
  ; digits/letters visible to the left of the compact private slice. ROM label literals
  ; are below $C000 and must of course remain untouched.
  push hl
  ld a,[${S_SRC + 1:04X}]
  cp $C0
  jr c,fieldmapnoclear
  ld d,a
  ld a,[${S_SRC:04X}]
  ld e,a
  ld a,[${S_LEN:04X}]
  ld c,a
  xor a
fieldmapsourceclear:
  ld [de],a
  inc de
  dec c
  jr nz,fieldmapsourceclear
fieldmapnoclear:
  pop hl
  ld a,[${S_BASE:04X}]
  ld b,a
  ld a,[${S_CAP:04X}]
  ld c,a
fieldmaploop:
  ld a,b
  ld [hl+],a
  inc b
  dec c
  jr nz,fieldmaploop
  ret

copymap:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,copymap
  ret
clearcells:
  xor a
clearloop:
  ld [hl+],a
  dec b
  jr nz,clearloop
  ret

strength:
  db %s
experience:
  db %s
weapontiles:
  db %s
shieldtiles:
  db %s
popupback:
  db $00,%s,$FF
popupstairs:
  db $00,%s,$FF,$00,%s,$FF
widths:
  db %s
glyphs:
""" % (EN_CODES['T'], SHIFT_STRIDE, SLOT_PLUS, SLOT_SLASH, EN_CODES['-'],
       EN_CODES['F'], EN_CODES['G'], strength, experience, weapon, shield,
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Back'),
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Proceed'),
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Stay'), width_bytes)


def install(buf, notes=None, font=None):
    if font is None:
        raise SystemExit('statusvwf requires the approved Dot font')

    used = set()
    for base, cap in PRIVATE_RUNS.values():
        run = set(range(base, base + cap))
        if used & run:
            raise AssertionError('statusvwf: private tile runs overlap')
        used |= run
    if used & WINDOW_LIVE_IDS:
        raise AssertionError('statusvwf: private tiles overlap persistent Window IDs')
    if used & set(WEAPON_TILES + SHIELD_TILES):
        raise AssertionError('statusvwf: dynamic tiles overlap structured labels')

    widths = tuple(font.advance_code(code) for code in SLOT_CODES)
    code, labels = gbasm.assemble(_source(widths), CODE_AT)
    blob = code + _shifted_font(font)
    if CODE_AT + len(blob) > 0x8000:
        raise SystemExit('statusvwf: bank %d overflow (%d bytes)' %
                         (FAR_BANK, len(blob)))
    bank = _off(FAR_BANK, 0x4000)
    if buf[bank] != FAR_BANK:
        raise SystemExit('statusvwf: bank %d far table is not installed' % FAR_BANK)
    index = bank + FAR_INDEX - 1
    if bytes(buf[index:index + 2]) != b'\xFF\xFF':
        raise SystemExit('statusvwf: far index $%02X in bank %d is occupied' %
                         (FAR_INDEX, FAR_BANK))
    at = _off(FAR_BANK, CODE_AT)
    if any(value != 0xFF for value in buf[at:at + len(blob)]):
        raise SystemExit('statusvwf: bank %d $%04X-$%04X is not free' %
                         (FAR_BANK, CODE_AT, CODE_AT + len(blob)))
    buf[at:at + len(blob)] = blob
    buf[index] = labels['statusentry'] & 0xFF
    buf[index + 1] = labels['statusentry'] >> 8
    popup_index = bank + POPUP_INDEX - 1
    if bytes(buf[popup_index:popup_index + 2]) != b'\xFF\xFF':
        raise SystemExit('statusvwf: far index $%02X in bank %d is occupied' %
                         (POPUP_INDEX, FAR_BANK))
    buf[popup_index] = labels['popupgate'] & 0xFF
    buf[popup_index + 1] = labels['popupgate'] >> 8

    hook = _off(*HOOK)
    if bytes(buf[hook:hook + len(HOOK_OLD)]) != HOOK_OLD:
        raise SystemExit('statusvwf: hook at %d:$%04X changed' % HOOK)
    buf[hook:hook + 3] = bytes((0xD7, FAR_INDEX, FAR_BANK))

    if notes is not None:
        notes.append('statusvwf: full Strength/Experience labels and seven live status '
                     'values use approved proportional glyphs in 40 private low-page '
                     'tiles; native LCD-off completion/map publication preserved')
