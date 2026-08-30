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
general allowlist is main (x0,y0,w5), item (x0,y3,w18), the hidden debug item picker
(x4,y0,rows4,w14), the one-row Floor item header
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
  * 1..18 SOURCE characters for menus/items or 1..21 for item information, seals, and
    clear-condition rows; every code
    is < $43 or one of the explicitly admitted punctuation/status glyphs. Equipment
    unidentified-equipment suffix `$88`, plating suffix `$8A`, and fusion-count suffixes
    `$8B-$94` (zero through nine seals) are composed as native marks at an 8px advance;
    shop inventory rows instead end with one of five native three-tile price slots:
    `$D0-$D2`, `$D3-$D5`, `$D6-$D8`, `$D9-$DB`, or `$DC-$DE`, selected by item-row
    position. The native shop formatter's 15-cell pre-price clamp is widened to 20
    virtual cells (two raw cells plus all 18 VWF source glyphs); otherwise it truncates
    names such as `Invincible Herb` to `Invincible He` before VWF sees them. Those price
    cells stay right-aligned and outside the proportional pen while the complete item
    name is composed normally.
    the cursed prefix `$87` remains a separate raw status cell. The fusion digits use a
    compact auxiliary shifter because bank 32 has no room for ten more 128-byte
    eight-shift slots. `$7D` is normalized to the approved font's `-` glyph.
    Kana, dakuten and DTE bytes all fall back. These scanner ceilings are not visual
    budgets: the row is accepted only after a separate font-pixel scan and allocator fit.
    The current 17-character fixture includes a staff/pot name plus two-digit `[NN]`.

ROM-SOURCED ELIGIBILITY. ``menuromcensus.py`` measures every literal/DTE row reaching the
untouched drawer. build.py keeps the approved rows literal and install() marks only boxes
1,8,9,14,16,17,24,28,29,32,33,34,38,41,46,47,48,50,51 with descriptor bit 6. Bank 32
reads them one byte at a time through the nested bank-31 gate at $459E. A leading zero
cursor cell stays raw. Descriptor bit 5 additionally keeps the nonzero first cell raw for
box 8: `Which?` is overwritten in its live flow. Pot's first letter cannot remain raw:
Status rendering legitimately repaints fixed tile `$1A`, so box 17 composes the complete
word into owned proportional tiles. The synthetic
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
first ITEM ROW THAT FITS uses the 11-run; 12-16-tile rows use the base run regardless of
their page position. This matters because row 0 is only an epoch-reset signal, not a
width class: forcing it into 11 tiles made the former 12-tile longest weapon fall back only at
the top of a page. The hostile measured permutation (12 + four 11-tile item rows plus
four 4-tile verbs) packs all 72 usable tiles without crossing or overlap. Item row 0
resets the hidden prior epoch;
same-destination redraws reuse a cap or fall back if they grow.

PAGE FLIPS. Fresh pixels uploaded into reused tiles used to show through the old map.
Screen-1 paging and Start-sort now drain the preceding map queue, prove the native
screen/row/allocator/count ownership state, normalize the five marker-coupled left borders, and blank the
five raw status cells, cursor cells, and five 16-cell name interiors during VBlank with the LCD on.
Because those map cells are blank, each incoming tile can be copied in four synchronized
four-byte HBlank slices without exposing partial pixels. Completed row references remain
hidden until final row 4 publishes the entire owned body in one VBlank. The final redraw
tail copies only the four
page-indicator cells rather than fourteen unchanged rows. Short-page rows use the native
exact 19-zero representation. Direct Status-root -> Items entry is owned by statusvwf's
earlier screen-1 shadow-clear hook; every rejected/unknown context retains the whole-map
LCD-off fallback and native tile queue. The visible sequence is old -> blank
status/cursor/name rows -> one complete new body; a short destination page first clamps
the selector and row to its final real item. Right borders, header, and unrelated map
cells remain owned throughout.

SCREEN-1 ACTION OVERLAY. Direct carried Items or a settled standing-item Floor page to
screen-2 Action retains the native overlay draw but allocates its first six verb rows
from six private four-tile slices at `$C7-$DE`. The unique seven-row unidentified-Pot
picker uses the ordinary collision-safe allocator for its final `Info` row. Row 0 admits those slices only
for the exact `0,1,2` stack, a valid carried selector or `$FF` Floor settlement proof,
ordinary viewport and a live BG/Window scan with no private-ID reference; priced shop rows
therefore reject structurally. Exact B-cancel arms state 7 at
the generic pop only when HL still names screen 2's `$5689` handler, reconstructs the
covered parent cells in shadow, and restores the complete seven-column,
`2*rows+1`-high footprint during VBlank. It then restores the retained Item/Floor record
state, cursor geometry, and screen state and returns directly to the screen-1 input loop.
This
retires every Action-map reference without exposing an empty rectangle or spending 40
frames on an invisible Status/Items replay. Every other Action, Name, and shop route
retains its established path; the exact screen-20 Info and Pot `See` lifecycles are
owned by the adjacent lifecycles below.

SCREEN-1 INFO LIFECYCLE. Selecting Info from that exact admitted Action parent pushes
screen 4, or screen 5 for an equipment-seal page, and retains the proof across the
`0,1,2,4/5` stack. Entry and page changes build and publish complete empty box-7 chrome
over BG rows 3-13 and retire visible rows 14-15 before composing hidden
proportional rows; the five interiors and pager appear together in a final VBlank. B at
any page and A/D-pad at the final page both remove screens 4 and 2. State 8 retires only
the five proportional Info rows and pager references while preserving box chrome and the
Window, suppresses the disposable screen-0 LCD-off publication, publishes complete empty
Item/Floor target chrome, then atomically reveals the exact replayed screen-1 parent.
Rejected Info callers keep the legacy path.

SCREEN-20 FLOOR / INFO. The independent Floor picker now joins the same exact regional
lifecycle. On entry, its Action labels retire while the complete small box remains; the
complete Info box and first row then replace it together. Page changes scan the visible
rows for tile allocations about to be reused, retire only whole overlapping rows in one
VBlank, upload a short incoming row through HBlank, and publish that complete row in the
same displayed frame. At least one old or new Info row remains throughout. Return state 9
suppresses the disposable screen-0 redraw, preserves the native 3-7-row Action height,
publishes complete empty full-width title and Action chrome, then reveals the title and
all Action rows together at the descriptor's actual last row.
This covers screen 4 descriptions and screen 5 equipment-seal pages. Five-page callers
rebuild the native footer digits, and rows 14-15 are retired so a six-row Action tail
cannot survive below Info. The compatibility stubs remain in pool banks 39/40; the exact
screen-1/screen-7/screen-20 lifecycle is co-located with Action ownership in bank 62.
Rejected
callers still reach the bank-60 full-map fallback.

SCREEN-7 FLOOR / INFO. The identity-hidden ground-Pot route is stack `0,7,4`, not the
screen-20 picker despite sharing native handler 4:$4A58. Its exact seven-row screen-4
Info child is independently admitted. Entry first removes box 6 from the right side of
box 5 and restores the underlying full-width Floor title, then uses the ordinary regional
Info publisher. Exit state 11 survives the disposable screen-0 replay, builds complete
empty box-5 plus y=1 box-6 chrome over visible BG rows 0-15, and reveals the title and all
seven Action interiors only at the final boundary. Screen 5, shorter screen-7 pickers,
and unknown callers remain rejected.

POT ENTRY / CARRIED RETURN. Selecting `See` enters screen 12 or 13 above an exact
carried, Items-appended Floor, alternate screen-7, or screen-20 Action parent. Exact
state 12 keeps LCDC bit 7 set, retires only visible BG rows 0-15 while preserving
the Window HUD, publishes complete empty compact-title and capacity-sized body chrome,
and keeps native body/title text shadow-only until box 17's final boundary. The exact
carried two-level B pop independently arms state 10, discards the intermediate Status redraw,
clears Pot page markers during VBlank, and feeds the unchanged direct screen-1 entry
gate. That gate retires the Pot map, publishes complete empty Items boxes, and only then
reveals rows. Box 17 composes all of `Pot`; leaving its first character as raw tile
`$1A` allowed the Status field renderer to replace it before the Pot title was visible.

INVENTORY NAME RETURN. The screen-9 Name finalizer natively replays screens `0,1,0`.
Status VWF admits the exact pre-screen-1 and post-screen-1 states as transaction 13,
suppresses only the disposable Status painter, regionally retires the keyboard over four
complete VBlanks, and publishes empty Items chrome before this renderer may expose any
row. One- through four-page and row-one through row-five fixtures prove the retained row
record count; unknown Name or Status callers retain the LCD-off fallback.

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
  * `$C1B3`        the synchronous transaction state: 1 is regional item-page pending;
                   2/3 are pending/settled Info or seals; 4 is fallback Info-return
                   pending; 5 is a
                   regional-to-whole-map fallback; 6 latches declined/initial Item entry;
                   7 is the transient admitted screen-2 Action B parent-restore proof;
                   8 is the exact screen-1 Info two-level parent replay; 9 is the exact
                   screen-20 Info parent replay; 10 is carried-Pot `See` replay; 11 is
                   the exact screen-7 unidentified-Pot Info parent replay; 12 is the
                   exact carried/Floor screen-12/13 Pot entry transaction;
                   `$10/$11/$12/$13/$14`
                   are title/file, difficulty, proportional Rankings, Fay-screen and
                   native Rankings transactions. It is cleared after the corresponding
                   map publication. Proven free 2026-08-17 the same way as the runs
                   above (`wramfree.py --lo C1B3 --hi C1B7`: no voted static reference
                   at `$C1B3`, zero dynamic writes in every scenario).
                   THIS BYTE MUST NOT BE SHARED WITH THE DIALOGUE RENDERER. It lived at
                   `$C0D7` until 2026-08-17, which is propvwf's `S_LOCAL`: `place`
                   stores the pen there for every glyph and `buildmap`'s `bmkeep` stores
                   a cell index 0-17. Both aliased every live state, so after any
                   dungeon message the leftover value read as an open transaction, and
                   a box redrawn while the game tore the menu down completed it: the
                   stale `$C300` menu shadow was copied over the map the native code was
                   rebuilding and LCDC bit 7 was set inside the native LCD-off interval,
                   exposing one frame of dungeon map drawn through menu-font tiles.
                   MEASURED ON THE SAME ROUTE, TWO DIFFERENT PATHS COMPLETED, so do not
                   read this as one narrow hole: leftover `$10` took `startfinish`'s
                   title/file path (`sfgeneric`'s only other gate is "last row of the
                   box") on the in-dungeon main menu, and leftover `$11` took
                   `pagepublish` on the one-row `Items` header — that path tests the
                   state byte only with `and a`, so ANY nonzero leftover arms it and its
                   remaining `$C1B1`/shadow-bank/width gates are what an ordinary
                   teardown redraw looks like anyway. The state is nonzero after almost
                   every message; only the several-frame overlap with the native blank
                   made it intermittent. `tools/potputspill.py` is the regression.
  * `$C1B4-$C1B6`  Action row count, packed retained Item/Floor record state/selector,
                   and private-pool admission latch. Screen-20 Info return saves its
                   3-7-row Action height in `$C1B4` before screen 0 overwrites `$C6BB`.
                   Screen-1 Info retains admission one and changes it to two only after
                   complete return chrome is published.
                   A gameplay-bound carried Action may leave admission one after its BG
                   has ceased to exist. The exact screen-20 `0,20,4/5` owner accepts
                   idle or that stale-one value, then clears it before publishing any
                   Info pixels; values two through four still identify other live
                   lifecycles and are rejected.
                   The mutually exclusive Item-page
                   path temporarily uses `$C1B4` as its four-slice counter, `$C1B5` as
                   the Items/Floor shape-header marker, and `$C1B6` as phases 2 (live),
                   4 (replacement header), and 3 (redraw tail). `$C1B7` marks a fully settled standing-item Floor
                   page so its direct Status pop, paging, and screen-2 Action parent can
                   retain the live-owner proof. The same
                   `$C1B3-$C1B7` free-space proof covers all four bytes.
  * `$C1B8-$C1BE`  exact seven-cell Item page-marker/top-edge snapshot retained across a
                   admitted Action overlay. Proven independently on 2026-08-24 with zero
                   static opcode references and zero dynamic writes in wramfree's menu,
                   walk, and forced-screen scenarios.
  * `$C12C-$C13B`  tile 12's composition buffer
  (`$C0E2-$C0E6` is ephemeral fusion-digit shifter scratch; the rest of the former
   `$C0E0-$C0FB` record table remains unused.)
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
import dotfont
import gbasm
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
SELECTOR_ROW_INDEX = 0x07
SELECTOR_AT = 0x4060
SELECTOR_LIMIT = 0x4100
# Screen 32 builds one Pass-selector row per eligible log by copying the shared
# ``Log`` label, replacing its terminator with the log digit, and immediately appending
# the next row.  That happened to produce the native nine-byte stride only because the
# Japanese label has seven glyphs.  English ``Log`` is shorter, so the proportional
# scanner consumed every generated log as row 0 and left the final native row outside
# the VWF/finalizer path, freezing the LCD off.  Replace the six-byte digit tail with a
# far call that appends a fresh terminator after each generated row.
SELECTOR_ROW_PATCH_BANK = 0x04
SELECTOR_ROW_PATCH_AT = 0x7924
SELECTOR_ROW_PATCH_OLD = bytes.fromhex('1b0e02811213')
SUMMARY_BANK = 0x23
SUMMARY_INDEX = 0x05
SUMMARY_AT = 0x4060
SUMMARY_LIMIT = 0x4100
CONFIRM_BANK = 0x24
CONFIRM_INDEX = 0x05
CONFIRM_AT = 0x4060
CONFIRM_LIMIT = 0x4100
# Bank 60's redirected-text base is deliberately raised to $4700 for this menu subsystem.
# Far indices 5/7/9/13/15, the same-frame Item-row publisher through $4479, the
# page-return and tile publishers through $46FF, and markers' index $0B/graphics tail
# remain disjoint.
ITEM_PUBLISH_BANK = 0x3C
ITEM_PUBLISH_INDEX = 0x05
ITEM_PUBLISH_AT = 0x405A
ITEM_PUBLISH_LIMIT = 0x4090
ITEM_REGION_BANK = 0x3C
ITEM_REGION_INDEX = 0x07
ITEM_REGION_AT = 0x4090
ITEM_REGION_LIMIT = 0x4300
ITEM_PAGE_BANK = 0x3C
ITEM_PAGE_INDEX = 0x09
ITEM_PAGE_AT = 0x4300
ITEM_PAGE_LIMIT = 0x4400
ITEM_ROW_FAST_AT = 0x43F0
ITEM_ROW_FAST_CLAMP_AT = 0x4450
ITEM_ROW_FAST_LIMIT = 0x4480
ITEM_RETURN_BANK = 0x3C
ITEM_RETURN_INDEX = 0x0F
ITEM_RETURN_AT = 0x4480
ITEM_RETURN_LIMIT = 0x45E0
ITEM_RETURN_HOOK = (0x04, 0x4D7A)
ITEM_RETURN_OLD = bytes.fromhex('f5c5e5faa3c6cb27c6966f3e00ce4d')
# The row blitter has only six bytes left in its fixed slot.  Its one same-bank call
# lands here, in the return helper's unused tail, to mark the final body row of an
# Items/Floor shape change before native box 14/18 composes the replacement header.
ITEM_SHAPE_PHASE_AT = 0x45B6
ITEM_SHAPE_PHASE_LIMIT = 0x45E0
ITEM_TILE_FAST_BANK = 0x3C
ITEM_TILE_FAST_AT = 0x45E0
ITEM_INDICATOR_AT = 0x46B1
ITEM_TILE_FAST_LIMIT = ITEM_INDICATOR_AT
ITEM_INDICATOR_LIMIT = 0x4700
# A direct held-Items Action overlay needs six four-tile verb slices without retaining
# pressure on the 72-tile Item allocator.  Bank 37 proves the live parent owns none of
# $C7-$DE, bank 61 chooses those private slices (its title-card owner begins at $7000),
# and bank 62 restores only box 6's covered parent on B-cancel (its title-logo owner also
# begins at $7000).
# Bank 60's remaining regional-controller gap holds the exact generic-pop call-site gate.
ACTION_GATE_BANK = 0x25
ACTION_GATE_INDEX = 0x05
ACTION_GATE_AT = 0x405A
ACTION_GATE_LIMIT = 0x4120
ACTION_ALLOC_BANK = 0x3D
ACTION_ALLOC_INDEX = 0x07
TITLE_CURSOR_INDEX = 0x09
ACTION_ALLOC_AT = 0x405A
ACTION_ALLOC_LIMIT = 0x4100
ACTION_BLANK_BANK = 0x3E
ACTION_BLANK_INDEX = 0x07
ACTION_BLANK_AT = 0x405A
ACTION_BLANK_LIMIT = 0x4420
INFO_CONTROL_INDEX = 0x09
INFO_FINISH_INDEX = 0x0B
INFO_POP_INDEX = 0x0D
INFO_RETURN_INDEX = 0x0F
INFO_LIFECYCLE_AT = 0x4420
INFO_LIFECYCLE_LIMIT = 0x5400
POT_FLOOR_RETURN_AT = 0x53F0
ACTION_POP_BANK = 0x3C
ACTION_POP_INDEX = 0x0D
ACTION_POP_AT = 0x422E
ACTION_POP_LIMIT = 0x4300
ACTION_POOL_BASE = 0xC7
ACTION_POOL_END = 0xDF
# statusvwf bank 53 index $0B owns the exact screen-7 Floor -> Status empty-chrome
# prepublication. Keep this ABI pair synchronized with statusvwf.STATUS_PRE_INDEX/BANK.
STATUS_FLOOR_PRE_INDEX = 0x0B
STATUS_FLOOR_PRE_BANK = 0x35
POT_PUT_ENTRY_INDEX = 0x0F
POT_PUT_ENTRY_BANK = 0x35
ACTION_POP_HOOK = (0x04, 0x485A)
ACTION_POP_OLD = bytes.fromhex('4ffa34c591ea34c5')
# Screen 12/13 begin by clearing the shared shadow at these identical `ld hl,$C300`
# instructions. Replace only that setup with the Info-return far entry; rejected callers
# receive the same HL value, while an exact screen-20 parent saves its Action height
# before the viewer overwrites C6BB.
POT_SEE_12_ENTRY_HOOK = (0x04, 0x4B83)
POT_SEE_13_ENTRY_HOOK = (0x04, 0x4BA5)
POT_SEE_ENTRY_OLD = bytes.fromhex('2100c3')
# Screen-1 selector $FF changes the Item list chrome between five carried rows and one
# standing-item row. Bank 58's standard pre-text helper slot is disjoint from ending
# credits at $4100 and gives the regional blanker room to commit the complete incoming
# rectangle before any text row becomes visible.
FLOOR_CHROME_BANK = 0x3A
FLOOR_CHROME_INDEX = 0x07
FLOOR_CHROME_AT = 0x405A
FLOOR_CHROME_LIMIT = 0x4100
# Banks 39/40 retain their established far entries as small compatibility stubs. The
# controller now lives beside the Action ownership machine in bank 62, where the exact
# screen-1 Action admission state can be validated without duplicating another protocol.
FLOOR_INFO_BANK = 0x27
FLOOR_INFO_INDEX = 0x05
FLOOR_INFO_AT = 0x405A
FLOOR_INFO_LIMIT = 0x4100
FLOOR_INFO_FINISH_BANK = 0x28
FLOOR_INFO_FINISH_INDEX = 0x05
FLOOR_INFO_FINISH_AT = 0x4060
FLOOR_INFO_FINISH_LIMIT = 0x4100
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

# A fused item appends `$8B + seal_count` after its name. That is ARITHMETIC, not a marker
# byte followed by a count: `$8B+0` is zero seals and `$8B+9` is nine, so the live range is
# `$8B-$94` -- TEN codes.
#
# It read `$8C-$94` until 2026-08-16. The canonical weapon/shield masks admit nine ability
# bits, and the nine was taken as the number of reachable values when it is really the
# MAXIMUM; a count of zero was never considered. Fusing two items that carry no seals
# yields exactly that, emits `$8B`, and because nothing admitted it the entire row dropped
# out of the proportional scanner to fixed width -- Joey found `Nagamaki` rendered fixed
# width with `$8B` drawn through the English font. `$8B` is the native zero digit, in the
# same style as 1-9; see tools/fusedzerospill.py.
#
# Bank 32 is packed to within two bytes once the menu renderer is installed, so ordinary
# 128-byte pre-shift slots would overlap code. The bank-48 helper shifts the selected
# native digit directly into the queue; bank 49 supplies the ten unshifted eight-byte
# glyphs and payload mapper.
FUSED_FIRST = 0x8B
FUSED_LAST = 0x94
FUSED_CODES = tuple(range(FUSED_FIRST, FUSED_LAST + 1))
# Pinned, NOT FUSED_FIRST: this names the ONE-seal code for equipmentmarkerspill's fixture,
# and following FUSED_FIRST would have silently retargeted it at the zero-seal glyph.
FUSED_CODE = 0x8C
FUSED_BANK = 0x30
FUSED_INDEX = 0x05
FUSED_AT = 0x405A
FUSED_LIMIT = 0x4100
FUSED_DATA_BANK = 0x31
FUSED_READ_INDEX = 0x05
FUSED_PAYLOAD_INDEX = 0x07
FUSED_DATA_AT = 0x405A
FUSED_DATA_LIMIT = 0x4100
FUSED_NATIVE = bytes.fromhex(
    '00 00 00 18 24 24 24 18 '
    '00 00 00 30 10 10 10 10 '
    '00 00 00 38 08 38 20 38 '
    '00 00 00 38 08 38 08 38 '
    '00 00 00 28 28 38 08 08 '
    '00 00 00 38 20 38 08 38 '
    '00 00 00 38 20 38 28 38 '
    '00 00 00 38 08 08 08 08 '
    '00 00 00 38 28 38 28 38 '
    '00 00 00 38 28 38 08 38')

# Shop-held inventory rows hold two raw item cells, up to 18 VWF name/suffix cells, then
# one of five dynamically painted three-tile price slots `$D0-$DE`. The slot base is
# `$D0 + 3*row`; these are tile IDs, not font codes. A dedicated pool-bank helper validates
# the exact slot, advances BC past its real terminator, and restores the raw cells after
# the VWF shadow row has been padded. Keeping this outside bank 32 also leaves the packed
# core room for the normal glyph renderer.
SHOP_SUFFIX_BANK = 0x33
SHOP_SCAN_INDEX = 0x05
SHOP_COPY_INDEX = 0x07
SHOP_SUFFIX_AT = 0x405A
SHOP_SUFFIX_LIMIT = 0x4100
SHOP_OLD_CONTENT_CELLS = 15     # native fixed row: two raw + thirteen name cells
SHOP_CONTENT_CELLS = 20         # VWF row: two raw + the full eighteen-glyph contract
# 4:$45B7 pads/truncates the staged content before appending the three price tile IDs.
# These are its five comparisons/arithmetic immediates, in execution order.
SHOP_CONTENT_PATCHES = (
    (0x45D2, 0xFE),             # cp n: already exact
    (0x45D8, 0xFE),             # cp n: choose pad vs truncate
    (0x45DC, 0x3E),             # ld a,n: padding target
    (0x45E9, 0xFE),             # cp n: truncation guard
    (0x45ED, 0xD6),             # sub n: truncation amount
)

# The two small value boxes on a shop Floor screen are drawn after the status menu has
# deliberately borrowed the native low-font planes.  Their native ``Price``/``G``
# headings and right-aligned amount rows therefore cannot safely keep referring to fixed
# alphabet/digit tiles.  The amount rows enter the ordinary proportional allocator through
# an exact shape gate in bank 56.  The headings use four private, screen-local tiles
# $C0-$C3 staged by bank 55 and uploaded through the native VBlank queue by bank 57; neither
# the outgoing status screen nor the settled Floor screen has another owner in that range.
# LCD-off returns retain a direct copy because the queue cannot run there and unrestricted
# VRAM access is already safe.  Both original heading calls are exactly three bytes, so
# they can be replaced by one far call without moving bank-4 code.
SHOP_LABEL_BANK = 0x37
SHOP_LABEL_INDEX = 0x05
SHOP_LABEL_AT = 0x405A
SHOP_LABEL_LIMIT = 0x4100
SHOP_SHAPE_BANK = 0x38
SHOP_SHAPE_INDEX = 0x05
SHOP_SHAPE_AT = 0x405A
SHOP_SHAPE_LIMIT = 0x4100
SHOP_UPLOAD_BANK = 0x39
SHOP_UPLOAD_INDEX = 0x05
SHOP_UPLOAD_AT = 0x405A
SHOP_UPLOAD_LIMIT = 0x4100
SHOP_LABEL_PATCHES = (0x4AC5, 0x4AF3)
SHOP_LABEL_OLD_CALL = bytes((0xCF, 0x11, 0x1F))
SHOP_LABEL_BASE = 0xC0
SHOP_LABEL_VRAM = 0x8C00
SHOP_PRICE_KEY = 0xC361
SHOP_GITAN_KEY = 0xC4A1
SHOP_VALUE_CLASS = 0x06

# The standing stair/trap command is the unique WRAM box (x3,y4,rows2,width5,flags0).
# Proceed/Trigger paint five tiles after the cursor, so widen only that descriptor to six
# output cells. A bank-53 gate validates the exact shape and rewrites trap row 1 from the
# shared Stay source to Back before the proportional scanner reaches it.
GROUND_POPUP_BOX = 3
GROUND_POPUP_WIDTH_OLD = 5
GROUND_POPUP_WIDTH = 6
GROUND_POPUP_BANK = 0x35
GROUND_POPUP_INDEX = 0x07

# The GameShark-enabled debug category screen (screen 27) uses ROM boxes 33/34, already
# covered by the static ROM-row VWF path.  Selecting a category dispatches screen 28 and
# stages four item names through box 35 at $C616.  That box normally falls back to the
# fixed font; after visiting the status/Items screens, statusvwf's private low-page tiles
# deliberately no longer contain the fixed alphabet, so the fallback becomes garbage.
# Admit only the exact hidden boxes.  The four-row picker resets the ordinary dynamic
# allocator at row 0.  Its weapon enhancement editor then reuses that live generation
# for the exact ``raw blank, '+', tens, ones, terminator`` payload; leaving the native
# digits in place is unsafe because their fixed-font planes have already been borrowed
# by proportional menu rows.  The helper lives in the next pool-bank prefix because
# bank 32 has too little room.
DEBUG_MENU_BOX = 35
DEBUG_VALUE_BOX = 36
DEBUG_MENU_BANK = 0x36
DEBUG_MENU_INDEX = 0x05
DEBUG_MENU_AT = 0x405A
DEBUG_MENU_LIMIT = 0x4100
DEBUG_MENU_SHAPE = (4, 0, 4, 14, 0)
DEBUG_VALUE_SHAPE = (6, 13, 1, 5, 0)

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
ROM_RAW_PREFIX_BOXES = (8,)
ROM_RAW_PREFIX_BIT = 0x20    # measured post-draw cursor overwrite of a nonzero cell
ROM_LONG_SOURCE_BOXES = (8, 14, 18, 29, 33, 34, 47)
ROM_LONG_SOURCE_BIT = 0x10   # source ends at $FF rather than descriptor width
ROM_POOL_BASE = 0xCB
ROM_POOL_END = 0xDE          # exclusive: nineteen contiguous tiles; $CA stays native
ROM_ONE_BASE = 0xC0
ROM_ONE_END = 0xC9           # one-row labels avoid the game's $D1-$D6 graphics reload
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
# The shared reader/index gate ends below $4060.  Start here so the allocator also has
# room for the saved-Log popup exception; rankvwf's manager still begins at $4180.
RANK_CATEGORY_AT = 0x4060
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
# repaint, so all three Log selections can safely reuse one 9+11+8 screen-local block.
# $DE-$F9 is absent from the settled title/log map; startspill checks the *whole* range
# for outside owners whenever a summary is visible.
# This avoids the native $A4/$AF empty-box / separator tiles and $C4 completed checkbox
# without relying on a later font restore.  The location is row 1's eleven-tile slice;
# numbered ``Moonlight Exit`` is the reachable maximum at eleven tiles for every floor
# from 1F through 50F.  Numbered ``Dragon's Maw`` is next at ten tiles.
SUMMARY_POOL_ROWS = (0xDE, 0xE7, 0xF2)
SUMMARY_POOL_CAPS = (9, 11, 8)
SUMMARY_SOURCE_CAP = 19
SUMMARY_ALT_POOL_ROWS = SUMMARY_POOL_ROWS
# Direct saved-title censuses prove $82-$8A and $9A-$A0 have no settled references
# outside box 27 while an erase confirmation is visible, or outside the exact box-21
# Continue/New Game popup while it is visible over a saved summary.  That second context
# matters for completed Log records: the generic two-row ROM pool begins at $CB and used
# to repaint the still-visible Orochi badge at $CB-$CE with letters from ``Continue``.
# Box 45 is mutually exclusive with those flows and has the same result, while its
# still-visible eighth title row owns $8B-$90. Keep these slices context-static rather
# than adding them to the global pool.
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


DEBUG_MENU_SRC = """
debugshape:
  ; Preserve the start/file selector classifications that used to be called directly
  ; from startaux's ssnone tail, then own only the otherwise-unclassified debug box.
  ; That classifier is free to use BC.  Here BC is also menurow's live staged-source
  ; pointer, so preserve it or screen 28's next row advances from $C6xx into arbitrary
  ; ROM and paints instruction bytes as menu text.
  push bc
  xor a
  rst $10
  db $%02X,$%02X
  pop bc
  and a
  ret nz
  ld a,[$C69A]
  cp $04
  jr z,debugpicker
  cp $06
  jr z,debugvalue
  jp debugbad
debugvalue:
  ; Screen 29's enhancement control is the only box at this geometry, but also
  ; validate its live WRAM source so another future five-cell box cannot borrow the
  ; debug allocator merely by sharing coordinates.
  ld a,[$C69B]
  cp $0D
  jr nz,debugvaluebad
  ld a,[$C69C]
  cp $01
  jr nz,debugvaluebad
  ld a,[$C69D]
  cp $05
  jr nz,debugvaluebad
  ld a,[$C69E]
  and a
  jr nz,debugvaluebad
  ld a,d
  and a
  jr nz,debugvaluebad
  ld a,b
  cp $C6
  jr z,debugvaluesource
debugvaluebad:
  xor a
  ret
debugvaluesource:
  push hl
  ld h,b
  ld l,c
  ld a,[hl+]
  and a
  jr nz,debugbadpop
  ld a,[hl+]
  cp $7C
  jr nz,debugbadpop
  ld a,[hl+]
  cp $0B
  jr nc,debugbadpop
  ld a,[hl+]
  and a
  jr z,debugbadpop
  cp $0B
  jr nc,debugbadpop
  ld a,[hl]
  cp $FF
  jr nz,debugbadpop
  pop hl
  jr debugready
debugbadpop:
  pop hl
  xor a
  ret
debugpicker:
  ld a,[$C69B]
  and a
  jr nz,debugbad
  ld a,[$C69C]
  cp $04
  jr nz,debugbad
  ld a,[$C69D]
  cp $0E
  jr nz,debugbad
  ld a,[$C69E]
  and a
  jr nz,debugbad
  ld a,d
  cp $04
  jr nc,debugbad
  and a
  jr nz,debugready
  ld a,$43
  ld [$C1AE],a
  ld a,$8B
  ld [$C1AF],a
  ld a,$9A
  ld [$C1B0],a
  xor a
  ld [$C1B2],a
debugready:
  xor a
  ld [$C1B1],a
  inc a
  ld [$C0D0],a
  ld a,$03
  ret
debugbad:
  xor a
  rst $10
  db $%02X,$%02X
  ret
""" % (SELECTOR_INDEX, SELECTOR_BANK, SHOP_SHAPE_INDEX, SHOP_SHAPE_BANK)


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

selectorrow:
  dec de
  ld c,$02
  add a,c
  ld [de],a
  inc de
  ld a,$FF
  ld [de],a
  inc de
  ret

"""


RANK_CATEGORY_SRC = """
rankcategoryalloc:
  ; The exact saved-Log Continue/New Game popup is drawn over a still-visible summary.
  ; Its native Orochi badge owns $CB-$CE, so it must not enter the generic two-row pool
  ; at $CB.  Reuse the independently censused confirmation slices instead.
  ld a,[$C69A]
  cp $03
  jr nz,categorynormal
  ld a,[$C69B]
  cp $04
  jr nz,categorynormal
  ld a,[$C69C]
  cp $02
  jr nz,categorynormal
  ld a,[$C69D]
  cp $0A
  jr nz,categorynormal
  ld a,[$C69E]
  and $1F
  jr nz,categorynormal
  ld a,d
  and a
  jr z,continue0
  cp $01
  jr nz,categorybad
  ld a,[$C0D3]
  cp $08
  jr nc,categorybad
  ld a,$%02X
  jr categoryok
continue0:
  ld a,[$C0D3]
  cp $0A
  jr nc,categorybad
  ld a,$%02X
  jr categoryok
categorynormal:
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
""" % (CONFIRM_POOL_ROWS[1], CONFIRM_POOL_ROWS[0],
         RANK_CATEGORY_ROW0_BASE, RANK_CATEGORY_ROW1_BASE,
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
  cp $0C
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
  ; Screen 28 stages all four selected-category rows in WRAM. The native wrapper
  ; republishes live BC after menurow returns, so return its next staged source here.
  ; Other ROM boxes advance through their native producer and retain the incoming pair.
  ld a,[$C69A]
  cp $04
  jr nz,summarynative
  ld a,[$C69B]
  and a
  jr nz,summarynative
  ld a,[$C69C]
  cp $04
  jr nz,summarynative
  ld a,[$C69D]
  cp $0E
  jr nz,summarynative
  ld a,[$C0CC]
  ld c,a
  ld [$C69F],a
  ld a,[$C0CD]
  ld b,a
  ld [$C6A0],a
  ret
summarynative:
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


# Admitted screen-2 Action rows have a private six-by-four-tile pool. The admission gate
# runs on row 0 before allocation and proves the direct Status/Items/Action stack, the
# carried inventory or settled standing-Floor context, standard viewport, and absence of
# every private ID in both live layers. A shop page therefore rejects structurally because
# its $D0-$DE price cells intersect the private run. Unknown callers retain the shared
# allocator.
ACTION_GATE_SRC = """
actiongate:
  push bc
  push de
  push hl
  xor a
  ld [$C1B6],a
  ld a,[$C1B3]
  and a
  jr nz,agdone
  ld a,[$C6A3]
  cp $02
  jr nz,agdone
  ld a,[$C534]
  cp $02
  jr nz,agdone
  ld a,[$C535]
  and a
  jr nz,agdone
  ld a,[$C536]
  cp $01
  jr nz,agdone
  ld a,[$C537]
  cp $02
  jr nz,agdone
  ld a,[$C6DE]
  and a
  jr nz,agdone
  ld a,[$C6AA]
  and a
  jr z,agdone
  cp $15
  jr nc,agdone
  ld b,a
  ld a,[$C6AC]
  cp b
  jr c,agselectorok
  ; The settled standing-item Floor page uses selector $FF. It is a real screen-1
  ; parent, but only its explicit settlement latch may broaden the held-item gate.
  inc a
  jr nz,agdone
  ld a,[$C1B7]
  dec a
  jr nz,agdone
agselectorok:
  ldh a,[$FF40]
  and $F8
  cp $E0
  jr nz,agdone
  ldh a,[$FF42]
  and a
  jr nz,agdone
  ldh a,[$FF43]
  and a
  jr nz,agdone
  ldh a,[$FF4A]
  cp $80
  jr nz,agdone
  ldh a,[$FF4B]
  cp $07
  jr nz,agdone
  ld hl,$9800
  ld b,$10
  call agscan
  jr c,agdone
  ld hl,$9C00
  ld b,$02
  call agscan
  jr c,agdone
  ; Row 0 runs before box 6 publication, so the Item page marker is still intact in
  ; shadow. Preserve its exact seven-cell right edge for the B-pop parent restore.
  ld a,$02
  rst $10
  db $%02X,$%02X
  ld a,$01
  ld [$C1B6],a
agdone:
  pop hl
  pop de
  pop bc
  ret
agscan:
  ld c,$14
agcell:
  ld a,[hl+]
  cp $%02X
  jr c,agsafe
  cp $%02X
  jr c,agcollision
agsafe:
  dec c
  jr nz,agcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,agnocarry
  inc h
agnocarry:
  dec b
  jr nz,agscan
  and a
  ret
agcollision:
  scf
  ret
""" % (ACTION_BLANK_INDEX, ACTION_BLANK_BANK,
         ACTION_POOL_BASE, ACTION_POOL_END)


# The allocator entry replaces the in-bank packing block, returning B=base, C=cap and
# carry on rejection. Non-screen-2 rows execute the prior 57+11+4 policy byte-for-byte;
# the first six rows of an admitted carried-/Floor-Action receive $C7+4*row. The only
# possible later row is the seventh `Info` verb on an unidentified ground Pot. It returns
# to the ordinary allocator used by the one-row Floor parent; that parent occupies the
# mid run, leaving the base run available without extending the private pool into the
# difficulty renderer's $E0+ ownership.
ACTION_ALLOC_SRC = """
actionalloc:
  ld a,[$C6A3]
  cp $02
  jr nz,aageneral
  ld a,[$C69A]
  cp $0D
  jr nz,aageneral
  ld a,d
  and a
  jr nz,aapermit
  xor a
  rst $10
  db $%02X,$%02X
aapermit:
  ld a,[$C1B6]
  and a
  jr z,aageneral
  ld a,c
  cp $05
  jr nc,aafail
  ld a,d
  cp $06
  jr nc,aageneral
  add a,a
  add a,a
  add a,$%02X
  ld b,a
  jr aaok
aageneral:
  ld a,[$C1B1]
  cp $01
  jr nz,aatrybase
  ld a,c
  cp $0C
  jr nc,aatrybase
  ld a,[$C1AF]
  cp $8B
  jr nz,aatrybase
  ld b,a
  add a,c
  cp $97
  jr nc,aafail
  ld [$C1AF],a
  jr aaok
aatrybase:
  ld a,[$C1AE]
  ld b,a
  add a,c
  cp $7D
  jr nc,aatrymid
  ld [$C1AE],a
  jr aaok
aatrymid:
  ld a,[$C1AF]
  ld b,a
  add a,c
  cp $97
  jr nc,aatrysmall
  ld [$C1AF],a
  jr aaok
aatrysmall:
  ld a,[$C1B0]
  ld b,a
  add a,c
  cp $9F
  jr nc,aafail
  ld [$C1B0],a
aaok:
  and a
  ret
aafail:
  scf
  ret

; The title/file atomic publisher runs before 4:$4E2B installs the native initial
; cursor. Pre-stage only screen 15's selected box-1 cell so the first complete Adventure
; map already contains it; the native writer repeats the same store afterward.
titlecursor:
  ld a,[$C6A3]
  cp $0F
  ret nz
  push bc
  push hl
  ld a,[$C6A5]
  ld c,$00
  ld b,a
  srl b
  rr c
  srl b
  rr c
  ld hl,$C341
  add hl,bc
  ld [hl],$81
  pop hl
  pop bc
  ret
""" % (ACTION_GATE_INDEX, ACTION_GATE_BANK, ACTION_POOL_BASE)


# The native B path calls the shared stack popper with HL still equal to the exact
# screen-2 B handler ($5689).  Hooking the popper's existing depth arithmetic provides
# enough room to arm only that call site while preserving every other caller.  State 7
# is the fully validated pre-pop proof; the same call restores box 6's covered parent
# before native Status reconstruction can repaint tiles still referenced by the Action
# map. A successful restore returns carry so the call-site patch can skip that now-
# redundant reconstruction; a failed proof returns carry clear to the native path.
ACTION_POP_SRC = """
actionpop:
  ld c,a
  ; Before the native one-level screen-7 pop can dispatch screen 0, let statusvwf prove
  ; the exact B handler/stack/shape and publish complete empty Status chrome. Rejected
  ; callers are register-transparent and continue through the unchanged classifiers.
  ld a,$01
  rst $10
  db $%02X,$%02X
  ; A ground-Pot See viewer is a one-level child of its retained screen-7 Action
  ; parent. Give that exact stack first refusal before the generic screen-4/5 pop
  ; classification; success has already performed the depth subtraction and arms the
  ; same chrome-first screen-7 replay used by Info.
  ld a,$03
  rst $10
  db $%02X,$%02X
  jr nc,apordinary
  and a
  ret
apordinary:
  ld a,c
  cp $02
  jr nz,apnotpot
  ; A carried Pot viewer pops screen 12/13 and its Action parent together. Hand the
  ; exact pre-pop proof to bank 62 so the disposable Status replay can be skipped
  ; and screen 1 can precommit its windows before restoring any Item rows.
  ld a,[$C6A3]
  cp $0C
  jr z,appot
  cp $0D
  jr nz,apinfo
appot:
  ld a,$03
  rst $10
  db $%02X,$%02X
  jr nc,apinfo
  and a
  ret
apnotpot:
  cp $01
  jp nz,apsub
  ; Screen-20 Info has C6DE bit 0 set, so the native pop amount is one rather than
  ; screen 1's two. Admit its B and final-page A/D-pad handlers before testing the
  ; separate screen-2 Action B path.
  ld a,h
  cp $59
  jr z,apinfoadvance
  cp $56
  jp nz,apsub
  ld a,l
  cp $91
  jr z,apinfotry
  cp $89
  jp nz,apsub
  jr apactionproof
apinfo:
  ld a,h
  cp $59
  jr z,apinfoadvance
  cp $56
  jp nz,apsub
  ld a,l
  cp $91
  jp nz,apsub
  jr apinfotry
apinfoadvance:
  ld a,l
  cp $26
  jp nz,apsub
apinfotry:
  xor a
  rst $10
  db $%02X,$%02X
  jr nc,apsub
  and a
  ret
apactionproof:
  ld a,[$C1B3]
  and a
  jr nz,apsub
  ld a,[$C1B6]
  dec a
  jr nz,apsub
  ld a,[$C6A3]
  cp $02
  jr nz,apsub
  ld a,[$C534]
  cp $02
  jr nz,apsub
  ld a,[$C6BB]
  cp $04
  jr c,apsub
  cp $07
  jr nc,apsub
  ld [$C1B4],a
  ld a,[$C6AC]
  cp $FF
  jr nz,apheldselector
  ld a,[$C1B7]
  dec a
  jr nz,apsub
  ld b,$1F
  jr appack
apheldselector:
  ld b,a
  inc b
  ld a,[$C6AA]
  cp b
  dec b
  jr c,apsub
appack:
  ld a,[$C1B5]
  or b
  ld [$C1B5],a
  ; The exact fast path owns the already-restored shadow and visible parent, so perform
  ; the native depth subtraction before the restorer validates the post-pop stack.
  ld a,[$C534]
  sub c
  ld [$C534],a
  ld a,$07
  ld [$C1B3],a
  xor a
  rst $10
  db $%02X,$%02X
  ret
apsub:
  ld a,[$C534]
  sub c
  ld [$C534],a
  ret
""" % (STATUS_FLOOR_PRE_INDEX, STATUS_FLOOR_PRE_BANK,
         INFO_RETURN_INDEX, ACTION_BLANK_BANK,
         ACTION_BLANK_INDEX, ACTION_BLANK_BANK,
         INFO_POP_INDEX, ACTION_BLANK_BANK,
         ACTION_BLANK_INDEX, ACTION_BLANK_BANK)


# From the exact pre-pop Action B path, reconstruct box 6's 7 x (2*rows+1) covered parent
# (the native picker inserts one spacer tile row after every verb). The admission hook
# saves the exact page-marker edge; retained Item row records recreate any covered VWF
# tails. The completed shadow region is copied in one VBlank before screen 0 can repaint
# tile data still referenced by the outgoing Action map. Because the shadow parent and
# Item raster records remain owned, the helper also restores the Item input-machine state
# and returns directly instead of replaying screen 0 and screen 1.
ACTION_BLANK_SRC = """
actionblank:
  cp $03
  jp z,potpop
  cp $02
  jp z,absave
  and a
  jp nz,abfinish
  ; Screen 11's Put selector reaches this existing mode-zero first refusal before
  ; the legacy item-page controller can disable the LCD. Bank 53 owns its exact
  ; chrome-first regional transaction; every rejected caller resumes unchanged.
  ld a,[$C6A3]
  cp $0B
  jr nz,abzero
  rst $10
  db $%02X,$%02X
  ret c
abzero:
  xor a
  ld a,[$C1B3]
  cp $07
  jr z,abstart
  cp $08
  jr z,abinfo
  cp $09
  jr z,abinfo
  cp $0B
  jr nz,abidle
abinfo:
  xor a
  rst $10
  db $%02X,$%02X
  jp abowned
abidle:
  ld a,[$C6A3]
  sub $0C
  cp $02
  ret nc
  ld a,$04
  rst $10
  db $%02X,$%02X
  ret
abstart:
  ld a,[$C6A3]
  cp $02
  jr z,abprepop
  and a
  jp z,abowned
  cp $01
  jp nz,abfail
  ld a,[$C534]
  cp $01
  jp nz,abfail
  jr abstack
abprepop:
  ld a,[$C534]
  cp $01
  jp nz,abfail
abstack:
  ld a,[$C535]
  and a
  jp nz,abfail
  ld a,[$C536]
  cp $01
  jp nz,abfail
  ld a,[$C537]
  cp $02
  jp nz,abfail
  ld a,[$C6DE]
  and a
  jp nz,abfail
  ld a,[$C1B6]
  dec a
  jp nz,abfail
  ld a,[$C1B4]
  cp $04
  jp c,abfail
  cp $07
  jp nc,abfail
  ld a,[$C1B5]
  and $1F
  ld b,a
  ld a,[$C6AC]
  cp $FF
  jr nz,abheldselector
  ld a,b
  cp $1F
  jp nz,abfail
  ld a,[$C1B7]
  dec a
  jp nz,abfail
  jr abselectorok
abheldselector:
  cp b
  jp nz,abfail
abselectorok:
  ldh a,[$FF40]
  and $F8
  cp $E0
  jp nz,abfail
  ldh a,[$FF42]
  and a
  jp nz,abfail
  ldh a,[$FF43]
  and a
  jp nz,abfail
  ldh a,[$FF4A]
  cp $80
  jp nz,abfail
  ldh a,[$FF4B]
  cp $07
  jp nz,abfail
  push bc
  push de
  push hl
  ; Build the covered parent in shadow before entering the time-bounded VBlank copy.
  ; Rows 1-2 are genuinely empty; row 3 is the exact saved page marker.
  ld hl,$C32D
  ld b,$02
abtoprow:
  xor a
  ld c,$07
abtopcell:
  ld [hl+],a
  dec c
  jr nz,abtopcell
  call abnextline
  dec b
  jr nz,abtoprow
  ld de,$C1B8
  ld c,$07
abmarkercell:
  ld a,[de]
  inc de
  ld [hl+],a
  dec c
  jr nz,abmarkercell
  call abnextline

  ; Item name tiles begin at x=3. Recreate their covered x=13..18 tail from the
  ; retained five-byte row record (indices 10..15), then restore the native x=19
  ; border. Referencing an unused capacity tile is pixel-equivalent to tile 0 because
  ; every allocation clears its complete cap before composition.
  ld a,[$C1B4]
  dec a
  ld b,a
  ld de,$C380
abparentrow:
  push bc
  push de
  push hl
  ld a,[$C1B2]
  and a
  jr z,abnorecord
  ld b,a
  ld hl,$C163
abfindrecord:
  ld a,[hl+]
  cp e
  jr nz,abnextrecord
  ld a,[hl]
  cp d
  jr z,abrecordfound
abnextrecord:
  ld a,l
  add a,$04
  ld l,a
  jr nc,abrecordnocarry
  inc h
abrecordnocarry:
  dec b
  jr nz,abfindrecord
abnorecord:
  ld d,$00
  ld c,$00
  jr abtailready
abrecordfound:
  inc hl
  ld a,[hl+]
  ld d,a
  ld a,[hl]
  ld c,a
abtailready:
  pop hl
  ld b,$0A
  ld e,$06
abtailcell:
  ld a,c
  cp b
  jr c,abtailblank
  jr z,abtailblank
  ld a,d
  add a,b
  jr abtailstore
abtailblank:
  xor a
abtailstore:
  ld [hl+],a
  inc b
  dec e
  jr nz,abtailcell
  ld [hl],$BF
  inc hl
  call abnextline
  pop de
  pop bc
  ld a,e
  add a,$40
  ld e,a
  jr nc,abkeyready
  inc d
abkeyready:
  ; A settled Floor parent has one real row. Its first separator is the bottom border;
  ; every later cell covered by the Action box belongs to the blank field.
  ld a,[$C6AC]
  inc a
  jr z,abfloorbottom
  ; Four- and five-row Action boxes end above the Item bottom edge. A six-row box
  ; covers it, so its final intervening line is the native bottom border, not spacer.
  ld a,[$C1B4]
  cp $06
  jr nz,abspacer
  ld a,b
  dec a
  jr z,abbottom
abspacer:
  xor a
  jr abseparator
abbottom:
  ld a,$BD
  jr abseparator
abfloorbottom:
  ld a,$BD
abseparator:
  ld c,$06
abseparatorcell:
  ld [hl+],a
  dec c
  jr nz,abseparatorcell
  cp $BD
  ld a,$BF
  jr nz,abseparatorend
  ld a,$BB
abseparatorend:
  ld [hl],a
  inc hl
  ld a,[$C6AC]
  inc a
  jr z,abfloorrest
  dec b
  jr z,abshadowready
  call abnextline
  jp abparentrow
abfloorrest:
  dec b
  jr z,abshadowready
  ld a,b
  add a,a
  ld b,a
  call abnextline
abfloorline:
  xor a
  ld c,$07
abfloorcell:
  ld [hl+],a
  dec c
  jr nz,abfloorcell
  dec b
  jr z,abshadowready
  call abnextline
  jr abfloorline
abnextline:
  ld a,l
  add a,$19
  ld l,a
  ret nc
  inc h
  ret
abshadowready:
abdrain:
  ld a,[$C11A]
  and a
  jr z,abdrained
  call $06F7
  jr abdrain
abdrained:
  di
absync:
  ldh a,[$FF44]
  cp $90
  jr nc,absync
abwait:
  ldh a,[$FF44]
  cp $90
  jr c,abwait
  ld a,[$C1B4]
  add a,a
  inc a
  ld b,a
  ld hl,$C32D
  ld de,$982D
abcopyrow:
  call abcopyseven
  call abnextline
  ld a,e
  add a,$19
  ld e,a
  jr nc,abcopydestready
  inc d
abcopydestready:
  dec b
  jr nz,abcopyrow
  jr abrestored
abcopyseven:
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ld a,[hl+]
  ld [de],a
  inc e
  ret
abrestored:
abblanked:
  ; The Action builder appended private records to the retained Item/Floor records.
  ; Restore the saved count, then re-establish the compact menu state that native
  ; screen-1 reconstruction would produce. Both tilemaps are already the exact parent.
  ld a,[$C1B5]
  rlca
  rlca
  rlca
  and $07
  ld [$C1B2],a
  ld a,$04
  ld [$C1B1],a
  ld a,[$C6AC]
  cp $FF
  jr z,abfloorstate
abheldstate:
  ld a,$04
  ld [$C6A4],a
  inc a
  ld [$C6BB],a
  ld a,[$C1B5]
  and $1F
abcursormod:
  cp $05
  jr c,abcursorready
  sub $05
  jr abcursormod
abcursorready:
  ld [$C6A5],a
  ld a,$42
  ld [$C6A0],a
  ld a,$82
  ld [$C6A7],a
  xor a
  ld [$C6A8],a
  ld hl,$C69A
  xor a
  ld [hl+],a
  ld a,$03
  ld [hl+],a
  ld a,$05
  ld [hl+],a
  ld a,$12
  ld [hl+],a
  ld a,$02
  ld [hl],a
  jr abstatecommon
abfloorstate:
  xor a
  ld [$C6A4],a
  ld [$C6A5],a
  inc a
  ld [$C6BB],a
  ; Restore the exact settled box-18 descriptor left by the standing Floor page.
  ld hl,$C69A
  xor a
  ld [hl+],a
  ld [hl+],a
  inc a
  ld [hl+],a
  ld a,$04
  ld [hl+],a
  ld a,$50
  ld [hl+],a
  ld a,$5C
  ld [hl+],a
  ld a,$43
  ld [hl],a
  ld a,$82
  ld [$C6A7],a
  xor a
  ld [$C6A8],a
abstatecommon:
  ld a,$01
  ld [$C6A3],a
  xor a
  ld [$C1B3],a
  ld [$C1B6],a
  ei
  pop hl
  pop de
  pop bc
abowned:
  scf
  ret
abfinish:
  ld a,[$C1B3]
  cp $0C
  jr nz,abfinishnotpot
  ld a,$05
  rst $10
  db $%02X,$%02X
  ret
abfinishnotpot:
  cp $07
  jp z,abowned
  cp $09
  jp z,abowned
  cp $0B
  jr nz,abfinishnot7
  ; Screen 0 is only the native replay's disposable bridge. Do not let its completed
  ; empty pass retire state $0B; screen 7 must build and publish the real Floor parent.
  ld a,[$C6A3]
  and a
  jp z,abowned
  ld a,$02
  jr abfinishcall
abfinishnot7:
  cp $08
  jr nz,abnotowned
  ld a,[$C6A3]
  dec a
  jp nz,abowned
  ld a,[$C1B1]
  cp $04
  jp nz,abowned
  ld a,[$C0DA]
  cp $C3
  jp nz,abowned
  ld a,[$C69C]
  cp $01
  jp nz,abowned
  ld a,[$C69D]
  cp $04
  jp nz,abowned
  ld a,$01
abfinishcall:
  rst $10
  db $%02X,$%02X
  jp nc,abfail
  xor a
  ld [$C1B3],a
  ld [$C1B6],a
  scf
  ret
abnotowned:
  and a
  ret
abfail:
  xor a
  ld [$C1B3],a
  ld [$C1B6],a
  ret

; Exact carried-Pot See B path. The native pop removes screen 12/13 and screen 2,
; then rebuilds disposable screen 0 before screen 1. State $0A is a capability handed
; to statusvwf: screen 0 must stay invisible, and screen 1 must retire the Pot map and
; publish complete empty Items chrome before any row text.
potpop:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  and a
  jp nz,potpopbad
  ld a,[$C6A3]
  ld e,a
  sub $0C
  cp $02
  jp nc,potpopbad
  ; Screen 12 can retain zero or one from Action admission; screen 13 must retain
  ; zero. Reject two-plus first, then distinguish the only nonzero case by screen.
  ld a,[$C1B6]
  cp $02
  jp nc,potpopbad
  and a
  jr z,potpoptypeok
  ld a,e
  cp $0C
  jp nz,potpopbad
potpoptypeok:
  ld a,[$C6A6]
  and a
  jp nz,potpopbad
  ld a,[$C6DE]
  and a
  jp nz,potpopbad
  ld a,[$C534]
  cp $03
  jr nz,potpopbad
  ld hl,$C535
  ld a,[hl+]
  and a
  jr nz,potpopbad
  ld a,[hl+]
  dec a
  jr nz,potpopbad
  ld a,[hl+]
  cp $02
  jr nz,potpopbad
  ld a,[hl]
  cp e
  jr nz,potpopbad
  ld a,[$C6AA]
  and a
  jr z,potpopbad
  cp $15
  jr nc,potpopbad
  ld b,a
  ; A Pot reached by paging from carried Items to the appended Floor page still has
  ; stack 0,1,2,12/13, but selector $FF has already been repurposed by the viewer.
  ; The settled-Floor latch is the retained proof; screen-1 entry consumes it below.
  ld a,[$C1B7]
  dec a
  jr z,potpopselectorok
  ld a,[$C6AC]
  cp b
  jr nc,potpopbad
potpopselectorok:
  ld hl,$C69A
  ld a,[hl+]
  and a
  jr nz,potpopbad
  ld a,[hl+]
  and a
  jr nz,potpopbad
  ld a,[hl+]
  dec a
  jr nz,potpopbad
  ld a,[hl+]
  cp $03
  jr nz,potpopbad
  ld a,[hl]
  cp $40
  jr nz,potpopbad
  ldh a,[$FF40]
  and $F8
  cp $E0
  jr nz,potpopbad
  ldh a,[$FF42]
  and a
  jr nz,potpopbad
  ldh a,[$FF43]
  and a
  jr nz,potpopbad
  ldh a,[$FF4A]
  cp $80
  jr nz,potpopbad
  ldh a,[$FF4B]
  cp $07
  jr nz,potpopbad
  ; The appended Floor page needs the already-proven screen-1 Info replay rather than
  ; the carried-Items state-$0A entry. Its tiny far helper packs selector $1F into the
  ; retained record byte and returns A=$08. Carried Pot viewers keep state $0A.
  ld a,[$C1B7]
  dec a
  jr nz,potpopcarried
  call $%04X
  jr potpoparm
potpopcarried:
  ld a,$0A
potpoparm:
  ld [$C1B3],a
  ld hl,$C534
  dec [hl]
  dec [hl]
  scf
  jr potpopdone
potpopbad:
  and a
potpopdone:
  pop hl
  pop de
  pop bc
  ret
absave:
  push bc
  push de
  push hl
  ld hl,$C36D
  ld de,$C1B8
  ld c,$07
absavecell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,absavecell
  ; At most five retained Item records precede the private Action records. Rotate that
  ; three-bit count into C1B5's high bits; B-pop later adds the five-bit selector.
  ld a,[$C1B2]
  rrca
  rrca
  rrca
  ld [$C1B5],a
  pop hl
  pop de
  pop bc
  and a
  ret
""" % (POT_PUT_ENTRY_INDEX, POT_PUT_ENTRY_BANK,
         INFO_RETURN_INDEX, ACTION_BLANK_BANK,
         INFO_RETURN_INDEX, ACTION_BLANK_BANK,
         INFO_RETURN_INDEX, ACTION_BLANK_BANK,
         INFO_RETURN_INDEX, ACTION_BLANK_BANK,
         POT_FLOOR_RETURN_AT)


# Ordinary page changes keep ``irclear``. A shape change involving selector $FF instead
# comes here with HL at row 4 and atomically converts the known settled source rectangle
# into the complete empty destination rectangle. Hot full-row fills are unrolled so the
# larger Items -> Floor contraction still finishes inside one VBlank. The same
# address-relative code serves shadow and visible BG; the enclosing regional gate has
# already saved the caller's BC/DE.
FLOOR_CHROME_SRC = """
floorchrome:
  ; Box 4 (the list body) is followed by box 14 or 18 (the Items/Floor header) in
  ; native screen-1 order.  Both headers use the same four-cell interior and the same
  ; private VWF tiles.  Retire those references with the body so the incoming word can
  ; be composed without repainting a title that scanout can still see.
  ld l,$21
  xor a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl],a
  ld l,$80
  ld a,[$C6AC]
  inc a
  jr z,fccontract
  ld a,[$C1B7]
  dec a
  jr nz,fcdecline
  ld de,$000C
  ; Floor -> carried Items. Rows 6-12 are structurally absent in the settled source,
  ; so only their new side borders need to be written.
  call fcsiderow
  call fcsiderow
  ld b,$07
fcexpandrows:
  call fcborders
  dec b
  jr nz,fcexpandrows
  call fcbottom
fcexpanddone:
  scf
  ret
fccontract:
  ld de,$000C
  ; Carried Items -> Floor. Retire page dots in the shared top border first.
  ld l,$60
  ld [hl],$B8
  ld l,$6F
  ld a,$BC
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl],a
  ld l,$73
  ld [hl],$B9
  ld l,$80
  ; Rows 4-5 become the complete empty one-row Floor box.
  call fcsiderow
  call fcbottom
  ; Clear four old text rows, the three interleaved side-border-only rows, and the
  ; old bottom. Each helper advances exactly one tilemap row.
  ld b,$03
fccontractrows:
  call fcclearrow
  call fcabsentrow
  dec b
  jr nz,fccontractrows
  call fcclearrow
  call fcclearrow
fccontractdone:
  scf
  ret
fcdecline:
  and a
  ret
fcsiderow:
  ld a,$BE
  ld [hl+],a
  xor a
  call fcfill18
  ld a,$BF
  ld [hl+],a
  add hl,de
  ret
fcbottom:
  ld a,$BA
  ld [hl+],a
  ld a,$BD
  call fcfill18
  ld a,$BB
  ld [hl+],a
  add hl,de
  ret
fcborders:
  ld a,$BE
  ld [hl],a
  ld a,l
  add a,$13
  ld l,a
  ld a,$BF
  ld [hl+],a
  add hl,de
  ret
fcabsentrow:
  xor a
  ld [hl],a
  ld a,l
  add a,$13
  ld l,a
  xor a
  ld [hl+],a
  add hl,de
  ret
fcclearrow:
  xor a
  ld [hl+],a
  ld [hl+],a
  call fcfill18
  add hl,de
  ret
fcfill18:
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ld [hl+],a
  ret
"""


# Bank 60 retains the safe whole-screen controller for Pot screens and for a regional
# screen-1 attempt that has to fall back. Screen 1's LCD-on paging/Start-sort path is begun and
# published by ITEM_REGION_SRC; state 1 plus screen 1 therefore means "regional", while
# state 5 means that regional rendering encountered a fallback and the old atomic
# whole-map publication must finish it; state 6 keeps initial/declined Items entry on
# that same path. Mode 2 still supports the legacy short-page/Pot
# completion boundary when no regional transaction owns the row.
ITEM_PAGE_SRC = """
itempage:
  and a
  jr z,pageblank
  dec a
  jp z,pagepublish
  jr pageempty
pageblank:
  xor a
  rst $10
  db $%02X,$%02X
  ret c
  xor a
  rst $10
  db $%02X,$%02X
  ld a,[$C6A3]
  dec a
  jr nz,pblegacy
  ld a,[$C1B3]
  cp $01
  ret z
pblegacy:
  ld a,[$C0D5]
  and a
  ret z
  ld a,[$C0D9]
  cp $80
  ret nz
  ldh a,[$FF40]
  bit 7,a
  ret z
pbwait:
  ldh a,[$FF44]
  cp $90
  jr c,pbwait
pbdisable:
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
  ld a,[$C1B3]
  cp $06
  ret z
  ld a,$01
  ld [$C1B3],a
  ret
pageempty:
  ld a,$02
  rst $10
  db $%02X,$%02X
  ld a,[$C6A3]
  dec a
  jr nz,pelegacy
  ld a,[$C1B3]
  cp $01
  jr nz,pelegacy
  ld a,$01
  ld [$C0E7],a
  ret
pelegacy:
  ld a,[$C1B1]
  cp $01
  ret nz
  ld a,[$C0D9]
  cp $80
  ret nz
  ld a,[$C0DA]
  cp $C4
  ret nz
  ld hl,$C480
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
pagepublish:
  ld a,$01
  rst $10
  db $%02X,$%02X
  ret c
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,[$C1B3]
  and a
  ret z
  ld a,[$C6A3]
  dec a
  jr nz,pagelegacy
  ld a,[$C1B3]
  cp $01
  jr nz,pagelegacy
  ld a,[$C1B1]
  cp $04
  ret nz
  ld a,[$C69D]
  cp $04
  ret nz
  xor a
  ld [$C1B7],a
  ld a,[$C6AC]
  inc a
  jr nz,pagecomplete
  inc a
  ld [$C1B7],a
pagecomplete:
  xor a
  ld [$C1B3],a
  ld a,$03
  ld [$C1B6],a
  ret
pagelegacy:
  ld a,[$C1B1]
  cp $04
  ret nz
  ; Only box 14's four-cell Items header may finish an item-page transaction.
  ; Box 17 (Pot) shares this shadow-map position but is one cell narrower; treating
  ; it as Items pre-stages a six-cell bottom edge, leaving a stray $BB at x=5.
  ; Mode 4, an active page transaction, shadow bank $C3, and an exact width of three
  ; (Pot) or four (Items) identify the only accepted completion paths. Omitting the
  ; redundant $20 low-byte comparison keeps the helper inside its original allocation.
  ld a,[$C0DA]
  sub $C3
  ret nz
  ld a,[$C69D]
  sub $03
  jr z,pagefinish
  dec a
  ret nz
  ld b,$04
  ; rborder runs before the native box drawer emits this one-row header's bottom
  ; edge. Pre-stage that exact asserted box-14 edge so the full map is complete now;
  ; the native drawer writes the same six bytes immediately after we return.
  ld hl,$C340
  ld a,$BA
  ld [hl+],a
pebottom:
  ld [hl],$BD
  inc hl
  dec b
  jr nz,pebottom
  ld [hl],$BB
pagefinish:
  xor a
  rst $10
  db $%02X,$%02X
  ret
""" % (ACTION_BLANK_INDEX, ACTION_BLANK_BANK,
         ITEM_REGION_INDEX, ITEM_REGION_BANK,
         ITEM_REGION_INDEX, ITEM_REGION_BANK,
         ACTION_BLANK_INDEX, ACTION_BLANK_BANK,
         ITEM_REGION_INDEX, ITEM_REGION_BANK,
         ITEM_PUBLISH_INDEX, ITEM_PUBLISH_BANK)


# Screen 1's same-screen Left/Right and Start-sort transaction. Mode 0 runs after row 0
# has composed but before any reused tile pixels upload. The native item count and its
# synchronous redraw state prove this is a same-screen redraw rather than initial entry;
# the visible page marker is transaction output, not an admission input. It then
# normalizes the five marker-coupled left-border cells and
# blanks exactly the five raw status-marker cells plus the five 16-cell name interiors in
# shadow WRAM and, during VBlank, in the visible BG map.
# Mode 1 publishes one completed proportional row after its tile publication. Mode 2
# pre-stages and publishes an empty native-fallback row. Mode 3 recognizes the native
# fixed-width all-zero empty representation; any other fallback converts the live regional
# attempt to the legacy LCD-off state before it can repaint through the blank rows.
ITEM_REGION_SRC = """
itemregion:
  and a
  jr z,irbegin
  dec a
  jp z,irrow
  dec a
  jp z,irempty
  jp irfail
irbegin:
  ld a,[$C6A3]
  dec a
  ret nz
  ld a,[$C1B3]
  and a
  ret nz
  ld a,[$C1B1]
  dec a
  ret nz
  ld a,[$C0D9]
  cp $80
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,[$C0D5]
  and a
  jr nz,iready
  ; Initial Items entry reaches row 0 once before the allocator epoch exists, then
  ; revisits the row after the new page indicator has been drawn. Remember that first
  ; observation so the second pass cannot be mistaken for a same-screen page flip.
  ld a,$06
  ld [$C1B3],a
  ret
iready:
  ldh a,[$FF40]
  bit 7,a
  ret z
  push bc
  push de
  push hl
irwait:
  ldh a,[$FF44]
  cp $90
  jr c,irwait
  ; The preceding screen-1 publication can still own selector $C11A here.  In
  ; particular, one of its final map chunks contains the four page-marker cells.
  ; Validate only after that queue is complete: sampling it first could admit a
  ; partially-published marker shape and incorrectly select the LCD-off fallback.
irpredrain:
  ld a,[$C11A]
  and a
  jr z,irvalidatedrain
  call $06F7
  jr irpredrain
irvalidatedrain:
  ; Native Right/Left has already committed $C6AC and synchronously owns this screen-1
  ; redraw. It never reads the visible page indicator. Do not turn a harmless stale or
  ; partially-published $986F-$9872 into an LCD-off fallback: the screen/shape/epoch
  ; gates above and the native item-count bound below are the ownership proof. Initial
  ; Items entry remains excluded by its fresh-allocation latch above.
  ld a,[$C6AA]
  dec a
  cp $14
  jr nc,irdecline
  call $%04X
irdrain:
irshadow:
  ld de,$002D
  ld hl,$C380
  call irclear
irvisible:
  di
  ; The ROM's far-call trampoline executes EI while switching banks. Mask IE around the
  ; VBlank publication so a pending VBlank interrupt cannot consume the budget inside
  ; the shape helper; IME remains off until irarmed below.
  ldh a,[$FFFF]
  push af
  xor a
  ldh [$FFFF],a
irblanksync:
  ldh a,[$FF44]
  cp $90
  jr nc,irblanksync
irblankwait:
  ldh a,[$FF44]
  cp $90
  jr c,irblankwait
  ld hl,$9880
  call irclear
  di
  pop af
  ldh [$FFFF],a
irarmed:
  ld a,$01
  ld [$C1B3],a
  inc a
  ld [$C1B6],a
  ei
  pop hl
  pop de
  pop bc
  ret
irdecline:
  ld a,$06
  ld [$C1B3],a
  xor a
  ld [$C1B6],a
  pop hl
  pop de
  pop bc
  ret
irclear:
  ld a,[$C6AC]
  inc a
  jr z,irfloorshape
  ld a,[$C1B7]
  dec a
  jr nz,irclearnormal
irfloorshape:
  rst $10
  db $%02X,$%02X
  ret c
irclearnormal:
  ld b,$05
  ld a,$BE
  jr irclearstore
irclearrow:
  ; The standing-item Floor page has one row.  Its outgoing carried-item rows 1-4
  ; must be zeroed with their contents instead of retaining four empty left borders.
  ld a,[$C6AC]
  inc a
  jr z,irclearstore
  ; On Floor -> carried Items, the selector already names the incoming page.  Retain
  ; the outgoing Floor latch so rows 1-4 stay absent until each new row is complete.
  ld a,[$C1B7]
  dec a
  jr z,irclearstore
irclearborder:
  ld a,$BE
irclearstore:
  ld [hl+],a
  xor a
  ld [hl],a
  inc hl
  ld c,$11
irclearcell:
  ld [hl+],a
  dec c
  jr nz,irclearcell
  add hl,de
  dec b
  jr nz,irclearrow
  ret
irempty:
  ld b,$01
  jr ircheck
irrow:
  ld b,$00
ircheck:
  ld a,[$C1B3]
  dec a
  ret nz
  ld a,[$C6A3]
  dec a
  ret nz
  ld a,[$C1B1]
  dec a
  ret nz
  ld a,d
  cp $05
  ret nc
  push bc
  push de
  push hl
  ld a,b
  and a
  jr z,irpublish
iremptyitem:
  ld a,[$C0D9]
  ld l,a
  ld a,[$C0DA]
  ld h,a
  ld a,[$C0E0]
  ld [hl+],a
  ld a,[$C0E1]
  ld [hl+],a
  ld b,$11
  xor a
iremptycell:
  ld [hl+],a
  dec b
  jr nz,iremptycell
  ld [hl],$BF
irpublish:
irrowdrain:
  ld a,[$C11A]
  and a
  jr z,irrowready
  call $06F7
  jr irrowdrain
irrowready:
  di
  ldh a,[$FF40]
  bit 7,a
  jr z,ircopy
  ; The tile queue returns near the top of the next visible frame. Publish this
  ; completed map row through safe LCD-on VRAM slots in that same frame instead of
  ; idling until another VBlank. The helper finishes either before this row's scanout
  ; or after it has passed, so the player still sees only blank or complete content.
  call $%04X
  jr ircopied
ircopy:
  ld a,[$C0D9]
  ld l,a
  ld e,a
  ld a,[$C0DA]
  ld h,a
  sub $2B
  ld d,a
  ld c,$02
ircopyraw:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,ircopyraw
  inc hl
  inc de
  ld c,$10
ircopycell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,ircopycell
ircopied:
  ei
  pop hl
  pop de
  pop bc
  ret
irfail:
  ld a,[$C1B3]
  dec a
  ret nz
  ld a,[$C6A3]
  dec a
  jr nz,irfaillcd
  ld a,[$C1B1]
  dec a
  jr nz,irfaillcd
  ld a,d
  cp $05
  jr nc,irfaillcd
  ld a,[$C69D]
  cp $12
  jr nz,irfaillcd
  ; Empty slots on a short Items page are 19 zero bytes with no $FF terminator.
  ; Accept only that exact fixed-width native representation; every other scanner
  ; fallback still takes the conservative whole-screen publication path below.
  push bc
  push hl
  ld a,[$C0CC]
  ld l,a
  ld a,[$C0CD]
  ld h,a
  ld b,$13
irzero:
  ld a,[hl+]
  and a
  jr nz,irnotzero
  dec b
  jr nz,irzero
irfixedempty:
  pop hl
  pop bc
  ld a,$01
  ld [$C0E7],a
  ld b,$01
  jp ircheck
irnotzero:
  pop hl
  pop bc
  ; Give the shared exact-caller gate first refusal. The full cursed-equipment proof
  ; lives in bank 53 because this controller ends exactly at the following Action gate.
  rst $10
  db $%02X,$%02X
  ret c
irfaillcd:
  ldh a,[$FF40]
  bit 7,a
  jr z,irfailed
irfailwait:
  ldh a,[$FF44]
  cp $90
  jr c,irfailwait
irdisable:
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
irfailed:
  ld a,$05
  ld [$C1B3],a
  xor a
  ld [$C1B6],a
  ret
""" % (ITEM_ROW_FAST_CLAMP_AT, FLOOR_CHROME_INDEX, FLOOR_CHROME_BANK,
         ITEM_ROW_FAST_AT, POT_PUT_ENTRY_INDEX, POT_PUT_ENTRY_BANK)


def item_transition_labels():
    """Return symbolic addresses for both Item-page LCD fallback controllers."""
    return (
        gbasm.assemble(ITEM_PAGE_SRC, ITEM_PAGE_AT)[1],
        gbasm.assemble(ITEM_REGION_SRC, ITEM_REGION_AT)[1],
    )


# Keep completed incoming rows unreferenced behind the regional blank until the final
# body row is ready, then publish every owned row together in one VBlank. This removes
# the visibly variable top-to-bottom fill time: wide proportional rows can take longer
# to compose, but the player sees blank -> complete page rather than a slow cascade.
# Selector $FF has one body row and uses the same helper with a one-row count.
ITEM_ROW_FAST_SRC = """
itemrowfast:
  ld a,[$C6AC]
  inc a
  jr z,irffinal
  ld a,d
  cp $04
  ret nz
irffinal:
  call $%04X
  di
  ldh a,[$FF40]
  bit 7,a
  jr z,irfcopy
irfphase:
  ldh a,[$FF44]
  cp $90
  jr c,irfwait
  cp $92
  jr c,irfcopy
irfnext:
  ldh a,[$FF44]
  cp $90
  jr nc,irfnext
irfwait:
  ldh a,[$FF44]
  cp $90
  jr c,irfwait
irfcopy:
  ld hl,$C380
  ld de,$9880
  ld a,[$C6AC]
  inc a
  ld b,$01
  jr z,irfrow
  ld b,$05
irfrow:
  ld c,$03
irfleft:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,irfleft
  ld c,$10
irfname:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,irfname
  ld a,l
  add a,$2D
  ld l,a
  jr nc,irfsourceready
  inc h
irfsourceready:
  ld a,e
  add a,$2D
  ld e,a
  jr nc,irfdestready
  inc d
irfdestready:
  dec b
  jr nz,irfrow
  call ircursor
  ei
  ret

; Native Left/Right advances the absolute selector by five but bounds it only against
; the padded page count. If the old row does not exist on the destination page, clamp
; this exact same-screen redraw to the final real item and keep its row in lockstep.
; The space-constrained caller validates (count - 1), so restore the real count before
; comparing the absolute selector.
irclamp:
  inc a
  ld b,a
  ld a,[$C6AC]
  cp $FF
  ret z
  cp b
  ret c
  dec b
  ld a,b
  ld [$C6AC],a
irclamprow:
  cp $05
  jr c,irclampset
  sub $05
  jr irclamprow
irclampset:
  ld [$C6A5],a
  ret

; The fast body publication precedes native 4:$4E2B's shadow cursor write. Publish the
; known screen-1 cursor directly while this helper still owns the same safe VRAM phase;
; the native writer immediately brings shadow into agreement afterward.
ircursor:
  ld hl,$9882
  ld bc,$0040
  ld a,[$C6A5]
  and a
  jr z,ircursorset
ircursorrow:
  add hl,bc
  dec a
  jr nz,ircursorrow
ircursorset:
  ld [hl],$81
  ret
""" % ITEM_SHAPE_PHASE_AT


# Native screen 1 draws the five-/one-row body before it draws the Items/Floor header.
# The regional body publisher calls this while D still holds the completed body row.
# Phase 4 suppresses the static-title reuse only after row 4 is complete, preserving the
# fast body path while forcing box 14/18 to compose the correct replacement word.
ITEM_SHAPE_PHASE_SRC = """
itemshapephase:
  ld a,[$C6AC]
  inc a
  jr nz,ispitems
  ; The selector-$FF body has one real row, so its header follows row 0.
  ld a,d
  and a
  ret nz
  jr ispshape
ispitems:
  ; Carried Items always finish the five-row body at row 4. Clear any stale Action
  ; packing there, then distinguish an ordinary page from a completed Floor source.
  ld a,d
  cp $04
  ret nz
  xor a
  ld [$C1B5],a
  ld a,[$C1B7]
  dec a
  jr z,ispshape
  jp $%04X
ispshape:
  ld a,$01
  ld [$C1B5],a
  ld a,$04
  ld [$C1B6],a
  jp $%04X
""" % (ITEM_INDICATOR_AT, ITEM_INDICATOR_AT)


# Call_004_483E's native tail republishes fourteen complete map rows after an Item
# page's five rows are already scan-safe and visible.  For an exact regional page flip,
# only the four page-indicator cells can still differ.  Publish those cells as soon as
# their scanline is safe and let a small Call_004_4D7A gate skip Call_004_44A2. Every
# other caller receives the original range setup and continues into the untouched native
# map publisher. A=0 selects the renderer's optional fast-tile service; A=1 selects the
# redraw-tail service.
ITEM_RETURN_SRC = """
itemservice:
  and a
  jr nz,itemreturn
  ; Give an admitted Info row a chance to retire only the row whose tile slice is
  ; about to be repainted. Reject ordinary Item paging locally so its proven fast path
  ; does not pay for another cross-bank call.
  ld a,[$C1B3]
  cp $02
  jr nz,itemservicefast
  ld a,$03
  rst $10
  db $%02X,$%02X
  ret c
itemservicefast:
  xor a
  jp $%04X
itemreturn:
  push af
  push bc
  push de
  push hl
  ld a,[$C1B6]
  cp $03
  jp nz,irtlegacy
  ld a,[$C1B3]
  and a
  jp nz,irtfail
  ld a,[$C6A3]
  cp $01
  jp nz,irtfail
  ld a,[$C1B1]
  cp $04
  jp nz,irtfail
  ld a,[$C69D]
  cp $04
  jp nz,irtfail
  ld a,[$C534]
  cp $01
  jp nz,irtfail
  ld a,[$C6A6]
  and a
  jp nz,irtfail
  ld a,[$C11A]
  and a
  jp nz,irtfail
  ld a,[$C1B5]
  dec a
  jr z,irtshape
  ld a,[$C6AC]
  inc a
  jp z,irtfail
  ldh a,[$FF40]
  bit 7,a
  jp z,irtfail
  ; The indicator occupies tile row 3 (scanlines 24-31).  If scanout is about
  ; to enter it, wait until the row has passed; otherwise publish immediately
  ; after any current mode-3 interval.
  ldh a,[$FF44]
  cp $20
  jr nc,irtaccess
  add a,$03
  cp $18
  jr c,irtaccess
irtwaitrow:
  ldh a,[$FF44]
  cp $20
  jr c,irtwaitrow
irtaccess:
  ldh a,[$FF44]
  cp $90
  jr nc,irtcopy
irtwaitmode:
  ldh a,[$FF41]
  and $03
  cp $03
  jr z,irtwaitmode
irtcopy:
  ld hl,$C36F
  ld de,$986F
  ld b,$04
irtcopyloop:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,irtcopyloop
  jr irtdone
irtshape:
  ; The regional VBlank retired the four shared title cells before either private
  ; title plane was repainted.  Commit the complete incoming box-14/18 word and its
  ; indicator together in VBlank; the identical surrounding header chrome stays live.
  di
irtshapewait:
  ldh a,[$FF44]
  cp $90
  jr c,irtshapewait
  ld hl,$C321
  ld de,$9821
  ld b,$04
irtshapetitle:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,irtshapetitle
  ld hl,$C36F
  ld de,$986F
  ld b,$04
irtshapeindicator:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,irtshapeindicator
  ; The shape conversion clears the shared row-0 cursor cell. Native 4:$4E2B has
  ; rebuilt it in shadow by this point, but the skipped full-map publisher cannot expose
  ; it. Commit that one separately-owned cell with the title and page indicator.
  ld a,[$C382]
  ld [$9882],a
  ei
irtdone:
  xor a
  ld [$C1B5],a
  ld [$C1B6],a
  pop hl
  pop de
  pop bc
  pop af
  scf
  ret
irtfail:
  xor a
  ld [$C1B5],a
  ld [$C1B6],a
irtlegacy:
  ; Call_004_4D7A range setup. Its caller continues into the original
  ; Call_004_44A2 map publisher when carry is clear.
  ld a,[$C6A3]
  add a,a
  ld e,a
  ld d,$00
  ld hl,irtranges
  add hl,de
  ld a,[hl+]
  ld [$C6A1],a
  ld a,[hl]
  ld [$C6A2],a
  pop hl
  pop de
  pop bc
  pop af
  and a
  ret
irtranges:
  db $00,$12,$00,$0E,$00,$12,$00,$12,$03,$0D,$03,$0D,$00,$12,$00,$12
  db $00,$12,$00,$12,$00,$12,$00,$12,$00,$12,$00,$12,$00,$12,$00,$12
  db $00,$12,$00,$12,$00,$12,$0D,$0F,$00,$12,$00,$12,$00,$12,$00,$12
  db $00,$12,$00,$12,$00,$12,$00,$12,$00,$0A,$0D,$0F,$00,$12,$00,$12
  db $00,$12,$00,$12,$06,$10
""" % (INFO_CONTROL_INDEX, ACTION_BLANK_BANK, ITEM_TILE_FAST_AT)


# Once the exact Item transaction has blanked its five owned rows, none of the newly
# composed name tiles is referenced by the visible map. Copy each 16-byte tile in four
# synchronized four-byte HBlank slices (continued immediately if VBlank begins), instead of
# parking the CPU behind the general once-per-frame tile queue.  Carry reports that the
# renderer can proceed directly to its shadow-map row; every unproved shape retains the
# native queue.
ITEM_TILE_FAST_SRC = """
itemtilefast:
  push af
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $01
  jp nz,itffail
  ld a,[$C6A3]
  cp $01
  jp nz,itffail
  ld a,[$C1B1]
  cp $01
  jp nz,itffail
  ld a,[$C69D]
  cp $12
  jp nz,itffail
  ld a,[$C11A]
  and a
  jp nz,itffail
  ld a,[$C0D3]
  and a
  jp z,itffail
  cp $0E
  jp nc,itffail
  ldh a,[$FF40]
  bit 7,a
  jp z,itffail
  di
  ; Signed $8800 addressing: IDs below $80 are based at $9000; IDs above it
  ; wrap into $8800-$8FF0.
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
  jr nz,itfsigned
  add a,$90
  jr itfdest
itfsigned:
  add a,$80
itfdest:
  ld h,a
  xor a
  ld [$C0DD],a
itftile:
  ld a,[$C0D3]
  ld b,a
  ld a,[$C0DD]
  cp b
  jr z,itfsuccess
  add a,a
  ld e,a
  ld d,$00
  push hl
  ld hl,itfsources
  add hl,de
  ld a,[hl+]
  ld d,[hl]
  ld e,a
  pop hl
itfsource:
  ld a,$04
  ld [$C1B4],a
itfchunk:
  ldh a,[$FF44]
  cp $90
  jr nc,itfcopyfour
itfmode3:
  ldh a,[$FF41]
  and $03
  cp $03
  jr nz,itfmode3
itfhblank:
  ldh a,[$FF41]
  and $03
  cp $03
  jr z,itfhblank
itfcopyfour:
  ld b,$04
itfcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,itfcopy
  ld a,[$C1B4]
  dec a
  ld [$C1B4],a
  jr nz,itfchunk
  jr itfnext
itfnext:
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr itftile
itfsuccess:
  pop hl
  pop de
  pop bc
  pop af
  scf
  ei
  ret
itffail:
  pop hl
  pop de
  pop bc
  pop af
  and a
  ret
itfsources:
  db $08,$C0,$18,$C0,$28,$C0,$38,$C0
  db $4A,$C0,$5A,$C0,$6A,$C0,$7A,$C0
  db $8C,$C0,$9C,$C0,$AC,$C0,$BC,$C0
  db $2C,$C1
"""


# Native 4:$4EB4 builds the page indicator only after all five body rows and the Items
# header.  That ordering lets the completed page appear for several frames with the old
# green dot.  The exact regional row path already owns the final body-row transaction, so
# reproduce 4:$4EB4's count/selector mapping there and publish its four cells in VBlank.
# The later native builder and redraw-tail copy are idempotent confirmation writes.
ITEM_INDICATOR_SRC = """
itemindicator:
  push af
  push bc
  push de
  push hl
  ld a,[$C6AC]
  cp $FF
  jr z,iidone
  ld c,a
  ld a,[$C6AA]
  cp $06
  jr c,iidone
  dec a
  ld b,$00
iipages:
  inc b
  sub $05
  jr nc,iipages
  ld hl,$C36F
  ld a,$C5
iifill:
  ld [hl+],a
  dec b
  jr nz,iifill
  ld a,c
  ld c,$FF
iiactive:
  inc c
  sub $05
  jr nc,iiactive
  ld b,$00
  ld hl,$C36F
  add hl,bc
  ld [hl],$C6
  di
iiwait:
  ldh a,[$FF44]
  cp $90
  jr c,iiwait
  ld hl,$C36F
  ld de,$986F
  ld b,$04
iicopy:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,iicopy
  ei
iidone:
  pop hl
  pop de
  pop bc
  pop af
  ret
"""


# Shared atomic fallback. It stays separate so the screen-1 regional controller can grow
# without taking this safety path away from Floor/Info, title/file, Rankings, Fay, or Pot.
ITEM_PUBLISH_SRC = """
publishmap:
  ld [$C1B3],a
  ld hl,$C300
  ld de,$9800
  ld b,$12
pprow:
  ld c,$14
ppcell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,ppcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,ppsrcok
  inc h
ppsrcok:
  ld a,e
  add a,$0C
  ld e,a
  jr nc,ppdestok
  inc d
ppdestok:
  dec b
  jr nz,pprow
  ldh a,[$FF40]
  set 7,a
  ldh [$FF40],a
  ret
"""


# The Floor item action picker and its Info box reuse VWF tiles and the visible map while
# their replacement is still being drawn. The exact Wood Arrow and five-page Fusion Pot
# routes prove three mixed-text transitions: action -> Info, Info page -> page, and Info -> action.
# The Gitan route separately proves that a shorter three-choice action box also reaches
# the final publication boundary after its one-page description closes.
# This source is retained as the exact byte-level fallback template. The regional
# extension gets first refusal for proven screen-1, screen-7, and screen-20 ownership; rejected
# callers still use the LCD-off transaction below. State 1 remains the item-page
# transaction.
#
# The controller and finalizer occupy the standard pre-text helper slots in pool banks
# 39/40. The final full-map copy is the shared bank-60 publisher.
FLOOR_INFO_LEGACY_SRC = """
floorinfo:
  and a
  jr z,fiblank
  dec a
  jr z,fiborder
  jr fiempty
fiblank:
  ld a,[$C1B1]
  cp $03
  jr z,fihelpblank
  and a
  ret nz
  ld a,[$C1B3]
  cp $03
  ret nz
  ld a,[$C0D9]
  cp $20
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,d
  and a
  ret nz
  ld a,$04
  jr fioff
fihelpblank:
  ld a,[$C0D9]
  cp $80
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,d
  and a
  ret nz
  ld a,$02
fioff:
  ld [$C1B3],a
  ldh a,[$FF40]
  bit 7,a
  ret z
fiwait:
  ldh a,[$FF44]
  cp $90
  jr c,fiwait
fidisable:
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
  ret
fiborder:
  ld a,[$C1B1]
  cp $03
  jr z,fihelpborder
  cp $02
  ret nz
  ld a,[$C1B3]
  cp $04
  jr z,fiborderowned
  cp $09
  ret nz
fiborderowned:
  ; Action boxes are not all four rows high. Equipment has four choices, while
  ; Gitan has three. Finish on the descriptor's last row instead of assuming D=3;
  ; otherwise the one-page Gitan Info return leaves state 4 and the LCD disabled.
  ld a,[$C69C]
  dec a
  cp d
  ret nz
  ld a,$02
  jr fifinish
fihelpborder:
  call fihelpcheck
  ret nz
  xor a
fifinish:
  rst $10
  db $%02X,$%02X
  ret
fiempty:
  ld a,[$C0E7]
  and a
  jr nz,fiemptyknown
  ld a,$03
  rst $10
  db $%02X,$%02X
fiemptyknown:
  ld a,[$C1B1]
  cp $03
  ret nz
  call fihelpcheck
  ret nz
  ld a,$01
  jr fifinish
fihelpcheck:
  ld a,[$C1B3]
  cp $02
  ret nz
  ld a,d
  cp $04
  ret nz
  ld a,[$C0D9]
  cp $80
  ret nz
  ld a,[$C0DA]
  cp $C4
  ret
""" % (FLOOR_INFO_FINISH_INDEX, FLOOR_INFO_FINISH_BANK,
         ITEM_REGION_INDEX, ITEM_REGION_BANK)


FLOOR_INFO_FINISH_LEGACY_SRC = """
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
  ; pickers end on row 11. Three-choice pickers already have their native bottom
  ; on row 9, so erase the detached stale Info edge before publishing the map.
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
  jr fipublish
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
  ld hl,$C4AD
  jr fiactiondraw
fiactionsix:
  ld hl,$C4ED
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
""" % (ITEM_PUBLISH_INDEX, ITEM_PUBLISH_BANK)


# Banks 39/40 keep their historical far-call ABI, but the implementation is co-located
# with the admitted Action state in bank 62.  Keep the legacy controller's cheap reject
# path in bank 39: ordinary screen-1 Item rows must not pay for a second far call merely
# because the Info extension exists.  The three admitted candidates alone cross banks;
# the bank-62 controller then proves ownership or falls through to this byte-for-byte
# LCD-off fallback.
FLOOR_INFO_SRC = """
floorinfo:
  and a
  jr z,fistubblank
  dec a
  jr z,fistubborder
  jr fistubempty
fistubblank:
  ld a,[$C1B1]
  cp $03
  jr z,fistubcallzero
  and a
  ret nz
  ld a,[$C1B3]
  cp $03
  ret nz
  ld a,[$C0D9]
  cp $20
  ret nz
  ld a,[$C0DA]
  cp $C3
  ret nz
  ld a,d
  and a
  ret nz
  jr fistubcallzero
fistubborder:
  ld a,[$C1B1]
  cp $03
  jr z,fistubcallone
  cp $02
  ret nz
  ld a,[$C1B3]
  cp $04
  jr z,fistubborderowned
  cp $09
  ret nz
fistubborderowned:
  ld a,[$C69C]
  dec a
  cp d
  ret nz
  jr fistubcallone
fistubempty:
  ld a,[$C0E7]
  and a
  jr nz,fistubemptyknown
  ld a,$03
  rst $10
  db $%02X,$%02X
fistubemptyknown:
  ld a,[$C1B1]
  cp $03
  ret nz
  ld a,$02
  jr fistubcall
fistubcallzero:
  xor a
  jr fistubcall
fistubcallone:
  ld a,$01
fistubcall:
  rst $10
  db $%02X,$%02X
  ret
""" % (ITEM_REGION_INDEX, ITEM_REGION_BANK,
         INFO_CONTROL_INDEX, ACTION_BLANK_BANK)


FLOOR_INFO_FINISH_SRC = """
floorinfofinish:
  rst $10
  db $%02X,$%02X
  ret
""" % (INFO_FINISH_INDEX, ACTION_BLANK_BANK)


# Inject the exact regional attempt ahead of the established Info LCD-off fallback.
# Mode three comes from the proportional renderer immediately before a row's tile upload;
# screen 20 uses it to retire and replace one row at a time. Every rejected caller stays
# on the fallback.
_INFO_CONTROL_SRC = FLOOR_INFO_LEGACY_SRC.replace(
    """floorinfo:
  and a
""",
    """floorinfo:
  cp $03
  jp z,infopreupload
  and a
""", 1)

_INFO_CONTROL_SRC = _INFO_CONTROL_SRC.replace(
    """fihelpblank:
  ld a,[$C0D9]
""",
    """fihelpblank:
  call infotry
  ret c
  ld a,[$C0D9]
""", 1)

# Screen 1 reveals each completed proportional row after its empty Info chrome. Screen 20
# instead preserves old rows and publishes each replacement after its tile allocation is
# safe. The final row still uses the existing all-rows-plus-pager publisher, so the native
# footer remains atomic. Rejected callers continue through the legacy finalizer.
_INFO_CONTROL_SRC = _INFO_CONTROL_SRC.replace(
    """fihelpborder:
  call fihelpcheck
""",
    """fihelpborder:
  call infopublishrow
  ret c
  call fihelpcheck
""", 1)

_INFO_FINISH_SRC = FLOOR_INFO_FINISH_LEGACY_SRC.replace(
    """fihelppublish:
  ld a,$03
  jr fipublish
""",
    """fihelppublish:
  call infopublish
  ret c
  ; Rejected legacy callers still publish the entire shadow while the LCD is off.
  ; Restore the native pager rasters that translated text can borrow, and erase the
  ; two visible rows below Info where a six-row Pot action box otherwise survives.
  call infopagerpixels
  ld hl,$C4C0
  ld b,$02
filegacyrow:
  ld c,$14
  xor a
filegacytail:
  ld [hl+],a
  dec c
  jr nz,filegacytail
  ld a,l
  add a,$0C
  ld l,a
  jr nc,filegacynocarry
  inc h
filegacynocarry:
  dec b
  jr nz,filegacyrow
  ld a,$03
  jr fipublish
    """, 1)

# During an exact screen-20 replay, the final Action row is the only point at which the
# title and every picker row are complete in shadow. Give the co-located lifecycle first
# refusal there; rejected callers resume the byte-for-byte legacy finalizer below.
_INFO_FINISH_SRC = _INFO_FINISH_SRC.replace(
    """floorinfofinish:
""",
    """floorinfofinish:
  push af
  ld a,$02
  call inforeturn
  jr nc,fireturnlegacy
  pop af
  ret
fireturnlegacy:
  pop af
""", 1)


_INFO_DIGIT_TABLE = '\n'.join(
    '  db ' + ','.join('$%02X' % value for value in
                       dotfont.load_approved().glyphs[digit])
    for digit in '123456789')


INFO_LIFECYCLE_SRC = _INFO_CONTROL_SRC + _INFO_FINISH_SRC + """
; Carry means the current screen-4 description or screen-5 seal page belongs to the
; admitted screen-1 Item/Floor Action overlay, the exact screen-20 Floor picker, or the
; separately proven screen-7 unidentified-Pot picker. A returns the parent screen ID.
; This predicate is shared by entry, paging, publication, and all forms of exit.
infoowned:
  ld a,[$C6A3]
  cp $04
  jr z,infoscreen
  cp $05
  jp nz,infofail
infoscreen:
  ld b,a
  ld a,[$C534]
  cp $03
  jr z,infoitems
  cp $02
  jp nz,infofail
  ; Screen 7 and Status -> Floor screen 20 both push only the Info/seal child and retain
  ; selector/context $FF/$01. They share a native drawer but not box geometry or replay
  ; ownership, so split them by the actual parent stack entry.
  ld a,[$C535]
  and a
  jp nz,infofail
  ld a,[$C536]
  cp $14
  jr z,info20
  cp $07
  jp nz,infofail
  ; The alternate screen-7 route is specifically the seven-row unidentified-Pot Action
  ; picker leading to ordinary Info screen 4. Keep screen 5 and shorter box-6 callers
  ; outside this new ownership epoch.
  ld a,b
  cp $04
  jp nz,infofail
  ld a,[$C537]
  cp b
  jp nz,infofail
  ld a,[$C1B6]
  and a
  jp nz,infofail
  ld a,[$C6DE]
  dec a
  jp nz,infofail
  ld a,[$C6AC]
  inc a
  jp nz,infofail
  ld a,[$C6BB]
  cp $07
  jp nz,infofail
  ld c,$07
  jr infopages
info20:
  ld a,[$C537]
  cp b
  jp nz,infofail
  ; A carried screen-2 Action which exits directly to gameplay can leave its private-pool
  ; admission byte at one. Screen 20 has already replaced that BG map and an exact
  ; 0,20,4/5 stack cannot own a live Item-page transaction. Accept only idle/stale-one;
  ; infotry clears the stale proof before any screen-20 Info pixels are published.
  ld a,[$C1B6]
  cp $02
  jp nc,infofail
  ld a,[$C6DE]
  dec a
  jp nz,infofail
  ld a,[$C6AC]
  inc a
  jp nz,infofail
  ld a,[$C6BB]
  cp $03
  jp c,infofail
  cp $08
  jp nc,infofail
  ld c,$14
  jr infopages
infoitems:
  ld a,[$C1B6]
  dec a
  jp nz,infofail
  ld a,[$C535]
  and a
  jp nz,infofail
  ld a,[$C536]
  dec a
  jp nz,infofail
  ld a,[$C537]
  cp $02
  jp nz,infofail
  ld a,[$C538]
  cp b
  jp nz,infofail
  ld a,[$C6DE]
  and a
  jp nz,infofail
  ld c,$01
  ld a,[$C6AC]
  cp $FF
  jr nz,infoheld
  ld a,[$C1B7]
  dec a
  jp nz,infofail
  jr infopages
infoheld:
  ld b,a
  inc b
  ld a,[$C6AA]
  cp b
  jp c,infofail
infopages:
  ; The native footer owns one tile each for current and total page. Keep this exact
  ; regional path to the representable one-digit producer domain.
  ld a,[$C6BD]
  and a
  jp z,infofail
  cp $0A
  jp nc,infofail
infohardware:
  ldh a,[$FF40]
  and $F8
  cp $E0
  jp nz,infofail
  ldh a,[$FF42]
  and a
  jp nz,infofail
  ldh a,[$FF43]
  and a
  jp nz,infofail
  ldh a,[$FF4A]
  cp $80
  jp nz,infofail
  ldh a,[$FF4B]
  cp $07
  jp nz,infofail
  ld a,c
  scf
  ret
infofail:
  and a
  ret

; Row zero arrives after the native box drawer has written only the current portion of
; box 7. Build the entire empty 20x11 shape in shadow. Screen 1 retains its established
; complete-empty publication; screen 20 leaves the outgoing Action/Info page visible and
; lets infopreupload replace only the row whose pixels are about to be recycled.
infotry:
  push bc
  push de
  push hl
  call infoowned
  jr nc,infotrybad
  ld e,a
  ld a,d
  and a
  jr nz,infotrybad
  ld a,[$C1B3]
  and a
  jr z,infotryinitial
  cp $03
  jr nz,infotrybad
  xor a
  jr infotrystate
infotryinitial:
  ld a,$01
infotrystate:
  ; $C1B5 is otherwise unused by the independent screen-20 child. Record whether row
  ; zero is replacing its Action parent (one) or another Info page (zero); screen-1
  ; retains its packed selector there.
  ld c,a
  ld a,e
  cp $14
  jr nz,infotryflagged
  xor a
  ld [$C1B6],a
  ld a,c
  ld [$C1B5],a
infotryflagged:
  ld a,[$C0D9]
  cp $80
  jr nz,infotrybad
  ld a,[$C0DA]
  cp $C3
  jr nz,infotrybad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jr nz,infotrybad
  ld a,[hl+]
  cp $03
  jr nz,infotrybad
  ld a,[hl+]
  cp $05
  jr nz,infotrybad
  ld a,[hl+]
  cp $12
  jr nz,infotrybad
  ld a,[hl]
  and a
  jr nz,infotrybad
  ld a,$02
  ld [$C1B3],a
infotrydrain:
  ld a,[$C11A]
  and a
  jr z,infotryready
  push de
  call $06F7
  pop de
  jr infotrydrain
infotryready:
  ld a,e
  cp $07
  call z,info7header
  call infobox
  pop hl
  pop de
  pop bc
  scf
  ret
infotrybad:
  pop hl
  pop de
  pop bc
  and a
  ret

; The renderer calls mode three after a proportional row is composed but before its tile
; upload starts. For the independent screen-20 Info child, retire every whole visible row
; whose references overlap the incoming allocation. On initial Action -> Info entry,
; retire only the Action labels, then replace its still-complete box with complete Info
; chrome plus row zero after those pixels are ready. The title and Window remain live.
infopreupload:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $02
  jp nz,infopreuploadbad
  call infoowned
  jp nc,infopreuploadbad
  cp $14
  jp nz,infopreuploadbad
  ld a,[$C1B1]
  cp $03
  jp nz,infopreuploadbad
  ld a,[$C69D]
  cp $12
  jp nz,infopreuploadbad
  ; Convert the five exact shadow destinations C380/C3C0/C400/C440/C480 to row 0-4.
  ld a,[$C0DA]
  cp $C3
  jr z,infopreuploadc3
  cp $C4
  jp nz,infopreuploadbad
  ld a,[$C0D9]
  and a
  jr z,infopreuploadrow2
  cp $40
  jr z,infopreuploadrow3
  cp $80
  jp nz,infopreuploadbad
  ld c,$04
  jr infopreuploadrow
infopreuploadc3:
  ld a,[$C0D9]
  cp $80
  jr z,infopreuploadrow0
  cp $C0
  jp nz,infopreuploadbad
  ld c,$01
  jr infopreuploadrow
infopreuploadrow0:
  ld c,$00
  ld a,[$C1B5]
  dec a
  jr nz,infopreuploadrow
  ; Retire only the old Action labels before their allocator slots are repainted. Keep
  ; the Action chrome visible until row-zero pixels are complete; the following helper
  ; can then publish complete Info chrome and row zero together.
  call infoactionblank
  jp infopreuploadok
infopreuploadrow2:
  ld c,$02
  jr infopreuploadrow
infopreuploadrow3:
  ld c,$03
infopreuploadrow:
  ; A new row can receive a differently packed slice and overlap more than its own old
  ; destination. Scan all five visible interiors and retire exactly the references in
  ; the tile interval about to be repainted. Each access waits out LCD mode 3; this is
  ; the same safety rule as the fast Item uploader, but it preserves every unaffected
  ; outgoing row instead of blanking the whole page.
  ld a,[$C0DB]
  ld d,a
  ld a,[$C0D3]
  add a,d
  ld e,a
  xor a
  ld [$C0DD],a
  ld hl,$9881
  ld c,$05
infopreuploadscanrow:
  xor a
  ld [$C1B4],a
  ld b,$12
infopreuploadscan:
  call infovramwait
  ld a,[hl]
  cp d
  jr c,infopreuploadnext
  cp e
  jr nc,infopreuploadnext
  ld a,$01
  ld [$C1B4],a
infopreuploadnext:
  inc hl
  dec b
  jr nz,infopreuploadscan
  ld a,[$C1B4]
  and a
  jr z,infopreuploadadvance
  ; Convert the descending row counter 5..1 to mask bits 1..16.
  ld a,$20
  ld b,c
infopreuploadmaskbit:
  rrca
  dec b
  jr nz,infopreuploadmaskbit
  ld b,a
  ld a,[$C0DD]
  or b
  ld [$C0DD],a
infopreuploadadvance:
  ld a,l
  add a,$2E
  ld l,a
  jr nc,infopreuploadnextrow
  inc h
infopreuploadnextrow:
  dec c
  jr nz,infopreuploadscanrow
  ld a,[$C0DD]
  and a
  jr z,infopreuploadok
  ; Publish every selected retirement as whole rows in one VBlank. Scanning during the
  ; visible period is read-only; this atomic write avoids the torn half-rows produced by
  ; modifying cells across multiple HBlanks.
  call infovblank
  ld hl,$9881
  ld d,$01
  ld c,$05
infopreuploadblankrows:
  ld a,[$C0DD]
  and d
  jr z,infopreuploadskipblank
  xor a
  ld b,$12
infopreuploadblankcell:
  ld [hl+],a
  dec b
  jr nz,infopreuploadblankcell
  ld a,l
  add a,$2E
  ld l,a
  jr nc,infopreuploadblanknext
  inc h
  jr infopreuploadblanknext
infopreuploadskipblank:
  ld a,l
  add a,$40
  ld l,a
  jr nc,infopreuploadblanknext
  inc h
infopreuploadblanknext:
  sla d
  dec c
  jr nz,infopreuploadblankrows
  ei
infopreuploadok:
  call infotilefast
  jr nc,infopreuploadslow
  ld a,[$C1B5]
  dec a
  jr nz,infopreuploadfastdone
  call infoentrychrome
  xor a
  ld [$C1B4],a
infopreuploadfastdone:
  pop hl
  pop de
  pop bc
  scf
  ret
infopreuploadbad:
infopreuploadslow:
  pop hl
  pop de
  pop bc
  and a
  ret

; The exact screen-20 row is now unreferenced wherever its allocation overlaps the
; outgoing page. Upload its one-pass tile raster through the same four-byte HBlank
; slices used by fast Item paging. Truly wide two-pass rows return carry clear and keep
; the native queue; their references have already been retired safely.
infotilefast:
  ld a,[$C11A]
  and a
  jp nz,infotilefastbad
  ld a,[$C0D3]
  and a
  jp z,infotilefastbad
  cp $0E
  jp nc,infotilefastbad
  ldh a,[$FF40]
  bit 7,a
  jp z,infotilefastbad
  di
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
  jr nz,infotilefastsigned
  add a,$90
  jr infotilefastdest
infotilefastsigned:
  add a,$80
infotilefastdest:
  ld h,a
  xor a
  ld [$C0DD],a
infotilefasttile:
  ld a,[$C0D3]
  ld b,a
  ld a,[$C0DD]
  cp b
  jr z,infotilefastdone
  add a,a
  ld e,a
  ld d,$00
  push hl
  ld hl,infotilefastsources
  add hl,de
  ld a,[hl+]
  ld d,[hl]
  ld e,a
  pop hl
  ld a,$04
  ld [$C1B4],a
infotilefastchunk:
  ldh a,[$FF44]
  cp $90
  jr nc,infotilefastcopyfour
infotilefastmode3:
  ldh a,[$FF41]
  and $03
  cp $03
  jr nz,infotilefastmode3
infotilefasthblank:
  ldh a,[$FF41]
  and $03
  cp $03
  jr z,infotilefasthblank
infotilefastcopyfour:
  ld b,$04
infotilefastcopy:
  ld a,[de]
  ld [hl+],a
  inc de
  dec b
  jr nz,infotilefastcopy
  ld a,[$C1B4]
  dec a
  ld [$C1B4],a
  jr nz,infotilefastchunk
  ld a,[$C0DD]
  inc a
  ld [$C0DD],a
  jr infotilefasttile
infotilefastdone:
  ld a,$FF
  ld [$C1B4],a
  scf
  ei
  ret
infotilefastbad:
  and a
  ret
infotilefastsources:
  db $08,$C0,$18,$C0,$28,$C0,$38,$C0
  db $4A,$C0,$5A,$C0,$6A,$C0,$7A,$C0
  db $8C,$C0,$9C,$C0,$AC,$C0,$BC,$C0
  db $2C,$C1

infovramwait:
  ldh a,[$FF41]
  and $03
  cp $03
  jr z,infovramwait
  ret

; Screen 7 uses box 6 at y=1 over the right edge of its full-width box-5 title. Before
; Info reuses the generic Action tiles, remove that overlay from the two rows above box
; 7 and restore the complete underlying title chrome. Rows 3-15 are replaced by infobox.
info7header:
  ld hl,$C32D
  xor a
  ld b,$06
info7headermiddle:
  ld [hl+],a
  dec b
  jr nz,info7headermiddle
  ld [hl],$BF
  ld hl,$C34D
  ld a,$BD
  ld b,$06
info7headerbottom:
  ld [hl+],a
  dec b
  jr nz,info7headerbottom
  ld [hl],$BB
  call infovblank
  ld hl,$C32D
  ld de,$982D
  ld b,$07
  call infocopycells
  ld hl,$C34D
  ld de,$984D
  ld b,$07
  call infocopycells
  ei
  ret

; Clear only the five-cell labels in the outgoing screen-20 Action picker. Its box and
; the full-width item title stay visible while row-zero pixels upload. The seventh Pot
; choice lies behind the hardware Window but is harmless to retire with the other rows.
infoactionblank:
  call infovblank
  ld hl,$988E
  ld a,[$C6BB]
  ld c,a
infoactionblankrow:
  ld b,$05
infoactionblankcell:
  xor a
  ld [hl+],a
  dec b
  jr nz,infoactionblankcell
  ld a,l
  add a,$3B
  ld l,a
  jr nc,infoactionblanknext
  inc h
infoactionblanknext:
  dec c
  jr nz,infoactionblankrow
  ei
  ret

; Atomically replace the screen-20 Action footprint with complete Info chrome and row 0.
; Only the right seven columns need clearing: every other middle cell was already empty
; on the Floor parent. The two visible rows below Info are cleared over the same seven
; columns for the six-/seven-row Pot picker.
infoentrychrome:
  call infovblank
  ld hl,$C360
  ld de,$9860
  ld b,$14
  call infocopycells
  ld hl,$9880
  ld de,$000D
  ld c,$09
infoentrymiddle:
  ld [hl],$BE
  add hl,de
  xor a
  ld b,$06
infoentryclear:
  ld [hl+],a
  dec b
  jr nz,infoentryclear
  ld [hl],$BF
  add hl,de
  dec c
  jr nz,infoentrymiddle
  ld hl,$C4A0
  ld de,$99A0
  ld b,$14
  call infocopycells
  ld hl,$99CD
  ld de,$0019
  ld c,$02
infoentrytailrow:
  xor a
  ld b,$07
infoentrytail:
  ld [hl+],a
  dec b
  jr nz,infoentrytail
  add hl,de
  dec c
  jr nz,infoentrytailrow
  ; Row zero's planes are already complete (or its native queue has just drained).
  ; Publish its exact contiguous references with the chrome so no displayed frame owns
  ; a large empty Info body.
  ld hl,$9881
  ld a,[$C0DB]
  ld b,a
  ld a,[$C0D3]
  ld c,a
  ld a,b
infoentryrowrefs:
  ld [hl+],a
  inc a
  dec c
  jr nz,infoentryrowrefs
  ld a,[$C0D3]
  ld c,a
  ld a,$12
  sub c
  ld c,a
  jr z,infoentryrowdone
  xor a
infoentryrowempty:
  ld [hl+],a
  dec c
  jr nz,infoentryrowempty
infoentryrowdone:
  xor a
  ld [$C1B5],a
infoentrychromedone:
  ei
  ret

; The final row has already staged the native pager into shadow. Wait for every glyph
; upload, then reveal all five 18-cell interiors plus the two arrow and three counter
; cells together. No full-map copy is safe inside one enabled-LCD VBlank.
infopublish:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $02
  jr nz,infopublishbad
  call infoowned
  jr nc,infopublishbad
  ld a,d
  cp $04
  jr nz,infopublishbad
  ld a,$03
  ld [$C1B3],a
infopublishdrain:
  ld a,[$C11A]
  and a
  jr z,infopublishready
  call $06F7
  jr infopublishdrain
infopublishready:
  call infovblank
  ; Status VWF may have repainted native low digit tiles $04-$0A. Restore just the two
  ; footer digits while the Info body is still hidden, then publish their references in
  ; the same VBlank as the completed proportional rows.
  call infopagerpixels
  ld hl,$C381
  ld de,$9881
  ld b,$05
infobodyrow:
  ld c,$12
infobodycell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,infobodycell
  ld a,l
  add a,$2E
  ld l,a
  jr nc,infobodysource
  inc h
infobodysource:
  ld a,e
  add a,$2E
  ld e,a
  jr nc,infobodydest
  inc d
infobodydest:
  dec b
  jr nz,infobodyrow
  ld hl,$C4A9
  ld de,$99A9
  ld b,$02
  call infocopycells
  ld hl,$C4B0
  ld de,$99B0
  ld b,$03
  call infocopycells
  ; A screen-1 Info redraw can span the input engine's initial $14-frame hold delay.
  ; By the time the completed page is published the physical direction has already
  ; been released, but $FF83/$FF87 can still retain its synthetic repeat source/event.
  ; Retire that consumed direction with the page so one tap cannot redraw every page.
  xor a
  ldh [$FF83],a
  ldh [$FF87],a
  ei
  pop hl
  pop de
  pop bc
  scf
  ret
infopublishbad:
  pop hl
  pop de
  pop bc
  and a
  ret

; Rows zero through three arrive here only after their proportional glyph uploads have
; been queued. Drain and expose the complete 18-cell interior. Screen 1 already owns its
; empty Info box; initial screen 20 publishes chrome plus row zero together, while later
; screen-20 rows use same-frame safe LCD slots after their fast upload. Row four remains
; hidden until infopublish can reveal it with the native arrow and page counter.
infopublishrow:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $02
  jr nz,infopublishrowbad
  call infoowned
  jr nc,infopublishrowbad
  ld a,d
  cp $04
  jr nc,infopublishrowbad
  ld c,a
infopublishrowdrain:
  ld a,[$C11A]
  and a
  jr z,infopublishrowready
  call $06F7
  jr infopublishrowdrain
infopublishrowready:
  ; A wide initial screen-20 row retained the small Action chrome while using the native
  ; tile queue. Now that the queue is empty, replace it with complete Info chrome and
  ; the finished first row in the same VBlank.
  push bc
  call infoowned
  jr nc,infopublishrownotinitial
  cp $14
  jr nz,infopublishrownotinitial
  ld a,[$C1B5]
  dec a
  jr nz,infopublishrownotinitial
  pop bc
  call infoentrychrome
  jr infopublishrowdone
infopublishrownotinitial:
  pop bc
infopublishrowaddress:
  ld a,c
  rrca
  rrca
  ld c,a
  add a,$81
  ld l,a
  ld a,$C3
  adc a,$00
  ld h,a
  ld a,c
  add a,$81
  ld e,a
  ld a,$98
  adc a,$00
  ld d,a
  ld a,[$C1B4]
  inc a
  jr nz,infopublishrowvblank
  ; The pre-upload helper already completed every tile plane. Publish the row through
  ; safe LCD-access slots in the current displayed frame instead of waiting through an
  ; otherwise empty VBlank.
  ld b,$12
infopublishrowfast:
  call infovramwait
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,infopublishrowfast
  xor a
  ld [$C1B4],a
  jr infopublishrowdone
infopublishrowvblank:
  call infovblank
  ld b,$12
  call infocopycells
infopublishrowdone:
  ei
  pop hl
  pop de
  pop bc
  scf
  ret
infopublishrowbad:
  pop hl
  pop de
  pop bc
  and a
  ret

; A ground-Pot See viewer retains screen 7 or screen 20 beneath screen 12/13. This is
; deliberately not the carried-Pot state-$0A path: its stack depth and pop amount are
; both one smaller. Screen 7 has a fixed seven-row parent; screen 20 uses the row count
; captured at viewer entry before C6BB was repurposed.
groundseepop:
  push bc
  push de
  push hl
  ld a,c
  dec a
  jp nz,groundseepopbad
  ld a,[$C1B3]
  and a
  jp nz,groundseepopbad
  ld a,[$C1B6]
  and a
  jp nz,groundseepopbad
  ld a,[$C6A3]
  ld e,a
  cp $0C
  jr z,groundseescreen
  cp $0D
  jp nz,groundseepopbad
groundseescreen:
  ld a,[$C534]
  cp $02
  jp nz,groundseepopbad
  ld hl,$C535
  ld a,[hl+]
  and a
  jp nz,groundseepopbad
  ld a,[hl+]
  ld b,a
  cp $07
  jr z,groundseeparent
  cp $14
  jp nz,groundseepopbad
groundseeparent:
  ld a,[hl]
  cp e
  jp nz,groundseepopbad
  ld a,[$C6A6]
  and a
  jp nz,groundseepopbad
  ld a,[$C6DE]
  dec a
  jp nz,groundseepopbad
  ld a,[$C6AC]
  inc a
  jp nz,groundseepopbad
  ld a,[$C6AA]
  cp $06
  jp nc,groundseepopbad
  ld a,[$C6BB]
  and a
  jp z,groundseepopbad
  cp $08
  jp nc,groundseepopbad
  ld a,[$C1B1]
  cp $04
  jp nz,groundseepopbad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jp nz,groundseepopbad
  ld a,[hl+]
  and a
  jp nz,groundseepopbad
  ld a,[hl+]
  dec a
  jp nz,groundseepopbad
  ld a,[hl+]
  cp $03
  jp nz,groundseepopbad
  ld a,[hl]
  cp $40
  jp nz,groundseepopbad
  ldh a,[$FF40]
  and $F8
  cp $E0
  jp nz,groundseepopbad
  ldh a,[$FF42]
  and a
  jp nz,groundseepopbad
  ldh a,[$FF43]
  and a
  jp nz,groundseepopbad
  ldh a,[$FF4A]
  cp $80
  jp nz,groundseepopbad
  ldh a,[$FF4B]
  cp $07
  jp nz,groundseepopbad
  ld a,b
  cp $07
  jr z,groundseearm7
  ld a,[$C1B8]
  cp $03
  jp c,groundseepopbad
  cp $08
  jp nc,groundseepopbad
  ld [$C1B4],a
  xor a
  ld [$C1B5],a
  ld a,$09
  jp infopoparm
groundseearm7:
  ld a,$07
  ld [$C1B4],a
  xor a
  ld [$C1B5],a
  ld a,$0B
  jp infopoparm
groundseepopbad:
  pop hl
  pop de
  pop bc
  and a
  ret

; Called only from the generic pop hook with HL equal to screen 4/5's A/D-pad handler
; $5926 or B handler $5691. Keep the completed Info/seal page visible across the native
; disposable screen-0 replay, arm the state-8 replay guard, and perform the native depth
; subtraction. The first proven screen-1 row retires those references immediately before
; the parent allocator can reuse them. Carry tells the caller not to subtract twice; it
; is deliberately cleared again before the native replay continues.
infopop:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $03
  jr nz,infopopbad
  ld a,[$C6A3]
  ld e,a
  call infoowned
  jr nc,infopopbad
  cp $14
  jr z,infopopfloor
  cp $07
  jr z,infopop7
  ; Remember whether this carried-item child was the ordinary description (4) or the
  ; equipment-seal screen (5). Only the latter can hand its one-screen return to the
  ; proven fast Item-page machinery; all ordinary Info callers keep the exact state-8
  ; completion contract.
  ld a,e
  ld [$C1B4],a
  ld a,$08
  jr infopoparm
infopopfloor:
  ; Screen 0's disposable Status replay overwrites C6BB. Preserve the exact
  ; standing-item Action height for construction of the empty return picker.
  ld a,[$C6BB]
  ld [$C1B4],a
  ld a,$09
  jr infopoparm
infopop7:
  ; Screen 7 has the same one-level pop depth as screen 20 but reconstructs box 6 at
  ; y=1. Preserve its proven seven-row height under an independent replay state.
  ld a,[$C6BB]
  ld [$C1B4],a
  ld a,$0B
infopoparm:
  ld [$C1B3],a
  ld a,[$C1B3]
  cp $09
  ld a,$01
  jr z,infopopdepth
  ld a,[$C1B3]
  cp $0B
  ld a,$01
  jr z,infopopdepth
  inc a
infopopdepth:
  ld b,a
  ld a,[$C534]
  sub b
  ld [$C534],a
  pop hl
  pop de
  pop bc
  scf
  ret
infopopbad:
  pop hl
  pop de
  pop bc
  and a
  ret

; Mode zero runs at the first screen-1 Item/Floor row of an exact state-8 replay and
; commits complete empty target chrome. Mode one publishes the completed title, page
; marker, and Item/Floor rows at the final header boundary.
inforeturn:
  push af
  ld a,[$C6A3]
  sub $0C
  cp $02
  jr nc,potseeentryskip
potseeentryscreen:
  ld a,[$C69A]
  cp $0D
  jr nz,potseeentryskip
  ld a,[$C69B]
  dec a
  and $FD
  jr nz,potseeentryskip
potseeentrycall:
  pop af
  jp potseeentry
potseeentryskip:
  pop af
  jr inforeturndispatch
potseeentry:
  push af
  push bc
  push de
  ld a,[$C6A3]
  ld e,a
  ld a,[$C1B3]
  and a
  jr nz,potseeentrydone
  ld a,[$C1B6]
  and a
  jr nz,potseeentrydone
  ld a,[$C534]
  cp $02
  jr nz,potseeentrydone
  ld hl,$C535
  ld a,[hl+]
  and a
  jr nz,potseeentrydone
  ld a,[hl+]
  cp $14
  jr nz,potseeentrydone
  ld a,[hl]
  cp e
  jr nz,potseeentrydone
  ld a,[$C6BB]
  cp $03
  jr c,potseeentrydone
  cp $08
  jr nc,potseeentrydone
  ld b,a
  ld a,[$C69B]
  cp $03
  jr nz,potseeentrydone
  ld a,[$C69C]
  cp b
  jr nz,potseeentrydone
  ld a,b
  ld [$C1B8],a
potseeentrydone:
  ld hl,$C300
  pop de
  pop bc
  pop af
  ret
inforeturndispatch:
  cp $04
  jp z,potentrybegin
  cp $05
  jp z,potentrypublish
  cp $03
  jp z,groundseepop
  cp $02
  jr nz,inforeturnmode
  ld a,[$C1B3]
  cp $0B
  jp z,inforeturn7publish
  jp inforeturn20publish
inforeturnmode:
  and a
  jp nz,inforeturnpublish
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $09
  jr z,inforeturn20start
  cp $0B
  jp z,inforeturn7start
  cp $08
  jr nz,inforeturnitembad
  ld a,[$C1B6]
  dec a
  jr nz,inforeturnitembad
  ld a,[$C6A3]
  dec a
  jr nz,inforeturnitembad
  ld a,[$C534]
  dec a
  jr nz,inforeturnitembad
  ld a,[$C535]
  and a
  jr nz,inforeturnitembad
  ld a,[$C536]
  dec a
  jr nz,inforeturnitembad
  ld a,[$C1B1]
  dec a
  jr nz,inforeturnitembad
  ld a,[$C0D9]
  cp $80
  jr nz,inforeturnitembad
  ld a,[$C0DA]
  cp $C3
  jr nz,inforeturnitembad
  call infoallblank
  call inforeturnchrome
  ; A carried screen-5 seal page can hand the completed empty parent directly to the
  ; ordinary screen-1 regional transaction. Its private tile uploader makes the replay
  ; as fast as paging, and its final-row publisher exposes all body rows atomically once
  ; their pixels are stable. Screen 4 retains state 8 and its exact final publisher.
  ld a,[$C1B4]
  cp $05
  jr nz,inforeturnitemarmed
  ld a,$01
  ld [$C1B3],a
inforeturnitemarmed:
  ld a,$02
  ld [$C1B6],a
  pop hl
  pop de
  pop bc
  scf
  ret
inforeturnitembad:
  pop hl
  pop de
  pop bc
  and a
  ret
inforeturn20start:
  ld a,[$C534]
  dec a
  jr nz,inforeturnbad
  ld a,[$C535]
  and a
  jr nz,inforeturnbad
  ld a,[$C536]
  cp $14
  jr nz,inforeturnbad
  ld a,[$C6A3]
  and a
  jr z,inforeturn20owned
  cp $14
  jr nz,inforeturnbad
  ld a,[$C1B6]
  cp $02
  jr z,inforeturn20owned
  and a
  jr nz,inforeturnbad
  ld a,[$C1B1]
  ; The first screen-20 header row reaches the controller in phase 1. Phase 4 is
  ; the later far-entry boundary, after incomplete chrome could already be exposed.
  cp $01
  jr nz,inforeturnbad
  ld a,[$C0D9]
  cp $20
  jr nz,inforeturnbad
  ld a,[$C0DA]
  cp $C3
  jr nz,inforeturnbad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jr nz,inforeturnbad
  ld a,[hl+]
  and a
  jr nz,inforeturnbad
  ld a,[hl+]
  dec a
  jr nz,inforeturnbad
  ld a,[hl+]
  cp $12
  jr nz,inforeturnbad
  ld a,[hl]
  cp $20
  jr nz,inforeturnbad
  call info20chrome
  ld a,$02
  ld [$C1B6],a
inforeturn20owned:
  pop hl
  pop de
  pop bc
  scf
  ret
inforeturnbad:
  pop hl
  pop de
  pop bc
  and a
  ret
inforeturn7start:
  ld a,[$C534]
  dec a
  jr nz,inforeturnbad
  ld a,[$C535]
  and a
  jr nz,inforeturnbad
  ld a,[$C536]
  cp $07
  jr nz,inforeturnbad
  ld a,[$C6A3]
  and a
  jr z,inforeturn7owned
  cp $07
  jr nz,inforeturnbad
  ld a,[$C1B6]
  and a
  jr z,inforeturn7begin
  cp $02
  jr nz,inforeturnbad
  jr inforeturn7owned
inforeturn7begin:
  ld a,[$C1B1]
  cp $01
  jr nz,inforeturnbad
  ld a,[$C0D9]
  cp $20
  jr nz,inforeturnbad
  ld a,[$C0DA]
  cp $C3
  jr nz,inforeturnbad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jr nz,inforeturnbad
  ld a,[hl+]
  and a
  jr nz,inforeturnbad
  ld a,[hl+]
  dec a
  jr nz,inforeturnbad
  ld a,[hl+]
  cp $12
  jr nz,inforeturnbad
  ld a,[hl]
  cp $20
  jr nz,inforeturnbad
  call info7chrome
  ld a,$02
  ld [$C1B6],a
inforeturn7owned:
  pop hl
  pop de
  pop bc
  scf
  ret
inforeturnpublish:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $08
  jr nz,inforeturnbad
  ld a,[$C1B6]
  cp $02
  jr nz,inforeturnbad
inforeturndrain:
  ld a,[$C11A]
  and a
  jr z,inforeturnready
  call $06F7
  jr inforeturndrain
inforeturnready:
  call infovblank
  ld hl,$C321
  ld de,$9821
  ld b,$04
  call infocopycells
  ld a,[$C6AC]
  cp $FF
  jr z,inforeturnfloor
  ld hl,$C36F
  ld de,$986F
  ld b,$04
  call infocopycells
  ld hl,$C380
  ld de,$9880
  ld b,$05
inforeturnitemrow:
  push bc
  ld b,$13
  call infocopycells
  ld a,l
  add a,$2D
  ld l,a
  jr nc,inforeturnitemsrc
  inc h
inforeturnitemsrc:
  ld a,e
  add a,$2D
  ld e,a
  jr nc,inforeturnitemdest
  inc d
inforeturnitemdest:
  pop bc
  dec b
  jr nz,inforeturnitemrow
  jr inforeturnpublished
inforeturnfloor:
  ld hl,$C380
  ld de,$9880
  ld b,$13
  call infocopycells
inforeturnpublished:
  ei
  pop hl
  pop de
  pop bc
  scf
  ret

; Mode two runs from the last row of the rebuilt screen-20 Action picker. The empty
; parent chrome is already visible, so reveal only the completed Floor title and the
; five-cell Action interiors together. Every other cell remains locked.
inforeturn20publish:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $09
  jp nz,inforeturnbad
  ld a,[$C1B6]
  cp $02
  jp nz,inforeturnbad
  ld a,[$C6A3]
  cp $14
  jp nz,inforeturnbad
  ld a,[$C1B1]
  cp $02
  jp nz,inforeturnbad
  ld hl,$C69A
  ld a,[hl+]
  cp $0D
  jp nz,inforeturnbad
  ld a,[hl+]
  cp $03
  jp nz,inforeturnbad
  ld a,[$C6BB]
  ld c,a
  ld a,[hl+]
  cp c
  jp nz,inforeturnbad
  ld a,[hl+]
  cp $05
  jp nz,inforeturnbad
  ld a,[hl]
  cp $02
  jp nz,inforeturnbad
  ld a,c
  dec a
  cp d
  jp nz,inforeturnbad
inforeturn20drain:
  ; Empty parent chrome has already been visible for several frames.  Release the
  ; native title/row upload tail now; it restores box 39's edge before revealing
  ; the first label.  Publishing here would race that tail's transient Floor-page
  ; indicator and expose text against the wrong top edge.
  xor a
  ld [$C1B3],a
  ld [$C1B4],a
  ld [$C1B6],a
  ei
  pop hl
  pop de
  pop bc
  scf
  ret

; Mode two at screen 7's last box-6 row reveals only the completed title and seven
; Action interiors. info7chrome already published every border and blank interior.
inforeturn7publish:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $0B
  jp nz,inforeturnbad
  ld a,[$C1B6]
  cp $02
  jp nz,inforeturnbad
  ld a,[$C6A3]
  cp $07
  jp nz,inforeturnbad
  ld a,[$C1B1]
  cp $02
  jp nz,inforeturnbad
  ld hl,$C69A
  ld a,[hl+]
  cp $0D
  jp nz,inforeturnbad
  ld a,[hl+]
  dec a
  jp nz,inforeturnbad
  ld a,[hl+]
  cp $07
  jp nz,inforeturnbad
  ld a,[$C1B4]
  cp $07
  jp nz,inforeturnbad
  ld a,[hl+]
  cp $05
  jp nz,inforeturnbad
  ld a,[hl]
  cp $02
  jp nz,inforeturnbad
  ld a,d
  cp $06
  jp nz,inforeturnbad
inforeturn7drain:
  ld a,[$C11A]
  and a
  jr z,inforeturn7ready
  call $06F7
  jr inforeturn7drain
inforeturn7ready:
  call infovblank
  ld hl,$C321
  ld de,$9821
  ld b,$12
  call infocopycells
  ld hl,$C34E
  ld de,$984E
  ld c,$07
inforeturn7row:
  ld b,$05
  call infocopycells
  ld a,l
  add a,$3B
  ld l,a
  jr nc,inforeturn7src
  inc h
inforeturn7src:
  ld a,e
  add a,$3B
  ld e,a
  jr nc,inforeturn7dst
  inc d
inforeturn7dst:
  dec c
  jr nz,inforeturn7row
  xor a
  ld [$C1B3],a
  ld [$C1B4],a
  ld [$C1B5],a
  ld [$C1B6],a
  ei
  pop hl
  pop de
  pop bc
  scf
  ret

; The first proportional row of a screen-12/13 Pot viewer arrives while its Action
; parent is still visible.  The native renderer composes the wide body before the
; compact title and used to disable the LCD until both were finished.  Prove one of the
; three measured parents -- Items/appended Floor (0,1,2), unidentified Floor (0,7), or
; storage Floor (0,20) -- retire its map while its tiles are still stable, and install
; complete empty Pot chrome.  Later row attempts retain state $0C and skip the legacy
; LCD-off site; their map references remain shadow-only until the title's existing final
; boundary calls potentrypublish.
potentrybegin:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $0C
  jp z,potentryactive
  and a
  jp nz,potentrybad
  ld a,[$C6A3]
  ld e,a
  sub $0C
  cp $02
  jp nc,potentrybad
  ld a,[$C1B6]
  cp $02
  jp nc,potentrybad
  ld a,[$C534]
  cp $03
  jr z,potentrystack3
  cp $02
  jp nz,potentrybad
  ld hl,$C535
  ld a,[hl+]
  and a
  jp nz,potentrybad
  ld a,[hl+]
  cp $07
  jr z,potentrystacklast
  cp $14
  jp nz,potentrybad
  jr potentrystacklast
potentrystack3:
  ld hl,$C535
  ld a,[hl+]
  and a
  jp nz,potentrybad
  ld a,[hl+]
  dec a
  jp nz,potentrybad
  ld a,[hl+]
  cp $02
  jp nz,potentrybad
potentrystacklast:
  ld a,[hl]
  cp e
  jp nz,potentrybad
  ld a,[$C6A6]
  and a
  jp nz,potentrybad
  ld a,[$C6DE]
  and $7E
  jp nz,potentrybad
  ld a,[$C6DE]
  rlca
  and $01
  ld d,a
  ld a,e
  and $01
  cp d
  jp nz,potentrybad
potentrycontextok:
  ld a,[$C6AA]
  and a
  jp z,potentrybad
  cp $15
  jp nc,potentrybad
  ld a,[$C6BB]
  and a
  jp z,potentrybad
  cp $06
  jp nc,potentrybad
  ld b,a
  ld hl,$C69A
  ld a,[hl+]
  and a
  jp nz,potentrybad
  ld a,[hl+]
  cp $03
  jp nz,potentrybad
  ld a,[hl+]
  cp b
  jp nz,potentrybad
  ld a,[hl+]
  cp $12
  jp nz,potentrybad
  ld a,[hl]
  cp $02
  jp nz,potentrybad
  ld a,[$C1B1]
  dec a
  jp nz,potentrybad
  ld a,[$C0D5]
  dec a
  jp nz,potentrybad
  ld a,[$C0D9]
  cp $80
  jp nz,potentrybad
  ld a,[$C0DA]
  cp $C3
  jp nz,potentrybad
  ldh a,[$FF40]
  and $F8
  cp $E0
  jp nz,potentrybad
  ldh a,[$FF42]
  and a
  jp nz,potentrybad
  ldh a,[$FF43]
  and a
  jp nz,potentrybad
  ldh a,[$FF4A]
  cp $80
  jp nz,potentrybad
  ldh a,[$FF4B]
  cp $07
  jp nz,potentrybad
  ld a,$0C
  ld [$C1B3],a
  ld a,e
  cp $0D
  jr nz,potentryblank
  xor a
  ld [$C1B6],a
potentryblank:
  call potentrychrome
potentryactive:
  pop hl
  pop de
  pop bc
  scf
  ret
potentrybad:
  pop hl
  pop de
  pop bc
  and a
  ret

; Blank only the sixteen visible BG rows owned by Items/Floor plus their Action overlay,
; four rows per VBlank.  With every old dynamic reference gone, publish static title/body
; borders in one further VBlank.  The Window status strip remains untouched throughout.
potentrychrome:
  ld hl,$9800
  ld b,$10
potentryclearbatch:
  call infovblank
  ld d,$04
potentryclearrow:
  ld c,$14
  xor a
potentryclearcell:
  ld [hl+],a
  dec c
  jr nz,potentryclearcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,potentryclearnext
  inc h
potentryclearnext:
  dec b
  jr z,potentrychromeready
  dec d
  jr nz,potentryclearrow
  jr potentryclearbatch
potentrychromeready:
  call infovblank
  ld hl,$9800
  ld [hl],$B8
  inc hl
  ld b,$03
  ld a,$BC
potentrytitletop:
  ld [hl+],a
  dec b
  jr nz,potentrytitletop
  ld [hl],$B9
  ld hl,$9820
  ld [hl],$BE
  ld hl,$9824
  ld [hl],$BF
  ld hl,$9840
  ld [hl],$BA
  inc hl
  ld b,$03
  ld a,$BD
potentrytitlebottom:
  ld [hl+],a
  dec b
  jr nz,potentrytitlebottom
  ld [hl],$BB
  ld hl,$9860
  ld [hl],$B8
  inc hl
  ld b,$12
  ld a,$BC
potentrybodytop:
  ld [hl+],a
  dec b
  jr nz,potentrybodytop
  ld [hl],$B9
  ld hl,$9880
  ld a,[$C6BB]
  ld b,a
potentrybodymiddle:
  ld [hl],$BE
  ld a,l
  add a,$13
  ld l,a
  jr nc,potentrybodyright
  inc h
potentrybodyright:
  ld [hl],$BF
  ld a,l
  add a,$0D
  ld l,a
  jr nc,potentrybodynext
  inc h
potentrybodynext:
  dec b
  jr nz,potentrybodymiddle
  ld [hl],$BA
  inc hl
  ld b,$12
  ld a,$BD
potentrybodybottom:
  ld [hl+],a
  dec b
  jr nz,potentrybodybottom
  ld [hl],$BB
  ei
  ret

; Box 17 is the native all-content completion boundary.  Once its title pixels and all
; prior body pixels have drained, reveal the finished shadow top-to-bottom in batches of
; at most three rows.  The already-visible Pot chrome therefore always precedes text.
potentrypublish:
  push bc
  push de
  push hl
  ld a,[$C1B3]
  cp $0C
  jr nz,potentrypublishbad
  ld a,[$C6A3]
  sub $0C
  cp $02
  jr nc,potentrypublishbad
  ld hl,$C69A
  ld a,[hl+]
  and a
  jr nz,potentrypublishbad
  ld a,[hl+]
  and a
  jr nz,potentrypublishbad
  ld a,[hl+]
  dec a
  jr nz,potentrypublishbad
  ld a,[hl+]
  cp $03
  jr nz,potentrypublishbad
  ld a,[hl]
  cp $40
  jr nz,potentrypublishbad
potentrypublishdrain:
  ld a,[$C11A]
  and a
  jr z,potentrypublishready
  call $06F7
  jr potentrypublishdrain
potentrypublishready:
  ld hl,$C300
  ld de,$9800
  ld a,[$C6BB]
  add a,$05
  ld c,a
potentrypublishbatch:
  call infovblank
  ld b,$03
potentrypublishrow:
  push bc
  ld b,$01
  call infocopyrows
  pop bc
  dec c
  jr z,potentrypublishdone
  dec b
  jr nz,potentrypublishrow
  jr potentrypublishbatch
potentrypublishdone:
  xor a
  ld [$C1B3],a
  ld a,[$C6A3]
  cp $0D
  jr nz,potentrypublished
  xor a
  ld [$C1B6],a
potentrypublished:
  ei
  pop hl
  pop de
  pop bc
  scf
  ret
potentrypublishbad:
  pop hl
  pop de
  pop bc
  and a
  ret

; Build the complete empty screen-4 box in shadow.
infobox:
  ; A six-/seven-row picker can extend two rows below Info's bottom border. This also
  ; occurs on the Items-derived screen-1 Floor route: its seventh Info row is mapped on
  ; row 14 and its bottom border is on row 15. Clear both rows before any Info raster can
  ; reuse those Action tiles, then publish them with the last chrome batch.
  ld hl,$C4C0
  ld b,$02
infoboxtailrow:
  ld c,$14
  xor a
infoboxtailcell:
  ld [hl+],a
  dec c
  jr nz,infoboxtailcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,infoboxtailnext
  inc h
infoboxtailnext:
  dec b
  jr nz,infoboxtailrow
infoboxbody:
  ld hl,$C360
  ld [hl],$B8
  inc hl
  ld b,$12
  ld a,$BC
infoboxtop:
  ld [hl+],a
  dec b
  jr nz,infoboxtop
  ld [hl],$B9
  ld hl,$C380
  ld d,$09
infoboxmiddle:
  ld [hl],$BE
  inc hl
  ld b,$12
  xor a
infoboxempty:
  ld [hl+],a
  dec b
  jr nz,infoboxempty
  ld [hl],$BF
  ld a,l
  add a,$0D
  ld l,a
  jr nc,infoboxnext
  inc h
infoboxnext:
  dec d
  jr nz,infoboxmiddle
  ld [hl],$BA
  inc hl
  ld b,$12
  ld a,$BD
infoboxbottom:
  ld [hl+],a
  dec b
  jr nz,infoboxbottom
  ld [hl],$BB
  ; The independent screen-20 lifecycle publishes this shadow selectively from the
  ; pre-upload hook. Screen 1 keeps its already-reviewed complete-empty transaction.
  call infoowned
  jr nc,infoboxpublish
  cp $14
  jr z,infoboxdone
infoboxpublish:
  ld hl,$C360
  ld de,$9860
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$03
  call infocopyrows
  ld b,$02
  call infocopyrows
infoboxdone:
  ei
  ret

; Retire only the five proportional Info rows before the parent allocator may repaint
; their tiles. Preserve both headers and all box chrome; normalize the native arrow and
; counter cells back to the bottom border so the visible intermediate is an empty Info
; window rather than a blank screen. The hardware Window at WY=$80 is untouched.
infoallblank:
  call infovblank
  ld hl,$9881
  ld d,$05
infoallrow:
  ld c,$12
  xor a
infoallcell:
  ld [hl+],a
  dec c
  jr nz,infoallcell
  ld a,l
  add a,$2E
  ld l,a
  jr nc,infoallnext
  inc h
infoallnext:
  dec d
  jr nz,infoallrow
  ld hl,$99A9
  ld b,$02
  ld a,$BD
infoallarrow:
  ld [hl+],a
  dec b
  jr nz,infoallarrow
  ld hl,$99B0
  ld b,$03
infoallcounter:
  ld [hl+],a
  dec b
  jr nz,infoallcounter
  ei
  ret

; The native replay cleared shadow before screen 1 began. Construct either the complete
; five-row Items chrome or the real one-row selector-$FF Floor chrome, then commit rows
; 0-15 in four VBlanks before proportional composition resumes.
inforeturnchrome:
  ld hl,$C300
  ld d,$10
inforeturnclearrow:
  ld b,$14
  xor a
inforeturnclearcell:
  ld [hl+],a
  dec b
  jr nz,inforeturnclearcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,inforeturnclearnext
  inc h
inforeturnclearnext:
  dec d
  jr nz,inforeturnclearrow
  ; Header box 14/18: x=0, y=0, one row, width four.
  ld hl,$C300
  ld c,$04
  call infochrometop
  ld hl,$C320
  ld c,$04
  call infochromemiddle
  ld hl,$C340
  ld c,$04
  call infochromebottom
  ; Body box 4: x=0, y=3, width eighteen and one or five text rows.
  ld hl,$C360
  ld c,$12
  call infochrometop
  ld hl,$C380
  ld a,[$C6AC]
  cp $FF
  jr z,inforeturnfloorchrome
  ld d,$09
inforeturnmiddleloop:
  ld c,$12
  call infochromemiddle
  ld a,l
  add a,$0D
  ld l,a
  jr nc,inforeturnmiddlenext
  inc h
inforeturnmiddlenext:
  dec d
  jr nz,inforeturnmiddleloop
  ld c,$12
  call infochromebottom
  jr inforeturnchromecopy
inforeturnfloorchrome:
  ld c,$12
  call infochromemiddle
  ld a,l
  add a,$0D
  ld l,a
  jr nc,inforeturnfloorbottom
  inc h
inforeturnfloorbottom:
  ld c,$12
  call infochromebottom
inforeturnchromecopy:
  ld hl,$C300
  ld de,$9800
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  ei
  ret

; Construct the exact empty screen-7 parent: full-width box-5 title plus seven-row box 6
; at y=1. This geometry is intentionally separate from screen 20's y=3 box 39 even
; though both dispatcher IDs share native handler 4:$4A58.
info7chrome:
  ld hl,$C300
  ld d,$12
info7clearrow:
  ld b,$14
  xor a
info7clearcell:
  ld [hl+],a
  dec b
  jr nz,info7clearcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,info7clearnext
  inc h
info7clearnext:
  dec d
  jr nz,info7clearrow
  ; Box 5: x=0, y=0, one row, width eighteen.
  ld hl,$C300
  ld c,$12
  call infochrometop
  ld hl,$C320
  ld c,$12
  call infochromemiddle
  ld hl,$C340
  ld c,$12
  call infochromebottom
  ; Box 6: x=13, y=1, seven rows, width five.
  ld hl,$C32D
  ld c,$05
  call infochrometop
  ld hl,$C34D
  ld d,$0D
info7middle:
  ld c,$05
  call infochromemiddle
  ld a,l
  add a,$1A
  ld l,a
  jr nc,info7middlenext
  inc h
info7middlenext:
  dec d
  jr nz,info7middle
  ld c,$05
  call infochromebottom
  ld hl,$C300
  ld de,$9800
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
info7chromedone:
  ei
  ret

; Construct the exact empty screen-20 Floor parent: its full-width item title plus the
; right-side 3-7-row Action picker. Rows 16-17 are shadow-complete for the seven-row
; identity-hidden Pot even though the hardware Window covers them at WY=$80. Only the
; sixteen visible BG rows are committed.
info20chrome:
  ld hl,$C300
  ld d,$12
info20clearrow:
  ld b,$14
  xor a
info20clearcell:
  ld [hl+],a
  dec b
  jr nz,info20clearcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,info20clearnext
  inc h
info20clearnext:
  dec d
  jr nz,info20clearrow
  ; Box 5: x=0, y=0, one row, width eighteen.
  ld hl,$C300
  ld c,$12
  call infochrometop
  ld hl,$C320
  ld c,$12
  call infochromemiddle
  ld hl,$C340
  ld c,$12
  call infochromebottom
  ; Box 39: x=13, y=3, width five and C6BB text rows.
  ld a,[$C1B4]
  ld e,a
  ld hl,$C36D
  ld c,$05
  call infochrometop
  ld a,e
  add a,a
  dec a
  ld d,a
  ld hl,$C38D
info20middle:
  ld c,$05
  call infochromemiddle
  ld a,l
  ; infochromemiddle leaves HL on the right border at column 19. Advance 26
  ; bytes to the next row's column 13 (a complete 32-byte tilemap stride).
  add a,$1A
  ld l,a
  jr nc,info20middlenext
  inc h
info20middlenext:
  dec d
  jr nz,info20middle
  ld c,$05
  call infochromebottom
  ld hl,$C300
  ld de,$9800
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
  call infovblank
  ld b,$04
  call infocopyrows
info20chromedone:
  ei
  ret

infochrometop:
  ld [hl],$B8
  inc hl
  ld a,$BC
  call infochromefill
  ld [hl],$B9
  ret
infochromemiddle:
  ld [hl],$BE
  inc hl
  xor a
  call infochromefill
  ld [hl],$BF
  ret
infochromebottom:
  ld [hl],$BA
  inc hl
  ld a,$BD
  call infochromefill
  ld [hl],$BB
  ret
infochromefill:
  ld [hl+],a
  dec c
  jr nz,infochromefill
  ret

; Wait for a complete VBlank while allowing native interrupts between batches. Preserve
; all copy registers across the interrupt handler and close the late-VBlank race after DI.
infovblank:
  push bc
  push de
  push hl
  ei
infovisible:
  ldh a,[$FF44]
  cp $90
  jr nc,infovisible
  di
  ldh a,[$FF44]
  cp $90
  jr c,infowait
infolate:
  ldh a,[$FF44]
  cp $90
  jr nc,infolate
infowait:
  ldh a,[$FF44]
  cp $90
  jr c,infowait
  pop hl
  pop de
  pop bc
  ret

infocopyrows:
  ld c,$14
infocopyrowcell:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,infocopyrowcell
  ld a,l
  add a,$0C
  ld l,a
  jr nc,infocopysource
  inc h
infocopysource:
  ld a,e
  add a,$0C
  ld e,a
  jr nc,infocopydest
  inc d
infocopydest:
  dec b
  jr nz,infocopyrows
  ret

infocopycells:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,infocopycells
  ret

infopagerpixels:
  ld a,[$C6BD]
  cp $02
  ret c
  cp $0A
  ret nc
  inc a
  call infodigit
  ld a,[$C6BC]
  add a,$02
  call infodigit
  ret

; A is the native tile code ($02-$0A) for digits 1-9. The approved font is 1bpp, so
; duplicate each row into both Game Boy bitplanes at that tile's signed $9000 address.
infodigit:
  ld c,a
  sub $02
  add a,a
  add a,a
  add a,a
  ld e,a
  ld d,$00
  ld hl,infodigits
  add hl,de
  ld a,c
  swap a
  ld e,a
  ld d,$90
  ld b,$08
infodigitrow:
  ld a,[hl+]
  ld [de],a
  inc de
  ld [de],a
  inc de
  dec b
  jr nz,infodigitrow
  ret

infodigits:
""" + _INFO_DIGIT_TABLE + "\n"


# Same-bank leaf called from the screen-12/13 pop proof. Keeping it at a fixed address
# avoids consuming a far-table slot: bank 62's last slot ends at $400F and the shared
# text-pool reader begins at $4010.
POT_FLOOR_RETURN_SRC = """
potfloorreturn:
  ld a,[$C1B5]
  or $1F
  ld [$C1B5],a
  ld a,$04
  ld [$C1B4],a
  ld a,$08
  ret
"""


def info_lifecycle_labels():
    """Assemble the installed Info helper and return its stable symbolic addresses.

    Runtime fixtures hook ``fidisable`` rather than sampling LCDC once per frame.  Keep
    that address derived from the same source the installer emits so adding a helper
    cannot silently move the blanker away from the audit.
    """
    return gbasm.assemble(INFO_LIFECYCLE_SRC, INFO_LIFECYCLE_AT)[1]


# Title/file screens are composites, not independent boxes: the parent title remains
# visible behind Log selection, difficulty, summaries and Rank/Pass. Their VWF tile
# lifetimes therefore have to be changed atomically.  Mode 0 starts an exact allowlisted
# multi-row transaction (or the Rankings transaction) before row 0 changes any pixels.
# The finalizer below pre-stages the native bottom border and publishes the complete
# 20x18 shadow map.  States $10-$13 stay disjoint from V4F's item/Floor states $01-$06.
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
  ld a,[$C1B3]
  and a
  jp nz,stdone
  xor a
  rst $10
  db $%02X,$%02X
  ; Classification 3 is the hidden debug item picker, not a layered title/file
  ; transaction.  Treating it as generic start-flow disabled the LCD on row 0; only
  ; Weapon happened to reach a compatible completion path; the other categories left
  ; the native queue active and the LCD white forever.
  cp $03
  jp z,stdone
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
  ld [$C1B3],a
  ldh a,[$FF40]
  set 3,a
  ld [$C110],a
  ldh [$FF40],a
  jr stdone
stgeneric:
  ld a,$10
stoff:
  ld [$C1B3],a
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
  ld a,[$C1B3]
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
  rst $10
  db $%02X,$%02X
sfcursorready:
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
sfpublished:
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
  ld [$C1B3],a
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
""" % (TITLE_CURSOR_INDEX, ACTION_ALLOC_BANK,
         ITEM_PUBLISH_INDEX, ITEM_PUBLISH_BANK, RESET_INDEX, FAR_BANK)


def rom_reader():
    code, labels = gbasm.assemble(ROM_READ_SRC, ROM_READ_ORG)
    assert len(code) == len(ROM_READ_OLD)
    return code, labels

# original entry bytes we replace ($40D8-$40E3): push af/bc/de/hl, then the two loads
# that build bc from $C69F/$C6A0. The fallback path re-does those loads far-side.
OLD_ENTRY = bytes.fromhex('f5c5d5e5fa9fc64ffaa0c647')


SRC = """
menurow:
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


def _fused_src():
    """Render native fusion-count digits $8B-$94 at any pixel residue."""
    return """
fusedglyph:
  add a,a
  add a,a
  add a,a
  ld [$C0E2],a
  ld a,$08
  ld [$C0DD],a
  ld a,[$C0CF]
  and $07
  ld [$C0E3],a
  ld b,a
  ld a,$08
  sub b
  ld [$C0E6],a
  ld a,[$C0CF]
  srl a
  srl a
  srl a
  rst $10
  db $%02X,$%02X
  push de
  ld a,[$C0CF]
  srl a
  srl a
  srl a
  inc a
  rst $10
  db $%02X,$%02X
  ld a,e
  ld [$C0E4],a
  ld a,d
  ld [$C0E5],a
  pop de
  ld b,$08
fusedrows:
  ld a,[$C0E2]
  rst $10
  db $%02X,$%02X
  ld c,a
  ld hl,$C0E2
  inc [hl]
  push bc
  ld a,[$C0E3]
  ld b,a
  inc b
  ld a,c
fusedright:
  dec b
  jr z,fusedrightdone
  srl a
  jr fusedright
fusedrightdone:
  ld c,a
  call fusedpair
  pop bc
  ld a,[$C0E3]
  and a
  jr z,fusednext
  push de
  ld a,[$C0E4]
  ld e,a
  ld a,[$C0E5]
  ld d,a
  push bc
  ld a,[$C0E6]
  ld b,a
  inc b
  ld a,c
fusedleft:
  dec b
  jr z,fusedleftdone
  sla a
  jr fusedleft
fusedleftdone:
  ld c,a
  call fusedpair
  ld a,e
  ld [$C0E4],a
  ld a,d
  ld [$C0E5],a
  pop bc
  pop de
fusednext:
  dec b
  jr nz,fusedrows
  ret
fusedpair:
  ld a,[de]
  or c
  ld [de],a
  inc de
  ld a,[de]
  or c
  ld [de],a
  inc de
  ret
""" % (FUSED_PAYLOAD_INDEX, FUSED_DATA_BANK,
       FUSED_PAYLOAD_INDEX, FUSED_DATA_BANK,
       FUSED_READ_INDEX, FUSED_DATA_BANK)


def _fused_data_src():
    """Reader/data shared by the compact fusion-count residue shifter."""
    table = ','.join('$%02X' % value for value in FUSED_NATIVE)
    return """
fusedread:
  push de
  ld l,a
  ld h,$00
  ld de,fuseddigits
  add hl,de
  ld a,[hl]
  pop de
  ret
fusedpayload:
  cp $0C
  jr c,fusedpnorm
  ld de,$C12C
  ret
fusedpnorm:
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
fuseddigits:
  db %s
""" % table


def _shop_suffix_src():
    """Validate and preserve the raw right-aligned price tiles on shop item rows."""
    return """
scanhigh:
  cp $7C
  jr c,scanbad
  cp $81
  jr c,scangood
  cp $88
  jr z,scangood
  cp $8A
  jr z,scangood
  cp $%02X
  jr c,scanbad
  cp $%02X
  jr c,scangood
  cp $9E
  jr c,scanbad
  cp $A1
  jr c,scangood
  cp $B0
  jr c,scanbad
  cp $B6
  jr c,scangood
  cp $D0
  jr c,scanbad
  cp $DF
  jr nc,scanbad
  push de
  push hl
  ld h,a
  ld a,d
  cp $05
  jr nc,shopsbad
  add a,a
  add a,d
  add a,$D0
  cp h
  jr nz,shopsbad
  ld a,[$C1B1]
  cp $01
  jr nz,shopsbad
  ld a,[$C0D0]
  cp $02
  jr nz,shopsbad
  ld l,$01
shopsloop:
  ld a,[bc]
  cp $FF
  jr z,shopsterm
  inc h
  cp h
  jr nz,shopsbad
  inc l
  ld a,l
  cp $04
  jr nc,shopsbad
  inc bc
  jr shopsloop
shopsbad:
  pop hl
  pop de
scanbad:
  and a
  ret
shopsterm:
  ld a,l
  cp $03
  jr nz,shopsbad
  inc bc
  ld [$C0E7],a
  pop hl
  pop de
  xor a
scangood:
  scf
  ret

copyprice:
  ld a,[$C0E7]
  and a
  ret z
  push bc
  push de
  push hl
  ld e,a
  ld d,a
  ld a,[$C0CC]
  ld c,a
  ld a,[$C0CD]
  ld b,a
  dec bc
copybacksrc:
  dec bc
  dec d
  jr nz,copybacksrc
  ld d,e
copybackdest:
  dec hl
  dec d
  jr nz,copybackdest
copyloop:
  ld a,[bc]
  ld [hl+],a
  inc bc
  dec e
  jr nz,copyloop
  pop hl
  pop de
  pop bc
  ret
""" % (FUSED_FIRST, FUSED_LAST + 1)


def _shop_label_src(font):
    """Stage private Dot-font ``Price``/``G`` tiles and patch their shadow cells."""
    def raster(text):
        extent = font.text_extent(text)
        tiles = [bytearray(8) for _ in range((extent + 7) >> 3)]
        pen = 0
        for ch in text:
            for y, bits in enumerate(font.glyphs[ch]):
                for x in range(8):
                    if not bits & (0x80 >> x):
                        continue
                    pixel = pen + x
                    if pixel < len(tiles) * 8:
                        tiles[pixel >> 3][y] |= 0x80 >> (pixel & 7)
            pen += font.advance(ch)
        return tuple(bytes(tile) for tile in tiles)

    price = raster('Price')
    gitan = raster('G')
    if (len(price), len(gitan)) != (3, 1):
        raise SystemExit('menuvwf: shop Price/G raster needs %d+%d tiles, expected 3+1' %
                         (len(price), len(gitan)))
    payload = b''.join(price + gitan)
    data = ','.join('$%02X' % value for value in payload)
    return """
shoplabel:
  push af
  push bc
  push de
  push hl
  ld a,h
  cp $%02X
  jr nz,shopgitan
  ld a,l
  cp $%02X
  jr nz,shoplabeldone
  ldh a,[$FF40]
  bit 7,a
  jr z,shopdirect
shopqueue:
  ld a,[$C11A]
  and a
  jr z,shopqueuedest
  call $06F7
  jr shopqueue
shopqueuedest:
  ld c,$01
  ld de,$C008
  jr shopcopy
shopdirect:
  ld c,$00
  ld de,$%04X
shopcopy:
  ld hl,shoplabeldata
  ld b,$%02X
shopcopyloop:
  ld a,[hl+]
  ld [de],a
  inc de
  ld [de],a
  inc de
  dec b
  jr nz,shopcopyloop
  ld a,c
  and a
  jr z,shopuploaded
  xor a
  rst $10
  db $%02X,$%02X
shopuploaded:
  ld hl,$%04X
  ld a,$%02X
  ld b,$%02X
shoppricemap:
  ld [hl+],a
  inc a
  dec b
  jr nz,shoppricemap
  jr shoplabeldone
shopgitan:
  cp $%02X
  jr nz,shoplabeldone
  ld a,l
  cp $%02X
  jr nz,shoplabeldone
  ld [hl],$%02X
shoplabeldone:
  pop hl
  pop de
  pop bc
  pop af
  ret
shoplabeldata:
  db %s
""" % (SHOP_PRICE_KEY >> 8, SHOP_PRICE_KEY & 0xFF,
       SHOP_LABEL_VRAM, len(payload), SHOP_UPLOAD_INDEX, SHOP_UPLOAD_BANK,
       SHOP_PRICE_KEY, SHOP_LABEL_BASE, len(price),
       SHOP_GITAN_KEY >> 8, SHOP_GITAN_KEY & 0xFF,
       SHOP_LABEL_BASE + len(price), data)


SHOP_UPLOAD_SRC = """
shopupload:
  push af
  push bc
  push de
  push hl
  ld a,[$C000]
  push af
  ld a,[$C001]
  push af
  ld hl,$C008
  ld de,$C04A
  ld b,$40
shopdup:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,shopdup
  ld hl,$C038
  ld de,$C08C
  ld b,$10
shoptail:
  ld a,[hl+]
  ld [de],a
  inc de
  dec b
  jr nz,shoptail
  xor a
  ld [$C000],a
  ld [$C006],a
  ld [$C048],a
  ld a,$8C
  ld [$C001],a
  ld [$C007],a
  ld [$C049],a
  ld a,$30
  ld [$C08A],a
  ld a,$8C
  ld [$C08B],a
  ld a,$0A
  ld [$C11A],a
  call $06F7
  pop af
  ld [$C001],a
  pop af
  ld [$C000],a
  pop hl
  pop de
  pop bc
  pop af
  ret
"""


SHOP_SHAPE_SRC = """
shopshape:
  ld a,[$C69A]
  and a
  jr nz,shopshapebad
  ld a,[$C69B]
  cp $03
  jr z,shopshapey
  cp $0D
  jr nz,shopshapebad
shopshapey:
  ld a,[$C69C]
  cp $01
  jr nz,shopshapebad
  ld a,[$C69D]
  cp $08
  jr nz,shopshapebad
  ld a,[$C69E]
  and a
  jr nz,shopshapebad
  ld a,d
  and a
  jr nz,shopshapebad
  ld a,b
  cp $C6
  jr nz,shopshapebad
  ld a,c
  cp $16
  jr nz,shopshapebad
  ld a,$%02X
  ld [$C61D],a
  ld a,$%02X
  ld [$C1B1],a
  ld a,$01
  ld [$C0D0],a
  ld a,$03
  ret
shopshapebad:
  xor a
  ret
""" % (propvwf.EN_CODES['G'], SHOP_VALUE_CLASS)


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

    # A long save-summary place row and screen 28 both need a shape-specific final
    # source handoff. Write the ordinary pointer first, then let the helper override it.
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

    old = """  cp $43
  jr c,scanok
  cp $7C
  jr z,scanok
  cp $7E
  jr z,scanok
  cp $7F
  jr z,scanok
  jp fallback
"""
    new = """  cp $43
  jr c,scanok
  rst $10
  db $%02X,$%02X
  jp nc,fallback
  and a
  jp z,scanend
  jr scanok
""" % (SHOP_SCAN_INDEX, SHOP_SUFFIX_BANK)
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
  ld [$C0D6],a
  and a
  jr nz,itemresetdone
  call resetalloc
  ld a,$01
  ld [$C0D5],a
itemresetdone:
  ld a,$01
  ld [$C1B1],a
  jp shapeok
badshape:
  jp fallback
notitem:
  cp $06
  jr nz,notgroundpopup
  xor a
  rst $10
  db $%02X,$%02X
  and a
  ; Width six is shared by the standing Trap/Stairs popup and the title-screen
  ; Rank/Pass popup.  A rejected ground-command shape must continue through the
  ; start-flow classifier; falling straight back here leaves Rank/Pass fixed-width.
  jp z,startshapecheck
  xor a
  ld [$C1B1],a
  inc a
  ld [$C0D0],a
  jp shapeok
notgroundpopup:
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
  cp $03
  jr z,shapeok
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
  ; VWF rows per box. This was $06, which is every action box EXCEPT one: an
  ; identity-hidden Pot on the floor. Hiding an identity inserts `Name`, and a Pot
  ; alone adds `See` and `Push`, so `Take/See/Push/Toss/Swap/Name/Info` is seven rows
  ; and `Info` fell out to fixed width. That was not merely cosmetic -- the fallback
  ; row never reaches the floor-info hook, so `fiborder` never saw D == [$C69C]-1,
  ; `fifinish`/publishmap never ran, and the LCD stayed disabled after the description
  ; closed. The player got a white screen. See tools/unidentifiedpotspill.py.
  ld a,d
  cp $08
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
""" % (GROUND_POPUP_INDEX, GROUND_POPUP_BANK,
         START_AUX_INDEX, START_AUX_BANK,
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
  jr z,fixedsummaryplace
  cp $02
  jr nz,fixednativecap
  ; Summary row 2's final fixed cell is the raw attempt-count digit. It is redrawn by
  ; the native field writer and must not be interpreted as an English source code (an
  ; Expert save's digit $38 otherwise appears as a duplicate lowercase `t`).
  ld a,e
  cp $0D
  jr z,scanend
  jr fixednativecap
fixedsummaryplace:
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

    # The item-page controller begins an exact screen-1 regional transaction before any
    # reused tile upload, while retaining the legacy Pot and LCD-off entry paths.
    old = """upload:
  ldh a,[$FF40]
"""
    new = """upload:
  ld a,[$C0DC]
  and a
  jp nz,widetail
  xor a
  rst $10
  db $%02X,$%02X
  xor a
  rst $10
  db $%02X,$%02X
  jp c,shadow
  ldh a,[$FF40]
""" % (ITEM_PAGE_INDEX, ITEM_PAGE_BANK,
         ITEM_RETURN_INDEX, ITEM_RETURN_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    # A proven live screen-1 Item row needs only its regional publisher. Skipping the
    # four unrelated Action/shop/title/Floor finalizers here saves enough CPU time to
    # arm the following row before the next VBlank. Every other shape retains the full
    # shared finalizer chain.
    old = """rborder:
  ld a,$BF
  ld [hl],a
  ld a,[$C0CC]
"""
    new = """rborder:
  ld [hl],$BF
  ld a,[$C1B3]
  dec a
  jr nz,rbgeneric
  ld a,[$C1B6]
  cp $02
  jr nz,rbgeneric
  ld a,[$C1B1]
  dec a
  jr nz,rbgeneric
  ld a,[$C0CC]
  ld [$C69F],a
  ld a,[$C0CD]
  ld [$C6A0],a
  ld a,$01
  rst $10
  db $%02X,$%02X
  scf
  ret
rbgeneric:
  rst $10
  db $%02X,$%02X
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,$01
  rst $10
  db $%02X,$%02X
  ld a,$01
  rst $10
  db $%02X,$%02X
rbfinished:
  ld a,[$C0CC]
""" % (ITEM_REGION_INDEX, ITEM_REGION_BANK,
         SHOP_COPY_INDEX, SHOP_SUFFIX_BANK,
         START_FINISH_INDEX, START_FINISH_BANK,
         ITEM_PAGE_INDEX, ITEM_PAGE_BANK, FLOOR_INFO_INDEX, FLOOR_INFO_BANK)
    assert old in src
    src = src.replace(old, new, 1)

    # Empty trailing rows take the native fallback. The controller marks an intentional
    # regional screen-1 empty row in per-row scratch; Floor/Info's generic fallback hook
    # then leaves that transaction alone. Pot/Info rows retain their established path.
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
  ld [$C0E7],a
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
  cp $9E
  jp nc,fallback
  ld a,e
  cp $9F
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

    # Deterministic packing policy for the measured 57+11+4 runs now lives in bank 61,
    # where the exact carried-/Floor-Action gate can select its disjoint $C7-$DE slices without
    # growing bank 32 (which is full). The ordinary allocator policy and outputs are
    # unchanged for every other shape.
    start = src.index("anew:\n")
    end = src.index("capfits:\n", start) + len("capfits:\n")
    allocate = """anew:
  call capneed
  ld c,a
  rst $10
  db $%02X,$%02X
  jp c,fallback
capfits:
""" % (ACTION_ALLOC_INDEX, ACTION_ALLOC_BANK)
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
  ld a,$%02X
  ld [$C0DB],a
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
  ; Same-screen Item paging preserves the already-visible static Items title planes.
  ; Rebuild only its shadow references; initial Status -> Items has no $C1B6=$02 proof
  ; and therefore still composes/uploads the title normally.
  ld a,[$C1B1]
  cp $04
  jr nz,alloccompose
  ld a,[$C1B6]
  cp $02
  jr nz,alloccompose
  ld a,[$C1B3]
  dec a
  jp z,shadow
alloccompose:
  ld hl,$C008
""" % (START_AUX_INDEX, START_AUX_BANK, fei_prompt_y, rank_header_x,
         ROM_RANK_HEADER_CAP + 1, ROM_RANK_HEADER_BASE,
         ROM_FEI_PROMPT_CAP + 1, ROM_FEI_PROMPT_BASE,
         ROM_ONE_BASE,
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
    new = """  ld a,c
  sub $%02X
  cp $%02X
  jr nc,composetable
  rst $10
  db $%02X,$%02X
  jr nospill
composetable:
  call widthfor
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
""" % (FUSED_FIRST, len(FUSED_CODES),
       FUSED_INDEX, FUSED_BANK, propvwf.GLYPH_ORG)
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
  call resetalloc
  ld hl,$9000
  ret
    """ % (propvwf.CORE_CODES, propvwf.CORE_WIDTH_ORG & 0xFF,
           propvwf.CORE_WIDTH_ORG >> 8,
           propvwf.META_ORG, propvwf.CORE_CODES, propvwf.META_ORG)
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
    if proportional:
        ptab = _off(31, 0x45D5)
        plo, phi = (buf[ptab + 2 * GROUND_POPUP_BOX],
                    buf[ptab + 2 * GROUND_POPUP_BOX + 1])
        popup_at = _off(31, (phi << 8) | plo)
        popup = tuple(buf[popup_at:popup_at + 5])
        if popup != (3, 4, 2, GROUND_POPUP_WIDTH_OLD, 0):
            raise SystemExit('menuvwf: ground-command box 3 geometry %s no longer '
                             'matches the measured stair/trap popup' % (popup,))
        buf[popup_at + 3] = GROUND_POPUP_WIDTH
        item_header = _box_geometry(buf, 14)
        if item_header != (0, 0, 1, 4, 0):
            raise SystemExit('menuvwf: item header box 14 geometry %s no longer matches '
                             'the V4F item transition boundary' % (item_header,))
        debug_menu = _box_geometry(buf, DEBUG_MENU_BOX)
        if debug_menu != DEBUG_MENU_SHAPE:
            raise SystemExit('menuvwf: hidden debug item box %d geometry %s no longer '
                             'matches the proportional allowlist %s' %
                             (DEBUG_MENU_BOX, debug_menu, DEBUG_MENU_SHAPE))
        debug_value = _box_geometry(buf, DEBUG_VALUE_BOX)
        if debug_value != DEBUG_VALUE_SHAPE:
            raise SystemExit('menuvwf: hidden debug value box %d geometry %s no longer '
                             'matches the proportional allowlist %s' %
                             (DEBUG_VALUE_BOX, debug_value, DEBUG_VALUE_SHAPE))
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

        # The original fixed-cell shop layout reserves 2 raw cells + 13 name cells +
        # 3 price cells.  VWF has enough horizontal pixels for every current 18-source
        # item variant, but it cannot recover letters already discarded here.  Widen the
        # staging clamp while retaining an explicit upper bound and the native three-cell
        # price suffix.  This is proportional-only: a no-menuvwf control still requires
        # the original fixed 18-cell layout.
        for address, opcode in SHOP_CONTENT_PATCHES:
            at = _off(4, address)
            found = bytes(buf[at:at + 2])
            expected = bytes((opcode, SHOP_OLD_CONTENT_CELLS))
            if found != expected:
                raise SystemExit('menuvwf: shop content clamp at 4:$%04X changed: '
                                 'expected %s, found %s' %
                                 (address, expected.hex(' '), found.hex(' ')))
            buf[at + 1] = SHOP_CONTENT_CELLS

        # 6:$4C2C masks weapons to $01FF and shields to $06FD before 6:$4C61 counts the
        # live ability bits, so both domains top out at nine. That popcount is the MAXIMUM
        # seal count, not the number of reachable values: the producer at 4:$5765/$5D8B
        # adds the count to $8B, so it emits $8B..$94 and a fusion carrying no seals at all
        # is the ordinary $8B case. Reading the nine as a value count is what left $8B
        # unadmitted and dropped every unsealed fusion to fixed width.
        fused_masks = (0x01FF, 0x06FD)
        fused_max = max(bin(mask).count('1') for mask in fused_masks)
        if len(FUSED_CODES) != fused_max + 1 or FUSED_FIRST + fused_max != FUSED_LAST:
            raise SystemExit('menuvwf: fusion-count range no longer covers 0..%d seals '
                             'from the canonical nine-bit equipment masks' % fused_max)
        fused_native_at = propvwf.FONT_BASE + FUSED_FIRST * propvwf.GLYPH_BYTES
        got_fused = bytes(buf[fused_native_at:fused_native_at + len(FUSED_NATIVE)])
        if got_fused != FUSED_NATIVE:
            raise SystemExit('menuvwf: native fusion-count glyphs $%02X-$%02X changed: %s'
                             % (FUSED_FIRST, FUSED_LAST, got_fused.hex()))
        fused_code, fused_labels = gbasm.assemble(_fused_src(), FUSED_AT)
        if FUSED_AT + len(fused_code) > FUSED_LIMIT:
            raise SystemExit('menuvwf: fused-item shifter needs %d bytes, only %d '
                             'available' %
                             (len(fused_code), FUSED_LIMIT - FUSED_AT))
        if buf[_off(FUSED_BANK, 0x4000)] != FUSED_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' % FUSED_BANK)
        fused_at = _off(FUSED_BANK, FUSED_AT)
        if any(value != 0xFF for value in buf[fused_at:fused_at + len(fused_code)]):
            raise SystemExit('menuvwf: bank %d fused-item region at $%04X is not free'
                             % (FUSED_BANK, FUSED_AT))
        fused_ix = _off(FUSED_BANK, 0x4000) + FUSED_INDEX - 1
        if bytes(buf[fused_ix:fused_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (FUSED_INDEX, FUSED_BANK))
        buf[fused_at:fused_at + len(fused_code)] = fused_code
        buf[fused_ix] = fused_labels['fusedglyph'] & 0xFF
        buf[fused_ix + 1] = fused_labels['fusedglyph'] >> 8

        fused_data, fused_data_labels = gbasm.assemble(_fused_data_src(), FUSED_DATA_AT)
        if FUSED_DATA_AT + len(fused_data) > FUSED_DATA_LIMIT:
            raise SystemExit('menuvwf: fusion-count data helper needs %d bytes, only %d '
                             'available' %
                             (len(fused_data), FUSED_DATA_LIMIT - FUSED_DATA_AT))
        if buf[_off(FUSED_DATA_BANK, 0x4000)] != FUSED_DATA_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % FUSED_DATA_BANK)
        fused_data_at = _off(FUSED_DATA_BANK, FUSED_DATA_AT)
        if any(value != 0xFF
               for value in buf[fused_data_at:fused_data_at + len(fused_data)]):
            raise SystemExit('menuvwf: bank %d fusion-count data region at $%04X is not free'
                             % (FUSED_DATA_BANK, FUSED_DATA_AT))
        for index, label in ((FUSED_READ_INDEX, 'fusedread'),
                             (FUSED_PAYLOAD_INDEX, 'fusedpayload')):
            at = _off(FUSED_DATA_BANK, 0x4000) + index - 1
            if bytes(buf[at:at + 2]) != b'\xff\xff':
                raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                                 % (index, FUSED_DATA_BANK))
            target = fused_data_labels[label]
            buf[at] = target & 0xFF
            buf[at + 1] = target >> 8
        buf[fused_data_at:fused_data_at + len(fused_data)] = fused_data

        shop_suffix, shop_labels = gbasm.assemble(_shop_suffix_src(), SHOP_SUFFIX_AT)
        if SHOP_SUFFIX_AT + len(shop_suffix) > SHOP_SUFFIX_LIMIT:
            raise SystemExit('menuvwf: shop-price suffix helper needs %d bytes, only %d '
                             'available' %
                             (len(shop_suffix), SHOP_SUFFIX_LIMIT - SHOP_SUFFIX_AT))
        if buf[_off(SHOP_SUFFIX_BANK, 0x4000)] != SHOP_SUFFIX_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed'
                             % SHOP_SUFFIX_BANK)
        shop_at = _off(SHOP_SUFFIX_BANK, SHOP_SUFFIX_AT)
        if any(value != 0xFF
               for value in buf[shop_at:shop_at + len(shop_suffix)]):
            raise SystemExit('menuvwf: bank %d shop-price suffix region at $%04X is '
                             'not free' % (SHOP_SUFFIX_BANK, SHOP_SUFFIX_AT))
        for index, label in ((SHOP_SCAN_INDEX, 'scanhigh'),
                             (SHOP_COPY_INDEX, 'copyprice')):
            at = _off(SHOP_SUFFIX_BANK, 0x4000) + index - 1
            if bytes(buf[at:at + 2]) != b'\xff\xff':
                raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                                 % (index, SHOP_SUFFIX_BANK))
            target = shop_labels[label]
            buf[at] = target & 0xFF
            buf[at + 1] = target >> 8
        buf[shop_at:shop_at + len(shop_suffix)] = shop_suffix

        shop_label_src = _shop_label_src(font)
        shop_label_code, shop_label_labels = gbasm.assemble(
            shop_label_src, SHOP_LABEL_AT)
        if SHOP_LABEL_AT + len(shop_label_code) > SHOP_LABEL_LIMIT:
            raise SystemExit('menuvwf: shop-label helper needs %d bytes, only %d '
                             'available' %
                             (len(shop_label_code), SHOP_LABEL_LIMIT - SHOP_LABEL_AT))
        if buf[_off(SHOP_LABEL_BANK, 0x4000)] != SHOP_LABEL_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             SHOP_LABEL_BANK)
        shop_label_at = _off(SHOP_LABEL_BANK, SHOP_LABEL_AT)
        if any(value != 0xFF for value in
               buf[shop_label_at:shop_label_at + len(shop_label_code)]):
            raise SystemExit('menuvwf: bank %d shop-label region at $%04X is not free' %
                             (SHOP_LABEL_BANK, SHOP_LABEL_AT))
        shop_label_ix = (_off(SHOP_LABEL_BANK, 0x4000) +
                         SHOP_LABEL_INDEX - 1)
        if bytes(buf[shop_label_ix:shop_label_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (SHOP_LABEL_INDEX, SHOP_LABEL_BANK))
        buf[shop_label_at:shop_label_at + len(shop_label_code)] = shop_label_code
        buf[shop_label_ix] = shop_label_labels['shoplabel'] & 0xFF
        buf[shop_label_ix + 1] = shop_label_labels['shoplabel'] >> 8

        shop_upload_code, shop_upload_labels = gbasm.assemble(
            SHOP_UPLOAD_SRC, SHOP_UPLOAD_AT)
        if SHOP_UPLOAD_AT + len(shop_upload_code) > SHOP_UPLOAD_LIMIT:
            raise SystemExit('menuvwf: shop-label VBlank uploader needs %d bytes, only '
                             '%d available' %
                             (len(shop_upload_code), SHOP_UPLOAD_LIMIT - SHOP_UPLOAD_AT))
        if buf[_off(SHOP_UPLOAD_BANK, 0x4000)] != SHOP_UPLOAD_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             SHOP_UPLOAD_BANK)
        shop_upload_at = _off(SHOP_UPLOAD_BANK, SHOP_UPLOAD_AT)
        if any(value != 0xFF for value in
               buf[shop_upload_at:shop_upload_at + len(shop_upload_code)]):
            raise SystemExit('menuvwf: bank %d shop-label VBlank region at $%04X is '
                             'not free' % (SHOP_UPLOAD_BANK, SHOP_UPLOAD_AT))
        shop_upload_ix = (_off(SHOP_UPLOAD_BANK, 0x4000) +
                          SHOP_UPLOAD_INDEX - 1)
        if bytes(buf[shop_upload_ix:shop_upload_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (SHOP_UPLOAD_INDEX, SHOP_UPLOAD_BANK))
        buf[shop_upload_at:shop_upload_at + len(shop_upload_code)] = shop_upload_code
        buf[shop_upload_ix] = shop_upload_labels['shopupload'] & 0xFF
        buf[shop_upload_ix + 1] = shop_upload_labels['shopupload'] >> 8

        shop_shape_code, shop_shape_labels = gbasm.assemble(
            SHOP_SHAPE_SRC, SHOP_SHAPE_AT)
        if SHOP_SHAPE_AT + len(shop_shape_code) > SHOP_SHAPE_LIMIT:
            raise SystemExit('menuvwf: shop-value shape helper needs %d bytes, only %d '
                             'available' %
                             (len(shop_shape_code), SHOP_SHAPE_LIMIT - SHOP_SHAPE_AT))
        if buf[_off(SHOP_SHAPE_BANK, 0x4000)] != SHOP_SHAPE_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             SHOP_SHAPE_BANK)
        shop_shape_at = _off(SHOP_SHAPE_BANK, SHOP_SHAPE_AT)
        if any(value != 0xFF for value in
               buf[shop_shape_at:shop_shape_at + len(shop_shape_code)]):
            raise SystemExit('menuvwf: bank %d shop-value shape region at $%04X is not '
                             'free' % (SHOP_SHAPE_BANK, SHOP_SHAPE_AT))
        shop_shape_ix = (_off(SHOP_SHAPE_BANK, 0x4000) +
                         SHOP_SHAPE_INDEX - 1)
        if bytes(buf[shop_shape_ix:shop_shape_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (SHOP_SHAPE_INDEX, SHOP_SHAPE_BANK))
        buf[shop_shape_at:shop_shape_at + len(shop_shape_code)] = shop_shape_code
        buf[shop_shape_ix] = shop_shape_labels['shopshape'] & 0xFF
        buf[shop_shape_ix + 1] = shop_shape_labels['shopshape'] >> 8

        shop_label_call = bytes((0xD7, SHOP_LABEL_INDEX, SHOP_LABEL_BANK))
        for address in SHOP_LABEL_PATCHES:
            at = _off(4, address)
            found = bytes(buf[at:at + len(SHOP_LABEL_OLD_CALL)])
            if found != SHOP_LABEL_OLD_CALL:
                raise SystemExit('menuvwf: shop-label writer at 4:$%04X changed: '
                                 'expected %s, found %s' %
                                 (address, SHOP_LABEL_OLD_CALL.hex(' '),
                                  found.hex(' ')))
            buf[at:at + len(shop_label_call)] = shop_label_call

        debug_menu_code, debug_menu_labels = gbasm.assemble(
            DEBUG_MENU_SRC, DEBUG_MENU_AT)
        if DEBUG_MENU_AT + len(debug_menu_code) > DEBUG_MENU_LIMIT:
            raise SystemExit('menuvwf: debug-menu shape helper needs %d bytes, only %d '
                             'available' %
                             (len(debug_menu_code), DEBUG_MENU_LIMIT - DEBUG_MENU_AT))
        if buf[_off(DEBUG_MENU_BANK, 0x4000)] != DEBUG_MENU_BANK:
            raise SystemExit('menuvwf: bank %d pool code is not installed' %
                             DEBUG_MENU_BANK)
        debug_menu_at = _off(DEBUG_MENU_BANK, DEBUG_MENU_AT)
        if any(value != 0xFF for value in
               buf[debug_menu_at:debug_menu_at + len(debug_menu_code)]):
            raise SystemExit('menuvwf: bank %d debug-menu helper region at $%04X is '
                             'not free' % (DEBUG_MENU_BANK, DEBUG_MENU_AT))
        debug_menu_ix = (_off(DEBUG_MENU_BANK, 0x4000) +
                         DEBUG_MENU_INDEX - 1)
        if bytes(buf[debug_menu_ix:debug_menu_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (DEBUG_MENU_INDEX, DEBUG_MENU_BANK))
        buf[debug_menu_at:debug_menu_at + len(debug_menu_code)] = debug_menu_code
        buf[debug_menu_ix] = debug_menu_labels['debugshape'] & 0xFF
        buf[debug_menu_ix + 1] = debug_menu_labels['debugshape'] >> 8

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
            DEBUG_MENU_INDEX, DEBUG_MENU_BANK,
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
        selector_row_ix = (_off(SELECTOR_BANK, 0x4000) +
                           SELECTOR_ROW_INDEX - 1)
        if bytes(buf[selector_row_ix:selector_row_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                             % (SELECTOR_ROW_INDEX, SELECTOR_BANK))
        buf[selector_at:selector_at + len(selector_code)] = selector_code
        buf[selector_ix] = selector_labels['selectorshape'] & 0xFF
        buf[selector_ix + 1] = selector_labels['selectorshape'] >> 8
        buf[selector_row_ix] = selector_labels['selectorrow'] & 0xFF
        buf[selector_row_ix + 1] = selector_labels['selectorrow'] >> 8

        selector_patch_at = _off(SELECTOR_ROW_PATCH_BANK, SELECTOR_ROW_PATCH_AT)
        selector_patch = bytes((0xD7, SELECTOR_ROW_INDEX, SELECTOR_BANK, 0, 0, 0))
        if bytes(buf[selector_patch_at:selector_patch_at + len(selector_patch)]) != \
                SELECTOR_ROW_PATCH_OLD:
            raise SystemExit('menuvwf: Pass log-selector producer moved at %d:$%04X'
                             % (SELECTOR_ROW_PATCH_BANK, SELECTOR_ROW_PATCH_AT))
        buf[selector_patch_at:selector_patch_at + len(selector_patch)] = selector_patch

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

        # The transaction state must never move back onto propvwf's `S_LOCAL`.  Any
        # dialogue leaves a pen or cell index in `$C0D7`, and every live state value is
        # inside that range: a stale read published the menu shadow map over the field
        # and cancelled the native LCD-off interval.  See the SCRATCH map above.
        for name, blob in (('ITEM_PAGE_SRC', ITEM_PAGE_SRC),
                           ('ITEM_REGION_SRC', ITEM_REGION_SRC),
                           ('ITEM_ROW_FAST_SRC', ITEM_ROW_FAST_SRC),
                           ('ITEM_RETURN_SRC', ITEM_RETURN_SRC),
                           ('ITEM_SHAPE_PHASE_SRC', ITEM_SHAPE_PHASE_SRC),
                           ('ITEM_TILE_FAST_SRC', ITEM_TILE_FAST_SRC),
                           ('ITEM_INDICATOR_SRC', ITEM_INDICATOR_SRC),
                           ('ITEM_PUBLISH_SRC', ITEM_PUBLISH_SRC),
                           ('ACTION_GATE_SRC', ACTION_GATE_SRC),
                           ('ACTION_ALLOC_SRC', ACTION_ALLOC_SRC),
                           ('ACTION_POP_SRC', ACTION_POP_SRC),
                           ('ACTION_BLANK_SRC', ACTION_BLANK_SRC),
                           ('FLOOR_CHROME_SRC', FLOOR_CHROME_SRC),
                           ('FLOOR_INFO_SRC', FLOOR_INFO_SRC),
                           ('FLOOR_INFO_FINISH_SRC', FLOOR_INFO_FINISH_SRC),
                           ('INFO_LIFECYCLE_SRC', INFO_LIFECYCLE_SRC),
                           ('POT_FLOOR_RETURN_SRC', POT_FLOOR_RETURN_SRC),
                           ('START_TRANSITION_SRC', START_TRANSITION_SRC),
                           ('START_FINISH_SRC', START_FINISH_SRC)):
            if '$C0D7' in blob or '$C0D8' in blob:
                raise SystemExit('menuvwf: %s references propvwf scratch $C0D7/$C0D8; '
                                 'the transaction state lives at $C1B3' % name)

        item_publish_code, item_publish_labels = gbasm.assemble(
            ITEM_PUBLISH_SRC, ITEM_PUBLISH_AT)
        item_region_code, item_region_labels = gbasm.assemble(
            ITEM_REGION_SRC, ITEM_REGION_AT)
        item_page_code, item_page_labels = gbasm.assemble(
            ITEM_PAGE_SRC, ITEM_PAGE_AT)
        item_row_fast_code, item_row_fast_labels = gbasm.assemble(
            ITEM_ROW_FAST_SRC, ITEM_ROW_FAST_AT)
        item_return_code, item_return_labels = gbasm.assemble(
            ITEM_RETURN_SRC, ITEM_RETURN_AT)
        item_shape_phase_code, item_shape_phase_labels = gbasm.assemble(
            ITEM_SHAPE_PHASE_SRC, ITEM_SHAPE_PHASE_AT)
        item_tile_fast_code, item_tile_fast_labels = gbasm.assemble(
            ITEM_TILE_FAST_SRC, ITEM_TILE_FAST_AT)
        item_indicator_code, item_indicator_labels = gbasm.assemble(
            ITEM_INDICATOR_SRC, ITEM_INDICATOR_AT)
        action_gate_code, action_gate_labels = gbasm.assemble(
            ACTION_GATE_SRC, ACTION_GATE_AT)
        action_alloc_code, action_alloc_labels = gbasm.assemble(
            ACTION_ALLOC_SRC, ACTION_ALLOC_AT)
        action_pop_code, action_pop_labels = gbasm.assemble(
            ACTION_POP_SRC, ACTION_POP_AT)
        action_blank_code, action_blank_labels = gbasm.assemble(
            ACTION_BLANK_SRC, ACTION_BLANK_AT)
        info_lifecycle_code, info_lifecycle_labels = gbasm.assemble(
            INFO_LIFECYCLE_SRC, INFO_LIFECYCLE_AT)
        pot_floor_return_code, _pot_floor_return_labels = gbasm.assemble(
            POT_FLOOR_RETURN_SRC, POT_FLOOR_RETURN_AT)
        floor_chrome_code, floor_chrome_labels = gbasm.assemble(
            FLOOR_CHROME_SRC, FLOOR_CHROME_AT)
        action_helpers = (
            ('admission gate', ACTION_GATE_BANK, ACTION_GATE_INDEX, ACTION_GATE_AT,
             ACTION_GATE_LIMIT, action_gate_code, action_gate_labels['actiongate']),
            ('private allocator', ACTION_ALLOC_BANK, ACTION_ALLOC_INDEX, ACTION_ALLOC_AT,
             ACTION_ALLOC_LIMIT, action_alloc_code, action_alloc_labels['actionalloc']),
            ('B-pop gate', ACTION_POP_BANK, ACTION_POP_INDEX, ACTION_POP_AT,
             ACTION_POP_LIMIT, action_pop_code, action_pop_labels['actionpop']),
            ('regional parent restorer', ACTION_BLANK_BANK, ACTION_BLANK_INDEX,
             ACTION_BLANK_AT,
             ACTION_BLANK_LIMIT, action_blank_code, action_blank_labels['actionblank']),
        )
        for (helper_name, helper_bank, helper_index, helper_at, helper_limit,
             helper_code, helper_entry) in action_helpers:
            if helper_at + len(helper_code) > helper_limit:
                raise SystemExit('menuvwf: Action %s needs %d bytes, only %d available'
                                 % (helper_name, len(helper_code),
                                    helper_limit - helper_at))
            if buf[_off(helper_bank, 0x4000)] != helper_bank:
                raise SystemExit('menuvwf: bank %d pool code is not installed' %
                                 helper_bank)
            helper_off = _off(helper_bank, helper_at)
            if any(b != 0xFF for b in
                   buf[helper_off:helper_off + len(helper_code)]):
                raise SystemExit('menuvwf: bank %d Action %s at $%04X is not free'
                                 % (helper_bank, helper_name, helper_at))
            helper_ix = _off(helper_bank, 0x4000) + helper_index - 1
            if bytes(buf[helper_ix:helper_ix + 2]) != b'\xff\xff':
                raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                                 % (helper_index, helper_bank))
            buf[helper_off:helper_off + len(helper_code)] = helper_code
            buf[helper_ix] = helper_entry & 0xFF
            buf[helper_ix + 1] = helper_entry >> 8

        if INFO_LIFECYCLE_AT + len(info_lifecycle_code) > INFO_LIFECYCLE_LIMIT:
            raise SystemExit('menuvwf: Item/Floor Info lifecycle needs %d bytes, only '
                             '%d available' %
                             (len(info_lifecycle_code),
                              INFO_LIFECYCLE_LIMIT - INFO_LIFECYCLE_AT))
        info_lifecycle_off = _off(ACTION_BLANK_BANK, INFO_LIFECYCLE_AT)
        if any(value != 0xFF for value in
               buf[info_lifecycle_off:
                   info_lifecycle_off + len(info_lifecycle_code)]):
            raise SystemExit('menuvwf: bank %d Item/Floor Info lifecycle at $%04X is '
                             'not free' %
                             (ACTION_BLANK_BANK, INFO_LIFECYCLE_AT))
        if INFO_LIFECYCLE_AT + len(info_lifecycle_code) > POT_FLOOR_RETURN_AT:
            raise SystemExit('menuvwf: Item/Floor Info lifecycle overlaps the fixed '
                             'Pot/Floor return leaf at $%04X' % POT_FLOOR_RETURN_AT)
        if POT_FLOOR_RETURN_AT + len(pot_floor_return_code) > INFO_LIFECYCLE_LIMIT:
            raise SystemExit('menuvwf: Pot/Floor return leaf needs %d bytes, only %d '
                             'available' %
                             (len(pot_floor_return_code),
                              INFO_LIFECYCLE_LIMIT - POT_FLOOR_RETURN_AT))
        pot_floor_return_off = _off(ACTION_BLANK_BANK, POT_FLOOR_RETURN_AT)
        if any(value != 0xFF for value in
               buf[pot_floor_return_off:
                   pot_floor_return_off + len(pot_floor_return_code)]):
            raise SystemExit('menuvwf: bank %d Pot/Floor return leaf at $%04X is not '
                             'free' %
                             (ACTION_BLANK_BANK, POT_FLOOR_RETURN_AT))
        buf[info_lifecycle_off:
            info_lifecycle_off + len(info_lifecycle_code)] = info_lifecycle_code
        buf[pot_floor_return_off:
            pot_floor_return_off + len(pot_floor_return_code)] = pot_floor_return_code
        info_entries = (
            (INFO_CONTROL_INDEX, info_lifecycle_labels['floorinfo']),
            (INFO_FINISH_INDEX, info_lifecycle_labels['floorinfofinish']),
            (INFO_POP_INDEX, info_lifecycle_labels['infopop']),
            (INFO_RETURN_INDEX, info_lifecycle_labels['inforeturn']),
        )
        for info_index, info_entry in info_entries:
            info_ix = _off(ACTION_BLANK_BANK, 0x4000) + info_index - 1
            if bytes(buf[info_ix:info_ix + 2]) != b'\xff\xff':
                raise SystemExit('menuvwf: Info far index $%02X in bank %d is already '
                                 'used' % (info_index, ACTION_BLANK_BANK))
            buf[info_ix] = info_entry & 0xFF
            buf[info_ix + 1] = info_entry >> 8

        title_cursor_ix = (_off(ACTION_ALLOC_BANK, 0x4000) +
                           TITLE_CURSOR_INDEX - 1)
        if bytes(buf[title_cursor_ix:title_cursor_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: title-cursor far index $%02X in bank %d is '
                             'already used' %
                             (TITLE_CURSOR_INDEX, ACTION_ALLOC_BANK))
        buf[title_cursor_ix] = action_alloc_labels['titlecursor'] & 0xFF
        buf[title_cursor_ix + 1] = action_alloc_labels['titlecursor'] >> 8

        if FLOOR_CHROME_AT + len(floor_chrome_code) > FLOOR_CHROME_LIMIT:
            raise SystemExit('menuvwf: standing-Floor chrome helper needs %d bytes, '
                             'only %d available' %
                             (len(floor_chrome_code),
                              FLOOR_CHROME_LIMIT - FLOOR_CHROME_AT))
        if buf[_off(FLOOR_CHROME_BANK, 0x4000)] != FLOOR_CHROME_BANK:
            raise SystemExit('menuvwf: bank %d Floor-chrome pool code is not installed' %
                             FLOOR_CHROME_BANK)
        floor_chrome_at = _off(FLOOR_CHROME_BANK, FLOOR_CHROME_AT)
        if any(value != 0xFF for value in
               buf[floor_chrome_at:floor_chrome_at + len(floor_chrome_code)]):
            raise SystemExit('menuvwf: bank %d Floor-chrome region at $%04X is not free' %
                             (FLOOR_CHROME_BANK, FLOOR_CHROME_AT))
        floor_chrome_ix = (_off(FLOOR_CHROME_BANK, 0x4000) +
                           FLOOR_CHROME_INDEX - 1)
        if bytes(buf[floor_chrome_ix:floor_chrome_ix + 2]) != b'\xff\xff':
            raise SystemExit('menuvwf: far index $%02X in bank %d is already used' %
                             (FLOOR_CHROME_INDEX, FLOOR_CHROME_BANK))
        buf[floor_chrome_at:floor_chrome_at + len(floor_chrome_code)] = floor_chrome_code
        buf[floor_chrome_ix] = floor_chrome_labels['floorchrome'] & 0xFF
        buf[floor_chrome_ix + 1] = floor_chrome_labels['floorchrome'] >> 8

        pop_hook = _off(*ACTION_POP_HOOK)
        if bytes(buf[pop_hook:pop_hook + len(ACTION_POP_OLD)]) != ACTION_POP_OLD:
            raise SystemExit('menuvwf: generic menu-pop arithmetic at 4:$%04X changed'
                             % ACTION_POP_HOOK[1])
        # Carry means the exact Action parent and menu machine state are already
        # restored. Skip the native clear + Status/Items replay and return through the
        # existing Call_004_4857 epilogue; carry-clear callers retain that replay.
        buf[pop_hook:pop_hook + len(ACTION_POP_OLD)] = bytes(
            (0xD7, ACTION_POP_INDEX, ACTION_POP_BANK,
             0x38, 0x19, 0x00, 0x00, 0x00))

        for see_hook in (POT_SEE_12_ENTRY_HOOK, POT_SEE_13_ENTRY_HOOK):
            see_off = _off(*see_hook)
            if bytes(buf[see_off:see_off + len(POT_SEE_ENTRY_OLD)]) != \
                    POT_SEE_ENTRY_OLD:
                raise SystemExit('menuvwf: Pot viewer shadow setup at 4:$%04X changed'
                                 % see_hook[1])
            buf[see_off:see_off + len(POT_SEE_ENTRY_OLD)] = bytes(
                (0xD7, INFO_RETURN_INDEX, ACTION_BLANK_BANK))

        if ITEM_REGION_AT + len(item_region_code) > ACTION_POP_AT:
            raise SystemExit('menuvwf: item regional controller overlaps Action pop gate '
                             'at bank %d:$%04X' % (ACTION_POP_BANK, ACTION_POP_AT))
        if ITEM_ROW_FAST_AT + len(item_row_fast_code) > ITEM_ROW_FAST_LIMIT:
            raise SystemExit('menuvwf: same-frame Item-row publisher needs %d bytes, '
                             'only %d available' %
                             (len(item_row_fast_code),
                              ITEM_ROW_FAST_LIMIT - ITEM_ROW_FAST_AT))
        item_row_fast_at = _off(ITEM_REGION_BANK, ITEM_ROW_FAST_AT)
        if any(value != 0xFF for value in
               buf[item_row_fast_at:item_row_fast_at + len(item_row_fast_code)]):
            raise SystemExit('menuvwf: bank %d same-frame Item-row region at $%04X '
                             'is not free' %
                             (ITEM_REGION_BANK, ITEM_ROW_FAST_AT))
        buf[item_row_fast_at:item_row_fast_at + len(item_row_fast_code)] = \
            item_row_fast_code
        if ITEM_RETURN_AT + len(item_return_code) > ITEM_SHAPE_PHASE_AT:
            raise SystemExit('menuvwf: Item redraw-tail helper overlaps shape-phase '
                             'helper at bank %d:$%04X' %
                             (ITEM_RETURN_BANK, ITEM_SHAPE_PHASE_AT))
        if ITEM_SHAPE_PHASE_AT + len(item_shape_phase_code) > ITEM_SHAPE_PHASE_LIMIT:
            raise SystemExit('menuvwf: Item shape-phase helper needs %d bytes, only %d '
                             'available' %
                             (len(item_shape_phase_code),
                              ITEM_SHAPE_PHASE_LIMIT - ITEM_SHAPE_PHASE_AT))
        item_shape_phase_at = _off(ITEM_RETURN_BANK, ITEM_SHAPE_PHASE_AT)
        if any(value != 0xFF for value in
               buf[item_shape_phase_at:
                   item_shape_phase_at + len(item_shape_phase_code)]):
            raise SystemExit('menuvwf: bank %d Item shape-phase region at $%04X is '
                             'not free' %
                             (ITEM_RETURN_BANK, ITEM_SHAPE_PHASE_AT))
        buf[item_shape_phase_at:
            item_shape_phase_at + len(item_shape_phase_code)] = item_shape_phase_code
        if ITEM_TILE_FAST_AT + len(item_tile_fast_code) > ITEM_TILE_FAST_LIMIT:
            raise SystemExit('menuvwf: same-frame Item-tile publisher needs %d bytes, '
                             'only %d available' %
                             (len(item_tile_fast_code),
                              ITEM_TILE_FAST_LIMIT - ITEM_TILE_FAST_AT))
        item_tile_fast_at = _off(ITEM_TILE_FAST_BANK, ITEM_TILE_FAST_AT)
        if any(value != 0xFF for value in
               buf[item_tile_fast_at:item_tile_fast_at + len(item_tile_fast_code)]):
            raise SystemExit('menuvwf: bank %d same-frame Item-tile region at $%04X '
                             'is not free' %
                             (ITEM_TILE_FAST_BANK, ITEM_TILE_FAST_AT))
        buf[item_tile_fast_at:item_tile_fast_at + len(item_tile_fast_code)] = \
            item_tile_fast_code
        if ITEM_INDICATOR_AT + len(item_indicator_code) > ITEM_INDICATOR_LIMIT:
            raise SystemExit('menuvwf: Item indicator publisher needs %d bytes, only %d '
                             'available' %
                             (len(item_indicator_code),
                              ITEM_INDICATOR_LIMIT - ITEM_INDICATOR_AT))
        item_indicator_at = _off(ITEM_TILE_FAST_BANK, ITEM_INDICATOR_AT)
        if any(value != 0xFF for value in
               buf[item_indicator_at:item_indicator_at + len(item_indicator_code)]):
            raise SystemExit('menuvwf: bank %d Item indicator region at $%04X is not free'
                             % (ITEM_TILE_FAST_BANK, ITEM_INDICATOR_AT))
        buf[item_indicator_at:item_indicator_at + len(item_indicator_code)] = \
            item_indicator_code
        item_helpers = (
            ('publisher', ITEM_PUBLISH_BANK, ITEM_PUBLISH_INDEX, ITEM_PUBLISH_AT,
             ITEM_PUBLISH_LIMIT, item_publish_code, item_publish_labels['publishmap']),
            ('regional controller', ITEM_REGION_BANK, ITEM_REGION_INDEX, ITEM_REGION_AT,
             ITEM_REGION_LIMIT, item_region_code, item_region_labels['itemregion']),
            ('fallback controller', ITEM_PAGE_BANK, ITEM_PAGE_INDEX, ITEM_PAGE_AT,
             ITEM_PAGE_LIMIT, item_page_code, item_page_labels['itempage']),
            ('return publisher', ITEM_RETURN_BANK, ITEM_RETURN_INDEX, ITEM_RETURN_AT,
             ITEM_RETURN_LIMIT, item_return_code, item_return_labels['itemservice']),
        )
        for (helper_name, helper_bank, helper_index, helper_at, helper_limit,
             helper_code, helper_entry) in item_helpers:
            if helper_at + len(helper_code) > helper_limit:
                raise SystemExit('menuvwf: item-page %s needs %d bytes, only %d available'
                                 % (helper_name, len(helper_code),
                                    helper_limit - helper_at))
            if buf[_off(helper_bank, 0x4000)] != helper_bank:
                raise SystemExit('menuvwf: bank %d pool code is not installed' %
                                 helper_bank)
            helper_off = _off(helper_bank, helper_at)
            if any(b != 0xFF for b in
                   buf[helper_off:helper_off + len(helper_code)]):
                raise SystemExit('menuvwf: bank %d item-page %s at $%04X is not free'
                                 % (helper_bank, helper_name, helper_at))
            helper_ix = _off(helper_bank, 0x4000) + helper_index - 1
            if bytes(buf[helper_ix:helper_ix + 2]) != b'\xff\xff':
                raise SystemExit('menuvwf: far index $%02X in bank %d is already used'
                                 % (helper_index, helper_bank))
            buf[helper_off:helper_off + len(helper_code)] = helper_code
            buf[helper_ix] = helper_entry & 0xFF
            buf[helper_ix + 1] = helper_entry >> 8

        return_hook = _off(*ITEM_RETURN_HOOK)
        if bytes(buf[return_hook:return_hook + len(ITEM_RETURN_OLD)]) != ITEM_RETURN_OLD:
            raise SystemExit('menuvwf: redraw-tail publisher at 4:$%04X changed' %
                             ITEM_RETURN_HOOK[1])
        buf[return_hook:return_hook + len(ITEM_RETURN_OLD)] = bytes(
            (0xF5, 0x3E, 0x01, 0xD7, ITEM_RETURN_INDEX, ITEM_RETURN_BANK,
             0x38, 0x02, 0xF1, 0xC9, 0xF1, 0xE1, 0xC3, 0x54, 0x48))

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
                # Keep cursor cells independently writable. Box 8 has no leading zero,
                # but its real flow replaces the first letter after the drawer returns,
                # so bit 5 preserves it. Box 17 deliberately composes all of `Pot`:
                # Status rendering can repaint fixed tile $1A before this screen opens.
                # Box 14's apparent overwrite exists
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
                             'at %d:$%04X; row pools are 9+11+8 tiles'
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
        x, y, w, fl = desc(GROUND_POPUP_BOX)
        if (x, y, w, fl) != (3, 4, GROUND_POPUP_WIDTH, 0):
            raise SystemExit('menuvwf: ground-command box descriptor no longer matches '
                             'the proportional popup allowlist')
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
        debug_categories = (desc(33), desc(34))
        if debug_categories != ((0, 0, 6, 0x50), (0, 0, 6, 0x50)):
            raise SystemExit('menuvwf: hidden debug category pages no longer share one '
                             'six-cell border geometry: %s' % (debug_categories,))
    if notes is not None:
        if proportional:
            notes.append('menuvwf: main/item/Floor-header/action/help/seal/condition '
                         'and standing stair/trap rows use approved %s advances, '
                         'painted extents, and shared 8-shift tables' % font.name)
            notes.append('menuvwf: native fusion-count suffixes $%02X-$%02X use a '
                         '%d-byte residue shifter at %d:$%04X and %d-byte glyph/data '
                         'helper at %d:$%04X'
                         % (FUSED_FIRST, FUSED_LAST, len(fused_code), FUSED_BANK, FUSED_AT,
                            len(fused_data), FUSED_DATA_BANK, FUSED_DATA_AT))
            notes.append('menuvwf: %d-byte shop-price suffix helper at %d:$%04X keeps '
                         'five raw $D0-$DE row slots outside the proportional pen; '
                         'shop staging widened from %d to %d pre-price cells'
                         % (len(shop_suffix), SHOP_SUFFIX_BANK, SHOP_SUFFIX_AT,
                          SHOP_OLD_CONTENT_CELLS, SHOP_CONTENT_CELLS))
            notes.append('menuvwf: %d-byte shop-label stager at %d:$%04X, %d-byte '
                         'VBlank uploader at %d:$%04X, and %d-byte value-row shape '
                         'gate at %d:$%04X keep Price/G and both shop amounts '
                         'independent of borrowed native font planes'
                         % (len(shop_label_code), SHOP_LABEL_BANK, SHOP_LABEL_AT,
                            len(shop_upload_code), SHOP_UPLOAD_BANK, SHOP_UPLOAD_AT,
                            len(shop_shape_code), SHOP_SHAPE_BANK, SHOP_SHAPE_AT))
            notes.append('menuvwf: %d-byte hidden debug-menu shape helper at %d:$%04X; '
                         'category pages, selected item rows, and enhancement values '
                         '0..99 stay proportional'
                         % (len(debug_menu_code), DEBUG_MENU_BANK, DEBUG_MENU_AT))
            if CONTEXT_STATIC_ROWS:
                notes.append('menuvwf: title/file shapes use %d-byte helper at '
                             '33:$%04X; context-static start rows enabled'
                             % (len(start_code), START_AUX_AT))
            else:
                notes.append('menuvwf: title and Log-selector rows use the keyed VWF '
                             'allocator; summary/confirm/Rank+Pass/difficulty rows use '
                             'fixed-cell fallback')
            notes.append('menuvwf: generated Pass selector terminates each English Log '
                         'row independently; two- and three-log forms stay inside the '
                         'title transaction')
            notes.append('menuvwf: %d+%d+%d-byte item-page regional/fallback/publisher '
                         'helpers in bank %d; screen-1 paging/Start-sort is old -> normal '
                         'left borders + blank status/cursor/name cells -> '
                         'one complete body with LCD on; %d-byte body, %d-byte tile, and '
                         '%d-byte redraw-tail and %d-byte early-indicator helpers remove '
                         'redundant waits and settle the page/dot together'
                         % (len(item_region_code), len(item_page_code),
                            len(item_publish_code), ITEM_REGION_BANK,
                            len(item_row_fast_code), len(item_tile_fast_code),
                            len(item_return_code), len(item_indicator_code)))
            notes.append('menuvwf: carried-/settled-Floor screen-2 Action uses six private four-tile '
                         '$C7-$DE slices after a %d-byte live-layer gate; the unique '
                         'seventh Info row uses the collision-safe ordinary base run; B-cancel uses '
                         '%d-byte pop proof plus a %d-byte box-6 parent/machine-state '
                         'restorer and returns to screen-1 input without redundant replay'
                         % (len(action_gate_code), len(action_pop_code),
                            len(action_blank_code)))
            notes.append('menuvwf: %d-byte standing-item Floor chrome helper at '
                         '%d:$%04X commits the complete one- or five-row incoming box '
                         'before text publication' %
                         (len(floor_chrome_code), FLOOR_CHROME_BANK,
                          FLOOR_CHROME_AT))
            notes.append('menuvwf: %d+%d-byte Floor/Info ABI stubs at '
                         '%d:$%04X + %d:$%04X dispatch a %d-byte exact '
                         'screen-1/screen-7/screen-20 '
                         'Info/seal regional lifecycle at %d:$%04X; exact carried, '
                         'Items-appended Floor, screen-7, and screen-20 Pot `See` '
                         'entries plus their admitted returns use the same regional arena and rejected '
                         'callers retain the LCD-off full-map fallback'
                         % (len(floor_info_code), len(floor_finish_code),
                            FLOOR_INFO_BANK, FLOOR_INFO_AT,
                            FLOOR_INFO_FINISH_BANK, FLOOR_INFO_FINISH_AT,
                            len(info_lifecycle_code), ACTION_BLANK_BANK,
                            INFO_LIFECYCLE_AT))
            notes.append('menuvwf: %d+%d-byte title/file transition at '
                         '%d:$%04X + %d:$%04X; layered title, Log, difficulty and '
                         'Rank/Pass redraws publish one complete shadow map'
                         % (len(start_transition_code), len(start_finish_code),
                            START_TRANSITION_BANK, START_TRANSITION_AT,
                            START_FINISH_BANK, START_FINISH_AT))
            pool = '$43-$7B + $8B-$95 + $9A-$9D (72 usable; isolated $87 unused)'
        else:
            notes.append('menuvwf: item-list rows composed at uniform 6px')
            pool = '$43-$7B'
        cap = ('18-source-char menu/item + 21-source-char help/seal/condition guards'
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
