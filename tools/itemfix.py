#!/usr/bin/env python3
"""Normalize runtime item text embedded in formatter code paths.

The equipment-modifier formatter at ``4:$5D20`` emits the native minus code ``$7D``.
English text encodes ``-`` as ``$42``.  Menu VWF already normalizes the former, but the
dialogue composer sees a late ``$7D`` in e.g. ``Stepped on True Rapier-77`` only after
its 72px half-line boundary.  At that point it must preserve timing instead of restarting,
so the unsupported code becomes an 8px blank: the first 7 moves to the edge and the second
is clipped.  Emit the English hyphen code at the one sign-producing instruction instead.

The other two ``$7D`` immediates in the item-name routine are title delimiters, not signs;
they deliberately remain native and are handled by the menu renderer's shape-specific
normalization.

Found by Joey playing the session-4 build, 2026-08-04: the item list drew
`7<symbol>YSilver Arrow`, and picking up money said `Got 293Gitan` with no space.

Both come from the same place. `4:$5C6A` builds the count/suffix around an item name and
dispatches on the item's category (`[$CF79] & $0F`). Two categories put the count BEFORE
the name -- arrows (3) and gitan (11) -- and both are reached by the item list AND by the
composer's `<cE3>`, via `13:$41DF` and `13:$41EB` (`rst $10 / db $1D,$04`). So one fix
serves both screens.

    arrows   4:$5D37   the count, then `$A6` and `$23`
    gitan    4:$5CAB   the count, and nothing else

`$A6` and `$23` are `本` and `の` -- "7 (long-thin-things) of", which is how Japanese
counts arrows. `$23` is inside the range latinfont overwrites, so it now draws as `Y`;
`$A6` is above it and still draws its original tile. Hence `7<symbol>Y`.

WHAT THIS PATCHES, and what it deliberately does not.

Only the arrow pair, and only in place: `ld a,$A6 / ld [de],a / inc de / ld a,$23 /
ld [de],a / inc de` becomes one space plus four `nop`s, and one of the two `inc [hl]` on
the row's cell counter `$C6DC` becomes a `nop` because one cell fewer is now drawn. Same
byte count, no new space, nothing relocated -- bank 4 has no free run to relocate into.

**Gitan is NOT patched here.** It needs a byte INSERTED after `4:$5CAB`'s digits and bank
4 has nowhere to put one, so it is done in the script instead: `11:$452C` is translated as
` Gitan` with a leading space, which the count path then renders as `293 Gitan`. That is a
one-character edit against a patch that would have had to rebuild a routine, and it fixes
the item list at the same time. See script/en.tsv.

UNIDENTIFIED ITEM INFO USES TWO MORE DIRECT PRODUCERS. The ordinary Info path selects the
157-entry description-pointer table at ``13:$554A`` only when ``$CF7B`` bit 7 says the item's
identity is known. Otherwise ``13:$7E0D`` returns the literal address ``13:$5537`` for
every category and appearance. That 18-byte sentence is not table-referenced, so the
extractor correctly never treated it as a relocatable script row; with the English font
installed, its kana bytes appeared as Latin gibberish under names such as ``Sapphire
Bracer`` and ``Gold Staff``.

The Japanese is ``みしきべつなので よくわからない``: “It is unidentified, so its effect
is unclear.” ``Effect is unknown.`` is natural English and exactly 18 source bytes, so it
replaces the literal in place without moving the adjacent description-pointer table.

The name formatter at ``4:$574C`` separately copies ``みしきべつのアイテム`` (“Unidentified
Item”) from the direct literal at ``4:$5773`` into the Info title row. Its 11-byte slot
cannot hold either 12-letter ``Unidentified`` or 12-letter ``Unknown Item``. ``Unknown``
is the natural compact heading; the formatter supplies the surrounding hyphens itself.

THE EMPTY POT VIEWER HAS ITS OWN DIRECT LITERAL TOO. Floor -> See does not enter the item
help resolver. Bank 4 copies ``−なにも はいっていません−`` (“—Nothing is inside—”)
from ``4:$7464`` into its three-row contents box. Every empty pot with a See action shares
that row, so translating this one asserted 14-byte slot fixes the family without changing
category-specific actions.

BACK/TODO POT CHARGES USE A SECOND DIRECT LITERAL. Their empty-looking slots are not empty
storage: each is one consumable activation. The native ``$CC`` placeholder expands through
``4:$744A`` to ``  せなか`` for every charge, which the English font exposes as garbage.
The SNES English convention is ``Press``. The shorter centered ``Empty`` replacement above
leaves two asserted `$FF` bytes immediately before this literal, so its pointer can move
from `$7473` to `$7471` and hold ``  Press`` without relocating code or changing the
three-row producer.
"""
from latinfont import EN_CODES


BANKSZ = 0x4000
SPACE = 0x00                # EN_CODES[' ']; the ROM's own indent byte, e.g. 13:$4B59
MINUS = EN_CODES['-']
NOP = 0x00
UNIDENTIFIED_HELP_AT = 0x5537
UNIDENTIFIED_HELP_JP = bytes.fromhex(
    '2A 16 11 27 79 1C 1F 23 1D 79 00 30 12 36 10 31 1F 0C')
UNIDENTIFIED_HELP_TEXT = 'Effect is unknown.'
UNIDENTIFIED_HELP_EN = bytes(EN_CODES[ch] for ch in UNIDENTIFIED_HELP_TEXT)
assert len(UNIDENTIFIED_HELP_EN) == len(UNIDENTIFIED_HELP_JP) == 18
UNIDENTIFIED_TITLE_AT = 0x5773
UNIDENTIFIED_TITLE_JP = bytes.fromhex('2A 16 11 27 79 1C 23 42 43 54 62')
UNIDENTIFIED_TITLE_TEXT = 'Unknown'
UNIDENTIFIED_TITLE_EN = bytes(EN_CODES[ch] for ch in UNIDENTIFIED_TITLE_TEXT)
assert len(UNIDENTIFIED_TITLE_EN) <= len(UNIDENTIFIED_TITLE_JP) == 11
EMPTY_POT_AT = 0x7464
EMPTY_POT_JP = bytes.fromhex('7D 1F 20 2D 00 24 0C 41 1D 0C 29 18 38 7D')
EMPTY_POT_TEXT = 'Empty'
# Two fixed cells precede this literal in the 18-cell viewer row. Seven proportional
# spaces put the compact word on the screen's visual center without changing geometry.
EMPTY_POT_ROW = '       ' + EMPTY_POT_TEXT
EMPTY_POT_EN = bytes(EN_CODES[ch] for ch in EMPTY_POT_ROW)
assert len(EMPTY_POT_EN) <= len(EMPTY_POT_JP) == 14
ACTION_POT_POINTER_AT = 0x7450
ACTION_POT_POINTER_JP = bytes.fromhex('21 73 74')     # ld hl,$7473
ACTION_POT_POINTER_EN = bytes.fromhex('21 71 74')     # ld hl,$7471
ACTION_POT_JP_AT = 0x7473
ACTION_POT_JP = bytes.fromhex('00 00 18 1F 10 FF')    # `  せなか`
ACTION_POT_AT = 0x7471
ACTION_POT_TEXT = 'Press'
ACTION_POT_ROW = '  ' + ACTION_POT_TEXT
ACTION_POT_EN = bytes(EN_CODES[ch] for ch in ACTION_POT_ROW) + bytes([0xFF])
assert len(ACTION_POT_EN) == 8


def _off(bank, addr):
    return bank * BANKSZ + (addr - 0x4000)


def install(buf, notes):
    """Patch direct item-text producers; assert every replaced byte."""
    # The signed weapon/shield modifier is the only punctuation here that enters both the
    # menu row and composer substitutions as text.  Patch the immediate operand only.
    at = _off(4, 0x5D20)
    want = bytes([0x3E, 0x7D])       # ld a,$7D -- native minus
    if bytes(buf[at:at + len(want)]) != want:
        raise SystemExit('itemfix: expected `ld a,$7D` at 4:$5D20 (negative equipment '
                         'modifier), found %s' % bytes(buf[at:at + len(want)]).hex(' '))
    buf[at + 1] = MINUS

    # `4:$5D37`, entered with the count already in `a`:
    #     ea 90 ff   ld [$FF90],a
    #     cd dc 5c   call $5CDC        format the count into `de`
    #     3e a6      ld a,$A6          本
    #     12 13      ld [de],a / inc de
    #     3e 23      ld a,$23          の
    #     12 13      ld [de],a / inc de
    #     e5         push hl
    #     21 dc c6   ld hl,$C6DC
    #     34 34      inc [hl] / inc [hl]   two cells for the two glyphs
    #     e1 c9      pop hl / ret
    want = bytes([0x3E, 0xA6, 0x12, 0x13, 0x3E, 0x23, 0x12, 0x13])
    at = _off(4, 0x5D3D)
    got = bytes(buf[at:at + len(want)])
    if got != want:
        raise SystemExit(
            'itemfix: expected %s at 4:$5D3D (the arrow counter `本の`), found %s -- the '
            'address moved, and patching blind would corrupt code'
            % (want.hex(' '), got.hex(' ')))
    buf[at:at + len(want)] = bytes([0x3E, SPACE, 0x12, 0x13]) + bytes([NOP] * 4)

    # One glyph fewer, so charge the row one cell instead of two. `$C6DC` is the counter
    # the item list measures a row with -- the same one the `[N]` counter charges, and
    # getting it wrong is what let `Stopgap Staff[6]` overflow in session 3.
    at = _off(4, 0x5D49)
    if bytes(buf[at:at + 2]) != bytes([0x34, 0x34]):
        raise SystemExit('itemfix: expected `inc [hl] / inc [hl]` at 4:$5D49, found %s'
                         % bytes(buf[at:at + 2]).hex(' '))
    buf[at + 1] = NOP

    # `13:$7E0D` loads this address directly when an item's identity is hidden. The next
    # byte is its terminator and $554A immediately begins the normal description-pointer
    # table, so exact length is part of the safety assertion.
    at = _off(13, UNIDENTIFIED_HELP_AT)
    want = UNIDENTIFIED_HELP_JP + bytes([0xFF])
    got = bytes(buf[at:at + len(want)])
    if got != want:
        raise SystemExit(
            'itemfix: expected unidentified-help literal at 13:$5537, found %s -- the '
            'resolver or adjacent $554A table may have moved' % got.hex(' '))
    buf[at:at + len(want)] = UNIDENTIFIED_HELP_EN + bytes([0xFF])

    # `4:$574C` copies the shared hidden-identity heading until $FF. It owns 11 bytes plus
    # its terminator immediately before code resumes at $577F. Terminate the shorter
    # English heading and clear only the remainder of that proven literal slot.
    at = _off(4, UNIDENTIFIED_TITLE_AT)
    want = UNIDENTIFIED_TITLE_JP + bytes([0xFF])
    got = bytes(buf[at:at + len(want)])
    if got != want:
        raise SystemExit(
            'itemfix: expected unidentified-title literal at 4:$5773, found %s -- the '
            'name formatter or adjacent code may have moved' % got.hex(' '))
    replacement = UNIDENTIFIED_TITLE_EN + bytes([0xFF])
    buf[at:at + len(want)] = replacement + bytes([0xFF]) * (len(want) - len(replacement))

    # Floor -> See copies this literal directly into the pot-content staging row. It is
    # not an item description and has no pointer-table entry, so keep the in-place slot
    # explicit. The next two zero bytes and the Back-Pot action literal begin immediately
    # afterward; only the asserted 14 bytes and their terminator belong to this record.
    at = _off(4, EMPTY_POT_AT)
    want = EMPTY_POT_JP + bytes([0xFF])
    got = bytes(buf[at:at + len(want)])
    if got != want:
        raise SystemExit(
            'itemfix: expected empty-pot See literal at 4:$7464, found %s -- adjacent '
            'viewer code or the Back-Pot action may have moved' % got.hex(' '))
    replacement = EMPTY_POT_EN + bytes([0xFF])
    buf[at:at + len(want)] = replacement + bytes([0xFF]) * (len(want) - len(replacement))

    # Back/Todo Pot See expands one `$CC` token per charge through this shared direct
    # row. The centered Empty patch above deliberately leaves $7471-$7472 as $FF, so
    # move the literal back two bytes and spend those bytes on the five-letter label.
    pointer = _off(4, ACTION_POT_POINTER_AT)
    if bytes(buf[pointer:pointer + 3]) != ACTION_POT_POINTER_JP:
        raise SystemExit(
            'itemfix: expected Back/Todo action pointer at 4:$7450, found %s' %
            bytes(buf[pointer:pointer + 3]).hex(' '))
    native = _off(4, ACTION_POT_JP_AT)
    if bytes(buf[native:native + len(ACTION_POT_JP)]) != ACTION_POT_JP:
        raise SystemExit(
            'itemfix: expected Back/Todo action literal at 4:$7473, found %s' %
            bytes(buf[native:native + len(ACTION_POT_JP)]).hex(' '))
    action = _off(4, ACTION_POT_AT)
    if bytes(buf[action:action + 2]) != bytes([0xFF, 0xFF]):
        raise SystemExit(
            'itemfix: centered Empty row did not free 4:$7471-$7472 for Press')
    buf[pointer:pointer + 3] = ACTION_POT_POINTER_EN
    buf[action:action + len(ACTION_POT_EN)] = ACTION_POT_EN

    notes.append('itemfix: runtime equipment minus (4:$5D20) $7D -> English hyphen $%02X; '
                 'arrow counter `本の` (4:$5D3D) -> one space; the row charges $C6DC '
                 'one cell instead of two; shared unidentified-item help (13:$5537) -> '
                 '`%s`; title (4:$5773) -> `%s`; shared empty-Pot See row (4:$7464) -> '
                 '`%s`; Back/Todo charge rows (4:$7473 -> $7471) -> `%s`, all in place' %
                 (MINUS, UNIDENTIFIED_HELP_TEXT, UNIDENTIFIED_TITLE_TEXT,
                  EMPTY_POT_TEXT, ACTION_POT_TEXT))
