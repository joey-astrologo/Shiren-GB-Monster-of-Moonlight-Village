#!/usr/bin/env python3
"""Redirect in-place dialogue out of banks 11/14 and into the empty half of the ROM.

THE PROBLEM. 301 dialogue strings (15,788 bytes) have no ROM pointer at all: event code
assembles the address at runtime and pushes it through a message queue, so they cannot be
repointed and must be translated INSIDE their original byte count. Natural English is
1.66x, so most of them do not fit, and the 496 KiB the 1 MiB expansion added is unreachable
because each reader runs in the same bank as its text.

THE FIX, and why it is not a new invention. This is the standard answer for a text engine
whose pointers are not enumerable: leave the pointer alone and teach the READER to follow a
redirect. Four bytes at the original address say "continue from here instead", and the text
itself lives in a free bank. It converts a PER-STRING budget into an AGGREGATE one -- which
is the whole game, because per-string slack cannot be transferred and aggregate slack can.

WHY IT IS CHEAP HERE. Three ROM facts, each verified rather than assumed:

1. `13:$7589` is the ONE gate FOR STAGING. It loads the stored pointer from $CF7F/$CF80
   and dispatches on `bit 7,h` to bank 11's stager or bank 14's. A scan of all 2869
   `rst $08`/`rst $10` byte positions finds exactly ONE call site for each stager, both
   inside `$7589`, and only two callers of `$7589` itself (`13:$67ED`, `13:$688A`).
   Hooking one routine catches every in-place line in the game.

   **CORRECTED 2026-08-05: it is NOT the only writer of the RESUME POINTER, and the
   difference cost the town signs three sessions.** `13:$6CA8` writes `$CF7F/$CF80` too,
   from the `$EC` path, AFTER `$7589` has run -- so a redirect's continuation was being
   thrown away for 25 strings. "One gate" was measured about staging and then relied on
   for the pointer, which is a different fact. See `EC_OPEN` below.

2. The ROM has its own far-call. `rst $10 / db <index>,<bank>` maps a bank, calls the entry
   at that bank's `$4000` index table, and restores the caller's bank on return -- the ROM
   uses it 50+ times. So the new reader does NOT need bank-0 space (which is full at
   158/158 after the DTE expander): it lives in the pool bank and is reached in 3 bytes.
   That was the blocker the previous plan could not get past, and it was not real.

3. The stored pointer has two free tag values, and one of them is free STRUCTURALLY.
   Bank 11 fixes up with `set 6,h` and bank 14 with `xor $C0`, so a real $4000-$7FFF
   address stores as $00-$3F (tag 0,0) or $80-$BF (tag 1,0). That leaves $40-$7F (0,1) and
   $C0-$FF (1,1). Tag (1,1) CANNOT be produced by any legitimate pusher: bit 7 routes to
   bank 14, whose `xor $C0` would turn it into a $00-$3F address, which is bank 0 and not
   text. Tag (0,1) is only free by observation (`tools/ptrtags.py`: 0 of 28 distinct
   pointers over 12 seeded runs), because bank 11's `set 6,h` makes bit 6 a don't-care --
   so `NORMALISE` closes that hole by forcing bit 6 clear on every pointer that arrives
   from the queue. With it, bit 6 can only ever be set by this module.

4. `rst $10` IS REGISTER-TRANSPARENT IN BOTH DIRECTIONS. Measured 2026-07-31 on the live
   ROM, not read off the disassembly: a callee reached through the far call returns its
   own `a`, `bc`, `de` and `hl` to the caller. `0:$078D` pops the caller's registers just
   before entering the callee, and `0:$07D7` -- the return trampoline the call plants --
   pushes af/hl/bc on the way in and pops them on the way out, while never touching de.
   `tools/pool.py --selftest` re-derives it, and `scratchpad/farcall_regs.py` measured it
   by replacing the dispatcher with `ld hl,$BEEF / ld de,$CAFE / ld bc,$F00D` and reading
   the caller's registers back.

   This is what makes the RELOCATABLE redirect cheap too: a far-called resolver can hand
   back `hl = $CF8F` or an advanced `de`, so a hooked copy loop needs no WRAM protocol.

WHY THE POOL IS NOT TWO BANKS ANY MORE. The old record was `MARK, lo, hi, $FF` and packed
the bank into bit 15 of `lo/hi`: one bit of bank, two banks, 32 KiB -- against 31 empty
banks. Widening the record was the obvious fix and it is the wrong one, because the
CONTINUATION pointer is the real constraint: `$CF7F/$CF80` is 16 bits of persistent state
that has to name where the next line resumes, and a third byte of it would have to live in
WRAM, which is the one resource in this ROM that cannot be proven free.

So the record does not name text at all. It names an ENTRY in an index:

    record   MARK, lo, hi, $FF        in bank 6/11/13/14, `lo/hi` -> bank 33
    entry    lo, hi, bank             in bank 33, 3 bytes, one per LINE of text
    text                              in banks 34-62, no constraints at all
                                      (bank 63 is the opening cinematic)

The continuation is then just `entry + 3` -- an address in bank 33, which the existing
tag (0,1) already names. No new WRAM state, no wider record, and the bank ceiling is gone:
5,034 index entries addressing 483,840 bytes of text across 30 banks. Text addresses never
travel through a stager any more either, so the terminator and bad-page rules that
constrained where text could sit are gone with it.

    pool.py --selftest        assemble, and run the readers under tools/gbemu.py
    pool.py <in.gb> <out.gb>  install the mechanism (no strings moved)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm                                                    # noqa: E402

# ---------------------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------------------
DTE_TABLE_BANK = 0x20       # bank 32 is taken by the DTE table -- do not tread on it
INDEX_BANK = 0x21           # bank 33: the code, the stub tables, and the index
TEXT_BANKS = tuple(range(0x22, 0x3F))       # banks 34-62: text; bank 63 is intro.py
POOL_A = INDEX_BANK         # kept: tools and notes still say POOL_A for "the code bank"

# Entries in a bank's own index table at $4000. The far call reads its target from
# ($4000 + n - 1, $4000 + n), so only ODD n names a whole pointer.
FAR_DISPATCH = 0x03         # bank 33: the 13:$7589 dispatcher
FAR_NORMALISE = 0x05        # bank 33: what 13:$67E0 used to do, plus `and $BF`
FAR_STAGE = 0x07            # bank 33: relocatable -> stage a line at $CF8F, return hl
FAR_COPY = 0x09             # bank 33: relocatable -> copy to [de], terminator INCLUDED
FAR_COPYN = 0x0B            # bank 33: relocatable -> copy to [de], terminator EXCLUDED
FAR_RENDER = 0x0D           # bank 33: relocatable -> render ONE line to [de]
FAR_READ = 0x03             # every TEXT bank: one reader, mode in `a`

# The three shapes of copy loop this ROM has. A redirected string must be delivered by a
# loop that agrees with the one it replaced about the terminator, or the destination ends
# up one byte short or one byte long -- which is a corrupted menu, not a crash, and would
# not show up in a reference check.
MODE_LINE = 0               # bc -> $CF8F, stop on $EE/$EF/$FF, terminator copied
MODE_STR = 1                # bc -> [de], stop after $FF          (`2A 12 13 FE FF 20`)
MODE_STRN = 2               # bc -> [de], stop BEFORE $FF         (`2A FE FF 28 .. 12 13`)
MODE_RENDER = 3             # bc -> [de], ONE line of 13:$7E51's control-aware render

CODE_ORG = 0x4010           # code starts past the index table
STUBS = 0x4300              # one 4-byte stub per text bank, page-aligned for `ld h`
INDEX_ORG = 0x4400          # 3-byte entries from here to $8000: 5120 of them
TEXT_ORG = 0x4100           # text banks: past their own index table and reader

# Bank 46's first $300 bytes after the shared text reader are a real code reservation,
# not a convenient-looking $FF run.  menuvwf installs the title/pop-up category
# allocator at $4060 and rankvwf installs the screen manager/static raster behind it.
# Starting this bank's redirected text at $4400 keeps normal, shuffled and redirect-all
# layouts disjoint by construction.
RANK_SCREEN_BANK = 0x2E
RANK_SCREEN_TEXT_ORG = 0x4400
# Bank 60's prefix is a declared menu-transition code arena. menuvwf owns far indices
# $05/$07/$09/$0D/$0F and helpers through $46FF; markers owns far index $0B and its
# graphics tail. Starting redirected text at $4700 makes that ownership structural in normal and
# redirect-all
# layouts instead of depending on the current pool's high-water mark.
MENU_TRANSITION_BANK = 0x3C
MENU_TRANSITION_TEXT_ORG = 0x4700
# Bank 37's exact held-/Floor-Action admission gate and contained-Pot Info owner share
# the prefix. Keep redirected text structurally clear of both transition proofs.
ACTION_GATE_BANK = 0x25
ACTION_GATE_TEXT_ORG = 0x42A0
# Bank 62 shares its far table/tail with the title logo. The carried-/Floor-Action parent
# restorer, exact screen-1/screen-20 Info lifecycle, and carried-Pot entry publisher
# occupy the prefix below $5480, so
# redirected text begins there while the title asset remains independently protected at
# $7000.
ACTION_BLANK_BANK = 0x3E
ACTION_BLANK_TEXT_ORG = 0x5490

RENDER_TABLE = 13 * 0x4000 + 0x554A - 0x4000   # the help table, for reloc_verify


def needs_line_records(r):
    """Does an address-pinned redirect have to preserve its line layout in ROM?

    The help table at 13:$554A has two consumers.  The renderer follows a pool index
    continuation, but 13:$7D90 first walks the bytes at the table target and publishes
    one message-queue pointer per line.  A single four-byte record ends in $FF, so that
    pre-scan publishes only line one (the No-Hunger Bracer exposed this as a lone
    ``When equipped:``).  A record per line gives the unmodified pre-scan the same
    $EE/$EF/$FF shape as the translated text while keeping the pinned start address.
    """
    return any(ref.get('kind') == 'table' and ref.get('table') == RENDER_TABLE
               for ref in r.get('refs', ()))

GATE = 0x7589               # 13:$7589, the single staging gate
GATE_END = 0x75A2           # first byte after it -- 25 bytes to work in
QUEUE_STORE = 0x67E0        # 13:$67E0, where a queued pointer becomes $CF7F/$CF80
QUEUE_STORE_END = 0x67ED    # 13 bytes

STAGE_BUF = 0xCF8F          # where a line is staged for the composer
PTR_LO, PTR_HI = 0xCF7F, 0xCF80

# ---------------------------------------------------------------------------------------
# `13:$7589` IS NOT THE ONLY WRITER OF THE RESUME POINTER, and the second one is $EC's
# ---------------------------------------------------------------------------------------
#
# The docstring above says "$7589 is the ONE gate", and for STAGING it is. For the resume
# POINTER it is not: `13:$67F3` tests the first staged byte for `$EC` and, if it matches,
# calls `13:$6C73`, which re-derives the pointer as `hl + 2` -- hl still being the address
# the message came from -- and stores it through `13:$6CA8`. That store lands AFTER
# `$7589` has run, so it throws away whatever continuation the redirect left behind.
#
# For in-place Japanese `hl + 2` is exactly right: it skips the two bytes `EC arg` and
# resumes at the first line. For a redirected string it points into the middle of the
# 4-byte record -- `14:$41C2`'s `E9 61 4D FF` resumed at `4D FF`, which the composer drew
# as a single `シ` and stopped. That is what the town signs were doing.
#
# THE FIX IS A LAYOUT RULE, NOT A CODE PATCH. Leave the `EC arg` pair where the ROM
# expects it and put the record at +2, which is precisely where `$6C73` is going to point:
#
#     14:$41C2   EC 04 E9 61 4D FF          instead of   E9 61 4D FF
#     pool       "  Moonlight Village<br>…"  -- the prefix is NOT repeated here
#
# `$67ED`'s first stage then reads `EC 04 E9 61 4D FF`, sees `$EC` and takes the sign
# path; `$6C73` points at +2; and the NEXT stage is the one that finds the record and
# follows it. Both of `$6C73`'s branches (`bit 3` clear -> `$6CA8`, set -> `$6E81`) reach
# the same store, so this covers all of them.
EC_OPEN = 0xEC              # the sign/plaque opener: `EC arg`, consumed before the text
EC_HEAD = 2                 # bytes of it that must stay at the original address

# The redirect record written at the original address: MARK, lo, hi, $FF, where `lo/hi`
# names an ENTRY in bank 33's index -- never text. See the module docstring.
#
# MARK must be a byte no LINE can legitimately begin with -- the dispatcher tests the first
# staged byte, and it does so on continuation lines too, not just the first. $E9 is chosen
# because it begins zero of the 1264 extracted strings; `check_marker()` re-derives that
# from script.json rather than trusting this comment, and build-time insertion must refuse
# any bank 11/14 line that starts with it.
#
# NOT $E1, which two strings already start with, and NOT $EE/$EF/$FF, which terminate the
# staging copy and would truncate the record itself.
MARK = 0xE9
RECORD_LEN = 4

# The smallest arena an `$EC` string can be redirected in: the prefix stays put and the
# record goes after it. Below this, redirecting would corrupt the string that follows,
# so `head_bytes()` refuses and the string falls through to the ordinary `too_long` path.
EC_MIN = EC_HEAD + RECORD_LEN

# The staging copy stops on these, so a record byte may not BE one of them. `hi` is an
# index address in $44-$7F and cannot collide; `lo` is constrained by the allocator, which
# skips the three offending entry addresses. TEXT addresses are now free of this rule
# entirely -- they live in an index entry, which no copy loop ever walks.
TERMINATORS = (0xEE, 0xEF, 0xFF)

ENTRY_LEN = 3               # lo, hi, bank

NORMALISE = True            # install the queue-pointer normalisation (see fact 3)

# What must be at the two patch sites before they are overwritten. `build.py` relocates
# bank 13 text, and a patch that writes through a moved string is exactly the class of bug
# that put a `ld [$CE01],a` into this ROM and cost three sessions -- so this is checked,
# not assumed, on every install.
EXPECT_GATE = bytes.fromhex('f5e5fa80cf67fa7fcf6fcb7c2005d70d0b1803d7030ee1f1c9')
EXPECT_QUEUE = bytes.fromhex('67cd7b3c6f7cea80cf7dea7fcf')


# ---------------------------------------------------------------------------------------
# The code
# ---------------------------------------------------------------------------------------
def text_reader_src():
    """Every TEXT bank's one entry point: source in `bc`, mode in `a`, destination in `de`.

    Source in bc because the dispatcher needs hl to reach the stub table and de belongs to
    the caller of the string copier; mode in a because a is the last register the
    dispatcher finishes with, so a single stub table serves all three loops.

    `line` is the stagers' own copy loop byte for byte, kept identical to `11:$56A5` and
    `14:$4010` on purpose: the composer downstream reads $CF8F with no idea where the line
    came from, so anything this does differently is a behaviour change smuggled in under a
    space fix. `str` and `strn` are the other two loops this ROM has -- and they are two,
    not one: `11:$52D5` copies the $FF into the destination and `11:$52BC` stops before it.
    Assuming they agreed is exactly the kind of thing that costs a session here.

    `render` is `13:$7E51` for ONE line, and it is here rather than in a trampoline for the
    reason every other mode is: only code co-resident with the text can read it. It is the
    only mode that interprets control codes, because the loop it replaces does -- $ED is
    dropped, $EF/$EE/$FF end the line without being copied (the caller writes what belongs
    in the destination, since only it knows the RECORD's terminator), and $F0 consumes an
    argument byte and far-calls `11:$7E26`, which appends a table string to [de] itself.
    That nested `rst $10` is safe from here: it restores the caller's bank from byte 0 of
    the mapped bank, and install() writes every text bank's id there. The four-line budget
    is NOT here -- it lives in the caller, where $7E4F's `ld b,$04` put it.
    """
    return """
      ld h,b
      ld l,c
      and a
      jr nz,str
      ld bc,$%04X
    .lcopy:
      ld a,[hl+]
      ld [bc],a
      inc bc
      cp $EF
      jr z,.ldone
      cp $EE
      jr z,.ldone
      cp $FF
      jr nz,.lcopy
    .ldone:
      ret
    str:
      dec a
      jr nz,strn
    .scopy:
      ld a,[hl+]
      ld [de],a
      inc de
      cp $FF
      jr nz,.scopy
      ret
    strn:
      dec a
      jr nz,render
    .ncopy:
      ld a,[hl+]
      cp $FF
      ret z
      ld [de],a
      inc de
      jr .ncopy
    render:
      ld a,[hl+]
      cp $FF
      ret z
      cp $EE
      ret z
      cp $EF
      ret z
      cp $ED
      jr z,render
      cp $F0
      jr nz,.rlit
      ld a,[hl+]
      rst $10
      db $03,$0B
      jr render
    .rlit:
      ld [de],a
      inc de
      jr render
    """ % STAGE_BUF


def read_entry_src(mode):
    """Follow one index entry: map its text bank and run that bank's reader in `mode`.

    Entered with hl -> a 3-byte entry in bank 33 (which is mapped: this runs there).
    Leaves hl = the NEXT entry, which is what the continuation pointer has to be, and
    passes the text address to the text bank in bc.

    `call jphl` is the indirect call the LR35902 does not have: `jp hl` reaches the stub,
    and the stub's own `ret` lands back after the call. The stub table is page-aligned so
    the index arithmetic is four bytes with no carry to worry about. `a` is loaded with the
    mode AFTER that arithmetic has finished with it, which is what lets three readers share
    one table of stubs.
    """
    return """
      ld a,[hl+]
      ld c,a
      ld a,[hl+]
      ld b,a
      ld a,[hl+]
      push hl
      sub $%02X
      add a,a
      add a,a
      ld l,a
      ld h,$%02X
      ld a,$%02X
      call jphl
      pop hl
      ret
    """ % (TEXT_BANKS[0], STUBS >> 8, mode)


def dispatch_src():
    """Bank 33's routine: the whole dispatch, entered from 13:$7589 with hl set.

    Four ways in, and the fourth is the redirect. `bit 6,h` set means hl already names an
    index entry (a continuation, or a record we followed a moment ago). Otherwise bit 7
    picks bank 11's stager or bank 14's, exactly as `13:$7589` used to, and then the first
    staged byte is tested for the marker.
    """
    return """
      bit 6,h
      jr nz,entry
      bit 7,h
      jr nz,b14
      rst $10
      db $0D,$0B
      jr chk
    b14:
      rst $10
      db $03,$0E
    chk:
      ld a,[$%04X]
      cp $%02X
      ret nz
      ld a,[$%04X]
      ld h,a
      ld a,[$%04X]
      ld l,a
    entry:
      call read_entry
      ld a,h
      ld [$%04X],a
      ld a,l
      ld [$%04X],a
      ret
    stage:
      call read_entry
      ld hl,$%04X
      ret
    jphl:
      jp hl
    read_entry:
    """ % (STAGE_BUF, MARK, STAGE_BUF + 2, STAGE_BUF + 1,
           PTR_HI, PTR_LO, STAGE_BUF) + read_entry_src(MODE_LINE) + """
    read_entry_str:
    """ + read_entry_src(MODE_STR) + """
    read_entry_strn:
    """ + read_entry_src(MODE_STRN) + """
    read_entry_render:
    """ + read_entry_src(MODE_RENDER)


# ---------------------------------------------------------------------------------------
# The RELOCATABLE redirect: teaching the pointer-reached copy loops the same record
# ---------------------------------------------------------------------------------------
#
# In-place dialogue reaches the pool because ONE gate assembles its address. A relocatable
# string does not: it is reached by a 16-bit bank-relative pointer read by a loop running
# in the string's own bank, so its arena is only the space its Japanese vacates, and that
# arena is what every endgame projection has been short of.
#
# The fix is the same record, read by the same index, at each of those loops. What is NOT
# the same is where the record can be recognised: the in-place path can test $CF8F after
# the stager has run, but a relocatable loop has to test ROM at (hl) before it starts. So
# each site gets a trampoline in its own bank -- 20 bytes, allocated by build.py out of the
# same free runs the strings use -- and the six-or-nine-byte loop becomes a `call` to it.
#
# WHY THE ARENA CANNOT RUN OUT AGAIN. A redirected string costs 4 bytes in its own bank
# whatever its length, so a bank's worst case is 4 x (its string count): 1,848 bytes for
# bank 11 against a 4,331-byte arena, 1,360 for bank 13 against 6,977, 228 for bank 14
# against 1,131. Those are ratio-independent. The expansion factor stops being a thing that
# can make a bank overflow, which is the point of the whole exercise.
#
# WHAT A MISSED READER COSTS. The record ends in $FF, so a loop that has not been taught it
# copies four bytes and stops: two stray glyphs, no crash, no corruption of a neighbour.
# Benign -- but silent, which is why `build.py` refuses to redirect a string unless every
# table that points at it has been ATTRIBUTED to a hooked loop by `tools/readers.py`.

# (bank, first byte of the loop, bytes it occupies, mode, what it is)
#
# The loop is REPLACED by `call <trampoline>` and padded with `nop` to its original length,
# so control falls out of the patch exactly where it fell out of the loop. Every one of
# these sites was confirmed by tracing which pointer table it reads -- see readers.py --
# and `11:$52BC` is in the list because that trace found it reading bank 11's two largest
# tables (368 of its 462 relocatable strings). No note before this one named it.
# NOT `11:$52D5`. The DTE expander already owns those seven bytes (`raw_copy`), and
# build.py writes the DTE hooks after the repack, so a trampoline call there is silently
# overwritten -- the records stay in the bank and the reader that replaced the loop has
# never heard of them. build.py now refuses the collision rather than shipping it. Its
# table (`11:$52E0`, 37 entries, 256 bytes) is small enough that leaving it unredirectable
# costs bank 11 nothing it needs.
RELOC_SITES = [
    (13, 0x407E, 3, None, 'bank 13 message gate -> the 18-cell composer'),
    (11, 0x52BC, 9, MODE_STRN, 'bank 11 raw copy until $FF (tables $4537, $4FC4)'),
    (11, 0x51F0, 7, MODE_STR, 'bank 11 table copy A'),
    (11, 0x7E63, 7, MODE_STR, 'bank 11 table copy B'),
    (14, 0x7C1E, 7, MODE_STR, 'bank 14 table copy (table $7C30)'),
    # The help/tutorial renderer, reached only from `4:$49BC rst $10 / db $09,$0D`, which
    # zeroes 120 bytes at $C616 and passes them as `de`. Table $554A's OTHER two readers
    # need no hook: `13:$7D90` publishes one queue address per line and `13:$7DE8` counts
    # units, and both test only $EE/$EF/$FF, which a record run reproduces exactly.
    (13, 0x7E4C, 3, MODE_RENDER, 'help renderer 13:$7E49 (table $554A)'),
]

# What has to be at each site before it is overwritten, so a build that has already moved
# code or text there fails loudly instead of writing a `call` through a string.
RELOC_EXPECT = {
    (13, 0x407E): bytes.fromhex('cdc540'),
    (11, 0x52BC): bytes.fromhex('2afeff2804121318f7'),
    (11, 0x52D5): bytes.fromhex('2a1213feff20f9'),
    (11, 0x51F0): bytes.fromhex('2a1213feff20f9'),
    (11, 0x7E63): bytes.fromhex('2a1213feff20f9'),
    (14, 0x7C1E): bytes.fromhex('2a1213feff20f9'),
    (13, 0x7E4C): bytes.fromhex('cd0d7e'),
}

# `push bc` is not tidiness. `read_entry` carries the text address to the text bank in bc,
# and the far call hands the callee's bc back to the caller (fact 4) -- so without this the
# redirect arm returns with bc holding a pool address. `11:$7E63` keeps b as an index into
# $C6BE and c as a four-iteration counter across its loop (`inc b / dec c / jr nz,$7E48`),
# so that lands the game in a wild outer loop. The plain arm below does not touch bc, which
# is exactly why the two arms have to agree about it.
_FOLLOW = """
      ld a,[hl]
      cp $%02X
      jr nz,plain
      push bc
      inc hl
      ld a,[hl+]
      ld h,[hl]
      ld l,a
      rst $10
      db $%02X,$%02X
      pop bc
"""


def tramp_src(mode):
    """The trampoline for one copy loop: follow a record, else run the loop it replaced.

    `hl` and `a` are dead at every one of these sites once the loop ends -- 11:$51F7,
    11:$52DC and 14:$7C25 all `pop hl` immediately and 11:$7E6A works on bc -- so only
    `de` has to come back right, and the far call brings it back advanced (fact 4).

    The bank 13 site is the odd one: it replaces a `call`, not a loop, and the composer
    behind it keeps `hl` across its own body. Bracketing the whole thing in push/pop leaves
    the caller with the pointer it had, redirect or not, which is what `13:$4081` onwards
    was written against.
    """
    if mode is None:                     # 13:$407E, the message gate's call to the composer
        return """
      push hl
    """ + (_FOLLOW % (MARK, FAR_STAGE, INDEX_BANK)) + """
    plain:
      call $40C5
      pop hl
      ret
    """
    if mode == MODE_RENDER:
        # 13:$7E4C, the `call $7E0D` inside the help renderer 13:$7E49. Unlike every other
        # site this replaces a CALL rather than a loop, and the loop it feeds -- $7E51 --
        # is left in place to serve the plain path unchanged.
        #
        # $7E0D resolves table $554A and skips [$C6BC] units, counting $EE/$FF. A
        # relocatable record run mirrors the line layout, so it lands on the first RECORD
        # of the wanted unit. A pinned in-place help string is different: `Pool.add`
        # leaves only ONE record at its original address, while the remaining lines exist
        # as consecutive INDEX entries. The old trampoline followed records in ROM and
        # therefore stopped after line 1 whenever such a pinned description grew beyond
        # its original slot (Leather Shield and Invincible Herb exposed this on screen).
        #
        # The record names the first INDEX entry, and `read_entry_render` already returns
        # HL advanced to the next entry plus A = the real line terminator. Follow that
        # authoritative chain directly. It works for both shapes, avoids overwriting the
        # pinned string's unverified interior bytes with a record run, and turns $EF into
        # the $FF row separator that $7E51 writes on the native path.
        #
        # It then hands $7E51 an address holding $FF, so the loop it did not replace runs
        # once, falls straight to $7E7C, and writes the destination's own terminator.
        # Leaving `de` where this trampoline left it is the entire contract between them.
        #
        # The six unreachable NOPs before `stop` retain this trampoline's established
        # 42-byte allocation. Bank 13 is repacked around that allocation; shrinking it by
        # six bytes changed the packing enough for the rescued-child route fixture to miss
        # its manifested 14:$5AFD interior entry. Until every runtime address producer is
        # enumerated, a local reader fix must not churn unrelated bank placement.
        #
        # `push bc` around the far call is not tidiness: read_entry carries the text
        # address in bc, and the far call hands the callee's bc back (fact 1), so without
        # it the line counter is gone after the first line.
        return """
      call $7E0D
      ld a,[hl]
      cp $%02X
      ret nz
      push bc
      inc hl
      ld a,[hl+]
      ld h,[hl]
      ld l,a
      ld b,$04
    line:
      push bc
      rst $10
      db $%02X,$%02X
      pop bc
      cp $EF
      jr nz,done
      ld a,$FF
      ld [de],a
      inc de
      dec b
      jr nz,line
    done:
      pop bc
      ld hl,stop
      ret
      nop
      nop
      nop
      nop
      nop
      nop
    stop:
      db $FF
    """ % (MARK, FAR_RENDER, INDEX_BANK)
    if mode == MODE_STR:
        return (_FOLLOW % (MARK, FAR_COPY, INDEX_BANK)) + """
      ret
    plain:
      ld a,[hl+]
      ld [de],a
      inc de
      cp $FF
      jr nz,plain
      ret
    """
    return (_FOLLOW % (MARK, FAR_COPYN, INDEX_BANK)) + """
      ret
    plain:
      ld a,[hl+]
      cp $FF
      ret z
      ld [de],a
      inc de
      jr plain
    """


def tramp(mode, org):
    """-> the trampoline's bytes, assembled to run at `org` in its own bank."""
    return gbasm.assemble(tramp_src(mode), org)[0]


def reloc_patch(at, org, size):
    """-> what replaces a copy loop: `call <trampoline>`, `nop` to the loop's own length.

    Padding to length rather than jumping past keeps control falling out of the patch
    exactly where it fell out of the loop -- `11:$52BC`'s nine bytes run into the `ret` at
    `$52C5`, and `11:$7E63`'s seven into the `inc b / dec c` that repeats it.
    """
    call, _ = gbasm.assemble('call $%04X' % org, at)
    if len(call) > size:
        raise SystemExit('$%04X: a %d-byte site cannot hold a call' % (at, size))
    return call + b'\x00' * (size - len(call))


def gate_src(dispatch_bank=INDEX_BANK):
    """13:$7589, rewritten: load the pointer exactly as before, then one far call.

    16 bytes where the original was 25. The 9 bytes it frees are left as $FF; nothing in
    this module needs them, and leaving them empty keeps the patch reviewable.
    """
    return """
      push af
      push hl
      ld a,[$%04X]
      ld h,a
      ld a,[$%04X]
      ld l,a
      rst $10
      db $%02X,$%02X
      pop hl
      pop af
      ret
    """ % (PTR_HI, PTR_LO, FAR_DISPATCH, dispatch_bank)


def queue_src():
    """13:$67E0, rewritten: one far call, so the normalisation has room to live elsewhere.

    The original 13 bytes are `ld h,a / call $3C7B / ld l,a` then the two stores. `$3C7B`
    is a bank-0 address, so the relocated copy can still call it from bank 33.
    """
    return """
      rst $10
      db $%02X,$%02X
    """ % (FAR_NORMALISE, INDEX_BANK)


def normalise_src():
    """Bank 33 index $05: what 13:$67E0 used to do, plus `and $BF`.

    That one instruction is what makes tag (0,1) safe by construction instead of safe by
    observation. Bank 11's fixup is `set 6,h`, so bit 6 of a queued pointer is a don't-care
    and event code is free to leave junk in it; clearing it here means a set bit 6 can only
    have come from a redirect record.
    """
    return """
      and $BF
      ld h,a
      call $3C7B
      ld l,a
      ld a,h
      ld [$%04X],a
      ld a,l
      ld [$%04X],a
      ret
    """ % (PTR_HI, PTR_LO)


# ---------------------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------------------
def _bank_off(bank):
    return bank * 0x4000


def _check_free(rom, bank, lo, hi):
    """A pool bank must be untouched $FF. Verified, because 'banks 32-63 are free' is a
    claim about the BASE rom and this runs on a build that has already been patched."""
    off = _bank_off(bank)
    blob = rom[off + lo - 0x4000:off + hi - 0x4000]
    if any(b != 0xFF for b in blob):
        bad = next(i for i, b in enumerate(blob) if b != 0xFF)
        raise SystemExit('bank %d $%04X is not free (byte $%04X = $%02X)'
                         % (bank, lo, lo + bad, blob[bad]))


def _far_entry(rom, bank, index, addr):
    """Point `bank`'s index-table entry `index` at `addr`. The far call reads its target
    from ($4000 + index - 1, $4000 + index), so an entry occupies those two bytes."""
    off = _bank_off(bank) + index - 1
    rom[off] = addr & 0xFF
    rom[off + 1] = addr >> 8


def install(rom, normalise=NORMALISE):
    """-> (rom, info). Installs the mechanism; moves no strings."""
    rom = bytearray(rom)
    if len(rom) < 0x100000:
        raise SystemExit('needs the 1 MiB expansion: this rom is %d bytes' % len(rom))

    dispatch, labels = gbasm.assemble(dispatch_src(), CODE_ORG)
    norm, _ = gbasm.assemble(normalise_src(), CODE_ORG + len(dispatch))
    reader, _ = gbasm.assemble(text_reader_src(), CODE_ORG)
    if CODE_ORG + len(dispatch) + len(norm) > STUBS:
        raise SystemExit('bank %d code overruns the stub table' % INDEX_BANK)
    if STUBS + 4 * len(TEXT_BANKS) > INDEX_ORG:
        raise SystemExit('the stub table overruns the index')
    if CODE_ORG + len(reader) > TEXT_ORG:
        raise SystemExit('text bank reader overruns the text')

    # ---- the index bank: code, then one stub per text bank in each of the two tables
    #
    # Checked over the range install() WRITES, not the whole bank: build.py lays the text
    # and the index down before it installs, so a whole-bank check would fail on this
    # module's own output. The regions do not overlap -- code and stubs end at $4400, the
    # index begins there -- and a collision with anything else still trips this.
    _check_free(rom, INDEX_BANK, 0x4000, INDEX_ORG)
    off = _bank_off(INDEX_BANK)
    rom[off] = INDEX_BANK                # the ROM's own convention: byte 0 = bank id
    rom[off + 1] = 0x00
    _far_entry(rom, INDEX_BANK, FAR_DISPATCH, CODE_ORG)
    _far_entry(rom, INDEX_BANK, FAR_NORMALISE, CODE_ORG + len(dispatch))
    _far_entry(rom, INDEX_BANK, FAR_STAGE, labels['stage'])
    _far_entry(rom, INDEX_BANK, FAR_COPY, labels['read_entry_str'])
    _far_entry(rom, INDEX_BANK, FAR_COPYN, labels['read_entry_strn'])
    _far_entry(rom, INDEX_BANK, FAR_RENDER, labels['read_entry_render'])
    rom[off + CODE_ORG - 0x4000:off + CODE_ORG - 0x4000 + len(dispatch)] = dispatch
    n = CODE_ORG + len(dispatch)
    rom[off + n - 0x4000:off + n - 0x4000 + len(norm)] = norm

    for i, bank in enumerate(TEXT_BANKS):
        stub, _ = gbasm.assemble('rst $10\ndb $%02X,$%02X\nret' % (FAR_READ, bank),
                                 STUBS + i * 4)
        at = off + STUBS - 0x4000 + i * 4
        rom[at:at + len(stub)] = stub

    # ---- every text bank gets the same two readers, whether or not it ends up holding
    # text. A stub table with a hole in it is a crash waiting for the allocator to reach
    # that bank; a uniform one cannot develop that hole.
    for bank in TEXT_BANKS:
        _check_free(rom, bank, 0x4000, TEXT_ORG)
        o = _bank_off(bank)
        rom[o] = bank
        rom[o + 1] = 0x00
        _far_entry(rom, bank, FAR_READ, CODE_ORG)
        rom[o + CODE_ORG - 0x4000:o + CODE_ORG - 0x4000 + len(reader)] = reader

    gate, _ = gbasm.assemble(gate_src(), GATE)
    if len(gate) > GATE_END - GATE:
        raise SystemExit('gate patch is %d bytes, %d available' % (len(gate), GATE_END - GATE))
    g = _bank_off(13) + GATE - 0x4000
    if bytes(rom[g:g + len(EXPECT_GATE)]) != EXPECT_GATE:
        raise SystemExit('13:$%04X is not the untouched dispatcher -- refusing to patch'
                         % GATE)
    rom[g:g + len(gate)] = gate
    rom[g + len(gate):_bank_off(13) + GATE_END - 0x4000] = \
        b'\xFF' * (GATE_END - GATE - len(gate))

    if normalise:
        q, _ = gbasm.assemble(queue_src(), QUEUE_STORE)
        if len(q) > QUEUE_STORE_END - QUEUE_STORE:
            raise SystemExit('queue patch too big')
        o = _bank_off(13) + QUEUE_STORE - 0x4000
        if bytes(rom[o:o + len(EXPECT_QUEUE)]) != EXPECT_QUEUE:
            raise SystemExit('13:$%04X is not the untouched queue store' % QUEUE_STORE)
        rom[o:o + len(q)] = q
        # `nop` fill, not $FF: this is reached by fall-through, not by a jump.
        rom[o + len(q):_bank_off(13) + QUEUE_STORE_END - 0x4000] = \
            b'\x00' * (QUEUE_STORE_END - QUEUE_STORE - len(q))

    return bytes(rom), {
        'dispatch': len(dispatch), 'normalise': len(norm), 'reader': len(reader),
        'gate': len(gate), 'index_entries': (0x8000 - INDEX_ORG) // ENTRY_LEN,
        'text': len(TEXT_BANKS) * (0x8000 - TEXT_ORG),
    }


# ---------------------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------------------
def split_lines(blob):
    """-> the blob cut after every $EE/$EF/$FF, which is where a staging copy stops.

    One index entry per LINE is what makes the continuation pointer an index address
    instead of a text address, and that is the whole reason the bank ceiling is gone. The
    cut has to land exactly where the stager would have stopped or the resumed line starts
    mid-word: the stager copies the terminator and then stops, so the terminator belongs to
    the line before it.
    """
    out, start = [], 0
    for i, b in enumerate(blob):
        if b in TERMINATORS:
            out.append(bytes(blob[start:i + 1]))
            start = i + 1
    if start < len(blob):
        out.append(bytes(blob[start:]))
    return out


class Pool:
    """Bump allocator over the index bank and the text banks.

    Text is placed first-fit across `TEXT_BANKS` and has no encoding constraints at all --
    it is named only by an index entry, so no copy loop ever walks its address. The one
    rule left applies to the ENTRY address, whose low byte travels inside a redirect record
    through a loop that stops on $EE/$EF/$FF.
    """

    def __init__(self, index_org=INDEX_ORG, text_org=TEXT_ORG):
        self.index_at = index_org
        self.index_base = index_org
        self.index = bytearray()
        special_orgs = {
            RANK_SCREEN_BANK: RANK_SCREEN_TEXT_ORG,
            ACTION_GATE_BANK: ACTION_GATE_TEXT_ORG,
            MENU_TRANSITION_BANK: MENU_TRANSITION_TEXT_ORG,
            ACTION_BLANK_BANK: ACTION_BLANK_TEXT_ORG,
        }
        self.at = {b: max(text_org, special_orgs.get(b, text_org))
                   for b in TEXT_BANKS}
        self.base = dict(self.at)
        self.data = {b: bytearray() for b in TEXT_BANKS}
        self.entries = 0

    def _add_text(self, blob):
        """-> (bank, addr). First fit: a line never straddles two banks."""
        for bank in TEXT_BANKS:
            if self.at[bank] + len(blob) <= 0x8000:
                addr = self.at[bank]
                self.data[bank] += bytes(blob)
                self.at[bank] = addr + len(blob)
                return bank, addr
        raise SystemExit('all %d text banks are full' % len(TEXT_BANKS))

    def _add_entry(self, bank, addr, in_record=False):
        """-> the entry's own address.

        `in_record` means this entry's address will travel inside a redirect RECORD, which
        a stager copies with a loop that stops on $EE/$EF/$FF -- so its low byte may not be
        one of those, and the allocator skips ahead when it would be.

        ONLY THEN. This used to skip for every entry, and that was wrong in a way that
        reached the game. A CONTINUATION is not copied anywhere: `read_entry` leaves
        hl = entry + 3 in a register and `$CF7F/$CF80` holds it as plain 16-bit state, so
        no terminator rule applies to it. Skipping mid-string left an `$FF` filler byte
        between two of a string's own entries, and `entry + 3` -- which the reader advances
        unconditionally, three `ld a,[hl+]` -- then landed on the filler instead of the
        next line. The string stopped there, on screen, part-way through.

        Found 2026-08-05 by the rewritten pool verifier, on 4 of session 5's 355 redirected
        strings; `11:$5AE6` read back 145 bytes of 228. Low bytes $EE/$EF/$FF are 3 of 256
        and an entry is 3 bytes, so it bites roughly once every 85 entries -- rare enough
        to survive every earlier build, which redirected two or three strings at a time.
        """
        while in_record and (self.index_at & 0xFF) in TERMINATORS:
            self.index += b'\xFF'
            self.index_at += 1
        if self.index_at + ENTRY_LEN > 0x8000:
            raise SystemExit('the index bank is full (%d entries)' % self.entries)
        at = self.index_at
        self.index += bytes([addr & 0xFF, addr >> 8, bank])
        self.index_at += ENTRY_LEN
        self.entries += 1
        return at

    def add(self, blob):
        """Place `blob` and return its 4-byte redirect record.

        The record names the FIRST entry; the rest follow it AT +3 EACH, which is what
        `read_entry` relies on when it hands back `entry + 3` as the continuation. Only the
        first entry's address travels inside the record, so only the first takes the
        low-byte constraint -- see `_add_entry`, where applying it to the others used to
        break the continuation it was meant to protect.
        """
        first = None
        for line in split_lines(blob):
            bank, addr = self._add_text(line)
            at = self._add_entry(bank, addr, in_record=first is None)
            if first is None:
                first = at
        if first is None:
            raise SystemExit('refusing to redirect an empty string')
        return bytes([MARK, first & 0xFF, first >> 8, 0xFF])

    def add_run(self, blob):
        """Place `blob` and return one record per LINE, each ending in that line's own
        terminator -- the shape a RELOCATABLE redirect has to leave behind.

        A relocatable string's line structure is not private to it. `13:$7DBD` walks the
        bytes to publish one message-queue address per line, because the composer composes
        exactly one line per queue entry; a single record would collapse a three-line
        message to its first line, on screen, with nothing reporting it. Mirroring the
        layout -- same number of lines, same terminator on each -- means that walker and
        anything shaped like it keep working with no hook at all, and the composer's own
        trampoline never looks at the fourth byte.

        The ordinary in-place path does NOT use this: it resumes through the index, so one
        record is both correct and cheaper there.  Address-pinned targets of help table
        13:$554A are the exception: its separate queue pre-scan must still see one visible
        terminator per line at the original address (see ``needs_line_records``).

        EVERY entry here goes inside a record -- that is what a run is -- so every one takes
        the low-byte constraint, unlike `add`.
        """
        lines = split_lines(blob)
        if not lines:
            raise SystemExit('refusing to redirect an empty string')

        # Every entry address is embedded in a record, but the help renderer also follows
        # entry + 3 between rows.  Reserve one consecutive run whose individual low bytes
        # are all safe for the line stager.  Calling _add_entry(..., in_record=True) once
        # per row can insert a one-byte hole at $xxEE/$xxEF/$xxFF; that is valid for the
        # records in isolation but strands the render continuation on the filler byte.
        while any(((self.index_at + ENTRY_LEN * i) & 0xFF) in TERMINATORS
                  for i in range(len(lines))):
            self.index += b'\xFF'
            self.index_at += 1

        out = bytearray()
        for line in lines:
            bank, addr = self._add_text(line)
            at = self._add_entry(bank, addr)
            end = line[-1] if line[-1] in TERMINATORS else 0xFF
            out += bytes([MARK, at & 0xFF, at >> 8, end])
        return bytes(out)

    def write(self, rom):
        rom = bytearray(rom)
        off = _bank_off(INDEX_BANK) + self.index_base - 0x4000
        rom[off:off + len(self.index)] = self.index
        for bank, blob in self.data.items():
            o = _bank_off(bank) + self.base[bank] - 0x4000
            rom[o:o + len(blob)] = blob
        return bytes(rom)

    def used(self):
        return sum(self.at[b] - self.base[b] for b in TEXT_BANKS)

    def report(self):
        banks = [b for b in TEXT_BANKS if self.at[b] > self.base[b]]
        return ('%d bytes of text in %d bank(s) of %d, %d index entries of %d'
                % (self.used(), len(banks), len(TEXT_BANKS), self.entries,
                   (0x8000 - self.index_base) // ENTRY_LEN))

    def capacity(self):
        """Total text bytes the pool can hold. THIRTY banks: the record names an index
        entry rather than text, so the 16 bits of the continuation pointer no longer have
        to carry a bank number and the two-bank ceiling is gone. The binding limit is now
        the index -- `entry_capacity()` -- and it is 5,034 lines."""
        return sum(0x8000 - self.base[b] for b in TEXT_BANKS)

    def entry_capacity(self):
        return (0x8000 - self.index_base) // ENTRY_LEN


def record_entry(record):
    """-> the cpu address in the index bank that a 4-byte record names."""
    return record[1] | record[2] << 8


def run_text(run, rom):
    """-> the text a record RUN names, lines concatenated, as the readers see it."""
    out = bytearray()
    for i in range(0, len(run), RECORD_LEN):
        at = _bank_off(INDEX_BANK) + record_entry(run[i:i + RECORD_LEN]) - 0x4000
        addr, bank = rom[at] | rom[at + 1] << 8, rom[at + 2]
        off = bank * 0x4000 + addr - 0x4000
        while off < len(rom) and rom[off] not in TERMINATORS:
            out.append(rom[off])
            off += 1
        out.append(rom[off] if off < len(rom) else 0xFF)
    return bytes(out)


def record_offset(record, rom):
    """-> file offset of the text a record points at, followed through the index.

    Needs the ROM because the record no longer carries the address: it names an entry, and
    the entry is what says (bank, address). `build.py`'s verifier follows exactly this
    chain, so a mis-written entry fails the build instead of rendering as an empty line.

    This is the FIRST LINE only. To read a whole redirected string, use `record_text` --
    reading linearly from here is what broke on 2026-08-05, see below.
    """
    at = _bank_off(INDEX_BANK) + record_entry(record) - 0x4000
    addr = rom[at] | rom[at + 1] << 8
    return rom[at + 2] * 0x4000 + addr - 0x4000


def record_text(record, rom):
    """-> the whole text an in-place record names, followed through the INDEX.

    THE BUG THIS FIXES, because it was a false alarm that looked exactly like a real one.
    `add()` stores one index entry per LINE and the record names the first; the runtime
    resumes with `entry + 3`, the next INDEX entry, and never assumes where the text is.
    The verifier did assume: it took `record_offset` and read forward to a terminator, so
    it was really asserting that a string's lines are laid out CONTIGUOUSLY.

    They usually are, which is why this survived until session 5 redirected 300 strings at
    once and `14:$5875` became the first string to straddle a pool bank -- lines 1-3 at the
    end of bank 34, line 4 in bank 35, line 5 back in a 17-byte gap in bank 34. Nothing was
    wrong with the ROM: `--redirect-all`, crashscan and reloc_verify were all clean, and
    the game reads it correctly. Only the check was wrong, and it reported `BADPLACE`,
    which docs/TEXT_REFERENCE.md tells a translator to stop and report as a tool bug.
    It was one.

    Walks entries until a line ends in `$FF`, which is the terminator `add()` appends to
    the blob and therefore the one the runtime stops on too.
    """
    out = bytearray()
    at = _bank_off(INDEX_BANK) + record_entry(record) - 0x4000
    for _ in range(MAX_LINES):
        addr, bank = rom[at] | rom[at + 1] << 8, rom[at + 2]
        off = bank * 0x4000 + addr - 0x4000
        while off < len(rom) and rom[off] not in TERMINATORS:
            out.append(rom[off])
            off += 1
        end = rom[off] if off < len(rom) else 0xFF
        out.append(end)
        if end == 0xFF:
            return bytes(out)
        at += 3
    raise SystemExit('record %s never terminates within %d lines' % (record.hex(), MAX_LINES))


# A redirected string cannot have more lines than this. Purely a runaway guard for the
# index walk above: the longest string in the script, 14:$4D19, is 36 lines.
MAX_LINES = 256


STAGER_BANKS = (11, 14)


def eligible(r):
    """Can this string be redirected? Structural, not observational -- and see below.

    A string in bank 11 or 14 with NO reference anywhere in the ROM has no other way to be
    reached than the runtime message queue, which lands on `13:$7589` and therefore on the
    dispatcher. Fall-through from the previous string is the same path (the stager's own
    continuation), so it is covered too.

    A box row is excluded: those are drawn by `31:$40D8` from a geometry table, never
    staged through $CF8F, so a record would be drawn as text.

    WHAT HAPPENS IF THIS IS WRONG. `extract.py` has been wrong about references before --
    240 of them -- so "no refs" is evidence, not proof. The failure is still benign, and the
    record ends in `$FF`, so a reader that does not understand the redirect draws a short
    line and stops. It cannot run off the end of anything, and it cannot corrupt a neighbour,
    because the record replaces only the first 4 bytes and the rest of the original string is
    LEFT WHERE IT IS -- so a pointer into the middle of it still finds what it pointed at.

    CORRECTED 2026-07-31: this used to say "MARK is `$E9`, whose control handler at
    `13:$6929` is a bare `ret`", and that conflated the composer's two dispatch tables (see
    docs/FINDINGS.md). `13:$4148` is the bare `ret` and belongs to the BANK 13 table at `$4126`.
    The dialogue table at `$68CF` sends `$E9` to `13:$6929`, which writes `$CF81` -- the
    player's first name character -- and its dakuten if it has one. So an unrecognised record
    draws one or two stray characters rather than nothing. Benign either way, and it does not
    affect the choice of MARK (a byte no LINE can legitimately begin with), but the reason
    given was wrong.
    """
    return (r['bank'] in STAGER_BANKS
            and not r['refs']
            and not r.get('box')
            and r['bytes'] >= (EC_MIN if starts_ec(r) else RECORD_LEN))


def starts_ec(r):
    """Does this string open with `EC arg` -- the sign/plaque prefix `13:$67F3` tests for?

    Asked of the JAPANESE, because that is what decides the ROM's own control flow, and
    checked against the translation by `head_bytes` so the two cannot drift.

    Scoped to the STAGER banks. `13:$67F3` is the queue path's entry and only banks 11 and
    14 arrive there; bank 13 dispatches through `13:$4126`, a different table in which
    `$EC` is a different code. All 31 today are in bank 14, so the scope changes nothing
    now -- it stops the check crying wolf over a bank-13 string later.
    """
    return (r['bank'] in STAGER_BANKS
            and bool(r.get('hex')) and int(r['hex'].split()[0], 16) == EC_OPEN)


class PrefixMoved(SystemExit):
    """A `<cEC:xx>` translation that does not lead with its prefix. A SystemExit so the
    one existing `except` around the pool call still catches it; its own type so build.py
    can report it as what it is rather than as `pool_full`."""


def head_bytes(r, data):
    """-> the bytes of `data` that must stay at the original address, before the record.

    `b''` for an ordinary string. For an `$EC` string, the two-byte prefix -- and the
    translation has to still carry it, because `13:$6C73` reads the argument out of the
    staged buffer and every sign's geometry comes from it. `lint_en`'s token parity
    already insists; this is the assertion that makes the layout depend on it.
    """
    if not starts_ec(r):
        return b''
    if len(data) < EC_HEAD or data[0] != EC_OPEN:
        raise PrefixMoved('the Japanese opens with <cEC> and the translation does not; '
                          '13:$6C73 would re-derive the resume pointer into the record')
    return bytes(data[:EC_HEAD])


# ---------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------
def check_marker(script_json='script/script.json'):
    """Re-derive the claim that MARK begins no string. Never trust the comment."""
    import json
    d = json.load(open(script_json, encoding='utf-8'))
    bad = [r['loc'] for r in d['strings']
           if r['hex'] and int(r['hex'].split()[0], 16) == MARK]
    return bad


def _test_rom(pool=None):
    """A 1 MiB image with the mechanism installed and a fake bank 11 stager.

    The stager is real code, not a stub: the dispatcher's record path only works if the
    four record bytes survive a loop that stops on $EE/$EF/$FF, so the selftest has to run
    one. It is `11:$56A5` byte for byte, behind each bank's own pointer fixup -- `set 6,h`
    for bank 11 and `xor $C0` for bank 14, which is what makes tag (0,1) free in the first
    place. A stager without the fixup would make this test pass on a wrong address.
    """
    rom = bytearray(b'\xFF' * 0x100000)
    rom[0x0000:0x0002] = b'\x00\x00'
    loop = """
      ld bc,$%04X
    .loop:
      ld a,[hl+]
      ld [bc],a
      inc bc
      cp $EF
      jr z,.done
      cp $EE
      jr z,.done
      cp $FF
      jr nz,.loop
    .done:
      ret
    """ % STAGE_BUF
    for bank, fixup in ((11, 'set 6,h\n'), (14, 'ld a,h\nxor $C0\nld h,a\n')):
        stager, _ = gbasm.assemble(fixup + loop, 0x4100)
        off = bank * 0x4000
        rom[off] = bank
        rom[off + 1] = 0
        rom[off + 0x0C] = 0x00                    # bank 11: entry $0D -> $4100
        rom[off + 0x0D] = 0x41
        rom[off + 0x02] = 0x00                    # bank 14: entry $03 -> $4100
        rom[off + 0x03] = 0x41
        rom[off + 0x100:off + 0x100 + len(stager)] = stager
    rom[0x3C7B:0x3C7E] = bytes([0x3E, 0x2D, 0xC9])          # ld a,$2D / ret, for normalise
    # The two bank-13 sites install() refuses to patch unless it recognises them.
    g = 13 * 0x4000 + GATE - 0x4000
    rom[g:g + len(EXPECT_GATE)] = EXPECT_GATE
    q = 13 * 0x4000 + QUEUE_STORE - 0x4000
    rom[q:q + len(EXPECT_QUEUE)] = EXPECT_QUEUE
    rom = bytearray(install(bytes(rom))[0])
    if pool is not None:
        rom = bytearray(pool.write(bytes(rom)))
    return rom


def _cpu(rom, bank=INDEX_BANK):
    import gbemu
    banks = {n: rom[n * 0x4000:(n + 1) * 0x4000] for n in range(len(rom) // 0x4000)}
    return gbemu.Cpu(banks, bank=bank)


def selftest():
    ok = 0
    lbl = gbasm.assemble(dispatch_src(), CODE_ORG)[1]

    # 1. A two-line string, followed the way the game follows it: enter the dispatcher with
    #    the record's target, read line 1, then re-enter with the continuation it stored and
    #    read line 2. This is the whole mechanism -- index entry, stub table, far call into
    #    a text bank, and the continuation that no longer has to carry a bank number.
    p = Pool()
    lines = [b'The first line of it.\xEE', b'and then the second.\xEF']
    rec = p.add(b''.join(lines))
    rom = _test_rom(p)
    stored = record_entry(rec)
    for want in lines:
        cpu = _cpu(rom)
        cpu.ram[PTR_LO - 0x8000] = stored & 0xFF
        cpu.ram[PTR_HI - 0x8000] = stored >> 8
        cpu.h, cpu.l = stored >> 8, stored & 0xFF
        cpu.call(CODE_ORG)
        got = bytes(cpu.ram[STAGE_BUF - 0x8000:STAGE_BUF - 0x8000 + len(want)])
        assert got == want, (want, got)
        stored = cpu.ram[PTR_LO - 0x8000] | cpu.ram[PTR_HI - 0x8000] << 8
        assert stored & 0x4000 and not stored & 0x8000, hex(stored)   # tag (0,1) kept
    ok += 1

    # 2. The record path: a bank-11 pointer whose bytes are the record. The stager copies
    #    it to $CF8F, the dispatcher recognises the marker and follows it, and the line that
    #    lands in $CF8F is the POOL's, not the record's.
    p = Pool()
    text = b'Redirected out of bank 11.\xFF'
    rec = p.add(text)
    rom = _test_rom(p)
    at = 0x5000                                   # somewhere in bank 11
    rom[11 * 0x4000 + at - 0x4000:11 * 0x4000 + at - 0x4000 + len(rec)] = rec
    cpu = _cpu(rom)
    stored = at & ~0x4000                         # tag (0,0): what bank 11 stores
    cpu.h, cpu.l = stored >> 8, stored & 0xFF
    cpu.call(CODE_ORG)
    got = bytes(cpu.ram[STAGE_BUF - 0x8000:STAGE_BUF - 0x8000 + len(text)])
    assert got == text, got
    ok += 1

    # 3. `stage` hands the caller hl = $CF8F, and `read_entry_str` hands back de advanced
    #    past a string it copied there. Both rely on the far call being register-transparent
    #    (fact 4); if it were not, the relocatable redirect would need a WRAM protocol.
    p = Pool()
    rec = p.add(b'Item name\xFF')
    rom = _test_rom(p)
    entry = record_entry(rec)
    cpu = _cpu(rom)
    cpu.h, cpu.l = entry >> 8, entry & 0xFF
    cpu.call(lbl['stage'])
    assert cpu.hl == STAGE_BUF, hex(cpu.hl)
    assert bytes(cpu.ram[STAGE_BUF - 0x8000:STAGE_BUF - 0x8000 + 10]) == b'Item name\xFF'
    for entrypoint, want, end in (('read_entry_str', b'Item name\xFF', 0xC50A),
                                  ('read_entry_strn', b'Item name', 0xC509)):
        cpu = _cpu(rom)
        cpu.h, cpu.l = entry >> 8, entry & 0xFF
        cpu.de = 0xC500
        cpu.ram[0xC500 - 0x8000:0xC500 - 0x8000 + 10] = b'\x00' * 10
        cpu.call(lbl[entrypoint])
        got = bytes(cpu.ram[0xC500 - 0x8000:0xC500 - 0x8000 + len(want)])
        assert got == want, (entrypoint, got)
        assert cpu.de == end, (entrypoint, hex(cpu.de))
    ok += 1

    # 3b. Each trampoline follows a record, and runs the loop it replaced when there is no
    #     record. The `plain` arm has to behave EXACTLY like the six or nine bytes it
    #     displaced, terminator and all, or a menu ends up a byte short.
    for mode, want, end in ((MODE_STR, b'Item name\xFF', 0xC50A),
                            (MODE_STRN, b'Item name', 0xC509)):
        code = tramp(mode, 0x6000)
        for redirect in (True, False):
            blob = bytearray(rom[11 * 0x4000:12 * 0x4000])
            blob[0x6000 - 0x4000:0x6000 - 0x4000 + len(code)] = code
            src, at = 0x5000, rec if redirect else b'Item name\xFF'
            blob[src - 0x4000:src - 0x4000 + len(at)] = at
            r = bytearray(rom)
            r[11 * 0x4000:12 * 0x4000] = blob
            cpu = _cpu(r, bank=11)
            cpu.h, cpu.l = src >> 8, src & 0xFF
            cpu.de = 0xC500
            cpu.ram[0xC500 - 0x8000:0xC500 - 0x8000 + 10] = b'\x00' * 10
            cpu.call(0x6000)
            got = bytes(cpu.ram[0xC500 - 0x8000:0xC500 - 0x8000 + len(want)])
            assert got == want, (mode, redirect, got)
            assert cpu.de == end, (mode, redirect, hex(cpu.de))
    ok += 1

    # 3c. The help trampoline follows INDEX entries, not a run of records in bank 13.
    #     Pinned help strings use Pool.add(), so only their first record exists in ROM;
    #     every later line is reachable solely as the next index entry. Following record
    #     bytes rendered only line 1 of Leather Shield and Invincible Herb.
    p = Pool()
    text = b'first\xEFsecond\xEFthird\xFF'
    rec = p.add(text)                         # deliberately ONE record, three entries
    rom = _test_rom(p)
    code = tramp(MODE_RENDER, 0x6000)
    bank = bytearray(rom[13 * 0x4000:14 * 0x4000])
    bank[0x6000 - 0x4000:0x6000 - 0x4000 + len(code)] = code
    bank[0x7E0D - 0x4000] = 0xC9              # the real resolver; test already has hl
    bank[0x5000 - 0x4000:0x5000 - 0x4000 + len(rec)] = rec
    r = bytearray(rom)
    r[13 * 0x4000:14 * 0x4000] = bank
    cpu = _cpu(r, bank=13)
    cpu.hl = 0x5000
    cpu.de = 0xC500
    cpu.bc = 0x1234
    cpu.call(0x6000)
    want = b'first\xFFsecond\xFFthird'
    got = bytes(cpu.ram[0xC500 - 0x8000:0xC500 - 0x8000 + len(want)])
    assert got == want, got
    assert cpu.de == 0xC500 + len(want), hex(cpu.de)
    assert cpu.bc == 0x1234, hex(cpu.bc)
    ok += 1

    # 3d. A record RUN must satisfy two readers at once: every entry address travels in
    #     a four-byte record (so no low byte may look like a line terminator), while the
    #     help renderer advances through the same entries at +3.  Start directly on an
    #     unsafe low byte to prove the allocator moves the WHOLE consecutive run instead
    #     of inserting a hole between its rows.
    p = Pool(index_org=0x44EE)
    blob = b'one\xEFtwo\xEFthree\xFF'
    run = p.add_run(blob)
    entries = [record_entry(run[i:i + RECORD_LEN])
               for i in range(0, len(run), RECORD_LEN)]
    assert all((entry & 0xFF) not in TERMINATORS for entry in entries), entries
    assert all(b - a == ENTRY_LEN for a, b in zip(entries, entries[1:])), entries
    rom = _test_rom(p)
    assert run_text(run, rom) == blob
    assert record_text(run[:RECORD_LEN], rom) == blob
    ok += 1

    # 4. Every record the allocator emits survives the staging copy: no byte of it is a
    #    terminator, so the bank 11/14 stager delivers all four bytes to $CF8F. Entries are
    #    3 bytes, so this bites about once every 85 of them.
    p = Pool()
    for n in (4, 17, 250, 900, 3, 5000):
        rec = p.add(b'x' * n + b'\xFF')
        assert rec[0] == MARK and rec[3] == 0xFF
        assert rec[1] not in TERMINATORS and rec[2] not in TERMINATORS, rec.hex()
    ok += 1

    # 5. Lines are cut where the stager stops, terminator included.
    assert split_lines(b'ab\xEEcd\xEFe\xFF') == [b'ab\xEE', b'cd\xEF', b'e\xFF']
    assert split_lines(b'no terminator') == [b'no terminator']
    ok += 1

    # 4b. A MULTI-LINE string's entries are exactly 3 apart, all the way through, however
    #     many strings were allocated before it. `read_entry` advances hl by three and
    #     never checks, so a gap anywhere in a string stops it mid-message on screen.
    #
    #     This is the regression test for the bug found 2026-08-05: the low-byte skip that
    #     keeps a RECORD's address out of $EE/$EF/$FF was being applied to continuation
    #     entries too, which do not travel in a record, and the filler it left behind broke
    #     4 of session 5's 355 redirected strings. Allocating single-line strings between
    #     the multi-line ones walks the index across every low byte, so a skip that fires
    #     on the wrong entry is certain to be caught rather than lucky to be.
    p = Pool()
    for i in range(400):
        p.add(b'filler\xFF')
        blob = b'one\xEFtwo\xEFthree\xFF'
        rec = p.add(blob)
        assert rec[1] not in TERMINATORS and rec[2] not in TERMINATORS, rec.hex()
        first = record_entry(rec)
        base = p.index_base
        for line_no in range(len(split_lines(blob))):
            at = first + ENTRY_LEN * line_no - base
            assert p.index[at + 2] in TEXT_BANKS, (
                'entry %d of a %d-line string is not an entry -- a filler byte landed '
                'inside the string at iteration %d' % (line_no, 3, i))
    ok += 1

    # 6. The gate patch fits, and the queue patch fits.
    assert len(gbasm.assemble(gate_src(), GATE)[0]) <= GATE_END - GATE
    assert len(gbasm.assemble(queue_src(), QUEUE_STORE)[0]) <= QUEUE_STORE_END - QUEUE_STORE
    ok += 1

    # 7. Normalisation really clears bit 6 and nothing else.
    rom = _test_rom()
    cpu = _cpu(rom)
    cpu.a = 0x63                                  # a bank-11 pointer with bit 6 set
    cpu.call(gbasm.assemble(dispatch_src(), CODE_ORG)[0].__len__() + CODE_ORG)
    assert cpu.ram[PTR_HI - 0x8000] == 0x23, hex(cpu.ram[PTR_HI - 0x8000])
    assert cpu.ram[PTR_LO - 0x8000] == 0x2D
    ok += 1

    print('pool.py: %d checks pass' % ok)
    bad = check_marker() if os.path.exists('script/script.json') else []
    print('marker $%02X begins %d of the extracted strings%s'
          % (MARK, len(bad), '' if not bad else ' -- ' + ' '.join(bad[:8])))
    return 0 if not bad else 1


def main():
    a = sys.argv[1:]
    if '--selftest' in a:
        return selftest()
    if len(a) < 2:
        print(__doc__)
        return 2
    rom = open(a[0], 'rb').read()
    out, info = install(rom)
    open(a[1], 'wb').write(out)
    print('installed: dispatch %d B, normalise %d B, text-bank reader %d B, gate %d B'
          % (info['dispatch'], info['normalise'], info['reader'], info['gate']))
    print('pool: %d bytes of text across banks %d-%d, %d index entries in bank %d'
          % (info['text'], TEXT_BANKS[0], TEXT_BANKS[-1], info['index_entries'],
             INDEX_BANK))
    return 0




if __name__ == '__main__':
    sys.exit(main())
