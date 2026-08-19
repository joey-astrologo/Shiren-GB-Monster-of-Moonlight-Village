#!/usr/bin/env python3
"""Lay text out with each real renderer contract and refuse anything that loses ink.

CURRENT PROPORTIONAL CONTRACT. Composer dialogue owns 18 tiles = 144px, three rows per box, and a
30-glyph source/reveal map. Item help and equipment seals own the same 144px but use the
measured bank-31 scanner: 21 source glyphs, four rows for help and one row per seal. The
approved font is proportional, so `check()` enforces source count and painted extent
independently. A narrow 30-glyph line may fit; a wide shorter line may clip.

The native Japanese and fixed-width diagnostic control still use 18 cells. The old uniform
VWF diagnostic stages 24 six-pixel glyphs. Those numbers remain in this module as controls
and historical calibration, not production English limits.

    dialogue_preview.py                     every translated dialogue string
    dialogue_preview.py 14:$5047 13:$4B6B   just these
    dialogue_preview.py 14:$566D --player-text Shiren
                                             audition the exact runtime player name
    dialogue_preview.py --jp                the Japanese, as a control
    dialogue_preview.py --check             print only the failures; exit 1 if any

WHERE THE 18-TILE CANVAS COMES FROM. It is read out of the ROM and checked against the
Japanese script, which is a known-good corpus:

  18 cells per line.   Three separate mechanisms agree.
      * `13:$40D6 ld b,$12` -- the bank-13 stager's cell budget. It counts down per
        character copied into $CF07 and STOPS the copy at zero, which is the truncation.
      * `13:$44F5 ld b,$12` -- the renderer that walks $CF07 onto the tilemap. Exactly 18,
        whatever the buffer holds.
      * `13:$6B40` = $A8, $BA, $CC -- the first TILE INDEX of each of the three rows, and
        they are 18 apart. This is the one that explains the dialogue path's symptom: it
        has no cell counter at all, so a 19th character is written to tile $BA, which is
        row 1's first tile. That is why an over-long line "ate the next line's indent".

  3 lines per box.     The same three tile rows, $A8-$DD, with $DE/$DF reserved for the
      dakuten overlay (`13:$6B06`/`$6B11`). 18*3 = 54 tiles, and the row-address table at
      `13:$6B43` holds exactly three tilemap addresses ($9C40/$9C80/$9CC0). There is no
      fourth row to spill into.

  A control code costs no cell, but a SUBSTITUTION does. `13:$4107` pushes bc around the
      dispatch, so no handler can charge the cell counter -- but `<var>`, `<name>` and the
      number codes all write into the buffer, and the RENDERER charges whatever it finds
      there. So the 18 cells are shared between the literal text and whatever gets
      substituted into it. See `subst_widths` and `floor_widths`.

VALIDATION. `--selftest` measures every Japanese dialogue line in the script under this
model. The longest is exactly 18 and 230 of the 1608 land exactly on that boundary -- a
model that mismeasured by even one cell could not produce that shape. Two strings come out
over and both are explained in `KNOWN_OVER`.

THE ITEM-DESCRIPTION SCREEN IS A SECOND GEOMETRY, and until 2026-08-04 this file measured
it with the composer's. It is not the composer at all: `13:$554A`'s 122 strings are staged
by `13:$7E49` into `$C616` and drawn by BANK 31's tilemap box renderer, the same one that
draws menus, as box 7. So every number is different and none of them is a guess --

  18 cells, 4 lines.  Box 7's descriptor at `31:$4221` is `00 03 05 12 00 16 c6 00`:
      x=0, y=3, 5 rows, width `$12` = 18, source `$C616`. Row 1 is the item NAME (staged
      separately by `4:$5736`), and `13:$7E49 ld b,$04` fills the other four. The Dot
      production path reaches it through `menuvwf.py`, accepts 21 source glyphs, and clips
      at 144px. The 18-cell native path is retained only as a diagnostic control.

  `<cF0:xx>` is INLINE TEXT and costs its expansion. `13:$7E6A` far-calls `11:$7E26`,
      which copies the string at `11:$55AC + 2*xx` straight into the buffer at the current
      position -- no line break either side. `<cF0:03>` is 'そうびすると', 6 cells, and
      `13:$5AD3` reads `<cF0:03> みずのうえを` = 13 cells on one line. Charging it zero,
      which is what this file used to do, under-measures 80 of the 126 descriptions.

  THE SEALS ARE THE SAME BOX AGAIN, ONE LINE EACH. `11:$5463`'s 20 strings are the
      ability lines an equipped weapon or shield prints -- `ドラゴンけいモンスターにつよい`
      is the dragon-killer seal. `4:$49F5` zeroes the same `$78` bytes at `$C616`, calls
      `4:$5736` for the item NAME, then far-calls `11:$7E40`, which walks the item's seal
      ids at `$C6BE` and copies up to `ld c,$04` of these into the buffer behind it,
      terminator included. `4:$4A0D` draws box `$13`, whose descriptor `31:$4395` is
      `00 03 05 12 00 16 c6 00` -- byte for byte box 7's. So: 18 cells, and ONE line per
      seal, because a seal IS a row and four of them share the four rows under the name.
      A `<br>` here would draw as a tile, not a break.

      Measured, not inferred: the longest Japanese seal is 18 cells and three sit exactly
      on 18 (`11:$54BC`, `11:$54FD`, `11:$557A`). Until 2026-08-06 `is_help` was scoped to
      bank 13 and `is_dialogue` returned False for these, so `--check` and `build.py`
      skipped them entirely -- neither the 18 nor the 1 was being applied to anything.

  Those 13 expansions are ORDINARY SCRIPT STRINGS in bank 11 (`CF0_LOCS`), so their
      English width is whatever en.tsv says. `cf0_from_trans` reloads the table from a
      translation, which is why the check tightens as they get translated.

The falsifier is the same one as above and it is sharper here, because this region has no
substitutions at all -- every cell is literal text or a `<cF0:xx>` expansion of known
width. Measured with this geometry the Japanese has NO line over 18 and NO box over 4, and
70 lines land exactly on 18; charging `<cF0:xx>` zero instead drops that to 39, and the
composer's 3-line box calls 51 boxes the game SHIPS too deep. `--selftest` asserts both.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec                                                        # noqa: E402
import dotfont                                                      # noqa: E402
from latinfont import EN_CODES                                      # noqa: E402

# The Latin alphabet is written OVER the kana tiles in place, so a byte draws whichever
# letter latinfont put at that index and codec.decode -- which is the Japanese table --
# would show a translated line as kana. Same inversion boxpreview.py uses, same reason.
EN_CHARS = {v: k for k, v in sorted(EN_CODES.items(), reverse=True)}

# A LINE IS 18 TILES AND ALWAYS WAS. The current Dot renderer may stage up to 30 source
# glyphs, then clips their painted pixels at the same 144px edge. The older uniform VWF
# staged 24 six-pixel glyphs; the native Japanese/control path remains 18 fixed cells.
# Keep all three names because diagnostic builds and the Japanese model use the controls.
FIXED_WIDTH = 18
UNIFORM_WIDTH = 24
WIDTH = 30                  # current Dot source/reveal ceiling, not a visual width
CELL_PX, PEN_PX = 8, 6
LINE_PX = FIXED_WIDTH * CELL_PX
LINES_PER_BOX = 3           # tiles $A8/$BA/$CC; $DE/$DF are the dakuten pair
BREAKS = {0xEF: 'br', 0xEE: 'brk'}      # both end a line; $EE also ends the box

# The item-description screen -- a different renderer, so its own geometry. See the module
# docstring: box 7's descriptor `31:$4221` is x=0 y=3 rows=5 w=$12 src=$C616, and
# `13:$7E49 ld b,$04` is the line budget. Row 1 of the five holds the item name.
HELP_FIXED_WIDTH = 18       # native/fixed-width control
HELP_WIDTH = 21             # measured Dot menu scanner ceiling; still clipped at 144px
HELP_LINES_PER_BOX = 4      # 13:$7E49 `ld b,$04`
HELP_RANGE = (0x5684, 0x67B0)   # bank 13, the strings table 13:$554A points at
HELP_BUF = 0x78             # 4:$49B0 `ld b,$78` -- the 120 bytes zeroed at $C616

# The equipment SEALS -- box $13, which is box 7's descriptor byte for byte (31:$4395 ==
# 31:$4221), staged into the same $C616 by the same 4:$49F5. Same 18 cells, but ONE line
# apiece: `11:$7E40 ld c,$04` copies up to four of these behind the item name, and a seal
# IS a row. A second line in one of them would eat another seal's row.
SEAL_RANGE = (0x548B, 0x55A5)   # bank 11, the 20 strings the table 11:$5463 points at
SEAL_LINES_PER_BOX = 1

# The staging buffer at $CF07, and how much of it the composer CLEARS before filling it.
# Text past the clear is read as whatever was there before, so this is the real ceiling.
BUF_LOOP1 = 0x32            # 13:$40CF `ld d,$32` -- bank 13 messages
BUF_LOOP2 = 0x36            # 13:$6884 `ld d,$36` -- bank 11/14 dialogue

# ---------------------------------------------------------------------------------------
# What a control code puts on the screen
# ---------------------------------------------------------------------------------------
# Cells each control code contributes, WORST CASE. Zero unless the handler writes to `de`,
# which is the buffer pointer -- so this is a fact about the ROM, not a convention.
#
#   $E4/$E6  13:$424C/$4261 call 13:$4294 with c=3   -> at most 3 digits
#   $E5      13:$4279       calls it with c=7        -> at most 7
#            ($4294 suppresses leading zeros, so these are ceilings, not fixed widths)
#   $E2      13:$4199       far-calls bank 11 and the callee writes a NAME
#   $EA      13:$4175       copies $CF81 until $FF   -- the player's name
#   $E3      13:$41AF       an item name, with a count prefix when the count is > 1
#
# Everything else writes nothing a player sees: $E0/$E1/$F0 are sound and screen effects,
# $E7/$E8/$EB/$ED set a flag, $EC repeats `rst $18` (a vblank wait -- a PAUSE, not text),
# and $E9's handler is a bare `ret`.
#
# $F0 is the exception, and only on the item-description path. There its handler DOES write
# to `de`: 13:$7E6A far-calls 11:$7E26, which copies the string at `11:$55AC + 2*arg` into
# the buffer inline. On the composer path the same code is a screen effect that draws
# nothing (docs/FINDINGS.md, "the composer has TWO dispatch tables"), so the cost is charged by
# geometry, not globally -- `help_widths()` adds it and `subst_widths()` does not.
DIGITS = {0xE4: 3, 0xE5: 7, 0xE6: 3}

# The 13 shared lines `<cF0:xx>` pastes in, in argument order, read out of `11:$55AC`.
# They are ordinary script strings, so their English lengths come from en.tsv; the Japanese
# widths here are the fallback for an untranslated build and for `--jp`.
CF0_LOCS = ('11:$55C6', '11:$55DE', '11:$55F0', '11:$5609', '11:$5611', '11:$5623',
            '11:$5633', '11:$563F', '11:$5654', '11:$5665', '11:$5677', '11:$5680',
            '11:$568F')
CF0_JP_TEXT = ('そうびするとこうげきりょくがあがるぞ', 'おおきなダメージをあたえるぞ',
               'そうびするとぼうぎょりょくがあがるぞ', 'そうびすると',
               'なげて つかうこともできるぞ', 'なげても こうかがあるぞ',
               'とおくからモンスターを', 'そうびすれば セレクトをおしながら',
               'Aボタンで やを うてるぞ', 'カベになげてわれば なかみを', 'とりだせるぞ',
               'なかまにも きいてしまうぞ', 'モンスターにむかって ふると')
CF0_CELLS = {i: len(t) for i, t in enumerate(CF0_JP_TEXT)}


def cf0_from_trans(trans, encode=None):
    """-> ({arg: cells}, {arg: text}) for `<cF0:xx>`, English where en.tsv has it.

    `trans` maps loc -> English text. `encode` is build.encode_en; passing it is what
    makes a `<br>` or a `<$XX>` in one of these cost what it really costs rather than its
    length in source characters. Without it the character count stands in, which is right
    for the plain labels these are today and wrong the moment one grows a token.
    """
    cells, text = dict(CF0_CELLS), dict(enumerate(CF0_JP_TEXT))
    for i, loc in enumerate(CF0_LOCS):
        en = (trans.get(loc) or '').strip()
        if not en:
            continue
        text[i] = en
        cells[i] = Line(encode(en), 'end', 0, 0).cells({}) if encode else len(en)
    return cells, text

# Legacy substitution reservations, retained as conservative warnings while the Dot
# Gothic runtime-substitution census is open. They are source-policy numbers translated
# from the old fixed-width renderer (8/10 + the six characters the uniform VWF gained),
# NOT measured Dot pixel ceilings. `docs/VWF_BUDGETS.md` records the distinction and the exact
# True Rapier+99 falsifier. Keep the public names for compatibility with existing tools;
# do not use them to justify shortening a translation without measuring its actual path.
NAME_CAP = 14               # legacy `<var>` reservation; audit/re-engineer if crossed
ITEM_CAP = 16               # legacy `<cE3>` reservation; includes an item/count variant
PLAYER_NAME = 6             # tools/name6.py widened name entry from 4, landed 2026-08-03

SUBST_DOC = {0xE2: 'a monster/item name', 0xE3: 'an item name and count',
             0xEA: 'the player name', 0xE4: 'a number', 0xE5: 'a number', 0xE6: 'a number'}

# An UNKNOWN substitution cannot fail a build, and the Japanese is what settles that.
# The player name is different: its producer and six-character input limit are known, so
# production_widths()/dot_production_widths() enforce its real worst case. Fifteen
# shipped Japanese lines go over 18 cells once `<var>` is charged the 8-cell cap --
# `<var>は モンスターにかこまれた！` is 14 literal cells and leaves 4 for the name, which no
# real monster name fits. So the original game truncates these too, and a check that
# refused them would be refusing text Nintendo shipped.
#
# The build therefore fails on the FLOOR: every substitution charged the least it can
# possibly draw, which is one cell (no name is empty and $4294 always emits a final digit,
# leading zeros suppressed). A line over 18 at the floor truncates for EVERY player, every
# time, with no runtime value that could save it -- which is exactly the class of error
# `for <cE4> Points of damage!` and `Innkeeper: Are you OK?` were, both pure literal
# overruns. The caps are reported as headroom instead; see `headroom()`.
SUBST_FLOOR = 1


def subst_widths(name_cap=NAME_CAP, item_cap=ITEM_CAP, player=PLAYER_NAME):
    """Legacy review reservations; not production clipping or glossary limits."""
    w = dict(DIGITS)
    w[0xE2] = name_cap
    w[0xE3] = item_cap
    w[0xEA] = player
    return w


def floor_widths():
    """Least case: what the build FAILS on, because nothing at runtime can beat it."""
    return {c: SUBST_FLOOR for c in SUBST_DOC}


def production_widths():
    """Source-glyph costs enforced in production.

    Unknown producers remain at their non-empty floor. ``<name>`` is settled: name entry
    stores up to six glyphs, so a translated line must stage all six.
    """
    widths = floor_widths()
    widths[0xEA] = PLAYER_NAME
    return widths


def help_widths(base=None, cf0=None):
    """Widths for the item-description path: `<cF0:xx>` pastes real text and costs cells.

    Unlike a `<var>`, this is not a runtime value with a floor -- the expansion is a fixed
    string sitting in bank 11, so its width is known exactly and the check may charge the
    whole of it. `base` is whichever production/review width table the caller wanted.
    """
    w = dict(production_widths() if base is None else base)
    w[0xF0] = dict(CF0_CELLS if cf0 is None else cf0)
    return w


def _cost(width, arg):
    """Cells a control code draws. A dict width is looked up by the code's argument byte.

    That indirection exists for `<cF0:xx>` alone: it is the one code whose output depends
    on its operand rather than on a runtime value.
    """
    if isinstance(width, dict):
        return width.get(arg[0], 0) if arg else 0
    return width


def _pixel_cost(width, arg):
    """Return ``(advance, painted extent)`` for one control expansion."""
    value = _cost(width, arg)
    if isinstance(value, tuple):
        return value
    return value, value


def dot_floor_widths(font):
    """Narrowest physically possible approved values for definite-overflow checks."""
    letter = min(font.advances[ch] for ch in EN_CODES if ch.isalpha())
    digit = min(font.advances[str(n)] for n in range(10))
    return {code: (digit if code in DIGITS else letter) for code in SUBST_DOC}


def dot_player_name_width(font):
    """Worst six-character player-name ``(advance, painted extent)`` in this font."""
    widest_advance = max(font.advances.values())
    widest_tail = max(
        (dotfont.ink_span(glyph)[1] + 1 if dotfont.ink_span(glyph) else
         font.advances[ch])
        for ch, glyph in font.glyphs.items())
    return (PLAYER_NAME * widest_advance,
            (PLAYER_NAME - 1) * widest_advance + widest_tail)


def dot_production_widths(font):
    """Pixel costs enforced in production; exact player cap plus other-value floors."""
    widths = dot_floor_widths(font)
    widths[0xEA] = dot_player_name_width(font)
    return widths


def dot_metrics(data, font, bank=None, controls=None):
    """Return ``(advance, painted extent, non-Dot codes)`` for renderer input.

    Painted extent is the clipping authority.  Advance includes the final glyph's
    trailing side bearing, so it can be one or more pixels larger even when every inked
    pixel fits (the formerly longest equipment substitution was the motivating case).
    """
    controls = controls or {}
    arity = codec.arity_for(bank)
    pen = extent = i = 0
    unknown = set()
    while i < len(data):
        code = data[i]
        if codec.CONTROL_MIN <= code <= codec.CONTROL_MAX:
            n = arity.get(code, 0)
            advance, ink = _pixel_cost(controls.get(code, 0),
                                       data[i + 1:i + 1 + n])
            # A zero-width control such as <end> paints nothing.  Counting its pen
            # coordinate as extent turns a legal final side-bearing into one pixel of
            # imaginary ink (three exact-144px lines exposed this after the 30-glyph
            # reflow).  Substitutions with real ink still extend the painted bound.
            if ink:
                extent = max(extent, pen + ink)
            pen += advance
            i += n
        elif code not in codec.COMBINING:
            ch = dotfont.CODE_TO_EN.get(code)
            if ch is None:
                advance = ink = 8
                unknown.add(code)
            else:
                advance = font.advances[ch]
                span = dotfont.ink_span(font.glyphs[ch])
                ink = span[1] + 1 if span else 0
            extent = max(extent, pen + ink)
            pen += advance
        i += 1
    return pen, extent, unknown


def dot_help_widths(font, cf0_data=None):
    """Dot pixel costs for help-path inline fragments, keyed like ``help_widths``."""
    widths = dot_production_widths(font)
    # An untranslated fragment takes the native 8px fallback. Current production rows are
    # English and overwrite these values below, but keeping the fallback makes alternate
    # TSVs conservative instead of accidentally charging an absent fragment zero pixels.
    widths[0xF0] = {index: (cells * CELL_PX, cells * CELL_PX)
                    for index, cells in CF0_CELLS.items()}
    if cf0_data is not None:
        widths[0xF0].update({index: dot_metrics(data, font, bank=11)[:2]
                             for index, data in cf0_data.items()})
    return widths


# ---------------------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------------------
def glyph(b, jp=False):
    """One byte -> the character it DRAWS. Latin unless asked for the Japanese table."""
    if not jp and b in EN_CHARS:
        return EN_CHARS[b]
    return codec.decode(bytes([b]))


def show(data, jp=False, bank=None):
    """Bytes -> readable text, control codes as their tokens. codec.decode with a font."""
    arity = codec.arity_for(bank)
    out, i = [], 0
    while i < len(data):
        b = data[i]
        if codec.CONTROL_MIN <= b <= codec.CONTROL_MAX:
            n = arity.get(b, 0)
            out.append(codec.decode(data[i:i + 1 + n], bank))
            i += n
        else:
            out.append(glyph(b, jp))
        i += 1
    return ''.join(out)


class Line:
    """One rendered line: the bytes that reach the buffer, and how they were ended."""

    def __init__(self, data, ends, box, row, bank=None):
        self.data, self.ends, self.box, self.row = data, ends, box, row
        # Which dispatch table read this line. $E7 and $F0 take an argument on the
        # message path and none on the dialogue path, so on banks 11/14 the byte after
        # one is a glyph that costs a cell. See codec.arity_for.
        self.bank = bank

    def cells(self, widths):
        """Cells this line draws. Literal characters plus whatever gets substituted.

        A combining mark is drawn OVER the preceding character (13:$6B06 swaps in tile
        $DE) and costs no cell, which is the same rule build.cells() uses.
        """
        table = codec.arity_for(self.bank)
        n = i = 0
        while i < len(self.data):
            b = self.data[i]
            if codec.CONTROL_MIN <= b <= codec.CONTROL_MAX:
                arity = table.get(b, 0)
                n += _cost(widths.get(b, 0), self.data[i + 1:i + 1 + arity])
                i += arity
            elif b not in codec.COMBINING:
                n += 1
            i += 1
        return n

    def text(self, jp=False):
        return show(self.data, jp, self.bank)


def split_lines(data, bank=None):
    """Bytes -> [Line]. Breaks at $EF and $EE; $EE also starts a new box.

    Both composer paths agree on this and neither has a third case: the bank-13 stager
    leaves the loop on $FF/$EE/$EF (13:$40DC-$40E6), and on the dialogue path $EE's and
    $EF's own handlers (13:$6A65/$6A6E) return $FF to break the same loop. $ED (`<end>`)
    is NOT a break -- it sets a flag at $CFC4 and the line carries on -- which is why the
    Japanese writes `<end><brk>` and not `<end>` alone.
    """
    arity = codec.arity_for(bank)
    out, cur, box, row, i = [], bytearray(), 0, 0, 0
    while i < len(data):
        b = data[i]
        if b in BREAKS:
            out.append(Line(bytes(cur), BREAKS[b], box, row, bank))
            cur = bytearray()
            if b == 0xEE:
                box, row = box + 1, 0
            else:
                row += 1
        else:
            cur.append(b)
            if codec.CONTROL_MIN <= b <= codec.CONTROL_MAX:
                n = arity.get(b, 0)
                cur += data[i + 1:i + 1 + n]
                i += n
        i += 1
    out.append(Line(bytes(cur), 'end', box, row, bank))
    return out


def buffer_bytes(data, scope='line', widths=None, bank=None):
    """Bytes the fullest fill of the staging buffer -- the ceiling BUF_LOOP1/2 bound.

    Control codes that only set a flag still take their byte on the dialogue path
    (13:$6908 stores it), so this counts every byte and every substitution, which is the
    conservative direction.

    `scope` is how much text shares one fill, and it differs by renderer:

      'line'  the composer, which re-clears $CF07 for every line.
      'box'   the item-description screen, where `4:$49A7` zeroes $C616 once and
              `13:$7E49` walks the whole page into it. PER PAGE, not per string: the
              stager leaves its loop on `$EE`, so a `<brk>` starts a fresh fill. Summing
              a whole string instead called the shipped Fusion Pot text a 245-byte
              overrun of a 120-byte buffer, which it is not -- it is five pages.
    """
    widths = floor_widths() if widths is None else widths
    per = {}
    for ln in split_lines(data, bank):
        n = len(ln.data) + sum(_cost(widths.get(b, 0), ln.data[i + 1:])
                               for i, b in enumerate(ln.data))
        key = ln.box if scope == 'box' else (ln.box, ln.row)
        per[key] = per.get(key, 0) + n
    return max(per.values(), default=0)


# ---------------------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------------------
def check(data, width=WIDTH, per_box=LINES_PER_BOX, buf=None, jp=False, widths=None,
          buf_scope='line', bank=None, font=None, pixel_limit=LINE_PX,
          pixel_widths=None):
    """-> [(kind, message)] for everything about `data` that CANNOT render.

    Empty means it renders. `kind` is what build.py reports in the worklist. Unknown
    substitutions are measured at their floor; the settled six-character player name is
    measured at its real maximum. Pass `widths` for a renderer-specific override;
    `help_widths()` does so because `<cF0:xx>` is fixed inline text.
    """
    floor = production_widths() if widths is None else widths
    lines = split_lines(data, bank)
    out = []
    for ln in lines:
        n = ln.cells(floor)
        if n > width:
            sub = sorted({b for b in ln.data if b in floor})
            why = ('' if not sub else
                   '  (runtime contribution charged by the production width table: %s)'
                   % ', '.join('<%s>' % codec.CONTROL[b] for b in sub))
            out.append(('line_too_long',
                        'box %d line %d stages %d glyphs, this renderer accepts %d and '
                        'DISCARDS the rest: %r%s' % (ln.box + 1, ln.row + 1, n, width,
                                                     ln.text(jp), why)))
        if font is not None and not jp:
            controls = dot_production_widths(font) if pixel_widths is None else pixel_widths
            advance, extent, _unknown = dot_metrics(ln.data, font, bank, controls)
            if extent > pixel_limit:
                out.append(('line_too_wide_px',
                            'box %d line %d advances %dpx and paints %dpx; the canvas is '
                            '%dpx and clips %dpx of ink: %r'
                            % (ln.box + 1, ln.row + 1, advance, extent, pixel_limit,
                               extent - pixel_limit, ln.text(jp))))
    deep = {}
    for ln in lines:
        deep[ln.box] = max(deep.get(ln.box, 0), ln.row + 1)
    for b, rows in sorted(deep.items()):
        if rows > per_box:
            out.append(('box_too_deep',
                        'box %d has %d lines and a box holds %d -- there is no row %d, so '
                        'it overwrites line 1. Split it with <end><brk>'
                        % (b + 1, rows, per_box, per_box + 1)))
    if buf:
        n = buffer_bytes(data, scope=buf_scope, widths=floor, bank=bank)
        if n >= buf:
            out.append(('buffer_overrun',
                        'stages %d bytes into a %d-byte buffer, past what the renderer '
                        'clears' % (n, buf)))
    return out


def headroom(data, widths=None, width=WIDTH, bank=None):
    """-> [(box, row, cells left for substitution, tokens)] for lines that substitute.

    This is docs/TEXT_REFERENCE.md section 4's table, computed instead of hand-written. It is a
    WARNING and never a build failure: the substituted text is a runtime value, and the
    Japanese itself leaves as little as 4 cells for a monster name. The report identifies
    templates for the producer/value census; it does not set one universal name cap.
    """
    widths = subst_widths() if widths is None else widths
    out = []
    for ln in split_lines(data, bank):
        toks = [b for b in ln.data if b in SUBST_DOC]
        if not toks:
            continue
        literal = ln.cells({c: 0 for c in SUBST_DOC})
        out.append((ln.box + 1, ln.row + 1, width - literal,
                    ' '.join('<%s>' % codec.CONTROL[b] for b in toks)))
    return out


# ---------------------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------------------
def _glyph_run(code, width):
    """A placeholder exactly `width` cells wide, so the preview measures like the screen."""
    name = codec.CONTROL.get(code, '$%02X' % code)
    if width >= len(name) + 2:
        return '[' + name.ljust(width - 2, '.') + ']'
    return name[:width].ljust(width, '.')


def render(data, widths=None, width=WIDTH, jp=False, cf0_text=None, bank=None):
    """-> [ [line-string, ...], ... ] one list per box, each string padded to `width`.

    Substitutions are drawn as a placeholder of the caller's declared review width.
    Production CLI previews use the one-glyph floor and report legacy headroom separately.
    Anything past `width` is shown, because the point is to see what gets lost.

    `<cF0:xx>` is drawn as the TEXT it pastes rather than as a placeholder, because that
    text is a fixed string and not a runtime value -- there is nothing to be worst-case
    about, and a translator needs to read the whole line to wrap the rest of it.
    """
    widths = subst_widths() if widths is None else widths
    boxes = []
    for ln in split_lines(data, bank):
        while len(boxes) <= ln.box:
            boxes.append([])
        out, i = [], 0
        while i < len(ln.data):
            b = ln.data[i]
            if codec.CONTROL_MIN <= b <= codec.CONTROL_MAX:
                arity = codec.arity_for(bank).get(b, 0)
                arg = ln.data[i + 1:i + 1 + arity]
                w = _cost(widths.get(b, 0), arg)
                if b == 0xF0 and w and cf0_text is not None and arg:
                    out.append(cf0_text.get(arg[0], '')[:w].ljust(w))
                elif w:
                    out.append(_glyph_run(b, w))
                i += arity
            elif b in codec.COMBINING:
                pass                        # drawn over the previous cell
            else:
                out.append(glyph(b, jp))
            i += 1
        boxes[ln.box].append(''.join(out))
    return boxes


def preview(data, widths=None, width=WIDTH, per_box=LINES_PER_BOX, jp=False, cf0_text=None,
            bank=None):
    """The boxes as text, with the cells that do not fit shown outside the frame."""
    out, boxes = [], render(data, widths, width, jp, cf0_text, bank)
    for bi, box in enumerate(boxes):
        out.append('    +' + '-' * width + '+')
        for ri, line in enumerate(box):
            keep, lost = line[:width], line[width:]
            flag = '  << LOSES %r' % lost if lost else ''
            if ri >= per_box:
                flag = flag or '  << NO SUCH ROW'
            out.append('    |%s|%s' % (keep.ljust(width), flag))
        out.append('    +' + '-' * width + '+')
        if bi != len(boxes) - 1:
            out.append('       (player presses A)')
    return '\n'.join(out)


# ---------------------------------------------------------------------------------------
# Which strings this applies to
# ---------------------------------------------------------------------------------------
# The composer draws banks 11, 13 and 14. Bank 13's messages arrive through the queue and
# render on the 18-cell path; banks 11 and 14 are staged through $CF8F and render on the
# dialogue path. A bank-31 box row is NOT composer text -- it is drawn by 31:$40D8 from the
# geometry table and build.py already measures it against the box's own width.
#
# Bank 11's 462 relocatable strings are monster and item NAMES, not standalone lines: they
# get substituted into measured templates at runtime. A standalone 18-cell test and the
# legacy NAME_CAP are both wrong as production verdicts, so they are excluded here and
# audited by `fontaudit.py` against known variants plus explicit producer-census warnings.
COMPOSER_BANKS = (11, 13, 14)

# Three bank-28 dialogue-selection tables hold short companion status lines.  Their
# Japanese entries contain no control code, so the generic bank-11/14 rule below used to
# misclassify them as names/menu labels -- and then skip geometry checks after English
# added `<br>`.  The reader is measured at 28:$421B-$422A: it indexes table $422C, loads
# the selected bank-14 pointer into bc, and calls 28:$41CD; that routine stores bc at
# $FF90 and calls $238B, the message-queue path.  Tables $424C and $425C are selected by
# the same surrounding dispatcher and are the other refs extract records on these rows.
DIALOGUE_TABLES = {
    28 * 0x4000 + (addr - 0x4000) for addr in (0x422C, 0x424C, 0x425C)
}

# The clear-condition list is ordinary bank-14 text, not dialogue.  Most entries are
# reached through the 36-pointer table at file $03BC30; four strings at $7E98-$7EC0 are
# walked by the same screen without an extracted reference.  The old "no refs means
# dialogue" fallback therefore caught those four by accident.  Keep the whole measured
# block together so adding a control-looking raw byte cannot turn a list label into a
# composer line.
CLEAR_CONDITION_RANGE = (0x7C78, 0x7ED8)
MENU_LABEL_RANGE = (0x5330, 0x5459)


def is_clear_condition(r):
    return (r['bank'] == 14
            and CLEAR_CONDITION_RANGE[0] <= _addr(r) <= CLEAR_CONDITION_RANGE[1])


def is_menu_label(r):
    """The 37-entry bank-11 menu-label table at 11:$52E0, plus Expert at its tail."""
    return (r['bank'] == 11
            and MENU_LABEL_RANGE[0] <= _addr(r) <= MENU_LABEL_RANGE[1])


def is_dialogue(r):
    """Does this string get laid out as LINES -- by the composer, or by a tilemap box?

    The name is older than the answer. It is the gate `build.py` and `--check` use to
    decide whether a string gets a geometry check at all, and the item descriptions have
    never been composer text either -- they passed only because bank 13 returns True
    wholesale. The SEALS are the same kind of string in a bank that does not, and they
    were falling through this gate: `refs` is non-empty (the table at 11:$5463) and they
    carry no control codes, so the last line returned False and NOTHING measured them.
    """
    if (r['bank'] not in COMPOSER_BANKS or r.get('box')
            or is_clear_condition(r) or is_menu_label(r)):
        return False
    if is_help(r):
        return True
    if r['bank'] == 13:
        return True
    if any(ref.get('kind') == 'table' and ref.get('table') in DIALOGUE_TABLES
           for ref in r['refs']):
        return True
    # Banks 11 and 14: in-place text is dialogue by construction (nothing points at it, so
    # the runtime message queue is the only way in -- the same rule pool.eligible uses).
    # A relocatable string there is a line only if it carries composer control codes; the
    # rest are names and menu labels reached by 11:$52D5, which never touch the composer.
    if not r['refs']:
        return True
    return any(codec.CONTROL_MIN <= b <= codec.CONTROL_MAX
               for b in bytes.fromhex(r['hex']))


def _addr(r):
    return int(r['loc'].split('$')[1], 16)


def is_seal(r):
    """Is this one of the 20 equipment ability lines -- box $13, 18 cells, ONE line?

    Same rule as `is_help`, and the same reason: `11:$7E40` selects on the address, from
    the 20-entry table at `11:$5463`, and nothing else in bank 11 lands in SEAL_RANGE.
    """
    return r['bank'] == 11 and SEAL_RANGE[0] <= _addr(r) <= SEAL_RANGE[1]


def is_help(r):
    """Is this drawn by BANK 31's tilemap box at 18 cells rather than by the composer?

    Two tables, one geometry: bank 13's 122 item descriptions (box 7) and bank 11's 20
    equipment seals (box `$13`, whose descriptor is box 7's byte for byte). What they
    share is the width and the renderer -- they differ in the line budget, so ask
    `geometry_for`, not this, for the number of lines.

    Decided by address range, because that is what the tables select on: `13:$554A` holds
    122 pointers and every one lands in HELP_RANGE, and nothing else in bank 13 does.
    `--selftest` re-checks that the range and the table agree.
    """
    if is_seal(r):
        return True
    return r['bank'] == 13 and HELP_RANGE[0] <= _addr(r) <= HELP_RANGE[1]


def geometry_for(r, proportional=True, vwf=True):
    """Return ``(source glyphs, lines, buffer)`` for the selected renderer build."""
    help_width = HELP_WIDTH if proportional else HELP_FIXED_WIDTH
    composer_width = WIDTH if proportional else (UNIFORM_WIDTH if vwf else FIXED_WIDTH)
    if is_seal(r):
        # The $78 buffer is shared -- item name plus up to four seals -- so the honest
        # ceiling is not 120 per seal. It does not need to be: five rows of 18 cells plus
        # a terminator each is 95 bytes, so the WIDTH check above already keeps the buffer
        # inside 120. Passing HELP_BUF here keeps the overrun message available for a
        # string that somehow measures narrow and stages wide.
        return help_width, SEAL_LINES_PER_BOX, HELP_BUF
    if is_help(r):
        return help_width, HELP_LINES_PER_BOX, HELP_BUF
    return composer_width, LINES_PER_BOX, (BUF_LOOP1 if r['bank'] == 13 else BUF_LOOP2)


def buffer_for(r):
    return geometry_for(r)[2]


# ---------------------------------------------------------------------------------------
# Self-test against the Japanese
# ---------------------------------------------------------------------------------------
# The two Japanese strings this model calls over-long, and why neither retracts it.
KNOWN_OVER = {
    '14:$7EE6': 'not script -- 294 cells of decoded garbage, an extraction false positive '
                'that survives because it round-trips (see the length heuristic in '
                'docs/FINDINGS.md). Nothing draws it.',
}

# Banks whose text dispatches through 13:$68CF rather than 13:$4126.
DIALOGUE_PATH_BANKS = (11, 14)


def _eb_pause_explains(bank, cells, line):
    """Is this line only over-long because $EB's PAUSE ARGUMENT was charged as a glyph?

    `14:$56EF` used to be a hand-listed exception here. Session 7's extraction fix added
    143 strings and produced SEVEN more instances of it, all in bank 11's ending farewells
    -- at which point listing them one by one would be recording a rule as a set of
    exceptions. So it is written as the rule.

    On the dialogue path $EB dispatches to 13:$690F, which reads ONE argument byte: the
    typewriter pause, a frame count that draws nothing. `codec.ARITY` says $EB takes no
    argument because the bank-13 path genuinely does not (13:$416D), and the cell model
    deliberately keeps codec.ARITY so it measures the same bytes the inserter writes.
    Hence exactly one over-charged cell per $EB, and no other error.

    THE EVIDENCE THAT THIS IS THE RULE AND NOT A CONVENIENT SUBTRACTION: every over-long
    Japanese dialogue line lands on EXACTLY 18 once its $EB count is removed -- 19-1,
    20-2, 21-3. A fudge factor would scatter them below the limit; the shipped script was
    written to 18 and it comes back to 18 on the nose, which is the same falsifier the
    rest of this self-test rests on. It stays a failure if a line is over for any other
    reason, and `14:$7EE6` above still is.
    """
    if bank not in DIALOGUE_PATH_BANKS:
        return None
    eb = line.data.count(0xEB)
    if not eb or cells - eb > FIXED_WIDTH:
        return None
    return ('%d cells, and all %d of the extra one(s) are `<mode1>` argument bytes. The '
            'dialogue path dispatches $EB to 13:$690F, which reads ONE argument -- the '
            'typewriter PAUSE, a frame count that draws nothing -- so the line is %d. See '
            '"two dispatch tables" in docs/FINDINGS.md.' % (cells, eb, cells - eb))


def selftest(script='script/script.json'):
    """Measure the Japanese under this model. It is the only known-good corpus there is.

    The claim being tested is narrow and falsifiable: the shipped script was written to
    this budget, so if the model is right almost every line lands at or under 18 and a
    good many land exactly on it. A model off by one cell in either direction could not
    produce that shape -- it would either push hundreds of lines over or leave the
    boundary empty.

    This measures against FIXED_WIDTH, not WIDTH, and must go on doing so. The Japanese
    was written for an 8px cell; VWF is a property of the English build. Re-pointing this
    at 30 would not make the model better, it would throw away the only falsifier the
    model has.
    """
    # A trailing no-ink control must not turn final side bearing into painted extent.
    # This regressed as three false 145/144 failures when prose first used the 30-glyph
    # edge, so keep an explicit invariant beside the corpus model.
    font = dotfont.load_approved()
    assert production_widths()[0xEA] == PLAYER_NAME
    # Thin Pixel-7 GB Compact's widest legal name glyph now advances 7px, with the
    # final ink ending one pixel before its cell edge.  Keep this exact assertion so a
    # future font edit cannot silently change every <name> fit calculation.
    assert dot_player_name_width(font) == (42, 41)
    sample = bytes(EN_CODES[ch] for ch in 'Wide')
    assert dot_metrics(sample + b'\xED', font, 14)[:2] == dot_metrics(sample, font, 14)[:2]

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strings = json.load(open(os.path.join(root, script), encoding='utf-8'))['strings']
    floor = floor_widths()
    hist, over, n, tight = {}, [], 0, []
    for r in strings:
        if not is_dialogue(r) or is_help(r):
            continue
        for ln in split_lines(bytes.fromhex(r['hex']), r['bank']):
            c = ln.cells(floor)
            hist[c] = hist.get(c, 0) + 1
            n += 1
            if c > FIXED_WIDTH:
                over.append((c, r['loc'], ln.text(jp=True),
                             _eb_pause_explains(r['bank'], c, ln)))
        for box, row, left, toks in headroom(bytes.fromhex(r['hex']), bank=r['bank']):
            tight.append((left, r['loc'], toks))
    print('%d Japanese dialogue lines; longest %d cells, %d of them at exactly %d'
          % (n, max(hist), hist.get(FIXED_WIDTH, 0), FIXED_WIDTH))
    print('distribution near the limit: %s'
          % ' '.join('%d:%d' % (c, hist[c]) for c in sorted(hist) if c >= FIXED_WIDTH - 3))
    bad = 0
    for c, loc, text, eb_why in sorted(over, key=lambda x: (-x[0], x[1])):
        why = KNOWN_OVER.get(loc) or eb_why
        print('  %-11s %3d cells  %s' % (loc, c, 'KNOWN: ' + why if why else 'UNEXPLAINED'))
        if not why:
            print('      %r' % text)
            bad += 1
    print()
    print('tightest substitution headroom in the Japanese (a WARNING class, not a failure '
          '-- these identify templates for the runtime producer census):')
    for left, loc, toks in sorted(tight)[:6]:
        print('  %-11s %2d cells left for %s' % (loc, left, toks))
    if bad:
        print('FAIL: %d Japanese line(s) over %d cells with no explanation -- the model is '
              'wrong, not the script.' % (bad, FIXED_WIDTH))
    else:
        print('OK: every Japanese dialogue line fits, or is one of the %d known exceptions.'
              % len(KNOWN_OVER))
    return (1 if bad else 0) + _selftest_help(strings)


def _selftest_help(strings):
    """The tilemap-box geometry, against the same corpus and the same way.

    Sharper than the composer's, because this region has no substitutions in it at all --
    every cell is literal text or a `<cF0:xx>` expansion whose width is known exactly. So
    the Japanese must land at or under 18 with nothing over, and inside its line budget.
    It does, on both counts, and the composer's own geometry gets both wrong: it
    under-reads the widest lines (charging `<cF0:xx>` nothing) while calling 51 shipped
    boxes too deep.

    BOTH tables are measured here, and the seals are the sharper half. 20 strings, and
    the line budget the game gives them is ONE -- so `SEAL_LINES_PER_BOX` is falsified by
    any shipped seal that breaks, and none does. Their widths land where box $13's
    descriptor says they should: nothing over 18, three exactly on it.
    """
    hw = help_widths(cf0=CF0_CELLS)
    hist, over, deep, n = {}, [], [], 0
    seals = 0
    naive_deep = 0
    for r in strings:
        if not is_help(r):
            continue
        n += 1
        seals += is_seal(r)
        per_box = geometry_for(r, proportional=False)[1]
        data = bytes.fromhex(r['hex'])
        rows = {}
        for ln in split_lines(data, r['bank']):
            c = ln.cells(hw)
            hist[c] = hist.get(c, 0) + 1
            rows[ln.box] = max(rows.get(ln.box, 0), ln.row + 1)
            if c > HELP_FIXED_WIDTH:
                over.append((c, r['loc'], ln.text(jp=True)))
        for box, k in sorted(rows.items()):
            if k > per_box:
                deep.append((r['loc'], box + 1, k))
            if k > LINES_PER_BOX:
                naive_deep += 1
    print()
    print('%d Japanese tilemap-box strings -- %d item descriptions (13:$554A, box 7) and '
          '%d equipment seals (11:$5463, box $13); longest line %d cells, %d of them at '
          'exactly %d' % (n, n - seals, seals, max(hist),
                          hist.get(HELP_FIXED_WIDTH, 0), HELP_FIXED_WIDTH))
    print('distribution near the limit: %s'
          % ' '.join('%d:%d' % (c, hist[c]) for c in sorted(hist)
                     if c >= HELP_FIXED_WIDTH - 3))
    print('the composer geometry (%d cells, %d lines) calls %d of these boxes too deep -- '
          'that is the model this replaces' % (UNIFORM_WIDTH, LINES_PER_BOX, naive_deep))
    for c, loc, text in sorted(over, reverse=True)[:6]:
        print('  OVER %-11s %3d cells  %r' % (loc, c, text))
    for loc, box, k in deep[:6]:
        print('  DEEP %-11s box %d has %d lines' % (loc, box, k))
    if over or deep:
        print('FAIL: the tilemap-box model is wrong -- %d line(s) over %d cells, %d '
              'box(es) deeper than their line budget, in text the game shipped.'
              % (len(over), HELP_FIXED_WIDTH, len(deep)))
        return 1
    print('OK: every Japanese tilemap-box line fits %d cells; every description fits %d '
          'lines and every seal fits %d.'
          % (HELP_FIXED_WIDTH, HELP_LINES_PER_BOX, SEAL_LINES_PER_BOX))
    return 0


# ---------------------------------------------------------------------------------------
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument('locs', nargs='*', help='loc keys; default is every translated one')
    ap.add_argument('--jp', action='store_true', help='preview the Japanese instead')
    ap.add_argument('--check', action='store_true', help='failures only; exit 1 if any')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--en', default='script/en.tsv')
    ap.add_argument('--name-cap', type=int, default=NAME_CAP)
    ap.add_argument('--player-name', type=int, default=PLAYER_NAME)
    ap.add_argument('--player-text',
                    help='replace <name> with this literal for an exact source/pixel '
                         'audition (the name-entry field accepts at most six characters)')
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    import build as B                            # only needed for encode_en
    if args.player_text is not None:
        if not args.player_text:
            ap.error('--player-text cannot be empty')
        if len(args.player_text) > PLAYER_NAME:
            ap.error('--player-text accepts at most %d characters' % PLAYER_NAME)
        try:
            B.encode_en(args.player_text)
        except ValueError as exc:
            ap.error('--player-text is not encodable: %s' % exc)
    legacy_widths = subst_widths(name_cap=args.name_cap, player=args.player_name)
    widths = production_widths()
    strings = json.load(open(os.path.join(root, 'script/script.json'),
                             encoding='utf-8'))['strings']
    by_loc = {r['loc']: r for r in strings}

    trans = {}
    if not args.jp:
        for line in open(os.path.join(root, args.en), encoding='utf-8'):
            if line.startswith('#') or '\t' not in line:
                continue
            k, v = line.split('\t', 1)
            if v.strip():
                trans[k.strip()] = v.rstrip('\n')

    font = dotfont.load_approved()
    cf0_cells, cf0_text = cf0_from_trans(trans, B.encode_en)
    cf0_pixel_data = {}
    for index, text in cf0_text.items():
        try:
            cf0_pixel_data[index] = B.encode_en(text, 11)
        except ValueError:
            pass
    composer_pixel_widths = dot_production_widths(font)
    help_pixel_widths = dot_help_widths(font, cf0_pixel_data)

    want = args.locs or sorted(by_loc if args.jp else trans,
                               key=lambda k: (by_loc[k]['bank'], k) if k in by_loc else (0, k))
    bad = 0
    for loc in want:
        r = by_loc.get(loc)
        if r is None:
            print('%s -- no such string' % loc)
            bad += 1
            continue
        if not is_dialogue(r):
            if args.locs:
                print('%s is not composer dialogue (bank %d%s) -- nothing to preview'
                      % (loc, r['bank'], ', menu box row' if r.get('box') else ''))
            continue
        if args.jp or loc not in trans:
            data = bytes.fromhex(r['hex'])
        else:
            lead = bytes.fromhex(r['hex'])[:1] == b'\xb4'   # keep a leading-space indent
            try:
                shown = trans[loc]
                if args.player_text is not None:
                    shown = shown.replace('<name>', args.player_text)
                data = B.encode_en((' ' if lead else '') + shown, r['bank'])
            except ValueError as exc:
                print('%-11s encode error: %s' % (loc, exc))
                bad += 1
                continue
        jp = args.jp or loc not in trans
        w, per_box, buf = geometry_for(r)
        help_ = is_help(r)
        lw = help_widths(widths, cf0_cells) if help_ else widths
        problems = check(data, width=w, per_box=per_box, buf=buf, jp=jp,
                         widths=help_widths(cf0=cf0_cells) if help_ else None,
                         buf_scope='box' if help_ else 'line', bank=r['bank'],
                         font=font, pixel_widths=(help_pixel_widths if help_ else
                                                  composer_pixel_widths))
        if problems:
            bad += 1
        if args.check and not problems:
            continue
        what = ('equipment seal' if is_seal(r) else 'item description') if help_ else None
        print('%s  (%s)' % (loc, '%s -- %d source glyphs / %dpx, %d line%s'
                            % (what, w, LINE_PX, per_box,
                               '' if per_box == 1 else 's')
                            if help_ else '%s -- %d source glyphs / %dpx'
                            % ('bank 13 message' if r['bank'] == 13 else
                               'bank %d dialogue' % r['bank'], w, LINE_PX)))
        print(preview(data, lw, width=w, per_box=per_box, jp=jp,
                      cf0_text=cf0_text if help_ else None, bank=r['bank']))
        for kind, msg in problems:
            print('    !! %s: %s' % (kind, msg))
        for box, row, left, toks in headroom(data, lw, width=w, bank=r['bank']):
            if left < max(legacy_widths[b] for b in SUBST_DOC):
                print('    -- legacy review: box %d line %d leaves %d source glyphs for %s'
                      % (box, row, left, toks))
        print()
    if args.check:
        print('%d string(s) checked, %d with problems' % (len(want), bad))
    return 1 if (args.check and bad) else 0


if __name__ == '__main__':
    sys.exit(main())
