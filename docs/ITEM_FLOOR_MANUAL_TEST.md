# Consolidated Item/Floor manual test

This is the visual acceptance pass for the 2026-08-29 Item/Floor regional-blanking
implementation. Every SRAM is tracked, hash-verified, and reached through normal game
state; no Lua script, GameShark write, or emulator state is used.

## Build and stage the isolated cases

Run from the repository root:

```sh
./build.sh
python3 tools/prepareitemfloortests.py build/shiren_en.gb
TEST_ROOT="$PWD/build/manual-tests/item-floor-$(shasum -a 256 build/shiren_en.gb | cut -c1-12)"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$MESEN_SAVES"
```

The current candidate is expected to report ROM SHA-256
`3454c095d2c94f3aa5167abd67c34c9e425da1b5a8e89e9b3e2c5900facd8a7d` and stage
`build/manual-tests/item-floor-3454c095d2c9`. If the hash changes after another code
edit, use the new path printed by `prepareitemfloortests.py`; do not rename an old ROM.

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

## Manual result recorded 2026-08-30

The nine original test contracts were exercised successfully. The same fixtures also
exposed nine additional route/history variants which were not covered by those original
contracts. A pass below therefore means the named baseline remains accepted; it does not
silently approve the newly discovered work linked in the last column.

| Test | Baseline result | Newly exposed work |
|---:|---|---|
| 1 | Pass: four-page entry, rapid paging, sorting, markers, cursor, and Status return | none |
| 2 | Pass: Items/Floor shape conversion, Action B, ordinary Info, and Status return | none |
| 3 | Pass: both Floor Name parents and all six originally requested Name returns | `IFR-01`, `IFR-02` |
| 4 | Pass: direct carried-item Name entry, End, reopen/erase, and B | `IFR-03` |
| 5 | Pass: Put selector, field action, rebuilt Items, and both B returns | `IFR-04`, `IFR-05` |
| 6 | Pass: fused equipment row and marker publication | confirms `IFR-01` with another sealed weapon |
| 7 | Pass: shield Info/seal paging and return on its prescribed route | none |
| 8 | Pass: direct shop Status/Floor/Action/Info/Floor cycle | `IFR-06` |
| 9 | Pass: seven-row unidentified-Pot Action plus See/Info entry and return | `IFR-07`, `IFR-08`, `IFR-09` |

## Remaining Item/Floor work discovered by the visual pass

These are implementation work, not accepted exceptions. The existing staged fixtures
already reproduce them without Lua, so the next pass must first turn each observation
into an exact button-driven trace and regression before changing shared admission logic.

| ID | Type | Exact observed route | Current symptom | Required acceptance |
|---|---|---|---|---|
| `IFR-01` | whole-LCD blank | Case 3 or 6: Items -> the reported sealed equipment -> Info; advance through the final Info/seal page so it returns automatically | LCD blanks on final-page return to Items; the existing B-return test does not cover this final-A history, while case 7's prescribed shield route passed | Final-A and B returns must be independently traced; both return chrome-first to the exact Items page with zero LCD-off frames |
| `IFR-02` | whole-LCD blank | Case 3: place either reported sealed item on the floor, then Floor -> Info and complete every page | LCD blanks on the automatic return to Floor | Preserve the correct direct Floor parent, page count, Action state, and sealed item while returning LCD-live and box-first |
| `IFR-03` | regional ordering defect | Case 4: open Info first, return to Items, then open Name and either cancel or confirm a name | LCD stays on, but keyboard/status fragments and the Name box survive while Items rows appear; the supplied `test 4 transition 1/2` captures show the mixed epochs | Both End and B histories must retire the entire outgoing keyboard/name map before complete Items chrome and rows are revealed; immediate input remains required |
| `IFR-04` | whole-LCD blank | Case 5: place items inside a Pot, open the contained item's Action menu, then choose Info; repeat from carried-Pot, direct Floor, and Items-appended Floor parents | LCD blanks before contained-item Info | Trace each parent stack separately and publish complete Info chrome/text without borrowing another Pot viewer's ownership |
| `IFR-05` | whole-LCD blank | Return from the contained-item Info page in each `IFR-04` context | LCD blanks again before restoring Pot contents | Restore the exact Pot title, contents, cursor, Action state, and parent context regionally; no stale rows or delayed input |
| `IFR-06` | steady-state rendering defect | Case 8: enter Items and page to the appended shop Floor page before opening Info | The Gitan value at the right of the selected row is absent; after Action -> Info -> Floor it appears as `10000` | Initial Items -> Floor and Info -> Floor must produce the same complete price/Gitan row, including the right-aligned value, without requiring a child-screen round trip |
| `IFR-07` | whole-LCD blank | Case 9: direct unidentified-Pot Floor seven-row Action -> Name | LCD blanks entering the Name keyboard | Add an exact seven-row Pot parent admission; complete keyboard/name chrome must appear with the HUD and LCD live |
| `IFR-08` | whole-LCD plus ordering defect | Case 9: End or B from that direct unidentified-Pot Name screen | LCD blanks returning, and outgoing Name text is not retired regionally before the Floor/Action reconstruction | Both return histories must be independent, LCD-live, and ordered keyboard retirement -> complete Floor/Action chrome -> completed text/cursor |
| `IFR-09` | history-dependent whole-LCD blank | Case 9: use Name from the Items-appended Floor parent, return to its still-open Action menu, then press B to dismiss Action | Name itself returns, but the subsequent Action dismissal blanks only after this history | Preserve and then consume the post-Name Floor/Action ownership state so Action B restores its exact parent without LCD-off or input delay |

Suggested implementation order is `IFR-01/02` (sealed final-page return family),
`IFR-04/05` (nested Pot Info matrix), `IFR-07/08/09` plus `IFR-03` (Name ownership and
retirement histories), then `IFR-06` (shop price-row parity). Each group must use the
sibling `../mgbdis` checkout plus runtime traces; a shared screen number alone is not
authorization to reuse another regional owner.

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

Expected: keyboard entry and both returns are chrome-first, LCD-live, and immediately
responsive. This is the carried `0,1,2,9` family, independent of the two Floor families
in case 3.

## 5. Storage Pot Put selector and post-action replay

```sh
run_item_floor_case 05_pot_put
```

Load Adventure Log 2. Press B, choose `Floor`, and choose the default `Take` on the
Storage Pot. Dismiss the pickup/description messages until the dungeon field is live.
Open B -> `Items`, move to the fourth row Storage Pot, open Action, move Down once to
`Put`, and press A. The Put selector begins on Big Onigiri; press A to commit it. After
Items returns, press B once, test Up/Down, then press B again to reach Status.

Expected: Action -> Put selector is regional and box-first. Confirming Big Onigiri is an
intentional exception: the menu blanks to a visible dungeon action, and the completed
action blanks into a newly built Items screen. Those are two genuine new-screen
boundaries found in the base engine, not a same-menu flash. The first B replay and final
Items -> Status transition must not add another whole-screen blank. Status -> field may
use the intentional native teardown.

## 6. Real fused equipment row

```sh
run_item_floor_case 06_equipment
```

Load Adventure Log 2 and open B -> `Items`. Inspect the equipped/fused Nagamaki and its
zero-seal marker, then move the cursor and leave to Status.

Expected: Status -> Items remains LCD-live, the full proportional name and native
equipment/fusion markers coexist, and no row or marker appears late. The automated
companion test additionally covers the hostile plated/cursed/fused three-row mix that a
natural compact SRAM cannot conveniently stage.

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

Expected: Status -> Floor -> Action -> Info -> Floor has no whole-screen blank. `Price`,
`G`, both values, Action labels, borders, and cursor stay complete. The earlier grouped
audit hits at native `2:$463C`/`4:$4154` were isolated to boot/field loading, not this
shop menu cycle.

## 9. Seven-row unidentified Pot Floor Action

```sh
run_item_floor_case 09_unidentified_pot
```

Load Adventure Log 3. Press B -> `Floor`; the unidentified Pot produces the unique
seven-row Action list. Exercise `See` and `Info` separately, returning to Floor after
each, and move through all seven Action rows.

Expected: every row is proportional; Action, See/Info entry, and both returns keep the
LCD/HUD live; the restored top-left title, seven-row border, cursor, page number, and
parent text are complete and correctly ordered.

## Optional automated confirmation

The grouped visual pass is backed by these focused commands:

```sh
python3 tools/itempagespill.py build/shiren_en.gb
python3 tools/floorpagespill.py build/shiren_en.gb --rapid --settle-frames 1
python3 tools/flooractionspill.py build/shiren_en.gb
python3 tools/unidentifiednamespill.py build/shiren_en.gb
python3 tools/potputspill.py build/shiren_en.gb
python3 tools/equipmentmarkerspill.py build/shiren_en.gb
python3 tools/iteminfospill.py build/shiren_en.gb
python3 tools/shopspill.py build/shiren_en.gb
python3 tools/unidentifiedpotspill.py build/shiren_en.gb
```
