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

PLAYER-NAMED UNIDENTIFIED ITEMS HAVE A SHARED CATEGORY PREFIX PRODUCER. ``11:$5244``
first calls ``11:$526D`` with the item's category, then appends the player's six-character
nickname from SRAM. Its native table emits ``うでわ：``, ``くさ：``, ``まきもの：``,
``つえ：``, ``つぼ：`` or ``はくし：``. With the Latin font those bytes appear as
garbage before otherwise-correct names such as ``Food`` and ``Poop``. The replacement
keeps the established producer and colon, but writes ``Bracer: ``, ``Herb: ``,
``Scroll: ``, ``Staff: ``, ``Pot: `` or ``Blank: `` from an expanded-bank helper.
"""
import gbasm
import gbemu
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

PLAYER_PREFIX_ENTRY = 0x526D
PLAYER_PREFIX_OLD = bytes.fromhex(
    'F5 C5 E5 CB 27 4F 06 00 21 83 52 09 2A 66 6F CD BC 52 E1 C1 F1 C9')
PLAYER_PREFIX_BANK = 0x32
PLAYER_PREFIX_INDEX = 0x05
PLAYER_PREFIX_AT = 0x405A
PLAYER_PREFIX_LIMIT = 0x4100
PLAYER_PREFIXES = {
    0x02: 'Bracer: ',
    0x05: 'Herb: ',
    0x06: 'Scroll: ',
    0x07: 'Staff: ',
    0x08: 'Pot: ',
    0x0C: 'Blank: ',
}


def _off(bank, addr):
    return bank * BANKSZ + (addr - 0x4000)


def _player_prefix_helper():
    branches = []
    loads = []
    strings = []
    for category, text in sorted(PLAYER_PREFIXES.items()):
        label = 'category%02x' % category
        branches += ['  cp $%02X' % category, '  jr z,%s' % label]
        loads += ['%s:' % label, '  ld hl,text%02x' % category, '  jr copy']
        payload = [EN_CODES[ch] for ch in text] + [0xFF]
        strings += ['text%02x:' % category,
                    '  db ' + ','.join('$%02X' % value for value in payload)]
    source = '\n'.join([
        'prefix:',
        '  push af',
        '  push bc',
        '  push hl',
    ] + branches + [
        '  jr done',
    ] + loads + [
        'copy:',
        '  ld a,[hl+]',
        '  cp $FF',
        '  jr z,done',
        '  ld [de],a',
        '  inc de',
        '  jr copy',
        'done:',
        '  pop hl',
        '  pop bc',
        '  pop af',
        '  ret',
    ] + strings)
    return gbasm.assemble(source, PLAYER_PREFIX_AT)


def _assert_player_prefix_helper(code, labels):
    """Run every category through the exact assembled helper before installing it."""
    bank = bytearray(BANKSZ)
    start = PLAYER_PREFIX_AT - 0x4000
    bank[start:start + len(code)] = code
    for category in range(0x0D):
        cpu = gbemu.Cpu({0: bytes(BANKSZ), PLAYER_PREFIX_BANK: bank},
                        bank=PLAYER_PREFIX_BANK)
        cpu.a = category
        cpu.b, cpu.c = 0xB1, 0xC2
        cpu.hl = 0xD345
        cpu.de = 0xC100
        cpu.call(labels['prefix'])
        expected = bytes(EN_CODES[ch] for ch in PLAYER_PREFIXES.get(category, ''))
        got = bytes(cpu.read(0xC100 + offset) for offset in range(len(expected)))
        if got != expected or cpu.de != 0xC100 + len(expected):
            raise SystemExit('itemfix: player-name category $%02X helper emitted %s at '
                             '$C100 and ended at $%04X; expected %s / $%04X'
                             % (category, got.hex(' '), cpu.de, expected.hex(' '),
                                0xC100 + len(expected)))
        if (cpu.a, cpu.b, cpu.c, cpu.hl) != (category, 0xB1, 0xC2, 0xD345):
            raise SystemExit('itemfix: player-name category $%02X helper clobbered '
                             'AF/BC/HL' % category)


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

    # Preserve the native category-prefix semantics for player-assigned identities, but
    # emit the category through the English code page. The original 22-byte selector is
    # guarded in full and replaced by a far-call stub. Bank 50's prefix is outside the
    # redirected-text arena, which begins at $4100.
    helper, labels = _player_prefix_helper()
    if PLAYER_PREFIX_AT + len(helper) > PLAYER_PREFIX_LIMIT:
        raise SystemExit('itemfix: %d-byte player-name prefix helper exceeds %d:$%04X'
                         % (len(helper), PLAYER_PREFIX_BANK, PLAYER_PREFIX_LIMIT))
    _assert_player_prefix_helper(helper, labels)
    entry = _off(11, PLAYER_PREFIX_ENTRY)
    got = bytes(buf[entry:entry + len(PLAYER_PREFIX_OLD)])
    if got != PLAYER_PREFIX_OLD:
        raise SystemExit('itemfix: expected player-name category producer at 11:$%04X, '
                         'found %s' % (PLAYER_PREFIX_ENTRY, got.hex(' ')))
    stub = bytes((0xD7, PLAYER_PREFIX_INDEX, PLAYER_PREFIX_BANK, 0xC9))
    buf[entry:entry + len(PLAYER_PREFIX_OLD)] = (
        stub + bytes([NOP]) * (len(PLAYER_PREFIX_OLD) - len(stub)))
    helper_at = _off(PLAYER_PREFIX_BANK, PLAYER_PREFIX_AT)
    if any(value != 0xFF for value in buf[helper_at:helper_at + len(helper)]):
        raise SystemExit('itemfix: player-name helper site %d:$%04X is occupied'
                         % (PLAYER_PREFIX_BANK, PLAYER_PREFIX_AT))
    table = _off(PLAYER_PREFIX_BANK, 0x4000) + PLAYER_PREFIX_INDEX - 1
    if bytes(buf[table:table + 2]) != bytes((0xFF, 0xFF)):
        raise SystemExit('itemfix: player-name far entry $%02X in bank %d is occupied'
                         % (PLAYER_PREFIX_INDEX, PLAYER_PREFIX_BANK))
    buf[helper_at:helper_at + len(helper)] = helper
    buf[table:table + 2] = bytes((labels['prefix'] & 0xFF,
                                  labels['prefix'] >> 8))

    notes.append('itemfix: runtime equipment minus (4:$5D20) $7D -> English hyphen $%02X; '
                 'arrow counter `本の` (4:$5D3D) -> one space; the row charges $C6DC '
                 'one cell instead of two; shared unidentified-item help (13:$5537) -> '
                 '`%s`; title (4:$5773) -> `%s`; shared empty-Pot See row (4:$7464) -> '
                 '`%s`; Back/Todo charge rows (4:$7473 -> $7471) -> `%s`; player-named '
                 'item prefixes -> Bracer/Herb/Scroll/Staff/Pot/Blank via %d:$%04X' %
                 (MINUS, UNIDENTIFIED_HELP_TEXT, UNIDENTIFIED_TITLE_TEXT,
                  EMPTY_POT_TEXT, ACTION_POT_TEXT, PLAYER_PREFIX_BANK,
                  PLAYER_PREFIX_AT))
