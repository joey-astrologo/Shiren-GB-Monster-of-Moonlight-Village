# HANDOFF — THE SPACE PROBLEM IS CLOSED

> **Archived:** completed historical investigation. See the repository
> [README](../../README.md) and [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

**Rewritten 2026-08-03, after the last two shortfalls were closed. Read `HANDOFF.md` for
project state, then this.** Every previous version of this file planned a ceiling to
remove. There are none left: `sh build.sh` now ends

```
   every arena fits the finished script at this ratio.
   ...
   ** every arena above can hold its whole share of the finished script.
```

The second line is the one that matters — it is the **ratio-independent floor**, and it
does not depend on 2.15x being the right number.

> ## The rule this job existed to satisfy
>
> **Joey, 2026-07-31:** *"We keep going in circles about the spacing issue. This was
> supposed to be solved. Every session it's, we have room, then oh wait there was a
> mistake... Having too much space is not an issue later. Constantly finding out we don't
> have space, that is a major issue."*
>
> **Budget at 2.15x natural English WITH DTE. Prefer removing a ceiling over buying
> headroom.** Applied four times now. Every ceiling is structurally gone, so the ratio no
> longer decides whether any bank fits.

---

## 1. Where things stand

```
   arena                     holds will need    margin
   bank 11                    4151     3737      +413
   bank 13                    6915     2924     +3990
   bank 14                    1108     1047       +60
   bank 30                      73       58       +15
   bank 31                     534      449       +84
   redirect pool            483840    25167   +458672
```

Bank 6 is not in the table any more — it had one "string" and it was code (§3).

For the record, the sequence: **5,850 short** (three banks) at the start of 2026-07-31 →
2,877 → **816** → **0**.

## 2. What the last two sessions actually found

Both remaining shortfalls turned out to be **the same bug twice**, and neither was a space
problem. `extract.py` was inventing references, and `build.py` was faithfully rewriting the
bytes underneath them.

### Bank 11 was never address-sensitive (−2061 → +413)

`build.py --shuffle` changes packing order and nothing else, and it hung the game on 4 of 4
seeds at `0:$2337`. The previous brief read that as "bank 11 holds an address-sensitive
dependency no reference scan sees" and shut bank 11 out of the redirect entirely.

The dependency was **in the reference scan**. `0:$22BD` is byte 17 of the 24-byte
state-transition table at `$22AC` that `0:$2274 ld hl,$22AC / add hl,bc / ld a,[hl]`
indexes. Its bytes `01 02 42` decode as `ld bc,$4202`, so a reference to `11:$4202` was
recorded and rewritten on every build. Address-order first-fit kept landing `11:$4202`
back at `$4202`, so the write was a no-op; under any other packing the entry's low nibble
steers the state machine into state 5, `0:$2337 jr $2337`. **Restoring those two bytes in
the hung ROM makes 4 of 4 seeds pass.**

`dis.boundary_votes` scores `$22BD` a perfect 64/0 and always would: it proves an immediate
is not inside a longer instruction, not that the bytes are code. What works is the ROM's own
structure — **a bank-0 `ld bc,$4xxx` either reaches `call $028B` or it is not a text
pointer.** `msg_push_kind` now traces control flow forward to the push instead of matching
two hard-coded byte shapes, and bank 0 must pass it. That also picked up 2 real pushes the
byte match had missed (`0:$30D2`, `0:$30E3` — three candidates and a longer `jr`).

### Bank 6 had no strings at all (−4 → the arena is gone)

`6:$472F` is the `ld hl,$786A` in the middle of the routine at `6:$4722`:

```
ld d,$00 / ld e,a / ld hl,$77CD / add hl,de / ld a,[hl] / ld [$FF90],a
                    ld hl,$786A / add hl,de / ld a,[hl] / ld [$FF91],a
```

Two identical idioms filling the message-pointer pair. What "pointed at" it was the
cross-bank table `10:$4663`, and a cross-bank table carries no bank byte — the target bank
was an inference and it was wrong. Its entries are also 1 and 2 bytes apart, which no
string can be. So six words of bank-10 data were being rewritten on every build, hidden by
exactly the same accident as `0:$22BD`. It is in `extract.MANUAL_DROP` now.

### Bank 13's renderer, and the WRAM buffer that was not needed (−812 → +3990)

Table `13:$554A` (122 strings, 4,224 JP bytes) has three readers, enumerated rather than
sampled: `13:$7D90` publishes one queue address per line, `13:$7DE8` counts units, and
`13:$7E49` renders. The first two test only `$EE`/`$EF`/`$FF`, so a record run is
transparent to them. The third got **`MODE_RENDER`**:

* **a fourth text-bank reader mode** — `13:$7E51`'s loop for ONE line, running co-resident
  with the text, because that is the only place pool text is readable. It is the only mode
  that interprets control codes, because the loop it replaces does: `$ED` dropped, `$F0`
  consuming an argument and far-calling `11:$7E26`. That nested `rst $10` is safe because
  `install()` writes every text bank's id to byte 0, which is where the far call reads the
  bank to restore.
* **a trampoline at `13:$7E4C`** replacing `call $7E0D` — one far call per line, the
  four-line budget `$7E4F` would have set, and `$EF` turned into the `$FF` that `$7E51`
  writes for it. It then hands `$7E51` an address holding `$FF`, so the loop it did *not*
  replace still runs once and writes the destination terminator.

**The previous brief budgeted a ~200-byte WRAM buffer and a poison test to prove it free.
Neither was needed** — rendering inside the text bank removes the requirement. The WRAM
census in `scratchpad/wramcensus.py` is unspent, and `$DD00-$DDE5`, `$DA22-$DAFD`,
`$DB25-$DBFE` remain unproven candidates if anything ever does need WRAM.

## 3. `--redirect-all`, and why it is the important part

The ratio-independent floor was a claim about a build nobody had ever made. Today a bank
redirects two or three strings, so the mechanism carried almost none of the text it was
being trusted with, and "it works" was measured on the easy case.

`python3 tools/build.py <expanded.gb> script/en.tsv out.gb --redirect-all` drains the
victim list instead of stopping the moment the bank fits: **598 strings become records.**
That is the endgame's load, buildable today. Everything in §4 is run against it.

## 4. Verification — what a build has to pass

* `sh build.sh` — reference checks ALL OK, `no problems`, and both projection lines saying
  every arena fits.
* `python3 tools/pool.py --selftest` — 8 checks.
* `python3 tools/reloc_verify.py build/shiren_en.gb build/base.gb --verbose` — 0
  mismatches. Against `--redirect-all`: **978 reads, 111 of them render units**. It skips
  strings whose pool text differs from the Japanese, because a translated string has no
  reference to compare against; watch that number grow as translation proceeds.
* `python3 tools/crashscan.py <rom> --seeds 12`.
* `python3 tools/pool_verify.py build/shiren_en.gb --seeds 4`.
* **`--shuffle` + crashscan on any bank whose layout you are about to change.** This is the
  falsifier for the whole invented-reference class, and it is the only reason bank 11's bug
  was ever seen. Run it.
* `tools/gbrun.py <rom> --walk-seed N --compare <--no-reloc build>` — IDENTICAL.
* `python3 tools/helpshot.py <rom> --topic N` — the help screen, which no walk seed
  reaches. Forces index 4 of bank 4's menu dispatcher (`4:$48AA`) and snapshots the render
  buffer at `4:$49BF`. All 24 topics byte-identical, 4 of them pixel-identical.
  **`$C6BC` (the unit index) is 0 for every topic in this table** — 1 makes both builds
  walk off the end of the string into different neighbours, which is not a defect.

Measured on this session's final state:

```
build                    2211 checks ALL OK; every arena fits, floor too
reloc_verify             978 reads, 111 render units, 0 mismatches
crashscan                12 seeds normal, 12 --redirect-all, 8 +--shuffle
gbrun --compare          IDENTICAL, 6 walk seeds x 3 builds vs --no-reloc
helpshot                 24/24 topics identical, 4/4 screens pixel-identical
readers.py               independently re-measured 13:$554A -> 13:$7E51
```

## 5. What this class of bug looks like, because it has now cost three sessions

Four instances so far: the name-entry grid stride, the death-message comparison, the
box-layout stride, and now **two invented references** (`0:$22BD`, `6:$472F`). The
signature of the last two:

* a build that works only because a string lands back where it started;
* a "dependency" that no scan can see, because there is nothing to see;
* `boundary_votes` scoring the site perfectly, because short data decodes as short
  instructions.

**The test is `--shuffle` + crashscan.** If moving text breaks a bank, suspect the
reference list before suspecting the bank.

## 6. Order for the next session

The space problem is not on this list. It is done. `HANDOFF.md` -> "PROJECT ORDER" carries
the full version; the short form:

1. **Translator export + lint.** `script.tsv` reports `bytes` for all 1,263 strings and it
   is the wrong number for **952** of them -- redirected strings have no byte budget at
   all, only cells. A lint that still reports bytes invents a limit and buys telegraphese
   for nothing. The 311 that ARE still bank-local are listed in `HANDOFF.md`.
2. **Player name 4 -> 6.** Small, unblocked, and it settles the `<var>` cell budgets
   `TRANSLATING.md` §4 depends on -- so it goes before bulk translation, not after.
3. **Bulk translation.** Write natural English; `build.py` redirects anything that overruns.
4. **Graphics** last, independent, can run alongside translation.

**Demoted: `HANDOFF_1B.md` (DTE for dialogue).** It compresses in-place dialogue, which now
lands in a pool with 458 KiB spare. A pure optimisation, not a blocker.

## 7. Tooling note

`mgbdis` and `rgbds` are installed (`../mgbdis`) and available if a job wants to read a
whole bank as a document. Nothing in the pipeline depends on them and nothing so far has
needed them -- `tools/dis.py` answers "what is at this address" and was enough for the
entire bank-13 renderer. mgbdis emits RGBDS source for the ORIGINAL 512 KiB ROM; the build
is byte-patching, not reassembly, so a listing is a reading aid and never an input.
