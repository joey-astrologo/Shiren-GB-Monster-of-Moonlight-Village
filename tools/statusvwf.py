#!/usr/bin/env python3
"""Proportional labels and live values for the in-dungeon status screen.

The native status producer in bank 4 finishes every dynamic field, then calls the
bank-31 Path copier at 4:$4FDD. Ordinary entries reach that boundary with LCDC.7 clear,
but Items -> Status and returns from the item-name picker can reach it with the LCD
enabled during the visible scan. Mesen and hardware reject unrestricted direct VRAM
writes there, leaving one status glyph plane native and the other proportional.

The exact Status-root -> Items entry is intercepted at screen 1's native shadow-clear
boundary. It retires visible BG rows 0..15 over four complete VBlanks while preserving
the enabled bottom Window, commits the empty header/list-box chrome, then lets the
existing row and final-map publishers reveal only completed Item content inside it.

The exact root -> Items -> root and root -> alternate-Floor-screen-7 -> root stack pops
are special too: all 40 private status tiles and the structured Weapon/Shield fragments
are disjoint from every visible outgoing BG/Window reference. Keep either outgoing page
live and upload each completed status field inside its own VBlank; the largest field is
seven tiles and fits the ten-line interval. The standing-item Floor page appended at
selector `$FF` receives the same treatment only after menuvwf marks its completed one-row
map in `$C1B7`. Unknown LCD-on returns retain the conservative LCD-off path. In every
case the game's existing status-map publisher remains authoritative.

Admitted screen-2 Action B-cancel is handled earlier by menuvwf's exact pop proof. It
restores both the covered carried-Item or settled-Floor parent and the retained screen-1 state, so the generic pop
skips its otherwise invisible screen-0/screen-1 reconstruction entirely. A rejected
proof reaches the ordinary conservative status path here.

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
ITEM_ENTRY_INDEX = 0x09
STATUS_PRE_INDEX = 0x0B
CODE_AT = 0x405A
HOOK = (4, 0x4FDD)
HOOK_OLD = bytes.fromhex('CF 11 1F')
ITEM_ENTRY_HOOK = (4, 0x4951)
ITEM_ENTRY_OLD = bytes.fromhex('21 00 C3 CD 0E 48')

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

# Empty screen-0 chrome for the exact screen-7 Floor -> Status handoff.  Publishing this
# four rows per VBlank establishes every destination box before the native producer is
# allowed to reveal any Status text.  BG rows 16-17 are hidden by the persistent Window.
STATUS_EMPTY_ROWS = (
    (0xB8,) + (0xBC,) * 5 + (0xB9, 0xB8) + (0xBC,) * 11 + (0xB9,),
    *((0xBE,) + (0,) * 5 + (0xBF, 0xBE) + (0,) * 11 + (0xBF,)
      for _ in range(6)),
    (0xBE,) + (0,) * 5 + (0xBF, 0xBA) + (0xBD,) * 11 + (0xBB,),
    (0xBA,) + (0xBD,) * 5 + (0xBB,) + (0,) * 13,
    (0,) * 20,
    (0xB8,) + (0xBC,) * 18 + (0xB9,),
    *((0xBE,) + (0,) * 8 + (0xB6,) + (0,) * 9 + (0xBF,)
      for _ in range(4)),
    (0xBA,) + (0xBD,) * 18 + (0xBB,),
)
STATUS_EMPTY_MAP = bytes(value for row in STATUS_EMPTY_ROWS for value in row)
if len(STATUS_EMPTY_MAP) != 16 * 20:
    raise AssertionError('statusvwf: empty Status map must cover 16 visible rows')

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
statusfloorpre:
  ; Called from the shared native popper while screen 7 and its exact Action descriptor
  ; still own the display. A rejected caller is register/flag transparent. An admitted
  ; Floor -> Status pop publishes complete empty Status chrome before native screen 0 can
  ; reveal any of its text.
  push af
  push bc
  push de
  push hl
  call statusfloorcheck
  jr nc,statusprerestore
  call statusprepublish
statusprerestore:
  pop hl
  pop de
  pop bc
  pop af
  ret

statusfloorcheck:
  ld a,c
  dec a
  jp nz,statusprebad
  ld a,h
  cp $56
  jp nz,statusprebad
  ld a,l
  cp $89
  jp nz,statusprebad
  ld a,[$C534]
  dec a
  jp nz,statusprebad
  ld a,[$C535]
  and a
  jp nz,statusprebad
  ld a,[$C536]
  cp $07
  jp nz,statusprebad
  ld a,[$C6A3]
  cp $07
  jr nz,statusprebad
  ld a,[$C1B3]
  and a
  jr nz,statusprebad
  ld a,[$C1B6]
  and a
  jr nz,statusprebad
  ld a,[$C1B7]
  and a
  jr nz,statusprebad
  ld a,[$C6A6]
  and a
  jr nz,statusprebad
  ld a,[$C6AC]
  inc a
  jr nz,statusprebad
  ld a,[$C6BB]
  cp $07
  jr nz,statusprebad
  ld a,[$C6DE]
  dec a
  jr nz,statusprebad
  ld hl,$C69A
  ld a,[hl+]
  cp $0D
  jr nz,statusprebad
  ld a,[hl+]
  dec a
  jr nz,statusprebad
  ld a,[hl+]
  cp $07
  jr nz,statusprebad
  ld a,[hl+]
  cp $05
  jr nz,statusprebad
  ld a,[hl]
  cp $02
  jr nz,statusprebad
  ldh a,[$FF40]
  and $F8
  cp $E0
  jr nz,statusprebad
  ldh a,[$FF42]
  and a
  jr nz,statusprebad
  ldh a,[$FF43]
  and a
  jr nz,statusprebad
  ldh a,[$FF4A]
  cp $80
  jr nz,statusprebad
  ldh a,[$FF4B]
  cp $07
  jr nz,statusprebad
  scf
  ret
statusprebad:
  and a
  ret

statusprepublish:
  ld hl,statusempty
  ld de,$9800
statusprevisible:
  ldh a,[$FF44]
  cp $90
  jr nc,statusprevisible
  di
  ; Close the visible-to-VBlank race exactly as the Status -> Items regional owner does.
  ldh a,[$FF44]
  cp $90
  jr c,statusprewaitblank
statusprelate:
  ldh a,[$FF44]
  cp $90
  jr nc,statusprelate
statusprewaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,statusprewaitblank
  ld a,$04
statusprebatch:
  push af
  ld b,$04
statusprerow:
  ld c,$14
statusprecell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,statusprecell
  ld a,e
  add a,$0C
  ld e,a
  jr nc,statusprenextrow
  inc d
statusprenextrow:
  dec b
  jr nz,statusprerow
  pop af
  dec a
  jr z,statuspredone
  ; Preserve the ROM source, VRAM destination, and remaining batch count while the
  ; native handlers run between complete VBlanks.
  push af
  push hl
  push de
  ei
statusprenextvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,statusprenextvisible
  di
  ldh a,[$FF44]
  cp $90
  jr c,statusprenextwaitblank
statusprenextlate:
  ldh a,[$FF44]
  cp $90
  jr nc,statusprenextlate
statusprenextwaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,statusprenextwaitblank
  pop de
  pop hl
  pop af
  jr statusprebatch
statuspredone:
  ei
  ret

itementry:
  ; This replaces screen 1's native `ld hl,$C300 / call $480E`.  Preserve that
  ; exact 20x18, stride-32 shadow clear after optionally retiring a direct Status
  ; predecessor.  Unknown callers therefore retain byte-for-byte native semantics.
  push af
  push bc
  push de
  push hl
  call itementrygate
  jr nc,itementryclear
  call itementryblank
  ld a,$01
  ld [$C1B3],a
itementryclear:
  ld hl,$C300
  ld de,$000C
  ld b,$12
itementryclearrow:
  ld c,$14
  xor a
itementryclearcell:
  ld [hl+],a
  dec c
  jr nz,itementryclearcell
  add hl,de
  dec b
  jr nz,itementryclearrow
  pop hl
  pop de
  pop bc
  pop af
  ret

itementrygate:
  ; Exact direct Status-root -> Items stack and hardware proof.  Screen 1 paging
  ; has the same logical stack, so the four cells that are unused on Status must
  ; also be zero.  Drain the preceding Status publication before observing them.
  ld a,[$C6A3]
  dec a
  jr nz,itementrybad
  ld a,[$C6A6]
  and a
  jr nz,itementrybad
  ld a,[$C1B3]
  and a
  jr nz,itementrybad
  ld a,[$C534]
  dec a
  jr nz,itementrybad
  ld a,[$C535]
  and a
  jr nz,itementrybad
  ld a,[$C536]
  dec a
  jr nz,itementrybad
  ld a,[$C6AA]
  and a
  jr z,itementrybad
  cp $15
  jr nc,itementrybad
  ld b,a
  ld a,[$C6AC]
  cp b
  jr nc,itementrybad
  ldh a,[$FF40]
  and $F8
  cp $E0
  jr nz,itementrybad
  ldh a,[$FF42]
  and a
  jr nz,itementrybad
  ldh a,[$FF43]
  and a
  jr nz,itementrybad
  ldh a,[$FF4A]
  cp $80
  jr nz,itementrybad
  ldh a,[$FF4B]
  cp $07
  jr nz,itementrybad
itementrydrain:
  ld a,[$C11A]
  and a
  jr z,itementrymapwait
  call $06F7
  jr itementrydrain
itementrymapwait:
  ldh a,[$FF44]
  cp $90
  jr c,itementrymapwait
itementrymap:
  ld hl,$986F
  ld b,$04
itementrymapcell:
  ld a,[hl+]
  and a
  jr nz,itementrybad
  dec b
  jr nz,itementrymapcell
  scf
  ret
itementrybad:
  and a
  ret

itementryblank:
  ; The hardware Window begins at y=128 and remains enabled, so BG rows 0..15 are
  ; the complete visible predecessor owned by this transition.  Retire four rows
  ; in each complete VBlank; the item renderer cannot reuse a Status tile until all
  ; four batches finish.  The Window and hidden BG rows 16..17 are never touched.
  ld hl,$9800
  ld d,$04
itementryvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,itementryvisible
  di
  ; Close the one-instruction race between observing visible scanout and DI.  If
  ; VBlank arrived there, wait through the following visible frame and use the next
  ; complete VBlank rather than writing in its late tail.
  ldh a,[$FF44]
  cp $90
  jr c,itementrywaitblank
itementrylate:
  ldh a,[$FF44]
  cp $90
  jr nc,itementrylate
itementrywaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,itementrywaitblank
itementrybatch:
  ld b,$04
itementryblankrow:
  ld c,$14
  xor a
itementryblankcell:
  ld [hl+],a
  dec c
  jr nz,itementryblankcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,itementryblanknext
  inc h
itementryblanknext:
  dec b
  jr nz,itementryblankrow
itementrybatchdone:
  dec d
  jr z,itementrychromebegin
  ; Let the native VBlank/timer handlers run between batches.  They may clobber the
  ; copy registers, so preserve the next destination and remaining count explicitly,
  ; then mask them again before entering the following complete VBlank.
  push de
  push hl
  ei
itementrynextvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,itementrynextvisible
  di
  ldh a,[$FF44]
  cp $90
  jr c,itementrynextwaitblank
itementrynextlate:
  ldh a,[$FF44]
  cp $90
  jr nc,itementrynextlate
itementrynextwaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,itementrynextwaitblank
  pop hl
  pop de
  jr itementrybatch
itementrychromebegin:
  ; Native screen 1 draws box 4's rows, then box 14's Items header, and publishes
  ; the complete map only at the end.  The regional row publisher would otherwise
  ; expose names against a blank field for most of that interval.  Commit only the
  ; two static perimeters now; their text interiors remain blank until the existing
  ; completed-row/final-map publishers fill them.
  call itementrychrome
itementryblankdone:
  ei
  ret

itementrychrome:
  ; Header box 14: x=0, y=0, one row, width 4.
  ld hl,$9800
  ld c,$04
  call itementrytop
  ld hl,$9820
  ld a,$BE
  ld [hl],a
  ld de,$0005
  add hl,de
  ld a,$BF
  ld [hl],a
  ld hl,$9840
  ld c,$04
  call itementrybottom

  ; Item box 4: x=0, y=3, five rows, width 18.  Text keys are on rows
  ; 4,6,8,10,12; the vertical sides also cover their separator rows.
  ld hl,$9860
  ld c,$12
  call itementrytop
  ld hl,$9880
  ld b,$09
itementrychromeside:
  ld a,$BE
  ld [hl],a
  ld de,$0013
  add hl,de
  ld a,$BF
  ld [hl],a
  ld de,$000D
  add hl,de
  dec b
  jr nz,itementrychromeside
  ld hl,$99A0
  ld c,$12
itementrybottom:
  ld a,$BA
  ld [hl+],a
  ld a,$BD
itementrybottomcell:
  ld [hl+],a
  dec c
  jr nz,itementrybottomcell
  ld a,$BB
  ld [hl],a
  ret
itementrytop:
  ld a,$B8
  ld [hl+],a
  ld a,$BC
itementrytopcell:
  ld [hl+],a
  dec c
  jr nz,itementrytopcell
  ld a,$B9
  ld [hl],a
  ret

statusentry:
  ; Preserve the exact native Path shadow copier this hook replaces.
  rst $08
  db $11,$1F
  ; Most native status builds already have the LCD off. Direct pops from Items and the
  ; alternate screen-7 Floor page have exact native stack/hardware/state proofs and can
  ; keep their disjoint outgoing page visible: field uploads below rendezvous separately
  ; with VBlank. Other LCD-on returns retain the conservative full-screen interval until
  ; their own ownership is mapped.
  ldh a,[$FF40]
  bit 7,a
  jp z,statusdraw
  call itemexit
  jp c,statusdraw
  call statusready
statusdisable:
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
  call statusdraw
  ldh a,[$FF40]
  set 7,a
  ldh [$FF40],a
  ret
statusready:
  ; Screen-1 Action/Info return state 8 has already retired every visible BG row and
  ; will replay Items immediately after this intermediate screen-0 build. Its status
  ; shadow is disposable, and the final screen-1 entry clears it. Discard statusentry's
  ; local return address and return directly to its caller before the unknown-return
  ; branch disables the LCD. Ordinary Status/Items timing never enters this special arm.
  ld a,[$C1B3]
  cp $08
  jr z,statusreadydiscard
  ; Screen-20 Floor/Info return uses the same disposable intermediate screen-0
  ; build, but has its own transaction state so that the final Floor chrome can
  ; be published independently of the carried-Items return protocol.
  cp $09
  jr z,statusreadydiscard
  ; The alternate screen-7 unidentified-Pot Info replay also owns its final parent
  ; directly; its box-6 geometry is rebuilt by the independent state-$0B lifecycle.
  cp $0B
  jr z,statusreadydiscard
  cp $0A
  jr z,statusreadypot
  jr statusreadywait
statusreadypot:
  ; Normalize the proven Pot pop to the ordinary direct-entry contract while the
  ; screen-0 build is still disposable. The marker cells are the only additional
  ; Status-root proof; clear them during VBlank, then let the unchanged hot Items
  ; gate perform the normal four-batch retirement and chrome commit.
  call statusreadywait
  ld hl,$986F
  ld b,$04
  xor a
statusreadypotmarker:
  ld [hl+],a
  dec b
  jr nz,statusreadypotmarker
  ld [$C1B3],a
  ; The native replay increments this counter once between screen 0 and screen 1.
  ; Seed $FF so the unchanged direct-entry proof observes its ordinary zero.
  dec a
  ld [$C6A6],a
statusreadydiscard:
  inc sp
  inc sp
  ret
statusreadywait:
  ldh a,[$FF44]
  cp $90
  jr c,statuswaitblank
statuswaitvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,statuswaitvisible
statuswaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,statuswaitblank
  ret
itemexit:
  ; Common root-pop proof. C536 is the stale child slot after the native pop: screen 1
  ; denotes Items and screen 7 denotes the alternate standing-item Floor page.
  ld a,[$C534]
  and a
  jp nz,itemexitbad
  ld a,[$C535]
  and a
  jp nz,itemexitbad
  ld a,[$C6A3]
  and a
  jp nz,itemexitbad
  ld a,[$C536]
  cp $01
  jr z,itemexititems
  cp $07
  jp nz,itemexitbad

  ; Screen 7 has already been popped and the native producer has staged the exact
  ; Status-root descriptor. Its retained Floor/Action page uses menu tiles $43+ and the
  ; private Action slices $C7-$DE, so none of statusdraw's low private runs or structured
  ; Weapon/Shield fragments are visible. Direct Floor exits and exits after See share
  ; this predicate; C537 is deliberately not consulted because it is only stale history.
  ld a,[$C1B3]
  and a
  jp nz,itemexitbad
  ld a,[$C1B6]
  and a
  jp nz,itemexitbad
  ld a,[$C1B7]
  and a
  jp nz,itemexitbad
  ld a,[$C6A6]
  dec a
  jp nz,itemexitbad
  ld a,[$C6AC]
  inc a
  jp nz,itemexitbad
  ld a,[$C6BB]
  cp $04
  jp nz,itemexitbad
  ld a,[$C6DE]
  dec a
  jp nz,itemexitbad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jp nz,itemexitbad
  ld a,[hl+]
  cp $0A
  jp nz,itemexitbad
  ld a,[hl+]
  cp $02
  jp nz,itemexitbad
  ld a,[hl+]
  cp $12
  jp nz,itemexitbad
  ld a,[hl]
  cp $04
  jp nz,itemexitbad
  jr itemexithardware

itemexititems:
  ld a,[$C6AA]
  and a
  jp z,itemexitbad
  cp $15
  jp nc,itemexitbad
  ld b,a
  ld a,[$C6AC]
  cp b
  jr c,itemexithardware
  inc a
  jp nz,itemexitbad
  ld a,[$C1B7]
  dec a
  jp nz,itemexitbad
  jr itemexithardware
itemexithardware:
  ldh a,[$FF40]
  and $F8
  cp $E0
  jp nz,itemexitbad
  ldh a,[$FF42]
  and a
  jp nz,itemexitbad
  ldh a,[$FF43]
  and a
  jp nz,itemexitbad
  ldh a,[$FF4A]
  cp $80
  jp nz,itemexitbad
  ldh a,[$FF4B]
  cp $07
  jp nz,itemexitbad
  ; A completed initial Items entry can retain menu VWF phase 3 because its native
  ; Status-entry path has no same-screen redraw-tail call.  This exact pop proves the
  ; Item page is gone, so retire that stale transaction before any later direct Floor
  ; child can inherit it.
  xor a
  ld [$C1B6],a
  ld [$C1B7],a
itemexitaccepted:
  scf
  ret
itemexitbad:
  and a
  ret
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
  ldh a,[$FF40]
  bit 7,a
  jr z,uploaddirect
  call uploadready
  call uploadcopy
uploadlivedone:
  ei
  nop
  scf
  ret
uploaddirect:
  call uploadcopy
  scf
  ret
uploadcopy:
  ; Establish every live copy register only after uploadready has masked interrupts.
  ; The native VBlank handler does not preserve BC/DE/HL, so preparing these before
  ; the wait made the first upload phase-dependent and could extend it into line 3.
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
  ret
uploadready:
  ; Keep interrupts live through almost all ordinary scanout. Mask them at line 140,
  ; safely before the line-144 VBlank interrupt: waiting until line 143 left a real race
  ; in which that handler could run between the LY test and DI, delaying a cap-6 upload
  ; into line 3. Returning with IME clear reserves the complete VBlank for at most 7*16
  ; copied bytes.
  ldh a,[$FF44]
  cp $90
  jr c,uploadline140
uploadvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,uploadvisible
uploadline140:
  ldh a,[$FF44]
  cp $8C
  jr c,uploadline140
  di
  ; A long native interrupt may already have begun just before DI and return late in
  ; VBlank. Never treat that tail as a complete budget: wait through visible scanout
  ; with IME masked, then take the following VBlank from line 144.
  ldh a,[$FF44]
  cp $90
  jr c,uploadblank
uploadlate:
  ldh a,[$FF44]
  cp $90
  jr nc,uploadlate
uploadblank:
  ldh a,[$FF44]
  cp $90
  jr c,uploadblank
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
statusempty:
  db %s
widths:
  db %s
glyphs:
""" % (EN_CODES['T'], SHIFT_STRIDE, SLOT_PLUS, SLOT_SLASH, EN_CODES['-'],
       EN_CODES['F'], EN_CODES['G'], strength, experience, weapon, shield,
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Back'),
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Proceed'),
       ','.join('$%02X' % EN_CODES[ch] for ch in 'Stay'),
       ','.join('$%02X' % value for value in STATUS_EMPTY_MAP), width_bytes)


def runtime_labels(font=None):
    """Return emitted hook labels for instruction-exact runtime fixtures."""
    if font is None:
        font = propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in SLOT_CODES)
    return gbasm.assemble(_source(widths), CODE_AT)[1]


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
    if len(STATUS_EMPTY_ROWS) != 16 or any(
            len(row) != 20 for row in STATUS_EMPTY_ROWS):
        raise AssertionError('statusvwf: empty Status chrome is not 20x16')

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
    item_entry_index = bank + ITEM_ENTRY_INDEX - 1
    if bytes(buf[item_entry_index:item_entry_index + 2]) != b'\xFF\xFF':
        raise SystemExit('statusvwf: far index $%02X in bank %d is occupied' %
                         (ITEM_ENTRY_INDEX, FAR_BANK))
    buf[item_entry_index] = labels['itementry'] & 0xFF
    buf[item_entry_index + 1] = labels['itementry'] >> 8
    status_pre_index = bank + STATUS_PRE_INDEX - 1
    if bytes(buf[status_pre_index:status_pre_index + 2]) != b'\xFF\xFF':
        raise SystemExit('statusvwf: far index $%02X in bank %d is occupied' %
                         (STATUS_PRE_INDEX, FAR_BANK))
    buf[status_pre_index] = labels['statusfloorpre'] & 0xFF
    buf[status_pre_index + 1] = labels['statusfloorpre'] >> 8

    hook = _off(*HOOK)
    if bytes(buf[hook:hook + len(HOOK_OLD)]) != HOOK_OLD:
        raise SystemExit('statusvwf: hook at %d:$%04X changed' % HOOK)
    buf[hook:hook + 3] = bytes((0xD7, FAR_INDEX, FAR_BANK))

    item_entry_hook = _off(*ITEM_ENTRY_HOOK)
    if bytes(buf[item_entry_hook:item_entry_hook + len(ITEM_ENTRY_OLD)]) != ITEM_ENTRY_OLD:
        raise SystemExit('statusvwf: Item-entry hook at %d:$%04X changed' %
                         ITEM_ENTRY_HOOK)
    buf[item_entry_hook:item_entry_hook + len(ITEM_ENTRY_OLD)] = bytes(
        (0xD7, ITEM_ENTRY_INDEX, FAR_BANK, 0x00, 0x00, 0x00))

    if notes is not None:
        notes.append('statusvwf: full Strength/Experience labels and seven live status '
                     'values use approved proportional glyphs in 40 private low-page '
                     'tiles; exact Status-to-Items entry retires only visible BG rows '
                     '0-15, precommits empty box chrome, and preserves the Window; exact '
                     'Items-to-Status pops keep LCD on with nine bounded field uploads; '
                     'exact screen-7 Floor exits prepublish empty Status chrome before '
                     'those same bounded uploads; '
                     'admitted Action B restores its Item/Floor parent and input state '
                     'without replay; exact screen-1/screen-7/screen-20 Info and carried-Pot '
                     'returns suppress only their disposable Status reconstruction; '
                     'unknown LCD-on returns retain the conservative path')
