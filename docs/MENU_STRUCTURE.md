# Menu systems and regional-blanking ownership

**Status:** Engineering map plus implemented Item/Floor checkpoints, measured through
2026-08-30. The dispatcher, box catalogue, memory map, and fixture-backed routes below
are established. Routes marked `outline` or `inferred` still need a real button-driven
trace before later work depends on them. Checkpoints 1-3 are committed and visually
accepted. Checkpoint 4 is visually accepted against ROM SHA-256
`3eca647016f1b78df6be91925d5ec145ab548a288685cdb1ac30e99e23bd5983`; commit provenance
is the commit containing this freeze record. The 2026-08-30 consolidated Item/Floor
visual pass accepted all nine original
test contracts, then exposed seven additional whole-LCD routes and two LCD-live
render-order/steady-state defects through deeper fixture exploration. Those findings are
now catalogued as `IFR-01` through `IFR-09`; they are not silently covered by the original
passes. Leaving any of pages 1-4 keeps the outgoing page live until Status replaces it.
Direct Status-to-Items entry/re-entry blanks only BG rows 0-15, preserves the bottom
Window, and commits empty box chrome before item text.

The nine follow-up findings `IFR-01` through `IFR-09` are implemented, automated, and
visually accepted. Final-page A returns for sealed equipment,
Info-before-Name histories, contained-item Pot Info, shop price publication, direct
unidentified-Pot Name entry/return, and the post-Name Action dismissal each have an
exact owner and a deterministic no-Lua fixture. They are no longer classified as
`remaining`.

The first grouped follow-up on 2026-08-30 failed and exposed additional natural-route
gaps: direct-Floor sealed final-A, a short-page glyph, contained-Pot retirement, shop
top-row preservation, and ordinary direct-Floor Name history. Those causes have now been
implemented and added to deterministic save-backed regressions. The reduced six-test
visual recheck passed in full on 2026-08-30 against the exact ROM hash above.

Checkpoint 3 is frozen at implementation commit `34a20ec` on 2026-08-25. Its accepted
scope includes the screen-15 Adventure cursor correction, complete one- and five-row
Items/Floor shape conversion, live standing-Floor exit and paging, atomic Item-body/page
indicator publication, and direct screen-2 Action B-cancel back to its exact carried-Item
or settled standing-Floor parent. The acceptance record below separates conclusions
proved by `mgbdis` from conclusions proved by frame-level runtime fixtures.

Checkpoint 4 is implemented and visually frozen at the ROM hash above. Its exact
screen-1, screen-7, and screen-20 Item/Floor -> Action -> Info/seal -> parent lifecycles
pass their automated entry, multi-page, single-tap input, both-exit, ownership, timing,
and adjacent-regression gates.
The exact carried-Pot screen-12/13 `See` entry/return and the independently proven
Items-appended Floor, alternate screen-7 Floor, and screen-20 Floor Pot entries/returns
are also regional and box-first. Every admitted entry keeps the HUD Window live, shows
complete empty Pot chrome, and only then publishes the title/body text.
In response to the reported blank,
screen-20 Info entry now keeps the Action box until complete Info chrome and row zero are
ready together. Page redraw retains unaffected old rows while replacing overlapping rows
whole; a page is never reduced to an empty body. The carried screen-5 seal return also
keeps the completed seal page visible
through the disposable Status replay, then hands the Items rebuild to the same bounded
regional renderer used by paging. The baseline and focused follow-up playtests accepted
these publication and return contracts.

The whole-LCD caller census is behavior-neutral and intentionally retains four dormant
safety fallbacks for malformed or unproved callers. Every catalogued Item/Floor
same-menu route now has a narrower regional owner; each automated route requires zero
fallback executions. The real unidentified-Pot Floor route is alternate parent screen 7,
not screen 20;
its Info and ground-Pot See returns now have their own zero-blank regional lifecycles and
exact instruction-level regression gates. Their matching Pot `See` entries now have
independent stack proofs and zero-blank chrome-first gates. The exact inventory Item
`Name -> End -> Items` replay has an independently gated zero-blank, chrome-first owner
covering every page and row. Its dedicated Mesen route was visually accepted on
2026-08-27.

The matching carried-Item `Action -> Name` entry is also regionally owned.
Only the exact dispatcher stack `0,1,2,9` receives the LCD-on regional transition. A
tracked SRM created through ordinary `Take` and save inputs makes that entry reproducible
without Lua, direct memory writes, or inherited emulator state. Start naming remains an
independent atomic native-font transition. Both Floor Name parents now have separate
regional End, initially-empty B, and erased-name B returns.

This document answers two separate questions:

1. What screen or box is the game drawing, and what other menu content survives behind it?
2. Which visible tilemap cells and tile-data slots may be changed without corrupting that
   surviving content?

The second question is why this map exists. Japanese menu text refers to immutable glyph
tiles. English VWF rows refer to a small set of reusable tile-data slots. If an incoming
row repaints one of those slots while an outgoing visible cell still refers to it, the old
text changes underneath the player. The current translation prevents this by disabling
the LCD and rebuilding the whole 20x18 map. That is safe, but creates translation-only
full-screen white flashes.

Regional blanking is the intended replacement where ownership is provable: remove all
visible references in the region being replaced, then recycle its tile slots, render the
new pixels, and publish only complete rows. Native blanks used when entering gameplay,
Map, dialogue, or another genuinely new screen are not targets.

The load-bearing invariant is:

> Remove a tile's final visible BG or Window reference before repainting its pixels, and
> reveal a new reference only after those pixels are complete.

## Evidence and confidence

The static map was recovered from the matching base ROM with the sibling `../mgbdis`
checkout, then checked against the project disassembler and the built ROM. The base ROM
MD5 used for this pass is
`754398219a3ab38394cdac543d8deb47`.

Runtime routes were driven through the real dispatcher and drawers with the repository's
PyBoy fixtures. In this document:

- **measured** means a ROM address, table entry, or runtime value was observed directly;
- **fixture** means a real button-driven saved-state route reached it;
- **inferred** means the draw routine is known but its complete player-facing route has
  not yet been captured;
- **outline** preserves the navigation description supplied during planning and is a
  worklist, not yet an implementation fact.

For context-sensitive screens, forcing a dispatcher index is useful for discovering the
draw routine but is not route evidence. Several screens read selected-item, file, or
debug state and cannot be understood safely in isolation.

## Whole-LCD blanking audit

The earlier 45/78 "writer" count was incomplete. It scanned only
`ldh [$FF40],a`/`ld [$FF40],a`, so it missed both direct
`ld hl,$FF40; res 7,[hl]` mutations and the native `$C110` LCDC shadow. The Japanese
engine normally clears bit 7 in `$C110`; VBlank's generic publisher at `0:$0737` later
copies that off value to hardware. Cataloguing only `$FF40` therefore hid the causal
native callers which explain several apparently unpredictable blanks.

The corrected build audit emits three files:

```sh
python3 tools/lcdblankaudit.py build/base.gb build/shiren_en.gb \
  --tsv build/lcd_blank_audit.tsv \
  --item-menu-tsv build/lcd_blank_item_paths.tsv \
  --start-menu-tsv build/lcd_blank_start_paths.tsv
```

`lcd_blank_audit.tsv` is the instruction census. The other two files deliberately split
the player-facing callers into the Item/Status and Start systems. A shared physical
instruction appears once per distinct route, because testing one caller does not approve
the others. Versioned snapshots live in
[`LCD_BLANKING_AUDIT.tsv`](LCD_BLANKING_AUDIT.tsv),
[`LCD_BLANKING_ITEM_PATHS.tsv`](LCD_BLANKING_ITEM_PATHS.tsv), and
[`LCD_BLANKING_START_PATHS.tsv`](LCD_BLANKING_START_PATHS.tsv); the build copies are the
freshly verified equivalents.

The corrected 2026-08-27 base/current census is 116/153 display mutators: 79/112 target
hardware LCDC and 37/41 target the `$C110` shadow. Thirty-seven are translation-added;
ten explicitly request LCD-off. A fresh `../mgbdis` disassembly of base ROM MD5
`754398219a3ab38394cdac543d8deb47` confirmed all literal `$FF40` and `$C110` references
and the native shadow routines at `2:$463C`, `2:$4702`, and `4:$4154`. Focused exhaustive
runtime traces then hooked all 153 candidates. The full 61-fixture battery used the
smaller causal set and produced 3,687 off-valued events. No variable direct LCDC writer
outside the catalogues below opened a menu blank in the focused runs.

The runtime recorder is opt-in for any fixture:

```sh
SHIREN_LCD_TRACE=build/lcd_trace.jsonl \
  SHIREN_LCD_TRACE_ALL=1 \
  python3 tools/potputspill.py build/shiren_en.gb
```

The trace records the producer, target, prior and incoming LCDC values, dispatcher stack,
transaction bytes, active bank, and fixture arguments. `0:$0737` is recorded as the
publisher but never treated as the route owner.

The path status vocabulary is strict:

- `remaining`: an observed same-menu transition still turns the whole LCD off;
- `regional`: the route has no whole-LCD producer and has an exact regional owner, but
  still requires the named visual review when it is a new checkpoint candidate;
- `review`: an observed menu-to-menu atomic blank which has not been visually accepted
  as permanent;
- `keep`: a boot, independent-screen, or gameplay replacement boundary where whole-LCD
  blanking is intentional;
- `dormant`: an executable safety fallback remains, but every admitted caller requires
  zero executions; and
- `coverage-gap`: the player edge is known, but no exact button-driven trace has yet
  identified its causal producer.

The ten explicit translation-owned whole-LCD sites are:

| Site | Owner and route | Policy |
|---|---|---|
| `38:$408F` | `structvwf.feirestore`: Fay's Puzzle composite/native fixed-tile reload | `keep` — independent composite screen |
| `41:$40E1` | `menuvwf.starttransition`: title/file complete shadow-map replacement | `review` — complete-screen menu transaction |
| `43:$40B6` | `rankvwf.rankfinish`: completed Rankings whole-map publication | `review` — complete-screen menu transaction |
| `44:$4066` | `name6.namerestore`: complete native font restore retained for Start naming and rejected screen-9 callers; exact carried Items, Items-appended screen-7 Floor, and screen-20 Floor are admitted before this fallback | `mixed` — keep the independent Start keyboard and unknown-caller fallback; proven Item/Floor callers are regional |
| `46:$42B5` | `rankvwf.nativerestore`: Rankings and Start-root native-font restoration | `keep` — tile-data lifetime boundary |
| `53:$4600` | `statusvwf.statusentry`: rejected Status reconstruction retained for unknown callers; every catalogued Item/Floor return has a narrower owner | `replace-menu` safety fallback; dormant in the expanded automated routes |
| `59:$406F` | `normalending.install`: Normal-ending full-screen art installation | `keep` — new scene |
| `60:$4222` | `menuvwf.itemregion`: rejected Item-row transaction; the canonical cursed/plated/fused equipment route is now admitted before it | `replace-menu` safety fallback, dormant for known callers |
| `60:$4338` | `menuvwf.itempage`: rejected Item/Pot transaction; the Pot `Put` selector is now admitted before it | `replace-menu` safety fallback, dormant for known callers |
| `62:$447E` | `menuvwf.infolifecycle`: legacy Item/Floor Info or seal fallback | `replace-menu`; dormant for every catalogued Info/seal/Pot route |

`keep` applies only to the named caller. The clearest example is `44:$4066`: the Start
keyboard is an independent screen and may keep the atomic native-font reload, while the
Item/Floor Name caller is same-menu debt.

### Item/Status LCD-off catalogue

The generated Item table currently has 32 caller rows: twenty-three admitted regional
rows, four dormant safety fallbacks, and five intentional gameplay/new-screen
replacement boundaries. There are no `remaining` Item/Floor rows. `IFR-03` and
`IFR-06` were LCD-live ordering/steady-state defects rather than off-producer paths, but
their history and price-row parity are now included in the named regional fixtures. The
catalogued regional scope was manually accepted on 2026-08-30 against ROM SHA-256
`3eca647016f1b78df6be91925d5ec145ab548a288685cdb1ac30e99e23bd5983`.

| Player path | Causal off producer(s) | Status and evidence |
|---|---|---|
| Dungeon field -> Status | shadow `4:$4154` | `keep`; independent field-to-menu replacement |
| Status -> Items with injected cursed/plated/fused rows | none | `regional`; exact auxiliary cursed-equipment fragment is distinguished from a failed row; three plane-exact rows and zero `irdisable` executions |
| Items case-3/6 sealed equipment -> Info final-page A -> Items | none | `regional` (`IFR-01`); `iteminfospill.py` independently drives native final-A handler `$C6BC` and B, returns chrome-first, and records zero LCD-off/uniform frames plus prompt input |
| Dropped case-3 sealed equipment Floor -> Info final-page A -> Floor | none | `regional` (`IFR-02`); a no-Lua carried fixture performs the real Drop onto an empty tile, then proves both direct `0,20,5` and appended `0,1,2,5` `$C6BC` final-A pops with zero explicit fallback/LCD-off/uniform frames and prompt input |
| Carried unidentified item -> Action -> Name | none | `regional` (`IFR-03`); direct and Info-then-Name B/End histories drain pending work, retire keyboard/status fragments, and publish complete Items chrome before rows with LCDC.7 set |
| B from an empty carried-item Name keyboard -> Items | none | `regional`; exact no-Lua screen-9 cancel arms state `$0E`, suppresses disposable Status, publishes complete Items chrome before rows, and accepts immediate input |
| B after erasing a reopened carried-item name -> Items | none | `regional`; real End/reopen/four-delete/final-B route preserves native mode 3, arms state `$0F`, publishes complete Items chrome before rows, and accepts immediate input |
| Items-appended Floor screen 7 -> Action -> Name | none | `regional`; exact stack `0,1,2,9`, selector `$FF`, Floor latch `$01`, transaction `00 00 20 01 01`, and box `(13,1,6,5,2)` use the bounded BG/native-plane publisher with LCDC.7 set |
| End from Items-appended Floor Name -> Floor Action | none | `regional`; exact `9 -> 0 -> 1 -> 2`, mode/row `$03/$00`, keyboard retirement, and complete Floor/Action chrome before text |
| B from initially empty Items-appended Floor Name -> Floor Action | none | `regional`; exact `9 -> 0 -> 1 -> 2`, mode/row `$00/$01`, zero Status fallback/LCD-off/uniform frames |
| B after erasing a reopened Items-appended Floor item name -> Floor Action | none | `regional`; exact `9 -> 0 -> 1 -> 2`, mode/row `$03/$01`, zero Status fallback/LCD-off/uniform frames |
| Items-appended unidentified-Pot Floor Name return -> dismiss Action | none | `regional` (`IFR-09`); `unidentifiedpotnamespill.py` consumes the retained post-Name Floor owner and returns directly to responsive screen 1 with zero Status fallback/LCD-off/uniform frames |
| Screen-20 unidentified Willow Staff Floor -> Action -> Name | none | `regional`; exact stack `0,20,9`, ground context, box-39 owner, and live direct-Action state `$C1B5/$C1B6=$20/$04` use the shared bounded BG/native-plane publisher; successful entry consumes that state, and the Status -> Floor predecessor is independently LCD-live and zero-off |
| End from screen-20 Floor Name -> Floor | none | `regional`; exact `9 -> 0 -> 20`, mode/row `$03/$00`, and the established screen-20 replay owner |
| B from initially empty screen-20 Floor Name -> Floor | none | `regional`; exact `9 -> 0 -> 20`, mode/row `$00/$01`, complete Floor/Action chrome before text |
| B after erasing a reopened screen-20 Floor item name -> Floor | none | `regional`; exact `9 -> 0 -> 20`, mode/row `$03/$01`, zero Status fallback/LCD-off/uniform frames |
| Direct unidentified-Pot Floor seven-row Action -> Name | none | `regional` (`IFR-07`); exact screen-7/seven-row owner retires the parent region and restores keyboard planes without reaching the native whole-screen Name restore |
| Direct unidentified-Pot Name End/B -> Floor Action | none | `regional` (`IFR-08`); deterministic End and initial-empty B routes retire the keyboard before complete screen-7 Floor/Action chrome and rows, with zero LCD-off/uniform frames |
| Carried Pot Action -> `Put` selector, screen 11 | none | `regional`; screen-11 owner retires Action and publishes empty Items chrome before selector rows; zero `pbdisable` |
| Commit `Put` -> dungeon action animation | shadow `2:$463C` | `keep`; frame trace shows the field/action animation from f3610-f3683, so this is a menu-to-gameplay boundary |
| Dungeon action animation -> rebuilt Items | shadow `4:$4154` | `keep`; new-screen boundary after the field action, not a same-menu redraw |
| First B after `Put` -> disposable Status -> Items replay | none | `regional`; exact Put epoch suppresses disposable screen 0 and never reaches `statusdisable` |
| Final B after `Put` -> Status | none | `regional`; ordinary Items-to-Status owner; the later Status-to-field teardown is separately kept |
| Pot contents item Action -> Info from carried/direct-Floor/appended-Floor parents | none | `regional` (`IFR-04`); stack-specific proof distinguishes carried/appended `0,1,2` from ground `0,7/20` Pot parents; the deterministic populated Storage-Pot route reaches Info with zero explicit or sampled LCD-off frames |
| Contained-item Info -> Pot contents parent | none | `regional` (`IFR-05`); state `$17` removes Action+Info, preserves Pot screen/selector, and reveals complete empty Pot chrome before restored title/content rows |
| Unknown rejected child -> Status | `53:$4600` | `dormant`; zero hits across the expanded 2026-08-30 Item/Floor regression battery |
| Unknown rejected page/sort/shape transaction | `60:$4222` | `dormant`; admitted paging, sort, and Floor paths require zero |
| Unknown rejected Item/Pot replacement | `60:$4338` | `dormant`; admitted paging and `See` paths require zero |
| Unknown rejected Info/seal/Pot lifecycle | `62:$447E` | `dormant`; sealed final-A, nested-Pot, shop appended-Floor, and established Info/See fixtures all record zero executions |
| Shop direct or Items-appended Floor -> Action -> Info -> Floor | none | `regional` (`IFR-06`); direct route dispatches `20,4,0,20`; appended route independently proves settled Floor ownership despite the `$D0-$DE` Action-pool collision, stays LCD-live both ways, and preserves identical initial/returned price suffixes |
| Action whose destination is gameplay/field message | shadow `2:$463C`, shadow `4:$4154` | `keep`; replacement path, including the pre-Floor history in `floorinfospill.py --fusion-kit-history` |
| B from Status -> dungeon field | shadow `2:$463C` | `keep`; intentional final menu teardown |

Normal Items paging, Start sorting, page indicators, Status -> ordinary Items, Status ->
screen-20 Floor, the originally prescribed Floor Action -> Name routes, Items -> Status,
the prescribed Info/seal B returns, admitted Pot `See` entry/return, screen-7 and
screen-20 ordinary Info returns, the direct carried-Item Name histories, all six
prescribed Floor-parent Name returns, equipment entry, the Pot `Put` selector/post-action
replay, and both direct and Items-appended shop Floor/Info cycles produced zero causal
off hits. The nine deeper history/context findings from the grouped pass now have their
own regressions. The two `Put` commit blanks remain intentional because the game visibly
leaves the menu for a dungeon action between them.

The grouped no-Lua visual acceptance procedure, isolated ROM/SRAM staging commands, and
nine exact routes are in
[`ITEM_FLOOR_MANUAL_TEST.md`](ITEM_FLOOR_MANUAL_TEST.md). Generate its uniquely named
fixtures with `python3 tools/prepareitemfloortests.py build/shiren_en.gb`; this never
touches a personal save. That document records the accepted baseline, the implemented
`IFR-01` through `IFR-09` matrix, and the grouped visual acceptance checklist.

### Start-menu LCD-off catalogue

The generated Start table has 17 caller rows. It names each visual path separately even
though most composites share `41:$40E1`.

| Player path | Causal off producer(s) | Status and evidence |
|---|---|---|
| Boot/logo/title presentation -> Start | `29:$411A`; shadows `31:$49B1`, `31:$4AE8`, `31:$4D59`, `31:$4899`, `4:$65F4` | `keep`; pre-interactive hardware/title initialization |
| Adventure -> saved-log summary/log changes | `41:$40E1` | `review`; observed screen 23 composite |
| Select Adventure log -> gameplay | shadows `2:$463C`, `4:$4154` | `keep`; replacement boundary |
| New Log -> selector | `41:$40E1` | `review`; observed screen 22 |
| New Log -> difficulty/explanation | `41:$40E1` | `review`; observed screen 25 |
| New Log -> personal-name keyboard | `44:$4066` | `keep`; independent screen-8/native-font replacement |
| Confirm New Log name -> village | shadow `2:$463C` | `keep`; replacement boundary |
| Copy Log summaries/confirmation | `41:$40E1` | `review`; observed screens 23 and 24 |
| Erase Log summary/confirmation | `41:$40E1` | `review`; observed screens 23 and 24 |
| Rename -> alternate selector | `41:$40E1` | `review`; observed screen 26 |
| Rename -> personal-name keyboard | `44:$4066` | `keep`; same static screen-8 caller as New Log, but an isolated Rename-entry trace is still missing |
| Return from file/Rank child -> Start root | `46:$42B5` | `keep`; complete native-font restoration observed beyond Rankings too |
| Rank/Pass root and Pass selector | `41:$40E1` | `review`; observed screens 30 and 32 |
| Rank category -> Rankings display | `43:$40B6`, `46:$42B5` | `review`; completed map publication plus native-font restoration on screen 33 |
| Fay's Puzzle -> task composite | `38:$408F` | `keep`; independent composite screen |
| Fay task -> gameplay | shadows `2:$463C`, `4:$4154` | `keep`; replacement boundary |
| Replay -> saved-log summary | `41:$40E1` | `review`; focused exhaustive trace observed screen 23; choosing the log produced no additional LCD-off producer before replay handoff |

The normal ending site `59:$406F` belongs to neither menu system and remains in the
instruction census as an intentional new-scene blank. Native `2:$4702` and the remaining
shadow producers likewise stay in the complete TSV; none opened a traced Item or Start
menu interval. This separation prevents non-menu boot, scene, and ending loaders from
inflating the menu worklist while ensuring they are not silently forgotten.

## The display model: there is no general menu z-buffer

Most menu boxes are composited into one 32-cell-stride WRAM shadow tilemap and later
published to the BG map. A later submenu appears to have a higher z value only because it
writes over cells drawn by its parents. The overwritten parent cells are not saved in a
separate layer.

The in-dungeon status panel uses the Game Boy Window and is a genuine separate hardware
layer. Its visible references count too: a BG tile cannot be recycled merely because no
BG cell refers to it if a visible Window cell still does.

| Purpose | Address | Ownership rule |
|---|---:|---|
| 20x18 menu shadow, stride 32 | `$C300-$C53F` span | Modify by exact visible cells; never clear the 12-byte row tails as map data |
| Visible BG map used by these menus | `$9800` base | Visible cell `(x,y)` is `$9800 + $20*y + x` |
| Corresponding shadow cell | `$C300` base | Shadow cell `(x,y)` is `$C300 + $20*y + x` |
| Alternate BG map | `$9C00` base | Translation title/Rankings code clears and uses it as a blank map; it is not a general free buffer |
| Menu upload scheduler | `$C006`, selector `$C11A` | Drain it before changing map ownership; do not bypass it with long LY busy-waits |
| VWF row scratch | `$C0CC-$C0DD` | Translation-owned while the menu renderer is active |
| VWF row records | `$C163-$C1B2` | Five-byte keyed records plus proportional metadata; ownership is per rendered row |
| Synchronous transition state | `$C1B3` | Translation-owned byte; values are listed below; `$08-$0C` own exact Info/Pot families, `$0D-$0F` own carried-Item Name returns, `$15` owns all Items-appended Floor Name returns, and `$16` owns the Pot Put selector |
| Shared Action/Item transition state | `$C1B4-$C1B6` | Held-Action row count and packed Item state; screen-1 Info return records child screen 4/5 in `$C1B4`, while screen-20 and screen-7 returns preserve their Action heights there. During exact Item paging `$C1B4` is instead the four-slice tile-copy counter, `$C1B5` marks an Items/Floor header change after the final body row, and `$C1B6` is the page phase (`2` body, `4` replacement header, `3` redraw tail). Direct screen-20 Action mode 4 owns the exact `$C1B5/$C1B6=$20/$04` pair while its top verb remains live; Name entry consumes and clears that pair. Screen 1 retains admitted Info/seal value `1`, then uses `2` only after complete empty return chrome is published. An exact Items-to-Status pop retires phase `3` because the initial Items build has no same-screen redraw-tail call; no later Floor child may inherit that dead transaction. An exact screen-20 child accepts idle `0` or stale carried-Action value `1` and clears it before publication; screen 7 uses `2` only after its independent empty parent chrome publishes. The lifecycles are mutually exclusive |
| Standing-item Floor settlement | `$C1B7` | One only after screen 1 selector `$FF` has completed; authorizes its exact live Status pop, then clears |
| Held-Action / Pot-viewer snapshot | `$C1B8-$C1BE` | Seven exact cells saved before box 6 overwrites a carried Item page marker; in the mutually exclusive screen-20 Pot-viewer lifetime, `$C1B8` instead preserves the parent box-39 row count before screen 12/13 reuses `$C6BB` |
| Tile-12 composition buffer | `$C12C-$C13B` | Translation-owned scratch |
| WRAM-staged menu strings | usually `$C616-$C699` | The next draw can replace them; never treat the bytes as persistent row ownership |
| Active box descriptor | `$C69A-$C6A0` | Seven bytes: x, y, rows, width, flags, text pointer |
| Current screen ID | `$C6A3` | Also used by shared handlers to choose different boxes |
| Cursor home | `$C6A7/$C6A8` | Offset from `$C300`, loaded from the screen table at `4:$4E6E` |
| Dynamic row count | `$C6BB` | Used when descriptor flag bit 1 is set |

Tile IDs use LCDC's signed `$8800` tile-data selection. IDs below `$80` address
`$9000 + 16*id`; for example `$8B-$9D` wrap to `$88B0-$89D0`. A linear
`$9000 + 16*id` calculation for every ID would write into tilemap memory.

The shadow's address span includes 12 non-visible bytes after each 20-cell row. In the
last row that tail begins at `$C534` and is reused for the menu stack. The native clear at
`4:$480E` deliberately skips every tail. A “full shadow clear” must do the same.

### Dynamic tile budget

The proportional menu allocator has three useful contiguous runs:

| Run | Tiles | Capacity |
|---|---:|---:|
| `$43-$7B` | 57 | primary run |
| `$8B-$95` | 11 | one maximum-width Item row |
| `$9A-$9D` | 4 | short spill run |
| **Total** | **72** | fragmented, not interchangeable with 72 contiguous tiles |

Tile `$87` is isolated and cannot satisfy the minimum four-tile allocation, so it is not
part of the usable budget. English glyph tiles `$40,$41,$42,$7C,$7E,$7F` are reserved and
must never be allocated. Persistent Window tiles, including `$22,$24,$2A,$36`, must also
be excluded from any status-menu reuse set.

Measured residency gives the planning envelope:

| Scenario | Peak capacity owned |
|---|---:|
| Ordinary Status -> Items -> Action route | 32 tiles |
| Largest observed real save state | 50 tiles visible; 54 while building a fresh row |
| Synthetic five 11-tile rows plus four 4-tile action rows | 71 tiles |
| Full outgoing and incoming worst-case Item pages | about 110 tiles |

The last line rules out general double-buffering. It is the reason blanking the outgoing
Item references before recycling their tiles is the first design.

## Menu stack and redraw semantics

The menu stack is more important than the apparent visual hierarchy:

- `4:$47E8` initializes stack depth `$C534` to `$FF` and clears ten screen entries at
  `$C535` plus a second ten-byte region beginning at `$C53F`; the second region's exact
  semantics have not yet been named.
- `4:$4DDC` pushes a screen: it stores the ID in `$C6A3`, increments `$C534`, and stores
  the ID at `$C535 + depth`. A per-screen table at `4:$4E08` can initialize selection
  state.
- `4:$4857` removes a requested number of levels. It clears the visible 20 columns of
  all 18 rows in the **shadow** map, then calls `4:$487C`.
- `4:$487C` replays every surviving screen from stack entry zero through the new top.
  It sets `$C6A3` for each dispatcher call and keeps `$C6A6` nonzero during the replay.
- Only after the replay does the caller publish the reconstructed map through `4:$44A2`.

Consequences for regional blanking:

1. Pushing an overlay leaves its parent pixels and map cells live outside the child's
   rectangle.
2. Popping an overlay is not a local erase. The engine reconstructs every surviving
   screen into `$C300`; any retained native publisher can later expose that reconstruction.
3. A transaction is not complete when a desired screenshot first appears. It is complete
   when uploads and native publishers are drained and no replay can restore stale cells.
4. `$C6A3` names the routine currently being replayed, not necessarily the only logical
   screen visible to the player.

## Screen dispatcher catalogue

`4:$48AA` dispatches the screen ID in `a` through 35 little-endian pointers at
`4:$48C3`. “Box” refers to the descriptor catalogue in the next section.

| ID | Handler | Draw responsibility | Box(es) | Confidence |
|---:|---:|---|---|---|
| 0 | `4:$4909` | In-dungeon Status root | 0, 1, 2 | fixture |
| 1 | `4:$4980` | Interactive paged Items list; Items/Floor header selected by context | 4 and 14 or 18 | fixture |
| 2 | `4:$4987` | Inventory item Action picker | 6 | fixture |
| 3 | `4:$4999` | Ground-object confirmation/action popup | 3 | fixture: Trap, Exit, Stairs |
| 4 | `4:$49A7` | Item Info/description screen | 7 | fixture, including multi-page Info |
| 5 | `4:$49F5` | Equipment seals screen | 19 | measured; context-sensitive |
| 6 | `4:$4A4E` | No-items message | 9 | measured |
| 7 | `4:$4A58` | Floor header plus alternate Action picker | 5, 6 | measured/inferred context |
| 8 | `4:$4B02` | Name-entry variant with four-cell field | 10, 12 | fixture via file naming |
| 9 | `4:$4B20` | Name-entry variant with six-cell field | 11, 12 | fixture via Floor `Name` |
| 10 | `4:$4B3E` | No-more-names message | 16 | measured |
| 11 | `4:$4B44` | Item list plus `Which?`, or Floor fallback | 4 and 8, or 18 | measured/inferred route |
| 12 | `4:$4B81` | Pot contents/action list | 15, 17 | fixture |
| 13 | `4:$4BA2` | Alternate Pot contents viewer/selection behavior | 15, 17 | fixture: empty Pot `See` |
| 14 | `4:$4BEC` | Alternate Item list plus `Which?` | 4, 8 | measured/inferred route |
| 15 | `4:$4C15` | Title/start root choices | 23 | fixture |
| 16 | `4:$4987` | Alias of screen 2, inventory item Action picker | 6 | measured |
| 17 | `4:$4C23` | Fay's Puzzle task screen | 30, 31, 32 | fixture |
| 18 | `4:$4928` | Non-interactive Items redraw/helper | 4, 14 | measured/inferred role |
| 19 | `4:$4D72` | No passwords/awards fallback | 38 | fixture |
| 20 | `4:$4A58` | Real Floor item header plus Floor Action picker | 5, 39 | fixture |
| 21 | `4:$4C55` | Continue/New Game, or New Game only | 24 or 51 | fixture |
| 22 | `4:$4C61` | Log selector | 25 | fixture |
| 23 | `4:$4C75` | Save/log summary | 26 | fixture |
| 24 | `4:$4C94` | Confirmation text plus No/Yes | 27, 28 | fixture |
| 25 | `4:$4CAB` | Difficulty picker plus selected explanation | 29 and 46, 48, or 50 | fixture |
| 26 | `4:$4CCA` | Alternate wrapper/redraw of screen 22 | 25 | measured/inferred route |
| 27 | `4:$4CD0` | Hidden debug item-category picker | 33 or 34; optionally 37 | fixture |
| 28 | `4:$4CF8` | Hidden debug item picker | 35 | fixture |
| 29 | `4:$4D07` | Hidden debug enhancement/value editor | 36 | fixture |
| 30 | `4:$4D10` | Rank/Pass choice | 45 | fixture |
| 31 | `4:$4D20` | Rankings category choice | 47 | fixture |
| 32 | `4:$4D2B` | Pass log selector | 49 | fixture |
| 33 | `4:$4D39` | Rankings display | 41 | fixture |
| 34 | `4:$4D4A` | Password/award/clear-condition display | 42, 43, 44 | fixture |

IDs 2/16 and 7/20 share handler addresses deliberately. Screen 7 versus 20 is resolved
by checking `$C6A3`; the same code draws box 6 for 7 and box 39 for 20. A hook that keys
only on the handler address cannot distinguish those lifetimes.

## Box descriptor catalogue

`31:$4055` indexes 52 pointers at `31:$45D5`. Each pointer names a seven-byte descriptor
copied to `$C69A-$C6A0`. `31:$4075` draws the box into `$C300`; `31:$40D8` draws one row.
The descriptor width is the number of interior cells, so the left and right borders occupy
`x` and `x + width + 1`. Selectable list rows are commonly two tilemap rows apart; do not
derive a blanking mask from descriptor `rows` alone. Measure the physical row keys.

The catalogue below records the current English build. Several widths and high flag bits
differ deliberately from the base ROM.

Established native flag meanings are bit 1 = take row count from `$C6BB`, and bit 2 =
draw an extra separator before the bottom border. Higher bits are used by translation
rendering and must be interpreted through the current build, not the base drawer alone.

`WRAM` sources are volatile staging. A ROM-looking address below `$8000` is in bank 31
while the drawer is mapped unless its call site proves otherwise.

| Box | Descriptor | x,y | Rows | Width | Flags | Text source | Role |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | `$41C2` | 0,0 | 3 | 5 | `$02` | `$C616` | Status choices |
| 1 | `$41C9` | 7,0 | 3 | 11 | `$44` | `$43B5` | Gitan / Floor / Path status |
| 2 | `$41E2` | 0,10 | 2 | 18 | `$04` | `$41E9` | Weapon/Strength and Shield/Experience |
| 3 | `$4205` | 3,4 | 2 | 6 | `$00` | `$C616` | Ground-object popup |
| 4 | `$420C` | 0,3 | 5 | 18 | `$02` | `$C616` | Items list |
| 5 | `$4213` | 0,0 | 1 | 18 | `$20` | `$C616` | Floor item header |
| 6 | `$421A` | 13,1 | 7 | 5 | `$02` | `$C616` | Inventory/alternate Action picker |
| 7 | `$4221` | 0,3 | 5 | 18 | `$00` | `$C616` | Item Info |
| 8 | `$4228` | 0,0 | 1 | 4 | `$70` | `$42CD` | `Which?` header |
| 9 | `$4235` | 0,6 | 1 | 18 | `$40` | `$423C` | No items held |
| 10 | `$424C` | 7,0 | 1 | 4 | `$04` | `$C6E3` | Short name field |
| 11 | `$4253` | 6,0 | 1 | 6 | `$04` | `$C6E3` | Long name field |
| 12 | `$425A` | 0,3 | 6 | 18 | `$04` | `$4261` | Name-entry keyboard |
| 13 | `$42D4` | 0,3 | 6 | 18 | `$04` | `$4261` | Alias keyboard descriptor |
| 14 | `$434F` | 0,0 | 1 | 4 | `$50` | `$422F` | Items header |
| 15 | `$435C` | 0,3 | 5 | 18 | `$02` | `$C616` | Pot contents list |
| 16 | `$4363` | 0,6 | 1 | 18 | `$40` | `$43DC` | No more names |
| 17 | `$437E` | 0,0 | 1 | 3 | `$60` | `$434C` | Pot header |
| 18 | `$4389` | 0,0 | 1 | 4 | `$50` | `$4356` | Floor header |
| 19 | `$4395` | 0,3 | 5 | 18 | `$00` | `$C616` | Equipment seals |
| 20 | `$439C` | 0,0 | 2 | 6 | `$00` | `$44BB` | Close/Quit |
| 21 | `$43AE` | 0,0 | 3 | 6 | `$00` | `$41D0` | Close/Exit/Quit |
| 22 | `$43C7` | 0,3 | 1 | 8 | `$00` | `$C616` | Context line/prompt |
| 23 | `$43CE` | 0,1 | 3 | 11 | `$02` | `$C616` | Title/start choices, dynamic 3-8 rows |
| 24 | `$43D5` | 3,4 | 2 | 10 | `$40` | `$436A` | Continue/New Game |
| 25 | `$43EF` | 5,9 | 3 | 9 | `$02` | `$C616` | Log selector |
| 26 | `$43F6` | 4,4 | 3 | 14 | `$04` | `$C616` | Save summaries |
| 27 | `$43FD` | 3,7 | 2 | 15 | `$00` | `$C616` | Confirmation prompt text |
| 28 | `$4404` | 11,2 | 2 | 4 | `$40` | `$440B` | No/Yes |
| 29 | `$4414` | 12,6 | 3 | 6 | `$50` | `$4453` | Difficulty choices |
| 30 | `$442E` | 0,0 | 1 | 18 | `$00` | `$441B` | Fay header/composite |
| 31 | `$4445` | 0,3 | 5 | 18 | `$04` | `$C616` | Fay tasks |
| 32 | `$444C` | 0,15 | 1 | 18 | `$40` | `$448F` | `Which task?` prompt |
| 33 | `$4467` | 0,0 | 5 | 6 | `$50` | `$432C` | Debug categories page 0 |
| 34 | `$4488` | 0,0 | 5 | 6 | `$50` | `$42E5` | Debug categories page 1 |
| 35 | `$44A6` | 4,0 | 4 | 14 | `$00` | `$C616` | Debug items |
| 36 | `$44AD` | 6,13 | 1 | 5 | `$00` | `$C616` | Debug value/enhancement |
| 37 | `$44B4` | 0,14 | 1 | 18 | `$00` | `$4435` | Pack full |
| 38 | `$44CA` | 3,9 | 1 | 13 | `$40` | `$43A3` | No awards/passwords |
| 39 | `$44E2` | 13,3 | 7 | 5 | `$02` | `$C616` | Real Floor Action picker |
| 40 | `$44E9` | 0,13 | 1 | 8 | `$00` | `$C616` | Context line/prompt |
| 41 | `$44F0` | 5,0 | 1 | 8 | `$40` | `$44D1` | Rankings header |
| 42 | `$4503` | 4,0 | 1 | 10 | `$00` | `$C616` | Password/award header |
| 43 | `$450A` | 7,3 | 1 | 4 | `$00` | `$C616` | Password field/short value |
| 44 | `$4511` | 0,6 | 5 | 18 | `$00` | `$C616` | Awards/clear conditions |
| 45 | `$4518` | 3,8 | 2 | 6 | `$02` | `$C616` | Rank/Pass |
| 46 | `$451F` | 0,13 | 2 | 18 | `$40` | `$4526` | Easy explanation |
| 47 | `$4542` | 5,7 | 2 | 10 | `$50` | `$446E` | Rankings category |
| 48 | `$4560` | 0,13 | 2 | 18 | `$40` | `$4567` | Normal explanation |
| 49 | `$4590` | 5,9 | 1 | 9 | `$02` | `$C616` | Pass log selector |
| 50 | `$4597` | 0,13 | 2 | 18 | `$40` | `$430B` | Hard explanation |
| 51 | `$45C3` | 3,4 | 1 | 10 | `$40` | `$449C` | New Game only |

## Transition ownership classes

Every route must be assigned one of these classes before a blanking implementation is
chosen:

| Class | What happens | Examples | Default policy |
|---|---|---|---|
| Page replacement | Same logical screen, same surrounding chrome, owned rows change | Items Left/Right; Info page change | Regional candidate |
| Overlay push | Child overwrites part of live parent; parent remains visible elsewhere | Item Action, confirmation, Rank/Pass | Blank only proven child/intersection cells; retain all parent owners |
| Stack pop/replay | Shadow is cleared and every surviving parent is redrawn | Info/Action cancel and many Back paths | High risk: intercept the final replay publication, not merely the top box |
| Composite redraw | Several boxes together form the apparent screen | Title plus log/difficulty windows; Fay; Rankings | Keep atomic policy until the full composite's owners and completion hook are known |
| Replacement screen | Menu is abandoned for Map, gameplay, dialogue, name entry, replay | Map, Quit, Take, Toss, Replay | Preserve native whole-screen transition; regional blanking has no benefit |

This classification supersedes the shorthand “higher z.” Two boxes can overlap in the
same BG map without being separate layers, while the status Window can be a separate layer
even when it looks like part of one screen.

## Start/title menu system

The player-facing outline is retained here, annotated with what has been tied to the
dispatcher. Indentation means a retained/composite parent unless a replacement is stated.

```text
Title/start root                                            screen 15
|-- Adventure
|   `-- saved-log summary                                  screen 23
|       `-- Continue / New Game                            screen 21
|           `-- gameplay/status                            replacement; screen 0 later
|-- New Log                                                outline
|   `-- log selection                                      screen 22 or 26
|       `-- difficulty + explanation                       screen 25
|           `-- name entry                                 replacement; screen 8 variant
|-- Copy Log                                               outline + fixture coverage
|   `-- source/target log selection                        screens 22/26
|-- Erase Log                                              outline + fixture coverage
|   `-- log selection
|       `-- prompt + No/Yes                                screen 24
|-- Rename                                                 outline + fixture coverage
|   `-- log selection
|       `-- name entry                                     replacement; screen 8 variant
|-- Rank/Pass                                              screen 30
|   |-- Rank category                                      screen 31
|   |   `-- Rankings                                       replacement/composite, screen 33
|   `-- Pass log selection                                 screen 32
|       `-- password/award/conditions                      replacement/composite, screen 34
|           `-- no-password fallback                      screen 19 when applicable
|-- Replay                                                 replacement into gameplay replay
|-- Fay's Puzzle                                           screen 17
|   `-- selected task enters gameplay/status               replacement; screen 0 later
```

Measured dispatcher sequences include:

- Adventure load: `15 -> 23 -> 21 -> 0`; moving among logs can redraw screen 23 more than
  once.
- Pass/award route: `15 -> 30 -> 32 -> 34`.
- Fay route: `15 -> 17 -> 0` after task selection.
- Copy, Erase, New, and name flows are exercised pixelwise by the current fixtures, but
  their complete dispatcher edge logs should be added before regional work targets them.

Title/file screens are composites. A child can borrow tile planes while title rows remain
visible, and returning can restore native planes. Current translation states `$10-$14`
protect these transactions; they are not candidates for the first regional checkpoint.
The atomic screen-15 publisher finishes before the native cursor initializer at
`4:$4E2B`. The translation therefore pre-stages cursor tile `$81` at
`$C341 + 64*$C6A5`; `tools/startspill.py` checks both that shadow cell and the first
published `$9841 + 64*$C6A5` BG cell, rather than accepting only the later settled menu.

## In-dungeon Status menu system

The established root is screen 0:

```text
Status                                                     screen 0
|-- Items                                                  screen 1, paged
|   |-- standing-item Floor page                           screen 1, selector $FF; appended after carried pages
|   |-- Action                                             screen 2 or 16
|   |   |-- Info / equipment seals                         screens 4/5, possibly paged
|   |   |-- Name                                           screen 9 in the measured route
|   |   |-- Pot contents / actions                         screens 12/13 by context
|   |   `-- gameplay dialogue/effect                       replacement by verb
|   `-- Left / Right                                       screen 1 regional redraw implemented
|-- Floor                                                  screen 20
|   |-- Action                                             box 39 within screen 20
|   |-- Info / equipment seals                             screens 4/5, possibly paged
|   |-- Name                                               screen 9
|   |-- Swap                                               returns through Items/replay
|   `-- Take / Wave / Toss / Put / Push / etc.             replacement by verb
|-- Map                                                    replacement screen
`-- Quit                                                   replacement to gameplay dialogue

Other context routes
|-- ground Trap / Exit / Stairs confirmation               screen 3
|-- equipment seals                                        screen 5
|-- no-items/no-more-names                                 screens 6/10
|-- Which? selectors                                       screens 11/14
`-- hidden debug categories -> items -> value              screens 27 -> 28 -> 29
```

Representative real fixture sequences:

| Route | Dispatcher sequence | What it establishes |
|---|---|---|
| Status to Items/action/Info | `15,23,21,0,1,2,4` | Inventory Info is a child of paged Items and Action |
| Screen-1 Info return | `...,0,1,2,4,(4),0,1` | Info page changes keep screen 4; either exit removes screens 4 and 2, then replays the exact Status and Item/Floor parent |
| Identity-hidden item | `...,0,1,1,2,4` or `...,0,1,1,1,2,4` | Screen 1 can redraw repeatedly before Action |
| Floor Info, two pages, Back | `...,0,20,4,4,0,20` | Info paging plus stack replay of Status and Floor |
| Gitan Info, Back | `...,0,20,4,0,20` | Three-choice Floor Action uses the same return lifecycle |
| Storage Pot Info, Back | `...,0,20,4,0,20` | Six-choice action geometry reaches the same lifecycle |
| Empty Pot `See` | `...,0,20,13` | Screen 13 is a real Pot viewer route |
| Unidentified Pot Info, Back | `...,0,7,4,0,7` | Seven-row hidden-Pot Floor uses an independent screen-7 regional lifecycle; state `$0B` survives screen 0 until the exact parent publishes |
| Items-appended Floor, seven-row Action, `See`, Back | `...,0,1,2,12/13,0,1` | Paging to Floor does not enter screen 7: it retains screen 1, pushes screen 2, and returns to that exact parent through state `$08` |
| Ground Trap/Exit/Stairs | `...,0,3` | Screen 3 is the real two-choice ground popup |
| Hidden debug picker | `...,0,1,27,(27),28` then `29` | Debug screens are reachable from an Items context |

The complete global action-verb inventory is deliberately not declared from these traces:
Floor, Pot-content, shop, Gitan, trap, stair, and debug contexts stage different lists.
Checkpoint 3 uses the narrower, fully enumerated carried-Item plus settled standing-Floor
scope below.

## Checkpoint-3 exact scope: screen-1 Item/Floor Action overlay

Checkpoint 3 changes one screen-2 overlay lifecycle over two exact screen-1 parent forms:

```text
Status screen 0 -> Items screen 1 (page 1, 2, 3, or 4)
                -> Action screen 2 / box 6
                -> B cancel -> the identical Items page and selection

Status screen 0 -> Items screen 1 -> standing-item Floor selector $FF
                -> Action screen 2 / box 6 (`Take / Fire / Swap / Info` for Wood Arrow)
                -> B cancel -> the identical settled Floor page
```

This is not shorthand for every menu containing an action verb. The admission predicate
must prove the direct `0,1,2` stack, screen 2, either an ordinary held-inventory selection
below `$C6AA` or selector `$FF` with the independently proven Floor settlement latch, the
standard menu viewport, and no shop-price context.
Screen 16 calls the same `4:$4987` handler but has no established button-driven route; it
remains conservative until such a trace exists.

`mgbdis` confirms the native builder at `30:$7D3C-$7DD1`. Its pointer table at
`30:$7DD2` selects three separate 11-category verb tables: held inventory at `$7DE8`,
Floor at `$7E14`, and Pot contents at `$7E40`. Checkpoint 3 admits the held table and only
the settled standing-item screen-1 route into the Floor table. The
held suffix at `$7DD8` adds `Drop`, optional `Name`, and `Info`; the separate Floor suffix
at `$7DE0` adds `Swap` instead. Other Floor-table callers remain out of scope. An
exhaustive item-ID census of the held table establishes these visible box-6 variants:

| Held item/state | Item IDs | Box-6 rows |
|---|---|---|
| Weapon, Shield, or Bracer | `$00-$33` | `Equip / Toss / Drop / Info` |
| Equipped Weapon, Shield, Bracer | `$00-$33`, equipped | `Remove / Toss / Drop / Info` |
| Arrow | `$34-$36` | `Equip / Fire / Drop / Info` |
| Equipped Arrow | `$34-$36`, equipped | `Remove / Fire / Drop / Info` |
| Food or known Herb | `$37-$54` | `Eat / Toss / Drop / Info` |
| Known Scroll | `$55-$6F` | `Read / Toss / Drop / Info` |
| Known Staff | `$70-$7B` | `Wave / Toss / Drop / Info` |
| Put-style Pot | `$7C-$80,$82-$84,$86-$87` | `See / Put / Toss / Drop / Info` |
| Push-style Pot | `$81,$85,$88-$89` | `See / Push / Toss / Drop / Info` |
| Any identity-hidden Bracer, Herb, Scroll, Staff, or Pot | corresponding range | insert `Name` immediately before `Info` |

The ordinary picker therefore has four rows for most known items, five for a known Pot
or an identity-hidden non-Pot, and six for an identity-hidden Pot. Those heights and both
`Equip -> Remove` substitutions are part of checkpoint-3 acceptance, not optional edge
cases. The builder also emits `Toss / Drop / Name / Info` for rare IDs `$8A-$8E` and
`Toss / Drop / Info` for `$8F-$90`, but a genuine carried-item route has not established
those as checkpoint admission cases; forced records may enumerate output but cannot prove
screen ownership.

### What changes in checkpoint 3

- Opening screen 2 retains the native overlay publication. Its proportional verb rows use
  six private four-tile slices only after proving that neither visible parent layer refers
  to those tiles; no opening blank is needed and the Item page outside box 6 remains live.
- Moving the Action cursor from first to last row and back must not redraw or blank either
  parent or overlay.
- B-cancel regionally retires box 6 and reconstructs the exact covered cells from the same
  Item or standing-Floor page. It must restore the original page number/selector,
  selected row, page marker or Floor box edge, Item names, equipment markers, borders,
  and Window without a full-screen blank.
- The contract applies independently to pages 1, 2, 3, 4, and the settled `$FF` Floor
  parent. Passing on page 1 cannot authorize any other parent.

### What does not change in checkpoint 3

- Selecting `Eat`, `Read`, `Wave`, `Equip`, `Remove`, `Fire`, `Toss`, or `Drop` may replace
  the menu with gameplay/effect handling; its native transition remains authoritative.
- `Info` to screen 4 and back is checkpoint 4. `Name` to screen 9 is a separate ownership
  epoch. Selecting a Pot's `See`, `Put`, or `Push` and any following selector/content
  screen is deferred with the Pot lifecycle.
- Floor screen 20/box 39, Pot screens 12/13, shop-priced/`Tag` variants, ground popup
  screen 3, debug screens 27-29, and the untraced screen-16 alias retain their current
  full-map-safe paths.

### Implemented ownership transaction

The exact screen-2 row-0 gate requires state `$00`, current screen/depth `$02`, stack
`0,1,2`, a valid selector within a 1-20-item inventory or `$FF` with `$C1B7=$01`,
`$C6DE=$00`, and the standard LCD/scroll/Window configuration. It then scans visible BG
rows 0-15 and Window rows 0-1.
Any reference to `$C7-$DE` rejects the private path; this also rejects shop Item pages
structurally because their price rasters occupy `$D0-$DE`.

An admitted Action picker assigns verb row `r` the fixed four-tile slice
`$C7 + 4*r`, for `r=0..5`. Thus the largest six-row picker owns exactly `$C7-$DE` and
cannot exhaust or alias the 72-tile Item-page allocator. One native history exceeds that
private capacity: paging from Items to the appended Floor page while standing on an
identity-hidden Pot produces the seven-row `Take / See / Push / Toss / Swap / Name / Info`
screen-2 picker. Its first six rows retain `$C7-$DE`, while the final `Info` row returns
to the ordinary collision-safe base run at `$43`. The protected pool deliberately does
not extend into `$E0+`, which is owned by the difficulty renderer. The opening draw, box chrome,
cursor writer, and final map publication remain native; the new work is lifetime proof
and disjoint raster allocation, not a replacement overlay renderer.

The Action admission hook snapshots the exact seven-cell Item page-marker/top edge from
shadow `$C36D-$C373` into translation-owned `$C1B8-$C1BE` and saves the retained Item
record count in `$C1B5`'s high three bits before box 6 publication. The low five bits hold
the carried selector or sentinel `$1F` for the settled Floor parent. The B handler at
`4:$5689` reaches the generic pop arithmetic with `HL=$5689`; the hook at
`4:$485A-$4861` preserves that arithmetic for every caller and arms state `$07` only for
this exact call site and admitted screen-2 stack. While that pre-pop proof is still live,
it reconstructs the covered parent in shadow: rows 1-2 are truly empty, the saved row 3
restores the complete page marker or Floor top edge, and retained Item VWF records restore
any name tails at x=13..18 plus the native right/bottom borders. For `$FF`, the first
separator is the Floor box bottom and all later covered rows are true blank field. It then
drains the VWF queue, enters a fresh VBlank, and copies that completed parent only to box
6's physical footprint:

```text
BG start $982D = (x=13, y=1)
width             7 cells, x=13..19
height            2 * verb_rows + 1
four rows         y=1..9
five rows         y=1..11
six rows          y=1..13
```

Once the parent is visible, the helper restores the retained Item-record count, row shape,
cursor limit/position/base, exact Item/Floor descriptor, and current screen state. Carry
returns to the patched bytes at
`4:$485D`, which jump directly to the existing pop epilogue at `4:$4878`. The generic
shadow clear, screen-0 Status reconstruction, screen-1 Item reconstruction, and final map
copy are therefore skipped only for this already-complete transaction. That replay was
the source of the roughly 40-frame input stall after the screen looked settled. The exact
route now returns from the B handler two frames after the press, and a post-release D-pad
press is accepted normally. If any proof or restore fails, carry remains clear and
execution falls through at `4:$4862` to the unchanged conservative native replay.

This direct return is safe because Action uses disjoint `$C7-$DE` rasters, its admission
preserves the Item VWF records, and the restorer makes both shadow and visible box-6 cells
match their Item/Floor parent before the jump. The page number or Floor selector, cursor,
borders, equipment markers, all cells outside the footprint, and the hardware Window
retain their existing owners.

ROM/WRAM ownership for this checkpoint is:

| Owner | Range / value | Responsibility |
|---|---|---|
| Bank 37, far `$05` | `$405A-$4104` | live-layer admission, collision scan, and Item/Floor page-edge save dispatch |
| Bank 61, far `$07/$09` | `$405A-$40EF` | private Action-row allocator plus register-transparent initial screen-15 cursor staging |
| Bank 62, far `$07` | `$405A-$4314` | exact box-6 Item/Floor parent and screen-1 machine-state restorer |
| Bank 60, far `$0D` | `$422E-$429E` | exact generic-pop proof and direct-return dispatch |
| `$C1B4` | four through seven | retained box-6 verb-row count; temporarily four per tile during an exact Item-page upload |
| `$C1B5` | `rrr ii iii` | retained Item record count in bits 7-5 plus selector in bits 4-0; `$1F` means the Floor parent |
| `$C1B6` | zero through four | zero idle, one private Action-pool admission, two live Item-page transaction or checkpoint-4 completed return chrome, three completed Item page awaiting redraw tail, four replacement Item/Floor header pending |
| `$C1B7` | zero or one | completed standing-item Floor page; authorizes only its proven Status pop, paging shape change, or screen-2 Action parent |
| `$C1B8-$C1BE` | seven tile references | saved Item page-marker/top edge under box 6 |

`tools/actionmenuspill.py` boots the real four-page Dragon's Maw inventory independently
for five full-inventory paths: page-1 `Equip`, page-1 equipped `Remove`, page-2 hidden
Bracer with five rows, page-3 `Eat`, and page-4 hidden Pot with six rows. Four additional
exact short-page shapes cover one through four pages and retained record counts below
five. Every run moves the Action cursor first-to-last-to-first, B-cancels, then immediately
moves Down and Up on the returned Item page. It verifies the exact `0,1,2` admission, all
private tile bases and both bitplanes, one `HL=$5689` pop, one VBlank parent restore, no
post-B Status/Items replay, B-handler return within two observed frames, accepted D-pad
input within two observed frames, no blank/mixed/unowned footprint, an immutable Window,
the identical final Item page/selector and menu-machine state, and zero LCD-off or
all-white frames. `menuspill.py --long` independently forces 11-tile Item rows so the
covered nonempty VWF tail reconstruction is exercised.

`tools/flooractionspill.py` independently traverses all four carried pages to the settled
Wood Arrow Floor page, opens its real four-row `Take / Fire / Swap / Info` box, and
B-cancels. It requires one private-pool admission, one `HL=$5689` pop, one exact parent
restore ending in VBlank, no screen/row replay, the exact settled Floor map and machine
state at return, a two-frame B return, and acceptance of the first subsequent Left input
in one frame. LCDC bit 7 remains set and no sampled frame is all-white.

`tools/unidentifiedflooractionspill.py` drives the bundled Log-3 save without Lua through
the distinct `Status -> Items -> Right -> Floor` history. It proves stack `0,1,2`, the
seven-row descriptor, allocations `$C7/$CB/$CF/$D3/$D7/$DB/$43`, and plane-exact text for
all seven verbs. Its Info variant additionally proves that visible BG and shadow rows
14-15 are blank before `-Unknown-` reuses `$43`; this prevents the former `-Unkr` raster
from appearing through the mapped seventh Action row beneath the Info box. Both Info and
`See` B returns require state `$08` to restore the byte- and pixel-exact screen-1 Floor
parent. The `See` variant excludes only the separately catalogued complete-screen viewer
entry interval; LCDC bit 7 remains set throughout every owned paging, Action, Info, and
return interval.

The complete `build.sh` battery passes with this controller in the final ROM. That
includes both Item-page cadences, synthesized one- through four-page inventories, direct
entry/exit, held Action-to-Info and Name entry, Floor/Info, Pot/Info and Pot Put, the
seven-row out-of-scope Pot picker, shop prices, debug menus, and all start-menu composites.
This is automated regression completion, not manual visual acceptance.

### Frozen manual visual acceptance paths

1. On each of Item pages 1, 2, 3, and 4, open one screen-2 picker, move its cursor to the
   last row and back, then press B. Confirm the surrounding Item page never disappears
   and the same page/selection returns.
2. Separately inspect a four-row known item, a four-row equipped item showing `Remove`, a
   five-row known Pot or identity-hidden non-Pot, and a six-row identity-hidden Pot.
3. For the Pot representatives, stop after B-cancel. Do not select `See`, `Put`, or `Push`
   when judging checkpoint 3; those descendants are deliberately unchanged.
4. Optionally select one gameplay-bound verb only to confirm its existing transition was
   not broken. A full-screen blank on that replacement path is not a checkpoint-3 defect.
5. From PUSH START, open the initial title menu and confirm its cursor is already beside
   Adventure before any D-pad input.
6. While standing on an item with four carried pages, page right from page 4 to the
   appended Floor page. Confirm there are no vertical borders below its single item box,
   then press B and confirm Status replaces it without a full-screen blank.

### Checkpoint-3 acceptance record

Checkpoint 3 was frozen on 2026-08-25 against implementation commit `34a20ec`. The full
`build.sh` battery passed, and manual playtest accepted paging, Start-sort, both directions
of the carried-Items/Floor boundary, live Floor-to-Status, the first title-menu cursor,
all scoped Action overlay heights, prompt B-cancel, and immediate post-cancel input.

`mgbdis` supplied control-flow facts, not visual timing. Most importantly, the Japanese
base-ROM handlers at `4:$7339` and `4:$7354` update `$C6AC` and immediately invoke the
stack redraw at `4:$483E`; neither handler reads visible page-indicator cells
`$986F-$9872`. That disproved the translation-added indicator veto responsible for rare
state-`$06` full-screen fallbacks. Disassembly also established the real `$FF` Floor
selector, screen/box dispatchers, the box-6 verb-table split, and the exact
`HL=$5689` Action pop call site used to narrow the direct return.

Runtime fixtures supplied the facts that code alone could not prove:

- `itempagespill.py` showed that removing the false veto exposed slow proportional
  composition rather than an ownership failure. Holding rows 0-3 unreferenced and
  committing all five Item bodies plus the page indicator at final row 4 changed the
  visible sequence to complete old page, complete regional blank, complete new page.
- Rapid-cadence and synthesized-inventory fixtures showed that ordinary carried-page
  paging could be fast, while the one-row Floor/five-row Items shape boundary had to stay
  serialized to prevent overlapping input and corrupted chrome.
- `actionmenuspill.py` showed that the visually complete Item parent remained input-locked
  because native B-cancel replayed unpublished Status and Items screens. Exact footprint
  reconstruction plus direct restoration of screen-1 state removed that replay and its
  roughly 40-frame stall.
- `flooractionspill.py` proved that the same direct return is safe for selector `$FF` only
  with the independent settlement latch: B returns in two observed frames, the following
  Left input is accepted in one, and no sampled frame disables the LCD or becomes white.

The reusable engineering lesson is to use static disassembly to establish native control
flow and state producers, then use frame-level fixtures to establish ownership lifetime,
publication order, VBlank timing, and responsiveness. Neither evidence source replaces
the other.

## Checkpoint-4 accepted scope: Item/Floor Info and Pot entry/return

**Visual status:** accepted on 2026-08-30 against ROM SHA-256
`3eca647016f1b78df6be91925d5ec145ab548a288685cdb1ac30e99e23bd5983`. The initial build
prevented LCD-off and structurally mixed frames, but left the large Info box empty for
roughly 9-14 frames on entry/page changes. Screen 1 retains its reviewed box-first
publisher. Screen 20 now follows a different lifetime rule: its Action box remains until
complete Info chrome and row zero replace it together, and later pages preserve complete
old rows while publishing complete new rows. No captured page has an empty body or a
partial row.
The Pot contents-viewer lifetime is separate: carried, Items-appended Floor, alternate
screen-7 Floor, and screen-20 Floor entries now share rendering machinery only after an
exact stack-specific admission proof. Carried returns still use their independent
two-level pop and mixed-title regression gate.

Checkpoint 4 first changes the `Info` descendant of the screen-2 Action overlays admitted
by checkpoint 3. It does not broaden screen-2 Action ownership. The exact parent stack is
`0,1,2`, where screen 1 is either a carried-Items page or the independently settled
standing-item Floor page. Selecting ordinary `Info` pushes screen 4; equipment with seals
uses screen 5, producing `0,1,2,4/5`.

The same regional Info machinery separately admits the independent screen-20 Floor
picker. Its exact stack is `0,20,4/5`; it preserves selector `$FF`, ground-context bit 0,
the real 3-7-row box-39 descriptor, and returns to screen 20 rather than screen 1. A third
narrow path independently admits the screen-7 identity-hidden ground-Pot stack `0,7,4`.
It requires ordinary Info screen 4, selector `$FF`, ground context, and exactly seven
Action rows; it does not borrow screen 20's box geometry. A fourth narrow path covers
carried Pot `See`: screen 12 or 13 sits above the screen-2 Action
parent, so B removes both children and regionally reconstructs Items from stack
`0,1,2,12/13`. A fifth exact path covers ground-Pot `See` above alternate screen 7:
its one-level `0,7,12/13` pop shares only screen 7's already-proven chrome-first parent
replay.

The changed player-facing paths are:

```text
Status -> Items page 1, 2, 3, or 4 -> carried item -> Action -> Info
       -> B from any Info page -> identical Items page, selection, and cursor

Status -> Items -> standing-item Floor page -> Take / Fire / Swap / Info -> Info
       -> B from any Info page -> identical standing-item Floor page and cursor
       -> A/Up/Down/Left/Right through the final Info page
       -> identical standing-item Floor page and cursor

Status -> Items -> standing-item Floor page -> seven-row unidentified-Pot Action -> See
       -> regional clear -> empty Pot chrome -> Pot screen 12 or 13 text -> B
       -> identical screen-1 Floor page and cursor

Status -> Floor screen 20 -> standing weapon/shield/pot/etc. -> Action -> Info or seals
       -> B from any page, or A/D-pad through the final page
       -> identical screen-20 full-width title and 3-7-row Action picker

Status -> Floor screen 20 -> standing Storage Pot -> Action -> See
       -> regional clear -> empty Pot chrome -> Pot screen 12 or 13 text -> B
       -> complete empty box-5/box-39 chrome -> identical Floor/Action parent

Stand on an unidentified Pot -> Status -> alternate Floor screen 7
       -> seven-row Action -> Info -> B
       -> identical screen-7 full-width title and y=1 seven-row Action picker

Stand on an unidentified Pot -> Status -> alternate Floor screen 7
       -> seven-row Action -> regional clear -> empty Pot chrome
       -> Pot screen 12 or 13 text -> B
       -> complete empty screen-7 chrome -> identical Floor/Action parent

Status -> Items -> carried Pot -> Action -> region blank -> empty Pot chrome
       -> Pot screen 12 or 13 text
       -> B -> complete empty Items boxes -> identical Items page and cursor
```

All checkpoint-3 admitted carried Action heights are in scope: ordinary four-row,
identity-hidden five-row, and identity-hidden Pot six-row boxes. Their verb rows and
opening overlay remain checkpoint-3 behavior; checkpoint 4 begins only when their final
`Info` row or carried-Pot `See` row is selected. Screen-20 box 39 is admitted only
through its independent exact stack and supports the measured 3-7-row descriptor
domain. Pot screens 12/13 are admitted on exact entry stacks `0,1,2,12/13`,
`0,7,12/13`, or `0,20,12/13`; carried B-pop remains an independent two-level proof.
The alternate unidentified-Pot Floor
parent at screen 7 is admitted only for its exact seven-row `0,7,4` ordinary-Info route;
its exact one-level `0,7,12/13` ground-Pot See entry and return are admitted separately. The
Items-appended Floor form is not screen 7: its exact `0,1,2,12/13` B return is accepted
only when the retained Floor latch proves the screen-1 parent, while the same stack plus
the screen-12/13 first-body descriptor admits its entry. Screen-7
seals and shorter or unknown pickers remain excluded. Screen-20 Floor Pot `See` return
is admitted only for its exact one-level `0,20,12/13` stack and saved 3-7-row parent;
the carried-Pot screen-11 `Put` selector is admitted separately. Committing Put is a
gameplay action and intentionally retains the native menu-to-field and field-to-menu
boundaries. The exact contained-item screen-16 Action/Info stack is admitted separately;
`Push`, malformed screen-16 contexts, and forced/unknown Info callers are not.

### Native control flow recovered with `mgbdis`

A fresh sibling `../mgbdis` pass over the matching Japanese ROM was decisive here. The
screen-4 drawer is `4:$49A7`; the same description ownership and pop machinery selects
screen 5 for equipment seals. Its A/D-pad handler at `4:$5926` increments the current
description page at `$C6BC`, synchronously redraws screen 4 through `4:$483E` while another
page exists, and performs the two-level pop after the final page. The B path at
`4:$5691` performs that pop immediately. A, Up, Down, Left, and Right therefore share the
advance/finish behavior; Start and Select do not. At the generic pop hook `4:$485A`, the
preserved `HL` distinguishes the final-page `$5926` exit from the `$5691` B exit.
The input engine feeding that handler is `0:$0501-$06CE`; it synthesizes held-key repeat
through `$FF80-$FF88`. A one-frame Down tap invokes `$5926` exactly once in a comparison
build with Menu VWF disabled. Before correction, the regional redraw crossed the initial
`$14`-frame repeat countdown while `$FF83/$FF87` still retained the consumed Down source
and event, so the same tap re-entered `$5926` on pages 2-5. The exact screen-1 Info
publisher now retires those two input bytes only after the completed page is visible.
The fixture proves one Down tap advances from page 1 to page 2 exactly once, then uses
separate deliberate A presses for the remaining pages.

The native footer writer at `4:$49C4-$49EF` stages current-page tile `$C6BC+2`, slash
`$B0`, and total-page tile `$C6BD+1` at `$C4B0-$C4B2`; their visible counterparts are
BG `$99B0-$99B2`. This exposed a translated ownership collision that two-page fixtures
could not see: Status VWF legitimately repaints low tiles `$04-$0A`, and Fusion Pot's
five-page total uses tile `$06`. The exact Info publisher now restores the current and
total digit rasters from the approved font during VBlank before exposing those native
references. The five-page fixture also caught incorrect first-candidate destinations:
body `$C381` maps to `$9881` and the pager maps to `$99A9/$99B0`, not one row/eight rows
earlier. Native queued publication had eventually covered those writes, masking the
transient contamination in settled screenshots.

Both exits remove screens 4 and 2, changing stack `0,1,2,4` to `0,1`; native replay then
reconstructs screen 0 followed by the exact screen-1 Items/Floor parent. This disproved an
earlier model in which Info merely returned to the Action box. It also explained why
optimizing only screen 4 could still leave a slow or visually unsafe parent replay. The
Japanese handler contains no LCD disable; the full-screen interval was in the English
proportional-text fallback.

That comparison also explains why simply removing the English fallback produced a slow
clear: the Japanese renderer's immutable glyph tiles can leave old map references live
while it prepares the next page. English proportional rows reuse allocator tiles, so an
old reference may visibly mutate as soon as new pixels upload. The screen-20 overlap scan
is the translated equivalent of that lifetime guarantee: retire every old row which
references the incoming allocation, but preserve all rows whose pixels remain valid.

The disassembly of `4:$5691` explains the two different Info returns: it pops two stack
records for ordinary screen-1 Items, but only one when `$C6DE` bit 0 identifies the
screen-20 Floor context. The generic stack remover at `4:$4857` then rebuilds screen 0
before the retained parent. That screen-0 map is disposable in both exact lifecycles and
must never become visible. The screen table identifies the two carried Pot viewers as
screen 12 at `4:$4B81` and screen 13 at `4:$4BA2`; both B paths reach the generic pop with
amount two, removing the viewer and its screen-2 Action parent. Runtime tracing originally
appeared to add the distinguishing ownership fact that screen 12 retained `$C1B6=1`,
whereas screen 13 cleared it. That was fixture-specific. A real five-row
`Egg / Egg / Happy Bracer / Fusion Pot / Manji Kabura` page collides with the private
Action tile run and legitimately reaches screen 12 with `$C1B6=0`. Fresh `mgbdis` of the
corrected build shows the screen-12 gate at `62:$4333-$433A` admitting both zero and one
while rejecting values two and above; screen 13 remains exactly zero. The remaining
stack, screen, selector/count, box-17 shape, context, and hardware checks distinguish the
two-level Pot return. Pot return cannot be treated as an ordinary one-level overlay
dismissal, and Action-pool admission cannot be required of every valid Pot viewer.

Static disassembly established those handlers, stack mutations, and call-site markers.
Runtime hooks were still required to establish which reconstructed screen was actually
visible, when the translated queue drained, and which LCD-off branch was translation-only.
In particular, they found an unknown-return branch in the expanded screen-0 renderer:
screen 0 is only a disposable shadow during this exact two-level replay, so checkpoint 4
returns before that branch can disable the LCD and lets screen 1 remain the sole visible
target.

### Ownership and publication sequence

#### Screen-1 Item/Floor Info

Entry and same-screen Info paging use box 7, `(x=0, y=3, rows=5, width=18)`, whose full
physical rectangle is BG rows 3-13. The owned entry transaction also retires rows 14-15:
ordinary Item/Floor parents leave them empty, while the unique seven-row screen-2 picker
maps its final `Info` label and bottom border there. After proving stack `0,1,2,4`,
screen 4, Action
admission `$C1B6=1`, a valid carried selector or settled `$FF` Floor latch, no shop
context, and the standard viewport/Window state, the controller:

1. drains the native menu upload queue;
2. builds the complete empty Info perimeter in shadow;
3. publishes rows 3-15 as complete 4/4/5-row VBlank batches while keeping the title and
   hardware Window live;
4. composes each proportional row behind the complete box, then publishes that row's
   18-cell interior in the following VBlank (rows are complete, never cascaded by cell);
   and
5. restores the two native low-tile digit rasters from the approved font, then publishes
   the final row plus page arrows/counter together in one VBlank.

The expected visible sequence is `complete old -> complete empty Info box -> complete
row 1 -> ... -> complete Info page`. Multi-page descriptions repeat that same regional
sequence; no partial text row or stale pager is an allowed state. The first completed row
must publish within four emulated frames of the completed chrome; the captured five-page
route displays it after three frames.

On either exit, state `$08` owns the exact parent replay. The completed Info/seal page now
stays visible while native screen 0 is reconstructed in shadow; that disposable screen's
LCD-off publication is suppressed. At the first exact screen-1 body row, immediately
before the parent allocator can reuse any visible Info pixels, the controller retires the
five Info interiors/pager and commits complete empty Items or one-row Floor chrome.
Ordinary screen-4 descriptions retain the exact final-header parent publisher. A carried
screen-5 seal child instead changes state `$08 -> $01` after that chrome commit and hands
the remaining work to the already-proven fast Item-page transaction: its body appears
atomically at the final row, then the native replacement header settles the title and
indicator. Both forms clear their state only after the parent is complete and responsive.

The carried-seal exit therefore contains one bounded regional redraw, not a blank screen:
`complete seal page -> complete empty parent windows -> complete parent`. A disabled LCD,
an empty Info interval before parent construction begins, absent window frames, all-white
frame including the hardware Window, partial border, Status text leaking into the Action
box, wrong pager/page indicator, or delayed cursor/input is a defect.

#### Screen-20 Floor Info and seals

The independent Floor gate proves stack `0,20,4/5`, selector `$FF`, `$C6DE=1`, current
screen 4 or 5, a one-digit page count, the standard viewport/Window configuration, and
box-39 height 3-7. It accepts `$C1B6=0` or a stale value one left by an earlier
gameplay-bound carried Action, then clears it before any Info pixels are published.
Values two through four still reject the exact route because they belong to active Item
transactions. This history distinction matters even when screen 20 has no remaining
private Action-tile references: requiring literal zero sent the valid `0,20,4/5` stack
to the translation-only LCD-off fallback after a Lua-assisted carried-Pot interaction.
Fresh `mgbdis` of the emitted ROM shows the screen-20 comparison at
`62:$45AA-$45B1` accepting only values below two and the admitted entry at
`62:$466D-$4674` clearing the byte before construction; the unchanged conservative
fallback disables LCDC bit 7 at `62:$4452-$4458`.
It deliberately does not use screen 1's complete-empty-Info hold.
On initial entry, the shared Action-label references retire while the complete small
Action box remains. A short proportional row uploads through four-byte HBlank slices;
complete Info chrome and row zero then replace the Action box in one VBlank.

For a later page, the allocator's incoming tile interval can overlap references in any
of the five outgoing text rows. Immediately before upload, the controller scans all five
visible interiors, forms an overlap mask, and retires every selected interior as a whole
row in one VBlank. Unaffected outgoing rows remain. The incoming row is then uploaded
and published through safe LCD-access slots in the same displayed frame. The result is a
row-wise `complete old -> old/new mix -> complete new` transition with at least one text
row always present; there is no complete empty Info page and no LCD disable. The final
row still publishes with the native arrows and page counter atomically.

On exit, state `$09` retires the visible Info references and skips the disposable
screen-0 reconstruction. Before any Floor text is visible, it clears the screen-20
shadow and builds the exact empty parent: full-width box-5 title plus box 39 using the
saved native Action height. When the descriptor's actual final row arrives, ownership is
released to the native upload tail; that tail restores box 39's edge before it reveals
the title and then the Action rows. This prevents the former diagonal border, stale
six-row tail, exposed Floor-page indicator, and left/right-dependent blank. Five-page
producers also restore the low-tile footer rasters before publishing `1/5` through `5/5`.

#### Screen-20 Floor Pot `See` entry and return

The Pot viewer reuses `$C6BB`, so its entry hook records the outgoing box-39 row count in
`$C1B8` before screen 12/13 clears the shared shadow. B is admitted only for exact stack
`0,20,12/13`, a one-level pop, selector `$FF`, ground context, compact box-17 geometry,
and the standard viewport/Window. State `$09` then suppresses only the disposable screen
0 and rebuilds complete empty box 5 plus the saved 3-7-row box 39. The underlying Floor
page briefly tries to restore its page indicator into box 39's top edge; the owned return
keeps text hidden until the native tail restores the overlay edge, then permits the title
and Action labels to appear. No whole-LCD blank is used on return.

`tools/groundpotreturnspill.py --screen20` drives the bundled Storage Pot SRAM without
Lua. On entry it additionally proves exact stack `0,20,13`, `$C6DE=$81`, the five-row
first-body descriptor, zero `$4338` calls, enabled LCDC, and complete empty Pot chrome
before `Pot`/`Empty`. On return it hooks all four translation-owned menu blankers,
requires complete parent chrome before any restored text, and compares the settled BG,
Window, and resolved pixels with the exact outgoing six-row parent.

#### Screen-7 unidentified-Pot Floor Info and `See` entry/return

The independent screen-7 gate proves stack `0,7,4`, ordinary Info screen 4, selector
`$FF`, `$C6DE=1`, exactly seven Action rows, and the standard viewport/Window. The
Japanese handler at `4:$4A58` is shared with screen 20, but `mgbdis` shows its branch at
`4:$4A79-$4A86` selects box 6 for screen 7 and box 39 otherwise. Their ownership masks
are therefore deliberately separate.

Box 6 starts at y=1 and overlays the right edge of full-width Floor title box 5. On Info
entry, the controller first restores the covered box-5 middle and bottom cells, then
publishes Info chrome before any description row. On B return, state `$0B` removes the
Info child but remains armed through the native disposable screen 0. Screen 0 is allowed
to finish its shadow-only passes but cannot retire the transaction. At the first proven
screen-7 header, the controller clears the shadow and reconstructs complete empty box 5
plus the y=1 seven-row box 6. Visible BG rows 0-15 publish in four bounded VBlanks; only
after that chrome is complete do the Floor title and seven Action interiors become
visible. The hardware Window is never changed.

`tools/unidentifiedpotspill.py` drives the real Log 3 save without Lua. It requires all
seven rows to reach the proportional allocator, exact armed dispatcher tail `0,7`, zero
calls to `fidisable`, no sampled LCD-off frame, ordered header/chrome/text publication,
and byte-exact outgoing-versus-returned BG and Window tilemaps and resolved pixels.

`See` is not an Info child and did not enter that original gate. `mgbdis` plus a pop-site
trace identifies its exact native return as amount one, screen 12 or 13, stack
`0,7,12/13`, selector `$FF`, ground context, compact box-17 geometry, and the standard
viewport. The new proof subtracts only that child, records the fixed seven-row parent,
and arms the same state `$0B` only after every condition matches. The disposable screen
0 remains shadow-only; complete box-5/y=1 box-6 chrome publishes before any of the seven
replayed labels.

`tools/groundpotreturnspill.py` uses the bundled Log-3 SRAM without Lua. Together with
its `--screen20` Storage Pot mode, it compares the settled BG, Window, and resolved pixels
with each exact outgoing parent; requires LCDC bit 7 throughout the return; hooks every
translation-owned blanker; and rejects any frame where restored text precedes complete
chrome. The screen-7 entry additionally freezes stack `0,7,12`, `$C6DE=$01`, the
four-row first-body descriptor, zero `$4338` calls, and empty Pot chrome before text.
Both modes also run with `--items-first`: they must dispatch through Items, return to
Status with `$C1B6=0`, and only then enter their direct Floor and Pot screens. This is a
separate required history, not an interchangeable cold-start sample.

#### Screen-7 Floor/Action return to Status

This final B is a different lifetime from `See -> Floor`. Fresh `mgbdis` output keeps
the native screen-7 B handler at `4:$5689`, the shared pop hook at `4:$485A`, the
screen-0 builder's original `call $4280` at `4:$490A`, and the translated Status field
boundary at `4:$4FDD`. The no-menu-VWF control proves that the native destination is
Status and uses no LCD-off frame. The prior translated build blanked only because the
late `statusentry` gate recognized stale child 1 (Items) but not stale child 7.

The new owner starts before the native pop, while the outgoing page is still
unambiguous. It requires pop amount 1 from handler `$5689`, current screen/stack
`7 / 0,7`, idle transaction bytes, ground context, selector `$FF`, seven Action rows,
flags `$01`, exact descriptor `(13,1,7,5,2)`, and the standard LCD-on viewport and
Window. A failed check is register- and flag-transparent.

An admitted exit copies a fixed 20x16 empty Status map to BG `$9800` four rows per
complete VBlank. This is the regional unload: it contains only the final three Status-box
structures and blank interiors. The hardware Window at `$9C00`, BG rows 16-17, and all
tile planes remain locked. Only after all four batches finish does the unchanged native
pop dispatch screen 0. At `statusentry`, the independently checked post-pop state has
root depth 0, stale child 7, the exact Status descriptor `(0,10,2,18,4)`, selector
`$FF`, and ground flag `$01`; it selects the existing nine bounded Status-field
uploads instead of `statusdisable`. Thus the visible order is
`Floor -> regional empty Status chrome -> completed Status text`, never text without
boxes and never a whole-LCD blank.

`tools/groundpotreturnspill.py` now continues beyond its exact `See -> Floor` pixel
comparison. Both the cold and `--items-first` histories press B again, require one
screen-7 prepublication, four chrome batches, cap-ordered Status uploads
`(6,7,5,2,4,4,4,4,4)`, zero Status fallback/LCD-off/uniform frames, no reference to a
Status-owned tile in the outgoing Floor/Window layers, complete chrome before text, and
prompt Status input by immediately reopening Items. A separate direct no-`See` probe
produces the same owner and zero-blank result. Screen 20 is deliberately excluded: its
native B destination remains the dungeon field and retains its native teardown.
Manual Mesen validation on 2026-08-27 confirmed both screen-7 return paths render in the
required order and remain promptly responsive.

#### Carried Item and both Floor `Action -> Name` entries

Fresh `mgbdis` output confirms that bank 4 has two screen-specific callers of the shared
name initializer: `4:$4B04` for Start screen 8 and `4:$4B22` for Item/Floor screen 9.
Runtime tracing then separates the latter by its complete dispatcher stack and parent
state. Start enters with `15,22,25,8`, screen-20 Floor enters with `0,20,9`, and both
carried Items and the Items-appended screen-7 Floor enter with `0,1,2,9`. The latter
pair is distinguished in regression by selector, Floor latch, retained transaction,
and Action shape. The screen number or numeric stack alone is therefore not a complete
ownership proof.

The shared bank-4 trampoline asks `statusvwf` to classify the caller before running the
unchanged native `$5E50` initializer. The screen-1/2 admission requires stack
`0,1,2,9`, current screen 9, the standard LCD-on signed-tile viewport, zero scroll, and
the expected Window position. This admits carried Items and the Items-appended Floor;
the latter exact trace has selector `$FF`, Floor latch `$C1B7=1`, retained transaction
`$C1B3-$C1B7 = 00 00 20 01 01`, and screen-7 Action shape `(13,1,6,5,2)`.
Screen-20 Floor admission is independent: stack `0,20,9`, replay counter zero,
selector `$FF`, ground context one, idle transition/queue state, name mode two, and the
still-live box-39 Action descriptor `(13,3,N,5,2)` with `N=3..7`. Start or any malformed
screen-9 caller falls through to the existing bank-44 complete native-font restore at
`44:$4066`; its conservative behavior is intentionally unchanged.

Every admitted Item/Floor entry has two bounded phases while LCDC bit 7 remains set:

1. Retire visible BG rows 0-15 in four complete four-row VBlank batches. The bottom HUD
   Window and hidden BG rows 16-17 remain byte-exact.
2. Restore the 90 unique native tile planes referenced by the complete screen-9 name
   field, keyboard, initial one-cell cursor, and the `$C7-$C9` four-cell underline exposed
   when Start selects `End`. They form eighteen five-tile VBlank records; the schedule
   includes the ROM-data decode inside each DMG VBlank budget.
   The embedded planes are bitwise-complement encoded in ROM so the raw LCDC-writer
   census cannot mistake font data for instructions; a one-cycle complement during copy
   leaves safe headroom in each batch. The menu VWF allocator is reset explicitly after
   the final batch, matching the side effect of the native loader.

The unchanged screen-9 initializer then publishes the keyboard. The permitted visible
sequence is `complete Items or Floor/Action -> regionally empty upper BG with HUD
retained -> complete Name chrome and text`. A disabled LCD, a uniform whole-screen frame, changed
HUD/hidden rows, text before chrome, or a half-restored referenced tile is a failure.

Cancelling an empty carried-item Name keyboard with B is not part of this entry
transaction. It has the separate, independently proved return transaction documented
below. Screen-20 and Items-appended Floor Name returns are likewise outside the entry
checkpoint; shared screen 9 alone authorizes no return direction.

`tools/unidentifiednamespill.py` proves all three Item/Floor entries on the same
gameplay-derived Willow Staff: screen-20 Floor uses stack `0,20,9`, the Items-appended
Floor uses the exact screen-7 state above, and carried layouts cover the existing one-
through four-page synthetic matrix. It requires each accepted path to use one
regional entry and zero native restores, while fresh Start naming still executes one
native restore and zero regional entries. The earlier catalogue attribution of native
shadow `2:$463C` to Status -> Floor was false: exact interval tracing shows that call only
at the earlier title-to-gameplay boundary; Status dispatch `0` to Floor dispatch `20`
has no `$C110` producer, LCD-off frame, or uniform frame. `tools/makeitemnametest.py` creates the manual SRM by pressing real
buttons to take the staff, saving cartridge RAM normally, and cold-booting the result;
it never writes inventory, identity, object, or menu-state memory. Regeneration must be
byte-identical to
`tests/fixtures/saves/shiren_en_log3_carried_unidentified_naming.srm` (SHA-256
`ece2da2b167ae51a42176304ae89d4fa2e4e8e0dbb4f70d7b1d31c12a0dfa235`).

##### Items-appended Floor screen-7 Name catalogue

The independent ground-item SRM also reaches the Floor page appended after its two
carried Item pages without Lua or memory injection. The exact real-input route is
`Status 0 -> Items 1 -> Items page 2 -> appended Floor -> Action 2 -> Name 9`.
Immediately before Name publication, the owner state is:

| Field | Exact value | Meaning |
|---|---:|---|
| Dispatcher stack `$C535...` | `0,1,2,9` | Status, Items, screen-7 Action, Name |
| Current/replay `$C6A3/$C6A6` | `$09/$00` | Name current; no replay pending |
| Item count/selector `$C6AA/$C6AC` | `$08/$FF` | Eight carried Items; appended Floor selected |
| Transaction `$C1B3-$C1B7` | `00 00 20 01 01` | idle entry, one retained Floor row, settled-Floor latch |
| Name box `$C69A-$C69E` | `13,1,6,5,2` | six-row screen-7 Action descriptor at y=1 |
| Ground context `$C6DE` | `$00` | screen-7 derives from Items, unlike screen 20's `$01` |
| Name mode/row `$C6F3/$C6F5` | `$00/$00` | initially empty keyboard state |

This entry already reaches the regional `statusvwf.nameentry` owner: four BG-retirement
batches, eighteen native-plane batches, zero calls to native restore `44:$4066`, zero
LCD-off frames, and zero uniform frames. It therefore has its own `regional` row even
though its numeric stack shares the screen-1/2 branch used by carried Items.

The three returns remain distinct paths. Each calls native pop `4:$5F0B`, then
dispatches through `4:$48AA` as `9 -> 0 -> 1 -> 2`, ending on the Floor Action picker.
Successful `End` additionally calls `4:$6026`. Exact mode/row classification now arms
state `$15`, suppresses the disposable Status build, retires the keyboard, commits the
complete screen-7 Floor and Action perimeters, and only then lets screen 1/2 reveal
their completed rows:

| Return variant | Native mode/row | Causal site | Current result |
|---|---:|---:|---|
| `End` | `$03/$00` | none | `regional`; zero Status fallback/LCD-off/uniform frames |
| B from initially empty Name | `$00/$01` | none | `regional`; zero Status fallback/LCD-off/uniform frames |
| End, reopen Name, erase saved name, final B | `$03/$01` | none | `regional`; zero Status fallback/LCD-off/uniform frames |

This owner preserves the distinct `9 -> 0 -> 1 -> 2` replay and restores the complete
screen-7 Floor plus Action parent before Action text becomes visible. It does not borrow
the carried `Name -> Items` transaction or screen-20 `Name -> Floor` transaction merely
because all three use screen 9.

For the screen-20 Floor-entry checkpoint, use the independent ground-item fixture and a
unique ROM basename:

```sh
TEST_TAG=shiren_floor_name_entry_20260829
TEST_DIR="$PWD/build/manual-tests/$TEST_TAG"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$TEST_DIR" "$MESEN_SAVES"
cp build/shiren_en.gb "$TEST_DIR/$TEST_TAG.gb"
cp tests/fixtures/saves/shiren_log3_unidentified_naming.srm \
  "$MESEN_SAVES/$TEST_TAG.srm"
md5 "$TEST_DIR/$TEST_TAG.gb"
shasum -a 256 "$MESEN_SAVES/$TEST_TAG.srm"
open -na "/Applications/Mesen.app" --args "$TEST_DIR/$TEST_TAG.gb"
```

The expected ROM MD5 is `0b372e50b5534eb50e1a1beef564b383`; expected SRAM SHA-256
is `21c38b8eb212f9cf5e0ae7987530e9ff2e7943f7e89c2fb501710693e0a2d5e8`.
Load Adventure log 3. In the dungeon press B, move Down once from `Items` to `Floor`,
and press A. Status -> Floor must remain LCD-live. In the six-row Action picker move
Down four times from `Take` to `Name` and press A. The Floor/Action map may retire
regionally while the bottom HUD remains visible; the whole LCD must never blank. The
complete keyboard, name field, cursor, punctuation, and `End` underline must settle
before normal input. Stop this checkpoint once the keyboard is complete: empty B,
successful End, and named-then-erased returns to screen 20 are separately catalogued
regional transitions and are included in the consolidated manual pass below.

For an isolated Mesen visual review, close any running instance first and run from the
repository root:

```sh
TEST_TAG=shiren_item_name_empty_cancel_20260829
TEST_DIR="$PWD/build/manual-tests/$TEST_TAG"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$TEST_DIR" "$MESEN_SAVES"
cp build/shiren_en.gb "$TEST_DIR/$TEST_TAG.gb"
cp tests/fixtures/saves/shiren_en_log3_carried_unidentified_naming.srm \
  "$MESEN_SAVES/$TEST_TAG.srm"
md5 "$TEST_DIR/$TEST_TAG.gb"
shasum -a 256 "$MESEN_SAVES/$TEST_TAG.srm"
open -na "/Applications/Mesen.app" --args "$TEST_DIR/$TEST_TAG.gb"
```

For this empty-cancel checkpoint candidate the ROM MD5 is
`0b372e50b5534eb50e1a1beef564b383`; the SRAM SHA-256 remains
`ece2da2b167ae51a42176304ae89d4fa2e4e8e0dbb4f70d7b1d31c12a0dfa235`.

Press Start through the opening screens, choose `Adventure`, choose the third log, and
load it. In the dungeon press B, choose `Items`, press Right to page 2, move Down three
rows to the unidentified Willow Staff, press A, move Down three rows to `Name`, and press
A. The upper BG may remain regionally empty for the bounded redraw, but the bottom HUD
must stay visible and the whole LCD must never blank. The complete keyboard must settle
with its cursor and accept input immediately. Do not enter a character; press B. The
keyboard may retire regionally, then complete empty Items boxes must appear before their
rows and cursor. The bottom HUD must remain visible and the whole LCD must never blank.
As soon as the page settles, press Up or Down: the Items cursor must respond immediately.
The previously accepted `End` underline and chrome-first success return remain automated
regressions. To repeat from the exact baseline, close Mesen and re-run only the second
`cp` command before reopening the uniquely named ROM.

#### Inventory Item empty `Name -> B -> Items` return

Fresh `mgbdis` output and the no-Lua trace isolate this from the successful finalizer.
With no character entered, B reaches the native bank-4 `$5F0B` pop directly and never
calls the `$6026` End routine. Both outcomes dispatch `9 -> 0 -> 1`, but their retained
Name state differs: successful End carries `(mode,row)=($03,$00)`, whereas empty cancel
carries `($00,$01)` and retains `$88` in the first name cell. The previous success-only
proof rejected that second state, so the shared Status fallback reached its whole-LCD
clear at the then-current `statusdisable` write. That rejected history is why the cancel
now has its own exact transaction rather than sharing the successful route by screen ID.

The cancel return now uses private transaction state `$0E`; successful End continues to
use `$0D`. At the disposable screen-0 boundary, the `$0E` proof requires the exact
empty-name state plus the same stack `0,1`, retained one-through-five Item rows, valid
inventory count/selector, Status descriptor, LCD-on viewport, Window, and idle queue as
the successful return. It suppresses the disposable Status painter. The screen-1 hook
then independently requires the native replay counter to advance and every retained
field—including the empty-name mode, row, and `$88` cell—to agree before it accepts
`$0E`. A success/cancel mismatch falls back rather than borrowing the other route's
ownership.

After that second proof, both transactions intentionally share the established regional
publisher: four VBlanks retire visible BG rows 0-15 while the bottom Window and hidden
rows remain locked, complete empty Items header/list chrome is committed, and only then
may the existing renderer publish rows and cursor. `tools/unidentifiednamespill.py`
requires the native `$5F0B` call and `9 -> 0 -> 1` dispatch, four `$0E` batches, zero
Status drawing/LCD-off/uniform frames, chrome before rows, an immediate Up selection,
and a subsequent clean Items-to-Status exit. The successful `$0D` matrix and End
underline planes run in the same regression, keeping the two variants independent.

#### Inventory Item erased-name `Name -> B -> Items` return

This is not the initially empty cancel above. The player first names the carried Item
through `End`, reopens `Name`, presses B until the saved text is empty, and presses B
once more to exit. Fresh `mgbdis` output for ROM MD5
`0b372e50b5534eb50e1a1beef564b383` places the unchanged native pop at bank 4 `$5F0B`,
the `End` finalizer at `$6026`, and the screen dispatcher at `$48AA`. A real-input trace
proves two complete screen-9 lifetimes: the successful first lifetime reaches `$5F0B`
with `(mode,row)=($03,$00)`, while the erased-name cancellation reaches it with
`($03,$01)`. The latter still dispatches `9 -> 0 -> 1`; it is neither successful End nor
the initially empty `($00,$01)` cancellation.

Private transaction `$0F` preserves that distinction. The disposable screen-0 half
requires mode/row `$03/$01`, an empty `$88` first name cell, exact stack `0,1`, retained
one-through-five Item rows, valid count/selector, the Status descriptor, idle queue, and
the standard LCD-on viewport and Window. Screen 1 independently rechecks `$0F`, the
advanced replay counter, mode/row, empty cell, retained Items state, descriptor, and
hardware state. Only then does it share the established four-VBlank keyboard retirement
and chrome-first Items publisher. `$0D`, `$0E`, and `$0F` cannot authorize one another.

`tools/unidentifiednamespill.py` types `Stun` through four real keyboard selections,
confirms `End`, reopens the same Action menu, erases all four characters with four real B
presses, and exits with a fifth B. It requires the second native `$5F0B` state to be
`$03/$01`, exact transaction `$0F` on both replay halves and all four batches, no
Status painter, LCD-off, or uniform frame, complete chrome before rows, immediate Up
input, and a subsequent clean Items-to-Status exit. The initially empty `$0E` route runs
separately in the same regression.

For the isolated visual review, close Mesen and run from the repository root:

```sh
TEST_TAG=shiren_item_name_erased_cancel_20260829
TEST_DIR="$PWD/build/manual-tests/$TEST_TAG"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$TEST_DIR" "$MESEN_SAVES"
cp build/shiren_en.gb "$TEST_DIR/$TEST_TAG.gb"
cp tests/fixtures/saves/shiren_en_log3_carried_unidentified_naming.srm \
  "$MESEN_SAVES/$TEST_TAG.srm"
md5 "$TEST_DIR/$TEST_TAG.gb"
shasum -a 256 "$MESEN_SAVES/$TEST_TAG.srm"
open -na "/Applications/Mesen.app" --args "$TEST_DIR/$TEST_TAG.gb"
```

The expected ROM MD5 is `0b372e50b5534eb50e1a1beef564b383`; expected SRAM
SHA-256 is
`ece2da2b167ae51a42176304ae89d4fa2e4e8e0dbb4f70d7b1d31c12a0dfa235`.
Load Adventure log 3, press B, choose `Items`, press Right to page 2, move Down three
rows to the unidentified Willow Staff, press A, move Down three rows to `Name`, and
press A. Press A once on the initial `A` keyboard cell, press Start to select `End`, and
press A to confirm. After Items has returned, press A on the same staff, move Down three
rows to `Name`, and press A. Press B once to erase `A`, then B once more to exit. The
keyboard may retire regionally, complete empty Items boxes must precede their rows and
cursor, the bottom HUD must remain visible, and the whole LCD must never blank. Press Up
or Down immediately after settlement to confirm that Items input is live. Restore the
fixture with the second `cp` command before repeating from the exact baseline.

#### Inventory Item `Name -> End -> Items` return

This return is its own tile epoch rather than an Item/Info variant. Fresh `mgbdis`
output identifies the screen-9 Name finalizer at bank 4 `$6026`, the dispatcher at
`4:$48AA`, the screen-1 shadow-clear hook at `4:$4951`, and the Status boundary at
`4:$4FDD`. Choosing `End` performs the native dispatcher sequence `9 -> 0 -> 1 -> 0`:
the first screen 0 and screen 1 are reconstruction steps, while the final screen 0 is
the ordinary later Items-to-Status exit driven by the fixture. The outgoing keyboard
may reference almost the entire native menu font, so repainting tile planes before its
map is retired is unsafe.

The regional owner splits admission around the native replay. At the disposable
screen-0 boundary it requires stack `0,1`, current/replay screens `0/1`, a valid
one-through-twenty-item count and selector, the exact Status descriptor
`(0,10,2,18,4)`, standard LCD-on viewport and Window, idle queue, inventory context
`$C6DE=0`, and one through five retained Item row records packed in `$C1B5`.
Only that complete proof arms state `$0D` and suppresses the Status painter. At the
screen-1 hook, a second proof requires the native replay to have advanced to screens
`1/2` while every retained count, selector, descriptor, viewport, and transaction value
still agrees. A mismatch on either side falls back instead of inheriting regional
ownership.

An admitted screen-1 entry keeps the bottom Window and every tile plane locked while it
retires visible BG rows 0-15 in four complete-VBlank batches. It then commits the complete
empty Items header and list-box chrome and converts `$0D` to the established state `$01`;
only afterward may the ordinary completed-row renderer expose item text. The visible
contract is therefore `complete keyboard -> regional retirement -> complete empty Items
boxes -> completed Item rows`, with no transient Status and no whole-LCD blank.

`tools/unidentifiednamespill.py` drives the real Name keyboard and finalizer, then creates
its inventory layouts through the native bank-6 inventory builder rather than the Lua
item injector. Its matrix covers `(items,page,row,retained rows)` values
`(1,1,1,1)`, `(7,2,2,2)`, `(13,3,3,3)`, `(19,4,4,4)`, and `(20,4,5,5)`—all four pages,
all five target rows, and every valid retained-record count. Each case requires the exact
`0,1,0` post-End dispatch suffix, one pre/post admission pair, state `$0D` through four
VBlank batches, unchanged Window/hidden BG/tile planes, complete chrome before text, and
zero `statusdisable`, LCD-off, or uniform frames.

Manual Mesen validation on 2026-08-27 used a dedicated ROM/SRAM basename and the supplied
unidentified-Willow-Staff fixture. It accepted the complete keyboard-to-Items transition:
no whole-LCD blank or transient Status text, retained bottom HUD, complete empty Items
boxes before list text, restored item/cursor, and prompt post-return input. The accepted
ROM MD5 is `31bb9fa4c6e92c69a938bfe3f057f635`. This freezes the exact inventory Name
return; unknown screen-9 or LCD-on Status contexts remain outside its ownership proof.

#### Items-appended Floor Pot `See` entry and return

This history looks like the direct screen-7 ground-Pot route but has different native
ownership. Paging Right from Items to Floor leaves screen 1 current; opening the
seven-row picker pushes screen 2, and `See` pushes screen 12 or 13. The exact B stack is
therefore `0,1,2,12/13`, not `0,7,12/13`. Although the viewer repurposes the live selector,
the completed screen-1 Floor latch at `$C1B7=1` survives and proves which parent must be
restored. The Pot-pop classifier packs selector sentinel `$1F`, removes both child
records, and enters the established state-`$08` screen-1 replay. Complete empty Floor
chrome publishes before the exact title, item row, and cursor return.

The final row of this Action picker is independently protected by the seven-row allocator
contract described in checkpoint 3. `tools/unidentifiedflooractionspill.py` freezes the
two no-Lua children: Info requires rows 14-15 to retire before `$43` is repainted, and
`See` requires stack `0,1,2,12`, the retained Floor latch, zero `$4338` calls, enabled
LCDC, complete empty Pot chrome before text, and a pixel-exact B return.

#### Exact Pot `See` entry and carried return

`mgbdis` separates the carried entry from the visually similar Floor routes. Screen 12
enters through wrapper `4:$4B81` (translated hook `$4B83`); screen 13 enters through
wrapper `4:$4BA2` (hook `$4BA5`). Native control draws the capacity-sized body first,
draws compact title box 17 last, then reaches bank-60 `$4338`, where the old page
controller disabled the LCD before publishing the full 20x18 shadow. The exact first
body descriptor is `(x=0,y=3,rows=1..5,width=18,flags=$02)`. The screen-13 hidden/full
variant additionally carries `$C6DE=$80`; screen 12 carries zero.

The new entry gate first proves one exact parent stack: carried or Items-appended Floor
`0,1,2,12/13`, alternate Floor `0,7,12/13`, or screen-20 Floor
`0,20,12/13`. It then proves the exact body descriptor, native shadow destination
`$C380`, live Window geometry, and the native flag relation: bits 1-6 of `$C6DE` are
zero, bit 7 is set exactly on screen 13, and bit 0 may distinguish the direct Floor
producer. Thus observed screen-12 values `$00/$01` and screen-13 values `$80/$81` are
accepted without treating unrelated flag values as equivalent. The gate arms state
`$0C`, clears only visible BG rows 0-15 in four bounded VBlanks, and publishes complete
empty box-17 title plus capacity-sized body
chrome. Native proportional rows continue in the shadow map while the visible chrome
remains stable. Box 17's existing final boundary drains the tile queue and publishes the
finished title/body top-to-bottom in at most three-row VBlank batches. Thus the observed
sequence is outgoing Items/Action -> region blank with HUD retained -> empty Pot chrome
-> Pot title/body text; LCDC bit 7 remains set throughout.

Opening Items and then returning to Status exposed an independent lifetime bug: an
initial Items build can finish with `$C1B6=3`, because that native entry path does not
execute the same-screen redraw-tail service that normally clears phase 3. The next
direct Floor Pot entry was otherwise byte-for-byte identical, but the stale phase made
the exact Pot gate reject it and select `$4338`; screen 7 then preserved the phase while
screen 20 happened to clear it after one return. `mgbdis` confirmed `$C1B6` is
translation-owned scratch. The exact Items-to-Status pop now retires both `$C1B6` and
the Floor latch `$C1B7`. Later Pot gates continue to require their proper idle phase;
they do not broadly accept a dead Item transaction.

The Pot B gate proves stack `0,1,2,12/13`, exact box-17 geometry, a valid inventory
selector/count, ordinary non-Floor context, and the standard live Window. Screen 12 may
carry Action admission `$C1B6=0` or `$01`, depending on whether the visible Item page
allowed the private Action pool; screen 13 must have cleared it to zero. It subtracts
both child records and arms state `$0A`. The screen-0 Status hook discards that disposable
redraw, clears Pot page markers during VBlank, and normalizes the replay counter so the
unchanged direct Status-to-Items gate can own the rest. The Pot map stays live until that
gate retires it; complete empty Items title/body boxes are visible before any restored
row text. Box 17 composes the complete word `Pot`, because raw tile `$1A` is legitimately
repainted by Status VWF and cannot own the title's `P` across this lifetime.

ROM and WRAM ownership added for this checkpoint is:

| Owner | Range / value | Responsibility |
|---|---|---|
| Bank 39, far `$05` | `$405A-$40DD` (132 bytes) | timing-preserving ABI classifier; ordinary Item rows return locally, exact candidates cross banks, and restored contained-Pot rows hand state `$17` to the Pot-entry owner |
| Bank 40, far `$05` | `$4060-$4063` (4 bytes) | final-row Info publication ABI |
| Bank 37, far `$05/$07` | `$405A-$4293` (570 bytes) | screen-2/direct-Floor/screen-16 Action admission plus contained-item Info proof for carried/appended `0,1,2,12/13,16,4/5` and ground `0,7/20,12/13,16,4/5` stacks; redirected text begins at `$42A0` |
| Bank 62, far `$07` | `$405A-$4429` (976 bytes) | screen-2 Action restore, screen-7 disposable-screen deferral, plus exact screen-12/13 Pot entry routing and Pot-pop proof |
| Bank 62, far `$09/$0B/$0D/$0F` | `$4430-$547E` (4175 bytes) | exact screen-1/screen-7/screen-20 Info entry/page publication and replay, all Pot-return forms, shop appended-Floor admission, plus exact carried/screen-1-Floor/screen-7/screen-20/contained-item Pot entry chrome and ordered final publication |
| Bank 62 fixed leaf | `$5480-$548F` (16 bytes) | packs the retained screen-1 Floor selector and enters state `$08` for exact `0,1,2,12/13` See return without consuming another far-table slot |
| Bank 62 redirected text origin | `$5490` | leaves a hard boundary between lifecycle code and redirected strings |
| `$C1B3` | `$02 -> $03 -> $08/$09/$0B -> $00` | Info construction, settled page, exact screen-1/screen-7/screen-20 replay, idle; exact alternate ground-Pot See return enters `$0B` directly; Items-derived Floor-Pot See return enters `$08` directly; carried screen-5 return briefly hands `$08 -> $01` to the Item-page transaction |
| `$C1B3` | `$0A -> $00/$01` | exact carried-Pot screen-12/13 two-level pop, disposable Status suppression, ordinary direct Items-entry handoff |
| `$C1B3` | `$0C -> $00` | exact admitted screen-12/13 Pot entry: regional retirement and empty chrome stay live while native rows remain shadow-only; box 17 performs final title/body publication |
| `$C1B3` | `$17 -> $0C -> $00` | contained-item Info removes the screen-16 Action and screen-4/5 child together, retains the exact screen-12/13 Pot parent, suppresses disposable reconstruction, and hands its native rows to the ordinary Pot chrome-first publisher |
| `$C1B6` | screen 1: `$01 -> $02 -> $00`; screen 20: `$00/$01 -> $00`; screen 7 return: `$00 -> $02 -> $00` | screen-1 Action admission and completed return chrome; screen-20 stale admission normalization; screen-7 empty parent publication completed |
| `$C1B4` | child screen 4/5 during screen-1 return, saved box-39 row count during screen-20 return, saved seven-row box-6 height during screen-7 return, retained Pot screen during state `$17`, or screen-20 fast-upload slice/completion byte during construction | selects the carried screen-5 fast handoff, reconstructs exact parent chrome, and keeps row upload/publication coupled in its disjoint phases |
| `$C1B5` | retained packed record count/selector for screen 1; initial-entry flag for screen 20; contained-Pot item selector during state `$17` | restores the exact carried page/selection (`$1F` remains the screen-1 Floor parent), distinguishes Action entry from same-Info-screen paging, or restores the exact Pot-content row |
| `$C1B7` | zero or one | required independently for the standing-item Floor parent |
| `$C1B8` | three through seven during exact screen-20 Pot viewing, or retained Info child screen 4/5 during state `$17` | preserves the box-39 parent height across screen 12/13's reuse of `$C6BB`, or proves the returning contained-item child before Pot publication |
| Visible BG rows 3-15, plus rows 0-15 for exact screen-7/screen-20 parent reconstruction and all admitted Pot entries | entry/page replacement | screen 1 uses empty chrome, clears any Action tail below it, then publishes complete rows; screen 20 uses Action-box-to-chrome+row-zero entry and whole old/new row replacement; screen 7 independently rebuilds box 5 plus y=1 box 6; Pot entry installs complete box-17/body chrome; final text never precedes complete parent chrome |
| Five Info interiors + five pager cells | Info exit/replay | proportional references retire while all window chrome and the hardware Window stay locked |

`tools/iteminfospill.py` drives six real-save button paths: page-1 four-row held Action/B,
page-2 five-row hidden-Bracer Action/B, page-4 six-row hidden-Pot Action/B, and the
standing Wood Arrow Floor Action with two Info pages and final-page A exit. A dedicated
carried-seal path replaces the page with the reported `Egg / Egg / Happy Bracer / Fusion
Pot / Manji Kabura` mix, opens screen 5 on the fused weapon, presses B, and requires exact
parent pixels plus accepted Up input. The final path uses the same mix, installs a
standing Fusion Pot, advances all five screen-1 Floor Info pages, returns to Items, enters
carried-Pot See, and requires an exact second return in the same session. When
`saves/dungeon.state` is available it also synthesizes a separate
five-page Fusion Pot producer
and validates `1/5` through `5/5`: the footer references must occupy BG row 13, both digit
rasters must match the approved font, and no publication may leak into intervening chrome
rows. Its first transition is a one-frame Down tap and must invoke native handler
`4:$5926` only once before the next deliberate input. The fixture requires one complete
empty Info publication per page, complete progressive rows with the first no more than
four frames after chrome, one narrow regional retirement, one complete empty
target-chrome publication, resolved-pixel equality with the exact originating parent, an
unchanged Window, accepted post-return input within four sampled frames, and zero LCD-off
or all-white frames. Existing paging, rapid Items/Floor shape changes, Action
B-cancel, direct entry/exit, Pot, shop, and hidden-identity fixtures remain separate
regression gates. `tools/floorinfospill.py --fusion` now exercises the real screen-20
six-row Fusion Pot Action and all five Info pages. It requires approved `1/5` through
`5/5` digit pixels, zero stale Action references in BG rows 14-15, complete Action or
Info chrome at every entry sample, no complete empty Info body, and zero LCD-off/uniform
frames. Every page change must retain at least one ink-bearing row; every visible row
must match a complete outgoing row, complete incoming row, or a wholly retired row. The
ordinary Wood Arrow, three-row Gitan,
Scroll, and six-row Storage Pot fixtures apply the same regional return contract.
`tools/floorinfospill.py --fusion-kit-history` separately reproduces the exact
`tools/mesen_spawn_fusion_kit.lua` records and the menu history which exposed the stale
state: open the spawned carried Fusion Pot's Action menu, take a gameplay-bound action,
return through Status to screen-20 Floor, then enter and page Info on the standing Wood
Arrow. It asserts that the resulting pending-header state `$C1B6=4` reaches the first
Info candidate, that the exact owner clears it before the first pixels publish, and that
the complete route has zero
LCD-off, uniform, empty-body, or torn-row frames. The simpler `--fusion-kit` case remains
independent so record bytes alone cannot be mistaken for the history-dependent trigger.
`tools/fusioncountspill.py` proves an actual screen-5 equipment-seal page enters this
lifecycle without disabling the LCD. `tools/potreturnspill.py` drives real carried
screen-12 and full-page screen-13 Pots through `See`. Its third case uses the reported
five-row item mix that forces screen 12's zero-latch generic Action path. Every case
hooks `$4338` and requires zero executions in both directions, requires a complete empty
Pot title/body frame before the settled `Pot` raster, and then proves that no restored
Items text precedes complete Items boxes. No entry or return frame may disable the LCD,
and the return title may never expose a partial/mixed raster such as `Potms`; settled
`Items` remains pixel-identical to its pre-Pot raster.

`tools/potseespill.py` drives two direct screen-20 Floor saves, while
`tools/groundpotreturnspill.py` independently covers direct screen 7 and screen 20 and
`tools/unidentifiedflooractionspill.py` covers the screen-1 appended Floor parent. All
three require zero `$4338` calls on entry, an enabled LCD and unchanged Window, and a
complete empty Pot title/body frame before any settled title/body text. The latter two
also retain their previously frozen chrome-first, exact-parent B returns.

The complete `build.sh` battery passes with the accepted implementation installed. In
the same run, ordinary and rapid Item paging retain their frozen timing budgets, all nine checkpoint-3
Action cases still return in two frames, the Wood Arrow and Fusion Pot screen-20
Floor/Info controls remain regional and chrome-first, carried Pot entry and return remain box-first,
and every other release fixture completes.

### Frozen manual visual acceptance paths

1. On Items page 1, open an ordinary four-row Action menu and select `Info`. Confirm the
   empty Info box exists before its text, then press B and confirm the same item, cursor,
   page indicator, and prompt D-pad input return.
2. On page 2 or later, repeat with an identity-hidden five-row Action box. On page 4,
   repeat with an identity-hidden Pot's six-row box. Neither path may jump to page 1.
3. Use a multi-page description. Check A and each D-pad direction as page-advance inputs,
   the page indicator settling with its text, and B from a non-final page.
4. Stand on an item, page from carried Items to the one-row Floor page, then open
   `Take / Fire / Swap / Info`. Test B from page 1 and final-page A separately. Both must
   restore the one-row Floor box and cursor immediately. On a standing Pot, also choose
   `See`: the upper menu may clear regionally but the LCD/HUD must remain on, complete
   empty Pot chrome must precede text, and B must restore the exact Floor page.
5. Observe the exit redraw itself: the completed Info/seal page must remain visible until
   complete empty parent windows replace it; the bottom status Window stays intact. A
   no-window upper screen, full-screen white, empty-Info interval, incomplete boxes,
   unrelated text in the retained Action header, a missing cursor, or an input stall is
   not allowed.
6. Use Status -> Floor (screen 20) while standing on a Fusion Pot, select `Info`, and
   inspect every page and the return. The LCD must remain on. Entry should show the
   complete Action box until complete Info chrome and its first row replace it together;
   later pages may mix only complete old/new rows and must never show an empty Info body.
   Each footer must read `1/5` through `5/5`, and no lower-right fragment of the six-row
   Action box may survive below the Info box.
   Repeat after running `tools/mesen_spawn_fusion_kit.lua` and performing a carried-Pot
   Action which returns to gameplay before reopening Status -> Floor. This retained-state
   route is a separate acceptance case; it must obey the same no-full-screen-blank rule.
7. Repeat the screen-20 route on a weapon or shield with seals. The seal page (screen 5)
   must obey the same retained-Action/whole-row, no-full-screen-blank contract in both
   directions.
8. Stand on an unidentified Pot and use the alternate Floor page's seven-row Action
   picker. Select `Info`, then press B. Entry must restore the complete full-width Floor
   title before Info replaces the Action overlay; return must show complete box 5 and the
   y=1 seven-row box 6 before its title/rows, with no whole-screen blank or Window change.
   Then select `See` and press B. Entry may regionally clear the upper menu but must keep
   the LCD and bottom HUD on and show empty Pot chrome before text; return must show the complete same
   box-5/box-6 parent before all seven labels, and settle pixel-identically.
   Press B once more from that screen-7 Floor/Action parent. Returning to Status is the
   native destination. The upper 16 BG rows may clear regionally over four VBlanks, but
   the LCD and bottom HUD must remain on; complete empty Status boxes must appear before
   any Status text. D-pad input must be accepted as soon as the settled Status page appears.
9. With the bundled Storage Pot save, use Status -> Floor, open the six-row Action menu,
   select `See`, and press B. Entry may regionally clear the upper menu but may not blank
   the whole LCD; empty Pot chrome must precede its text. The B return must show complete
   empty box 5 and box 39 first, then `Storage Pot[5]` and the Action labels. The
   underlying Floor page indicator must never cut through box 39's top edge.
   Pressing B once more from screen 20 exits to the dungeon field rather than Status;
   the no-menu-VWF control proves that different destination is native behavior.
10. On a carried ordinary Pot such as Heal Pot or Walrus Pot, select `See`, then press B.
   Entry may regionally blank the menu area but must retain the bottom HUD, must never
   blank the whole LCD, and must show complete empty `Pot` title/body boxes before their
   text. On return both empty Items boxes must appear before any item row; the title must
   never read `ot`, `Potms`, or any other partial/mixed word, and rows must not float
   temporarily without their boxes. Repeat with a full page whose hidden Pot selects
   screen 13, and with the five-row Egg/Egg/Happy/Fusion/Manji inventory because its
   generic Action allocation reaches a distinct screen-12 path.

The original grouped pass accepted these ten paths. The later six-case focused recheck
accepted the natural sealed final-A routes, short-page cleanup, contained-Pot lifecycle,
shop Action/price preservation, direct-Floor exit/reopen behavior, and direct-Floor Name
history matrix. The exact commands, SRAM isolation procedure, expected results, and final
pass record are in [`ITEM_FLOOR_MANUAL_TEST.md`](ITEM_FLOOR_MANUAL_TEST.md).

## Current transition controller

`$C1B3` is an English-only synchronous state byte. It must remain disjoint from dialogue
scratch and should remain nonzero until the associated pixels and map publication settle.

| Value | Current meaning |
|---:|---|
| `$00` | no translation-owned synchronous menu transaction |
| `$01` | screen-1 regional Item-page rebuild or direct Status-to-Items entry pending |
| `$02` | exact screen-1/screen-7/screen-20 Info or seal construction/publication pending |
| `$03` | settled Info/seal page; authorizes exact paging or exit |
| `$04` | retained legacy Info-to-parent return pending |
| `$05` | regional Item attempt rejected after blanking; finish through whole-map fallback |
| `$06` | initial/declined Items entry latch; never reinterpret a later row-0 pass as Left/Right |
| `$07` | transient admitted screen-2 Action B parent/machine-state restore; cleared before direct return |
| `$08` | exact screen-1 Info two-level replay: outgoing page retained through disposable Status suppression, then retired at the first proven parent row; screen-5 may hand off to `$01` |
| `$09` | exact screen-20 Info/seal replay: visible BG retired, disposable Status replay suppressed, final Floor title/Action parent pending |
| `$0A` | exact carried-Pot `See` two-level replay: disposable Status suppressed, direct Items entry pending |
| `$0B` | exact screen-7 unidentified-Pot Info or admitted ground-Pot See replay: disposable screen 0 suppressed, complete box-5/y=1 box-6 parent and final title/Action publication pending |
| `$0C` | exact carried, Items-appended Floor, screen-7, or screen-20 Pot screen-12/13 entry: old parent/Action region retired, empty Pot chrome live, native title/body text held in shadow until the box-17 completion boundary |
| `$0D` | exact inventory Name finalizer handoff: disposable Status suppressed, keyboard retirement and empty Items chrome pending at screen-1 entry; converts to `$01` only after chrome completes |
| `$0E` | exact initially empty inventory Name B-cancel handoff: native mode/row `$00/$01`, empty first cell, and both replay halves independently proved before sharing the Name-to-Items publisher |
| `$0F` | exact named-then-erased inventory Name B-cancel handoff: native mode/row `$03/$01`, empty first cell, and both replay halves independently proved before sharing the Name-to-Items publisher |
| `$10` | title/file composite transaction |
| `$11` | difficulty composite transaction |
| `$12` | proportional Rankings map-swap transaction |
| `$13` | Fay composite transaction |
| `$14` | native Rankings transaction |
| `$15` | exact Items-appended Floor Name replay: suppress disposable Status/screen 1, retire the keyboard, publish complete Floor/Action chrome, then normalize to the ordinary regional screen-1 owner |
| `$16` | exact carried-Pot screen-11 Put selector: retire Action, publish empty Items chrome, and hold incoming selector rows until complete |

`$C1B6` retains value one while an admitted screen-1 Action child is on screen 4 or 5.
During state `$08`, its change to two records that complete empty Item/Floor return chrome
has already been published; the final parent publication clears both bytes. Screen 20
uses independent stack/context ownership: it normalizes idle or stale-one admission to
zero at entry, and state `$09` does not require it as a live child proof. Ordinary Item paging
continues to use `$C1B6` phases two, three, and four only while its disjoint lifecycle is
active. Screen 7 begins with zero, changes it to two only after complete empty box-5/box-6
chrome is visible, and clears it with state `$0B` at final parent publication.

`$C1B7` is a separate one-bit settlement proof, not another `$C1B3` mode. It is set only
after screen 1 completes selector `$FF`. It admits only the proven direct Status pop,
Items/Floor paging conversion, or screen-2 Action parent; Action B retains it because the
result is the same settled Floor page, while an actual page exit clears it. A stale or
partially built `$FF` page therefore cannot broaden any live path.

Screen-1 Left/Right and Start-sort redraws use the narrow regional transaction below.
Exact direct Status-to-Items entry and Items-to-Status pops use the two broader directions
described afterward. Exact screen-1, screen-7, and screen-20 Info/seal pages use the
checkpoint-4 lifecycle above, and exact carried screen-12/13 Pot return hands off to
direct Items entry. Exact inventory Name success, initially empty cancel, and
named-then-erased cancel use states `$0D`, `$0E`, and `$0F` respectively across their
disposable Status/screen-1 handoffs. Screen-20 Floor Name returns reuse the independently
proved `$09` parent-reconstruction lifecycle after exact Name-mode classification;
Items-appended Floor returns use `$15` because their replay is `9 -> 0 -> 1 -> 2`.
Exact admitted Pot entries share the state-`$0C` chrome-first
publisher while retaining stack-specific admission and return ownership.
Unexpected nonempty Item fallback, rejected Pot viewers, and unknown LCD-on Status or
Info reconstructions still disable LCDC bit 7 before pixels are reused, build the
replacement in `$C300`, publish all visible 20x18 cells, then re-enable the LCD. That
retained path is the safe fallback. Regional publication changes scope and ownership
timing, not the text renderer itself.

## Item paging and Start-sort regional checkpoint

This is the narrow first-checkpoint implementation. It
covers same-screen page replacement and the Start-button sort redraw within screen 1: the
Items header, box borders, enabled bottom Window, and surrounding cells stay live. Action,
Info, entry/exit, and adjacent special routes do not inherit this five-row mask.

### Exact candidate mask

Box 4 is `(x=0, y=3, rows=5, width=18, flags=$02)`. Its five physical row keys are:

```text
row 0  $C380    row 1  $C3C0    row 2  $C400
row 3  $C440    row 4  $C480
```

Within each row, `key+0` is the marker-coupled left border, `key+1` is a raw
equipped/status cell, `key+2` is the cursor cell, `key+3..key+18` is the 16-cell name
interior, and `key+19` is the right border. An equipped `$84/$86` marker selects border
`$83/$85`; clearing only `key+1` leaves the border tile's vertical component visible.
The retirement state therefore normalizes `key+0` to `$BE` while blanking the complete
mutable interior `key+1..key+18`, including the outgoing cursor:

| Row | Shadow border / marker / cursor / name | Visible BG border / marker / cursor / name |
|---:|---:|---:|
| 0 | `$C380->$BE`, `$C381-$C392->$00` | `$9880->$BE`, `$9881-$9892->$00` |
| 1 | `$C3C0->$BE`, `$C3C1-$C3D2->$00` | `$98C0->$BE`, `$98C1-$98D2->$00` |
| 2 | `$C400->$BE`, `$C401-$C412->$00` | `$9900->$BE`, `$9901-$9912->$00` |
| 3 | `$C440->$BE`, `$C441-$C452->$00` | `$9940->$BE`, `$9941-$9952->$00` |
| 4 | `$C480->$BE`, `$C481-$C492->$00` | `$9980->$BE`, `$9981-$9992->$00` |

This is a 95-cell write set: five normalized borders plus 90 blank
marker/cursor/name cells. It
still retires at most 55 dynamic tile-data slots for five 11-tile proportional rows. The
border and marker tile planes remain immutable; only their map references change.
For the standing-item Floor page (`$C6AC=$FF`), the same transaction has a narrower final
shape: only item row 0 exists. Its blank commit retains row 0's `$BE` left border but
zeros the left borders of outgoing rows 1-4 along with their interiors. This prevents
the four permanent vertical remnants that result from treating a one-row page as a short
five-row Item list. The shape-specific commit also rebuilds the complete empty Floor
rectangle at rows 3-5 before its first text row. In the reverse direction, a completed
Floor latch plus the incoming carried selector commits the complete empty five-row Items
rectangle at rows 3-13 before page text. Right selects page 1; Left selects the last
carried page. Both shape directions also retire the shared header interior at
`$C321-$C324/$9821-$9824`; box 14/18 then composes `Items`/`Floor` while no visible map
cell refers to those private title tiles. The regional controller masks IE around the ROM's internally-`EI` far-call
trampoline so both conversions finish inside the VBlank that begins their publication.

### Locked and separately mutable cells

The neighboring and separately mutable cells follow these ownership rules:

| Region | Address/shape | Rule |
|---|---|---|
| Items/Floor header boxes 14/18 | x `0..5`, y `0..2` | Lock for ordinary Item-page changes. An Items/Floor shape change owns only the four middle-row interior cells x `1..4`; its border remains locked |
| Item top border | y 3, x `0..19` | Lock except the page-indicator transaction below |
| Page indicator | shadow `$C36F-$C372`, BG `$986F-$9872` | Exclude from row clear; publish the new value at the explicit commit point |
| Equipped border/mark pair | each row `key+0..key+1` | Normalize to `$BE,$00`; republish the completed incoming `$83,$84`, `$85,$86`, or ordinary pair atomically; keep their tile planes immutable |
| Cursor | each row `key+2`; first is `$C382/$9882` | Blank with the outgoing row, clamp `$C6AC/$C6A5` if the destination row is empty, and publish exactly one `$81` with the completed body; native `$4E2B` confirms the same shadow cell afterward |
| Right borders | each row `key+19` | Lock |
| Inter-row separators and bottom border | rows between item keys and box bottom | Lock |
| Status Window | separate hardware layer | Lock its map references and tile planes for the whole transaction |
| Unrelated BG cells | complement of the exact masks above | Must remain byte-exact on every sampled frame |

“Locked map cell” also locks the referenced tile pixels. A tile ID shown in a locked cell
cannot be returned to the allocator even if its original VWF row record is being replaced.

### Implemented transaction

1. The row-0 upload hook calls bank 60 far index `$07`. It requires screen `$01`, VWF
   Item mode `$01`, shadow key `$C380`, bank `$C3`, a nonzero allocator epoch, and LCDC
   bit 7. It bounds native item count `$C6AA` to one through twenty and drains `$C11A`
   before taking ownership. `mgbdis` shows that native Right/Left first commits `$C6AC`
   and then synchronously calls `4:$483E`; neither handler nor the redraw uses visible
   `$986F-$9872` as an input. Those four cells are rendered output and can legitimately
   still describe the outgoing page while the next redraw is already owned. The former
   exact-marker validation could therefore decline a valid redraw into state `$06`, whose
   legacy publisher disables the LCD. Admission now relies on the native screen, row,
   allocator-epoch, selector flow and item-count state instead. Initial entry remains
   excluded by the fresh-allocation state latch and is owned by the separate screen-1
   pre-clear gate; an unsupported row still retains the distinct state `$05` LCD-off
   safety fallback.
2. After the predecessor proof, the controller normally writes `$BE`
   to the five marker-coupled left borders and clears exactly the five status-marker,
   five cursor, and five 16-cell name interiors in shadow, then applies the same regional state to
   visible BG during VBlank. Interrupts are masked only across the VBlank rendezvous/copy
   so the native handler cannot consume the write window, and are restored immediately
   afterward. Selector `$FF` instead converts the complete five-row Items box to a
   complete empty one-row Floor box and structurally zeros rows 6-13. A completed Floor
   latch with an incoming carried selector performs the inverse conversion to a complete
   empty five-row Items box. The same VBlank zeros the four shared title references.
   These shape commits finish inside VBlank; state then becomes `$01`, and LCDC bit 7
   never changes.
3. The existing allocator resets its row records at the new row-0 epoch, but no reused
   tile pixels are published until the old visible name references are gone. In the exact
   transaction, each 16-byte glyph tile is copied from composition WRAM in four
   synchronized four-byte HBlank slices; if VBlank begins, the remaining four-byte slices
   continue immediately. Interrupts remain masked across this short direct transfer so
   the destination/source registers cannot be disturbed. Other shapes retain the native
   `$C11A` tile queue. Completed rows 0-3 remain unreferenced behind the regional blank.
   When row 4 is complete, all five rows' 19 owned map cells are copied from shadow to BG
   together in one VBlank. The border and marker therefore appear as one completed native
   pair and the body cannot cascade top-to-bottom. The helper publishes the cursor at
   `key+2`; only `key+19` remains outside it. Selector `$FF` uses the same helper for its
   one real row.
4. The native short-page representation has no `$FF`: it is an exact 19-byte all-zero
   field. Mode 3 recognizes only that representation and builds the empty shadow row for
   the final atomic body commit. Any other nonempty fallback sets state `$05`, disables the
   LCD during VBlank, and completes through the shared full-map publisher.
5. Native Right/Left changes `$C6AC` by five against a padded page bound and does not
   clamp the row to `$C6AA`. The regional admission therefore clamps an absent destination
   row to the final real item and updates `$C6A5` before blanking. The fast body publisher
   places the known screen-1 cursor tile `$81` at the resulting visible row in its VBlank;
   native `4:$4E2B` then writes the same cell to shadow. On an Items/Floor shape change,
   the later shape tail repeats the row-0 cursor copy with the completed title and
   indicator. Native
   `4:$4EB4` does not build the page indicator until after the body and header, which
   previously left a visually complete incoming page carrying the outgoing green dot for
   several frames. The exact
   final-body-row transaction now derives the same one-through-four-page map from
   `$C6AA/$C6AC` and commits `$C36F-$C372` to `$986F-$9872` in the same VBlank that
   publishes the complete body. The later native builder and redraw-tail copy are
   idempotent confirmation writes. The last body row also changes phase `$C1B6` from two
   to four only for an Items/Floor shape change, which forces native box 14/18 to compose
   the proper replacement word instead of reusing the outgoing static title. Completion
   of the four-cell header changes the phase to three.
   The `$4D7A`
   range-selector gate then publishes only `$C36F-$C372` to `$986F-$9872` at a
   scan-safe point for an ordinary page. A marked shape change instead publishes the
   completed four title cells and indicator together during VBlank. Unknown callers receive the
   native range values and continue into the untouched `$44A2` publisher. States
   `$05/$06` still route to the full fallback publisher. No Action, Info, or replay path
   can enter through the regional gate.

ROM ownership is explicit:

| Bank 60 range | Far index | Responsibility |
|---:|---:|---|
| `$405A-$4084` | `$05` | shared 20x18 fallback publisher |
| `$4090-$422D` | `$07` | exact screen-1 regional controller |
| `$422E-$429E` | `$0D` | Item/Floor Action B-pop proof and direct-return dispatch |
| `$4300-$43EE` | `$09` | initial/Pot/fallback controller |
| `$43F0-$447C` | direct | atomic five-row Item / one-row Floor body publisher, short-page selector clamp, and cursor commit |
| `$4480-$45A5` | `$0F` | Item page/header/cursor fast return plus native range-selector continuation |
| `$45A6-$45CE` | direct | final-body-row Items/Floor shape-phase marker and indicator dispatch |
| `$45E0-$46B0` | direct through `$0F` | scan-safe Item glyph-tile publisher |
| `$46B1-$46FF` | direct | native-equivalent page-indicator builder and VBlank publisher |
| `$4700-$4FFF` | — | redirected text; allocator origin raised to protect the code arena |

Allowed visual body states are `complete old -> complete regional blank -> complete new`.
Rows whose old and new pixels are identical may visually collapse adjacent states, but
the sole final-row VBlank hook proves there is no intermediate body publication. No row
may regress from new to blank or old.

### Checkpoint acceptance and evidence

- LCDC bit 7 stays enabled for every scoped Left/Right and Start-sort frame.
- Every Item name row is exactly old, blank, or complete new content.
- Header, right borders, separator rows, Window/status panel, and unrelated BG cells
  remain byte-exact on ordinary pages. Shape changes admit only blank or complete
  `Items`/`Floor` title interiors. Each left-border/marker pair is exactly old, `$BE,$00`, or complete
  new content; `$83,$00` and `$85,$00` are forbidden remnants.
- Page marker and cursor change only at their documented commit points.
- No tile-data slot is repainted while any visible BG or Window cell refers to it.
- A row becomes visible only after all queued or scanline-sliced bytes for its referenced
  tiles have landed.
- Tests cover one-, two-, three-, and four-page inventories; a selected row-5 transition
  into a one-item final page with selector/cursor clamp; every
  Right/Left page boundary including wraparound; reversal after settle; and Start-sort.
- Sampling continues through the transition tail to catch delayed replay or publication.
- Existing Action, Info, Pot, shop-price, hidden-identity, and debug fixtures still pass;
  they are adjacent ownership regressions even though their transitions remain LCD-off.

`tools/itempagespill.py` exercises eight complete five-row draws plus the native one-row
standing-item Floor page over four unique carried pages. Its seven direction presses cross the equipped
page-1 boundary both ways, then drive both physical stages of last-page-to-page-1 wrap;
Start-sort supplies the final redraw. Direct initial entry now records zero LCD-off frames;
every scoped Left/Right or Start-sort transaction also records zero. For each redraw it hooks the controller
immediately before shadow blanking,
after shadow blanking, and after BG blanking, proving that all 90
marker/cursor/name targets are zero, all five left borders are `$BE`, and the complement
is unchanged. Every sampled
left-border/marker pair is old, `$BE,$00`, or complete new content in both directions
across the equipped page boundary. Every sampled name row resolves by tile reference and both
physical bitplanes to old, blank, or complete new content. It directly hooks the sole
row-4 VBlank body commit, proves the raw marker returns with its incoming name, and locks
unrelated visible BG cells and structural tiles `$81`, `$83-$85`, `$B8-$BF`, and
`$C5/$C6`, and rejects state `$05/$06` on a
scoped flip. The standing-Floor wrap additionally proves that selector `$FF`, followed by the
selector-zero/all-`$BC` page-1 transient, begins two regional transactions with no fallback.
The second build invocation uses a 20-frame cadence and a carried-page-only four-page cycle;
all seven redraws remain regional with no fallback or LCD-off frame. It also records input
latency: those redraws are visually complete in 11-13 frames and return from the handler
in 15-17 frames. The ordinary cadence measures 11-16 visual frames and 11-20 handler
frames for carried pages; VBlank alignment on the Floor-to-five-row-Items header/body
conversion raises the bounded handler maximum to 23 frames.
Unlike the two-frame direct Action cancel, a page flip must compose five new proportional
rows; these values are therefore the bounded rendering cost, not an invisible replay tail.

`tools/floorpagespill.py` uses the Wood Arrow save to traverse selectors
`0,5,10,15,$FF`. After settlement it requires the one ground-item box at rows 3-5 and
twenty zero cells in every shadow and BG row 6-15. Three independent boots then leave
Floor by B, Right, and Left. B requires the same nine live Status uploads; Right returns
to selector 0 and Left to selector 15. Both paging exits require a byte-exact empty
five-row rectangle before text, while Items-to-Floor requires a byte-exact empty one-row
rectangle. All three routes require zero regional/status fallbacks, zero LCD-off frames,
and zero all-white frames. A second build route schedules every next input one frame after
native `4:$4856` returns. It proves exact `Floor` and `Items` title pixels at settlement
and crosses all four carried pages plus both Floor exits at the earliest accepted cadence.

`tools/fusioncountspill.py` synthesizes the shortest one-, two-, three-, and four-page
inventories (1/6/11/16 items). It cycles Right through every page and wrap boundary, then
Left through every page and wrap boundary, then invokes Start-sort: 3/5/7/9 real redraws,
all matched by regional begins, with zero fallback or LCD-off frames. Each blank commit
occurs during VBlank, contains `$BE` in all five left borders, and contains zero in all
five marker cells and all 80 name cells.

The real trace now reports `OOOOO -> BBBBB -> NNNNN`; identical empty rows can display
`=` without weakening the direct single-commit proof. The Start-sort capture likewise
exposes the complete five-row regional blank followed by one complete return while the
screen chrome remains visible. Automated correction
coverage also forbids the observed `$83,$00`/`$85,$00` vertical remnants. Checkpoint 1 is
the committed and visually accepted paging/Start-sort POC.

## Status-to-Items regional entry (checkpoint 2, entry direction)

Status and Items share the persistent hardware Window but replace essentially the whole
BG above it. A five-row Item mask is therefore insufficient on entry: Status VWF references
also survive in the header, menu choices, and value fields. The safe entry region is all
20 visible BG columns in rows 0-15. Rows 16-17 are covered by the Window at `WY=$80` and
remain locked together with the complete Window map and all planes it references.

The sibling `mgbdis` disassembly identifies the earliest safe screen-1 boundary:

```text
4:$494E  push af / push bc / push hl
4:$4951  ld hl,$C300
4:$4954  call $480E          ; clear 20x18 shadow cells, skipping stride tails
4:$4957  ld hl,$C549         ; item count/selector preparation follows
```

`statusvwf` replaces the six bytes at `$4951-$4956` with bank 53 far index `$09`. The
helper preserves the native shadow-clear result exactly and admits a live entry only with
this complete predecessor proof:

| State | Required value | Meaning |
|---|---:|---|
| `$C534` | `$01` | stack contains Status root plus the new Items child |
| `$C535/$C536` | `$00,$01` | exact root/Items screen IDs |
| `$C6A3/$C6A6` | `$01,$00` | direct screen-1 draw, not replay |
| `$C1B3` | `$00` | no other translation transaction owns the screen |
| `$C6AA` | `$01-$14` | one through twenty real items |
| `$C6AC` | less than `$C6AA` | valid retained selector before native reset |
| `LCDC & $F8` | `$E0` | LCD and Window enabled with signed BG tiles |
| `SCY/SCX` | `$00,$00` | ordinary menu viewport |
| `WY/WX` | `$80,$07` | persistent bottom Window |
| BG `$986F-$9872` | four `$00` cells after queue drain | exact Status predecessor, not a same-stack Item-page redraw |

The helper first drains `$C11A` and reacquires VBlank before reading the four predecessor
cells. It then clears four 20-cell BG rows per complete VBlank,
for four batches covering visible columns 0-19 in BG rows 0-15. Row tails, hidden BG rows
16-17, the `$9C00` Window map, and every tile plane stay byte-exact. Interrupts are masked
only while a batch is copied and are restored between VBlanks; all four measured batches
finish at LY `$94`.

The native order after this boundary is box 4's five Item rows, then box 14's `Items`
header, and only then `$4620` full-map publication. Publishing completed rows immediately
therefore produced the visually inverted sequence `text -> boxes`. At the end of the
fourth entry VBlank, the helper now commits the static box-14 header perimeter and complete
box-4 list perimeter while leaving both text interiors blank. The chrome commit finishes
inside VBlank and changes no tile plane. Item rows then appear progressively inside the
established list box; the native final publisher adds `Items`, the page indicator, and the
exact completed map. The visible order is now `regional clear -> empty boxes -> complete
text rows -> final decoration`, never text floating on an unframed field.

After retirement and chrome publication, state `$01` authorizes the existing completed
Item-row publisher. The helper performs the native 20x18 stride-aware shadow clear, each
Item row appears only after its VWF upload completes, and native `$4620` remains the final
map authority. Unknown callers receive only the original shadow clear and later fall
through to the conservative path.

`tools/itementryspill.py` independently starts from pages 1, 2, 3, and 4, exits to Status,
reopens Items, and immediately pages right. Each run requires one accepted entry, four
LY-`$94` blank batches, an exact chrome-first BG map completed inside VBlank before the
first Item-row call, an unchanged Window and tile planes, zero LCD-off/all-white frames,
and exactly one following five-row regional transaction with zero fallback. This covers
re-entry after every prior page-selector lifetime, not only the first opening.

## Items-to-Status live exit (checkpoint 2, exit direction)

The exit requirement is explicit: pressing B on carried page 1, 2, 3, or 4, or on the
settled standing-item Floor page after them, must not blank the screen. This route does
not need an Item-region blank. The outgoing page owns the display
until the native Status publisher progressively replaces its cells with completed Status
content.

The native B handler at `4:$5689` reaches the generic pop call at `4:$568C`, reconstructs
screen 0, and invokes the Status field boundary at `4:$4FDD`. At that boundary the exact
direct predecessor is:

| State | Required value | Meaning |
|---|---:|---|
| `$C534` | `$00` | stack depth after the Items child was popped |
| `$C535/$C536` | `$00,$01` | surviving Status root plus stale popped Items entry |
| `$C6A3` | `$00` | Status is the screen currently being reconstructed |
| `$C6AA` | `$01-$14` | one through twenty items, hence at most four pages |
| `$C6AC` | less than `$C6AA`, or `$FF` with `$C1B7=$01` | a real selected carried item, or the independently proven completed standing-item Floor page |
| `LCDC & $F8` | `$E0` | LCD on, signed BG tiles, Window configuration intact |
| `SCY/SCX` | `$00,$00` | ordinary menu viewport |
| `WY/WX` | `$80,$07` | persistent two-row status Window at the bottom |

Only that complete predicate selects the live exit. Any unknown LCD-on Status return uses
the retained LCD-off fallback. Name-to-Items is not silently admitted by this exit gate:
it has the separate two-half state-`$0D` proof below, and after it settles a later direct
Items B pop can qualify normally.
Every admitted pop clears `$C1B6` as well as `$C1B7`: phase 3 can remain after the
initial Items build because that path has no same-screen redraw-tail call, but it owns
nothing after Items has been popped. The `$FF` branch still requires the Floor latch;
selector `$FF` alone is never sufficient.

The outgoing visible BG and Window reference none of the 40 private Status field IDs or
the eight structured Weapon/Shield IDs. Those 48 tile planes may therefore be restored
without changing a displayed Item pixel. `statusvwf` composes nine fields—Strength,
Experience, and seven values—then uploads each completed slice in its own VBlank. The
largest slice is seven tiles/112 physical bytes. Every copy starts at LY `$90`; observed
completion is LY `$92-$97`, inside the ten-line VBlank. Weapon and Shield retain their
source-stable four-tile fragments and need only their map references restored.

The VBlank rendezvous deliberately rejects a late VBlank tail. A real page-2 phase showed
that a native interrupt can begin just before `DI` and return at LY `$97`; treating that
as a fresh budget pushed the first upload through line 3. The controller now masks at the
end of visible scanout, rechecks LY, waits through the next visible frame if it arrived
late, and establishes BC/DE/HL only after interrupts are masked. Thus an interrupt cannot
corrupt either the byte count or VRAM destination.

`tools/itemexitspill.py` boots the real 18-item save four times and independently leaves
selectors 0, 5, 10, and 15. For every page it requires the exact stack/hardware predicate,
nine cap-ordered uploads `(6,7,5,2,4,4,4,4,4)`, starts at LY `$90`, completion no later
than LY `$99`, zero LCD-off frames, and zero all-white frames. At every sampled frame each
visible BG cell resolves to either its outgoing Item raster or final Status raster and
never regresses; the enabled Window map and all of its referenced planes remain exact.
All four routes settle to the same visible Status raster. The unidentified-item Name
fixture separately proves one regional Name reconstruction followed by one live direct
Items exit.

`tools/floorpagespill.py` independently covers the fifth-page form. Its Status-entry
snapshot requires selector `$FF`, latch `$01`, the exact `0,0,1` stale stack and standard
viewport. It observes the same nine VBlank uploads and verifies that the latch is zero
after the final Status screen, with no full-screen blank.

## Checkpoint-2 acceptance record

Checkpoint 2 was frozen on 2026-08-23 against implementation commit `3489572` after it
passed manual review and the complete regression battery. The accepted visual contract
is:

- Status-to-Items retains the bottom status Window, regionally clears only the replaceable
  BG, publishes both empty box perimeters, and then reveals completed Item text rows.
- Items-to-Status leaves pages 1-4 visible until completed Status fields replace them; no
  Item page may trigger a full-screen blank on this direct exit.
- Paging in either direction and Start-sort retain the checkpoint-1 five-row regional
  redraw, including short inventories and every wrap boundary.

Any later change to these routes must preserve the ownership predicates and fixture-backed
fallbacks documented above, then pass a new visual review. Later checkpoints must not
broaden this frozen scope implicitly.

The 2026-08-24 standing-item Floor correction extends the implementation beyond that
historical pages-1-4 acceptance record. Its automated and visual contracts are accepted
as part of the checkpoint-3 freeze at `34a20ec`.

## 2026-08-30 grouped-follow-up root causes

The first six-case follow-up failed even though narrower injected fixtures passed. The
fixes below are now required regression evidence rather than inferred behavior:

- A real Log-3 sealed weapon uses screen 5's automatic final-A path with native page
  counter address `$C6BC` left in HL. The generic pop gate recognized that signature only
  when the pop depth was two (carried Items/appended Floor). Direct screen-20 Floor pops
  one level, so the identical signature fell through to `fidisable`. The pop classifier
  now sends `$C6BC` to the same exact `infoowned` predicate in both depth branches. The
  no-Lua regression begins from a normally carried fixture, performs the real Drop onto
  an empty dungeon tile, and separately proves direct and appended parents.
- `mgbdis` exposed a second late blank which was not a translation fallback. Native
  `2:$4621` is the shared Japanese menu-to-gameplay display reconstruction;
  `2:$463C` clears bit 7 of shadow LCDC `$C110`, and VBlank `0:$0737` publishes it. An
  early candidate tried to suppress that body when a completed direct-Floor descriptor
  was still live. The same descriptor is also present on the real Floor-to-field exit,
  so the predicate stranded the Action image and later froze Status re-entry. The hook
  is now removed: `2:$462F` retains its byte-for-byte native `$C9DC==2` check, and the
  regional controller owns only menu-to-menu work before this boundary. The natural
  Drop regression now presses B through field reconstruction and reopens Status, rather
  than declaring success at the first transient screen/state change.
- Direct screen-20 Action mode 4 keeps only its exposed top verb private, but its
  admission snapshot also leaves `$C1B5/$C1B6=$20/$04`. The exact screen-20 Pot `See`
  entry accepts the same phase-four header state, clears it before publishing empty Pot
  chrome, and still rejects phase four for screen 7. The seven-row screen-7 Pot did
  not have that pair, which is why its Name tests passed while the ordinary six-row
  Willow Staff still used the native font/LCD reset. Name admission now recognizes that
  pair only with the complete `0,20,9` stack, ground selector, shape, height, and hardware
  proof, then clears both bytes before the keyboard owns the screen.
- `$C0E7=1` is the regional short-page empty-row marker, not a one-cell shop suffix.
  Passing it to `copyprice` copied stale staging tile `$88` into the last empty row. Shop
  suffix publication now requires a length of at least two.
- Contained-Pot Info return needs its own early retirement. State `$17` publishes complete
  empty Pot chrome before the native `0 -> 1 -> 2 -> Pot` replay can reuse outgoing Info
  planes. The restored screen-12/13 page must then consume `$17`, enter ordinary Pot
  publication state `$0C`, and clear to idle `$00`; leaving `$17` alive looked correct
  until Pot -> Items -> Status -> field, then froze the next Status entry with LCDC off.
  The contained-Pot regression now performs that complete exit and reopen. `mgbdis` also
  proved screens 2 and 16 share native Action drawer `4:$4987`, so exact screen 16 reserves
  its exposed top verb in a collision-scanned private slice. Direct shop Floor mode 4
  does the same for visible `Take`.

These discoveries are why natural save-backed routes and `mgbdis` call-site traces are
mandatory for this menu work. A synthetic object record can prove the regional renderer
while still missing the caller's real stack depth, native handler address, or later
display reconstruction.

## What remains deliberately outside exact Item/Floor admission

- **Other Info and Action callers:** checkpoint 4 admits only the exact screen-1,
  screen-7, and screen-20 stacks described above, plus exact carried screen-12/13 B
  return and exact carried/Items-appended-Floor/screen-7/screen-20 Pot entries and
  ground-Pot B returns, the screen-11 Put selector, and the no-cheat shop Floor/Info
  cycle, plus exact contained-item screen-16 Action/Info. `Push`, malformed screen-16
  descriptors, and forced/unknown Info callers retain their safety fallbacks. Committing
  `Put` intentionally leaves the menu for a dungeon
  action and therefore retains the base engine's two new-screen blanks. Shared screen
  IDs do not imply shared ownership.
- **Start/title composites:** log summaries, confirmation, difficulty, Rank/Pass, Fay, and
  Rankings borrow planes across several boxes. Their current atomic controller remains.
- **Map, Quit, Replay, and gameplay verbs:** these are replacement paths. Preserve their
  native blank/transition unless a separate visual defect is demonstrated.
- **Unknown Name entry/return contexts:** carried entry is admitted only by the exact
  `0,1,2,9` stack/viewport proof above, and the matching inventory return only by the
  separate state-`$0D` proof below. Any other screen-9 caller or malformed replay retains
  its catalogued native/Status LCD-off fallback; shared screen IDs do not authorize the
  inventory mask.
- **Forced context-dependent screens:** a forced screen can draw plausible garbage or
  run through invalid state. It cannot authorize a blanking mask.

## Remaining exploration and implementation worklist

1. Extend the direct Window reference-set audits used by `itemexitspill.py` and
   `itementryspill.py` to any future
   route that keeps the hardware Window enabled.
2. Treat future alternate Pot-content, shop action, or screen-16 callers as independent
   ownership epochs; the current exact Put-selector and shop Floor/Info proofs do not
   authorize them.
3. Capture complete dispatcher logs for New Log, Copy Log, Erase Log, Rename, Rank, Replay,
   and every staged action verb. Replace every `outline`/`inferred` edge before using it as
   an implementation boundary.

The implemented scope remains narrow: screen-1 paging/Start-sort owns an exact five-row
mask; direct Status-to-Items owns BG rows 0-15 while locking the Window; direct
Items-to-Status owns only nine private field uploads; and admitted screen-2 Action
B-cancel owns box 6 plus the exact Item/Floor input state needed for its direct return.
The accepted checkpoint-4 scope additionally owns screen-4/5 BG rows 3-15 and, on exact return,
only the five proportional text interiors plus five pager cells while locking all chrome
and the Window. Its exact screen-20 Info and Pot-viewer returns own complete title/Action
chrome before text;
its exact screen-7 return independently owns complete box-5/y=1 box-6 chrome and seven
Action interiors; exact carried, Items-appended Floor, screen-7, and screen-20
screen-12/13 Pot entries own BG rows 0-15 while locking the Window, and carried return
hands off to direct Items-entry ownership. No other caller
inherits those masks. Native
final-map publication remains authoritative on every rebuilding route. Every direction
retains the existing full-screen-safe path whenever an allowlist or ownership assertion
fails.
