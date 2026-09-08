# Editing the script

This folder holds the game's text. This page is the practical guide: **which file to open
for each kind of text, and what will break if you get it wrong.**

[`docs/TEXT_REFERENCE.md`](../docs/TEXT_REFERENCE.md) is the measurement behind these
rules — storage classes, the character set, the per-renderer pixel budgets, every worklist
error, and what the build does not check. Read it once before a large batch. Come back
here when you want to know "where do I change a monster's name".

The [translation workbenches](../site/workbench/README.md) provide subject-specific
browser editors, complete extraction/cinematic coverage and a validated changes-TSV
importer. The [prose editor](../site/prose/README.md) retains automatic wrapping by event;
structured choices have a separate editor. Run `python3 tools/prose_editor.py serve`
from the repository root, then open **http://127.0.0.1:8765/**. The original files below
remain the source of truth. Workbench imports route each edit to the appropriate file,
and can include a prose download in the same transaction for coordinated name changes.

## The map

| You want to change | Open | Section |
|---|---|---|
| An item name | `glossary.tsv` | [Item names](#item-names) |
| An item description or equipment seal | `en.tsv` | [Descriptions and seals](#descriptions-and-seals) |
| A monster or NPC name | `glossary.tsv` | [Monster and NPC names](#monster-and-npc-names) |
| A menu entry, button, label | `en.tsv` | [Menu strings](#menu-strings) |
| Village or story dialogue | `prose_draft.tsv` | [Prose and story](#prose-and-story) |
| A combat or dungeon message | `en.tsv` | [Combat and dungeon messages](#combat-and-dungeon-messages) |
| The opening/ending cinematic | `intro.tsv` | its own header |

`build-inputs/` and `evidence/` are not translation files — ignore them. `script.json` and
`script.tsv` are generated working files from `tools/extract.py` and remain ignored.
The complete Japanese TSV is also published as a tracked snapshot at
[`site/data/script.tsv`](../site/data/script.tsv), which the browser editor loads automatically.
For any address already in `prose_draft.tsv`, edit that draft even when the row is help
or menu text; the wrapper owns its generated `en.tsv` value.

## Two rules that apply everywhere

**Keys are `loc` (`bank:$address`), never the row number.** Ids get reassigned by sorted
offset, so an id-keyed edit silently retranslates the wrong string. The build refuses
numeric keys for exactly this reason.

**A rejected translation fails the build.** `tools/build.py` exits nonzero on collected
text/reference errors before writing its ROM or relocation map, preserving any previous
outputs. `sh build.sh` requests the detailed `build/worklist.tsv` report. Successful
insertion removes a stale worklist; a later build gate can still fail, so check the command's
exit status and output. The absence of a worklist alone does not prove a successful run.

```sh
sh build.sh              # build + every check
# If insertion failed, inspect build/worklist.tsv and the command output.
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

- **The inventory row gives you a 128px payload and the source scanner accepts 18 glyphs,**
  including the runtime suffix. Weapons and shields can
  carry any signed value from `-99` to `+99`; staffs and pots carry `[1]` to `[99]`.
- The 2026-09-08 font audit measures `Battle Counter-99` at 17 source glyphs and 84px,
  requiring 11 allocator tiles. A character count alone does not establish a visual fit.
- `lint_en.py` **fails** a staff or pot whose name plus an ordinary two-digit counter
  crosses the 18-glyph scanner (`counter_overflow`).
- Item *descriptions* are a different renderer: four rows of 144px, not three.

```sh
grep こんぼう script/glossary.tsv       # what is this thing called
python3 tools/lint_en.py               # glossary + token checks
python3 tools/fontaudit.py --details 4 # every bare/signed/[NN] variant, in real pixels
```

## Descriptions and seals

**File:** `en.tsv`. Item descriptions have four 144px rows per page and a 21-glyph
source limit per row. Preserve the Japanese description's page count: the item selector
uses those boundaries. Equipment seals have one 144px, 21-glyph row per seal.

`<cF0:xx>` expands a shared help fragment; its actual translated text spends glyphs and
pixels in the containing row. Run `dialogue_preview.py --check` and `fontaudit.py` after
editing either a description or a shared fragment. A seal cannot borrow another seal's row.

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

- **Every menu box has its own pixel width**, derived from the extracted descriptor and
  the approved overrides in `build-inputs/box_geometry.tsv`.
  There is no single character budget — the item action menu has a 32px text payload
  after its 8px cursor cell (boxes 6/39 have five interior tiles), while a
  title-menu row is the descriptor width minus one cursor tile.
- `box_too_wide` fails insertion when a row exceeds its measured source scanner.
  `fontaudit.py` separately checks physical pixels; live menu regressions check allocation.
- The 40 clear-condition labels at `14:$7C78` are five 144px rows, up to 21 source glyphs
  each, checked individually *and* as the worst possible group of five.
- **The font has no percent glyph.** Write `Max Belly 200`, not a raw native tile.

## Prose and story

**File:** `prose_draft.tsv` for rows already drafted there. It primarily contains village
and story dialogue, plus a few explicitly grouped wrapped help/menu records. Edit those
rows in the draft so a later wrap keeps the change.

Write **sentences**: `loc <TAB> english`, without manual `<end>` or leading indents.
Use `<brk>` for an authored page/pacing break and `<br>` when a deliberate line break
matters; the wrapper handles the remaining wrapping. Then:

```sh
python3 tools/wrap_en.py script/prose_draft.tsv --preview   # see the lines it will make
python3 tools/wrap_en.py script/prose_draft.tsv --apply     # write them into en.tsv
```

`wrap_en.py` preserves authored breaks, adds continuation indents, balances overflowing
pages, and places `<end>` before generated page boundaries. It preserves structural
source endings before terminal effect controls. It reports `auto_split` when a drafted
page needed more than one box; review the pacing and source close behavior afterward.

An existing value starting with `=` is a verbatim row: the wrapper removes `=` and copies
the rest unchanged. It receives no automatic wrapping or indent repair. Preserve its
reviewed controls and run the same validation as for direct `en.tsv` edits.

Editing the generated dialogue rows in `en.tsv` by hand means your next re-wrap discards
the edit. Change the draft.

### Limits

- A box is **144 pixels wide, three lines, up to 30 staged glyphs per line.** There is no
  fourth line — the ROM reserves exactly 54 tiles — so a fourth overwrites the first
  (`box_too_deep`). Split with `<end><brk>` instead; **extra boxes are free.**
- Do not aim at a character count. A narrow 30-glyph line fits; a wide one runs out of
  pixels first. `wrap_en.py` fills to the real edge.
- A native leading space costs one source glyph and its font advance. The builder,
  preview and wrapper share that rule; the wrapper reserves the first-line indent without
  writing it into the draft or doubling it in the output. Selector rows have their own
  cursor-spacing transformation in `tools/textlayout.py`; do not normalize their spaces.
- Text does **not** pixel-wrap at runtime. Anything past 144 painted pixels is clipped, and
  `line_too_wide_px` fails insertion. `line_too_long` independently protects the source scanner.
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

### Never add a `<br>` or `<brk>` to a queued fragment

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

Unknown runtime values are checked at their minimum contribution. The settled `<name>`
producer instead reserves all six player-name glyphs and their widest approved pixels;
shared help fragments use their actual translations. Known item suffixes and selected
message families receive additional variant audits. A passing minimum-value check does
not prove every remaining actor/item substitution fits.

`tools/varaudit.py` reports unresolved combinations as `REVIEW`. For example, a historical
report had this form; regenerate the report for the current font and glossary:

```
REVIEW 13:$4B66  [combat-actor ; combat-target]: 449/15246 candidates overflow;
                 first Dadster Tank + Killer Gather => 145px/30 glyphs; <var> hit <var>
```

### Tokens must survive exactly

`<var>`, `<name>`, `<cE3>`/`<cE3:xx>`, `<cE4>`, `<cF0:xx>` and friends inject runtime data.
Dropping one can encode successfully while losing runtime data. Token lint catches that
semantic error and makes insertion fail.

| token | rule |
|---|---|
| `<var>` `<name>` `<cE3>` `<cE4>` `<cF0:xx>` … | must survive exactly: same tokens, same arguments, same counts |
| `<br>` `<brk>` `<end>` | follow the renderer's wrapping, page-count and close rules above |
| leading `<cEC:xx>` in bank-11/14 source | **must stay first**, with its argument; the dialogue path reads its prefix at a fixed position |

`lint_en.py` compares the multiset of significant tokens, including arguments, rather
than their sequence. Passing parity does not establish that reordering is safe: preserve
the producer's substitution order and effect/control sequence unless the actual route
proves a change. Identical `<var>` tokens can still refer to different queued actors.

---

## Checking your work

```sh
python3 tools/lint_en.py                     # tokens, glossary, <end> placement
python3 tools/dialogue_preview.py --check    # every dialogue line, drawn
python3 tools/fontaudit.py --details 4       # physical pixels, item variants
sh build.sh                                 # normal build and runtime gates
```

These checks use the local extraction in `script/script.json`. On insertion failure,
read `build/worklist.tsv`; other gate failures are reported by the command that failed.
`docs/TEXT_REFERENCE.md` §6 lists the main diagnostics and how to address them.
