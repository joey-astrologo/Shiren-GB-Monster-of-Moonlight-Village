# VWF EVERYWHERE — the menu renderer, and every other screen the composer's VWF never touched

> **Archived:** completed implementation record. See the repository
> [README](../../README.md) and [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

> ## CURRENT 2026-08-12 — RANKINGS OWNERSHIP COMPLETE; VISUALLY APPROVED
>
> Rankings remains proportional in this one-VRAM-bank, non-CGB/SGB ROM. Its settled board
> now owns one unified `$80-$A6` allocation: 14 deduplicated heading/difficulty tiles plus
> five five-tile names. The category selectors borrow `$C0-$CB` only while visible, then
> the native menu-font loader restores `$00-$D2` before Rankings, title or Adventure maps
> reveal those planes. LCD-on title Rankings retains queued 4+4+1 uploads; LCD-off rescued-
> child results retain synchronous direct copies.
>
> The rewritten `tools/orochisymbolspill.py` requires a native control and checks the real
> `$CB/$CD/$CC/$CE` badge, complete Kuyo/Village boards, native status/OAM and repeated
> returns. It fails the frozen known-bad SHA-256
> `b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`
> and passes the final normal RC, SHA-256
> `b5b45c3c95a3ff1305d36c0fbf1b538097f5fae7f3a5cf01146ac67ddb3a260f`.
> Shuffled and redirect-all builds also pass at
> `c9842fec9c9ff02e2a9eb24eab5ecf64f5c2dda7cfc55c3776a93de48c628be1` and
> `7b8153b7d19a7e578f77fd872cbd7dd2039708599c79b9d592fb2b9ffa80591f`.
> Joey completed and approved the exact Kuyo/repeat/Village Exit route in Mesen; see
> `HANDOFF_RANKVWF.md`.

> ## CURRENT 2026-08-11 — SAVE-SUMMARY LOCATION ROWS CLOSED
>
> The three supplied Log-1 variants now render as proportional `Dragon's Maw`,
> `19F Dragon's Maw`, and `5F Koma Cave`, with the difficulty row intact. Bank 4's native
> producer reserved four prefix cells even when there was no floor number, while a long
> numbered place spilled past the legacy 14-cell row and placed `aw` ahead of row 2.
> The context helper removes only the numberless indent, preserves complete overflow in
> private staging, clears the original spill, and restores both the native BC and saved
> source pointer before row 2. The static summary pool is now 9+10+8 tiles at `$DE-$F8`.
> `tools/savesummaryspill.py` checks the exact payload, shadow, both planes and following
> `Hard` row for all three SRAMs. Full `sh build.sh` is green; current ROM SHA-256 is
> `e13cbaedc24ea23d995429be9a7ce161e2fa7814951536ec0545ed2bb7905e3f`.

> ## CURRENT 2026-08-10 — FIXED-CELL NAME GRID CLEANUP COMPLETE
>
> The name keyboard remains intentionally fixed-cell, but its five rows now fill all 75
> selectable positions without gaps: A-Y in the left block, Z/a-x in the middle, then
> y-z, 13 punctuation marks and 0-9 in the right. Box 13 remains aliased to box 12 and its
> bank-31 free run remains intact. Because the picker reads one raw ROM byte while the box
> drawer can expand DTE, box 12 is explicitly non-compressible. Normal and shuffled
> `gridprobe` runs pass every row through both internal page branches; fresh/rename/save,
> `newgamesmoke` and the fixed-cell control comparison are also green. Current ROM SHA-256:
> `0df21e78f009363787c327851035a19ff9f643b0b8ce305574cf736a52edf2d5`.
> The saved Copy -> Erase -> New Log transition also restores native `$89/$9E-$A0`
> before name entry, preventing the outgoing `Log of Shiren` / `Erase this?` fragments
> from replacing the name underline or `() :` keys. `nameflowspill.py` permanently covers
> that exact route on normal and shuffled builds.

> ## CURRENT 2026-08-10 — V4E MAIN-MENU TRANSITIONS COMPLETE
>
> Commit `393a543` closes the layered title/file-menu redraw defects and the previously
> scheduled V4E scope. The saved Log-3 route proved that difficulty explanations at
> `$67-$7A` overwrote
> live Rename/Rank+Pass/Replay/Log-selector glyphs; they now use the isolated `$E0-$F3`
> slice. Title, Log selector, summary, confirmation, difficulty and Rank/Pass redraws are
> one LCD-off transaction and publish a complete 20x18 shadow map, so no intermediate box
> labels or stale VWF planes can appear.
>
> Rankings cannot disable the LCD while its native fixed fields use the VBlank queue. The
> title path therefore clears the otherwise-unused `$9C00` map; Rankings displays that
> blank page while rebuilding `$9800`, then the authoritative page return drains the queue
> and publishes the finished board at VBlank. Fay's task screen similarly stays LCD-off
> while all ten borrowed native/VWF tiles and its composite boxes are rebuilt. The visible
> label is now the official `Fay's Puzzles`; its 13 source glyphs compose into eight tiles
> inside the existing title box.
>
> `tools/mainmenuspill.py` boots `saves/shiren_en_path_select.srm`, exercises the real
> Log-3 difficulty and four-record Rankings routes, checks rendered transition frames,
> persistent title/selector map owners and every owned tile plane. Normal, shuffled and
> redirect-all builds report 24 white title/difficulty frames, seven hidden Rankings
> frames and zero problems. `startspill`, `rankspill` and the full saved-route
> `structspill` battery also pass on all three layouts. Current ROM SHA-256 is
> `0df21e78f009363787c327851035a19ff9f643b0b8ce305574cf736a52edf2d5`.

> ## CURRENT 2026-08-10 — V4F COMPLETE AND VISUALLY APPROVED
>
> `vwf-item-menu` replaces the earlier partial name-field blank/publish guard. Exact item
> row 0 disables the LCD at VBlank; all five item rows and the following `Items` header
> compose while the screen is white; header completion publishes the complete 20x18
> shadow map and restores the LCD. The short final page pre-stages its empty fifth row and
> takes the same completion path. Cursor and page-arrow sprites remain native and appear
> after complete text, with the row-0 cursor verified at `$C382`.
>
> `itempagespill.py` boots `saves/shiren_en_item_menu.srm`, captures initial entry plus
> five Right/Left transitions, requires four unique pages, an LCD-off interval, restored
> cursor and no rendered frame except outgoing/white/complete incoming text. The pre-fix
> ROM fails all six; normal, shuffled and redirect-all V4F builds pass all six. The normal
> route measures 4-5 white frames per transition. The helper
> is 163 bytes at 37:$405A-$40FC, after that bank's pool reader and before text at $4100;
> install-time free-space/far-index and exact box-14 geometry checks guard the placement.
> Joey approved the white-flash transition in emulator on 2026-08-10. His approval
> screenshot exposed an older box-14 split-renderer defect: a fixed-width `I` followed by
> proportional `tems`. The raw first-cell exception came only from synthetic forced screen
> 1, not a real item-menu lifetime, so box 14 now composes the complete word; real
> `Which?`/`Pot` cursor exceptions retain their raw cell. Joey approved the corrected
> `Items` spacing.
>
> `floorinfospill.py` boots `saves/shiren_en_item_menu_wood_arrow.srm` and checks the three
> additional Floor transitions Joey reported: action -> Info page 1, page 1 -> page 2,
> and page 2 -> action. The old ROM exposes mixed text on all three. The new controller at
> 39:$405A and finalizer at 40:$4060 keep each redraw LCD-off until one complete shadow map
> contains the help/action rows, borders, arrow and page counter. The shared full-map
> publisher is bank 37 far index 7; the native action cursor follows the publish normally.
> Normal, shuffled and redirect-all builds pass with 5/5/8 LCD-off frames and zero blended
> frames. The 48-run normal/shuffled dungeon/town crash sweep is also green. Joey tested
> that exact Wood Arrow route in emulator and approved it as perfect on 2026-08-10.
>
> Inventory paging, the `Items` header and Floor/Info are closed. A follow-up fixed-cell
> status polish expands `Nrm` to `Normal` and sets the Easy/Normal/Hard leading padding to
> 6/4/6, right-aligning all three through column 18. `pathspill.py` boots the supplied
> Path fixture's active **Log 2**, selects all three choices through the real sign and
> verifies the exact shadow/BG-map field and untouched column-19 border on normal,
> shuffled and redirect-all builds. Current ROM SHA-256 is
> `92db1e18d9318a2a9ac569b2c11b69ce769fefa56f630354e24fe3d85478f1c1`.

> ## CURRENT 2026-08-09 — DOT VWF BUDGET RESET IMPLEMENTED AND BATTERY-GREEN
>
> The final baseline is **Dot Gothic Shiren**, derived from MxAshlynn's
> `dot_gothic_8x8-variable` (OFL 1.1). The downloaded source PNG remains untouched; the
> exact approved delta is frozen in `assets/fonts/dot_gothic_shiren.json` against source
> SHA-256 `f057acf691ba24f7cb4beaeaf2e69b69d96868a9e6be8d2586fbdd82006152f7`:
>
> * lowercase `e`: delete pixel (4,5), add pixel (3,4), advance 6→5 (**e clear**);
> * spacing only: `D` 6→5, `t` 6→5, `/` 8→7; each retains one blank column after ink;
> * compact `+`: remove one pixel from each of its four arms and reduce advance 6→4;
> * compact `-`: remove one pixel from each end and reduce advance 5→4;
> * compact `4`: approved four-column form, advance 7→5;
> * compact HUD-style `7`: four-column form with a top-right corner and straight lower
>   leg, advance 7→5.
>
> **Playtest closure added later the same day:** dispatcher screen 20's Ground header is
> box 5 (`x0,y0,one row,w18,$C616`) and has one raw prefix cell. Bit 5 now selects the
> proportional item path for that exact descriptor; no other box shares the shape.
> An earlier synthetic test incorrectly injected two zeros and therefore did not test the
> live format. `groundspill.py` boots `saves/shiren_en_ground.srm`, opens the real screen,
> requires the staged `00 Iron Shield FF`, and verifies the one-cell allocator and visible
> Dot planes. `menuspill` keeps a corrected `Accurate Sword+99` component fixture, while
> `menuromspill` treats its marker separately from the one-cell raw-prefix ROM boxes
> 8/14/17. This is the top item-name box shown after standing on an item and choosing
> **Ground**.
>
> The same measurement found `4` and `7` are the widest digits (7px advance each versus
> 5px for `9`), so `+44`/`+77` were wider than `+99`. Joey approved their one-column
> redraw and the compact minus on 2026-08-09; `fontbakeoff.py --approved-dot
> --digit-review` reproduces the source/approved comparison.
>
> `tools/dotfont.py` is the deterministic source loader. It verifies that hash, parses
> GB Studio's magenta advances, applies only the approved edits, and rejects malformed
> glyphs or ink outside an advance. `tools/fontbakeoff.py` and `tools/fontaudit.py`
> enumerate every signed equipment value and `[NN]` counter rather than assuming `99` is
> widest. The exact hostile five-row page (representative `Accurate Sword-99` plus four
> 11-tile `[77]` rows) and `Remove/Toss/Drop/Info` consume **71/72 tiles**, packable into usable runs
> `57+11+4`.
> The isolated `$87` tile cannot satisfy the minimum four-tile queue footprint.
>
> `tools/fontaudit.py` now measures the whole translated corpus in physical pixels using
> ROM-derived geometry and reports **0 unproven translated classes**. The last eight place
> labels are selected at `4:$6941-$698B`, staged at `$C62D`, and drawn in save-summary box
> 26. The bare `Dragon's Maw` label is widest at 63 painted pixels / 64px advance; the
> complete numbered location row has a separate ten-tile allocation as documented above.
> Dialogue uses 30 source glyphs / 144px, item rows 17 / 128px including suffix, and
> item-help, seals, and clear-condition rows 21 / 144px. Unknown `<var>/<cE3>` producers
> still produce labelled legacy-reservation warnings, not false glossary limits.
>
> Reproduce the font gate with:
>
>     PYTHONDONTWRITEBYTECODE=1 python3 tools/dotfont.py
>     PYTHONDONTWRITEBYTECODE=1 python3 tools/fontaudit.py
>     PYTHONDONTWRITEBYTECODE=1 python3 tools/fontbakeoff.py \
>         "font candidates/dot_gothic_8x8-variable.png" --approved-dot \
>         --output build/font_approved_dot_gothic_shiren.png
>
> **The proportional composer is now real ROM/emulator evidence.** `build.py --dot-font`
> installs `tools/propvwf.py`; `build.sh` now makes it the default `build/shiren_en.gb`.
> A direct build without `--dot-font` remains the measured uniform-6px control. Dot
> stages up to 30 source glyphs on the measured 144px canvas, carries a glyph that crosses
> the 72px queue boundary, prepares the split 30-entry character→tile reveal map at the end
> of pass 2 without touching live `$C0FE/$C0FF`, and falls back to native
> 8px for seven untranslated lines. Every English literal uses a measured fast path; the
> copied native scanner remains the control-code path and is byte-asserted before install.
>
> Exact shipping commands and evidence (2026-08-09):
>
>     python3 tools/build.py build/_base_expanded.gb script/en.tsv \
>         build/shiren_en.gb --dot-font
>     python3 tools/propvwf.py --selftest
>     python3 tools/proptiming.py build/shiren_en.gb --frames 3000 --seeds 4
>     python3 tools/propupload.py build/shiren_en.gb --frames 3000 --seeds 4
>     python3 tools/boxspill.py build/shiren_en.gb
>     python3 tools/menuspill.py build/shiren_en.gb
>     python3 tools/menuspill.py build/shiren_en.gb --long
>     python3 tools/menuspill.py build/shiren_en.gb \
>         --ram saves/shiren_en_menu.srm
>     python3 tools/menuspill.py build/shiren_en.gb --help-seals
>     python3 tools/conditionspill.py build/shiren_en.gb \
>         --png-dir build/conditionspill
>     python3 tools/menuromcensus.py build/menurom_control.gb \
>         --ram saves/shiren_en_menu.srm
>     python3 tools/menuromspill.py build/shiren_en.gb \
>         --ram saves/shiren_en_menu.srm
>     python3 tools/build.py build/_base_expanded.gb script/en.tsv \
>         build/orochisymbolspill_native_control.gb --dot-font --no-menuvwf
>     python3 tools/build.py build/_base_expanded.gb script/en.tsv \
>         build/rankvwf_control.gb --dot-font --no-rankvwf
>     python3 tools/rankspill.py build/shiren_en.gb \
>         --control build/rankvwf_control.gb \
>         --native-control build/orochisymbolspill_native_control.gb \
>         --png build/rankvwf_stress.png
>     python3 tools/orochisymbolspill.py build/shiren_en.gb \
>         --native-control build/orochisymbolspill_native_control.gb
>     python3 tools/startspill.py build/shiren_en.gb \
>         --ram saves/shiren_en_menu.srm \
>         --wide-ram saves/shiren_en_ranking_repaired.srm
>     python3 tools/newgamesmoke.py build/shiren_en.gb
>     python3 tools/rescuespill.py build/shiren_en.gb
>
> Current composer selftest: 1,257 plane-exact line cases / 60,426 checks, including every
> admitted dialogue glyph at every shift residue. Timing peaks are 153/154 scanlines for
> a full renderer pass and 93/154 for reveal-map work, with no
> unfinished pass. `proptiming` gates the real
> execution budget rather than start-frame alignment. Every completed `$C006` payload
> reached `0:$11A8/$11C5` byte-exact; 0 spills in 20,320 live text frames. The preceding
> current build and a `--shuffle` build each passed 12 dungeon + 12 town crash seeds,
> composer timing/upload/spill checks, hostile allocation, and both supplied-save routes.
> Clear-condition
> pages pass 10/10 plane-exact real/synthetic row checks; the widest current five consume
> 56/57 primary-run tiles. The current ROM SHA-256 is
> `97f06a39cf058523b09b6eb0dfd5946f7949618e48273169880ae56f02852e83`. Fresh screen evidence is
> in `build/dotpilot_finalshots/` and `build/dotpilot_typewriter/`; the f30/f45/f60/f75
> sequence verifies the proportional typewriter while the text is still appearing.
>
> **MAIN / ITEM / ACTION PROPORTIONAL VWF LANDED 2026-08-07.** `--dot-font` installs the
> proportional `menuvwf` build at `32:$7740`. The shared pre-shift table now retains the
> native `$88` unidentified star as well as `$8A` plating; its width table is packed rather
> than page-padded. The bank-32 image ends at `$7FD6`, leaving 42 tail bytes; start-flow
> classification/allocation helpers live in
> explicitly reserved code arenas in banks 33-36.
> The descriptor-shape allowlist covers main box 0, item boxes 4/15, and action boxes
> 6/39; install-time assertions bind those IDs to the geometry duplicated in the far
> routine. `Remove` is proportional on Joey's equipped weapon page.
>
> The allocator uses three census-proven contiguous runs: `$43-$7B` (57), `$8B-$95`
> (11), and `$9A-$9D` (4). **The old policy tied item row 0 to the 11-tile run. Joey's
> 2026-08-09 sorted/page-two screenshot falsified that:** the then-12-tile
> `Accurate Sword+99`
> fell back only at the top of a page, and its final `9` spilled into row 1. The first
> item row whose cap actually fits now uses the 11-run; a 12-16-tile row uses base
> regardless of page position. With Joey's final compact 4/7, the hostile bounded page is
> five 11-tile names plus four 4-tile verbs = **71/72 usable tiles**. `menuspill --long` proves nine
> non-overlapping records, every slice wholly inside one run, every VRAM plane byte-exact,
> and the exact row-0 regression string fully proportional.
>
> The first integrated run exposed a signed-tile trap: BG IDs `$80-$FF` select
> `$8800-$8FF0`, but both renderer and verifier initially used linear `$9000+16*n`
> addressing. The screen showed resident `012345...` glyphs in row 0. `vdest` and the
> verifier now use signed addressing; the photographed and plane-exact rerun is green.
>
> **Page flips no longer show mixed old/new names.** Reusing slices made new pixels
> visible through the old tilemap for 5-13 frames. The first landed name-field blanker
> still exposed reused pixels and progressively published rows; Joey asked to revisit the
> full white-flash version. V4F now disables the LCD at a fresh VBlank on exact item row
> 0, composes the five rows plus header, publishes the complete 20x18 shadow map, and
> enables the LCD. The short final page takes the same boundary through a pre-staged empty
> row 4. `itempagespill` proves six real transitions are `old -> white -> complete new`;
> the native cursor/page arrows appear only after complete text.
>
> A shared-WRAM trap was resolved during integration: propvwf uses `$C0D7/$C0D8`
> ephemerally, while the old menu renderer kept allocator state there persistently. The
> Dot menu build moves persistent state to `$C1AE-$C1B2` (three run watermarks, shape kind,
> record count) in the proven record-table run and uses 15 records instead of 16; the
> measured stacked maximum is 13. This prevents a composer call during a live menu
> session from silently corrupting allocator state.
>
> **ITEM INFORMATION / SEALS LANDED 2026-08-07.** Boxes 7/19 are the same measured
> `x0,y3,w18,flags0` shape and stage rows directly at `$C616`, with ZERO raw prefix cells.
> Their path accepts 21 characters and up to 16 physical tiles. A 14-16-tile row gets a
> 16-tile allocator cap and uses two overlapping pens: upload tiles 0-8, retain tile 8,
> then resume at that exact pixel boundary and upload tiles 8-15. This claims no new WRAM
> and preserves glyphs crossing the boundary. `menuspill --help-seals` forces a real help
> page, all five groups covering the 20 equipment seals, a synthetic 16-`W` row, and a
> synthetic 21-`i` row. Result: **120 plane-exact row checks**, zero invariant frames,
> zero problems, covering both the real LCD-off direct path and a forced LCD-on VBlank
> queue path. The English item-information title's raw `$7D` delimiters normalize to the
> approved Dot hyphen, so its item name composes too; title fixtures containing native
> kana still take the byte-exact raw fallback.
> `dialogue_preview`/`build.py` still hold the shared TSV to 18 characters so the same
> translations remain safe in the fixed-width control; 21 is tested renderer headroom.
>
> Install-time geometry assertions include boxes 7/19 as well as 0, 4/15, and 6/39.
>
> **ROM-SOURCED MENU ROWS LANDED 2026-08-07.** `tools/menuromcensus.py` hooks the untouched
> `31:$40D8` drawer in a fresh `--dot-font --no-menuvwf` control. Ordinary play, Joey's
> save, all 35 forced dispatcher entries, category page two, and the blank-cart difficulty
> route observed **55 distinct ROM rows in 23 box IDs**. The completed path marks 19 safe
> boxes: `1 8 9 14 16 17 24 28 29 32 33 34 38 41 46 47 48 50 51`.
>
> Bank 32 reads their bank-31 sources through the ROM's own nested `rst $10` far call.
> Index `$03` in bank 31 now reaches a 16-byte gate at `31:$459E`: `$FE/$FF` read one byte
> through HL/BC, while every ordinary value jumps to the original box routine at `$403F`.
> `build.py` reserves that exact range before repacking bank 31. No bank-0 bytes or WRAM
> staging were needed.
>
> These rows use the context-scoped `$CA-$DD` pool, separate from the hostile item/action
> allocator. Static partitions are 16 for one row, `8+12`, `4+8+8`, or `5+4+4+4+3` for
> the category pages. `menuromcensus.py` now keeps both the drawer-epilogue shadow and an
> end-of-frame snapshot for **every call**; it does not hide a mutated draw behind an
> identical unmutated signature. That measured the first-cell policy precisely: leading
> zero cursor slots remain raw, and descriptor bit 5 preserves a nonzero first cell only
> for boxes 8 and 17 (`Which?`, `Pot`). Box 14's apparent first-cell overwrite occurs only
> in synthetic forced screen 1, not in an ordinary item-menu lifetime; preserving it made
> `Items` render as a fixed-width `I` plus proportional `tems`. It now composes the whole
> word. `Gitan`, `Floor`, `Path` (renamed from `Mode`), `No more names.`,
> `No passwords.`, and `Rankings` receive no visible first-cell mutation and now compose
> from their first letter. The apparent status-label mutation at ordinary frame 422 is the
> whole box being cleared during teardown, after it stops being the displayed owner.
> `tools/menuromspill.py` checks source advancement, complete shadow rows, both VRAM
> planes, pool ownership on every live frame, and simultaneous-box residency. Final
> result: **76 epilogue-exact row checks and 5,095 live-frame plane checks, zero problems**,
> on both normal and shuffled builds. It caught and prevented the first prototype's
> box-30/32 and box-29/46 tile reuse, the missing `$80` question-mark ink extent, and a
> fall-through from the WRAM allocator into the ROM allocator.
>
> Three groups deliberately remain raw: box 2 (`Weapon | Str` / `Shield | Exp`) and box 30
> (`No … Rating`) receive later fixed-cell insertions; boxes 12/13 are the Japanese
> name-entry grid. The shape shared by box 25 is admitted only when its staged payload is
> exactly `Log 1`-`Log 3`; the unrelated over-dialogue picker still stays raw because it
> does not own the menu-font arena.
>
> **RANKINGS LIST VWF LANDED 2026-08-07; SCREEN OWNERSHIP REPAIRED 2026-08-12.**
> The old “bank-15 renderer” label was wrong:
> bank 15 stores/builds the 12-byte records, but the live five-row drawer is in bank 31.
> `31:$4A4B` stages exactly six name bytes at `$C6E3`; its call at `31:$4A58` now far-calls
> `tools/rankvwf.py` in bank 32. Scores, floor, count, icons, and every other fixed cell
> remain on the original renderer.
>
> The screen manager owns `$80-$A6` for the complete settled board. Five tiles hold the
> heading, three each hold deduplicated `Easy`, `Norm.` and `Hard`, and `$8E-$A6` holds
> five five-tile names: 39 tiles total. The game's established `$C006` VBlank consumer
> still transfers 4+4+1 tiles, now through overlapping destination windows that publish
> exactly five name IDs. The real title-screen route reaches the drawer with LCDC on and
> arms that queue; LCD-off rescued-child results synchronously copy the same five-tile
> rows without waiting for a disabled consumer.
>
> Kuyo and Village Exit selectors use a separate temporary phase at `$C0-$CB`. Before a
> board or adjacent title/Adventure map is shown, the bank-13 native menu-font loader
> restores `$00-$D2` while the destination remains hidden. Consequently live native board
> assets such as `$B7` and `$CB-$D2` stay disjoint from the settled VWF allocation, and
> borrowed Orochi planes are exact before their map IDs reappear. No CGB bank or secondary
> permanent pool exists.
>
> `$80-$A6` overlaps native kana, so eligibility is a WHOLE-PAGE decision. All five
> records must contain only the approved name-picker page; one kana/dakuten record makes
> all five calls delegate through the original `31:$4A5F`. Stored `$AF` (`~`) is staged
> natively as `$5C $7A`; the proportional path collapses that measured pair back to the
> approved Dot `~` rather than indexing `$5C` as an English glyph.
>
> `tools/rankspill.py` drives the real title-menu Rank route and substitutes bounded
> fixtures only when `31:$4662` begins the page. `Shiren`, `WWWWWW`, `iiiiii`, `Abcdef`,
> and `+-[]?~` pass **25 private name tiles plane-exact, 5/5 byte-exact VBlank transfers,
> zero unowned pool references, and fixed cells equal to `--no-rankvwf`**. Legacy page 0
> and nonzero page 1 each take the original writer 5/5 and match the complete visible board
> against a `--no-menuvwf` native control. The page-1 fixture proves prevalidation starts
> at `C6AC * 12` and catches the unsupported code in its fifth selected row. Normal,
> shuffled and redirect-all builds pass. Evidence: `build/rankvwf_stress.png`.
>
> The old pool had been moved from `$43-$6A` to `$80-$A7` after an incorrect diagnosis of
> the supplied cleared-Orochi save. The replacement `orochisymbolspill.py` now checks the
> real badge, every complete board region, native status/OAM and repeated returns against
> a `--no-menuvwf` control. It fails the frozen bad ROM and passes normal, shuffled and
> redirect-all repaired builds. Joey's repeated manual Mesen route also passes.
>
> **TITLE / FILE / DIFFICULTY FLOW LANDED 2026-08-08, INCLUDING THE TWO PLAYER-FOUND
> V1 GAPS.** A blank-cart and saved-cart census
> measured the real title routes instead of inferring them from forced dispatches. The
> proportional path now covers title box 23 (3-8 dynamic rows), the exact `Log 1`-`Log 3`
> payload of the shared box-25/49 shape, three-row save summaries in box 26, the two-row
> Log 1 erase confirmation in box 27, and difficulty explanations 46/48/50. The lower
> Easy, Normal, and Hard explanations are ROM rows and coexist with choice box 29.
>
> These screens do not have one globally free tile range. Direct title-flow tile censuses
> proved different native residents in each context, so the final allocation is deliberately
> fragmented: difficulty uses primary `$67-$7A` and alternate `$E0-$F3`; Log 1/3 summaries
> use `$C0-$C7,$A1-$A4,$DE-$E5`, Log 2 uses `$E6-$ED,$EE-$F1,$F2-$F9`, and confirmation
> uses `$82-$8A,$9A-$9D`. Rank/Pass reuses the first four tiles of each confirmation slice
> in its mutually exclusive context. Normal difficulty alternates away from Easy/Hard so cursor
> transitions never repaint tiles still referenced by the outgoing description.
>
> **ERASE SEQUENCE — DO NOT COLLAPSE THESE TWO BOXES INTO ONE TEST.** Choosing a log draws
> box 26 (`x4,y4,n3,w14,flags04`): Log 2 row 0 is `2: Log of Shir`, which fits its
> eight-tile proportional slice, and row 1 is `en`. Confirming it draws VWF `No/Yes` in
> ROM box 28, then rebuilds the record below in box 27 (`x3,y7,n2,w15,flags00`). That wider
> row is `2: Log of Shire`; the extra `e` plus Dot's wider `2` needs **nine tiles**. Log 1
> needs eight because `1` is narrow, so the old eight-tile confirmation pool made Log 1
> proportional while Log 2/3 silently took the intentional raw fallback. Row 1's lone `n`
> still composed, making the mixed result even less obvious.
>
> The first `startspill` fixture selected only Log 1 and therefore produced the obsolete
> **43 exact / 5,893 visible / zero-problem** result. Joey's Log 2 screenshot falsified it.
> The tool now selects all three logs separately and opens the Rank/Pass popup. The fixed
> normal and shuffled builds each report **46 title, 3 selector, 27 summary, 6 confirmation
> and 2 Rank/Pass calls; 84 epilogue-exact and 16,182 visible plane checks; zero problems**.
> It also rejects any settled visible cell that references one of a static row's tile IDs
> without owning that exact position. Screenshots are in `build/startspill_v1/` and
> `build/startspill_v1_shuffle/`.
>
> **RANK/PASS POPUP — FIXED AND GUARDED.** The saved-title route stages
> `00 Rank FF` at `$C616` and `00 Pass FF` at `$C61C`; both reach the ordinary bank-31
> drawer as box 45, shape `x3,y8,n2,w6,flags02`. The selector helper now admits only that
> exact shape and per-row source; the allocator independently checks the physical cap and
> exact six-byte payload. Its static-prefix mode preserves the cursor cell and composes
> `Rank`/`Pass` into `$82-$85`/`$9A-$9D` without adding records to the already-full title
> allocator.
>
> **THE V1 TILE CENSUS, NOT ADJACENCY, PROVED THE POOLS.** Immediately before box-27 row
> 0, settled references in `$80-$9F` were `$81,$98,$99` for Log 1, `$81,$96-$99` for Log
> 2, and `$81,$96,$97` for Log 3: `$8A` had zero outside-row references in every case.
> Immediately before box 45, `$81` and `$8B-$90` were live; the latter six IDs belonged to
> the still-visible eighth title row. `$82-$89` and `$9A-$9D` had zero outside-row
> references. This is why confirmation extends through `$8A`, Rank/Pass reuses its static
> slices, and neither path touches the tempting but live `$8B-$90/$96-$99` ranges.
>
> **THE BLANK-CART FREEZE WAS A CODE-OWNERSHIP BUG, NOW FIXED.** `name6.py` owns bank
> 32:`$4300-$4369`: a copier followed by an 81-byte live new-game template. The first
> rankings uploader had been placed at `$4362` because the trailing template bytes looked
> like free `$FF`; it overwrote the final eight bytes and left the Japanese village card
> on screen forever. Rankings validation/upload now live in bank 33 at `$4200/$4240`,
> ending exactly at `$42B4`, with the shared far dispatcher at `$4100`. Every range is
> asserted against its owning reserved arena. `tools/newgamesmoke.py` starts with temporary
> blank cartridge RAM and requires the route to leave the card, produce the village sprite
> layer, change the screen, and respond to input. The fixed build reports 8 sprite, 49
> screen, and 14 CPU changes; the overwritten control fails.
>
> **REMAINING SESSION ORDER — V1/V2/V3 ENGINEERING GATES ARE CLOSED:**
>
> 1. **V2 — prologue/ending cinematic VM — COMPLETE:** `script/intro.tsv`, third-alphabet coverage,
>    relocated programs, Dot Gothic static VWF packs and `introspill` are complete. The
>    boot prologue and post-game Moonshadow Village Exit ending,
>    all 12 packs, exact original pauses/transitions, edited-TSV insertion and input behavior
>    pass. Joey's first visual run caught the single-buffer white-panel defect; his second
>    caught raw `$45/$46` overlay marks being allocated as ordinary glyph slices. The
>    corrected 34/39-tile double buffer now passes full-pause pixel stability plus exact
>    settled-row and blank overlay-row checks for all ten transitions.
>    Joey approved the prologue and forced ending playback in emulator on 2026-08-09.
>    `tools/introplayback.py` provides a reproducible CLI capture without a completed save.
> 2. **V3 — implemented and battery-green; broad playtest underway:** static box-2 words
>    (`Weapon/Shield/Str/Exp`) and Fay's `No`/`Rating` use fixed-position Dot fragments.
>    Absolute status values (`0 G`, `2 F`, `Easy` / `Normal` / `Hard`, and runtime
>    variants), the divider,
>    Fay's number/stars, and the cursor-addressed name grid retain their exact cells.
>    `structspill.py` proves status planes, the real Fay task-1→6 redraw, and a
>    pixel/shadow-identical name grid on normal and shuffled builds.
> 3. **V4A — optional runtime-substitution research; no known fit failure:** a
>    producer-to-template census could replace the 63 historical warning labels with
>    exact value classes, but current audits have zero definite failures and zero unproven
>    translated classes. Never rewrite translations merely to clear these warnings;
>    resume only by explicit request or for a concrete failing route/value.
> 4. **V4B — concrete playtest/text intake; scope intentionally open:** preserve Joey's
>    screenshots/routes and place suggested wording, authored-break, spacing, pacing or
>    reveal-rhythm work here. Newly observed hidden-text routes belong here and must gain
>    strict runtime-entry fixtures; concrete regressions on
>    the completed menu routes retain V4E/V4F ownership. Font metric edits reopen every
>    fit/allocation audit; cinematic text remains frozen.
> 5. **V4C — box geometry — COMPLETE; visually approved 2026-08-10:** boxes previously
>    widened for fixed-width English were re-measured and compacted with their cursor/field
>    coordinates as one change. Intentional fixed status values, Fay task/stars and name
>    cells remain fixed.
> 6. **V4D — translated-text completeness audit — COMPLETE, 2026-08-10:** all ten
>    script-bank embedded/unframed candidates are tied to non-text consumers and guarded
>    by exact address+byte declarations. Unknown runtime entries remain V4B/V6 route QA;
>    the bounded static audit no longer blocks graphics work.
> 7. **V4E — atomic clearing and Rankings ownership COMPLETE:** title, selector,
>    summary, confirmation, difficulty and Rank/Pass rows
>    publish as complete maps; Rankings rebuilds behind a blank alternate map; Fay restores
>    all borrowed planes before reveal. Rankings now uses the unified `$80-$A6` board,
>    temporary `$C0-$CB` selectors and native reload described above. The exact manual
>    Mesen route recorded in `HANDOFF_RANKVWF.md` also passes.
> 8. **V4F — item-menu stale-text/page-transition repair — COMPLETE; VISUALLY APPROVED
>    2026-08-10:** exact item entry/paging and the three Wood Arrow
>    action/Info transitions now use `old -> white -> complete`; normal, shuffled and
>    redirect-all real-save checks preserve compact geometry, native cursors, page
>    indicators and allocator contracts. Box 14 composes all of `Items` and is approved.
> 9. **V5 — graphics — COMPLETE:** **V5A** opening credits splash screen; **V5B** title
>    screen; **V5C** dungeon/town markers and screens, including the floor-name banner;
>    **V5D** all 22 native ending-credit cards. The final Japanese end mark is preserved.
>    The completed cinematic text renderer remains frozen.
> 10. **R3 — Rankings VWF ownership — COMPLETE; VISUALLY APPROVED 2026-08-12:** automated
>     normal/shuffled/redirect-all, both LCD paths and the repeated Mesen route pass;
>     fixed-width fallback remains unacceptable.
> 11. **V6 — release candidate:** freeze font/text/graphics/geometry; run blank and
>     populated saves, full screenshot and interaction sweeps, normal/shuffled batteries,
>     48 crash runs, intro regression, a clean playthrough and a translator-from-TSV build
>     dry run.
>
> The detailed acceptance criteria live at the top of `HANDOFF_NEXT.md`. Do not schedule
> V4A from warning count alone; collect ordinary visual findings for V4B, but repair
> crashes, progression blockers or newly exposed missing renderers immediately.
>
> **V3 MEASUREMENTS AND THE TWO TRAPS THEY FOUND.** `4:$4F88+` writes the status
> numbers/units and difficulty at absolute shadow cells; `31:$4186+` turns the name
> cursor's row/column into a source address with a fixed stride. Those are functional
> tables, not prose, and stay fixed. Box 2's four words and box 30's two static words are
> different: they can be precomposed into the same cells without moving the divider,
> task-number slot or star slots, so `tools/structvwf.py` installs exactly 12+6 Dot tiles
> and mirrors the Fay row at `4:$704E`.
>
> The first two plausible tile allocations were wrong. `$D1-$D6` looked unused beside
> Fay's seven-tile `$CA-$D0` prompt but the real screen rewrote all six planes with
> graphics. Apparent holes `$CD/$CE/$D2` in the status pool were also rewritten because
> the ROM-row allocator owns full reserved slices, not only referenced extents. The final
> allocation comes from the complete visible BG/window/OBJ census, rejects live `$87`,
> and context-shares only `$94/$95/$9D` with the ordinary allocator. `menuspill` exempts
> those IDs only at `(row,col)=(11,1),(1,1),(1,2)` and only when the live 2bpp planes equal
> the approved fragment raster. Heavy item pages still retain all 72 allocator tiles.
> Mutual exclusion alone is not a lifetime guarantee: Rank/Pass writes `$9A-$9D`, erase
> confirmation can write `$8A`, and the `No passwords.` one-row pool writes through native
> checkbox `$C4`; the Pass route reaches Fay without a font upload. Fay's authoritative
> entry at `4:$6E95` therefore calls a bank-38 restore before dispatching screen 17. It
> restores `$8A,$94,$95,$9A-$9D,$A4,$AF,$C4` over three fresh VBlanks. `structspill` drives
> both Rank and Pass/No-passwords routes and also poisons all ten planes immediately before
> entry, so an unenumerated prior screen is covered by the boundary invariant.
>
> Do not regress `structspill` to a forced dispatcher. Forcing screen 17 draws a convincing
> Fay screenshot but never installs callback `4:$6F90`, so Down merely exercises unrelated
> state and `4:$700E` never fires. The verifier now boots blank cartridge RAM, enters Fay's
> Puzzles through the title menus, moves task 1→6, checks the real BG map after the queued
> redraw (the game's shadow retains the entry row), and confirms the number/stars against
> a matching control. It also waits through the full name-grid transition; an earlier
> f1700 capture landed on opposite sides of that harmless transition by ROM checksum.
>
> **POST–VWF EVERYWHERE POLISH — BOX SIZING (Joey, 2026-08-07).** Several menu boxes were
> widened earlier to accommodate fixed-width English and now look oversized with Dot VWF.
> Defer shrinking them until every intended renderer/box is proportional and approved;
> otherwise the final text widths are still moving and geometry work will be repeated.
> The cleanup must be measured screen by screen, not treated as a descriptor-only visual
> tweak: box geometry is duplicated in cursor homes, selection/hit positioning, staging
> widths, and `menuvwf`'s shape allowlist assertions. Re-run the screenshot sweep, cursor
> interaction checks, normal/hostile/save `menuspill`, and crash battery after that pass.
>
> Post-integration evidence: `menuspill` passes normal (14 exact rows), hostile (23), and
> Joey-save (31, including `Remove`) flows with zero invariant violations. The save flow
> also proves all three page transitions have no old/new mixture. The help/seal flow adds
> 120 exact checks across real and synthetic-wide rows with zero violations. Proportional dialogue
> still passes 625 exact cases, 248 live passes under the one-frame execution budget,
> byte-exact VBlank delivery,
> and 0/20,320 spilling text frames. Current `rankspill` adds 25 plane-exact name tiles,
> five byte-exact queue transfers, and page-0/page-1 5/5 native-control fallbacks with
> exact `C6AC * 12` prevalidation on normal, shuffled and redirect-all builds.
> `menuromspill` adds 73 exact rows / 4,989 live checks. The expanded `startspill` adds 84
> exact rows / 16,182 live checks and is green on normal and shuffled builds;
> `newgamesmoke` still proves blank-cart village entry. Normal and
> shuffled Dot builds each passed 12 dungeon + 12 town crash seeds at 20,000 frames;
> shuffled normal/hostile/save/help/ROM/start/rank/new-game checks pass.
> The corrected cinematic VM additionally passes the prologue and ending on both layouts:
> 70 exact native
> mode-8 VBlank passes, ten pixel-stable outgoing panels, exact settled shadow rows and
> blank overlay rows, original pause/return timing, and early plus active-pause skip checks.
> It alternates code `$01-$22` at VRAM `$8B10` with the fragmented odd pool `$23-$44` at
> `$8D30` plus `$47-$4B` at `$8F70`; raw `$45/$46` remain dakuten/handakuten overlays and
> `$4C`/tile `$FC` remains the live panel fill. Five independent native 20-byte records are
> parked after seven hidden-buffer passes and restored to their
> tilemap destinations on the terminal delay tick before clear.
> `--redirect-all` builds cleanly. The pre-V2 deterministic ROM was SHA-256
> `a3ad1f15f10c757b0ea44c49dee03d2b780354fde99f6010197a8ac4b596c4d6`; the approved V2
> ROM is `9548bf505153f2ce1c49593bdd6361f27a68e02c3f4a16f09e2a400b5b536e93`.
>
> Attribution and the complete OFL text are in README §8 and
> `licenses/OFL-1.1-Dot-Gothic.txt`.
>
> ## HISTORICAL STEP 4B RECORD — SUPERSEDED BY THE CURRENT RESULT ABOVE
>
> The following preserves measurements and rejected ideas that led to the fragmented
> allocator. Its “next measurement” and “blocked” language is historical, not the next
> task. Return to the current section above before choosing new work.
>
> **STEP 4 LANDED 2026-08-06 (evening session, all six items).** `menuvwf` is a build.py
> stage (`--no-menuvwf`), the scratch WRAM is PROVEN free (`tools/wramfree.py`), 17-char
> `[NN]` counter rows and hyphen names compose, `tools/menuspill.py` verifies every
> composed row PLANE-EXACT in both a real-flow mode and a `--long` worst-case mode, and
> the current whitelist covers the ITEM LISTS (4/15). The MAIN MENU (0) and ACTION
> MENUS (6/39) were proven through the same renderer and then reverted because their
> retained slices starved item pages. Full battery green; 35-screen sweep vs
> `--no-menuvwf` diffs only inside whitelisted boxes; name-entry grid pixel-identical.
> §4B below records what step 4 changed and the SIX new facts it found — read it before
> touching menuvwf.py.
>
> **Joey: play `build/shiren_en.gb`** (your `shiren_en_menu.srm` is already beside it as
> the cart RAM — log 3 resumes on floor 7). **Your two reports from the first build are
> FIXED and verified on your own save**: equipped `E` rows compose (the `$84` marker is
> both the border select AND the E glyph at column 1 — measured against the raw
> drawer's shadow), and every page flip reallocates fresh so pages 2+ are fully VWF —
> `build/menuvwf_joey_p1/p2/p3.png` are your actual inventory pages. The MAIN MENU and
> ACTION MENUS are back to fixed-width ON PURPOSE: their session-long slices starved
> full item pages out of the 57-tile pool (that was the real cause of "most items
> aren't VWF"); they return with the pool extension below. On a PACKED page (five
> 17-char counter rows = 65 tiles) the last row still falls back — correct, rare,
> `build/glossary_widest_counter.png` shows it.
>
> **Step 4B, in working order:**
> 1. ~~**The `$82-$9D` pool extension** (+28 tiles → 85).~~ **REJECTED BY THE REQUIRED
>    CENSUS, 2026-08-07.** "No English glyph lives there" was true and irrelevant: these
>    are also raw UI tiles. `tools/menucensus.py` watches every LCD-on frame of the real
>    dungeon menu flow, Joey's floor-7 save (including its equipped rows and page flips),
>    all 35 forced dispatcher entries, both visible tilemaps and visible sprites. On BOTH
>    `--no-menuvwf` and the integrated build it found the same game-owned references:
>
>        live on screen:  $82 $83 $84 $88 $89 $8A $96 $97 $98 $99
>        live drawer arm:           $85 $86       (31:$40E5, alternate equipped marker)
>        unseen only:     $87 $8B-$95 $9A-$9D     (16 fragmented tiles, not 28)
>
>    `$82` is the back arrow; `$83/$84` are the equipped border/E marker; `$88` is the
>    name-field blank; `$89` a separator; `$8A` the Fay stars; `$96-$99` are paired
>    scroll decorations/arrows. The fixture did not carry a `$86` row, but the shipped
>    drawer explicitly maps `$86` to border `$85`, so both are reserved by code rather
>    than wished free. The first saved-flow draft reported all 28 live because it counted
>    the unsigned `$80-$A7` FLOOR BANNER during the white Continue transition; the final
>    tool gates on signed menu mode and a recent bank-4 screen dispatch. That false
>    positive is retained in the tool's comments because renderer scope is the whole
>    measurement here.
>
>    **Therefore DO NOT build an 85-tile allocator over `$43-$7B + $82-$9D`.** The only
>    measured addition is 16 tiles, for 73 total — short of the 65-tile packed item page
>    plus the main/action-menu residency that motivated 85. Step 4B must first either
>    reduce simultaneous record residency, find another genuinely non-simultaneous VRAM
>    fragment, or relocate the live UI tiles. The `$A8-$DD` composer-tile extension
>    remains OFF the table: picker prompts put composer dialogue and a menu box on screen
>    at once.
> 2. **A residency/lifetime audit rejects reclamation as the whole answer (2026-08-07).**
>    `tools/menuresidency.py` hooks the ORIGINAL drawer in `--no-menuvwf`, models the
>    intended main/item/action allowlist, and checks raw shadow bytes against the BG map
>    so stale WRAM is not called visible. It also injects five modelled 17-character
>    counter rows at the real item-row calls, then opens the real action overlay. Run:
>
>        python3 -B tools/menuresidency.py build/nomenuvwf.gb \
>            --ram saves/shiren_en_menu.srm
>
>    Ordinary dungeon inventory + action peaks at 35 cap tiles. Joey's actual busiest
>    page + `Remove/Toss/Drop/Info` peaks at **71**, so the measured 73 would pass that
>    save with only two tiles spare. The bounded worst case does not: five 13-tile rows
>    are **65** before overlays, **81** while the 16-cap action menu is visible, and a
>    no-stomp redraw reaches **85** while old tilemap references still exist. Therefore
>    deleting stale main-menu records cannot make 73 a worst-case solution; the original
>    85 target was real.
>
>    Fragmentation is independently fatal to the 73 plan. Its actual runs are
>    `57 + 11 + 4 + 1`; five indivisible 13-tile row slices total only 65 but cannot be
>    packed into those runs. The audit's action-overlay ownership trace also found a
>    possible later optimization: the action box covers the right tails of the first
>    three packed item rows, reducing the settled visible payload from 78 text tiles to
>    57. That is NOT free capacity yet — the overlay tilemap must hide those tails before
>    their tile data can be reused, and closing the overlay must redraw the item rows.
>
>    **NEXT MEASUREMENT: find and prove at least 12 more context-safe tiles, including a
>    run that can hold a 13-tile row; do not write the allocator first.** A preliminary
>    reference-only scan found `$CA-$DD` unseen in the real flows and all 35 forced menu
>    entries, but those 20 tiles belong to the dialogue composer's fixed `$A8-$DD`
>    three-line arena. "Not referenced in these snapshots" does not prove they cannot be
>    overwritten while a target menu row is visible. The next tool must measure
>    **concurrency** between main/item/action rows and composer tile writes/references.
>    Only a clean concurrency proof may reopen `$CA-$DD`; picker prompts are the required
>    hostile case.
>
>    **While in there: the page-flip jumble.** Joey saw 1-5 frames of mixed old/new
>    text on page flips (2026-08-07; cosmetic, he asked rather than reported). It is
>    OURS, not the GB's: the row-0 rewind reallocates the SAME tile indices the
>    still-displayed page references, so freshly uploaded pixels show through old rows
>    until each row's tilemap cells update. With 85 tiles, alternate allocation
>    between the pool's two ends on consecutive row-0 rewinds (a flip-flop bit next
>    to the watermark) and a new page never composes into tiles the old page shows.
>    **That exact fix is now blocked too**, because its two non-overlapping halves depended
>    on the invalid 85-tile pool. Preserve the diagnosis; redesign the allocation after
>    settling where the missing tiles come from.
>    **Current resolution (superseding the first blank/publish guard):** V4F's LCD-off
>    full-map transactions solve both inventory paging and Floor action/Info blending
>    without double-buffering or claiming another VRAM tile pool.
> 3. **Boxes 7 (item info) and 19 (seals)**: identical descriptors (x0,y3,w18,fl00) —
>    whitelisting one whitelists both. Their rows run to 18 cells, so they need a
>    21-char/16-tile row cap (w18 interior at 6px) and therefore the extension first,
>    or one box renders in two pens.
> 4. **Headers/status/shop ROM-SOURCE boxes**: the far code runs in bank 32 and cannot
>    read bank 31 ROM text pointers — composing those needs a bank-0 trampoline or a
>    staging copy. Census value first; most are short labels.
> 5. ~~Rankings renderer~~ **DONE in the current section above**; ~~the cinematic remains~~
>    **V2 later implemented it; see the current banner.**

**Branch `vwf-everywhere`, opened 2026-08-06 on Joey's direction:** *"for this project to be
very high quality, we need VWF … I don't care if it is difficult to do, as long as it is not
impossible, we should do it."* Order of work he set: (1) find where VWF is missing, (2) plan
it for the item menu, (3) POC on the item menu, (4) finish the item menu, (5) then the rest.

Everything in §1 and §2 below was **measured this session** on `build/shiren_en.gb` from
`saves/dungeon.state`, with hook logs and VRAM dumps — not inferred from old notes. The
scripts are in the scratchpad; the important numbers are restated here.

## 1. Where VWF is missing — the full inventory

Two render paths were already established (FINDINGS "TWO render paths"); this table is the
per-screen consequence, verified against the live build:

| # | renderer | screens | VWF? | evidence |
|---|---|---|---|---|
| 1 | composer, `13:$43B8` (+ typewriter `13:$6B59`) | all dialogue, dungeon/combat messages, story text, town signs, Kuyo picker prompts | **YES** — `tools/vwf.py`, 24 chars/line | landed 2026-08-03, `boxspill.py` green |
| 2 | menu box drawer, `31:$4075`/`$40D8`, per-char via `dte_box` `0:$00F0` | all 52 boxes; approved dynamic shapes, 19 measured ROM boxes, title/file/difficulty rows, all erase logs, and Rank/Pass compose; V3 gives box 2/30 fixed-position Dot fragments while live fields stay fixed | **YES for approved ordinary/static words; guarded live-field exceptions** | `menuvwf.py`, `structvwf.py`, `menuspill.py`, `structspill.py`, `menuromspill.py`, `startspill.py` |
| 3 | item info screen, `13:$7E49` → `$C616` (box 7, 18 cells, 4 lines) | identified descriptions from table `$554A`, plus shared identity-hidden title/body literals at `4:$5773` / `13:$5537` | **YES** | same proportional drawer; real + synthetic-wide plane checks; `unidentifiedhelp.py` proves the shared `Unknown` / `Effect is unknown.` data and `identityhiddenspill.py` replays real bracer/staff Info routes |
| 4 | seal rows, `11:$7E40` → `$C616` (box $13) | the 20 equipment seals under the item name | **YES** | same proportional drawer; all five seal groups plane-exact |
| 5 | rankings storage in bank 15; live drawer `31:$4662/$4A4B/$4A5F` | five rankings-list names | **YES; ownership complete and visually approved** | `rankvwf.py` / `rankspill.py` / `orochisymbolspill.py`; one-bank `$80-$A6` board, temporary `$C0-$CB` selectors and native reload; see `HANDOFF_RANKVWF.md` |
| 6 | status bar (window rows 0-1, own tileset `$E0-$FF`) | HP/floor/belly bar | n/a | pre-drawn glyph tiles ("0123456789", "BELLY"), graphics not text — route to V5C |
| 7 | prologue/ending cinematic VM, source `31:$5C62/$5DBE`, table `13:$7FAA` | boot prologue + post-game ending | **YES** | canonical `intro.tsv`; relocated bank-63 programs + 12 static Dot packs; `introspill.py` |

Paths 2-5 and 7 are implemented and measured. V3 explicitly resolved the structured
fixed-cell rows rather than silently equating “not an ordinary drawer row” with “done.”
New wording/spacing findings and newly observed hidden-text routes enter V4B, with a final
strict route sweep in V6. V4E/V4F are
complete; reopen them only for concrete regressions on their starting-menu or item-menu
routes rather than reopening the V3 renderer policy.

## 2. The four measurements that make menu VWF feasible

Menus were "not VWF-able" because the tilemap entry is the raw code — one glyph per cell by
construction, backed by a fixed font. All four hard constraints behind that turned out to be
soft:

1. **`$9000-$97FF` (tile indices `$00-$7F`) is already a per-screen swap area.** In the
   dungeon view it holds terrain graphics; opening a menu uploads the font over it
   (`13:$7643`, 1bpp doubled to 2bpp, 128 tiles + 68 + 15 more into `$8800+`), closing
   restores terrain. Nothing about that region is permanent. A VWF menu renderer may
   therefore *own* font-region tiles and redraw them per screen — the game already does.

2. **Menu-open transitions run with the LCD OFF.** Hook log: `font-upload f68 LCDC=$67`
   (bit 7 clear), first three box draws f70 LCD OFF. During a transition there is a free
   unlimited-VRAM-write window; composed tiles can be written directly.

3. **Later box draws run with the LCD ON — and the `$C006` tile-data queue is serviced
   there.** The item list itself draws at f141-142 (LCD on) after `A` on the main menu; the
   tile-data consumer `0:$11C5` fired at f143/f145 and the tilemap-row consumer `0:$10A0`
   at f147-150 during exactly that interaction. So the existing 12-tiles-per-frame upload
   path (three 66-byte `$C006` slots, destinations written the way `13:$43E2` does) works
   mid-menu. An item page (~40-90 tiles) uploads in 4-8 frames, ~0.1 s.

4. **The visible item-list screen references only:** blank `$00`, English text codes
   (≤ `$3E`), cursor `$81`, borders `$B8-$BF`. **The kana half of the font — indices
   `$40-$7F`, data `$9400-$97FF`, 64 tiles — is referenced by no English menu screen.**
   That is the dynamic tile pool, before touching anything else. (If 64 is ever short:
   the dialogue-composer tiles `$A8-$DD` minus borders are idle while a menu is up —
   +46 more — but that interaction must be measured first, see §5 Q3.)

Row mechanics, traced at `31:$40E4` (source `bc` ← `$C69F/$C6A0`, dest `hl` = shadow row,
`d` = row#): item rows are consecutive `$FF`-terminated code strings staged in `$C616`
("  Vision Herb", "  Big Onigiri", 3 empty rows, then header box 14 from ROM `31:$4390`).
Item rows land on shadow rows 4,6,8,10,12 — five slots a page, width 18, cell 0 is the
cursor slot. Redraws after closing an overlaying box also come through the drawer
(f301-304) — the allocator must survive partial redraws, not just full screens.

## 3. The design (step 2 deliverable)

**Same 6px uniform pen as dialogue, reusing bank 32's pre-shifted glyph table**
(`DATA_ORG $4400`, `$B3` codes × shifts 0/2/4/6 × 16 bytes). Cell k of a row starts at
pixel 6k; `(6k) % 8` cycles 0,6,4,2 — the four shifts already baked. Width-18 boxes go
18 → 24 characters, exactly the dialogue arithmetic.

**Hook the whole row at `31:$40D8`** (a far-call stub via `rst $10`, code in a free bank),
not the per-character store — the per-character site is `dte_box`'s and the composition
needs the whole expanded line anyway:

1. Read the row source; expand DTE inline (same table `dte_box` uses) into a ≤24-char
   buffer.
2. **Eligibility test, per row:** the box is whitelisted for VWF (POC: the item list only)
   AND every expanded code is on the English page (letters/digits/punct, no `$79/$7A`
   dakuten, no kana). Anything else falls through to the ORIGINAL drawer path unchanged —
   the kana name-entry grid, Japanese leftovers, and the dakuten `hl-33` overlay trick
   stay byte-identical.
3. Compose glyphs into the `$C006` slot payloads; write the three slot destinations as
   `13:$43E2` does, aimed at pool tiles (`$9400 + 16·alloc`); >12-tile rows go in two
   pumps (the dialogue two-halves pattern). During LCD-off transitions, write VRAM
   directly instead.
4. Write the allocated pool INDICES (`$40+`) into the shadow row, borders and padding as
   the original does. The cursor writer (`4:$4F2B`, writes `$81` into shadow) needs no
   change.
5. **Allocator:** watermark over `$40-$7F`, reset on every full screen build (the font
   upload `13:$7643` is the reset signal — it is the transition marker), plus a small
   per-shadow-row record (row → pool base/len) so partial redraws (action menu closing
   over the list) recompose into the SAME slice instead of leaking. Pool exhausted →
   fixed-width fallback for the remainder, never a crash.

**Historical POC model — superseded by the measured contracts above.** What stayed a
character count at this stage: the cell budgets (`$C6DC` charging, box width checks in
`build.py`/`dialogue_preview`) — same decision as dialogue VWF, so DTE and every existing
checker keep their units. A width-18 row holds 24 chars; `ITEM_CAP` can rise once the item
menu is DONE and measured (re-decree, not re-measure — the `[N]` counter still applies).

> **2026-08-09 correction after a genuine `Accurate Sword+99` test:** the old 14-character
> equipment-name limit is a 17-cell source-staging limit, not the proportional row's visual
> capacity. At the time of the photograph, `Accurate Sword+99` advanced 90px and painted
> 89px against the item payload's 128px. The later approved compact-plus edit makes it
> 88px/87px/11 tiles. After Joey's final compact-minus/4/7 edits, 144 signed two-digit
> suffixes share the peak; deterministic representative `Accurate Sword-99` is likewise
> 88px/87px/11 tiles. Do not turn 14 into a new lint until the item-name stager is widened
> and the independent dialogue substitution paths are measured. One of those paths proved
> the distinction: `Put down Accurate Sword-77` is 135px advance / 134px painted; the old
> 24-character contract truncated it, while the accepted 30/144 contract renders it.

**Bisect control:** `--no-menuvwf` in `build.py`, exactly like `--no-vwf`/`--no-name6`.

## 4. POC scope (step 3) — **LANDED 2026-08-06, `tools/menuvwf.py`** — and DONE criteria (step 4)

POC = the item list box only: composed rows on the real screen in the emulator, raw path
for every other box. Prove: composition, queue upload with LCD on, pool indices on the
shadow map, survival of open→action-menu→close→redraw.

**All four proven.** `tools/menuvwf.py <rom-in> <rom-out>` applies it standalone (not yet
a `build.py` stage). Evidence: `build/menuvwf_poc_items.png` ("Vision Herb" / "Big Rice
Ball" at the 6px pen in the real item list), `build/menuvwf_poc_redraw.png` (the same
rows recomposed cleanly after an action menu opened and closed over them). Crashscan:
12 seeds dungeon + 12 town, 0 halts. Main menu, action menu and header draw through the
raw path pixel-untouched.

**One ROM fact the POC had to discover — §2's item 3 was HALF right.** The tile-data
consumer is serviced during menus, but it moves **9 tiles a pass, not 12**: the third
slot's unrolled copy is ONE tile (32/32/8 pop-`de` units, counted at `0:$11C9/$126A/
$130B`) — the dialogue's 4+4+1 half-line shape hardcoded in bank 0. HANDOFF_VWF's
"payload: 4 tiles" table is right about the stride and wrong as a capacity claim. A
10-12 tile row therefore uploads in TWO passes; the second re-aims all three slots at
tiles 8-11 (idempotent rewrites for the two spare slots). The symptom that found it:
"Big Rice Bal" plus one stale KANA tile — the 10th tile simply never arrived, and the
pool's previous content showed through.

**A second ROM fact, found by JOEY PLAYING on a colour screen (2026-08-06, same day):**
every pass of either `$C006` consumer first replays the ONE-CELL record at `$C000`
(dest word, then 2 bytes to dest+0/1 and 2 to dest+32/33). Menus PARK that record with
dest = `$C002` — a write aimed into the queue itself as a no-op — so each pass wrote
`$C0,$0C` over payload bytes `$C022/23` (slot-1 tile 1, row 5) before the copy ran. One
row of one tile in every composed item name carried single-plane garbage: near-invisible
grey on DMG, **green specks on a colour screen**, which is what Joey photographed. The
dialogue path never hits it because the typewriter keeps `$C000` aimed at real VRAM.
Fix: while our upload is armed, aim the record at our own slot-1 destination (its stale
write lands inside the 64 bytes the copy immediately overwrites), restore the game's
park after the last pass. Composed tiles now verify PLANE-EXACT against the glyph table
(0 diverging bytes) — and that plane-level check is the shape `menuspill.py` should keep:
an OR'd-planes dump hid this for a whole session, and a DMG screenshot hid it from every
PNG in this file. **Photograph on a colour palette, compare planes separately.**

**POC limits, deliberate:** 16 chars / 12 fixed tiles a row (rows 0-4 at `$40+12d`);
17-char rows (a two-digit `[N]` staff stack) fall back to the raw drawer, correct but
fixed-width; boxes 7 (item info) and 19 (seals) stay raw via the flags-bit-1 test; the
scratch run `$C0CC-$C0D4` is asserted free by HANDOFF_VWF's "$C0CC is referenced
nowhere" and still needs a wramcensus pass.

Step 4 (DONE) adds:
* every WRAM-staged English box whitelisted (action menu, main menu, category pages,
  status screen, "Which?"/"Items" headers, yes/no, shops);
* `menuspill.py` — the `boxspill.py` idea for menus: every frame, no visible cell may
  reference a pool tile outside its row's recorded slice, and settled screens must
  pixel-match a reference render of the expected TEXT (screen-memory check, not a model);
* `menushot.py --sweep` pixel-compare vs `--no-menuvwf` for every NON-whitelisted screen
  (they must be identical), and photographs of the whitelisted ones for Joey;
* the standing battery: crashscan (both states), logicdiff, coverage, lint, msgdur
  unchanged, gridprobe for the name-entry grid (must be untouched — it is raw path);
* **hand Joey a build** — the battery does not play the game, and menus are exactly where
  he has caught what it missed (name-entry box, `[N]` counter).

## 4B. What step 4 changed (2026-08-06 evening) — and the six facts it found

The implementation of record: `tools/menuvwf.py`'s docstring is the authority; this is
the delta. Rows are allocated by a WATERMARK ALLOCATOR over pool `$43-$7B` (57 tiles),
records keyed by SHADOW DEST at `$C163-$C1B2` (16 × 5: key, base, cap, raw cells),
reset by a far-call hook on the font upload `13:$7643` (far index 9). Tile 12 of a
13-tile row composes into `$C12C-$C13B` — the `$C006` queue's flat space holds exactly
12 tiles, which is what really capped the POC at 16 chars. Upload footprints are
TIERED: 4 tiles for n<=4 (idempotent slot stacking), 8 for 5-8, the native 4+4+1 shape
plus a backward last-4 window for 9-13. `tools/wramfree.py` (static opcode+boundary
voting + per-frame dynamic watch over menus/walks/35 forced screens) is how every WRAM
run above was proven; `tools/menuspill.py` is the verifier (plane-exact vs a python
composition from the ROM's own glyph table; `--long` drives real worst-case rows).

0. **(Round 2, from Joey playing his own save — both fixed the same night.)**
   **The equipped marker `$84`/`$86` does DOUBLE duty**: it selects the left border
   ($83/$85) AND is drawn as the row's column-1 cell — tile $84 IS the E glyph.
   FINDINGS' "select $83/$85 instead" reads as border-only and is easy to
   half-implement: consuming the marker shifted composed E-rows one cell left and put
   the cursor over their first tile. The control build's SHADOW dump (`83 84 81
   codes...`) is the authority. And **exact-size slices are wrong across PAGE FLIPS**:
   page 2 restages all five rows with different text, so reusing page-1 caps left most
   rows raw — row 0 of an allowlisted box now rewinds that box's record tail (keys
   hl+64i) and every full redraw reallocates fresh. The main menu + action menus were
   whitelisted for part of the night and REVERTED: their session-long records held
   20-36 of 57 pool tiles and starved full item pages — they need the extension.
1. **Six English glyphs live INSIDE `$40-$7F`**: `, ' - + [ ]` at $40/41/42/7C/7E/7F.
   §2's "referenced by no English menu screen" was measured on screens without
   counters or punctuation — the `[N]` counter writer `4:$5D58` writes `$7E`/`$7F`,
   and five item names carry `-`. The POC's fixed slices covered `$41/$42` (latent
   glyph stomp); the pool now EXCLUDES all six and eligibility ACCEPTS them as codes.
2. **The raw-cell prefix is SHAPE-DEPENDENT**: w18 item rows stage TWO leading zero
   cells, the w7 main menu and w9 action menus stage ONE. A fixed two-zero test made
   every main-menu row fall back silently — and the narrow, left-aligned latin font
   made the raw result LOOK composed in a screenshot. Only the far-call trace
   (`$C0D8` never moving) told the truth. Verify composition by allocator state or
   plane comparison, never by eye.
3. **Eligibility must be a DESCRIPTOR SHAPE ALLOWLIST, not a flags test**: box 25
   (x5 y9 w9, dynamic, WRAM-staged, English — the over-dialogue picker) passes every
   flags-only rule and draws on screens whose `$9000-$97FF` holds TERRAIN, not the
   font. Composing is only safe after a font upload; the allowlisted shapes are all
   dispatcher screens. install() asserts the BUILT descriptors match the asm constants
   so a box_geometry.tsv edit fails the build (the layout-duplicated-in-code trap).
4. **Records must REUSE ACROSS SCREENS of one session and GROW**: the font upload only
   fires at session open (main menu -> item list -> action menu share one pool), and
   shadow row 4 is BOTH main-menu "Quit" and item row 0 — same key. A reused record
   too small for its new text grows iff it is the top watermark allocation, else that
   row falls back raw. This is also why footprints are tiered: a flat 9-tile floor let
   four short main-menu verbs hold 36 of 57 tiles and starve 5-item inventories.
5. **Bank 32's far-index table has a ONE-BYTE stride** — entries overlap, so live
   indices are odd: name6 3, vwf 5, menurow 7, menureset 9.
6. **The font-upload hook shifts walk RNG alignment**: it fires ~once per screen
   transition (measured 1 in 3000 walked frames), and those few cycles move frame
   boundaries, so `msgdur`'s seeded walk meets DIFFERENT boxes than a `--no-menuvwf`
   control (17 vs 9-10; reverting the 3 hook bytes reproduces the control
   byte-identically). Cross-build msgdur comparisons need both builds hooked
   identically; within-build numbers are unaffected.

`13:$7643` has NO literal `call` anywhere in the ROM (the one `call $7643` is bank-4-
local code) — it is reached through a computed path; the hook works regardless, proven
by menuspill's fresh-session reset scenario. The step-4 census scripts live in
`tools/wramfree.py` and this session's scratchpad; the box-descriptor dump one-liner is
in the git log of this file if needed again.

## 5. Open questions the POC must answer (ranked by risk)

1. **What arms the tile-data consumer vs the tilemap-row consumer of `$C006`?** Both read
   the same queue with different strides. `13:$43E2` only writes the three destination
   words. Mimic the dialogue caller wholesale and trace; if there is a mode flag, find it
   by diffing WRAM around the two firings (f143/145 vs f147-150).
2. **Where does the per-row record + watermark live in WRAM?** ~40 bytes. Candidates: dead
   bytes vwf's install freed in bank 13's WRAM usage, or unused `$C6xx`/`$CFxx` slack —
   must be proven idle across menus AND dialogue (wramcensus.py).
3. **Do menus and the dialogue composer ever hold the screen at the same time?** (shop
   menus + shopkeeper lines is the suspect). If yes, the `$A8-$DD` extension pool is off
   the table and 64 tiles is the budget; measure before extending.
4. **The busiest screens' tile counts** — status screen, shop buy list with prices,
   rankings: run a census per `menushot.py --sweep` screen before whitelisting each.
5. **Rankings renderer** (bank 15): trace its writer; it may want its own small hook or a
   restage through the box drawer.

## 6. What was tried/settled this session, so nobody re-derives it

* `saves/dungeon.state` loads IN the dungeon; **B opens the main menu** (start does not),
  `A` then enters the item list. Earlier confusion ("start opens the menu") cost several
  probe runs.
* The shadow→VRAM tilemap copy is command-stream driven (`0:$3C3F` appends; emitters
  around `0:$3D90-$3EAF`), consumed in vblank. No `$C300`/`$9800` immediates exist in
  bank 0 — do not search for them.
* `31:$4106` already reads `call $00F0` in the shipped ROM — the menu DTE hook LANDED;
  any VWF hook must expand DTE itself or sit above it. (An old HANDOFF line still calls
  this "still to hook"; it is stale.)
* The `$8800` region's 68+15 extra font tiles (`13:$7657+`) include the cursor `$81`,
  digits-for-status, borders `$B8-$BF` — indices `$80-$D2` are re-uploaded at menu open
  too, so nothing composed may live below `$D3` in that half without the same
  compose-after-upload ordering.
