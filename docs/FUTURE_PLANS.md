# Future plans

## Regional blanking for proportional Item pages

**Status:** Checkpoints 1 and 2 are committed, regression-complete, and visually
accepted. Checkpoint 2 keeps pages 1-4 live on Items-to-Status, while Status-to-Items
blanks only the replaceable BG above the persistent Window and commits empty box chrome
before item text. This accepted implementation is frozen at commit `3489572` on
2026-08-23. The current checkpoint-3 working tree also fixes two regressions found during
visual review: the first title-menu publication now includes the Adventure cursor, and
the special standing-item Floor page after carried pages retires all four unused row
borders, converts between complete one- and five-row chrome in both paging directions,
and returns live to Status. Both have first-frame fixtures but still await the same manual
review. Checkpoint 3's exact held-inventory Action-overlay scope is implemented
and regression-complete. Its B-cancel now replaces the outgoing Action box with the
reconstructed Item parent and restores the retained Item input state directly. The
unpublished Status/Items replay is skipped, eliminating both shared-tile contamination
and the former 40-frame input stall. Checkpoints 4-6 remain deferred.

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
4. Render the incoming rows through the existing VBlank upload queue. Do not busy-wait
   for LY and directly copy a large payload into VRAM.
5. Publish each row only after all of its tile pixels are complete. Rows may appear
   progressively from top to bottom; partially painted or aliased rows are forbidden.
6. Publish the correct cursor and page indicator with the relevant completed map state,
   then release input once the transaction has settled.
7. Keep the WRAM shadow map and visible BG map synchronized, and cancel or redirect any
   pending native publisher that could repaint an older intermediate map afterward.

The expected visual sequence is therefore:

```text
complete old page
empty Item status/name rows, with the surrounding menu still visible
one or more complete new rows
complete new page
```

### Checkpoint-1 implementation record

The implementation is deliberately narrower than the general proposal:

- Bank 60 far index `$07` owns the regional controller at `$4090-$4294`; far index `$09`
  owns the fallback controller at `$4300-$43E9`; far index `$05` retains the shared full
  20x18 publisher at `$405A-$4084`. Redirected text begins at `$4400` in this bank.
- The regional begin gate requires screen 1, proportional Item mode, row key `$C380`, an
  active allocator epoch and LCDC bit 7. It derives one through four pages from native
  item count `$C6AA` and validates the exact settled `4:$4EB4` shape: one page has four
  `$BC` border cells; two through four have one `$C6`, the remaining live `$C5` cells,
  then `$BC`. Right wrap has one additional exact transient: selector zero is committed
  while all four old markers are retired to `$BC`. It drains `$C11A` and reacquires
  VBlank before validating that visible marker: this closes two phase-sensitive
  false-fallback candidates consistent with the rare report, a partially published marker
  and a blocked mode-3 VRAM read after a long drain. The rare trigger has not been
  captured deterministically. Initial entry is handled separately at the screen-1
  shadow-clear boundary.
- The controller normally writes `$BE` to each marker-coupled left border (`key+0`) and zero to
  each raw marker cell (`key+1`) and name interior (`key+3..key+18`), then applies the
  same 90-cell regional state to BG. The 85 marker/name cells are blank; every other cell
  remains outside this initial write set. Selector `$FF` is not a dummy fifth Item row:
  when Shiren stands on an item it is the real one-row Floor page appended after the
  carried pages. That shape transition commits a complete empty one-row Floor rectangle
  before Floor text. Leaving Floor by Right or Left commits a complete empty five-row
  Items rectangle before page-1 or last-page text. Both finish before tilemap row 3 is
  scanned—and currently inside VBlank; the four rows absent from Floor are structurally
  zero after contraction.
- A completed row drains `$C11A` before publishing its left border, marker cell, and 16
  name cells together. This is required because equipped `$84/$86` markers select the
  paired `$83/$85` border; publishing only the marker leaves a visible vertical remnant.
  The controller masks interrupts only across the VBlank rendezvous and map copy so the
  native VBlank handler cannot consume the safe write window, then immediately restores
  them. Cursor and right-border cells are not copied by the regional publisher. A short
  page's native empty slot is accepted only when its exact 19-byte source field is all zero.
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
`tools/menuspill.py --ram` independently observes the top-to-bottom `old -> blank -> new`
row sequence and keeps allocator records plane-exact.

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
   both empty box perimeters, and then uses the existing completed-row/native-final
   publishers for text and final decoration. A 2026-08-24 follow-up additionally admits
   the completed standing-item Floor page (`$C6AC=$FF`) through an exact settlement latch;
   its automated evidence passes and its visual correction awaits review.
3. **Held-inventory Action overlay — IMPLEMENTED, awaiting visual acceptance:** change only
   the direct screen-1 Items to screen-2 Action open and B-cancel back to the identical
   Item page/selection. Pages 1-4 and every proven four- through six-row box-6 verb set
   are one acceptance unit. The validated B-pop now atomically replaces box 6 with its
   reconstructed Item parent, restores the Item cursor/record/screen state, and returns
   directly without rebuilding unpublished Status and Items screens. This prevents
   shared-tile `Gitan / Floor / Path` contamination, the prolonged empty footprint, and
   the former 40-frame input stall; observed B return and post-release D-pad acceptance
   are both two frames. Cursor movement and gameplay-bound item use are regression checks,
   not new regional transitions. Screen 16, shop context, Floor box 39, Info, Name entry,
   and Pot descendants remain on their current paths until separately traced.
4. **Item Info lifecycle:** Action to Info, multi-page Info where applicable, and Info
   back to Items with the correct selection and page restored.
5. **Adjacent special routes:** priced shop items, Pot actions, Floor menus, debug menus,
   and transitions that legitimately return directly to gameplay.
6. **Release validation:** normal, shuffled, and redirect-all layouts followed by the
   complete release battery.

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
