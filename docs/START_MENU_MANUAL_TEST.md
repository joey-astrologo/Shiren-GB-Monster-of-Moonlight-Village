# Start-menu regional blanking manual test

This is the visual acceptance procedure for Start checkpoint S2. Checkpoint S1 was
visually accepted on 2026-08-31 for the screen-23 saved-log summaries shared by
Adventure, Copy, Erase, Rename, and Replay. The three S2 incoming transitions were
visually accepted on 2026-08-31; the final check below covers the cursor regression
found while returning from those accepted children.

S2 changes exactly three incoming screens:

- screen 22: New Log's log selector;
- screen 26: Copy Log's destination selector; and
- screen 24: Erase Log's No/Yes confirmation.

Difficulty, personal-name keyboards, Rank/Pass, and gameplay/replay handoffs retain
their separately catalogued behavior and are not scored in S2. Whole-LCD policy for B
returns to the Start root also remains separate, but the returned root must have exactly
one cursor at the option the player backed out from.

## Build and stage an isolated save

Run from the repository root:

```sh
./build.sh
python3 tools/startpathspill.py build/shiren_en.gb
python3 tools/preparestarttests.py build/shiren_en.gb
START_ROOT="$PWD/build/manual-tests/start-$(shasum -a 256 build/shiren_en.gb | cut -c1-12)"
MESEN_SAVES="$HOME/Library/Application Support/MesenCE/Saves"
mkdir -p "$MESEN_SAVES"
```

The post-acceptance cursor candidate is SHA-256
`12fe799ad06b505c6bcfa0b8f2c8b858e430202b415b77b9bfb70f27114e538c`.
`startpathspill.py` must report nine routes and zero problems. In particular, its New,
Copy, and Erase lines must report `regional=22,22`, `regional=23,26`, and
`regional=23,24`, respectively, with no Start LCD-off hit for screens 22, 26, or 24.

Define this helper once in the same terminal session:

```sh
run_start_s2() {
  test_base="shiren_start_s2"
  cp -f "$START_ROOT/$test_base.srm" \
    "$MESEN_SAVES/$test_base.srm"
  open -na "/Applications/Mesen.app" --args \
    "$START_ROOT/$test_base.gb"
}
```

Close Mesen before invoking `run_start_s2`. Invoke it again before every numbered test.
This resets only the uniquely named `shiren_start_s2.srm`; it cannot overwrite the
normal `shiren_en.srm` or another personal save. The tracked SRAM is hash-verified and no
Lua mutation is used.

## S2 visual contract

On each tested incoming transition:

- the LCD must never blank the whole screen;
- title/root or summary content outside the incoming child's rectangles must remain
  stable;
- only the incoming child rectangles may clear while they redraw;
- each complete border/chrome must precede its text and cursor; and
- no stale text, partial border, missing cursor, or delayed input may remain once
  settled.

The exact `mgbdis`-derived rectangles, including borders, are:

| Screen | Native owner | Visible BG rectangle(s) |
|---|---|---|
| 22 New Log selector | handler `4:$4C61`, box 25 | x=5..15, y=9..15 |
| 26 Copy destination | handler `4:$4CCA`, calls screen-22 builder/box 25 | x=5..15, y=9..15 |
| 24 Erase confirmation | handler `4:$4C94`, boxes 27 then 28 | x=3..19, y=7..11 and x=11..16, y=2..6 |

A regional clear lasting through the child's redraw is acceptable. A full-screen white
frame is not.

## Three accepted incoming checks

### 1. New Log selector

```sh
run_start_s2
```

At the Start root, move down once to `New Log` and press A. Inspect the log selector
before selecting a slot.

Expected: the root remains visible outside box 25; only x=5..15/y=9..15 may clear; the
selector border appears before its text and cursor; there is no whole-screen blank.

Selecting a slot proceeds to screen 25's difficulty/explanation composite, which is S3
and may still blank.

### 2. Copy destination selector

```sh
run_start_s2
```

Select `Copy Log`. Wait for the source summary to settle, then press A once to open the
destination selector.

Expected: the already accepted screen-23 summary remains visible outside box 25; only
x=5..15/y=9..15 may clear; the destination border appears before text/cursor; there is
no whole-screen blank. Do not complete the copy.

### 3. Erase No/Yes confirmation

```sh
run_start_s2
```

Select `Erase Log`. Wait for the summary to settle, then press A once to open the
confirmation. Do not choose Yes.

Expected: the summary remains stable outside the two child rectangles. The prompt box
and higher-z No/Yes box may clear regionally, but both borders must precede their text
and cursor. There is no whole-screen blank.

## Cursor-return regression check

```sh
run_start_s2
```

At the Start root, select `New Log`, then press B to return without choosing a slot.
Repeat from `Copy Log` and `Erase Log`, backing out from each first child screen.

Expected after every return: exactly one cursor is visible, and it is beside the option
just entered. There must not also be a cursor beside `Adventure`. Move Up/Down once after
each return and confirm that only the single active cursor moves.

The automated fixture checks this invariant for every root return in all nine traced
Start routes, in both the shadow map and the published BG map. Joey visually accepted
the transient cursor-return correction on 2026-08-31.

## Later checkpoints

- S2R: B returns from Adventure/New/Copy/Erase/Rename/Replay selectors or summaries to
  the Start root. Cursor ownership is accepted; their whole-LCD policy remains work.
- S3: New Log difficulty/explanation entry, difficulty redraws, and B returns.
- S3N: New Log/Rename name-entry directions, pending final visual-policy review.
- S4: Rank/Pass choice, category, and Pass log-selector layers only. The final Rankings
  and Pass displays are user-approved independent screens; whole-LCD blanking is allowed
  entering and leaving them, and between Rankings pages.
- Replay saved-log selection remains LCD-live; its gameplay handoff may blank.
- Start <-> Fay's Puzzle and Fay -> gameplay may blank. Fay's two puzzle pages must
  continue paging LCD-live and need a second-50-puzzles save-backed regression fixture.
