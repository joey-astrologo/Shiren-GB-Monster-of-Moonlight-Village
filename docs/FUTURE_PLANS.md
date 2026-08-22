# Future plans

## Regional blanking for proportional Item pages

**Status:** Deferred design. This is not implemented and should be revisited with a fresh
usage budget. Treat Item-menu Left/Right paging as the first prototype; do not expand it
to every menu transition until that prototype is visually approved and regression-tested.

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

### Proposed transition

1. Drain any pending VWF upload or map-publication job.
2. During one VBlank, replace only the five Item-name interiors with blank tilemap cells.
   Keep the LCD enabled and preserve the title, box borders, status panel, and other
   unaffected screen regions.
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
empty Item-name rows, with the surrounding menu still visible
one or more complete new rows
complete new page
```

An optional refinement can blank and replace one row at a time. That would retain more
of the outgoing page during the redraw, but it requires a proven spare 11-tile row slice
and stricter per-row ownership. Start with the simpler five-row regional clear.

### Implementation checkpoints

Stop after every checkpoint for manual review. Do not combine these stages into one large
rewrite.

1. **Left/Right prototype:** full and short Item pages, repeated movement in both
   directions, correct page indicator, cursor, and borders.
2. **Item entry and exit:** status menu to Items, Items back to status, and re-entry after
   paging beyond page 1.
3. **Action menu lifecycle:** open the action picker from every page, move its cursor,
   cancel, consume an item, and return to Items without corrupting either screen.
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
- Tests include a full inventory, a short final page, two-page inventories, repeated
  Left/Right movement, and entry/exit from page 2 or later.
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
