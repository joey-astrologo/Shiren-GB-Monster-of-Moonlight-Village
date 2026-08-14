# Handoff — Shiren GB translation

> # ➜ START AT `HANDOFF_NEXT.md`
>
> **It is the entry point for a cold session** (written 2026-08-03): what to read and what
> to skip, the standing verification battery, where the script stands, and the remaining
> work ordered session by session. This file is a **reference to look things up in**, not
> a document to read front to back — `## Tools` and `## TRAPS` are the parts worth knowing.
> The former Rankings release blocker is complete and visually approved. Its detailed
> implementation record is archived at `docs/archive/HANDOFF_RANKVWF.md`.
>
> **Current 2026-08-11:** V4C menu geometry, V4E title/file/Rankings/Fay transitions and
> V4F item/Floor transitions are complete, battery-green and visually approved. V4D is
> also complete: all ten static embedded/unframed candidates are exact-byte classified as
> non-text. The deferred zero-byte name-grid cleanup is complete on normal and shuffled
> layouts, including raw-picker/DTE protection, both aliased page branches, and the
> Copy -> Erase -> New Log native-tile restore. V5A-V5C graphics are complete; V5A now
> reproduces Joey's approved full-screen `Shiren GB` copyright mock-up exactly while
> preserving the native fade, timing and scene-0 transition. V5C now uses Joey's approved
> Poppins Medium arrival-card mock-ups: Moonlight Village and Forest 1 are pixel-exact,
> with all eight labels and floors 1-50 covered by the three-row renderer. Thin Pixel-7
> GB Compact remains the dialogue/menu/cinematic production font. Gitan's Floor/Info dismissal crash is fixed,
> plated/cursed suffixes remain proportional, and the active-dungeon Continue bubble is
> English. Decoy Staff targets now use the live player name without the untranslated
> runtime `にせ` prefix that displayed as `VNShiren`; the exact Log-1 attack is covered by
> `tools/decoynamespill.py`. V5D now translates all 22 native ending-credit cards in the
> approved Poppins style and preserves the final Japanese end mark. The one scheduled
> former V6 blocker—the screen-scoped Rankings VWF ownership rebuild—is complete; its
> record is in `docs/archive/HANDOFF_RANKVWF.md`;
> V4B continues to receive concrete playtest wording/pacing or newly exposed route
> findings, while V4A substitution
> research is optional. Both former rescue blockers are closed: ordinary stairs retain
> their cross-bank choice and the shared rescued-child final exit reaches Rankings, with
> Koppa, Nagi and Fumi save-backed controls. The ROM's `$66` Blank Scroll entry is unused data with no
> reachable Write/scribing screen, so it creates no translation task. The canonical
> evidence and ordered roadmap are at the top of `HANDOFF_NEXT.md`.
>
> ### Two numbers below this line are HISTORY, not rules. Read them as dated.
>
> * **"18 cells a line" was true until 2026-08-03.** `tools/vwf.py` gave the composer a 6px
>   pen, so a line holds **24** characters in the same 18 tiles. Every measurement below
>   that says 18 was correct when it was made and is still correct about the *tiles*; only
>   the character count moved. `--no-vwf` still builds at 18, and the **item description
>   screen** (`13:$7E49`, 122 strings) is a different renderer that is still 18 either way.
> * **"cap names at 7-8 cells" was re-decreed with it**: `NAME_CAP` 14, `ITEM_CAP` 16.
>
> `HANDOFF_NEXT.md` §4 is the live version of both.

**Historical milestone:** the pipeline worked, the ROM was playable, and nothing blocked
translation at this point. DTE ran end to end, the menu box drawer was hooked, the item
category boxes were English on screen, the message-timing bug was fixed, and English
dialogue was on screen. TASK 1, TASK 1b and TASK 2 were done. Read the current block above
and `HANDOFF_NEXT.md` for today's state.

**`TRANSLATING.md` is the rules document** — storage classes, cell budgets and control
tokens; read it before touching `script/en.tsv`. `FINDINGS.md` is how the ROM works.

> ## ✔ JOB 1a IS DONE (2026-07-31) — the dialogue preview and build check exist.
>
> `tools/dialogue_preview.py` draws a translation as the composer will, and `sh build.sh`
> now FAILS on a line over 18 cells (`line_too_long`). It found five over-long lines in the
> shipped innkeeper speech on its first run — each losing one character on the real screen.
> Fixed, photographed, build green. See "TASK 1a" below.
>
> ## ✔ THE SPACE PROBLEM IS CLOSED (2026-08-03) — `docs/archive/HANDOFF_SPACE.md`.
>
> Every arena fits the finished script, at the **ratio-independent floor** as well as at the
> ratio. The last two shortfalls were not space problems: `extract.py` was inventing
> references (`0:$22BD`, `6:$472F`) and `build.py` was rewriting the bytes underneath them.
>
> **Standing rule, decided by Joey 2026-07-31: all space budgeting assumes 2.15x natural
> English WITH DTE (1.60x stored). DTE is assumed ON — there is no "without DTE" case any
> more. Do not re-litigate the ratio.** Being wrong high costs nothing; being wrong low has
> cost this project a session, twice.
>
> **`sh build.sh` now prints an ENDGAME PROJECTION** — what each arena needs when every
> string in it is English, against what it holds. That report is the fix for the cycle:
> today's spare was never headroom, and bank 11 read `+29 spare` while being 1,703 bytes
> short of its finished script. Read it every build.
>
> It currently says the relocatable banks are **5,850 bytes short** (bank 13 worst at
> −3,561) and the redirect pool has 22% margin. **DTE does not fix that** — job 1b improves
> the pool, which is the arena that already fits. What fixes it is removing two ceilings,
> and **31 ROM banks (~500 KiB) are still entirely `$FF` against a ~32 KiB finished script**:
>
> 1. **The pool's 5-byte redirect record** — 2 banks is a record-format limit, not a ROM
>    one, and no eligible string is short enough to be excluded.
>    `docs/archive/HANDOFF_1B.md` §3a.
> 2. **The relocatable redirect** — job 3 below, the same mechanism on five copy loops
>    instead of one gate. This is what clears the 5,850.
>
> Do both and the projection goes green with a margin no measurement error can reopen.
> **Job 1b is then an optimisation, not a blocker**; its brief stays valid for when it comes
> up.
>
> `docs/archive/HANDOFF_SPACE.md` has the research already done: the bank-13 message gate is **`13:$404A`**
> (a single gate with the ROM address in `hl`, the same shape that made `pool.py` cheap), the
> indirection-table design for ceiling B, a suggested order, and the trap below.
>
> **One live bug fell out of that research and is fixed:** `13:$405F` compares against a
> hardcoded string address, split into two immediates so no pointer scan sees it. It named
> the death message, which TASK 2 relocated, so it had been matching the wrong string ever
> since — green on 1498 checks, 12 crash seeds and both pixel comparisons the whole time.
> Third instance of "an address duplicated in arithmetic"; expect more as this job moves
> text.

## TASK 4 — THE SPACE PROBLEM IS SOLVED (2026-07-31). Bulk translation is unblocked.

**In-place dialogue is redirected into free banks.** `tools/pool.py` replaces the single
staging gate at `13:$7589` with a far call to a dispatcher in bank 33; a **4-byte record
`$E9 lo hi $FF`** at a string's original address means "continue from bank/address", and the
text lives in banks 33 and 34. `build.py` does this automatically for any in-place dialogue
string whose English overruns its slot, and `sh build.sh` reports it.

| | |
|---|---|
| in-place dialogue, banks 11+14 | 301 strings, **15,788 bytes** |
| pool available | **32,256 bytes** = 2.05x, before DTE |
| natural English, measured | 1.66x |

The per-string budget is now an aggregate one, which is what killed the 12-of-18 problem.
**Write natural English.** Worked example in `script/en.tsv`: `14:$5047`, the innkeeper's
wake-up speech, is 415 bytes of ordinary prose in a 190-byte slot — the line that had been
cut to telegraphese. `build.py --no-pool` is the bisect control and still reports it
`too_long`.

Three things the old plan called blockers were not real. **Bank 0 is not needed** — the ROM
has its own far call (`rst $10 / db <index>,<bank>`, 3 bytes, restores the caller's bank),
so the new reader lives in the pool bank. **Bank 11 is never touched** — the gate is in bank
13. **The tag bit is structural, not observational** — see FINDINGS.

~~Remaining gate on bulk translation is now the **dialogue preview tool**.~~ **Built
2026-07-31 — see TASK 1a. Bulk translation has no correctness gate left.**

## TASK 1a — the dialogue preview + build check — **DONE 2026-07-31**

`tools/dialogue_preview.py`. `build.py` imports it and adds three problem kinds:
**`line_too_long`**, **`box_too_deep`**, **`buffer_overrun`**. A failing string keeps its
Japanese, the same as `box_too_wide`, so the ROM is still always valid.

**It paid for itself on the first run.** The TASK 4 innkeeper speech — the worked example of
natural English, already photographed and shipped — had **five lines at 19 cells**, each
silently losing its last character (`at last!` drew `at last`, `gives out` drew `gives ou`).
1498 checks, 12 clean crash seeds and two pixel comparisons were all green on it. Reworded
(`woke up at last!`, `strength runs out`), and the fixed box is photographed at
`build/inn_2495.png`.

**The model is read out of the ROM and then validated against the Japanese.** Full derivation
in `FINDINGS.md` → "The composer's layout budget"; the short version is that three
independent mechanisms say 18 (`13:$40D6`, `13:$44F5`, and the 18-tile row stride at
`13:$6B40`), and of 1608 shipped Japanese dialogue lines the longest is exactly 18 with 230
sitting on the boundary. `--selftest` re-runs that. Two Japanese strings come out over and
both are explained rather than excused.

**The one design decision worth not re-litigating: a substitution cannot fail a build.**
Charging `<var>` the 8-cell cap from `TRANSLATING.md` §4 puts **fifteen shipped Japanese
lines** over 18 — `<var>は モンスターにかこまれた！` leaves 4 cells for a monster name. The
original game truncates those too. So the build fails only at the substitution **floor** of
one cell each, which is an overrun no runtime value could rescue, and the caps are reported
as headroom instead (`notes`, and `--selftest` prints the tightest lines in the script).
That is what the name caps should be set from when names get translated.

**Two things fell out of it.** The `$EB` skip-chain question open since 2026-07-26 is
resolved — the composer has **two dispatch tables** and five codes have different arities on
the two paths (`FINDINGS.md`). And `gbrun.py --walk-seed` now works with `--png`/`--compare`,
not just `--dte-scan`, so dialogue screens can be photographed reproducibly and the frame
numbers line up with a `msglog.py` transcript at the same seed. That is how the inn box above
was captured.

TASK 2 is answered and **VWF is cancelled** (TASK 2b). Four findings from it change how
you have to work:

0. **Run `tools/crashscan.py --seeds 12` on every build.** The sample's first version
   crashed the game on every death, and NOTHING else in the pipeline saw it — 1438 checks
   were green, the expander verified, the menus pixel-matched, and `msgdur.py` reported the
   crash as a message that stayed up for 12,034 frames. The cause is in "THE DEATH CRASH"
   below and is fixed; the lesson is that the CPU needs its own health check.

1. **Check the BUDGET before rewording.** In-place village dialogue looked like a hard
   1.0x byte cap and is really ~1.3x, because DTE applies to it and only the observer
   could not see it. The first draft of the sample was hand-abbreviated until Joey could
   not recover the meaning. See "Observing the dialogue stagers". **Bank 11 is still in
   that state — 613 strings — and fixing it is job 1b.**
2. **A line over 18 cells silently LOSES TEXT. Nothing wraps.** Measured on both composer
   paths, not assumed — the previous handoff asserted the opposite. See "Over-long lines
   truncate" below. **Caught by the build since 2026-07-31** — see TASK 1a.
3. **`<var>` substitutions are the real cell budget**, and monster/item names have to be
   capped to fit them. Numbers below.

Confirmed fixed by Joey on a real build: **dungeon message timing.** It was a phantom
pointer reference corrupting one byte of bank 0 — not DTE, not the hooks. Full record in
`docs/archive/HANDOFF_BUG.md`; the durable lesson is in the TRAPS section.

Last updated 2026-07-31 (TASK 2 done: dialogue sample on screen, VWF cancelled, the
bank-0/bank-13 immediate ambiguity fixed).

---

## Current state

**Reverse engineering: complete.** Encoding, control codes and arity, all three string
addressing mechanisms, the mapper question, the status-bar graphics, which renderer draws
which screen, the menu box geometry table, and the selection-cursor table.

**Pipeline: works and self-checks.** `sh build.sh` produces a verified 1 MiB MBC3 ROM.
**1498 checks, all passing, and NO problems** — "every supplied translation fit". Bank 30's
13-byte shortfall is closed; the item verbs are English for the first time. (1498, up from
1438: 240 cross-bank message-queue references were being DISCARDED and are now checked --
see "THE DEATH CRASH" below, which is what they were causing. 1438 rather than the 1442 of
earlier notes because four checks verified a bank-0 immediate claimed by two banks at once;
1442 rather than 1445 because three verified phantom references inside live instructions.)

**DTE: expander built, verified, and reaching the menus.** Resident expander in bank 0,
table in bank 32, **46 pairs, 28.2%** on the SNES English corpus (narrowed from 124/40.2% on
2026-07-30 so the composer cannot expand untranslated Japanese -- that was a fix for the
WRONG cause and the yield may be recoverable, see the fixed bug below). Hooked at `13:$40F1`,
`13:$6893`, `11:$52D5`, `30:$7E8A` and now **`31:$4106`, the menu box row drawer**.
Verified against `dte.py`'s reference decoder by interpreting the real ROM bytes — 5278
segments, 0 mismatches — and the box path additionally by running the REAL drawer at
`31:$40D8` out of `base.gb` under `tools/gbemu.py`, patched and unpatched, and requiring
the two to agree.

Gating compression by BANK was wrong and shipped garbage to the screen. The gate is
`script/dte_ok.tsv`, an allowlist of strings a trace has *observed* an expanding loop read.
Box rows have a **second** gate — see "The box drawer needs a gate" below.

**Proven on screen 2026-07-30.** Build the pre-hook ROM to compare against, then diff
screens. Everything below is IDENTICAL except where noted:

```
git stash && sh build.sh && cp build/shiren_en.gb build/prehook.gb && git stash pop
sh build.sh
python3 tools/gbrun.py build/shiren_en.gb --compare build/prehook.gb --frames 1400 \
        --press start:700,start:760,start:820,start:880,a:940,a:1000     # file menu
python3 tools/gbrun.py build/shiren_en.gb --compare build/prehook.gb \
        --state saves/dungeon.state --frames 800 --press b:120           # status screen
python3 tools/msgdur.py build/shiren_en.gb build/shiren_nohook.gb        # message TIMING
```

**Run those after every render-path change.** The two `--compare` lines are the only check
that catches a missing hook -- and once, the only check that caught THREE separate white
screens that byte verification, the reference decoder and 1451 build checks were all green
on. They are necessary and NOT sufficient: pixel comparison samples one frame, so it cannot
see a duration, which is how the message-timing bug survived every check in the project.
`msgdur.py` is the third line for exactly that reason -- expect the same 10 boxes at the
same frames with the same durations in both builds.

**The table trains on the SNES English corpus**, not on our own text. Yield tracks the
TABLE's corpus, so this gives the measured yield from the first translated line instead of
only once enough English exists for digrams to repeat.

**The code space is MEASURED against the script**, not chosen: it holds only bytes no
untranslated string contains, and `build.py` fails if that drifts. `tools/dte_ranges.py`
recomputes it -- the safe set grows as translation replaces Japanese.

**Emulation is now scripted and headless.** `tools/gbrun.py` (pyboy) boots, drives, screenshots
and hooks. Use it instead of hand-driving Mesen.

**Translated and confirmed on screen:** file menu, difficulty select, place names, status
screen (`Gitan / Floor / Mode`, `Weapon / Shield / Str / Exp`), the in-game menu
(`Item / Floor / Map / Quit`), inventory titles, Close/Exit/Quit, No/Yes,
Continue/New Game, Rankings, `No passwords.`, name-entry labels, and the `FULLNESS` bar art.

Added 2026-07-31 and **photographed on the real screen**: nine combat fragments, four
hunger warnings, and three village dialogue strings including the 190-byte four-box
innkeeper conversation. See TASK 2 below.

**Not translated:** item names, monster names, item descriptions, and all dialogue beyond
the TASK 2 sample. **Names are now the priority**, because every combat line spends most of
its 18 cells on a `<var>` substitution that is still Japanese.

**The player name is 6 characters as of 2026-08-03** (`tools/name6.py`, TASK 3 below), and
the SAVE RECORD grew with it — 79 bytes to 81. A save from an older build still loads but
misreads every field past the name; `build.py --no-name6` is the build that reads it.

**Bank 31 is no longer tight.** Aliasing the name-entry katakana page (box 13) to box 12
returned 116 contiguous bytes; the bank now needs 369 of 534 with **+165 spare**, against
+60 before. That is the headroom for the next box that needs room.

**Script: 1264 strings / 28,819 bytes**, all round-trip verified.

---

# TASK 1 — hook the menu box drawer (`31:$40D8`) — **DONE 2026-07-30**

`31:$4106`'s `call $4124` is now `call dte_box`. Three bytes, exactly in place, and `$4106`
is the ONLY caller of `$4124` in the ROM, so that one patch covers the whole box text path
and nothing else. Boxes 1, 8, 9, 14 and 24 carry compressed rows today; bank 31's need fell
from 492 to 474 bytes.

The previous handoff's plan was right about where to hook and wrong about what it would
cost. What it missed is below, because every item cost a white screen.

## The box drawer needs a GATE, and that is the whole story

The plan assumed the composer's "accepted cost" transfers: expanding a byte that is not
really a DTE code garbles some glyphs, and Japanese renders as garbage anyway. **It does
not transfer.** The composer's floor is one bad line -- its buffer is bounded, its string
ends at an `$FF` the expander refuses, and the next line starts from a fresh pointer.

The drawer has no floor. It draws a FIXED number of cells and then leaves `bc` wherever it
stopped; the next row simply continues from there. So a byte that expands to two cells
where the row budgeted one makes the row run out of cells *before* it reaches its
terminator, and **every following row of that box starts at the wrong byte**.

And the drawer's source is not always ours to vet. The file-select box draws the **player's
saved name out of SRAM** -- katakana codes, squarely inside `$43-$78`. No content test can
ever make that safe.

So expansion is gated on the BOX: **bit 7 of the descriptor's flags byte**, which reaches
the drawer at `$C69E`. Only 2 of its 8 bits are used across all 52 descriptors (`$00`,
`$02`, `$04` are the only values) and only `31:$4043` and `31:$40A1` read it. `build.py`
sets it only for a box whose **every** row is translated English and whose text is not
WRAM-staged -- exactly the condition under which every DTE-range byte in it is one the
compressor put there.

## dte_box, and where it lives

Bank 0 has two holes and the routine uses both. The low half rides with the expander in the
`$0062` padding so it can name `is_dte` as a label; the high half is at `$3FEC`.

```
dte_box:                    ; a = byte, bc = source (advanced), hl = dest $C300+,
        call is_dte         ; e = cells left, d = the caller's ROW index and LIVE
        jp nc,$4124         ; a mark, a literal, or the terminator's pad space
        ld a,[$C69E]        ; the descriptor flags
        rla                 ; bit 7 -> carry, one byte where `and $80` costs two
        dec bc
        ld a,[bc]           ; the code again -- none of these three touch flags
        inc bc
        jp dte_box_hi
dte_box_hi:                 ; at $3FEC
        jp nc,$4124         ; box not marked: draw the byte as it stands
        push bc             ; the source pointer -- emit_lit uses c as scratch
        push de             ; d is the row index and has to come back
        ld b,e              ; b = cells free, which is what emit_lit charges
        ld d,h
        ld e,l              ; de = the destination, which is what it writes
        call dte_emit_yes   ; is_dte already answered, so skip its test
        ld h,d
        ld l,e              ; hl = the destination, past the expansion
        pop de
        ld e,b
        pop bc
        ret
```

Three things worth keeping:

* **It reuses `dte_emit` whole** by moving the drawer's registers into the ones the
  expander uses (`hl` -> `de`, `e` -> `b`) and moving them back. No second expander.
  `emit_lit`'s `$CF38` guard does not fire because the box destination is page `$C3-$C5`,
  which is right -- the box is bounded by its width instead.
* **`a` is recovered from the source, not saved**, because `pop af` cannot give `a` back
  without also giving back the flags the `rla` just set. Sound only here: `$4105` has
  advanced `bc` past the byte, and the one case where it has not -- the terminator, where
  the drawer substitutes `$00` -- cannot reach this path, `$00` not being a DTE code.
* **`emit_lit` was shortened by 3 bytes** to pay for it: `dec b` moved above the store so
  the combining-mark path can share `ld [de],a / inc de / ret`.

## The three white screens, because each is a rule

**1. A `<$XX>` layout escape cannot be a DTE code.** `31:$41E9` is `Weapon  <$B6>Str` --
`$B6` is the vertical bar holding the status screen's two columns, and it was inside
`$B3-$DF`. The drawer expanded it, drew two cells where the row budgeted one, and the
cascade above did the rest. **`$B3-$B6` is now reserved** and the top DTE range starts at
`$B7` (124 codes, not 128; 40.2% not 40.6%), and `build.py` rejects any translation whose
raw escape lands in the code space -- a build error naming the string, not a white screen.
A `<$XX>` byte is layout the renderer must reproduce EXACTLY, the same category as a
control code or a combining mark, and it belongs in the same exclusion.

**2. The gate above.** Reserving `$B3-$B6` fixed the status screen and the file-select
screen still died, on the player's saved name.

**3. Resident code must not run to the last byte of bank 0.** `dte_box_hi` was first
written as exactly 20 bytes, `$3FEC-$3FFF`, so its `ret` sat on `$3FFF` -- and that `ret`
did not return. White screen, CPU spinning on `rst $38`, while the identical bytes ran
clean under `tools/gbemu.py`. Moving the routine twelve bytes earlier, changing nothing
else, fixed it outright. The byte after `$3FFF` is `$4000`, which belongs to whichever bank
is mapped, and during an expansion that is the TABLE bank. `BOX_END` is `$3FFF`, not
`$4000`, and `build_box()` refuses to cross it.

## What this cost, and the one difference that remains

Reserving four codes shrank the table, and **that changes how untranslated Japanese
expands** -- which is not only cosmetic. In the dungeon, `a:120` leaves the status bar's
second row hidden until the next button press, where the pre-hook build restores it after
~46 frames. It is not the box hook: a build with the box hook and `--no-dte` behaves like
the baseline, and an ARBITRARY different code set (`$81-$9C` instead of `$81-$9D`) breaks
it the same way. It is the accepted cost, sharpened: **expanding Japanese changes cell
counts, so it can change message wrapping and therefore timing, not just glyphs.** It
resolves on input, the game stays healthy, and it goes away as text gets translated.

## TASK 1b — the item category boxes (33, 34) — **DONE 2026-07-30**

`Herb / Scroll / Staff / Pot / Food` and `Weapon / Shield / Bracer / Arrow / Other`, both
width 7, both marked compressed, both **photographed on the real screen**. `Staff` is kept:
Joey chose to spend the katakana-grid bytes rather than reword it.

Three things had to be solved, and each is a reusable technique.

**1. Reaching the screen — solved, and it generalises.** The previous session could not
show these boxes and reverted the work for that reason. The way in is bank 4's
**menu-screen dispatcher at `4:$48AA`**: `a` is an index into a 35-entry table at `4:$48C3`,
and **index 27 is `4:$4CD0`**, the routine that shows box 33 or 34 according to `$C6E3`.
Forcing that index makes the REAL routine draw the REAL box through the REAL drawer — only
the navigation is synthetic. `tools/boxscan.py` does it; `--page 0`/`--page 1` picks the box.

This beats hunting for the in-game path, which is still unknown (storehouse / shop / sort
are the guesses). **Any screen with a dispatcher index can be reached this way.**

**2. The allowlist — earned, not argued.** `script/dte_ok.tsv` demands that a trace have
SEEN an expanding loop read a string. The brief proposed reasoning around it instead. Once
the screen was reachable that became unnecessary: `tools/boxscan.py` produces a genuine
observation of all ten rows through `31:$40E4`, and the entries carry a comment saying how
to reproduce it. **Do not weaken this rule; make the screen reachable instead.**

**3. The last byte — 116 of them, via a box ALIAS.** Compression takes box 33 from 32
contiguous bytes to 24 against a largest free run of 23. Rewording the つえ row was the cheap
fix (`Wand`, `Rod` and `Cane` all measure identically at need 476); Joey kept `Staff`.

The supply is `script/box_alias.tsv`, a new declarative file: **box 13 renders box 12's
text**, so its own 116 bytes at `31:$42DB-$434E` become a DECLARED free region. In English
box 12 alone already carries A-Z, a-z, 0-9 and punctuation, so the second page was
redundant. The visible toggle is retired; a forced page-2 state still shows and selects the
same grid. `build.py` redirects every
reference into the aliased block to the target's matching row, which covers the descriptor's
text pointer and `31:$4192`'s grid base. This is **not** `--use-filler`: the bytes are free
because a named box now renders a different one, not because they looked like padding.

## The name-entry grid was reading the WRONG CHARACTER, and now does not

Found while doing the above, in the same code. **The picker duplicates the grid box's row
spacing as an immediate**: `31:$419D` computes `base + (row - 1) * stride + column`, where
`base` is box 12 row 1 (a normal reference, repointed with the box) and `stride` is the
operand of `31:$41A0 ld a,$13`.

`$13` = 19 is correct for the Japanese — 18 bytes plus a terminator. Translated rows fill
all 18 cells, so `needs_term` drops their terminators and the real stride becomes **18**.
Nothing updated the constant, so every row below the first read one byte further along than
the row before it. Measured on the shipped build: **row 2 gave `G` for `F`, row 3 `M` for
`K`, row 4 `S` for `P`.** Typing your own name mostly did not work.

`build.py` now derives the stride from where the rows actually landed, asserts they are
evenly spaced, checks the opcode before patching, and reports the change. Verified with
`tools/gridprobe.py`: every row of both pages now reads the byte it displays.

**The general lesson: a renderer's geometry can be duplicated in ARITHMETIC somewhere else.**
`box_geometry.tsv` moves a box; it cannot know that another routine hardcoded the old
layout. When a box's byte layout changes, grep for code that indexes it.

## Save states — DONE, and this is how to remake them

`saves/` holds Joey's battery save plus three pyboy states. **All of it is gitignored** (game
data), so on a fresh clone it has to be rebuilt:

```sh
cp ~/Library/Application\ Support/MesenCE/Saves/shiren_en.srm saves/shiren_en.srm
sh build.sh                    # copies it to build/shiren_en.gb.ram, which is what pyboy reads
python3 tools/mkstate.py build/shiren_en.gb saves/shiren_en.srm --png-dir build/mkstate
```

```
saves/town.state       Moonlight village, inside the first house
saves/dungeon.state    a floor of 変化の森
saves/floorname.state  the floor-arrival banner, caught while it is up
```

> **THE OLD RECIPE HERE WAS WRONG and is deleted.** It said to pick "Log 3 in the dungeon"
> from the title screen. **Shiren does not let you save inside a dungeon** — that is the
> genre — so no `.srm` can hold a log parked on a floor, and no such save exists. The
> dungeon has to be WALKED into from the village, and it cannot be found by searching
> either: four 20,000-frame seeded random walks never left the village. Joey gave the
> route on 2026-08-04 and `mkstate.py` drives it: out of the house, then **west across
> town** to the gate, clearing the villagers' text boxes, one more square, accept.

Use them with `gbrun.py --state saves/dungeon.state`. **This is what finally reached the
composer** — `13:$40D8` fired 98 times and `dte_emit` 587 from the dungeon state, against
zero from the title screen.

One caveat when scripting: ~5000 frames of random input from `dungeon.state` walks out of the
dungeon and back to the village, and the level resets 2 -> 1. That is the Shiren mechanic for
leaving, not a bug.

~~A screenshot of the item action menu.~~ **Done 2026-07-30** -- `See / Put / Toss / Drop /
Info` all correct in a real dungeon, all five stored compressed, `See` a single byte.


## The copy-loop inventory — use this instead of guessing

| idiom | bytes | sites |
|---|---|---|
| store-then-test | `2A 12 13 FE FF 20` | 6: `4:$7458` `11:$51F0` `11:$52D5` `11:$7E63` `14:$7C1E` `30:$7E8A` |
| box row drawer | `31:$40D8`, source in **bc** | 1 caller, `31:$4095`; hooked at `31:$4106` |
| test-then-store | `2A FE FF 28` | 44 candidates (generic pattern; includes `13:$40DB`) |
| control-aware | `2A FE E0` | 2: `13:$6893`, `13:$6AE5` |

`tools/gbrun.py --trace` hooks all of them at once and reports which fired with what source,
which is how to attribute a screen rather than reason about it.

## What is already in the ROM and correct

| piece | where |
|---|---|
| expander + `dte_box` low half, 158 bytes | bank 0 `$0062-$00FF` — **FULL, 0 spare** |
| `dte_box_hi`, 17 bytes | bank 0 `$3FEC-$3FFC`; `$3FFF` must stay unused |
| table, direct-indexed by code | bank 32 `$4100`/`$4200`, two 256-byte pages |
| hook | `13:$40F1` -> `call dte_emit`; 7 bytes free at `13:$40F6` |
| hook | `13:$6893` -> `jp $00C2`, loop relocated to bank 0 |
| hook | `31:$4106` -> `call dte_box`, three bytes in place |

**46 pairs, 28.2% measured on the SNES English corpus.** Narrowed from 124 on 2026-07-30:
the code space now holds only bytes NO untranslated string contains, because the composer
has no gate and expanding Japanese changed cell counts. See the fixed bug above.

Two ROM facts made the table cheap, both in `FINDINGS.md`:

1. **Byte 0 of every bank is that bank's own number**, readable at `$4000` — how `0:$079E`
   recovers the caller's bank. A resident routine can map a bank over the caller and put it
   back, so **the table never had to be resident**.
2. **Banks 32-63 are entirely `$FF`.** Free by inspection, unlike any WRAM gap.

The old three-way decision (table size / table location / expander location) is closed. Do
not reopen it.

## Two decisions worth not re-litigating

**The buffer bound is an address, not a character cap.** `emit_lit` refuses to write at or
past `$CF38` — stronger than a character cap, because it holds however many bytes a pair
expands to. `$CF38` not `$CF43` because the composer reads the buffer's zeroes as the end of
the line, so writing past the shorter clear (`$CF07+$32`) would leave text unterminated.

The box path does NOT get that guard, and should not: its destination is the `$C300`
tilemap staging buffer, and what bounds it is the box width in `e`.

**Cell counting charges the dakuten, not the base character.** `13:$40F3` peeked the next
*source* byte, which cannot survive expansion once that byte may live inside a table entry.
Charging the mark is equivalent — a mark always follows a base character, two never adjoin —
and needs no lookahead.

## ~~The one accepted cost~~ — RETRACTED 2026-07-30, it was a real bug

**Untranslated Japanese collides with the DTE code space** (it uses 181 of 224 literal
codes) and renders differently garbled. The Latin font is already over the kana tiles, so
it is garbage either way, and the `$CF38` guard makes overrun impossible. Only translated,
allowlisted strings are compressed, and box text is expanded only for a box marked
compressed.

**It is not purely cosmetic, though, and this session measured that.** Expanding Japanese
changes CELL counts, so it changes message wrapping and therefore timing: with `a:120` from
`saves/dungeon.state` the status bar's second row stays hidden until the next button press.
Any change to the code set moves this around — an arbitrary `$81-$9C` does it too. It
resolves on input, the game stays healthy, and it shrinks as text gets translated.

## Code space is 46, and it is MEASURED against the script

The old plan said 140; that counted only English. A DTE code must also miss the combining
marks, be separable cheaply, and — learned the hard way — miss any byte a translation names
with a `<$XX>` escape. Free: `$43-$78`, `$81-$9D`, `$B7-$DF` = **124 codes**, five compares.
`$B3-$B6` is the reservation for layout glyphs; `$B6` is the status screen's column divider.

The 19 left over are English's punctuation, reusing the ROM's **native** glyphs at
`$7C-$B2`. (Also why `codec.encode` resolves `'F'` to `$B4` and not latinfont's `$10` —
`build.encode_en`/`EN_CODES` is the one the inserter uses.) Compacting them into `$43-$4C`
would make `$4D-$B2` one range and a one-compare test: the only DTE upgrade left.

## The tools

| tool | why it matters |
|---|---|
| `tools/gbasm.py` | assembler whose opcode table is **inverted from `dis.py`'s**, so the two cannot drift. `--selftest` round-trips 249 forms |
| `tools/gbemu.py` | ~40-opcode interpreter that **raises on anything unimplemented**, so a patch cannot be silently mis-executed into a passing test |
| `tools/dte_rom.py` | the expander source, the table, the hooks, `verify()` and `verify_box()` |
| `tools/gbrun.py` | **headless pyboy**: boot, drive, screenshot, hook. `--trace` attributes a screen to a copy loop; `--dte-scan` generates the allowlist; `--compare` pixel-diffs two builds; `--state` loads a save state |
| `tools/msgdur.py` | **the only check that sees a DURATION**: message lifetimes from WY over a seeded dungeon walk, comparable build to build. Run it after anything that touches the composer, the code space or the inserter |
| `tools/msglog.py` | transcript of what the COMPOSER drew, decoded, with frame numbers and ROM/WRAM source |
| `tools/dialogue_fit.py` | **prices natural English against the composer's real rules** — auto-wraps at 18 cells so hand-fitting cannot flatter the result, then compresses. `--ranges max` prices the best case. Read the PER-STRING column: in-place fitting cannot borrow slack |
| `tools/crashscan.py` | **the only check that looks at the CPU**: seeded walks, detects `rst $38` / VRAM execution / a stuck loop, and `--stack` names the routine that jumped into nothing. Sweep seeds -- one proves nothing |
| `tools/dialogue_preview.py` | **draws a translation as the composer will**, and FAILS a build on a line over **24** cells (18 before VWF, and `FIXED_WIDTH` is still 18 for `--no-vwf`). `--selftest` re-validates the model against 1608 Japanese lines **at 18** — the Japanese was written for an 8px cell and is the model's only falsifier; `--check` lints every translated string without building a ROM |
| `tools/name6.py` | the 4 → 6 character player name: the save record, the summary cascade, the packed buffer, the default name. `--selftest` checks the sizes its bank-15 layout depends on; every write asserts the opcode it replaces. `build.py --no-name6` is the bisect control **and the build that can read an old save** |
| `tools/rank6.py` | the rankings board's own name, 4 → 6 characters: the record 10 → 12 bytes, 20 → 19 entries, and a struct builder that sources the name from `$D0FD`. `--selftest` checks the layout arithmetic and the two operands that must NOT move; `install` sweeps the drawer and **fails on an unclassified field offset**. `--upgrade old.srm new.srm` converts a save. `build.py --no-rank6` is the bisect control |
| `tools/vwf.py` | the composer's variable-width font: a uniform **6px pen**, so a line holds 24 characters in the same 18 tiles. Pre-shifted font + renderer in bank 32, reached by one `rst $10`; the scanner is COPIED out of bank 13 at build time rather than rewritten. `--selftest` checks the pen geometry both ways round. `build.py --no-vwf` is the bisect control, and the build to compare against for anything about timing or line breaks |
| `tools/mkstate.py` | rebuilds all three `saves/*.state` fixtures from a save the ROM wrote. **Use this instead of hand-editing a state** — they carry WRAM *and* cart RAM, so a layout change makes them silently wrong. `--png-dir` photographs each one, which is the only way to notice the route has drifted |
| `tools/namerun.py` | **the only way to reach name entry** — no walk seed does. Types a name by writing the picker's cursor variables, follows it into SRAM (`--sram`) and back out onto file select (`--reload`). `--fresh` for a blank cart (the new-game path), `--rename` for the other entry point |
| `tools/nameflowspill.py` | drives the saved Copy Log -> Erase copied log -> New Log route and proves the field underline plus `() :` native planes are restored before the name keyboard appears |

`python3 tools/dte_rom.py` runs the **actual ROM expander** over the SNES English corpus
against `dte.py`'s reference decoder: **5278 segments, 0 mismatches**, checking emitted
bytes, cells charged, `hl`/stack integrity, and bank restoration. `verify_box()` goes
further and runs **bank 31's real drawer out of `base.gb`**, patched and unpatched, over
every real box row -- which is the only way to state "the Japanese path is untouched" as a
checkable claim rather than a hope.

**But pair it with a screenshot.** Byte-level verification proves the patch is correct; it
cannot prove the renderer calls it, and it cannot see a cascade two rows later. All three of
this session's white screens were green at every byte-level check.

---
## TASK 2 — the dialogue sample — **DONE 2026-07-31. VWF IS CANCELLED.**

Sixteen real composer strings translated, in the ROM, and photographed on the real screen:
nine combat fragments, four hunger warnings, and three village dialogue strings including
the 190-byte four-box innkeeper conversation. `script/menu_en.tsv`, section
`DIALOGUE SAMPLE (TASK 2)`. Every one was picked out of a `msglog.py` transcript, so all of
them are text the game demonstrably draws.

Build is clean: **1498 checks, no problems**, `dte_rom.py` 5278 segments / 0 mismatches,
`verify_box` 0 failures, and the file menu and status screen pixel-compare **IDENTICAL**
against the same build without the sample.

### The three questions, answered

**1. Does fixed-width English at 18 cells read badly, or merely plainly?**

**Merely plainly, and it looks fine.** Three-line boxes, nothing clipped, nothing cramped:

```
Innkeeper: You OK?          This is Moonlight        Keyaki: Don't...
 You moaned badly.           Village. Monsters        But I'm glad.
 I worried.                  got you at Kuyo   ▼
```

Eleven lines and four boxes of one conversation fit 189 of 190 bytes with no line over 18
cells and no contortion in the wording. This is the answer VWF was waiting on.

**2. How much do the `<var>` substitutions cost? — this is where the budget actually goes.**

A lot, and it is the real constraint on combat text. On screen today:

```
Shir hit XMfJbt             XMfJbt hit you
for 6 damage!               for 2 damage!
```

`Shir` is the 4-character player name (TASK 3), and `XMfJbt` is an **untranslated monster
name** drawn through the Latin font. The literal cells are the small part of each line:

| string | literal cells | leaves for substitution |
|---|---|---|
| `<var> hit <var>` | 5 | 13, for **both** names together |
| `<var> hit you` | 8 | 10 |
| `Defeated <var>!` | 10 | 8 |
| `Dodged <var>!` | 8 | 10 |
| `<var> missed!` | 8 | 10 |
| `<var> is now Lv<cE4>!` | 11 | 7 minus the level digits |

**The binding case is `<var> hit <var>`.** With TASK 3's 6-character player name that
leaves **7 cells for a monster name**, and with today's 4-character name, 9. So translated
monster names need a cap around 7-8 cells, and `<var> is now Lv<cE4>!` independently caps
the PLAYER name at 6 — which is exactly what TASK 3 targets, so the two agree.

Nothing here is a font problem. It is a budget that has to be respected when the names get
translated, and a build check can enforce it.

**3. Does anything wrap badly?**

Nothing wrapped badly, because **nothing wraps at all** — see the next section, which is
the most important thing this session found.

### Over-long lines TRUNCATE. They do not spill. — measured, and it retracts a claim

The previous handoff argued VWF was optional partly because "the composer's failure mode at
fixed width is plain text, not broken text. Dialogue spills into more lines and more boxes;
nothing truncates." **That is false, on both composer paths.** Tested by deliberately
over-running a line in a throwaway build and photographing the result:

* **18-cell path (`13:$40D8`, bank 13 combat and dungeon messages).** `for <cE4> points of
  damage!` — 21 cells — drew `for 2 Points of da` and lost `mage!` outright.
* **loop2 (`13:$6893`, bank 11 and 14 dialogue).** `Innkeeper: Are you OK?` — 22 cells —
  drew `Innkeeper: Are you`, lost ` OK?`, and ate the next line's leading indent as well.

So a line over 18 cells silently loses text, and on the dialogue path it also disturbs the
line after it. There is no wrap, no ellipsis and no build error — it just goes.

**Consequence: build the dialogue preview tool before bulk translation, not after.**
**Done 2026-07-31 — `tools/dialogue_preview.py`, see TASK 1a.** The
previous handoff already listed "no dialogue equivalent of `boxpreview.py`" as owed work;
this is the reason it was not optional. It has to run a string through the composer's real
rules — the 18-cell budget, the `<name>`-costs-zero counter bug, the ~54-byte `$CF07`
buffer — and it should FAIL a build, the way `box_too_wide` does, rather than print a
warning. Cells are computable from the translation; only the `<var>` width is not, which is
what the caps in question 2 are for.

### What the sample cost, mechanically

* **Bank 13 gained 7 bytes.** Eleven relocatable strings went from 167 Japanese bytes to
  170 raw English, and DTE (nine of them are already in `dte_ok.tsv`) took it back under.
* **Bank 14 stayed at +0 spare**, because all three village strings are IN-PLACE — bank 14
  and bank 11 dialogue pointers are computed at runtime and cannot be repointed, so English
  must fit the original byte count exactly.

  **CORRECTED 2026-07-31, and this was the important error of the session.** The first
  version of this section said in-place dialogue was "a hard byte cap with no compression
  to spend". That is FALSE — nothing in `build.py` excludes an in-place string from DTE.
  They were uncompressed only because they were not in `dte_ok.tsv`, and they could never
  GET there: `loop2` is the loop that expands, but its source is the WRAM buffer at
  `$CF8F`, so the ROM address never appears in a register at the expander and
  `--dte-scan` discarded it. Village text was invisible to the observer, not ineligible.

  Joey read the shipped lines and said some were so unnatural the meaning could not be
  recovered — correct, and the cause was this budget being ~22% too pessimistic. See
  "Observing the dialogue stagers" below. `14:$5047` now holds **240 bytes of English in
  190** (180 packed), and the prose is ordinary sentences instead of telegraphese.
* **The speaker prefix is where the bytes go.** `おかみ「` is 4 bytes; `Innkeeper: ` is 11.
  It eats 11 of an 18-cell line, which is why the first draft's opening line was cramped.
  With the real budget the fix is simply to let the sentence run to the next line.
* **The font has no `"` glyph.** Available punctuation is `` !'()+,-./:?[]~ `` (see
  `latinfont.EN_CODES`), so attribution is written `Name: ` with no quotes. Adding `"`
  means a new glyph over a kana tile plus reserving its code out of `dte_rom.DTE_RANGES`;
  cheap, but it was not needed and is not done.

### Control codes in translations are now written by NAME

`build.encode_en` previously understood only `<$XX>` raw escapes, so dialogue would have had
to spell `<var>` as `<$E2>`. It now accepts every token in `codec.CONTROL` — `<var>`,
`<br>`, `<end>`, `<brk>`, `<cE4>`, `<cE0:88>` — the same tokens `codec.decode` prints in
`script.tsv`'s `jp` column, so a translator copies the token straight across.

Keep the two spellings apart. **An escape means "layout byte, reserve it out of the DTE code
space"** and `build.py` checks it against `dte_rom.DTE_CODES`; a control code is already
excluded by being `>= $E0`. Writing `<$E2>` for `<var>` would work byte-for-byte and quietly
put a control code into the wrong category.

`build.cells()` was corrected at the same time: control codes and their argument bytes are
not cells. They never reach the tilemap, and `<br>` ends a line rather than sitting on it,
so the old count charged a dialogue line for its own line break. Box rows contain no control
codes, so every box measurement is unchanged — verified, the checks and both pixel
comparisons are identical with and without.

### Observing the dialogue stagers — how village text became compressible

**The problem.** `script/dte_ok.tsv` demands that a trace have SEEN an expanding loop read
a string, and that rule is right and must not be weakened. But village and story dialogue
could never satisfy it, for a structural reason rather than a missing observation:

```
ROM string --(bank 11 $569E / bank 14 $4010)--> $CF8F --(loop2, EXPANDS)--> $CF07
```

`loop2` is the loop that expands, and its source is WRAM. `gbrun.dte_scan` requires a
`$4000-$7FFF` source, so it discarded every hit — and all 613 bank-11 plus 207 bank-14
strings, **the bulk of the script**, were locked out of compression for ever without
anyone noticing.

**The fix.** `--dte-scan` now also hooks `dte_rom.STAGER_SITES`, the two routines that copy
a line out of the ROM into `$CF8F`, at the `ld bc,$CF8F` that sets each copy up. Not the
loop head (`11:$56A5`, `14:$4010`): that is re-entered per BYTE and would record every
interior address as a string start. By the setup instruction `hl` holds the real ROM
address — both readers arrive with the window bits toggled and undo that first
(`11:$56A0 set 6,h`, `14:$400A xor $C0`).

**This is a weaker claim than observing the expander**, and it is labelled separately in
the allowlist for that reason: it says *these bytes reach loop2*, not *an expanding loop
read these bytes*. Three things could break in between, and all three were checked:

1. The stagers stop at `$EE`/`$EF`/`$FF`. Every DTE code is in `$92-$99`, `$B8-$C1` or
   `$C4-$DF`, and a pair may not span a control code, so the byte a stager stops on is the
   same before and after compression.
2. `13:$67F3` reads the FIRST staged byte and does `cp $EC`. `$EC` is a control code, so
   compression neither produces it nor absorbs it — a line that started with `$EC` still
   does, and one that did not still does not.
3. `13:$688D`/`$6893` is loop2, which is hooked to the expander.

Those are the **only** three readers of `$CF8F` in the ROM, established by scanning for the
operand bytes `8F CF`: `11:$56A2`, `13:$67F3`, `13:$688D`, `14:$400D`.

`--dte-scan` also gained **`--walk-seed`**, because a press schedule cannot reach combat,
death or the inn scene — it drives with the same seeded walk `msgdur.py` and `crashscan.py`
use, so an allowlist entry is reproducible. And it now drops the interior addresses the
stagers report when re-entering a conversation at each `<br>`.

**What it bought:** `14:$5047` went from 189 bytes of English to **240 in the same 190**
(180 packed). That is the difference between `Pass, eh? Fall / there and you get / sent
back.` and `If your strength / runs out there, / you wake up here.`

**Do this for bank 11 next.** ~~613 strings~~ — corrected 2026-07-31: it is **151** in-place
strings in bank 11 plus the **146** of bank 14 that this pass did not reach either, and the
blocker is coverage rather than the hook. Full brief in `docs/archive/HANDOFF_1B.md`.

### Bank 13's allocator — a negative result worth not repeating

Bank 13 now runs at ~100% utilisation (6968 of 6977 bytes). At that point placement is bin
packing, not a heuristic problem: with single-digit total slack, a unit needing 5
contiguous fails unless the leftover happens to land in ONE run.

**400 seeded randomised restarts on top of the three existing orders were tried and do NOT
help** — the failure survived every one, at every slack level from +2 to +9. The change was
reverted rather than left in; the comment in `build.py` records the result. Making bank 13
hold more English needs exact-fit search (subset-sum per run) or more space, not a better
shuffle.

**The cheapest real lever is deduplication.** Identical translated strings are stored twice
today: `for <cE4> damage!` is `13:$4B6B` and `13:$4B82`, byte-identical, 13 bytes each. In
bank 6's message list `しかし なにもおきなかった` is pushed from **12** different sites.
Pointing every reference at one copy is a pure win and needs no new ROM code — only the
inserter noticing that two units have the same bytes.

### THE DEATH CRASH — 240 discarded references, fixed 2026-07-31

**Joey hit this on a real build: the game halted while walking in the dungeon, and again
on every death, before the inn dialogue could be reached.** Reproduced headlessly with
`tools/crashscan.py` (2 of 12 seeds), bisected, fixed, and re-verified over 12 seeds.

**What it was.** `extract.py` only trusted a `ld r16,$XXXX` from bank 0 or from the
string's own bank. But **banks 4, 5, 6, 15 and 31 all push bank-13 message pointers**
through `0:$028B`, and all **240** of those references were being discarded. That was
invisible for the entire project because **bank 13 had never moved** -- every stale
pointer still happened to be correct. The TASK 2 sample was the first bank-13 translation
ever, `13:$4C2D` (`<var>は ちからつきた…`, the death message) moved to `$4E96`, and
`5:$44B8` / `5:$5891` went on pointing at `$4C2D`. The game read garbage as a message
pointer and fell into `rst $38`.

**How it was found**, because the method generalises: `crashscan.py --stack` dumped the
stack at the halt. Bank 13 mapped, `$00E7` on the stack (inside the relocated `loop2`) and
`$683A`/`$6878`/`$68CB` (bank 13's message reader) -- so the crash was in the message path,
not the render path. Bisecting the sample showed each group healthy ALONE and G1+G2
crashing, which said "not a string's content, but how far bank 13 shifts". Then a byte scan
for the death message's address found the two bank-5 loads nobody was repointing.

**The rule that fixes it, and it is structural rather than a heuristic.** `0:$028B` stores
bc at `$FF90`/`$FF91` and pushes it through `0:$23A4` into the ring at `0:$3C5C` -- the
queue bank 13's `$67D5` consumes. **So a `ld bc` that reaches `$028B` names a bank-13
address whatever bank the caller lives in.** 233 direct sites plus 7 `jr`-chain sites
(`ld bc,A / jr $+3 / ld bc,B / call $028B`, an if/else where both branches push). Zero of
the 240 also match a string in their own bank, so no new ambiguity. `boundary_votes` still
runs on every one, and still rejects two of them as mid-instruction.

**Plus a safety net.** An untrusted-bank `ld bc` that looks like a reference but does NOT
reach `$028B` no longer gets silently dropped -- the target string is **pinned** and never
relocated (`"pin"` in `script.json`, honoured by `build.py`). 16 strings. Dropping is only
safe while the target stays put, which is precisely the assumption that just crashed;
pinning costs a few bytes and cannot crash.

**What it cost.** Bank 13 goes from 183 to 323 relocatable strings, so its pool is much
more contended: the first build after the fix failed with `fragmentation, not shortfall`
(needed 5 contiguous, largest run 4). Three sample strings were shortened by 3 bytes each
to clear it (`Gained` -> `Got`, and two `...` dropped). **Bank 13 is now the tight bank**
and bulk translation there will need the allocator to do better than first-fit.

Verification after the fix: **1498 checks ALL OK** (up from 1438 -- the recovered
references are now checked), no problems, `dte_rom.py` 5278/0, extract round-trip ALL OK,
menus pixel-IDENTICAL, and **12 of 12 seeds healthy** where 2 previously halted. The death
-> village -> inn sequence is photographed working on the seed that used to crash.

### One immediate, two banks — a repointing hazard, fixed

**Found because the sample tripped it.** Translating bank 13 made bank 13's strings move for
the first time, and four bank-11 strings immediately failed reference verification.

A bank-0 immediate `ld bc,$4C1E` names an **address, not a bank**. `extract.py` resolved
each one against every text bank and recorded it on *all* of them, so four operands were
each claimed by two strings at once — a bank-11 one and a bank-13 one at the same in-bank
address. `build.py` writes an operand once, so whichever bank moved first won and the other
got a pointer into the winner's text. Bank 13 had never moved before, which is the only
reason this had not fired.

| operand | bank 11 claimant | bank 13 claimant |
|---|---|---|
| `0:$2592` | `ヤミウッチー` (monster) | `かいしんのいちげき！` (critical hit) |
| `0:$2661` | `とおせんりゅう` (item) | `<var>はレベル<cE4>にさがった` |
| `0:$2687` | `ぼうれいむしゃ` (monster) | `<var>のこうげきをかわした` |
| `0:$2786` | `ライオンのえのまきもの` (item) | `<cE0:6E>しかし アイテムをつかって` |

**Bank 13 wins, from the ROM's structure rather than from the text.** Every one of these
loads feeds `0:$028B`, which stores the pointer at `$FF90`/`$FF91` and pushes it through
`0:$23A4` into the ring at `0:$3C5C` — the queue bank 13's `$67D5` consumes. Bank 11's and
bank 14's text is reached by tables in its own bank, or by a runtime pointer whose stored
form has its window bits toggled (`$232D`, `$82B7`), never as a plain `$4xxx` immediate in
bank 0. Confirmed three ways: **all 24** unambiguous bank-0 immediates resolve to bank 13;
the bank-11 claimants are item and monster NAMES, which a message pusher would not push; and
`msglog.py` caught the composer reading **12 bytes** at `$4BA7`, which is bank 13's
`<var>のこうげきをかわした` and not bank 11's 8-byte `ぼうれいむしゃ`.

The fix is deliberately narrow — when there is no bank-13 candidate nothing changes — so
`0:$22BD` still claims `11:$4202` and still pins box 2. That one is a **data blob**, and it
is worth knowing that `dis.boundary_votes` cannot see through it: it scores **64/0**,
because a run of short data bytes decodes as a sequence of valid short instructions. Votes
prove an immediate is not inside a longer instruction; they do not prove the bytes are code.

Each bank-11 string kept a genuine `table` reference, so all four are still relocatable and
nothing was lost — which independently corroborates the diagnosis.

### `msgdur.py` is no longer a straight build-to-build A/B

Its walk is seeded random input, so it is only controlled while the SCRIPT is identical.
English combat text changes a message's duration, the next press then lands on a different
game state, and the run diverges: at seed 2 the sample build's walk got the player killed
(`HP 0/20`, LCD on, game healthy) and reported one 12,034-frame "message" that was the death
box, not a hang.

**And the exact control is gone, for a reason worth understanding.** `--no-hooks` implies
`--no-dte`, and bank 13 only fits with DTE, so a `--no-hooks` build of the current script
reverts bank 13 (and bank 30) to Japanese. **The control ROM therefore no longer holds the
same text as the build it is controlling**, which is precisely the condition under which the
seeded walk diverges. Against a freshly built control the sample build reports 9 boxes to
10, median 202 to 193 — divergence, not regression.

This was verified rather than assumed. Built with the sample REMOVED (so bank 13 is Japanese
in both), the full build and its `--no-hooks` control are frame-for-frame identical: same 10
boxes, same frames, same durations. That is what exonerates this session's code changes —
`cells()`, `encode_en()` and the `extract.py` disambiguation move nothing.

**So going forward, use it two ways.** To exonerate a CODE change, revert the script to a
state `--no-hooks` can carry and expect exact equality. To judge a SCRIPT change, expect
divergence and read the durations for health — nothing collapsing toward the ~17-frame
symptom of the old bug — rather than for equality. Getting an exact control back for
translated bank-13 text would need a `--no-hooks` variant that keeps DTE's *storage* while
bypassing its render path, which does not exist and may not be worth building.

---

## TASK 2b — VWF for the composer — **CANCELLED 2026-07-31, on the sample's evidence**

Not deferred. Cancelled. `docs/archive/HANDOFF_VWF.md` is kept as reference for the two loops and the
space survey, and is marked cancelled at the top.

**Why, in the order the evidence supports:**

1. **Fixed-width English reads fine.** Question 1 above. Nobody had seen it; now it is
   photographed, and it is plain rather than bad.
2. **The tightest constraint in the dialogue script is BYTES, and VWF does not buy a single
   byte.** Bank 11 and bank 14 dialogue is in-place because its pointer is computed at
   runtime; `14:$5047` had to land in exactly 190 bytes. VWF buys cells. Cells were not what
   ran out there.
3. **Where cells DO bind — `<var>` substitution — a name cap fixes it for free.** 7-8 cells
   for monster names, 6 for the player. That is a rule the translator follows and the build
   checks, against a job that needs a high bank, a trampoline, a width table, a font rebuild,
   changes to both composer loops, and a collision with DTE's cell accounting.
4. **VWF is the one remaining change that can move message TIMING**, which is the class of
   bug that cost three sessions, and `msgdur.py` has just become a weaker control (above).

The honest argument on the other side, recorded so it is not lost: truncation is real (it
was the previous handoff's reason for relaxing about VWF, and it was wrong), and VWF would
genuinely rescue long substituted names. It is the wrong trade anyway — capping names costs
nothing and truncation is preventable by a build check.

**If this is ever reopened**, reopen it for ITEM NAMES in the 16-cell list box, not for
dialogue, and bring a measurement of how many translated names actually exceed the cap.

---

## TASK 4 — THE SPACE PROBLEM — measured 2026-07-31, and it is the real blocker

**Joey's question: is there enough room for natural English, or does DTE force
machine-translation-grade text?** Measured, not estimated. The answer is that **DTE alone
is not enough**, and the shortfall is structural rather than a matter of writing tighter.

### The measurement

Eighteen varied village/story strings were translated as ordinary English with **no budget
fitting at all**, then laid out by the composer's real rules (18 cells, `<br>`, 3 lines per
box) so hand-fitting could not flatter the result. `tools/dialogue_fit.py` does this.

| | |
|---|---|
| Japanese | 831 bytes |
| Natural English, raw | 1376 bytes = **1.66x** |
| after DTE at today's 46 codes | 1033 = **1.24x** |
| after DTE at the theoretical maximum 128 codes | 905 = **1.09x** |

An earlier note in this file guessed 1.8-2.0x. That was a guess; 1.66x is measured.

### Why that still is not enough — the number that matters

**58% of the script (16,853 of 28,819 bytes) is IN-PLACE**, and in-place fitting is
**per string**, not aggregate. A string that comes in under budget cannot lend its slack
to one that comes in over. At the full 128-code space:

**12 of the 18 sample strings still do not fit.** The overruns are not marginal —
`14:$6317` is 1.66x, `14:$53FB` 1.49x, `14:$5B9B` 1.36x. Getting those into their original
byte counts is exactly the telegraphese Joey objected to.

### And the full code space is not available yet anyway

`tools/dte_ranges.py`: only **58** bytes are safe today, because 1147 untranslated strings
still occupy 179 distinct values — the kana block `$43-$78` alone is 54 of the 128 codes
and cannot be touched until the Japanese using it is gone. The composer has **no gate**, so
it expands untranslated Japanese too. The code space therefore widens only as translation
finishes, which is the wrong way round: the budget arrives after the work that needed it.

(The expander also cannot afford a fourth range — it is 158 bytes at three ranges and bank
0's padding is exactly 158, so codes are taken by MERGING ranges, never by adding one.)

### The fix: redirect in-place strings into the empty half of the ROM

**The ROM is already 1 MiB MBC3 and 31 banks (496 KiB) are entirely `$FF`.** Space is not
the constraint and MBC5 would add nothing. The constraint is ADDRESSING: each reader lives
in the same bank as its text, so the bank is implicit and the arena is only the ~30 KB
where text already sits.

In-place strings cannot be repointed because their pointer is assembled in event code at
runtime and never appears in the ROM as a constant. **But they do not have to be.** Leave
the pointer alone and change what the READER does with it:

* At the original address, write a short **redirect**: a marker byte plus a bank and
  address, ~4 bytes out of the string's original budget.
* Teach the dialogue reader that a line beginning with the marker means "continue from
  bank B, address A" — the overflow text lives in a free high bank.

**Why this beats the bank-selector idea I raised earlier.** The runtime pointer does have a
spare bit (`13:$7593` dispatches on `bit 7,h`; bit 14 is 0 in all 27 pointers observed at
runtime, both banks — `$2340` -> `set 6,h` -> `11:$6340`, `$B305` -> `xor $C0` ->
`14:$7305`). But using it requires the PUSHERS to set it, and the pushers are the event
code that FINDINGS established is not statically enumerable. Redirection needs no pusher
change at all, because the pointer still points where it always did.

**The decisive advantage: it converts a PER-STRING constraint into an AGGREGATE one.** That
is what kills the 12-of-18 problem — overflow goes into a shared pool instead of having to
fit inside each individual string.

### What is unverified, and must be a spike before anything is built on it

1. **Where the redirect check goes.** The natural place is the stagers (`11:$56A2`,
   `14:$400D`), which hold the ROM source in `hl` — but a routine executing in bank 11
   cannot switch bank 11 out from under itself, so the read loop has to be relocated first,
   exactly as `13:$6893` was relocated to bank 0.
2. **Where that relocated code lives.** Bank 0's `$0062` padding is FULL (158/158), the
   tail holds 17 of 19, and the RST gaps are 18 bytes in three runs of 6. So it needs a
   free high bank plus a trampoline — the same conclusion VWF reached, and it was never
   tested.
3. **The marker byte.** It must be something no line can legitimately start with. The
   unused control codes (`$E1`, `$E6`, `$E9`) are candidates; `13:$67F3` already tests the
   first staged byte against `$EC`, so first-byte dispatch is established practice here.
4. **Cost per string** (~4 bytes x ~800 strings) against the space freed in banks 11 and
   14, which the RELOCATABLE strings in those banks can then use.

**Do this before bulk translation, not after.** Prose written against a 30 KB arena gets
rewritten if the arena becomes 100 KB, which is the same re-fit trap that already cost this
project once.

## TASK 3 — player name: 4 -> 6 characters — **DONE 2026-08-03, `tools/name6.py`**

Name entry and Rename both take six characters, the name survives save → reload, and the
log list draws it. Full account in `HANDOFF_NEXT.md` §3 session 1; the module's docstring is
the design. Bisect control and old-save reader: `build.py --no-name6`.

**The save format changed** — the scatter/gather record is 81 bytes, not 79 — so a save
written by an older build loads without crashing but reads every field past the name two
bytes early, and the log list loses its place name.

Almost everything the brief below predicted was wrong in some detail, which is the useful
part of the record:

- ~~**The limit is two immediate bytes**~~ — it is ONE NIBBLE, `4:$5E91 ld a,$40`, the high
  half of `$C6E2`. The two `ld d,$04` are the pack/unpack caps and do nothing on their own.
- ~~**Storage looks 8 bytes wide**~~ — the packed buffer is exactly 4 bytes at `$D100` and
  `$D104` starts a live 120-byte block, so it was rehomed BACKWARD to `$D0FD`. The `$08` at
  `4:$676C` is the DISPLAY form, two bytes per character because a dakuten gets its own; it
  is deliberately left at 8, because the translated picker has no kana and therefore no
  dakuten, and the file-select row it writes into has only 16 bytes per slot.
- **The display field did have to widen** — `4:$5E76`/`$5E85` `ld d,$08` → `$0C`, twelve
  cells for six characters. The ROM already had the wider box: `4:$6150` picks box `$0B` for
  any width but 4, and `4:$5E9A` was already setting width 6 for the Rename screen.
- **The real work was the SAVE**, which the brief only flagged as "verify": a 79-entry
  pointer table, a class table, an 81-byte template, a summary buffer whose stride and
  twenty-one `ld hl,sp+n` operands all move, and eight bytes of bank 15 that do not exist.
- **The picker grid already works in Latin** and its label row is translated
  (`CAPS  Fwd Bck  End`, cursor lands correctly — `gridprobe.py` clean on every row and on
  the page-2 alias after the change).

---

## PARKED — menu work (TASK 1's hooks are now in; the blocker is space, not reach)

**Item action menu verbs — DONE 2026-07-30**, closed by DTE with the table weighted toward
bank 30. Needs 59 of 73 bytes. Confirmed on screen in a dungeon. Original note follows.

Box widened to columns 9-19 (cursor + 8 cells) and the cursor
table moved with it. Bank 30's pool is 73 bytes and needed
86. DTE at 15.4% gives 10 of the 13, and the last 3 come free from **four dead verb entries**
— index 10 `かく` (in no category table and no code path, probably vestigial: writing blank
scrolls is an SNES mechanic) plus three that point at a lone `$FF`. Reachability was
enumerated from the category tables at `30:$7DE8`/`$7E14`/`$7E40`, the context rows at
`$7DD8`/`$7DE0`, and the substitutions at `$7D73` and `$7DA0`.

**~~Item category boxes (33, 34).~~ DONE 2026-07-30** — see TASK 1b above. Route 2 (alias,
data only) is what shipped, generalised into `script/box_alias.tsv` so the next reclamation
does not need new code. The freed run is `31:$42DB-$434E`, 116 bytes, and bank 31 went from
+60 to +165 spare.

**Box 48 (`Normal`'s difficulty explanation) stays Japanese.** Its first row is 20 bytes but
16 cells — four dakuten — and English has none, so nothing can consume 20 bytes inside an
18-cell box without starting row 2 two bytes early. Reported as `box_in_place`. The fix is to
unpin the box, which needs **interior-reference repointing** (rewrite a reference that points
into the middle of a block by the same delta the block moved). That also unpins boxes 50 and
51 and frees more of bank 31.

**No dialogue equivalent of `boxpreview.py`.** Boxes are checked; dialogue is not. Before bulk
translation, build one: run a message through the composer's real rules — 18-cell budget, the
`<name>`-costs-zero counter bug, the ~54-byte `$CF07` buffer — and print the wrapped result.
**Promoted to job 1 in the work queue as of 2026-07-31**: over-long lines were found to lose
text silently on both composer paths, so this is the only thing that can catch the failure,
and it should FAIL a build the way `box_too_wide` does rather than print a warning. Cells are
computable from the translation; only `<var>` width is not, which is what the name caps in
TASK 2 are for.
Padding audit for context: of 478 in-place non-box strings, **380 contain dakuten**, so a
translation padded to byte length draws more cells than the Japanese did (mostly +1 to +4,
worst `14:$5CE0` at +34). That is cosmetic — trailing blank space — not corruption. The one
corrupting case is checked and currently affects exactly one string.

---

## TRAPS — every one of these cost real time

**A measurement is about ONE thing, and the sentence you wrote it in may cover two.**
`pool.py` proved `13:$7589` is the only gate — for **staging**. That sentence was then
relied on for the **resume pointer**, which has a second writer (`13:$6CA8`, the `$EC`
path, running *after* `$7589`). 25 strings were byte-perfect in the pool, green on every
check, and drew a single Japanese glyph on screen; it took three sessions and cost the town
signs, the shrine menus and the Kuyo Pass road picker (2026-08-06). This is the same shape
as `regions.py` vs `codec.py`, the two dispatch tables, `codec.ARITY`, and the Fei's Quiz
tilemap row — **five instances now**. When a claim is load-bearing for something other than
what it was measured for, re-measure it for that thing.

**`$FF` in a real cartridge save is not proof a byte is free — and neither is a run of
`$00` at the end of a bank.** Both nearly sank the 6-character name (2026-08-03).
`$A74F` looked USED because Joey's `.srm` had `51 A4 EE DB` there; that is uninitialised
SRAM from a physical cart, and a save written by the ROM itself has `$FF`. `$A6FE` looked
FREE because every real save had `$FF` before each slot base; it is a live 128-byte block
that `15:$5AC1` mirrors to SRAM bank 0 and `15:$4E67` re-clears, so the record written
there came back with `$FF` in its first two bytes and the log list read `65535回目`. **Ask
what the ROM WRITES, not what a save happens to contain** — a fresh save from an unpatched
build settled both questions in one command. The same rule retires the "17 free bytes at
`15:$7F27`" and "52-byte hole at `4:$7F21`" in the old name brief: sparse `$00` inside a
bank's tail blob is data nobody has identified, not padding. Same family as `--use-filler`.

**Do not hand-transcribe a list of operand addresses.** The name brief's list of sites was
carefully researched and still had six errors in it — three `cp $4F` addresses off by one
or four, two summary offsets wrong by 2 (52→56 not 54, 86→92 not 90), and three
`ld hl,sp+n` sites missing. Every one was caught by asserting the opcode before writing, and
the two silent ones only by DERIVING the offsets from the decoded instruction stream instead
of copying them. `tools/name6.py` does both; keep that shape for the next patch this size.

**"It cannot be compressed" was really "it cannot be OBSERVED".** Village and story
dialogue was written to a raw 1.0x byte budget and hand-abbreviated until the English was
barely recoverable — because `dte_ok.tsv` had no entry for it. Nothing in `build.py`
excluded it; the SCANNER could not see it, since loop2 expands from WRAM and the ROM
address never reaches the expander. When a whole category of string is missing from an
observation-gated list, check whether the observer can physically see it before concluding
anything about the category.

**Budget errors show up as bad prose, not as build failures.** Every check was green while
the shipped dialogue read like a telegram. The only detector was Joey reading it. If a
translation needs contorting to fit, suspect the budget before rewording again.

**A reference the extractor DISCARDS is a landmine that arms itself later.** 240 real
`ld bc,$XXXX / call $028B` message-queue pushes in banks 4, 5, 6, 15 and 31 were dropped
by a bank-trust rule that only believed bank 0 and the string's own bank. Nothing ever
noticed, because bank 13 had never moved and every stale pointer still happened to be
right. The first bank-13 translation moved the death message and the game crashed to
`rst $38` on **every death**. Discarding a reference is only safe while its target stays
put -- which is the one thing a translation patch is guaranteed to change. Prefer PINNING
a string you cannot vouch for over dropping the reference; `extract.py` now does, 16 of
them.

**A crash and "a message that never closes" look identical to `msgdur.py`.** It measures
how long the window stays up, so a hung ROM reads as one enormous message. That is exactly
how this crash was first recorded here -- as seed 2 "diverging" into a 12,034-frame box. I
checked `LCDC & $80` and the screen and called it healthy; the CPU was spinning at $0038
and I never looked at PC. **Health-check the CPU, not just the screen** -- `crashscan.py`.

**One seed proves nothing.** Of twelve seeded walks only two reached the death that
crashed. `crashscan.py --seeds 12` is the sweep; a single green run is not evidence.

**An over-long line does not wrap. It silently LOSES TEXT.** Both composer paths. 21 cells
on `13:$40D8` drew `for 2 Points of da`; 22 cells on loop2 drew `Innkeeper: Are you`, lost
` OK?` and ate the next line's indent. The previous handoff asserted the opposite — "nothing
truncates" — and used it as an argument about VWF. Measured 2026-07-31 by over-running a
line in a throwaway build and photographing it. ~~**Nothing in the pipeline catches
this**~~ — `line_too_long` does, since 2026-07-31.

**A bank-0 immediate names an ADDRESS, not a BANK.** `extract.py` resolved each one against
every text bank and recorded it on all of them, so four operands were claimed by a bank-11
string and a bank-13 string at once. `build.py` writes an operand once, so the first bank to
move wins and the other gets a pointer into the winner's text. It stayed invisible for the
whole project because bank 13 had never moved — the first bank-13 translation exposed it.
When two candidates fit a pattern equally, the fix is to find what the ROM does with the
value (here: `0:$028B` pushes it into the queue bank 13's `$67D5` consumes), not to pick the
likelier-looking one.

**`dis.boundary_votes` proves an immediate is not inside a longer instruction. It does NOT
prove the bytes are code.** `0:$22BD` is a known data blob and scores a perfect **64/0**,
because a run of short data bytes decodes as a sequence of valid short instructions. The
votes are a necessary test, not a sufficient one.

**`msgdur.py` is only a controlled A/B while the SCRIPT is identical.** Its walk is seeded
random input, so English text changes a duration, the next press lands on a different game
state, and the whole run diverges. At seed 2 the sample build's walk got the player killed
and reported a 12,034-frame "message" that was the death box (`HP 0/20`, LCD on, game
healthy). Same script with `--no-hooks` is still exact; different script, read the durations
for health rather than equality. And `--no-hooks` can no longer carry the English that only
DTE makes fit, so that control ROM is not the same text.

**A pointer found by PATTERN is a candidate; only a decode makes it a reference.** The
extractor matched `01 xx xx` as `ld bc,$xxxx` anywhere it appeared, including inside the
operand of `0:$227B ld [$CF01],a`, whose bytes `01 CF 7E` name bank 30's item verb at
`$7ECF`. The inserter then rewrote that "reference" when DTE moved the verb one byte, and
`ld [$CF01],a` became `ld [$CE01],a` — the dungeon message-timing bug, and three sessions
of blaming DTE for it. `dis.boundary_votes()` settles it: LR35902 code self-synchronises,
so decoding from each of the preceding 64 bytes votes 63/1 for a real site and 0/64 for a
phantom.

**A bisect names the artefact, never the mechanism.** Three builds correctly showed the
DTE build was the broken one. Every hypothesis about WHY was then argued from what DTE
plausibly does — cell counts, wrapping, the runtime buffer — and each was wrong, one of
them at a cost of 12 points of compression yield. `cmp` the two ROMs bank by bank before
theorising: the answer was one byte, and it was in a bank the previous session had
explained away without looking.

**"Bank 0 differs only because of the checksum" was an assumption, not a measurement.**
It was true of every other build in the project and false of the one that mattered.

**"Cosmetic" is a claim about GLYPHS, and a renderer counts more than glyphs.** DTE
expanding untranslated Japanese changes CELL counts, and cell counts drive wrapping. This
was NOT the message-timing bug — that was the phantom reference above — but it is real:
the status bar's second row still stays hidden under `a:120` from `saves/dungeon.state`.
Before calling a rendering difference cosmetic, ask what the renderer DERIVES from it.

**A screenshot cannot see a duration, a rate, or an ordering — but an emulator can.**
Pixel comparison samples one frame, so `--compare` was green throughout this bug. The
answer is not "only a human can check it": find the state the effect lives in and measure
it over frames. For dungeon messages that state is **WY (`$FF4A`)** — the box is the
window layer and its height is the message's lifetime. `tools/msgdur.py`.

**A harness that "works" can still be driving nothing.** `gbrun.py --press` used pyboy's
one-frame default; the player visibly walked, so runs looked healthy while `--trace`
reported no copy site firing and `dte_emit` never appearing. Presses are now held for 5
frames. Corollary: when instrumentation reports ZERO, suspect the instrumentation before
concluding something about the game — "a scripted walk never triggers a dungeon message"
was recorded as a fact about the game for two sessions and was a fact about the button
schedule.


**A renderer's layout can be duplicated in ARITHMETIC elsewhere in the ROM.** The
name-entry picker hardcodes its grid's row stride as an immediate at `31:$41A0`, so
translating the grid — which dropped the rows' terminators and changed the stride from 19
to 18 — made it select the wrong character on four of its five rows for as long as the
English build has existed. Every byte-level check was green: the STRINGS were all correct,
and so was the base pointer, because that one is a normal reference. When a box's byte
layout changes, look for code that indexes it.

**`--compare` against a ROM you copied without its `.ram` compares two different games.**
`build.sh` writes `<rom>.gb.ram` from the battery save, and `cp build/shiren_en.gb
build/base_to_compare.gb` does not bring it. The baseline then boots with blank SRAM, the
title menu shows the three no-save-data entries instead of eight, and every screen after
that differs. It reads exactly like a render regression. **Copy the `.ram` with the ROM.**
This is the sharper form of the existing "health-check your baseline" trap.

**BSD `sed` has no `\|` alternation, so a recipe built on it silently does nothing.** The
TASK 1b brief shipped a `sed -i '' 's/^#31:\$\(446E\|4472\|...\)/.../'` one-liner to
uncomment ten rows. On macOS it matches nothing, exits 0, and the build then reports success
having ignored the edit entirely — the same failure mode as editing `menu_en.tsv` alone. Use
Python for anything with alternation, and always diff the file afterwards.

**"marked compressed" is printed BEFORE the allocator runs.** It means a box is ELIGIBLE,
not that it placed. A harness that scraped that line to decide whether a candidate wording
fit reported all nine candidates as passing, including the baseline that fails — the real
verdict is the `[bank_full]` problem list and the `N PROBLEM(S)` count. Parse the verdict,
not the intent.

**`boxpreview.py` does not expand DTE.** A box marked compressed renders in it as garbage
with the rows apparently sliding — which is precisely the cascade symptom you are looking
for, so it reads as a catastrophe. For a compressed box the tools that mean something are
`dte_rom.verify_box()` and a screenshot.

**`build.sh` reads `script/en.tsv`, not `script/menu_en.tsv`.** `menu_en.tsv` is the source
of truth and nothing copies it across. Editing only `menu_en.tsv` gives a build that
silently ignores every change you made and reports success -- there is no warning, because
as far as the pipeline is concerned you changed nothing. `cp script/menu_en.tsv
script/en.tsv` is part of the edit, not an afterthought.

**A byte scan for a call site sees the fall-through and misses the branch.** Scanning for
`ld a,<box id>` before a box far-call maps most boxes correctly and gets one wrong:
`4:$4CDC` is attributed to box 34 because `ld a,$22` immediately precedes it, when box 33
reaches the same instruction via a `jr` two instructions earlier. Both share one call site.
Check what jumps INTO a site before believing what sits above it.

**Resident code must not run to the LAST BYTE of bank 0.** `dte_box_hi` was exactly 20
bytes at `$3FEC-$3FFF`, so its `ret` sat on `$3FFF` -- and that `ret` did not return. White
screen, CPU spinning on `rst $38`. The identical bytes ran clean under `tools/gbemu.py`,
every build check was green, and moving the routine twelve bytes earlier -- changing
nothing else -- fixed it. The byte after `$3FFF` is `$4000`, which belongs to whichever
bank is mapped, and during an expansion that is the TABLE bank. `BOX_END` is `$3FFF`.

**"Cosmetic for the composer" is not "cosmetic for the box drawer".** Expanding a byte
that was not really a DTE code costs the composer one garbled line. It costs the DRAWER
every subsequent row of the box, because the drawer stops at a fixed cell count and leaves
the source pointer wherever it landed, and the next row continues from there. Two of this
session's three white screens were that cascade. Never assume a render path inherits
another's failure mode.

**A `<$XX>` raw escape is layout, not text.** `31:$41E9`'s `<$B6>` column divider was
inside the DTE code space, so the drawer expanded our OWN translation. `$B3-$B6` is now
reserved and `build.py` rejects any escape in the code space by name. The general rule:
a byte the renderer must reproduce exactly belongs in the same exclusion as control codes
and combining marks.

**Some of the text a renderer draws is not yours.** The file-select box draws the player's
saved name straight out of SRAM. No content check, no allowlist and no amount of
translating can make those bytes safe -- which is why box expansion is gated on a
descriptor bit rather than on anything about the string.

**pyboy hooks are not free instrumentation.** A hook on `$0038` makes the emulator
effectively hang once the ROM is spinning there, so the obvious "catch the crash" probe
never returns; and a hook on the last byte of a bank reported stale registers, which sent
this session chasing a `pop bc` that had in fact executed. Prefer bisecting by PATCHING a
variant ROM (`poke.py`-style: patch bytes, fix both checksums, `--compare`) -- that is what
actually located all three bugs.

**Do not trust `--compare` against a baseline you have not health-checked.** Two builds were
used as "known good" references this session and both turned out to crash a few hundred
frames later on a different screen. Check `LCDC & $80` and that the top sampled PC is not
`$0038` before believing a comparison.


**A verified routine is not a reached routine.** The DTE expander was proven against a
reference decoder on 5277 segments, every compressed string round-tripped, 1451 build checks
passed -- and the file menu still drew `New廿`, because bank 11's labels are copied by a raw
loop that never calls it. "The code is correct" and "the code runs" are separate claims with
separate evidence. Screenshot before believing a render change.

**`tools/dis.py` shadows the stdlib `dis`.** Any script in `tools/` that imports something
which imports `inspect` (e.g. pyboy -> pysdl2 -> inspect -> dis) dies with "module 'dis' has
no attribute COMPILER_FLAG_NAMES". `gbrun.py` drops its own directory from `sys.path` before
importing pyboy. Remember this before debugging a bizarre import error.

**"It appears in no table" is not "it is dead."** Bank 30's four "unreachable" verb entries
were to be reclaimed for the last 4 bytes. Index `$0A` really is absent from every category
table -- but so is index `$12` = `はずす`/"Doff", which must be reachable for equipped items,
because the substitution code at `30:$7D73`/`$7DA0` COMPUTES indices (`ld bc,$0004` /
`add hl,bc`). An enumeration over tables cannot see a computed index. Aliasing on that
evidence would have put the wrong verb on an item menu.

**Spend a shared resource where the constraint binds, not evenly.** The DTE table is one
fixed pair of pages, so which text its 128 codes serve is free. Training evenly left bank 30
four bytes short while bank 11 sat on slack. Weighting bank 30's own strings 64x in the
training set (`dte_rom.TRAIN_WEIGHT`) took it from 77 bytes to 59 for 1.5 points of prose
yield -- and that, not the dead-entry plan, is what closed the bank.

**Check the PREMISE of a blocker before rationing against it.** "Where does the 280-byte
table live?" was the DTE plan's central open question, and all three candidate answers were
ways to ration bank 0's ~150 bytes of padding. The premise -- that the table must be
resident because the expander dereferences it -- was false: the ROM's own far-call
trampoline recovers the caller's bank by reading `[$4000]`, because **byte 0 of every bank
holds that bank's own number**. Once the expander can do the same, the table can live in
bank 32 and be indexed by code rather than packed. The WRAM audit, the write-watch and the
64-pair fallback were all work that did not need doing.

**"140 codes are free" counted only English.** A DTE code must also avoid the combining
marks and be cheap to separate. The real figure is 128. Related: `codec.encode` is the
*Japanese* table and resolves `'F'` to the ROM's native `$B4`, not the Latin font's `$10` --
`build.encode_en`/`EN_CODES` is the one the inserter uses. Training a table with the wrong
one produces bytes the inserter never writes.

**`--use-filler` is dangerous and is OFF. Leave it off.** It reclaims runs of `$00` inside
banks as free space. Some of those runs are live data: bank 30 `$7F80`+ is sparse flag
data and `$7F12`-`$7F7F` is code. It produced a black file-select screen, freezes on
save-state load, and flicker on every message. The reference verification **cannot** catch
this — it proves strings resolve, not that you missed data.

**A rule derived from the ROM's own structure is not a heuristic and must never be traded
away to make a different filter behave.** `impossible()` (no `$F1`-`$FE` byte can be
script, since the dispatch table has 17 entries) was being waived for hand-specified
regions so that a *digit* filter would stop rejecting a real label — and those regions
were padded `0x100` on each side, extending the waiver past anything verified. Result:
**1,434 bytes of binary data extracted as "strings."** Bank 4 was 96% junk. Fixed this
session; banks 4 and 31 re-extracted, 0 impossible bytes remain.

**Never filter a diagnostic on volume when the thing you are hunting co-occurs with the
noise.** The render tracer suppressed any frame with >8 tilemap runs as "map redraw" — but
opening a menu also redraws the map, so the item action menu was discarded on every run.
Filter on **content** instead: terrain scores 0.25 on the text test, menu text scores 0.65.

**Mesen Lua: `emu.getState()` returns a FLAT table with dotted keys** — `st["cpu.pc"]`,
`st["cpu.d"]`. It is NOT nested; `st.cpu.pc` is a nil index that fires on every callback.
Track the ROM bank by watching MBC writes to `$2000-$3FFF` rather than reading state.
Register callbacks through `pcall` with a 2-argument fallback. **Copy from a script that
has actually run** (`tools/mesen_strread.lua`) rather than writing fresh against a
remembered API.

**~~Menu boxes are narrower than their Japanese suggests~~ — there is no ratio.** This trap
was a workaround for not knowing where the width came from. It is byte 3 of the descriptor:
read it, or edit it in `script/box_geometry.tsv`. Delete the ⅔ rule of thumb from your head.

**A pool's TOTAL free space does not mean a string fits.** Bank 31 had 534 bytes free, 20 to
spare, and still could not place a 35-byte box, because its descriptors sit between the text
blocks and the vacated runs never merge — largest run 26. `build.py` now distinguishes
"needs N more bytes" from "fragmentation, not shortfall" and names the run it ran out of.
When a bank reports plenty of room and still fails, read the second half of the message.

**Cells and bytes diverge, and which one binds depends on placement.** A dakuten costs a
byte and no cell. For a *relocated* row the limit is cells (the box width). For a *pinned*
row the limit is bytes CONSUMED, because the row after it has to keep starting where it did —
and since English has no dakuten, a Japanese row with more bytes than the box has cells
cannot be replaced in place at all (`31:$4567`: 20 bytes, 16 cells, 18-cell box).

**Stranding one unplaceable string instead of reverting its bank does not work.** It looks
strictly better and it cascades: withdrawing a unit's space from the pool costs about what
its translation saved, so bank 30 stranded all fifteen item verbs one at a time. Tried and
reverted 2026-07-29. The all-or-nothing rule stands.

**Translations are keyed on `loc` (`11:$5330`), never the sequential `id`.** ids are
assigned by sorted offset, so any change to extraction renumbers everything and silently
shifts a whole translation file by one entry. `build.py` rejects numeric keys outright.

**`tile = code + 16` applies to glyph DATA only** (`$7680 + code*8`). Tilemap entries store
the raw code, and the status bar uses a different tileset entirely (base `$1000`).

**Sequential labels must be PADDED, never terminated early** — an early terminator strands
the tail of the original as a phantom entry (this produced a stray `t` on screen).

**Bank allocation is all-or-nothing.** A partial relocation leaves some strings moved and
others at their old addresses, overlapping. A bank that cannot fit reverts entirely to
Japanese: untranslated is correct, half-relocated is corrupt.

**Trace the ENGLISH build, not `base.gb`, when debugging insertion.** Several traces on the
original showed everything correct because the bytes were still Japanese. (For a *survey*
of how the game works, base.gb is the honest source.)

**Watch data, not code, when the code's location is the unknown.** Hooking guessed entry
points failed twice; a read-watch on the string bytes found the village-dialogue reader
immediately. If a watch comes back empty, suspect the filter before concluding the thing
does not exist.

---

## Tools

| Tool | Purpose |
|---|---|
| `build.sh` | full pipeline: base → MBC3 → 1 MiB → font + script → verified ROM |
| `tools/codec.py` | **canonical** encoding table; everything imports from here |
| `tools/extract.py` | script extraction, round-trip verified |
| `tools/coverage.py` | **is what we extracted ALL there is?** Walks every bank for `$FF`-runs of pure script bytes that no extracted string covers, classifies them (dialogue / other / truncated), and fails the build on unextracted dialogue. In `build.sh`. The 7.9 KB gap of session 7 survived five sessions because no tool could produce this number |
| `tools/regions.py` | what each part of the ROM *is*. `script_regions` is the extractor's only bulk discovery rule — **its table is imported from `codec`, and restating it there is what caused session 7** |
| `tools/build.py` | insertion, repointing, verification, checksums |
| `tools/dte.py` | DTE / byte-pair compression, plain and recursive |
| `tools/dte_rom.py` | **the ROM side of DTE**: expander, table bank, hooks, `verify()` |
| `tools/gbasm.py` | assembler, opcode table inverted from `dis.py`'s; `--selftest` |
| `tools/gbemu.py` | ~30-opcode interpreter for testing patches; raises on the unimplemented |
| `tools/dte_measure.py` | yield measurement against the SNES English corpus |
| `tools/dte_project.py` | per-bank projection and break-even ratios |
| `tools/boxpreview.py` | **renders a menu box out of a built ROM** by replaying `31:$40D8`; `--screen` for a 20x18 grid. **Does NOT expand DTE** — a compressed box looks broken in it |
| `tools/boxscan.py` | **reaches a screen no button script reaches**, by forcing bank 4's menu dispatcher index, and dte-scans the box it draws |
| `tools/gridprobe.py` | checks the name-entry picker reads the character it displays, row by row, on both pages |
| `tools/namerun.py` | **types a name on the name-entry screen** and dumps every buffer it lands in (`$C6E2` width/cursor, `$C6E3`, `$CF81`, `$D100`). Drives the picker by writing `$C6F5`/`$C6F0`/`$C6F4` rather than counting d-pad presses, which types the wrong letter. `--name Shiren` on the shipped ROM types `Shin` — the 4-character bug |
| `tools/crashscan.py` | headless halt detector: `rst $38`, VRAM execution, stuck loops; `--stack` dumps return addresses |
| `tools/mesen_crashwatch.lua` | the same thing **inside Mesen**, for confirming on a real session. Samples at end-of-frame; do NOT breakpoint $0038 |
| `tools/mesen_rendertrace.lua` | **which renderer draws which screen** (v4, content-filtered) |
| `tools/decodetrace.py` | decodes a rendertrace log into readable text |
| `tools/findtables.py` | pointer-table scanner (cross-bank, longest-run) |
| `tools/latinfont.py` | 8x8 Latin font written over the freed kana tiles |
| `tools/bartext.py` | renders text across a tile strip (status-bar labels) |
| `tools/dis.py` | LR35902 disassembler. `dis.py <rom> <cpu-addr> <count> --bank N`, or a raw file offset with no `--bank` |
| `tools/setmapper.py`, `tools/expand.py` | MBC3 conversion, ROM expansion |
| `tools/helpshot.py` | **the help/tutorial screen**, which no walk seed reaches: forces index 4 of bank 4's dispatcher and snapshots the render buffer at `4:$49BF`. `--topic N`; `--unit` is 0 for every topic in table `13:$554A` |
| `tools/msgshot.py` | **any bank-11/14 MESSAGE on the real screen**, which is the other half of the same problem: `msgshot.py <rom> saves/sign.state 14:'$4638'` substitutes the queued pointer at `13:$67ED` and lets the game's own renderer draw it. Set `hl` as well as `$CF7F`/`$CF80` — `13:$6C73` reads the register, which is exactly the asymmetry that hid the `<cEC>` bug. Tag: bank 14 `xor $C0` on the high byte, bank 11 `set 6,h` |
| `saves/sign.state` | a NEW LOG parked facing the village-entrance sign — one square from where a new game starts, and the only cheap route to a signboard (four 20,000-frame seeded walks never reached one). Built by `mkstate.py`, which boots a BLANK cart for it because the route is "New Log" |
| `tools/reloc_verify.py` | runs every relocatable trampoline in the BUILT ROM against the loop it replaced. `--verbose` reports the render-mode units and how many strings it skipped as translated |
| `tools/mesen_*.lua` | other Mesen traces; see the header comment in each |

**`mgbdis` and `rgbds` are installed** (`../mgbdis`, one directory up from this repo) and
are **available if a job needs a full bank listing** — nothing in the pipeline depends on
them, and no work so far has required them. `tools/dis.py` disassembles a range in place
(`dis.py <rom> <cpu-addr> <count> --bank N`) and has been enough for every routine this
project has had to read, including the whole bank-13 help renderer. Reach for mgbdis when
you want to *read a bank as a document* rather than answer a question about one address —
tracing an unfamiliar control-flow graph, or auditing a bank for a pattern. Note it emits
RGBDS source for the ORIGINAL 512 KiB ROM: the build pipeline is byte-patching, not
reassembly, so a listing is a reading aid and never an input to `build.sh`.

Translation files: `script/menu_en.tsv` (source of truth, keyed on `loc`),
`script/box_geometry.tsv` (menu box x / y / width, keyed on box id),
`script/raw_patches.tsv` (bytes inside composites), `script/tile_patches.tsv` (graphics
labels). `script/en.tsv` is a copy of `menu_en.tsv` — `build.sh` reads that one.

---

## ~~OPEN BUG~~ — dungeon messages expire too fast to read — **FIXED 2026-07-30**

> **It was never DTE.** The inserter rewrote a phantom `ld bc,$7ECF` that lives inside
> `0:$227B ld [$CF01],a`, so the English build wrote `ld [$CE01],a` and the message system
> lost its hold counter. One byte, in bank 0 — the bank an earlier session dismissed as
> "differs only because of the checksum" without diffing it. `extract.py` now proves an
> immediate is a real instruction start before recording it, and `build.py` re-checks
> before writing through it. **Full record: `docs/archive/HANDOFF_BUG.md`.**
>
> Confirmed with `tools/msgdur.py`, which measures message LIFETIMES headlessly (the box
> is the window layer; its height is WY at `$FF4A`): all three builds — full, `--no-dte`
> and `--no-hooks` — now show identical durations at identical frames.
>
> **The composer hooks are exonerated and stay in.** `shiren_nodte.gb` and
> `shiren_nohook.gb` are behaviourally identical, so the hooked composer matches the
> untouched one exactly.
>
> The narrowing of the code space (124 -> 46 codes) is kept for now, but it was a fix for
> this bug and this bug had another cause — the 12 points of yield may be recoverable, and
> `msgdur.py` is how to decide. The rest of this section is the original (wrong) diagnosis,
> kept because the measurements in it are still good.

The wrong diagnosis that used to fill this section is in `docs/archive/HANDOFF_BUG.md`, under "How
the diagnosis went wrong" — worth reading once, because the reasoning was careful and
still wrong three times running.

**What survives from it, and is still true:**

* The narrowed code space `$92-$99 $B8-$C1 $C4-$DF` (46 codes, 28.2% against 124/40.2%),
  enforced by a build check that fails naming any untranslated string containing a code
  byte. Bank 30 needs 58 of 73, bank 31 needs 389 of 534. **Its justification is gone**
  — it was a fix for this bug — so widening it back is now a legitimate, measured
  experiment worth up to 12 points of yield. Rules: `tools/dte_ranges.py` recomputes what
  is safe; taking more codes means MERGING ranges, never adding a fourth (the expander's
  range test is 158 bytes and bank 0's padding is exactly 158); relaxing the ranges means
  relaxing the build check with them; and `tools/msgdur.py` against `shiren_nohook.gb` is
  the verdict.
* Expanding untranslated Japanese does change cell counts, and the status bar's second row
  still stays hidden under `a:120` from `saves/dungeon.state`. Real, small, and not this
  bug.
* `tools/msgtime.py` and `tools/findtimer.py` record two dead ends: tile occupancy cannot
  see a message (dungeon terrain fills all 18 rows of `tilemap_background`), and a WRAM
  scan for a decrementing counter finds only animation timers. The thing that DOES work is
  WY — see `tools/msgdur.py`.

## Open / unverified

- **Screenshots owed** for the widened item action menu over a real item list, and for the
  in-game submenus that share box 0 (Trap/Stair, Close/Exit, Down/Up, Go/Stay/Step,
  Rank/Pass) — box 0 went from 5 to 7 cells and they all widened together.
- **The cursor step is unresolved.** `4:$4F2B` computes `[$C6A5]*64` = two tilemap rows per
  selection, but the difficulty menu shows one row. Patching the cursor HOME does not depend
  on it, so box moves are fine; do not build on the step.
- **Box 2 is pinned by a false positive** — `0:$22BD` is a data blob, not code. Costs nothing
  today; unpin if it needs to grow.
- **SRAM name field width** — is `$D100+4..6` really free?
- **Bank 0 resident space is EXHAUSTED, and so is bank 13**: the `$0062` padding is full
  (158/158) and the tail holds 17 of 19 usable bytes. The RST gaps (`$002A-$002F`,
  `$0032-$0037`, `$003A-$003F`, 18 bytes in three runs) are the only untouched reserve, and
  they were never verified beyond "the vector's `jr self` stays put". **Bank 13 — where the
  composer lives — has zero free bytes**, not one `$FF` run of 8. VWF therefore needs a high
  bank plus a trampoline, not a hole; see `docs/archive/HANDOFF_VWF.md`. Do not ration the RST gaps
  before checking that premise.
- **The status-bar timing difference** under `a:120` from `saves/dungeon.state`. Believed to
  be Japanese expansion changing message wrapping; it resolves on the next button press.
  This is now MEASURABLE rather than eyeballed — `tools/msgdur.py` against
  `build/shiren_nohook.gb` — and settling it is part of the "re-widen the code space"
  experiment.
- The `$EB` skip-chain at `13:$441B` advances two bytes but `$EB`'s handler reads no argument.
  The codec follows the handler (0 args). Confirm before the inserter depends on it.
- Graphics localisation (title, credits) untouched. Bank 0 `$3ABD` is an RLE-style
  decompressor that likely covers it.

## If picking this up cold

1. `python3 tools/extract.py build/base.gb` then `sh build.sh` — expect **1498 checks, ALL
   OK**, **no problems**, and the lines `message-queue pushes: 240 ...` and `pinned 16
   bank-13 string(s)`. Extraction prints the three phantom `ld r16` references it
   drops; that is correct and expected.
2. `python3 tools/dte_rom.py` — expect 5278 segments / 0 mismatches from `verify`, and from
   `verify_box` 120 unmarked row draws identical, 118 marked, 2391 English rows, 0 failures.
2a. `python3 tools/dialogue_preview.py --selftest` — expect **1608 lines, longest 18, 230 on
   the boundary, 2 known exceptions**. It re-validates the composer layout model against the
   Japanese, so a wrong edit to it shows up here rather than as text lost on screen.
   `--check` then lints every translated string.
2b. `python3 tools/crashscan.py build/shiren_en.gb --seeds 12` — expect **0 halts**. This is
   the CPU health check, and it is the one no other tool in the project performs; a crash
   reads to `msgdur.py` as a message that never closes and to `--compare` as nothing at all.
3. The duration check, **and note that its control has to be rebuilt from the CURRENT
   script** — `build.sh` does not make one, and a stale `shiren_nohook.gb` compares two
   different games:

   ```
   python3 tools/setmapper.py build/base.gb build/_m.gb --type 13
   python3 tools/expand.py    build/_m.gb  build/_e.gb --size-code 5
   python3 tools/build.py     build/_e.gb  script/en.tsv build/shiren_nohook.gb \
           --no-dte --no-hooks          # bank 13 and 30 revert: correct, DTE is what fits them
   rm -f build/_m.gb build/_e.gb ; cp saves/shiren_en.srm build/shiren_nohook.gb.ram
   python3 tools/msgdur.py build/shiren_en.gb build/shiren_nohook.gb
   ```

   With bank 13 translated the control reverts bank 13 to Japanese, so it is a DIFFERENT
   SCRIPT and the seeded walk diverges — currently 9 boxes to 10, median 202 to 193. That
   is expected. What you are checking is HEALTH: no message collapsing toward the ~17-frame
   symptom of the old timing bug. For an exact A/B, see TASK 2's msgdur note.
4. Read **TASK 2** for what the dialogue sample settled — over-long lines truncate, `<var>`
   is the real cell budget, VWF is cancelled — then `FINDINGS.md` -> "DTE" and "Menu boxes
   are a TABLE".
5. Before believing any render change, `--compare` against a baseline you have
   health-checked — and copy its `.ram` with it.

## PROJECT ORDER — the four goals, and where they stand

Agreed 2026-07-31. **Goal 1 was closed 2026-08-03** — see
`docs/archive/HANDOFF_SPACE.md`. Re-ordered
below on that basis.

| goal | state | the gate |
|---|---|---|
| **1. Headroom for bulk translation** | **DONE** — every arena fits at the ratio-independent floor | — |
| **2. Translation tooling and rules** | rules written (`TRANSLATING.md`); export/lint NOT built | `script.tsv` reports `bytes` for all 1,419 strings; it is the wrong number for **902** of them |
| **3. Insertion verified end to end** | strong: 2,211 checks, 12-seed sweeps, `--redirect-all`, help screen photographed | no coverage report of which strings have been SEEN |
| **4. Graphics** | untouched | needs its own discovery phase |

**The session-by-session plan now lives in `HANDOFF_NEXT.md`.** Summary:

1. ~~**Dialogue preview + build check**~~ (goal 1) — **DONE 2026-07-31**, see TASK 1a.
2. ~~**Relocatable redirect**~~ (goal 1) — **DONE 2026-08-03**,
   `docs/archive/HANDOFF_SPACE.md`.
3. ~~**Translation lint**~~ (goal 2) — **DONE 2026-08-03**. `tools/lint_en.py` checks
   control-token parity, which is the one failure with no other detector; `build.py` fails
   the string rather than shipping it. The *export* half was dropped: there is no human
   translator, so Claude translates in-session and no export format is needed.
4. **Player name 4 → 6** (`shiren-gb-name-length`) — small, unblocked, and it settles half
   the `<var>` budget every combat line is written against, so it goes before prose.
5. **The glossary: 388 item/monster/place names**, translated once and frozen. Terminology
   drift is the failure review cannot catch.
6. **Bulk translation** (goals 2/3) — bank 13 system/help first, then village prose.
7. **Graphics** (goal 4) last. Independent; can run alongside translation.

**Demoted: job 1b, DTE for dialogue (`docs/archive/HANDOFF_1B.md`).** It was queued as a blocker. It is
not one any more — it compresses in-place dialogue, which now lands in the redirect pool,
and the pool has 458 KiB spare against a ~32 KiB script. It is a pure optimisation. Its
finding still stands and is still worth reading: the mechanism works, the missing piece is
COVERAGE (reaching 301 strings so a trace can see them), which is a content problem, not an
engineering one.

### What a translator is actually constrained by now — measured 2026-08-03

| class | strings | the limit |
|---|---|---|
| redirected (relocatable + in-place) | **952** | **no byte budget** — cells only: 18 per line, and lines TRUNCATE |
| still bank-local | **311** | its slot in the bank, *and* cells |

The 311 are: bank 11 172 (mostly `11:$52E0`, the menu labels whose reader is the seven
bytes DTE already owns), bank 31 59 (menu boxes), bank 13 37, bank 14 21, bank 30 21
(item verbs), bank 4 1. Every one of those banks still projects positive, so this is a
lint-accuracy problem, not a space one.

Regenerate the counts with the `reloc_can` rule in `build.py` — do not copy this table
forward, derive it.

## ~~NEXT SESSION: the dialogue preview + build check~~ — DONE 2026-07-31

**Kept as the brief it was written from; every item below is implemented. See TASK 1a.**

A dialogue line over 18 cells does not wrap, it silently LOSES TEXT — on both composer
paths, measured on screen 2026-07-31. `boxpreview.py` covers menus; dialogue has no
equivalent, so this is the one correctness hole in an otherwise strong verification stack.

What it has to do:

* Run a message through the composer's REAL rules: 18 cells, `<br>` / `<brk>` / `<end>`,
  three lines to a box, the `~54-byte $CF07` buffer ceiling, and `cells()`' rule that control
  codes and their arguments cost nothing.
* **FAIL the build** the way `box_too_wide` does, not print a warning. A budget error shows
  up as bad prose, never as a build failure — that is exactly how the telegraphese shipped.
* Print the wrapped result so a translator can see the box they wrote.

`tools/dialogue_fit.py` already has the layout engine; this is mostly wiring it into
`build.py` and adding the problem kind. `<var>` width is the one thing not computable from
the translation — see the caps in `TRANSLATING.md` §4, and TASK 3 (name 4 -> 6) is what makes
the player-name half of it true.

## The work queue, shortest useful order

| | task | size | why now |
|---|---|---|---|
| ~~1~~ | ~~TASK 4 spike~~ **DONE 2026-07-31** — `tools/pool.py`, on screen, in `build.sh` | — | The budget is aggregate now: 32,256 bytes of pool against 15,788 of Japanese |
| ~~1a~~ | ~~The dialogue preview tool~~ **DONE 2026-07-31** — `tools/dialogue_preview.py`, wired into `build.py` | — | It found 5 over-long lines in the shipped innkeeper speech immediately |
| **1b** | **Make dialogue compressible** — **see `docs/archive/HANDOFF_1B.md`**, which corrects this line: it is **301** strings across banks 11 *and* 14, the hook already works, and the blocker is REACHING endgame story dialogue | a day | The pool runs 81% full without it, 61% with |
| **1c** | **Deduplicate identical translated strings** — `for <cE4> damage!` is stored twice; bank 6 pushes one message from 12 sites | half a day | Pure win, no ROM code, and bank 13 is 9 bytes from full |
| **1d** | Bank 13's allocator — exact-fit search. Randomised restarts were tried and do NOT help | half a day | Only after 1b/1c; they may make it moot |
| 2 | Item and monster NAMES, capped at 7-8 cells | ongoing | Every combat line is mostly `<var>` today, so names buy more readable text per byte than dialogue does |
| 2b | **End the space problem** — `docs/archive/HANDOFF_SPACE.md`. Pool 5-byte record, then the relocatable redirect | 2-3 days | The projection says −5,850 bytes; **do this before bulk translation** |
| 3 | Bulk translation of dialogue | ongoing | **Unblocked, and no longer gated on anything.** Write natural English; overruns are redirected, and an over-long LINE now fails the build |
| ~~4~~ | ~~TASK 3 — player name 4 -> 6 characters~~ **DONE 2026-08-03** — `tools/name6.py` | — | It was a day, not half: the caps were the easy part and the SRAM save record was the task |
| 5 | Re-widen the DTE code space, measured with `msgdur.py` | half a day | Worth 1.24x -> 1.09x, but only 58 of 128 codes are safe until the Japanese using them is gone. Necessary, not sufficient |
| — | Screenshots owed (item action menu over a real list, box 0's submenus) | small | Debt from TASK 1 |
| — | ~~TASK 2b — VWF~~ | — | **Cancelled 2026-07-31 on the sample's evidence** |
