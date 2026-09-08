# Text reference — Shiren GB

The measured rules behind the translation: the character set, how much room each string
actually has, the control tokens, the per-renderer pixel budgets, every worklist error, and
what the build does **not** check.

**Start at [`script/README.md`](../script/README.md).** That page tells you which file to
open for each kind of text and the rules that matter while you write. This page is what you
come to when you need the underlying measurement or the full error list.

Section numbers are stable — other files cite `docs/TEXT_REFERENCE.md §4` and `§7` — so do
not renumber them.

**Current contract reviewed 2026-09-08.** Production uses **Thin Pixel-7 GB Compact**.
The checks below use the same approved font as insertion; historical Dot Gothic and
fixed-width measurements do not define current translation limits.

| Subject | Implementation source |
|---|---|
| Encodable glyphs and approved pixels | `tools/latinfont.py:EN_CODES`, `tools/dotfont.py:load_approved`, `assets/fonts/thin_pixel_7_compact.json` |
| Control syntax and argument counts | `tools/codec.py:arity_for`, `tools/build.py:encode_en` |
| Token parity, close rules and glossary checks | `tools/lint_en.py` |
| Native indents and selector spaces | `tools/textlayout.py` |
| Prose wrapping and verbatim draft rows | `tools/wrap_en.py` |
| Dialogue/help/seal source and pixel limits | `tools/dialogue_preview.py` |
| Item/menu variants and shared tile budgets | `tools/fontaudit.py`, `tools/menuvwf.py`, `script/build-inputs/box_geometry.tsv` |
| Storage eligibility, reserved text windows and fatal insertion errors | `tools/build.py`, `tools/pool.py`, `docs/ROM_BANK_MAP.md` |
| Queued-fragment break prohibition | `tools/healfragmentspill.py` |

Use these sources and their regression evidence when updating a rule or building an
editor. A browser preview must distinguish a known failure from an unresolved runtime
value; it cannot confer emulator or visual acceptance.

---

## 2. Character set

77 glyphs. Letters `A-Z a-z`, digits `0-9`, space, and exactly this punctuation:

```
! ' ( ) + , - . / : ? [ ] ~
```

**There is no `"` and no `;`.** Attribution is written `Name: ` with no quotes — which is
also cheaper than the Japanese `「...」` it replaces. An unavailable character is an `encode`
error, never a silent substitution.

This is the current ROM encoding, not general Unicode support. Additional languages may
need glyph, encoding, input and renderer changes before their text can be built.

---

## 3. How much room you have — three storage classes

This is the part that matters. The same displayed line can be free, tight, or impossible
depending on which class the string is in.

### A. Redirected — **shared text pool** (approved readers and runtime interior entries)

Village and story dialogue, plus most item and monster names and most of bank 13. If the
English overruns its slot, `build.py` writes a 4-byte redirect record at the original
address and puts the text in an approved text window — automatically, with no action from you.

The accepted translation has substantial pool headroom. Capacity is derived from
`tools/pool.py:TEXT_WINDOWS`, including code/graphics exclusions recorded in
[`ROM_BANK_MAP.md`](ROM_BANK_MAP.md). Use the current build report for allocation and
projection figures; older aggregate sizes and bank-spare snapshots are not budgets for a
new translation. `romtextcheck.py` verifies allocation across every reserved text window.

> **Write ordinary, natural English. Do not abbreviate to fit a byte count.**

> ### **Dialogue: avoid extra final waits and printable text after `<end>`**
>
> Adding a trailing `<end>` where the source has no such ending makes the composer draw
> the final box again, identically. Moving that token earlier was not a complete fix:
> with the proportional reveal path, printable English after `<end>` can disappear while
> the unchanged box still consumes a press. Joey caught the
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
> and were reverted. That historical comparison counted 261 English box breaks to the
> Japanese's 120; it is evidence about that route's pacing, not a current script count.
>
> So adding a `<brk>` really is free, as this section originally said. What is NOT free is
> leaving an `<end>` last.

Ordinary prose may use more boxes than the Japanese, subject to its source close behavior.
The **source and pixel limits** in §4 still apply. Queued fragments and item descriptions
have different break/page rules; do not apply prose pagination to them.

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

### B. Bank-local — **aggregate within the verified bank arena**

Movable labels and menu rows can be repointed within their reader's bank. Sequential box
rows move as a unit. Some attributed readers can also consume redirect records and move
the text into class A; `build.py` derives that eligibility from the current reference
allowlist and installed hooks. A bank number alone does not identify a storage class.

`bank_full` means the actual allocator could not place the bank's units. Report it for
engineering review; do not impose an old bank-30 “one spare byte” limit on item verbs.

### C. Fixed in place — **same-or-shorter, in bytes**

Records without a safe relocation/redirect path retain their byte budget. Pinned box rows
also have to preserve the following row's start. A pinned address may still contain an
approved redirect, so `pinned` alone does not prove the translated body is byte-capped.
Failures are reported as `too_long` or `box_in_place`.

**How to tell which class a string is in:** don't guess and don't use `script.tsv`'s `bytes`
column as an English limit. Check `build.py`'s placement and `reloc_can` rules together
with `pool.eligible()`, or write naturally and inspect the current build diagnostics.

**Rejected translations fail insertion.** Collected text/reference errors make `build.py`
exit nonzero before writing the ROM or its relocation map. With `--report`, it writes the
failure worklist; `sh build.sh` supplies `--report build/worklist.tsv`. Successful insertion
removes a stale worklist. Missing reports cannot prove that the build ran, and later
font/runtime gates may fail after insertion succeeded. Check the whole command's exit status.

---

## 3a. Control tokens — parity and runtime meaning

`<var>`, `<name>`, `<cE3>` (or dialogue `<cE3:xx>`) and `<cF0:xx>` inject runtime data: a monster name, the player's
name, a table string. Dropping one may still encode, but loses runtime data. Token lint
exists to catch this semantic failure before it can be shipped.

`tools/lint_en.py` checks token parity against the Japanese and `build.py` fails insertion
on a rejected translation. Rules:

| token | rule |
|---|---|
| `<var>` `<name>` `<cE3>` / `<cE3:xx>` `<cE4>` `<cF0:xx>` `<cE0:xx>` `<cE7:xx>` `<cEC:xx>` `<mode0>` `<mode1>` `<cF1>` `<cF2>` `<cF3>` `<cF4>` | **must survive exactly** — same tokens, same arguments, same counts |
| `<br>` `<brk>` `<end>` | layout/close controls; follow the path-specific rules in §4, including help page counts and the queued-fragment break prohibition |
| `<$XX>` | raw bytes; not protected by token parity; preserve approved structural/effect sequences and avoid DTE-code collisions |

The lint compares a **multiset**, not a sequence. This permits moving text around a token;
it does not prove that changing substitution order or effect sequencing is safe. Preserve
the producer/consumer contract. Two identical `<var>` tokens can consume different actors
in order even though swapping their grammatical roles leaves the lint result unchanged.

> ### A leading bank-11/14 `<cEC:xx>` must stay first
>
> It opens a signboard, a shop confirmation, a help menu or a road picker, and it is the
> dialogue prefix the ROM reads out of a fixed position rather than out of the stream:
> `13:$67F3` tests the FIRST byte of the staged line for it, and `13:$6C73` then resumes
> reading at "the message's own address, plus 2". So its two bytes have to be the first two
> bytes at that address, and `build.py` writes the redirect record after them rather than
> over them. Move it, and the message resumes inside the record and draws one stray glyph.
>
> `build.py`'s `ec_prefix_moved` / `ec_prefix_lost` fail the build if that happens, and `pool.head_bytes()`
> refuses a translation whose `<cEC:xx>` is not leading. **Keep it where the Japanese has
> it**, argument and all. This prefix rule is scoped by `pool.starts_ec()`; bank 13 uses
> a different control path.

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

Thin Pixel-7 GB Compact makes the old “one character equals one cell” rule obsolete. Byte counts are
still storage, not display, but a character count alone is no longer a display verdict
either. Every path has four separate limits: physical pixels, the current source-staging
loop, temporary composed tiles, and runtime suffix/substitution values. The measured
register is [`VWF_BUDGETS.md`](VWF_BUDGETS.md).

> **Both source and pixel limits must pass.** A physically fitting line can still exceed
> its scanner. Re-wrap prose or review the measured source path before shortening a
> runtime template; do not weaken a guard to accept it. Old font-specific examples are
> historical evidence, not limits for the approved font.

### Dialogue: 144 pixels, 3 lines, up to 30 staged glyphs

The composer owns 18 tiles = 144px per line and three lines per box. The uniform VWF first
used a 6px pen and therefore expressed this as 24 characters. The current proportional renderer
stages and typewriter-maps as many as **30**, then clips at the unchanged 144px edge. This
is deliberately permissive: a narrow 30-glyph line can fit, while a wide line can run out
of pixels much earlier. The build checks both limits using painted extent.

```
Innkeeper: Ah, you<br> are awake at last!<br> You were crying<end><brk>
```

- `<br>` ends a line. Three lines fill a box.
- `<brk>` creates a page/window boundary; input behavior depends on the caller.
- `<end>` sets the message wait/end flag. It is not the physical `$FF` string terminator.
  Preserve source close behavior and the lint rules in §3/§3a; the former `$5AFD` stairs
  exception is retracted.
- The wrapper adds continuation indents. `textlayout.py` retains a native first-line
  space and expands selector continuation spacing to preserve the cursor slot. Each
  rendered space consumes source capacity and font advance; do not trim structural spaces.

> **Text does not pixel-wrap at runtime.** The stager can insert an automatic source break
> at 30 glyphs, but it cannot see proportional widths; anything beyond 144 painted pixels is clipped.
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

**Descriptions reached through `13:$554A` are not composer dialogue.** They are staged
by `13:$7E49` into `$C616` and drawn by bank 31 as box 7, whose descriptor is `x=0, y=3,
5 rows, width 18`. Row 1 holds the item name, so the description gets **four 144px rows**.
Menu VWF renders this path proportionally and its measured scanner accepts **21 source
glyphs**. The production TSV uses that proportional contract; the 18-cell fixed-width
build remains a diagnostic control and no longer dictates English wording.

`dialogue_preview.py <loc>` knows which geometry a string is on and checks both its
21-glyph scanner and the approved font's 144px painted edge.

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
  the actual selected fragment, including any authored space, must be included in the
  21-glyph and 144px measurements. Do not assign every `<cF0:xx>` a fixed placeholder cost.

Equipment seals use the same 144px/21-glyph row contract, but each seal gets **one row**.
Clear-condition lists show **five** such rows. Validate the entire visible group against
the shared tile allocator as well as measuring individual rows.

### The item list: 128 pixels, 18-source-glyph guard

The 18-tile inventory row has two raw cells before proportional text, leaving a **128px
name payload**. The current source scanner accepts at most 18 glyphs. Runtime variants
matter: weapons and shields can add any signed value from `-99` through `+99`; staffs and
pots add `[1]` through `[99]` in ordinary play.

The 2026-09-08 font audit measures the widest current item variant, `Battle Counter-99`,
at 17 source glyphs, 84 painted pixels and 11 tiles. Five widest current rows plus four
4-tile verbs use 71/72 temporary tiles. These are measurements of the current glossary;
a new name must pass its own suffix and allocation checks. Plating, curses, fusion counts,
player-assigned names and shop prices also have dedicated runtime regressions.

`lint_en.py` fails a staff/pot whose name plus ordinary two-digit counter crosses the real
18-glyph scanner. `fontaudit.py` separately enumerates every current bare/signed/`[NN]`
variant against both that source guard and the 128px painted payload.

### Menus: the box's own pixel width

Each menu box starts with its extracted descriptor width and applies any override in
`script/build-inputs/box_geometry.tsv`. Approved raw cursor/prefix cells keep their full
8px; the remaining payload uses approved font advances. Current physical shapes:

| box | text span |
|---|---|
| title / file menu | descriptor width minus one raw cursor tile |
| difficulty | measured per approved ROM row |
| places | measured per approved ROM row |
| item action menu | five interior tiles (40px), including one 8px cursor cell; **32px text payload** — boxes 6 and 39 |

`box_too_wide` protects the measured source scanner; approved narrow proportional rows
can scan beyond their descriptor's native cell count. `fontaudit.py`, `menuspill.py` and
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

**The old 14-character `<var>` and 16-character `<cE3>` reservations are historical warnings.**
They are not glossary lint limits or proven producer maxima. `fontaudit.py` reports them
separately from actual source/pixel failures. The player name's six characters are a
measured storage/input contract (`tools/name6.py`).

**This one is a warning, not a build failure, and the reason is worth knowing.** What lands
in a `<var>` is a runtime value, and the Japanese itself does not respect the cap: `<var>は
モンスターにかこまれた！` is 14 literal cells and leaves **4** for a monster name, so the
original game truncates that line too. Unknown producers are checked at their minimum
contribution. The settled player name reserves six glyphs and its widest approved pixel
footprint; help fragments use their actual translated expansion. Additional audits cover
known item variants and selected message families. A minimum-value pass alone does not
prove every unresolved runtime substitution fits:

```sh
python3 tools/dialogue_preview.py --selftest   # the tightest lines in the whole script
```

Use the report to identify templates that need runtime census. The final name policy must
combine each template's actual value class, source contract and approved font pixels; the tightest
unrelated line does not by itself define every name.

---

## 5. Control tokens

Write them as `<name>`. They round-trip with what `script.tsv` prints in the `jp` column, so
you can copy a token straight out of the Japanese.

| token | meaning |
|---|---|
| `<br>` | end of line |
| `<brk>` | page/window boundary; caller-specific input behavior |
| `<end>` | message wait/end flag; distinct from the `$FF` string terminator |
| `<var>` | a name pulled from the message queue |
| `<name>` | the player's name |
| `<cE4>` | a number (level, damage, …) |
| `<cE0:XX>` | sound trigger, argument in hex |

`<$XX>` emits a raw byte verbatim. It can represent structural layout or a byte retained
in a reviewed effect sequence. Use a named token whenever one exists; a stray `<$XX>`
in the compression range is a build error (`escape_is_dte_code`), and getting it wrong once
took the status screen to a white screen.

Two reserved bytes you will never write but should know exist: **`$E9`** marks a redirect
record, and the compression codes occupy part of `$92-$DF`. The build checks both.

---

## 6. Worklist errors, and what to do about each

Insertion writes collected errors to the requested worklist. Standalone lint, font,
cinematic and runtime checks also report their own diagnostics; this table covers the
main translator-facing failures, not every installer assertion.

| kind | meaning | what to do |
|---|---|---|
| `too_long` | fixed string exceeds its byte budget | verify its storage class; revise wording or request an engineered relocation path |
| `line_too_long` | source scanner would discard glyphs even if the pixels fit | re-wrap ordinary prose; review a runtime template's source path |
| `line_too_wide_px` | painted text exceeds the pixel edge | re-wrap where breaks are legal, or revise wording |
| `box_too_deep` | row count exceeds this renderer's geometry | prose can paginate; help must preserve page count and seals must stay on one row |
| `buffer_overrun` | staged data reaches/exceeds the path's cleared buffer | inspect the reported scope and controls; revise or review the renderer |
| `box_too_wide` | a menu row exceeds its measured source scanner | revise the row or engineer and verify a geometry/scanner change |
| `box_in_place` | pinned box row cannot preserve the next row's start | verify the consuming reference and pin before accepting a byte limit |
| `token_lost` / `token_added` | significant token count or argument differs | restore the source token contract |
| `end_lost` | source has an end/wait flag but the translation has none | restore the source close behavior through the draft/wrapper or reviewed controls |
| `end_trailing` | translation adds a final `<end>` absent from the source ending | remove the duplicate final wait; use a legal page boundary or structural terminal effect sequence |
| `end_resumes_text` | printable bank-11/14 dialogue follows `<end>` without a page boundary | place the intended semantic pause at `<brk>` in the draft |
| `end_before_terminal_brk` | terminal `<end><brk>` added to dialogue whose source has no `<end>` | preserve its native `$FF` close; do not add an empty final page |
| `ec_prefix_moved` / `ec_prefix_lost` | required dialogue prefix no longer leads | restore the leading `<cEC:xx>` and its argument |
| `counter_overflow` | item name plus two-digit counter exceeds 18 source glyphs | measure the full name/suffix in the item renderer |
| `term_ignored`, `glossary_split`, `glossary_collision` | terminology differs from the reviewed glossary contract | correct the glossary/usage or record a justified exception |
| `bank_full` / `pool_full` | allocator cannot place text in approved space | report for engineering review; inspect the current allocation report |
| `encode` | unsupported character, token or argument form | use the current character set and bank-specific control syntax |
| `escape_is_dte_code` | raw byte collides with compression codes | restore the approved byte/token; changing reservations requires engineering |
| `dte_roundtrip`, `BADREF`, `BADPLACE`, `BADPOOL` | compression or inserted references do not reproduce the expected bytes | stop and investigate the toolchain/reference failure |

---

## 7. What the build does NOT check

Passing the implemented checks leaves these limits:

1. **Whether every substitution variant fits.** The literal and minimum-value text are
   checked; the complete `<var>`/`<cE3>` producer-to-template census is still open. See §4
   and `VWF_BUDGETS.md`; legacy reservations are warnings, not final limits.
2. **Meaning, speaker, tone and pacing.** Glossary lint checks selected terms; it cannot
   establish that a scene reads correctly or that queued actors retain their intended roles.
3. **Complete route coverage.** Static coverage, live scans and save-backed fixtures cover
   known paths. They cannot prove that every event or interior entry has been discovered.
   See the current README for the accepted release battery and remaining manual playtest.

Control decoding is path-specific, so a validator must pass the record's bank to
`codec.arity_for(bank)`. The current encoded forms are:

| Control | Banks 11/14 dialogue | Default message path |
|---|---|---|
| Item substitution | `<cE3:xx>`; selector is already inside the token | `<cE3>` |
| E7 / F0 | `<cE7>` / `<cF0>` | `<cE7:xx>` / `<cF0:xx>` |
| F1–F4 | `<cF1>` through `<cF4>`, no arguments | not ordinary message-path controls |

The codec currently models `<mode1>` as zero-argument. Some reviewed translations retain
an adjacent raw byte such as `<mode1><$3C>`; preserve that sequence. `codec.py` records a
native skip-chain/handler discrepancy, so parity or encoder acceptance alone cannot
authorize deleting, translating or moving the following byte. The former blanket rule
that both `<cE3:xx>` and `<mode1>` always have an extra argument printed as text was
incorrect. Consult the actual consuming path before changing a reviewed effect sequence.

---

## 8. Translator tooling and remaining gaps

**Implemented prose proof of concept:** [Prose Studio](../site/prose/README.md) has
480 prose/reference records in 25 draft-derived event groups, including 436 editable
ordinary drafts. It supports local Japanese-source import, font-aware wrapping/preview,
control and fit checks, local saving, changes-TSV download and a Python project importer.
The public catalogue excludes Japanese prose; structured/verbatim records remain read-only.
`tools/prose_editor_check.py` and `site/prose/checks.html` check the browser model against
the current Python wrapper and layout measurements, plus import and browser interactions.

Remaining gaps:

- **A translator export with budgets and context.** `script.tsv` gives you `bytes`, which is
  the wrong number for almost everything above. It should carry each path's source/pixel/
  tile contract, the storage class from §3, speaker/screen, and conversation ordering.
- **Editor coverage beyond prose.** Menus, items, glossary, cinematics and graphics need
  separate editing models and validators. The prose-only TSV contract is documented with
  the editor; the original translation files remain the build inputs.
- **Runtime name substitution census.** Pixel-aware source staging is now 30 glyphs with a
  separate 144px painted-edge check, and the old `over_cap` decree is gone. Current item
  signed/`[NN]` variants are exhaustive; `<var>`/`<cE3>` producer scope remains open.

Already available without a full ROM rebuild: `lint_en.py`, `dialogue_preview.py --check`
and `fontaudit.py`, using the local extraction. Live emulator spill tests still require
a built ROM because allocation and VBlank behavior are runtime facts.
