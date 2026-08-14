# Item-menu no-white transition: deferred revisit plan

Status: **deferred; experimental branch is not release-ready**  
Recorded: 2026-08-14  
Branch: `v-blank-fix`  
Stable starting commit: `c3ccdc628a44cb662e28f1e64226e82002a031ff` (`main`)  
Experimental ROM SHA-256: `0896967fd35f79618469849c74555d9f82a3b3906ba7af76cf87d4432cb71a8c`

## Decision

The stable `main` behavior is acceptable. Do not spend more time incrementally repairing
the current experiment and do not merge it as the release implementation.

Preserve `v-blank-fix` as a record of the investigation. If this feature is revisited,
start a fresh implementation from the stable commit above and use this branch only for
reference. Do not carry its menu-wide ownership state machine forward by default.

The only original goal worth reconsidering is removing the white interval from **Item
R/L page changes**. Main -> Items, Item Action, Item/Floor Info, Pot, entry, exit and
cancel transitions are outside the initial scope. They keep the stable behavior unless a
later, independently budgeted project addresses them.

## What was learned

### Japanese behavior

- Item page changes keep LCDC.7 enabled.
- The new page appears progressively over complete rows; it is not an atomic full-page
  swap.
- Main -> Items and the Action/Info routes are also LCD-on and progressive.
- Dungeon -> top-level Main genuinely has a native white/LCD-off interval and should not
  be treated as an English regression.

### Hardware constraint

The Japanese renderer points at immutable shared kana tiles. English VWF rows require new
tile pixels to be uploaded.

- A worst Item page is five rows x 11 tiles = 55 dynamic tiles.
- Keeping complete old and new worst pages simultaneously requires about 110 dynamic
  tiles before other UI owners.
- The general DMG/SGB menu context has only about 72 safely usable dynamic tiles and no
  second VRAM bank.
- The existing mode-$0A queue uploads nine tiles per VBlank. Uploading 55 new Item tiles
  therefore has a lower bound of seven VBlanks before map/publication overhead when that
  queue is used unchanged.

Consequently, native Japanese speed, a completely atomic page swap, no blanking and the
existing DMG tile budget cannot all be obtained at once. A bounded progressive update may
still be possible.

## Why the current experiment was stopped

The experiment expanded from Item paging into a global transaction system involving:

- persistent Item lifecycle states `$A0-$A9`;
- five visible row owners, a rotating high scratch owner and a borrowed `$25-$2F` row;
- separate Action, low-Info and high-Info generations;
- full-map VBlank publication;
- tile migration and map translation;
- restoration of native fixed-font planes in as many as seven queued passes;
- special handling for Main, Action cancel, Pot and Floor Action/Info returns.

This produced unacceptable latency in measured routes:

| Transition | Approximate press-to-settled time |
| --- | ---: |
| Item R/L page | 17 frames |
| Main -> Items | 23 frames |
| low Info -> Items | 25 frames |
| high Info -> Items | 33 frames |
| Action cancel -> Items | 31 frames |

Manual testing also found state/history-dependent failures that fixture tests missed:

- the first Item row losing VWF after extended navigation;
- first-row name corruption after leaving an Item Action submenu;
- broken Floor menu content when returning from the final Info page;
- very slow box and full-screen construction;
- gameplay sprites visible through incomplete menu construction;
- VWF/status tile-plane corruption that sometimes disappeared after another page change
  or after leaving and reopening the menu.

These are architectural ownership and publication failures, not one remaining off-by-one
bug. Adding more route-specific states and borrowed ranges would increase risk and cost.

### Test-suite blind spots

The experiment's tests were useful but insufficient as release evidence:

- most routes used long settling windows without a maximum latency requirement;
- fixed saves covered selected ownership permutations, not prolonged arbitrary input;
- several checks proved allocator records existed without proving every final visible
  glyph plane matched its intended text;
- intermediate shadow/map disagreement was sometimes intentionally excluded;
- taking the last sampled frame as the expected endpoint can normalize a stable corrupt
  endpoint unless a separate plane oracle rejects it.

## Narrow future feasibility study

Only proceed through these gates. Stop at the first failed gate and retain the stable
white transition.

### Gate 1: isolate Item R/L only

1. Start from the stable commit, not from the experimental state machine.
2. Trace the exact stable allocator records, VRAM owners, OAM state and tilemap writes for
   every Item page and both directions.
3. Prove a page-only scratch/rotation schedule for all built Item variants. It must not
   require borrowing native fixed-font planes, changing Action/Info allocation, or
   maintaining ownership through another menu screen.
4. If settled Item ownership cannot return to the stable menu contract without extra
   normalization frames, stop.

### Gate 2: one-row combined VBlank prototype

Investigate a dedicated VBlank operation which, for one Item row:

1. composes at most 11 glyph tiles into WRAM without arming the ordinary upload job;
2. copies at most 176 tile bytes into a non-visible scratch slice;
3. copies the complete 20-cell shadow row to the visible BG map in the same VBlank;
4. only then releases the outgoing row owner for the next row.

This could reduce the transaction from separate upload and map VBlanks to approximately
one committed row per frame. It is only viable after measuring the complete routine,
interrupt overhead and worst entry time against the real DMG VBlank budget. Do not infer
that it fits from emulator success alone.

### Gate 3: acceptance limits

The prototype may continue only if all are true:

- LCDC.7 stays enabled for every scoped R/L frame.
- No visible 8x8 glyph cell contains a raster other than the complete old or complete new
  cell.
- Page indicator and cursor remain coherent.
- Input is usable no later than seven frames after the page press. Eight frames is a hard
  stop for review, not permission to expand the design.
- No full 20x18 map copy, native-font restoration, transient low-font borrowing or
  cross-screen lifecycle state is introduced.
- Main -> Items, Action open/navigation/cancel, Info, Floor, Pot and Items -> Main match
  stable-main framebuffer/state traces outside the isolated R/L transaction.

### Gate 4: regression strategy

Before considering a merge:

- enumerate all 9,131 reachable Item name/count variants against the 11-tile limit;
- test short and full final pages, all directions and every page count;
- run at least 1,000 deterministic randomized operations combining R/L, selection moves,
  Action open/cancel, Info open/return, Items exit/re-entry and Floor menus;
- verify final visible tile planes, not only allocator records and tile IDs;
- reject any unexpected OAM visibility, border/map partial state, lifecycle residue or
  input-latency overrun;
- test normal, `--shuffle` and `--redirect-all` builds;
- perform manual emulator testing before calling the feature complete.

## Work-budget rule

Treat Gates 1-2 as a small feasibility prototype, not authorization for another broad
rewrite. Do not expand into Action/Info/Floor fixes to make the prototype pass. If the
page-only transaction cannot satisfy the seven-frame target cleanly, document the
measurement and keep the stable white flash.

The white flash is preferable to corrupted text, exposed sprites, delayed input or a
large cross-menu state machine.
