# Translating Shiren GB

Everything a translator needs, and the rules that decide whether a translation can actually
be inserted. `HANDOFF_NEXT.md` is the current engineering queue; `FINDINGS.md` and
`HANDOFF.md` are lookup references for how the ROM works. None is needed to translate.

> ## CURRENT COMPLETENESS CORRECTION — 2026-08-09
>
> The current manifest is **1,422 records**, not 1,419. Three conservative Nagi interiors,
> `14:$5AFD`, `14:$5B81` and `14:$70BE`, begin inside parent records whose bytes were
> already covered; all have editable English rows. They were observed while the ordinary-
> stair pointer was still corrupt and are retained until a wider route sweep proves no
> independent event enters them. This is why `coverage.py` must not be described as
> proving runtime completeness: it gates framed bytes, known alphabets and declared
> runtime starts, while emulator routes discover unknown starts. Its ten script-bank
> embedded/unframed hits have now been traced to code, pointer tables, graphics or
> animation data and are exact-byte classified as non-text. The older historical status
> block below records how the previous milestones were reached; do not treat its 1,419
> denominator or “zero unextracted” sentence as current.
>
> **Current supplied count: 1,404 / 1,422.** The five visible box-12 name-grid rows are now
> explicit English records. The 18 unsupplied records are all unrendered: six belong to
> aliased page 2 and 12 are non-text extraction records.
>
> `tools/rescuespill.py` verifies those records remain safe but also proves the corrected
> ordinary route does not enter them; it uses shared `Go down / Stay here` instead.

> ## ~~BULK TRANSLATION IS PAUSED~~ — **UNPAUSED 2026-08-05. Both blockers are fixed.**
>
> ~~`script/script.tsv` is not all the text in the ROM.~~ It was ~8.6 KB short, in **two
> separate causes**, both now closed (`HANDOFF_NEXT.md` sessions 7 and 8b). **1261 → 1419
> strings.** The whole shop, the Kuyo Pass road picker and the ending narration were among
> the missing; they are in `script.json` now and they need English.
>
> ~~And the text box currently spills~~ — **FIXED**. Both the column-19 spill and the
> trailing-`<end>` double-draw are gone; `tools/boxspill.py` and `lint_en`'s `end_trailing`
> keep them gone.
>
> Nothing already translated was wasted: `en.tsv` is keyed on `loc`, which survived both
> re-extractions unchanged — verified by re-running `wrap_en.py --apply` and diffing.
>
> **Historical wording, now superseded:** `tools/coverage.py` runs on every build and was
> once described as the check that says whether the script is complete. The current tool
> reports its reviewed non-text list, fails any new or byte-changed script-bank hit, and
> states that route scans remain the runtime discovery mechanism.
>
> **Session 8 then translated all 161 of them (2026-08-05).** `1376 / 1419` after box 48
> landed too. What is left is 23 item-help lines and item verbs for session 9, 11 kana rows
> that belong to the name-entry grid, and 9 extraction false positives that are not text.
>
> **Being translated is not the same as rendering.** Joey found two screens by PLAYING that
> the whole battery calls green: the town signs are not drawn by the composer at all, and
> Fay's Puzzles header has a **second, untranslated copy at `4:$704E`** — a pre-rendered
> tilemap row, so `coverage.py` cannot see it and never could. Both are written up as
> session A in `HANDOFF_NEXT.md`. **If you are about to trust a count on this page, that is
> the thing it does not measure.**

**Read §3 before writing anything.** How much room you have depends on *how the game reaches
the string*, and it varies from "must be same-or-shorter" to "length does not matter at all".
Writing to the wrong one is how this project shipped dialogue that read like a telegram.

---

## 1. The workflow

```sh
python3 tools/wrap_en.py script/prose_draft.tsv --apply   # sentences -> en.tsv lines
sh build.sh                     # base ROM -> English ROM, and checks everything
cat build/worklist.tsv          # anything that did not fit. ABSENT = nothing did
```

**For dialogue, write sentences and let `wrap_en.py` make the lines.** Drafts live in
`script/prose_draft.tsv` as `loc <TAB> english` with no `<br>`, no `<end>` and no indents —
the tool owns all three, and it puts `<end>` exactly where the shipped Japanese does. You
place `<brk>` where the pacing wants a page. It reports `auto_split` when a drafted page
needed more than one box. Do not target a fixed character total: `wrap_en.py` fills each
line up to the real 30-glyph/144px Dot edge.

This is also why the drafts are kept: `<br>` is authored data, so renderer changes do not
re-flow old text by themselves. Re-wrapping against the current font is one command.

`sh build.sh` **never produces a corrupt ROM.** A translation that cannot be inserted is
reported and the original Japanese is kept for that string, so the build always boots. The
worklist is the only place failures appear — a green build is not proof you read it.

| file | what it is |
|---|---|
| `script/script.tsv` | every extracted string: `id`, `loc`, `bytes`, `jp`, `en`. Read-only reference. |
| `script/prose_draft.tsv` | **the file you edit for dialogue.** Sentences; `wrap_en.py` makes the lines |
| `script/en.tsv` | `loc <TAB> english`. Edit directly only for menus and labels — dialogue rows here are generated |
| `script/glossary.tsv` | **the 391 frozen names** — `loc <TAB> class <TAB> jp <TAB> en`. Read it; do not edit it casually. §3b |
| `script/glossary_ok.tsv` | reviewed exceptions to the glossary, one justification each |
| `script/term_uncertainties.tsv` | unresolved monster/NPC names whose available wiki English is unofficial or not an exact Japanese match |
| `build/worklist.tsv` | what failed this build, and why. **Deleted by a clean build**, so "no such file" means no failures |
| `build/shiren_en.gb` | the result |

### Keys are `loc`, never `id`

```
11:$5330	Adventure
```

`loc` is `bank:$address`. **Ids are reassigned by sorted offset**, so any change to
extraction silently shifts an id-keyed file by one entry and every line translates the wrong
string. The build refuses a numeric key for this reason.

---

## 2. Character set

77 glyphs. Letters `A-Z a-z`, digits `0-9`, space, and exactly this punctuation:

```
! ' ( ) + , - . / : ? [ ] ~
```

**There is no `"` and no `;`.** Attribution is written `Name: ` with no quotes — which is
also cheaper than the Japanese `「...」` it replaces. An unavailable character is an `encode`
error, never a silent substitution.

---

## 3. How much room you have — three storage classes

This is the part that matters. The same displayed line can be free, tight, or impossible
depending on which class the string is in.

### A. Redirected — **length is free** (pool-backed dialogue and runtime interior entries)

Village and story dialogue, plus most item and monster names and most of bank 13. If the
English overruns its slot, `build.py` writes a 4-byte redirect record at the original
address and puts the text in a free bank — automatically, with no action from you.

The pool is **483,840 bytes against a ~32 KiB finished script**, and as of 2026-08-03 every
arena also fits at the **ratio-independent floor**: the case where every redirectable string
is redirected, which does not depend on the 2.15x estimate being right. `sh build.sh` says
so on the last line of its projection.

> **Write ordinary, natural English. Do not abbreviate to fit a byte count.**

> ### **Never trail `<end>` or resume printable dialogue after it. 2026-08-10**
>
> A trailing `<end>` makes the composer draw the final box again, identically. Moving that
> token earlier was not a complete fix: with the Dot reveal path, printable English after
> `<end>` can disappear while the unchanged box still consumes a press. Joey caught the
> concrete forms `He went to rescue<end> Fumi!` and `I'm not going up<end> there!`.
>
> In bank-11/14 dialogue, `<end>` may therefore be followed only by `<brk>` or by terminal
> effect controls such as `<mode0>`. Author a semantic pause as `<brk>` in
> `prose_draft.tsv`; never hide `<end>` before a final word or line. `wrap_en.py` no longer
> guesses a last-box placement, and `lint_en` enforces both `end_trailing` and
> `end_resumes_text` during every build.
>
> ### ~~a `<brk>` also costs a press~~ — **RETRACTED 2026-08-05, it does not**
>
> Chasing the above, the first diagnosis was that every extra box costs a press, because a
> box waits iff it holds an `<end>` and every `<brk>` carries one. **Measured head-on
> afterwards, it is false**: a two-box and a one-box rendering of the same text, in the
> same NPC, are both 1 wait and 2 presses. 22 strings were tightened on the strength of it
> and have been reverted. `tools/boxcount.py` still reports the structural divergence — we
> use 261 box breaks to the Japanese's 120 — but that is **pacing, your call**, not a cost.
>
> So adding a `<brk>` really is free, as this section originally said. What is NOT free is
> leaving an `<end>` last.

You may add `<brk>` boxes freely — a translation may use more screens than the Japanese did,
and natural English at ~2.15x usually needs to. What still binds is the **per-line cell
budget** in §4, which is a display limit, not a storage one.

> **Retracted event exception — `14:$5AFD`:** this was inferred while two bank-13 stair
> loads were incorrectly repointed from bank 14's choice to Nagi text. Original-Japanese
> state handoffs proved that Nagi, Koppa and Fumi ordinary stairs all use `14:$46C1` and
> transition after the choice. Do not copy the former terminal `<end><brk>` rule.
>
> The related concrete failure is now a lint rule: if bank-11/14 Japanese dialogue has no
> `<end>`, English may not finish with `<end><brk>`. `14:$7BC2` did exactly that, so talking
> to Koppa rendered the correct phrase, then an empty box, then finally closed. Preserve
> the native `$FF` close instead. `koppatalkspill.py` covers both its real town consumer
> and a dungeon-context compatibility probe.

### B. Still bank-local — **aggregate within their bank** (502 strings)

Menu labels (bank 11's `11:$52E0`, whose reader is the seven bytes the DTE expander already
owns), menu box rows (bank 31), item verbs (bank 30), and the rest. These move, but only
inside their own bank, because the reading code lives there. So the budget is a shared pool
per bank: a string that shrinks donates to one that grows.

**Every one of those banks currently projects positive** — re-measured 2026-08-05 after
sessions 7 and 8b re-extracted 158 more strings into them: bank 11 **+840**, 13 **+4036**, 30
**+1**, 31 **+82**, and the redirect pool +447,332. `bank_full` is not expected any more. If
you see it, report it — it is an engineering task, not a translation error, and the fix is
to hook one more reader.

**Bank 30's +1 is not a typo and it is the one to watch.** 73 bytes held against 72 needed,
so a single character added to an item verb overruns it. `build.sh`'s projection is the
check; it is on screen every build.

### C. Fixed in place — **same-or-shorter, in bytes**

Anything `pinned`, and box rows whose geometry is fixed. Reported as `too_long` or
`box_in_place`.

**How to tell which class a string is in:** don't guess and don't use `script.tsv`'s `bytes`
column — it is the wrong number for the 902 in class A. Derive it from `build.py`'s
`reloc_can` rule, or just write naturally and read `build/worklist.tsv`.

**`build/worklist.tsv` only exists when there is something wrong with it.** A clean build
deletes it, so its absence means "no problems", not "not run yet". It used to be left behind
by whichever build last failed, which made a stale list of BADPOOL strings look current.

---

## 3a. Control tokens — the one thing that fails SILENTLY

`<var>`, `<name>`, `<cE3>` and `<cF0:xx>` inject runtime data: a monster name, the player's
name, a table string. **A translation that drops one encodes cleanly, inserts cleanly, and
passes every reference check and crash seed — and then prints "The  attacked!" on screen.**

`tools/lint_en.py` checks token parity against the Japanese and `build.py` fails the string
rather than shipping it. Rules:

| token | rule |
|---|---|
| `<var>` `<name>` `<cE3>` `<cE4>` `<cF0:xx>` `<cE0:xx>` `<cE7:xx>` `<cEC:xx>` `<mode0>` `<mode1>` `<cF1>` `<cF2>` `<cF3>` `<cF4>` | **must survive exactly** — same tokens, same arguments, same counts |
| `<br>` `<brk>` `<end>` | **yours** — line breaks and pagination are a translation decision |
| `<$XX>` | raw layout bytes; covered by `escape_is_dte_code`, not by parity |

Order is deliberately **not** checked: `<var> dodged the blow` and `Shiren attacked <var>`
are both fine. Only the multiset matters.

> ### `<cEC:xx>` IS THE ONE TOKEN WHOSE POSITION MATTERS: it must stay FIRST
>
> It opens a signboard, a shop confirmation, a help menu or a road picker, and it is the
> only token the ROM reads out of a fixed position rather than out of the stream:
> `13:$67F3` tests the FIRST byte of the staged line for it, and `13:$6C73` then resumes
> reading at "the message's own address, plus 2". So its two bytes have to be the first two
> bytes at that address, and `build.py` writes the redirect record after them rather than
> over them. Move it, and the message resumes inside the record and draws one stray glyph.
>
> `build.py`'s `ec_prefix_lost` fails the build if that happens, and `pool.head_bytes()`
> refuses a translation whose `<cEC:xx>` is not leading. **Keep it where the Japanese has
> it**, argument and all — the argument picks the box. See HANDOFF_NEXT.md session A1.

```sh
python3 tools/lint_en.py            # check script/en.tsv
python3 tools/lint_en.py --tsv      # machine-readable, for a repair pass
```

## 3b. The glossary — names are decided already

**391 item, monster and NPC names are frozen in `script/glossary.tsv` (last series audit
2026-08-10).** If
the Japanese you are translating names one of them, your English uses the frozen rendering.
Not a preference — `tools/lint_en.py` fails on it (`term_ignored`) and names the string.

```sh
python3 tools/lint_en.py          # token parity AND glossary adherence
grep こんぼう script/glossary.tsv  # what is this thing called
```

Both the lint and the build take `--glossary PATH`, so a review copy is a first-class
build and never has to be merged by hand:

```sh
python3 tools/lint_en.py --glossary script/glossary_mine.tsv
python3 tools/build.py build/_base_expanded.gb script/en.tsv build/mine.gb \
        --glossary script/glossary_mine.tsv
```

**Editing it in OSX Numbers is supported.** Numbers pads every line out to the widest row
with tabs and wraps any line containing a comma in double quotes — which here means the
comment block, so the file stops starting with `#`. Both loaders absorb exactly that (see
`lint_en.spreadsheet_line`). A quoted or padded field in the DATA still fails loudly,
because there it means something broke rather than something was reformatted.

The reason is the one failure review cannot catch. `こんぼう` is an item name, a line of
help text, a combat message and a shop's dialogue; translated batch by batch it becomes
Club, then Cudgel, then Stick, and noticing means holding 1,419 strings in your head.

**The style, so a new name matches:** modern official-Shiren English, plain and
meaning-first — `ひとつめゴロシ` is `One-Eye Killer`, not `Hitotsume Goroshi`. Category
nouns are **Herb / Bracer / Staff / Pot / Scroll**. Tier families read as families: Rat
Minion, Rat Boss, Rat Kingpin. Proper nouns that mean nothing in Japanese either stay
transliterated — Mamel, Gazer, Chintala, Orochi.

For monster/NPC terminology, prefer an exact Japanese match from the newest official
English Shiren represented by the Mystery Dungeon Franchise Wiki, then Shiren 1 DS, then
an established unflagged Moonlight Village name, then the completed Shiren 2 N64 fan
patch. A wiki row marked `UT` is evidence to review, not official terminology. Keep the
current frozen choice and record the question in `script/term_uncertainties.tsv` rather
than silently adopting it.

**When the glossary is wrong, change the glossary** — one cell, then re-run the lint and
fix what it names. That is what happened to `おかみ`: frozen as *Landlady*, while the
reviewed innkeeper speech had already made her *Innkeeper*.

**When the English is right and the glossary is also right**, you have an address rather
than a name — `おかみさん` in Keyaki's mouth is "Ma'am". Add a line to
`script/glossary_ok.tsv` with a sentence of justification. If that file grows past a
handful of entries, the glossary has the wrong name in it and the exceptions are hiding it.

## 4. Rendering budgets — pixels, source, tiles and runtime values

Dot Gothic makes the old “one character equals one cell” rule obsolete. Byte counts are
still storage, not display, but a character count alone is no longer a display verdict
either. Every path has four separate limits: physical pixels, the current source-staging
loop, temporary composed tiles, and runtime suffix/substitution values. The measured
register is [`VWF_BUDGETS.md`](VWF_BUDGETS.md).

> **Do not shorten English merely because a source guard fires.** First ask whether the
> physical Dot text fits. `Put down Accurate Sword-77` is the concrete example that drove
> the reset: all 26 glyphs and 134 painted pixels now fit. Joey's final four-column `4`
> and `7` make every formerly hostile Accurate Sword `±44/±47/±74/±77` Stepped
> line an exact 144px edge fit. V4A still owns the complete runtime-value census.

### Dialogue: 144 pixels, 3 lines, up to 30 staged glyphs

The composer owns 18 tiles = 144px per line and three lines per box. The uniform VWF first
used a 6px pen and therefore expressed this as 24 characters. The current Dot renderer
stages and typewriter-maps as many as **30**, then clips at the unchanged 144px edge. This
is deliberately permissive: a narrow 30-glyph line can fit, while a wide line can run out
of pixels much earlier. The build checks both limits using painted extent.

```
Innkeeper: Ah, you<br> are awake at last!<br> You were crying<end><brk>
```

- `<br>` ends a line. Three lines fill a box.
- `<brk>` ends a box and waits for the player.
- `<end>` marks end of message. It is commonly paired with `<brk>`, but event-specific
  ordering must match the measured caller; see the `$5AFD` stairs exception above.
- A leading space on continuation lines is the ROM's own indent style. Keep it.

> **Text does not pixel-wrap at runtime.** The stager can insert an automatic source break
> at 30 glyphs, but it cannot see Dot widths; anything beyond 144 painted pixels is clipped.
> Prefer explicit `<br>` where a sentence should break. `dialogue_preview.py` and the
> normal build enforce the 30-glyph and 144px limits together.

**You do not have to count cells by hand. Draw the box:**

```sh
python3 tools/dialogue_preview.py 14:$5047     # one string, as the screen will draw it
python3 tools/dialogue_preview.py --check      # every translated line; exit 1 if any overrun
```

```
    +------------------------------+
    |Innkeeper: Ah, you             |
    | are awake at last!            |
    | You were crying               |
    +------------------------------+
       (player presses A)
```

Over-long source lines are shown with the text that falls off marked `<< LOSES '...'`, and
**`sh build.sh` fails on them** (`line_too_long`) instead of shipping them. Run
`tools/fontaudit.py` as well for physical pixels and runtime-value warnings.

Boxes hold **three** lines and there is no fourth — the ROM reserves exactly 54 tiles, three
rows of 18 tiles — so a fourth line overwrites the first (`box_too_deep`). Split with `<end><brk>`;
extra boxes are free.

Keep boxes aligned to sentences the way the Japanese does, rather than letting a wrapper
break them mid-clause.

### Item descriptions: 144 pixels, FOUR lines — a different renderer

**The 122 strings reached through `13:$554A` are not composer dialogue.** They are staged
by `13:$7E49` into `$C616` and drawn by bank 31 as box 7, whose descriptor is `x=0, y=3,
5 rows, width 18`. Row 1 holds the item name, so the description gets **four 144px rows**.
Menu VWF renders this path proportionally and its measured scanner accepts **21 source
glyphs**. The production TSV now uses that real Dot contract; the 18-cell fixed-width
build remains a diagnostic control and no longer dictates English wording.

`dialogue_preview.py <loc>` knows which geometry a string is on and checks both its
21-glyph scanner and the Dot 144px painted edge.

```
    +------------------+          -Pickaxe-        <- the item name, row 1
    |Equip to dig walls|
    |and raise attack. |
    |It wears out after|
    |a few digs.       |
    +------------------+
```

- **`<brk>` is a PAGE, and the page count must match the Japanese.** The unit selector at
  `13:$7E0D` pages by counting `$EE`/`$FF` markers, so adding or dropping one changes what
  the player can reach. Tighten the English instead. (This is the opposite of dialogue,
  where extra `<brk>` boxes are free.)
- **`<cF0:xx>` pastes one of 13 shared lines from `11:$55AC` inline** — real text, not a
  screen effect, and it spends its own source glyphs and pixels. `<cF0:00>` is `Raises attack.`
  Those 13 are ordinary script strings and are translated in `en.tsv` like anything else;
  `<cF0:03>` (`Equip:`) is the only one that shares a line, leaving 15 of the current 21
  staged glyphs plus the remaining pixel width for the rest.

### The item list: 128 pixels, current 17-source-character guard

The 18-tile inventory row has two raw cells before proportional text, leaving a **128px
name payload**. The current source scanner accepts at most 17 glyphs. Runtime variants
matter: weapons and shields can add any signed value from `-99` through `+99`; staffs and
pots add `[1]` through `[99]` in ordinary play.

After the approved compact-digit edits, `Accurate Sword-99` is exactly 17 source characters,
advances 88px, paints 87px and needs 11 tiles. It deterministically represents the broad
144-way tie at the signed two-digit suffix peak. It therefore fits with 41px of real slack.
This is the measurement that disproved the old
14-character equipment-name “visual limit.” The allocator regression at the first row of
either page is also fixed; `menuspill --long` now packs five 11-tile item rows and four
4-tile verbs into 71/72 temporary tiles.

`lint_en.py` fails a staff/pot whose name plus ordinary two-digit counter crosses the real
17-glyph scanner. `fontaudit.py` separately enumerates every current bare/signed/`[NN]`
variant against both that source guard and the 128px painted payload.

### Menus: the box's own pixel width

Each menu box has a width in `script/box_geometry.tsv`; approved raw cursor/prefix cells
keep their full 8px and the remaining payload uses Dot advances. Current physical shapes:

| box | text span |
|---|---|
| title / file menu | descriptor width minus one raw cursor tile |
| difficulty | measured per approved ROM row |
| places | measured per approved ROM row |
| item action menu | 8 tiles = 64px — boxes 6 and 39 |

`box_too_wide` protects the shared source geometry; `fontaudit.py`, `menuspill.py` and
`menuromspill.py` protect physical rows and allocation.

The 40 clear-condition labels at `14:$7C78-$7ED8` are a measured menu path of their own:
five 144px rows in box 44, up to 21 source glyphs each. `fontaudit.py` checks every row and
the worst possible current group of five; `conditionspill.py` executes the real box,
allocator, VBlank queue and tilemap with both that group and an exact 21-glyph fixture.
The font has no percent glyph, so write `Max Belly 200`, not a raw native `<$B1>` tile.

### Substitution: `<var>` is where the cells really go

Combat lines are stored as fragments and the name is injected at runtime, so the literal
English is the small part:

| string | literal source glyphs | left before the 30-glyph ceiling |
|---|---|---|
| `<var> hit <var>` | 5 | 25, for **both** names |
| `<var> hit you` | 8 | 22 |
| `Defeated <var>!` | 10 | 20 |
| `<var> is now Lv<cE4>!` | 11 | 19 minus the digits |

**The old 14-character `<var>` and 16-character `<cE3>` reservations are under audit.**
They were obtained by adding six characters to pre-VWF decrees, not by measuring Dot
Gothic or enumerating each runtime producer. They are no longer glossary lint limits;
`fontaudit.py` retains them only as labelled historical warnings while reporting real Dot
pixels. The player name's six characters *are* a storage/input contract (`tools/name6.py`).

**This one is a warning, not a build failure, and the reason is worth knowing.** What lands
in a `<var>` is a runtime value, and the Japanese itself does not respect the cap: `<var>は
モンスターにかこまれた！` is 14 literal cells and leaves **4** for a monster name, so the
original game truncates that line too. The build therefore fails a line only when it
overruns with every substitution charged just **one** cell — an overrun no runtime value
could rescue. Everything tighter is reported as headroom:

```sh
python3 tools/dialogue_preview.py --selftest   # the tightest lines in the whole script
```

Use the report to identify templates that need runtime census. The final name policy must
combine each template's actual value class, source contract and Dot pixels; the tightest
unrelated line does not by itself define every name.

---

## 5. Control tokens

Write them as `<name>`. They round-trip with what `script.tsv` prints in the `jp` column, so
you can copy a token straight out of the Japanese.

| token | meaning |
|---|---|
| `<br>` | end of line |
| `<brk>` | end of box, wait for the player |
| `<end>` | end of message |
| `<var>` | a name pulled from the message queue |
| `<name>` | the player's name |
| `<cE4>` | a number (level, damage, …) |
| `<cE0:XX>` | sound trigger, argument in hex |

`<$XX>` emits a raw byte verbatim. **It means "layout, reproduce exactly"** — a column
divider, a border glyph — not text. Use a named token whenever one exists; a stray `<$XX>`
in the compression range is a build error (`escape_is_dte_code`), and getting it wrong once
took the status screen to a white screen.

Two reserved bytes you will never write but should know exist: **`$E9`** marks a redirect
record, and the compression codes occupy part of `$92-$DF`. The build checks both.

---

## 6. Worklist errors, and what to do about each

| kind | meaning | what to do |
|---|---|---|
| `too_long` | in-place string over its byte budget | class C: shorten. Class A should never produce this — report it |
| `line_too_long` | a line crosses the current source-character guard — the screen would discard the rest even if its Dot pixels fit | re-wrap ordinary prose; for a physically fitting runtime template, report the source path for engineering |
| `line_too_wide_px` | staged text paints beyond the renderer's measured pixel edge | add an explicit `<br>` or revise the wording; source slack cannot recover clipped ink |
| `box_too_deep` | more than 3 lines in one box — line 4 overwrites line 1 | split with `<end><brk>`; extra boxes are free |
| `buffer_overrun` | one line stages more bytes than the composer clears at `$CF07` | shorten the line; you will hit `line_too_long` first in practice |
| `box_too_wide` | more cells than the box width | shorten, or widen the box (`box_geometry.tsv`, an engineering change) |
| `box_in_place` | pinned box row, and no English fits its byte count | **suspect the PIN first.** Three of the five pinned boxes were pinned by a `ld bc,nn` that reaches `0:$028B` — a bank-13 message push whose operand only *looked* like a pointer into bank 31. Fixed 2026-08-05; if you see this, check the load site before accepting it |
| `end_lost` | the Japanese ends the message and the English does not — **the box never closes** | put `<end>` back. It costs one byte and is not optional, however tight the budget |
| `bank_full` | the bank's shared arena ran out | not your fault — report it |
| `pool_full` | the redirect pool ran out | not your fault — report it |
| `encode` | a character with no glyph | see §2 |
| `escape_is_dte_code` | a `<$XX>` inside the compression range | use a named token |
| `BADREF` / `BADPLACE` | a string does not read back from the ROM | **a tool bug — stop and report** |

---

## 7. What the build does NOT check

Be aware of these; they will not fail a build.

1. **Whether every substitution variant fits.** The literal and minimum-value text are
   checked; the complete `<var>`/`<cE3>` producer-to-template census is still open. See §4
   and `VWF_BUDGETS.md`; legacy reservations are warnings, not final limits.
2. **Whether the text is any good in context.** Nothing knows who is speaking.
3. **That a screen was ever displayed.** There is no coverage report of which strings have
   been seen rendered.
4. **Tone and consistency** across 1,422 manifested records.

~~Dialogue line width.~~ **Closed 2026-07-31** — `line_too_long` fails the build, and
`dialogue_preview.py` draws the box.

One decoding hazard, small but real, and **session 7's re-extraction roughly doubled it**:
in banks 11 and 14 the codes `<cE3>` (10 strings) and `<mode1>` (**33**, was 17) each take
an **argument byte** that `script.tsv` prints as an ordinary character — a stray digit after
`<cE3>`, a stray kana after `<mode1>`. It is a pause length or an item selector, not text.
**Leave it alone**; do not "tidy" a character that follows one of those two tokens.
Engineering detail in `FINDINGS.md` → "The composer has TWO dispatch tables".

`<cF1>`-`<cF4>` are new in the token list as of 2026-08-05 and appear only in banks 11/14.
They take no arguments. They exist because those banks dispatch through a table with 21
entries where bank 13's has 17 — see `FINDINGS.md`. Treat them like `<mode0>`/`<mode1>`:
carry them through untouched, in the same order.

**`<cF0>` and `<cE7>` are written WITHOUT an argument in banks 11/14, and WITH one
everywhere else.** That is not a style choice: on the dialogue path those two codes take no
argument, so the byte after one is ordinary text. `codec.arity_for(bank)` decides, the
`jp` column already shows the right form, and copying the token out of it is correct in
both places. It was measured against the ROM's own staging loop on 2026-08-05 — before
that, `<cF0:56>ギ` was hiding the ナ of `ナギ`. `FINDINGS.md` → "The arities are MEASURED".

This is also why `dialogue_preview.py --selftest` reports eight bank-11/14 lines at 19–21
cells and calls them KNOWN: the cell model charges that argument byte as a glyph, on
purpose, because it keeps `codec.ARITY` so it measures the same bytes the inserter writes.
Every one of those lines lands on exactly 18 once its `<mode1>` count comes off.

---

## 8. Tooling that does not exist yet

Listed so nobody assumes it is there.

- **A translator export with budgets and context.** `script.tsv` gives you `bytes`, which is
  the wrong number for almost everything above. It should carry each path's source/pixel/
  tile contract, the storage class from §3, speaker/screen, and conversation ordering.
- ~~A dialogue preview / build check~~ — **built 2026-07-31**, `tools/dialogue_preview.py`.
- ~~A lint mode that checks `en.tsv` without a full ROM build~~ — **built**:
  `lint_en.py`, `dialogue_preview.py --check`, and `fontaudit.py`. The live emulator spill
  tests still require a built ROM because allocation and VBlank behavior are runtime facts.
- **Runtime name substitution census.** Pixel-aware source staging is now 30 glyphs with a
  separate 144px painted-edge check, and the old `over_cap` decree is gone. Current item
  signed/`[NN]` variants are exhaustive; `<var>`/`<cE3>` producer scope remains open.
