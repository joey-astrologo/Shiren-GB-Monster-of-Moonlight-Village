# HANDOFF — job 1b: make dialogue compressible

> **Archived:** completed historical investigation. See the repository
> [README](../../README.md) and [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) for current work.

**Written 2026-07-31, straight after job 1a. Read `HANDOFF.md` first for project state, then
this. Everything below was measured this session, not carried over.**

> ## The one-line version
>
> The mechanism is already built and already works. **What is missing is COVERAGE** — a way
> to make the game read 301 dialogue strings so a trace can see it — and the old framing of
> this job ("613 strings in bank 11") is wrong in two ways. Corrected numbers below.

---

## 1. What the previous handoff said, and what is actually true

`HANDOFF.md`'s work queue says:

> **1b** — Allowlist bank 11 the way bank 14 was — `--dte-scan --walk-seed` through the
> village, **613 strings** currently uncompressed for want of an observation.

Three corrections, all checked against `script.json` and a live trace:

**a. It is 151 strings in bank 11, not 613.** 613 is every bank-11 string. The 462
relocatable ones are monster names, item names and menu labels — they never go near the
dialogue stager. 17 of them are *already* allowlisted, via `0:$00CC` on the `11:$52D5`
menu-label path. The dialogue is the **151 in-place** strings, 8,087 Japanese bytes.

**b. Bank 14 was never finished either.** The handoff reads as though bank 14 is done and
bank 11 is the leftover. It is not: bank 14 has **150** in-place dialogue strings and
**4** of them are allowlisted — the inn scene, and only because the seeded dungeon walk
happens to die and wake up there. So the real job is **301 strings across both banks**, and
bank 14 is not a solved precedent to copy so much as the same problem at 3% coverage.

| | strings | JP bytes | in `dte_ok.tsv` |
|---|---|---|---|
| bank 11 in-place dialogue | 151 | 8,087 | **0** |
| bank 14 in-place dialogue | 150 | 7,701 | **4** |

**c. "For want of an observation" is right, but the missing piece is not the hook.**
`11:$56A2` is already in `dte_rom.STAGER_SITES` and `gbrun.py --dte-scan` already hooks it.
It fires. It fired this session:

```
python3 tools/gbrun.py build/shiren_en.gb --state saves/town.state --walk-seed 1 \
        --frames 6000 --dte-scan
  11:$6340   via 11:$56A2 bank 11 dialogue stager -> $CF8F      # 1 string, of 151
```

(`11:$6340` is `タグラ「おにいちゃん どっから<br> きたの？」` — a child in the village. It is
not in `dte_ok.tsv` yet; the run above was a diagnostic, without `--append`.)

From `saves/dungeon.state`, over two seeds and 6,000 frames each, `11:$56A2` fires **zero**
times. **The tooling is done. The problem is reaching the text.**

---

## 2. Why the text is hard to reach, which is the actual content of this job

Look at what bank 11's in-place dialogue *is*:

```
11:$571F  むらおさ「オ、オロチを・・・ オロチを ついに たおしたのか！」
11:$5741  キンジ「やったあ！」
11:$5770  ロクロウ「こんなメデタイことは ないぜ。さあ こんやはえんかいだ！
11:$57F6  みんな「おおーーっ！！」
11:$7C36  だいくのマサ「よう <name>さん！ これが おれにできる さいごの しごとだ。
```

It is the **post-Orochi celebration, the endgame village, the carpenter's last job**. Story
dialogue, gated behind progress a random walk cannot make. A seeded button walk from a
mid-game save will never see most of it, and no amount of extra frames changes that. This is
the same wall `boxscan.py` hit with the item category boxes, and it has the same answer.

---

## 3. The prize — and READ §3a BEFORE COSTING THIS JOB

DTE is what keeps the redirect pool from filling up. In-place dialogue has nowhere else to
go — banks 11 and 14 have no spare bytes and the text cannot be repointed — so the pool is
the whole budget:

| | English in the pool | of 32,256 bytes |
|---|---|---|
| no DTE, at the project's 1.66x | 26,208 | **81%** |
| no DTE, at the measured 2.15x (§3a) | 33,900 | **105% — DOES NOT FIT** |
| DTE at today's 46 codes, from 1.66x | 19,577 | 61% |
| DTE at today's 46 codes, from 2.15x | 25,100 | **78%** |

**It is already proven to work end to end.** `14:$5047` is both allowlisted *and*
pool-redirected: 407 bytes of English stored in **302** (74%), read through the pool
dispatcher, expanded by loop2, and photographed on the real screen this session
(`build/inn_2495.png`). So compression and redirection compose correctly. That question is
closed — do not re-open it.

## 3a. TWO CORRECTIONS THAT MAY REORDER THIS JOB — found 2026-07-31, unresolved

### The 1.66x expansion ratio is probably wrong, and the whole budget rests on it

`HANDOFF.md` prices everything at **1.66x**, from `dialogue_fit.py` over an 18-string sample.
**The only string in the project actually written as natural English measures 2.15x:**

| | JP slot | English raw | ratio |
|---|---|---|---|
| `14:$5047` as shipped before job 1a | 190 | 413 | **2.17x** |
| `14:$5047` after job 1a's re-wrap | 190 | 407 | **2.14x** |
| `14:$5106`, `14:$5127` (written to the OLD byte cap) | 62 | 66 | 1.06x |

The two 1.06x strings are telegraphese — they were fitted to a slot, so they are not evidence
about natural English. The 2.15x one is, and it is 29% above the number the pool budget uses.
The rewrite is not the cause: it measured 2.17x *before* job 1a touched it.

**Roughly a third of the gap is layout, not prose** — English needs 26 lines where the
Japanese needs 11, and each line costs an indent space plus a break code, about 35 extra
bytes on a 190-byte slot. That still leaves ~1.95x for the prose itself.

**Consequence: at 2.15x the pool does not fit at all without DTE, and fits at 78% with it.**
That flips 1b from an optimisation into a prerequisite — or, if §3a's second half is taken,
makes it optional again. Either way **do not cost this job off 1.66x.**

### The 32,256-byte pool ceiling is a design choice, not ROM space

**Banks 32-63 are entirely `$FF` — 31 free banks, ~500 KiB.** The pool uses two of them, and
the reason is the redirect record:

```python
RECORD_LEN = 4                 # MARK, lo, hi, $FF
def _stored(bank, addr):       # 16 bits total: bit 15 picks the bank, 15 bits of address
    return addr if bank == POOL_A else (addr | 0x8000)
```

One bit of bank, so two banks. **A 5-byte record `MARK, lo, hi, bank, $FF` would lift the
ceiling to whatever is free**, and it costs nothing in eligibility: `pool.eligible` needs
`bytes >= RECORD_LEN`, and of the 301 eligible strings **zero are 4 bytes and only two are
under 9**. A bank number `$21-$3F` also cannot collide with the staging terminators
`$EE`/`$EF`/`$FF`, so the record stays safe by construction.

**It is not free work, though, and here is the honest cost.** Two things resist:

1. **The far call's bank is an immediate.** `rst $10 / db $03,$22` hardcodes bank 34, so a
   variable bank needs a table of one 4-byte stub per pool bank in bank 33 — cheap, but it
   is ASM, plus `pool_verify.py` and the `gbemu.py` selftest.
2. **The continuation pointer would have to carry the bank.** `dispatch_src`'s `done:` writes
   `h`/`l` back to `$CF7F`/`$CF80` so the next line resumes where the copy stopped. With more
   than two banks that needs a third byte of state, and finding a safe WRAM byte in the
   `$CFxx` block is exactly the kind of thing that has cost this project sessions.

Call it a half-day spike, not an hour — but it removes the constraint permanently instead of
buying 20 percentage points against an uncertain ratio.

### DECIDED 2026-07-31 by Joey: budget at 2.15x with DTE, and stop re-measuring

The project has "solved" the space problem twice and re-opened it twice, both times because
a decision had been costed against an optimistic estimate. **The ratio is no longer an open
question and should not be re-litigated.** Standing rule:

> **All space budgeting assumes 2.15x natural English WITH DTE (1.60x stored). DTE is
> assumed ON — no "without DTE" column. Being wrong high costs nothing; being wrong low has
> cost a session, twice.**

This is implemented, not just written down: `build.py`'s `PROJECT_RATIO`, and **every build
now prints an ENDGAME PROJECTION** — what each arena will need when every string in it is
English, against what it holds. Today's spare is not headroom and never was, and reporting
only today's spare is the direct cause of the cycle: bank 11 read `+29 spare` while being
1,703 bytes short of its finished script.

### So which job is next? — and the answer is NOT 1b

Run `sh build.sh` and read the projection. As of 2026-07-31:

```
   arena                     holds will need    margin   done
   bank 11                    4331     6034     -1703   36/460 strings
   bank 13                    6977    10538     -3561   11/323 strings
   bank 14                    1131     1713      -582   0/57 strings
   bank  6                       8       11        -3   0/1 strings
   redirect pool             32256    25167     +7088   4/301 strings
```

**Two conclusions, and they reorder everything.**

1. **DTE does not buy the guarantee.** Even with DTE assumed on, the relocatable banks are
   **5,850 bytes short** and the pool has only 22% margin — on a projection whose ratio is
   itself one data point. Job 1b (DTE for dialogue) improves the pool, which is the arena
   that already fits. **It does not touch the arenas that do not.**
2. **The shortfall and the margin are both ceilings that can simply be removed.** 31 ROM
   banks (~500 KiB) are still entirely `$FF`, against a total finished-script need of about
   **32 KiB**. That is a 15x margin available for the taking.

**So the next job is not 1b — it is to end the space problem properly**, by giving both
redirect mechanisms access to the free banks:

* **The pool's 5-byte record** (§3a above), which turns 2 pool banks into as many as wanted.
* **The relocatable redirect** — `HANDOFF.md`'s job 3, the same mechanism applied to the
  five copy loops instead of the one gate, three of which are already hooked for DTE. This
  is what fixes the 5,850.

Do those and the projection goes permanently green with a margin no future measurement error
can reopen. **1b then becomes what it should have been all along: an optimisation, doable
whenever, on a project that is no longer short of space.** The brief above stays valid for
when it comes up.

---

## 4. Two routes. Take the first.

### Route A (recommended) — force the pointer, let the REAL stager run

`13:$7589` is the single gate, and its inputs are two bytes of WRAM:

```
13:$7589  ld a,[$CF80] / ld h,a          ; the pointer the message queue stored
13:$758F  ld a,[$CF7F] / ld l,a
13:$7593  bit 7,h
13:$7595  jr nz,$759C
13:$7597  rst $10 / db $0D,$0B           ; bit 7 clear -> bank 11's stager
13:$759C  rst $10 / db $03,$0E           ; bit 7 set   -> bank 14's stager
```

So: **write the address into `$CF7F`/`$CF80`, call `13:$7589`, and the real stager copies the
real bytes.** Only the navigation is synthetic — exactly the argument `boxscan.py` makes for
the item category boxes, and `HANDOFF.md` accepts it there ("Forcing that index makes the
REAL routine draw the REAL box through the REAL drawer").

Mind the window bits. Bank 11's stager does `set 6,h` at `11:$56A0` before reading, so a
bank-11 address is **stored with bit 14 clear**: `11:$6340` is stored as `$2340`. Bank 14's
does `xor $C0` (`14:$400A`), so `14:$7305` is stored as `$B305`. Get this wrong and you will
scan the wrong bank and not notice.

**Build it as `tools/dlgscan.py`, modelled on `tools/boxscan.py`** (~100 lines; that file is
the template for "force an entry point, hook, record"). Feed it every in-place string in
banks 11/14 from `script.json`, one per call, and append the hits to `script/dte_ok.tsv`.

**Two self-checks to build in, because they are free and they catch the failure mode:**

1. **Assert the stager stops where `script.json` says the string ends.** The stager halts on
   `$EE`/`$EF`/`$FF`, so the byte count it copies should match the string's own extent. If it
   does not, either the extraction is wrong or you forced the wrong address — and it
   independently corroborates 301 extractions for free.
2. **Confirm the EXPANDER fired**, not just the stager. Hook `13:$6893`/`dte_emit` in the
   same run. A stager observation is explicitly the weaker claim (`HANDOFF.md`, "Observing
   the dialogue stagers"); catching loop2 as well upgrades it, and costs one more hook.

**The hazard to guard.** Forcing a pointer proves the stager *can* read those bytes, not that
the game ever pushes them. Feed it only addresses that are real extracted in-place strings —
never a byte range you picked — or you will cheerfully allowlist something like `14:$7EE6`,
the 294-cell blob that is not script at all. Check 1 above is the guard.

### Route B (fallback) — the structural argument

`pool.eligible()` already stakes the ROM on this claim:

> A string in bank 11 or 14 with NO reference anywhere in the ROM has no other way to be
> reached than the runtime message queue, which lands on `13:$7589`.

If that is true, every one of the 301 is *necessarily* staged through `$CF8F` and therefore
necessarily reaches loop2, and an observation adds nothing a proof does not already give. The
three interposing risks were checked once and cover both stagers equally (`HANDOFF.md`,
"Observing the dialogue stagers"): the stagers stop on the same bytes before and after
compression, `13:$67F3`'s `cp $EC` is unaffected, and `13:$688D` is the hooked loop. The only
three readers of `$CF8F` in the ROM are `11:$56A2`, `13:$67F3`, `13:$688D`, `14:$400D`.

**Why it is the fallback and not the plan.** `HANDOFF.md` says twice, in bold, not to weaken
the allowlist rule — "Do not weaken this rule; make the screen reachable instead" — and it
says so because guessing eligibility per bank *already shipped garbage to the screen* once.
Route A makes the text reachable and keeps the rule. Use Route B only if Route A turns out to
be genuinely blocked, and if you do, say so in `dte_ok.tsv` with a distinct site label so the
weaker evidence is visible where it is used.

### Route C — more save states

Ask Joey for a save at each story beat and walk from each. Real evidence, zero new code, and
worth doing anyway for the strings players actually see — but it cannot reach 301 strings and
it blocks on someone else's play time. Complement, not plan.

---

## 5. Do it together with some bank-11 translation, or you cannot verify it

**Allowlisting alone changes nothing in the ROM.** `build.py` compresses a string only when
it is translated *and* differs from the Japanese, so a bigger allowlist over untranslated
Japanese produces a byte-identical build. That is a good property — but it means the job has
no observable effect and nothing to check.

**So translate a handful of bank-11 dialogue strings in the same session** (the village
scene at `11:$6340` is a natural pick — short, already observed, and reachable from
`saves/town.state` for a screenshot). Then you can state the yield as a number and photograph
the result, the way TASK 2 did.

**Do ten of them, and do them FIRST**, because per §3a the same ten settle the expansion
ratio that decides whether this job is a prerequisite or an optimisation. Write them as
ordinary English with no fitting — `dialogue_preview.py` will catch any line that overruns —
then:

```sh
python3 tools/dialogue_preview.py --check      # no line_too_long
# then read raw-bytes / JP-bytes across the ten. That is the ratio.
```

Ten strings is a far better sample than the one natural example the 2.15x rests on, and it is
translation work that has to happen anyway.

---

## 6. The thing most likely to break, and it is not the scan

**The DTE table is trained on what is eligible.** `build.py` builds its training set from
eligible strings plus the SNES English corpus, weighted by `dte_rom.TRAIN_WEIGHT`. Making 301
dialogue strings eligible will move where the 46 codes get spent — and `TRAIN_WEIGHT = {30:
256}` exists specifically to stop bank 30 losing its fit, which is 73 bytes against 58 needed
today. Expect to re-measure, and expect bank 30 and bank 13 (**+9 bytes spare**) to be the
banks that complain.

Also: the code space is only 46 of a possible 128 because untranslated Japanese still
occupies 179 distinct byte values, and the composer has no gate. That number improves as
translation proceeds, not as this job proceeds — `tools/dte_ranges.py` recomputes it.

---

## 7. Verification checklist

Everything in `HANDOFF.md` → "If picking this up cold", plus:

```sh
sh build.sh                                            # 1498 checks, no problems
python3 tools/dialogue_preview.py --selftest           # 1608 lines, longest 18, 2 known
python3 tools/dialogue_preview.py --check              # 0 with problems
python3 tools/dte_rom.py                               # 5278 segments / 0 mismatches
python3 tools/crashscan.py build/shiren_en.gb --seeds 12   # 0 halts
```

And the two that matter specifically here:

* **A screenshot of newly-compressed bank-11 dialogue.** Byte verification cannot prove the
  renderer expands it, and this is exactly the path that shipped garbage when eligibility was
  guessed by bank. `gbrun.py --walk-seed` now works with `--png`, so this is reproducible —
  see how `build/inn_2495.png` was taken.
* **`--compare` against a pre-change build for the file menu and status screen**, which must
  stay IDENTICAL: nothing in this job should touch a menu.

## 8. One loose end you may trip over

If you scan a build where a bank-11 string has already been **redirected into the pool**, the
address `11:$56A2` reports is the *pool* address, not the string's `loc`, and the allowlist
entry will match nothing. It cannot bite today — bank 11 is untranslated, so nothing there is
redirected — but it will the moment §5's translations land. Either scan before translating,
or map pool addresses back through `build/relocmap.tsv`.
