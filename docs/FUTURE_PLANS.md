# Future plans

## Regional blanking for proportional Item pages

**Status:** Checkpoints 1-3 are committed, regression-complete, and visually accepted.
Checkpoint 2 keeps pages 1-4 live on Items-to-Status, while Status-to-Items blanks only
the replaceable BG above the persistent Window and commits empty box chrome before item
text. It is frozen at commit `3489572` on 2026-08-23. Checkpoint 3 is frozen at commit
`34a20ec` on 2026-08-25. Its accepted scope includes carried-page paging and sorting, the
real appended standing-item Floor page in both paging directions, live Floor-to-Status,
the initial Adventure cursor, and screen-2 Action B-cancel over carried Items pages 1-4
and the settled standing-item Floor page. B-cancel replaces the outgoing Action box with
the reconstructed Item/Floor parent and restores the retained screen-1 input state
directly. The unpublished Status/Items replay is skipped, eliminating both shared-tile
contamination and the former 40-frame input stall. Checkpoint 4 is now a partial automated
review candidate, not frozen: it covers exact screen-1, screen-7, and screen-20
Item/Floor -> Action -> Info/seal -> same-parent lifecycles plus carried-Pot screen-12/13 `See` ->
Items return. After failed visual review, screen-20 Info entry/page redraw was revised
from a 9-14-frame empty hold to Action-box-to-chrome-plus-row-zero entry and whole-row
old/new replacement. The reported carried screen-5
seal return now retains the complete seal page through the disposable Status replay and
hands the parent to the bounded Item-page regional renderer instead of taking an LCD-off
fallback. Visual acceptance is still pending.
Checkpoints 5-6 remain deferred.

The behavior-neutral whole-LCD audit is now implemented. `tools/lcdblankaudit.py`
compares every `$FF40` writer in the Japanese and English ROMs and makes every explicit
translation-added bit-7 clear a manifested build decision. The first census found 45
base writers and 78 English writers, including ten explicit English blankers: four
complete-screen/tile-reload sites currently kept, two complete-screen menu sites awaiting
policy review, three same-menu fallbacks marked for replacement, and one mixed site. The
mixed Item-page instruction is required exactly once when entering complete Pot viewer
screen 12/13 but is prohibited for ordinary Items paging and sorting. Each same-menu site
is connected to an exact execution hook in its paging, Status-return, Pot, or Info
fixtures; visual playtesting is no longer the primary detector for those known fallbacks.

The audit also made the remaining debt reproducible. The unidentified-Pot Floor parent is
dispatcher screen 7, despite sharing a handler with screen 20. Its exact `0,7,4,0,7`
Info route is now an independent zero-blank regional lifecycle: entry restores the
underlying full-width title before Info, and return carries state `$0B` through disposable
screen 0 before rebuilding box 5 plus the y=1 seven-row box 6. Item Action -> Name -> End
-> Items still executes the Status blanker once during its disposable screen-0
reconstruction and is now the next same-menu regional-removal candidate. The
rejected Item-row blanker at `60:$4222` has no observed exact execution; it remains a
zero-execution fixture invariant until a real caller proves otherwise.

The review gate now includes the reported five-row `Egg / Egg / Happy Bracer /
Fusion Pot / Manji Kabura` inventory. That case proved screen 12 can legitimately retain
either zero or one private-Action admission latch; requiring one caused the LCD-off,
box-late, mixed-title return. The corrected exact proof accepts both screen-12 producers,
and the fixture chains five standing-Floor Info pages through carried-Pot See and back.
It also includes the exact `mesen_spawn_fusion_kit.lua` history. The injected records
were not themselves the blanking trigger: a gameplay-bound carried Action could leave
the private admission byte at one after its BG owner disappeared. The independent
screen-20 `0,20,4/5` route now admits idle or that stale-one value, clears it before
publication, and continues to reject active Item transaction phases two through four.

### Motivation

The Japanese game changes Item pages while the LCD remains enabled. Its character tiles
are immutable, so it can progressively replace tilemap references without changing the
pixels still used by the outgoing page.

The English VWF instead paints packed text into reusable tile-data slots. Repainting a
slot while the visible tilemap still refers to it makes the outgoing text mutate into
new letters, missing glyphs, or border graphics. The current robust workaround disables
the LCD while the page is rebuilt, but that produces a conspicuous full-screen white
flash that is not present in the Japanese Item-page transition.

Full double-buffering is not a practical default. A worst-case Item page needs five
11-tile rows, or 55 dynamic tiles; keeping complete outgoing and incoming pages at once
would require roughly 110 tiles. Only about 72 tiles are realistically reusable in this
DMG/SGB menu context, and adjacent menus temporarily own several of them.

Regional blanking accepts a short-lived empty Item region in exchange for eliminating
both the full white screen and unsafe tile reuse.

### Implemented checkpoint-1 transition

1. Drain any pending VWF upload or map-publication job.
2. During one VBlank, normalize the five marker-coupled left-border cells to `$BE`, then
   replace the five raw status-marker cells and five Item-name interiors with blank
   tilemap cells. Keep the LCD enabled and preserve the title, right borders, status
   panel, and other unaffected screen regions.
3. Once that blank map is visible, release the old page's dynamic tile slots. They are
   now safe to reuse because no visible cell refers to them.
4. Render the incoming rows into the existing WRAM payloads. For the proven blank Item
   region, copy each 16-byte glyph tile as four synchronized four-byte HBlank slices;
   every unproved context retains the existing VBlank upload queue. The bounded slices,
   not an unbounded LY copy, are the implemented exception to the original caution.
5. Keep every completed incoming row unreferenced until the final body row is ready,
   then publish all five owned row regions together in one VBlank. The proportional
   composition cost may vary, but a top-to-bottom visible cascade is forbidden.
6. Publish the correct cursor and page indicator with the relevant completed map state,
   then release input once the transaction has settled.
7. Keep the WRAM shadow map and visible BG map synchronized, and cancel or redirect any
   pending native publisher that could repaint an older intermediate map afterward.

The expected visual sequence is therefore:

```text
complete old page
empty Item status/name rows, with the surrounding menu still visible
complete new page
```

### Checkpoint-1 implementation record

The implementation is deliberately narrower than the general proposal:

- Bank 60 far index `$07` owns the regional controller at `$4090-$422D`; far index `$09`
  owns the fallback controller at `$4300-$43EE`; far index `$05` retains the shared full
  20x18 publisher at `$405A-$4084`. The atomic body helper occupies
  `$43F0-$444E`; far index `$0F` owns the redraw-tail service at `$4480-$45A5`, with a
  final-body shape marker at `$45A6-$45CE`, and
  dispatches the direct tile helper at `$45E0-$46B0`. The final row also calls the
  native-equivalent indicator builder at `$46B1-$46FF`, so the new page and green dot
  settle together. Redirected text begins at `$4700`.
- The regional begin gate requires screen 1, proportional Item mode, row key `$C380`, an
  active allocator epoch, LCDC bit 7, and native item count `$C6AA` in the supported
  one-through-twenty range. `mgbdis` confirms that native Right/Left commits `$C6AC` and
  synchronously calls the redraw; that path never reads the visible `$986F-$9872` page
  indicator. The indicator is transaction output, not an ownership proof. The former
  visible-marker veto could observe an outgoing or partially published marker and
  incorrectly select state `$06`'s LCD-off full-map publisher, so it has been removed.
  Items/Floor shape changes additionally
  retire the four shared title references, compose box 14/18 while those tiles are
  unreferenced, and commit the completed replacement title with the indicator. It drains
  `$C11A` before beginning its own transaction, but does not use the resulting visible
  marker as an admission input. Initial entry is handled separately at the screen-1
  shadow-clear boundary, while an unsupported regional row retains its distinct LCD-off
  safety fallback.
- The controller normally writes `$BE` to each marker-coupled left border (`key+0`) and zero to
  each raw marker (`key+1`), cursor (`key+2`), and name interior (`key+3..key+18`), then applies the
  same 95-cell regional state to BG. The 90 marker/cursor/name cells are blank; every other cell
  remains outside this initial write set. Selector `$FF` is not a dummy fifth Item row:
  when Shiren stands on an item it is the real one-row Floor page appended after the
  carried pages. That shape transition commits a complete empty one-row Floor rectangle
  before Floor text. Leaving Floor by Right or Left commits a complete empty five-row
  Items rectangle before page-1 or last-page text. Both finish before tilemap row 3 is
  scanned—and currently inside VBlank; the four rows absent from Floor are structurally
  zero after contraction.
- Each row's tile pixels are completed first, but rows 0-3 remain unreferenced behind the
  regional blank. Final row 4 derives and publishes the page indicator, then copies all
  five left-border/marker pairs, cursor cells, and 16-cell name interiors together in one VBlank. This
  is required because equipped `$84/$86` markers select the paired `$83/$85` border;
  publishing only the marker leaves a visible vertical remnant. Exact glyph tiles still
  use four-byte HBlank slices with interrupts masked. A native selector whose old row is
  empty on a short destination page is clamped to the final real item before the visible
  cursor is published; only right-border cells remain outside the body publisher. A short
  page's native empty slot is accepted only when its exact 19-byte source field is all
  zero. Selector `$FF` uses the same helper with its single real row.
- Any unknown nonempty fallback changes state to `$05`, disables the LCD during VBlank,
  and completes through the retained whole-map publisher. Initial/declined entry is
  latched as `$06` and also stays on that safe path.

`tools/itempagespill.py` drives four unique pages, seven real direction presses, and one
Start-sort redraw. The last-page right wrap deliberately exercises its two native stages:
the first input selects the one-row standing-item Floor page at `$FF` and the second
selects page 1. It
checks the exact blanking boundaries, both tile bitplanes, all locked BG cells, structural
tiles, atomic border/marker/name lifetime, transaction states, cursor/page indicator, the
short-page zero rows, and that all eight scoped redraws keep LCDC bit 7 enabled. The
Floor-page transaction and the page-1 transaction both remain regional while the wrap
temporarily retires all four page markers to `$BC`.
The build repeats a carried-page-only four-page cycle with only 20 frames between row-4
completion and the next input; it has seven regional redraws, zero fallbacks, and zero
LCD-off frames. This shorter cadence prevents the old fixed 90-frame idle from hiding
queue/publication phase defects.
`tools/fusioncountspill.py`
adds 1/6/11/16-item cases, cycles both directions through every page and wrap boundary,
then invokes Start-sort. It proves all 3/5/7/9 redraws enter regional mode without
fallback or LCD-off frames.
`tools/itempagespill.py` observes `complete old -> complete regional blank -> complete
new body`, hooks the sole final-row VBlank commit directly, and keeps allocator records
plane-exact.

An optional refinement can blank and replace one row at a time. That would retain more
of the outgoing page during the redraw, but it requires a proven spare 11-tile row slice
and stricter per-row ownership. Start with the simpler five-row regional clear.

### Implementation checkpoints

Stop after every checkpoint for manual review. Do not combine these stages into one large
rewrite.

1. **Screen-1 redraw checkpoint — COMPLETE and visually accepted:** full and short Item
   pages, repeated movement in both directions, Start-sort, correct page indicator,
   cursor, and borders.
2. **Item entry and exit — COMPLETE and visually accepted:** Items back to Status from
   each of pages 1-4 keeps the LCD and outgoing page live. Direct Status-to-Items
   entry/re-entry keeps the Window live, retires BG rows 0-15 in four VBlanks, commits
   both empty box perimeters, and then uses the existing completed-body/native-final
   publishers for text and final decoration. A 2026-08-24 follow-up additionally admits
   the completed standing-item Floor page (`$C6AC=$FF`) through an exact settlement latch;
   its automated and visual evidence is accepted as part of the checkpoint-3 freeze.
3. **Screen-1 Item/Floor Action overlay — COMPLETE and visually accepted:**
   change only direct screen-1 carried Items or the settled standing-item Floor page to
   screen-2 Action, followed by B-cancel back to the identical parent. Pages 1-4, the
   appended `$FF` Floor page, and every proven four- through six-row box-6 verb set are
   one acceptance unit. The validated B-pop now atomically replaces box 6 with its
   reconstructed Item/Floor parent, restores the cursor/record/screen state, and returns
   directly without rebuilding unpublished Status and Items screens. This prevents
   shared-tile `Gitan / Floor / Path` contamination, the prolonged empty footprint, and
   the former 40-frame input stall; observed B return and post-release D-pad acceptance
   are at most two frames. The standing Floor fixture independently measures a two-frame
   B return and one-frame acceptance of the next page input. Cursor movement and
   gameplay-bound item use are regression checks, not new regional transitions. Screen
   16, shop context, screen-20 Floor box 39, Info, Name entry, and Pot descendants remain
   on their current paths until separately traced.
4. **Item/Floor Info lifecycle — COMPLETE; post-freeze nine-seal footer recheck pending:** exact
   screen-1 carried-Item/settled-Floor and independent screen-20 Floor parents may enter
   screen-4 Info or screen-5 equipment seals. Screen 1 publishes complete empty box-7
   chrome before complete rows. Screen 20 instead keeps its Action box until complete
   Info chrome and row zero are ready together; later pages preserve unaffected old rows
   while replacing allocator-overlapping rows whole, so the body never becomes empty.
   The final row and pager are atomic. Exit suppresses the disposable screen-0
   publication while retaining the completed outgoing page, then retires its five text
   rows/pager only at the first
   proven parent row and builds the complete empty target. Carried screen-5 seals hand
   that target to the same fast regional renderer as Item paging; screen-4 descriptions
   retain their exact final-header publisher. Both reveal text only after complete boxes. Screen-20
   preserves its real 3-7-row Action height; five-page Fusion Pot footers settle as
   `1/5` through `5/5`, with no stale Action tail. The post-freeze screen-5 amendment
   separately restores the bounded three-page seal footer and automatically proves
   `1/3`, `2/3`, and `3/3`; only its focused visual recheck remains pending. A one-frame
   Down tap enters the native page handler once, avoiding translated-redraw autorepeat.
   The exact carried-Pot
   screen-12/13 `See` B paths also skip their disposable Status redraw and hand off to
   box-first direct Items entry. All scoped fixtures keep the LCD enabled and avoid a
   uniform whole-display frame. The revised five-page screen-20 fixture additionally
   rejects zero-row frames and row rasters which are not a complete old row, complete new
   row, or complete retirement. A separate exact-Lua-history fixture proves the stale
   carried-Action admission is normalized on Status -> Floor -> Info, but manual visual
   acceptance remains.
   Floor Pot
   viewers, `Put`/`Push`, shop, screen 16, and unknown Info callers remain unchanged.
5. **Adjacent special routes:** priced shop items, remaining Pot actions/viewers, debug
   menus, and transitions that legitimately return directly to gameplay.
6. **Release validation:** normal, shuffled, and redirect-all layouts followed by the
   complete release battery.

### Checkpoint-3 freeze record

Checkpoint 3 was frozen on 2026-08-25 against implementation commit `34a20ec` after the
complete automated battery and manual playtest accepted the final transitions. The
investigation used two complementary kinds of evidence:

- A fresh `../mgbdis` disassembly of the Japanese base ROM established that native
  Right/Left handlers `4:$7339` and `4:$7354` store `$C6AC` and synchronously call
  `4:$483E`; they do not read the visible green page indicator at `$986F-$9872`. The
  translation-added visible-indicator veto was therefore invalid. The indicator is
  redraw output, not permission to begin a redraw.
- Frame-level PyBoy fixtures established the behavior that static disassembly could not:
  which intermediate pixels were visible, when VBlank was missed, whether the LCD was
  disabled, whether rapid input overlapped a transaction, and when the input machine
  became responsive. Those traces required completed Item rows to remain hidden until
  one atomic final-body publication and identified the unnecessary screen `2 -> 0 -> 1`
  replay behind Action B-cancel.

The resulting accepted rules are:

1. Prove redraw admission from native selector, screen, stack, allocator, and ownership
   state; never infer ownership from a visible decoration produced by the redraw.
2. Compose variable-time proportional text behind the regional blank, then publish the
   complete body and page indicator atomically during VBlank.
3. Treat selector `$FF` as a real one-row Floor page, not a paging sentinel. Convert the
   complete box shape in both directions and retire all four unused Item-row borders.
4. Serialize the Floor/Items shape boundary even when ordinary carried-page paging can
   accept a shorter cadence; this prevents rapid-input overlap and menu corruption.
5. Give Action rows a proven disjoint tile pool. On exact B-cancel, reconstruct the
   covered Item/Floor parent and restore its retained input state directly; do not replay
   invisible Status and Items screens after the visible parent is already complete.
6. Preserve a conservative native fallback whenever any admission or ownership proof
   fails. A forced or plausible-looking screen is not evidence that the route is owned.

Blanking used by an original Japanese transition or by an immediate return to gameplay
is outside this plan. The primary target is translation-only full-screen blanking during
Item-menu navigation.

### Required regression contract

Frame-level tests must cover the entire sampled transition tail rather than inspecting
only a settled endpoint.

- LCDC bit 7 remains enabled throughout the scoped menu transitions.
- Every visible Item row is exactly old, blank, or complete new content—never an unknown
  or partially painted row.
- Once a row becomes new, it cannot regress to old or blank content.
- Borders, header, page marker, cursor, Window/status panel, and unrelated map cells stay
  exact on every frame.
- No tile-data slot is repainted while any BG or Window cell still visibly references it.
- All queued uploads complete byte-exactly before their map references become visible.
- Tests include one-, two-, three-, and four-page inventories, short final pages, repeated
  Left/Right movement through every boundary and wraparound, and entry/exit from page 2 or later.
- A standing-item fixture includes four carried pages plus the appended Floor page,
  requires rows 6-15 to be structurally zero in shadow and BG, then independently leaves
  that page by B, Right, and Left. B reaches Status; Right reaches page 1; Left reaches
  page 4. Both paging directions require complete incoming chrome before text and every
  route forbids LCD-off, all-white, and fallback frames.
- From that settled Floor page, a separate fixture opens the real `Take / Fire / Swap /
  Info` screen-2 Action box, B-cancels, requires one exact VBlank parent restore and no
  replay, then proves the first post-B Left input is accepted promptly.
- Tests include Action and Info transitions from page 2 or later, because settled page-1
  fixtures do not prove allocator lifetime safety.
- Tests continue past the first settled frame to catch delayed native publications,
  restoration work, or settle-then-corrupt failures.

### Trade-offs and non-goals

- The Item area may be empty for several frames while new VWF pixels are uploaded. This
  is intentional and preferable to blanking the whole LCD.
- Regional blanking will not be pixel-identical to the Japanese progressive transition,
  but it preserves the rest of the menu and prevents text corruption.
- This plan does not attempt complete two-page pixel buffering, CGB VRAM banking, or
  universal prefetching.
- A passing final screenshot is insufficient. Transition ownership and every visible
  intermediate frame are part of correctness.

The guiding rule is simple: **remove a tile's final visible map reference before reusing
its pixels, and reveal a new map reference only after those pixels are complete.**
