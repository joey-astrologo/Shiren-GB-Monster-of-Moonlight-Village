#!/usr/bin/env python3
"""Extract the Shiren GB script into a translation working file.

Two sources of strings:
  1. Pointer-table entries  -- discovered, then quality-filtered so numeric data that
     merely decodes as valid bytes (bank 10) does not get mistaken for a table.
  2. Sequential 0xFF-delimited blocks in script regions no table covers.

Every extracted string is round-trip verified (decode -> encode == original bytes).
A string that fails is reported rather than silently emitted, because a failure means
the table is incomplete and inserting it later would corrupt the ROM.

usage: extract.py <rom> [--out DIR]
"""
import sys, os, json, hashlib, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec
import dis                    # this project's disassembler, NOT the stdlib one
import findtables
from regions import script_regions, GFX_BANKS, FONT

BANKSZ = 0x4000

# Immediate operands normally name text in the instruction's own switchable bank.  These
# two bank-13 loads are a measured exception: both load ``hl,$46C1``, then move ``$0E``
# into the bank selector before calling the dialogue stager.  Their target is therefore
# bank 14's ordinary-stair choice (``Descend / Stay here``), not the unrelated bank-13
# message that happens to start at the same CPU address.
#
# Leaving this implicit is destructive.  The extractor used to attach both operands to
# 13:$46C1; repacking that message changed the loads to ``hl,$5AFD`` and every stair event
# began staging a rescued-child line.  Original-Japanese state handoffs for Nagi, Koppa
# and Fumi all instead stage 14:$46C1 and transition directly after the choice.
#
# instruction file offset -> (register, target bank, original pointer)
CROSS_BANK_IMMEDIATES = {
    13 * BANKSZ + (0x549F - 0x4000): ('hl', 14, 0x46C1),
    13 * BANKSZ + (0x54B5 - 0x4000): ('hl', 14, 0x46C1),
}

# Conservatively retained runtime-observed entry points that static extraction cannot
# prove. Most begin inside another extracted conversation; a few are standalone records
# rejected by a conservative byte heuristic until their control semantics are known.
#
# Static byte coverage cannot discover these: a sequential walker quite reasonably sees
# one $FF-terminated parent, and an immediate-reference scan cannot see a pointer assembled
# by event bytecode. During investigation of the rescued-child route, a build whose
# ordinary-stair pointer was later proven corrupt queued 14:$5AFD directly, eight bytes
# inside 14:$5AF5, then the other two starts below. The corrected original-Japanese path
# does not enter them on an ordinary stair; retain them conservatively until a broader
# event sweep proves that no independent route does. If a legitimate route enters one
# while only the parent is redirected, it bypasses English and stages the Japanese tail.
#
# Keep this evidence explicit and small.  New entries belong here only after a real route
# observes them entering a dialogue stager at a position that is neither a parent start
# nor a proven $EE/$EF line continuation; gbrun.py now reports that case as an error
# instead of silently classifying every interior address as a continuation.
RUNTIME_INTERIOR_ENTRIES = {
    14 * BANKSZ + (0x52AB - 0x4000):
        'Keyaki Otogiri Herb receipt; observed from Log 2 walk-left event',
    14 * BANKSZ + (0x5AFD - 0x4000):
        'conservative Nagi interior; observed during pre-fix stair-pointer investigation',
    14 * BANKSZ + (0x5B81 - 0x4000):
        'conservative Nagi interior; observed during pre-fix stair-pointer investigation',
    14 * BANKSZ + (0x70BE - 0x4000):
        'conservative Nagi interior; observed during pre-fix stair-pointer investigation',
}


def bank_of(off):
    return off // BANKSZ


def addr_of(off):
    b = bank_of(off)
    return off % BANKSZ + (0x4000 if b else 0)


def loc(off):
    return "%d:$%04X" % (bank_of(off), addr_of(off))


# ---------------------------------------------------------------- tables
# The scanner lives in findtables.py so there is exactly one implementation. An earlier
# version duplicated it here, and the two copies drifted -- this one resolved pointers
# only within the containing bank, which hid every cross-bank table.
string_at = findtables.string_at


# A pointer table must select something. Fewer than three distinct entries and it cannot:
# indexing it returns the same address whatever the index, which is not what a table is
# for. Every "table" below that bar has turned out to be an ordinary byte array whose
# pairs happen to decode as addresses.
#
# THIS IS MEASURED, and the gap is clean: of the 39 candidates in this ROM, 19 have one or
# two distinct entries and 20 have four or more. NOTHING has three, so the threshold is not
# balanced on a knife edge. The real tables are emphatic about it -- `10:$476A` is 100
# entries and 100 distinct, `11:$4537` is 145 of 157.
#
# It cost a play-test to learn, twice, and both times the damage was silent:
#
#   10:$46B0 (11 entries, 2 distinct) and 10:$46C6 (6 entries, 2 distinct) are bank 10's
#   numeric item stats -- a run of $47 bytes with the odd $46/$48/$49 -- read as pointers
#   $4747/$4947 into bank 11. build.py duly REWROTE 25 bytes of them to relocated
#   addresses, and the status screen then read a Hyakki Shield's strength as 0 where the
#   Japanese ROM reads 9 (Joey, 2026-08-04). Nothing else noticed: the references verified,
#   because they verify that a string is reachable, not that the site was ever a pointer.
#
#   6:$56B9 (2 distinct) put `13:$57AB` in the script -- a "string" starting two bytes
#   inside `13:$57A9` -- and failed BADREF the moment that description was translated.
#
# `10:$4663` (6 entries, 1 distinct) is the third member and was already in MANUAL_DROP by
# hand, for `6:$472F`. So this rule does not introduce a judgement; it generalises one the
# file had already made three times.
MIN_DISTINCT = 3


def table_is_real(rom, tab, kana_thresh=0.35, digit_thresh=0.15, min_kana=2):
    """Reject 'tables' that point at numeric data, and 'tables' that cannot select.

    A plain kana-ratio test at 0.55 was too blunt: real dialogue carrying control codes
    and punctuation scores 0.42-0.52 and was being thrown away (`b6 $56BB`, the `b28`
    NPC tables). What actually separates them is digit density plus an absolute kana
    count -- data runs are digit-heavy ("33おう 146") or have no kana at all ("−", "17"),
    whereas dialogue always carries several kana however many control codes it has.

    The distinct-entry test above is a second, independent filter: the kana test asks what
    a table POINTS AT, and this one asks whether it is a table at all. Bank 10's stat runs
    passed the kana test because the bytes they happened to address are real strings.
    """
    ptrs = [ptr for _, ptr, _ in findtables.entries(rom, tab)]
    if len(set(ptrs)) < MIN_DISTINCT:
        return False
    strs = [string_at(rom, off) for _, _, off in findtables.entries(rom, tab)]
    if not strs:
        return False
    n = len(strs)
    kana = sum(codec.kana_ratio(s) for s in strs) / n
    digit = sum(sum(1 for b in s if 0x01 <= b <= 0x0A) / max(1, len(s)) for s in strs) / n
    kana_n = sum(sum(1 for b in s if 0x0B <= b <= 0x78) for s in strs) / n
    return kana >= kana_thresh and digit <= digit_thresh and kana_n >= min_kana


# ---------------------------------------------------------------- menu boxes
# Bank 31 draws every menu box in the game from a table of geometry descriptors.
#
#   31:$4055  indexes BOX_TABLE by box id, follows the pointer, and copies 7 bytes into
#             $C69A: x, y, rows, width, flags, text-pointer-lo, text-pointer-hi
#   31:$4075  draws a top border, `rows` text rows, then a bottom border
#   31:$40D8  draws ONE row: left border tile, `width` CELLS, right border tile
#
# So the table is an exact enumeration of both the geometry and the text of every box --
# which is what the hand-written EXTRA_REGIONS bounds were approximating, badly. A bound
# of $4340 cut off 17 boxes. Walking the table instead accounts for every byte of
# $41C2-$45D5 with nothing left over, which is the standard a region claim has to meet.
BOX_TABLE = (31, 0x45D5, 52)
DESC_LEN = 7


def box_descriptors(rom):
    """-> [ {id, desc, x, y, rows, width, flags, text} ] for every box, in table order.

    `text` is a CPU address; boxes whose text is staged in WRAM (the item list, the item
    action menu) point into $C6xx and carry no ROM text.
    """
    bank, addr, count = BOX_TABLE
    base = bank * BANKSZ
    out = []
    for i in range(count):
        o = base + (addr - 0x4000) + i * 2
        ptr = rom[o] | (rom[o + 1] << 8)
        d = base + (ptr - 0x4000)
        de = rom[d:d + DESC_LEN]
        out.append({"id": i, "bank": bank, "desc": d, "desc_addr": ptr,
                    "x": de[0], "y": de[1], "rows": de[2], "width": de[3],
                    "flags": de[4], "text": de[5] | (de[6] << 8)})
    return out


def box_rows(rom, box):
    """Split a box's text block into rows exactly the way 31:$40D8 reads it.

    A row ends after `width` cells or at an $FF, whichever comes first, so the terminator
    is OPTIONAL: 31:$44F7 (the ranking header) genuinely omits it because its 12 bytes are
    exactly 10 cells. Splitting on $FF alone therefore runs two boxes together.

    Cells, not bytes: 31:$4124 draws a dakuten over the preceding cell and skips the
    `dec e`, and it peeks the NEXT byte to do so -- which means a row whose last character
    is voiced consumes its dakuten even after the width is used up (31:$4356 `どうぐ`).
    Replicating the peek is the only way to land on the true end of the block.

    -> [ (offset, length, terminated) ] and the offset just past the block.
    """
    base = box["bank"] * BANKSZ
    p = box["text"] - 0x4000 + base
    rows = []
    for _ in range(box["rows"]):
        start, c = p, box["width"]
        while c > 0:
            if rom[p] != codec.TERMINATOR:
                p += 1
            if rom[p] not in codec.COMBINING:
                c -= 1
        term = rom[p] == codec.TERMINATOR
        rows.append((start, p - start, term))
        if term:
            p += 1
    return rows, p


def box_interior_targets(rom, blocks):
    """Addresses strictly inside a box's text that bank 31 or bank 0 loads directly.

    Some box text has a second reader. 31:$418D `ld hl,$4275` is the name-entry grid page,
    which is row 1 of box 12 -- harmless, because a row start gets its own record and its
    own reference. A target that is NOT a row start is the dangerous kind: relocating the
    block would leave that load pointing at whatever moved in, and nothing would catch it,
    because the verifier only follows references it knows about.

    Same bank-trust rule as immediate_refs: a load in bank 9 whose operand happens to
    equal a bank 31 address is bank 9's own data.

    **A `ld bc,nn` THAT REACHES `0:$028B` IS NOT ONE OF THESE, WHATEVER BANK IT SITS IN.**
    The queue push names a BANK 13 address (see MSG_PUSH), so its operand has nothing to
    do with the bank-31 block it happens to land in. Six of these were pinning three boxes
    on 2026-08-05, among them box 48 -- the "Normal" difficulty explanation on the title
    menu, which Joey reported as untranslatable. `31:$755B ld bc,$4571 / call $028B` is
    `13:$4571`, `<cE0:2B>とっぷうだ！！`, an extracted bank-13 string; `31:$4571` is the
    combining dakuten inside `ダンジョン`, and a string cannot begin on one.
    `msg_push_kind` is the same filter immediate_refs already uses for exactly this.

    -> {box id: [addresses]}
    """
    starts, spans = set(), []
    for box, rows in blocks:
        base = box["bank"] * BANKSZ
        for off, n, _ in rows:
            starts.add(off - base + 0x4000)
        spans.append((box, rows[0][0] - base + 0x4000, rows[-1][0] + rows[-1][1] - base + 0x4000))
    bad = collections.defaultdict(list)
    for i in range(len(rom) - 3):
        if rom[i] not in LD_IMM:
            continue
        ptr = rom[i + 1] | (rom[i + 2] << 8)
        if not (0x4000 <= ptr < 0x8000) or ptr in starts:
            continue
        if rom[i] == 0x01 and msg_push_kind(rom, i):     # bc -> $028B: a BANK 13 address
            continue
        code_bank = i // BANKSZ
        for box, lo, hi in spans:
            if lo <= ptr < hi and code_bank in (0, box["bank"]):
                bad[box["id"]].append(ptr)
    return bad


# ---------------------------------------------------------------- blocks
KNOWN = set(codec.CHARS) | set(codec.COMBINING) | set(codec.CONTROL)

# Banks that actually hold script. Used to resolve immediate operands, which are
# bank-relative and therefore ambiguous without knowing the intended bank.
TEXT_BANKS = (3, 4, 6, 11, 13, 14, 30, 31)

# ---- manual exclusions: data that decodes as text but demonstrably is not.
# Module scope because `immediate_refs` needs it too: these offsets are declared NOT to
# be text, so the "an immediate inside a string is text" rule must not treat their bytes
# as string bytes and suppress a real reference there. 6:$472F in particular IS code.
# The reasoning for each is at the point where they are removed from `entries`.
MANUAL_DROP = {30 * BANKSZ + (0x71BD - 0x4000),
               6 * BANKSZ + (0x472F - 0x4000),
               # The four below arrived together when regions.py's character table was
               # corrected (2026-08-05) and the widened script regions reached four more
               # blocks of non-text. All four are unreferenced, so nothing repoints them;
               # they are dropped so they never reach a translator or the relocator.
               3 * BANKSZ + (0x7580 - 0x4000),
               3 * BANKSZ + (0x7F43 - 0x4000),
               31 * BANKSZ + (0x55D8 - 0x4000),
               31 * BANKSZ + (0x55F2 - 0x4000)}

# ---- candidate pointer tables declared false BY HAND, where no measured rule reaches them.
#
# `MIN_DISTINCT` below catches the tables that are one repeated value. This one is not: it
# ALTERNATES. `9:$6FCD` reads as
#
#     5848  4410  5A50  4410  5C58  4410  ...
#
# -- every other entry the identical $4410, the other half stepping by $208. That is a
# four-byte record structure being read at a two-byte stride, not a table of pointers: a
# table indexed by item or monster does not repeat one address at every odd index. Bank 9
# is one of the four banks this file already names as a source of data that merely decodes
# (see the length note below), and build.py was rewriting ten bytes of it every build.
#
# It is declared rather than measured because the honest measurement does NOT separate it:
# the share of entries taken by one value runs 53%, 50%, 33%, 17% across the accepted
# tables, so any threshold that removed this one would also remove `6:$7C87`, and there is
# no gap to put it in. `MIN_DISTINCT` had a clean gap and is a rule; this does not and is a
# judgement, so it is written down as one.
#
# What it also settles: `11:$5848` is a "string" starting 69 bytes inside `11:$5803`, kept
# alive only by this table, and it was going to fail BADREF the moment the village prose
# around it was translated -- the same way `11:$4847` and `13:$57AB` did.
FALSE_TABLES = {9 * BANKSZ + (0x6FCD - 0x4000)}

# Length is the discriminator that actually works here, measured rather than guessed:
# real strings in the dialogue banks top out at 503 bytes (one "string" is a whole
# multi-box conversation, with <end>/<br> inside), while the data runs that leaked in
# from banks 0/2/3/9 have a median length of 875 and reach 12001. known_ratio looked
# promising but does NOT separate them -- junk medians 0.90 against real p5 of 0.80.
MAX_STRING = 520
MIN_KANA = 0.10      # low: a legitimate line can be almost entirely ellipsis
MIN_KNOWN = 0.80     # loose backstop only, since it is a weak signal on its own
MAX_DIGIT = 0.15     # dialogue barely uses digits; the bank 10 numeric tables are full
                     # of them ("33ああ  い8くえ"), which is what separates them from
                     # real text once the length and kana tests are loosened


def known_ratio(data):
    if not data:
        return 0.0
    return sum(1 for b in data if b in KNOWN) / len(data)


LD_IMM = {0x01: 'bc', 0x11: 'de', 0x21: 'hl'}

# The message-queue push. `0:$028B` takes a pointer in bc, stores it at $FF90/$FF91 and
# pushes it through `0:$23A4` into the ring at `0:$3C5C` -- the queue bank 13's `$67D5`
# consumes. So a `ld bc,$XXXX` that reaches it names a BANK 13 address, whatever bank the
# calling code lives in, and banks 4, 5, 6, 15 and 31 all do this.
MSG_PUSH = bytes([0xCD, 0x8B, 0x02])            # call $028B
MSG_BANK = 13


# Opcodes that leave bc no longer holding the loaded pointer. `inc bc` is in here for a
# reason: `0:$22C0` is `03 03 03 03 c9`, and it is what stops the trace below at $22BD.
BC_WRITE = ({0x01, 0x03, 0x0B, 0xC1,            # ld bc,nn / inc bc / dec bc / pop bc
             0x04, 0x05, 0x06,                  # inc b / dec b / ld b,d8
             0x0C, 0x0D, 0x0E}                  # inc c / dec c / ld c,d8
            | set(range(0x40, 0x50)))           # ld b,r / ld c,r
# Control transfers the trace will not follow: it cannot know whether bc survives them.
BC_STOP = {0xC9, 0xD9, 0xCD, 0xC3, 0xE9, 0x76,  # ret / reti / call / jp / jp hl / halt
           0xC4, 0xCC, 0xD4, 0xDC,              # call cc,nn
           0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}   # rst
JR_ANY = {0x18, 0x20, 0x28, 0x30, 0x38}


def msg_push_kind(rom, i, budget=48):
    """-> 'direct' / 'jr-chain' / None for a `ld bc,nn` at `i` that reaches `$028B`.

    Follows control flow forward from the load until it either reaches the push or loses
    bc. The two shapes this used to match by bytes -- the direct `ld bc,A / call $028B`
    and the two-way `ld bc,A / jr $+3 / ld bc,B / call $028B` -- are just the two shortest
    paths; `0:$30D2` and `0:$30E3` are the same idiom with three candidates and a longer
    `jr`, and matching by bytes missed both.

    THIS IS ALSO THE PHANTOM FILTER, which is the more important job. A bank-0
    `ld bc,$4xxx` either reaches the queue push or it is not a reference to text at all,
    and `dis.boundary_votes` cannot tell the difference: it proves an immediate is not
    inside a longer instruction, not that the bytes are code, and it scores `0:$22BD`
    a perfect 64/0 while $22BD is byte 17 of the 24-byte state-transition table that
    `0:$2274 ld hl,$22AC / add hl,bc / ld a,[hl]` reads. See immediate_refs.
    """
    seen, out, start = set(), None, i + 3
    stack = [(start, 0)]
    while stack:
        at, spent = stack.pop()
        if at in seen or spent > budget or not 0 <= at < len(rom) - 3:
            continue
        seen.add(at)
        if rom[at:at + 3] == MSG_PUSH:
            return 'direct' if at == start else 'jr-chain'
        op = rom[at]
        if op in BC_WRITE:                      # bc no longer holds the pointer
            continue
        _, n = dis.decode(rom, at, at)
        if op in JR_ANY:
            rel = rom[at + 1] - 256 if rom[at + 1] > 127 else rom[at + 1]
            stack.append((at + 2 + rel, spent + n))
            if op == 0x18:                      # unconditional: no fall-through
                continue
        elif op in BC_STOP:
            continue
        stack.append((at + n, spent + n))
    return out


def immediate_refs(rom, entries):
    """Find `ld bc/de/hl,$XXXX` instructions whose operand addresses a known string.

    The message printer $028B takes its pointer in bc, so a large share of dungeon and
    combat text is reached this way rather than through a table. These never cluster, so
    a table scan cannot see them -- they have to be matched by operand value.

    -> {string_offset: [ {kind:'imm', at, operand_at, reg, ptr}, ... ]}

    A match is only kept if `at` is where an instruction REALLY starts (dis.py's
    `is_instruction_start`). Without that test the scan also matches the middle of a
    longer instruction, and a phantom hit is not harmless: build.py rewrites every
    reference it is given, so a phantom inside code writes the string's new address over
    two bytes of a live routine. That shipped -- `0:$227B ld [$CF01],a` became
    `ld [$CE01],a`, because its operand bytes `01 CF` read as `ld bc,$7ECF` and bank 30's
    item verb at 30:$7ECF moved one byte when DTE compressed it. The message system then
    lost the variable that holds a dungeon message on screen, and messages went by too
    fast to read. See FINDINGS.md and HANDOFF_BUG.md.

    `is_instruction_start` cannot help inside a TEXT block, because there is no
    instruction stream there to be inside of -- a linear decode of kana returns whatever
    the kana happen to decode as. `き` is code $11, which is `ld de,nn`, so every string
    containing き offers the scan a load whose "operand" is the next two characters. Two
    of them address a real string by coincidence, and the cost is not a stray reference:
    the operand span makes `holds_ptr` below discard the string the bytes belong to, so
    きみょうなはこ, エーテルもどき and アイアンヘッド -- one item and two monsters, all
    three reached by live pointer tables -- were silently absent from the script.

    So: an immediate that starts inside a known string is text. Measured, this suppresses
    exactly 2 of 249 immediates, both in bank 11, both `ld de` (never a queue push), and
    both demonstrably kana. MANUAL_DROP is excluded from the spans because those offsets
    are declared NOT to be text -- 6:$472F is code, and its bytes must stay eligible.
    """
    want = {}
    for off in entries:
        bank = off // BANKSZ
        want.setdefault((bank, off % BANKSZ + 0x4000), off)
    # +1 for the terminator: a load starting on it is still not code.
    text_spans = sorted((o, o + len(entries[o]) + 1)
                        for o in entries if o not in MANUAL_DROP)
    out = collections.defaultdict(list)
    phantom = []
    pin = set()
    pushes = collections.Counter()
    for i in range(len(rom) - 11):
        reg = LD_IMM.get(rom[i])
        if reg is None:
            continue
        ptr = rom[i + 1] | (rom[i + 2] << 8)
        if not (0x4000 <= ptr < 0x8000):
            continue
        code_bank = i // BANKSZ
        kind = msg_push_kind(rom, i) if reg == 'bc' else None
        cross = CROSS_BANK_IMMEDIATES.get(i)
        if cross is not None:
            expected_reg, target_bank, expected_ptr = cross
            if (reg, ptr) != (expected_reg, expected_ptr):
                raise SystemExit(
                    'cross-bank immediate at %s changed: expected ld %s,$%04X, found '
                    'ld %s,$%04X' %
                    (loc(i), expected_reg, expected_ptr, reg, ptr))
            target = want.get((target_bank, ptr))
            if target is None:
                raise SystemExit(
                    'cross-bank immediate at %s targets missing string %d:$%04X' %
                    (loc(i), target_bank, ptr))
            hits = [(target_bank, target)]
        # A `ld bc` that reaches the message-queue push names a BANK 13 address whatever
        # bank it lives in. This is the ONE case where the bank-trust rule below is wrong,
        # and it is wrong 240 times: banks 4, 5, 6, 15 and 31 push bank-13 messages, so
        # every one of those references used to be discarded. That was invisible for the
        # whole project because bank 13 had never moved -- the stale pointers still
        # happened to be right. The first bank-13 translation moved `13:$4C2D`, the death
        # message, and `5:$44B8`/`5:$5891` kept pointing at the old address: the game
        # crashed to `rst $38` on every death.
        elif kind and (MSG_BANK, ptr) in want:
            hits = [(MSG_BANK, want[(MSG_BANK, ptr)])]
            pushes[kind] += 1
        else:
            hits = []
            for bank in TEXT_BANKS:
                off = want.get((bank, ptr))
                if off is None:
                    continue
                # Only trust a reference the code could actually be making. Bank 0 is
                # resident (the confirmed combat-message callers all live there), and code
                # can always address its own bank. A load in bank 28 whose operand happens
                # to equal a bank 11 string address is bank 28's own data -- rewriting that
                # operand would corrupt unrelated game logic, not repoint a string.
                if code_bank != 0 and code_bank != bank:
                    # ...but if it LOOKS like a reference we cannot verify, do not just
                    # drop it: pin the string so it cannot move. Dropping is only safe
                    # while the target stays put, which is precisely the assumption that
                    # just crashed. Pinning costs a few bytes of a bank and cannot crash.
                    if bank == MSG_BANK and dis.boundary_votes(rom, i)[0] > \
                            dis.boundary_votes(rom, i)[1]:
                        pin.add(off)
                    continue
                hits.append((bank, off))
        if not hits:
            continue
        # Text is not code. See the docstring: this is the only test that works inside a
        # string, because dis.boundary_votes needs an instruction stream to reason about
        # and a kana block does not have one.
        if any(s <= i < e for s, e in text_spans):
            phantom.append((i, ptr, 'starts inside the string at %s, so these bytes are '
                                    'kana and not an instruction'
                                    % loc(next(s for s, e in text_spans if s <= i < e))))
            continue
        # A bank-0 immediate names an ADDRESS, not a bank, so when two banks both hold a
        # string at that address only one of them can be the reference -- and build.py
        # writes the operand once, so recording both guarantees the loser is repointed
        # at the winner's text. Bank 13 wins, from the ROM's own structure rather than
        # from the text: every one of these loads feeds `0:$028B`, which stores the
        # pointer at $FF90/$FF91 and pushes it through `0:$23A4` into the ring at
        # `0:$3C5C` -- the queue bank 13's `$67D5` consumes (FINDINGS.md, "Where dialogue
        # comes from"). Bank 11's and bank 14's text is reached by tables in their own
        # bank, or by a runtime pointer whose stored form has its window bits toggled
        # ($232D, $82B7), never as a plain $4xxx immediate in bank 0.
        #
        # Confirmed three ways: all 24 unambiguous bank-0 immediates resolve to bank 13;
        # the four ambiguous ones claim bank-13 messages carrying <var>/<cE4> against
        # bank-11 monster and item NAMES, which no message pusher would push; and
        # msglog.py caught the composer reading 12 bytes at $4BA7, which is bank 13's
        # `<var>のこうげきをかわした` and not bank 11's 8-byte ぼうれいむしゃ.
        #
        if code_bank == 0 and any(b == 13 for b, _ in hits):
            hits = [(b, o) for b, o in hits if b == 13]
        # ...and the same structure says what a bank-0 immediate is when NO bank-13
        # candidate exists: nothing. The bank-trust rule above cannot filter bank 0 --
        # it is resident, so every text bank's addresses are equally plausible operands
        # -- and reaching the queue push is the only other evidence available. All 25
        # bank-0 `ld bc,$4xxx` are decided by it: 24 reach $028B, and `0:$22BD` does not.
        #
        # $22BD IS NOT A REFERENCE. It is byte 17 of the 24-byte state-transition table
        # at $22AC that `0:$2274 ld hl,$22AC / add hl,bc / ld a,[hl]` indexes; the bytes
        # `01 02 42` read as `ld bc,$4202` and boundary_votes scores them 64/0, because
        # it proves an immediate is not inside a longer instruction and not that the
        # bytes are code. build.py rewrote those two table entries on every build. It
        # was invisible only because address-order packing kept landing 11:$4202 back at
        # $4202, so the write was a no-op -- under any other packing the low nibble of
        # entry 18 steers the machine into state 5, `0:$2337 jr $2337`, and the game
        # hangs. That is the whole of "bank 11 is not freely relocatable".
        if code_bank == 0 and not kind:
            phantom.append((i, ptr, 'reaches no `call $028B`, so bc is not a text pointer'))
            continue
        # The byte scan found the SHAPE of a load; only a decode can say whether it
        # found the instruction. Check before recording, not after: an unfiltered
        # phantom is two bytes of live code the inserter will overwrite.
        on, over = dis.boundary_votes(rom, i)
        if on <= over:
            phantom.append((i, ptr, '%d of %d linear decodes step OVER it, so it is '
                                    'inside another instruction' % (over, on + over)))
            continue
        for _, off in hits:
            out[off].append({"kind": "imm", "at": i, "operand_at": i + 1,
                             "reg": reg, "ptr": ptr})
    for i, ptr, why in phantom:
        print("phantom `ld r16,$%04X` at %s ignored: %s" % (ptr, loc(i), why))
    if pushes:
        print("message-queue pushes: %d cross-bank `ld bc,$XXXX` -> `call $028B` "
              "resolved to bank 13 (%s)"
              % (sum(pushes.values()),
                 ', '.join('%s %d' % kv for kv in sorted(pushes.items()))))
    pin -= set(out)          # a string with a verified reference does not need pinning
    if pin:
        print("pinned %d bank-13 string(s): an untrusted-bank `ld bc` looks like a "
              "reference but does not reach $028B, so they must not move" % len(pin))
    return out, pin


# Banks whose text dispatches through 13:$68CF instead of 13:$4126, and whose legal
# control range is therefore four codes longer. See codec.CONTROL_MAX.
DIALOGUE_PATH_BANKS = (11, 14)


def impossible(data, bank=None):
    """True if the bytes cannot be script IN THIS BANK.

    A byte past the end of the bank's dispatch table would index into garbage and jump
    there, so real script never contains one. This rule also purges the pointer tables the
    block walker used to emit as 'strings' -- their high bytes land in that range.

    THE TABLES ARE DIFFERENT LENGTHS AND THIS USED TO IGNORE THAT, at a cost of 532 bytes
    of dialogue across 12 strings -- the shop's opening line, Yoshizota's confession, the
    ending narration, Keyaki at the shrine. `13:$4126` (bank 13, messages) has 17 entries,
    $E0-$F0; `13:$68CF` (banks 11/14, dialogue) has 21, $E0-$F4. Applying bank 13's limit
    everywhere made `$F1`-`$F4` look impossible in exactly the banks where they are
    ordinary control codes.

    **It discarded whole BLOCKS, not just the bytes.** A `$FF`-delimited block is not one
    string in these banks, so a single `$F4` threw away everything around it: `14:$4C89`'s
    block is 125 bytes holding two complete messages separated by one `$F4`.

    `bank=None` keeps the strict $E0-$F0 reading. That is the safe default and it is what
    every caller outside banks 11/14 wants.
    """
    top = codec.CONTROL_MAX if bank in DIALOGUE_PATH_BANKS else 0xF0
    arity = codec.arity_for(bank)
    i = 0
    while i < len(data):
        value = data[i]
        if top < value <= 0xFE:
            return True
        arguments = arity.get(value, 0)
        if i + arguments >= len(data):
            return True
        # Argument bytes are data, not opcodes. In particular dialogue-path $E3 may
        # legally consume selector $FE; treating that selector as an impossible control
        # hid Keyaki's Otogiri Herb receipt at 14:$52AB from extraction.
        i += 1 + arguments
    return False


def script_starts_at(data, bank):
    """Offset the real string starts at, skipping code that precedes it in the same run.

    A `$FF`-delimited run is not always one string: in banks 11 and 14 a routine's bytes
    can sit immediately before the text it prints, with no terminator between, because the
    only `$FF` around is the string's own. `14:$401D` reads as

        ほ1せ<br>＋<brk> <$C0> ヨ ＋ <name> ？ <$CF> − <name> ］ <$CF> <cE1> <$C1> <cF1> <$C9>
        てんしゅ「いらっしゃいませ」<cE0:15>

    -- and `$C9` is `ret`. Extracting from `$401D` would hand the inserter twenty bytes of
    live code to overwrite the moment anyone translated the shop's greeting.

    THE MARKER IS THE DTE CODE SPACE, $C0-$DF, and that is measured rather than chosen:
    `tools/dte_ranges.py` establishes which bytes untranslated Japanese never contains, and
    that is the whole basis on which DTE codes are allocated. A $C0-$DF byte that is not a
    control code's argument therefore is not text. Arguments have to be excluded first --
    `$EB`'s typewriter pause is routinely $C8 or $DC, which is exactly why those two are
    not DTE codes (see dte_rom.DTE_RANGES).

    Restart after the LAST such byte, not the first: `14:$401D` has five.

    **This lands on the nose in both cases it fires**, which is the reason to trust it:
    `14:$401D` -> `14:$4031`, `てんしゅ「いらっしゃいませ」`, and `11:$56B2` -> `11:$56C3`,
    `フミ「・・・おかあさん`. Both were identified by eye first and the rule agrees with
    neither tuned to it.
    """
    out, i = -1, 0
    while i < len(data):
        b = data[i]
        if b in KNOWN:
            # $EB reads one argument on the dialogue path (13:$690F) and none on bank 13's
            # (13:$416D); codec.arity_for keeps every other difference between the two
            # tables. Skipping the argument here is what stops a $C8 pause count being
            # read as code.
            n = codec.arity_for(bank).get(b, 0)
            if b == 0xEB and bank in DIALOGUE_PATH_BANKS:
                n = 1
            i += 1 + n
            continue
        if 0xC0 <= b <= 0xDF:
            out = i
        i += 1
    return out + 1


def digit_ratio(data):
    if not data:
        return 0.0
    return sum(1 for b in data if 0x01 <= b <= 0x0A) / len(data)


# Label blocks too sparse for automatic region detection. The status screen keeps its
# labels among binary data, so the kana-density test never fires on them -- but they are
# ordinary $FF-delimited strings once you know where to look. Found from a screenshot.
#
# Bounds matter: these regions are NOT padded (see block_strings), precisely because
# `trusted` waives the statistical filters. An over-wide region hands that waiver to
# whatever data happens to sit next to the labels. The earlier bounds were narrower than
# these but were padded by 0x100 on each side, which is how ~1 KiB of bank 4 and bank 31
# binary data entered the script as "strings".
EXTRA_REGIONS = [
    (4 * BANKSZ + (0x4AFC - 0x4000), 4 * BANKSZ + (0x4B02 - 0x4000)),    # money label
    # Bank 31 used to need two hand-written regions here -- the name-entry screen and the
    # yes/no + difficulty prompts. Both are gone: box_descriptors() enumerates all 52
    # boxes from the table the game itself indexes, which is authoritative where a bound
    # guessed from a screenshot never was. The old bounds missed 17 boxes between them.
]


def block_strings(rom, covered, pad=0x100):
    """Sequential 0xFF-delimited strings in script regions, skipping known offsets.

    Block-sourced strings get stricter filtering than table-sourced ones: a pointer
    table structurally vouches for its targets, whereas a sequential walk through a
    mis-classified region will happily emit data.
    """
    found = []
    for s, e, trusted in ([(a, b, False) for a, b in script_regions(rom)]
                          + [(a, b, True) for a, b in EXTRA_REGIONS]):
        # Hand-specified regions are already exact -- padding them would extend the
        # `trusted` waiver into the neighbouring data, which is the bug that let
        # ~1 KiB of binary into the script.
        p = 0 if trusted else pad
        lo, hi = max(0, s - p), min(len(rom), e + p)
        # align to a terminator so we do not start mid-string
        while lo > 0 and rom[lo - 1] != codec.TERMINATOR:
            lo -= 1
        # and extend the end so the final string is not cut off mid-way -- a truncated
        # fragment would get locked in by setdefault and could never be corrected
        while hi < len(rom) and rom[hi - 1] != codec.TERMINATOR:
            hi += 1
        for off, data in codec.split_strings(rom, lo, hi):
            # Drop any code that precedes the text inside this run. Done BEFORE `covered`
            # and before the statistical filters, because the filters have to judge the
            # string and not the routine sitting in front of it -- the untrimmed
            # `14:$401D` is 36 bytes of which 20 are a routine, which drags every ratio.
            #
            # DIALOGUE BANKS ONLY. Applied ROM-wide it also trims the head off data runs
            # in banks 2, 3, 4, 9, 29 and 31, exposing tails that then pass the
            # statistical filters -- 12 junk strings, one of them in bank 9, which
            # logicdiff requires to be untouched. The phenomenon being corrected is
            # specific to how banks 11 and 14 store dialogue next to the code that prints
            # it, so the correction is too.
            if not trusted and bank_of(off) in DIALOGUE_PATH_BANKS:
                skip = script_starts_at(data, bank_of(off))
                if skip:
                    off, data = off + skip, data[skip:]
            if off in covered or len(data) < 2:
                continue
            if bank_of(off) in GFX_BANKS or FONT[0] <= off < FONT[1]:
                continue
            if len(data) > MAX_STRING:
                continue
            # Hand-specified regions are trusted: they were located from a screenshot,
            # so the heuristics that guard auto-detected regions only get in the way.
            # 31:$41E2 has 3 digits in 19 bytes (layout data) and the digit filter
            # rejected it, leaving the weapon/strength row untranslatable.
            if not trusted:
                if codec.kana_ratio(data) < MIN_KANA or known_ratio(data) < MIN_KNOWN:
                    continue
                if digit_ratio(data) > MAX_DIGIT:
                    continue
            # `impossible` is NOT a heuristic and is never waived. It follows from the
            # bank's dispatch table having a fixed length: a byte past its end would index
            # into garbage and jump there, so the game could not survive rendering such a
            # string. Trust exempts the statistical filters above, never this one.
            #
            # It takes the BANK, because the two tables are different lengths -- $E0-$F4 on
            # the banks-11/14 dialogue path, $E0-$F0 on bank 13's message path. Passing the
            # bank is the whole of session 8b.
            if impossible(data, bank_of(off)):
                continue
            found.append((off, data))
    return found


# ---------------------------------------------------------------- main
def main():
    a = sys.argv[1:]
    rom_path = a[0]
    outdir = a[a.index('--out') + 1] if '--out' in a else 'script'
    rom = open(rom_path, 'rb').read()
    os.makedirs(outdir, exist_ok=True)

    entries = {}          # offset -> record
    refs = collections.defaultdict(list)

    tables = findtables.scan(rom)
    real = [t for t in tables if t['pos'] not in FALSE_TABLES and table_is_real(rom, t)]
    rejected = len(tables) - len(real)

    # ---- tables whose true length the scanner cannot see
    # The item action verbs at 30:$7E99 are 21 entries, not the 15 the scan finds: entry 15
    # points at a lone $FF (an empty verb slot), the run of plausible pointers breaks there,
    # and everything after it was invisible. Three of those hidden entries are LIVE verbs --
    # ひろう / はずす / だす -- reached from the category tables at 30:$7E14 and $7E40 and
    # from the equip/remove substitution at 30:$7D73. They would have stayed Japanese
    # forever, in a menu that is otherwise English.
    #
    # 21 is not a guess: entry 20 is the last one before code at 30:$7F0C, and index 20 is
    # the highest value any builder table stores.
    #
    # The item descriptions at 13:$554A are 157 entries, not the 137 the scan finds, and
    # they break for the same reason: topic 137 points at `13:$677F`, which is one space
    # and a terminator -- the blank description shared by the unused item slots -- so the
    # run of "plausible pointers" ends there and the last twenty topics are invisible.
    #
    # 157 is proven twice over and neither is a guess. $554A + 157*2 = $5684, which is
    # exactly where the first description (the Club's) begins: the table ends on the byte
    # its own data starts. And 157 is the length of the item NAME table at 11:$4537, which
    # topic index maps to one-for-one -- topic 0 is the Club, topic 4 the Dragon Killer.
    #
    # What it cost to leave alone: `13:$6781` (money) and `13:$67B0` (the Kasa Tanuki) sat
    # past entry 137 with no reference at all, and were relocatable only by accident --
    # a weak "table" elsewhere happened to address them. Removing those tables left both
    # honestly unreferenced and too long to translate in place.
    for t in real:
        if t['pos'] == 30 * BANKSZ + (0x7E99 - 0x4000) and t['count'] < 21:
            print("extended table %s: %d -> 21 entries (empty slots hid the tail)"
                  % (loc(t['pos']), t['count']))
            t['count'] = 21
        if t['pos'] == 13 * BANKSZ + (0x554A - 0x4000) and t['count'] < 157:
            print("extended table %s: %d -> 157 entries (a blank description hid the tail; "
                  "the table ends where its text begins, $5684)" % (loc(t['pos']), t['count']))
            t['count'] = 157

    for tab in real:
        for idx, (ptr_off, ptr, off) in enumerate(findtables.entries(rom, tab)):
            data = string_at(rom, off)
            # A table structurally vouches for its targets, so table-sourced strings
            # skip the statistical filters -- but not this one. `impossible` is a
            # property of the string itself, not of how it was reached: the game could
            # not render a byte past its dispatch table's end, whoever pointed at it. A
            # table that targets one is a false positive (3:$4646 was reached by a "table"
            # whose six entries all held the same pointer).
            if impossible(data, bank_of(off)):
                continue
            entries.setdefault(off, data)
            refs[off].append({"kind": "table", "table": tab['pos'],
                              "target_bank": tab['target_bank'], "index": idx,
                              "operand_at": ptr_off, "ptr": ptr})

    # ---- menu boxes: authoritative, so they override anything already found here
    boxes = box_descriptors(rom)
    blocks = [(b, box_rows(rom, b)[0]) for b in boxes if 0x4000 <= b['text'] < 0x8000]
    interior = box_interior_targets(rom, blocks)

    box_meta, desc_bytes, box_bytes = {}, set(), set()
    for b in boxes:
        desc_bytes.update(range(b['desc'], b['desc'] + DESC_LEN))
    for b, rows in blocks:
        # A block whose interior is loaded directly by code cannot be relocated: only
        # row starts get a record, so a load into the middle of a row would be left
        # pointing at whatever moved in. Pin the whole box instead -- in-place text is
        # merely un-growable, whereas a stale pointer is silent corruption.
        pinned = b['id'] in interior
        for r, (off, n, term) in enumerate(rows):
            box_bytes.update(range(off, off + n + (1 if term else 0)))
            box_meta[off] = {"id": b['id'], "row": r, "rows": b['rows'],
                             "width": b['width'], "x": b['x'], "y": b['y'],
                             "desc": b['desc'], "term": term, "pinned": pinned}
            entries[off] = rom[off:off + n]
            if r == 0 and not pinned:
                refs[off].append({"kind": "box", "box": b['id'],
                                  "operand_at": b['desc'] + 5, "ptr": b['text']})

    # Descriptor bytes are data, and a block's non-start bytes belong to their row.
    for o in [o for o in entries if o in desc_bytes
              or (o in box_bytes and o not in box_meta)]:
        entries.pop(o, None)
        refs.pop(o, None)
    print("menu boxes        : %d in table, %d with ROM text, %d rows, %d pinned (%s)"
          % (len(boxes), len(blocks), len(box_meta), len(interior),
             ' '.join('box%d@%s' % (i, ','.join('$%04X' % a for a in v))
                      for i, v in sorted(interior.items())) or 'none'))

    covered = set(entries) | desc_bytes | box_bytes
    for off, data in block_strings(rom, covered):
        entries.setdefault(off, data)

    # A runtime entry may be nested in a parent already found above.  Add it before the
    # reference pass so it gets the same validation, overlap accounting and round-trip
    # checks as every statically discovered string.  ``runtime_entry`` metadata below is
    # deliberately NOT a pointer reference: there is no operand for build.py to rewrite.
    for off, evidence in RUNTIME_INTERIOR_ENTRIES.items():
        if not 0 <= off < len(rom):
            raise SystemExit('runtime interior entry outside ROM: %s' % loc(off))
        data = string_at(rom, off)
        if impossible(data, bank_of(off)):
            raise SystemExit('runtime interior entry is not valid text: %s' % loc(off))
        entries.setdefault(off, data)

    # Immediate-load references, resolved after every string is known. `entries` rather
    # than its keys: immediate_refs needs the string SPANS, to tell a load from the kana
    # that happen to spell one.
    imm, pinned = immediate_refs(rom, entries)
    for off, lst in imm.items():
        refs[off].extend(lst)

    # ---- manual exclusions: data that decodes as text but demonstrably is not
    # 30:$71BD is `7f 2f 3f 1f 0f 1f 0f 1f 17 3f df` -- descending bit masks, a bitmask
    # table. Extracting it as a string cost 12 bytes of bank 30, which is exactly the
    # space the English item verbs need.
    #
    # 6:$472F is CODE, and it was bank 6's only "string" -- the bank has none. It is the
    # `ld hl,$786A` in the middle of the routine at `6:$4722`:
    #
    #     ld d,$00 / ld e,a / ld hl,$77CD / add hl,de / ld a,[hl] / ld [$FF90],a
    #                         ld hl,$786A / add hl,de / ld a,[hl] / ld [$FF91],a
    #
    # -- two identical idioms filling the message-pointer pair. What pointed "at" it is
    # the cross-bank table `10:$4663`, and a cross-bank table carries no bank byte, so the
    # target bank was an inference and it was wrong; the entries are also 1 and 2 bytes
    # apart, which no string can be. So build.py was rewriting six words of bank-10 data
    # on every build, and it only looked harmless because the string was placed back at
    # its own address every time -- the same accident that hid `0:$22BD`.
    #
    # This is also the whole of bank 6's endgame shortfall: 2.15x of a string that is not
    # one. The arena disappears with it rather than being budgeted for.
    #
    # 3:$7580 is the SAME IDIOM as 6:$472F, and it is worth seeing why it reads as a string
    # at all. The routine is:
    #
    #     ld hl,$000A / add hl,de / ld a,[hl+] / ld h,[hl] / ld l,a / ld a,[hl]
    #     ld [$FF91],a / call $19BC
    #
    # -- ordinary message-pointer plumbing. The `$FF` the string splitter stopped on is the
    # high byte of `ld [$FF91],a`'s operand, not a terminator. Any run-of-$FF-delimited-
    # bytes scan will find "strings" wherever code addresses the $FFxx page, which is
    # exactly where the message system lives, so this shape recurs.
    #
    # 3:$7F43 (`09 09 0e 0e 15 0e 13 09 15 ...`) is a repetitive small-value table;
    # 31:$55D8 and 31:$55F2 both carry bytes the codec cannot name ($C0, $DB) and
    # disassemble as ordinary code. None of the four has a single reference.
    #
    # (The set itself is at module scope -- immediate_refs excludes it from the spans it
    # treats as text, so that 6:$472F's bytes stay eligible to be the code they are.)
    for o in MANUAL_DROP:
        if entries.pop(o, None) is not None:
            refs.pop(o, None)
            print("dropped manual exclusion at %s (known data, not text)" % loc(o))

    # ---- drop anything overlapping a pointer TABLE
    # A table's bytes can decode as plausible text (11:$55AC reads as `<$C6>ト<$DE>ト...`
    # but is really `c6 55 de 55 f0 55 ...`, pointers into $55xx). Extracting that as a
    # string let the inserter relocate it and overwrite the real table -- silent
    # corruption that only the reference verification caught.
    table_spans = [(t['pos'], t['pos'] + t['count'] * 2) for t in tables]
    clobber = {o for o in entries
               if any(o < te and ts < o + len(entries[o]) + 1 for ts, te in table_spans)}
    for o in clobber:
        entries.pop(o, None)
        refs.pop(o, None)
    if clobber:
        print("dropped %d 'strings' that overlap a pointer table" % len(clobber))

    # ---- drop 'strings' that contain a reference OPERAND
    # A region holding a pointer is data, not text, even when its bytes decode. 4:$4AD8
    # contains the 2-byte pointer to 4:$4AFE; extracting it as a string meant the
    # verifier reported a mismatch every time that pointer was legitimately rewritten.
    operand_spans = [(rf['operand_at'], rf['operand_at'] + 2)
                     for lst in refs.values() for rf in lst if 'operand_at' in rf]
    holds_ptr = {o for o in entries
                 if any(o < b and a < o + len(entries[o]) + 1 for a, b in operand_spans)}
    for o in holds_ptr:
        entries.pop(o, None)
        refs.pop(o, None)
    if holds_ptr:
        print("dropped %d 'strings' that contain a pointer operand" % len(holds_ptr))

    # ---- drop spurious mid-string starts
    # The block walker can begin a "string" partway inside a real one -- typically just
    # after a dakuten byte, producing a fragment like `゙のえのまきもの` inside
    # `ヒツジのえのまきもの`. A start strictly inside another string, with nothing
    # pointing at it, is not a real string. Nested starts that ARE referenced are kept:
    # those are legitimate mid-conversation entry points.
    #
    # ...with one exception, and it is a fact about the CODEC rather than a heuristic, so
    # a reference does not buy it a waiver. $79/$7A are COMBINING marks: they draw a
    # dakuten over the cell already emitted, so a string cannot begin with one -- there is
    # no preceding cell to voice. `11:$4847` is `ヒツジ...`'s dakuten and the seven bytes
    # after it, and what "referenced" it was index 0 of a six-entry cross-bank "table" in
    # bank 10 whose other five entries all hold the same pointer -- bank 10 is the numeric
    # stat data, and 6:$472F is already dropped by hand for being the same mistake.
    #
    # Keeping it was not cosmetic. It OVERLAPS `11:$4844`, so the inserter placed both and
    # one wrote over the other: the build failed `BADREF id=195 11:$4844` the moment that
    # string was translated, and would have done so for any translation of Sheep Scroll.
    # ...and with a second exception, which is about the EVIDENCE rather than the string.
    # "Referenced, so it is a real entry point" is only as good as the reference, and a
    # "table" whose entries are all the same value is not a pointer table: indexing it
    # cannot select anything. Measured over all 39 candidate tables the split is clean --
    # 19 have one or two distinct entries and 20 have four or more, with nothing at three
    # -- and the rule reproduces a judgment this file already makes by hand: `10:$4663`,
    # the "table" that put `6:$472F` in MANUAL_DROP, is six identical pointers.
    #
    # `13:$57AB` is why this is here. It starts TWO bytes inside `13:$57A9`, splitting
    # かいしん in half, and what "referenced" it was `6:$56B9` -- one $57AB followed by
    # seventeen identical $57E2, in the middle of a longer run of repeated constants in a
    # bank whose only other "string" is already hand-dropped as code. Both strings were
    # placed, one wrote over the other, and the build failed `BADREF id=855 13:$57A9` the
    # moment the Minotaur Axe description was translated -- exactly what `11:$4847` did.
    #
    # Deliberately scoped to nested starts, which is the only place a bad reference has
    # been shown to do damage: it changes 1 string, not the 18 other weak tables, which
    # are a separate finding and not this session's to act on.
    weak = {t['pos'] for t in tables
            if len({rom[t['pos'] + 2 * i] | rom[t['pos'] + 2 * i + 1] << 8
                    for i in range(t['count'])}) < 3}

    def credible(o):
        return [r for r in refs.get(o, ()) if r.get('table') not in weak]

    order = sorted(entries)
    spans = [(o, o + len(entries[o])) for o in order]
    drop, combining, weakref = set(), set(), set()
    for i, (s, e) in enumerate(spans):
        for j in range(i + 1, len(spans)):
            s2, _ = spans[j]
            if s2 >= e:
                break
            if entries[s2][:1] and entries[s2][0] in codec.COMBINING:
                combining.add(s2)
            elif s2 in RUNTIME_INTERIOR_ENTRIES:
                continue
            elif not refs.get(s2):
                drop.add(s2)
            elif not credible(s2):
                weakref.add(s2)
    drop |= weakref
    for o in drop | combining:
        entries.pop(o, None)
        refs.pop(o, None)
    if drop:
        print("dropped %d mid-string fragments (unreferenced starts inside another string)"
              % len(drop))
    for o in sorted(combining):
        print("dropped mid-string fragment at %s: starts with a combining dakuten, which "
              "voices the cell before it -- no string can begin there" % loc(o))
    for o in sorted(weakref):
        print("dropped mid-string fragment at %s: its only reference is a 'table' of one "
              "repeated value, which cannot be a pointer table" % loc(o))

    # ---- verify before emitting anything
    records, failures = [], []
    for n, off in enumerate(sorted(entries)):
        data = entries[off]
        # The bank decides which dispatch table read this string, and five codes take a
        # different number of arguments on each. Getting it wrong is invisible in the
        # Japanese -- the bytes round-trip either way -- and hides a real character
        # inside a control token, which then prints as garbage in front of the English.
        try:
            jp = codec.decode(data, bank_of(off))
            back = codec.encode(jp, bank_of(off))
            ok = (back == data)
        except Exception as exc:
            jp, ok = '', False
            failures.append((off, data, str(exc)))
            continue
        if not ok:
            failures.append((off, data, 'round-trip mismatch: %s' % back.hex(' ')))
            continue
        rec = {
            "id": n,
            "offset": off,
            "loc": loc(off),
            "bank": bank_of(off),
            "bytes": len(data),
            "hex": data.hex(' '),
            "jp": jp,
            "en": "",
            "refs": refs.get(off, []),
        }
        # An unverifiable `ld bc` in an untrusted bank looks like a reference to this
        # string and we cannot prove it either way. Refuse to RELOCATE it rather than
        # repoint a load that may not be one -- see immediate_refs.
        if off in pinned:
            rec["pin"] = "unverified imm ref in an untrusted bank"
        if off in box_meta:
            rec["box"] = box_meta[off]
        if off in RUNTIME_INTERIOR_ENTRIES:
            rec["runtime_entry"] = RUNTIME_INTERIOR_ENTRIES[off]
        records.append(rec)

    # ---- emit
    manifest = {
        "rom": os.path.basename(rom_path),
        "rom_sha1": hashlib.sha1(rom).hexdigest(),
        "tables_found": len(tables),
        "tables_used": len(real),
        "tables_rejected": rejected,
        "string_count": len(records),
        "script_bytes": sum(r["bytes"] for r in records),
        "runtime_interior_entries": [
            {"loc": loc(off), "evidence": evidence}
            for off, evidence in sorted(RUNTIME_INTERIOR_ENTRIES.items())
        ],
        # The whole geometry table, including the boxes whose text is staged in WRAM and
        # so has no rows here (the item list and the item action menu). Their width is
        # still editable, and it is the one that hurts most.
        "boxes": [dict(b, wram=not (0x4000 <= b['text'] < 0x8000),
                       pinned=b['id'] in interior) for b in boxes],
        "strings": records,
    }
    jpath = os.path.join(outdir, 'script.json')
    with open(jpath, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    tpath = os.path.join(outdir, 'script.tsv')
    with open(tpath, 'w', encoding='utf-8') as f:
        f.write("id\tloc\tbytes\tjp\ten\n")
        for r in records:
            f.write("%d\t%s\t%d\t%s\t\n" % (r["id"], r["loc"], r["bytes"], r["jp"]))

    # ---- report
    print("tables: %d found, %d used, %d rejected as non-text" % (len(tables), len(real), rejected))
    print("strings extracted : %d" % len(records))
    print("script bytes      : %d (%.1f KiB)" % (manifest["script_bytes"],
                                                 manifest["script_bytes"] / 1024))
    print("round-trip        : %s" % ("ALL OK" if not failures else "%d FAILURES" % len(failures)))
    for off, data, why in failures[:15]:
        print("   0x%06X %s : %s" % (off, loc(off), why))
        print("      %s" % data.hex(' ')[:70])
    by_bank = collections.Counter(r["bank"] for r in records)
    print("per bank          : %s" % ' '.join("b%d:%d" % (b, c) for b, c in sorted(by_bank.items())))
    print("wrote %s and %s" % (jpath, tpath))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
