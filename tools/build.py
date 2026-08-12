#!/usr/bin/env python3
"""Build a translated ROM: font + script insertion + repointing + checksums.

Three insertion strategies, chosen per string by how the game reaches it:

  RELOCATE   the string is reached by a pointer table entry and/or an `ld bc,$XXXX`
             immediate. Both are 2-byte operands we can rewrite, so the string may be
             moved anywhere WITHIN ITS OWN BANK and every reference updated.

  IN PLACE   nothing static points at it -- village/story dialogue reaches its text via
             a pointer assembled at runtime and passed through the message queue. There
             is no operand to rewrite, so the string must keep its exact address and can
             only be replaced with something no longer than the original.

Why "within its own bank" and not the expanded banks: the reading code lives in the same
bank as its text, so the bank is implicit. Moving text to bank 32+ would require the
reader to switch banks, which is ASM work this tool does not do. Repacking within a bank
still helps, because strings that shrink donate their space to strings that grow.

usage: build.py <rom> <translations.tsv> <out.gb> [--report FILE]
       translations.tsv:  id <TAB> english
"""
import sys, os, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec
import dis                    # this project's disassembler, NOT the stdlib one
import dte_rom
import dialogue_preview as dialogue     # source + pixel contracts for each text renderer
import lint_en                          # control-token parity: what encode_en cannot see
import name6                            # the player name, 4 characters -> 6
import rank6                            # the rankings board, 4 name characters -> 6
import itemfix                          # runtime item punctuation/counter normalization
import awardfix                         # Awards screen's native four-kana code -> heading
import decoyname                        # Decoy Staff target uses the live player name
import vwf                              # retained uniform-6px diagnostic renderer
import propvwf                          # opt-in approved proportional composer
import menuvwf                          # the MENU drawer's VWF (item-list rows)
import structvwf                        # fixed-position font fragments in composite rows
import rankvwf                          # rankings board's six-cell proportional names
import dotfont                          # approved proportional-font source/spec loader
import intro                            # separately encoded opening cinematic + font packs
import markers                          # approved Poppins town/dungeon arrival-card graphics
import titlecard                        # pre-intro English title/copyright graphics card
import titlelogo                        # illustrated English title-screen logo
import waitcard                         # active-dungeon Continue loading bubble
import endingcredits                    # approved English ending-credit graphics
import pool as textpool          # `pool` is taken: build.py's free-run allocator
from latinfont import EN_CODES, patch as patch_font

BANKSZ = 0x4000
COMBINING_BYTES = set(codec.COMBINING)

# ---------------------------------------------------------------- endgame projection
#
# WHY THIS EXISTS. Every space decision in this project was costed against 1.66x, an
# estimate from one 18-string sample, and every session then discovered a shortfall. The
# reason it kept being a surprise is that this file reported TODAY's spare and nothing else
# -- bank 11 reads "+29 spare" with 3 of its 462 strings translated, which is true and
# useless. A bank does not run out when you translate the last string; it runs out at some
# point in the middle, and by then the work is done and has to be unwound.
#
# So every arena now reports what it will need when the script is FINISHED, and it does it
# pessimistically on purpose:
#
#   * 2.15x, not 1.66x. That is `14:$5047`, the only string in the project ever written as
#     natural English with no fitting -- 190 Japanese bytes to 407 raw. It measured 2.17x
#     before job 1a re-wrapped it, so it is not an artefact of the wrapping.
#   * DTE is ASSUMED ON. Untranslated Japanese does not compress against an English-trained
#     table, so a projection that ignored DTE would be pessimistic in the wrong place --
#     it would inflate the need instead of exposing the arena. The 74% is measured on the
#     same string, 407 raw to 302 packed.
#
# Being wrong high costs nothing. Being wrong low has cost this project a session, twice.
PROJECT_RATIO = 2.15                # natural English, measured on 14:$5047 (190 -> 407)
PROJECT_DTE = 302 / 407             # what DTE then took off it
PROJECT_NET = PROJECT_RATIO * PROJECT_DTE

# The name-entry character picker. Its grid is a normal menu box, but bank 31 also does
# ARITHMETIC on that box's layout to turn a cursor position into a character: at 31:$419D
# it computes base + (row - 1) * stride + column, where `base` is the box's row 1 (a
# normal reference, repointed with the box) and `stride` is an immediate operand. So the
# box's row spacing is duplicated in code, and translating the box changes it -- rows that
# fill all 18 cells lose their terminators and go from 19 bytes apart to 18.
GRID_BOX = 12                       # the page whose layout the picker addresses
GRID_STRIDE_AT = 31 * BANKSZ + (0x41A1 - 0x4000)    # operand of 31:$41A0 `ld a,$13`
GRID_STRIDE_OPCODE = 0x3E                            # `ld a,n8`, checked before patching

# The bank-13 message gate compares hl against ONE hardcoded string address, split into two
# `ld a,n8` immediates so no pointer scan can see it. See the patch site for the full story.
# Fay's Puzzles draws its header TWICE, from two different places, and only one is
# text. On entry it draws box 30 (`31:$4435`); on every task change it copies a
# PRE-RENDERED TILEMAP ROW out of bank 4. Joey found this by playing: the header is
# English until you pick a different challenge, and then it is not, and going back does
# not bring it back.
#
# `4:$704E` is `だい   もん  なんいど` with the dakuten bytes stripped and padded to all 18
# cells, followed by `$BF` -- the box's right-border tile -- and `$FF`. One byte per cell,
# no control codes, so it is tiles rather than a string, which is why `coverage.py` cannot
# see it: it scans `$FF`-framed runs in the SCRIPT banks and this is neither.
#
# MIRRORED FROM THE BOX-30 TRANSLATION RATHER THAN TRANSLATED SEPARATELY. Two copies of
# one row is what put this bug here, and a second hand-maintained copy would go stale the
# same way the first did. The guard below is what makes that safe: if the bytes at
# `4:$704E` are ever not the row we think, the build says so instead of writing over
# whatever moved in.
QUIZ_ROW_LOC = '31:$4435'
QUIZ_ROW_AT = 4 * BANKSZ + (0x704E - 0x4000)
QUIZ_ROW_CELLS = 18
QUIZ_ROW_JP = bytes.fromhex('1a0c0000002d3800001f380c1e0000000000')

# The status screen draws the current Path value at absolute shadow column 9. Bank 4's
# table at $4FE5 supplies a different count of leading blank cells for each path because
# the Japanese labels are 4/3/6 cells. The English values are now Easy/Normal/Hard, so
# right-align all three through column 18 with 6/4/6 leading cells. This is independent of
# proportional VWF: the game owns these fixed cells and the alignment belongs to its
# absolute writer. ``pathspill.py`` measures modes 1/2/3 through the real Log-2 sign route.
PATH_PADDING_AT = 4 * BANKSZ + (0x4FE6 - 0x4000)
PATH_PADDING_OLD = bytes((0x06, 0x07, 0x05))
PATH_PADDING_NEW = bytes((0x06, 0x04, 0x06))

DEATH_CMP_LOC = '13:$4C2D'
DEATH_CMP_LO = 13 * BANKSZ + (0x4060 - 0x4000)      # operand of 13:$405F `ld a,$2D`
DEATH_CMP_HI = 13 * BANKSZ + (0x4065 - 0x4000)      # operand of 13:$4064 `ld a,$4C`


def cells(data, bank=None):
    """Screen cells a string occupies. Dakuten costs a byte but no cell.

    Control codes are not cells either: `$E0`-`$F0` and their argument bytes never reach
    the tilemap, and `<br>`/`<end>` end the line rather than sitting on it. Counting them
    would charge a dialogue line for its own line break. Box rows contain no control
    codes, so this leaves every box measurement exactly as it was.

    `bank` matters for the same reason it matters to the codec: on the dialogue path
    `$E7` and `$F0` take no argument, so the byte after one is a glyph and does cost a
    cell. Without it a line carrying one of those measures a cell short.
    """
    arity = codec.arity_for(bank)
    out, i = 0, 0
    while i < len(data):
        b = data[i]
        if codec.CONTROL_MIN <= b <= codec.CONTROL_MAX:
            i += arity.get(b, 0)
        elif b not in COMBINING_BYTES:
            out += 1
        i += 1
    return out


def encode_en(text, bank=None):
    """English -> game bytes. `<$XX>` emits a raw byte verbatim; `<var>`, `<br>`,
    `<cE0:88>` and the rest of codec.CONTROL emit the control code and its arguments.

    Some status-screen strings are composites that pack two labels plus layout into one
    string (bank 31 $41E2 is `<prefix>けんのつよさ  ▌ちから`). Those bytes are not text
    and must survive untouched, so the translation file needs a way to say "this byte,
    exactly".

    Dialogue needs the NAMED form as well. `<$E2>` would work byte-for-byte, but the
    escape check downstream treats an escape as layout to be reserved out of the DTE code
    space -- and a control code is already excluded by being >= $E0. Spelling it `<var>`
    keeps the two categories apart, and it round-trips with what codec.decode prints in
    script.tsv, so a translator can copy the token out of the Japanese column.

    `bank` picks the dispatch path, so that a token copied out of the Japanese column
    encodes back to the bytes it came from -- `<cF0>` in banks 11/14, `<cF0:xx>`
    elsewhere. See codec.arity_for.
    """
    arity = codec.arity_for(bank)
    out = bytearray()
    pos = 0
    for m in codec.TOKEN_RE.finditer(text):
        for ch in text[pos:m.start()]:
            if ch not in EN_CODES:
                raise ValueError('no glyph for %r' % ch)
            out.append(EN_CODES[ch])
        tok = m.group(1)
        if tok.startswith('$'):
            out.append(int(tok[1:], 16))
        else:
            parts = tok.split(':')
            name, args = parts[0], parts[1:]
            if name not in codec.REV_CONTROL:
                raise ValueError('unknown token <%s>' % tok)
            code = codec.REV_CONTROL[name]
            want = arity.get(code, 0)
            if len(args) != want:
                raise ValueError('<%s> takes %d argument(s), got %d'
                                 % (name, want, len(args)))
            out.append(code)
            out.extend(int(x, 16) for x in args)
        pos = m.end()
    for ch in text[pos:]:
        if ch not in EN_CODES:
            raise ValueError('no glyph for %r' % ch)
        out.append(EN_CODES[ch])
    return bytes(out)


def bank_of(off):
    return off // BANKSZ


def cpu_addr(off):
    b = bank_of(off)
    return off % BANKSZ + (0x4000 if b else 0)


# ---------------------------------------------------------------- free space
def cpu_loc(off):
    """File offset -> the `bank:$addr` form translations and dte_ok.tsv are keyed on."""
    return '%d:$%04X' % (bank_of(off), cpu_addr(off))


def free_runs(extents):
    """Space we may write into, given the extents relocatable strings VACATE.

    Conservative on purpose. An earlier version treated everything in the bank's arena
    that was not a fixed string as free, which silently overwrote the pointer tables
    interleaved with the text -- 218 references then resolved to garbage. Only bytes
    that currently hold a relocatable string may be reused; code, tables and fixed
    strings are never touched.

    extents: [(start, end)] -> merged [(start, length)]
    """
    merged = []
    for s, e in sorted(extents):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e - s) for s, e in merged]


def load_reloc_ok(path=None):
    """-> {(kind, key): site} from script/reloc_ok.tsv. See that file's header.

    `key` is a table's file offset, or the string `target:<bank>` for the message-queue
    rule that covers every `imm` reference into a bank. Declared rather than inferred, for
    the same reason box_alias.tsv is: this decides whether a string's bytes may be replaced
    by a record, and getting it wrong shows up as two stray glyphs that no check can see.
    """
    path = path or os.path.join('script', 'reloc_ok.tsv')
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if not line:
            continue
        f = line.split('\t')
        if len(f) < 3:
            raise SystemExit('reloc_ok.tsv: expected "kind<TAB>key<TAB>site", got %r' % line)
        kind, key, site = f[0].strip(), f[1].strip(), f[2].strip()
        if not key.startswith('target:'):
            bank, addr = key.split(':')
            key = int(bank) * BANKSZ + (int(addr.lstrip('$'), 16) - BANKSZ)
        out[(kind, key)] = site
    return out


def ref_key(r, ref):
    """The attribution key for one reference: its table, or the bank it points into."""
    return ('table', ref['table']) if ref['kind'] == 'table' \
        else ('imm', 'target:%d' % r['bank'])


def load_box_aliases(path=None):
    """-> {box id: box id it renders instead}. See script/box_alias.tsv.

    Deliberately a declared list rather than anything inferred. Freeing a block because
    it LOOKS unreferenced is how --use-filler ate live data; freeing one because a line
    here says which box now renders it is a claim someone made and can be checked on
    screen.
    """
    path = path or os.path.join('script', 'box_alias.tsv')
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if not line:
            continue
        f = line.split('\t')
        if len(f) < 2:
            raise SystemExit('box_alias.tsv: expected "box<TAB>renders", got %r' % line)
        src, dst = int(f[0]), int(f[1])
        if src == dst:
            raise SystemExit('box_alias.tsv: box %d aliases itself' % src)
        out[src] = dst
    # An alias whose target is itself aliased would repoint at freed bytes.
    for src, dst in out.items():
        if dst in out:
            raise SystemExit('box_alias.tsv: box %d renders box %d, which is itself '
                             'aliased to %d -- chained aliases are not supported'
                             % (src, dst, out[dst]))
    return out


def filler_runs(rom, bank, strings, min_run=16):
    """Padding inside a bank that no known string occupies.

    OPT-IN (--use-filler) and deliberately so. A long run of $00 is usually padding
    between structures, but it can also be legitimate data -- a table of zeroes, or code
    that happens to be sparse. The reference verification only proves STRINGS still read
    correctly; it cannot tell you that you clobbered something else. Anything built with
    this needs play-testing, not just a green build.
    """
    lo, hi = bank * BANKSZ, (bank + 1) * BANKSZ
    used = bytearray(BANKSZ)
    for r in strings:
        if r['bank'] != bank:
            continue
        s = r['offset'] - lo
        for i in range(max(0, s), min(BANKSZ, s + r['bytes'] + 1)):
            used[i] = 1
    out, i = [], 0
    while i < BANKSZ:
        if not used[i] and rom[lo + i] in (0x00, 0xFF):
            j = i
            while j < BANKSZ and not used[j] and rom[lo + j] == rom[lo + i]:
                j += 1
            if j - i >= min_run:
                out.append((lo + i, j - i))
            i = j
        else:
            i += 1
    return out


def alloc(runs, size, best=False):
    """Carve `size` bytes out of one run. -> (offset, remaining_runs) or (None, runs).

    First-fit by default, which for a bank whose strings are repacked in address order
    hands each string back roughly the space it came from. `best` picks the tightest run
    instead, so a large unit that must stay contiguous still has a big run left to go in.
    """
    fits = [i for i, (_, length) in enumerate(runs) if length >= size]
    if not fits:
        return None, runs
    i = min(fits, key=lambda j: runs[j][1]) if best else fits[0]
    start, length = runs[i]
    out = list(runs)
    if length == size:
        out.pop(i)
    else:
        out[i] = (start + size, length - size)
    return start, out


def alloc_at(runs, at, size):
    """Remove [at, at+size) from `runs`. -> remaining runs.

    `alloc` picks WHERE to place; this records a placement that has already been decided,
    which is what lets the report replay a finished plan and say what contiguous space
    survived it. Splitting rather than truncating matters: a unit placed by best-fit can
    land in the middle of a run and leave usable space on both sides.
    """
    out = []
    for start, length in runs:
        end, cut = start + length, at + size
        if cut <= start or at >= end:
            out.append((start, length))
            continue
        if at > start:
            out.append((start, at - start))
        if cut < end:
            out.append((cut, end - cut))
    return out


# ---------------------------------------------------------------- main
def main():
    a = sys.argv[1:]
    rom_path, tsv_path, out_path = a[0], a[1], a[2]
    report_path = a[a.index('--report') + 1] if '--report' in a else None
    use_filler = '--use-filler' in a
    no_hooks = '--no-hooks' in a
    # The redirect is what makes an in-place string's length stop mattering; --no-pool is
    # for bisecting against a build that still has the old per-string budget.
    no_pool = '--no-pool' in a or no_hooks
    # `--no-reloc` keeps the trampolines but redirects no relocatable string, which is the
    # bisect that separates "the hook broke something" from "a redirected string broke
    # something". Both halves are worth being able to test alone.
    no_reloc = '--no-reloc' in a or no_pool
    # `--shuffle` packs each bank size-descending instead of address-order-first. It changes
    # nothing about WHAT is in the ROM, only WHERE -- so a build that works and a --shuffle
    # build that does not means the bank depends on an address no reference scan can see.
    # Bank 11 does: --shuffle hangs it on 4 of 4 seeds in the message state machine's
    # invalid-state trap at 0:$2337, with the relocatable redirect entirely disabled. Keep
    # this flag: it is the one-command repro, and the same test on any other bank is the
    # cheapest way to find out whether that bank's text may be moved at all.
    shuffle = '--shuffle' in a
    # See the redirect loop below: this builds the endgame's redirect load today.
    redirect_all = '--redirect-all' in a
    # The 6-character player name changes the SAVE RECORD's layout, so `--no-name6` is the
    # control for "did the name change break this, or the script?" -- and it is the build
    # to make if a save written by the old layout has to be read again.
    no_name6 = '--no-name6' in a
    # The rankings board stores its own name, in a 10-byte record that has no room for six
    # characters. `--no-rank6` is its bisect control. It is IMPLIED by `--no-name6`: the
    # board's name is read from the packed buffer at `$D0FD`, which only holds six bytes in
    # a name6 build.
    no_rank6 = '--no-rank6' in a or no_name6
    # The frozen name glossary, loaded alongside en.tsv. `--no-glossary` is its bisect
    # control: it is 391 strings landing at once, so "did the glossary break this?" has
    # to be answerable in one flag.
    no_glossary = '--no-glossary' in a
    glossary_path = (a[a.index('--glossary') + 1] if '--glossary' in a
                     else os.path.join('script', 'glossary.tsv'))
    # The approved proportional composer is selected by the historical --dot-font flag;
    # build.sh
    # passes that flag for the default ROM. Omitting it keeps the measured uniform-6px
    # control available. Dot production stages 30 glyphs; that diagnostic stages 24.
    dot_font = '--dot-font' in a
    # `--no-vwf` remains the fixed-width control.  A Dot + no-vwf build is permitted as a
    # raw 8px visual control, with the same known line-spill caveat as every no-vwf build.
    no_vwf = '--no-vwf' in a
    # The MENU renderer's VWF (bank 31's box drawer).  The uniform build consumes vwf's
    # four-shift table; the Dot build consumes propvwf's approved widths and eight-shift
    # table.  Both depend on their dialogue renderer being installed, so --no-vwf still
    # implies the raw menu control.
    no_menuvwf = '--no-menuvwf' in a or no_vwf
    # Composite rows whose dynamic fields must remain at absolute cells. This layer needs
    # the Dot menu font and is separately switchable for a pixel-exact V3 control.
    no_structvwf = '--no-structvwf' in a or no_menuvwf or not dot_font
    # The rankings list has a separate bank-31 writer and six-cell pool.  It depends on
    # the proportional menu primitives, so the raw menu control also disables it.
    no_rankvwf = '--no-rankvwf' in a or no_menuvwf or not dot_font
    # The cinematic is a separate VM and source TSV.  It is proportional only in a Dot
    # build; non-Dot diagnostic builds retain the measured Japanese control path.
    no_intro = '--no-intro' in a or not dot_font
    intro_path = (a[a.index('--intro-tsv') + 1] if '--intro-tsv' in a
                  else os.path.join('script', 'intro.tsv'))
    # The village marker shares intro's deliberately reserved bank 63.  Keeping the two
    # controls coupled means --no-intro remains a true control with no hidden bank owner.
    no_markers = '--no-markers' in a or no_intro
    # The dated black title card shares the final tail of that same graphics bank.  Its
    # independent flag makes native/English boot-card comparisons reproducible.
    no_titlecard = '--no-titlecard' in a or no_markers
    # The illustrated title is dispatched by the title-card decompression wrapper but
    # owns a separate bank and remains independently bisectable.
    no_titlelogo = '--no-titlelogo' in a or no_titlecard
    # The active-dungeon Continue screen owns an independent uncompressed tile/map block.
    # It needs the approved font but no other graphics module, and remains bisectable.
    no_waitcard = '--no-waitcard' in a or not dot_font
    # Ending credits use frozen approved Poppins strips in their own expanded bank while
    # retaining the native forest, music and transition. Keep a direct native control.
    no_endingcredits = '--no-endingcredits' in a or not dot_font

    rom = open(rom_path, 'rb').read()
    manifest = json.load(open('script/script.json', encoding='utf-8'))
    strings = manifest['strings']

    # ---- box aliases: one box renders another's text, and its own block is freed
    #
    # Applied before anything else looks at `strings`, so an aliased box's rows simply do
    # not exist for the rest of the build: they are not translated, not placed, not
    # verified, and the bytes they used to occupy are handed to the bank's free pool as a
    # DECLARED region -- justified in script/box_alias.tsv, not guessed by scanning for
    # padding the way --use-filler does.
    #
    # Their references are not dropped, they are redirected: a reference to the aliased
    # box's row N becomes a reference to the target's row N, which covers the descriptor's
    # text pointer (row 0) and any code that points into the block. See alias_refs below.
    aliases = load_box_aliases()
    alias_free = collections.defaultdict(list)   # bank -> [(start, end)] declared free
    alias_refs = []                              # (target box, row, operand file offset)
    alias_notes = []
    if aliases:
        rows_by_box = collections.defaultdict(list)
        for r in strings:
            if r.get('box'):
                rows_by_box[r['box']['id']].append(r)
        for g in rows_by_box.values():
            g.sort(key=lambda r: r['box']['row'])
        dropped = set()
        for src, dst in sorted(aliases.items()):
            g, tgt = rows_by_box.get(src), rows_by_box.get(dst)
            if not g or not tgt:
                raise SystemExit('box_alias.tsv: box %d or %d has no rows' % (src, dst))
            if len(tgt) < len(g):
                raise SystemExit(
                    'box_alias.tsv: box %d has %d rows but box %d only %d, so a row would '
                    'have nothing to point at' % (src, len(g), dst, len(tgt)))
            last = g[-1]
            start = g[0]['offset']
            end = last['offset'] + last['bytes'] + (1 if last['box']['term'] else 0)
            alias_free[g[0]['bank']].append((start, end))
            for r in g:
                dropped.add(r['id'])
                for ref in r['refs']:
                    alias_refs.append((dst, r['box']['row'], ref['operand_at']))
            alias_notes.append(
                'box %d now renders box %d; %s-%s (%d bytes) declared free'
                % (src, dst, cpu_loc(start), cpu_loc(end - 1), end - start))
        strings = [r for r in strings if r['id'] not in dropped]

    by_id = {r['id']: r for r in strings}

    # Translations are keyed on `loc` (bank:$addr), NOT on the sequential id.
    # ids are assigned by sorted offset, so any improvement to extraction renumbers
    # every string -- which silently shifted a whole translation file by one entry
    # before this was caught. `loc` is stable as long as the source ROM is.
    by_loc = {r['loc']: r for r in strings}
    trans, unknown = {}, []

    def read_translations(path, columns):
        """Fold one TSV of translations into `trans`. `columns` is how many fields the
        file has; the English is always the last one. Later files win, which is why the
        glossary is read FIRST -- an entry in en.tsv is a deliberate override of a frozen
        name, and a build that silently preferred the glossary would make that edit look
        like it did nothing."""
        for line in open(path, encoding='utf-8'):
            # Tolerant of a spreadsheet export -- Joey reviews the glossary in Numbers,
            # which pads every line out to the widest row and quotes any line holding a
            # comma. See lint_en.spreadsheet_line for exactly what is absorbed and why
            # nothing in the DATA fields is.
            line = lint_en.spreadsheet_line(line)
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t', columns - 1)
            if len(parts) < columns:
                continue
            key, en = parts[0].strip(), parts[-1]
            if not en.strip():
                continue
            if key.isdigit():
                raise SystemExit(
                    "translations must be keyed on loc (e.g. 11:$5330), not id -- "
                    "ids are not stable across extractions. Offending line: %r" % line)
            r = by_loc.get(key)
            if r is None:
                unknown.append(key)
                continue
            trans[r['id']] = en

    # The frozen glossary: 391 item, monster and NPC names, `loc class jp en`. It is a
    # separate file from en.tsv because it is a CONSTRAINT on every later batch and not
    # just another batch -- lint_en.py reads the jp column to check that prose which
    # names a monster names it the frozen way. `--no-glossary` is the bisect control.
    if not no_glossary and os.path.exists(glossary_path):
        read_translations(glossary_path, 4)
        print("glossary          : %d name(s) from %s" % (len(trans), glossary_path))
    read_translations(tsv_path, 2)
    if unknown:
        print("WARNING: %d translation key(s) match no string: %s"
              % (len(unknown), ' '.join(unknown[:6])))

    approved_font = dotfont.load_approved() if dot_font else None
    buf = bytearray(approved_font.patch(rom) if dot_font else patch_font(rom))
    problems, notes = [], []
    if dot_font:
        notes.append('--dot-font: approved %s glyphs installed; proportional composer '
                     'enabled' % approved_font.name)

    if bytes(buf[PATH_PADDING_AT:PATH_PADDING_AT + len(PATH_PADDING_OLD)]) != PATH_PADDING_OLD:
        raise SystemExit('Path status padding table at 4:$4FE6 changed; expected %s'
                         % PATH_PADDING_OLD.hex(' '))
    buf[PATH_PADDING_AT:PATH_PADDING_AT + len(PATH_PADDING_NEW)] = PATH_PADDING_NEW
    notes.append('Path status values Easy/Normal/Hard right-aligned at column 18 '
                 '(4:$4FE6 padding 6/4/6)')

    def renderer_layout(text):
        """Preserve fixed cursor cells without changing the reviewed TSV text.

        Dialogue selectors use ``$81`` in the first row and one blank source cell before
        every unselected continuation row.  In the native renderer that cell is 8px;
        Dot's proportional word space is 4px.  Compile those structural blanks as two
        ordinary spaces so the game's 8px cursor cannot overwrite the first glyph.
        """
        if '<$81>' in text:
            return text.replace('<br> ', '<br>  ')
        return text

    selector_continuations = sum(
        text.count('<br> ') for text in trans.values() if '<$81>' in text)
    notes.append('dialogue selectors: %d continuation row(s) retain an 8px cursor cell '
                 'without changing TSV text' % selector_continuations)

    # ---- decide the final bytes for every string
    final = {}
    for r in strings:
        orig = bytes.fromhex(r['hex'])
        en = trans.get(r['id'])
        if en is None:
            final[r['id']] = orig            # untranslated: keep the Japanese
            continue
        # Form is what encode_en checks; CONTENT is what lint_en checks. A translation
        # that drops `<var>` encodes cleanly, inserts cleanly, and passes every reference
        # check and crash seed -- and then prints "The  attacked!" at runtime. That is the
        # one failure in this pipeline with no other detector, and it is exactly the kind
        # a model produces in bulk, because the token carries no meaning in the sentence
        # it is rewriting. See tools/lint_en.py for what counts as significant and why
        # `<br>`/`<brk>`/`<end>`/`<$XX>` deliberately do not.
        lost = lint_en.check_one(r['jp'], en, r['bank'])
        if lost:
            for kind, detail in lost:
                problems.append((r, kind, detail))
            final[r['id']] = orig
            continue
        lead = orig[:1] == bytes([EN_CODES[' ']])
        try:
            data = encode_en((' ' if lead else '') + renderer_layout(en), r['bank'])
        except ValueError as exc:
            problems.append((r, 'encode', str(exc)))
            final[r['id']] = orig
            continue
        # A `<$XX>` escape names a byte the renderer must reproduce EXACTLY -- it is
        # layout, not text. If it lands in the DTE code space an expanding loop will
        # expand it: 31:$41E9's `<$B6>` column divider drew two cells where the row
        # budgeted one, which overran the box, skipped the terminator, misaligned every
        # following row and left the status screen white. Only an escape can trip this,
        # because dte_rom._check_ranges already proves no EN_CODES letter can.
        clash = sorted(set(data) & set(dte_rom.DTE_CODES))
        if clash:
            problems.append((r, 'escape_is_dte_code',
                             'raw escape %s is in the DTE code space, so a renderer that '
                             'expands would draw it as a pair. Reserve the byte in '
                             'dte_rom.DTE_RANGES or use a glyph outside it'
                             % ' '.join('<$%02X>' % c for c in clash)))
            final[r['id']] = orig
            continue
        final[r['id']] = data

    # ---- menu boxes are placed as a UNIT
    # 31:$4075 walks a box's rows sequentially -- row 1 is simply whatever follows row 0's
    # terminator. Relocating row 0 on its own therefore strands the rest of the box at the
    # old address, which is the same all-or-nothing hazard as a half-relocated bank.
    #
    # Computed before the DTE block because compressing a box row is only safe when the
    # box MOVES -- see the eligibility rule below.
    box_groups = collections.defaultdict(list)
    for r in strings:
        if r.get('box'):
            box_groups[r['box']['id']].append(r)
    for g in box_groups.values():
        g.sort(key=lambda r: r['box']['row'])
    moving_boxes = {bid: g for bid, g in box_groups.items() if not g[0]['box']['pinned']}
    moving_ids = {r['id'] for g in moving_boxes.values() for r in g}

    # ---- which boxes may have their text EXPANDED at all
    #
    # dte_box expands only when bit 7 of the descriptor's flags byte is set, because the
    # drawer's source is not always ours to vet: the file-select box draws the player's
    # saved name straight out of SRAM, and those bytes are whatever they typed. So a box
    # qualifies only when every one of its rows is translated English -- the condition
    # under which every DTE-range byte in it is one this build put there -- and never
    # when its text is staged in WRAM, where the bytes come from somewhere else entirely.
    # Box 12 is another deliberate exception: the drawer could expand it, but the name
    # picker reads the selected ROM byte directly at 31:$41B0. Compressing a visible pair
    # there would make A select a DTE code rather than the character the player sees.
    boxes_by_id = {b['id']: b for b in manifest.get('boxes', [])}
    markable = {bid for bid, g in box_groups.items()
                if bid != GRID_BOX
                and not boxes_by_id[bid]['wram']
                and all(r['id'] in trans and final[r['id']] != bytes.fromhex(r['hex'])
                        for r in g)}

    # ---- DTE: compress what the expander can actually reach
    #
    # `plain` is what the RENDERER will produce and `final` is what goes in the ROM. They
    # stop being the same thing here, and the distinction is load-bearing: every byte
    # budget below has to measure `final`, and every CELL budget has to measure `plain`,
    # because one compressed byte draws several cells.
    #
    # A string is eligible only if a trace has SEEN an expanding loop read it
    # (script/dte_ok.tsv, generated by `gbrun.py --dte-scan`). Guessing this per bank was
    # tried and was wrong: bank 11's menu labels are copied by 11:$52D5, which never
    # reaches the expander, so they rendered as raw katakana. An empty allowlist means no
    # compression -- which costs space, where a wrong one costs correctness.
    #
    # A BOX ROW has to clear two more gates. Its box must be MARKABLE, or the drawer will
    # never expand it (see `markable` above). And its box must RELOCATE: a pinned row is
    # written by put(), which pads it with spaces back out to its original byte length --
    # and 31:$40D8 draws those spaces as cells ON TOP of the ones the expansion already
    # drew, so the row overruns the box width, the drawer never reaches the terminator,
    # and every row after it shifts. Compression buys a pinned row nothing regardless,
    # since the padding refills exactly the bytes it saved.
    plain = dict(final)
    dte_table, dte_stats = [], None
    dte_allow = dte_rom.load_allowlist()
    runtime_offsets = {r['offset'] for r in strings if r.get('runtime_entry')}
    runtime_parents = {
        r['id'] for r in strings
        if any(r['offset'] < entry < r['offset'] + r['bytes']
               for entry in runtime_offsets)
    }
    if '--no-dte' not in a:
        eligible = [r for r in strings
                    if r['id'] in trans
                    # A runtime interior start and its overlapping parent are two
                    # independently addressable views of the same original bytes.  Both
                    # are pool-redirected below, but the rescued-child route proved that
                    # the interior redirect path does not preserve DTE expansion.  Keep
                    # these few records literal: observation proves that the stager sees
                    # them, not that every pool-entry path reaches the expander.
                    and not r.get('runtime_entry')
                    and r['id'] not in runtime_parents
                    and (not r.get('box') or (r['id'] in moving_ids
                                              and r['box']['id'] in markable))
                    # The proportional menu renderer reads this small approved set
                    # directly from bank 31 through a nested far call.  Keep those rows
                    # literal: duplicating the recursive DTE expander in the final 371
                    # bytes of bank 32 would spend code to save only a handful of bank-31
                    # bytes, while literal rows remain readable by both render paths.
                    and not (dot_font and r.get('box')
                             and r['box']['id'] in menuvwf.ROM_BOXES)
                    and r['loc'] in dte_allow
                    and final[r['id']] != bytes.fromhex(r['hex'])]
        # Repeat a tight bank's strings so the table spends its codes where space is
        # scarce -- see dte_rom.TRAIN_WEIGHT for the measurement.
        segs = []
        for r in eligible:
            w = dte_rom.TRAIN_WEIGHT.get(r['bank'], dte_rom.DEFAULT_WEIGHT)
            segs += dte_rom.training_segments(final[r['id']]) * w
        # Train on the SNES English corpus AS WELL as our own text. Yield scales with the
        # TABLE's corpus, not with the text being compressed -- which is why the measured
        # 40.7% transfers -- and without it there is a chicken-and-egg: two translated
        # labels are 19 bytes, too little for any pair to repeat, so nothing compresses
        # until most of the script is already written and would need re-fitting.
        corpus = dte_rom.training_corpus()
        if segs or corpus:
            dte_table, _, dte_stats = dte_rom.encode_segments(corpus + segs)
            saved = 0
            for r in eligible:
                packed = dte_rom.compress(final[r['id']], dte_table)
                # round-trip every string, not just the corpus: compress() has to agree
                # with the expander for text the table was not trained on too
                back = dte_rom.expand_bytes(packed, dte_table)
                if back != final[r['id']]:
                    problems.append((r, 'dte_roundtrip',
                                     'compressed form does not expand back'))
                    continue
                saved += len(final[r['id']]) - len(packed)
                final[r['id']] = packed
            dte_stats['saved'] = saved
            dte_stats['strings'] = len(eligible)

        # ---- no UNTRANSLATED string may contain a DTE code byte
        #
        # The composer expands unconditionally: it has no gate, unlike the box drawer, so a
        # Japanese byte that lands in the code space is expanded into two. This was carried
        # for weeks as "the accepted cost" on the argument that Japanese renders as garbage
        # anyway -- and the argument was wrong. Expansion changes CELL counts, cell counts
        # drive wrapping, and the dungeon's self-dismissing messages came and went too fast
        # to read. A screenshot cannot see a duration; Joey found it by playing, and an A/B
        # against --no-dte confirmed it.
        #
        # So the code space is measured against the real script (see dte_rom.DTE_RANGES and
        # tools/dte_ranges.py) and this makes it stay measured. It is an error, not a
        # warning: the failure mode is a bug nobody can see in a screenshot.
        codes = set(dte_rom.DTE_CODES)
        hit = []
        for r in strings:
            if final[r['id']] != bytes.fromhex(r['hex']):
                continue                     # translated, or compressed on purpose
            bad = sorted(set(final[r['id']]) & codes)
            if bad:
                hit.append((r['loc'], bad))
        if hit:
            listed = '; '.join('%s uses %s' % (loc, ' '.join('$%02X' % b for b in bad[:4]))
                               for loc, bad in hit[:5])
            raise SystemExit(
                '%d untranslated string(s) contain a byte in the DTE code space, so the '
                'composer will expand them and change their cell counts: %s%s\n'
                'Run tools/dte_ranges.py and narrow dte_rom.DTE_RANGES, or translate those '
                'strings. This is what made dungeon messages expire too fast to read.'
                % (len(hit), listed, ' ...' if len(hit) > 5 else ''))
        notes.append('no untranslated string collides with the %d-code DTE space '
                     '(%s) -- the composer cannot expand Japanese'
                     % (len(codes), ' '.join('$%02X-$%02X' % r for r in dte_rom.DTE_RANGES)))

    # The grid is a dual-reader structure: the box drawer renders its bytes and the picker
    # returns one raw byte as the chosen character. Keep this as a separate assertion from
    # markable's eligibility rule so a future DTE refactor cannot silently break selection.
    if any(final[r['id']] != plain[r['id']] for r in box_groups.get(GRID_BOX, ())):
        raise SystemExit('box %d name-entry rows were DTE-compressed, but the character '
                         'picker reads their raw bytes' % GRID_BOX)

    # Mark only the boxes that actually ended up holding a compressed row. Marking every
    # markable box would work -- translated English contains no DTE-range byte, so the
    # expander would be a no-op on it -- but a bit that is set only where it is needed is
    # a bit whose meaning can be read off the ROM.
    marked = sorted(bid for bid in markable
                    if any(final[r['id']] != plain[r['id']] for r in box_groups[bid]))
    for bid in marked:
        desc = boxes_by_id[bid]['desc']
        buf[desc + 4] |= dte_rom.BOX_FLAG_BIT
    if marked:
        notes.append('box %s marked compressed (descriptor flags bit 7)'
                     % ' '.join(str(b) for b in marked))

    # ---- menu box geometry
    # Width and position are bytes 0, 1 and 3 of the descriptor, so a box that is too
    # narrow for English is a data edit, not a render-path rewrite. The drawer occupies
    # x .. x+width+1 (the two border columns are outside `width`) and y .. y+rows+1.
    #
    # NOTHING HERE IS CHECKED BY THE REFERENCE VERIFIER. It proves the text fits the
    # declared width and the box fits the screen; it cannot tell you the box overlaps
    # something else's text or sits two columns off. Screenshot every box you touch.
    SCREEN_W, SCREEN_H = 20, 18
    boxes_by_id = {b['id']: b for b in manifest.get('boxes', [])}

    # The selection cursor is placed by bank 4, NOT by the box drawer, and it carries its
    # own position -- which is why moving a box used to leave the cursor behind:
    #
    #   4:$4E2B   menu id in $C6A3 -> table at 4:$4E6E, 2 bytes per entry
    #             -> $C6A7/$C6A8 = cursor home, a 16-bit offset into the $C300 tilemap
    #   4:$4F2B   hl = home + selection*64 + $C300 ; ld [hl],$81
    #
    # A box's home is (y+1)*32 + (x+1): one row down and one column in from its corner,
    # i.e. the cursor slot. So moving a box means adding the same delta to every table
    # entry that pointed at its old home. Several menus share an entry value (the item
    # action menu has three, one per category set) and they all have to move together.
    CURSOR_TABLE = 4 * BANKSZ + (0x4E6E - 0x4000)

    def cursor_home(x, y):
        return (y + 1) * SCREEN_W_STRIDE + (x + 1)

    SCREEN_W_STRIDE = 32          # the shadow tilemap is 32 bytes per row, not 20

    def cursor_entries():
        """-> [(offset, value)] for the table, stopping at the first non-screen offset."""
        out = []
        for k in range(64):
            o = CURSOR_TABLE + k * 2
            v = buf[o] | (buf[o + 1] << 8)
            r, c = divmod(v, SCREEN_W_STRIDE)
            if not (0 <= r < SCREEN_H and 0 <= c < SCREEN_W):
                break
            out.append((o, v))
        return out

    geom_path = os.path.join('script', 'box_geometry.tsv')
    if os.path.exists(geom_path):
        for line in open(geom_path, encoding='utf-8'):
            line = line.split('#')[0].strip()
            if not line:
                continue
            f = line.split()
            bid, x, y, w = (int(v, 0) for v in f[:4])
            # A display box -- a header or a message -- has no selection cursor, so there is
            # no table entry to move and no ambiguity to resolve. Say so explicitly rather
            # than letting the check be skipped by accident.
            no_cursor = 'nocursor' in f[4:]
            box = boxes_by_id.get(bid)
            if box is None:
                raise SystemExit("box_geometry.tsv: box %d is not in the table" % bid)
            if x + w + 2 > SCREEN_W:
                raise SystemExit("box_geometry.tsv: box %d ends at column %d, screen is %d"
                                 % (bid, x + w + 2, SCREEN_W))
            if y + box['rows'] + 2 > SCREEN_H:
                raise SystemExit("box_geometry.tsv: box %d ends at row %d, screen is %d"
                                 % (bid, y + box['rows'] + 2, SCREEN_H))
            # Move the cursor with the box. Refuse rather than guess when another box shares
            # the same home: the entries are keyed on position, so two boxes at the same
            # corner are indistinguishable here and moving one would drag the other's cursor.
            if (x, y) != (box['x'], box['y']) and not no_cursor:
                old, new = cursor_home(box['x'], box['y']), cursor_home(x, y)
                sharers = [o['id'] for o in boxes_by_id.values() if o['id'] != bid
                           and cursor_home(o['x'], o['y']) == old]
                hits = [o for o, v in cursor_entries() if v == old]
                if sharers:
                    raise SystemExit(
                        "box_geometry.tsv: box %d shares its cursor home $%04X with box(es) "
                        "%s, so the cursor entries cannot be attributed. Moving it needs the "
                        "right entry identified by hand." % (bid, old, sharers))
                if not hits:
                    raise SystemExit(
                        "box_geometry.tsv: box %d has no cursor entry at its home $%04X. "
                        "Either it has no selection cursor -- in which case say so here -- or "
                        "the home is computed differently for it." % (bid, old))
                for o in hits:
                    buf[o], buf[o + 1] = new & 0xFF, new >> 8
                notes.append("box %2d cursor: home $%04X -> $%04X (%d table entr%s at 4:%s)"
                             % (bid, old, new, len(hits), 'y' if len(hits) == 1 else 'ies',
                                ' '.join('$%04X' % (0x4000 + (o % BANKSZ)) for o in hits)))
            desc = box['desc']
            buf[desc], buf[desc + 1], buf[desc + 3] = x, y, w
            for r in box_groups.get(bid, []):
                r['box'].update(x=x, y=y, width=w)
            notes.append("box %2d geometry: columns %d-%d, rows %d-%d, %d text cells%s"
                         % (bid, x, x + w + 1, y, y + box['rows'] + 1, w,
                            "  (text staged in WRAM)" if box['wram'] else ""))

    # ---- every extracted box row must fit its measured source scanner
    # Native rows stop at descriptor width. V4C's explicitly marked narrow proportional
    # ROM rows instead scan their terminator under the measured 18-glyph contract, then
    # independently measure Dot pixels and deterministic tiles in menuvwf/fontaudit.
    # This is a source-path guard, not a claim that each character is eight pixels.
    # Measured on `plain`, not `final`: the drawer counts the cells it DRAWS, so a
    # compressed byte spends as many as it expands to.
    for bid, g in sorted(box_groups.items()):
        for r in g:
            w = r['box']['width']
            source_cap = (menuvwf.ROM_SOURCE_CAP
                          if (dot_font and not no_menuvwf and
                              bid in menuvwf.ROM_LONG_SOURCE_BOXES) else w)
            if cells(plain[r['id']], r['bank']) > source_cap:
                problems.append((r, 'box_too_wide',
                                 'box %d row %d stages %d glyph cells, its measured '
                                 'source scanner accepts %d'
                                 % (bid, r['box']['row'],
                                    cells(plain[r['id']], r['bank']), source_cap)))
                final[r['id']] = plain[r['id']] = bytes.fromhex(r['hex'])

    # ---- every dialogue LINE must fit its source staging and physical canvas
    #
    # The dialogue equivalent of box_too_wide. The old 18-cell and 24-glyph renderers
    # silently discarded overflow; current Dot production independently rejects more than
    # 30 staged glyphs or ink beyond 144px. The TASK 4 innkeeper speech once lost a
    # character off five lines because no equivalent check existed.
    #
    # Measured on `plain` for the same reason box_too_wide is: the renderer counts what it
    # DRAWS, and a compressed byte draws as many cells as it expands to. Unknown
    # substitutions are charged their non-empty floor. The player name is a known
    # six-character input contract and is charged its real maximum.
    #
    # Dot dialogue now stages up to 30 glyphs and help/seals up to 21, while both still
    # paint into 144px. Diagnostic uniform/native builds retain their 24/18 and 18/18
    # source contracts. `check` enforces both source glyphs and painted Dot extent.
    cf0_cells, _ = dialogue.cf0_from_trans(
        {r['loc']: trans[r['id']] for r in strings if r['id'] in trans}, encode_en)
    rows_by_loc = {r['loc']: r for r in strings}
    cf0_data = {index: plain[rows_by_loc[loc]['id']]
                for index, loc in enumerate(dialogue.CF0_LOCS)
                if loc in rows_by_loc}
    dot_production_px = (dialogue.dot_production_widths(approved_font)
                         if dot_font else None)
    dot_help_px = (dialogue.dot_help_widths(approved_font, cf0_data)
                   if dot_font else None)
    tight = []
    for r in strings:
        if r['id'] not in trans or not dialogue.is_dialogue(r):
            continue
        width, per_box, stage = dialogue.geometry_for(
            r, proportional=dot_font, vwf=not no_vwf)
        help_ = dialogue.is_help(r)
        widths = (dialogue.help_widths(cf0=cf0_cells) if help_
                  else dialogue.production_widths())
        for kind, msg in dialogue.check(plain[r['id']], width=width, per_box=per_box,
                                        buf=stage, widths=widths,
                                        buf_scope='box' if help_ else 'line', bank=r['bank'],
                                        font=approved_font if dot_font else None,
                                        pixel_widths=(dot_help_px if help_
                                                      else dot_production_px)):
            problems.append((r, kind, msg))
            final[r['id']] = plain[r['id']] = bytes.fromhex(r['hex'])
        for box, row, left, toks in dialogue.headroom(plain[r['id']], width=width):
            if left < dialogue.NAME_CAP:
                tight.append((left, r['loc'], box, row, toks))
    if tight:
        # A warning, never a failure: what goes into a `<var>` is a runtime value, and the
        # Japanese leaves as little as 4 source cells for a monster name itself. NAME_CAP
        # is retained only as the legacy review threshold while the Dot producer census is
        # open; this warning must not be read as a physical name limit.
        tight.sort()
        notes.append('%d translated line(s) cross the legacy %d-source-character '
                     'substitution reservation (runtime/pixel census still open); '
                     'tightest: %s' % (len(tight), dialogue.NAME_CAP,
                                       ', '.join('%s box %d line %d = %d for %s'
                                                 % (l, b, rw, c, t)
                                                 for c, l, b, rw, t in tight[:3])))

    # ---- in-place strings must fit their original cell budget
    #
    # `pin` means extraction found something that LOOKS like a reference to this string in
    # a bank it cannot vouch for, and could not prove it either way. Such a string keeps
    # its address: relocating it would be safe only if the suspect load is not a
    # reference, and that is exactly the assumption that crashed the game on every death
    # when 240 real cross-bank message-queue pushes were being discarded. In place is
    # always correct; relocating on an unproven premise is not.
    # A runtime-observed interior entry makes its containing parent address-sensitive even
    # when the parent has a normal table reference.  Repacking the parent strands the
    # interior event pointer; writing a shorter English parent in place is just as bad,
    # because those bytes overwrite the child's redirect.  Keep both at their original
    # starts and force the parent itself through a four-byte pool record below.
    relocatable, fixed = [], []
    pinned = runtime_pinned = 0
    for r in strings:
        if r['id'] in moving_ids:
            continue                      # allocated with its box, below
        if r.get('pin') or r['id'] in runtime_parents:
            if r.get('pin'):
                pinned += 1
            else:
                runtime_pinned += 1
            fixed.append(r)
            continue
        (relocatable if r['refs'] else fixed).append(r)
    if pinned:
        notes.append('%d string(s) pinned by an unverified reference -- kept in place'
                     % pinned)
    if runtime_pinned:
        notes.append('%d parent string(s) pinned and pool-redirected to preserve '
                     'runtime-observed interior entry points' % runtime_pinned)

    # Which referenced strings may use the four-byte record.  Usually this is consumed by
    # the relocatable-bank allocator below; runtime parents are address-pinned but use the
    # same attributed table reader, so they need the decision before fixed strings are
    # written.  Keeping one definition prevents the two redirect paths drifting.
    reloc_ok = load_reloc_ok()
    hooked = {'%d:$%04X' % (b, a) for b, a, _, _, _ in textpool.RELOC_SITES}
    hooked.add('13:$40DB')
    reloc_can = set() if no_reloc else {
        r['id'] for r in strings
        if r['bank'] in {b for b, *_ in textpool.RELOC_SITES}
        and r['refs'] and not r.get('box') and not textpool.starts_ec(r)
        and all(reloc_ok.get(ref_key(r, ref)) in hooked for ref in r['refs'])}

    # A pinned box row stays put, so the row AFTER it must still begin where it did -- and
    # what fixes that is how many BYTES the drawer consumes, not how many cells it drew.
    # 31:$4567 is 20 bytes but only 16 cells, because four of them are dakuten. English has
    # no dakuten, so padding a replacement out to 20 bytes would draw 20 cells: the drawer
    # would stop at the box width of 18, never reach the terminator, and row 2 would start
    # two bytes early. There is no English string that consumes 20 bytes inside an 18-cell
    # box, so this row is simply not translatable in place.
    for r in fixed:
        box = r.get('box')
        if (box and box['row'] < box['rows'] - 1 and r['bytes'] > box['width']
                and final[r['id']] != bytes.fromhex(r['hex'])):
            problems.append((r, 'box_in_place',
                             'in-place box row: %d bytes in a %d-cell box (dakuten cost no '
                             'cell), so no English string consumes the same space and the '
                             'next row would shift' % (r['bytes'], box['width'])))
            final[r['id']] = bytes.fromhex(r['hex'])

    # The real in-place constraint is BYTES: `put` writes at the original address, so
    # anything longer than the original overwrites the string that follows. The old check
    # used cells(jp) as the budget, which is the same number for English (no dakuten) but
    # strictly tighter whenever the Japanese had any -- and it is exactly that slack DTE
    # is meant to spend. Measuring `final` in bytes is what turns the compression ratio
    # into room for this group, which cannot be repointed at all.
    #
    # A translation may now draw more cells than the Japanese did. That is cosmetic: these
    # are composer-path strings and the composer wraps at its own line budget. `widened`
    # counts them so the cost stays visible rather than implicit.
    # An overrun no longer has to mean "revert to Japanese". A dialogue string that does
    # not fit its slot is REDIRECTED: four bytes at the original address name a pool bank
    # address, and the text itself goes into the 32 KiB of empty ROM the two pool banks
    # provide. That is what turns this per-string budget into an aggregate one -- the
    # whole reason natural English did not fit. See tools/pool.py.
    #
    # A `<cEC:xx>` string keeps its two-byte prefix AT the original address and puts the
    # record after it, because the ROM re-derives the resume pointer as "the address the
    # message came from, plus 2" and would otherwise resume inside the record. See the
    # `EC_OPEN` note in tools/pool.py; `ec_head` is what `put` writes in front of the
    # record and what the verifier below prepends before reading the pool back.
    redirects, ec_head, text_pool = {}, {}, textpool.Pool()
    widened = 0
    for r in fixed:
        data = final[r['id']]
        # The Awards screen's four unreferenced tail labels are copied through the
        # runtime bank-14 stager just like dialogue, but short in-place translations were
        # historically padded back to their Japanese byte length.  That is correct for
        # sequential menu-label tables and wrong here: the proportional box-44 scanner
        # sees the padding as source glyphs, so ``Hard, no items in`` becomes 23 cells
        # and delegates the whole row to fixed width.  The overlong neighbouring labels
        # already take this pool route and arrive with an immediate terminator.  Send all
        # translated, unreferenced clear-condition rows through the same proven stager
        # redirect so the real save-backed route and the synthetic compositor fixture
        # have the identical terminated contract.
        force_award_row = (dialogue.is_clear_condition(r) and not r['refs']
                           and r['id'] in trans
                           and data != bytes.fromhex(r['hex']))
        force_runtime_view = (((r.get('runtime_entry') or r['id'] in runtime_parents)
                               and r['id'] in trans
                               and data != bytes.fromhex(r['hex']))
                              or force_award_row)
        if len(data) > r['bytes'] or force_runtime_view:
            if not no_pool and (textpool.eligible(r) or r['id'] in reloc_can
                                or r.get('runtime_entry') or r['id'] in runtime_parents):
                try:
                    # `head_bytes` raises if the translation moved its `<cEC:xx>` off the
                    # front. Reported like any other problem and the string reverts to
                    # Japanese, rather than exiting: a build that stops on the first bad
                    # string hides the other 985.
                    head = textpool.head_bytes(r, data)
                    pool_data = data[len(head):] + bytes([codec.TERMINATOR])
                    redirect = (text_pool.add_run(pool_data)
                                if textpool.needs_line_records(r)
                                else text_pool.add(pool_data))
                    # An address-pinned string cannot move, so its record run must fit
                    # inside the bytes the Japanese entry owned.  Every current help
                    # entry does; make that structural fact fail loudly if a later edit
                    # adds enough rows to violate it.
                    if len(head) + len(redirect) > r['bytes']:
                        raise SystemExit(
                            'line-preserving redirect needs %d bytes, pinned slot has %d'
                            % (len(head) + len(redirect), r['bytes']))
                    redirects[r['id']] = redirect
                    if head:
                        ec_head[r['id']] = head
                    continue
                except textpool.PrefixMoved as exc:
                    problems.append((r, 'ec_prefix_moved', str(exc)))
                except SystemExit as exc:
                    problems.append((r, 'pool_full', str(exc)))
            problems.append((r, 'too_long',
                             'in-place: needs %d bytes, budget %d%s'
                             % (len(data), r['bytes'],
                                '' if data == plain[r['id']] else
                                ' (%d before DTE)' % len(plain[r['id']]))))
            final[r['id']] = plain[r['id']] = bytes.fromhex(r['hex'])
        elif (cells(plain[r['id']], r['bank'])
              > cells(bytes.fromhex(r['hex']), r['bank'])):
            widened += 1

    # ---- write fixed strings at their original addresses
    #
    # Only write a terminator when the string SHRANK. If it kept its length the original
    # terminator is already in the right place, and writing one unconditionally corrupts
    # overlapping strings -- some pointer targets are legitimate mid-conversation entry
    # points nested inside a longer string (11:$5848 sits inside the 179-byte 11:$5803),
    # so the inner string's terminator would truncate the outer one.
    unpadded_boxes = []

    def put(r, data):
        # PAD with spaces, never terminate early. These labels are walked SEQUENTIALLY,
        # so an early terminator strands the tail of the old string as a phantom entry:
        # とうたつちてん (7 bytes) replaced by "Floor" (5) left `ん` + $FF at $41DA, which
        # the renderer then drew as the next label -- the stray "t" on the status screen.
        # The real next label was pushed to fourth place and never drawn.
        # Padding keeps every terminator where the game expects it.
        #
        # A COMPRESSED box row is the one thing that cannot be padded: 31:$40D8 pads to
        # the box width itself, so these spaces would draw as cells on top of the ones the
        # expansion already drew, the row would overrun its width, the drawer would never
        # reach the terminator and every row after it would shift. The eligibility rule
        # above keeps compressed rows out of this function; a box that turns out to
        # overlap another unit arrives here anyway, so revert it rather than trust that.
        off, orig_len = r['offset'], r['bytes']
        # A redirected string writes only its record (or, for the 13:$554A help table,
        # one record per line) and LEAVES THE REST ALONE.  Not padding is the point:
        # 11:$5848 is a legitimate mid-conversation entry point nested inside 11:$5803,
        # so anything that pointed beyond the records into the old bytes still finds
        # them. The pool is pure addition -- it never reclaims the space it frees.
        if r['id'] in redirects:
            rec = ec_head.get(r['id'], b'') + redirects[r['id']]
            buf[off:off + len(rec)] = rec
            return rec
        if r.get('box') and data != plain[r['id']] and len(data) < orig_len:
            data = plain[r['id']]
            unpadded_boxes.append(r['loc'])
        buf[off:off + len(data)] = data
        if len(data) < orig_len:
            pad = bytes([EN_CODES[' ']]) * (orig_len - len(data))
            buf[off + len(data):off + orig_len] = pad
        return data + (pad if len(data) < orig_len else b'')

    for r in fixed:
        if r['id'] in redirects:
            put(r, final[r['id']])       # writes the record; `final` stays the pool text,
            continue                     # which is what the verifier below has to find
        final[r['id']] = put(r, final[r['id']])

    # ---- repack relocatable strings, per bank
    #
    # The allocator works on UNITS, not strings: a unit is one contiguous allocation whose
    # rows are written back to back, each closed with a terminator. An ordinary string is a
    # one-row unit; a menu box is an N-row unit, which is what keeps its rows adjacent.
    placed = {}
    # Which relocatable strings MAY be redirected. Every reader that can reach a string has
    # to understand the record, so the rule is: every reference it has must belong to a
    # table (or the message-queue rule) that script/reloc_ok.tsv attributes to a site
    # tools/pool.py actually hooks. A string whose readers are not all known stays put --
    # and if that leaves its bank short, the projection says so by name.
    # NOT an `$EC` string. The in-place redirect can keep the prefix at the original
    # address and put the record after it, because `13:$7589` stages the record on the
    # NEXT pass. A relocatable redirect cannot: its trampoline tests the MARK at (hl)
    # before the loop starts, so a record two bytes in is invisible to it and the loop
    # copies `EC arg E9 lo hi FF` out as text. The two mechanisms genuinely disagree here,
    # and none of the six such strings needs the pool today -- all six fit in place.
    reloc_redirects, reloc_hooks = {}, []
    # A string counts as translated only if English actually went in -- one that was
    # reported as a problem and reverted still has its Japanese to pay for. `projected`
    # collects (bank, capacity, endgame need, done, total) for the report at the end.
    translated_ids = {r['id'] for r in strings
                      if final[r['id']] != bytes.fromhex(r['hex'])}
    projected = []
    by_bank = collections.defaultdict(list)
    for r in relocatable:
        by_bank[r['bank']].append([r])
    for bid, g in sorted(moving_boxes.items()):
        by_bank[g[0]['bank']].append(list(g))

    def needs_term(r):
        """Whether a terminator has to follow this row's bytes.

        31:$40D8 pads a short row with blanks until it has drawn `width` cells, so a short
        row must say where it ends -- but a row that FILLS the box does not, and the
        original relies on that: 31:$44F7's 12 bytes are exactly 10 cells and the next
        descriptor begins immediately after. Budgeting a terminator for such a row costs a
        byte it never had, which is what made box 41 unplaceable in a bank with 4 spare.

        Derived from the current text, not the original, so it stays right when a row
        grows into its box or is reverted to Japanese -- and from `plain` rather than
        `final`, because what fills the box is the cells the drawer DRAWS. Measuring the
        compressed bytes would call a row short when its expansion fills the box exactly,
        costing a byte the row does not have.
        """
        # V4C's narrowed proportional rows scan a terminated source independently of
        # physical width. Other ROM boxes retain the native boundary, including pinned
        # padded rows and the historical unterminated Rankings heading.
        if (dot_font and not no_menuvwf and r.get('box') and
                r['box']['id'] in menuvwf.ROM_LONG_SOURCE_BOXES):
            return True
        return not r.get('box') or cells(plain[r['id']], r['bank']) < r['box']['width']

    def span_of(unit):
        """The bytes a unit occupies in the ORIGINAL rom, terminators included.

        Uses the original `term` flag from extraction, not needs_term: this is what the
        bank is getting back, and over-claiming by one byte would donate a descriptor byte
        to the free pool -- data loss the reference verifier cannot see.
        """
        last = unit[-1]
        end = last['offset'] + last['bytes']
        if not last.get('box') or last['box']['term']:
            end += 1
        return unit[0]['offset'], end

    for bank, group in sorted(by_bank.items()):
        # Repack the whole group into the space it collectively occupies. Leaving strings
        # that still fit where they are avoids churn, but then the space freed by strings
        # that shrank comes back as scattered scraps -- bank 11 ended up with 13 strings
        # unplaceable against a largest free run of 5 bytes. Because every one of these is
        # repointed anyway, moving them all costs nothing and consolidates the space.
        #
        # Strings nested inside another (mid-conversation entry points) are NOT moved:
        # they share bytes with their parent and only make sense in situ.
        # Pin any string that OVERLAPS another, not merely those fully nested inside
        # one. A partial overlap (11:$55AC and 11:$55C6 share bytes but neither contains
        # the other) still means the two cannot be relocated independently.
        spans = sorted(span_of(u) + (i,) for i, u in enumerate(group))
        nested = set()
        for i, (s, e, u1) in enumerate(spans):
            for s2, e2, u2 in spans[i + 1:]:
                if s2 >= e:
                    break
                nested.add(u1)
                nested.add(u2)

        # ...and against the FIXED strings too, which is not the same test. `11:$5848` is a
        # relocatable mid-conversation entry point sitting inside `11:$5803`, a 179-byte
        # in-place string -- so its span is really $5803's tail. Moving it hands those bytes
        # to the free pool and whatever lands there truncates $5803.
        #
        # This was latent, not new: address-order first-fit happened to put $5848 back at
        # its own address, which restored the parent's tail byte for byte. It only surfaced
        # when the trampolines shifted the packing by twenty bytes, and it surfaced as a
        # hang, not as a bad line. A unit that shares bytes with anything only makes sense
        # in situ, whoever it shares them with.
        fixed_spans = sorted((r['offset'], r['offset'] + r['bytes'] + 1)
                             for r in fixed if r['bank'] == bank)
        for s, e, u in spans:
            for s2, e2 in fixed_spans:
                if s2 >= e:
                    break
                if s < e2:
                    nested.add(u)

        movable = [u for i, u in enumerate(group) if i not in nested]
        for i, u in enumerate(group):
            if i in nested:
                for r in u:
                    final[r['id']] = put(r, final[r['id']])
                    placed[r['id']] = r['offset']

        def reloc_run_len(r):
            """What a redirect would cost this string: four bytes per LINE. See
            textpool.Pool.add_run -- the record run mirrors the original line layout so
            the walkers that publish one queue address per line keep working."""
            return textpool.RECORD_LEN * max(
                1, len(textpool.split_lines(final[r['id']] + bytes([codec.TERMINATOR]))))

        def size_of(unit):
            return sum(len(reloc_redirects[r['id']]) if r['id'] in reloc_redirects
                       else len(final[r['id']]) + (1 if needs_term(r) else 0)
                       for r in unit)

        extra = filler_runs(rom, bank, strings) if use_filler else []
        reclaimed = sum(n for _, n in extra)
        # Declared free regions vacated by box_alias.tsv. Unlike filler_runs these are not
        # a heuristic over the ROM's contents: the block is free because a named box now
        # renders a different one, and every reference into it has been redirected.
        extra = extra + [(s, e - s) for s, e in alias_free.get(bank, ())]

        # Address order keeps related text together and packs runs front to back, and for a
        # bank that fits exactly (13 and 14 both do) it is what achieves that fit -- so it
        # stays the first attempt. But one large unit can fail against a fragmented pool
        # even when the totals fit: bank 31's descriptors chop its free space into runs of
        # at most 26 bytes, and a 5-row category box needs 35 contiguous. Fall back to
        # best-fit decreasing, which is what actually packs bins.
        #
        # If neither order fits, revert the WHOLE bank to Japanese. Placing only some of
        # the units would leave moved text overlapping unmoved text, which is what produced
        # BADREFs when bank 30 first ran out of room: a bank of untranslated text is
        # correct, a half-relocated one is corrupt. Stranding just the offending unit looks
        # tempting and does not work -- withdrawing its space from the pool costs about as
        # much as its translation saved, so bank 30 strands all fifteen verbs one at a time.
        pool = free_runs([span_of(u) for u in movable]) + extra
        if bank == 31 and dot_font and not no_menuvwf:
            reserve_at = bank * BANKSZ + (menuvwf.ROM_READ_ORG - BANKSZ)
            reserve_n = len(menuvwf.rom_reader()[0])
            before = sum(n for _, n in pool)
            pool = alloc_at(pool, reserve_at, reserve_n)
            if before - sum(n for _, n in pool) != reserve_n:
                raise SystemExit(
                    'menuvwf: bank-31 ROM reader reservation at 31:$%04X (%d bytes) '
                    'is not wholly inside the measured relocatable text arena'
                    % (menuvwf.ROM_READ_ORG, reserve_n))
            notes.append('menuvwf: reserved %d bytes at 31:$%04X for the ROM-row reader'
                         % (reserve_n, menuvwf.ROM_READ_ORG))
        if bank == 31 and dot_font and not no_rankvwf:
            reserve_at = bank * BANKSZ + (rankvwf.PAGE_FINISH_AT - BANKSZ)
            reserve_n = len(rankvwf.page_finish()[0])
            before = sum(n for _, n in pool)
            pool = alloc_at(pool, reserve_at, reserve_n)
            if before - sum(n for _, n in pool) != reserve_n:
                raise SystemExit(
                    'rankvwf: bank-31 page-finalizer reservation at 31:$%04X (%d bytes) '
                    'is not wholly inside the declared box-alias arena'
                    % (rankvwf.PAGE_FINISH_AT, reserve_n))
            notes.append('rankvwf: reserved %d bytes at 31:$%04X for the Rankings page '
                         'finalizer' % (reserve_n, rankvwf.PAGE_FINISH_AT))

        # ---- the RELOCATABLE redirect
        #
        # A relocatable string is reached by a bank-relative pointer read by a loop running
        # in its own bank, so its arena is only the space its Japanese vacates -- and that
        # is what every endgame projection has been short of. Redirecting one replaces its
        # bytes with a 4-byte record naming the pool, so the arena's worst case becomes
        # 4 x (its string count), which is ratio-independent and far under every arena
        # here. That is the property this whole job exists to buy: the bank cannot overflow
        # however long the English turns out to be.
        #
        # Victims are the LARGEST eligible units first, so the fewest strings move for the
        # most space -- fewer moved strings is less exposure to a mis-attributed reader.
        # The trampoline comes out of the same free runs; it is allocated first, and it is
        # allocated whether or not this bank redirects anything, because a mechanism that
        # only appears in the builds that need it is one whose bugs only appear then too.
        # ...but only in a bank that has something to redirect. The trampolines cost bank 11
        # 63 bytes it does not have, and installing them into a bank whose tables are not
        # attributed buys nothing and reverts the bank to Japanese to pay for it.
        hook_undo = []
        wanted = (not no_pool
                  and (any(r['id'] in reloc_can for u in movable for r in u)
                       or any(r['bank'] == bank and r['id'] in redirects
                              and r['id'] in reloc_can for r in fixed)))
        for site in [s for s in textpool.RELOC_SITES if s[0] == bank] if wanted else []:
            at, size, mode = site[1], site[2], site[3]
            code = textpool.tramp(mode, 0)
            org, pool = alloc(sorted(pool), len(code), best=True)
            if org is None:
                raise SystemExit('bank %d: no room for the %d-byte trampoline for %d:$%04X'
                                 % (bank, len(code), bank, at))
            org = cpu_addr(org)
            want = textpool.RELOC_EXPECT[(bank, at)]
            off = bank * BANKSZ + (at - BANKSZ)
            if bytes(buf[off:off + len(want)]) != want:
                raise SystemExit('%d:$%04X is not the loop this hook expects -- refusing '
                                 'to patch' % (bank, at))
            buf[off:off + size] = textpool.reloc_patch(at, org, size)
            blob = textpool.tramp(mode, org)
            o = bank * BANKSZ + (org - BANKSZ)
            buf[o:o + len(blob)] = blob
            hook_undo.append((off, want))
            reloc_hooks.append('reloc hook %d:$%04X -> trampoline at %d:$%04X (%s)'
                               % (bank, at, bank, org, site[4]))

        total_free = sum(n for _, n in pool)
        need = sum(size_of(u) for u in movable)
        moved = [0]
        victims = sorted((u for u in movable if all(r['id'] in reloc_can for r in u)),
                         key=lambda u: -size_of(u)) if not no_pool else []
        vnext = [0]

        def redirect_one():
            """Move the largest remaining eligible unit into the pool. -> bytes freed."""
            while vnext[0] < len(victims):
                u = victims[vnext[0]]
                vnext[0] += 1
                was = size_of(u)
                floor = sum(reloc_run_len(r) for r in u)
                if was <= floor:
                    continue      # a slot this short cannot hold its record run, and there
                for r in u:       # would be nothing to win if it could
                    reloc_redirects[r['id']] = \
                        text_pool.add_run(final[r['id']] + bytes([codec.TERMINATOR]))
                moved[0] += len(u)
                return was - floor
            return 0

        # `--redirect-all` drains that list instead of stopping the moment the bank fits.
        # It exists because the endgame projection's ratio-independent floor is a claim
        # about a build nobody has ever made: today a bank redirects two or three strings,
        # so the mechanism carries almost none of the text it is being trusted to carry,
        # and "it works" is measured on the easy case. This flag builds the hard case now
        # -- every eligible string a record -- so crashscan, reloc_verify and the screen
        # checks all run against the shape the finished translation will actually have.
        while redirect_all and redirect_one():
            pass
        while need > total_free:
            freed = redirect_one()
            if not freed:
                break
            need -= freed
        need = sum(size_of(u) for u in movable)
        # ...and what it will need when every string in it is English. See PROJECT_RATIO.
        # The arena does NOT grow as translation proceeds -- it is the span the Japanese
        # vacates -- so this number is comparable to `total_free` today and every day.
        #
        # A REDIRECTABLE string's endgame cost is a 4-byte record, not its English, because
        # by then the allocator will have moved it: this loop redirects victims until the
        # bank fits, and the endgame is just the case where it has to redirect more of
        # them. Projecting those at 2.15x would report a shortfall the mechanism has
        # already answered, which is the report crying wolf rather than the bank being
        # short. `worst` is the floor underneath it: what the bank needs if EVERY
        # redirectable string is redirected, which is ratio-independent and is the number
        # that says this arena can no longer overflow.
        need_end = worst = 0
        for u in movable:
            for r in u:
                size = (size_of([r]) if r['id'] in translated_ids else
                        r['bytes'] * PROJECT_NET + (1 if needs_term(r) else 0))
                floor = reloc_run_len(r) if r['id'] in reloc_can else size
                need_end += min(size, floor)
                worst += floor
        projected.append((bank, total_free, need_end,
                          sum(1 for u in movable for r in u if r['id'] in translated_ids),
                          sum(len(u) for u in movable), worst,
                          sum(1 for u in movable for r in u if r['id'] in reloc_can)))

        # Address order keeps related text together and packs runs front to back; size
        # descending (first-fit then best-fit) is what actually packs bins when one large
        # unit faces a fragmented pool.
        #
        # NEGATIVE RESULT, 2026-07-31: 400 seeded randomised restarts on top of these were
        # tried and do NOT help. Once a bank runs at ~100% utilisation -- bank 13 sits at
        # 6973 of 6977 bytes with the composer strings translated -- a unit needing 5
        # contiguous fails unless the total slack happens to land in ONE run, and greedy
        # placement in any order cannot arrange that. Making bank 13 hold more English
        # needs exact-fit search (subset-sum per run) or more space, not a better shuffle.
        #
        # ...and when no order works, redirect one more unit and try again. That negative
        # result is about SHUFFLING, and it stands: no ordering wins against a bank at 100%
        # utilisation. What it does not cover is having more space, which is what a redirect
        # buys -- bank 11 hit exactly this, 4,151 bytes free and no 4 contiguous, and the
        # answer is to move one more string out rather than revert 459 of them to Japanese.
        plan, blocked, left = None, None, 0
        while plan is None:
            orders = [(lambda u: u[0]['offset'], False),
                      (lambda u: -size_of(u), False),
                      (lambda u: -size_of(u), True)]
            for order, best in (orders[1:] + orders[:1] if shuffle else orders):
                trial, attempt = list(sorted(pool)), []
                for u in sorted(movable, key=order):
                    at, trial = alloc(trial, size_of(u), best)
                    if at is None:
                        blocked, left = u, max((n for _, n in trial), default=0)
                        break
                    attempt.append((at, u))
                else:
                    plan = attempt
                    break
            if plan is None and not redirect_one():
                break
            need = sum(size_of(u) for u in movable)

        # The LARGEST CONTIGUOUS run left, not just the total. Freed space is not blanked,
        # so scanning the built ROM for $FF runs reports 9 bytes in a bank that has 4,291
        # -- and "is there room for a routine in bank 13" is a question this project keeps
        # having to answer (VWF was cancelled partly on a wrong answer to it).
        if plan is not None:
            left = sorted(pool)
            for at, u in plan:
                left = alloc_at(left, at, size_of(u))
            biggest = max((n for _, n in left), default=0)
            where = next((cpu_addr(o) for o, n in left if n == biggest), 0)
        else:
            biggest, where = 0, 0
        notes.append("bank %2d: repacked %d strings into %d bytes (need %d, %+d spare%s%s%s)"
                     % (bank, sum(len(u) for u in movable), total_free, need,
                        total_free - need,
                        ", %d from filler" % reclaimed if reclaimed else "",
                        ", %d redirected" % moved[0] if moved[0] else "",
                        "; largest free run %d at $%04X" % (biggest, where)
                        if biggest else ""))

        if plan is None:
            why = ('needs %d more bytes' % (need - total_free) if need > total_free else
                   'has %d bytes free, but by the time %s needed %d contiguous the largest '
                   'run left was %d -- fragmentation, not shortfall'
                   % (total_free, blocked[0]['loc'], size_of(blocked), left))
            problems.append((blocked[0], 'bank_full',
                             'bank %d %s; the whole bank reverted to Japanese to keep the '
                             'ROM valid' % (bank, why)))
            # Reverting writes the Japanese back at its ORIGINAL addresses, which is where
            # the trampolines were allocated from -- so the hooks have to come out with it,
            # or the bank keeps `call`s into bytes that are now text. That is what a
            # 12-of-12-seed hang looked like the first time this branch fired with the
            # relocatable redirect installed. Redirected strings in this bank go back too:
            # a bank of untranslated text is correct, a half-redirected one is not.
            for off, orig in hook_undo:
                buf[off:off + len(orig)] = orig
            reloc_hooks[:] = [h for h in reloc_hooks
                              if not h.startswith('reloc hook %d:' % bank)]
            plan = []
            for u in movable:
                for r in u:
                    final[r['id']] = bytes.fromhex(r['hex'])
                    reloc_redirects.pop(r['id'], None)
                plan.append((u[0]['offset'], u))

        for at, u in plan:
            for r in u:
                # A redirected string writes its record where its bytes would have gone;
                # the record carries its own $FF, so it never takes a terminator on top.
                data = reloc_redirects.get(r['id']) or final[r['id']]
                buf[at:at + len(data)] = data
                placed[r['id']] = at
                at += len(data)
                if needs_term(r) and r['id'] not in reloc_redirects:
                    buf[at] = codec.TERMINATOR
                    at += 1

    # ---- rewrite every reference to point at the new location
    #
    # Box rows are included: row 0 carries the descriptor's text pointer, and a row may
    # carry an immediate of its own -- 31:$418D `ld hl,$4275` is row 1 of box 12, the
    # name-entry grid page. Both have to follow the block when it moves.
    # An `imm` reference is an INSTRUCTION OPERAND, and a byte scan cannot prove it found
    # an instruction. Re-check every one against the untouched ROM before writing through
    # it: extract.py filters phantoms out, but script.json is a file on disk that can be
    # older than this check, and the failure mode is silent corruption of live code. The
    # one that shipped turned `0:$227B ld [$CF01],a` into `ld [$CE01],a` -- see
    # immediate_refs() in extract.py and HANDOFF_BUG.md.
    repointed = collections.Counter()
    for r in relocatable + [r for g in moving_boxes.values() for r in g]:
        new = placed.get(r['id'], r['offset'])
        ptr = cpu_addr(new)
        for ref in r['refs']:
            at = ref['operand_at']
            if ref.get('kind') == 'imm' and not dis.is_instruction_start(rom, at - 1):
                raise SystemExit(
                    'reference for %s at %s is not an instruction: `ld r16,$%04X` there '
                    'is inside a longer one, and rewriting it would overwrite live code. '
                    'Re-run tools/extract.py -- script.json predates the phantom filter.'
                    % (r['loc'], cpu_loc(at - 1), ref['ptr']))
            buf[at] = ptr & 0xFF
            buf[at + 1] = (ptr >> 8) & 0xFF
            repointed[ref.get('kind', '?')] += 1

    # An aliased box's references follow the TARGET's matching row, which is what makes
    # the alias invisible to the code that shows the box: the descriptor's text pointer
    # (row 0) makes the drawer read the target's block, and 31:$4192's `ld hl` -- box 13
    # row 1, the second grid page's base -- ends up on box 12 row 1, so the page a player
    # toggles to selects the characters it displays.
    if alias_refs:
        rows_now = collections.defaultdict(dict)
        for r in strings:
            if r.get('box'):
                rows_now[r['box']['id']][r['box']['row']] = r
        for dst, row, at in alias_refs:
            t = rows_now[dst].get(row)
            if t is None:
                raise SystemExit('box_alias.tsv: box %d has no row %d to point at'
                                 % (dst, row))
            ptr = cpu_addr(placed.get(t['id'], t['offset']))
            buf[at] = ptr & 0xFF
            buf[at + 1] = (ptr >> 8) & 0xFF
            repointed['alias'] += 1
    for n in alias_notes:
        notes.append(n)

    # ---- name-entry picker: the row stride, which the ROM holds as a CONSTANT
    #
    # 31:$41A0 `ld a,$13` is the number of bytes between grid rows: the picker reads
    # base + (row - 1) * stride + column, where base is the grid box's row 1. $13 = 19 is
    # right for the Japanese -- 18 bytes of text plus a terminator -- and WRONG the moment
    # the rows are translated, because English rows fill all 18 cells, `needs_term` drops
    # their terminators and the stride becomes 18. The base pointer is repointed above and
    # so stays correct; nothing was updating the stride, so every row below the first read
    # one byte further along than the row before it. Measured on the shipped build: row 2
    # gave 'G' for 'F', row 3 'M' for 'K', row 4 'S' for 'P'.
    #
    # Derived from where the rows actually landed rather than hardcoded to 18, so it stays
    # right if the grid is ever re-laid-out, and asserted uniform because the ROM has room
    # for exactly one stride.
    grid = sorted((r['box']['row'], r) for r in strings
                  if r.get('box') and r['box']['id'] == GRID_BOX)
    if grid:
        offs = [placed.get(r['id'], r['offset']) for _, r in grid]
        steps = {b - a for a, b in zip(offs, offs[1:])}
        if len(steps) != 1:
            raise SystemExit(
                'box %d rows are not evenly spaced (%s), so the picker cannot address '
                'them with one stride' % (GRID_BOX, sorted(steps)))
        stride = steps.pop()
        if not 0 < stride < 256:
            raise SystemExit('box %d row stride %d does not fit the constant at %s'
                             % (GRID_BOX, stride, cpu_loc(GRID_STRIDE_AT)))
        if buf[GRID_STRIDE_AT - 1] != GRID_STRIDE_OPCODE:
            raise SystemExit(
                'expected `ld a,n8` at %s for the picker stride, found opcode $%02X -- '
                'the address moved, and patching it blind would corrupt code'
                % (cpu_loc(GRID_STRIDE_AT - 1), buf[GRID_STRIDE_AT - 1]))
        was = buf[GRID_STRIDE_AT]
        buf[GRID_STRIDE_AT] = stride
        notes.append('name-entry grid stride %s: %d -> %d (box %d rows, %d cells each)'
                     % (cpu_loc(GRID_STRIDE_AT), was, stride, GRID_BOX,
                        cells(plain[grid[0][1]['id']], grid[0][1]['bank'])))

    # ---- an ADDRESS duplicated in a COMPARISON, not in a pointer
    #
    # 13:$404A is the gate for bank-13 message text: it builds `hl` from the high byte in
    # `a` and a low byte popped off the queue, then hands it to the composer at $40C5. On
    # the way it special-cases exactly ONE message by address, split across two immediates
    # so the reference scanner cannot see it as a pointer:
    #
    #   13:$405F  ld a,$2D / cp l        \  hl == $4C2D ?
    #   13:$4064  ld a,$4C / cp h        /  -> b = 0, which SKIPS the $CF05 page-break at
    #   13:$4069  ld b,$00                  $4070-$407D before drawing
    #
    # $4C2D is the death message. It relocates like any other bank-13 string -- TASK 2 moved
    # it and nothing updated this -- so the test then matched whatever string happened to
    # land at $4C2D and never the death message again. Same class as the name-entry grid
    # stride above: geometry, or here an address, duplicated in arithmetic somewhere else.
    #
    # A scan of the whole ROM for this shape (`ld a,n/cp l` paired with `ld a,n/cp h` within
    # 12 bytes) finds four sites, and this is the ONLY one that tests a string address; the
    # other three test $C9D6, which is WRAM. So this patch is complete, not a sample.
    if DEATH_CMP_LOC in by_loc:
        r = by_loc[DEATH_CMP_LOC]
        new = cpu_addr(placed.get(r['id'], r['offset']))
        for at, want, half in ((DEATH_CMP_LO, new & 0xFF, 'lo/cp l'),
                               (DEATH_CMP_HI, new >> 8, 'hi/cp h')):
            if buf[at - 1] != 0x3E:
                raise SystemExit(
                    'expected `ld a,n8` at %s for the %s half of the %s comparison, found '
                    'opcode $%02X -- patching blind would corrupt code'
                    % (cpu_loc(at - 1), half, DEATH_CMP_LOC, buf[at - 1]))
            buf[at] = want
        if new != 0x4C2D:
            notes.append('bank-13 message gate 13:$405F: hardcoded %s comparison -> $%04X '
                         '(the string moved; the test follows it)' % (DEATH_CMP_LOC, new))

    # ---- raw byte patches for text embedded in composites
    raw_applied = 0
    raw_spans = []
    rp = os.path.join('script', 'raw_patches.tsv')
    if os.path.exists(rp):
        for line in open(rp, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            key, en = line.split('\t', 1)
            bank, addr = key.split(':$')
            off = int(bank) * BANKSZ + (int(addr, 16) - 0x4000)
            data = encode_en(en.strip(), int(bank))
            # length must match: these sit between other data with no terminator
            old = cells(bytes(buf[off:off + len(data)]), int(bank))
            buf[off:off + len(data)] = data
            raw_spans.append((off, off + len(data)))
            raw_applied += 1
            notes.append("raw patch %s = %r (%d bytes)" % (key, en.strip(), len(data)))

    # ---- Fay's Puzzles header: mirror box 30's translation into bank 4's tilemap row
    #
    # See QUIZ_ROW_AT. This is a DERIVED copy, not a second translation -- edit
    # `31:$4435` and this follows. `plain` rather than `final` because the row is copied
    # into the tilemap byte for byte and never passes an expander, so it must not be
    # compressed.
    quiz = next((r for r in strings if r['loc'] == QUIZ_ROW_LOC), None)
    if quiz is not None:
        was = bytes(buf[QUIZ_ROW_AT:QUIZ_ROW_AT + QUIZ_ROW_CELLS])
        row = plain[quiz['id']]
        if was != QUIZ_ROW_JP:
            problems.append((quiz, 'quiz_row_moved',
                             'bank 4 %s does not hold the header row any more (%s) -- the '
                             'mirror was not applied' % (cpu_loc(QUIZ_ROW_AT), was.hex(' '))))
        elif len(row) > QUIZ_ROW_CELLS or any(b >= codec.CONTROL_MIN for b in row):
            problems.append((quiz, 'quiz_row_unfit',
                             '%d byte(s) with control codes=%s cannot be a %d-cell tilemap '
                             'row' % (len(row), any(b >= codec.CONTROL_MIN for b in row),
                                      QUIZ_ROW_CELLS)))
        else:
            pad = row + bytes([EN_CODES[' ']]) * (QUIZ_ROW_CELLS - len(row))
            buf[QUIZ_ROW_AT:QUIZ_ROW_AT + QUIZ_ROW_CELLS] = pad
            raw_spans.append((QUIZ_ROW_AT, QUIZ_ROW_AT + QUIZ_ROW_CELLS))
            notes.append("Fay's Puzzles header row %s mirrored from %s (%d cells)"
                         % (cpu_loc(QUIZ_ROW_AT), QUIZ_ROW_LOC, QUIZ_ROW_CELLS))

    # ---- tile patches for labels drawn as bitmaps
    tp = os.path.join('script', 'tile_patches.tsv')
    if os.path.exists(tp):
        import bartext
        for line in open(tp, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            loc, ntiles, text = line.split('\t')
            off = bartext.parse_loc(loc)
            tiles = bartext.render(text, int(ntiles) * 8)
            for i, t in enumerate(tiles):
                buf[off + i * 8: off + i * 8 + 8] = t
            notes.append("tile patch %s = %r (%s tiles)" % (loc, text, ntiles))

    # The pool TEXT and its index go in here -- after the repack, because the relocatable
    # redirect decides its victims per bank and so allocates pool entries all through it,
    # and before the verifier, which follows every record to the address it names and
    # compares what it reads there. Writing it after the verifier would have that check
    # read an empty bank -- and pass, since a bank of $FF reads back as a zero-length
    # string for any record it cannot follow.
    if not no_pool:
        buf = bytearray(text_pool.write(bytes(buf)))

    # ---- verify BEFORE checksums: follow every reference and confirm where it lands
    def read_at(off, limit=700):
        out = bytearray()
        while off < len(buf) and len(out) < limit and buf[off] != codec.TERMINATOR:
            out.append(buf[off])
            off += 1
        return bytes(out)

    # Strings nested inside a longer one (legitimate mid-conversation entry points, e.g.
    # 11:$5848 inside the 179-byte 11:$5803) have no terminator of their own, so reading
    # from their address runs on to the outer string's. Verify those by prefix.
    spans = sorted((r['offset'], r['offset'] + r['bytes'], r['id']) for r in strings)
    nested = set()
    for i, (s, e, _) in enumerate(spans):
        for s2, e2, id2 in spans[i + 1:]:
            if s2 >= e:
                break
            if e2 <= e:
                nested.add(id2)

    # A raw patch intentionally rewrites bytes inside a composite, so any string
    # overlapping one will not read back as extracted. Exempt those rather than report
    # a mismatch we deliberately caused.
    def raw_touched(r):
        a, b = r['offset'], r['offset'] + r['bytes'] + 1
        return any(a < y and x < b for x, y in raw_spans)

    # A box row that exactly fills its box carries no terminator (31:$44F7), so reading
    # from its address runs into whatever follows. Verify those by prefix too: the drawer
    # stops after `width` cells, not at an $FF.
    unterminated = {r['id'] for r in strings if not needs_term(r)}

    checks = mismatches = 0
    for r in strings:
        if raw_touched(r):
            continue
        want = final[r['id']]
        if r['refs']:
            for ref in r['refs']:
                at = ref['operand_at']
                ptr = buf[at] | (buf[at + 1] << 8)
                # A REDIRECTED relocatable string is verified through its record: the
                # reference lands on four bytes naming an index entry, and what has to read
                # back is the text that entry points at. Checking the record's own bytes
                # would pass on a record that names nothing.
                if r['id'] in reloc_redirects or r['id'] in redirects:
                    reloc_run = r['id'] in reloc_redirects
                    run = (reloc_redirects[r['id']] if reloc_run else
                           ec_head.get(r['id'], b'') + redirects[r['id']])
                    here = r['bank'] * BANKSZ + (ptr - BANKSZ)
                    checks += 1
                    if bytes(buf[here:here + len(run)]) != run:
                        mismatches += 1
                        problems.append((r, 'BADREF', 'ref at 0x%06X -> $%04X is not the '
                                                      'redirect record run' % (at, ptr)))
                        continue
                    # Follow every record in the run and read the lines back concatenated.
                    # Checking the run's own bytes would pass on a run naming empty banks.
                    checks += 1
                    got = (textpool.run_text(run, buf) if reloc_run else
                           ec_head.get(r['id'], b'')
                           + textpool.record_text(redirects[r['id']], buf))
                    if got != want + bytes([codec.TERMINATOR]):
                        mismatches += 1
                        problems.append((r, 'BADPOOL', 'record run at $%04X names text that '
                                                       'does not read back' % ptr))
                    continue
                got = read_at(r['bank'] * BANKSZ + (ptr - BANKSZ))
                checks += 1
                ok = (got.startswith(want)
                      if r['id'] in nested or r['id'] in unterminated else got == want)
                if not ok:
                    mismatches += 1
                    if mismatches <= 5:
                        problems.append((r, 'BADREF',
                                         '%s ref at 0x%06X -> $%04X reads the wrong bytes'
                                         % (ref.get('kind', '?'), at, ptr)))
        else:
            # A box row other than row 0 has no reference of its own, so it is verified
            # where it actually ended up -- which for a relocated box is not r['offset'].
            #
            # A REDIRECTED string is read through the INDEX, one entry per line, because
            # that is how the runtime reads it: `read_entry` resumes at `entry + 3` and
            # never assumes the lines are contiguous in the pool. Reading linearly from
            # the first line's address instead asserted a layout the pool does not
            # promise, and it failed the moment a string straddled two pool banks --
            # `14:$5875`, session 5. Terminators included, same as the reloc path above.
            checks += 1
            if r['id'] in redirects:
                # An `$EC` string's first two bytes never reach the pool -- they stay at
                # the original address, where `13:$6C73` resumes. Read them back OUT OF
                # THE ROM rather than out of `ec_head`: a verifier that re-derives the
                # value the writer used agrees with itself for ever, which is exactly how
                # the contiguity bug survived (see textpool.record_text).
                head = len(ec_head.get(r['id'], b''))
                got = (bytes(buf[r['offset']:r['offset'] + head])
                       + textpool.record_text(redirects[r['id']], buf))
                ok = (got == want + bytes([codec.TERMINATOR])
                      and bytes(buf[r['offset'] + head:r['offset'] + head + 1])
                      == bytes([textpool.MARK]))
                kind = 'BADPOOL'
            else:
                got = read_at(placed.get(r['id'], r['offset']))
                ok = (got.startswith(want)
                      if r['id'] in nested or r['id'] in unterminated else got == want)
                kind = 'BADPLACE'
            if not ok:
                mismatches += 1
                if mismatches <= 5:
                    problems.append((r, kind, 'redirected string does not read back through '
                                              'the index' if kind == 'BADPOOL' else
                                              'in-place string does not read back'))

    # ---- every `<cEC:xx>` string still OPENS with its prefix, in the ROM
    #
    # This is the check that was missing, and it reads the built bytes rather than any
    # variable that decided them. `13:$67F3` tests the first staged byte for `$EC` and
    # `13:$6C73` then resumes at "that address + 2"; a record written at the string's own
    # first byte puts bytes 2-3 of the record there instead, and the composer draws one
    # stray glyph and stops. Nothing else here can see it -- the string round-trips
    # through the pool perfectly, and it is the POINTER that is wrong.
    for r in strings:
        if not textpool.starts_ec(r):
            continue
        at = placed.get(r['id'], r['offset'])
        if buf[at] != textpool.EC_OPEN:
            problems.append((r, 'ec_prefix_lost',
                             'opens with <cEC> but the ROM has $%02X at %s: 13:$6C73 '
                             'resumes at +2 and would read the wrong two bytes'
                             % (buf[at], r['loc'])))

    # ---- the DTE expander, its table bank, and the render hooks
    #
    # Written after the verifier, because the verifier follows string references and these
    # are code and data at fixed addresses that no reference points at. Emitted even when
    # nothing was compressed: the expander is inert on text that contains no DTE code, so
    # the ROM stays uniform and the hooks get exercised on every build.
    # --no-hooks is the TRUE control for bisecting a render bug: --no-dte still installs
    # every hook and the expander, and only stops strings being compressed, so a bug caused
    # by a hook's own behaviour (loop2's cell cap, emit_lit's $CF38 destination guard)
    # survives it untouched. Distinguishing "the compressed CONTENT is wrong" from "the
    # HOOK changed how the renderer behaves" needs a build with no DTE machinery at all.
    # Implies --no-dte, because a compressed string with no expander is garbage.
    if no_hooks:
        if dte_table:
            raise SystemExit('--no-hooks requires --no-dte: compressed strings need an '
                             'expander to read them back')
        notes.append('--no-hooks: no expander, no table, no render hooks (bisect control)')
    exp, labels = dte_rom.build_expander()
    if no_hooks:
        exp, labels = b'', labels
    if any(buf[dte_rom.EXPANDER_ORG + i] != 0xFF for i in range(len(exp))):
        stray = [dte_rom.EXPANDER_ORG + i for i in range(len(exp))
                 if buf[dte_rom.EXPANDER_ORG + i] != 0xFF]
        notes.append('bank 0 padding held %d non-$FF byte(s) at %s -- overwritten'
                     % (len(stray), ' '.join('$%04X' % s for s in stray)))
    buf[dte_rom.EXPANDER_ORG:dte_rom.EXPANDER_ORG + len(exp)] = exp

    tb = dte_rom.TABLE_BANK * BANKSZ
    for off, blob in ({} if no_hooks else dte_rom.build_table(dte_table)).items():
        if any(b != 0xFF for b in buf[tb + off:tb + off + len(blob)]):
            raise SystemExit('bank %d is not free at $%04X' % (dte_rom.TABLE_BANK, off))
        buf[tb + off:tb + off + len(blob)] = blob

    # Resident code that does not fit the $0062 padding -- currently dte_box, in bank 0's
    # 20-byte tail. Each entry names the byte that must already be there: $3FE0-$3FEB
    # looks equally empty and is NOT free (three `rst $10` far-call thunks, one of which
    # 7:$505F calls), so "it disassembles as nothing" is not the test. Refuse rather than
    # warn: overwriting live resident code is not something a string verifier can catch.
    for addr, patch, fill, note in ([] if no_hooks else dte_rom.resident(labels)):
        wrong = [addr + i for i, b in enumerate(buf[addr:addr + len(patch)]) if b != fill]
        if wrong:
            raise SystemExit('0:$%04X is not free: %d byte(s) are not $%02X, first at '
                             '$%04X -- %s' % (addr, len(wrong), fill, wrong[0], note))
        buf[addr:addr + len(patch)] = patch
        notes.append('resident 0:$%04X %s' % (addr, note))

    # ---- the dialogue redirect
    #
    # Installed even when nothing was redirected, so that every build takes the same code
    # path through `13:$7589`. A mechanism that only appears in builds that need it is one
    # whose bugs only appear then too, and this one sits on EVERY line of dialogue in the
    # game -- the cheapest way to keep it honest is to never have a build without it.
    # The pool's endgame need. Every eligible string lands here once it is natural English --
    # at 2.15x essentially none of them still fit their own slot -- so the projection is over
    # ALL of them, not just the ones redirected so far.
    pool_projection = None
    if not no_pool:
        elig = [r for r in strings if textpool.eligible(r)]
        done = [r for r in elig if r['id'] in translated_ids]
        pool_projection = (
            text_pool.capacity(),
            sum(len(final[r['id']]) + 1 for r in done)
            + sum(r['bytes'] for r in elig if r['id'] not in translated_ids) * PROJECT_NET,
            len(done), len(elig))

    if not no_pool:
        buf = bytearray(textpool.install(bytes(buf))[0])
        notes.append('dialogue redirect installed; %s' % text_pool.report())
        if redirects:
            notes.append('%d in-place string(s) redirected into the pool, %d bytes of '
                         'English that had no room at their own address'
                         % (len(redirects), sum(len(v) for v in text_pool.data.values())))
        notes += reloc_hooks
        if reloc_redirects:
            notes.append('%d relocatable string(s) redirected into the pool; each cost its '
                         'bank 4 bytes instead of its length' % len(reloc_redirects))

    # The DTE hooks are written LAST, so anything they overlap silently wins. A relocatable
    # trampoline overwritten this way leaves the `call` gone but the records still in the
    # bank, and the reader that replaced it does not know what a record is -- which is a
    # hang, not a bad line. Two mechanisms may not own the same bytes; say so loudly.
    for bank, addr, patch, note in ([] if no_hooks else dte_rom.hooks(labels)):
        for s in textpool.RELOC_SITES:
            if s[0] == bank and addr < s[1] + s[2] and s[1] < addr + len(patch):
                raise SystemExit('hook collision: the DTE patch at %d:$%04X (%d bytes) '
                                 'overlaps the relocatable trampoline call at %d:$%04X '
                                 '(%d bytes). One of them has to move.'
                                 % (bank, addr, len(patch), s[0], s[1], s[2]))
        off = bank * BANKSZ + (addr - 0x4000)
        buf[off:off + len(patch)] = patch
        notes.append('hook %d:$%04X %s' % (bank, addr, note))
    if not no_hooks:
        notes.append('expander: %d bytes at 0:$%04X, table: %d pairs in bank %d'
                     % (len(exp), dte_rom.EXPANDER_ORG, len(dte_table),
                        dte_rom.TABLE_BANK))
    if unpadded_boxes:
        notes.append('%d box row(s) reverted to uncompressed because they are written in '
                     'place and would have been padded: %s'
                     % (len(unpadded_boxes), ' '.join(unpadded_boxes)))

    # ---- the player name, 4 characters -> 6
    #
    # Last, because it rewrites bank 15's save-record tables wholesale and asserts the
    # opcode at every site it touches: run after everything else and a collision with the
    # pool, the DTE table or a hook fails the build rather than being overwritten by it.
    # It moves no text, so it is outside the reference verifier's business.
    if not no_name6:
        name6.install(buf, notes)
    else:
        notes.append('--no-name6: the player name stays at 4 characters (bisect control)')

    # ---- Decoy Staff actor name: remove the untranslated runtime `ni-se` prefix
    #
    # This is not a glossary string. Bank 11 writes two Japanese font bytes immediately
    # before copying the live player name, so the English font showed `VNShiren`.
    # Preserve the dynamic player-name copy and skip only those two source-font bytes.
    if '--no-decoyname' not in a:
        decoyname.install(buf, notes)
    else:
        notes.append('--no-decoyname: Decoy Staff names retain raw `ni-se` prefix bytes')

    # ---- runtime item punctuation, counter word and direct item/viewer literals
    #
    # `4:$5D20` emits native `$7D` for a negative equipment modifier, while the English
    # composer needs its `$42` hyphen. `4:$5D37` writes the arrow count then `本の`, which
    # English does not want and which the Latin font draws as a symbol and a `Y`. Same
    # The identity-hidden Info branch also returns one literal Japanese sentence at
    # `13:$5537` instead of indexing the normal description table, and empty Pot See uses
    # another at `4:$7464`. Same patcher discipline as name6: every replaced byte is
    # asserted and each change is in place, so they move no text and are outside the
    # reference verifier's business. `--no-itemfix` is their shared bisect control.
    if '--no-itemfix' not in a:
        itemfix.install(buf, notes)
    else:
        notes.append('--no-itemfix: native runtime minus, arrow counter, unidentified '
                     'Info help and empty-Pot See text remain')

    # ---- Awards screen heading
    #
    # The four-cell box below Log N is generated from save data, not extracted text.
    # Under the English font its four kana codes appear as `TtfD`-style gibberish.
    # `Pass` fits the native four-character field and its existing box.
    if '--no-awardfix' not in a:
        awardfix.install(buf, notes)
    else:
        notes.append('--no-awardfix: Pass screen keeps its native generated four-kana code')

    # ---- the rankings board's own copy of the name, 4 characters -> 6
    #
    # After name6 for the same reason name6 goes last, and because it reads the packed
    # name buffer name6 rehomes. It changes the SAVE FORMAT of the rank table: a board
    # written by an older build is read at the wrong stride.
    if not no_rank6:
        rank6.install(buf, notes)
    else:
        notes.append('--no-rank6: the rankings board stays at 4 characters (bisect control)')

    # ---- the composer's variable-width font: an 8px cell becomes a 6px pen
    #
    # Last of all, for the reason name6 goes last and one more of its own: it COPIES bank
    # 13's source scanner into bank 32, so it has to read the scanner every other patch is
    # finished with. It asserts the copy holds no absolute address and that bank 32 is
    # free where it writes, so a collision with the DTE table, the pool or name6's copier
    # fails the build instead of being overwritten by it.
    if not no_vwf:
        if dot_font:
            unsupported = []
            native_fallback = set()
            late_fallback = []
            checked = 0
            for row in strings:
                if not dialogue.is_dialogue(row):
                    continue
                if row['id'] in trans:
                    checked += 1
                    original = bytes.fromhex(row['hex'])
                    leading = original[:1] == bytes([EN_CODES[' ']])
                    audit_data = encode_en(
                        (' ' if leading else '') + renderer_layout(trans[row['id']]),
                        row['bank'])
                else:
                    audit_data = final[row['id']]
                bad_codes = propvwf.unsupported_codes(audit_data, row['bank'])
                if bad_codes and row['id'] in trans:
                    unsupported.append((row['loc'], bad_codes))
                elif bad_codes:
                    for line in dialogue.split_lines(audit_data, row['bank']):
                        point = propvwf.fallback_point(line.data, row['bank'], approved_font)
                        if point is None:
                            continue
                        ordinal, pen = point
                        native_fallback.add(row['loc'])
                        if pen >= propvwf.HALF_PX:
                            late_fallback.append((row['loc'], ordinal, pen))
            if unsupported:
                raise SystemExit(
                    '--dot-font: %d composer string(s) retain glyphs outside the approved '
                    '%s page: %s' %
                    (len(unsupported), approved_font.name, ', '.join('%s=%s' %
                     (loc, '/'.join('$%02X' % code for code in sorted(codes)))
                     for loc, codes in unsupported[:12])))
            # A native-only glyph discovered after the 72px first half cannot restart
            # safely: those pixels are already committed. 14:$7EE6 is the one known
            # extraction false positive (294 decoded cells, no runtime consumer), also
            # calibrated in dialogue_preview.KNOWN_OVER. Any real/new line is a build
            # failure rather than a permanent preflight tax on every English frame.
            known_late = {'14:$7EE6'}
            unsafe_late = [item for item in late_fallback if item[0] not in known_late]
            if unsafe_late:
                raise SystemExit(
                    '--dot-font: native fallback is first detectable after the committed '
                    '72px half: %s' % ', '.join('%s glyph%d@%dpx' % item
                                                for item in unsafe_late[:12]))
            notes.append('propvwf: %d composer/help strings contain only approved %s '
                         'glyphs plus controls' % (checked, approved_font.name))
            notes.append('propvwf: %d untranslated composer/help strings select the '
                         'native 8px fallback' % len(native_fallback))
            notes.append('propvwf: %d late-native line(s) are known non-rendered '
                         'extraction false positives; every runtime line selects before '
                         'pixel 72' % len(late_fallback))
            propvwf.install(buf, approved_font, notes)
        else:
            vwf.install(buf, notes)
    else:
        notes.append('--no-vwf: the composer stays fixed-width, 18 characters a line '
                     '(bisect control)')

    # ---- the MENU renderer's VWF: bank 31's item-list drawer shares the active font
    #
    # After the dialogue renderer because the far code composes from its pre-shifted
    # glyph table in bank 32 and sits behind its blob in that bank. install() asserts
    # the expected table and free code region, so a collision fails the build.
    if not no_menuvwf:
        menuvwf.install(buf, notes, font=approved_font if dot_font else None)
    else:
        notes.append('--no-menuvwf: menu boxes stay fixed-width, raw drawer path '
                     '(bisect control)')

    # ---- structured fixed-cell rows: proportional words, immovable live fields
    if not no_structvwf:
        structvwf.install(buf, notes, font=approved_font)
    else:
        notes.append('--no-structvwf/non-Dot: composite status/quiz words stay fixed-width')

    # ---- rankings list names: six private proportional tiles per visible row
    #
    # Dot-only: the routine shares the approved glyph table and tiny lookup helpers from
    # menuvwf.  A page containing legacy kana selects the untouched native writer.
    if not no_rankvwf:
        if not dot_font:
            raise SystemExit('rankvwf requires --dot-font')
        rankvwf.install(buf, notes, font=approved_font)
    else:
        notes.append('--no-rankvwf: rankings list names stay fixed-width '
                     '(bisect control)')

    # ---- opening cinematic: canonical TSV -> relocated bytecode + static VWF packs
    #
    # After the text pool, which deliberately reserves bank 63 for this module, and after
    # the other renderers so every collision is checked against the final layout.
    intro_built = None
    if not no_intro:
        intro_built = intro.install(buf, intro_path, font=approved_font,
                                    source_rom=rom, notes=notes)
    else:
        notes.append('--no-intro/non-Dot: opening cinematic keeps the Japanese VM data')

    # ---- town/dungeon arrival cards: approved three-row Poppins masks, not script text
    #
    # Static label bases combine with the structure's live floor number. The larger pack
    # lives in guarded bank 60; installation remains after intro to keep graphics ordering.
    markers_built = None
    if not no_markers:
        markers_built = markers.install(buf, approved_font, intro_built, notes=notes)
    else:
        notes.append('--no-markers/non-Dot: town/dungeon arrival cards stay Japanese')

    # ---- pre-intro title/copyright card: approved full raster after native LCD-off load
    #
    # The complete visible 20x18 card comes from Joey's pixel-exact mock-up. Fade timing,
    # scene-0 entry and the later illustrated title continue down the native code path.
    titlecard_built = None
    if not no_titlecard:
        logo_far = None if no_titlelogo else (titlelogo.FAR_UPLOAD, titlelogo.FAR_BANK)
        titlecard_built = titlecard.install(buf, approved_font, markers_built, notes=notes,
                                            logo_far=logo_far)
    else:
        notes.append('--no-titlecard/non-Dot: pre-intro title card stays Japanese')

    # ---- illustrated title screen: four-shade English logo, native frame/PUSH START
    if not no_titlelogo:
        titlelogo.install(buf, approved_font, titlecard_built, notes=notes)
    else:
        notes.append('--no-titlelogo: illustrated title screen stays Japanese')

    # ---- active-dungeon Continue card: private speech-bubble text tiles
    if not no_waitcard:
        waitcard.install(buf, approved_font, notes=notes)
    else:
        notes.append('--no-waitcard/non-Dot: dungeon-resume bubble stays Japanese')

    # ---- ending credits: all 22 native cards translated over the native forest
    if not no_endingcredits:
        endingcredits.install(buf, approved_font, notes=notes)
    else:
        notes.append('--no-endingcredits/non-Dot: ending credits stay Japanese')

    # ---- checksums
    h = 0
    for i in range(0x134, 0x14D):
        h = (h - buf[i] - 1) & 0xFF
    buf[0x14D] = h
    buf[0x14E] = buf[0x14F] = 0
    g = sum(buf) & 0xFFFF
    buf[0x14E] = (g >> 8) & 0xFF
    buf[0x14F] = g & 0xFF
    open(out_path, 'wb').write(bytes(buf))

    # ---- address map: where each string ENDED UP -> the loc it is keyed on
    #
    # gbrun.py --dte-scan watches the BUILT rom, so it sees post-relocation addresses,
    # while translations and script/dte_ok.tsv are keyed on the original `loc`. Without
    # this map every relocated string the scan observed was recorded under an address
    # that matches nothing, so it silently failed to be allowlisted -- and the whole
    # point of the scan is to decide what may be compressed.
    mapname = os.path.join(os.path.dirname(out_path) or '.', 'relocmap.tsv')
    with open(mapname, 'w', encoding='utf-8') as f:
        f.write('# built address\toriginal loc -- generated by build.py, read by gbrun.py\n')
        for r in strings:
            f.write('%s\t%s\n' % (cpu_loc(placed.get(r['id'], r['offset'])), r['loc']))

    # ---- report
    print("translations supplied : %d" % len(trans))
    print("strings relocatable   : %d   in place: %d" % (len(relocatable), len(fixed)))
    print("references rewritten  : %s" % (dict(repointed) or 'none'))
    if dte_stats:
        print("DTE                   : %d pairs, depth %d, %d strings %d -> %d bytes "
              "(%.1f%%, %d saved)"
              % (dte_stats['pairs'], dte_stats['depth'], dte_stats['strings'],
                 dte_stats['before'], dte_stats['after'], dte_stats['pct'],
                 dte_stats['saved']))
        print("                        in-place budget %.2fx; %d in-place string(s) now "
              "draw more cells than the Japanese (cosmetic, the composer wraps)"
              % (1 / (1 - dte_stats['pct'] / 100), widened))
    elif '--no-dte' in a:
        print("DTE                   : disabled (--no-dte)")
    else:
        print("DTE                   : expander built, %d string(s) allowlisted, none "
              "compressed" % len(dte_allow))
        print("                        populate script/dte_ok.tsv with "
              "`gbrun.py <rom> --dte-scan` -- a string is only safe to compress once a "
              "trace has seen an EXPANDING loop read it")
    print("verification          : %d checks, %s"
          % (checks, "ALL OK" if not mismatches else "%d MISMATCH" % mismatches))
    for n in notes:
        print("   " + n)
    print("checksums             : header $%02X global $%04X" % (h, g))
    print("size                  : %d bytes" % len(buf))
    print("wrote %s" % out_path)

    # ---- what it will need when the script is FINISHED
    # Today's spare is not headroom, and reporting only today's spare is why every space
    # shortfall in this project has been discovered late. See PROJECT_RATIO.
    print("\nENDGAME PROJECTION at %.2fx natural English with DTE (%.2fx stored) -- what "
          "each arena needs\nwhen every string in it is English, against what it holds:"
          % (PROJECT_RATIO, PROJECT_NET))
    print("   %-22s %8s %8s %9s   %s" % ('arena', 'holds', 'will need', 'margin', 'done'))
    worst, floors = [], []
    for bank, cap, need, done, total, floor, movable_n in sorted(projected):
        if total == done and need <= cap:
            continue                      # finished and fitting: nothing to project
        print("   bank %-17d %8d %8d %+9d   %d/%d strings"
              % (bank, cap, need, cap - need, done, total))
        if need > cap:
            worst.append(('bank %d' % bank, need - cap))
        if movable_n:
            floors.append((bank, cap, floor, movable_n, total))
    if pool_projection:
        cap, need, done, total = pool_projection
        print("   %-22s %8d %8d %+9d   %d/%d strings"
              % ('redirect pool', cap, need, cap - need, done, total))
        if need > cap:
            worst.append(('the redirect pool', need - cap))
    if worst:
        print("   ** %s SHORT: %s. Total %d bytes."
              % ('ARENAS' if len(worst) > 1 else 'ARENA',
                 ', '.join('%s by %d' % w for w in worst),
                 sum(n for _, n in worst)))
        print("   ** This is a PROJECTION, not a failure -- the build is valid. It is here "
              "so the shortfall\n      is known now rather than found halfway through "
              "translating. 31 ROM banks are still empty.")
    else:
        print("   every arena fits the finished script at this ratio.")

    # The ratio-independent floor. A redirected string costs its bank 4 bytes whatever its
    # length, so this is what each arena needs if the English turns out to be so long that
    # EVERY redirectable string has to move. It does not depend on PROJECT_RATIO being
    # right, which is the point: the number above can be wrong and this one still holds.
    if floors:
        print("\n   ratio-independent floor -- what each arena needs if every redirectable "
              "string is\n   redirected, at 4 bytes each. This does not depend on the ratio "
              "above being right:")
        for bank, cap, floor, movable_n, total in floors:
            print("   bank %-17d %8d %8d %+9d   %d/%d redirectable"
                  % (bank, cap, floor, cap - floor, movable_n, total))
        stuck = [b for b, cap, floor, _, _ in floors if floor > cap]
        print("   ** %s" % ('every arena above can hold its whole share of the finished '
                            'script.' if not stuck else
                            'STILL SHORT AT THE FLOOR: bank(s) %s. More readers have to be '
                            'hooked (script/reloc_ok.tsv).'
                            % ', '.join(str(b) for b in stuck)))

    if problems:
        print("\n%d PROBLEM(S) -- these strings kept their original text:" % len(problems))
        for r, kind, msg in problems[:20]:
            print("   [%-9s] id=%-5d %-11s %s" % (kind, r['id'], r['loc'], msg))
        if report_path:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("id\tloc\tkind\tdetail\tjp\ten\n")
                for r, kind, msg in problems:
                    f.write("%d\t%s\t%s\t%s\t%s\t%s\n"
                            % (r['id'], r['loc'], kind, msg, r['jp'],
                               trans.get(r['id'], '')))
            print("   full worklist -> %s" % report_path)
    else:
        print("\nno problems: every supplied translation fit.")
        # Remove a worklist left by an EARLIER build, rather than leaving it to be read as
        # this one's. It is only written when there are problems, so a clean build used to
        # leave the last failing build's file sitting there with a current-looking name --
        # `build/worklist.tsv` still listed five BADPOOL strings hours after the pool fix
        # landed, and TRANSLATING.md §6 tells a translator to work from it.
        if report_path and os.path.exists(report_path):
            os.remove(report_path)
            print("removed a stale %s from an earlier build" % report_path)
    return 1 if any(k == 'no_space' for _, k, _ in problems) else 0


if __name__ == '__main__':
    sys.exit(main())
