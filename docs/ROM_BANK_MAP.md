# ROM bank ownership map

This is the allocation guide for the current English build. Read it before placing or moving
ROM code, tables, text, or graphics. A run of `00` or `FF` bytes is **not evidence that a span
is free**: the ending-credit sequencer was once placed over the high-byte plane of the enemy
EXP table because most of that live table happened to contain zeroes.

The constants and exact-byte/checksum guards in the named installer are authoritative. Update
this map in the same commit whenever ownership changes.

## Address notation

- `31:$6DC8-$6E2C` means switchable ROM bank 31, CPU addresses `$6DC8` through `$6E2C`,
  inclusive.
- For a switchable address `$4000-$7FFF`, the raw ROM offset is
  `bank * $4000 + address - $4000`.
- Bank 0 uses its CPU address directly as the raw offset.
- Ranges below are inclusive. “Guarded native patch” means only the owning installer may
  alter the range, after confirming the expected Japanese bytes or SHA-256 digest.

## Native banks: strict no-touch and guarded regions

| Bank | CPU range | Owner / contents | Rule |
|---:|:---|:---|:---|
| 0 | `$0062-$00FF` | `tools/dte_rom.py`: DTE expander | No other allocation |
| 0 | `$3FEC-$3FFF` | `tools/dte_rom.py`: bank-switch helper and guard byte | No other allocation |
| 9 | `$4115-$4117` | `tools/titlecard.py`: pre-intro copyright-card hook | Guarded native patch |
| 11 | `$51D0-$51DC` | `tools/decoyname.py`: decoy-name producer | Guarded native patch |
| 13 | `$7FAA-$7FFF` | Native cinematic pointer table consumed by `tools/intro.py` | Never allocate |
| 15 | `$592F-$5A80` | `tools/name6.py`, `tools/rank6.py`: six-character save-name records/helpers | Exclusive |
| 29 | `$71C4-$7263` | `tools/waitcard.py`: loading-bubble tiles | Guarded graphics patch |
| 29 | `$78C4-$798B` | `tools/waitcard.py`: first loading-bubble tilemap plane | Guarded graphics patch |
| 29 | `$7A90-$7B57` | `tools/waitcard.py`: second loading-bubble tilemap plane | Guarded graphics patch |
| 31 | `$6980-$6AD9` | Native actor/stat readers, including enemy reward construction | Never allocate |
| 31 | `$6ADA-$74B2` | Native actor/stat data; includes all enemy-tier EXP arrays below | Never allocate |
| 31 | `$767E-$76D6` | `tools/endingcredits.py`: exact replacement of native credit driver | Exclusive, SHA-guarded |
| 31 | `$7B40-$7B51` | `tools/endingcredits.py`: credit tilemap builder patch | Exclusive, byte-guarded |

### Enemy EXP table — especially important

The game stores each tier's 101 24-bit rewards as separate low, middle, and high byte planes.
Every one of these bytes must remain identical to the Japanese ROM. `tools/enemyexp.py` checks
all 303 reconstructed rewards (909 bytes) on every build.

**EXP is only three of each tier's SEVEN planes.** Each tier is seven 101-byte planes; the
four before the reward triple carry the rest of the constructed actor's stats, and those are
what a collision would have to hit to change DAMAGE rather than experience:

| Tier | Stat planes | EXP planes |
|---:|:---|:---|
| 1 | `$6C34` `$6C99` `$6CFE` `$6D63` | `$6DC8` `$6E2D` `$6E92` |
| 2 | `$6F12` `$6F77` `$6FDC` `$7041` | `$70A6` `$710B` `$7170` |
| 3 | `$71F0` `$7255` `$72BA` `$731F` | `$7384` `$73E9` `$744E` |

Until 2026-08-16 the gate covered only the 909 reward bytes, so the twelve stat planes were
declared never-allocate but nothing enforced it. `enemyexp.py` now also compares the complete
`31:$6980-$74B2` span — 2,867 bytes, readers included — byte for byte against the control ROM.

| Tier | Low-byte plane | Middle-byte plane | High-byte plane |
|---:|:---|:---|:---|
| 1 | `31:$6DC8-$6E2C` | `31:$6E2D-$6E91` | `31:$6E92-$6EF6` |
| 2 | `31:$70A6-$710A` | `31:$710B-$716F` | `31:$7170-$71D4` |
| 3 | `31:$7384-$73E8` | `31:$73E9-$744D` | `31:$744E-$74B2` |

Tier-3 enemy `$30` is Mouse Don and must award 40 EXP. The old credit placement at
`31:$7440` overlapped tier 3's middle/high boundary and changed Mouse Don to 131,112 EXP.
That address is permanently forbidden for code placement.

### Other small guarded native patches

These do not reserve broad allocation pools, but they are not free space. Only their named
installer should modify them:

| Bank/range | Owner | Purpose |
|:---|:---|:---|
| `4:$4FE6-$4FE7`, `4:$704E-$704F` | `tools/build.py` | Path label and quiz row layout |
| `13:$5537-$5548`, `4:$5773-$577D` | `tools/itemfix.py` | Unidentified-item help/title sources |
| `4:$4AE0-$4AE2`, `4:$4AFA-$4B01` | `tools/itemfix.py` | Shop `Price` / `G` value-box headings and pointer |
| `4:$7450-$7452`, `4:$7464-$7478` | `tools/itemfix.py` | Empty/action-pot text and pointer |
| `11:$796F-$79B1` | `tools/awardfix.py` | Pass/Awards screen renderer and title slot |
| `31:$41A0-$41A1` | `tools/build.py` | Name-entry grid stride |
| `4:$69F2-$69F5` | `tools/summarydifficulty.py` | Save-summary difficulty column offsets |

The save-summary offsets are the clearest example of a table whose values encode SOURCE
lengths. `4:$69F2` right-aligns each difficulty by its Japanese kana count, so translating
a label longer than its source silently clips it against the thirteen-cell field — the
copier at `4:$69EB` runs to the terminator and never reports a problem. Only `Normal`
(`ふつう`, three cells) grows in English, which is why it was the only visible failure.
The paired index table at `4:$69F6` is asserted but not modified.

## Expanded banks: current ownership

Banks 32-63 were added by `tools/expand.py`. Do not assume the unused-looking tail of an
owned range is available: several installers enforce an entire reservation, and text growth
can consume more of a pool bank later.

| Bank(s) | CPU range | Owner / contents | Rule |
|---:|:---|:---|:---|
| 32 | `$4000-$40FF` | `tools/rankvwf.py`: far entry/vectors | Exclusive |
| 32 | `$4100-$42FF` | `tools/dte_rom.py`: DTE tables | Exclusive |
| 32 | `$4300-$43FF` | `tools/name6.py`: far name helpers | Exclusive |
| 32 | `$4400-$773F` | `tools/propvwf.py`: glyph data, metadata, scanner/render code | Exclusive |
| 32 | `$7740-$7FEF` | `tools/menuvwf.py`: menu VWF engine | Exclusive |
| 33 | `$4000-$40FF` | `tools/pool.py`: redirected-text reader | Exclusive |
| 33 | `$4100-$42B5` | `tools/menuvwf.py`, `tools/rankvwf.py`: start/rank helpers | Exclusive |
| 33 | `$4300-$4373` | `tools/pool.py`: far stubs | Exclusive |
| 33 | `$4400-$7FFF` | `tools/pool.py`: redirected-string index | Exclusive |
| 34-57 | `$4100-$7FFF` | `tools/pool.py`: redirected English text arena, subject to exclusions below | Pool-only; bank 46 begins at `$4400` |
| 34-45 | `$405A-$40FF` when assigned | VWF carry/transition helpers | See per-module constants; otherwise reader-owned |
| 38 | `$405A-$41FF` | `tools/propvwf.py` + `tools/structvwf.py`: carry and Fei restore | Exclusive |
| 46 | `$4100-$43FF` | `tools/menuvwf.py` + `tools/rankvwf.py`: rank-screen helpers | Exclusive |
| 47 | `$405A-$40ED` | `tools/rankvwf.py`: `Village` / `Dragon` ranking rasters and uploader | Exclusive |
| 48-49 | `$405A-$40FF` | `tools/menuvwf.py`: native fusion-count residue shifter plus `$8C-$94` glyph table/reader | Exclusive |
| 50 | `$405A-$40FF` | `tools/itemfix.py`: English category prefixes for player-named unidentified items | Exclusive |
| 51 | `$405A-$40F2` | `tools/menuvwf.py`: priced Item-row `$D0-$DE` five-slot classifier and restorer | Exclusive |
| 52 | `$405A-$4088` | `tools/faypath.py`: status-only `Puzzle` / `Expert` Path producers | Exclusive, exact call-site guard |
| 58-59 | `$4100-$7EFF` | `tools/endingcredits.py`: 22-card code, pointers, and packed graphics | Exclusive |
| 60 | `$5000-$76AF` | `tools/markers.py`: town/dungeon arrival-card graphics | Exclusive tail |
| 61 | `$7000-$77F5` | `tools/titlecard.py`: pre-intro card plus fresh/progressed title-route dispatch | Exclusive tail |
| 62 | `$7000-$7F43` | `tools/titlelogo.py`: illustrated title screen | Exclusive tail |
| 63 | `$4010-$6DA3` | `tools/intro.py`: prologue/ending cinematic engine and data | Exclusive |

Banks 34-62 are addressable by the redirected-text allocator, but the graphics/helper tails
listed above take precedence. Their installers assert the reserved spans are still untouched;
a collision must be solved by changing allocation policy, never by weakening that assertion.

## Script-bank text is executable data

Changing text in banks 11, 13, or 14 can move every later entry in that bank. That is not
automatically safe merely because the redirected English pool has room. Native code can hold
an address, branch into a parent record, or supply a runtime value for a control token that a
static extractor cannot fully infer.

The combat pair at `13:$4B66` and `13:$4B6B` is the clearest current example. Native code
constructs the attacker, target, and damage substitutions before entering those records. A
`<var>`, `<cE4>`, `<br>`, or terminator is therefore part of the producer/consumer ABI, not
ordinary punctuation. Changing the visible template without changing and proving the native
producer can make queued pointers or control bytes render as glyphs. Even a token-safe length
change repacks later bank-13 records and must be treated as a ROM-layout change.

**A queued fragment must not contain an authored `<br>` or `<brk>`.** These records are not
dialogue. Native code pushes them through the queue appender at `0:$028B` and interleaves
runtime substitutions between them — the Fluffy Bunny heal line is `13:$4D7D`, then the
target's name via `15:$6713`, then `13:$4D88`. Across the whole ROM, 239 call sites name 198 distinct
records, and the Japanese base has an authored break in none of them. Enumerating only
the 235 sites with an adjacent `ld bc,nn` misses 18: four sites name their record
indirectly, and three of those are a second paired-fragment producer of the same shape --
parallel pointer tables at `6:$7C59`/`6:$7C7F` giving each trap its event and outcome
lines. One
was added to the English heal line for readability; in play it garbled the line, blanked
the dialogue box, fired an unrelated actor animation, and displaced the healer past its
target. The consumer wraps by itself and needs no help: `<var> robbed <var>` reaches 179px
with the widest monster name substituted twice, which is the real budget. `tools/healfragmentspill.py`
enforces both facts and locates the records by content, because `script/en.tsv` is keyed
by Japanese addresses that the build relocates.

Rules for dynamic records:

1. Keep control-token count and order identical unless the native producer is disassembled,
   patched, and covered by a live route.
2. Run `tools/varaudit.py`; unresolved broad domains are a warning that the widest runtime
   substitution is not yet known.
3. Add an emulator fixture for the actual producer. A preview of the literal TSV cannot prove
   a runtime message.
4. Run all normal, shuffled, and redirect-all layouts with `tools/release_battery.py`.

The redirect-all layout is also a timing proof. It exposed a real 160-scanline second-pass
reveal-map build for the existing combat damage line even though normal placement passed. The
bank-32 VWF builder now keeps a direct destination pointer and the same case completes within
143 scanlines while `tools/propupload.py` remains byte-exact. Do not replace that loop with a
per-character address helper without rerunning the complete timing/upload matrix.

## Safe allocation procedure

1. Prefer an already owned pool belonging to the same subsystem.
2. Search this map and the repository for both the proposed bank and address.
3. Prove a native span's semantics from disassembly/readers; zero-filled bytes are insufficient.
4. Add an exact expected-byte or SHA-256 guard before replacing native bytes.
5. Add a semantic regression for the displaced risk. For gameplay tables, compare the whole
   table against `build/_base_expanded.gb`, as `tools/enemyexp.py` does.
6. Update this map and run `python3 tools/release_battery.py`.

For a quick overlap search, use both hexadecimal styles because modules vary:

```sh
rg -n '7440|0x7440|\$7440' tools docs README.md
```

If an agent cannot prove that a region is safe, it must leave that region untouched.
