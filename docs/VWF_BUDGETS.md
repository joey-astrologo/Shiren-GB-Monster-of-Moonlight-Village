# VWF budget register

**Current contract reviewed 2026-09-08.** This is the canonical answer to “does this text fit?” after the
Thin Pixel-7 GB Compact migration. Cinematic text has its own completed VM/pack contract and
is intentionally outside this reset. Implementation sources for each rule are indexed in
[`TEXT_REFERENCE.md`](TEXT_REFERENCE.md). Dated measurements below retain their original
context; regenerate `fontaudit.py --details 4 --strict-unproven` for the current text.

A single character count is not a fit verdict. Every non-cinematic renderer can have four
independent constraints:

1. **Physical pixels** — the painted extent available on screen.
2. **Source staging** — how many encoded glyphs the current ROM loop reads or retains.
3. **Temporary tiles** — how many composed tiles and contiguous allocator slots exist.
4. **Runtime variants** — names, signed modifiers, counters, numbers and player input
   inserted after the TSV string was built.

If text fits in pixels but crosses a source guard, the guard is an engineering limit—not a
reason to abbreviate English. If it crosses the physical edge after the source path accepts
it, wrapping or wording must change.

## Current measured contracts

| Renderer | Physical geometry | Production source contract | Temporary/runtime constraint | Acceptance evidence |
|---|---|---|---|---|
| Dialogue composer | 144px × 3 lines | **30 staged glyphs per line** | Runtime substitutions share both 30 glyphs and 144px | 30-entry reveal map; 625 plane cases / 30,090 checks; worst renderer pass 153/154 scanlines |
| Item list | 128px payload in an 18-tile row | **18 glyphs including suffix** | 72 allocator tiles in runs 57+11+4; each row needs 4, 8, 9–13 or 16 contiguous tiles | All 145 names and every signed/`[NN]` representative; exact plating/curse regressions; canonical fused counts 1–9 on two pages; all nine fusion glyphs at all eight pixel residues in Items and Info |
| Item descriptions | 144px × 4 lines | **21 staged glyphs** | Shared `$C616` staging and overlapping queue pens | Real help plus synthetic-wide plane checks |
| Equipment seals | 144px × 1 line per seal | **21 staged glyphs** | Up to four seal rows after one item name | All 20 seals photographed and plane-exact |
| Clear-condition list | 144px × 5 visible rows | **21 staged glyphs per row** | 72 allocator tiles in runs 57+11+4; current worst five use 57/57 primary-run tiles (2026-09-08 audit) | `conditionspill.py`: widest five plus exact 21-glyph edge, plane-exact |
| Main/action/start/Ground menus | Descriptor width minus measured raw cells | Shape-specific; the shared staged scanner admits at most 18 glyphs | Shared menu allocator and context-specific pools; Ground box 5 has one raw cell | `menuspill`, real-save `groundspill`, `menuromspill`, `startspill` |
| ROM menu rows | Descriptor width minus approved raw prefix | Ends at the row's actual ROM terminator | Deterministic per-box tile pools | Approved box census only; unknown shapes fall back native |
| Rankings | Measured five-name slices | Six stored player-name characters | **COMPLETE:** one screen-scoped allocation with native restoration; VWF remains mandatory | `rankspill` plus the replacement `orochisymbolspill`; see the menu VWF implementation record below |
| Status / Fay structured rows | Fixed field coordinates plus proportional fragments | Per-fragment, not a prose-line cap | Numeric values and selectors deliberately remain fixed-cell | `structspill` against native control |

The old uniform-6px renderer's 24-character line and the native renderer's 18-cell line
remain useful diagnostic controls. Neither is a production English limit.

## Dialogue: why 30 is safe

The visible canvas is unchanged: 18 tiles = 144px. The production proportional composer accepts
30 source glyphs and clips composed ink at that edge. It does not pixel-wrap at runtime.
`tools/wrap_en.py`, `dialogue_preview.py`, `build.py`, and `fontaudit.py` therefore test two
separate conditions:

- no more than 30 staged source glyphs;
- no painted pixel beyond x=143.

The typewriter cannot use a naïve contiguous 30-byte extension. `$C0FE/$C0FF` are live
game-owned bytes. Its reveal map uses `$C0E2-$C0FD` for entries 1–28 and independently
measured-free `$C0D6/$C0DD` for entries 29–30. One helper moved to pool bank 38 at
`38:$405A`; after the real Ground-header correction, bank 32's menu VWF blob ends exactly
at `$8000` with no tail bytes free. Further bank-32 code requires relocation or a measured
size optimization, not an assumed padding byte.

Timing remains inside the measured VBlank budget: worst full renderer pass 153/154
scanlines, reveal-map pass 92/154, with no unfinished pass. The build also proves every
current translated line selects the proportional path before pixel 72; the sole apparent exception
is the already-calibrated non-rendered extraction false positive at `14:$7EE6`.

The permissive 30-glyph source policy changed some automatic source-only box boundaries.
The reset's seeded message-duration comparison saw 11 boxes versus the old 24-glyph build's 15. This
is expected reflow, not memory corruption; visual review may restore authored `<br>` or
`<brk>` where pacing benefits.

**Retracted stairs exception — `14:$5AFD`:** this interior entry was reached while an
ordinary-stair pointer was corrupt. Corrected Nagi, Koppa and Fumi stairs stage the shared
bank-14 choice at `14:$46C1`. `rescuespill.py` verifies that the conservative interior
records remain intact and are not staged by ordinary stairs. Retain their reviewed text
and controls, but do not infer a universal terminal `<end><brk>` rule from them.

## Signed True Rapier census

This is the retained fixture census from the font migration. The current glossary-wide
audit is broader: on 2026-09-08 its widest item variant is `Battle Counter-99`, with
17 source glyphs, 84 painted pixels and 11 allocator tiles; the five widest item rows
plus four 4-tile verbs use 71/72 tiles.

Thin Pixel-7 GB Compact gives several two-digit signed suffixes the same peak width. `-99` is the
audit's deterministic representative, while `-77` remains a stable regression fixture:

| Live text | Source glyphs | Font advance | Painted extent | Result under 30/144 |
|---|---:|---:|---:|---|
| `Got True Rapier-77` | 18 | 91px | 90px | fits |
| `Took True Rapier-77` | 19 | 96px | 95px | fits |
| `Put down True Rapier-77` | 23 | 116px | 115px | fits |
| `Equipped True Rapier-77` | 23 | 115px | 114px | fits |
| `Removed True Rapier-77` | 22 | 112px | 111px | fits |
| `Stepped on True Rapier-77` | 25 | 125px | 124px | fits |

These forms retain substantial room in the 144px dialogue canvas. The runtime item
formatter emits the English hyphen code `$42` instead of native `$7D`; previously the
late unsupported byte became an 8px blank and could clip a trailing digit after a drop.

The widest `Stepped on True Rapier±44/±47/±74/±77` forms share the same 125px advance /
124px painted extent. No signed True Rapier variant clips. The
63 generic runtime-substitution reservations remain explicitly historical review labels;
replacing them with measured producer classes is optional research, not a known repair.

The item-list version is a different path. `True Rapier-77` is 14 source glyphs,
71px advance, 70px painted, and 9 allocator tiles in its 128px payload. The synthetic
hostile page uses that row, four 11-tile counter rows and four 4-tile verbs: 69/72. The allocator
gives the 11-tile run to the first row that fits it rather than assuming page row 0 is
always narrow. Runtime plating can append native `★`; `equipmentmarkerspill.py` proves
that `True Rapier+99★` remains proportional alongside the cursed-item prefix. Fused
weapons and shields append one native count glyph: the canonical masks contain at most
nine bits, so the complete emitted range is `$8C-$94` (counts 1–9) and `$95` is rejected.
`fusioncountspill.py` constructs all nine canonical counts over two real Item pages and
opens count 9 in Info; `menuglyphspill.py` additionally renders all nine at every pixel
residue in both consumers. The 18-glyph source guard remains available for other long
names plus runtime suffixes.

Player-assigned identities use a separate native producer: it emits a category prefix,
then copies the six-character name stored in SRAM. The translated prefixes are
`Bracer: `, `Herb: `, `Scroll: `, `Staff: `, `Pot: ` and `Blank: `. The shared helper is
executed for every category at build and regression time, including categories that must
emit no prefix. `playernamedspill.py` also combines every translated prefix with a widest
six-character nickname and requires no more than the Item row's 11-tile slice, then boots
the supplied Log-1 fixture and checks real `Bracer: Food` and `Staff: Poop` rows
plane-exact on the last Items page.

Shop-held inventory rows have another shape-specific suffix contract. After the ordinary
two raw Item cells and name, the native formatter right-aligns one three-tile price slot
per physical row: `$D0-$D2`, `$D3-$D5`, `$D6-$D8`, `$D9-$DB`, or `$DC-$DE`. These are
tile IDs, not character codes; their pixels can hold a five-digit amount. The
original formatter allowed only 13 name cells here, so it discarded `rb` from
`Invincible Herb` before VWF could compose it. The proportional build widens the staged
pre-price area from 15 to 20 cells: two raw cells plus the complete 18-source-character
VWF contract. The scan ends before the exact price slot and restores it after padding
the name row.
`shopspill.py` exercises all five slots independently of preceding name length, checks
the `Price`/`G` headings and real 500G Strength Herb row, and replays the supplied Log-3
3000G Invincible Herb failure at row 4 with the complete name plane-exact. A controlled
copy of that same route
changes the ROM price-table entry to the calculation cap, 65000G, and requires the native
formatter to report 65000 while the VWF row and `$DC-$DE` cells remain exact. The
145-entry base table tops out at 62000 for reserved `New ...` entries; the highest
ordinary named base item is 50000G Rasen Fuuma. The shop calculation clamps purchase
prices at 65000 and sale values at 32000.

## Runtime substitutions

`<var>` and `<cE3>` do not name one universal kind of value. A producer-to-template census
could refine their classifications, so the historical `NAME_CAP=14` and `ITEM_CAP=16`
constants survive only as labelled review thresholds in reports. They are not lint
failures, are not a release blocker, and must not be used to shorten glossary names or
rewrite translations without a concrete failing runtime route.

Build-time clipping checks charge an unknown runtime value its narrowest possible glyph.
That catches lines which can never fit under any value. The player name is no longer in
that unknown class: build, wrapping and preview checks charge `<name>` all six source
glyphs and the widest possible approved six-character pixel footprint. `fontaudit.py`
separately reports the remaining unknown templates that cross the old reservations so
they stay visible until the runtime producer census can replace them with exact classes.

Known fixed variants are stricter:

- item rows enumerate every modifier from `-99` through `+99`;
- staff/pot rows enumerate ordinary one- and two-digit `[NN]` counters;
- `<cF0:xx>` help fragments are measured from the actual translated bank-11 strings;
- the six-character player name is enforced as a real storage/input/rendering contract;

## Tool and translator policy

- `sh build.sh` builds the ROM, then runs `lint_en.py` and `fontaudit.py` automatically.
- `wrap_en.py` uses the approved font and fills prose against both 30 source glyphs
  and 144 painted pixels. It no longer wraps around legacy 14/16 reservations.
- `dialogue_preview.py --check` reports `line_too_long` and `line_too_wide_px`
  independently and knows the 30-glyph dialogue and 21-glyph help/seal geometries.
- `fontaudit.py` uses painted extent as clipping authority and enumerates fixed runtime
  item variants against both physical pixels and source scanners.
- `lint_en.py` protects token/glossary semantics plus the real 18-glyph item-row scanner;
  it has no universal glossary-name length failure.
- `menuspill.py`, `itempagespill.py`, `floorinfospill.py`, `conditionspill.py`, `boxspill.py`,
  `menuromspill.py`, `playernamedspill.py`, `startspill.py`, `rankspill.py`, and
  `structspill.py` remain the live acceptance tests for allocation and screen behavior.

The policy is deliberately close to the edge: accept exact 30-glyph or 144-painted-pixel
fits, then correct concrete visual/pacing conflicts rather than preserving speculative
headroom. Do not extend that policy to an unmeasured renderer shape; measure its source,
pixels and temporary storage first.

## Current status and remaining work

The [repository README](../README.md) records accepted release hashes and battery results;
[MENU_STRUCTURE.md](MENU_STRUCTURE.md) records exact menu routes and visual acceptance.
The following reconciles the earlier V4–V6 worklist as of 2026-09-08:

- **V4A — optional runtime research:** the complete `<var>`/`<cE3>` producer-to-template
  census remains open. The current strict font audit reports **zero definite physical/source
  failures, 27 legacy line-reservation warnings and zero unproven translated geometries**.
  Do not shorten translations to clear historical warnings; investigate a concrete failing
  value/route or an explicitly requested census.
- **V4B — playtest and text intake:** wording, spacing, pacing and newly reached routes
  remain open to review. Ordinary companion stairs use `14:$46C1`; the former `$5AFD`
  one-window stairs contract is retracted. Any font metric change requires renewed pixel,
  variant and allocator checks.
- **V4C/D — geometry and static completeness:** known paths are complete. Current box
  geometry and retained width exceptions live in `script/build-inputs/box_geometry.tsv`.
  Static coverage cannot prove every dynamic event entry has been discovered.
- **V4E/F — Start and Item/Floor rendering:** the catalogued same-menu regional work,
  checkpoints 1–4, Start S1–S4 and follow-up findings IFR-01–IFR-09 are implemented,
  regression-covered and visually accepted. Dormant fallbacks are distinct from remaining
  route work. Follow `MENU_STRUCTURE.md` for the exact admission boundaries.
- **V5 — graphics and cinematics:** known routes are complete. Production VWF uses
  Thin Pixel-7 GB Compact; arrival labels use approved source rasters and ending credits
  use Inter SemiBold. Cinematics retain their separate `intro.tsv` VM/pack contract.
- **K1/K2 and R3 — companion stairs/exits and Rankings:** the known defects are fixed
  and covered by real-save regressions. Conservative interior records remain manifested
  and isolated from the ordinary stairs route.
- **V6 — release:** the full normal, shuffled and redirect-all battery passed on
  2026-09-07, including the clean-checkout artifact reproduction recorded in the README.
  Continue manual hardware/emulator playtesting before the final release tag. A new
  translation or renderer change must pass the applicable gates again.

The ROM's `$66` Blank Scroll name/object slot remains classified unused: no reachable
Write action or scribing screen is known. It adds no current localization task.

## Menu VWF implementation record

**Historical implementation record:** these are the measured deltas that shaped the
renderer, including superseded shapes and allocation stages. Current contracts are in
the table above; current implementation is in `tools/menuvwf.py`, and memory ownership
is in `ROM_BANK_MAP.md`.

The initial rows were allocated by a WATERMARK ALLOCATOR over pool `$43-$7B` (57 tiles),
records keyed by SHADOW DEST at `$C163-$C1B2` (16 × 5: key, base, cap, raw cells),
reset by a far-call hook on the font upload `13:$7643` (far index 9). Tile 12 of a
13-tile row composes into `$C12C-$C13B` — the `$C006` queue's flat space holds exactly
12 tiles, which is what really capped the POC at 16 chars. Upload footprints are
TIERED: 4 tiles for n<=4 (idempotent slot stacking), 8 for 5-8, the native 4+4+1 shape
plus a backward last-4 window for 9-13. `tools/wramfree.py` (static opcode+boundary
voting + per-frame dynamic watch over menus/walks/35 forced screens) is how every WRAM
run above was proven; `tools/menuspill.py` is the verifier (plane-exact vs a python
composition from the ROM's own glyph table; `--long` drives real worst-case rows).

0. **(Round 2, from Joey playing his own save — both fixed the same night.)**
   **The equipped marker `$84`/`$86` does DOUBLE duty**: it selects the left border
   ($83/$85) AND is drawn as the row's column-1 cell — tile $84 IS the E glyph.
   FINDINGS' "select $83/$85 instead" reads as border-only and is easy to
   half-implement: consuming the marker shifted composed E-rows one cell left and put
   the cursor over their first tile. The control build's SHADOW dump (`83 84 81
   codes...`) is the authority. And **exact-size slices are wrong across PAGE FLIPS**:
   page 2 restages all five rows with different text, so reusing page-1 caps left most
   rows raw — row 0 of an allowlisted box now rewinds that box's record tail (keys
   hl+64i) and every full redraw reallocates fresh. The main menu + action menus were
   whitelisted for part of the night and REVERTED: their session-long records held
   20-36 of 57 pool tiles and starved full item pages — they need the extension.
1. **Six English glyphs live INSIDE `$40-$7F`**: `, ' - + [ ]` at $40/41/42/7C/7E/7F.
   §2's "referenced by no English menu screen" was measured on screens without
   counters or punctuation — the `[N]` counter writer `4:$5D58` writes `$7E`/`$7F`,
   and five item names carry `-`. The POC's fixed slices covered `$41/$42` (latent
   glyph stomp); the pool now EXCLUDES all six and eligibility ACCEPTS them as codes.
2. **The raw-cell prefix is SHAPE-DEPENDENT**: w18 item rows stage TWO leading zero
   cells, the w7 main menu and w9 action menus stage ONE. A fixed two-zero test made
   every main-menu row fall back silently — and the narrow, left-aligned latin font
   made the raw result LOOK composed in a screenshot. Only the far-call trace
   (`$C0D8` never moving) told the truth. Verify composition by allocator state or
   plane comparison, never by eye.
3. **Eligibility must be a DESCRIPTOR SHAPE ALLOWLIST, not a flags test**: box 25
   (x5 y9 w9, dynamic, WRAM-staged, English — the over-dialogue picker) passes every
   flags-only rule and draws on screens whose `$9000-$97FF` holds TERRAIN, not the
   font. Composing is only safe after a font upload; the allowlisted shapes are all
   dispatcher screens. install() asserts the BUILT descriptors match the asm constants
   so a box_geometry.tsv edit fails the build (the layout-duplicated-in-code trap).
4. **Records must REUSE ACROSS SCREENS of one session and GROW**: the font upload only
   fires at session open (main menu -> item list -> action menu share one pool), and
   shadow row 4 is BOTH main-menu "Quit" and item row 0 — same key. A reused record
   too small for its new text grows iff it is the top watermark allocation, else that
   row falls back raw. This is also why footprints are tiered: a flat 9-tile floor let
   four short main-menu verbs hold 36 of 57 tiles and starve 5-item inventories.
5. **Bank 32's far-index table has a ONE-BYTE stride** — entries overlap, so live
   indices are odd: name6 3, vwf 5, menurow 7, menureset 9.
6. **The font-upload hook shifts walk RNG alignment**: it fires ~once per screen
   transition (measured 1 in 3000 walked frames), and those few cycles move frame
   boundaries, so `msgdur`'s seeded walk meets DIFFERENT boxes than a `--no-menuvwf`
   control (17 vs 9-10; reverting the 3 hook bytes reproduces the control
   byte-identically). Cross-build msgdur comparisons need both builds hooked
   identically; within-build numbers are unaffected.

`13:$7643` has NO literal `call` anywhere in the ROM (the one `call $7643` is bank-4-
local code) — it is reached through a computed path; the hook works regardless, proven
by menuspill's fresh-session reset scenario. The step-4 census scripts live in
`tools/wramfree.py` and this session's scratchpad; the box-descriptor dump one-liner is
in the git log of this file if needed again.
