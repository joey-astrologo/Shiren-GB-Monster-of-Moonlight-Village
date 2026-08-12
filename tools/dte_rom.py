#!/usr/bin/env python3
"""The ROM side of DTE: the resident expander, its table bank, and the hook patches.

Decided 2026-07-29, after two facts the earlier plan did not have:

  * banks 32-63 of the expanded ROM are entirely $FF, so a table bank costs nothing and
    needs no verification -- unlike the WRAM gaps, which a static scan cannot clear.
  * byte 0 of every switchable bank holds that bank's own number. The ROM's own far-call
    trampoline reads it at 0:$079E to recover the caller's bank, so a resident routine
    can map the table over the caller and put it back with no WRAM shadow at all.

So the table lives in bank TABLE_BANK, direct-indexed by code (LEFT[c], RIGHT[c] on two
aligned pages, no arithmetic in the lookup), and only the ~120-byte expander has to be
resident. It goes in bank 0's $0062-$00FF padding: the gap between the joypad interrupt
vector and the cartridge header. Both of the ROM's checksums verify, so the nine non-$FF
bytes in there are authentic -- and every one of them is $FF with one or two bits cleared
($7F $FB $FB $EF $EF $FA $BF $EF $BF), which is unprogrammed mask-ROM fill, not data.

CODE SPACE. A DTE code has to be a byte the renderers do not already act on: not a
control code ($E0-$F0), not the terminator, not a combining mark ($79/$7A), and not a
letter English uses. That leaves three ranges (see DTE_RANGES) holding exactly 128 codes
-- separable in five compares, which is why the table is 128 pairs and not the 140 the
handoff assumed. The remaining 19 codes are English's scattered punctuation, which reuses
the ROM's native glyphs at $7C-$B2; compacting those into $43-$4C would free a single
$4D-$DF range of 147 and is the one upgrade left on the table.

UNTRANSLATED JAPANESE MUST NOT COLLIDE, and this is no longer a matter of taste. The
expander runs on every line the composer draws, including Japanese that was never
compressed, and a byte that happens to sit in the code space gets expanded into two.

That was carried for a long time as "the accepted cost", on the argument that the Latin
font is written over the kana tiles so Japanese is garbage either way. **The argument was
wrong, and it shipped a real bug**: expansion changes CELL counts, cell counts drive line
wrapping, and the dungeon's self-dismissing messages came and went too fast to read. Joey
found it by playing; no screenshot could see it, because it is a duration. An A/B against
a --no-dte build confirmed it.

So the code space is now chosen to be **bytes untranslated Japanese never uses at all** --
measured over the real script, not assumed -- and `build.check_no_jp_collision()` fails the
build if that stops being true. It costs yield (46 pairs at 28.2%, against 124 at 40.2%)
and every bank still fits with room to spare.

The constraint RELAXES as translation progresses: every string that stops being Japanese
frees the bytes it used. Re-run tools/dte_ranges.py to see what has opened up.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
import codec

CONTROL_MIN = codec.CONTROL_MIN      # $E0; the expander must never touch a control code

TABLE_BANK = 0x20           # first bank freed by the 1 MiB expansion
LEFT_PAGE = 0x41            # bank 32 $4100: LEFT[code]
RIGHT_PAGE = 0x42           # bank 32 $4200: RIGHT[code]

EXPANDER_ORG = 0x0062       # bank 0, just past the joypad interrupt vector
EXPANDER_END = 0x0100       # the cartridge header starts here

# dte_box does not fit in what the expander leaves of that padding, so it goes in the
# other resident hole: the 20 bytes of $00 at the very end of bank 0. $3FE0-$3FEB is NOT
# free -- it holds three `rst $10` far-call thunks, one of which 7:$505F calls -- so the
# region starts at $3FEC. Every 16-bit reference to $3FEC-$3FFF anywhere in the ROM was
# checked and all of them sit inside data blobs (bank 22 $432B's `call $3FFF` is
# surrounded by `rst $38` filler, bank 27 $624A's `ld bc,$3FFC` by graphics).
BOX_ORG = 0x3FEC
BOX_END = 0x3FFF            # NOT $4000 -- see below
BOX_FILL = 0x00             # what build.py must find there before overwriting

# $3FFF, the last byte of bank 0, is deliberately left out of BOX_END. An earlier cut of
# dte_box_hi was exactly 20 bytes and so ended with its `ret` sitting on $3FFF, and that
# ret did not return: the status screen went to a white screen and the CPU ended up
# spinning on `rst $38`, while the same bytes run clean in tools/gbemu.py. Moving the
# routine twelve bytes earlier -- changing nothing else -- fixed it outright.
#
# The mechanism is the fetch that runs off the end of the bank: the byte after $3FFF is
# $4000, which belongs to whichever bank is mapped, and during an expansion that is the
# TABLE bank. Whatever the exact semantics, the rule to keep is simple and costs one
# byte: resident code must not run to the last byte of bank 0.

# 31:$40E4 peeks a box row's FIRST byte to choose the left border glyph -- $84 -> $83,
# $86 -> $85, anything else -> $BE -- and then the row loop reads that same byte AGAIN as
# text. Both selectors are DTE codes, so a pair landing at offset 0 would silently redraw
# the border. No row in the base ROM starts with either, and teaching the drawer about it
# would mean hooking a second site, so compress() simply declines such a string.
BOX_FIRST_UNSAFE = (0x84, 0x86)

# Bytes free of English letters, of the combining marks, of the control range -- and of
# the LAYOUT GLYPHS a translation names with a `<$XX>` escape.
#
# $B3-$B6 is reserved for that last group, which is why the top range starts at $B7 and
# not at $B3. A `<$B6>` (the vertical bar that splits the status screen's two columns)
# is a byte the renderer has to reproduce EXACTLY, the same category as a control code
# or a combining mark -- and once 31:$4106 is hooked, a drawer that expands it draws two
# cells where the row budgeted one, runs the row past the box width, never reaches the
# terminator, and starts every following row of that box at the wrong byte. It took the
# status screen to a white screen: the ROM's own layout bytes are not decoration.
#
# Costs 4 of 128 codes. build.check_escapes() enforces the other half of the rule, so a
# future escape that lands in the code space is a build error and not a white screen.
#
# THESE RANGES ARE MEASURED, NOT CHOSEN. They are the bytes no untranslated string in
# script.json contains, intersected with what the renderers allow -- see the module
# docstring for why that matters and what it cost to learn. `tools/dte_ranges.py` recomputes
# them; `build.check_no_jp_collision()` fails the build if they drift.
#
# Three ranges is also the most the expander can afford: its generated range test is five
# compares at 158 bytes, which is EXACTLY bank 0's padding. Four ranges is 166 and does not
# fit. If more codes are wanted, they have to come from a range that MERGES with one of
# these as translation frees bytes, not from a fourth.
# RE-MEASURED 2026-08-05, after session 7 corrected the extractor. The old top range
# $C4-$DF held $C8 and $DC, and 143 strings that had never been extracted turned out to
# use both -- they are `$EB` typewriter-PAUSE arguments in the ending farewells
# (11:$5ECB, 11:$60B8, 11:$60FC, 11:$616C). The bytes were always in the ROM and always
# went through the expander; nothing could see them, because "no untranslated string in
# script.json contains these" was measured against a script.json missing 7.9 KB.
#
# That is the standing hazard of this file's rule, and it is worth naming: the code space
# is measured against the SCRIPT, so it is only ever as sound as extraction coverage.
# `tools/coverage.py` is now the check that keeps that denominator honest.
#
# 46 codes -> 32, and the shape of the loss is set by `_is_dte_source`, not by the safe
# set. The last range emits no upper compare -- the caller has already excluded $E0 and up
# -- so the TOP RANGE MUST END AT $DF. $DC being unsafe therefore caps the top range at
# $DD-$DF, three codes, and the 19-code run $C9-$DB has to be spent as a middle range
# instead. Giving the last range an upper test would recover it and costs 4 bytes: 162
# against the 158 of bank 0 padding, so it does not fit, for the same reason a fourth
# range does not.
#
# The three largest safe runs that satisfy the abut rule: $C9-$DB (19), $B8-$C1 (10),
# $DD-$DF (3). $92-$99 is dropped -- it is 8 codes and there is no room for a fourth range.
#
# DO NOT TRUST `dte_ranges.py`'s "newly safe" list on its own -- it is a suggestion, not a
# measurement of the whole rule, and it named three ranges here that are all wrong:
#   $89-$90  `13:$4BD2` and `13:$4BF2` end in `<cE0:89>`. $89 is a control code's ARGUMENT
#            byte, and the tool only scans UNTRANSLATED strings, so it cannot see an
#            argument that survives into the English. build.check_no_jp_collision() can.
#   $B1, $82-$83  named by `<$B1>`/`<$82>` raw escapes in en.tsv (build.check_escapes()).
# In both cases the byte is one the renderer must reproduce exactly. Take a range only
# when the BUILD agrees, which is the check that sees translated strings too.
DTE_RANGES = ((0xB8, 0xC1), (0xC9, 0xDB), (0xDD, 0xDF))
DTE_CODES = [c for lo, hi in DTE_RANGES for c in range(lo, hi + 1)]


def _check_ranges():
    """The ranges must not contain any byte the inserter can emit as a literal.

    build.encode_en emits EN_CODES and nothing else -- except for `<$XX>` raw escapes,
    which can name any byte at all. Those are layout data the renderer acts on, so
    build.py has to treat them as segment barriers the same way it does control codes;
    encode_segments() re-checks per build in case a new escape lands in the range.
    """
    from latinfont import EN_CODES
    clash = sorted(set(EN_CODES.values()) & set(DTE_CODES))
    assert not clash, 'DTE ranges overlap English letters: %s' % (
        ' '.join('$%02X' % c for c in clash))
    assert not set(DTE_CODES) & set(codec.COMBINING), 'DTE ranges include a dakuten byte'
    assert max(DTE_CODES) < CONTROL_MIN, 'DTE ranges reach into the control codes'


_check_ranges()

LINE_BUF = 0xCF07           # the composer's line buffer
CLEAR_40CF = 0x32           # bytes 13:$40CF zeroes before the 18-cell loop
CLEAR_6884 = 0x36           # bytes 13:$6884 zeroes before the uncapped loop
OTHER_CODE = 0xCF43         # the first address past the buffer that belongs to someone

# The write guard stops one byte short of the SHORTER clear, not at $CF43. Both loops
# zero the buffer first and the composer reads those zeros as the end of the line, so a
# write into the uncleared gap would leave text with no terminator after it -- which the
# $CF43 bound would have allowed. Stopping at $CF37 keeps $CF38 zero for either loop.
LINE_END = (LINE_BUF & 0xFF) + min(CLEAR_40CF, CLEAR_6884) - 1
assert LINE_BUF + min(CLEAR_40CF, CLEAR_6884) <= OTHER_CODE
assert LINE_END == 0x38

def _is_dte_source():
    """Generate the range test from DTE_RANGES, so the two cannot disagree.

    Two bytes of compare per range boundary, walking upwards. The last range has no
    upper test because the caller has already excluded the control codes, which is why
    it must end exactly where they begin.
    """
    ranges = sorted(DTE_RANGES)
    assert ranges[-1][1] + 1 == CONTROL_MIN, 'the top DTE range must abut $E0'
    for (_, hi), (lo, _) in zip(ranges, ranges[1:]):
        assert hi < lo, 'DTE_RANGES must be disjoint and ascending'
    # The composer already excluded $E0 and up before calling, but the raw copy loops do
    # not -- they pass the terminator and every control code straight through. Without
    # this test `is_dte($FF)` falls past the last range and answers YES, so the
    # terminator would be "expanded" through the table. Costs four bytes once.
    lines = ['is_dte:',
             '        cp $%02X' % CONTROL_MIN,
             '        jr nc,is_dte_no']
    for i, (lo, hi) in enumerate(ranges):
        lines += ['        cp $%02X' % lo, '        jr c,is_dte_no']
        if i < len(ranges) - 1:
            lines += ['        cp $%02X' % (hi + 1), '        jr c,is_dte_yes']
    return '\n'.join(lines + ['is_dte_yes:', '        scf', '        ret',
                              'is_dte_no:', '        and a', '        ret'])


SOURCE = """
; =========================================================== is_dte
; a = a byte already known to be below $E0. Returns with carry SET if it is a
; DTE code. `and a` clears carry without touching a, and `cp` never writes a, so
; a survives either exit -- which is what lets the caller reuse it as the symbol.
; Generated from DTE_RANGES by _is_dte_source().
{IS_DTE}

; ========================================================= emit_lit
; Store one literal byte and charge it against the line.
;   a  = the byte, de = destination, b = cells still free
; Two independent bounds, because cells and bytes diverge:
;   * de < $CF38 is the hard one, and it is a BYTE bound, which is what a
;     character cap could not be: it holds however many bytes one pair expands
;     to, and it holds for a colliding Japanese byte too. $CF38 rather than
;     $CF43 because the composer reads the buffer's zeroes as the end of the
;     line, so the last write has to stay inside the shorter of the two clears.
;   * b is the width budget, and only real cells spend it.
; A combining mark costs a byte and no cell. The original loop at 13:$40F3 said
; that by peeking the NEXT source byte and skipping `dec b` on the base
; character; charging the mark itself instead is equivalent (a mark always
; follows a base character and two never adjoin) and needs no lookahead, which
; is what lets the rule survive expansion -- the "next byte" may now live inside
; a table entry rather than in the source at all.
; c is free scratch: the composer pushes bc, uses b as the counter, and never
; reads c; both control-code handlers push bc before touching it.
emit_lit:
        ld c,a
        ld a,d
        cp {LINE_PAGE}             ; only the $CF07 line buffer gets the address bound
        jr nz,emit_nobound         ; a raw loop's buffer is elsewhere; it had no bound
        ld a,e
        cp {LINE_END}             ; LINE_END: the composer's zeroes must survive
        ld a,c                  ; an 8-bit ld leaves the cp's flags alone
        ret nc                  ; buffer full: drop the byte
emit_nobound:
        ld a,c
        cp $79
        jr z,emit_store
        cp $7a
        jr z,emit_store
        inc b                   ; test b without disturbing a
        dec b
        ret z                   ; no cells left on the line
        dec b                   ; charge the cell BEFORE the store, so that the
emit_store:                     ; mark path can share the store and save 3 bytes
        ld [de],a               ; (ld [de],a does not read flags)
        inc de
        ret

; ========================================================= dte_emit
; The composer's literal store, replaced.
;   a  = source byte, already known not to be a control code
;   de = destination, advanced past everything written
;   b  = cells still free, charged per EXPANDED cell
;   hl = source pointer, preserved
; A literal never switches banks. A DTE code maps the table over the caller for
; the length of one expansion and puts the caller back afterwards, recovering
; its bank number from [$4000] the way 0:$079E does. di/ei matches the ROM's own
; far-call trampoline, which does the same around every bank write at 0:$07AF --
; and since all banked code including the composer is reached through it, IME is
; on by the time we get here.
;
; `dte_emit_yes` is the same routine entered with is_dte already answered YES. It
; exists for dte_box, which has to make that test itself so it can hand a
; non-code byte to bank 31's own handler instead of to emit_lit.
dte_emit:
        call is_dte
        jr nc,emit_lit
dte_emit_yes:
        push hl                 ; the source pointer
        ld l,a                  ; l = the code
        ld a,[$4000]            ; a = the caller's own bank number
        ld h,a
        push hl                 ; hold code and caller bank across the expansion
        di
        ld a,{TABLE_BANK}             ; TABLE_BANK
        ld [$3f00],a
        ld a,l
        call expand
        pop hl
        ld a,h
        ld [$3f00],a
        ei
        pop hl
        ret

; =========================================================== expand
; a = symbol, de = destination, b = cells. TABLE_BANK is mapped.
; Recursive, so a code may expand to other codes. Depth is whatever the table
; build reports; each level costs 4 bytes of stack.
expand:
        call is_dte
        jr nc,emit_lit
        ld l,a
        ld h,{RIGHT_PAGE}             ; RIGHT_PAGE
        ld a,[hl]
        push af                 ; hold the right symbol
        dec h                   ; -> LEFT_PAGE
        ld a,[hl]
        call expand             ; left subtree
        pop af
        jr expand               ; right subtree, as a tail call

; ============================================================ loop2
; 13:$6893's copy loop, moved here whole.
;
; It could not be patched in place: threading a 3-byte call through it needed one
; byte more than the loop had, and the byte after it is the entry point of its own
; control-code handler. Relocating is free instead -- bank 13 stays mapped, so
; reading the source through hl and calling back to 13:$68A8 both work unchanged.
;
; This is the loop that had no length cap at all. It still has no cell cap worth
; the name (b is set high); the real bound is emit_lit's destination guard, which
; is stronger than a character count because it holds however many bytes a pair
; expands to.
; ========================================================= raw_copy
; The whole of a raw string copy: hl -> de, expanding, terminator included.
;
; Five sites in this ROM copy a string with the IDENTICAL seven bytes
; `2A 12 13 FE FF 20 F9` (`ld a,[hl+] / ld [de],a / inc de / cp $FF / jr nz`):
; 4:$7458, 11:$51F0, 11:$52D5, 14:$7C1E, 30:$7E8A. None handles a control code and
; none reaches the expander -- 11:$52D5 is why the file menu drew raw katakana.
;
; Because this routine replaces the ENTIRE loop rather than one iteration, the
; patch is a 3-byte `call` plus padding, which FITS IN PLACE in all seven bytes.
; That is why these sites need no relocation and cost nothing in bank 0, unlike
; loop2 -- and each site keeps its own epilogue untouched.
;
; hl ends past the terminator and de past the copy, exactly as the original left
; them. b is set high because emit_lit charges cells and would otherwise spend
; whatever b happened to hold; there is no address bound, since emit_lit applies
; that only to the $CF07 page, which matches what these loops always did.
raw_copy:
        ld b,$ff
raw_next:
        ld a,[hl+]
        cp $ff
        jr z,raw_done
        call dte_emit
        jr raw_next
raw_done:
        ld [de],a               ; the terminator, as the originals wrote it
        inc de
        ret

; ============================================================ loop2
loop2:
        ld b,$3c
loop2_next:
        ld a,[hl+]
        cp {CONTROL_MIN}
        jr nc,loop2_ctrl
        call dte_emit
        jr loop2_next
loop2_ctrl:
        call $68a8              ; the original control-code handler, in bank 13
        cp $ff
        jr nz,loop2_next
        pop hl
        pop de
        pop bc
        pop af
        ret
"""


# The menu box row drawer, 31:$40D8. `call $4124` at $4106 is its per-character store,
# and it is the ONLY caller of $4124 -- so replacing that one `call` covers the whole
# ROM-sourced box text path and nothing else.
BOX_LOOP = 0x40D8           # the drawer, for the trace tables
BOX_HOOK = 0x4106           # `call $4124` -> `call dte_box`, three bytes in place
BOX_HANDLER = 0x4124        # bank 31's own per-character handler, still used verbatim
BOX_SRCPTR = 0x40E4         # where bc is loaded and still points at the row's first byte

# WHY THE BOX PATH NEEDS A GATE AND THE COMPOSER DOES NOT
#
# The composer's cost for expanding a byte it should not have is one garbled line: its
# buffer is bounded, its string ends at an $FF the expander refuses, and the next line
# starts from a fresh pointer.
#
# The box drawer has no such floor. It draws a FIXED number of cells and then leaves
# `bc` wherever it stopped, and the next row simply continues from there -- so a byte
# that expands to two cells where the row budgeted one makes the row run out of cells
# before it reaches its terminator, and every following row of that box starts at the
# wrong byte. That cascade took the status screen and the file-select screen to a white
# screen, twice.
#
# And the drawer's source is not always ours to vet. The file-select box draws the
# PLAYER'S SAVED NAME out of SRAM, whose bytes are whatever the player typed -- katakana
# codes, squarely inside $43-$78. No content test can ever make that safe.
#
# So expansion is gated on the BOX, not on the byte: bit 7 of the descriptor's flags
# byte, which reaches the drawer at $C69E. Only 2 of its 8 bits are used across all 52
# descriptors ($00, $02 and $04 are the only values) and only 31:$4043 and 31:$40A1 read
# it, both testing a single named bit. build.py sets bit 7 for a box only when every row
# of that box is translated English, which is exactly the condition under which every
# DTE-range byte in it is one the compressor put there.
BOX_FLAG_ADDR = 0xC69E      # the descriptor's flags byte, as the drawer sees it
BOX_FLAG_BIT = 0x80         # free in every one of the ROM's 52 descriptors

# dte_box does not fit in one hole, so it is split where the split is free: everything up
# to and including the flag test goes in the tail of the $0062 padding (it is assembled
# with the expander, so it can name is_dte and dte_emit_yes as labels), and the rest at
# BOX_ORG. `jp` does not touch flags, so the carry `rla` leaves survives the crossing.
BOX_LO_SOURCE = """
; ========================================================== dte_box
; 31:$4106's `call $4124`, replaced. Reached ONLY from there, which is why it may
; `jp` straight back into bank 31: that bank is mapped for the whole drawer.
;
;   a  = the source byte           bc = the source pointer, already advanced
;   hl = the destination, $C300+   e  = cells left, i.e. the box width
;   d  = the caller's ROW index and is LIVE -- $4146 tests it
;
; Three ways out, and only the third expands:
;
;   NOT a DTE code -> bank 31's handler, untouched. It combines a dakuten into the
;   previous tile, stores the byte, and peeks the next SOURCE byte to decide whether
;   a cell was spent. All of that stays correct for Japanese, and the pad space the
;   drawer synthesises at a terminator ($00) comes through here too.
;   Box NOT marked compressed -> the same handler, byte drawn verbatim.
;   Otherwise -> dte_emit, which charges cells per EXPANDED byte and never peeks the
;   source, since after a pair expands "the next byte" may live inside a table entry.
dte_box:
        call is_dte
        jp nc,{BOX_HANDLER}      ; a mark, a literal, or the terminator's pad space
        ld a,[{FLAG_ADDR}]      ; the descriptor flags, as $4055 staged them
        rla                     ; bit 7 -> carry, one byte where `and` costs two
        dec bc
        ld a,[bc]               ; the code again -- none of these three touch flags
        inc bc
        jp {BOX_HI}
"""

BOX_SOURCE = """
; ====================================================== dte_box_hi
; Entered with a = the code and carry = "this box holds compressed text".
;
; dte_box recovered `a` from the source rather than saving it, because a push/pop
; pair cannot give `a` back without also giving back the flags the test just set.
; That is only sound on this path: bc has been advanced past the byte by $4105, and
; the one case where it has NOT -- the terminator, where the drawer substitutes $00
; -- cannot reach here, because $00 is not a DTE code.
;
; It reuses dte_emit whole instead of growing a second expander, by moving the
; drawer's registers into the ones dte_emit uses -- destination hl -> de, cells
; e -> b -- and moving them back afterwards. Two consequences worth stating:
; emit_lit's $CF38 address guard does not apply, because the box destination is
; page $C3-$C5 and not the composer's line buffer, which is correct -- the box is
; bounded by its width instead; and emit_lit scratches c, which is why the source
; pointer has to be saved rather than merely preserved by convention.
dte_box_hi:
        jp nc,{BOX_HANDLER}      ; box not marked: draw the byte as it stands
        push bc                 ; the source pointer -- emit_lit uses c as scratch
        push de                 ; d is the row index and has to come back
        ld b,e                  ; b = cells free, which is what emit_lit charges
        ld d,h
        ld e,l                  ; de = the destination, which is what it writes
        call {DTE_EMIT_YES}      ; is_dte already answered, so skip its test
        ld h,d
        ld l,e                  ; hl = the destination, past the expansion
        pop de                  ; the row index
        ld e,b                  ; cells left, as the drawer's loop expects them
        pop bc
        ret
"""


def box_source():
    """BOX_SOURCE with the expander's own addresses substituted in.

    gbasm has no way to import labels, so the addresses dte_box_hi needs are formatted
    in from the expander's label table -- the same thing hooks() does.
    """
    _, labels = build_expander()
    return BOX_SOURCE.format(BOX_HANDLER='$%04X' % BOX_HANDLER,
                             DTE_EMIT_YES='$%04X' % labels['dte_emit_yes'])


def build_box():
    """-> (bytes, {label: cpu-address}) for the resident dte_box at BOX_ORG."""
    code, labels = gbasm.assemble(box_source(), BOX_ORG)
    if BOX_ORG + len(code) > BOX_END:
        raise ValueError('dte_box_hi is %d bytes and bank 0 has %d at $%04X. The last '
                         'byte of the bank ($%04X) is deliberately not available -- code '
                         'that ends there does not return.'
                         % (len(code), BOX_END - BOX_ORG, BOX_ORG, BOX_END))
    return code, labels


def resident(labels=None):
    """-> [(cpu-addr, bytes, fill, note)] for bank 0 code outside the $0062 padding.

    Kept separate from hooks() because these are bank 0 ADDRESSES, not banked ones, and
    because each carries the byte build.py must find there first: writing resident code
    over something live is the one mistake no reference verifier can catch.
    """
    code, _ = build_box()
    return [(BOX_ORG, code, BOX_FILL,
             'dte_box: menu box row drawer expansion path (%d of %d bytes)'
             % (len(code), BOX_END - BOX_ORG))]


def expander_source():
    """SOURCE with every constant substituted from this module's configuration.

    dte_box's low half is assembled WITH the expander rather than beside it, so that it
    can name `is_dte` as a label and so that build_expander()'s bounds check covers it.
    """
    return (SOURCE.replace('{IS_DTE}', _is_dte_source()) + BOX_LO_SOURCE).format(
        LINE_END='$%02X' % LINE_END,
        LINE_PAGE='$%02X' % (LINE_BUF >> 8),
        TABLE_BANK='$%02X' % TABLE_BANK,
        RIGHT_PAGE='$%02X' % RIGHT_PAGE,
        CONTROL_MIN='$%02X' % CONTROL_MIN,
        BOX_HANDLER='$%04X' % BOX_HANDLER,
        FLAG_ADDR='$%04X' % BOX_FLAG_ADDR,
        BOX_HI='$%04X' % BOX_ORG,
    )


def build_expander():
    """-> (bytes, {label: cpu-address}) for the resident routine at $0062."""
    code, labels = gbasm.assemble(expander_source(), EXPANDER_ORG)
    if EXPANDER_ORG + len(code) > EXPANDER_END:
        raise ValueError('expander is %d bytes, bank 0 padding holds %d'
                         % (len(code), EXPANDER_END - EXPANDER_ORG))
    return code, labels


def rom_symbol(s, first_code=0x100):
    """tools/dte.py's symbol id -> the byte the ROM will carry it as."""
    return DTE_CODES[s - first_code] if s >= first_code else s


def build_table(table):
    """-> {bank-32 offset: bytes} for the direct-indexed LEFT/RIGHT pages.

    `table[i]` is the expansion of the symbol tools/dte.py numbered `first_code + i`;
    here it is re-indexed by the ROM code `DTE_CODES[i]` that will carry it, so the
    lookup is `ld l,code` with no arithmetic. That costs two 256-byte pages of an
    otherwise empty bank, which is the cheapest thing in this design.
    """
    left = bytearray(0x100)
    right = bytearray(0x100)
    for i, (a, b) in enumerate(table):
        code = DTE_CODES[i]
        # a recursive pair may reference another pair, so both halves go through the
        # same symbol -> ROM code mapping the encoded segments do
        left[code], right[code] = rom_symbol(a), rom_symbol(b)
    return {
        0x0000: bytes([TABLE_BANK]),          # honour the ROM's bank-id convention
        (LEFT_PAGE - 0x40) << 8: bytes(left),
        (RIGHT_PAGE - 0x40) << 8: bytes(right),
    }


def hooks(labels):
    """-> [(bank, cpu-addr, bytes, note)] -- every patch outside bank 0."""
    dte_emit = labels['dte_emit']
    loop2 = labels['loop2']
    out = []

    # ---- 13:$40DB, the composer loop with the 18-cell budget -------------------
    # Its literal path is 12 bytes ($40F1-$40FC): store, then peek the next source
    # byte to decide whether the character was a cell. All of that moves into
    # dte_emit, which counts expanded cells instead, so 7 bytes come free. They are
    # left as $00 and are where the <name>-costs-zero counter fix goes next.
    code, _ = gbasm.assemble("""
            call $%04X
            jr $40FD
    """ % dte_emit, 0x40F1)
    out.append((13, 0x40F1, code + bytes(0x40FD - 0x40F1 - len(code)),
                'composer literal path -> dte_emit (18-cell budget preserved)'))

    # ---- 13:$6893, the loop with no cap, relocated whole -----------------------
    code, _ = gbasm.assemble('jp $%04X' % loop2, 0x6893)
    out.append((13, 0x6893, code + bytes(0x68A8 - 0x6893 - len(code)),
                'second composer loop -> bank 0 loop2, now bounded'))

    # ---- 31:$4106, the menu box row drawer -------------------------------------
    # `call $4124` -> `call dte_box`: three bytes, exactly in place, and $4106 is the
    # only caller of $4124 in the ROM. This is the last render path between DTE and the
    # menus -- and note that it does NOT cover the item verbs, whose staging buffer at
    # $C616 is filled by 30:$7E8A and so arrives already expanded.
    code, _ = gbasm.assemble('call $%04X' % labels['dte_box'], BOX_HOOK)
    assert len(code) == 3, 'the drawer had exactly three bytes here'
    out.append((31, BOX_HOOK, code,
                'menu box row drawer -> dte_box (ROM-sourced box text)'))

    # ---- the raw 7-byte copy loops --------------------------------------------
    # `call raw_copy` + padding replaces the whole loop in place, so each site keeps
    # its own epilogue and none of them costs a byte of bank 0.
    #
    # ONLY sites whose content is known to be script text. The other three
    # (4:$7458, 11:$51F0, 14:$7C1E) are the same seven bytes but nobody has
    # established what they copy, and raw_copy would expand a $B3-$DF byte inside a
    # data blob just as happily as inside text. Trace them before adding them.
    for bank, addr, note in RAW_COPY_SITES:
        code, _ = gbasm.assemble('call $%04X' % labels['raw_copy'], addr)
        out.append((bank, addr, code + bytes(RAW_COPY_LEN - len(code)), note))
    return out


# ---------------------------------------------------------------------------------------
# WHICH STRINGS MAY BE COMPRESSED
#
# By OBSERVATION, never by bank. A per-bank guess was tried and was wrong: bank 11's menu
# labels are copied by `11:$52D5`, reached from a pointer table at `11:$52E0`, which never
# touches the expander -- so they rendered as raw katakana glyphs, because the DTE codes
# `$43-$78` ARE the katakana range.
#
# The ROM has far more string-copy loops than the four the plan named. Scanning for the
# idiom finds 6 raw `ld a,[hl+] / ld [de],a / inc de / cp $FF` loops, 44 test-then-store
# candidates, and a SECOND control-aware loop at `13:$6AE5`. Deciding which of those draws
# a given string is not something to reason about statically -- it is what
# `gbrun.py --dte-scan` measures, by hooking the loops that DO call the expander and
# recording the source pointer each one reads.
#
# So the allowlist is data, generated by playing the game, and an unlisted string is simply
# left uncompressed. That fails safe: no compression costs space, wrong compression costs
# correctness.
ALLOWLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'script', 'dte_ok.tsv')

# The loops that reach dte_emit, and where the source register still points at the START
# of a string. `13:$40D8` is the `ld de,$CF07` immediately before the 18-cell loop;
# `loop2` is the relocated second composer loop, entered with hl already set.
#
# The box drawer is the one site that does NOT use hl -- hl is its destination and bc is
# its source, which is what the previous handoff got backwards. `31:$40E4` is the peek
# that chooses the left border glyph: bc is loaded by then and has not been advanced yet,
# so it is the row's first byte. Rows are separate $FF-terminated strings with their own
# `loc`, so one hit per row is exactly what the allowlist wants.
SCAN_SITES = [(13, 0x40D8, 'composer 18-cell loop', 'hl'),
              (0, 'loop2', 'composer uncapped loop', 'hl'),
              (0, 'raw_copy', 'raw string copy', 'hl'),
              (31, BOX_SRCPTR, 'menu box row drawer', 'bc')]

# ---- the WRAM stagers, which are one step UPSTREAM of an expanding loop ----------------
#
# Village and story dialogue can never be attributed by watching the expander itself.
# `loop2` is the loop that expands, but its source is the WRAM buffer at $CF8F, not the
# ROM: bank 11 `$569E` and bank 14 `$4010` copy ONE LINE out of the ROM into $CF8F first,
# and `13:$688D` then points loop2 at it. So a scan hooked only on expanding loops sees a
# WRAM address, discards it (`gbrun.dte_scan` requires $4000-$7FFF), and every bank-11 and
# bank-14 string stays uncompressed for ever -- which is why the TASK 2 village lines had
# to be hand-abbreviated against a raw 1.0x byte budget when DTE was sitting right there.
#
# Observing the stager is a WEAKER claim than observing the expander, and it is recorded
# separately for that reason: it says "these bytes reach loop2", not "an expanding loop
# read these bytes". The gap is closed by checking the three things that could break in
# between, all of which hold:
#
#   1. The stagers stop at `$EE`/`$EF`/`$FF`. Every DTE code is in $92-$99, $B8-$C1 or
#      $C4-$DF, and a pair may not span a control code, so the byte a stager stops on is
#      the same byte before and after compression.
#   2. `13:$67F3` reads the FIRST staged byte and does `cp $EC`. $EC is a control code, so
#      compression neither produces it nor absorbs it into a pair -- a line that started
#      with $EC still does, and one that did not still does not.
#   3. `13:$688D`/`$6893` is loop2, which is hooked to the expander, so what the stager
#      copied is expanded before it reaches `$CF07`.
#
# Those are the only three readers of $CF8F in the ROM (scanned for the operand bytes
# `8F CF`: 11:$56A2, 13:$67F3, 13:$688D, 14:$400D).
#
# Hooked at the `ld bc,$CF8F` that sets up the copy, NOT at the loop head. The loop head
# (`11:$56A5`, `14:$4010`) is re-entered per BYTE, so hooking it would record every
# intermediate address as though it were a string start. The setup runs exactly once per
# line, and by then `hl` holds the real ROM address: both readers arrive with the window
# bits toggled and undo that first (`11:$56A0 set 6,h`, `14:$400A xor $C0`).
STAGER_SITES = [(11, 0x56A2, 'bank 11 dialogue stager -> $CF8F', 'hl'),
                (14, 0x400D, 'bank 14 dialogue stager -> $CF8F', 'hl')]

# The identical 7-byte copy loop `2A 12 13 FE FF 20 F9`, at the sites whose content is
# known to be script text. `call raw_copy` + padding fits in place.
# How many times a bank's own strings are repeated in the training set.
#
# The table is one fixed pair of pages, so where its 128 codes get SPENT is a free choice --
# and spending them evenly is wrong, because the banks are not equally tight. Prose banks
# have slack (bank 11 sat at +93 bytes); bank 30's pool is 73 bytes against 77 needed, so
# four bytes there matter more than four hundred in bank 11.
#
# Measured, bank 30 need / prose yield: weight 1 -> 77 B / 40.8%, 16 -> 75 B / 40.7%,
# 64 -> 59 B / 39.3%, 256 -> 39 B / 36.5%. 64 buys the fit for 1.5 points of prose.
#
# This is what closed bank 30, NOT the dead-entry reclamation the plan expected -- see
# FINDINGS.md on why that evidence did not hold up.
TRAIN_WEIGHT = {30: 256}
DEFAULT_WEIGHT = 1

RAW_COPY_LEN = 7
RAW_COPY_SITES = [
    (11, 0x52D5, 'menu label copy -> raw_copy (file menu; verified on screen)'),
    (30, 0x7E8A, 'item verb staging -> raw_copy (table at 30:$7E99)'),
]


def load_allowlist(path=None):
    """-> {loc}: the strings a trace has actually seen an expanding loop read.

    Missing file means an empty set, which means no compression at all. That is the
    correct default: the infrastructure still gets built and exercised, and nothing is
    put on screen that cannot be expanded.
    """
    path = path or ALLOWLIST
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.split('#')[0].strip()
            if line:
                out.add(line.split('\t')[0].strip())
    return out


def chunks(data):
    """Split a string into (compressible, bytes) runs.

    A pair may never span a control code, because a DTE byte is expanded blind into the
    line buffer and anything the renderer has to ACT on must stay a byte of its own --
    argument bytes included, or the skip-chain would resynchronise on the wrong byte.

    Combining marks are barriers too. They need not be: emit_lit handles a mark wherever
    it appears. But keeping them out of the table is what bounds the one write that
    bypasses the cell budget -- if no pair can contain a mark, an expansion can never
    emit one, so the bypass is limited to a byte that was already in the source. English
    has no marks, so this costs nothing.

    THE MESSAGE-PATH ARITY IS USED HERE ON PURPOSE, and this is the one place in the
    project where the two dispatch tables may safely disagree. On banks 11/14 `$E7` and
    `$F0` take no argument (codec.DIALOGUE_ARITY), so this over-reads their barrier by a
    byte -- but a barrier is only ever emitted verbatim, so the ROM gets the same bytes
    in the same order either way. All it costs is one byte of compression at seven sites.
    Threading a bank through compress() and training_segments() to buy that back would
    add a parameter to four callers for no change in output.
    """
    out, run, i = [], bytearray(), 0
    while i < len(data):
        b = data[i]
        if b >= CONTROL_MIN or b in codec.COMBINING:
            if run:
                out.append((True, bytes(run)))
                run = bytearray()
            n = 1 + (codec.ARITY.get(b, 0) if b >= CONTROL_MIN else 0)
            out.append((False, bytes(data[i:i + n])))
            i += n
        else:
            run.append(b)
            i += 1
    if run:
        out.append((True, bytes(run)))
    return out


def training_segments(data):
    """The runs of `data` a table may be trained on."""
    return [blob for ok, blob in chunks(data) if ok and len(blob) > 1]


def compress(data, table, first_code=0x100):
    """Apply an existing table to one string. -> ROM bytes.

    The pairs are applied in the order dte.build assigned them, which is what makes this
    agree with the encoder: a later pair may only match because an earlier one already
    collapsed part of the text. Applying them out of order, or all at once, would produce
    a different -- and unexpandable -- encoding.

    Returns `data` unchanged if the first byte would be one of BOX_FIRST_UNSAFE. Applied
    to every string rather than to box rows only: it costs a byte or two on roughly one
    string in seventy, and a flag threaded through every caller would be one more thing
    to get wrong at the one site where it matters.
    """
    import dte
    out = bytearray()
    for ok, blob in chunks(data):
        if not ok:
            out += blob
            continue
        syms = list(blob)
        for k, pair in enumerate(table):
            syms = dte._replace([syms], pair, first_code + k)[0]
        out += bytes(rom_symbol(s, first_code) for s in syms)
    if out[:1] and out[0] in BOX_FIRST_UNSAFE:
        return bytes(data)
    return bytes(out)


def expand_bytes(rom_bytes, table, first_code=0x100):
    """Decode ROM bytes back to plain text bytes -- build.py's round-trip check."""
    code_of = {DTE_CODES[i]: table[i] for i in range(len(table))}
    out = bytearray()
    stack = list(reversed(rom_bytes))
    while stack:
        s = stack.pop()
        if s in code_of:
            a, b = code_of[s]
            stack.append(rom_symbol(b, first_code))
            stack.append(rom_symbol(a, first_code))
        else:
            out.append(s)
    return bytes(out)


def encode_segments(segments, npairs=len(DTE_CODES), recursive=True):
    """Compress byte segments and re-code them for the ROM.

    -> (table, [rom-bytes], stats). `table` is tools/dte.py's, indexed by build order;
    the returned segments carry DTE_CODES[i] wherever dte.py used symbol 256+i.

    A literal that already equals one of the DTE codes would be indistinguishable from a
    pair reference, so that is an error rather than something to encode around. English
    text cannot produce one -- its letters all live below $43 or in the punctuation the
    ranges skip -- which is exactly why the ranges were chosen that way.
    """
    import dte
    bad = sorted({b for s in segments for b in s} & set(DTE_CODES))
    if bad:
        raise ValueError('literal bytes collide with the DTE code space: %s'
                         % ' '.join('$%02X' % b for b in bad))
    table, enc = dte.build(segments, npairs, recursive=recursive, first_code=0x100)
    if len(table) > len(DTE_CODES):
        raise ValueError('%d pairs but only %d codes' % (len(table), len(DTE_CODES)))
    out = [bytes(rom_symbol(s) for s in e) for e in enc]
    before = sum(len(s) for s in segments)
    after = sum(len(s) for s in out)
    return table, out, {
        'before': before, 'after': after, 'pairs': len(table),
        'pct': 100.0 * (before - after) / before if before else 0.0,
        'depth': dte.max_depth(table, 0x100),
    }


def _emu_banks(table, caller_bank=13):
    """Bank 0 with the expander in it, plus the table bank. -> (banks, labels)."""
    import gbemu
    code, labels = build_expander()
    bank0 = bytearray(0x4000)
    bank0[EXPANDER_ORG:EXPANDER_ORG + len(code)] = code
    banks = {0: bank0}
    tb = bytearray(0x4000)
    for off, blob in build_table(table).items():
        tb[off:off + len(blob)] = blob
    banks[TABLE_BANK] = tb
    caller = bytearray(0x4000)
    caller[0] = caller_bank          # the bank-id convention dte_emit depends on
    banks[caller_bank] = caller
    return gbemu, banks, labels


def run_line(table, rom_bytes, cells=0xFF, caller_bank=13):
    """Drive dte_emit over `rom_bytes` the way 13:$40DB's loop does.

    -> (bytes written to the line buffer, cells charged, checks) so a test can compare
    against tools/dte.py and against the ROM's own cell rule at the same time.
    """
    gbemu, banks, labels = _emu_banks(table, caller_bank)
    src = 0x5000
    banks[caller_bank][src - 0x4000:src - 0x4000 + len(rom_bytes)] = rom_bytes
    cpu = gbemu.Cpu(banks, bank=caller_bank)
    cpu.de = LINE_BUF
    cpu.b = cells
    cpu.hl = src
    checks = []
    for i in range(len(rom_bytes)):
        cpu.hl = src + i + 1                    # the loop has already done ld a,[hl+]
        cpu.a = rom_bytes[i]
        before_hl, before_sp = cpu.hl, cpu.sp
        cpu.call(labels['dte_emit'])
        checks.append((cpu.bank == caller_bank, cpu.hl == before_hl, cpu.sp == before_sp))
    n = cpu.de - LINE_BUF
    return bytes(cpu.ram[LINE_BUF - 0x8000:LINE_BUF - 0x8000 + n]), cells - cpu.b, checks


def _base_rom():
    """The unmodified ROM, for tests that want to run the REAL bank 31."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'build', 'base.gb')
    with open(path, 'rb') as f:
        return f.read()


def _box_banks(table, rom, patched=True, rom_bank=31):
    """Bank 0 with the expander and dte_box, plus the REAL bank `rom_bank` from `rom`.

    `patched=False` leaves 31:$4106 as the ROM shipped it, which is what makes a
    before/after comparison possible: the whole claim about the Japanese path is that
    the drawer keeps drawing exactly what it drew, and that is only checkable against
    the unpatched original.
    """
    import gbemu
    exp, labels = build_expander()
    box, box_labels = build_box()
    bank0 = bytearray(0x4000)
    bank0[EXPANDER_ORG:EXPANDER_ORG + len(exp)] = exp
    bank0[BOX_ORG:BOX_ORG + len(box)] = box
    banks = {0: bank0}
    tb = bytearray(0x4000)
    for off, blob in build_table(table).items():
        tb[off:off + len(blob)] = blob
    banks[TABLE_BANK] = tb
    b = bytearray(rom[rom_bank * 0x4000:(rom_bank + 1) * 0x4000])
    assert b[0] == rom_bank, ('bank %d does not hold its own number at $4000, which is '
                              'what dte_emit reads to restore it' % rom_bank)
    if patched:
        code, _ = gbasm.assemble('call $%04X' % labels['dte_box'], BOX_HOOK)
        b[BOX_HOOK - 0x4000:BOX_HOOK - 0x4000 + len(code)] = code
    banks[rom_bank] = b
    labels.update(box_labels)
    return gbemu, banks, labels


BOX_DEST = 0xC300           # where 31:$408C points the drawer's tilemap staging buffer


def run_box_row(table, rom, row, width=18, patched=True, row_index=0, flag=True):
    """Run the REAL drawer at 31:$40D8 over one row. -> (drawn cells, bytes consumed).

    This runs the ROM's own bytes, not a model of them: the border-glyph peek at $40E4,
    the pad-to-width behaviour at $4101, bank 31's $4124 handler and its dakuten
    combining at $4142 are all the shipped code. Only $4106 differs, and only when
    `patched`.

    `drawn` is width+2 bytes because the drawer writes a left border before the loop and
    a right border after it, neither of which spends a cell.
    """
    gbemu, banks, _ = _box_banks(table, rom, patched)
    src = 0x5000
    blob = bytes(row) + b'\xff'
    banks[31][src - 0x4000:src - 0x4000 + len(blob)] = blob
    cpu = gbemu.Cpu(banks, bank=31)
    cpu.ram[0xC69D - 0x8000] = width
    cpu.ram[BOX_FLAG_ADDR - 0x8000] = BOX_FLAG_BIT if flag else 0x04
    cpu.ram[0xC69F - 0x8000] = src & 0xFF
    cpu.ram[0xC6A0 - 0x8000] = src >> 8
    cpu.hl = BOX_DEST
    cpu.d = row_index                       # $4146 reads it; the drawer must not lose it
    cpu.call(BOX_LOOP)
    end = cpu.ram[0xC69F - 0x8000] | (cpu.ram[0xC6A0 - 0x8000] << 8)
    drawn = bytes(cpu.ram[BOX_DEST - 0x8000:BOX_DEST - 0x8000 + width + 2])
    return drawn, end - src


def verify_box(rom=None, table=None, quiet=False):
    """Check dte_box by running the real drawer, both patched and unpatched. -> stats.

    Three claims, and they need different evidence:

      * THE GATE HOLDS. With the descriptor's bit 7 CLEAR, the patched drawer must draw
        what the unpatched one drew for EVERY real bank-31 row -- including the 19 that
        are full of bytes in the DTE code space. This is the claim that matters most,
        because it is the one covering text this project does not control: the
        file-select box draws the player's saved name straight out of SRAM.
      * JAPANESE IS UNCHANGED EVEN IF MARKED. With bit 7 set, a row holding no DTE-range
        byte must still draw identically -- dakuten combining, terminator padding and
        border glyph included.
      * ENGLISH SURVIVES COMPRESSION. A compressed row through the patched drawer, with
        the box marked, must draw what the uncompressed row draws through the unpatched
        one.

    Plus the overrun case: a row too long for the box must still stop at the width.
    """
    import csv
    rom = rom or _base_rom()
    if table is None:
        table, _, _ = encode_segments(training_corpus())
    codes = set(DTE_CODES)
    stats = {'gated': 0, 'jp_rows': 0, 'jp_skipped': 0, 'en_rows': 0, 'fails': 0}

    # ---- the real Japanese rows of bank 31
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'script', 'script.tsv')
    rows = []
    if os.path.exists(script):
        with open(script, encoding='utf-8') as f:
            for r in csv.DictReader(f, delimiter='\t'):
                if not r['loc'].startswith('31:'):
                    continue
                bank, addr = r['loc'].split(':$')
                off = int(bank) * 0x4000 + int(addr, 16) - 0x4000
                rows.append(rom[off:off + int(r['bytes'])])
    # An unmarked box must be untouched no matter what its bytes are. Also run a row of
    # pure DTE codes, which is what a saved name of katakana looks like to the drawer.
    for row in rows + [bytes(DTE_CODES[:12])]:
        for width in (row and len(row), 18):
            want, want_n = run_box_row(table, rom, row, width, patched=False)
            got, got_n = run_box_row(table, rom, row, width, patched=True, flag=False)
            if (got, got_n) != (want, want_n):
                stats['fails'] += 1
                if not quiet and stats['fails'] <= 3:
                    print('   GATE LEAKED  %s\n     was %s (%d)\n     now %s (%d)'
                          % (bytes(row).hex(' '), want.hex(' '), want_n,
                             got.hex(' '), got_n))
            stats['gated'] += 1

    for row in rows:
        if set(row) & codes:
            stats['jp_skipped'] += 1        # would expand, and is meant to when marked
            continue
        for width in (row and len(row), 18):
            want, want_n = run_box_row(table, rom, row, width, patched=False)
            got, got_n = run_box_row(table, rom, row, width, patched=True, flag=True)
            if (got, got_n) != (want, want_n):
                stats['fails'] += 1
                if not quiet and stats['fails'] <= 3:
                    print('   JP CHANGED  %s\n     was %s (%d)\n     now %s (%d)'
                          % (bytes(row).hex(' '), want.hex(' '), want_n,
                             got.hex(' '), got_n))
            stats['jp_rows'] += 1

    # ---- English, compressed against uncompressed
    width = 18
    for seg in _default_corpus():
        if not seg or len(seg) > width:
            continue
        packed = compress(seg, table)
        want, want_n = run_box_row(table, rom, seg, width, patched=False)
        got, got_n = run_box_row(table, rom, packed, width, patched=True)
        if got != want:
            stats['fails'] += 1
            if not quiet and stats['fails'] <= 3:
                print('   EN MISMATCH  %s\n     want %s\n     got  %s'
                      % (seg.hex(' '), want.hex(' '), got.hex(' ')))
        elif want_n != len(seg) + 1 or got_n != len(packed) + 1:
            stats['fails'] += 1            # the next row would start in the wrong place
            if not quiet:
                print('   EN CONSUMPTION  %s: %d/%d vs %d/%d'
                      % (seg.hex(' '), want_n, len(seg) + 1, got_n, len(packed) + 1))
        stats['en_rows'] += 1

    # ---- an over-long row must stop at the box width, not run off the buffer
    long_row = max((s for s in _default_corpus() if s), key=len)
    packed = compress(long_row * 4, table)
    drawn, _ = run_box_row(table, rom, packed, 8, patched=True)
    stats['overrun_ok'] = len(drawn) == 10 and drawn[-1] == 0xBF

    if not quiet:
        print('verify_box: %d UNMARKED row draws byte-identical to the unpatched drawer '
              '(the gate; includes rows made only of DTE codes)' % stats['gated'])
        print('   %d marked row draws with no DTE-range byte also unchanged '
              '(%d rows skipped: they are meant to expand when marked)'
              % (stats['jp_rows'], stats['jp_skipped']))
        print('   %d English rows draw identically compressed and uncompressed, '
              '%d failure(s)' % (stats['en_rows'], stats['fails']))
        print('   over-long row stopped at the box width: %s'
              % ('OK' if stats['overrun_ok'] else 'NO'))
    return stats


def verify(corpus=None, npairs=len(DTE_CODES), quiet=False):
    """Run the ROM expander against tools/dte.py's reference decoder. -> stats."""
    import dte
    if corpus is None:
        corpus = _default_corpus()
    table, enc, stats = encode_segments(corpus, npairs)

    fails = 0
    checked = 0
    max_depth_seen = 0
    for orig, packed in zip(corpus, enc):
        # the line buffer is bounded, so only compare segments that fit inside it
        if len(orig) > LINE_END - (LINE_BUF & 0xFF):
            continue
        got, charged, checks = run_line(table, packed)
        want_cells = sum(1 for b in orig if b not in (0x79, 0x7A))
        if got != bytes(orig):
            fails += 1
            if fails <= 3 and not quiet:
                print('   MISMATCH  want %s\n             got  %s'
                      % (bytes(orig).hex(' '), got.hex(' ')))
        elif charged != want_cells:
            fails += 1
            if fails <= 3 and not quiet:
                print('   CELL COUNT  want %d got %d for %s'
                      % (want_cells, charged, bytes(orig).hex(' ')))
        elif not all(all(c) for c in checks):
            fails += 1
            if not quiet:
                print('   STATE  bank/hl/sp not restored')
        checked += 1
    stats.update(checked=checked, fails=fails)

    # the guard: a segment that cannot fit must stop inside the cleared buffer
    long_src = enc[max(range(len(enc)), key=lambda i: len(corpus[i]))]
    got, _, _ = run_line(table, long_src * 4)
    stats['guard_bytes'] = len(got)
    stats['guard_ok'] = LINE_BUF + len(got) <= LINE_BUF - (LINE_BUF & 0xFF) + LINE_END

    if not quiet:
        print('verify: %d segments through the ROM expander, %d mismatches'
              % (checked, fails))
        print('   %d -> %d bytes (%.1f%%), %d pairs, expansion depth %d'
              % (stats['before'], stats['after'], stats['pct'],
                 stats['pairs'], stats['depth']))
        print('   write guard: an over-long line stopped after %d bytes at $%04X (%s)'
              % (stats['guard_bytes'], LINE_BUF + stats['guard_bytes'],
                 'OK' if stats['guard_ok'] else 'PAST $CF%02X' % LINE_END))
    return stats


def training_corpus():
    """Segments to TRAIN the table on, independent of what is being compressed.

    The table is a fixed 256-byte pair of pages in the ROM, so its cost does not depend on
    how much text it was trained on -- and yield tracks the corpus, not the input. Training
    on the SNES English fan translation therefore gives our own strings the measured 40.7%
    from the first translated line, instead of only once enough English exists to have
    repeated digrams. Same franchise, same register; see FINDINGS.md.

    Falls back to our own TSV if that corpus is not checked out next door.
    """
    out = []
    for seg in _default_corpus():
        out.extend(training_segments(seg))
    return out


def _default_corpus():
    """English byte segments to train and test on: the SNES script, else our own TSV.

    Encoded through EN_CODES, which is what build.encode_en emits. NOT through
    codec.encode -- codec is the Japanese table, and its REV_CHARS resolves 'F' to the
    ROM's native status-bar glyph at $B4 rather than the Latin font's $10, which would
    train the table on bytes the inserter never writes.
    """
    from latinfont import EN_CODES
    texts = []
    try:
        import dte_measure
        cats = dte_measure.load_corpus()
        for units in cats.values():
            for _, segs in units:
                texts.extend(segs)
    except Exception:
        for line in open(os.path.join(os.path.dirname(__file__), '..',
                                      'script', 'menu_en.tsv'), encoding='utf-8'):
            if '\t' in line:
                texts.append(line.split('\t', 1)[1].strip())
    # drop characters with no glyph rather than transliterate them: the point is to train
    # on the bytes the ROM can actually hold
    out = []
    for t in texts:
        b = bytes(EN_CODES[ch] for ch in t if ch in EN_CODES)
        if b:
            out.append(b)
    return out


def selftest():
    code, labels = build_expander()
    print('expander: %d bytes at $%04X-$%04X (%d spare in bank 0 padding)'
          % (len(code), EXPANDER_ORG, EXPANDER_ORG + len(code) - 1,
             EXPANDER_END - EXPANDER_ORG - len(code)))
    box, box_labels = build_box()
    print('dte_box : %d bytes at $%04X-$%04X (%d spare in bank 0 tail)'
          % (len(box), BOX_ORG, BOX_ORG + len(box) - 1, BOX_END - BOX_ORG - len(box)))
    print('dte codes: %d in %s' % (len(DTE_CODES),
                                   ' '.join('$%02X-$%02X' % r for r in DTE_RANGES)))
    for name in ('is_dte', 'emit_lit', 'dte_emit', 'dte_emit_yes', 'expand', 'loop2',
                 'dte_box'):
        print('   %-12s $%04X' % (name, labels[name]))
    print('   %-12s $%04X' % ('dte_box_hi', box_labels['dte_box_hi']))
    for bank, addr, patch, note in hooks(labels):
        print('hook %d:$%04X  %-2d bytes  %s' % (bank, addr, len(patch), note))
    for addr, patch, fill, note in resident():
        print('resident 0:$%04X  %-2d bytes  (expects $%02X fill)  %s'
              % (addr, len(patch), fill, note))
    print()
    verify()
    print()
    verify_box()


if __name__ == '__main__':
    selftest()
