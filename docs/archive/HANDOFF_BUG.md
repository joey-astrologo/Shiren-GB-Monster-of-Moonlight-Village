# BUG — dungeon messages expire too fast to read — **FIXED 2026-07-30**

> **Archived:** fixed historical defect. See the repository [README](../../README.md) and
> [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

**Cause: one byte, `0:$227D`.** The inserter rewrote a phantom pointer reference that sat
inside a live instruction, turning `0:$227B ld [$CF01],a` into `ld [$CE01],a` and
destroying the variable that holds a dungeon message on screen.

**It was not DTE, not the hooks, and not the compressed content.** Three sessions of
reasoning pointed at all three. Read "How the diagnosis went wrong" below before trusting
a similar chain of inference.

---

## The fix

`extract.py` matched `ld bc/de/hl,$XXXX` by byte pattern. `0:$227B` is `ea 01 cf` —
`ld [$CF01],a` — and starting one byte later, `01 cf 7e` reads as `ld bc,$7ECF`, which is
the address of a real string: bank 30's item verb at `30:$7ECF`. So a reference was
recorded pointing into the middle of another instruction, and `build.py` rewrites every
reference it is given.

With `--no-dte` that verb does not move, so the phantom rewrite wrote back the bytes that
were already there and the ROM was correct **by accident**. With DTE on, compression moved
the verb one byte to `$7ECE`, and the rewrite put `$CE` where `$CF` belonged.

`$CF01` is part of the composer's message-state block; `0:$2274` unpacks the message
timing nibbles from the table at `0:$22AC` into `$CF01` and `$CF03`. `$CF03` is the hold
counter — with the write redirected, it decays from its stale value and the box closes
after ~16 frames instead of ~180.

Three changes, all in the build pipeline:

| file | change |
|---|---|
| `tools/dis.py` | `boundary_votes()` / `is_instruction_start()`: decode linearly from each of the preceding 64 bytes and count sweeps that land ON the candidate against sweeps that step OVER it. LR35902 code self-synchronises, so this converges. |
| `tools/extract.py` | `immediate_refs()` keeps a match only if it is a real instruction start, and PRINTS every phantom it drops. |
| `tools/build.py` | re-checks every `imm` reference against the untouched ROM before writing through it, and fails the build naming the site — a stale `script.json` cannot reintroduce this. |

Three phantoms exist in this ROM and all three are now dropped. The one real contested
site, `0:$2D18 ld bc,$4F96`, survives (63 sweeps to 1). Nothing else about extraction
changed: same 1264 strings, same 28,819 bytes, same `loc`s, round-trip all OK, and only
those three refs differ from the previous `script.json`.

## Verified

```
sh build.sh                  # 1442 checks ALL OK, no problems, no bank reverted
python3 tools/dte_rom.py     # 5278 segments / 0 mismatches; verify_box 0 failures
python3 tools/msgdur.py build/shiren_en.gb build/shiren_nodte.gb build/shiren_nohook.gb
```

`msgdur` reports **10 message boxes with identical start frames and identical durations in
all three builds** — the full DTE build now behaves exactly like both controls, frame for
frame. Before the fix it showed 14 boxes, median 64 frames against 193.

`gbrun.py --compare` against the pre-fix build is IDENTICAL on the file menu and the
dungeon status screen, and bank 0 now differs from `base.gb` only in the expander
(`$0062-$00FF`), the header (`$0147-$0148`, `$014D-$014F`) and `dte_box` (`$3FEC-$3FFC`).
The one stray byte is gone.

**Joey should still play a dungeon.** The measurement is strong — a deterministic seeded
walk, three builds, frame-identical — but it is one input script.

## The thing this bug was really about: measuring a duration

The project's whole verification culture is "screenshot before believing", and it caught
none of this, because **a screenshot cannot see a duration**. It can now:

**The dungeon message box is the WINDOW layer, and its height is WY (`$FF4A`).** Parked at
136 it shows one row, the status bar. A message slides it to 99, holds, and slides back.
So a message's lifetime is the number of frames WY stays above the parked value —
`tools/msgdur.py`.

Two things had to be true to get there, and both were previously recorded as dead ends:

* **Counting non-blank tiles cannot see it** — correct, and irrelevant. The box is not in
  `tilemap_background` at all.
* **"A scripted walk never triggers a dungeon message"** — FALSE, and it cost the most.
  Two separate causes, both in the harness rather than the game:
  * `gbrun.py --press` used pyboy's default one-frame press, which this ROM does not
    reliably sample, so `--trace` reported "no copy site fired" on runs that were driving
    nothing. It now holds each press for `PRESS_FRAMES` = 5, and the same recipes report
    hits.
  * `emitlog.py` does hold its presses, but its sequence includes `start` and `select`
    every 8 frames: the run walks the corridor (HP and belly change) and never fights.
    Zero composer calls in 2000 frames — measured, and it is the schedule, not the game.

  A seeded walk of movement and `a` only, pressed 5 frames every 12, fires the composer
  186 times and produces real combat messages (`<var>から <cE4>ポイントのダメージをうけた`,
  `<var>をやっつけた`, `<cE5>のけいけんちをえた`). That is `msgdur.py`'s `SEQ`.

`tools/msglog.py` is how the walk was confirmed to reach real messages: it hooks both
composer loops and decodes what each one read, so a run reads as a transcript. It is also
the start of the "dialogue equivalent of `boxpreview.py`" the handoff asks for before bulk
translation.

## How the diagnosis went wrong — three times

**Attempt 1: "DTE expands untranslated Japanese, which changes cell counts."** Plausible,
supported by a real measured side effect (the status bar's second row under `a:120`), and
wrong. Fix committed as `1d0b9e0`, narrowing the code space from 124 codes to 46 and
costing 12 points of compression yield. Joey retested: still broken.

**Attempt 2: "the bytes come from the composer's runtime buffer at `$CF8F`, which no static
check can see."** This followed from a correct three-way bisect (`nohook` clean, `nodte`
clean, `en` buggy) plus a correct observation (banks 13 and 14 are byte-identical between
the builds). The inference was that the only remaining lever was the DTE table. It was
not: **bank 0 also differed, and the session dismissed bank 0 as "the checksum at `$014E`"
without diffing it.** A one-byte difference hid behind a plausible explanation for the
whole bank.

Measured afterwards: the expander expands **zero** bytes in 20,000 frames of dungeon play.
The runtime-buffer theory had no runtime evidence for it.

**Attempt 3 (the brief this file used to contain): "remove the two composer hooks, they buy
nothing."** Would have appeared to work only if it also happened to change bank 30's
packing — it does not. The hooks are now positively exonerated by measurement:
`shiren_nodte.gb` and `shiren_nohook.gb` produce **identical message durations at identical
frames**, so the hooked composer is behaviourally indistinguishable from the untouched one.
**Keep the composer hooks.** They cost nothing and dialogue compression will need them.

The general lesson, and it is the expensive one: **a bisect tells you WHICH artefact
differs, never WHY.** Three builds correctly implicated the DTE build; every hypothesis
about the mechanism was then argued from what DTE plausibly does, and none of them was
tested against the actual bytes. `cmp` on the two ROMs, bank by bank, would have found it
on day one.

## What stays, and one thing worth revisiting

**Keep the narrowed code space** (`$92-$99 $B8-$C1 $C4-$DF`, 46 codes) for now. It is a
real invariant — the composer has no gate — and `build.py` enforces it. But its
justification was this bug, and this bug had another cause, so **the 12 points of yield may
be recoverable**. `tools/msgdur.py` is now the instrument to decide it: widen
`dte_rom.DTE_RANGES` (the build check will have to be relaxed with it, since untranslated
Japanese will then collide again), rebuild, and compare durations against
`build/shiren_nohook.gb`. Do it as its own measured change.

`build/prefix_bug.gb` is the pre-fix ROM, reconstructed and confirmed by checksum
(`$4A85`, the build Joey tested). Keep it as the regression baseline: `msgdur` on it must
show the fast-expiry signature.

## Files

| path | what |
|---|---|
| `tools/msgdur.py` | **the duration check** — message lifetimes from WY, seeded walk, comparable across builds |
| `tools/msglog.py` | what the composer actually drew, decoded, frame by frame |
| `build/shiren_en.gb` | full build — **fixed** |
| `build/prefix_bug.gb` | the bug, preserved (checksum `$4A85`) |
| `build/shiren_nodte.gb`, `build/shiren_nohook.gb` | the bisect controls, both clean |
| `tools/emitlog.py` | logs what the expander expands, ROM vs WRAM source. **Its built-in walk never reaches the composer** — swap in `msgdur.py`'s `SEQ` and 12-frame spacing before believing a zero from it. |

All ROMs need their `.ram` beside them — a build without its save boots to a different
title menu and every screen after it differs.
