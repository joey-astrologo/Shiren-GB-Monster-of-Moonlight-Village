# Consolidated Item/Floor manual test

This records the accepted grouped visual pass for the 2026-08-30 Item/Floor
regional-blanking checkpoint, including follow-ups `IFR-01` through `IFR-09`. Every SRAM
is tracked, hash-verified, and reached through normal game state; no Lua script,
GameShark write, or emulator state is used.

## Build and stage the isolated cases

Run from the repository root:

```sh
./build.sh
python3 tools/prepareitemfloortests.py build/shiren_en.gb
TEST_ROOT="$PWD/build/manual-tests/item-floor-$(shasum -a 256 build/shiren_en.gb | cut -c1-12)"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$MESEN_SAVES"
```

Use the ROM hash and directory printed by `prepareitemfloortests.py`; do not rename or
reuse an older staged ROM. Visual acceptance applies only to the exact hash recorded
below.

Accepted on 2026-08-30: SHA-256
`3eca647016f1b78df6be91925d5ec145ab548a288685cdb1ac30e99e23bd5983`, staged under
`build/manual-tests/item-floor-3eca647016f1/`. All six focused rechecks passed against
this ROM in one clean grouped run. No focused recheck remains pending, and no standalone
rerun of checks 1 or 6 is required. A later all-nine-seal footer defect is tracked in the
post-freeze amendment below; it requires one new route, not a repeat of those accepted
checks.

Define this helper once in the same shell:

```sh
run_item_floor_case() {
  case_name="$1"
  test_base="shiren_$case_name"
  cp -f "$TEST_ROOT/$case_name/$test_base.srm" \
    "$MESEN_SAVES/$test_base.srm"
  open -na "/Applications/Mesen.app" --args \
    "$TEST_ROOT/$case_name/$test_base.gb"
}
```

Close Mesen before starting or resetting a case. The helper overwrites only a uniquely
named test SRAM such as `shiren_03_floor_names.srm`; it never touches the normal
`shiren_en.srm` or another personal save. To reset a route, close Mesen and invoke the
same `run_item_floor_case` command again.

## What every menu-to-menu transition must do

- Keep the bottom HUD Window visible.
- Never turn the whole LCD white unless the instructions explicitly mark a transition
  as a gameplay/new-screen boundary.
- Retire outgoing text regionally, draw complete incoming borders/chrome, then reveal
  completed text and cursor rows.
- Never show destination text through an old box, old text through a new box, a partial
  border, stale page dot, missing cursor, or delayed `E` marker.
- Accept input as soon as the screen appears settled.

## Acceptance history recorded 2026-08-30

The nine broad baseline contracts passed. The first grouped follow-up did **not** pass:
it exposed six concrete defects/history gaps. Those results supersede the earlier claim
that the Item/Floor batch was ready for acceptance.

| Finding from the failed batch | Root cause now covered automatically | Final manual status |
|---|---|---|
| Sealed Info final-A blanked on held, direct-Floor, and appended-Floor returns | the one-level screen-20 `$C6BC` final-A handler was missing from the regional pop gate; real no-Lua Drop routes now cover both Floor parents | Passed rechecks 1-3 |
| Short Item page 2 showed a stray `#` at lower right | regional empty-row marker `$C0E7=1` was mistaken for a one-cell shop suffix | Passed recheck 1 |
| Contained Storage-Pot Info returned through mixed stale text, then later froze after leaving/reopening menus | outgoing Info references survived until native Pot replay reused their tile planes, and replay state `$17` was never handed to restored-Pot state `$0C`/idle `$00`; the regression now exits through gameplay and reopens Status | Passed recheck 4 |
| The prior zero-seal test duplicated sealed-Info coverage and still failed | removed from this acceptance list; the real fused zero-seal row remains in the already-passed equipment regression | Not repeated |
| Shop Info overwrote the visible `Take` row behind it | direct screen-20 Action now reserves a private top-row slice and preserves it plane-exactly | Passed recheck 5 |
| Direct Floor Name blanking depended on prior Name/Info history | ordinary screen-20 Action reaches Name with `$C1B5/$C1B6=$20/$04`; that exact live pair is now consumed and cleared | Passed recheck 6 |
| Direct Floor exits in checks 2/3/5 froze with the Action image still visible | a candidate bank-37 predicate suppressed native Japanese menu-to-gameplay reconstruction `2:$4621`; the hook is removed and direct dropped-equipment/shop regressions now require live gameplay plus a successful Status reopen | Passed rechecks 2, 3, and 5 |

The passing results for checks 1 and 6 from the rejected ROM were not used to freeze a
mixed candidate. All six were rerun against the accepted hash above and passed together.

## Implemented and visually accepted follow-ups

Each follow-up has an exact regional owner, a deterministic regression, and manual visual
acceptance through the numbered routes below.

| ID | Original defect | Implementation proof | Visual acceptance |
|---|---|---|---|
| `IFR-01` | sealed held equipment blanked on automatic final-page A return | `iteminfospill.py` hooks native `$C6BC` separately from B; zero off/uniform frames and exact parent/input | Complete the last page with A; Items chrome precedes rows and the cursor moves immediately |
| `IFR-02` | dropped sealed equipment blanked on automatic final-page A return | `iteminfospill.py` uses the naturally carried Log-3 fixture, performs the real Drop action, and proves both `0,20,5` and `0,1,2,5` final-A pops with zero off/uniform frames and prompt input | Complete the seal page; Floor border/cursor return without a full blank or stale Info cells |
| `IFR-03` | Info-before-Name left keyboard/status fragments during return | carried Info-then-Name B and End routes drain pending work and retire the keyboard before Items publication | Test both B and End histories; borders appear before rows and input is immediate |
| `IFR-04` | contained-item Action -> Info blanked | stack proof distinguishes carried/appended `0,1,2` and ground `0,7/20` Pot parents; populated Storage-Pot regression reaches Info with zero off writes | Info chrome appears before its text while the HUD remains visible |
| `IFR-05` | contained Info -> Pot contents blanked | state `$17` preserves Pot screen/selector and publishes complete empty Pot chrome before content rows | The same Pot title, contents, selection, and Action context return without stale rows or delay |
| `IFR-06` | initial appended shop Floor omitted the right-hand price | fast one-row publisher now invokes the native price suffix helper; initial and post-Info `$D0-$D2` shadow/BG cells both equal `3600`; Info stays LCD-live both ways | Price is present on first arrival and unchanged after Info; no full blank in either direction |
| `IFR-07` | direct seven-row Pot Action -> Name blanked | `unidentifiedpotnamespill.py` proves exact `0,7,9` entry with no native whole-screen restore | Keyboard/name chrome appears complete with HUD and LCD live |
| `IFR-08` | direct Pot/ordinary Floor Name End/B blanked and retired text out of order | independent Pot and Willow-Staff End, initial-empty B, named-then-erased B, repeated-B, and Info-first histories use their exact action-state pairs with zero off/uniform frames | Test the ordinary direct-Floor histories in recheck 6; complete Floor/Action chrome precedes labels and cursor |
| `IFR-09` | appended Floor Name then Action B blanked | exact `9,0,1,2` Name return followed by Action B reaches responsive screen 1 with zero Status fallback/off/uniform frames | Already passed in the broad baseline; retain as automated regression |

## Focused six-test recheck — all passed 2026-08-30

These are the exact manual checks used to accept the ROM above. Each case was reset before
its numbered test so no history or emulator SRAM leaked between them.

### Recheck 1 — held sealed return and short-page cleanup — PASS

```sh
run_item_floor_case 03_floor_names
```

Load Adventure Log 3. Open B -> `Items`, select the first row (`Drain Slayer+15`), open
its Action list, choose `Info`, and press A once on the seal summary to return
automatically. Then press Right to Item page 2.

Expected: the return never blanks the whole LCD; complete Items chrome precedes rows;
the cursor responds immediately; page 2 has no isolated `#` or any other glyph in its
empty lower-right rows.

### Recheck 2 — naturally dropped seal, appended Floor return — PASS

```sh
run_item_floor_case 04_carried_name
```

Load Adventure Log 3. This fixture has already taken the Willow Staff, so the dungeon
tile is empty. Open `Items`, select first-row `Drain Slayer+15`, choose `Drop`, and wait
until field input returns. Open B -> `Items`, page Right until the appended `Floor` page,
open the weapon's Action list, choose its last `Info` row, and press A once.

Expected: final-A returns to the appended Floor page without a whole-LCD blank, stale
seal text, malformed border, or delayed input. Press B to return to Status, B again to
return to gameplay, then B to reopen Status; none of those inputs may strand or freeze
the menu.

### Recheck 3 — naturally dropped seal, direct Floor return — PASS

```sh
run_item_floor_case 04_carried_name
```

Repeat the same real Drop from a freshly reset case. This time open B -> `Floor`; its
Action list appears directly. Choose the last `Info` row and press A once.

Expected: the complete direct-Floor title/Action parent returns without a whole-LCD
blank. Press B immediately after it settles; direct Floor must return promptly to live
gameplay. Press B again and require a complete, responsive Status screen. This exit and
reopen are part of the test, not optional exploration.

### Recheck 4 — contained Storage-Pot Info return order — PASS

```sh
run_item_floor_case 05_pot_put
```

Load Adventure Log 2. Use B -> `Floor` -> default `Take` on the Storage Pot and dismiss
the pickup text. Open `Items`, select the Storage Pot on row 4, choose `Put`, and put the
default Big Onigiri inside. Reopen the Pot, choose `See`, select Big Onigiri, open its
Action list, choose its final `Info` row, then press B.

Expected: Info entry and return remain LCD-live. On return, complete empty Pot title/body
chrome appears before the restored content row and cursor. No mixed fragments such as
`Ite`, `Pow`, `all Storage...`, or partial action verbs may appear, and the exposed top
Action verb must remain correct while Info is visible. Then press B from the Pot viewer,
B from Items, B from Status, and B once more in gameplay: the field must regain input and
the reopened Status screen must render completely without a freeze.

### Recheck 5 — shop `Take` preservation and Gitan — PASS

```sh
run_item_floor_case 08_shop_floor
```

Load Adventure Log 3. Open B -> `Floor`, move to `Info`, and enter it. While Info is
visible, inspect the exposed top row of the Action box behind the upper-right Info
window; it must still say `Take`, not the first line of the Happy/Insight Bracer text.
Return with B. Reset, open `Items`, page to appended `Floor`, and confirm the right-side
price is present both before and after its Info round trip.

Expected: `Take`, Gitan/price, borders, and cursor remain correct with no LCD blank. On
the direct route, press B after Info has returned, verify live gameplay, then press B
again and require a complete responsive Status screen.

### Recheck 6 — direct Floor Name history matrix — PASS

```sh
run_item_floor_case 03_floor_names
```

Load Adventure Log 3 and use B -> `Floor`; choose `Name` on the Willow Staff. Reset the
case between these histories:

1. Press B immediately on the empty name, reopen `Name`, and press B again.
2. Enter `A`, select `End`, confirm, reopen `Name`, press B to erase `A`, then B again.
3. Choose `Info` first and return; choose `Name`, press B on the empty name, reopen it,
   and press B again.

Expected: Name entry and every exit stay LCD-live. The upper BG retires regionally while
the HUD remains; complete Floor/Action chrome precedes its labels; no keyboard garbage or
native full-screen flash appears; the restored action list accepts input immediately.

### Focused acceptance result

All six rechecks passed on 2026-08-30 against SHA-256
`3eca647016f1b78df6be91925d5ec145ab548a288685cdb1ac30e99e23bd5983`.
Together with the already accepted nine-case baseline below and the automated gates,
this freezes the catalogued Item/Floor regional-blanking scope. Malformed or unproved
callers still retain their documented safety fallbacks, and gameplay/new-screen
boundaries retain their intentional native whole-LCD transitions.

## Post-freeze all-seal footer recheck — passed

The accepted six-test ROM did not cover screen 5 with more than four seals. On 2026-08-30
an all-nine-seal weapon exposed corrupt page digits. The corrected weapon and symmetric
all-nine-seal shield routes passed visual review on 2026-08-30 against accepted SHA-256
`8e14822ea2e1834ef5b620fb39607667b2df1b87e5ded33b8b0ba3a42cc47a29`.
`fusioncountspill.py` now independently requires exact
`1/3`, `2/3`, and `3/3` map cells and digit pixels plus an LCD-live B return for both the
contiguous weapon mask `$01FF` and the non-contiguous shield mask `$06FD`.

Build the candidate, open it with a disposable dungeon save, and load
`tools/mesen_spawn_fusion_kit.lua` in Mesen's Script Window. The script appends a
Fusion Pot, a configurable weapon carrying all nine weapon seals, and a configurable
shield carrying all nine shield seals; it does not need a personal save or a second
memory-edit script.

The accepted shield procedure was: open B -> `Items`, select the spawned
`Rasen Fuuma+1`, choose `Info`, then press Right once per four-description group. Inspect
the lower-right footer on all three settled pages and press B from the last page.

Accepted result: the shield footer is visibly `1/3`, then `2/3`, then `3/3`; neither
digit is replaced by letters, fragments, or garbage pixels. Page changes and B return
remain LCD-live, chrome-first, and immediately responsive.

## Baseline appendix — already accepted, not part of the six-test recheck

## 1. Four Item pages, sorting, and Status return

```sh
run_item_floor_case 01_item_pages
```

Load Adventure Log 1. In the dungeon press B and select `Items`. Page rapidly Right and
Left through all four pages, including wraparound, then press Start several times to
sort. Move Up/Down after each redraw and watch the green page dot and every `E` marker.
Finally press B to return to Status.

Expected: no whole-screen blank, corruption, stale page dot, missing cursor, or delayed
equipment marker during entry, paging, sorting, or Items -> Status. Pressing B once more
from Status intentionally returns to gameplay and may use the native full-screen blank.

## 2. Items-appended Floor shape, Action, and Info

```sh
run_item_floor_case 02_floor_pages
```

Load Adventure Log 1, open `Items`, and page Right through carried pages to the appended
`Floor` page. Page both Right and Left across the Items/Floor boundary several times,
including rapid inputs. On Floor, open the Action list, press B to close it, reopen it,
choose `Info`, page the description normally, and return. Also return from the appended
Floor page to Status.

Expected: both shape directions have complete borders before text; the selected Floor
row and cursor settle correctly; Action B restores the exact Floor parent; Info returns
to that parent; no menu-to-menu whole-screen blank occurs.

## 3. Both Floor Name parents and all six return histories

```sh
run_item_floor_case 03_floor_names
```

Load Adventure Log 3. Test the two parents separately:

1. Direct parent: B -> `Floor`, then choose `Name` in the standing Willow Staff's Action
   list.
2. Appended parent: B -> `Items`, page Right until `Floor`, then choose `Name` in its
   Action list.

For each parent, reset the fixture between these three variants:

1. Enter Name and immediately press B with the field empty.
2. Enter one `A`, press Start to select `End`, and press A to confirm.
3. Enter one `A` and confirm `End`; reopen `Name`, press B once to erase `A`, then press B
   once more to leave the empty field.

Expected: all six routes keep the HUD and LCD live. The keyboard retires regionally;
complete Floor and Action borders appear before their labels and cursor. The restored
Action list accepts Up/Down immediately. The `End` underline remains an underline, not
the word `Wave`.

## 4. Carried-item Name smoke test

```sh
run_item_floor_case 04_carried_name
```

Load Adventure Log 3. Open `Items`, page Right to page 2, select the unidentified Willow
Staff, and choose `Name`. Enter one `A`, confirm `End`, reopen `Name`, erase the `A`, and
press B again to leave.

Reset the fixture for each history. On the same Willow Staff choose `Info` first and
return to Items, then choose `Name`: once leave with an empty-field B, and once enter an
`A`, select `End`, and confirm.

Expected: keyboard entry and both returns are chrome-first, LCD-live, and immediately
responsive. In the Info-first histories, no keyboard, Status value, or Name-box fragment
may remain while Items rows appear. This is the carried `0,1,2,9` family, independent of
the two Floor families in case 3.

## 5. Storage Pot Put selector and post-action replay

```sh
run_item_floor_case 05_pot_put
```

Load Adventure Log 2. Press B, choose `Floor`, and choose the default `Take` on the
Storage Pot. Dismiss the pickup/description messages until the dungeon field is live.
Open B -> `Items`, move to the fourth row Storage Pot, open Action, move Down once to
`Put`, and press A. The Put selector begins on Big Onigiri; press A to commit it. After
Items returns, reopen the Storage Pot, choose `See`, select the Big Onigiri inside, open
its Action list, choose its final `Info` row, and press B from Info to return to the Pot
contents. Then leave the Pot viewer, press B once from Items, test Up/Down, and press B
again to reach Status.

For the two ground parents, reset and repeat through the successful Put. From the rebuilt
Items page open the Storage Pot Action list and choose `Drop`; dismiss the real dungeon
action until input returns. Test the populated Pot twice, resetting between variants:

1. Direct parent: B -> `Floor` -> `See` -> contained Big Onigiri -> Action -> `Info` -> B.
2. Appended parent: B -> `Items`, page Right to `Floor`, then `See` -> contained Big
   Onigiri -> Action -> `Info` -> B.

Expected: Action -> Put selector is regional and box-first. Confirming Big Onigiri is an
intentional exception: the menu blanks to a visible dungeon action, and the completed
action blanks into a newly built Items screen. Those are two genuine new-screen
boundaries found in the base engine, not a same-menu flash. The first B replay and final
Items -> Status transition must not add another whole-screen blank. Contained-item
Action -> Info and Info -> Pot contents must also stay LCD-live: complete Info chrome
precedes description text, then complete Pot title/body chrome precedes restored
contents and cursor. Status -> field may use the intentional native teardown.
Dropping the Pot is another real menu-to-gameplay boundary and may use the native blank;
the later Floor/Pot/Info menu-to-menu edges may not.

## 6. Real fused equipment row

```sh
run_item_floor_case 06_equipment
```

Load Adventure Log 2 and open B -> `Items`. Inspect the equipped/fused Nagamaki and its
zero-seal marker. Open its `Info`, advance with A through every seal/description page so
the final page returns automatically, then move the cursor and leave to Status.

Expected: Status -> Items remains LCD-live, the full proportional name and native
equipment/fusion markers coexist, no row or marker appears late, and the automatic
final-A return is chrome-first and immediately responsive. The automated companion test
additionally covers the hostile plated/cursed/fused three-row mix that a natural compact
SRAM cannot conveniently stage.

## 7. Shield Info and seal pages

```sh
run_item_floor_case 07_shield_info
```

Load Adventure Log 1, open `Items`, select the two-star shield, and choose `Info`. Page
through every description/seal page with deliberate single presses, then return to
Items and move the cursor immediately.

Expected: page numbers are correct; one Down press does not auto-scroll; Info/seal pages
and the return are regional and chrome-first; the cursor is clamped to a real row.

## 8. Shop Floor/Action/Info cycle

```sh
run_item_floor_case 08_shop_floor
```

Load Adventure Log 3. Shiren stands on the shop Insight Bracer. Press B, choose `Floor`,
move Down three times in the Action list to `Info`, press A, then press B to return.

Reset the fixture. Press B, choose `Items`, and page Right through all four carried pages
to the appended `Floor` page. Before opening anything, confirm that the selected Insight
Bracer already shows its right-aligned `3600` price. Open Action, move to `Info`, enter,
and press B to return; confirm that the same price is still present.

Expected: both the direct and Items-appended Floor -> Action -> Info -> Floor paths have
no whole-screen blank. `Price`, `G`, both values, Action labels, borders, and cursor stay
complete. The appended price must be present on first arrival—not only after Info. The
earlier grouped audit hits at native `2:$463C`/`4:$4154` were isolated to boot/field
loading, not this shop menu cycle.

## 9. Seven-row unidentified Pot Floor Action

```sh
run_item_floor_case 09_unidentified_pot
```

Load Adventure Log 3. Press B -> `Floor`; the unidentified Pot produces the unique
seven-row Action list. Exercise `See` and `Info` separately, returning to Floor after
each, and move through all seven Action rows.

Reset for each Name exit. From the direct seven-row Action list choose `Name`: first
press B immediately on the empty field; then reset, enter an `A`, select `End`, and
confirm. Finally reset, enter B -> `Items`, page Right to its appended `Floor`, open the
same seven-row Action list, choose `Name`, return with B, and press B once more to dismiss
the still-open Action list.

Expected: every row is proportional; Action, See/Info entry, and both returns keep the
LCD/HUD live. Both direct Name exits retire the keyboard before complete Floor/Action
chrome and labels. The appended post-Name Action B returns directly to responsive Items
without another flash. The restored top-left title, seven-row border, cursor, page
number, and parent text are complete and correctly ordered.

## Optional automated confirmation

The grouped visual pass is backed by these focused commands:

```sh
python3 tools/itempagespill.py build/shiren_en.gb
python3 tools/floorpagespill.py build/shiren_en.gb --rapid --settle-frames 1
python3 tools/flooractionspill.py build/shiren_en.gb
python3 tools/unidentifiednamespill.py build/shiren_en.gb
python3 tools/unidentifiedpotnamespill.py build/shiren_en.gb
python3 tools/potputspill.py build/shiren_en.gb
python3 tools/potcontentinfospill.py build/shiren_en.gb
python3 tools/equipmentmarkerspill.py build/shiren_en.gb
python3 tools/iteminfospill.py build/shiren_en.gb --frames 5200
python3 tools/shopspill.py build/shiren_en.gb
python3 tools/unidentifiedpotspill.py build/shiren_en.gb
```
