# Traps — mistakes that cost real time

Every entry here is a wrong turn someone actually took on this project, with what it cost
and what the correct move was. They are kept because a recorded wrong turn is the only
thing that reliably stops the next person repeating it.

This is method, not ROM behaviour. For how the ROM works see [`FINDINGS.md`](FINDINGS.md);
for the rules a change must satisfy see [`ENGINEERING_RULES.md`](ENGINEERING_RULES.md).

---

## Measurement and inference

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

**Editing a "source of truth" that nothing copies across is a silent no-op.** The project
once kept menu strings in a second file that the build did not read; editing it produced a
build that ignored every change and reported success, because as far as the pipeline was
concerned nothing had changed. That particular file is gone, but the shape recurs: before
editing, confirm the build actually reads the file you are editing. `grep` the filename in
`tools/build.py` and `build.sh` — if it appears only in comments, it is not an input.

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
read it, or edit it in `script/build-inputs/box_geometry.tsv`. Delete the ⅔ rule of thumb from your head.

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

## What this class of bug looks like

Reconstructed from the pool/relocation investigation, which cost three sessions.

Four instances so far: the name-entry grid stride, the death-message comparison, the
box-layout stride, and now **two invented references** (`0:$22BD`, `6:$472F`). The
signature of the last two:

* a build that works only because a string lands back where it started;
* a "dependency" that no scan can see, because there is nothing to see;
* `boundary_votes` scoring the site perfectly, because short data decodes as short
  instructions.

**The test is `--shuffle` + crashscan.** If moving text breaks a bank, suspect the
reference list before suspecting the bank.

---

## Measuring a duration, and how that diagnosis went wrong three times

From the dungeon-message expiry bug. The lesson generalises past the specific defect: it is
the clearest worked example in the project of a plausible model surviving several rounds of
reasoning and still being wrong.

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

### How the diagnosis went wrong — three times

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
