# Rankings VWF ownership repair — completed handoff

> **Archived:** completed implementation record. See the repository
> [README](../../README.md) and [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

**Current 2026-08-12 status: COMPLETE.** The implementation, automated acceptance matrix
and final manual Mesen route all pass. Rankings remains proportional VWF; no fixed-width
fallback was introduced. Joey repeated the Kuyo/Adventure cycle, inspected Village Exit
and reported the repaired build works.

The final normal RC build is `build/shiren_en_rankvwf_rc.gb` (identical to the current
normal `build/shiren_en.gb`), SHA-256
`b5b45c3c95a3ff1305d36c0fbf1b538097f5fae7f3a5cf01146ac67ddb3a260f`.
The matching shuffled and redirect-all matrix ROMs are SHA-256
`c9842fec9c9ff02e2a9eb24eab5ecf64f5c2dda7cfc55c3776a93de48c628be1` and
`7b8153b7d19a7e578f77fd872cbd7dd2039708599c79b9d592fb2b9ffa80591f`.
The frozen pre-repair ROM is `build/shiren_en_rankvwf_known_bad.gb`, SHA-256
`b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`.
The replacement regression fails that frozen ROM on the real badge, category-selector
and native-graphic assertions; it passes the RC.

## Implemented screen-scoped ownership

This non-CGB/SGB ROM still has exactly one usable VRAM bank. The repair treats the title
Rankings flow as one allocation and restoration lifetime:

- The settled Rankings board owns `$80-$A6`: five tiles for `Rankings`, three each for
  `Easy`, `Norm.` and `Hard`, and five tiles for each of the five proportional names.
  Static strings are deduplicated, so the complete board needs 39 tiles rather than five
  unconditional eight-tile name slices. Live native board graphics remain disjoint.
- The Kuyo/Village category selectors temporarily use `$C0-$CB` (`$C0-$C3` for Kuyo and
  `$C4-$CB` for Village Exit). Before a Rankings board, title screen or Adventure Log map
  can reveal those native IDs, the proven bank-13 menu-font loader restores `$00-$D2`.
  No CGB bank-1 design and no permanent relocation of another pool is used.
- LCD-on title Rankings retains the native VBlank queue. Each five-tile name is delivered
  through overlapping 4+4+1 destination windows and published only with the complete
  `$9800` board behind the blank `$9C00` map. LCD-off rescued-child results retain the
  synchronous direct-copy path and do not wait for VBlank while the display is disabled.
- A full title rebuild begins a new screen allocation, reloads the native planes while
  hidden, rebuilds the destination map, and only then publishes it. This restores the
  actual Orochi planes `$CB/$CD/$CC/$CE` before the Adventure Log summary is exposed.

`tools/orochisymbolspill.py` is now a native-control lifetime regression. It checks the
real badge cells and planes, every complete Kuyo/Village Rankings region, proportional
headers/difficulties/names, native status graphics, visible OAM and exact repeated Log
restoration. `tools/rankspill.py` additionally proves the 25 name planes, exact queue
payload/destination windows, then compares legacy page 0 and nonzero page 1 completely
against a `--dot-font --no-menuvwf` native control. Both pages take the native writer 5/5;
the second proves prevalidation begins at `C6AC * 12` and catches the unsupported code in
the fifth selected row. Shadow and BG maps, resolved planes, framebuffer, display state
and visible OAM semantics must all match that native control.

## Automated evidence

- The replacement Orochi regression fails the frozen known-bad hash above: all three
  returned Log summaries lose `$CB/$CD/$CC/$CE`, and the Kuyo native/selector assertions
  also fail.
- The RC completes Kuyo, Village Exit and repeated Kuyo cycles with three complete
  proportional boards, four badge reveals, exact repeated restoration, zero native-cell
  or native-pixel mismatches, and zero visible unexpected OAM.
- Normal, `--shuffle` and `--redirect-all` builds all pass `orochisymbolspill.py`,
  `rankspill.py`, `mainmenuspill.py`, `rescueexitspill.py`, `startspill.py`,
  `structspill.py`, `savesummaryspill.py`, the ordinary/long/save/help-seals menu tests
  and `menuromspill.py`. The full normal `sh build.sh` battery is green and now builds both
  Rankings controls and runs `rankspill.py` whenever its supplied SRAM is present.
- Both execution modes are covered: five queued VBlank name transfers on the ordinary
  title route and five synchronous direct rows with zero queue arms on the rescued-child
  LCD-off route.

## Manual Mesen gate — PASSED 2026-08-12

Use `saves/shiren_en_log_1_orochi_symbol.srm` with the final RC and hand-drive exactly:

1. `Adventure -> Log 1` and inspect the coloured cleared-Orochi badge.
2. `Rank/Pass -> Rank -> Kuyo`; inspect VWF and every native clear/status graphic.
3. `Adventure -> Log 1`; confirm the badge is exact.
4. Repeat the complete Kuyo/Adventure cycle and confirm exact restoration again.
5. Open `Rank/Pass -> Rank -> Village Exit`; inspect VWF and native graphics, then return
   to `Adventure -> Log 1` and confirm the summary once more.

Joey completed this route in Mesen with the authoritative SRAM and approved the result.
The proportional board, native clear/status graphics and cleared-Orochi badge remained
correct across the repeated returns and the Village Exit board.

## Historical pre-repair record (2026-08-11)

The remainder of this file preserves the diagnosis and repair brief that produced the
implementation above. References to an “open blocker”, the “current diagnostic ROM” or
the old regression describe the frozen pre-repair state, not the 2026-08-12 RC.

### Reproduction

Authoritative SRAM:

```text
saves/shiren_en_log_1_orochi_symbol.srm
SHA-256 ea41082a249c5d42f3f82b6e049ebe6f09c39696fa767f1282f6727b3640f1b3
```

Use Log 1 and reproduce this complete route:

1. `Adventure -> Log 1`: record the coloured cleared-Orochi badge.
2. Return, then open `Rank/Pass -> Rank -> Kuyo`.
3. Inspect every ranking row and its native clear/status graphics.
4. Return to `Adventure -> Log 1` and inspect the badge again.
5. Repeat the Rankings/Adventure cycle. Also exercise the `Village Exit` board.

The frozen diagnostic ROM has SHA-256
`b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`.
It passes `sh build.sh` but is **known bad** on this route and is not a release candidate.

### Confirmed diagnosis

This is a VRAM ownership/lifetime defect, not bad SRAM and not a translation string.

The visible Log-summary Orochi badge is actually:

| Component | Actual value |
|---|---|
| tile IDs | `$CB/$CD` on top, `$CC/$CE` on bottom |
| BG cells | row 9 columns 5-6; row 10 columns 5-6 in `$9800` |
| visible crop | `(40,72)-(56,88)` in the 160x144 framebuffer |

Selecting Kuyo changes those four tile planes. Returning to Adventure restores their
tilemap IDs but not their original pixels, so VWF fragments appear where the badge was.
Clearing a tilemap cannot repair this: it removes references but does not recreate the
overwritten tile planes.

The old `tools/orochisymbolspill.py` was a false-positive regression. It watched:

- tiles `$5B/$5C/$63/$64`;
- BG cells `(8,2)/(8,3)/(10,2)/(10,3)`; and
- crop `(16,64)-(32,80)`.

Those coordinates are an unrelated unaffected region. Consequently its own
`build/orochisymbolspill/returned_log.png` visibly shows a missing badge while the test
reports zero problems. Do not use its current pass result as evidence.

The earlier Rankings-name pool `$43-$6A` was moved to `$80-$A7` based on that incorrect
observation. `$80-$A7` has only been shown not to collide with the sampled fixed Rankings
BG cells; it has not been proven private across every native graphic, window/BG use, OAM
use, or adjacent-screen lifetime. Do not relocate the pool again without a complete live
ownership audit.

There is only one usable VRAM tile bank. This ROM is a non-CGB Game Boy/SGB cartridge:
header byte `$0143` is `$42` rather than `$80/$C0`, and VBK reads as unavailable. A CGB
bank-1/attribute-map design is therefore **not** a solution for this game.

Two separate properties must be preserved:

1. **Atomic presentation:** Rankings is built behind the blank `$9C00` map and published
   only when complete. This already prevents half-drawn transitions.
2. **Plane ownership:** VWF and native symbols must not occupy the same physical tile
   storage while simultaneously visible, and borrowed adjacent-screen planes must be
   restored before their tilemap is shown again. This was the open defect.

### Relevant pre-repair implementation

- `tools/rankvwf.py`: five ranking-name rows; LCD-on queued upload and LCD-off direct
  rescue-result upload. The pre-repair name pool was `$80-$A7`.
- `tools/menuvwf.py`: generic proportional menu/static-row allocator. Its ROM-row pools
  include `$CB-$DD`, the range implicated by the real badge collision.
- `tools/rankspill.py`: useful name-composition/queue test, but its control retains the
  generic menu VWF and therefore cannot prove native-symbol preservation.
- `tools/orochisymbolspill.py`: was invalid until rewritten around the actual badge and full
  route.
- `tools/mainmenuspill.py`: transition/publish coverage.
- `tools/rescueexitspill.py`: mandatory LCD-off rescued-child result coverage.
- `tools/startspill.py`, `tools/structspill.py`: adjacent title/save/Fay ownership tests.

Useful generated screenshots:

```text
build/orochisymbolspill/initial_log.png
build/orochisymbolspill/kuyo_rankings.png
build/orochisymbolspill/returned_log.png     # visibly corrupt despite a passing test
build/orochi_diagnosis/
build/rankvwf_stress.png
```

Original Mesen captures, if still present on Joey's machine:

```text
/Users/joey/Desktop/orochi symbol present.png
/Users/joey/Desktop/orochi symbol missing for entry 1.png
/Users/joey/Desktop/orochi symbol log missing.png
/Users/joey/Desktop/choose kuyou.png
```

### Required repair approach (completed)

Treat Rankings as one screen-scoped renderer rather than several independent claims on
apparently free tile IDs.

1. **Repair the regression first.** It must fail on the current known-bad ROM. Capture the
   actual badge cells/planes/crop, the complete visible Rankings area, native ranking
   status graphics, and the returned Log summary. A screenshot generated by the test may
   not disagree with its assertions.
2. **Census the complete live page.** Audit BG/window tilemaps, all OAM entries and the
   single VRAM bank for both Kuyo and Village Exit, with every clear/status variant that
   can coexist. Include entry, settled display, exit and repeated cycles.
3. **Use a unified Rankings allocation.** Allocate/deduplicate the header, category and
   difficulty labels plus all five VWF names together. Exact physical tile demand matters;
   five unconditional eight-tile reservations are not automatically required.
4. **Keep live native assets disjoint.** Any native icon or fixed graphic visible on the
   board must retain separate physical tiles. If no sufficiently large disjoint run exists,
   explicitly relocate the native ranking graphics and rewrite their live tilemap cells.
5. **Restore adjacent-screen planes.** For tiles safely borrowed only because their native
   users are offscreen, snapshot/restore their exact planes or call a proven native reload
   before returning to Adventure. Do this while the alternate map/LCD hides the operation.
6. **Publish atomically.** Keep the existing blank-map transaction or replace it with an
   equally strict full-page publish. Aggressive clearing is useful for references, but it
   is not a substitute for plane restoration.
7. **Preserve both execution modes.** Ordinary title Rankings runs with LCD on and queued
   uploads. Rescued-child results enter with LCD off and require synchronous uploads.

### Acceptance criteria

- VWF remains active for Rankings names and proportional Rankings labels.
- Both Kuyo and Village Exit boards show correct native clear/status graphics.
- Adventure Log 1 shows the exact original coloured Orochi badge before and after each
  Rankings visit.
- Multiple Rankings/Adventure cycles remain exact.
- The replacement regression demonstrably fails on the current known-bad ROM and passes
  only after the repair.
- `rankspill.py`, `mainmenuspill.py`, `rescueexitspill.py`, `startspill.py` and related
  save-summary/Fay tests remain green.
- Normal, shuffled and redirect-all layouts pass.
- The final built ROM is manually confirmed in Mesen. PyBoy alone is insufficient for
  closing this release blocker.

### Archived copy-ready repair prompt

> Work only on the final release-candidate blocker documented in
> `HANDOFF_RANKVWF.md`: rebuild the title-menu Rankings renderer so it retains
> proportional VWF without corrupting native ranking/status graphics or Adventure Log
> summaries. Fixed-width fallback is not acceptable.
>
> Start from the current dirty `main` worktree and preserve every existing change; do not
> reset, restore, or check out files. Reproduce with
> `saves/shiren_en_log_1_orochi_symbol.srm`: Adventure -> Log 1, inspect the cleared-Orochi
> badge, return, Rank/Pass -> Rank -> Kuyo, inspect all ranking symbols, then return to
> Adventure -> Log 1. Repeat the cycle and cover Village Exit too.
>
> Do not trust the current passing `tools/orochisymbolspill.py`. It watches the wrong
> tile IDs, cells and crop; `build/orochisymbolspill/returned_log.png` is visibly corrupt
> while the test passes. First replace it with a regression that fails on the current ROM
> and checks the actual visible badge (`$CB/$CD/$CC/$CE`, rows 9-10 columns 5-6, crop
> `(40,72)-(56,88)`), the complete Rankings regions and native status graphics.
>
> Audit `tools/rankvwf.py` and `tools/menuvwf.py` as one screen-scoped allocation. This is
> a non-CGB/SGB ROM with one usable VRAM bank, so do not plan on CGB bank-1 attributes and
> do not merely relocate another pool. Census BG/window, OAM and all tile planes over
> entry, settled display, exit and repeated lifetimes. Deduplicate VWF tiles where useful;
> keep simultaneously visible native assets disjoint, explicitly relocate them if needed,
> and restore any offscreen planes borrowed across screens before their map is revealed.
> Keep atomic blank-map publication.
>
> Preserve both execution modes: ordinary title Rankings uses LCD-on/VBlank uploads;
> rescued-child results enter LCD-off and use synchronous uploads. Acceptance requires
> VWF on both boards, correct native symbols, exact Orochi restoration over repeated
> cycles, `rankspill.py`/`mainmenuspill.py`/`rescueexitspill.py` and adjacent tests green,
> normal/shuffled/redirect-all coverage, and final manual Mesen confirmation.
