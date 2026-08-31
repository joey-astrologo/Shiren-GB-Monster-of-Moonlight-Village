# Start-menu regional blanking manual test

This is the accepted visual procedure for Start checkpoint S4. S1 through S3 were
accepted on 2026-08-31 and do not need to be repeated. The focused Erase-No/Orochi
prerequisite also passed on 2026-08-31. S4 itself covers only the retained
Rank/Pass menu layers:

1. screen 30, the Rank/Pass choice;
2. screen 31, the conditional Rank category choice; and
3. screen 32, the Pass log selector.

The final Rankings display (screen 33) and final Pass display (screen 34) are independent
screens. Their entry, exit, and Rankings page changes may blank the LCD. The test below
uses those displays only to verify that their retained blanking does not break the
regional parent on return.

## Build and stage four isolated saves

Close Mesen, then run this from the repository root:

```sh
./build.sh
python3 tools/startpathspill.py build/shiren_en.gb
python3 tools/preparestarttests.py build/shiren_en.gb
START_ROOT="$PWD/build/manual-tests/start-$(shasum -a 256 build/shiren_en.gb | cut -c1-12)"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$MESEN_SAVES"
```

The accepted S4 ROM is SHA-256
`9e3ce9cfe5adb5c76aa4741b07930b533725b4198922485ab0c982fcac9ae8c2`.
`startpathspill.py` must report **23 routes and zero problems**.

Define this helper once in the same terminal session:

```sh
run_start_s4() {
  case "$1" in
    erase_orochi|rank_direct|rank_category|pass_selector) ;;
    *) echo "usage: run_start_s4 erase_orochi|rank_direct|rank_category|pass_selector"; return 2 ;;
  esac
  test_base="shiren_start_s4_$1"
  cp -f "$START_ROOT/$test_base.srm" \
    "$MESEN_SAVES/$test_base.srm"
  open -na "/Applications/Mesen.app" --args \
    "$START_ROOT/$test_base.gb"
}
```

The function lasts only for this terminal session. Close Mesen before each numbered
test, then run the named command. Each command recopies a tracked, hash-verified SRAM
under its own S4 basename. It does not touch `shiren_en.srm`, use Lua, or use a save
state.

For each run, wait for the title screen and press Start before following the steps.

## Accepted prerequisite regression: Erase No preserves Orochi

```sh
run_start_s4 erase_orochi
```

1. Press Start at the title.
2. Move Down once to `Erase Log` and press A.
3. Select the completed Log carrying the Orochi badge and press A.
4. Leave `No` selected and press A.
5. Inspect the returned saved-Log summary for several seconds.

Expected: the return is LCD-live, the summary border and text settle normally, and the
four-tile Orochi badge remains intact. Neither `No` nor any fragment of it may replace
the badge while the summary is visible. This prerequisite was added after the regression
was reported before S4 visual testing; it does not ask you to repeat the already accepted
S1-S3 transition review. Joey visually accepted this exact route on 2026-08-31 against
the accepted hash above; it does not need to be repeated during the three S4 checks.

## Visual contract

On transitions among the Start root and screens 30, 31, and 32:

- the LCD must not become a whole white/blank screen;
- only the outgoing owned rectangle may temporarily clear;
- incoming border/chrome must be complete before its text and cursor appear;
- there must be no stale text, partial border, duplicate/missing cursor, or long input
  delay; and
- once settled, Up/Down/A/B must respond immediately.

A regional clear lasting through a full redraw is expected and is not a defect.

The `mgbdis`- and runtime-proven bordered rectangles are:

| Screen | Layer | Rectangle including border |
|---|---|---|
| 30 | Rank/Pass choice | x=3..10, y=8..11 |
| 31 | Rank category | x=5..16, y=7..10 |
| 32 | Pass log selector | x=5..15, y=9..11 |

## Three accepted S4 checks

### 1. Rank/Pass choice and direct Rankings return

```sh
run_start_s4 rank_direct
```

1. Press Start at the title.
2. Move Down five times to `Rank/Pass` and press A.
3. Inspect the Rank/Pass choice, then press B.
4. Confirm the Start root returns with exactly one cursor on `Rank/Pass`.
5. Press A again, leave `Rank` selected, and press A to enter Rankings.
6. Press B to return from Rankings, then press B from Rank/Pass to the Start root.

Expected: steps 2-4 and the final Rank/Pass-to-root return are LCD-live and follow the
visual contract. Rankings entry and exit may blank because screen 33 is an approved
independent display. After that allowed return, the Rank/Pass box itself must be complete
and responsive before the final B.

### 2. Rank category return

```sh
run_start_s4 rank_category
```

1. Press Start at the title.
2. Move Down three times to `Rank/Pass` and press A.
3. Leave `Rank` selected and press A to open the two-row Rank category box.
4. Press B once to return to Rank/Pass, then B once to return to the Start root.
5. Re-enter Rank/Pass and the Rank category box.
6. Choose either category with A to enter Rankings, then press B to return.
7. Press B from the category box, then B from Rank/Pass.

Expected: root <-> Rank/Pass <-> Rank category is LCD-live in both directions, with
complete borders before text and no duplicate cursor. The screen-33 boundary in step 6
may blank in either direction. Its returned category parent must still settle correctly,
and the two following B returns must remain LCD-live.

### 3. Pass log-selector return

```sh
run_start_s4 pass_selector
```

1. Press Start at the title.
2. Move Down five times to `Rank/Pass` and press A.
3. Move Down once to `Pass` and press A to open the log selector.
4. Press B once to return to Rank/Pass, then B once to return to the Start root.
5. Re-enter Rank/Pass, select `Pass`, and press A again.
6. Select the available log with A to enter the final Pass display, then press B.
7. Press B from the log selector, then B from Rank/Pass.

Expected: root <-> Rank/Pass <-> Pass selector is LCD-live in both directions and follows
the visual contract. The screen-34 boundary in step 6 may blank in either direction.
After that allowed return, the log selector must be complete and responsive, and the two
following B returns must stay LCD-live.

## Automated ownership frozen with S4

The prerequisite has an independent real-input gate. Fresh sibling `../mgbdis` output
confirms the exact screen-24 classifier at `56:$40B0-$40F6` and the private No/Yes queue
destinations `$8A` and `$8E`. `orochipopupspill.py` requires exact screen sequence
`15,23,24,15,23`, six plane-exact No/Yes rows across the three saved Logs, and all four
Orochi tiles to remain plane-exact through 224 returned-summary frames.

Fresh sibling `../mgbdis` output identifies handlers `4:$4D10`, `4:$4D20`, and
`4:$4D2B` for screens 30, 31, and 32. The S4 owner admits only exact Start-root stacks
whose retained parent is screen 30. It clears the exact bordered rectangle during one
complete VBlank with LCDC.7 set. Screens 33 and 34 fail that admission deliberately and
retain their approved full-screen paths.

`startpathspill.py` freezes 23 routes. Its three focused `return-rank-*`/`return-pass-*`
cases never enter screens 33 or 34, require zero LCD-off frames and zero whole-white
frames, compare every returned root raster to its initial reference, verify exact cursor
ownership, and require the expected regional commit sequence. The full `rank-direct`,
`rank-category`, and `pass` routes separately prove that the final-display fallbacks are
retained and their choice-layer parents still recover correctly.

Joey visually accepted all three S4 checks on 2026-08-31 against the hash above. All
catalogued same-menu Start and Item/Floor whole-LCD blanking work is complete. Remaining
whole-LCD sites are approved independent screen/gameplay boundaries or dormant
exact-caller fallbacks.
