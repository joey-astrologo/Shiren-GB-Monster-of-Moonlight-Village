# TASK 2b — VWF for the composer — **LANDED 2026-08-03**

> **Archived:** completed implementation record. See the repository
> [README](../../README.md) and [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

> ## It is on screen. `tools/vwf.py`, `--no-vwf` is the bisect control.
>
> **A composer line holds 24 characters instead of 18**, in the same 18 tiles, at a
> uniform 6px pen. Photographed on real English: `build/vwfshots/pool_dungeon_s1_009.png`
> against `build/vwfshots_base/pool_dungeon_s1_009.png`, the innkeeper's *"Ah, you woke up
> at last! You were crying"* drawn both ways from the same save and the same frame.
>
> **Message timing did not move, and that was the last honest risk on the list.**
> `msgdur.py` reports **17 boxes, total 3382 frames, median 189, min 17, max 628 — the same
> four numbers on the VWF build and on `--no-vwf`**, on the remade `saves/dungeon.state`
> whose seeded walk reaches real combat.** The typewriter counts characters, not
> pixels, so it was always going to be safe; now it is measured rather than hoped.
>
> **Nothing outside the composer moved.** The status screen and the whole title → file
> menu sequence are **pixel-IDENTICAL** against a `--no-vwf` control built from the same
> script, so the 6px pen reaches the composer and only the composer.
>
> Battery green: `build.sh` no problems / every arena fits, `lint_en` 0, `dialogue_preview
> --check` 0 at **24**, `--selftest` still validates the Japanese model at 18, crashscan
> **12/12 from both states** and 6/6 on `--redirect-all` and `--shuffle`, `pool --selftest`
> 8, `reloc_verify` 0 mismatches, `vwf --selftest` 48, `name6`/`rank6` selftests pass,
> `gridprobe` 0 wrong on every row and the page-2 alias, and `namerun` still round-trips
> `Shiren` to SRAM `$A702` and back.
>
> **What it does NOT cover, so nobody plans around a promise:**
>
> * **The ITEM DESCRIPTION screen is a different renderer** and stays fixed width.
>   Measured: `helpshot.py --topic N` is byte-for-byte and pixel-for-pixel identical on
>   both builds, because `4:$49A7` far-calls `13:$7E49`, which composes into `$C616` and is
>   drawn on the tilemap — it never reaches `13:$43B8`. 122 entries are affected.
>   (`helpshot.py`'s "help/tutorial" label is wrong: every entry in `13:$554A` is an item
>   name in dashes plus two or three lines of what the item does.)
> * **Menus are tilemap-drawn** and were never in scope (`31:$40D8`, one code per cell).
> * **The dakuten overlay row is now wrong for JAPANESE lines over 18 characters.**
>   `13:$44ED` walks 18 source characters to decide where `$DE`/`$DF` go, and cell position
>   no longer tracks character position. English has no dakuten and untranslated Japanese
>   renders as Latin garbage either way, so this is recorded, not fixed.
> * `Blade of Kamaitachi` is 19 characters against a 14-cell `NAME_CAP`. VWF made a handful
>   of the longest names possible, not all of them.
>
> **The caps were re-decreed:** `NAME_CAP` 8 → **14**, `ITEM_CAP` 10 → **16**, `PLAYER_NAME`
> stays 6. That is the old decree translated into the new geometry — the same share of a
> line, plus the six characters VWF found — and deliberately not a measurement. Session 3
> (the glossary) is written against those.
>
> The design, the trace that settled the plumbing, and the patch table are below and still
> current. What changed from the plan: nothing. It went in as written.

---

# The brief, as it stood when the work started — **REOPENED 2026-08-03**

> ## Why it is back
>
> **Joey, 2026-08-03:** *"I don't want abbreviations though. Isn't this a reason to work on
> VWF?"* — and he is right. Of the four reasons this was cancelled on 2026-07-31, **two are
> now dead and a third is the cost he has just declined to pay.**
>
> | cancellation reason | status 2026-08-03 |
> |---|---|
> | 1. Fixed width reads fine | **still true.** Photographed. VWF is a quality gain, not a rescue |
> | 2. *"The tightest constraint is BYTES, and VWF buys no bytes"* | **DEAD.** The space problem closed 2026-08-03 (`HANDOFF_SPACE.md`). Bytes are not a constraint anywhere. **Cells are the only limit left, and cells are exactly what VWF buys** |
> | 3. *"a 7-8 cell name cap fixes it free"* | **that "free" is paid in abbreviations**, which is the thing being refused. Joey said so on 2026-07-28 too and this file already recorded it |
> | 4. VWF can move message TIMING | **still true.** The real remaining risk — `msgdur.py` is a weaker control now |
>
> **And the engineering blocker is dead as well.** This file says: *"THE BLOCKER, measured
> 2026-07-30: there is nowhere to put the code... bank 13, the composer's own bank, has
> ZERO free bytes, not one `$FF` run of 8."* That was true then. It is not now — redirecting
> bank 13's strings frees its arena:
>
> ```
> normal build     bank 13  +83 spare,   largest free run  37 bytes
> --redirect-all   bank 13  +4291 spare, largest free run 588 bytes at $58B8
> ```
>
> **588 contiguous bytes in the composer's own bank, and the font is already there at
> `13:$7680`.** Code, font and width table can sit together, beside what they patch. No far
> call, no high bank, no trampoline.

## What VWF actually buys — MEASURED 2026-08-03, not estimated

The shipped Latin font is drawn **5px wide inside an 8px cell** (`tools/latinfont.py`;
'M' inks columns 0-4, 'i' inks 1-3). So this is not the usual proportional-font gain of a
few percent on narrow letters — it is a near-uniform **8px → 6px advance**, mean 5.73px.

```
a composer line is 18 cells = 144 px
   fixed width   18 characters
   VWF           25 characters
```

The `<var>` name slot is *line capacity minus the line's own words*, so:

```
line text          fixed: name gets    VWF: name gets
' attacked!'            8 chars            15 chars
' was defeated'         5 chars            12 chars
' dodged the blow'      2 chars            10 chars
```

Against `<var> attacked!`, on 16 realistic Shiren names — **fixed-width: 2 of 16 fit.
VWF: 14 of 16.** `Dragon Killer`, `Skeleton Warrior`, `Sure-Hit Sword`, `Confusion Grass`
and `Minotaur Axe` all go from impossible to comfortable.

**What VWF still does NOT fix, so nobody plans around a promise:**

* `Preservation Pot` (91px) and `Blade of Kamaitachi` (105px) overflow an 88px slot even
  with VWF. A handful of the longest names still need rewording — but a handful, not 34.
* **Menus are not VWF-able.** `31:$40D8` writes tilemap entries, one code per cell. Item
  names in the inventory list stay fixed width — that box gives ~16 cells, which is roomier
  than the combat line, so this is survivable. Confirmed in the survey below.
* Message timing. Reason 4 above.
* The `$CF07` line buffer is 49 bytes and does **not** grow with VWF. At 25 characters a
  line that is not a conflict, but the pixel budget and the buffer bound are two different
  limits and both have to be enforced.

## Order — this decides WHEN, and it is urgent

This file already said it, and it is the reason the question had to be answered now rather
than later:

> **Whichever way it goes, decide BEFORE bulk translation.** The translator picks the line
> breaks (`$EF` `<br>` is in the data), so text laid out for an 18-cell fixed line gets
> re-broken if VWF lands later.

VWF also resets the name caps, which the glossary is written against. So the order is
**VWF → glossary → prose**, and `HANDOFF_NEXT.md` has been updated to match.

## Status

**The plumbing question is SETTLED — 2026-08-03, by trace, not by reading.** The survey
further down still stands (the two loops in full, the DTE cell-accounting collision); the
"what has NOT been mapped" section at the end is now answered and is kept only for the
record. What follows is the answer, the geometry it implies, and the design that comes out
of it.

## SETTLED: `$C006` is a VRAM transfer queue, and both readings were right

`13:$43B8` and `13:$4484` write **the same buffer with different payload types**, because
`$C006` is not a tilemap row and not a tile buffer — it is a queue of VRAM transfers, each

```
dw   destination            ; a VRAM address
db   payload[n]             ; the bytes to put there
```

consumed by a stack-pointer blitter in bank 0 (`ld sp,$C006` / `pop hl` = destination /
`pop de` × n / `ld [hl+],a` ×2). There are two consumers and they disagree about `n`, which
is the whole reason the two readings looked irreconcilable:

| consumer | slot stride | payload | slots seen |
|---|---|---|---|
| `0:$10A0` | **22** (`dw` + 20) | a **tilemap row**, 20 entries | `$C006 $C01C $C032 $C048 $C05E` … |
| `0:$11C5` | **66** (`dw` + 64) | **tile data**, 4 tiles | `$C006 $C048 $C08A` |

`3 × 22 = 66`, so the two views agree on the boundaries at `$C006`, `$C048` and `$C08A`.
`$C0CC` has no reference anywhere in the ROM, so three 66-byte slots is the whole of it —
**192 bytes, 12 tiles**, and that is the constraint that shapes everything below.

### The geometry that falls out — measured

* A message line owns **18 consecutive VRAM tiles**. `13:$4523` writes the tilemap row as
  18 *incrementing* tile indices (`ld [hl+],a / inc a`, `ld b,$12`), so the tilemap does
  nothing but count.
* The three lines' tile bases are the table at `13:$4412`: **`$8A80`, `$8BA0`, `$8CC0`**,
  picked by `[$CF06] & 3`. They are `$120` apart = exactly 18 tiles. No slack between them.
* **A line is drawn in TWO HALVES of 9 tiles**, because 18 tiles is 288 bytes and the queue
  holds 192. `13:$43B8` renders 9 glyphs into the three slots (4 + 4 + 1) and
  `13:$43E2` adds **`$90` = 9 tiles** to the destination when `([$CF06] >> 4) & 3 == 1`.
* The caller state machine is `13:$4310`, on `([$CF06] & $30) >> 4`:
  `2` → `ld hl,$CF07` + `call $43B8` (first half) → `1` → `call $439F` + `call $43B8`
  (second half) → `0` → `call $4484` (the tilemap row). `13:$439F` is *"advance `hl` past 9
  characters"*, and `13:$6BE2` is its twin on the other caller path.
* `13:$43B8` is the **single choke point**: its five callers are `13:$4328 $433A $524B
  $6A97 $6AA3`, and `13:$4464` (the blitter) has no other caller. Patch `$43B8` and every
  path that draws composed text gets VWF.

Trace evidence, from `saves/town.state` walking into the first villager:

```
f163  13:$43B8 CF06=A0  blits c=4A,65,48,9A,1D,2C,2D,36,29 to de=C008,C018,C028,C038,
                                                                C04A,C05A,C06A,C07A,C08C
      13:$43F5 dest1=$8A80        0:$11C5 copy dests=8A80 8AC0 8B00
f164  13:$43B8 CF06=90  blits c=32,15,7B,38,B2,9B,00,00,00
      13:$43F5 dest1=$8B10        0:$11C5 copy dests=8B10 8B50 8B90
```

`$8A80 + $90 = $8B10`; `de` steps `$10` inside a slot and `$12` across a slot boundary,
which is the 2-byte destination field being skipped. `1D 2C 2D 36 29 32` is `Shiren`.

## What that means for VWF — the design, and why it is uniform 6px

**The tilemap side needs no change at all.** A line owns 18 tiles whatever is drawn in
them, and the row is 18 counting indices. VWF only changes *which pixels land in those 18
tiles*, so the entire `13:$4484` / `$44ED` / `$4523` path is untouched. That was the risk
the unreconciled reading was hiding, and it is not there.

**Take a uniform 6px advance rather than a per-glyph width table.** The gain is 24
characters a line against a true-proportional 25 — one character — and it buys back three
things that a pixel budget would cost:

1. **`72` is divisible by both `6` and `8`.** The half-line boundary therefore lands on a
   glyph boundary *and* a tile boundary, so the second half needs no pen carried into it
   and `13:$439F` / `13:$6BE2` stay a plain character skip (`ld b,$09` → `$0C`).
2. **The cell budget stays a character count**, so `13:$40D6 ld b,$12` → `ld b,$18` is the
   whole of loop 1's change and **`dte_emit` needs no change whatever**. The DTE collision
   described further down — "if `b` becomes a pixel budget the expander has to charge
   pixels too" — is closed rather than solved.
3. The `$CF38` buffer bound still holds: 24 characters against 49 bytes.

**The cost is that the font has to actually be 5px, and today it is not everywhere.** Ink
extents of every code the English page uses, measured out of `build/shiren_en.gb`:

| codes | glyphs | inked columns | conforms? |
|---|---|---|---|
| `$0B-$42` | `A-Z a-z . , ' -` | 0..4 (or narrower, left-aligned) | **yes** — `latinfont.py` drew them |
| `$01-$0A` | digits `0-9` | **1..6** | **no** — ROM-native, 6px wide and right-shifted |
| `$7C $AF` | `+ ~` | **0..6 / 0..7** | **no** |
| `$7E $7F $80 $9E $9F $A0 $B0 $B2` | `[ ] ? ( ) : / !` | 1..6 / 3..4 / … | **no** — centred in an 8px cell |

So `latinfont.py` has to draw the digits and the punctuation too, left-aligned in ≤5
columns, exactly as it already draws the letters. That is a data change in the `G` dict,
not code. **It is also a visible change outside the composer**: digits are drawn on the
tilemap paths (`HP 15/ 15`, `BELLY 100/100`, menu numbers) and will sit left-of-centre in
their cells there. Joey should see that before it is called done.

### The patch sites, all inside bank 13

| site | now | becomes | why |
|---|---|---|---|
| `13:$40D6` | `ld b,$12` | `ld b,$18` | loop 1's budget, 18 → 24 characters |
| `13:$43A3` | `ld b,$09` | `ld b,$0C` | `$439F`'s half-skip, 9 → 12 characters |
| `13:$6BE6` | `ld b,$09` | `ld b,$0C` | the twin half-skip on the other caller path |
| `13:$43B8` | 9 × `call $4418` | a VWF renderer | 12 glyphs → 9 tiles, pen 0,6,4,2,… |
| `13:$4523`, `13:$44ED` | `ld b,$12` | **unchanged** | these count TILES, and a line still owns 18 |

The renderer is the only real code. It has to write the 2-byte destination gaps at `$C048`
and `$C08A` correctly — a glyph straddles tile 3→4 and tile 7→8, which is where those gaps
fall — so build the nine tiles in a 1bpp staging buffer first and expand with the gaps in a
second pass, rather than merging in place across a discontinuity.

**Where the code goes:** bank 13's own arena, which is only free once bank 13's strings are
redirected (`+83` bytes and a 37-byte largest run in a normal build today; `+4291` and a
588-byte run at `$58B8` with `--redirect-all`). That is a `build.py` ordering question, not
a space question — the endgame projection already gives bank 13 `+3990`.

---

Everything needed to start from cold. Read `HANDOFF.md` first for project state and the
traps; this file is only about the variable-width font.

Written 2026-07-30, after TASK 1b landed as commit `02a3e04`.

**Status: not started, and now gated on TASK 2. The prerequisite routine is found and read;
the space to put the code in is NOT found, and that is the first real problem.**

Everything below marked **MEASURED** was read out of the ROM or a build this session.
Everything marked **UNVERIFIED** is inference and has to be checked before anything is
built on it. The last brief's two costly mistakes were both in the unmarked middle —
a `sed` recipe nobody ran and an allowlist argument nobody tested — so the distinction is
kept explicit here.

---

## Why VWF — RESCOPED BY JOEY 2026-07-30, read this before planning

**The menus no longer need it.** Box resizing solved the known spacing problems: box 0 went
to 7 cells, the item action menu to 8, difficulty to 7, and all of them are confirmed on
screen. The earlier framing — "there is now a case geometry cannot fix", `Ground` at six
characters — **is retracted**. Geometry did fix it.

That is just as well, because VWF could never have fixed it: the menu box drawer
(`31:$40D8`) writes tilemap entries, one code per cell, and cannot position sub-cell without
a rewrite of a different order. **VWF is the COMPOSER only** — dialogue, dungeon messages,
combat messages, item descriptions.

**What is still unknown, and is the actual question to answer first:**

* **How long do item names get in the menu?** Untested. The list box gives 16 cells.
* **Is there a per-item description shown in the menu?** Untested — nobody has looked.
* **Does dialogue actually need VWF at all?** Unknown. It already works at fixed width
  because it can spill into more lines and boxes.

So the deciding question is no longer "how do we fit the menus" but **"does the dialogue
look good enough at fixed width?"** — and the honest answer is that nobody has read enough
translated dialogue to say. Very little dialogue is translated yet.

**Joey's position:** VWF is reportedly easy for everything outside the menu, and if it is
easy then it is worth doing purely for quality. So this task is now **quality-driven and
optional, gated on a cheap experiment**, not a blocker.

### Do this before writing any VWF code

1. **Translate a handful of real dungeon/village messages** and look at them at fixed width.
   That answers "does it need VWF" for a fraction of the cost of building it.
2. **Check the item menu**: how long are item names, and is there a description field?
   That is a `boxscan.py` / screenshot job, not a code job.
3. Only then decide. If fixed-width dialogue reads fine, VWF is polish and can wait behind
   TASK 3 and bulk translation.

**And note the "easy" claim has one measured counter-example**: see the space table below.
The blit itself is easy. Finding somewhere to put it is not.

## The composer, as read this session

Two loops, both **MEASURED**.

**Loop 1 — source bytes into the line buffer, budgeted in CELLS.** `13:$40D6`:

```
13:$40D6  ld b,$12          ; 18 cells, the budget
13:$40D8  ld de,$CF07       ; the line buffer
13:$40DB  ld a,[hl+]        ; source byte
13:$40DC  cp $FF / cp $EE / cp $EF     -> done
13:$40E8  cp $E0 / jr c,$40F1          ; >= $E0 is a control code
13:$40EC  call $4107                   ; control-code handler
13:$40F1  ld [de],a / inc de           ; <- THE DTE HOOK LIVES HERE
13:$40F3  ld a,[hl] / cp $79 / cp $7A  ; next byte a combining mark?
13:$40FC  dec b                        ; charge a cell
13:$40FD  ld a,b / cp $00 / jr nz,$40DB
```

`$40F1` is already `call dte_emit` in the built ROM. **Whatever VWF does to the budget has
to agree with what `dte_emit` charges**, because one compressed byte expands to several
cells — the expander charges cells in `b` itself. See "The DTE collision" below.

**Loop 2 — buffer bytes into glyph tiles.** `13:$4418` walks the buffer; `13:$4464` is the
blitter, and it is the prerequisite that makes VWF cheap:

```
13:$4464  ld b,$00
13:$4466  sla c / rl b   (x3)      ; bc = code * 8
13:$4472  push hl
13:$4473  ld hl,$7680              ; font base, 1bpp, 8 bytes per glyph
13:$4476  add hl,bc
13:$4477  ld b,$08
13:$4479  ld a,[hl+] / ld [de],a / inc de / ld [de],a / inc de / dec b / jr nz
13:$4481  pop hl / pop bc / ret
```

`de` is a running tile-data pointer; the doubled store is 1bpp expanded into both 2bpp
planes and stays exactly as it is. **The composer already builds a fresh tile per
character** — it is not picking tiles out of a fixed set — so VWF is a change to this loop,
not a new rendering path.

VWF here = shift the font byte by a pen offset, OR it into the current tile, carry the
remainder into the next tile. Width side: `13:$40DB`'s cell counter becomes `b -= width[c]`
in pixels.

**The font is at `13:$7680`, 1bpp, 8 bytes per glyph — MEASURED**, and it is where
`tools/latinfont.py` writes (`FONT_BASE = 0x37680`). English uses **77 glyphs over codes
`$00-$B2`** (sparse: the punctuation reuses the ROM's native glyphs at `$7C-$B2`), so the
font region spans `$7680-$7C17`, about 1432 bytes.

## The blocker nobody has hit yet: there is nowhere to put the code

This is the finding that changes the shape of the task, and it is **MEASURED**:

| home | state |
|---|---|
| bank 0 `$0062` padding | **FULL** — 158 of 158 bytes, 3 stray `$FF` only |
| bank 0 tail `$3FEC-$3FFF` | **FULL** — `dte_box_hi` has it, and `$3FFF` must stay unused |
| bank 0 RST gaps | 18 bytes in three runs of 6 (`$002A`, `$0032`, `$003A`), all `$FF` |
| **bank 13 (the composer's own bank)** | **ZERO free bytes — not one `$FF` run of 8 anywhere** |
| banks 32-63 | free; bank 32 holds the DTE table at `$4000-$42FF`, so `$4300+` is open |

So VWF cannot live beside the code it patches, and it cannot live resident. **The DTE
plan's central lesson applies directly: check the premise of the blocker before rationing
against it.** Rationing 18 RST bytes is the same mistake as rationing bank 0's padding was.

### The architecture that follows — **UNVERIFIED, but it is the one to test first**

Put **code, font and width table together in a free high bank**, and reach it the way the
ROM already reaches other banks.

* The blitter needs the font (`13:$7680`) *and* the width table at the same time, and only
  one switchable bank is mapped at `$4000-$7FFF`. So **copy the Latin font into the VWF
  bank** — `latinfont.py` already writes the font, so it can write it twice, and `$7680`
  stops being load-bearing.
* Entry is the ROM's own far-call trampoline: `rst $08 / db <routine>, <bank>`, three bytes
  in place, exactly the shape of the `31:$4106` box hook. `0:$079E` recovers the caller's
  bank by reading `[$4000]`, because **byte 0 of every bank holds that bank's own number**.
* **Call it once per LINE, not once per glyph.** Move the whole of loop 2 into the VWF
  bank rather than paying trampoline overhead 18+ times. This is the part most likely to
  be wrong on the first attempt — measure it.

The width table is ~179 bytes if indexed directly by code `$00-$B2`, which is nothing in a
bank that is entirely `$FF`. Do not pack it.

## The DTE collision — think about this before writing any code

`13:$40F1` is `call dte_emit`, and `dte_emit` **charges cells in `b` itself**. Two settled
decisions constrain what VWF may do to that register:

* **The buffer bound is an address, not a character cap.** `emit_lit` refuses to write at or
  past `$CF38`, which is stronger than a character cap because it holds however many bytes a
  pair expands to. `$CF38` and not `$CF43` because the composer reads the buffer's zeroes as
  the end of the line.
* **Cell counting charges the dakuten, not the base character**, because `13:$40F3` peeked
  the next *source* byte and that cannot survive a byte living inside a table entry.

So the line buffer is **`$CF38 - $CF07` = 49 bytes** and that ceiling does not move with
VWF. VWF lets a line hold more CHARACTERS than 18, but never more than the buffer holds —
**the budget in `b` and the buffer bound are two different limits and VWF changes only the
first.** Widening the buffer is a separate change with its own blast radius (`$CF43` is the
next structure; `13:$4497` copies 20 bytes from `$C008` to `$CF43`).

If `b` becomes a pixel budget, `dte_emit` has to charge pixels too, which means the expander
needs the width table as well. **That is an argument for doing the width lookup in one place
and having both callers use it**, and an argument against a quick hack in the blitter only.

## ~~What has NOT been mapped, and must be first~~ — **ANSWERED 2026-08-03, see the top**

> Kept because the reasoning below is how the question was framed, and the answer is that
> **both readings were correct**: `$C006` is a transfer queue and the payload type depends
> on which bank-0 consumer runs. `0:$10A0` reads 22-byte slots (tilemap rows), `0:$11C5`
> reads 66-byte slots (tile data), and `3 × 22 = 66` is why the same addresses served both.

**UNVERIFIED — this is the first job, before any design is committed.**

The tile/tilemap plumbing between loop 2 and the screen. What is known: `13:$43B8` sets
`de = $C008`, `b=2`, `c=4`, and calls the blitter four times per group; `13:$4484` treats
`$C008` as a **20-byte tilemap row** copied to `$CF43`. Those two readings do not obviously
reconcile — 16 bytes of glyph data per blit would overrun a 20-byte row after one glyph —
so **one of them is a different context and I did not settle which.**

VWF depends entirely on this: it packs characters into FEWER tiles, and whether that helps
depends on how many tiles a line owns and who writes the tilemap entries that point at them.

Settle it by tracing, not by reading:

```
python3 tools/gbrun.py build/shiren_en.gb --state saves/dungeon.state --frames 800 \
        --press a:120 --trace          # which copy loop drew the message
```

then hook `13:$4464` and log `de` per call, and `13:$4484` and log what it copies. Same
technique as `tools/gridprobe.py`, which is a worked example of hooking one instruction and
comparing what the game computed against what the ROM actually holds.

## The verification path, which is much stronger than it was

Use all of it. Every one of these caught something real this year.

```
sh build.sh                       # expect 1445 checks ALL OK, no problems
python3 tools/dte_rom.py          # 5278 segments / 0 mismatches; verify_box 0 failures

# the regression pair -- build the pre-change ROM first, AND COPY ITS .ram
cp build/shiren_en.gb build/prevwf.gb && cp saves/shiren_en.srm build/prevwf.gb.ram
python3 tools/gbrun.py build/shiren_en.gb --compare build/prevwf.gb \
        --state saves/dungeon.state --frames 800 --press b:120
python3 tools/gbrun.py build/shiren_en.gb --compare build/prevwf.gb --frames 1400 \
        --press start:700,start:760,start:820,start:880,a:940,a:1000
```

* **`tools/gbemu.py`** raises on any opcode it does not implement, so a VWF blitter cannot
  be silently mis-executed into a passing test. Write the shift/merge loop against it first
  — that is how the DTE expander was built and it is much faster than emulator round trips.
* **`tools/gbasm.py --selftest`** round-trips 249 forms; its opcode table is inverted from
  `dis.py`'s so the two cannot drift.
* **`tools/gridprobe.py`** must still pass. Name entry shares the font.
* **`tools/boxscan.py`** reaches any of bank 4's 35 screens by forcing the dispatcher index
  at `4:$48AA` — use it to photograph message screens that are awkward to navigate to.
* **A screenshot is not optional.** Three white screens during TASK 1 were green at every
  byte-level check, and the name-entry picker read the wrong character for the entire life
  of the English build with 1451 checks passing.

## Traps that apply specifically to this task

**A renderer's geometry can be duplicated in ARITHMETIC somewhere else.** This is the fresh
one and it is exactly the shape of a VWF bug. The name-entry picker hardcoded its grid's row
stride as an immediate at `31:$41A0`; translating the grid changed the real stride and the
constant went on being 19. References get repointed, immediates do not. **Before changing
how the composer lays out tiles, grep for code that indexes those tiles.**

**"Cosmetic for the composer" is not "cosmetic for the box drawer".** They fail differently.
The composer's floor is one bad line; the drawer's is every subsequent row of the box.

**`build.sh` reads `script/en.tsv`, not `script/menu_en.tsv`.**

**`tools/dis.py` shadows the stdlib `dis`** — any script in `tools/` that imports pyboy dies
with a bizarre `COMPILER_FLAG_NAMES` error. Copy the `_import_pyboy()` shim from
`gbrun.py` / `gridprobe.py`.

**Do not trust a `--compare` baseline you have not health-checked, and copy its `.ram`.**
A ROM without its save file boots to a different title menu and every screen after that
differs. That looked like a render regression for a while this session.

## ~~After VWF: TASK 3, the player name~~ — **DONE 2026-08-03, before VWF**

The name is six characters (`tools/name6.py`) and the rankings board stores and draws six
(`tools/rank6.py`). Both landed ahead of VWF, and the reasoning here was right about why:
name entry is on the **tilemap** path, so VWF was never going to make six characters fit a
four-cell field — the field had to genuinely widen, and it did.

**What that leaves for VWF: `PLAYER_NAME` is already 6 in `dialogue_preview.py`, so the
`<var>` budget you are re-decreeing against is the real one.** `NAME_CAP = 8` and
`ITEM_CAP = 10` are still the fixed-width numbers and are what session 2 exists to replace.

The picker's stride is derived by `build.py` (`GRID_BOX` / `GRID_STRIDE_AT`) and checked by
`tools/gridprobe.py`, so **re-laying-out the name-entry grid is cheap and independent** —
see the note in `HANDOFF_NEXT.md` §3. It shares the font with the composer, so `gridprobe`
staying green is part of this task's battery either way.
