# Editing the script

This folder holds the game's text. This page is the practical guide: **which file to open
for each kind of text, and what will break if you get it wrong.**

[`docs/TEXT_REFERENCE.md`](../docs/TEXT_REFERENCE.md) is the measurement behind these
rules — storage classes, the character set, the per-renderer pixel budgets, every worklist
error, and what the build does not check. Read it once before a large batch. Come back
here when you want to know "where do I change a monster's name".

## The map

| You want to change | Open | Section |
|---|---|---|
| An item name | `glossary.tsv` | [Item names](#item-names) |
| A monster or NPC name | `glossary.tsv` | [Monster and NPC names](#monster-and-npc-names) |
| A menu entry, button, label | `en.tsv` | [Menu strings](#menu-strings) |
| Village or story dialogue | `prose_draft.tsv` | [Prose and story](#prose-and-story) |
| A combat or dungeon message | `en.tsv` | [Combat and dungeon messages](#combat-and-dungeon-messages) |
| The opening/ending cinematic | `intro.tsv` | its own header |

`build-inputs/` and `evidence/` are not translation files — ignore them. `script.json` and
`script.tsv` are generated from your own ROM by `tools/extract.py` and are not in the repo.

## Two rules that apply everywhere

**Keys are `loc` (`bank:$address`), never the row number.** Ids get reassigned by sorted
offset, so an id-keyed edit silently retranslates the wrong string. The build refuses
numeric keys for exactly this reason.

**A failed translation never corrupts the ROM.** Anything that cannot be inserted is
reported and the original Japanese is kept for that one string, so the build always boots.
Failures appear *only* in `build/worklist.tsv` — a green build is not proof you read it. A
clean build deletes that file, so "no such file" means nothing failed.

```sh
sh build.sh              # build + every check
cat build/worklist.tsv   # what did not fit
```

---

## Item names

**File:** `glossary.tsv`, column 4 (`loc <TAB> class <TAB> japanese <TAB> english`), rows
with class `item`. 145 of them.

Edit the English column. The glossary is inserted directly, so this *is* the name the game
prints — there is no second place to update.

### Why it is frozen

`こんぼう` is an item name, a line of help text, a combat message, and a shop's dialogue.
Translated batch by batch it becomes Club, then Cudgel, then Stick, and no reviewer catches
it, because catching it means holding 1,263 strings in your head at once. So names are
decided once here, and `lint_en.py --glossary` enforces them: if a Japanese string contains
a glossary term, its English **must** use the frozen rendering. Deliberate exceptions go in
`glossary_ok.tsv` with a written justification.

### Limits

- **The inventory row gives you a 128px payload and the source scanner accepts 17 glyphs.**
  Not 17 *letters of the base name* — the runtime suffix counts. Weapons and shields can
  carry any signed value from `-99` to `+99`; staffs and pots carry `[1]` to `[99]`.
- `Accurate Sword-99` is exactly 17 source characters and paints 87px, so it fits with real
  slack. That measurement is what disproved the old "14 character" rule of thumb.
- `lint_en.py` **fails** a staff or pot whose name plus an ordinary two-digit counter
  crosses the 17-glyph scanner (`counter_overflow`).
- Item *descriptions* are a different renderer: four rows of 144px, not three.

```sh
grep こんぼう script/glossary.tsv       # what is this thing called
python3 tools/lint_en.py               # glossary + token checks
python3 tools/fontaudit.py --details 4 # every bare/signed/[NN] variant, in real pixels
```

## Monster and NPC names

**File:** `glossary.tsv`, classes `monster` (129), `npc` (23), `appearance` (94).

Same frozen rules and the same enforcement as items. `appearance` rows are the descriptive
forms the game uses when a monster is not yet identified.

### House style

- Read as modern official Shiren English — plain and meaning-first — not as the Aeon
  Genesis SNES romanisations. `ひとつめゴロシ` is **One-Eye Killer**, not Hitotsume Goroshi.
- Category nouns follow Aeon Genesis so the two projects agree cheaply: Herb, Bracer,
  Staff, Pot, Scroll.
- A tier family should read as a family: Rat Minion / Rat Boss / Rat Kingpin.
- Proper nouns carrying no meaning in Japanese stay transliterated: Mamel, Gazer, Orochi.

### The limit that is easy to miss

A monster name is not just a menu entry — it gets substituted into combat lines at runtime.
`<var>はモンスターにかこまれた！` is 14 literal cells and leaves **four** for the name, so
the *original game* truncates that line too. Long names are therefore a real cost paid
somewhere you are not looking.

If you cannot find a defensible English name, leave the current choice and record the
question in `term_uncertainties.tsv` rather than guessing. That file exists so unresolved
naming does not silently become a decision.

## Menu strings

**File:** `en.tsv`, edited directly. This is the one place direct editing is the normal
route — menus and labels are not generated from anything.

Find the row by `loc`; the file is grouped by screen with `# ---- title / file menu ----`
style comments.

### Limits

- **Every menu box has its own pixel width**, recorded in `build-inputs/box_geometry.tsv`.
  There is no single character budget — the item action menu is 8 tiles (64px), while a
  title-menu row is the descriptor width minus one cursor tile.
- `box_too_wide` fails the build if a string overruns its box's measured geometry.
- The 40 clear-condition labels at `14:$7C78` are five 144px rows, up to 21 source glyphs
  each, checked individually *and* as the worst possible group of five.
- **The font has no percent glyph.** Write `Max Belly 200`, not a raw native tile.

## Prose and story

**File:** `prose_draft.tsv` — *not* `en.tsv`. Village and story dialogue only.

Write **sentences**: `loc <TAB> english`, with no `<br>`, no `<end>`, and no leading
indents. Then:

```sh
python3 tools/wrap_en.py script/prose_draft.tsv --preview   # see the lines it will make
python3 tools/wrap_en.py script/prose_draft.tsv --apply     # write them into en.tsv
```

`wrap_en.py` owns the line breaks, the indents, and `<end>` placement — it puts `<end>`
exactly where the shipped Japanese does. You place `<brk>` where the pacing wants a new
page. It reports `auto_split` when a drafted page needed more than one box.

Editing the generated dialogue rows in `en.tsv` by hand means your next re-wrap discards
the edit. Change the draft.

### Limits

- A box is **144 pixels wide, three lines, up to 30 staged glyphs per line.** There is no
  fourth line — the ROM reserves exactly 54 tiles — so a fourth overwrites the first
  (`box_too_deep`). Split with `<end><brk>` instead; **extra boxes are free.**
- Do not aim at a character count. A narrow 30-glyph line fits; a wide one runs out of
  pixels first. `wrap_en.py` fills to the real edge.
- Text does **not** pixel-wrap at runtime. Anything past 144 painted pixels is clipped, and
  `line_too_long` fails the build rather than shipping it.
- Keep boxes aligned to sentences the way the Japanese does.

```sh
python3 tools/dialogue_preview.py 14:$5047   # draw one string as the screen will
python3 tools/dialogue_preview.py --check    # every line; exit 1 on any overrun
```

### `<end>` is the one that bites

A **trailing `<end>` draws the final box a second time**, and the player has to press A
again to clear a box they already read. This was mis-diagnosed once as "every extra box
costs a press" — it was measured head-on and that is **false**: a two-box and a one-box
rendering of the same text both took one wait and two presses. Extra boxes cost nothing.
Trailing `<end>` costs a press. `lint_en.py` catches it as `end_trailing` and
`end_resumes_text`.

## Combat and dungeon messages

**File:** `en.tsv`, edited directly — these are not in `prose_draft.tsv`.

### They are fragments, not sentences

Combat and event text is **assembled at render time from fragments**, not stored as whole
sentences. `<var>` pulls a name from a queue and `<cE4>` supplies a number, so one stored
fragment serves every attacker, target and item in the game:

```
13:$4B66	<var> hit <var>
13:$4B94	Defeated <var>!
```

Word each fragment so it reads correctly under **every** substitution. English word order
will not always match the Japanese fragment boundaries, and some sentences need their
fragments restructured rather than translated one-to-one.

### Never add a `<br>` to a queued fragment

**This is the most dangerous edit in the entire script, and it breaks gameplay, not
layout.**

These lines are pushed through the queue appender at `0:$028B`, one record after another,
with runtime substitutions interleaved between them. The Fluffy Bunny heal line is the
clearest example — three pushes make one sentence:

```
15:$670B   ld bc,$4D7D / call $028B     "Fluffy Bunny healed <var>"
15:$6713   call $26B3                   the target actor's name
15:$6716   ld bc,$4D88 / call $028B     "with a spell."
```

The English for the first record once carried an authored `<br>`. In play that produced:

1. garbled Latin text, then
2. a blank dialogue box, then
3. an unrelated actor animation, then
4. the healer displacing across its target

That is **the queue consumer losing its place** — not a line that merely looked wrong. A
cosmetic edit corrupted actor behaviour.

**A line break was never part of this ABI.** All 239 `call $028B` sites in the ROM were
located and every bank-13 record they name decoded, giving 198 distinct fragments. The
Japanese base has an authored break in **none of them**. One English string had acquired
the only one in the game.

**You do not need the break anyway.** The fragment consumer wraps by itself. The width
budget is pinned to a line already shipping rather than to a guessed cap: `<var> robbed
<var>` reaches 179px with the widest name substituted twice, and the heal line's worst case
is 167px — comfortably inside what the path already carries.

`tools/healfragmentspill.py` now enforces both facts on every build, and it refuses to pass
while *any* `call $028B` site is unaccounted for — so a new producer shape fails loudly
instead of quietly falling outside the sweep, which is the failure mode that let this ship.

> **The rule: if the Japanese fragment has no break, yours must not either.** Not "prefer
> not to" — the path cannot carry one.

### Width, for lines that are not queued fragments

Where a break *is* legal, there is still a trap worth knowing. A `<br>` fixes the break at
one point in a sentence whose real width is not known until runtime: break `<var> hit
<var>` where it reads well for `Rat` and it is wrong for `Lantern Puffer`.

The overflow check is deliberately permissive here. The build fails a line only when it
overruns **with every substitution charged just one cell** — an overrun no runtime value
could rescue. Everything tighter is reported as headroom. So a break that is fine for short
names and broken for long ones passes every check and ships.

`tools/varaudit.py` reports these as `REVIEW` rather than failing them. It is worth reading:

```
REVIEW 13:$4B66  [combat-actor ; combat-target]: 449/15246 candidates overflow;
                 first Dadster Tank + Killer Gather => 145px/30 glyphs; <var> hit <var>
```

### Tokens must survive exactly

`<var>`, `<name>`, `<cE3>`/`<cE3:xx>`, `<cE4>`, `<cF0:xx>` and friends inject runtime data.
**A translation that drops one encodes cleanly, inserts cleanly, passes every reference
check and crash seed — and then prints "The  attacked!" on screen.**

| token | rule |
|---|---|
| `<var>` `<name>` `<cE3>` `<cE4>` `<cF0:xx>` … | must survive exactly: same tokens, same arguments, same counts |
| `<br>` `<brk>` `<end>` | yours — but see the warning above |
| `<cEC:xx>` | **must stay first.** The ROM reads it from a fixed position, not from the stream |

Order is not checked otherwise — `<var> dodged the blow` and `Shiren attacked <var>` are
both fine. Only the multiset matters. `lint_en.py` reports `token_lost` / `token_added` and
the build fails the string rather than shipping it.

---

## Checking your work

```sh
python3 tools/lint_en.py                     # tokens, glossary, <end> placement
python3 tools/dialogue_preview.py --check    # every dialogue line, drawn
python3 tools/fontaudit.py --details 4       # physical pixels, item variants
sh build.sh                                  # everything, then read build/worklist.tsv
```

`docs/TEXT_REFERENCE.md` §6 lists every worklist error and what to do about each.
