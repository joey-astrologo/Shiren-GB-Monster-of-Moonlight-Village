#!/usr/bin/env python3
"""Approved-font VWF names on the rankings board.

The rankings drawer in bank 31 stages six name bytes at ``$C6E3`` and calls ``$4A5F``
to write them into one of five six-cell shadow fields.  Unlike the menu transition,
the real title-screen route reaches that writer with the LCD enabled.  This patch keeps
that VBlank queue path, but packs its native 4+4+1 transfer as identical overlapping
windows so each proportional name owns exactly five physical planes.

The complete settled screen is one allocation at ``$80-$A6``: five tiles for
``Rankings``, three shared tiles apiece for ``Easy``/``Norm.``/``Hard``, and five tiles
for each of five names.  The native clear/status graphics at ``$B7`` and ``$CB-$D2``
are disjoint while the board is visible.  The earlier category selector temporarily
uses ``$C0-$CB``; the cartridge's LCD-off native font loader restores that whole slice
before any result map is revealed, and restores ``$80-$D2`` again before a title or
Adventure map is revealed.

Eligibility remains a WHOLE-PAGE decision.  Before any shared VWF plane is uploaded or
any row is drawn, all five 12-byte rank records are checked and the result is held for the
entire page.  A page containing even one code outside the name picker's approved English
page delegates to the original bank-31 writer through its existing far entry.  Thus old
Japanese saves remain byte-identical and a page can never display raw kana while the same
tile IDs hold composed pixels.

Only the header, difficulty labels and six-cell name fields are replaced.  Score, floor,
count, icons and every other fixed cell continue through the original rankings renderer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
import menuvwf
import propvwf


BANKSZ = 0x4000
FAR_BANK = 0x20
FAR_INDEX = 0x0B
ENTRY_AT = 0x400C
ENTRY_LIMIT = 0x4100

# The queue uploader originally landed at bank 32:$4362 because that looked like an $FF
# run.  It overwrote eight live trailing bytes of name6's new-game template and froze a
# fresh game on the village card.  Neither auxiliary routine needs the bank-32 glyph
# table, so both now live in pool.py's explicitly reserved bank-33 CODE_ORG..STUBS arena.
# Their byte ranges are asserted below; no filler scan is treated as ownership evidence.
# menuvwf owns bank 33's final far index and forwards modes 2/3 here.
AUX_BANK = menuvwf.START_AUX_BANK
AUX_INDEX = menuvwf.START_AUX_INDEX
VALIDATE_AT = menuvwf.RANK_VALIDATE_AT
VALIDATE_LIMIT = menuvwf.RANK_UPLOAD_AT
UPLOAD_AT = menuvwf.RANK_UPLOAD_AT
UPLOAD_LIMIT = menuvwf.START_BLANK_AT
TRANSITION_BANK = 0x2B        # pool bank 43: reader ends $405A, text starts $4100
TRANSITION_INDEX = 0x05
TRANSITION_AT = 0x405A
TRANSITION_LIMIT = 0x4100
# Dedicated screen-manager helper in the next otherwise-unused text-pool bank.  It owns
# the complete Rankings allocation and the ROM-backed native-font restore; no VRAM bank
# or unproven WRAM snapshot is involved.
MANAGER_BANK = menuvwf.RANK_SCREEN_BANK
MANAGER_INDEX = 0x07
MANAGER_PREPARE_INDEX = 0x09
MANAGER_AT = menuvwf.RANK_CATEGORY_LIMIT
MANAGER_LIMIT = 0x4400
PAGE_PREPARE_AT = 0x4671
PAGE_PREPARE_OLD = bytes.fromhex('cde519')
PAGE_RETURN = 0x46AC
PAGE_RETURN_OLD = bytes.fromhex('e1d1c1f1c9')
PAGE_FINISH_AT = 0x42DB       # first bytes of box 13, redirected to box 12 by build.py
PAGE_FINISH_OLD = bytes.fromhex('253110791f000017172b')

RANK_BANK = 31
RANK_CALL = 0x4A58
OLD_CALL = bytes.fromhex('cd5f4a')
RAW_INDEX = 0x11                 # existing bank-31 far entry -> original $4A5F writer
RAW_ENTRY = 0x4A5F

POOL_BASE = 0x8E
STATIC_POOL_BASE = 0x80
STATIC_POOL_END = POOL_BASE
ROWS = 5
# Six approved picker characters paint at most five tiles with the production Dot font.
# The sixth map cell stays blank (or is replaced by the native clear/status graphic), so
# the five name rows use exactly $8E-$A6.  $80-$8D belong to the same screen manager's
# deduplicated Rankings header and Easy/Norm./Hard labels.
TILES_PER_ROW = 5
RECORD_STRIDE = 12
NAME_BYTES = 6

# Shared proven-free menu/composer scratch.  Rankings drawing is not concurrent with a
# menu-row composition; the menu allocator is reset on its next font upload.
S_ROW = 0xC0CC
S_PEN = 0xC0CD
S_LEFT = 0xC0CE
S_DEST = 0xC0D1                 # two bytes
S_WIDTH = 0xC0D3
S_BASE = 0xC0D4


def _off(bank, addr):
    return bank * BANKSZ + (addr - BANKSZ)


def _static_tile_data(font):
    """Build the one screen-scoped header/difficulty raster, deduplicating labels."""
    chunks = []
    for text, expected_tiles in (('Rankings', 5), ('Easy', 3),
                                 ('Norm.', 3), ('Hard', 3)):
        extent = font.text_extent(text)
        tiles = [bytearray(16) for _ in range((extent + 7) >> 3)]
        pen = 0
        for ch in text:
            glyph = font.glyphs[ch]
            for y, bits in enumerate(glyph):
                for x in range(8):
                    if not bits & (0x80 >> x):
                        continue
                    pixel = pen + x
                    if pixel >= len(tiles) * 8:
                        continue
                    tile = tiles[pixel >> 3]
                    mask = 0x80 >> (pixel & 7)
                    tile[y * 2] |= mask
                    tile[y * 2 + 1] |= mask
            pen += font.advance(ch)
        if len(tiles) != expected_tiles:
            raise SystemExit('rankvwf: static %r needs %d tiles, expected %d' %
                             (text, len(tiles), expected_tiles))
        chunks.extend(tiles)
    data = b''.join(bytes(tile) for tile in chunks)
    assert len(data) == (STATIC_POOL_END - STATIC_POOL_BASE) * 16
    return data


def _assert_name_extent(font):
    """Prove every six-code page admitted by VALIDATE_SRC fits five physical tiles."""
    allowed = tuple(range(0x43)) + (0x7C, 0x7E, 0x7F, 0x80)
    code_to_char = {code: ch for ch, code in propvwf.EN_CODES.items()}
    missing = [code for code in allowed if code not in code_to_char]
    if missing:
        raise SystemExit('rankvwf: validator admits codes absent from approved font: %s'
                         % ' '.join('$%02X' % code for code in missing))
    max_advance = max(font.advance(code_to_char[code]) for code in allowed)
    final_extents = []
    for code in allowed:
        ch = code_to_char[code]
        glyph = font.glyphs[ch]
        ink = [x for x in range(8)
               if any(row & (0x80 >> x) for row in glyph)]
        final_extents.append(max(ink) + 1 if ink else font.advance(ch))
    worst = (NAME_BYTES - 1) * max_advance + max(final_extents)
    if worst > TILES_PER_ROW * 8:
        raise SystemExit('rankvwf: approved six-code name can paint %dpx, beyond the '
                         '%d-tile allocation' % (worst, TILES_PER_ROW))


def manager_src(font):
    data = _static_tile_data(font)
    native_header = bytes(propvwf.EN_CODES[ch] for ch in 'Rankings')
    return MANAGER_SRC % (menuvwf.START_AUX_INDEX, menuvwf.START_AUX_BANK,
                          ','.join('$%02X' % value for value in data),
                          ','.join('$%02X' % value for value in native_header))


VALIDATE_SRC = """
validate:
  ld h,d
  ld l,e
  ld a,[$C0CC]
  and a
  jr z,vstart
  ld bc,$FFF4
vback:
  add hl,bc
  dec a
  jr nz,vback
vstart:
  ld b,$05
vrecord:
  push hl
  ld c,$06
vchar:
  ld a,[hl+]
  cp $FF
  jr z,vnext
  cp $43
  jr c,vok
  cp $7C
  jr z,vok
  cp $7E
  jr c,vbad
  cp $81
  jr c,vok
vbad:
  ; rankprepare performs the authoritative complete-page scan before any shared VWF
  ; plane is uploaded. Record the native fallback for every row and final publication.
  ld a,$14
  ld [$C0D7],a
  pop hl
  scf
  ret
vok:
  dec c
  jr nz,vchar
vnext:
  pop hl
  ld de,$000C
  add hl,de
  dec b
  jr nz,vrecord
  and a
  ret
"""

UPLOAD_SRC = """
upload:
waitq:
  ld a,[$C11A]
  and a
  jr z,arm
  call $06F7
  jr waitq
arm:
  ld a,[$C0D4]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  ; LCDC uses signed tile IDs: $00-$7F start at $9000, while $80-$FF wrap
  ; to $8800.  After x16, (high XOR $08)+$88 expresses both halves.
  xor $08
  add a,$88
  ld h,a
  ld a,[$C000]
  ld [$C0D5],a
  ld a,[$C001]
  ld [$C0D6],a
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  push hl
  ; The native consumer always copies 4+4+1 tiles.  Feed it overlapping windows
  ; 0..3, 1..4 and 4 so a five-tile name owns only five unique physical planes.
  ld de,$0010
  add hl,de
  ld a,l
  ld [$C048],a
  ld a,h
  ld [$C049],a
  ld de,$0030
  add hl,de
  ld a,l
  ld [$C08A],a
  ld a,h
  ld [$C08B],a
  pop hl
  ld a,$0A
  ld [$C11A],a
armed:
  call $06F7
  ld a,[$C0D5]
  ld [$C000],a
  ld a,[$C0D6]
  ld [$C001],a
  ld a,[$C0D1]
  ld l,a
  ld a,[$C0D2]
  ld h,a
  ld a,[$C0D4]
  ld b,$05
shadow:
  ld [hl+],a
  inc a
  dec b
  jr nz,shadow
  ret
"""


MANAGER_SRC = """
rankmanager:
  cp $01
  jr z,staticmap
  cp $02
  jp z,nativerestore
  cp $03
  jp z,packpayload
  ret

staticmap:
  ; Any raw name makes this a genuinely native whole-page fallback.  The generic menu
  ; renderer has already replaced the eight-cell header map and may have painted planes
  ; which a legacy name itself references. rankprepare already restored every native
  ; plane and skipped the static VWF upload; restore the fixed-width header map before
  ; publishing. Supported English pages take the unified proportional path below.
  ld a,[$C0D7]
  cp $14
  jr nz,staticvwf
  ld hl,nativeheader
  ld de,$C326
  ld b,$08
  call copybytes
  ret
staticvwf:
  ; Reassert every screen-owned static map cell after the native board drawer.  Empty
  ; difficulty rows (Village Exit) stay native; populated Kuyo rows select one of the
  ; three shared rasters from their actual first character.
  ld hl,$C326
  ld a,$80
  call write5
  xor a
  ld [hl+],a
  ld [hl+],a
  ld [hl],a
  ld hl,$C3A3
  call writedifficulty
  ld hl,$C403
  call writedifficulty
  ld hl,$C463
  call writedifficulty
  ld hl,$C4C3
  call writedifficulty
  ld hl,$C523
  call writedifficulty
  ; Five name tiles leave a sixth fixed-width cell.  Preserve row 1's native clear icon;
  ; clear only the ordinary trailing cells on later rows.
  ld hl,$C392
  ld a,[hl]
  cp $CB
  jr z,firstnative
  cp $CF
  jr z,firstnative
  xor a
  ld [hl],a
firstnative:
  xor a
  ld [$C3F2],a
  ld [$C452],a
  ld [$C4B2],a
  ld [$C512],a
  ret

writedifficulty:
  ld a,[hl]
  cp $0F
  jr z,diffeasy
  cp $18
  jr z,diffnorm
  cp $12
  ret nz
  ld a,$8B
  jr diffwrite
diffeasy:
  ld a,$85
  jr diffwrite
diffnorm:
  ld a,$88
diffwrite:
  ld b,$03
  call writeloop
  xor a
  ld [hl+],a
  ld [hl],a
  ret

write5:
  ld b,$05
writeloop:
  ld [hl+],a
  inc a
  dec b
  jr nz,writeloop
  ret

rankprepare:
  push af
  push bc
  push de
  push hl
  ; This replaces the native call at 31:$4671.  LCD-on title Rankings and LCD-off
  ; rescued-child results share the same restore/static work, without waiting on LY
  ; while the display is off.  Run the replaced multiplication exactly once now:
  ; FF90=C6AC and FF91=12 on entry, and the native caller consumes FF90's product.
  call $19E5
  ldh a,[$FF40]
  ld e,a
  call nativerestore
  push de
  ; Decide whole-page eligibility before any VWF plane is uploaded.  C6AC selects the
  ; current 60-byte page at D61B; FF90 is the native C6AC*12 result, and validator mode
  ; 2 scans all five records from row zero.
  ld a,$12
  ld [$C0D7],a
  xor a
  ld [$C0CC],a
  ldh a,[$FF90]
  ld e,a
  ld d,$00
  ld hl,$D61B
  add hl,de
  ld d,h
  ld e,l
  ld a,$02
  rst $10
  db $%02X,$%02X
  jr c,skipstatic
  ld hl,staticdata
  ld de,$8800
  ld bc,$00E0
staticcopy:
  ld a,[hl+]
  ld [de],a
  inc de
  dec bc
  ld a,b
  or c
  jr nz,staticcopy
skipstatic:
  pop de
  bit 7,e
  jr z,preparedone
  ld a,e
  set 3,a
  ld [$C110],a
  ldh [$FF40],a
preparedone:
  pop hl
  pop de
  pop bc
  pop af
  ret

nativerestore:
  ; The complete native menu-font loader restores $00-$D2.  If the LCD is on, disable
  ; only in VBlank; callers decide whether and which hidden/finished map is selected.
  ldh a,[$FF40]
  bit 7,a
  jr z,restoredark
restorewait:
  ldh a,[$FF44]
  cp $90
  jr c,restorewait
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
restoredark:
  rst $10
  db $33,$0D
  ret

packpayload:
  ; Preserve logical tile 4 in slot 3, then make slot 2 the contiguous 1..4 window.
  ld hl,$C04A
  ld de,$C08C
  ld b,$10
  call copybytes
  ld hl,$C04A
  ld de,$C07A
  ld b,$10
  call copybytes
  ld hl,$C018
  ld de,$C04A
  ld b,$30
copybytes:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,copybytes
  ret
staticdata:
  db %s
nativeheader:
  db %s
"""


# The Rankings screen temporarily borrows private tile IDs.  Its native fixed fields
# continue to use the VBlank queue between name rows, so this transaction displays
# the title-prepared blank $9C00 BG map instead of disabling the LCD.  The queue remains
# live while all populated rows rebuild $9800; the final writer flips back during VBlank.
TRANSITION_SRC = """
rankupload:
  cp $03
  jr z,rankdirect
  cp $02
  jr z,rankstart
  and a
  jr nz,rankfinish
  ld a,$03
  rst $10
  db $%02X,$%02X
  ret
rankstart:
  push bc
  push de
  push hl
  ld a,[$C0D7]
  and a
  jr nz,rsdone
  ld a,[$C0CC]
  and a
  jr nz,rsdone
  ld a,$12
  ld [$C0D7],a
  ldh a,[$FF40]
  set 3,a
  ld [$C110],a
  ldh [$FF40],a
rsdone:
  pop hl
  pop de
  pop bc
  ret
rankfinish:
  ld a,[$C0D7]
  cp $12
  jr z,rffinalize
  cp $14
  ret nz
rffinalize:
rfqueue:
  ld a,[$C11A]
  and a
  jr z,rfready
  call $06F7
  jr rfqueue
rfready:
  ; Drain any last menu/native transfer before the manager restores legacy planes.  A
  ; late queue consumer must never repaint a plane after the native restore.
  ld a,$01
  rst $10
  db $%02X,$%02X
  ; The page loop has finished every shadow write, while the native screen copier would
  ; still reveal $9800 over several frames.  Disable at VBlank, publish that complete
  ; shadow synchronously, then select $9800 again in the same blank interval.  Rescue
  ; exits enter the Rankings result with the LCD already disabled, so that route must
  ; skip the LY wait -- an off LCD never reaches VBlank and used to deadlock here.
  ldh a,[$FF40]
  bit 7,a
  jr z,rfpublish
rfblank:
  ldh a,[$FF44]
  cp $90
  jr c,rfblank
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
rfpublish:
  xor a
  rst $10
  db $%02X,$%02X
  ldh a,[$FF40]
  res 3,a
  set 7,a
  ld [$C110],a
  ldh [$FF40],a
  ret
rankdirect:
  ; The ordinary title-menu Rankings route uploads each composed name through the
  ; game's VBlank queue.  The rescue-result route has deliberately turned the LCD off,
  ; so copy the same five private tiles directly instead of arming a queue whose
  ; consumer cannot run.  Slot 1 contains 0..3 and slot 2 contains 1..4.
  ld a,[$C0D4]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  xor $08
  add a,$88
  ld h,a
  ld de,$C008
  ld b,$40
rdslot1:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,rdslot1
  ; Skip slot 2's repeated tiles 1..3 and copy only its last tile (tile 4).
  ld de,$C07A
  ld b,$10
rdslot2:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,rdslot2
  ret
""" % (AUX_INDEX, AUX_BANK,
         MANAGER_INDEX, MANAGER_BANK,
         menuvwf.ITEM_PUBLISH_INDEX, menuvwf.ITEM_PAGE_BANK)


PAGE_FINISH_SRC = """
rankpagefinish:
  ld a,$01
  rst $10
  db $%02X,$%02X
  pop hl
  pop de
  pop bc
  pop af
  ret
""" % (TRANSITION_INDEX, TRANSITION_BANK)


def page_finish():
    return gbasm.assemble(PAGE_FINISH_SRC, PAGE_FINISH_AT)

def _entry_src(labels):
    """Entry/compositor.  Calls the already-installed proportional menu primitives."""
    return """
rankname:
  push af
  push bc
  push de
  push hl
  ld a,l
  ld [$C0D1],a
  ld a,h
  ld [$C0D2],a
  call rowbase
  jr c,raw
  ; rankprepare made the sole whole-page decision before uploading any shared plane.
  ; Every row follows that immutable state; supported and native renderers cannot mix.
  ld a,[$C0D7]
  cp $12
  jr nz,raw
  call compose
  pop hl
  pop de
  pop bc
  pop af
  ret
raw:
  pop hl
  pop de
  pop bc
  pop af
  rst $10
  db $11,$1F
  ret

rowbase:
  push de
  ld bc,$C38D
  ld e,$00
rowloop:
  ld a,h
  cp b
  jr nz,rownext
  ld a,l
  cp c
  jr z,rowfound
rownext:
  inc e
  ld a,e
  cp $05
  jr z,rowbad
  ld a,c
  add a,$60
  ld c,a
  jr nc,rowloop
  inc b
  jr rowloop
rowbad:
  pop de
  scf
  ret
rowfound:
  ld a,e
  ld [$C0CC],a
  ld b,a
  add a,a
  add a,a
  add a,b
  add a,$%02X
  ld [$C0D4],a
  pop de
  and a
  ret

compose:
  ld hl,$C008
  call $%04X
  ld hl,$C04A
  call $%04X
  xor a
  ld [$C0CD],a
  ld a,$06
  ld [$C0CE],a
  ld bc,$C6E3
cloop:
  ld a,[$C0CE]
  and a
  jp z,composed
  ld a,[bc]
  cp $FF
  jp z,composed
  push bc
  ld c,a
  cp $5C
  jr nz,codeok
  ld c,$AF
codeok:
  call $%04X
  ld [$C0D3],a
  ld a,c
  call $%04X
  srl a
  ld h,a
  ld l,$00
  jr nc,sloteven
  ld l,$80
sloteven:
  ld a,[$C0CD]
  and $07
  swap a
  add a,l
  ld l,a
  jr nc,slotready
  inc h
slotready:
  ld de,$4400
  add hl,de
  ld a,[$C0CD]
  srl a
  srl a
  srl a
  push af
  call $%04X
  call $%04X
  pop af
  inc a
  cp $06
  jr nc,nospill
  call $%04X
  call $%04X
nospill:
  ld a,[$C0D3]
  ld b,a
  ld a,[$C0CD]
  add a,b
  ld [$C0CD],a
  pop bc
  inc bc
  ld a,[$C0CE]
  dec a
  ld [$C0CE],a
  jp cloop
composed:
  ; Repack the flat compositor output as the queue's overlapping 0..3, 1..4, 4 windows.
  ld a,$03
  rst $10
  db $%02X,$%02X
  ; Normal Rankings pages run with the LCD on and use uploader mode 0.  Rescue-result
  ; pages arrive LCD-off; mode 3 performs the equivalent direct VRAM copy in the
  ; transition helper, avoiding a wait on the disabled VBlank consumer.
  ldh a,[$FF40]
  bit 7,a
  ld a,$00
  jr nz,composedcall
  ld a,$03
composedcall:
  rst $10
  db $%02X,$%02X
  ret
""" % (POOL_BASE,
         labels['zero64'], labels['zero64'],
         labels['widthfor'], labels['slotfor'], labels['payload'], labels['or8'],
         labels['payload'], labels['or8'],
         MANAGER_INDEX, MANAGER_BANK,
         TRANSITION_INDEX, TRANSITION_BANK)


def install(buf, notes=None, font=None):
    if font is None:
        raise SystemExit('rankvwf: proportional rankings require the approved font')
    _assert_name_extent(font)

    fei_prompt_rows = menuvwf._box_row_starts(buf, 32)
    if len(fei_prompt_rows) != 1:
        raise SystemExit('rankvwf: Fay prompt box 32 no longer has one row')
    fei_prompt_y = menuvwf._box_geometry(buf, 32)[1]
    rank_header_x = menuvwf._box_geometry(buf, 41)[0]
    menu_code, menu_labels = gbasm.assemble(
        menuvwf._proportional_src(font, fei_prompt_y, rank_header_x),
        menuvwf.PROP_CODE_AT)
    menu_at = _off(FAR_BANK, menuvwf.PROP_CODE_AT)
    if bytes(buf[menu_at:menu_at + len(menu_code)]) != menu_code:
        raise SystemExit('rankvwf: proportional menuvwf primitives are not installed')

    validator, validate_labels = gbasm.assemble(VALIDATE_SRC, VALIDATE_AT)
    uploader, upload_labels = gbasm.assemble(UPLOAD_SRC, UPLOAD_AT)
    transition, transition_labels = gbasm.assemble(TRANSITION_SRC, TRANSITION_AT)
    manager, manager_labels = gbasm.assemble(manager_src(font), MANAGER_AT)
    page_code, page_labels = page_finish()
    entry_src = _entry_src(menu_labels)
    entry, entry_labels = gbasm.assemble(entry_src, ENTRY_AT)
    if ENTRY_AT + len(entry) > ENTRY_LIMIT:
        raise SystemExit('rankvwf: entry needs %d bytes, only %d available'
                         % (len(entry), ENTRY_LIMIT - ENTRY_AT))
    if VALIDATE_AT + len(validator) > VALIDATE_LIMIT:
        raise SystemExit('rankvwf: validator needs %d bytes, only %d available'
                         % (len(validator), VALIDATE_LIMIT - VALIDATE_AT))
    if UPLOAD_AT + len(uploader) > UPLOAD_LIMIT:
        raise SystemExit('rankvwf: uploader needs %d bytes, only %d available'
                         % (len(uploader), UPLOAD_LIMIT - UPLOAD_AT))
    if TRANSITION_AT + len(transition) > TRANSITION_LIMIT:
        raise SystemExit('rankvwf: transition helper needs %d bytes, only %d available'
                         % (len(transition), TRANSITION_LIMIT - TRANSITION_AT))
    if MANAGER_AT + len(manager) > MANAGER_LIMIT:
        raise SystemExit('rankvwf: screen manager needs %d bytes, only %d available'
                         % (len(manager), MANAGER_LIMIT - MANAGER_AT))
    if len(page_code) != len(PAGE_FINISH_OLD):
        raise SystemExit('rankvwf: page finalizer is %d bytes, reserved span is %d'
                         % (len(page_code), len(PAGE_FINISH_OLD)))

    for bank, addr, data, what in ((FAR_BANK, ENTRY_AT, entry, 'entry'),
                                   (AUX_BANK, VALIDATE_AT, validator, 'validator'),
                                   (AUX_BANK, UPLOAD_AT, uploader, 'uploader'),
                                   (TRANSITION_BANK, TRANSITION_AT, transition,
                                    'transition helper'),
                                   (MANAGER_BANK, MANAGER_AT, manager,
                                    'screen manager')):
        at = _off(bank, addr)
        if any(value != 0xFF for value in buf[at:at + len(data)]):
            raise SystemExit('rankvwf: bank %d %s region at $%04X is not free'
                             % (bank, what, addr))
        buf[at:at + len(data)] = data

    index = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if bytes(buf[index:index + 2]) != b'\xff\xff':
        raise SystemExit('rankvwf: far index $%02X in bank %d is already used'
                         % (FAR_INDEX, FAR_BANK))
    buf[index] = entry_labels['rankname'] & 0xFF
    buf[index + 1] = entry_labels['rankname'] >> 8

    transition_index = (_off(TRANSITION_BANK, 0x4000) + TRANSITION_INDEX - 1)
    if buf[_off(TRANSITION_BANK, 0x4000)] != TRANSITION_BANK:
        raise SystemExit('rankvwf: bank %d pool code is not installed' % TRANSITION_BANK)
    if bytes(buf[transition_index:transition_index + 2]) != b'\xff\xff':
        raise SystemExit('rankvwf: far index $%02X in bank %d is already used'
                         % (TRANSITION_INDEX, TRANSITION_BANK))
    buf[transition_index] = transition_labels['rankupload'] & 0xFF
    buf[transition_index + 1] = transition_labels['rankupload'] >> 8

    if buf[_off(MANAGER_BANK, 0x4000)] != MANAGER_BANK:
        raise SystemExit('rankvwf: bank %d pool code is not installed' % MANAGER_BANK)
    for index, label in ((MANAGER_INDEX, 'rankmanager'),
                         (MANAGER_PREPARE_INDEX, 'rankprepare')):
        at = _off(MANAGER_BANK, 0x4000) + index - 1
        if bytes(buf[at:at + 2]) != b'\xff\xff':
            raise SystemExit('rankvwf: far index $%02X in bank %d is already used'
                             % (index, MANAGER_BANK))
        buf[at] = manager_labels[label] & 0xFF
        buf[at + 1] = manager_labels[label] >> 8

    prepare_at = _off(RANK_BANK, PAGE_PREPARE_AT)
    if bytes(buf[prepare_at:prepare_at + len(PAGE_PREPARE_OLD)]) != PAGE_PREPARE_OLD:
        raise SystemExit('rankvwf: Rankings page setup call at 31:$%04X changed'
                         % PAGE_PREPARE_AT)
    buf[prepare_at:prepare_at + 3] = bytes(
        (0xD7, MANAGER_PREPARE_INDEX, MANAGER_BANK))

    # menuvwf reserves an inert five-byte patch point in full-title row-0 allocation.
    # That transaction is already LCD-off, so restore borrowed planes before its rows
    # are rebuilt and before Adventure/Log maps can be published.
    _, start_finish_labels = gbasm.assemble(menuvwf.START_FINISH_SRC,
                                            menuvwf.START_FINISH_AT)
    restore_hook = start_finish_labels['rankrestorehook']
    restore_at = _off(menuvwf.START_FINISH_BANK, restore_hook)
    if bytes(buf[restore_at:restore_at + 5]) != bytes(5):
        raise SystemExit('rankvwf: title restore hook at %d:$%04X is not reserved'
                         % (menuvwf.START_FINISH_BANK, restore_hook))
    buf[restore_at:restore_at + 5] = bytes(
        (0x3E, 0x02, 0xD7, MANAGER_INDEX, MANAGER_BANK))

    page_at = _off(RANK_BANK, PAGE_FINISH_AT)
    if bytes(buf[page_at:page_at + len(PAGE_FINISH_OLD)]) != PAGE_FINISH_OLD:
        raise SystemExit('rankvwf: reserved page finalizer at 31:$%04X changed or was '
                         'packed over' % PAGE_FINISH_AT)
    buf[page_at:page_at + len(page_code)] = page_code
    page_return = _off(RANK_BANK, PAGE_RETURN)
    if bytes(buf[page_return:page_return + len(PAGE_RETURN_OLD)]) != PAGE_RETURN_OLD:
        raise SystemExit('rankvwf: rankings page return at 31:$%04X changed' % PAGE_RETURN)
    buf[page_return:page_return + len(PAGE_RETURN_OLD)] = bytes(
        (0xC3, PAGE_FINISH_AT & 0xFF, PAGE_FINISH_AT >> 8, 0x00, 0x00))

    if buf[_off(AUX_BANK, 0x4000)] != AUX_BANK:
        raise SystemExit('rankvwf: bank %d pool code is not installed' % AUX_BANK)
    at = _off(AUX_BANK, 0x4000) + AUX_INDEX - 1
    want_aux = menuvwf.START_AUX_AT
    if bytes(buf[at:at + 2]) != bytes((want_aux & 0xFF, want_aux >> 8)):
        raise SystemExit('rankvwf: bank %d far index $%02X does not point to menuvwf '
                         'auxiliary $%04X' % (AUX_BANK, AUX_INDEX, want_aux))

    raw_index = _off(RANK_BANK, 0x4000) + RAW_INDEX - 1
    if bytes(buf[raw_index:raw_index + 2]) != bytes((RAW_ENTRY & 0xFF,
                                                     RAW_ENTRY >> 8)):
        raise SystemExit('rankvwf: bank-31 far index $%02X no longer points to $%04X'
                         % (RAW_INDEX, RAW_ENTRY))
    call = _off(RANK_BANK, RANK_CALL)
    if bytes(buf[call:call + len(OLD_CALL)]) != OLD_CALL:
        raise SystemExit('rankvwf: expected original name-writer call at 31:$%04X'
                         % RANK_CALL)
    buf[call:call + 3] = bytes((0xD7, FAR_INDEX, FAR_BANK))

    if notes is not None:
        notes.append('rankvwf: unified Rankings allocation uses $80-$A6: five static '
                     'header tiles, nine deduplicated difficulty tiles and five private '
                     'queued tiles per name; '
                     'whole-page legacy-name fallback retains the original writer')
        notes.append('rankvwf: %d-byte entry at 32:$%04X + %d-byte validator at '
                     '33:$%04X + %d-byte uploader at 33:$%04X + %d-byte atomic '
                     'transition helper at %d:$%04X + %d-byte screen manager at '
                     '%d:$%04X + page finalizer 31:$%04X; LCD-on rows use the game '
                     'VBlank transfer queue and LCD-off rescue results copy five tiles '
                     'synchronously'
                     % (len(entry), ENTRY_AT, len(validator), VALIDATE_AT,
                        len(uploader), UPLOAD_AT, len(transition), TRANSITION_BANK,
                        TRANSITION_AT, len(manager), MANAGER_BANK, MANAGER_AT,
                        PAGE_FINISH_AT))
    return entry_labels, validate_labels, upload_labels


if __name__ == '__main__':
    raise SystemExit('rankvwf is installed by tools/build.py --dot-font')
