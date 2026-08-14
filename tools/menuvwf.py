#!/usr/bin/env python3
"""VWF for the MENU renderer — menus, item information and seals share Dot spacing.

WHAT THIS HOOKS. The menu box row drawer `31:$40D8` writes raw character codes into the
`$C300` shadow tilemap — one glyph per cell, VRAM tile N = code N (FINDINGS "Path B").
This patch replaces its entry with a far call (rst $10, bank 32 index 7). The far routine
draws an ELIGIBLE row itself with a variable-width pen and returns carry set; anything else falls
back to the original drawer byte-for-byte (it returns with bc pre-loaded exactly as the
original's first two loads would have left it, and carry clear).

ELIGIBILITY — a DESCRIPTOR SHAPE ALLOWLIST, not a flags test. The step-5 census found
that x5,y9,w9 is shared by both the title-screen `Log N` selector and an over-dialogue
picker whose $9000-$97FF holds TERRAIN, not the font. The proportional path therefore
requires both measured geometry and, for that shared shape, the exact staged
`00 Log [1-3]` payload. Composing is only safe on screens the font upload built. The
general allowlist is main (x0,y0,w5), item (x0,y3,w18), the one-row Floor item header
(x0,y0,w18), action (x13,w5), the no-cursor
item-information/seal shape (x0,y3,w18, flags 0), and the five-row clear-condition list
(x0,y6,w18, flags 0). Start-flow additions are the title box
(x0,y1,w11, 3-8 rows), payload-gated Log selector (x5,y9,w9, 1-3 rows), save summary
(x4,y4,w14, 3 rows), and confirmation prompt (x3,y7,w15, 2 rows). install() asserts the
stable box IDs still match their measured geometry. The uniform control remains item-only
and byte-identical. Every unrelated use of the shared selector shape remains raw. A
WRAM-staged row must also have:
  * row source inside the measured `$C616-$C699` staging block,
  * a shape-dependent raw prefix: ZERO cells for item information/seals, ONE zero cell
    for main/action, or TWO item cells where
    byte 0 is $00 or the EQUIPPED MARKER $84/$86 and byte 1 is $00. The marker does
    DOUBLE duty, measured on Joey's save
    2026-08-06 against the raw drawer's own shadow output: it selects the left border
    ($83/$85 instead of $BE) AND is itself drawn at column 1 — tile $84 IS the E
    glyph. menurow replicates both (border from the byte, the byte redrawn raw at
    col 1), so equipped rows compose with their name at column 3 like every other row.
    A first guess that the marker was border-only shifted composed E-rows one cell
    left and put the cursor over their first tile,
  * row number `d` <= 4 and a valid prefix; the raw cursor cells stay raw so the game
    cursor writer keeps working,
  * 1..18 SOURCE characters for WRAM menus/items or 1..21 for item information, seals, and
    clear-condition rows; every code
    is < $43 or one of the explicitly admitted punctuation/status glyphs. Equipment
    unidentified-equipment suffix `$88` and plating suffix `$8A` are composed as their
    native marks at an 8px advance; the cursed prefix `$87` remains a separate raw status
    cell. `$7D` is normalized to the approved font's `-` glyph.
    Kana, dakuten and DTE bytes all fall back. These scanner ceilings are not visual
    budgets: the row is accepted only after a separate font-pixel scan and allocator fit.
    The current 17-character fixture includes a staff/pot name plus two-digit `[NN]`.

ROM-SOURCED ELIGIBILITY. ``menuromcensus.py`` measures every literal/DTE row reaching the
untouched drawer. build.py keeps the approved rows literal and install() marks only boxes
1,8,9,14,16,17,24,28,29,32,33,34,38,41,46,47,48,50,51 with descriptor bit 6. Bank 32
reads them one byte at a time through the nested bank-31 gate at $459E. A leading zero
cursor cell stays raw. Descriptor bit 5 additionally keeps the nonzero first cell raw for
boxes 8 and 17: `Which?` and `Pot` are overwritten in their live flows. The synthetic
forced-screen-1 cursor overwrite is not a real `Items` lifetime, so box 14 composes its
complete word. Static headings compose from their first letter. The remaining codes accept the approved font page plus
question mark $80 and the measured high English codes. Composite fixed-cell rows (boxes 2
and 30), the name grid, and every non-Log use of the shared box-25 shape stay raw.

THE TILE POOL AND THE ALLOCATOR. The base pool is `$43-$7B`, 57 tiles — NOT the whole kana
half. §2's "no English menu screen references $40-$7F" was measured on screens without
counters or punctuation: latinfont put `, ' - + [ ]` on tiles $40/$41/$42/$7C/$7E/$7F,
so the item list's `[N]` counter and the five `-` item names (One-Use Shield ...)
reference INSIDE $40-$7F, and a composed slice covering those tiles garbles every raw
row that draws them — the POC's fixed `$40+12*d` slices had exactly this bug, latent.
A row's slice comes from a WATERMARK allocator. Records are keyed by shadow destination
and hold (base, cap, raw cells), with cap = 4 for <=4 tiles, 8 for 5-8, the exact
9-13 tile queue footprint, or 16 for a 14-16-tile wide row. The proportional build adds
only census-unseen `$8B-$95`
(11) and `$9A-$9D` (4); `$87` is isolated and cannot satisfy capneed's minimum 4. The
ordinary allocator uses the 11-run first, with 12-16-tile rows using the base run. Exact
Items pages rotate five visible rows plus one free owner through six settled 11-tile
slices. `$25-$2F` is a guarded transition-only slice: Action-cancel and three-row Pot
contents borrow it for returned row 0, while high-Info return may borrow it for whichever
row has no released high slice. The completed Items/Pot map then releases a high owner;
the borrowed row is pixel-identically migrated there before input resumes and the native
`$25-$36` font is restored. Initial and repeated Main -> Items instead choose the five
high slices not owned by Main and never borrow the low slice. Action rows use a
page-independent generation `$9A-$A1,$C7-$CD,$D6-$DC`; the compact Name/Info tail uses
three tiles per row.  It never borrows an Item high slice, so Info paging and return can
rebuild Items without repainting text still referenced by the resident Action box.

PAGE FLIPS. Fresh pixels uploaded into reused tiles used to show through the old map.
Each replacement item row is now composed into the one slice absent from the five shadow
rows, then its complete 20-cell shadow row is copied to the visible map at VBlank. Only
after that commit can the outgoing row's slice become the scratch for the following row.
Blank trailing rows take the same commit path. The LCD remains on and complete old/new
rows progress like the Japanese renderer; no glyph tile visible in the outgoing row is
modified. Before each complete-row commit, the restored selection in `$C6A5` pre-stages
the `$81` cursor in its final shadow row, so no later native cursor write creates a
partially published frame.

FLOOR ACTION / INFO. The same reused-tile exposure occurred on action -> Info, Info page
1 -> 2, and Info -> action. Alternating low/high Info generations keep every outgoing
glyph immutable while the next page is composed. Each painted row is published whole at
a fresh VBlank; the last row stages the native border/pager and uses bank 4's own 18-row
map producer. A settled-Info marker survives the intermediate screen-0 redraw on return;
that transient map is suppressed, and screen 20's real Action rows progressively release
the old Info slices before reusing them. Low-generation fixed glyphs are restored only
after the completed map no longer refers to their proportional pixels. The LCD stays on.

THE UPLOAD. Composition goes into the `$C006` queue payloads (the three 66-byte slots,
a flat 12-tile space with 2-byte dest gaps) plus a 16-byte extension buffer for TILE 12
— the queue physically cannot hold a 13th tile, which is what capped the POC at 16
characters. With the LCD on: write the three slot destinations the way `13:$43E2` does,
arm the vblank tile-data consumer (`[$C11A] = $0A`, table `0:$06CF` entry -> `0:$11A8`),
and wait one pass (`call $06F7`). **The consumer moves 9 tiles a pass, not 12** — slot
3's unrolled copy is ONE tile (counted at `0:$130B`: 32/32/8 pop-de units), the dialogue
half-line shape hardcoded. Rows of 10-13 tiles take a SECOND pass shaped as a uniform
4-tile window over the row's LAST 4 tiles (tiles n-4..n-1): all three slots carry the
same window content aimed at the same destination, so every slot's write is correct or
idempotent REGARDLESS of consumer order, and the upload footprint is exactly n tiles.
Rows of 14-16 tiles use two overlapping pens: the first uploads tiles 0-8, tile 8 is
retained, and the second resumes at that boundary and uploads tiles 8-15. This avoids
claiming more WRAM; wide records round to a 16-tile cap. With the LCD off (menu-open
transitions run that way), ordinary rows copy exactly n tiles and wide rows use the same
9+8 overlap. Glyphs come
from the active dialogue renderer's pre-shifted 1bpp table in bank 32, OR-ed into both
2bpp planes. The baseline path retains vwf.py's four uniform-6px shifts; `--dot-font`
uses propvwf.py's eight font shifts, width metadata, and painted final-glyph extent.
Tile destinations use LCDC's signed `$8800` mapping: IDs below `$80` are `$9000+16*n`,
while `$8B-$9D` wrap into `$88B0-$89D0`; linear `$9000+16*n` writes into the tilemap.

THE ONE-CELL PARK — the bug Joey's colour screenshot found (2026-08-06). Every pass of
EITHER `$C006` consumer first replays the one-cell record at `$C000` ([$C000]=dest,
writes [$C002]/[$C003] to dest+0/1 and [$C004]/[$C005] to dest+32/33). Menus PARK that
record with dest = `$C002` — aimed into the queue itself as a no-op — so each pass wrote
`$C0,$0C` over payload bytes `$C022/$C023` (slot-1 tile 1, row 5) BEFORE the copy ran:
one row of one tile got single-plane garbage, green specks on a colour screen. The
dialogue path never hits this because the typewriter keeps `$C000` aimed at real VRAM.
While our upload is armed we aim the record at our own slot-1 destination (its stale
write lands inside the 64 bytes the copy immediately overwrites) and restore the park
after the last pass — the game's later passes must keep writing where the game parked it.

SCRATCH — all PROVEN free 2026-08-06 by `tools/wramfree.py` (zero voted static
references in the base ROM; zero dynamic writes on the --no-menuvwf control across the
dungeon menu script, 8 seeded walks and all 35 forced menu screens, watched every
frame; the survivors of the naive pair scan were all data banks misread as code):
  * `$C0CC-$C0DD`  per-row state: src ptr, count, raw-cell prefix, pen, ptr, tiles,
                   tile idx, park save, watermark, record count, row key, base,
                   window, tile cursor
  * `$C163-$C1B2`  the record-table run. The uniform control uses all 16 records and
                   keeps watermark/count at `$C0D7/$C0D8`. The proportional build uses
                   15 records (`$C163-$C1AD`) and puts three watermarks, shape kind and
                   count at `$C1AE-$C1B2`; 15 exceeds the measured 13-row stacked peak
                   and prevents propvwf's ephemeral `$C0D7/$C0D8` from corrupting them.
                   `$C0D7` is the synchronous Floor/Info and start-screen transaction
                   byte: 2/3 are settled low/high Info generations, 4/5 are their
                   respective return-pending states, and
                   `$10/$11/$12/$13/$14` are title/file, difficulty, proportional
                   Rankings, Fay-screen and native Rankings transactions. It is cleared
                   after the corresponding map publication. Item ownership is disjoint:
                   `$C1BA` holds lifecycle magics `$A0-$A9` (invalid, settled, page,
                   entry, Action, cancel, low/high Info return, Main, and Pot build).
  * `$C12C-$C13B`  tile 12's composition buffer
  ($C0E0-$C0FB, the first 7-record table, is proven free but no longer used.)
The game's own park at `$C0DE` writes to `$C0DE/DF` and `$C0FE/FF`, next to the first
run — those bytes are excluded on purpose. THE RAW-CELL PREFIX IS SHAPE-DEPENDENT:
w18 boxes stage TWO leading zero cells (cursor slot + the cell the cursor writer
toggles), the w5 main and action menus stage ONE — a fixed two-zero test made
every main-menu row fall back, and the narrow latin font's left-aligned glyphs made the
raw result look composed in a screenshot. The uniform control retains contiguous-pool
growth. The proportional path validates every reused record wholly inside one of its
three runs and never grows in place; a larger redraw safely falls back.
Pre-first-reset garbage is guarded by record-count, base and run-boundary checks —
composing through garbage state could overwrite font data or the tilemap, so these
guards are load-bearing, not paranoia.

usage: menuvwf.py <rom-in> <rom-out> [--dot-font]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
import dialogue_preview as dialogue
import pool as textpool
import propvwf

BANKSZ = 0x4000
FAR_BANK = 0x20             # bank 32, with vwf's glyph table at $4400
FAR_INDEX = 0x07            # entry pointer at 32:$4006/7 ($4000 + index - 1)
CODE_AT = 0x7300            # after vwf's blob (ends $71D8); 3.3 KiB free behind it
PROP_CODE_AT = 0x7740       # exactly after propvwf; rankvwf's auxiliary moved to bank 33

# Start/file-flow shape and difficulty-pool classification need no glyph-table access, so
# they live in pool.py's explicitly reserved bank-33 code arena rather than being squeezed
# against name6's live template in bank 32.  $0F is the one remaining whole far index;
# modes 2/3 are stable forwarding slots for rankvwf's validator/uploader at $4200/$4240.
START_AUX_BANK = 0x21
START_AUX_INDEX = 0x0F
START_AUX_AT = 0x4100
START_AUX_LIMIT = 0x4200
RANK_VALIDATE_AT = 0x4200
RANK_UPLOAD_AT = 0x4240
# rankvwf's signed-ID uploader needs two more bytes now that its private pool crosses
# $80.  The blanker still ends below $4300, so move its explicitly owned start forward.
START_BLANK_AT = 0x42B6
SELECTOR_BANK = 0x22
SELECTOR_INDEX = 0x05
SELECTOR_AT = 0x4060
SELECTOR_LIMIT = 0x4100
SUMMARY_BANK = 0x23
SUMMARY_INDEX = 0x05
SUMMARY_AT = 0x4060
SUMMARY_LIMIT = 0x4100
CONFIRM_BANK = 0x24
CONFIRM_INDEX = 0x05
CONFIRM_AT = 0x4060
CONFIRM_LIMIT = 0x4100
ITEM_PAGE_BANK = 0x25       # pool bank 37: reader ends $405A, text starts at $4100
ITEM_PAGE_INDEX = 0x05
ITEM_PAGE_AT = 0x405A
ITEM_PAGE_LIMIT = 0x4100
ITEM_PUBLISH_INDEX = 0x07
# Five settled Item rows rotate through six high slices.  `$25-$2F` is a guarded
# transition-only slice: it is normalized into a free high slice before input resumes,
# then the shared fixed-font restorer repaints its canonical native glyphs.
ITEM_ROW_TILES = 11
ITEM_SOURCE_CHARS = 18       # proportional staged scan accepts through E=$12, rejects $13
ITEM_HIGH_SLICES = (0x43, 0x4E, 0x59, 0x64, 0x6F, 0x8B)
ITEM_TRANSIENT_BASE = 0x25
ITEM_ROW_SLICES = ITEM_HIGH_SLICES + (ITEM_TRANSIENT_BASE,)
ITEM_MAIN_VIRGIN_ROWS = ITEM_HIGH_SLICES[1:]
ITEM_INFO_LOW_ROWS = ITEM_HIGH_SLICES[2:] + ITEM_HIGH_SLICES[1:2]
# High-Info return must work for every page-history permutation.  The Action box owns its
# disjoint generation while Info is open, so the chooser may consider all six high Item
# slices plus the transient without a page-history-dependent exclusion.
ITEM_INFO_HIGH_CANDIDATES = ITEM_HIGH_SLICES + (ITEM_TRANSIENT_BASE,)
ITEM_NAME_BANK = 11
ITEM_NAME_TABLE = 0x4537
ITEM_NAME_COUNT = 145
ITEM_INFO_TOPIC_COUNT = 157  # final twelve table slots alias the Kasa Tanuki name
ITEM_ENHANCEMENT_COUNT = 34
ITEM_COUNTER_NAME_COUNT = 23  # terminal-noun Staff/Pot names; not numbered placeholders
# Equipment has 199 signed states including bare zero; counter classes have [1]..[99];
# every other live name has one bare form: 34*199 + 23*99 + 88 = 9,131.
ITEM_VARIANT_COUNT = (ITEM_ENHANCEMENT_COUNT * 199 +
                      ITEM_COUNTER_NAME_COUNT * 99 +
                      ITEM_NAME_COUNT - ITEM_ENHANCEMENT_COUNT - ITEM_COUNTER_NAME_COUNT)


def _asm_bytes(values):
    """Format one canonical Python tile tuple as an RGBDS-style byte list."""
    return ','.join('$%02X' % value for value in values)


# Measured-free persistent ownership state.  Five current row bases, the free high
# slice, transient-row index, lifecycle, then five context bytes (cancel/Pot roll state
# or Info's outgoing row caps).
ITEM_ROWS_AT = 0xC1B3
ITEM_FREE_AT = 0xC1B8
ITEM_LOW_ROW_AT = 0xC1B9
ITEM_STATE_AT = 0xC1BA
ITEM_CONTEXT_AT = 0xC1BB
ITEM_STATE_INVALID = 0xA0
ITEM_STATE_SETTLED = 0xA1
ITEM_STATE_PAGE = 0xA2
ITEM_STATE_ENTRY = 0xA3
ITEM_STATE_ACTION = 0xA4
ITEM_STATE_CANCEL = 0xA5
ITEM_STATE_INFO_LOW = 0xA6
ITEM_STATE_INFO_HIGH = 0xA7
ITEM_STATE_MAIN = 0xA8
# Exact three-row Pot contents use a separate build/finalization state. They borrow the
# Action-cancel release sequence, normalize their transient row, then settle back to
# Action ownership; the later B route returns to Items through an ordinary page rotation.
ITEM_STATE_POT = 0xA9
# Item Action pickers have up to six rows.  Keeping every row in a context-local run is
# essential: Info remains over the Action map, so borrowing ITEM_FREE_AT would leave a
# page-history-dependent high slice visibly live during Info -> Items.  Rows 4/5 are the
# native tail choices Name/Info and have a proved three-tile VWF cap; the first four keep
# four tiles.  The ranges avoid checkbox `$A4`, Pot-header `$C7-$C8` while its three-row
# picker is live, and transient screen-0 users `$CE,$D0-$D5`.
ITEM_ACTION_BASE = 0x9A
ITEM_ACTION_BASES = (ITEM_ACTION_BASE, ITEM_ACTION_BASE + 4,
                     0xD6, 0xC7, 0xCB, 0xDA)
ITEM_ACTION_ROWS = 6
ITEM_ACTION_CAPS = (4, 4, 4, 4, 3, 3)
# Row commit is separate from allocation so both helpers fit before their banks' text.
# Bank 46's prefix is explicitly outside its Rankings text/helper region at $4100+.
ITEM_COMMIT_BANK = 0x2E
ITEM_COMMIT_INDEX = 0x0B
ITEM_COMMIT_AT = 0x405A
ITEM_COMMIT_LIMIT = 0x4100
# The completed Items header owns the transient-to-settled migration. Pool bank 48 is
# otherwise text-only from $4100 onward; its reader-to-text prefix is explicitly reserved.
ITEM_FINISH_BANK = 0x30
ITEM_FINISH_INDEX = 0x05
ITEM_FINISH_AT = 0x405A
ITEM_FINISH_LIMIT = 0x4100
# Complex ownership selection is split out of the tiny bank-37 allocator entry.
ITEM_STATE_BANK = 0x32
ITEM_STATE_INDEX = 0x05
ITEM_STATE_AT_ROM = 0x405A
ITEM_STATE_LIMIT = 0x4100
ITEM_CHOICE_BANK = 0x33
ITEM_CHOICE_INDEX = 0x05
ITEM_CHOICE_AT = 0x405A
ITEM_CHOICE_LIMIT = 0x4100
ITEM_INFO_CHOICE_BANK = 0x34
ITEM_INFO_CHOICE_INDEX = 0x05
ITEM_INFO_CHOICE_AT = 0x405A
ITEM_INFO_CHOICE_LIMIT = 0x4100
ITEM_MIGRATE_BANK = 0x35
ITEM_MIGRATE_INDEX = 0x05
ITEM_MIGRATE_AT = 0x405A
ITEM_MIGRATE_LIMIT = 0x4100
ITEM_TRANSITION_BANK = 0x36
ITEM_TRANSITION_INDEX = 0x05
ITEM_TRANSITION_AT = 0x405A
ITEM_TRANSITION_LIMIT = 0x4100
ITEM_FIXED_BANK = 0x37
ITEM_FIXED_INDEX = 0x05
ITEM_FIXED_AT = 0x405A
ITEM_FIXED_LIMIT = 0x4100
# The completed Item header publishes four complete 20-cell rows per VBlank from the
# same bank tail as the fixed return allocator.
ITEM_MAP_BANK = ITEM_FIXED_BANK
ITEM_MAP_INDEX = 0x07
ITEM_VALIDATE_BANK = 0x38
ITEM_VALIDATE_INDEX = 0x05
ITEM_VALIDATE_AT = 0x405A
ITEM_VALIDATE_LIMIT = 0x4100
ITEM_ACTION_BANK = ITEM_STATE_BANK
ITEM_ACTION_INDEX = 0x07
ITEM_POT_FINISH_BANK = ITEM_STATE_BANK
ITEM_POT_FINISH_INDEX = 0x09
ITEM_MAIN_BANK = 0x3A
# Ending credits own index 5 and $4100+ in this bank; Item Main fits in the otherwise
# free pre-text prefix and uses the adjacent far slot.
ITEM_MAIN_INDEX = 0x07
ITEM_POT_HEADER_INDEX = 0x09
ITEM_MAIN_AT = 0x405A
ITEM_MAIN_LIMIT = 0x4100
# Shared with the Floor/Info fixed-font restorer.
FIXED_RESTORE_BANK = 0x31
FIXED_RESTORE_INDEX = 0x05
FIXED_RESTORE_AT = 0x405A
FIXED_RESTORE_LIMIT = 0x4100
FLOOR_INFO_BANK = 0x27      # pool banks 39/40: reader ends $405A, text starts at $4100
FLOOR_INFO_INDEX = 0x05
FLOOR_INFO_AT = 0x405A
FLOOR_INFO_LIMIT = 0x4100
FLOOR_INFO_FINISH_BANK = 0x28
FLOOR_INFO_FINISH_INDEX = 0x05
FLOOR_INFO_FINISH_AT = 0x4060
FLOOR_INFO_FINISH_LIMIT = 0x4100
# Floor/Info mode 1/2 work and allocation are split into free pre-text prefixes.  Bank
# $3B's index 5 and $4100+ belong to endingcredits; index 7 is independently free.
FLOOR_INFO_POST_BANK = 0x39
FLOOR_INFO_POST_INDEX = 0x05
FLOOR_INFO_POST_AT = 0x405A
FLOOR_INFO_POST_LIMIT = 0x4100
FLOOR_ALLOC_BANK = 0x3B
FLOOR_ALLOC_INDEX = 0x07
FLOOR_ALLOC_AT = 0x405A
FLOOR_ALLOC_LIMIT = 0x4100
# Native bank 4's map producer at $44A2 copies C6A2 rows starting at C6A1, up to five
# per mode-8 VBlank.  Far index $4F is unused in the base and points at that routine.
NATIVE_MAP_BANK = 0x04
NATIVE_MAP_INDEX = 0x4F
NATIVE_MAP_AT = 0x44A2
START_TRANSITION_BANK = 0x29  # pool banks 41/42: reader ends $405A, text starts $4100
START_TRANSITION_INDEX = 0x05
START_TRANSITION_AT = 0x405A
START_TRANSITION_LIMIT = 0x4100
START_FINISH_BANK = 0x2A
START_FINISH_INDEX = 0x05
START_ALLOC_INDEX = 0x07
START_FINISH_AT = 0x405A
START_FINISH_LIMIT = 0x4100

# Save-summary place names are assembled in bank 4 as fixed-cell rows.  A numberless
# place was still indented by four cells, while a numbered long place could spill its
# final letters into the difficulty row.  The helper uses unused pre-text space in pool
# bank 45: its producer entry removes the numberless indent, and its render entry copies
# a genuinely overflowing row to private staging before clearing only the spill bytes.
SUMMARY_HELPER_BANK = 0x2D
SUMMARY_HELPER_INDEX = 0x05
SUMMARY_HELPER_AT = 0x405A
SUMMARY_HELPER_LIMIT = 0x4100
SUMMARY_PRODUCER_AT = 0x6985

GLYPHS = 0x4400             # vwf DATA_ORG: 4 shifts x $B3 codes x 16 bytes (8 + 8 spill)
SHIFT_STRIDE = 0xB30        # $B3 * 16

ROW_DRAWER = 0x40D8         # bank 31
ROW_EPILOG = 0x411F         # pop hl/de/bc/af + ret
POOL_BASE = 0x43            # first pool tile index -- NOT $40: see the glyph-tile note
POOL_END = 0x7C             # exclusive -- $7C is '+'
GLYPH_TILES = (0x40, 0x41, 0x42, 0x7C, 0x7E, 0x7F)   # , ' - + [ ] live INSIDE $40-$7F

FONT_UPLOAD = 0x7643        # bank 13: the menu-transition font upload = the reset signal
OLD_FONT_ENTRY = bytes.fromhex('210090')      # ld hl,$9000 -- replaced by the far call
RESET_INDEX = 0x09          # far index for menureset (menurow is FAR_INDEX = 7; the
                            # index table has a ONE-byte stride so entries overlap --
                            # live indices are odd: name6 3, vwf 5, menurow 7, this 9)

# ROM-sourced rows use a shape-scoped $CB-$DD pool.  $CA is deliberately excluded: it is
# the name keyboard's native underline.  Box 1 (Gitan/Floor/Path) and box 9 (No items
# held) really coexist, so the allocator below gives those two identities disjoint slices
# instead of assigning both from row count alone.
ROM_BOXES = (1, 8, 9, 14, 16, 17, 18, 24, 28, 29, 32, 33, 34,
             38, 41, 46, 47, 48, 50, 51)
ROM_SOURCE_CAP = 18         # explicit terminator follows at most 18 source glyphs
CONTEXT_STATIC_ROWS = True
ROM_FLAG_BIT = 0x40          # descriptor bit 6; bits 0/1/2 and DTE bit 7 keep their jobs
ROM_RAW_PREFIX_BOXES = (8, 17)
ROM_RAW_PREFIX_BIT = 0x20    # measured post-draw cursor overwrite of a nonzero cell
ROM_LONG_SOURCE_BOXES = (8, 14, 18, 29, 33, 34, 47)
ROM_LONG_SOURCE_BIT = 0x10   # source ends at $FF rather than descriptor width
ROM_POOL_BASE = 0xCB
ROM_POOL_END = 0xDE          # exclusive: nineteen contiguous tiles; $CA stays native
ROM_ONE_BASE = 0xC0
ROM_ONE_END = 0xC9           # one-row labels avoid the game's $D1-$D6 graphics reload
# Box 17 is the one-row header shown over three-row Pot contents.  `$C0-$C3` remain
# visible in the outgoing Items header and are repainted again by the returning Items
# header, while `$C5/$C6` belong to settled Item status cells.  `$C7/$C8` are absent at
# both endpoints, giving this exact header a disjoint two-tile generation.
ROM_POT_HEADER_BASE = 0xC7
ROM_POT_HEADER_CAP = 2
# Box 32 (Fay's co-resident "Which task?" prompt) cannot use $C0-$C8: completed
# quiz cells are native tile $C4.  Its measured eight-tile row uses a disjoint slice
# above the unstable $D1-$D6 range; menuromspill and structspill own this exception.
ROM_FEI_PROMPT_BASE = 0xD7
ROM_FEI_PROMPT_CAP = 8
# The one-row Rankings header paints five tiles. Its old generic $C0 base therefore
# ended on native tile $C4, and the completed-quiz checkbox stayed corrupted when the
# player returned through the title menu into Fay. It now enters directly through the
# unified Rankings allocation; Fay keeps its independently restored high-page slice.
ROM_RANK_HEADER_BASE = 0x80
ROM_RANK_HEADER_CAP = ROM_FEI_PROMPT_CAP

# Rankings is one screen-scoped allocation shared with rankvwf.  Its two-row category
# selector is the preceding temporal phase: $C0-$C3 for ``Kuyou`` and $C4-$CB for
# ``Village Exit``.  The complete native font reload restores this exact borrowed slice
# before the result map is revealed.  The helper lives in bank 46's prefix, formally
# excluded from pool.py's redirected-text allocator.
RANK_SCREEN_BANK = 0x2E
RANK_CATEGORY_INDEX = 0x05
RANK_CATEGORY_AT = 0x4100
RANK_CATEGORY_LIMIT = 0x4180
RANK_CATEGORY_ROW0_BASE = 0xC0
RANK_CATEGORY_ROW1_BASE = 0xC4

# Difficulty explanations remain simultaneous with the complete title, Log selector and
# box 29.  The real saved Log-3 route proved that the old $67-$7A slice was not actually
# screen-local: it was the live Rename/Rank+Pass/Replay/Log3 title range.  Keep every
# difficulty value in the high-page $E0-$F3 slice instead.  Cursor changes are published
# as an LCD-off transaction below, so Easy/Normal/Hard may safely reuse this one slice.
DIFFICULTY_POOL_BASE = 0xE0
DIFFICULTY_ROW0_CAP = 9
DIFFICULTY_ROW1_CAP = 11
DIFFICULTY_ALT_ROW0_BASE = DIFFICULTY_POOL_BASE
DIFFICULTY_ALT_ROW1_BASE = DIFFICULTY_POOL_BASE + DIFFICULTY_ROW0_CAP

# The saved-summary row blanker removes the outgoing tilemap references before each
# repaint, so all three Log selections can safely reuse one 9+10+8 screen-local block.
# $DE-$F8 is absent from the settled title/log map; startspill checks the *whole* range
# for outside owners whenever a summary is visible.
# This avoids the native $A4/$AF empty-box / separator tiles and $C4 completed checkbox
# without relying on a later font restore.  Row 1 genuinely needs nine tiles for both
# ``5 F Koma Cave`` (nine tiles) and numbered ``Dragon's Maw`` (ten tiles) forms.
SUMMARY_POOL_ROWS = (0xDE, 0xE7, 0xF1)
SUMMARY_POOL_CAPS = (9, 10, 8)
SUMMARY_ALT_POOL_ROWS = SUMMARY_POOL_ROWS
# Direct saved-title censuses prove $82-$8A and $9A-$A0 have no settled references
# outside box 27 while an erase confirmation is visible. Box 45 is mutually exclusive
# with that flow and has the same result, while its still-visible eighth title row owns
# $8B-$90. Keep these slices context-static rather than adding them to the global pool.
CONFIRM_POOL_ROWS = (0x82, 0x9A)
CONFIRM_POOL_CAPS = (9, 7)
RANKPASS_POOL_CAPS = (4, 5)

# A nested far call lets bank 32 read bank-31 source bytes without new bank-0 code or
# WRAM staging.  Bank 31's live index $03 normally points at $403F (draw a box); its
# gate preserves that behaviour for every ordinary A value and reserves $FE/$FF for
# one-byte reads through HL/BC.  build.py removes this exact range from bank 31's text
# repacker before install(), so the helper cannot be packed over by a later translation.
ROM_READ_INDEX = 0x03
ROM_READ_ORG = 0x459E
ROM_READ_OLD = bytes.fromhex('4e7b5d70619c260d310c234d6b6f9d37')
ROM_READ_SRC = """
readgate:
  cp $FF
  jr z,readbc
  cp $FE
  jr z,readhl
  jp $403F
readbc:
  ld a,[bc]
  inc bc
  ret
readhl:
  ld a,[hl+]
  ret
"""


START_SRC = """
startaux:
  and a
  jp z,startshape
  cp $01
  jp z,difficultyalloc
  cp $02
  jp z,$%04X
  cp $03
  jp z,$%04X
  cp $04
  jp z,$%04X
  ret

startshape:
  ld a,[$C69A]
  and a
  jr nz,sslog26
  ld a,[$C69B]
  cp $01
  jr nz,ssnone
  ld a,[$C69C]
  cp $03
  jr c,ssnone
  cp $09
  jr nc,ssnone
  ld a,[$C69D]
  cp $0B
  jr nz,ssnone
  ld a,[$C69E]
  cp $02
  jr nz,ssnone
  ld a,$01
  ret
sslog26:
  cp $04
  jr nz,sslog27
  ld a,[$C69B]
  cp $04
  jr nz,ssnone
  ld a,[$C69C]
  cp $03
  jr nz,ssnone
  ld a,[$C69D]
  cp $0E
  jr nz,ssnone
  ld a,[$C69E]
  cp $04
  jr nz,ssnone
  ld a,$02
  ret
sslog27:
  cp $03
  jr nz,ssnone
  ld a,[$C69B]
  cp $07
  jr nz,ssnone
  ld a,[$C69C]
  cp $02
  jr nz,ssnone
  ld a,[$C69D]
  cp $0F
  jr nz,ssnone
  ld a,[$C69E]
  and a
  jr nz,ssnone
  ld a,$02
  ret
ssnone:
  xor a
  rst $10
  db $%02X,$%02X
  ret

difficultyalloc:
  ld a,[$C69A]
  and a
  jr nz,danone
  ld a,[$C69B]
  cp $0D
  jr nz,danone
  ld a,[$C69C]
  cp $02
  jr nz,danone
  ld a,[$C69D]
  cp $12
  jr nz,danone
  ld a,[$C69E]
  and $1F
  jr nz,danone
  ld a,d
  and a
  jr nz,darow1
  ld a,[$C0D3]
  cp $%02X
  jr nc,dabad
  ld a,[$C69F]
  cp $%02X
  jr nz,da0base
  ld a,[$C6A0]
  cp $%02X
  jr nz,da0base
  ld a,$%02X
  jr daok
da0base:
  ld a,$%02X
  jr daok
darow1:
  cp $01
  jr nz,dabad
  ld a,[$C0D3]
  cp $%02X
  jr nc,dabad
  ld a,[$C69F]
  cp $%02X
  jr nz,da1base
  ld a,[$C6A0]
  cp $%02X
  jr nz,da1base
  ld a,$%02X
  jr daok
da1base:
  ld a,$%02X
daok:
  ld [$C0DB],a
  scf
  ret
dabad:
  ld a,$01
  and a
  ret
danone:
  xor a
  rst $10
  db $%02X,$%02X
  ret
"""


SELECTOR_SRC = """
selectorshape:
  push hl
  ld a,[$C69A]
  cp $05
  jr nz,selrankpass
  ld a,[$C69B]
  cp $09
  jr nz,sellogbad
  ld a,[$C69C]
  and a
  jr z,sellogbad
  cp $04
  jr nc,sellogbad
  ld a,[$C69D]
  cp $09
  jr nz,sellogbad
  ld a,[$C69E]
  and $1F
  cp $02
  jr nz,sellogbad
  ld a,b
  cp $C6
  jr nz,sellogbad
  ld h,b
  ld l,c
  ld a,[hl+]
  and a
  jr nz,sellogbad
  ld a,[hl+]
  cp $16
  jr nz,sellogbad
  ld a,[hl+]
  cp $33
  jr nz,sellogbad
  ld a,[hl+]
  cp $2B
  jr nz,sellogbad
  ld a,[hl]
  cp $02
  jr c,sellogbad
  cp $05
  jr nc,sellogbad
  ld a,$01
  pop hl
  ret
sellogbad:
  xor a
  pop hl
  ret
selrankpass:
  cp $03
  jr nz,selnone
  ld a,[$C69B]
  cp $08
  jr nz,selnone
  ld a,[$C69C]
  cp $02
  jr nz,selnone
  ld a,[$C69D]
  cp $06
  jr nz,selnone
  ld a,[$C69E]
  and $1F
  cp $02
  jr nz,selnone
  ld a,b
  cp $C6
  jr nz,selnone
  ld a,d
  and a
  jr z,selrank
  cp $01
  jr nz,selnone
  ld a,c
  cp $1C
  jr nz,selnone
  jr selrankok
selrank:
  ld a,c
  cp $16
  jr nz,selnone
selrankok:
  ld a,$02
  pop hl
  ret
selnone:
  xor a
  pop hl
  ret

"""


RANK_CATEGORY_SRC = """
rankcategoryalloc:
  ; All two-row ROM boxes retain the established allocator except the unique title
  ; Rankings category selector (y=7).  Its 4+8 queue footprints are consecutive,
  ; screen-local, and wholly restorable by the native $00-$D2 font loader.
  ld a,[$C69B]
  cp $07
  jr nz,categorygeneric
  ld a,d
  and a
  jr nz,categoryrow1
  ld a,[$C0D3]
  cp $05
  jr nc,categorybad
  ld a,$%02X
  jr categoryok
categoryrow1:
  cp $01
  jr nz,categorybad
  ld a,[$C0D3]
  cp $09
  jr nc,categorybad
  ld a,$%02X
  jr categoryok
categorygeneric:
  ld a,d
  and a
  jr nz,genericrow1
  ld a,[$C0D3]
  cp $09
  jr nc,categorybad
  ld a,$%02X
  jr categoryok
genericrow1:
  cp $01
  jr nz,categorybad
  ld a,[$C0D3]
  cp $0C
  jr nc,categorybad
  ld a,$%02X
categoryok:
  ld [$C0DB],a
  scf
  ret
categorybad:
  and a
  ret
""" % (RANK_CATEGORY_ROW0_BASE, RANK_CATEGORY_ROW1_BASE,
         ROM_POOL_BASE, ROM_POOL_BASE + 8)


SUMMARY_SRC = """
summaryalloc:
  ld a,[$C69A]
  cp $04
  jr z,sasummary
  cp $03
  jr nz,sanone
  xor a
  rst $10
  db $%02X,$%02X
  ret
sasummary:
  ld a,[$C69B]
  cp $04
  jr nz,sanone
  ld a,[$C69C]
  cp $03
  jr nz,sanone
  ld a,[$C69D]
  cp $0E
  jr nz,sanone
  ld a,[$C69E]
  and $1F
  cp $04
  jr nz,sanone
  ld a,d
  cp $03
  jr nc,sabad
  cp $01
  jr z,sasummary1
  and a
  jr nz,sasummary2
  ld a,[$C0D3]
  cp $0A
  jr nc,sabad
  ld c,$00
  jr saselect
sasummary2:
  ld a,[$C0D3]
  cp $09
  jr nc,sabad
  ld c,$02
  jr saselect
sasummary1:
  ld a,[$C0D3]
  cp $0B
  jr nc,sabad
  ld c,$01
saselect:
  ld a,[$C616]
  cp $03
  jr z,saalt
  cp $02
  jr z,saprimary
  cp $04
  jr nz,sabad
saprimary:
  ld hl,saprimarytab
  jr satable
saalt:
  ld hl,sasalttab
satable:
  ld b,$00
  add hl,bc
  ld a,[hl]
  ld [$C0DB],a
  scf
  ret
sabad:
  ld a,$01
  and a
  ret
sanone:
  xor a
  ret
saprimarytab:
  db $%02X,$%02X,$%02X
sasalttab:
  db $%02X,$%02X,$%02X
""" % ((CONFIRM_INDEX, CONFIRM_BANK) + SUMMARY_POOL_ROWS +
         SUMMARY_ALT_POOL_ROWS)


CONFIRM_SRC = """
confirmalloc:
  ld a,[$C69B]
  cp $07
  jr z,caconfirm
  cp $08
  jr z,carankpass
canone:
  xor a
  ret
caconfirm:
  ; startshape admitted only the exact box-27 descriptor.
  ld a,d
  cp $02
  jr nc,cabad
  and a
  jr z,carow0
  ld a,[$C0D3]
  cp $08
  jr nc,cabad
  ld c,$%02X
  jr caselect
carow0:
  ld a,[$C0D3]
  cp $0A
  jr nc,cabad
  ld c,$%02X
caselect:
  ld a,[$C616]
  cp $02
  jr z,caready
  cp $03
  jr z,caready
  cp $04
  jr nz,cabad
caready:
  ld a,c
  ld [$C0DB],a
  scf
  ret
carankpass:
  ; selectorshape admitted only the build-asserted box-45 descriptor and source.
  ; Recheck its physical cap, per-row source, and exact payload before allocation.
  push de
  ld a,d
  and a
  jr z,carank
  cp $01
  jr nz,cabadpop
  ld a,[$C0D3]
  cp $06
  jr nc,cabadpop
  ld hl,$C61C
  ld c,$%02X
  ld de,capass
  ld b,$06
  jr cacheck
carank:
  ld a,[$C0D3]
  cp $05
  jr nc,cabadpop
  ld hl,$C616
  ld c,$%02X
  ld de,carankdata
  ld b,$06
cacheck:
  ld a,[$C69F]
  cp l
  jr nz,cabadpop
  ld a,[$C6A0]
  cp h
  jr nz,cabadpop
caloop:
  ld a,[de]
  cp [hl]
  jr nz,cabadpop
  inc de
  inc hl
  dec b
  jr nz,caloop
  pop de
  ld a,c
  ld [$C0DB],a
  scf
  ret
cabadpop:
  pop de
  jr cabad
cabad:
  ld a,$01
  and a
  ret
carankdata:
  db $00,$1C,$25,$32,$2F,$FF
capass:
  db $00,$1A,$25,$37,$37,$FF
""" % (CONFIRM_POOL_ROWS[1], CONFIRM_POOL_ROWS[0],
         CONFIRM_POOL_ROWS[1], CONFIRM_POOL_ROWS[0])


START_BLANK_SRC = """
startblank:
  push hl
  push bc
  push de
  ld a,$05
  ld [$C1B1],a
  xor a
  ld [$C0D0],a
  ld a,[$C69B]
  cp $08
  jr nz,sbready
  ld a,$04
  ld [$C1B1],a
sbready:
  ldh a,[$FF40]
  bit 7,a
  jr z,sbdone
sbwait:
  ldh a,[$FF44]
  cp $90
  jr c,sbwait
  ld a,h
  ld d,h
  ld e,l
  inc de
  sub $2B
  ld h,a
  inc hl
  ld a,[$C69D]
  ld b,a
  xor a
sbcell:
  ld [de],a
  inc de
  ld [hl+],a
  dec b
  jr nz,sbcell
sbdone:
  pop de
  pop bc
  ld a,$FF
  rst $10
  db $%02X,$%02X
  pop hl
  ret
""" % (SUMMARY_HELPER_INDEX, SUMMARY_HELPER_BANK)


SUMMARY_HELPER_SRC = """
summaryhelper:
  cp $FE
  jr z,summaryrestore
  cp $FF
  jr z,summaryprep
  ; Producer call from 4:$6985. DE is the start of logical row 1 and A is the
  ; selected place-string key. Numbered rows always have the English F in payload cell
  ; two (even a one-digit floor has a blank cell zero); four zero prefix cells mean the
  ; place has no floor number and should not retain the native four-cell indent.
  push af
  ld a,[$C627]
  and a
  jr z,summaryproducerdone
  inc de
  inc de
  inc de
  inc de
summaryproducerdone:
  pop af
  ret

summaryprep:
  ; startblank calls this after restoring the native BC/DE. Ignore every shape except
  ; box 26, then normalize row 0 once or redirect row 1 when normalization was needed.
  ld a,[$C69A]
  cp $04
  ret nz
  ld a,[$C69B]
  cp $04
  ret nz
  ld a,d
  and a
  jr z,summarynormalize
  cp $01
  ret nz
  ld a,[$C647]
  and a
  ret z
  ld bc,$C648
  ret

summaryrestore:
  ; A long row is scanned from private staging, but the native box loop still expects
  ; both BC and its saved source pointer at the original row-2 source after a successful
  ; proportional return. Publishing the private pointer skips the difficulty row.
  ld a,[$C69A]
  cp $04
  ret nz
  ld a,d
  cp $01
  ret nz
  ld a,[$C647]
  and a
  ret z
  ld a,[$C645]
  ld c,a
  ld [$C69F],a
  ld a,[$C646]
  ld b,a
  ld [$C6A0],a
  ret

summarynormalize:
  ; C633 is the first payload cell of logical row 2. Nonzero here can only be the tail of a
  ; row-1 place name: intended difficulty text begins later after zero padding. Preserve
  ; the complete row in spare staging, then clear the tail *and its terminator* to spaces
  ; so row 2 can reach its own Hard/Normal/Easy field.
  ld a,[$C633]
  and a
  ret z
  push de
  ld hl,$C625
  ld de,$C648
summarycopy:
  ld a,[hl+]
  ld [de],a
  inc de
  cp $FF
  jr nz,summarycopy
  ld a,l
  ld [$C645],a
  ld a,h
  ld [$C646],a
  ld a,$01
  ld [$C647],a
  ld hl,$C633
summaryclear:
  ld a,[hl]
  ld [hl],$00
  inc hl
  cp $FF
  jr nz,summaryclear
  pop de
  ret
"""


# Seven 11-tile slices provide five live Item rows plus transition headroom. Mode 0
# chooses a run absent from the complete visible map (ordinary Action rows also use a
# small context-local run); mode 1
# commits one complete shadow row at a fresh VBlank, making its outgoing slice reusable;
# mode 2 pre-stages and commits an empty trailing row before native fallback advances the
# source.  The LCD stays on.  Index 7 retains the synchronous full-map publisher used by
# Rankings after it has disabled the LCD; the independent Floor/Info controller no longer
# calls that compatibility entry.
ITEM_PAGE_SRC = """
itempage:
  and a
  jr z,itemalloc
  cp $02
  jr z,itemblank
  rst $10
  db $%02X,$%02X
  ret
itemalloc:
  ld a,[$C1B1]
  cp $01
  jr z,itemrow
  xor a
  rst $10
  db $%02X,$%02X
  ret
itemrow:
  ld a,[$C0D0]
  cp $02
  jr nz,itemunused
  ; Only the exact five-row Items list and exact three-row Pot contents may enter the
  ; rolling ownership state machine.  Other raw-prefix-2 boxes retain the generic
  ; allocator and cannot mutate the persistent Item lifecycle.
  ld a,[$C69A]
  and a
  jr nz,itemunused
  ld a,[$C69B]
  cp $03
  jr nz,itemunused
  ld a,[$C69C]
  cp $03
  jr z,itemshape
  cp $05
  jr nz,itemunused
itemshape:
  ld a,[$C69D]
  cp $12
  jr nz,itemunused
  ld a,[$C69E]
  cp $02
  jr nz,itemunused
  ld a,[$C0D3]
  cp $0C
  ret nc
  ld a,[$C0D6]
  cp $05
  ret nc
  xor a
  rst $10
  db $%02X,$%02X
  ret nc
  ld c,$0B
  ret
itemblank:
  ld a,[$C1B1]
  cp $01
  jr nz,itemcommitblank
  ld a,[$C0D0]
  cp $02
  jr nz,itemcommitblank
  ld a,$02
  rst $10
  db $%02X,$%02X
itemcommitblank:
  ld a,$02
  rst $10
  db $%02X,$%02X
  ld a,$02
  rst $10
  db $%02X,$%02X
  ret
itemunused:
  xor a
  rst $10
  db $%02X,$%02X
  ret
publishmap:
  ; Rankings calls this entry with A=0 after disabling the LCD.  Its page finalizer
  ; still needs the old synchronous shadow publication and transaction-state clear;
  ; a queued/VBlank publisher cannot run while the LCD is off.
  ld [$C0D7],a
  ld hl,$C300
  ld de,$9800
  ld b,$12
ippubrow:
  ld c,$14
ippubcell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,ippubcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,ippubsrc
  inc h
ippubsrc:
  ld a,e
  add a,$0C
  ld e,a
  jr nc,ippubdest
  inc d
ippubdest:
  dec b
  jr nz,ippubrow
  ldh a,[$FF40]
  set 7,a
  ldh [$FF40],a
  ret
""" % (ITEM_VALIDATE_INDEX, ITEM_VALIDATE_BANK,
       ITEM_STATE_INDEX, ITEM_STATE_BANK,
       ITEM_CHOICE_INDEX, ITEM_CHOICE_BANK,
       ITEM_CHOICE_INDEX, ITEM_CHOICE_BANK,
       ITEM_COMMIT_INDEX, ITEM_COMMIT_BANK,
       FLOOR_INFO_INDEX, FLOOR_INFO_BANK,
       FLOOR_ALLOC_INDEX, FLOOR_ALLOC_BANK)


ITEM_STATE_SRC = """
itemstate:
  ld a,[$C1B1]
  cp $02
  jr z,istateaction
  and a
  jr nz,istateunused
  rst $10
  db $%02X,$%02X
  ret
istateaction:
  ld a,$02
  rst $10
  db $%02X,$%02X
  ret
istateunused:
  xor a
  rst $10
  db $%02X,$%02X
  ret
""" % (ITEM_MAIN_INDEX, ITEM_MAIN_BANK,
       ITEM_ACTION_INDEX, ITEM_ACTION_BANK,
       FLOOR_ALLOC_INDEX, FLOOR_ALLOC_BANK)


ITEM_ACTION_SRC = """
itemaction:
  ld a,[$C69B]
  cp $01
  jr nz,iaunused
  ld a,[$C0D6]
  cp $%02X
  ret nc
  ld e,a
  ld a,[$%04X]
  cp $%02X
  jr z,iactionready
  cp $%02X
  jr nz,iaunused
  ld a,e
  and a
  jr nz,iaunused
  rst $10
  db $%02X,$%02X
  jr nc,iaforced
  ld a,$%02X
  ld [$%04X],a
iactionready:
  ld a,[$C0D6]
  ld e,a
  ld d,$00
  ld hl,iactionbases
  add hl,de
  ld b,[hl]
  ld c,$04
  ld a,e
  cp $04
  jr c,iactiondone
  dec c
iactiondone:
  scf
  ret
iaforced:
  ld a,$01
  and a
  ret
iaunused:
  xor a
  rst $10
  db $%02X,$%02X
  ret
iactionbases:
  db %s
""" % (ITEM_ACTION_ROWS,
       ITEM_STATE_AT, ITEM_STATE_ACTION, ITEM_STATE_SETTLED,
       ITEM_VALIDATE_INDEX, ITEM_VALIDATE_BANK,
       ITEM_STATE_ACTION, ITEM_STATE_AT,
       FLOOR_ALLOC_INDEX, FLOOR_ALLOC_BANK,
       _asm_bytes(ITEM_ACTION_BASES))


# The exact three-row Pot screen first uses the Action-cancel release schedule
# T,R0,R1.  Its completed shadow map releases R2 as well, so normalize T into R2 before
# restoring the native low font.  Keeping the five reserved row owners as
# [R2,R0,R1,R3,R4] lets the ordinary cancel transition return to Items progressively
# without repainting a tile that the Pot map still exposes.
ITEM_POT_FINISH_SRC = """
potfinish:
  ld a,[$%04X]
  cp $%02X
  ret nz
  ; Content rows are at Y=3.  The following exact Pot header is the only Y=0 row while
  ; this lifecycle state is active, and its rborder hook is the full-screen boundary.
  ld a,[$C69B]
  and a
  ret nz
  ld hl,$C340
  ld [hl],$BA
  inc hl
  ld a,$BD
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl],$BB
  ld a,$03
  rst $10
  db $%02X,$%02X
  ld a,[$%04X]
  ld b,a
  xor a
  rst $10
  db $%02X,$%02X
  ret nc
  ld a,$05
  rst $10
  db $%02X,$%02X
  ld b,$25
  ld c,$02
  ld a,$80
  rst $10
  db $%02X,$%02X
  ld a,$FF
  ld [$%04X],a
  ld a,$%02X
  ld [$%04X],a
  ret
""" % (ITEM_STATE_AT, ITEM_STATE_POT,
       NATIVE_MAP_INDEX, NATIVE_MAP_BANK,
       ITEM_CONTEXT_AT, ITEM_MIGRATE_INDEX, ITEM_MIGRATE_BANK,
       ITEM_VALIDATE_INDEX, ITEM_VALIDATE_BANK,
       FIXED_RESTORE_INDEX, FIXED_RESTORE_BANK,
       ITEM_LOW_ROW_AT, ITEM_STATE_ACTION, ITEM_STATE_AT)


ITEM_MAIN_SRC = """
itemmain:
  ld a,[$C69B]
  and a
  jr nz,imunused
  ld a,[$C0D6]
  cp $04
  ret nc
  ld e,a
  ld a,[$C0D7]
  cp $04
  jr z,imsuppress
  cp $05
  jr z,imsuppress
  ld a,[$%04X]
  cp $%02X
  jr z,imsuppress
  cp $%02X
  jr z,imsuppress
  cp $%02X
  jr z,imainready
  cp $%02X
  jr z,imainstart
  cp $%02X
  jr nz,imunused
  ld a,e
  and a
  jr nz,imunused
  ld hl,imvirginrows
  ld de,$%04X
  ld b,$05
imvirgincopy:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,imvirgincopy
  ld a,$43
  ld [$%04X],a
  jr imainset
imainstart:
  ld a,e
  and a
  jr nz,imunused
  xor a
  rst $10
  db $%02X,$%02X
  jr nc,imforced
imainset:
  ld a,$%02X
  ld [$%04X],a
imainready:
  ld a,[$C0D6]
  ld e,a
  ld a,e
  cp $02
  jr nc,imainfixed
  add a,a
  add a,a
  ld b,a
  ld a,[$%04X]
  add a,b
  ld b,a
  jr imainbase
imainfixed:
  sub $02
  add a,a
  add a,a
  add a,$%02X
  ld b,a
imainbase:
  ld c,$04
  scf
  ret
imsuppress:
imforced:
  ld a,$01
  and a
  ret
imunused:
  xor a
  ret
itempotheader:
  ld a,[$%04X]
  cp $%02X
  ld a,$%02X
  jr z,iphstore
  ld a,$%02X
iphstore:
  ld [$C0DB],a
  ret
imvirginrows:
  db %s
""" % (ITEM_STATE_AT, ITEM_STATE_ACTION, ITEM_STATE_POT, ITEM_STATE_MAIN,
       ITEM_STATE_SETTLED, ITEM_STATE_INVALID,
       ITEM_ROWS_AT, ITEM_FREE_AT,
       ITEM_VALIDATE_INDEX, ITEM_VALIDATE_BANK,
       ITEM_STATE_MAIN, ITEM_STATE_AT,
       ITEM_FREE_AT, ITEM_ACTION_BASES[0],
       ITEM_STATE_AT, ITEM_STATE_POT, ROM_POT_HEADER_BASE, ROM_ONE_BASE,
       _asm_bytes(ITEM_MAIN_VIRGIN_ROWS))


ITEM_CHOICE_SRC = """
itemchoice:
  cp $02
  jr nz,ichoicepainted
  ld a,$01
  ld [$C0D5],a
  xor a
  jr ichoicenormal
ichoicepainted:
  xor a
  ld [$C0D5],a
ichoicenormal:
  ld a,[$C0D6]
  ld e,a
  and a
  jr nz,ichoicenext
  ld a,[$C0D7]
  cp $04
  jr z,iinfolowstart
  cp $05
  jr z,iinfohighstart
  ld a,[$%04X]
  cp $%02X
  jr z,ipagestart
  cp $%02X
  jr nz,ichoicenotaction
  ; Only the exact three-row Pot contents route enters the Pot lifecycle.  Five-row
  ; Items returns keep the ordinary Action-cancel allocator below.
  ld a,[$C69C]
  cp $03
  jr nz,icancelstart
  ld a,$07
  jr ichoicechecked
ichoicenotaction:
  cp $%02X
  jr z,imainentrystart
  ld a,$01
  and a
  ret
imainentrystart:
  ld a,$06
  jr ichoicechecked
iinfolowstart:
  ; Reuse Main-entry mode 6: it selects all five high slices except the persistent
  ; Action owner at ITEM_FREE_AT.  A fixed `$43` exclusion is wrong after paging.
  ld a,$06
  jr ichoicecall
iinfohighstart:
  ld a,$02
  jr ichoicefixedcall
ipagestart:
  ld a,$03
  jr ichoicechecked
icancelstart:
  ld a,$04
ichoicechecked:
  ld [$C0D4],a
  ld a,[$C0D5]
  ; The proportional renderer owns C0CC as its saved source-pointer low byte.
  ; Preserve the painted/blank flag on the stack while the validator uses C0D5.
  push af
  xor a
  rst $10
  db $%02X,$%02X
  ; POP does not alter the validator's carry result; B receives the saved flag.
  pop bc
  jr nc,ichoiceinvalid
  ld a,b
  ld [$C0D5],a
  ld a,[$C0D4]
  jr ichoicecall
ichoiceinvalid:
  ld a,$01
  and a
  ret
ichoicenext:
  ld a,[$%04X]
  cp $%02X
  jr z,ientrynext
  cp $%02X
  jr z,iinfolownext
  cp $%02X
  jr z,iinfohighnext
  cp $%02X
  jr z,ipagenext
  cp $%02X
  jr z,icancelnext
  cp $%02X
  jr z,icancelnext
  xor a
  ret
ientrynext:
  ld a,$06
  jr ichoicecall
iinfolownext:
  ld a,$06
  jr ichoicecall
iinfohighnext:
  ld a,$02
  jr ichoicefixedcall
icancelnext:
  ld a,$04
  jr ichoicecall
ipagenext:
  ld a,$03
ichoicecall:
  rst $10
  db $%02X,$%02X
  ret
ichoicefixedcall:
  rst $10
  db $%02X,$%02X
  ret
""" % (ITEM_STATE_AT, ITEM_STATE_SETTLED, ITEM_STATE_ACTION,
       ITEM_STATE_MAIN,
       ITEM_VALIDATE_INDEX, ITEM_VALIDATE_BANK,
       ITEM_STATE_AT, ITEM_STATE_ENTRY, ITEM_STATE_INFO_LOW,
       ITEM_STATE_INFO_HIGH, ITEM_STATE_PAGE, ITEM_STATE_CANCEL, ITEM_STATE_POT,
       ITEM_TRANSITION_INDEX, ITEM_TRANSITION_BANK,
       ITEM_FIXED_INDEX, ITEM_FIXED_BANK)


ITEM_TRANSITION_SRC = """
itemtransition:
  cp $07
  jr z,itpot
  cp $06
  jr z,itmainentry
  cp $04
  jr z,itcancel
itrotate:
  ld a,[$C0D6]
  and a
  jr nz,itrotateready
  ld a,$%02X
  ld [$%04X],a
itrotateready:
  ld a,[$C0D6]
  ld e,a
  call itrowptr
  ld a,[$%04X]
  ld b,a
  ld a,[hl]
  ld [$%04X],a
  ld [hl],b
  scf
  ret
itpot:
  ; Mode 7 is used only for row 0 of the exact three-row Pot contents screen.  Its
  ; following rows call the ordinary mode-4 continuation without changing this state.
  ld a,$%02X
  ld [$%04X],a
  jr itcancelbody
itcancel:
  ld a,[$C0D6]
  and a
  jr nz,itcancelnext
  ld a,$%02X
  ld [$%04X],a
itcancelbody:
  ld a,[$C0D5]
  and a
  ld a,$00
  jr nz,itcancellow
  or $80
itcancellow:
  ld [$%04X],a
  xor a
  ld e,a
  call itrowptr
  ld a,[hl]
  ld [$%04X],a
  ld b,$%02X
  ld [hl],b
  scf
  ret
itcancelnext:
  ld e,a
  call itrowptr
  ld a,[$%04X]
  ld b,a
  ld a,[hl]
  ld [$%04X],a
  ld [hl],b
  scf
  ret
itmainentry:
  ld a,[$C0D6]
  and a
  jr nz,itmainready
  ld a,$%02X
  ld [$%04X],a
itmainready:
  ld a,[$C0D6]
  ld c,a
  ld hl,itmainbases
itmainnext:
  ld b,[hl]
  inc hl
  ld a,[$%04X]
  cp b
  jr z,itmainnext
  ld a,c
  and a
  jr z,itmainstore
  dec c
  jr itmainnext
itmainstore:
  ld a,[$C0D6]
  ld e,a
  call itrowptr
  ld [hl],b
  scf
  ret
itrowptr:
  ld d,$00
  ld hl,$%04X
  add hl,de
  ret
itmainbases:
  db %s
""" % (ITEM_STATE_PAGE, ITEM_STATE_AT,
       ITEM_FREE_AT, ITEM_FREE_AT,
       ITEM_STATE_POT, ITEM_STATE_AT,
       ITEM_STATE_CANCEL, ITEM_STATE_AT,
       ITEM_LOW_ROW_AT, ITEM_CONTEXT_AT,
       ITEM_TRANSIENT_BASE,
       ITEM_CONTEXT_AT, ITEM_CONTEXT_AT,
       ITEM_STATE_ENTRY, ITEM_STATE_AT, ITEM_FREE_AT,
       ITEM_ROWS_AT, _asm_bytes(ITEM_HIGH_SLICES))


ITEM_FIXED_SRC = """
itemfixed:
  ld e,a
  ld a,[$C0D6]
  and a
  jr nz,ifixedprepared
  call ifixedclear
  ld a,e
  dec a
  jr z,ifixedlowinit
  ld a,$%02X
  ld [$%04X],a
  jr ifixedhigh
ifixedlowinit:
  ld a,$%02X
  ld [$%04X],a
  ld hl,ifixedlowbases
  jr ifixedselect
ifixedprepared:
  ld a,e
  dec a
  jr z,ifixedlow
ifixedhigh:
  xor a
  rst $10
  db $%02X,$%02X
  ret
ifixedlow:
  ld hl,ifixedlowbases
ifixedselect:
  ld a,[$C0D6]
  ld e,a
  ld d,$00
  add hl,de
  ld b,[hl]
  ld a,b
  cp $%02X
  jr nz,ifixedstore
  ld a,e
  ld [$%04X],a
ifixedstore:
  ld hl,$%04X
  add hl,de
  ld [hl],b
  scf
  ret
ifixedclear:
  ld hl,$%04X
  ld b,$05
  ld a,$FF
ifixedclearloop:
  ld [hl+],a
  dec b
  jr nz,ifixedclearloop
  ld [$%04X],a
  ret
ifixedlowbases:
  ; Low-generation proportional Info ends at $42, but its outgoing screen still maps a
  ; separate static $43-$45 row until ITEM_MAP settles.  Do not claim $43 early.
  db %s
""" % (ITEM_STATE_INFO_HIGH, ITEM_STATE_AT,
       ITEM_STATE_INFO_LOW, ITEM_STATE_AT,
       ITEM_INFO_CHOICE_INDEX, ITEM_INFO_CHOICE_BANK,
       ITEM_TRANSIENT_BASE, ITEM_LOW_ROW_AT,
       ITEM_ROWS_AT, ITEM_ROWS_AT, ITEM_LOW_ROW_AT,
       _asm_bytes(ITEM_INFO_LOW_ROWS))


ITEM_MAP_SRC = """
itemmap:
  ; Drain the pending native header upload before waiting for our first fresh VBlank.
  ; Without this, row 0 can be copied while that upload still owns the transfer queue.
  rst $18
  ld hl,$C340
  ld [hl],$BA
  inc hl
  ld a,$BD
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl],$BB
  ld hl,$C300
  ld de,$9800
  ld b,$04
imapbatch:
  push bc
  call imapwait
  ld b,$04
imaprow:
  ld c,$14
imapcell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,imapcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,imaphready
  inc h
imaphready:
  ld a,e
  add a,$0C
  ld e,a
  jr nc,imapdready
  inc d
imapdready:
  dec b
  jr nz,imaprow
  pop bc
  dec b
  jr nz,imapbatch
  scf
  ret
imapwait:
  ldh a,[$FF40]
  bit 7,a
  ret z
imapvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,imapvisible
imapblank:
  ldh a,[$FF44]
  cp $90
  jr c,imapblank
  ret
"""


ITEM_VALIDATE_SRC = """
itemvalidate:
  cp $03
  jr z,ivfindfree
  cp $05
  jr z,ivlowowner
  cp $06
  jr z,ivlowtarget
  cp $FE
  jr z,ivinit
  ld hl,$%04X
  ld b,$06
  xor a
  ld [$C0D5],a
ivnext:
  ld a,[hl+]
  ld e,a
  push hl
  ld hl,ivbases
  ld c,$06
  ld d,$01
ivfind:
  ld a,[hl+]
  cp e
  jr z,ivfound
  sla d
  dec c
  jr nz,ivfind
  jr ivinvalid
ivfound:
  ld a,[$C0D5]
  and d
  jr nz,ivinvalid
  ld a,[$C0D5]
  or d
  ld [$C0D5],a
  pop hl
  dec b
  jr nz,ivnext
  scf
  ret
ivinvalid:
  pop hl
  ld a,$%02X
  ld [$%04X],a
  ld a,$01
  and a
  ret
ivfindfree:
  ld hl,ivbases
  ld c,$06
ivfnext:
  ld b,[hl]
  inc hl
  push hl
  ld hl,$%04X
  ld d,$05
ivfrow:
  ld a,[hl+]
  cp b
  jr z,ivfused
  dec d
  jr nz,ivfrow
  pop hl
  scf
  ret
ivfused:
  pop hl
  dec c
  jr nz,ivfnext
  xor a
  ret
ivlowowner:
  ld a,[$%04X]
  and $7F
  ld e,a
  ld d,$00
  ld hl,$%04X
  add hl,de
  ld a,[$C0D4]
  ld [hl],a
  scf
  ret
ivlowtarget:
  ld a,[$%04X]
  cp $%02X
  jr nz,ivfindfree
  ld a,[$%04X]
  ld b,a
  scf
  ret
ivinit:
  ld hl,$%04X
  ld b,$07
  ld a,$FF
ivinitloop:
  ld [hl+],a
  dec b
  jr nz,ivinitloop
  ld a,$%02X
  ld [$%04X],a
  ret
ivbases:
  db %s
""" % (ITEM_ROWS_AT, ITEM_STATE_INVALID, ITEM_STATE_AT,
       ITEM_ROWS_AT,
       ITEM_LOW_ROW_AT, ITEM_ROWS_AT,
       ITEM_STATE_AT, ITEM_STATE_CANCEL, ITEM_CONTEXT_AT,
       ITEM_ROWS_AT, ITEM_STATE_INVALID, ITEM_STATE_AT,
       _asm_bytes(ITEM_HIGH_SLICES))


ITEM_INFO_CHOICE_SRC = """
iteminfochoice:
  ld a,[$C0D5]
  ; Scan already saved this row's next source pointer at C0CC/C0CD.  Keep the
  ; painted/blank flag on the stack instead of corrupting that renderer state.
  push af
  ld a,[$C0D6]
  ld c,a
  ld hl,$%04X
  ld b,$05
  ld de,$0000
iicsum:
  ld a,[hl+]
  ld [$C0D4],a
  add a,e
  ld e,a
  ld a,c
  and a
  jr z,iicnorelease
  dec c
  ld a,[$C0D4]
  add a,d
  ld d,a
iicnorelease:
  dec b
  jr nz,iicsum
  ld a,d
  add a,$43
  ld [$C0D4],a
  ld a,e
  add a,$43
  ld [$C0D5],a
  ld hl,iiccandidates
  ld c,$%02X
iicnext:
  ld b,[hl]
  inc hl
  push hl
  ld hl,$%04X
  ld a,[$C0D6]
  ld d,a
iicusedloop:
  ld a,d
  and a
  jr z,iicunused
  ld a,[hl+]
  cp b
  jr z,iicused
  dec d
  jr iicusedloop
iicunused:
  ld a,b
  cp $%02X
  jr z,iicchoose
  add a,$0B
  ld e,a
  ld a,[$C0D4]
  cp e
  jr nc,iicchoose
  ld a,[$C0D5]
  cp b
  jr z,iicchoose
  jr c,iicchoose
iicused:
  pop hl
  dec c
  jr nz,iicnext
  pop af
  ld a,$01
  and a
  ret
iicchoose:
  pop hl
  ld a,[$C0D6]
  ld e,a
  ld d,$00
  ld hl,$%04X
  add hl,de
  ld [hl],b
  ld a,b
  cp $%02X
  jr z,iictransient
  ; Discard the saved flag on ordinary high-slice success.
  pop af
  jr iicready
iictransient:
  ; Consume the saved flag only when recording transient ownership.
  pop af
  and a
  ld a,e
  jr nz,iiclowready
  or $80
iiclowready:
  ld [$%04X],a
iicready:
  scf
  ret
iiccandidates:
  ; State 5 is reachable only from odd/high Info pages.  Action rows use disjoint
  ; context-local tiles, so the live-interval proof only needs to avoid outgoing Info.
  db %s
""" % (ITEM_CONTEXT_AT, len(ITEM_INFO_HIGH_CANDIDATES),
       ITEM_ROWS_AT, ITEM_TRANSIENT_BASE,
       ITEM_ROWS_AT, ITEM_TRANSIENT_BASE, ITEM_LOW_ROW_AT,
       _asm_bytes(ITEM_INFO_HIGH_CANDIDATES))


ITEM_COMMIT_SRC = """
itemcommit:
  dec a
  jr z,icommit
  dec a
  jr z,itemempty
  dec a
  jr z,iforced
  ret
itemempty:
  ld a,[$C1B1]
  cp $01
  ret nz
  ld a,[$C0D0]
  cp $02
  ret nz
  ld a,[$C0D9]
  ld l,a
  ld a,[$C0DA]
  ld h,a
  ld a,[$C0E0]
  ld [hl+],a
  ld a,[$C0E1]
  ld [hl+],a
  ld c,$11
  xor a
perow:
  ld [hl+],a
  dec c
  jr nz,perow
  ld [hl],$BF
icommit:
  ld a,[$C1B1]
  cp $01
  jr z,irowcommit
  cp $04
  ret nz
  ld a,[$C0D9]
  cp $20
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,[$C69D]
  cp $04
  jr z,iitemsheader
  ; The exact Pot header is one cell narrower.  Its completed rborder is the Pot
  ; lifecycle's map-publication and transient-normalization boundary.
  ld a,$01
  rst $10
  db $%02X,$%02X
  ret
iitemsheader:
  xor a
  rst $10
  db $%02X,$%02X
  ret
irowcommit:
  ld a,[$C0D0]
  cp $02
  ret nz
  ld a,[$C0D9]
  ld l,a
  ld a,[$C0DA]
  ld h,a
  ; Screen 1 restores the Item selection in C6A5 before any returned row is drawn.
  ; Stage its cursor before every complete-row commit. C0D6 is composer scratch by
  ; this point, so derive the destination directly instead of comparing row numbers.
  push hl
  ld a,[$C6A5]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld de,$C382
  add hl,de
  ld [hl],$81
  pop hl
  ld e,l
  ld a,h
  sub $2B
  ld d,a
  jr icwait
iforced:
  ld a,l
  and $E0
  ld l,a
  ld e,a
  ld a,h
  sub $2B
  ld d,a
icwait:
  ldh a,[$FF40]
  bit 7,a
  jr z,icopy
  ; Always begin at line 144, rather than risking a call late in an existing VBlank.
icwaitvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,icwaitvisible
icwaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,icwaitblank
icopy:
  ld c,$14
icopycell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,icopycell
  ret
"""
ITEM_COMMIT_SRC %= (ITEM_POT_FINISH_INDEX, ITEM_POT_FINISH_BANK,
                    ITEM_FINISH_INDEX, ITEM_FINISH_BANK)


ITEM_FINISH_SRC = """
itemfinish:
  ld a,[$%04X]
  cp $%02X
  ret z
  cp $%02X
  ret z
  ; At the Item-header boundary the native shadow is complete except for its bottom
  ; border and page indicator.  Stage the pager, then reveal rows 0-15 in four
  ; VBlanks before any transition-only glyph slice is retired.
  ld hl,$C36F
  ld a,$C5
  ld b,$04
ifpagerclear:
  ld [hl+],a
  dec b
  jr nz,ifpagerclear
  ld a,[$C6AC]
  cp $14
  ret nc
  ld b,$FF
ifpagerindex:
  inc b
  sub $05
  jr nc,ifpagerindex
  ld e,b
  ld d,$00
  ld hl,$C36F
  add hl,de
  ld [hl],$C6
  xor a
  rst $10
  db $%02X,$%02X
  ret nc
  ld a,[$%04X]
  cp $FF
  jr z,ifnormalized
  ld a,$06
  rst $10
  db $%02X,$%02X
  ret nc
  ld a,[$%04X]
  bit 7,a
  jr z,ifowneronly
  xor a
  rst $10
  db $%02X,$%02X
  ret nc
  jr ifsetowner
ifowneronly:
  ld a,b
  ld [$C0D4],a
ifsetowner:
  ld a,$05
  rst $10
  db $%02X,$%02X
ifnormalized:
  ld a,[$%04X]
  cp $%02X
  jr z,iffindfree
  cp $%02X
  jr nz,iffreeready
iffindfree:
  ld a,$03
  rst $10
  db $%02X,$%02X
  jr nc,iffreeready
  ld a,b
  ld [$%04X],a
iffreeready:
  ld a,[$C0D7]
  cp $04
  jr z,iffullrestore
  cp $05
  jr z,iffullrestore
  ld a,[$%04X]
  cp $FF
  jr z,ifsettle
  bit 7,a
  jr z,ifsettle
  ld b,$25
  ld c,$02
  jr ifrestore
iffullrestore:
  ld b,$04
  ld c,$07
ifrestore:
  ld a,$80
  rst $10
  db $%02X,$%02X
  xor a
  ld [$C0D7],a
ifsettle:
  ld a,$FF
  ld [$%04X],a
  ld a,$%02X
  ld [$%04X],a
  ret
""" % (ITEM_STATE_AT, ITEM_STATE_SETTLED, ITEM_STATE_INVALID,
       ITEM_MAP_INDEX, ITEM_MAP_BANK,
       ITEM_LOW_ROW_AT, ITEM_PAGE_INDEX, ITEM_PAGE_BANK,
       ITEM_LOW_ROW_AT,
       ITEM_MIGRATE_INDEX, ITEM_MIGRATE_BANK,
       ITEM_PAGE_INDEX, ITEM_PAGE_BANK,
       ITEM_STATE_AT, ITEM_STATE_INFO_LOW, ITEM_STATE_INFO_HIGH,
       ITEM_PAGE_INDEX, ITEM_PAGE_BANK, ITEM_FREE_AT,
       ITEM_LOW_ROW_AT, FIXED_RESTORE_INDEX, FIXED_RESTORE_BANK,
       ITEM_LOW_ROW_AT, ITEM_STATE_SETTLED, ITEM_STATE_AT)


ITEM_MIGRATE_SRC = """
itemmigrate:
  ld a,b
  ld [$C0D4],a
  ld a,[$C1B2]
  and a
  ret z
  ld c,a
  ld hl,$C163
imrecord:
  ld a,[hl+]
  ld [$C0CC],a
  ld a,[hl+]
  ld [$C0CD],a
  ld a,[hl]
  cp $%02X
  jr z,imfound
  inc hl
  inc hl
  inc hl
  dec c
  jr nz,imrecord
  xor a
  ret
imfound:
  ld a,[$C0D4]
  ld [hl],a
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  bit 3,a
  jr z,imlowtarget
  add a,$80
  jr imtargetready
imlowtarget:
  add a,$90
imtargetready:
  ld h,a
  ld d,h
  ld e,l
  ld hl,$9250
  call imwait
  ld c,$60
imcopyfirst:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,imcopyfirst
  call imwait
  ld c,$50
imcopylast:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,imcopylast
  ld a,[$C0CC]
  add a,$03
  ld l,a
  ld e,a
  ld a,[$C0CD]
  ld h,a
  sub $2B
  ld d,a
  ld b,$0B
imtranslate:
  ld a,[hl]
  sub $%02X
  cp $0B
  jr nc,imnext
  ld c,a
  ld a,[$C0D4]
  add a,c
  ld [hl],a
imnext:
  inc hl
  dec b
  jr nz,imtranslate
  call imwait
  ld a,[$C0CC]
  add a,$03
  ld l,a
  ld e,a
  ld a,[$C0CD]
  ld h,a
  sub $2B
  ld d,a
  ld c,$0B
immap:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,immap
  scf
  ret
imwait:
  ldh a,[$FF40]
  bit 7,a
  ret z
imwaitvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,imwaitvisible
imwaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,imwaitblank
  ret
""" % (ITEM_TRANSIENT_BASE, ITEM_TRANSIENT_BASE)


# Floor Action and Info use two fixed Info generations.  Low Info owns the native
# fixed-font IDs $04-$42; high Info owns the 57-tile proportional run $43-$7B.  Row 0
# switches generation and clears the five saved caps before any pixels are uploaded.
# Painted rows are committed as complete aligned 20-cell rows with the LCD on.  The last
# row stages the native border/pager and invokes bank 4's four-VBlank full-map producer.
#
# Returning Info first draws a transient screen-0 picker at C320/C360/C3A0/C3E0 (and
# C420/C460 for taller shapes).  It must never be published: state 4/5 makes the Item Main
# allocator force native fallback for that shadow-only draw.  The real screen-20 Action
# rows at C38D/C3CD/C40D/C44D/C48D/C4CD then publish progressively.  Each aligned commit
# releases the matching outgoing Info row, so high-return Action can use the deterministic
# bases $9A,$9E,$43,$47,$4B,$4F without a low-tile fallback.  install() exhaustively proves
# every built Info page has cap(row0)+cap(row1) >= 12, which is stronger than the 4/8/12
# released-prefix requirements for rows 2/3/4; row 5 begins after all five Info rows have
# been committed.  Low Info's fixed font is restored only after the completed map no
# longer references it.
FLOOR_INFO_SRC = """
floorinfo:
  and a
  jr z,fipre
  rst $10
  db $%02X,$%02X
  ret
fipre:
  ld a,d
  and a
  ret nz
  ld a,[$C1B1]
  cp $03
  jr z,fihelp
  and a
  ret nz
  ; Only the transient screen-0 x0 action shape may convert settled Info to return state.
  ld a,[$C0D9]
  cp $20
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,[$C69A]
  or a
  ret nz
  ld a,[$C69B]
  or a
  ret nz
  ld a,[$C69D]
  cp $05
  ret nz
  ld a,[$C69E]
  cp $02
  ret nz
  ld a,[$C0D7]
  cp $02
  jr z,fireturnlow
  cp $03
  ret nz
  ld a,$05
  jr fistore
fireturnlow:
  ld a,$04
fistore:
  ld [$C0D7],a
  ret
fihelp:
  ld a,[$C0D9]
  cp $80
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,[$C69A]
  or a
  ret nz
  ld a,[$C69B]
  cp $03
  ret nz
  ld a,[$C69C]
  cp $05
  ret nz
  ld a,[$C69D]
  cp $12
  ret nz
  ld a,[$C69E]
  or a
  ret nz
  ; The row scanner still owns BC (source) and HL (shadow destination) here.
  push bc
  push hl
  ld a,[$C0D7]
  cp $02
  ld a,$03
  jr z,fihelpstate
  ld a,$02
fihelpstate:
  ld [$C0D7],a
  cp $03
  ld a,$04
  jr nz,fiwatermark
  ld a,$43
fiwatermark:
  ld [$C1AE],a
  ld hl,$C1BB
  ld b,$05
  xor a
ficlearcaps:
  ld [hl+],a
  dec b
  jr nz,ficlearcaps
  pop hl
  pop bc
  ret
""" % (FLOOR_INFO_POST_INDEX, FLOOR_INFO_POST_BANK)


FLOOR_INFO_POST_SRC = """
floorpost:
  dec a
  jr z,fppainted
  dec a
  jp z,fpempty
  ret
fppainted:
  ld a,[$C1B1]
  cp $03
  jr z,fphelpcheck
  cp $02
  jr z,fpactioncheck
  ; Mode 1 is an earlier, incomplete header pass.  The same row arrives complete in
  ; mode 2; publishing the first pass exposes partially drawn Action text.
  ret
fpactioncheck:
  ld a,[$C0D7]
  sub $04
  cp $02
  ret nc
  ; Info is always the final Action choice.  Native restores its cursor only after
  ; the text rows, so put the cursor in that last row before the atomic map commit.
  ld a,[$C69C]
  dec a
  cp d
  jr nz,fpcommit
  ; Post-render HL is six cells past the Action key; its cursor is key+1.
  ld a,l
  sub $05
  ld l,a
  ld [hl],$81
  jr fpcommit
fphelpcheck:
  ld a,[$C0D7]
  sub $02
  cp $02
  ret nc
fpcommit:
  ; ITEM_COMMIT mode 3 clobbers AF/C/DE/HL but deliberately preserves B.
  ld b,d
  ld a,$03
  rst $10
  db $%02X,$%02X
  ld a,[$C1B1]
  cp $03
  jr z,fphelpafter
  ld a,[$C69C]
  dec a
  cp b
  ret nz
  ld a,$02
  call fpcallfinish
  ld a,[$C0D7]
  cp $04
  call z,fprestore
  xor a
  ld [$C0D7],a
  ret
fphelpafter:
  ld a,b
  cp $04
  ret nz
  xor a
  call fpcallfinish
  ld a,[$C0D7]
  cp $03
  ret nz
  jp fprestore
fpempty:
  ld a,[$C1B1]
  cp $03
  ret nz
  ld a,[$C0D7]
  sub $02
  cp $02
  ret nc
  ld a,d
  cp $04
  ret nz
  ld a,$01
  call fpcallfinish
  ld a,[$C0D7]
  cp $03
  ret nz
  jp fprestore
fpcallfinish:
  push af
  xor a
  ld [$C6A1],a
  ld a,$12
  ld [$C6A2],a
  pop af
  rst $10
  db $%02X,$%02X
  ret
fprestore:
  ld b,$04
  ld c,$07
  ld a,$80
  rst $10
  db $%02X,$%02X
  ret
""" % (ITEM_COMMIT_INDEX, ITEM_COMMIT_BANK,
       FLOOR_INFO_FINISH_INDEX, FLOOR_INFO_FINISH_BANK,
       FIXED_RESTORE_INDEX, FIXED_RESTORE_BANK)


FLOOR_ALLOC_SRC = """
flooralloc:
  ld a,[$C0D7]
  sub $02
  cp $04
  jr c,facontext
  xor a
  ret
facontext:
  ld e,a
  ld a,[$C1B1]
  cp $03
  jr z,fainfo
  cp $02
  jr nz,famodeother
  bit 1,e
  jr z,fainfo
  jr faaction
famodeother:
  cp $01
  jp z,faheader
  xor a
  ret
fainfo:
  ld a,[$C0D7]
  cp $02
  ld e,$43
  jr z,fainfostate
  cp $03
  jr nz,faforce
  ld e,$7C
fainfostate:
  ld a,d
  cp $05
  jr nc,faforce
  ld a,[$C1AE]
  ld b,a
  add a,c
  cp e
  jr c,fastoreinfo
  jr nz,faforce
fastoreinfo:
  ld [$C1AE],a
  ld e,d
  ld d,$00
  ld hl,$C1BB
  add hl,de
  ld [hl],c
  scf
  ret
faaction:
  ld a,[$C0D7]
  cp $04
  jr z,faactionstate
  cp $05
  jr nz,faforce
faactionstate:
  ld a,c
  cp $04
  jr nz,faforce
  ld a,d
  cp $06
  jr nc,faforce
  ld e,a
  ld d,$00
  ld hl,falowbases
  ld a,[$C0D7]
  cp $04
  jr z,faactionbase
  ld hl,fahighbases
faactionbase:
  add hl,de
  ld b,[hl]
  scf
  ret
faforce:
  ld a,$01
  and a
  ret
faheader:
  bit 1,e
  jr z,faforce
faheaderstate:
  ld a,[$C69E]
  cp $20
  jr nz,faforce
  ld a,d
  or a
  jr nz,faforce
  ld a,c
  cp $0C
  jr nc,faforce
  ld b,$8B
  scf
  ret
falowbases:
  db $43,$47,$4B,$4F,$53,$57
fahighbases:
  db $9A,$9E,$43,$47,$4B,$4F
"""


# Bank 13's native menu font and propvwf's bank-32 shift-0 source are byte-identical for
# codes $04-$42.  A magic guarded menurow entry below exposes one source byte at a time to
# this other-bank helper.  Each mode-$0A pass uploads exactly nine complete 2bpp tiles.
# ABI: B=first tile ID, C=number of nine-tile batches.  Thus $25,2 restores $25-$36 and
# $04,7 restores the complete $04-$42 native font.  C000/C001 are put back afterward.
FIXED_RESTORE_SRC = """
fixedrestore:
  push af
  push bc
  push de
  push hl
  ld a,[$C000]
  push af
  ld a,[$C001]
  push af
frbatch:
  ld a,[$C11A]
  and a
  jr z,frbuild
  call $06F7
  jr frbatch
frbuild:
  push bc
  ld l,b
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  add a,$44
  ld h,a
  ld c,$09
  ld de,$C008
frtile:
  push bc
  ld b,$08
frbyte:
  ld a,$FD
  rst $10
  db $%02X,$%02X
  ld [de],a
  inc de
  ld [de],a
  inc de
  dec b
  jr nz,frbyte
  pop bc
  dec c
  jr z,frbuilt
  ld a,c
  cp $05
  jr z,frskip
  cp $01
  jr nz,frstride
frskip:
  inc de
  inc de
frstride:
  ld a,l
  add a,$78
  ld l,a
  jr nc,frtile
  inc h
  jr frtile
frbuilt:
  pop bc
  ld a,b
  swap a
  and $F0
  ld l,a
  ld a,b
  swap a
  and $0F
  add a,$90
  ld h,a
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  ld de,$0040
  add hl,de
  ld a,l
  ld [$C048],a
  ld a,h
  ld [$C049],a
  add hl,de
  ld a,l
  ld [$C08A],a
  ld a,h
  ld [$C08B],a
  ld a,$0A
  ld [$C11A],a
  call $06F7
  ld a,b
  add a,$09
  ld b,a
  dec c
  jp nz,frbatch
  pop af
  ld [$C001],a
  pop af
  ld [$C000],a
  pop hl
  pop de
  pop bc
  pop af
  ret
""" % (FAR_INDEX, FAR_BANK)


FLOOR_INFO_FINISH_SRC = """
floorinfofinish:
  cp $02
  jr z,fiaction
  and a
  jr z,fihelpbottom
  ld hl,$C480
  ld [hl],$BE
  inc hl
  ld b,$12
  xor a
fiemptycells:
  ld [hl+],a
  dec b
  jr nz,fiemptycells
  ld [hl],$BF
fihelpbottom:
  ld hl,$C4A0
  ld [hl],$BA
  inc hl
  ld b,$12
fiedge:
  ld [hl],$BD
  inc hl
  dec b
  jr nz,fiedge
  ld [hl],$BB
  ld a,[$C6BD]
  cp $01
  jr z,fihelppublish
  inc a
  ld [$C4B2],a
  ld a,[$C6BC]
  add a,$02
  ld [$C4B0],a
  ld a,$B0
  ld [$C4B1],a
  ld a,[$C6BC]
  inc a
  ld hl,$C6BD
  cp [hl]
  jr nc,fihelppublish
  ld hl,$C4A9
  ld [hl],$98
  inc hl
  ld [hl],$99
fihelppublish:
  ld a,$03
  jr fipublish
fiaction:
  ; Info's four-row body leaves its bottom border at shadow row 11. Pickers with
  ; five or six choices continue below it, so convert that stale edge to an
  ; interior spacer and pre-stage the real bottom at row 13 or 15. Four-choice
  ; pickers end on row 11. Three-choice native staging reaches row 9 only after
  ; this finalizer, so pre-stage that bottom too before publishing the map.
  ld a,[$C69C]
  cp $03
  jr nz,fiactiontall
  ld hl,$C46D
  xor a
  ld b,$07
fiactionclear:
  ld [hl+],a
  dec b
  jr nz,fiactionclear
  ; Clearing through C473 leaves H=$C4, so only L must move to row 9 x13.
  ld l,$2D
  jr fiactiondraw
fiactiontall:
  cp $05
  jr c,fiactionnormal
  ld hl,$C46D
  ld [hl],$BE
  inc hl
  ld b,$05
  xor a
fipotcells:
  ld [hl+],a
  dec b
  jr nz,fipotcells
  ld [hl],$BF
  ld a,[$C69C]
  cp $05
  jr nz,fiactionsix
  ; The spacer setup above already established H=$C4.
  ld l,$AD
  jr fiactiondraw
fiactionsix:
  ld l,$ED
  jr fiactiondraw
fiactionnormal:
  ld hl,$C46D
fiactiondraw:
  ld [hl],$BA
  inc hl
  ld b,$05
fiactionedge:
  ld [hl],$BD
  inc hl
  dec b
  jr nz,fiactionedge
  ld [hl],$BB
  xor a
fipublish:
  rst $10
  db $%02X,$%02X
  ret
""" % (NATIVE_MAP_INDEX, NATIVE_MAP_BANK)


# Title/file screens are composites, not independent boxes: the parent title remains
# visible behind Log selection, difficulty, summaries and Rank/Pass. Their VWF tile
# lifetimes therefore have to be changed atomically.  Mode 0 starts an exact allowlisted
# multi-row transaction (or the Rankings transaction) before row 0 changes any pixels.
# The finalizer below pre-stages the native bottom border and publishes the complete
# 20x18 shadow map. C0D7 states $10-$14 stay disjoint from Floor/Info states 2-5;
# Items use the separate C1BA lifecycle range $A0-$A9.
START_TRANSITION_SRC = """
starttransition:
  push af
  push bc
  push de
  push hl
  ld a,d
  and a
  jp nz,stdone
  ; A full title redraw is a fresh ownership epoch even when Quit left gameplay's
  ; unrelated value in the shared transaction byte.  Non-title row-0 shapes are a
  ; no-op here and continue to preserve active popup/background transactions.
  xor a
  rst $10
  db $%02X,$%02X
  ld a,[$C0D7]
  and a
  jp nz,stdone
  xor a
  rst $10
  db $%02X,$%02X
  and a
  jr nz,stgeneric
  ; Difficulty choice box 29 starts a composite ending at explanation box 48.
  ld a,[$C69A]
  cp $0C
  jr nz,strank
  ld a,[$C69B]
  cp $06
  jr nz,stdone
  ld a,[$C69C]
  cp $03
  jr nz,stdone
  ld a,[$C69D]
  cp $06
  jr nz,stdone
  ld a,[$C69E]
  cp $50
  jr nz,stdone
  ld a,$11
  jr stoff
strank:
  ; Rankings header box 41 can switch to the title-prepared blank map without
  ; stopping the native VBlank queue used by the fixed score/floor fields.
  ld a,[$C69A]
  cp $05
  jr nz,stdone
  ld a,[$C69B]
  or a
  jr nz,stdone
  ld a,[$C69C]
  cp $01
  jr nz,stdone
  ld a,[$C69D]
  cp $08
  jr nz,stdone
  ld a,$12
  ld [$C0D7],a
  ldh a,[$FF40]
  set 3,a
  ld [$C110],a
  ldh [$FF40],a
  jr stdone
stgeneric:
  ld a,$10
stoff:
  ld [$C0D7],a
  ldh a,[$FF40]
  bit 7,a
  jr z,stdone
stwait:
  ldh a,[$FF44]
  cp $90
  jr c,stwait
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
  ; The title owns the otherwise-unused $9C00 BG map as a guaranteed blank page.
  ; Rankings keeps the LCD/queue running by displaying this page while rebuilding
  ; $9800, then flips back only when the complete Rankings page is ready.
  ld hl,$9C00
  ld bc,$0400
  ld d,$00
stclearmap:
  ld a,d
  ld [hl+],a
  dec bc
  ld a,b
  or c
  jr nz,stclearmap
stdone:
  pop hl
  pop de
  pop bc
  pop af
  ret
""" % (START_ALLOC_INDEX, START_FINISH_BANK, START_AUX_INDEX, START_AUX_BANK)


START_FINISH_SRC = """
startfinish:
  push af
  push bc
  push de
  push hl
  ld a,[$C0D7]
  cp $10
  jr z,sfgeneric
  cp $11
  jr z,sfdifficulty
  cp $13
  jr z,sffei
  jr sfdone
sfgeneric:
  ld a,d
  inc a
  ld b,a
  ld a,[$C69C]
  cp b
  jr nz,sfdone
  jr sfpublish
sfdifficulty:
  ld a,[$C69A]
  or a
  jr nz,sfdone
  ld a,[$C69B]
  cp $0D
  jr nz,sfdone
  ld a,[$C69C]
  cp $02
  jr nz,sfdone
  ld a,[$C69D]
  cp $12
  jr nz,sfdone
  ld a,d
  cp $01
  jr nz,sfdone
  jr sfpublish
sffei:
  ; Fay box 32 is the final one-row prompt in screen 17.
  ld a,[$C69A]
  or a
  jr nz,sfdone
  ld a,[$C69B]
  cp $0F
  jr nz,sfdone
  ld a,[$C69C]
  cp $01
  jr nz,sfdone
  ld a,[$C69D]
  cp $12
  jr nz,sfdone
sfpublish:
  ; HL points at the current row's right border.  Move to the next row's left
  ; edge and pre-stage the exact native bottom border before the atomic map copy.
  ld a,[$C69D]
  inc a
  ld b,a
sfleft:
  dec hl
  dec b
  jr nz,sfleft
  ld de,$0020
  add hl,de
  ld [hl],$BA
  inc hl
  ld a,[$C69D]
  ld b,a
sfedge:
  ld [hl],$BD
  inc hl
  dec b
  jr nz,sfedge
  ld [hl],$BB
  xor a
  rst $10
  db $%02X,$%02X
sfdone:
  pop hl
  pop de
  pop bc
  pop af
  ret

titlealloc:
  ld a,[$C69A]
  and a
  ret nz
  ld a,[$C69B]
  cp $01
  ret nz
  xor a
  ld [$C0D7],a
rankrestorehook:
  ; rankvwf replaces these five NOPs with mode 2 of the screen manager.  Keeping the
  ; placeholder inert means --no-rankvwf controls retain the ordinary menu renderer.
  nop
  nop
  nop
  nop
  nop
  rst $10
  db $%02X,$%02X
  ret
""" % (ITEM_PUBLISH_INDEX, ITEM_PAGE_BANK, RESET_INDEX, FAR_BANK)


def rom_reader():
    code, labels = gbasm.assemble(ROM_READ_SRC, ROM_READ_ORG)
    assert len(code) == len(ROM_READ_OLD)
    return code, labels

# original entry bytes we replace ($40D8-$40E3): push af/bc/de/hl, then the two loads
# that build bc from $C69F/$C6A0. The fallback path re-does those loads far-side.
OLD_ENTRY = bytes.fromhex('f5c5d5e5fa9fc64ffaa0c647')


SRC = """
menurow:
  ; The fixed-font restorer reads bank-32's shift-0 glyph bytes through this guarded
  ; one-byte mode.  Normal menu calls never arrive with both A=$FD and D bit 7 set.
  cp $FD
  jr nz,menunormal
  bit 7,d
  jr z,menunormal
  ld a,[hl+]
  ret
menunormal:
  push hl
  push de
  ld a,[$C69F]
  ld c,a
  ld a,[$C6A0]
  ld b,a
  ld a,b
  cp $C6
  jp nz,fallback
  ld a,c
  cp $16
  jp c,fallback
  cp $9A
  jp nc,fallback
  ld a,[$C69D]
  cp $12
  jp nz,fallback
  ld a,[$C69A]
  and a
  jp nz,fallback
  ld a,[$C69B]
  cp $03
  jp nz,fallback
  ld a,[$C69E]
  bit 1,a
  jp z,fallback
  ld a,d
  and a
  jr nz,norw
  push bc
rwloop:
  ld a,[$C0D8]
  and a
  jr z,rwdone
  dec a
  ld c,a
  add a,a
  add a,a
  add a,c
  add a,$63
  ld c,a
  ld b,$C1
  ld a,[bc]
  sub l
  ld e,a
  inc bc
  ld a,[bc]
  sbc a,h
  jr c,rwdone
  cp $02
  jr nc,rwdone
  cp $01
  jr nz,rwlow
  ld a,e
  and a
  jr nz,rwdone
  jr rwmatch
rwlow:
  ld a,e
  and $3F
  jr nz,rwdone
rwmatch:
  inc bc
  ld a,[bc]
  ld [$C0D7],a
  ld a,[$C0D8]
  dec a
  ld [$C0D8],a
  jr rwloop
rwdone:
  pop bc
norw:
  ld a,l
  ld [$C0D9],a
  ld a,h
  ld [$C0DA],a
  ld a,d
  cp $05
  jp nc,fallback
  ld a,[bc]
  and a
  jr z,pfxzero
  cp $84
  jr z,pfxmark
  cp $86
  jr z,pfxmark
  jp fallback
pfxzero:
  ld [$C0E1],a
  ld a,$BE
  ld [$C0E0],a
  jr pfxnext
pfxmark:
  ld [$C0E1],a
  cp $84
  ld a,$83
  jr z,pfxbord
  ld a,$85
pfxbord:
  ld [$C0E0],a
pfxnext:
  inc bc
  ld a,[bc]
  and a
  jp nz,fallback
  inc bc
  ld a,$02
  ld [$C0D0],a
  ld a,c
  ld [$C0D1],a
  ld a,b
  ld [$C0D2],a
  ld e,$00
scan:
  ld a,[bc]
  cp $FF
  jr z,scanend
  cp $43
  jr c,scanok
  cp $7C
  jr z,scanok
  cp $7E
  jr z,scanok
  cp $7F
  jr z,scanok
  jp fallback
scanok:
  inc bc
  inc e
  ld a,e
  cp $12
  jr c,scan
  jp fallback
scanend:
  ld a,e
  and a
  jp z,fallback
  ld [$C0CE],a
  inc bc
  ld a,c
  ld [$C0CC],a
  ld a,b
  ld [$C0CD],a
  ld a,e
  add a,a
  ld b,a
  add a,a
  add a,b
  add a,$07
  srl a
  srl a
  srl a
  ld [$C0D3],a
  ld b,a
  ld a,[$C0D0]
  ld e,a
  ld a,[$C69D]
  sub e
  cp b
  jp c,fallback
  ld a,[$C0D8]
  cp $11
  jp nc,fallback
  and a
  jr z,anew
  ld c,a
  ld hl,$C163
aloop:
  ld a,[$C0D9]
  cp [hl]
  jr nz,askip0
  inc hl
  ld a,[$C0DA]
  cp [hl]
  jr nz,askip1
  inc hl
  ld a,[hl+]
  ld [$C0DB],a
  cp $43
  jp c,fallback
  ld b,a
  ld a,[hl]
  add a,b
  jp c,fallback
  cp $7D
  jp nc,fallback
  ld e,a
  ld a,[$C0D3]
  cp [hl]
  jr z,reuseok
  jr c,reuseok
  ld a,[$C0D7]
  cp e
  jp nz,fallback
  call capneed
  add a,b
  jp c,fallback
  cp $7D
  jp nc,fallback
  ld [$C0D7],a
  sub b
  ld [hl],a
reuseok:
  inc hl
  ld a,[$C0D0]
  ld [hl],a
  jr allocok
askip0:
  inc hl
askip1:
  inc hl
  inc hl
  inc hl
  inc hl
  dec c
  jr nz,aloop
anew:
  ld a,[$C0D7]
  cp $43
  jr nc,wmok
  ld a,$43
wmok:
  ld b,a
  ld a,$7C
  sub b
  jp c,fallback
  jp z,fallback
  cp $0D
  jr c,capok
  ld a,$0D
capok:
  ld c,a
  call capneed
  cp c
  jr z,capset
  jr c,capset
  jp fallback
capset:
  ld c,a
capfits:
  ld a,[$C0D8]
  cp $10
  jp nc,fallback
  ld a,b
  ld [$C0DB],a
  add a,c
  ld [$C0D7],a
  ld a,[$C0D8]
  push bc
  ld c,a
  add a,a
  add a,a
  add a,c
  add a,$63
  ld l,a
  ld h,$C1
  ld a,c
  inc a
  ld [$C0D8],a
  pop bc
  ld a,[$C0D9]
  ld [hl+],a
  ld a,[$C0DA]
  ld [hl+],a
  ld a,b
  ld [hl+],a
  ld a,c
  ld [hl+],a
  ld a,[$C0D0]
  ld [hl],a
allocok:
  ld hl,$C008
  call zero64
  ld hl,$C04A
  call zero64
  ld hl,$C08C
  call zero64
  ld hl,$C12C
  ld c,$10
  xor a
zext:
  ld [hl+],a
  dec c
  jr nz,zext
  xor a
  ld [$C0CF],a
compose:
  ld a,[$C0CE]
  and a
  jr z,upload
  dec a
  ld [$C0CE],a
  ld a,[$C0D1]
  ld l,a
  ld a,[$C0D2]
  ld h,a
  ld a,[hl+]
  ld c,a
  ld a,l
  ld [$C0D1],a
  ld a,h
  ld [$C0D2],a
  ld a,[$C0CF]
  and $07
  rrca
  ld de,$0B30
  ld hl,$4400
shiftmul:
  and a
  jr z,shiftdone
  add hl,de
  dec a
  jr shiftmul
shiftdone:
  push hl
  ld l,c
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  pop de
  add hl,de
  ld a,[$C0CF]
  srl a
  srl a
  srl a
  ld [$C0D4],a
  call payload
  call or8
  ld a,[$C0D4]
  inc a
  cp $0D
  jr nc,nospill
  call payload
  call or8
nospill:
  ld a,[$C0CF]
  add a,$06
  ld [$C0CF],a
  jr compose
upload:
  ldh a,[$FF40]
  bit 7,a
  jp z,direct
waitq:
  ld a,[$C11A]
  and a
  jr z,arm
  call $06F7
  jr waitq
arm:
  call vdest
  ld a,[$C000]
  ld [$C0D5],a
  ld a,[$C001]
  ld [$C0D6],a
  ld a,[$C0D3]
  cp $05
  jr c,tier4
  cp $09
  jp nc,tier9
  push hl
  ld hl,$C07A
  ld de,$C08C
  ld b,$10
t8cp:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,t8cp
  pop hl
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  push hl
  ld de,$0040
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
  jr gopass1
tier4:
  push hl
  ld hl,$C008
  ld de,$C04A
  ld b,$40
t4cp1:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,t4cp1
  ld hl,$C038
  ld de,$C08C
  ld b,$10
t4cp2:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,t4cp2
  pop hl
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld [$C048],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  ld [$C049],a
  push hl
  ld de,$0030
  add hl,de
  ld a,l
  ld [$C08A],a
  ld a,h
  ld [$C08B],a
  pop hl
gopass1:
  ld a,$0A
  ld [$C11A],a
  call $06F7
  jp qdone
tier9:
  ld a,l
  ld [$C000],a
  ld a,h
  ld [$C001],a
  ld a,l
  ld [$C006],a
  ld a,h
  ld [$C007],a
  ld de,$0040
  add hl,de
  ld a,l
  ld [$C048],a
  ld a,h
  ld [$C049],a
  add hl,de
  ld a,l
  ld [$C08A],a
  ld a,h
  ld [$C08B],a
  ld a,$0A
  ld [$C11A],a
  call $06F7
  ld a,[$C0D3]
  cp $0A
  jp c,qdone
  sub $04
  ld [$C0DC],a
  ld [$C0DD],a
  ld hl,$C008
w2build:
  ld a,[$C0DD]
  call payload
  ld b,$10
w2copy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,w2copy
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  ld a,l
  cp $48
  jr nz,w2build
  ld hl,$C008
  ld de,$C04A
  ld b,$40
w2dup1:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,w2dup1
  ld hl,$C008
  ld de,$C08C
  ld b,$10
w2dup2:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,w2dup2
  call vdest
  ld a,[$C0DC]
  swap a
  ld e,a
  ld d,$00
  add hl,de
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld [$C048],a
  ld [$C08A],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  ld [$C049],a
  ld [$C08B],a
  ld a,$0A
  ld [$C11A],a
  call $06F7
qdone:
  ld a,[$C0D5]
  ld [$C000],a
  ld a,[$C0D6]
  ld [$C001],a
  jp shadow
direct:
  call vdest
  xor a
  ld [$C0DD],a
dloop:
  ld a,[$C0D3]
  ld b,a
  ld a,[$C0DD]
  cp b
  jr z,shadow
  call payload
  ld b,$10
dcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,dcopy
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr dloop
shadow:
  pop de
  pop hl
  ld a,[$C0E0]
  ld [hl+],a
  ld a,[$C0E1]
  ld [hl+],a
  xor a
  ld [hl+],a
  ld a,[$C0DB]
  ld b,a
  ld a,[$C0D3]
  ld c,a
tiles:
  ld a,b
  ld [hl+],a
  inc b
  dec c
  jr nz,tiles
  ld a,[$C0D0]
  ld c,a
  ld a,[$C69D]
  sub c
  ld c,a
  ld a,[$C0D3]
  ld b,a
  ld a,c
  sub b
  jr z,rborder
  ld c,a
  xor a
pad:
  ld [hl+],a
  dec c
  jr nz,pad
rborder:
  ld a,$BF
  ld [hl],a
  ld a,[$C0CC]
  ld [$C69F],a
  ld a,[$C0CD]
  ld [$C6A0],a
  scf
  ret
fallback:
  ld a,[$C69F]
  ld c,a
  ld a,[$C6A0]
  ld b,a
  pop de
  pop hl
  or a
  ret
capneed:
  ld a,[$C0D3]
  cp $05
  jr nc,cn8
  ld a,$04
  ret
cn8:
  cp $09
  ret nc
  ld a,$08
  ret
vdest:
  ld a,[$C0DB]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  add a,$90
  ld h,a
  ret
payload:
  cp $0C
  jr c,pnorm
  ld de,$C12C
  ret
pnorm:
  push hl
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  srl a
  srl a
  add a,a
  ld e,a
  ld d,$00
  add hl,de
  ld de,$C008
  add hl,de
  ld e,l
  ld d,h
  pop hl
  ret
zero64:
  ld c,$40
  xor a
zloop:
  ld [hl+],a
  dec c
  jr nz,zloop
  ret
or8:
  ld c,$08
orloop:
  ld a,[de]
  or [hl]
  ld [de],a
  inc de
  ld a,[de]
  or [hl]
  ld [de],a
  inc de
  inc hl
  dec c
  jr nz,orloop
  ret
menureset:
  ld a,$43
  ld [$C0D7],a
  xor a
  ld [$C0D8],a
  ld hl,$9000
  ret
"""


def _proportional_src(font, fei_prompt_y, rank_header_x):
    """Return the item-row renderer retargeted to propvwf's font tables.

    Keep ``SRC`` byte-for-byte as the established uniform-6px renderer: the normal
    build is still its regression control.  The proportional variant changes only the
    scan's pixel measurement and the compose loop's glyph lookup/advance; allocator,
    queue upload, raw fallback, border/cursor handling, and safety guards stay shared.
    """
    src = SRC

    # The proportional scan/lookup and wide-row branches make the compose loop too
    # large for the uniform renderer's original relative back-edge.
    assert src.count("  jr compose\n") == 1
    src = src.replace("  jr compose\n", "  jp compose\n", 1)
    assert src.count("  jr z,scanend\n") == 1
    src = src.replace("  jr z,scanend\n", "  jp z,scanend\n", 1)

    # WRAM-staged rows remain bounded to the proven $C616 block.  A descriptor bit marks
    # the explicit ROM-box allowlist; those sources are read one byte at a time through
    # bank 31's nested-far-call gate installed below.
    old = """  ld a,b
  cp $C6
  jp nz,fallback
  ld a,c
  cp $16
  jp c,fallback
  cp $9A
  jp nc,fallback
"""
    new = """  ld a,b
  cp $C6
  jr z,srcwram
  cp $40
  jp c,fallback
  cp $80
  jp nc,fallback
  ld a,[$C69E]
  bit 6,a
  jp z,fallback
  jr srcok
srcwram:
  ld a,c
  cp $16
  jp c,fallback
  cp $9A
  jp nc,fallback
srcok:
"""
    assert old in src
    src = src.replace(old, new, 1)

    # A long save-summary place row scans from private staging. Restore the native next-
    # row BC after composition so the box loop still visits difficulty row 2.
    old = """  ld a,[$C0CD]
  ld [$C6A0],a
  scf
  ret
fallback:
"""
    new = """  ld a,[$C0CD]
  ld [$C6A0],a
  ld a,$FE
  rst $10
  db $%02X,$%02X
  scf
  ret
fallback:
""" % (SUMMARY_HELPER_INDEX, SUMMARY_HELPER_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    old = """  cp $7F
  jr z,scanok
  jp fallback
"""
    new = """  cp $7F
  jr z,scanok
  cp $80
  jr z,scanok
  cp $88
  jr z,scanok
  cp $8A
  jr z,scanok
  cp $9E
  jr z,scanok
  cp $9F
  jr z,scanok
  cp $A0
  jr z,scanok
  cp $B0
  jp c,fallback
  cp $B6
  jr c,scanok
  jp fallback
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,[$C69D]
  sub e
  cp b
  jp c,fallback
  ld a,[$C0D8]
"""
    new = """  ld a,[$C69D]
  sub e
  cp b
  jp c,fallback
  ld a,[$C1B1]
  sub $04
  cp $02
  jp c,romalloc
  ld a,[$C0D8]
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  cp $7C
  jr z,scanok
  cp $7E
"""
    new = """  cp $7C
  jr z,scanok
  cp $7D
  jr z,scanok
  cp $7E
"""
    assert old in src
    src = src.replace(old, new, 1)

    # The proven extension runs live above tile $7F.  This menu uses LCDC's signed
    # $8800 tile-data mode, so those IDs map to $8800-$8FF0, not linearly beyond
    # $97F0.  Keep the uniform control byte-identical; only the proportional path
    # needs the signed half of the address calculation.
    old = """vdest:
  ld a,[$C0DB]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,h
  add a,$90
  ld h,a
  ret
"""
    new = """vdest:
  ld a,[$C0DB]
  ld l,a
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  ld a,[$C0DB]
  bit 7,a
  ld a,h
  jr nz,vdsigned
  add a,$90
  jr vdset
vdsigned:
  add a,$80
vdset:
  ld h,a
  ret
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,$0A
  ld [$C11A],a
  call $06F7
  ld a,[$C0D3]
  cp $0A
  jp c,qdone
"""
    new = """  ld a,$0A
  ld [$C11A],a
  call $06F7
  ld a,[$C0D3]
  cp $0E
  jp nc,wideprep
  cp $0A
  jp c,qdone
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """direct:
  call vdest
  xor a
  ld [$C0DD],a
dloop:
  ld a,[$C0D3]
  ld b,a
  ld a,[$C0DD]
  cp b
  jr z,shadow
  call payload
  ld b,$10
dcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,dcopy
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr dloop
"""
    new = """direct:
  ld a,[$C0D3]
  cp $0E
  jr c,dlimit
  ld a,$09
dlimit:
  ld [$C0D4],a
  call vdest
  xor a
  ld [$C0DD],a
dloop:
  ld a,[$C0D4]
  ld b,a
  ld a,[$C0DD]
  cp b
  jr nz,dcopynext
  ld a,[$C0D3]
  cp $0E
  jp nc,wideprep
  jp shadow
dcopynext:
  call payload
  ld b,$10
dcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,dcopy
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr dloop
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """qdone:
  ld a,[$C0D5]
"""
    new = """  jp qdone
wideprep:
  ld hl,$C08C
  ld de,$C12C
  ld b,$10
wpsave:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,wpsave
  ld hl,$C008
  call zero64
  ld hl,$C04A
  call zero64
  ld hl,$C08C
  call zero64
  ld hl,$C12C
  ld de,$C008
  ld b,$10
wprest:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,wprest
  ld a,$01
  ld [$C0DC],a
  ld a,[$C0CF]
  sub $40
  ld [$C0CF],a
  jp compose
widetail:
  ldh a,[$FF40]
  bit 7,a
  jp z,widedirect
wtwait:
  ld a,[$C11A]
  and a
  jr z,wtarm
  call $06F7
  jr wtwait
wtarm:
  call vdest
  ld de,$0080
  add hl,de
  push hl
  ld hl,$C07A
  ld de,$C08C
  ld b,$10
wtcopy:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,wtcopy
  pop hl
  ld a,l
  ld [$C000],a
  ld [$C006],a
  ld a,h
  ld [$C001],a
  ld [$C007],a
  push hl
  ld de,$0040
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
  jp gopass1
widedirect:
  call vdest
  ld de,$0080
  add hl,de
  xor a
  ld [$C0DD],a
wdloop:
  ld a,[$C0DD]
  cp $08
  jp z,shadow
  call payload
  ld b,$10
wdcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,wdcopy
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr wdloop
qdone:
  ld a,[$C0D5]
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """cn8:
  cp $09
  ret nc
  ld a,$08
  ret
"""
    new = """cn8:
  cp $09
  jr c,cnset8
  cp $0E
  ret c
  ld a,$10
  ret
cnset8:
  ld a,$08
  ret
"""
    assert old in src
    src = src.replace(old, new, 1)

    # Restore the main/action descriptor shapes that the uniform renderer proved before
    # they were reverted for lack of tile capacity.  Dot's measured pool model fits them,
    # but only if an item row-0 starts a fresh allocation epoch: main rows are no longer
    # visible then, and retaining their records would strand 16 tiles for the session.
    start = src.index("  ld a,[$C69D]\n  cp $12\n")
    end = src.index("  ld a,c\n  ld [$C0D1],a\n", start)
    shape = """  xor a
  ld [$C0D5],a
  ld a,b
  cp $C6
  jp nz,romshape
  ld a,[$C69D]
  cp $12
  jr nz,notitem
  ld a,[$C69A]
  and a
  jr nz,badshape
  ld a,[$C69B]
  cp $07
  jr nc,badshape
itemyok:
  ld a,[$C69E]
  bit 2,a
  jr nz,badshape
  and $22
  jr nz,itemdynamic
  ld a,d
  and a
  jr nz,helpresetdone
  call resetalloc
helpresetdone:
  ld a,$03
  ld [$C1B1],a
  xor a
  ld [$C0D0],a
  jp shapeok
itemdynamic:
  ; Select the measured raw-cell contract before A is reused: ordinary item rows have
  ; flags $02 and two raw cells; Floor box 5 has flags $20 and one.  CP's carry plus
  ; ADC maps those exact asserted descriptors to 2 and 1 respectively.
  cp $20
  ld a,$01
  adc a,$00
  ld [$C0D0],a
  ld a,d
  and a
  jr nz,itemresetdone
  call resetalloc
itemresetdone:
  ld a,$01
  ld [$C1B1],a
  jp shapeok
badshape:
  jp fallback
notitem:
  cp $05
  jr nz,startshapecheck
  ld a,[$C69A]
  and a
  jr z,mainshape
  cp $0D
  jr nz,startshapecheck
  ld a,[$C69E]
  bit 1,a
  jp z,fallback
  ld a,$02
  ld [$C1B1],a
  dec a
  ld [$C0D0],a
  jp shapeok
mainshape:
  ld a,[$C69B]
  and a
  jp nz,fallback
  ld a,[$C69E]
  bit 1,a
  jp z,fallback
  xor a
  ld [$C1B1],a
  inc a
  ld [$C0D0],a
  jp shapeok
startshapecheck:
  xor a
  rst $10
  db $%02X,$%02X
  and a
  jp z,fallback
  cp $01
  jr z,starttitle
  ld a,$04
  rst $10
  db $%02X,$%02X
  ; startblank leaves the static allocator mode and context-specific raw prefix set.
  jp shapeok
starttitle:
  xor a
  ld [$C1B1],a
  inc a
  ld [$C0D0],a
  jp titleok
romshape:
  ld a,d
  cp $05
  jp nc,fallback
  ld a,$04
  ld [$C1B1],a
  xor a
  ld [$C0D0],a
shapeok:
  ld a,d
  ld [$C0D6],a
  cp $06
  jp nc,fallback
titleok:
  ld a,l
  ld [$C0D9],a
  ld a,h
  ld [$C0DA],a
  ld a,[$C1B1]
  cp $03
  jr z,prefixdone
  cp $05
  jr z,prefixdone
  cp $04
  jr z,romprefix
  cp $01
  jr z,itemprefix
  ld a,[bc]
  and a
  jp nz,fallback
  ld [$C0E1],a
  ld a,$BE
  ld [$C0E0],a
  inc bc
  jr prefixdone
itemprefix:
  ld a,[bc]
  and a
  jr z,pfxzero
  cp $84
  jr z,pfxmark
  cp $86
  jr z,pfxmark
  cp $87
  jr z,pfxplain
  jp fallback
pfxzero:
pfxplain:
  ld [$C0E1],a
  ld a,$BE
  ld [$C0E0],a
  jr pfxnext
pfxmark:
  ld [$C0E1],a
  cp $84
  ld a,$83
  jr z,pfxbord
  ld a,$85
pfxbord:
  ld [$C0E0],a
pfxnext:
  inc bc
  ld a,[$C0D0]
  dec a
  jr z,prefixdone
  ld a,[bc]
  and a
  jp nz,fallback
  inc bc
prefixdone:
  jr prefixready
romprefix:
  call readbc
  ld [$C0E1],a
  and a
  jr z,romraw
  ld a,[$C69E]
  bit 5,a
  jr z,romfull
romraw:
  ld a,$01
  ld [$C0D0],a
  jr romborder
romfull:
  dec bc
romborder:
  ld a,$BE
  ld [$C0E0],a
prefixready:
""" % (START_AUX_INDEX, START_AUX_BANK,
         START_AUX_INDEX, START_AUX_BANK)
    src = src[:start] + shape + src[end:]

    # Start/file and Floor/Info transactions begin before scanning or composing row 0,
    # while D still carries the native row number. The upload path later reuses D as
    # scratch.
    old = """  ld a,h
  ld [$C0DA],a
  ld a,[$C1B1]
"""
    new = """  ld a,h
  ld [$C0DA],a
  xor a
  rst $10
  db $%02X,$%02X
  xor a
  rst $10
  db $%02X,$%02X
  ld a,[$C1B1]
""" % (START_TRANSITION_INDEX, START_TRANSITION_BANK,
         FLOOR_INFO_INDEX, FLOOR_INFO_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    # Source reads are uniform after the prefix: WRAM is read directly, while ROM bytes
    # take the nested far call and return with the chosen pointer incremented.  The scan
    # therefore leaves BC at the next row in both terminated and exact-width cases.
    old = """scan:
  ld a,[bc]
"""
    new = """scan:
  call readbc
"""
    assert old in src
    src = src.replace(old, new, 1)
    old = """  ld [$C0CE],a
  inc bc
  ld a,c
"""
    new = """  ld [$C0CE],a
  ld a,c
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,[$C0D2]
  ld h,a
  ld a,[hl+]
  ld c,a
"""
    new = """  ld a,[$C0D2]
  ld h,a
  call readhl
  ld c,a
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """fallback:
  ld a,[$C69F]
"""
    new = """readbc:
  bit 7,b
  jr nz,readbcw
  ld a,$FF
  rst $10
  db $%02X,$1F
  ret
readbcw:
  ld a,[bc]
  inc bc
  ret
readhl:
  bit 7,h
  jr nz,readhlw
  ld a,$FE
  rst $10
  db $%02X,$1F
  ret
readhlw:
  ld a,[hl+]
  ret
fallback:
  ld a,$02
  rst $10
  db $%02X,$%02X
  ld a,[$C69F]
""" % (ROM_READ_INDEX, ROM_READ_INDEX, FLOOR_INFO_INDEX, FLOOR_INFO_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    # The no-cursor help/seal shape has the whole 18-cell interior and stages text
    # directly, with no raw prefix. ROM-backed Dot rows likewise scan their complete
    # terminated source, independently of the box's physical tile width: this is what
    # lets V4C restore narrow Japanese boxes when the proportional pixels still fit.
    # build.py terminates each explicitly marked long-source row. Other ROM-backed rows
    # retain the native descriptor-width boundary (including the exact-width Rankings
    # heading), so this path never broadens a source contract accidentally.
    #
    # The first saved-summary / erase-confirmation row is a 16-character logical header
    # (`N: Log: ` plus a six-character player name), even though the legacy fixed-cell
    # boxes expose only 14/15 cells. Scan that row through its terminator; its measured
    # nine-tile raster still fits the physical box. Later rows retain their boundary.
    old = """  inc bc
  inc e
  ld a,e
  cp $12
  jr c,scan
  jp fallback
"""
    new = """  inc e
  ld a,[$C1B1]
  cp $04
  jr z,fixedscancap
  cp $05
  jr nz,stagedscancap
  ld a,d
  and a
  jr z,scan
fixedscancap:
  ld a,[$C1B1]
  cp $04
  jr nz,fixedsummarycap
  ld a,[$C69B]
  cp $08
  jr nz,fixednativecap
  ld a,d
  cp $01
  jr z,terminatedromcap
  jr fixednativecap
fixedsummarycap:
  cp $05
  jr nz,fixednativecap
  ld a,d
  cp $01
  jr nz,fixednativecap
  ld a,[$C647]
  and a
  jr nz,terminatedromcap
fixednativecap:
  ld a,[$C69E]
  bit 4,a
  jr nz,terminatedromcap
  ld a,[$C0D0]
  add a,e
  ld h,a
  ld a,[$C69D]
  cp h
  jr z,scanend
terminatedromcap:
  ld a,e
  cp $13
  jp c,scan
  jp fallback
stagedscancap:
  ld a,[$C1B1]
  cp $03
  ld a,e
  jr z,helpscancap
  cp $13
  jp c,scan
  jp fallback
helpscancap:
  cp $16
  jp c,scan
  jp fallback
"""
    assert old in src
    src = src.replace(old, new, 1)

    # The queue's established flat scratch holds 12 tiles plus one extension tile.
    # Wider rows use the same storage in two overlapping pens (implemented below), so
    # reject only a true >16-tile physical line before allocation or composition.
    old = """  ld [$C0D3],a
  ld b,a
  ld a,[$C0D0]
"""
    new = """  ld [$C0D3],a
  cp $11
  jp nc,fallback
  ld b,a
  ld a,[$C0D0]
"""
    assert old in src
    src = src.replace(old, new, 1)

    # A 14-16-tile row is composed in two overlapping pens. Phase one stops before
    # the first glyph whose pen begins in tile 8; phase two resumes with that source
    # pointer and a pen relative to tile 8. Tile 8 is retained between phases so a
    # boundary-crossing glyph is ORed with, rather than erasing, its left neighbour.
    old = """zext:
  ld [hl+],a
  dec c
  jr nz,zext
  xor a
  ld [$C0CF],a
compose:
  ld a,[$C0CE]
  and a
  jr z,upload
"""
    new = """zext:
  ld [hl+],a
  dec c
  jr nz,zext
  xor a
  ld [$C0CF],a
  ld [$C0DC],a
compose:
  ld a,[$C0CE]
  and a
  jp z,upload
  ld a,[$C0D3]
  cp $0E
  jr c,composenext
  ld a,[$C0DC]
  and a
  jr nz,composenext
  ld a,[$C0CF]
  cp $40
  jp nc,upload
composenext:
  ld a,[$C0CE]
"""
    assert old in src
    src = src.replace(old, new, 1)

    # Wide rows re-enter upload for their second pen.  Item rows no longer blank here:
    # their allocator chose a slice absent from the visible page before composition, and
    # rborder commits the complete replacement row below.
    old = """upload:
  ldh a,[$FF40]
"""
    new = """upload:
  ld a,[$C0DC]
  and a
  jp nz,widetail
  ldh a,[$FF40]
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """rborder:
  ld a,$BF
  ld [hl],a
  ld a,[$C0CC]
"""
    new = """rborder:
  ld a,$BF
  ld [hl],a
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,[$C0CC]
""" % (START_FINISH_INDEX, START_FINISH_BANK,
         ITEM_COMMIT_INDEX, ITEM_COMMIT_BANK,
         FLOOR_INFO_INDEX, FLOOR_INFO_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    # Empty trailing rows take the native fallback. Mode 2 writes and visibly commits
    # that exact blank row first, releasing its outgoing rolling slice without changing
    # native source-pointer advancement.
    old = """scanend:
  ld a,e
  and a
  jp z,fallback
"""
    new = """scanend:
  ld a,e
  and a
  jr nz,scannonempty
  ld a,$02
  rst $10
  db $%02X,$%02X
  jp fallback
scannonempty:
""" % (ITEM_PAGE_INDEX, ITEM_PAGE_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld e,$00
scan:
"""
    new = """  xor a
  ld [$C0CF],a
  ld [$C0D4],a
  ld e,$00
scan:
"""
    assert old in src
    src = src.replace(old, new, 1)

    # Records may now point into any of the three useful census-proven runs. Reuse only
    # when the whole recorded cap remains inside one run and still fits the new row.
    # Growing in place was a contiguous-watermark trick; a larger redraw safely falls
    # back instead, while every full item redraw starts a fresh epoch above.
    start = src.index("  inc hl\n  ld a,[hl+]\n  ld [$C0DB],a\n  cp $43\n",
                      src.index('aloop:\n'))
    end = src.index("reuseok:\n", start) + len("reuseok:\n")
    reuse = """  inc hl
  ld a,[hl+]
  ld [$C0DB],a
  ld b,a
  ld a,[hl]
  ld c,a
  add a,b
  ld e,a
  ld a,b
  cp $43
  jp c,fallback
  cp $7C
  jr c,vbase
  cp $8B
  jp c,fallback
  cp $96
  jr c,vmid
  cp $9A
  jp c,fallback
  cp $A2
  jp nc,fallback
  ld a,e
  cp $A3
  jp nc,fallback
  jr vslice
vbase:
  ld a,e
  cp $7D
  jp nc,fallback
  jr vslice
vmid:
  ld a,e
  cp $97
  jp nc,fallback
vslice:
  ld a,[$C0D3]
  cp c
  jr z,reuseok
  jr c,reuseok
  jp fallback
reuseok:
"""
    src = src[:start] + reuse + src[end:]

    # Exact Item and Action rows use the bank-37 rolling allocator. Other shapes retain
    # the deterministic 57+11+4 packing policy. The helper returns carry with B=base and
    # C=cap; carry clear falls through to the ordinary allocator unchanged.
    start = src.index("anew:\n")
    end = src.index("capfits:\n", start) + len("capfits:\n")
    allocate = """anew:
  call capneed
  ld c,a
  xor a
  rst $10
  db $%02X,$%02X
  jr c,capfits
  and a
  jp nz,fallback
  ld a,[$C1B1]
  cp $01
  jr nz,trybase
  ld a,c
  cp $0C
  jr nc,trybase
  ld a,[$C1AF]
  cp $8B
  jr nz,trybase
  ld b,a
  add a,c
  cp $97
  jp nc,fallback
  ld [$C1AF],a
  jr capfits
trybase:
  ld a,[$C1AE]
  ld b,a
  add a,c
  cp $7D
  jr nc,trymid
  ld [$C1AE],a
  jr capfits
trymid:
  ld a,[$C1AF]
  ld b,a
  add a,c
  cp $97
  jr nc,trysmall
  ld [$C1AF],a
  jr capfits
trysmall:
  ld a,[$C1B0]
  ld b,a
  add a,c
  cp $9F
  jp nc,fallback
  ld [$C1B0],a
capfits:
""" % (ITEM_PAGE_INDEX, ITEM_PAGE_BANK)
    src = src[:start] + allocate + src[end:]
    old = """  ld a,b
  ld [$C0DB],a
  add a,c
  ld [$C0D7],a
"""
    new = """  ld a,b
  ld [$C0DB],a
"""
    assert old in src
    src = src.replace(old, new, 1)
    assert '$C0D7' in src       # only the old menureset remains at this point

    # The ROM allocator is inserted immediately before ``allocok`` below, so the
    # proportional record-reuse branch can no longer reach that label with an 8-bit JR.
    # Keep the uniform control's established short branch byte-identical.
    if src.count("  jr allocok\n") != 1:
        raise AssertionError('menuvwf: proportional allocok branch count changed')
    src = src.replace("  jr allocok\n", "  jp allocok\n", 1)

    # The ROM pool is deterministic and record-free. Static labels never grow between
    # redraws.  One-row labels use $C0-$C8; multi-row labels partition $CB-$DD to their
    # measured English widths. Thus coexisting box 1 (Gitan/Floor/Path) and box 9
    # (No items held) cannot repaint one another.
    old = """allocok:
  ld hl,$C008
"""
    new = """  jp allocok
romalloc:
  ld a,$01
  rst $10
  db $%02X,$%02X
  jp c,allocok
  and a
  jp nz,fallback
  ; Three-row status/difficulty choices redraw while the game can reload tile $CE.
  ; Both measured candidates use a table that skips that tile.
  ld a,[$C69C]
  cp $03
  jr nz,romcount
  ld a,d
  ld c,a
  ld b,$00
  ld hl,romdifficultytab
  add hl,bc
  ld a,[hl]
  ld [$C0DB],a
  jp allocok
romcount:
  ld a,[$C69C]
  cp $01
  jr z,romone
  cp $02
  jr z,romtwo
  cp $05
  jp nz,fallback
  ld a,d
  cp $05
  jp nc,fallback
  ld c,a
  ld b,$00
  ld hl,romfivecaps
  add hl,bc
  ld a,[$C0D3]
  cp [hl]
  jp nc,fallback
  ld hl,romfivetab
  add hl,bc
  ld a,[hl]
  ld [$C0DB],a
  jr allocok
romone:
  ld a,[$C0D3]
  cp $0A
  jp nc,fallback
  ; Identify Fay's prompt by its unique one-row Y coordinate. The running source
  ; pointer can retain a relocated alias after returning from Rankings.
  ld a,[$C69B]
  cp $%02X
  jr z,romonefei
  ; The Rankings header is the only marked one-row box at this X coordinate.
  ld a,[$C69A]
  cp $%02X
  jr nz,romonecommon
  ld a,[$C0D3]
  cp $%02X
  jp nc,fallback
  ld a,$%02X
  ld [$C0DB],a
  jr allocok
romonefei:
  ld a,[$C0D3]
  cp $%02X
  jp nc,fallback
  ld a,$%02X
  ld [$C0DB],a
  jr allocok
romonecommon:
  ; Pot contents are composed over an Items/Action header that still maps `$C0-$C3`.
  ; A tiny context helper selects/stores its disjoint two-tile generation while POT is
  ; active and retains the ordinary one-row base everywhere else.
  rst $10
  db $%02X,$%02X
  jr allocok
romtwo:
  rst $10
  db $%02X,$%02X
  jp c,allocok
  jp fallback
romfivetab:
  db $%02X,$%02X,$%02X,$%02X,$%02X
romfivecaps:
  db $05,$05,$05,$05,$04
romdifficultytab:
  db $CB,$CF,$D3
allocok:
  ld hl,$C008
""" % (START_AUX_INDEX, START_AUX_BANK, fei_prompt_y, rank_header_x,
         ROM_RANK_HEADER_CAP + 1, ROM_RANK_HEADER_BASE,
         ROM_FEI_PROMPT_CAP + 1, ROM_FEI_PROMPT_BASE,
         ITEM_POT_HEADER_INDEX, ITEM_MAIN_BANK,
         RANK_CATEGORY_INDEX, RANK_SCREEN_BANK,
         ROM_POOL_BASE, ROM_POOL_BASE + 4, ROM_POOL_BASE + 8,
         ROM_POOL_BASE + 12, ROM_POOL_BASE + 16)
    assert old in src
    src = src.replace(old, new, 1)

    # propvwf uses $C0D8 as ephemeral tile scratch. The record count must survive
    # composer calls, so move it to the tail of the proven record-table run. Fifteen
    # records still exceed the measured 13-row stacked peak.
    assert '$C0D8' in src
    src = src.replace('$C0D8', '$C1B2')
    old = """  ld a,[$C1B2]
  cp $11
  jp nc,fallback
"""
    new = """  ld a,[$C1B2]
  cp $10
  jp nc,fallback
"""
    assert old in src
    src = src.replace(old, new, 1)
    old = """  ld a,[$C1B2]
  cp $10
  jp nc,fallback
"""
    new = """  ld a,[$C1B2]
  cp $0F
  jp nc,fallback
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """scanok:
  inc e
"""
    new = """scanok:
  push bc
  push de
  ld c,a
  call inkfor
  ld d,a
  ld a,[$C0CF]
  add a,d
  ld [$C0D4],a
  call widthfor
  ld d,a
  ld a,[$C0CF]
  add a,d
  ld [$C0CF],a
  pop de
  pop bc
  inc e
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,e
  add a,a
  ld b,a
  add a,a
  add a,b
  add a,$07
"""
    new = """  ld a,[$C0D4]
  add a,$07
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,[$C0CF]
  and $07
  rrca
  ld de,$0B30
  ld hl,$4400
shiftmul:
  and a
  jr z,shiftdone
  add hl,de
  dec a
  jr shiftmul
shiftdone:
  push hl
  ld l,c
  ld h,$00
  add hl,hl
  add hl,hl
  add hl,hl
  add hl,hl
  pop de
  add hl,de
"""
    new = """  call widthfor
  ld [$C0DD],a
  ld a,c
  call slotfor
  srl a
  ld h,a
  ld l,$00
  jr nc,sloteven
  ld l,$80
sloteven:
  ld a,[$C0CF]
  and $07
  swap a
  add a,l
  ld l,a
  jr nc,slotready
  inc h
slotready:
  ld de,$%04X
  add hl,de
""" % propvwf.GLYPH_ORG
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,[$C0CF]
  add a,$06
  ld [$C0CF],a
"""
    new = """  ld a,[$C0DD]
  ld b,a
  ld a,[$C0CF]
  add a,b
  ld [$C0CF],a
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """  ld a,[$C0E0]
  ld [hl+],a
  ld a,[$C0E1]
  ld [hl+],a
  xor a
  ld [hl+],a
"""
    new = """  ld a,[$C0E0]
  ld [hl+],a
  ld a,[$C0D0]
  and a
  jr z,shadowtext
  cp $02
  jr nz,shadowzero
  ld a,[$C0E1]
  ld [hl+],a
shadowzero:
  ld a,[$C1B1]
  cp $04
  jr nz,shadowblank
  ld a,[$C0E1]
  ld [hl+],a
  jr shadowtext
shadowblank:
  xor a
  ld [hl+],a
shadowtext:
"""
    assert old in src
    src = src.replace(old, new, 1)

    old = """menureset:
  ld a,$43
  ld [$C0D7],a
  xor a
  ld [$C1B2],a
  ld hl,$9000
  ret
"""
    new = """widthfor:
  ld a,c
  cp $7D
  jr nz,wfready
  ld c,$42
wfready:
  ld a,c
  cp $%02X
  jr nc,wfsparse
  add a,$%02X
  ld l,a
  ld h,$%02X
  ld a,[hl]
  ret
wfsparse:
  ld l,a
  ld h,$00
  add hl,hl
  ld de,$%04X
  add hl,de
  inc hl
  ld a,[hl]
  ret
slotfor:
  ld a,c
  cp $%02X
  ret c
  ld l,a
  ld h,$00
  add hl,hl
  ld de,$%04X
  add hl,de
  ld a,[hl]
  ret
inkfor:
  ld c,a
  call widthfor
  ld b,a
  ld a,c
  and a
  jr z,inkfull
  cp $43
  jr c,inkminus
  cp $7C
  jr z,inkminus
  cp $7E
  jr z,inkminus
  cp $7F
  jr z,inkminus
  cp $80
  jr nz,inkfull
inkminus:
  dec b
inkfull:
  ld a,b
  ret
resetalloc:
  ld a,$43
  ld [$C1AE],a
  ld a,$8B
  ld [$C1AF],a
  ld a,$9A
  ld [$C1B0],a
  xor a
  ld [$C1B1],a
  ld [$C1B2],a
  ret
menureset:
  ld a,$FE
  rst $10
  db $%02X,$%02X
  call resetalloc
  ld hl,$9000
  ret
    """ % (propvwf.CORE_CODES, propvwf.CORE_WIDTH_ORG & 0xFF,
           propvwf.CORE_WIDTH_ORG >> 8,
           propvwf.META_ORG, propvwf.CORE_CODES, propvwf.META_ORG,
           ITEM_PAGE_INDEX, ITEM_PAGE_BANK)
    assert old in src
    src = src.replace(old, new, 1)
    if '$C0D7' in src or '$C0D8' in src:
        lines = src.splitlines()
        stale = [' / '.join(lines[max(0, i - 2):i + 3]) for i, line in enumerate(lines)
                 if '$C0D7' in line or '$C0D8' in line]
        raise AssertionError('stale proportional allocator scratch reference: %s' % stale)
    return src


def _off(bank, addr):
    return bank * BANKSZ + (addr - BANKSZ)


def _info_text_at(buf, bank, addr):
    """Read one built item-name/help string, following a pool redirect if present."""
    at = _off(bank, addr)
    if buf[at] == textpool.MARK:
        return textpool.record_text(buf[at:at + textpool.RECORD_LEN], buf)
    end = at
    bank_end = (bank + 1) * BANKSZ
    while end < bank_end and buf[end] != 0xFF:
        end += 1
    if end == bank_end:
        raise SystemExit('menuvwf: %d:$%04X item text has no $FF terminator' %
                         (bank, addr))
    return bytes(buf[at:end + 1])


def _info_pointer_text(buf, bank, table, index):
    at = _off(bank, table) + 2 * index
    addr = buf[at] | (buf[at + 1] << 8)
    if not 0x4000 <= addr < 0x8000:
        raise SystemExit('menuvwf: %d:$%04X item pointer %d is $%04X' %
                         (bank, table, index, addr))
    return _info_text_at(buf, bank, addr)


def _info_pages(data):
    """Split one built help stream without treating control arguments as terminators."""
    pages, lines, line = [], [], bytearray()
    arity = dialogue.codec.arity_for(13)
    at = 0
    while at < len(data):
        code = data[at]
        argc = (arity.get(code, 0)
                if dialogue.codec.CONTROL_MIN <= code <= dialogue.codec.CONTROL_MAX
                else 0)
        if at + argc >= len(data):
            raise SystemExit('menuvwf: truncated control $%02X in item help' % code)
        if code in textpool.TERMINATORS:
            lines.append(bytes(line))
            line.clear()
            at += 1
            if code in (0xEE, 0xFF):
                pages.append(tuple(lines))
                lines = []
            if code == 0xFF:
                return tuple(pages)
            continue
        line.extend(data[at:at + argc + 1])
        at += argc + 1
    raise SystemExit('menuvwf: item help stream has no $FF terminator')


def _item_name_text(data, index):
    """Decode one built item-table name, rejecting anything the Dot path cannot paint."""
    unknown = sorted(set(data) - set(propvwf.dotfont.CODE_TO_EN))
    if unknown:
        raise SystemExit('menuvwf: item name %d contains non-Dot code(s) %s' %
                         (index, ' '.join('$%02X' % code for code in unknown)))
    return ''.join(propvwf.dotfont.CODE_TO_EN[code] for code in data)


def _item_suffix_domain(index, name_text):
    """Return every suffix the live Item-row producer can append to this built name."""
    encode = lambda text: bytes(propvwf.EN_CODES[ch] for ch in text)
    if index < ITEM_ENHANCEMENT_COUNT:
        # itemfix patches the negative producer at 4:$5D20 to the English `$42`
        # hyphen. Zero has no visible suffix; every other signed value emits its sign.
        return tuple(('%+d' % value if value else '',
                      encode('%+d' % value) if value else b'')
                     for value in range(-99, 100))
    # Mirror lint_en.carries_counter exactly. The numbered New Staff/Pot placeholders
    # are not runtime counter classes because their terminal noun is the number.
    if name_text.endswith(' Staff') or name_text.endswith(' Pot'):
        return tuple(('[%d]' % value, encode('[%d]' % value))
                     for value in range(1, 100))
    return (('', b''),)


def _item_tile_violation(tiles):
    """Single predicate shared by the corpus gate and its negative self-check."""
    return tiles > ITEM_ROW_TILES


def _assert_item_slice_constants():
    """Keep every generated runtime table tied to the six canonical high slices."""
    if len(ITEM_HIGH_SLICES) != 6 or len(set(ITEM_HIGH_SLICES)) != 6:
        raise SystemExit('menuvwf: Item high-slice list must contain six unique bases')
    ordered = sorted(ITEM_HIGH_SLICES)
    if any(left + ITEM_ROW_TILES > right
           for left, right in zip(ordered, ordered[1:])):
        raise SystemExit('menuvwf: Item high slices overlap at the 11-tile contract')
    if ITEM_ROW_SLICES != ITEM_HIGH_SLICES + (ITEM_TRANSIENT_BASE,):
        raise SystemExit('menuvwf: Item transient slice diverged from row-slice table')
    if (set(ITEM_MAIN_VIRGIN_ROWS) != set(ITEM_HIGH_SLICES[1:]) or
            len(ITEM_MAIN_VIRGIN_ROWS) != 5):
        raise SystemExit('menuvwf: virgin Main -> Items rows are not five high owners')
    if (len(ITEM_INFO_LOW_ROWS) != 5 or
            set(ITEM_INFO_LOW_ROWS) != set(ITEM_HIGH_SLICES) - {ITEM_HIGH_SLICES[0]}):
        raise SystemExit('menuvwf: low-Info return table is not five high owners')
    if ITEM_INFO_HIGH_CANDIDATES != ITEM_HIGH_SLICES + (ITEM_TRANSIENT_BASE,):
        raise SystemExit('menuvwf: high-Info chooser must consider six highs + transient')
    if (len(ITEM_ACTION_BASES) != ITEM_ACTION_ROWS or
            len(ITEM_ACTION_CAPS) != ITEM_ACTION_ROWS):
        raise SystemExit('menuvwf: Item Action row tables have the wrong length')
    action_runs = tuple((base, base + cap)
                        for base, cap in zip(ITEM_ACTION_BASES, ITEM_ACTION_CAPS))
    if any(left_hi > right_lo and right_hi > left_lo
           for index, (left_lo, left_hi) in enumerate(action_runs)
           for right_lo, right_hi in action_runs[index + 1:]):
        raise SystemExit('menuvwf: Item Action extra-row tile runs overlap')


def _assert_item_row_contract(buf, font):
    """Exhaust every reachable built Item name/suffix against the 11-tile slices."""
    _assert_item_slice_constants()
    # Make a future inverted/off-by-one predicate fail even if the current corpus happens
    # to remain narrow. This is intentionally a negative check: 12 must be rejected.
    if _item_tile_violation(ITEM_ROW_TILES) or not _item_tile_violation(ITEM_ROW_TILES + 1):
        raise SystemExit('menuvwf: Item-row tile-limit negative self-check failed')

    table_names = [_info_pointer_text(buf, ITEM_NAME_BANK, ITEM_NAME_TABLE, index)[:-1]
                   for index in range(ITEM_INFO_TOPIC_COUNT)]
    names = table_names[:ITEM_NAME_COUNT]
    if len(set(names)) != ITEM_NAME_COUNT:
        raise SystemExit('menuvwf: first %d built Item-name pointers are not distinct' %
                         ITEM_NAME_COUNT)
    if any(name != names[-1] for name in table_names[ITEM_NAME_COUNT:]):
        raise SystemExit('menuvwf: Item-name table tail no longer aliases topic %d; '
                         'recensus the %d live-name boundary' %
                         (ITEM_NAME_COUNT - 1, ITEM_NAME_COUNT))
    variant_count = counter_count = max_tile_count = max_extent_count = 0
    max_tiles = max_extent = max_source = -1
    peak_sample = None
    for index, name in enumerate(names):
        name_text = _item_name_text(name, index)
        suffixes = _item_suffix_domain(index, name_text)
        if index >= ITEM_ENHANCEMENT_COUNT and len(suffixes) == 99:
            counter_count += 1
        for suffix_text, suffix in suffixes:
            source_chars = len(name) + len(suffix)
            if source_chars > ITEM_SOURCE_CHARS:
                raise SystemExit(
                    'menuvwf: Item row %d `%s%s` uses %d source glyphs, exceeding '
                    'the exact %d-glyph WRAM scanner contract' %
                    (index, name_text, suffix_text, source_chars, ITEM_SOURCE_CHARS))
            _advance, extent, unknown = dialogue.dot_metrics(
                name + suffix, font, bank=ITEM_NAME_BANK)
            if unknown:
                raise SystemExit(
                    'menuvwf: Item row %d `%s%s` contains non-Dot code(s) %s' %
                    (index, name_text, suffix_text,
                     ' '.join('$%02X' % code for code in sorted(unknown))))
            tiles = (extent + 7) >> 3
            if _item_tile_violation(tiles):
                raise SystemExit(
                    'menuvwf: Item row %d `%s%s` paints %dpx/%d tiles, exceeding '
                    'the exact %d-tile rolling-slice contract' %
                    (index, name_text, suffix_text, extent, tiles, ITEM_ROW_TILES))
            variant_count += 1
            max_source = max(max_source, source_chars)
            if tiles > max_tiles:
                max_tiles = tiles
                max_tile_count = 1
            elif tiles == max_tiles:
                max_tile_count += 1
            if extent > max_extent:
                max_extent = extent
                max_extent_count = 1
                peak_sample = name_text + suffix_text
            elif extent == max_extent:
                max_extent_count += 1

    if counter_count != ITEM_COUNTER_NAME_COUNT:
        raise SystemExit('menuvwf: built Item table has %d terminal-noun Staff/Pot '
                         'counter names, expected %d; recensus the suffix classes' %
                         (counter_count, ITEM_COUNTER_NAME_COUNT))
    if variant_count != ITEM_VARIANT_COUNT:
        raise SystemExit('menuvwf: built Item proof enumerated %d variants, expected %d' %
                         (variant_count, ITEM_VARIANT_COUNT))
    # Five/six-row Item Action pickers end in Name/Info.  Those two rows deliberately
    # use adjacent three-tile runs in the context-local Action generation.
    for label in ('Name', 'Info'):
        encoded = bytes(propvwf.EN_CODES[ch] for ch in label)
        _advance, extent, unknown = dialogue.dot_metrics(encoded, font, bank=30)
        tiles = (extent + 7) >> 3
        if unknown or tiles > 3:
            raise SystemExit('menuvwf: Item Action tail `%s` needs %dpx/%d tiles; '
                             'three-tile Action run is insufficient' %
                             (label, extent, tiles))
    return (len(names), variant_count, counter_count, max_tiles, max_tile_count,
            max_extent, max_extent_count, max_source, peak_sample)


def _info_cap(data, font, controls=None, bank=None, title=False):
    """Return the proportional allocator cap for this exact non-raw row."""
    if not data:
        return 0
    if title:
        # The native item formatter's two title delimiters are rendered as the approved
        # English hyphen by menurow's shape-specific normalizer.
        hyphen = propvwf.EN_CODES['-']
        data = bytes(hyphen if code == 0x7D else code for code in data)
    _advance, extent, unknown = dialogue.dot_metrics(
        data, font, bank=bank, controls=controls)
    if unknown:
        raise SystemExit('menuvwf: Info ownership proof found non-Dot codes %s' %
                         ' '.join('$%02X' % code for code in sorted(unknown)))
    tiles = (extent + 7) >> 3
    if tiles > 16:
        raise SystemExit('menuvwf: Info ownership proof found a %d-tile row' % tiles)
    if tiles <= 4:
        return 4
    if tiles <= 8:
        return 8
    return tiles if tiles <= 13 else 16


def _assert_info_ownership(buf, font):
    """Prove Info generations plus both high-generation return allocators.

    Page zero starts in the 63-tile low generation and each native page step toggles the
    generation, so odd continuation pages use the 57-tile high generation.  Titles are
    charged with both native delimiters and every live -99..+99/[1]..[99] suffix, not just
    the bare pointer-table name.  The three prefix inequalities prove that the fixed high
    Action bases are released before they are composed.  State 5 is reachable only from
    odd continuation pages; simulate its exact Item-row chooser while the disjoint
    Action generation and outgoing high Info generation remain visible.
    """
    topics = ITEM_INFO_TOPIC_COUNT
    names = [_info_pointer_text(buf, ITEM_NAME_BANK, ITEM_NAME_TABLE, index)[:-1]
             for index in range(topics)]
    fragments = {index: _info_pointer_text(buf, 11, 0x55AC, index)[:-1]
                 for index in range(13)}
    controls = dialogue.dot_help_widths(font, fragments)
    delimiter = bytes([0x7D])
    page_count = 0
    min_first_two = 0xFF
    max_low = max_high = 0
    for topic, name in enumerate(names):
        name_text = _item_name_text(name, topic)
        suffixes = tuple(data for _label, data in _item_suffix_domain(topic, name_text))
        title_cap = max(_info_cap(delimiter + name + suffix + delimiter, font,
                                  bank=11, title=True)
                        for suffix in suffixes)
        help_data = _info_pointer_text(buf, 13, 0x554A, topic)
        pages = _info_pages(help_data)
        if not pages:
            raise SystemExit('menuvwf: item topic %d has no Info page' % topic)
        for page, lines in enumerate(pages):
            if not 1 <= len(lines) <= 4:
                raise SystemExit('menuvwf: item topic %d page %d has %d body rows' %
                                 (topic, page, len(lines)))
            caps = [title_cap]
            caps.extend(_info_cap(line, font, controls=controls, bank=13)
                        for line in lines)
            caps.extend([0] * (5 - len(caps)))
            first_two = caps[0] + caps[1]
            released = (sum(caps[:2]), sum(caps[:3]), sum(caps[:4]))
            required = (4, 8, 12)
            if first_two < 12 or any(have < need
                                     for have, need in zip(released, required)):
                raise SystemExit(
                    'menuvwf: item topic %d page %d caps %s do not release the fixed '
                    'high-Info Action bases (%s < %s)' %
                    (topic, page, '/'.join(map(str, caps)), released, required))
            total = sum(caps)
            capacity = 57 if page & 1 else 63
            if total > capacity:
                raise SystemExit('menuvwf: item topic %d page %d caps %s need %d/%d '
                                 'Info-generation tiles' %
                                 (topic, page, '/'.join(map(str, caps)), total, capacity))
            if page & 1:
                candidates = ITEM_INFO_HIGH_CANDIDATES
                live_end = 0x43 + total
                claimed = []
                for row in range(5):
                    released = 0x43 + sum(caps[:row])
                    choice = next((base for base in candidates
                                   if base not in claimed and
                                   (base == ITEM_TRANSIENT_BASE or
                                    base + ITEM_ROW_TILES <= released or
                                    live_end <= base)), None)
                    if choice is None:
                        raise SystemExit(
                            'menuvwf: item topic %d high page %d caps %s cannot '
                            'allocate returned Item row %d from %s after %s' %
                            (topic, page, '/'.join(map(str, caps)), row,
                             '/'.join('$%02X' % base for base in candidates),
                             '/'.join('$%02X' % base for base in claimed)))
                    claimed.append(choice)
            page_count += 1
            min_first_two = min(min_first_two, first_two)
            if page & 1:
                max_high = max(max_high, total)
            else:
                max_low = max(max_low, total)
    return topics, page_count, min_first_two, max_low, max_high


def _box_row_starts(buf, box):
    """Return each built bank-31 source-row pointer for a literal box."""
    ptab = _off(31, 0x45D5)
    lo, hi = buf[ptab + 2 * box], buf[ptab + 2 * box + 1]
    desc = _off(31, (hi << 8) | lo)
    rows, width = buf[desc + 2], buf[desc + 3]
    src = buf[desc + 5] | (buf[desc + 6] << 8)
    starts = []
    at = _off(31, src)
    for _row in range(rows):
        starts.append(0x4000 + at - 31 * BANKSZ)
        for _cell in range(width):
            value = buf[at]
            at += 1
            if value == 0xFF:
                break
    return tuple(starts)


def _box_geometry(buf, box):
    """Return the built descriptor's x, y, rows, width and flags."""
    ptab = _off(31, 0x45D5)
    lo, hi = buf[ptab + 2 * box], buf[ptab + 2 * box + 1]
    desc = _off(31, (hi << 8) | lo)
    return tuple(buf[desc:desc + 5])


def install(buf, notes=None, font=None):
    proportional = font is not None
    code_at = PROP_CODE_AT if proportional else CODE_AT
    item_contract = None
    info_ownership = None
    if proportional:
        item_contract = _assert_item_row_contract(buf, font)
        info_ownership = _assert_info_ownership(buf, font)
        pot_header = _box_geometry(buf, 17)
        if pot_header[:4] != (0, 0, 1, 3):
            raise SystemExit('menuvwf: Pot header box 17 geometry %s no longer matches '
                             'the disjoint $C7-$C8 transition slice' %
                             (pot_header,))
        if ROM_POT_HEADER_BASE + ROM_POT_HEADER_CAP > ROM_ONE_END:
            raise SystemExit('menuvwf: Pot header slice exceeds the one-row ROM pool')
        fei_prompt_rows = _box_row_starts(buf, 32)
        if len(fei_prompt_rows) != 1:
            raise SystemExit('menuvwf: Fay prompt box 32 no longer has one row')
        fei_prompt_y = _box_geometry(buf, 32)[1]
        collisions = [box for box in ROM_BOXES if box != 32 and
                      _box_geometry(buf, box)[2] == 1 and
                      _box_geometry(buf, box)[1] == fei_prompt_y]
        if collisions:
            raise SystemExit('menuvwf: Fay prompt Y=%d is shared by one-row ROM boxes %s'
                             % (fei_prompt_y, collisions))
        rank_header = _box_geometry(buf, 41)
        if rank_header[2] != 1:
            raise SystemExit('menuvwf: Rankings header box 41 is no longer one row')
        rank_header_x = rank_header[0]
        collisions = [box for box in ROM_BOXES if box != 41 and
                      _box_geometry(buf, box)[2] == 1 and
                      _box_geometry(buf, box)[0] == rank_header_x]
        if collisions:
            raise SystemExit('menuvwf: Rankings header X=%d is shared by one-row ROM '
                             'boxes %s' % (rank_header_x, collisions))
        rank_category = _box_geometry(buf, 47)
        if rank_category[:4] != (5, 7, 2, 10):
            raise SystemExit('menuvwf: Rankings category box 47 geometry %s no longer '
                             'matches its screen-scoped allocator' %
                             (rank_category,))
        collisions = [box for box in ROM_BOXES if box != 47 and
                      _box_geometry(buf, box)[2] == 2 and
                      _box_geometry(buf, box)[1] == rank_category[1]]
        if collisions:
            raise SystemExit('menuvwf: Rankings category Y=%d is shared by two-row ROM '
                             'boxes %s' % (rank_category[1], collisions))
        src = _proportional_src(font, fei_prompt_y, rank_header_x)
    else:
        src = SRC

    if proportional:
        expected = propvwf.preshift(font, buf)
        start = _off(FAR_BANK, propvwf.GLYPH_ORG)
        if bytes(buf[start:start + len(expected)]) != expected:
            raise SystemExit('menuvwf: proportional Dot tables are not installed; '
                             'run propvwf.install first')
        widths = bytes(font.advance_code(code) for code in range(propvwf.CORE_CODES))
        start = _off(FAR_BANK, propvwf.CORE_WIDTH_ORG)
        if bytes(buf[start:start + len(widths)]) != widths:
            raise SystemExit('menuvwf: proportional core-width page does not match '
                             'the approved font')

        normal_rows = _box_row_starts(buf, 48)
        if len(normal_rows) != 2:
            raise SystemExit('menuvwf: difficulty box 48 no longer has two rows')
        start_template = START_SRC
        selector_src = SELECTOR_SRC
        if not CONTEXT_STATIC_ROWS:
            # Preserve the proportional title and Log-selector paths, which use the
            # keyed/restored menu allocator.  Reject only allocations whose tile IDs
            # outlive the screen that painted them.
            old = "difficultyalloc:\n  ld a,[$C69A]"
            new = "difficultyalloc:\n  jp danone"
            if old not in start_template:
                raise AssertionError('menuvwf: difficulty static-pool gate moved')
            start_template = start_template.replace(old, new, 1)
            old = "  ld a,$02\n  ret\n"
            if start_template.count(old) != 2:
                raise AssertionError('menuvwf: start static classifications moved')
            start_template = start_template.replace(old, "  xor a\n  ret\n")
            old = "selrankok:\n  ld a,$02"
            new = "selrankok:\n  xor a"
            if old not in selector_src:
                raise AssertionError('menuvwf: Rank/Pass static classification moved')
            selector_src = selector_src.replace(old, new, 1)

        start_src = start_template % (
            RANK_VALIDATE_AT, RANK_UPLOAD_AT, START_BLANK_AT,
            SELECTOR_INDEX, SELECTOR_BANK,
            DIFFICULTY_ROW0_CAP + 1,
            normal_rows[0] & 0xFF, normal_rows[0] >> 8,
            DIFFICULTY_ALT_ROW0_BASE, DIFFICULTY_POOL_BASE,
            DIFFICULTY_ROW1_CAP + 1,
            normal_rows[1] & 0xFF, normal_rows[1] >> 8,
            DIFFICULTY_ALT_ROW1_BASE,
            DIFFICULTY_POOL_BASE + DIFFICULTY_ROW0_CAP,
            SUMMARY_INDEX, SUMMARY_BANK)
        start_code, start_labels = gbasm.assemble(start_src, START_AUX_AT)
        if START_AUX_AT + len(start_code) > START_AUX_LIMIT:
            raise SystemExit('menuvwf: start-flow helper needs %d bytes, only %d available'
                             % (len(start_code), START_AUX_LIMIT - START_AUX_AT))
        if buf[_off(START_AUX_BANK, 0x4000)] != START_AUX_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % START_AUX_BANK)
        start_at = _off(START_AUX_BANK, START_AUX_AT)
        if any(b != 0xFF for b in buf[start_at:start_at + len(start_code)]):
            raise SystemExit('menuvwf: bank %d start-flow region at $%04X is not free'
                             % (START_AUX_BANK, START_AUX_AT))
        start_ix = _off(START_AUX_BANK, 0x4000) + START_AUX_INDEX - 1
        if bytes(buf[start_ix:start_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (START_AUX_INDEX, START_AUX_BANK))
        buf[start_at:start_at + len(start_code)] = start_code
        buf[start_ix] = start_labels['startaux'] & 0xFF
        buf[start_ix + 1] = start_labels['startaux'] >> 8

        blank_src = START_BLANK_SRC
        blank_code, blank_labels = gbasm.assemble(blank_src, START_BLANK_AT)
        if START_BLANK_AT + len(blank_code) > 0x4300:
            raise SystemExit('menuvwf: start-flow blanker needs %d bytes, only %d '
                             'available' % (len(blank_code), 0x4300 - START_BLANK_AT))
        blank_at = _off(START_AUX_BANK, START_BLANK_AT)
        if any(b != 0xFF for b in buf[blank_at:blank_at + len(blank_code)]):
            raise SystemExit('menuvwf: bank %d start-flow blanker at $%04X is not free'
                             % (START_AUX_BANK, START_BLANK_AT))
        buf[blank_at:blank_at + len(blank_code)] = blank_code

        summary_helper_code, summary_helper_labels = gbasm.assemble(
            SUMMARY_HELPER_SRC, SUMMARY_HELPER_AT)
        if SUMMARY_HELPER_AT + len(summary_helper_code) > SUMMARY_HELPER_LIMIT:
            raise SystemExit('menuvwf: save-summary producer helper needs %d bytes, only '
                             '%d available' %
                             (len(summary_helper_code),
                              SUMMARY_HELPER_LIMIT - SUMMARY_HELPER_AT))
        if buf[_off(SUMMARY_HELPER_BANK, 0x4000)] != SUMMARY_HELPER_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             SUMMARY_HELPER_BANK)
        summary_helper_at = _off(SUMMARY_HELPER_BANK, SUMMARY_HELPER_AT)
        if any(b != 0xFF for b in
               buf[summary_helper_at:summary_helper_at + len(summary_helper_code)]):
            raise SystemExit('menuvwf: bank %d save-summary helper at $%04X is not free'
                             % (SUMMARY_HELPER_BANK, SUMMARY_HELPER_AT))
        summary_helper_ix = (_off(SUMMARY_HELPER_BANK, 0x4000) +
                             SUMMARY_HELPER_INDEX - 1)
        if bytes(buf[summary_helper_ix:summary_helper_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (SUMMARY_HELPER_INDEX, SUMMARY_HELPER_BANK))
        buf[summary_helper_at:summary_helper_at + len(summary_helper_code)] = \
            summary_helper_code
        buf[summary_helper_ix] = summary_helper_labels['summaryhelper'] & 0xFF
        buf[summary_helper_ix + 1] = summary_helper_labels['summaryhelper'] >> 8

        # Replace the fixed four-cell place-name indent with the context-aware helper.
        # Four bytes are available exactly: far call (three inline bytes) plus one NOP.
        producer_at = _off(4, SUMMARY_PRODUCER_AT)
        producer_old = bytes((0x13, 0x13, 0x13, 0x13))
        if bytes(buf[producer_at:producer_at + len(producer_old)]) != producer_old:
            raise SystemExit('menuvwf: save-summary place indent at 4:$%04X moved: %s'
                             % (SUMMARY_PRODUCER_AT,
                                bytes(buf[producer_at:producer_at + 4]).hex()))
        buf[producer_at:producer_at + 4] = bytes(
            (0xD7, SUMMARY_HELPER_INDEX, SUMMARY_HELPER_BANK, 0x00))

        selector_code, selector_labels = gbasm.assemble(selector_src, SELECTOR_AT)
        if SELECTOR_AT + len(selector_code) > SELECTOR_LIMIT:
            raise SystemExit('menuvwf: selector helper needs %d bytes, only %d available'
                             % (len(selector_code), SELECTOR_LIMIT - SELECTOR_AT))
        if buf[_off(SELECTOR_BANK, 0x4000)] != SELECTOR_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % SELECTOR_BANK)
        selector_at = _off(SELECTOR_BANK, SELECTOR_AT)
        if any(b != 0xFF for b in buf[selector_at:selector_at + len(selector_code)]):
            raise SystemExit('menuvwf: bank %d selector region at $%04X is not free'
                             % (SELECTOR_BANK, SELECTOR_AT))
        selector_ix = _off(SELECTOR_BANK, 0x4000) + SELECTOR_INDEX - 1
        if bytes(buf[selector_ix:selector_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (SELECTOR_INDEX, SELECTOR_BANK))
        buf[selector_at:selector_at + len(selector_code)] = selector_code
        buf[selector_ix] = selector_labels['selectorshape'] & 0xFF
        buf[selector_ix + 1] = selector_labels['selectorshape'] >> 8

        category_code, category_labels = gbasm.assemble(
            RANK_CATEGORY_SRC, RANK_CATEGORY_AT)
        if RANK_CATEGORY_AT + len(category_code) > RANK_CATEGORY_LIMIT:
            raise SystemExit('menuvwf: Rankings category allocator needs %d bytes, only '
                             '%d available' %
                             (len(category_code),
                              RANK_CATEGORY_LIMIT - RANK_CATEGORY_AT))
        if buf[_off(RANK_SCREEN_BANK, 0x4000)] != RANK_SCREEN_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             RANK_SCREEN_BANK)
        category_at = _off(RANK_SCREEN_BANK, RANK_CATEGORY_AT)
        if any(b != 0xFF for b in
               buf[category_at:category_at + len(category_code)]):
            raise SystemExit('menuvwf: bank %d Rankings category region at $%04X is not '
                             'free' % (RANK_SCREEN_BANK, RANK_CATEGORY_AT))
        category_ix = (_off(RANK_SCREEN_BANK, 0x4000) +
                       RANK_CATEGORY_INDEX - 1)
        if bytes(buf[category_ix:category_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (RANK_CATEGORY_INDEX, RANK_SCREEN_BANK))
        buf[category_at:category_at + len(category_code)] = category_code
        buf[category_ix] = category_labels['rankcategoryalloc'] & 0xFF
        buf[category_ix + 1] = category_labels['rankcategoryalloc'] >> 8

        summary_code, summary_labels = gbasm.assemble(SUMMARY_SRC, SUMMARY_AT)
        if SUMMARY_AT + len(summary_code) > SUMMARY_LIMIT:
            raise SystemExit('menuvwf: summary helper needs %d bytes, only %d available'
                             % (len(summary_code), SUMMARY_LIMIT - SUMMARY_AT))
        if buf[_off(SUMMARY_BANK, 0x4000)] != SUMMARY_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' % SUMMARY_BANK)
        summary_at = _off(SUMMARY_BANK, SUMMARY_AT)
        if any(b != 0xFF for b in buf[summary_at:summary_at + len(summary_code)]):
            raise SystemExit('menuvwf: bank %d summary region at $%04X is not free'
                             % (SUMMARY_BANK, SUMMARY_AT))
        summary_ix = _off(SUMMARY_BANK, 0x4000) + SUMMARY_INDEX - 1
        if bytes(buf[summary_ix:summary_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (SUMMARY_INDEX, SUMMARY_BANK))
        buf[summary_at:summary_at + len(summary_code)] = summary_code
        buf[summary_ix] = summary_labels['summaryalloc'] & 0xFF
        buf[summary_ix + 1] = summary_labels['summaryalloc'] >> 8

        confirm_code, confirm_labels = gbasm.assemble(CONFIRM_SRC, CONFIRM_AT)
        if CONFIRM_AT + len(confirm_code) > CONFIRM_LIMIT:
            raise SystemExit('menuvwf: confirm helper needs %d bytes, only %d available'
                             % (len(confirm_code), CONFIRM_LIMIT - CONFIRM_AT))
        if buf[_off(CONFIRM_BANK, 0x4000)] != CONFIRM_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' % CONFIRM_BANK)
        confirm_at = _off(CONFIRM_BANK, CONFIRM_AT)
        if any(b != 0xFF for b in buf[confirm_at:confirm_at + len(confirm_code)]):
            raise SystemExit('menuvwf: bank %d confirm region at $%04X is not free'
                             % (CONFIRM_BANK, CONFIRM_AT))
        confirm_ix = _off(CONFIRM_BANK, 0x4000) + CONFIRM_INDEX - 1
        if bytes(buf[confirm_ix:confirm_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (CONFIRM_INDEX, CONFIRM_BANK))
        buf[confirm_at:confirm_at + len(confirm_code)] = confirm_code
        buf[confirm_ix] = confirm_labels['confirmalloc'] & 0xFF
        buf[confirm_ix + 1] = confirm_labels['confirmalloc'] >> 8

        item_page_code, item_page_labels = gbasm.assemble(ITEM_PAGE_SRC, ITEM_PAGE_AT)
        if ITEM_PAGE_AT + len(item_page_code) > ITEM_PAGE_LIMIT:
            raise SystemExit('menuvwf: item-page helper needs %d bytes, only %d available'
                             % (len(item_page_code), ITEM_PAGE_LIMIT - ITEM_PAGE_AT))
        if buf[_off(ITEM_PAGE_BANK, 0x4000)] != ITEM_PAGE_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % ITEM_PAGE_BANK)
        item_page_at = _off(ITEM_PAGE_BANK, ITEM_PAGE_AT)
        if any(b != 0xFF for b in
               buf[item_page_at:item_page_at + len(item_page_code)]):
            raise SystemExit('menuvwf: bank %d item-page region at $%04X is not free'
                             % (ITEM_PAGE_BANK, ITEM_PAGE_AT))
        item_page_ix = _off(ITEM_PAGE_BANK, 0x4000) + ITEM_PAGE_INDEX - 1
        if bytes(buf[item_page_ix:item_page_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (ITEM_PAGE_INDEX, ITEM_PAGE_BANK))
        item_publish_ix = _off(ITEM_PAGE_BANK, 0x4000) + ITEM_PUBLISH_INDEX - 1
        if bytes(buf[item_publish_ix:item_publish_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (ITEM_PUBLISH_INDEX, ITEM_PAGE_BANK))
        buf[item_page_at:item_page_at + len(item_page_code)] = item_page_code
        buf[item_page_ix] = item_page_labels['itempage'] & 0xFF
        buf[item_page_ix + 1] = item_page_labels['itempage'] >> 8
        buf[item_publish_ix] = item_page_labels['publishmap'] & 0xFF
        buf[item_publish_ix + 1] = item_page_labels['publishmap'] >> 8

        item_commit_code, item_commit_labels = gbasm.assemble(
            ITEM_COMMIT_SRC, ITEM_COMMIT_AT)
        if ITEM_COMMIT_AT + len(item_commit_code) > ITEM_COMMIT_LIMIT:
            raise SystemExit('menuvwf: item-row commit helper needs %d bytes, only %d '
                             'available' %
                             (len(item_commit_code), ITEM_COMMIT_LIMIT - ITEM_COMMIT_AT))
        if buf[_off(ITEM_COMMIT_BANK, 0x4000)] != ITEM_COMMIT_BANK:
            raise SystemExit('menuvwf: bank %d item-row commit pool is not installed' %
                             ITEM_COMMIT_BANK)
        item_commit_at = _off(ITEM_COMMIT_BANK, ITEM_COMMIT_AT)
        if any(b != 0xFF for b in
               buf[item_commit_at:item_commit_at + len(item_commit_code)]):
            raise SystemExit('menuvwf: bank %d item-row commit region at $%04X is not '
                             'free' % (ITEM_COMMIT_BANK, ITEM_COMMIT_AT))
        item_commit_ix = (_off(ITEM_COMMIT_BANK, 0x4000) +
                          ITEM_COMMIT_INDEX - 1)
        if bytes(buf[item_commit_ix:item_commit_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (ITEM_COMMIT_INDEX, ITEM_COMMIT_BANK))
        buf[item_commit_at:item_commit_at + len(item_commit_code)] = item_commit_code
        buf[item_commit_ix] = item_commit_labels['itemcommit'] & 0xFF
        buf[item_commit_ix + 1] = item_commit_labels['itemcommit'] >> 8

        item_finish_code, item_finish_labels = gbasm.assemble(
            ITEM_FINISH_SRC, ITEM_FINISH_AT)
        if ITEM_FINISH_AT + len(item_finish_code) > ITEM_FINISH_LIMIT:
            raise SystemExit('menuvwf: item-row finalizer needs %d bytes, only %d '
                             'available' %
                             (len(item_finish_code), ITEM_FINISH_LIMIT - ITEM_FINISH_AT))
        if buf[_off(ITEM_FINISH_BANK, 0x4000)] != ITEM_FINISH_BANK:
            raise SystemExit('menuvwf: bank %d item-row finalizer pool is not installed' %
                             ITEM_FINISH_BANK)
        item_finish_at = _off(ITEM_FINISH_BANK, ITEM_FINISH_AT)
        if any(b != 0xFF for b in
               buf[item_finish_at:item_finish_at + len(item_finish_code)]):
            raise SystemExit('menuvwf: bank %d item-row finalizer region at $%04X is not '
                             'free' % (ITEM_FINISH_BANK, ITEM_FINISH_AT))
        item_finish_ix = (_off(ITEM_FINISH_BANK, 0x4000) +
                          ITEM_FINISH_INDEX - 1)
        if bytes(buf[item_finish_ix:item_finish_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (ITEM_FINISH_INDEX, ITEM_FINISH_BANK))
        buf[item_finish_at:item_finish_at + len(item_finish_code)] = item_finish_code
        buf[item_finish_ix] = item_finish_labels['itemfinish'] & 0xFF
        buf[item_finish_ix + 1] = item_finish_labels['itemfinish'] >> 8

        def install_item_aux(name, bank, at, limit, source, entries):
            """Install one privately owned Item helper prefix and its far entries."""
            helper_code, helper_labels = gbasm.assemble(source, at)
            if at + len(helper_code) > limit:
                raise SystemExit('menuvwf: %s needs %d bytes, only %d available' %
                                 (name, len(helper_code), limit - at))
            if buf[_off(bank, 0x4000)] != bank:
                raise SystemExit('menuvwf: bank %d %s pool is not installed' %
                                 (bank, name))
            helper_at = _off(bank, at)
            if any(b != 0xFF for b in
                   buf[helper_at:helper_at + len(helper_code)]):
                raise SystemExit('menuvwf: bank %d %s region at $%04X is not free' %
                                 (bank, name, at))
            for index, label in entries:
                helper_ix = _off(bank, 0x4000) + index - 1
                if bytes(buf[helper_ix:helper_ix + 2]) != b'\xff\xff':
                    raise SystemExit('menuvwf: far index $%02X in bank %d is already '
                                     'used by %s' % (index, bank, name))
                if label not in helper_labels:
                    raise SystemExit('menuvwf: %s has no entry label %s' %
                                     (name, label))
            buf[helper_at:helper_at + len(helper_code)] = helper_code
            for index, label in entries:
                helper_ix = _off(bank, 0x4000) + index - 1
                helper_addr = helper_labels[label]
                buf[helper_ix] = helper_addr & 0xFF
                buf[helper_ix + 1] = helper_addr >> 8
            return helper_code, helper_labels

        item_state_code, item_state_labels = install_item_aux(
            'Item state/Action/Pot allocator', ITEM_STATE_BANK, ITEM_STATE_AT_ROM,
            ITEM_STATE_LIMIT,
            ITEM_STATE_SRC + '\n' + ITEM_ACTION_SRC + '\n' + ITEM_POT_FINISH_SRC,
            ((ITEM_STATE_INDEX, 'itemstate'), (ITEM_ACTION_INDEX, 'itemaction'),
             (ITEM_POT_FINISH_INDEX, 'potfinish')))
        item_main_code, item_main_labels = install_item_aux(
            'Item Main allocator', ITEM_MAIN_BANK, ITEM_MAIN_AT, ITEM_MAIN_LIMIT,
            ITEM_MAIN_SRC, ((ITEM_MAIN_INDEX, 'itemmain'),
                            (ITEM_POT_HEADER_INDEX, 'itempotheader')))
        item_choice_code, item_choice_labels = install_item_aux(
            'Item ownership chooser', ITEM_CHOICE_BANK, ITEM_CHOICE_AT,
            ITEM_CHOICE_LIMIT, ITEM_CHOICE_SRC,
            ((ITEM_CHOICE_INDEX, 'itemchoice'),))
        item_info_choice_code, item_info_choice_labels = install_item_aux(
            'Item Info-return chooser', ITEM_INFO_CHOICE_BANK, ITEM_INFO_CHOICE_AT,
            ITEM_INFO_CHOICE_LIMIT, ITEM_INFO_CHOICE_SRC,
            ((ITEM_INFO_CHOICE_INDEX, 'iteminfochoice'),))
        item_migrate_code, item_migrate_labels = install_item_aux(
            'Item transient-slice migrator', ITEM_MIGRATE_BANK, ITEM_MIGRATE_AT,
            ITEM_MIGRATE_LIMIT, ITEM_MIGRATE_SRC,
            ((ITEM_MIGRATE_INDEX, 'itemmigrate'),))
        item_transition_code, item_transition_labels = install_item_aux(
            'Item transition allocator', ITEM_TRANSITION_BANK, ITEM_TRANSITION_AT,
            ITEM_TRANSITION_LIMIT, ITEM_TRANSITION_SRC,
            ((ITEM_TRANSITION_INDEX, 'itemtransition'),))
        item_fixed_code, item_fixed_labels = install_item_aux(
            'Item fixed-return allocator/map publisher', ITEM_FIXED_BANK,
            ITEM_FIXED_AT, ITEM_FIXED_LIMIT, ITEM_FIXED_SRC + '\n' + ITEM_MAP_SRC,
            ((ITEM_FIXED_INDEX, 'itemfixed'), (ITEM_MAP_INDEX, 'itemmap')))
        item_validate_code, item_validate_labels = install_item_aux(
            'Item ownership validator', ITEM_VALIDATE_BANK, ITEM_VALIDATE_AT,
            ITEM_VALIDATE_LIMIT, ITEM_VALIDATE_SRC,
            ((ITEM_VALIDATE_INDEX, 'itemvalidate'),))
        fixed_restore_code, fixed_restore_labels = install_item_aux(
            'shared fixed-font restorer', FIXED_RESTORE_BANK, FIXED_RESTORE_AT,
            FIXED_RESTORE_LIMIT, FIXED_RESTORE_SRC,
            ((FIXED_RESTORE_INDEX, 'fixedrestore'),))
        floor_post_code, floor_post_labels = install_item_aux(
            'Floor/Info post-commit controller', FLOOR_INFO_POST_BANK,
            FLOOR_INFO_POST_AT, FLOOR_INFO_POST_LIMIT, FLOOR_INFO_POST_SRC,
            ((FLOOR_INFO_POST_INDEX, 'floorpost'),))
        floor_alloc_code, floor_alloc_labels = install_item_aux(
            'Floor/Info generation allocator', FLOOR_ALLOC_BANK, FLOOR_ALLOC_AT,
            FLOOR_ALLOC_LIMIT, FLOOR_ALLOC_SRC,
            ((FLOOR_ALLOC_INDEX, 'flooralloc'),))

        native_map_at = _off(NATIVE_MAP_BANK, NATIVE_MAP_AT)
        native_map_expect = bytes.fromhex('f5c5d5e5dffa')
        if bytes(buf[native_map_at:native_map_at + len(native_map_expect)]) != \
                native_map_expect:
            raise SystemExit('menuvwf: native map producer at %d:$%04X moved' %
                             (NATIVE_MAP_BANK, NATIVE_MAP_AT))
        native_map_ix = (_off(NATIVE_MAP_BANK, 0x4000) +
                         NATIVE_MAP_INDEX - 1)
        if bytes(buf[native_map_ix:native_map_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (NATIVE_MAP_INDEX, NATIVE_MAP_BANK))
        buf[native_map_ix] = NATIVE_MAP_AT & 0xFF
        buf[native_map_ix + 1] = NATIVE_MAP_AT >> 8

        floor_info_code, floor_info_labels = gbasm.assemble(
            FLOOR_INFO_SRC, FLOOR_INFO_AT)
        if FLOOR_INFO_AT + len(floor_info_code) > FLOOR_INFO_LIMIT:
            raise SystemExit('menuvwf: Floor/Info controller needs %d bytes, only %d available'
                             % (len(floor_info_code), FLOOR_INFO_LIMIT - FLOOR_INFO_AT))
        if buf[_off(FLOOR_INFO_BANK, 0x4000)] != FLOOR_INFO_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % FLOOR_INFO_BANK)
        floor_info_at = _off(FLOOR_INFO_BANK, FLOOR_INFO_AT)
        if any(b != 0xFF for b in
               buf[floor_info_at:floor_info_at + len(floor_info_code)]):
            raise SystemExit('menuvwf: bank %d Floor/Info region at $%04X is not free'
                             % (FLOOR_INFO_BANK, FLOOR_INFO_AT))
        floor_info_ix = _off(FLOOR_INFO_BANK, 0x4000) + FLOOR_INFO_INDEX - 1
        if bytes(buf[floor_info_ix:floor_info_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (FLOOR_INFO_INDEX, FLOOR_INFO_BANK))
        buf[floor_info_at:floor_info_at + len(floor_info_code)] = floor_info_code
        buf[floor_info_ix] = floor_info_labels['floorinfo'] & 0xFF
        buf[floor_info_ix + 1] = floor_info_labels['floorinfo'] >> 8

        floor_finish_code, floor_finish_labels = gbasm.assemble(
            FLOOR_INFO_FINISH_SRC, FLOOR_INFO_FINISH_AT)
        if FLOOR_INFO_FINISH_AT + len(floor_finish_code) > FLOOR_INFO_FINISH_LIMIT:
            raise SystemExit('menuvwf: Floor/Info finalizer needs %d bytes, only %d available'
                             % (len(floor_finish_code),
                                FLOOR_INFO_FINISH_LIMIT - FLOOR_INFO_FINISH_AT))
        if buf[_off(FLOOR_INFO_FINISH_BANK, 0x4000)] != FLOOR_INFO_FINISH_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % FLOOR_INFO_FINISH_BANK)
        floor_finish_at = _off(FLOOR_INFO_FINISH_BANK, FLOOR_INFO_FINISH_AT)
        if any(b != 0xFF for b in
               buf[floor_finish_at:floor_finish_at + len(floor_finish_code)]):
            raise SystemExit('menuvwf: bank %d Floor/Info finalizer at $%04X is not free'
                             % (FLOOR_INFO_FINISH_BANK, FLOOR_INFO_FINISH_AT))
        floor_finish_ix = (_off(FLOOR_INFO_FINISH_BANK, 0x4000) +
                           FLOOR_INFO_FINISH_INDEX - 1)
        if bytes(buf[floor_finish_ix:floor_finish_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (FLOOR_INFO_FINISH_INDEX, FLOOR_INFO_FINISH_BANK))
        buf[floor_finish_at:floor_finish_at + len(floor_finish_code)] = floor_finish_code
        buf[floor_finish_ix] = floor_finish_labels['floorinfofinish'] & 0xFF
        buf[floor_finish_ix + 1] = floor_finish_labels['floorinfofinish'] >> 8

        start_transition_code, start_transition_labels = gbasm.assemble(
            START_TRANSITION_SRC, START_TRANSITION_AT)
        if START_TRANSITION_AT + len(start_transition_code) > START_TRANSITION_LIMIT:
            raise SystemExit('menuvwf: start transition controller needs %d bytes, only '
                             '%d available' %
                             (len(start_transition_code),
                              START_TRANSITION_LIMIT - START_TRANSITION_AT))
        if buf[_off(START_TRANSITION_BANK, 0x4000)] != START_TRANSITION_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             START_TRANSITION_BANK)
        start_transition_at = _off(START_TRANSITION_BANK, START_TRANSITION_AT)
        if any(b != 0xFF for b in
               buf[start_transition_at:start_transition_at + len(start_transition_code)]):
            raise SystemExit('menuvwf: bank %d start transition region at $%04X is not free'
                             % (START_TRANSITION_BANK, START_TRANSITION_AT))
        start_transition_ix = (_off(START_TRANSITION_BANK, 0x4000) +
                               START_TRANSITION_INDEX - 1)
        if bytes(buf[start_transition_ix:start_transition_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (START_TRANSITION_INDEX, START_TRANSITION_BANK))
        buf[start_transition_at:start_transition_at + len(start_transition_code)] = \
            start_transition_code
        buf[start_transition_ix] = start_transition_labels['starttransition'] & 0xFF
        buf[start_transition_ix + 1] = \
            start_transition_labels['starttransition'] >> 8

        start_finish_code, start_finish_labels = gbasm.assemble(
            START_FINISH_SRC, START_FINISH_AT)
        if START_FINISH_AT + len(start_finish_code) > START_FINISH_LIMIT:
            raise SystemExit('menuvwf: start transition finalizer needs %d bytes, only '
                             '%d available' %
                             (len(start_finish_code),
                              START_FINISH_LIMIT - START_FINISH_AT))
        if buf[_off(START_FINISH_BANK, 0x4000)] != START_FINISH_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             START_FINISH_BANK)
        start_finish_at = _off(START_FINISH_BANK, START_FINISH_AT)
        if any(b != 0xFF for b in
               buf[start_finish_at:start_finish_at + len(start_finish_code)]):
            raise SystemExit('menuvwf: bank %d start finalizer region at $%04X is not free'
                             % (START_FINISH_BANK, START_FINISH_AT))
        start_finish_ix = (_off(START_FINISH_BANK, 0x4000) +
                           START_FINISH_INDEX - 1)
        if bytes(buf[start_finish_ix:start_finish_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (START_FINISH_INDEX, START_FINISH_BANK))
        buf[start_finish_at:start_finish_at + len(start_finish_code)] = start_finish_code
        buf[start_finish_ix] = start_finish_labels['startfinish'] & 0xFF
        buf[start_finish_ix + 1] = start_finish_labels['startfinish'] >> 8
        start_alloc_ix = (_off(START_FINISH_BANK, 0x4000) +
                          START_ALLOC_INDEX - 1)
        if bytes(buf[start_alloc_ix:start_alloc_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (START_ALLOC_INDEX, START_FINISH_BANK))
        buf[start_alloc_ix] = start_finish_labels['titlealloc'] & 0xFF
        buf[start_alloc_ix + 1] = start_finish_labels['titlealloc'] >> 8

    code, labels = gbasm.assemble(src, code_at)
    if code_at + len(code) > 0x8000:
        raise SystemExit('menuvwf: bank %d overflow (%d bytes from $%04X)'
                         % (FAR_BANK, len(code), code_at))
    o = _off(FAR_BANK, code_at)
    if any(b != 0xFF for b in buf[o:o + len(code)]):
        raise SystemExit('menuvwf: bank %d not free at $%04X' % (FAR_BANK, code_at))
    buf[o:o + len(code)] = code

    ix = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if buf[ix] != 0xFF or buf[ix + 1] != 0xFF:
        raise SystemExit('menuvwf: far index %d in bank %d already used'
                         % (FAR_INDEX, FAR_BANK))
    buf[ix] = labels['menurow'] & 0xFF
    buf[ix + 1] = labels['menurow'] >> 8

    rx = _off(FAR_BANK, 0x4000) + RESET_INDEX - 1
    if buf[rx] != 0xFF or buf[rx + 1] != 0xFF:
        raise SystemExit('menuvwf: far index %d in bank %d already used'
                         % (RESET_INDEX, FAR_BANK))
    buf[rx] = labels['menureset'] & 0xFF
    buf[rx + 1] = labels['menureset'] >> 8

    if proportional:
        reader, reader_labels = rom_reader()
        ro = _off(31, ROM_READ_ORG)
        if bytes(buf[ro:ro + len(reader)]) != ROM_READ_OLD:
            raise SystemExit('menuvwf: reserved bank-31 ROM reader site 31:$%04X '
                             'changed or was packed over' % ROM_READ_ORG)
        table = _off(31, 0x4000) + ROM_READ_INDEX - 1
        if bytes(buf[table:table + 2]) != bytes.fromhex('3f40'):
            raise SystemExit('menuvwf: bank-31 far index $%02X no longer points to $403F'
                             % ROM_READ_INDEX)
        buf[ro:ro + len(reader)] = reader
        buf[table] = reader_labels['readgate'] & 0xFF
        buf[table + 1] = reader_labels['readgate'] >> 8

    # the allocator's reset signal: the font upload's first instruction (ld hl,$9000,
    # 3 bytes) becomes the 3-byte far call; menureset replays it and returns
    fo = _off(13, FONT_UPLOAD)
    if bytes(buf[fo:fo + 3]) != OLD_FONT_ENTRY:
        raise SystemExit('menuvwf: 13:$%04X is not the font upload entry' % FONT_UPLOAD)
    buf[fo:fo + 3] = bytes((0xD7, RESET_INDEX, FAR_BANK))

    eo = _off(31, ROW_DRAWER)
    if bytes(buf[eo:eo + len(OLD_ENTRY)]) != OLD_ENTRY:
        raise SystemExit('menuvwf: 31:$%04X is not the expected drawer entry' % ROW_DRAWER)
    # push af/bc/de/hl ; rst $10 db idx,bank ; jr c,epilog ; nop x3 ; (original $40E4...)
    rel = ROW_EPILOG - (ROW_DRAWER + 7 + 2)
    if not -128 <= rel <= 127:
        raise SystemExit('menuvwf: jr to epilog out of range')
    stub = bytes((0xF5, 0xC5, 0xD5, 0xE5,
                  0xD7, FAR_INDEX, FAR_BANK,
                  0x38, rel & 0xFF,
                  0x00, 0x00, 0x00))
    assert len(stub) == len(OLD_ENTRY)  # replaces exactly $40D8-$40E3
    buf[eo:eo + len(stub)] = stub

    # The shape allowlist in the far code is DUPLICATED GEOMETRY -- the exact trap
    # that shipped a broken name-entry picker (memory: layout-duplicated-in-code).
    # Assert the BUILT descriptors still match the constants the asm tests, so a
    # box_geometry.tsv edit fails the build instead of silently un-whitelisting.
    ptab = _off(31, 0x45D5)

    def desc(box):
        lo, hi = buf[ptab + 2 * box], buf[ptab + 2 * box + 1]
        d = _off(31, (hi << 8) | lo)
        return buf[d], buf[d + 1], buf[d + 3], buf[d + 4]    # x, y, width, flags

    if proportional:
        allowed = set(propvwf.EN_CODES.values()) | {0x7D}
        code_to_char = {code: ch for ch, code in propvwf.EN_CODES.items()}

        def rom_cap(box, rows, row):
            if box == 17:
                return ROM_POT_HEADER_CAP
            if box in (46, 48, 50):
                return (DIFFICULTY_ROW0_CAP, DIFFICULTY_ROW1_CAP)[row]
            if rows == 1:
                return 16
            if rows == 2:
                return (8, 12)[row]
            if rows == 3:
                return (4, 8, 8)[row]
            if rows == 5:
                return (4, 4, 4, 4, 3)[row]
            return 0

        marked = []
        for box in ROM_BOXES:
            lo, hi = buf[ptab + 2 * box], buf[ptab + 2 * box + 1]
            do = _off(31, (hi << 8) | lo)
            x, y, rows, width, flags = buf[do:do + 5]
            src = buf[do + 5] | (buf[do + 6] << 8)
            if flags & (ROM_FLAG_BIT | ROM_RAW_PREFIX_BIT | ROM_LONG_SOURCE_BIT):
                raise SystemExit('menuvwf: ROM descriptor bits already used by box %d' % box)
            if flags & 0x80:
                raise SystemExit('menuvwf: ROM box %d is still DTE-compressed; keep the '
                                 'approved ROM_BOXES literal in build.py' % box)
            if not 0x4000 <= src < 0x8000 or rows not in (1, 2, 3, 5):
                raise SystemExit('menuvwf: ROM box %d has unsupported source/row geometry'
                                 % box)
            at = _off(31, src)
            for row in range(rows):
                data = []
                source_limit = (ROM_SOURCE_CAP if box in ROM_LONG_SOURCE_BOXES
                                else width)
                terminated = False
                for _ in range(source_limit):
                    source_code = buf[at]
                    if source_code == 0xFF:
                        at += 1
                        terminated = True
                        break
                    data.append(source_code)
                    at += 1
                if box in ROM_LONG_SOURCE_BOXES and not terminated:
                    raise SystemExit('menuvwf: ROM box %d row %d has no terminator '
                                     'within the %d-glyph source contract'
                                     % (box, row, ROM_SOURCE_CAP))
                # Keep cursor cells independently writable. Boxes 8/17 have no leading
                # zero, but real flows replace their first letter after the drawer
                # returns, so bit 5 preserves it. Box 14's apparent overwrite exists
                # only in a synthetic forced-dispatch context; ordinary Items must
                # compose from its `I` or the word visibly splits fixed/VWF spacing.
                prefix = int(data[0] == 0 or box in ROM_RAW_PREFIX_BOXES)
                codes = data[prefix:]
                if not codes or any(code not in allowed for code in codes):
                    raise SystemExit('menuvwf: ROM box %d row %d contains a non-Dot or '
                                     'empty payload: %s' %
                                     (box, row, ' '.join('$%02X' % c for c in codes)))
                pen = extent = 0
                for glyph_code in codes:
                    normal = 0x42 if glyph_code == 0x7D else glyph_code
                    ch = code_to_char.get(normal)
                    advance = font.advance_code(normal, unknown=8)
                    span = (propvwf.dotfont.ink_span(font.glyphs[ch])
                            if ch is not None else None)
                    ink = span[1] + 1 if span else advance
                    extent = pen + ink
                    pen += advance
                tiles = (extent + 7) >> 3
                if tiles > rom_cap(box, rows, row):
                    raise SystemExit('menuvwf: ROM box %d row %d needs %d tiles, exceeds '
                                     'its deterministic %d-tile slice' %
                                     (box, row, tiles, rom_cap(box, rows, row)))
            buf[do + 4] = (flags | ROM_FLAG_BIT |
                           (ROM_RAW_PREFIX_BIT if box in ROM_RAW_PREFIX_BOXES else 0) |
                           (ROM_LONG_SOURCE_BIT if box in ROM_LONG_SOURCE_BOXES else 0))
            marked.append(box)

        # Box 5 shares the $C616 item staging block but has flags=0, like the raw-prefix-0
        # help boxes.  Mark it with bit 5 so the compact bank-32 classifier can select
        # item mode (one independently blank prefix cell) without another geometry
        # branch.  Bit 5 is our already-proven custom descriptor bit and is ignored by
        # the stock drawer; unlike bit 1 it does not turn this header into a selectable
        # list.  The item-mode row-0 reset also gives the following action popup a fresh
        # allocation epoch.
        lo, hi = buf[ptab + 10], buf[ptab + 11]       # box 5 pointer
        ground_do = _off(31, (hi << 8) | lo)
        gx, gy, grows, gw, gflags = buf[ground_do:ground_do + 5]
        gsrc = buf[ground_do + 5] | (buf[ground_do + 6] << 8)
        if (gx, gy, grows, gw, gflags, gsrc) != (0, 0, 1, 18, 0, 0xC616):
            raise SystemExit('menuvwf: Floor item header box 5 no longer matches the '
                             'measured one-row $C616 descriptor')
        buf[ground_do + 4] = ROM_RAW_PREFIX_BIT

        # The compact runtime classifier masks the only accepted dynamic bits and rejects
        # bit 2 (box 31). Freeze the complete WRAM-staged width-18 census here so another
        # descriptor flag/source edit cannot silently enter that compact branch.
        staged18 = []
        for box in range(52):
            lo, hi = buf[ptab + 2 * box], buf[ptab + 2 * box + 1]
            do = _off(31, (hi << 8) | lo)
            x, y, rows, width, flags = buf[do:do + 5]
            source = buf[do + 5] | (buf[do + 6] << 8)
            if x == 0 and y < 7 and width == 18 and source == 0xC616:
                staged18.append((box, y, rows, flags))
        expected_staged18 = [(4, 3, 5, 2), (5, 0, 1, ROM_RAW_PREFIX_BIT),
                             (7, 3, 5, 0), (15, 3, 5, 2), (19, 3, 5, 0),
                             (31, 3, 5, 4), (44, 6, 5, 0)]
        if staged18 != expected_staged18:
            raise SystemExit('menuvwf: staged width-18 descriptor census changed: %s; '
                             'runtime flag classifier must be re-measured' % staged18)
        if notes is not None:
            if CONTEXT_STATIC_ROWS:
                notes.append('menuvwf: ROM boxes %s marked for context-scoped static '
                             'pools (difficulty explanations use isolated $E0-$F3); '
                             '%d-byte nested bank-31 reader at 31:$%04X'
                             % (' '.join(map(str, marked)), len(reader), ROM_READ_ORG))
                notes.append('menuvwf: save-summary place producer uses %d-byte helper '
                             'at %d:$%04X; row pools are 9+10+8 tiles'
                             % (len(summary_helper_code), SUMMARY_HELPER_BANK,
                                SUMMARY_HELPER_AT))
            else:
                notes.append('menuvwf: unsafe context-static ROM/title/summary pools '
                             'disabled; ROM rows use the original fixed-cell drawer')

    boxes = [(4, (0, 3, 18)), (15, (0, 3, 18))]
    if proportional:
        boxes = [(0, (0, 0, 5))] + boxes + [
            (6, (13, None, 5)), (39, (13, None, 5))]
    for box, (wx, wy, ww) in boxes:
        x, y, w, fl = desc(box)
        if x != wx or (wy is not None and y != wy) or w != ww or not fl & 2:
            raise SystemExit(
                'menuvwf: box %d descriptor (x=%d y=%d w=%d fl=$%02X) no longer '
                'matches the far code shape allowlist -- update BOTH' % (box, x, y, w, fl))
    if proportional:
        x, y, w, fl = desc(5)
        if (x, y, w, fl) != (0, 0, 18, ROM_RAW_PREFIX_BIT):
            raise SystemExit(
                'menuvwf: Floor item header box 5 descriptor '
                '(x=%d y=%d w=%d fl=$%02X) no longer matches the proportional '
                'one-row allowlist' % (x, y, w, fl))
        ground_shapes = [box for box in range(52)
                         if desc(box) == (0, 0, 18, ROM_RAW_PREFIX_BIT)]
        if ground_shapes != [5]:
            raise SystemExit('menuvwf: Floor header geometry is shared by boxes %s; '
                             'the compact runtime allowlist is no longer exact'
                             % ground_shapes)
        for box in (7, 19):
            x, y, w, fl = desc(box)
            if (x, y, w, fl) != (0, 3, 18, 0):
                raise SystemExit(
                    'menuvwf: box %d descriptor (x=%d y=%d w=%d fl=$%02X) no longer '
                    'matches the no-cursor help/seal allowlist -- update BOTH'
                    % (box, x, y, w, fl))
        x, y, w, fl = desc(44)
        if (x, y, w, fl) != (0, 6, 18, 0):
            raise SystemExit(
                'menuvwf: clear-condition box 44 descriptor '
                '(x=%d y=%d w=%d fl=$%02X) no longer matches the proportional '
                'five-row allowlist' % (x, y, w, fl))
        for box, want in ((23, (0, 1, 11, 2)), (26, (4, 4, 14, 4)),
                          (27, (3, 7, 15, 0)), (45, (3, 8, 6, 2))):
            got = desc(box)
            if got != want:
                raise SystemExit(
                    'menuvwf: start-flow box %d descriptor %s no longer matches %s -- '
                    'update both the helper and census' % (box, got, want))
    if notes is not None:
        if proportional:
            notes.append('menuvwf: main/item/Floor-header/action/help/seal/condition '
                         'rows use approved %s advances, painted extents, and shared '
                         '8-shift tables' % font.name)
            if CONTEXT_STATIC_ROWS:
                notes.append('menuvwf: title/file shapes use %d-byte helper at '
                             '33:$%04X; context-static start rows enabled'
                             % (len(start_code), START_AUX_AT))
            else:
                notes.append('menuvwf: title and Log-selector rows use the keyed VWF '
                             'allocator; summary/confirm/Rank+Pass/difficulty rows use '
                             'fixed-cell fallback')
            notes.append('menuvwf: %d-byte item rolling allocator at %d:$%04X + '
                         '%d-byte complete-row VBlank committer at %d:$%04X + '
                         '%d-byte transient-slice finalizer at %d:$%04X; LCD-on '
                         'transitions expose only complete old/new rows'
                         % (len(item_page_code), ITEM_PAGE_BANK, ITEM_PAGE_AT,
                            len(item_commit_code), ITEM_COMMIT_BANK, ITEM_COMMIT_AT,
                            len(item_finish_code), ITEM_FINISH_BANK, ITEM_FINISH_AT))
            (item_names, item_variants, counter_names, item_max_tiles,
             item_max_tile_count, item_max_extent, item_max_extent_count, item_max_source,
             item_peak_sample) = item_contract
            notes.append('menuvwf: exhaustive Item-row contract: %d built names / '
                         '%d reachable variants (%d Staff/Pot counter names); peak '
                         '%d/%d tiles across %d variants; widest %dpx across %d, '
                         'source peak %d/%d glyphs (`%s`); synthetic 12-tile negative '
                         'guard rejects'
                         % (item_names, item_variants, counter_names, item_max_tiles,
                            ITEM_ROW_TILES, item_max_tile_count, item_max_extent,
                            item_max_extent_count,
                            item_max_source, ITEM_SOURCE_CHARS, item_peak_sample))
            notes.append('menuvwf: %d+%d+%d+%d-byte Floor/Info transaction at '
                         '%d:$%04X + %d:$%04X + %d:$%04X + %d:$%04X; LCD-on '
                         'row commits finish through native bank-4 map publication'
                         % (len(floor_info_code), len(floor_post_code),
                            len(floor_alloc_code), len(floor_finish_code),
                            FLOOR_INFO_BANK, FLOOR_INFO_AT,
                            FLOOR_INFO_POST_BANK, FLOOR_INFO_POST_AT,
                            FLOOR_ALLOC_BANK, FLOOR_ALLOC_AT,
                            FLOOR_INFO_FINISH_BANK, FLOOR_INFO_FINISH_AT))
            topics, pages, min_prefix, max_low, max_high = info_ownership
            notes.append('menuvwf: exhaustive Info ownership: %d topics / %d pages; '
                         'min first-two-row release %d tiles; low/high peaks %d/63 and '
                         '%d/57; %d-byte native fixed-font restorer at %d:$%04X'
                         % (topics, pages, min_prefix, max_low, max_high,
                            len(fixed_restore_code), FIXED_RESTORE_BANK,
                            FIXED_RESTORE_AT))
            notes.append('menuvwf: %d+%d-byte title/file transition at '
                         '%d:$%04X + %d:$%04X; layered title, Log, difficulty and '
                         'Rank/Pass redraws publish one complete shadow map'
                         % (len(start_transition_code), len(start_finish_code),
                            START_TRANSITION_BANK, START_TRANSITION_AT,
                            START_FINISH_BANK, START_FINISH_AT))
            pool = ('$43-$7B + $8B-$95, with six Item-Action rows isolated in '
                    '$9A-$A1/$C7-$CD/$D6-$DC (isolated $87 unused)')
        else:
            notes.append('menuvwf: item-list rows composed at uniform 6px')
            pool = '$43-$7B'
        cap = ('18-source-char WRAM menu/item + 21-source-char help/seal/condition guards'
               if proportional else '17-source-char guard')
        notes.append('menuvwf: %s, guarded allocator over %s '
                     '(the , \' - + [ ] glyph tiles are excluded); %d bytes '
                     'of far code at %d:$%04X; %d bytes left in bank'
                     % (cap, pool, len(code), FAR_BANK, code_at,
                        0x8000 - code_at - len(code)))
    return labels


def main():
    args = sys.argv[1:]
    proportional = '--dot-font' in args
    args = [arg for arg in args if arg != '--dot-font']
    if len(args) != 2:
        raise SystemExit(__doc__)
    buf = bytearray(open(args[0], 'rb').read())
    notes = []
    font = None
    if proportional:
        font = propvwf.dotfont.load_approved()
        buf[:] = font.patch(buf)
        propvwf.install(buf, font, notes)
    install(buf, notes, font=font)
    open(args[1], 'wb').write(buf)
    for n in notes:
        print(n)


if __name__ == '__main__':
    main()
