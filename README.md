# Fuurai no Shiren GB — English translation

**Made with AI assistance.**

This is a personal, unofficial project made so I can play the game in English—and so
anyone else who wants to can do the same. Anyone may freely use this repository or use it
as the basis for a translation into any language. This is not an official release and is
not affiliated with or endorsed by the original developers or publishers. Third-party
components remain subject to the license notices preserved under [`licenses/`](licenses/).

An English translation patch for **Fushigi no Dungeon: Fuurai no Shiren GB — Tsukikage Mura
no Kaibutsu** (風来のシレンGB 月影村の怪物), Chunsoft, Game Boy, 1996.

The repo is a **toolchain**, not a patch file. You supply the Japanese ROM; the tools pull
the extracted script out of it, insert English back in, and verify the result. The ordinary
script and the separately encoded prologue/ending cinematics both live in editable TSV files.

Before placing code or data in ROM, read the maintained
[`docs/ROM_BANK_MAP.md`](docs/ROM_BANK_MAP.md). It records the native no-touch regions,
expanded-bank ownership, and the collision checks required for every new allocation.

**Status:** 1,404 of 1,422 ordinary extracted records are English. The remaining 18 are
unrendered: six records from the aliased second name-entry page and 12 entries nothing
draws. All 12 lines of the separately encoded prologue and ending cinematics are extracted,
translated, and rendered with Thin Pixel-7 GB Compact VWF. V4D is complete: all ten script-bank
embedded/unframed scanner hits are
proven non-text by their consumers and guarded by exact address+byte declarations. Unknown
runtime entries remain an ordinary playtest/V6 discovery concern, not a known localization
backlog. **V5A-V5C graphics are complete:** the pre-intro card reproduces the approved
full-screen copyright-card mock-up; the illustrated title uses the approved four-colour
`Mystery Dungeon / Shiren / The Wanderer / Monster of Moonlight Village / GB` design; and all
eight town/dungeon arrival labels use the approved clean, 12px-cap Poppins treatment.
`Moonlight Village` and `1 Forest` reproduce the supplied mock-ups pixel-for-pixel; the
three-row renderer keeps their descenders and combines the other six names with all 50
live floor values. Every native numbered card now gives its number and name one shared
line origin and is centered from visible ink rather than the reserved four-tile number
field. The 22 active numbered combinations have at most a four-pixel outer-margin
imbalance; the real floor-19 `Dragon's Maw` fixture is exact at 7/7px.
The active-dungeon Continue screen also replaces its Japanese loading bubble with centered
`Please` / `wait...` text while preserving the native character and speech-bubble art.
Decoy Staff targets now report as the live player name alone: the runtime actor-name
producer no longer emits the untranslated Japanese `にせ` prefix that appeared as
`VNShiren` under the English font.
The title graphics retain their native fades/input path and scene-0 transition, the floor cards retain a fixed
live number field through floor 50, and fresh-boot/title/file-menu plus real Forest 1F
routes are exact regressions. The complete 22-card ending roll is also translated in the
approved white/green Poppins style, while the separate final Japanese end mark remains
native by design. Its compact sequencer now replaces the checksum-guarded native credit
driver instead of occupying a zero-filled-looking gameplay-data span. The normal build
compares all 303 enemy-tier EXP rewards (all nine byte planes) with the expanded Japanese
control ROM; tier-3 Mouse Don is explicitly verified at 40 EXP. Its real Hard-ending route
is a permanent save-backed regression.
The shared rescued-child final-exit freeze is fixed: Rankings now uses a synchronous
LCD-off name upload instead of waiting forever for a disabled VBlank consumer, and the
supplied Nagi route is a permanent emulator regression. Ordinary stairs are fixed too:
two bank-13 instructions explicitly select bank 14's `Go down / Stay here` text, but the
extractor once attached their same-address operands to bank 13 and repointed them at a
companion line. The proven cross-bank references now remain with the choice. Two Koppa
floors plus Nagi and Fumi are save-regressed against the original Japanese behavior.
Talking to Koppa is also one-press exact again: `14:$7BC2` now follows its Japanese source
and ends naturally at `$FF`, rather than appending `<end><brk>` and drawing an empty box.
The supplied town route and a dungeon-consumer probe share one regression.
V4A substitution research remains
optional because no failing value is known; V4B remains the intake for concrete wording,
spacing and pacing findings. Three of the 1,422 records are runtime-observed starts inside
parent records; static byte coverage alone did not discover them. Structured fixed-cell
labels were resolved in V3: static words compose from proportional fragments while live aligned
values and selectable name cells deliberately keep their fixed coordinates. The visible
name grid is now ordered continuously across its three blocks—A-Y, then Z/a-x, then y-z,
punctuation and digits—with no accidental selectable gaps. See
`HANDOFF_NEXT.md`. The saved Copy -> Erase -> New Log route also restores the name
underline and `() :` glyph planes borrowed by the outgoing confirmation before drawing
the keyboard. V4F item-menu transitions are implemented and visually approved: item
entry and Left/Right paging show a brief white frame before complete new text instead of
blending old and new rows. Box 14 also composes the complete proportional `Items` heading
with its corrected spacing. The same atomic boundary covers the supplied Wood
Arrow Floor action/Info route and Gitan's shorter three-choice action box. The latter now
returns from its one-page description instead of leaving the LCD disabled. The status Path
field now spells out `Normal`
and right-aligns `Easy` / `Normal` / `Hard` at the same fixed-cell edge. Main-menu and
file-menu redraws now use the same atomic contract: layered title, Log, difficulty and
Rank/Pass screens cannot expose stale VWF pixels, and Rankings remains on a blank alternate
map until its complete board is ready. The Rankings ownership repair now treats its labels,
difficulties and five names as one proportional `$80-$A6` board allocation. Category
selectors borrow `$C0-$CB` only while their map is live; a native menu-font reload restores
those single-bank planes before the Rankings, title or Adventure maps are revealed. A full
title rebuild also starts a fresh allocation epoch before inspecting the prior transaction
byte, covering both direct Erase Log and
Load Log 1 -> Quit -> Erase Log routes. The menu label now uses the official name
`Fay's Puzzles`, whose 13 source glyphs fit the existing box in eight proportional tiles.
V4C menu geometry, V4E atomic publication and V4F item/Floor transitions are complete and
visually approved. Rankings' normal/shuffled/redirect-all automated acceptance is green,
and the exact Kuyo/repeat/Village Exit route passed in Mesen on 2026-08-12. VWF,
native ranking graphics and the cleared-Orochi badge all remained correct.

---

## Current release status — 2026-08-12

| Area | State | What remains |
|---|---|---|
| Extracted script and cinematics | **Complete** | 1,404 supplied ordinary translations; the other 18 extracted records are proven unrendered. All 12 separately encoded cinematic lines are translated. |
| English prose and terminology | **Build-complete; playtest ongoing** | The direct uncertainty list is empty. Continue reviewing wording, pacing and newly reached event routes during a full playthrough. |
| Player-name safety | **Complete** | `nameaudition.py` reports zero unsafe lines for both `Shiren` and the widest legal six-character name. |
| VWF, menus and item/status screens | **Complete and visually approved** | Rankings retains VWF with one screen-scoped allocation, disjoint native graphics and exact Adventure Log restoration in automated tests and the repeated Mesen route. Other known item, Floor/Info, main/file, Fay, equipment, Pot, Decoy and name-entry routes remain regression-covered. |
| Production fonts | **Complete** | Thin Pixel-7 GB Compact covers dialogue, menus and cinematics. Arrival-card graphics use the separately approved Poppins Medium one-bit treatment. |
| Graphics | **V5A-V5D complete** | All 22 ending-credit cards preserve the native roster, order and timing; the final Japanese end mark remains native by request. The active-dungeon Continue bubble is also English. |
| Known gameplay blockers | **None known** | R3 Rankings/Orochi is closed after the complete automated matrix and manual Mesen approval. The cross-bank stair and rescued-child exit freeze remain closed. |
| Release | **RC1 automated validation complete** | Continue broad manual playthrough intake before declaring a final release. |

RC1 was built from commit `1a92fc1`. The complete normal, shuffled and redirect-all release
batteries pass, including all 72 CPU-health seeds and 1.44 million containment frames with
zero spill. The normal artifact is `build/shiren_en_rc1.gb`,
SHA-256 `5b8018d35ce963bd6932412fe606705e3ad6aacd7a9340b83ab2cb32eb6e2cd5`.
The matching shuffled and redirect-all matrix ROMs have SHA-256 values
`5da813423bf5b837b21a5046756a96ba5da5e2fc82b5b988513a929c7dd11bde` and
`0a6a85315001c5f84518a7eb9a6703946ad5759439e47c409c3fc3e9c6f12ed4`.
Manual acceptance passed on 2026-08-12 using
`Adventure -> Log 1 -> Rank/Pass -> Rank -> Kuyo -> Adventure -> Log 1`, repeated the
cycle, and also checked `Village Exit`; VWF and the native graphics remained correct.
The replacement `tools/orochisymbolspill.py` requires a native control and checks the real
`$CB/$CD/$CC/$CE` badge, complete boards, native status graphics and repeated restoration.
It demonstrably fails the frozen known-bad ROM,
SHA-256 `b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`.
`rescuespill.py` keeps three conservative Nagi interior records intact and proves the
ordinary stair does not enter them.
The historically named `koppastairspill.py` independently loads two Koppa Log-1 floors,
Nagi and Fumi and proves all four stage relocated `14:$46C1` (`Go down / Stay here`),
never the Nagi or Koppa companion text.

---

## 1. What you need

* **Python 3** with two packages: `pyboy` (headless emulator, used by every check that
  looks at the real screen) and `pillow`.

  ```sh
  pip install pyboy pillow
  ```

* **Your own copy of the Japanese ROM.** No game data is in this repo and none should ever
  be committed — `.gitignore` blocks `*.gb`, the extracted Japanese script and all build
  output. The tools are written against this dump:

  ```
  size   524288 bytes
  md5    754398219a3ab38394cdac543d8deb47
  sha1   920ef94c05ac741047a266cb1668c881eab2937c
  header FURAINO SIREN G
  ```

  Another dump may work, but every address in the docs was measured against this one.

## 2. Build it

From a fresh clone, three commands:

```sh
mkdir -p build
cp "/path/to/Fuurai no Shiren GB (Japan).gb" build/base.gb   # or symlink it

python3 tools/extract.py build/base.gb    # Japanese script -> script/script.json
sh build.sh                               # -> build/shiren_en.gb
```

`build.sh` should end with **`no problems: every supplied translation fit.`** The ROM it
writes is 1 MiB — the build converts the cart to MBC3 and doubles it, because the original
512 KiB is full. `build/shiren_en.gb` runs in any Game Boy emulator.

> **`extract.py` must run before your first build** and again whenever you change anything
> about extraction. It writes `script/script.json`, which every other tool reads and which
> is deliberately *not* in the repo — it is the game's Japanese text, so it is regenerated
> rather than distributed. Your translations survive re-extraction untouched: they are
> keyed on address, not on line number.

## 3. Edit the translation

**`script/en.tsv` is the file.** One string per line, `address <TAB> English`, with `#`
comments anywhere:

```
13:$461A	<cE1><cE0:4C>Got <cE3>
14:$51D3	Keyaki: <name>! Waaait!
11:$548B	Strong vs Dragons
```

The address on the left is the string's location in the ROM — bank and offset — and it is
the key. Look one up in `script/script.tsv` (regenerated by `extract.py`) to see the
Japanese it replaces.

Edit a line, rebuild, and that is the whole loop:

```sh
sh build.sh
```

### Editing the prologue and ending cinematics

The boot prologue and post-game ending use a separate bytecode VM and therefore share their canonical file:
`script/intro.tsv`. Each row keeps its exact ROM ranges, source bytes and Japanese beside
the editable English. **Edit only the `english` column.** The normal `build.sh` consumes it
automatically and relocates the result; English is not restricted to the Japanese byte
count.

`<br>` forces a line break and `<page>` is a real measured screen transition. The build
rejects missing/extra rows, changed source metadata, unknown glyphs, malformed controls,
wrong page counts and text wider than its 152-pixel area. To re-extract or check the file:

```sh
python3 tools/intro.py build/_base_expanded.gb --extract --existing script/intro.tsv \
        --output script/intro.tsv
python3 tools/intro.py build/_base_expanded.gb --check script/intro.tsv
python3 tools/introspill.py build/_base_expanded.gb build/shiren_en.gb
python3 tools/introplayback.py
```

`introplayback.py` forces the post-game ending without requiring a completed save and
writes a native-resolution looping GIF to `build/forced_ending_playback.gif`. Its header
documents optional ROM and output paths.

**Anything in angle brackets is a control code and must survive.** `<name>` is the player's
name, `<var>` a monster or item name, `<cE3>` (or dialogue `<cE3:xx>`) a selected item
name with its count, `<br>` a line
break, `<brk>` a page/window break, and `<end>` a message-end marker. `lint_en.py` fails
the build if you drop one — the game substitutes real values into those slots at runtime,
so a lost token is a lost word on screen, not a cosmetic difference.

Keyaki's Otogiri Herb receipt (`14:$52AB`) is manifested from the public Log-2 walk-left
route. Its `<cE3:FE>` token is an item substitution plus selector byte, not visible text;
`tools/keyakigiftspill.py` verifies that hidden entry and the complete four-message event.

Three Nagi interior rows (`14:$5AFD`, `$5B81`, `$70BE`) remain manifested conservatively:
they were observed during investigation of the formerly corrupt stair pointer. The
corrected ordinary route does not enter them, but retaining their independent English
records protects any still-unseen event that does. `tools/rescuespill.py` verifies the
records and their isolation; `tools/koppastairspill.py` covers the actual shared
`Go down / Stay here` choice on two Koppa floors, Nagi and Fumi.

`TRANSLATING.md` is the full rules document: the three storage classes, what each control
code costs, and how much room each screen actually has. **Read it before a large edit.**

### Writing prose without counting characters

Dialogue lines are hard-wrapped with `<br>`, which is tedious to maintain by hand. Write
sentences in `script/prose_draft.tsv` instead and let the wrapper do the line breaks:

```sh
python3 tools/wrap_en.py script/prose_draft.tsv --preview   # see the boxes
python3 tools/wrap_en.py script/prose_draft.tsv --apply     # write into en.tsv
```

The wrapper uses the approved Thin Pixel-7 GB Compact glyphs and accepts the longest line satisfying both the
30-glyph source stager and 144px painted edge. This is also how you re-flow everything at
once if a renderer contract or approved glyph changes.

### Direct prose review and optional Gemini proposals

The primary story-prose pass is a direct Japanese-to-English review. Verified state lives
in `script/prose_review.json`; genuinely unresolved meaning, terminology or localization
decisions go in the intentionally small `script/prose_uncertainties.tsv` rather than being
silently guessed.

`tools/gemini_prose.py` remains available as an optional independent proposal layer. It can
store a fresh candidate in the same tracked queue and run the token, glossary, codec and
measured-fit gates before a human accepts it. It never writes either canonical TSV directly
from a model response. Menus, items, labels, byte-exact layout rows and the separately
translated opening/ending cinematics are outside its default scope. Setup, credential
handling, free-tier caveats, commands and review states are documented in
[`GEMINI_TRANSLATION.md`](GEMINI_TRANSLATION.md).

### Keeping names consistent

`script/glossary.tsv` freezes 391 item, monster and NPC names, so `こんぼう` is "Club" in the
item list, in a shop's dialogue and in a combat message alike. `lint_en.py` checks one
Japanese name rendered two ways, two names rendered the same way, terminology drift, and
the real 18-glyph item-row source contract, including runtime equipment suffixes. The old universal
14/16 name reservations are no longer lint failures; `fontaudit.py` keeps them visible as
historical runtime-substitution warnings. Change a name **in the glossary**, not in the
40 places it appears.

## 4. The limits that will bite you

**Text does not wrap at runtime. It truncates silently.** With proportional text, “one character
too long” is no longer a sufficient diagnosis: physical pixels, source staging, temporary
tiles and runtime substitutions are separate constraints. The canonical measured register
is [`VWF_BUDGETS.md`](VWF_BUDGETS.md).

Different renderers have different budgets, and the tools track them separately:

| Where | Physical width | Lines | Current source policy |
|---|---|---|---|
| Dialogue boxes | **144px** | 3 per box | Up to 30 staged glyphs; painted extent must also fit |
| Item descriptions | **144px** | 4 | Proportional path accepts 21 staged glyphs |
| Equipment seals | **144px** | **1** | Proportional path accepts 21 staged glyphs |
| Item-list text | **128px** | 1 | Current source scanner accepts 17 including suffix |
| Menu boxes | descriptor pixels | per box | Shape/prefix-specific guards |

Substituted text shares the same pixels with your sentence. The old monster/item 14 and
`<cE3>` 16 values in `dialogue_preview.py` are now explicitly **legacy reservations under
audit**, not proportional-font limits. Do not shorten natural English from those numbers alone. The
six-character player name is a real input/storage contract; dialogue wrapping, preview
and build validation reserve all six glyphs and their widest approved pixel footprint.

Space in the ROM is **not** a constraint: strings that do not fit their original slot are
relocated automatically into free banks, and `build.sh` prints how much room every region
has left. Write the line the way it should read.

## 5. Check your work

### Ordinary build gate

Run this from the repository root after any change that alters what a player reads:

```sh
sh build.sh
```

It rebuilds `build/shiren_en.gb`, runs all static build/font/coverage gates, and runs every
SRAM-backed regression from the curated, hash-verified files under
`tests/fixtures/saves/`. `build.sh` stages ignored links at the legacy `saves/` paths and
refuses to overwrite a differing personal file.

Two tests also need PyBoy machine states. States are generated rather than tracked because
they contain a complete emulator snapshot and silently become stale when WRAM/SRAM layouts
move. On a fresh clone, build once, regenerate the states from the current ROM, inspect the
four checkpoint images, then rerun the normal build:

```sh
sh build.sh
python3 tools/fixtures.py states build/shiren_en.gb \
    --png-dir build/fixture-state-shots
python3 tools/fixtures.py preflight --require-states
sh build.sh
```

The preflight verifies every public SRAM hash, confirms every persisted log/Rankings
name is the public default `Shiren` (or empty), checks for path/email metadata, and requires
all four generated machine states. It therefore covers release-only fixtures such as
`shiren_en_menu.srm`, not just paths mentioned conditionally by `build.sh`.

### Entire release battery

`build.sh` is the normal-build gate; it does **not** perform the hostile-placement or long
seeded sweeps. Before tagging a release candidate, run the following complete matrix from
the repository root after the fixture check above. It builds the normal, shuffled and
redirect-all ROMs, regenerates matching controls, checks static invariants and the offline
translation tooling, then exercises timing, VBlank delivery, 12-seed CPU health, box
containment and the brittle menu/Rankings ownership routes on all three layouts.

```sh
set -eu

# Hash/privacy-check and stage all tracked SRAMs; require current generated states.
python3 tools/fixtures.py preflight --require-states

# Normal build and every available save-backed route.
sh build.sh

# Static models and offline developer tooling not all invoked directly by build.sh.
python3 tools/dialogue_preview.py --check
python3 tools/dialogue_preview.py --selftest
python3 tools/logicdiff.py build/_base_expanded.gb build/shiren_en.gb
python3 tools/intro.py build/_base_expanded.gb --check script/intro.tsv
python3 tools/pool.py --selftest
python3 tools/vwf.py --selftest
python3 tools/name6.py --selftest
python3 tools/rank6.py --selftest
python3 tools/decoyname.py --selftest
python3 tools/nameaudition.py
python3 tools/test_gemini_prose.py

# Hostile string-placement builds and current comparison controls.
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/shiren_en_shuffle.gb --dot-font --shuffle
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/shiren_en_redirect_all.gb --dot-font --redirect-all
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/orochisymbolspill_native_control.gb --dot-font --no-menuvwf
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/rankvwf_control.gb --dot-font --no-rankvwf
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/structvwf_control.gb --dot-font --no-structvwf

# The original-drawer census is layout-independent and needs to run once.
python3 tools/menuromcensus.py build/orochisymbolspill_native_control.gb \
    --ram saves/shiren_en_menu.srm

for battery_rom in \
    build/shiren_en.gb \
    build/shiren_en_shuffle.gb \
    build/shiren_en_redirect_all.gb
do
    python3 tools/logicdiff.py build/_base_expanded.gb "$battery_rom"
    python3 tools/enemyexp.py build/_base_expanded.gb "$battery_rom"
    python3 tools/introspill.py build/_base_expanded.gb "$battery_rom"
    python3 tools/proptiming.py "$battery_rom" --frames 3000 --seeds 4
    python3 tools/propupload.py "$battery_rom" --frames 3000 --seeds 4

    # 24 CPU-health runs and 480,000 frames per ROM: dungeon + town.
    python3 tools/crashscan.py "$battery_rom" --seeds 12
    python3 tools/crashscan.py "$battery_rom" --seeds 12 \
        --state saves/town.state
    python3 tools/boxspill.py "$battery_rom" --seeds 12 --frames 20000

    # Hostile menu allocation and cross-screen VRAM ownership.
    python3 tools/menuspill.py "$battery_rom"
    python3 tools/menuspill.py "$battery_rom" --long
    python3 tools/menuspill.py "$battery_rom" --ram saves/shiren_en_menu.srm
    python3 tools/menuspill.py "$battery_rom" --help-seals
    python3 tools/conditionspill.py "$battery_rom"
    python3 tools/menuromspill.py "$battery_rom" --ram saves/shiren_en_menu.srm
    python3 tools/mainmenuspill.py "$battery_rom"
    python3 tools/startspill.py "$battery_rom" \
        --ram saves/shiren_en_menu.srm \
        --wide-ram saves/shiren_en_ranking_repaired.srm
    python3 tools/rankspill.py "$battery_rom" \
        --control build/rankvwf_control.gb \
        --native-control build/orochisymbolspill_native_control.gb
    python3 tools/orochisymbolspill.py "$battery_rom" \
        --native-control build/orochisymbolspill_native_control.gb
    python3 tools/rescueexitspill.py "$battery_rom"
    python3 tools/structspill.py build/structvwf_control.gb "$battery_rom" \
        --ram saves/shiren_en_menu.srm \
        --rank-ram saves/shiren_en_ranking_repaired.srm
    python3 tools/savesummaryspill.py "$battery_rom"
done
```

The block stops on the first failing command. A release-battery pass therefore means:
all conditional normal routes actually ran, all three ROM layouts completed, every
renderer pass stayed below the 154-scanline budget, every completed queue reached VBlank
byte-exact, every CPU seed remained healthy, and `boxspill` observed zero spilling frames.
This is still not a substitute for the manual emulator playthrough described below.

### Individual checks

The same checks can be run independently while iterating:

```sh
sh build.sh                                   # must end "no problems"
python3 tools/lint_en.py                      # control tokens + glossary
python3 tools/dialogue_preview.py --check     # per-string geometry; exit 1 if text is lost
python3 tools/dialogue_preview.py --selftest  # checks the MODEL against the Japanese
python3 tools/logicdiff.py                    # no unexplained pure-logic rewrite
python3 tools/enemyexp.py build/_base_expanded.gb build/shiren_en.gb
                                               # all 303 native enemy-tier rewards exact
python3 tools/coverage.py                     # static byte census + exact non-text classifications
python3 tools/dotfont.py                      # approved source hash and glyph edits
python3 tools/fontaudit.py                    # proportional pixel budgets
python3 tools/propvwf.py --selftest           # every dialogue glyph/shift plane-exact
python3 tools/markerspill.py build/shiren_en.gb
                                                # exact New Log village-card raster + tilemap
python3 tools/floormarkerspill.py build/shiren_en.gb
                                                # real Forest 1F + every card/digit form
python3 tools/dragonmawmarkerspill.py build/shiren_en.gb
                                                # real Log-1 floor 19 + centered widest card
python3 tools/newgamesmoke.py build/shiren_en.gb
                                                # same blank-cart route reaches live village
python3 tools/menuspill.py build/shiren_en.gb # includes the Floor item-name header
python3 tools/menuglyphspill.py build/shiren_en.gb
                                                # every textual glyph through Items + Info
python3 tools/unidentifiedspill.py build/shiren_en.gb
                                                # real hidden-modifier Hyakki Shield★★ name
python3 tools/unidentifiedhelp.py build/shiren_en.gb
                                                # all identity-hidden categories' title/body
python3 tools/identityhiddenspill.py build/shiren_en.gb
                                                # real Opal Bracer + Gold Staff Info routes
python3 tools/potseespill.py build/shiren_en.gb
                                                # real Floor -> See empty Storage Pot route
python3 tools/actionpotspill.py build/shiren_en.gb
                                                # real Log-2 Back/Todo charge rows
python3 tools/itempagespill.py build/shiren_en.gb
                                                # real multi-page item transitions
python3 tools/rescuespill.py build/shiren_en.gb
                                                # real Nagi stair entry + one-window controls
python3 tools/koppastairspill.py build/shiren_en.gb
                                                # ordinary choice: two Koppa floors + Nagi + Fumi
python3 tools/koppatalkspill.py build/shiren_en.gb
                                                # shared Koppa phrase: town close + dungeon advance
python3 tools/copylogspill.py build/shiren_en.gb
                                                # direct + post-Quit Erase -> Copy Log VWF
python3 tools/decoynamespill.py build/shiren_en.gb
                                                # real Log-1 attack; decoy copies live player name
python3 tools/conditionspill.py build/shiren_en.gb
                                                # five-row clear-condition VWF
python3 tools/introspill.py build/_base_expanded.gb build/shiren_en.gb
                                                # cinematic TSV + both live VM variants
```

`build.sh` runs the lint and proportional audit itself; the separate commands are useful
for faster iteration and detailed reports. `--check` is the one you will use most: it
reports both the source-glyph ceiling and painted-pixel clipping using the approved font.

```
11:$5529  (equipment seal -- 21 source glyphs / 144px, 1 line)
    +---------------------+
    |This item will never |  << LOSES 'rust'
    +---------------------+
    !! line_too_long: box 1 line 1 stages 25 glyphs, this renderer accepts 21
```

That sentence paints only 112px, so the diagnostic correctly identifies a source-scanner
limit rather than asking for a shorter phrase on false pixel grounds.

Dropping a control code is caught by `lint_en.py` instead, which prints the Japanese beside
your English so you can see what the token was standing in for:

```
14:$78AE     token_lost
    <name> appears 1 time(s) in the Japanese, 0 in the English
    jp: <name>は、マムルのけんを<br>もらった！
    en: You received the<br> Mamel Sword!
```

Some strings are pasted into others, so an edit can fail somewhere you did not touch:
`<cF0:xx>` names one of 13 shared lines that most item descriptions include, and widening
one makes every description carrying it too wide. The address `--check` reports is where
the text *lands*, which is the one that matters.

**Everything that looks at a running game needs SRAM or a save state.** The curated SRAM
inputs are tracked under `tests/fixtures/saves/`, hash/privacy-checked by
`tools/fixtures.py`, and staged into the ignored `saves/` working directory. PyBoy machine
states are not tracked: they carry WRAM and cartridge RAM and silently become wrong when a
layout moves.

Regenerate the standard states from the current ROM with:

```sh
python3 tools/fixtures.py states build/shiren_en.gb \
    --png-dir build/fixture-state-shots
```

This wraps `tools/mkstate.py`, using the curated repaired-ranking SRAM to walk from the
first village house into Forest 1 and write `saves/*.state`. Inspect all four checkpoint
images. The floor-card tilemap is also checked exactly, so a drifted timed checkpoint now
fails generation. The source `.srm` must be one
this save format supports—the player-name widening changed the persistent layout.

`boxspill.py` announcing *"the box never opened in any run, so this measured nothing"* is
it working correctly. Believe it over a green exit code.

### Looking at a screen you cannot reach

Several screens are hard to navigate to. Rather than replaying the game, force them:

```sh
# no save state needed -- boots from reset and drives the game headless
python3 tools/gbrun.py build/shiren_en.gb --frames 600 --png shot.png

# these need a state; --state defaults to saves/dungeon.state
python3 tools/helpshot.py build/shiren_en.gb --topic 3 --png help.png    # item description
python3 tools/sealshot.py build/shiren_en.gb --all --png seals.png       # all 20 seals
python3 tools/msgshot.py  build/shiren_en.gb saves/sign.state 14:'$4638' # any bank 11/14 line
```

**And photograph the screen, not the string.** Every check above compares the build against
a *model* of the game. A translation can be byte-perfect, pass all seven, and still render
wrong — that has happened here more than once, and every time it was found by someone
playing the build rather than by a check.

## 6. Where things are

```
script/en.tsv             THE TRANSLATION. Edit this.
script/prose_draft.tsv    dialogue as sentences; wrap_en.py turns it into en.tsv rows
tests/fixtures/           tracked SRAM regressions, hashes, routes and setup instructions
script/glossary.tsv       391 frozen item / monster / NPC names
script/intro.tsv          canonical prologue/ending cinematics; edit only the English column
script/intro_draft.tsv    historical decoding/research draft; not consumed by the build
script/box_geometry.tsv   menu box positions and widths (data — you may widen a box)
script/script.json        the extracted Japanese. Generated; never edited by hand

tools/build.py            inserts the translation and verifies it
tools/extract.py          pulls the Japanese script out of the ROM
tools/lint_en.py          control-token parity and glossary consistency
tools/dialogue_preview.py source/pixel model: what fits, and what falls off
tools/codec.py            the character table. The single source of truth for encoding
tools/dotfont.py          verifies and loads the approved proportional-font source/spec
tools/fontaudit.py        audits translated text against measured physical pixel budgets
tools/fontbakeoff.py      renders candidate previews and models hostile menu tile peaks
tools/propvwf.py          opt-in approved proportional dialogue composer
tools/menuvwf.py          proportional menu/help/seal composer and guarded allocator
tools/menuspill.py        plane-exact live verification of composed menu rows
tools/itempagespill.py    real-save atomic item-page transition verifier
tools/floorinfospill.py   real-save Floor action/Info transition verifier
tools/scrollinfospill.py  Log-2 five-choice Scroll Info-return/border regression
tools/storagepotinfospill.py Log-2 six-choice Pot Info-return/border regression
tools/gitanmenuborderspill.py Log-2 three-choice Gitan Info-return/border regression
tools/gitaninfospill.py   Log-3 three-choice Gitan Info-dismissal regression
tools/decoyname.py        removes the runtime Japanese Decoy Staff name prefix
tools/decoynamespill.py   Log-1 decoy attack/live-player-name regression
tools/keyakigiftspill.py  Log-2 Keyaki Otogiri Herb reward/hidden-entry regression
tools/pathspill.py        real Log-2 Path selection/alignment verifier
tools/mainmenuspill.py    real-save atomic title/difficulty/Rankings verifier
tools/nameflowspill.py    Copy -> Erase -> New Log native-tile lifetime verifier
tools/nameaudition.py     audits/reflows every line against legal six-character names
tools/mesen_spawn_blank_scroll.lua  Mesen probe for the GB ROM's unused item-$66 remnant
tools/mesen_spawn_action_pots.lua   safely adds Back + Todo pots for behavior fixtures
tools/mesen_spawn_mouse_don.lua     live native level-3 Mouse Don/EXP diagnostic
tools/enemyexp.py       guards all 303 native enemy-tier rewards against ROM collisions
tools/potseespill.py      real Log-1/Log-2 Floor -> See empty-Pot text and compact-title geometry
tools/actionpotspill.py   real Back/Todo Pot three-charge `Press` VWF regression
tools/conditionspill.py   real five-row clear-condition allocator/plane test
tools/rescuespill.py      Nagi route; conservative interiors + ordinary-choice isolation
tools/koppastairspill.py  cross-bank ordinary-stair choice; Koppa/Nagi/Fumi regression
tools/koppatalkspill.py   shared Koppa phrase; one-press town + dungeon-context regression
tools/copylogspill.py     direct + post-Quit Erase -> title/Copy Log plane regressions
tools/structvwf.py        fixed-position font fragments around immovable live fields
tools/structspill.py      status/Fay redraw/name-grid control verifier for those fragments
tools/rankvwf.py          guarded proportional rankings-list name renderer
tools/rankspill.py        rankings pixels/queue/page-offset/native-control fallback verifier
tools/orochisymbolspill.py real badge/Rankings/native-graphics lifetime regression
tools/intro.py            extracts/validates/compiles the cinematic TSV and font packs
tools/floorcardgen.py     bakes the supplied Poppins mock-up process into stable masks
tools/markers.py          shared 160x24 town/dungeon card renderer and ROM installer
tools/markerpreview.py    contact sheet of all eight representative arrival cards
tools/markerspill.py      exact fresh-cart Moonlight Village raster/fade regression
tools/floormarkerspill.py exact Forest 1F + all marker forms/floors 1-50 regression
tools/dragonmawmarkerspill.py real Log-1 floor-19 Dragon's Maw centering regression
tools/waitcard.py         English active-dungeon Continue bubble installer
tools/waitcardspill.py    real Log-3 loading-card tile/map regression
tools/titlecard.py        approved full-screen pre-intro copyright-card installer
tools/titlecardspill.py   exact 160x144 card raster/palette/fade-path regression
tools/titlelogo.py        approved four-colour title-screen installer
tools/titlelogospill.py   full 160x144 title and PUSH START/file-menu regression
tools/endingcreditsaudition.py  generates/audits the complete 22-card Poppins roll
tools/endingcredits.py    installs every translated card without changing native timing
tools/endingcreditspill.py Hard-ending exact-card/order/timing/final-End regression
tools/introspill.py       edited-TSV, timing, transition, input and emulator verifier
tools/introplayback.py    forces and records the translated ending as a looping GIF
tools/proptiming.py       verifies renderer/map work stays inside its scheduler frame
tools/propupload.py       follows composed bytes through the real VBlank upload

assets/fonts/thin_pixel_7_compact.json        approved production-font spec
assets/fonts/thin_pixel_7_compact_glyphs.json adapted 8x8 production glyph rows
assets/fonts/moonlit_sans.json                prior original-font spec/comparison
assets/fonts/moonlit_sans_glyphs.json         project-original glyph drawings/digits
assets/fonts/dot_gothic_shiren.json           earlier font retained for history
assets/graphics/arrival_cards_poppins.json    stable one-bit labels/floors 1-50
licenses/Thin-Pixel-7.txt                     upstream freeware-use terms and credit
licenses/OFL-1.1-Dot-Gothic.txt               license for the retained Dot Gothic asset
licenses/OFL-1.1-Poppins.txt                   license for the arrival-card source font

TRANSLATING.md            the rules a translator needs. Read before a large edit
FINDINGS.md               how the ROM works — encodings, renderers, control codes
HANDOFF_NEXT.md           concise current state, remaining work and task routing
HANDOFF.md                durable low-level tools and traps reference
docs/archive/README.md    index of completed historical handoffs
```

Only `HANDOFF_NEXT.md` is required onboarding. `HANDOFF.md` remains a durable technical
reference, while completed subsystem handoffs are preserved under `docs/archive/`; none
of those historical records needs to be read front to back.

## 7. Translating into another language

Nothing here is English-specific except the font and the glossary.

1. **The font.** The default build uses the approved Thin Pixel-7 GB Compact proportional renderer;
   its glyphs replace kana tiles that an English script does not use. A measured
   uniform-6px control remains available by omitting `--dot-font` from a direct
   `tools/build.py` invocation. See §8. For a language
   needing different glyphs, replace the font source and regenerate its width table. The
   renderer's pixel audit must pass before relying on a translated line's measured width.
2. **The glossary.** Replace `script/glossary.tsv`'s English column. The checks are about
   *consistency*, not about English.
3. **The script.** Clear `script/en.tsv` and work through `script/script.tsv`, which lists
   every string with its Japanese and its address.

The physical/source/tile/runtime budgets in §4 and `VWF_BUDGETS.md` are properties of the
ROM and renderer and apply to any language; character widths come from that language's
approved font.

## 8. Font design and provenance

The approved baseline is **Thin Pixel-7 GB Compact**. Its letters and punctuation are
adapted from the exact binary 20ppem strike of Thin Pixel-7 version 1.0. The `g/p/q/y`
bodies retain the normal lowercase baseline and complete two-row
tails while one repeated bowl/stem row is omitted; one repeated stem row is removed from
the otherwise nine-row lowercase `j`. The font's bundled EULA permits use
in freeware software with credit; commercial or business use requires a separate license.
The full upstream license and attribution notice is preserved in
[`licenses/Thin-Pixel-7.txt`](licenses/Thin-Pixel-7.txt). The TTF itself is not redistributed.

The production source remains reviewable text:
[`assets/fonts/thin_pixel_7_compact_glyphs.json`](assets/fonts/thin_pixel_7_compact_glyphs.json)
contains all 77 adapted pixel drawings, while
[`assets/fonts/thin_pixel_7_compact.json`](assets/fonts/thin_pixel_7_compact.json) records
their advances, source hashes, attribution and provenance. Its numerals use compact,
playtest-reviewed drawings with uniform 5px tabular advances; the comma, question mark and
colon carry the matching symbol refinements, while `+` and `-` use centered three-pixel
forms with 5px advances. The complete dialogue and clear-condition audits remain the
acceptance gate at 144px and 57 tiles respectively.

Town and dungeon arrival cards deliberately use a separate display face: **Poppins Medium
v4.004**, under the SIL Open Font License 1.1. The two approved 6x mock-ups are the
authoritative `Moonlight Village` and `1 Forest` rasters. `tools/floorcardgen.py` retains
the supplied 12px-cap, 8x supersample and one-bit threshold process; its output is baked
into [`assets/graphics/arrival_cards_poppins.json`](assets/graphics/arrival_cards_poppins.json)
so ordinary ROM builds do not depend on a system TTF or a particular FreeType version.
The full license is in
[`licenses/OFL-1.1-Poppins.txt`](licenses/OFL-1.1-Poppins.txt).

**Moonlit Sans** remains in the repository as the prior approved font and a comparison
target. It was drawn from scratch for this project with no copied Espy font data. Dot
Gothic Shiren remains as earlier project history with its upstream SIL Open Font License
in [`licenses/OFL-1.1-Dot-Gothic.txt`](licenses/OFL-1.1-Dot-Gothic.txt).

### Auditioning a font candidate

`fontbakeoff.py` accepts a TTF/OTF, a 128x112 GB Studio variable-width PNG, or one of the
project's approved JSON font specs. It renders the candidate against the same dialogue,
descender, punctuation, numeral, item, menu and alphabet samples, then prints the hostile
menu-tile peak and whether those rows can be packed into the real allocator runs.

To compare the production font with its declared reference:

```sh
python3 tools/fontbakeoff.py assets/fonts/thin_pixel_7_compact.json \
    --output build/thin_pixel_7_comparison.png
```

To audition an external candidate without changing the ROM:

```sh
python3 tools/fontbakeoff.py "/path/to/candidate.ttf" \
    --output build/font_candidate.png

# A GB Studio sheet must be exactly 128x112 and use its magenta width columns.
python3 tools/fontbakeoff.py "/path/to/candidate.png" \
    --output build/font_candidate_sheet.png
```

The TTF/OTF path deliberately rejects antialiasing at 8px; accepting a smoothed preview
would not prove that the glyph has a usable native Game Boy strike. Inspect the generated
sheet at integer zoom, especially `g/p/q/y/j`, `I/l/1`, punctuation, tabular numerals and
signed equipment suffixes. A printed `runs PASS` and an in-budget peak establish allocator
feasibility, not aesthetic approval or whole-game safety.

For a serious candidate, create a reviewable JSON spec and 8x8 row source following the
two `thin_pixel_7_compact*.json` files, including authorship, license, source hash and an
advance for every supported glyph. Then run the complete translated-corpus audit:

```sh
python3 tools/fontaudit.py --font-spec assets/fonts/candidate.json
```

`--font-spec` is review-only and does not modify the production build. Promoting a font
means deliberately changing `dotfont.py`'s approved default/spec assets and then running
`tools/dotfont.py`, `tools/nameaudition.py` and the complete `build.sh` emulator battery;
never replace the production source merely because the bakeoff sheet looks good.

The default `build/shiren_en.gb` is the verified proportional dialogue-and-menu build.
To reproduce it directly instead of through `build.sh`:

```sh
python3 tools/build.py build/_base_expanded.gb script/en.tsv \
    build/shiren_en.gb --dot-font
```

The build passed emulator timing, byte-exact VBlank upload, screen-spill, long crash,
pixel-audit, shuffled-layout, and screenshot checks. Its deterministic loader verifies the
source hash and approved edits. All eight place labels are now measured at their real
consumer. The bare `Dragon's Maw` label paints 63px inside its 64px advance; save-summary
box 26 separately reserves ten proportional tiles for the complete numbered location row,
so `19F Dragon's Maw` also fits without entering the following difficulty row.

Dialogue, main-menu verbs, item names, action labels such as `Remove`, item-information
text, all 20 equipment seals, and measured ROM labels such as `Gitan`, `Path`, `Which?`,
category pages, `Kuyou`, and `Rankings` now share the approved proportional widths and
eight-shift glyph table. Static ROM headings compose from their first letter; only measured
cursor cells remain independent fixed tiles. The five widest current item variants use
55 allocator tiles; combined with four 4-tile action verbs, the hostile measured stack
uses 71/72 tiles across the proven `$43-$7B`, `$8B-$95`, and `$9A-$9D` runs. The first
item that fits 11 tiles uses the 11-tile run; page row 0 is not treated as a width class.
The help/seal/clear-condition path accepts 21 staged characters and uploads physical rows through 16
tiles using two overlapping queue pens. Real help, every seal group, and synthetic wide
rows pass plane-exact checks in both LCD-off and LCD-on paths. Clear-condition box 44 now
uses that proportional path for all 40 labels; its widest possible current five consume
57/57 primary-run tiles, and `conditionspill.py` verifies both those rows and an exact
21-glyph fixture plane-exact. The production TSV uses the
21-glyph/144px proportional contract; the old 18-cell path remains a diagnostic control and does
not dictate English wording.

The title-menu submenu is `Rank/Pass`, and its second entry is `Pass`. The game
stores 40 cumulative award flags, but it does not store 40 independent passwords: the
native four-kana field above the list was generated from the selected log's overall state.
Because those codes become meaningless Latin strings after replacing the Japanese font,
the English build replaces the field with a literal `Pass` heading in the native box.
`tools/awardspill.py` follows the real save-backed route, checks that exact
heading, verifies every award in native flag order against an untouched Japanese control
ROM, rejects a blank final screen, and pages through all eight five-row screens:

```bash
python3 tools/awardspill.py build/shiren_en.gb \
  --ram saves/shiren_en_log_1_password.srm \
  --matrix --control build/_base_expanded.gb \
  --csv build/award_passwords.csv \
  --all-png build/awardspill_all_page8.png --frames 2300
```

For manual inspection in Mesen, run `tools/mesen_unlock_all_awards.lua`, open
`Rank/Pass → Pass`, choose a log, and use Up/Down to inspect all eight pages. The
helper temporarily changes only the selected log's live WRAM award bitfield and keeps it
active through the screen's intermediate dispatches. It restores the exact original bytes
when the real title menu is reached again; use a backed-up save and do not stop the script
while the Awards screen is still open.

Item page changes deliberately transition from the old screen to a brief white LCD-off
interval, then to the complete new page. Blank and publish each begin at a fresh VBlank
boundary, so neither 80-cell update can be scanned out partway; a frame-by-frame check
rejects any old/new mixture. Floor action -> Info, Info page -> page and Info -> action use
the same contract, including the completed help border, arrow and page counter. Title,
file and difficulty composites likewise stay hidden until the whole shadow map is ready.
Rankings uses one proportional `$80-$A6` allocation for its five-tile heading, three-tile
difficulty labels and five five-tile names. LCD-on title Rankings transfers each name
through the native VBlank queue behind the blank `$9C00` map, then reveals the complete
`$9800` board in one transition; LCD-off rescued-child results use the synchronous direct
path. The Kuyo and Village Exit selectors temporarily use `$C0-$CB`, then the native
menu-font loader restores `$00-$D2` before any adjacent map can reveal the borrowed
single-bank planes. `tools/mainmenuspill.py`
drives the supplied Log-3 and four-record Rankings routes and checks every transition
frame plus persistent title-tile ownership. The five-row pool is admitted only when the
whole page uses the approved name-picker alphabet; old kana records use the original
writer byte-for-byte. `tools/rankspill.py` verifies five hostile names across 25 private
tiles and exact 4+4+1 queue payload windows against the `--no-rankvwf` component control.
Against the complete `--no-menuvwf` native control, legacy page 0 and nonzero page 1 each
take the raw writer 5/5 with the full visible board, framebuffer, display state and OAM
semantics exact. The page-1 fixture proves prevalidation starts at `C6AC * 12` and finds an
unsupported code in the fifth selected row.
`tools/orochisymbolspill.py` supplies the adjacent-screen ownership proof against a native
control, including the real Orochi badge, complete Kuyo/Village boards, native status/OAM
and repeated returns. All related checks pass on normal, shuffled and redirect-all layouts;
the exact repeated route is also visually approved in Mesen. The fixed ranking fields now use `1.` ordinals,
`F` floors, `x` attempt counts, and `Easy` / `Norm.` / `Hard`. The fixed fields eliminated the remaining
Japanese suffix and difficulty tiles. A few fields intentionally remain fixed. The status
values (`0 G`, `2 F`, and `Easy` / `Normal` / `Hard`) are absolute, aligned bank-4
writes; `pathspill.py` proves the three Path choices end at the same column without
touching the border. The name-entry keyboard is a cursor lookup table with one selectable
character per cell. Its fixed coordinates remain unchanged, but its five rows now use all
75 selectable cells deliberately: A-Y occupy the left block, Z/a-x the middle, and y-z,
13 punctuation marks and 0-9 the right. The raw picker cannot expand DTE, so box 12 is
explicitly barred from compression. V3 leaves the renderer fixed-cell while
`Weapon/Shield/Str/Exp` and Fay's `No`/`Rating` render from fixed-position font fragments.
Fay's task number and stars still overwrite their original cells, including after the
independent bank-4 redraw. `tools/structspill.py` verifies both status rows plane-exact,
drives the real blank-cart Fay route from task 1 to 6, and covers saved-summary, Rank, and
`Pass → No awards.` routes into Fay. Fay now restores all ten VWF-borrowable
heading/star/checkbox/separator tiles unconditionally at its own entry boundary; the test
poisons every one immediately before entry and requires an exact recovery. It also
requires the name grid to remain pixel/shadow
identical to a `--no-structvwf` control. The title, Log selector, save
summaries, all three erase confirmations, Rank/Pass, and all three difficulty explanations
use measured context-specific pools. `tools/menuromspill.py` verifies the 19 approved ROM boxes.
`tools/startspill.py` exercises all three erase logs and Rank/Pass with exact shadow,
two-plane, visible-lifetime, and static-tile collision checks; normal and shuffled builds
each pass 84 exact rows (the current normal build records 16,241 live checks). See
`docs/archive/HANDOFF_MENUVWF.md` for the tile
census and structured exceptions. `tools/savesummaryspill.py` adds the three supplied
Log-1 variants: numberless `Dragon's Maw`, full `19F Dragon's Maw`, and `5F Koma Cave`.
It requires the exact VWF payload, intact `Hard` row, shadow map and both tile bitplanes.

The retained Dot Gothic font software and its modified version are distributed under the
**SIL Open Font License 1.1**. The required copyright notice and complete license are in
[`licenses/OFL-1.1-Dot-Gothic.txt`](licenses/OFL-1.1-Dot-Gothic.txt). That license applies
to the font software and derived glyph data; it does not change the status of the game ROM
or grant permission to distribute Nintendo/Chunsoft game data.
The Poppins-derived arrival-card masks are distributed under the separate OFL notice in
[`licenses/OFL-1.1-Poppins.txt`](licenses/OFL-1.1-Poppins.txt).
The ending-credit source roster, including every Japanese role/name for audit, and the
approved two-bit graphical payload are frozen in
[`assets/graphics/ending_credits_poppins.json`](assets/graphics/ending_credits_poppins.json).
Run `python3 tools/endingcreditsaudition.py --font Poppins-Medium.ttf --frame
frame_15060.png --output build/ending_credits_complete_audition.png` to regenerate the
complete contact sheet;
`tools/endingcreditspill.py` proves that all 22 cards appear once in native order, use the
approved pixels and durations, retain the animated forest, and reach the native Japanese
end mark. It reconstructs the displayed tilemap raster and compares the fully faded live
screen rows too; checking uploaded VRAM bytes alone once allowed row-major tile data to
pass despite producing visibly interleaved fragments.

## 9. Honest limits

* **Graphics are complete for known routes** — the pre-intro card, illustrated title, all
  town/dungeon arrival cards, active-dungeon Continue bubble and all 22 ending-credit
  cards are English. The final Japanese end mark remains native by request. Credits are
  frozen graphical tile strips rather than ordinary script text.
* **`coverage.py` gates both known alphabets and declared runtime starts.** Its ordinary
  `codec.py` scan and cinematic VM/table census are reported separately. The ten former
  bytecode-embedded script-bank candidates are now tied to code, pointer, graphics or
  animation consumers and exact-byte guarded as non-text. It still cannot prove that no
  event enters the middle of already covered bytes; the Nagi stair route did exactly
  that. Emulator route scans remain required during playtest and the V6 freeze.
* **The visible name-entry grid is English but deliberately fixed-cell.** It is a selectable
  lookup table, so one character must remain at each cursor coordinate rather than using
  proportional layout. The six Japanese records for the old second page remain only as
  aliased, unreachable storage; both internal page branches address the English grid.
* **Blank Scroll is unused internal data, not an unfinished screen.** The ROM retains its
  name and object ID `$66`, but no reachable `Write` action or scribing interface. A
  ROM-correct injected object reuses the Lost Scroll description and is consumed when read;
  `tools/mesen_spawn_blank_scroll.lua` exists only to reproduce that classification.

## 10. Contributing

Wording changes to `script/en.tsv`, `script/intro.tsv`, `script/prose_draft.tsv` and
`script/glossary.tsv` are the easiest and most useful contributions — run §5's checks and
include what they printed.

Code, layout and graphics changes should include the narrowest relevant headless-emulator
regression and, where appearance is part of the change, a screenshot from the built ROM.
Font or art submissions must identify their source, author and license; use §8's audition
workflow before proposing a production-font change.

Do not commit ROMs, save files, `build/`, or `script/script.json`. `.gitignore` already
blocks all four; if something game-derived gets past it, that is a bug in the ignore rules.

*Distributed as tools and a translation only. No copyrighted game data is included, and you
must supply your own copy of the original cartridge.*
