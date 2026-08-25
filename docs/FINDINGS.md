# Shiren GB — translation project, ROM triage findings

ROM: `Fushigi no Dungeon - Fuurai no Shiren GB - Tsukikage Mura no Kaibutsu (Japan) (SGB Enhanced).gb`
SHA1 `920ef94c05ac741047a266cb1668c881eab2937c` · MD5 `754398219a3ab38394cdac543d8deb47` · 512 KiB

## Cartridge header

| Field | Value |
|---|---|
| Title | `FURAINO SIREN GB` |
| Cart type (`$147`) | `03` = MBC1 + RAM + battery |
| ROM size (`$148`) | `04` = 512 KiB, 32 banks |
| RAM size (`$149`) | `03` = 32 KiB (4×8 KiB banks) |
| CGB / SGB | DMG-only; SGB enhanced (`$146`=03) |
| Checksums | header `DF` and global `5A74` both valid |

## The mapper problem (decided early, affects everything)

**MBC1 cannot address more than 512 KiB while this game also uses 32 KiB of SRAM.**
MBC1 has one 2-bit secondary register that serves *either* the upper ROM bank bits *or*
the RAM bank select — not both. This game needs it for RAM banking (4 SRAM banks).

So the ROM is at its hard ceiling as an MBC1 cart. **Expansion requires MBC3** (`$147` =
`13`) — **not** MBC5, which was the original guess and is wrong for this game.

Settled live with `tools/mesen_mbc_watch.lua`. The bank-switch routine at bank 0 `$07A8`
does `ld d,$3F` / `ld [de],a`, so **every** ROM bank write lands in `$3F00-$3FFF` — 6137
writes observed, 100% of them.

| Range | MBC1 | MBC3 | MBC5 |
|---|---|---|---|
| `$2000-3FFF` | ROM bank (lo 5) | **ROM bank, 7 bits, whole range** | lo 8 / **bit 8** |
| `$4000-5FFF` | RAM bank / ROM hi | RAM bank | RAM bank |
| `$6000-7FFF` | mode select | RTC latch (no RTC on `$13`) | ignored |

MBC5 would read `$3Fxx` as ROM bank *bit 8* and break every switch. MBC3 treats the whole
`$2000-$3FFF` range as the bank register exactly like MBC1, so the writes work unchanged,
and it reaches 2 MiB.

**Both the MBC3 conversion and a 1 MiB expansion have been validated in play** — dungeon,
combat, death, new cycle, save and reload. See `tools/setmapper.py` and `tools/expand.py`.

## Free space

The ROM is **essentially full**: only ~2.4 KiB of filler runs ≥64 bytes across all
512 KiB, and exactly one usable bank tail (**317 bytes at bank 1 `$7EC3`**). There is no
free bank. Any meaningful English script must live in banks added by expansion.

## Font

**8×8, 1bpp**, in bank 13. Tile 0 of the syllabary block is at file offset `0x037600`.
Laid out in strict gojūon order, which is what made the encoding fall out.

Indices below are *font tile indices* relative to `0x037600`:

| Tile index | Contents |
|---|---|
| 16 | space |
| 17–26 | digits `0`–`9` |
| 27–72 | hiragana あ…ん (gojūon) |
| 73–81 | small hiragana ぁぃぅぇぉゃゅょっ |
| 82–127 | katakana ア…ン (gojūon) |
| 128+ | small katakana, then punctuation |

Banks 16–24 are bulk graphics (clear bitplane signatures). Kanji glyphs occupy a large
part of bank 13 around the syllabary — that space becomes reclaimable once translated.

## Text encoding — SOLVED

`code = font_tile_index - 16`. Established by relative search (matching *deltas* between
known-order kana) and confirmed by decoding real strings.

| Code | Meaning |
|---|---|
| `0x00` | space |
| `0x01`–`0x0A` | digits `0`–`9` |
| `0x0B` | あ (hiragana runs from here) |
| `0x42` | ア (katakana runs from here) |
| `0x79` | **dakuten ゛— combines with the PRECEDING kana** |
| `0x7A` | **handakuten ゜— combines with the PRECEDING kana** |
| `0x7B` | ー chōonpu |
| `0xFF` | string terminator / separator |
| `0xEF` | line break (within a message) |
| `0xED` | end of message |
| `0xE2` | name variable |
| `0xEA` | second name variable (seen as `<name2>さん`) |

Punctuation, read off the font at indices `code+16` and cross-checked behaviourally:

| Code | Char | | Code | Char |
|---|---|---|---|---|
| `0x9A` | 「 | | `0xA0` | ： |
| `0x9B` | 」 | | `0xA1` | 、 |
| `0x9C` | 『 | | `0xA2` | 。 |
| `0x9D` | 』 | | `0xA3` | ・ |
| `0x9E` | （ | | `0xAF` | ～ |
| `0x9F` | ） | | `0xB2` | ！ |
| | | | `0xB3` | … |

Plus a partial Latin set for stat labels and button prompts: `0xA8` A, `0xA9` B,
`0xAD` H, `0xAE` P, `0xB4` F, `0xB5` G.

Two corrections to earlier guesses. `0x9A` is **not** a speaker separator — it is the
opening quote 「 that follows an NPC's name. And 、/。/・ were settled by measuring how
often each precedes `<br>`/`<end>`/terminator: `0xA1` 4.9% (mid-sentence comma), `0xA2`
26.7% (sentence-final period), `0xA3` self-repeats 646× (the ellipsis dot ・・・).

Codes `0x79`/`0x7A` also sit exactly where predicted in the font (゛゜ immediately before
ー at `0x7B`), independently confirming the dakuten finding.

## THERE IS A THIRD CHARACTER TABLE — the opening cinematic (2026-08-06)

**`13:$7FAA` is a 77-entry table mapping a cinematic byte to a font code.** It is the
game's whole character inventory, packed densely rather than laid out like the font:

```
$00        space
$01-$2E    あ .. ん     46 contiguous entries -> font codes $0B-$38
$2F-$31    っ ゃ ょ                            -> $41 $3E $40
$32-$42    イウオキケコサシタニハフヤラリンッ         the 17 katakana the game owns
$43-$44    ！ ？          $45-$46  ゙ ゚ (the dakuten pair)
$47-$4B    「 」 ・ 、 。
```

So `あ` is `$01` here and `$0B` in `codec.py`. **The consumer is the opening cinematic**, a
bytecode program at `31:$5C63`-`$5FA0` (~830 bytes, 7 scenes — the `<4D><C8>` scene-end
opcode occurs 7 times and all 7 are in that range, so this is the ROM's only program of
this kind). `tools/introtext.py` decodes it.

**COMBINING MARKS PRECEDE THE KANA HERE.** `むら ゙ ひと` is むらびと, `かわいそう ゙た ゙か` is
かわいそうだが, `コッ ゚ハ` is コッパ. The main script's rule is the opposite (see "Text
encoding" above), and the renderer here draws the mark into the tilemap row ABOVE the text
row — so a cinematic line occupies two rows and the mark lands over the character *after*
it. Two encodings, two orders, and the difference is silent: applying the wrong one
produces valid bytes that spell something else.

### Why every completeness check missed it, and why that is structural

`coverage.py` exists to answer "is what we extracted all there is". It answers by decoding
ROM bytes through `codec.py`. **A run in a third encoding is invisible to it by
construction** — not by a bad threshold. Read through `codec`, `おさなごを` comes out
`ぇうくおを`: fluent-looking kana that *passes* every "is this text" heuristic the extractor
has, so the region was never rejected. It was never asked about.

**This is the third instance of one shape of bug** — `regions.py` restating `codec`'s table
until it went stale (session 7), `impossible()` using bank 13's dispatch table for banks
11/14 (8b), and now a completeness checker that inherits one alphabet. The first two were
duplicated facts that drifted. This one is worse and more interesting: **both tables are
correct, current, and in use — the checker simply only knows about one of them.** A
coverage check is only as complete as its alphabet, and nothing in this project measured
the alphabet.

## Control codes — SOLVED from the game's own dispatch table

Found statically. The renderer lives in **bank 13**; the relevant code:

```
13:$40E8  cp $E0          ; < $E0 is a character, >= $E0 is a control code
13:$4110  sub $E0         ; code - $E0 = table index
13:$4112  sla a           ; x2, 16-bit entries
13:$4114  add a,$26       ; \  hl = $4126 + (code-$E0)*2
13:$4119  adc a,$41       ; /
13:$411C  ld a,[hl+]      ; \  fetch handler
13:$411D  ld h,[hl]       ; /
13:$4120  jp hl           ; dispatch
```

**Dispatch table: bank 13 `$4126`, exactly 17 entries** — `$4126 + 17*2 = $4148`, which is
where the first handler begins, so the table's extent is certain. Therefore control codes
are **`$E0`–`$F0` and nothing else**.

This yields a hard validation rule: **a byte in `$F1`–`$FE` cannot appear in real script**,
since it would index past the table and jump to garbage. That single rule purged the last
of the pointer tables that the block walker had been emitting as "strings".

| Code | Handler | Name | Args | Behaviour |
|---|---|---|---|---|
| `$E0` | `$4186` | `cE0` | **1** | reads arg, conditional `call $3F84` (sound trigger?) |
| `$E1` | `$42B0` | `cE1` | 0 | `ld a,$80` then `rst $10` |
| `$E2` | `$4199` | `var` | 0 | pulls 3 bytes from the queue — runtime variable |
| `$E3` | `$41AF` | `cE3` | 0 | pulls 6 bytes from the queue |
| `$E4` | `$424C` | `cE4` | 0 | pulls from queue, `call $38D6` |
| `$E5` | `$4279` | `cE5` | 0 | pulls 3 bytes, `call $399C` |
| `$E6` | `$4261` | `cE6` | 0 | pulls 3 bytes |
| `$E7` | `$415D` | `cE7` | **1** | reads arg → `$CFC3` |
| `$E8` | `$4165` | `mode0` | 0 | `$CF05 = 0` |
| `$E9` | `$4148` | `nop` | 0 | bare `ret` |
| `$EA` | `$4175` | `name` | 0 | copies `$CF81` until `$FF` — variable substitution |
| `$EB` | `$416D` | `mode1` | 0 | `$CF05 = 1` |
| `$EC` | `$4149` | `cEC` | **1** | reads arg = repeat count, `rst $18` that many times |
| `$ED` | `$4155` | `end` | 0 | `$CFC4 = 1` — end of message |
| `$EE` | `$4148` | `brk` | 0 | handler is `ret`; callers treat it as a line end |
| `$EF` | `$4148` | `br` | 0 | handler is `ret`; callers treat it as a line end |
| `$F0` | `$42BB` | `cF0` | **1** | reads arg, passes to `rst $10` |

**Arity is the critical column for the inserter.** A code taking an argument must have that
byte preserved; the codec now swallows arguments into the token (`<cF0:55>`) so a parameter
can never be mistaken for text or re-encoded as a glyph.

~~**Unresolved:** the skip-chain at `$441B` advances *two* bytes for `$EB`, but `$EB`'s
handler reads no argument.~~ **RESOLVED 2026-07-31 — both are right, because there are two
dispatch tables.** See below.

## A box "pinned by an interior reference" — 3 of 5 were bank-13 messages (2026-08-05)

`extract.box_interior_targets` pins a menu box when code loads an address strictly inside
its text block: only row starts get a record, so relocating the block would leave that load
pointing at whatever moved in. Sound rule, and it trusts a load from bank 0 or from the
box's own bank.

**It did not ask what the code DOES with the operand.** `31:$755B ld bc,$4571 /
call $028B` is a message-queue push, and a push names a **bank 13** address whatever bank
the caller lives in (see MSG_PUSH). `13:$4571` is `<cE0:2B>とっぷうだ！！`, an ordinary
extracted string. `31:$4571` is the combining dakuten inside `ダンジョン` — and **a string
cannot begin on a combining mark**, which is the tell.

Six such loads were pinning three boxes: **48** (the "Normal" difficulty explanation on the
title menu, which Joey reported as permanently untranslatable), **50** and **51**. One more
pushed `$45AE`, which is a *terminator*. `msg_push_kind` is the filter `immediate_refs`
already used for exactly this class; `box_interior_targets` now calls it too.

The two that survive are real and stay pinned: box 2's `0:$62BD ld bc,$4202` reaches no
push, and box 46's two `31:$5D1B/$5DB1 ld hl,$4527` are `ld hl`, not the queue idiom.

**The arithmetic that was blamed instead was true and irrelevant.** `31:$4567` really is 20
bytes and 16 cells, and no English string consumes 20 bytes inside an 18-cell box — but
that only binds a row that cannot MOVE. Unpinned, the box relocates as a unit and the
question never arises. A correct sum about the wrong constraint reads exactly like a
finished diagnosis.

## The composer has TWO dispatch tables, and they disagree — SOLVED 2026-07-31

The table above is `13:$4126`, reached from `13:$4107`. **The dialogue path has its own**,
at `13:$68CF`, reached from `13:$68A8` (`sub $E0 / sla a / add a,$CF / adc a,$68`), and five
codes read a different number of argument bytes from the string:

| code | bank 13 messages (`$4126`) | banks 11/14 dialogue (`$68CF`) |
|---|---|---|
| `$E3` | `$41AF`, **0** args — pulls 6 bytes from the queue | `$6942`, **1** arg (`ld a,[bc] / inc bc`) |
| `$E7` | `$415D`, **1** arg → `$CFC3` | `$6A4D`, **0** — sets bit 1 of `$CF02` |
| `$EB` | `$416D`, **0** — `$CF05 = 1` | `$690F`, **1** arg — shares `$E0`'s handler |
| `$EC` | `$4149`, **1** arg = frame count | `$6908`, **0** — stores the byte and returns |
| `$F0` | `$42BB`, **1** arg | `$6A1B`, **0** — screen effect |

So `$441B`'s skip-chain and `$416D` were both correct: the chain was following the *dialogue*
arity for `$EB` and the handler the *message* arity.

**Confirmed against the script, in both directions.** `$E3` is followed by kana (`を` x18) at
its 32 bank-13 sites — real text — and by digit codes at all 10 of its bank-11/14 sites — an
argument. `$EB`'s bank-14 argument is a typewriter PAUSE: the dialogue renderer at `13:$6AF8`
does `cp $EB / ld a,[hl+] / call $6AB2`, and `$6AB2` repeats `rst $18` (a vblank wait) that
many times. Charging that byte as text is what made `14:$56EF` measure 19 cells instead of 18.

~~`$F0` never appears in banks 11/14, so its difference is inert.~~ **RETRACTED
2026-08-05. It was true of the script AS EXTRACTED THEN, and sessions 7 and 8b brought
seven `$F0` sites in with the 158 strings they added — every one of them in banks 11/14.
See "the arities are MEASURED" below.**

### The arities are MEASURED — 2026-08-05, and two of them were wrong

The table above was read off the handlers. **It is now measured**, by running the ROM's own
staging loop at `13:$6893` over `code + あいう` in `tools/gbemu.py` and reading the `$CF07`
buffer back. `$6893` is the pass that matters: `ld a,[hl+] / cp $E0 / jr c` copies a
character straight to `[de]`, and anything `>= $E0` goes through `13:$68A8`, which sets
`bc = hl` so a handler can take arguments with `ld a,[bc] / inc bc` and copies `bc` back
into `hl` on the way out.

```
  $E0  ->  <cE0:0B>いう     the code AND one argument are staged     arity 1
  $EC  ->  <cEC:0B>いう     likewise                                 arity 1
  $E7  ->  あいう           the code VANISHES and あ survives as text arity 0
  $F0  ->  あいう           likewise                                 arity 0
  $F1-$F4 -> あいう         effect-only, as already recorded          arity 0
```

**`$EC`'s "one loose end" is closed, in favour of what the codec already did.** `$6908`
does `ld [de],a / inc de / ret`, so `$EC` reaches the composer buffer and the byte after it
goes in behind it — whether that byte is then read as an argument is the *renderer's*
question, downstream of here, and the 18-cell measurement is what answers it. Either way
`codec.ARITY`'s 1 puts the byte in the right place, which is all the inserter needs.

**`$E7` and `$F0` were wrong, and `$F0` was the one that mattered.** Their handlers never
`ld [de],a`: they perform an effect (`set 1,[$CF02]`; window-enable via `set 5,[$FF40]`) and
return without touching `bc`. So the following byte is TEXT. Reading it as an argument
swallows a real character into the token, which is invisible in Japanese — the bytes
round-trip either way — and prints as garbage the moment English is written around it:

```
  14:$5BF2   <cF0:56>ギ「まにあった   is   <cF0>ナギ「まにあった      Nagi
  14:$4F11   <cF0:49>スリをのんだ     is   <cF0>クスリをのんだ        the drug
  14:$46EC   <cF0:EA>は かぜに       is   <cF0><name>は かぜに      the player's name
```

`codec.arity_for(bank)` is the fix. It defaults to the message table, so a caller that does
not know a bank keeps the behaviour it always had; `extract.py`, `build.encode_en`,
`build.cells` and `dialogue_preview` pass one. **`dte_rom.chunks` deliberately does not** —
it only ever emits a barrier verbatim, so the ROM gets the same bytes either way and the
one-byte-per-site loss of compression is cheaper than a parameter on four callers.

**`$E3` and `$EB` are still read at the message path's arity ON PURPOSE**, so bank-11/14
strings containing them (10 and 33) show one argument byte as an ordinary character in
`script.tsv`. `dialogue_preview.py` keeps `codec.ARITY` for them so the checker measures
exactly the bytes the inserter writes, and the eight lines that measure 19-21 cells are
explained rather than excused. The hazard is a translator "tidying away" a stray digit,
which `docs/TEXT_REFERENCE.md` §7 warns about.

Two independent confirmations of earlier work fell out of this:

- `13:$4473 ld hl,$7680` is the font base = file offset `0x37680`, which is exactly the
  tile the encoding derivation called index 16. So `code = index - 16` is confirmed **from
  the game's own code**, not just inference.
- `13:$4479-$447C` reads one font byte and writes it to `[de]` twice — 1bpp expanded into
  both 2bpp planes, confirming the font is 1bpp.

Also useful for later line-breaking work: the width routine at `$40DB` decrements its
character counter only when the *next* byte is not `$79`/`$7A`, i.e. **combining dakuten
marks do not count toward the line width.**

After all of this, **6 of 1181 strings (1%)** still contain an unidentified byte — 17
occurrences across 9 codes (`$85`–`$88`, `$A7` are glyphs; `$C6`, `$D6`, `$DE`, `$DF` come
from one remaining mis-extracted table at `11:$55AC`).

## Extraction — done

`tools/codec.py` is the canonical codec, `tools/extract.py` the extractor.

**1175 strings / 27.6 KiB, every one round-trip verified** (`decode` → `encode` reproduces
the original bytes exactly). Output: `script/script.json` (authoritative — offsets, bank,
hex, pointer refs) and `script/script.tsv` (translator working file, `en` column blank).

Dakuten is handled by emitting the combining mark and NFC-composing, so a translator sees
が rather than か+`<$79>`; `encode` runs NFD to reverse it. Verified for all 256 byte
values.

Filtering the sequential-block walker took three passes, and the lessons generalise:

- **Length is the discriminator that works.** Real strings reach 503 bytes (one "string"
  is a whole multi-box conversation with `<end>`/`<br>` inside); the data runs that leaked
  in from banks 0/2/3/9 have median length 875 and reach 12001.
- **`known_ratio` does *not* separate** — junk medians 0.90 against real p5 of 0.80. It is
  kept only as a loose backstop.
- **A kana-ratio floor of 0.40 wrongly rejected real lines** — a mostly-ellipsis line
  scores 0.18. Lowered to 0.10.
- **Digit density separates bank 10's numeric tables** (`33ああ  い8くえ`) from dialogue,
  which barely uses digits.
- A bug worth remembering: bounding the walk at `hi` emitted a *truncated* trailing
  fragment, which `setdefault` then locked in permanently. The walk must extend to the
  next terminator.

Final state: all extracted strings live in banks 11/13/14/30, every detected junk region
contributes zero, and per-region coverage of the dialogue banks is ≥85% (mostly ≥97%).

### Re-extraction of banks 4 and 31 (2026-07-28) — a waived hard rule

`impossible()` (no `$F1`-`$FE` byte can be script, because the dispatch table has exactly
17 entries) was being **waived for hand-specified `EXTRA_REGIONS`**:

```python
if not trusted and impossible(data):   # the bug
```

Those regions are located from screenshots and marked `trusted` so the *statistical*
filters do not reject them — `31:$41E2` has 3 digits in 19 bytes and the digit filter was
throwing away the weapon/strength row. But trust was extended to the structural rule as
well, and the regions were additionally padded by `0x100` on each side, so the waiver
reached ~256 bytes past anything anyone had actually verified.

Result: **1,434 bytes of binary data entered the script as "strings"** — bank 4 was 96%
junk (662 of 686 bytes), bank 31 about 30%.

Three fixes: `impossible()` now applies unconditionally, including to table-sourced
strings (`3:$4646` was reached by a "table" whose six entries all held the same pointer);
`trusted` regions are no longer padded; and the region bounds were widened deliberately to
cover what is really there.

| | before | after |
|---|---|---|
| strings | 1264 | 1217 |
| bytes | 29,973 | 28,527 |
| bank 4 | 686 B | **3 B** (`おかね`) |
| bank 31 | 1,090 B | 339 B |
| strings with impossible bytes | 8 | **0** |

`sh build.sh` still verifies clean (1402 checks). **Bank 4 was the tightest bank in the DTE
projection and is now irrelevant** — re-run `dte_project.py` rather than quoting the old
table.

The general lesson, which is the same one the `--use-filler` incident taught: a rule
derived from the ROM's own structure is not a heuristic and must not be traded away to
make a different filter behave.

Voiced kana are *not* separate glyphs — が is `か` followed by `0x79`. Confirmed by
うでわ (`て`+`79` → で), まんぷく (`ふ`+`7A` → ぷ), ハラヘラズ, モンスター.

**The script is stored as plain uncompressed bytes, one per character.** No DTE, no
dictionary, no LZ. This was the single biggest feasibility risk and it resolved the
good way.

## Pointer tables

16-bit **little-endian**, **bank-relative** (values in `$4000-$7FFF`). Entries of
`$FFFF` mark unused slots, and duplicate entries reusing one string are normal.

Two addressing patterns, both confirmed:

- **Same-bank**: table and strings share a bank. e.g. `0x02C5FF` (bank 11) indexes the
  scroll names at `0x02C39A+`.
- **Cross-bank**: table lives in one bank, strings in another, with the bank implied by
  the calling code rather than stored in the entry. e.g. the 32-entry trap-message table
  at `0x01BC59` (bank 6) targets bank 13.

Strings are additionally `0xFF`-separated, so a block can be walked sequentially as well
as indexed.

`tools/findtables.py` finds 15 tables / 625 entries. Confirmed real ones (banks 11, 13,
14, 30) cover weapons (157), monsters (214), herbs (77), bracelets (17), menus, verbs
and clear conditions. The three "tables" it reports in bank 10 are **false positives** —
dense numeric data that decodes as valid codes.

## How strings are addressed — two mechanisms, both mechanical

Not one scheme but two, which is why a table scanner alone could never reach everything.

**1. Pointer tables — 679 of 1184 strings (57%).** 16-bit LE, bank-relative, in same-bank
and cross-bank forms. `tools/findtables.py` finds 35 tables / 1045 entries.

**2. Immediate loads in code — 207 more (18%).** The message printer `$028B` takes its
pointer in `bc`, so call sites read `ld bc,$XXXX` / `call $028B`. There are 286 such
sites (240 `ld bc`, 40 `ld hl`, 6 `ld de`). Being individual instructions scattered
through code, they never cluster, so no table scan can find them — they have to be
located by matching the immediate operand against known string offsets, filtered to
code regions.

Combined: **886 of 1184 (75%) accounted for. ~298 still unexplained.**

Both mechanisms are mechanical to repoint:
- table entry -> rewrite 2 bytes in the table
- immediate load -> rewrite the 2-byte operand at a known instruction offset

#### An immediate match is not an instruction — the phantom reference (2026-07-30)

A byte scan for `01 xx xx` finds the SHAPE of `ld bc,$xxxx`, and the shape also occurs
inside the operand of a longer instruction. `0:$227B` is `ea 01 cf` = `ld [$CF01],a`;
starting one byte in, `01 cf 7e` reads as `ld bc,$7ECF` — which is the address of a real
string, bank 30's item verb at `30:$7ECF`. The extractor recorded it as a reference, and
because build.py rewrites every reference it is given, the moment DTE moved that verb one
byte the inserter wrote the new address over live code: `ld [$CF01],a` became
`ld [$CE01],a`, and the message system lost the variable that holds a dungeon message on
screen. **That was the "messages expire too fast" bug** — one byte, in bank 0, in a build
whose 1445 checks were all green.

The disambiguator is that LR35902 code **self-synchronises**: start a linear decode at
almost any nearby byte and it converges on the real instruction stream within a few
instructions. `dis.boundary_votes()` decodes from each of the preceding 64 bytes and
counts how many sweeps land ON the candidate against how many step OVER it. Measured on
this ROM's 41 immediate references, the four contested sites separate cleanly:

| site | operand | on / over | verdict |
|---|---|---|---|
| `0:$2D18` | `ld bc,$4F96` | 63 / 1 | real — the call site of `$028B` |
| `0:$227C` | `ld bc,$7ECF` | 0 / 64 | phantom, inside `ld [$CF01],a` |
| `0:$27EA` | `ld bc,$7DCD` | 1 / 63 | phantom, inside `call $01DF` |
| `13:$7210` | `ld de,$58CD` | 0 / 64 | phantom, inside `ld e,$11` |

`extract.py` drops the phantoms and prints each one; `build.py` re-checks every `imm`
reference against the untouched ROM before writing through it, so a stale `script.json`
fails the build instead of corrupting code. The general rule: **a pointer found by
pattern is a candidate, and only a decode makes it a reference.**

#### A real immediate may explicitly select another bank — ordinary stairs (2026-08-11)

The “same switchable bank as the instruction” rule also has a proven exception. Bank-13
instructions at `$549F` and `$54B5` are both `ld hl,$46C1`; the following code moves
`$0E` into the bank selector before calling the dialogue stager. They therefore target
`14:$46C1`, the ordinary `Descend / Stay here` choice, not the unrelated message at
`13:$46C1`.

The old extractor assigned both operands to bank 13 because the CPU address was the same.
When `13:$46C1` repacked to `$5AFD`, it rewrote both live stair loads, producing Nagi or
Koppa dialogue on every route. State handoffs into the original Japanese code showed the
same behavior for two Koppa floors, Nagi and Fumi: each stages only `14:$46C1` and moves
to the next floor after the choice. `extract.py::CROSS_BANK_IMMEDIATES` now records the
two instruction sites and their explicit bank-14 ownership; `koppastairspill.py` verifies
the rewritten operands and all four real-save routes.

#### Terminal `<end><brk>` can manufacture an empty box (2026-08-11)

`14:$7BC2`, Koppa's `Brrr... That was scary / Let's hurry home!`, contains two native
`<br>` controls and then ends naturally at `$FF`; it has no `<end>` or `<brk>`. English
had appended `<end><brk>`. In the supplied town conversation this rendered the phrase,
then one completely empty dialogue box, then closed on the second A press. Removing the
two added controls restores `message -> closed` and also lets the same record advance a
dungeon consumer in one press.

`lint_en` now rejects terminal `<end><brk>` in bank-11/14 English when the Japanese record
contains no `<end>`. `koppatalkspill.py` replays the real town conversation and a diagnostic
dungeon consumer; `koppastairspill.py` independently ensures production stairs retain the
normal `Go down / Stay here` choice.

**But both are bank-relative**, so relocating a string into a new bank still requires the
code that reads it to switch to that bank first. Relocation therefore stays a per-group
operation, not per-string.

### 3. Village/story dialogue — a runtime-queued pointer

Found by watching the string bytes with `tools/mesen_strread.lua` after three attempts to
guess the code location failed. The chain:

1. Event code pushes a dialogue pointer into the message ring buffer (via `$3C5C`).
2. **Bank 13 `$67D5`** takes the high byte in `a`, **pulls the low byte from the queue**
   (`call $3C7B`), and stores the pair at **`$CF7F`/`$CF80`**.
3. **Bank 11 `$569E`** (and **bank 14 `$4010`**, an identical copy) reads ONE LINE at a
   time from that pointer into a WRAM buffer at `$CF8F`, stopping at `$EF` `<br>`,
   `$EE` `<brk>` or `$FF`, then writes the advanced pointer back to `$CF7F`/`$CF80`.

The reader lives in the *same bank as its text*, which is why the bank is implicit and
why every scan for tables or immediates missed these strings entirely: **the pointer never
appears in the ROM as a constant.** It is assembled at runtime and passed through a queue.

Note `set 6,h` / `res 6,h` (bank 11) and `xor $C0` (bank 14): the stored pointer has its
window bits toggled, so it is not a plain `$4000-$7FFF` address.

**The stored pointer is NOT a plain address.** Traced live: values appear as `$232D`,
`$2391`, `$82B7`. The reader restores the window bits -- bank 11 does `set 6,h`
(`$232D` -> `$632D`), bank 14 does `xor $C0` (`$82B7` -> `$42B7`). Bit 15 selects which
reader/bank. Every earlier scan searched for `$4000-$7FFF` values and so could never have
matched the constants actually stored in the ROM.

Even searching for the correct encoded form, the pointers appear only as isolated
constants (2066 positions, overwhelmingly coincidental) and **never in tables** -- zero
clusters with 4+ distinct targets. They are computed in event logic, not enumerable.

**Consequence for insertion.** These strings cannot be repointed, so they must be
translated **in place**, same-or-shorter. Measured cost: 505 strings, 16998 cells, but
the median string is only **18 cells** and the mean 33 -- most are short exclamations
that English fits comfortably. Only **40 strings exceed 80 cells**. So the constraint
bites on a small, identifiable minority rather than the whole body of dialogue.
Everything reached by tables or immediates relocates freely.

### Runtime variables

Combat and event text is stored as *fragments* assembled at render time, not as complete
sentences. `<var>` (`$E2`) and `<name>` (`$EA`) pull their content from a queue, and
`<cE4>` supplies a number. So one stored fragment such as "`<cE4>` points of damage
dealt" serves every attacker, target and item in the game.

This matters for translation: fragments must be worded so they read correctly under every
substitution, and English word order will not always match the Japanese fragment
boundaries. Some sentences may need their fragments restructured rather than translated
one-to-one.

## DTE — measured, and it closes the bank shortfall

Measured 2026-07-28. `tools/dte.py` (algorithm), `tools/dte_measure.py` (yield),
`tools/dte_project.py` (per-bank projection).

**Corpus: the SNES Shiren English fan translation**, at
`../Shiren/shiren-revamp-fixes/text/*.asm` — 108 KB across dialogue, dungeon messages,
enemy names, item names. Same franchise, same register, same content categories as the GB
script, and already English. Pairs are forbidden from spanning a control code or a string
boundary, matching what the ROM expander could actually do.

| Variant | 96 pairs | 120 | 140 | Expander cost |
|---|---|---|---|---|
| plain (code → 2 literals) | 32.7% | 34.7% | 36.0% | one lookup, emit 2 bytes |
| recursive (code → any symbols) | 37.0% | 40.0% | 41.8% | needs a depth-8 stack |

**The yield does not depend on corpus size** — 36.1% at 4 KiB against 34.6% at 64 KiB, at
a fixed 120 pairs. So the number transfers to a 40 KB script instead of being a
small-sample artefact. This was the one thing that could have made the measurement
worthless, and it checks out.

English needs **84 distinct characters**, so with control codes at `$E0`-`$F0` there are
**140 codes free** for pairs. The table costs 2 bytes per pair — 280 bytes — which fits
the one known free bank tail (**317 bytes at bank 1 `$7EC3`**) if bank 13 is tight.

### Per-bank projection

At 34.7% (plain, 120 pairs) and 1.46x English expansion, **every real bank fits**:

| Bank | jp | avail | raw en | +DTE | slack | break-even ratio |
|---|---|---|---|---|---|---|
| 11 | 11977 | 12590 | 17486 | 11419 | +1171 | 1.61 |
| 14 | 8775 | 8982 | 12812 | 8366 | +616 | 1.57 |
| 13 | 7380 | 7741 | 10775 | 7036 | +705 | 1.61 |
| 31 | 1090 | 1146 | 1591 | 1039 | +107 | 1.61 |
| 4 | 686 | 695 | 1002 | 654 | +41 | 1.55 |
| 30 | 42 | 57 | 61 | 40 | +17 | 2.08 |

Banks 3 (16 B) and 6 (7 B) are excluded: one or two strings each, and bank 3's decode as
junk. Too small to plan around, trivially handled by hand.

**The last column is the number that matters.** Plain DTE tolerates English up to ~1.55x;
recursive up to ~1.74x. Against that:

- Cognate names measure **1.35x** (14 matched pairs, e.g. マムル→Mamul, ドラゴンキラー→
  Dragon Killer, 88 jp bytes → 119 en). But names transliterate almost 1:1 and are the
  easy case.
- Prose is unmeasured — no parallel prose exists — and Japanese-to-English dialogue
  typically runs higher.
- **VWF raises the ratio**, because the reason to abbreviate disappears.

So plain DTE's margin sits exactly where the uncertainty is. **Use recursive.** It costs a
small stack and buys the difference between "probably fits" and "fits with room".

### Where the expander goes — one place, settled by scan

`$CF07` (the line buffer) is referenced from **bank 13 only**, 14 sites. Banks 11 and 14
stage a raw line at `$CF8F` and **bank 13 consumes it**. So all text funnels through
bank 13 and there is exactly one place to put the expander and its table.

Two literal-copy loops feed `$CF07`, and they are the same four-instruction shape:

| Site | Path | Budget |
|---|---|---|
| `13:$40DB` | layout / width | `ld b,$12` = 18 cells, dakuten-aware |
| `13:$6893` | village + story, via `$CF8F` | none — copies until `$FF` |

Both do `cp $E0` / `ld [de],a` / `inc de`. DTE hooks in as one subroutine called from both.
These are also the two sites VWF's width accounting has to change, so the two jobs touch
the same code.

**Hard constraint found here: the `$CF07` buffer is ~54 bytes.** `13:$6884` clears `$36`
bytes, `13:$40CF` clears `$32`, and `$CF43` is in use by other code — so there are only
about 6 bytes of slack past the clear. DTE expands and VWF packs more characters per line;
both push against this exact buffer. `13:$6893` has **no length cap at all** and relies on
upstream `<br>`/`<brk>` placement to bound the line. Any expander must respect the ceiling,
and the line-break placement in the English script must keep *expanded* lines under it.

### The other win: in-place strings

The 505 runtime-queued strings must be translated same-or-shorter **in bytes** — they
cannot be repointed. Today that means a 1.0x budget. With recursive DTE they tolerate
`1 / (1 - 0.418)` = **1.72x**. Bank relocation does nothing for this group; DTE fixes it
outright.

`build.py` now enforces this group's budget **in bytes** (`len(final) <= r['bytes']`)
rather than in cells. The old check used `cells(jp)`, which is the same number for English
but strictly tighter whenever the Japanese had dakuten — and that slack is exactly what DTE
exists to spend. The consequence is that a translation may draw more cells than the
Japanese did; that is cosmetic, because these are composer-path strings and the composer
wraps. The report counts them.

## THE DIALOGUE REDIRECT — BUILT AND VERIFIED 2026-07-31

`tools/pool.py`. In-place dialogue no longer has to fit its original byte count.

### The gate

`13:$7589` is the ONE place a dialogue line is staged. It loads the stored pointer from
`$CF7F`/`$CF80` into `hl` and dispatches on `bit 7,h`:

```
13:$7589  push af / push hl
13:$758B  ld a,[$CF80] / ld h,a / ld a,[$CF7F] / ld l,a
13:$7593  bit 7,h
13:$7597  rst $10 / db $0D,$0B     ; bank 11's stager, 11:$569E
13:$759C  rst $10 / db $03,$0E     ; bank 14's stager, 14:$4006
```

**Both far calls are the only ones in the ROM.** Scanning all 2869 `rst $08`/`rst $10` byte
positions for `(index, bank)` = `($0D, 11)` and `($03, 14)` finds exactly one site each,
both above. `$7589` itself has two callers, `13:$67ED` and `13:$688A`. So replacing this one
routine catches every in-place line in the game, first line and continuation alike.

#### `13:$6CA8` writes the resume pointer too — the `$EC` path (2026-08-05)

**Staging has one gate. The resume POINTER has two writers, and the second one runs after
the first.** Right after the first stage, `13:$67F3` tests the first staged byte:

```
13:$67ED  call $7589            ; stage the first line at $CF8F  <- the gate
13:$67F3  ld a,[$CF8F] / cp $EC
13:$67F8  jr nz,$67FF           ; ordinary message -> call $680E
13:$67FA  call $6C73            ; the <cEC> path
```

`13:$6C73` reads the ARGUMENT out of the staged buffer (`ld a,[$CF90]` → `$CF8B`) but the
POINTER out of `hl`, which still holds the address the message came from:

```
13:$6C73  ld a,[$CF90] / inc hl / inc hl / ld [$CF8B],a
13:$6C7E  bit 7,a / jr z,$6C91
13:$6C91  bit 3,a / jr nz,$6C9D      ; $6C9D -> $6E81 -> $6E8F call $6CA8
13:$6C95  call $6CA8
13:$6CA8  ld a,h / ld [$CF80],a / ld a,l / ld [$CF7F],a   ; RESUME := original + 2
13:$6CB3  ld c,$00 / call $6CE9 ... x3                    ; then compose THREE lines
```

So a `<cEC:arg>` message is `EC arg` followed by exactly **three lines**, and the handler
rewinds to just past the prefix and composes them. Both of `$6C73`'s branches reach
`$6CA8`, so every argument value takes the store.

**Consequence for the redirect, and it is the whole of session A1.** `$6CA8` overwrote the
pool continuation `13:$7589` had just stored, pointing back into the middle of the 4-byte
record: `14:$41C2`'s `E9 61 4D FF` resumed at `4D FF`, which drew a single `シ` and stopped.
The fix is a layout rule — leave `EC arg` at the original address and put the record at +2,
which is exactly where `$6C73` is going to point. `tools/pool.py`'s `head_bytes()`.

### The far call is the ROM's own

`rst $08` and `rst $10` both `jp $078D`. Encoding is **`db <index>,<bank>` inline, 3 bytes**.
The trampoline saves `[$4000]` (the caller's bank — byte 0 of every switchable bank holds
its own number), maps `<bank>`, reads a code pointer from that bank's index table at `$4000`
(entry `<index>` is at `$4000+index-1`/`$4000+index`, so indices are odd), calls it, and
restores the caller's bank. Registers pass through and it nests.

**This is why the new reader does not need bank 0.** "Bank 0's padding is full at 158/158"
was treated as the blocker for a year of planning and it was never the question.

### The encoding

Fixups are `set 6,h` (bank 11) and `xor $C0` (bank 14), so a real `$4000-$7FFF` address is
STORED as `$00-$3F` (tag bit15,bit14 = 0,0) or `$80-$BF` (1,0). Two tags are free:

| tag | meaning | pool |
|---|---|---|
| 0,0 | bank 11, `set 6,h` | — |
| 1,0 | bank 14, `xor $C0` | — |
| 0,1 | free | bank 33, real address = stored |
| 1,1 | free | bank 34, real address = stored & $7FFF |

**Tag (1,1) is free STRUCTURALLY.** Bit 7 routes to bank 14, whose `xor $C0` would turn it
into a `$00-$3F` address — bank 0, not text. No pusher can produce it.

**Tag (0,1) is made structural by `NORMALISE`.** Bank 11's `set 6,h` makes bit 6 a
don't-care, so event code is free to leave junk there and `tools/ptrtags.py` (0 of 28
distinct pointers over 12 seeded runs) is only evidence. `pool.py` therefore relocates
`13:$67E0` — where a queued pointer becomes `$CF7F`/`$CF80` — into bank 33 and adds one
`and $BF`. After that, bit 6 can only be set by a redirect record.

### The record

`$E9 lo hi $FF`, four bytes, written over the START of the original string.

* `$E9` is `nop` in `codec.CONTROL` and its handler at `13:$6929` is a bare `ret`. It begins
  zero of the 1264 extracted strings (`pool.check_marker()` re-derives that from
  script.json). **A reader that does not understand the redirect draws an empty line and
  stops** — the failure mode is blank text, never corruption or a crash.
* `lo`/`hi` may not be `$EE`/`$EF`/`$FF`, which terminate the staging copy and would truncate
  the record. The allocator skips those addresses; pool B also skips real pages `$6E`, `$6F`
  and `$7F` (`$FFxx` is the composer's end-of-message sentinel at `13:$684D`).
* **The rest of the original string is LEFT WHERE IT IS.** `11:$5848` is a legitimate
  mid-conversation entry point inside the 179-byte `11:$5803`; anything pointing into the old
  bytes still finds them. The pool is pure addition and never reclaims.

### Capacity

301 in-place strings, 15,788 bytes of Japanese, in banks 11 and 14. Two pool banks give
**32,256 bytes = 2.05x, before DTE**, against measured natural English of 1.66x. More is
available if it is ever wanted: a WRAM byte holding a pool bank number would open all 496 KiB,
and `$CF83-$CF89` has no static reference (but `$CF81-$CF88` is the 8-byte player name
buffer, so only `$CF89` is a real candidate and it may be the name's terminator slot).

### Verification

* `pool.py --selftest` — 5 checks; the reader is executed under `tools/gbemu.py` for both
  tags, and the flags half of `bit 6,h` / `bit 7,h` is exercised (getting it wrong passes a
  copy test and still routes every string to the wrong bank). Added `ld [bc],a`, `and n`,
  `or n` and the CB `bit`/`res`/`set` group to `gbemu.py`.
* `install()` refuses to patch unless `13:$7589` and `13:$67E0` still hold their untouched
  bytes, and unless the pool banks are `$FF`.
* `build.py` verifies a redirected string BY FOLLOWING ITS RECORD — it reads the pool address
  the record names and compares. A mis-encoded record fails the build.
* `crashscan.py --seeds 12` clean; `pool_verify.py` hooks the dispatcher in a real run,
  decodes the staged line through the ROM's own DTE table, and screenshots the result.
* `build.py --no-pool` is the bisect control: same script, and `14:$5047` comes back as
  `too_long`.

## DTE — BUILT AND VERIFIED 2026-07-29

`tools/dte_rom.py` (expander, table, hooks), `tools/gbasm.py` (assembler),
`tools/gbemu.py` (interpreter). `sh build.sh` emits it on every build.

**Two ROM facts settled the design, and neither was in the earlier plan.**

**1. Byte 0 of every switchable bank holds that bank's own number.** Verified across all 32
banks of `base.gb`. That is what the ROM's own far-call trampoline reads at `0:$079E`
(`ld a,[$4000]`) to recover the caller's bank before restoring it. So **any resident
routine can map a bank over the caller and put it back with no WRAM shadow**, which is a
general-purpose tool, not just a DTE one.

**2. Banks 32-63 of the expanded ROM are entirely `$FF`.** 512 KiB of free space that needs
no verification at all — unlike the WRAM gaps, which a static scan cannot clear.

Together those retire the WRAM question: **the table does not have to be resident**, only
the expander does.

| piece | where | size |
|---|---|---|
| expander | bank 0 `$0062-$00D9` | 120 bytes, 38 spare before the header |
| table | bank 32 `$4100`/`$4200`, direct-indexed `LEFT[c]`/`RIGHT[c]` | two 256-byte pages |
| bank id | bank 32 `$4000` = `$20` | honours fact 1 |

Direct indexing by code means the lookup is `ld l,code` / `ld h,$41` / `ld a,[hl]` — no
multiply, no subtract — at the cost of two pages of an otherwise empty bank.

**Bank 0's padding is settled, not merely unverified.** Both ROM checksums verify, so the
nine non-`$FF` bytes in `$0062-$00FF` are authentic to the cartridge — and every one of
them is `$FF` with one or two bits cleared (`$7F $FB $FB $EF $EF $FA $BF $EF $BF`). That is
unprogrammed mask-ROM fill, not data. No bank-0 or bank-13 reference points into the range.

### Code space is 128, not 140

The 140 figure assumed only English would be in the ROM. A DTE code must also avoid the
combining marks and, in practice, be separable by a cheap compare. Three ranges are free of
English letters, of `$79`/`$7A`, and of the control codes:

```
$43-$78   54      $81-$9D   29      $B3-$DF   45      = 128 codes
```

Five compares separate them (`is_dte`, generated from `DTE_RANGES` so the table and the
assembly cannot drift). Measured on the SNES English corpus: **128 pairs recursive = 40.7%,
depth 5** — an in-place budget of **1.69x**.

The 19 codes left over are English's scattered punctuation, which reuses the ROM's *native*
glyphs at `$7C-$B2`. Compacting those into `$43-$4C` would make `$4D-$DF` a single 147-code
range and a one-compare test. That is the one upgrade still on the table; it touches the
font, so it is not free.

### Untranslated Japanese collides, and that is cosmetic

Japanese text uses 181 of the 224 literal codes, so its bytes *do* land in the DTE ranges,
and it flows through the same expander. It cannot be avoided while any Japanese remains.
It also does not matter: the Latin font is already written over the kana tiles, so Japanese
renders as garbage either way. What would have mattered is an overrun, and that is closed —
see the guard below. Only translated strings are ever compressed, so nothing *correct* is
put at risk.

### The buffer guard is an address bound, not a character cap

The handoff called for a hard character cap on `13:$6893`. An address bound is strictly
stronger, and it is what `emit_lit` does: it refuses to write at or past **`$CF38`**.

`$CF38` and not `$CF43`, which was the first answer: both loops zero the buffer before
filling it and the composer reads those zeroes as the end of the line, so a write into the
uncleared gap past `$CF07+$32` would leave text with no terminator after it. The guard
therefore stops one byte inside the *shorter* of the two clears. This is a byte bound, so
it holds however many bytes one pair expands to — which a character cap could not.

### Cell counting survives expansion

`13:$40F3` decided whether a character was a cell by peeking the **next source byte** and
skipping `dec b` if it was a dakuten. That cannot work after expansion: the next byte may
now live inside a table entry rather than in the source.

Charging the **mark itself** instead of the base character is equivalent — a mark always
follows a base character and two never adjoin, so either rule bills one cell per pair — and
it needs no lookahead at all. That is what lets the 18-cell budget keep working unchanged.

### Hooks

| site | what happened |
|---|---|
| `13:$40F1` | the 12-byte literal path became `call dte_emit` / `jr $40FD`. **7 bytes free at `13:$40F6`** — that is where the `<name>`-costs-zero counter fix goes |
| `13:$6893` | the whole loop moved to bank 0 as `loop2`, replaced by `jp $00C2` |

`13:$6893` could not be patched in place: threading a 3-byte call through it needed one byte
more than the loop had, and the byte after it (`$68A8`) is the entry point of its own
control-code handler. Relocating is free — bank 13 stays mapped, so reading the source
through `hl` and calling back to `13:$68A8` both work unchanged. Nothing references the
vacated `$6896-$68A7`; the apparent cross-bank hits resolve to those banks' own `$68xx`.

### How it is verified without Mesen

`tools/gbasm.py` derives its opcode table by **inverting `dis.py`'s**, so the assembler and
disassembler cannot disagree; `--selftest` round-trips 249 instruction forms.
`tools/gbemu.py` is a ~30-opcode interpreter that raises on anything it does not implement,
so a patch cannot be silently mis-executed into a passing test.

`dte_rom.verify()` runs the **actual ROM expander** over the SNES English corpus and
compares against `dte.py`'s reference decoder: **5277 segments, 0 mismatches**, checking the
bytes emitted, the cell count charged, that `hl` and the stack come back intact, and that
the caller's bank is restored. The write guard is tested by feeding it an over-long line.

`build.py` additionally round-trips **every** compressed string through `expand_bytes`,
because `compress()` has to agree with the expander on text the table was never trained on.

### The render surface is much wider than four sites — CORRECTED 2026-07-30

The first attempt gated compression **by bank** (11/13/14 non-box), on the reasoning that
those banks funnel through bank 13. **On screen it was wrong**: the file menu drew
`New廿`, `ト/Pオ`, `Fei's刀z`. The literals were fine and the DTE codes came out as raw
katakana — because `$43-$78` *is* the katakana range and nothing had expanded them.

Cause: bank 11's menu labels are copied by **`11:$52C6`**, which derefs a pointer table at
`11:$52E0` and runs its own raw loop at `11:$52D5`:

```
11:$52C6  sla a / ld c,a / ld b,$00      ; index*2
11:$52CE  ld hl,$52E0 / add hl,bc
11:$52D2  ld a,[hl+] / ld h,[hl] / ld l,a
11:$52D5  ld a,[hl+] / ld [de],a / inc de / cp $FF / jr nz,$52D5
```

No control-code handling, no cell counting, no cap — and no path to the expander.
Confirmed under pyboy: `dte_emit` fired **0** times across boot, file menu and name entry,
while `11:$52C6` fired 6 and `11:$52D5` 47.

**Scanning for the idiom shows how incomplete the four-site list was:**

| idiom | bytes | sites |
|---|---|---|
| store-then-test | `2A 12 13 FE FF 20` | 6 — `4:$7458` `11:$51F0` `11:$52D5` `11:$7E63` `14:$7C1E` `30:$7E8A` |
| test-then-store | `2A FE FF 28` | 44 candidates (generic; includes `13:$40DB`) |
| control-aware | `2A FE E0` | 2 — `13:$6893` **and `13:$6AE5`**, which no list named |

**~~`31:$40D8` reads WRAM, not ROM~~ — WRONG, corrected 2026-07-30.** That trace recorded
`hl`, which is the drawer's **destination**. Its source is `bc`, loaded from the pointer at
`$C69F`/`$C6A0` (`31:$40DC-$40E3`), and it reads `[bc]`.

Re-traced on the pointer itself, the source is **both**: ROM at `31:$43DC` `$43E2` `$43E9`
`$4526` `$452C` (box text in bank 31), and RAM at `$C616` `$C61C` `$C61F` `$C622` `$C62A`.

`$C616` is the item-verb staging buffer that `30:$7E8A` fills — and that site IS hooked, so
verbs arrive already expanded. **There is no separate staging copy to find, and the drawer is
the right place to hook after all**, for the ROM-sourced text. See "The menu box drawer needs a GATE" below.

Lesson worth keeping: when hooking a copy loop, record the register the loop *reads*, not the
one it writes. `hl` is the source in the five raw loops and the destination in this one.

### Scanning needs a save state, and the addresses need translating

Two things had to be fixed before the scan could produce a usable allowlist.

**The composer is unreachable from the title screen.** Boot, file menu and name entry never
touch `13:$40D8`; only real dialogue does. From a state parked in a dungeon the composer
fires 98 times and `dte_emit` 587 times, against zero from boot. Joey's Mesen battery save
(`.srm`, 32 KiB = the cart's 4 SRAM banks) drops in as pyboy's `<rom>.ram`, which is enough to
boot into a real file and drive to a log; `build.sh` copies it automatically.

**The scan sees BUILT addresses, the allowlist is keyed on ORIGINAL ones.** A relocated string
appears at its new address, so 19 of the first 52 scanned entries matched no string at all --
silently failing to allowlist the very strings the scan had just observed. `build.py` now
writes `build/relocmap.tsv` (built address -> `loc`) and `gbrun.py` translates through it.

### So the gate is now evidence, not bank

`script/build-inputs/dte_ok.tsv` lists strings a trace has **observed** an expanding loop read, generated
by `gbrun.py --dte-scan` (hooks `13:$40D8` and bank 0's `loop2`, where `hl` still holds the
string start, and reads the current bank from `[$4000]`). An unlisted string is left
uncompressed.

That fails safe in the right direction: **no compression costs space, wrong compression
costs correctness.** It is currently empty, so no string is compressed — the expander is
still emitted and exercised on every build.

Populating it needs the composer to actually run, i.e. in-game dialogue. Boot, file menu and
name entry never touch it.

### PROVEN ON SCREEN 2026-07-30

`11:$52D5` is now hooked -- relocated whole to bank 0 as `label_loop`, same trick as
`loop2`. With `New Log` and `Fei's Quiz` compressed, the file menu renders
**pixel-identical** to a `--no-dte` build (`gbrun.py --compare`). That is the full chain
working for the first time: translation -> compressed bytes in ROM -> hooked copy loop ->
expander -> correct glyphs.

Two changes made it possible:

**`is_dte` now tests `cp $E0` itself.** The composer excluded control codes before calling,
but a raw loop passes the terminator straight through -- and `is_dte($FF)` fell past the last
range and answered YES, so `$FF` would have been expanded through the table.

**The `$CF38` address bound applies only when `d == $CF`.** A raw loop's destination is
elsewhere (`$C616`, a menu buffer), where comparing `e` against `$38` would drop writes at
arbitrary points. Those loops keep the bound they always had, which is none; `label_loop`
sets `b` high so the cell counter cannot spuriously stop it.

Expander is now 148 bytes of the 158 available. **10 bytes spare** -- the remaining hooks
will need the `0:$3FEC` tail (20 bytes) or the unused RST vectors (`$0028-$003F`, 24 bytes).

### One shared routine hooks all five raw loops

Five sites copy a string with the **identical seven bytes** `2A 12 13 FE FF 20 F9`
(`ld a,[hl+] / ld [de],a / inc de / cp $FF / jr nz`): `4:$7458`, `11:$51F0`, `11:$52D5`,
`14:$7C1E`, `30:$7E8A`.

Because `raw_copy` replaces the **whole loop** rather than one iteration, the patch is a
3-byte `call` plus padding -- which **fits in place in all seven bytes**. So these sites need
no relocation, cost nothing in bank 0, and keep their own epilogues. That is strictly better
than the relocation used for `loop2`, and `11:$52D5` was converted to it.

Hooked: `11:$52D5` (menu labels) and `30:$7E8A` (item verbs). **Not** hooked: `4:$7458`,
`11:$51F0`, `14:$7C1E` -- same seven bytes, but nobody has established what they copy, and
`raw_copy` would expand a `$B3-$DF` byte inside a data blob just as happily as inside text.

### BANK 30 IS CLOSED -- but not the way the plan said

`sh build.sh` now reports **"no problems: every supplied translation fit."** Bank 30 needs
59 bytes of its 73, +14 spare. All 17 item verbs are English for the first time.

**The dead-entry reclamation did NOT do it, and its evidence does not hold up.** The plan was
to reclaim four unreachable verb entries -- index 10 `かく` plus three pointing at a lone
`$FF`. Verb index `$0A` does indeed appear nowhere in `$7D00-$7E98`: not in the category
tables at `$7DE8`/`$7E14`/`$7E40`, not in the context rows at `$7DD8`/`$7DE0`.

**But neither does index `$12` = `はずす` = "Doff"**, which has to be reachable for equipped
items. The substitution code at `$7D73`/`$7DA0` *computes* indices (`ld bc,$0004` /
`add hl,bc`), so **absence from the tables does not prove an entry is dead.** Aliasing on that
basis would have put the wrong verb on an item menu.

**What closed it was aiming the table at the tight bank.** The table is one fixed pair of
pages, so where its 128 codes get spent is a free choice, and spending them evenly is wrong:
prose banks have slack, bank 30 has four bytes. Repeating bank 30's strings in the training
set (`dte_rom.TRAIN_WEIGHT`) buys the fit cheaply:

| weight | bank 30 needs | prose yield |
|---|---|---|
| 1 | 77 B (4 short) | 40.8% |
| 16 | 75 B (2 short) | 40.7% |
| **64** | **59 B (fits, +14)** | **39.3%** |
| 256 | 39 B | 36.5% |

1.5 points of prose yield for the fit. Verbs like `Swap` end up as a **single byte** (`$DC`)
expanding to four characters.

Verified by running `raw_copy` in `gbemu` over the real bank-30 bytes from the built ROM:
**21 of 21 verbs expand to exactly their intended English.** The file menu remains
pixel-identical to a `--no-dte` build.

**CONFIRMED ON SCREEN 2026-07-30.** The item action menu draws `See / Put / Toss / Drop /
Info` correctly in a real dungeon. All five are stored compressed, and `See` is a **single
byte** (`$DF`) expanding to three characters:

| verb | stored | plain |
|---|---|---|
| See | `df` | 3 |
| Put | `76 38` | 3 |
| Toss | `81 73` | 4 |
| Drop | `0e 62 34` | 4 |
| Info | `8e 2a 33` | 4 |

That is the full chain proven on the hardest path in the ROM: compressed bytes in bank 30 ->
`raw_copy` at `30:$7E8A` -> staged into `$C616` -> drawn by `31:$40D8` from RAM. Note the
drawer needed **no** hook for these, because the staging copy expanded them first.

### Still to hook

**`31:$40D8` itself** — patch `31:$4106` (`call $4124` -> `call dte_box`), 3 bytes in place.
Its registers differ from every other site: source `bc`, destination `hl`, cell counter `e`,
and `d` is a live flag. `$4124` peeks the next SOURCE byte to charge a cell (`$4137`), the
same shape as `13:$40F3`, so only DTE codes may take the new path and plain bytes must fall
through to the original handler. Implemented; see "The menu box drawer needs a GATE" below.

Then `13:$6AE5`, `11:$52BC`, and the three untraced raw loops above.

## TWO render paths — settled in Mesen 2026-07-28

Established with `tools/mesen_rendertrace.lua` + `tools/decodetrace.py`, by walking every
screen and decoding what was actually written. This decides the whole scope of VWF.

**Path A — dynamic tile composition (`13:$4418`). VWF-able.**
Reads the `$CF07` line buffer, composes a fresh tile per character, writes them to a WRAM
staging buffer at `$C008`. Traced hit counts come in exact multiples of 18 — 18/36/54 —
matching the `ld b,$12` line budget, i.e. one, two and three lines.

Everything in the message window uses it. Confirmed by decoding the buffer live:
`ロクロウ「おっ、よそモンだ・・・」`, `むらおさ「あっ！ ナギ！！」`,
`おおきいおにぎりをたべた`, `2ポイントのダメージをうけた`, `シレンは ちからつきた…`.
So **all village dialogue, story text, dungeon messages and combat text is VWF-able.**

**Path B — raw character codes written into the BG tilemap. NOT VWF-able.**
Menus write the character code *directly* as a tilemap entry, one glyph per 8x8 cell,
with `$BE`/`$BF` as box borders. Captured at `$9940`/`$9980`:

```
$9940  BE 15 16 17 18 19 00 2E 00 2F 00 30 00 00 01 02 03 04 05 BF
       -> さしすせそ や ゆ よ  01234        (= 31:$429B, the name-entry kana grid)
$9980  -> たちつてと らりるれろ  56789      (= 31:$42AE)
```

**The tilemap entry is the raw code**, confirming the earlier claim: `13:$7643` uploads the
font to VRAM `$9000` starting at `$7680`, which is code 0, so VRAM tile *N* = code *N*.

Changing the composer does **nothing** for this path. Menus are one glyph per cell by
construction.

**Path C — the status bar**, window layer `$9C00`+, its own tileset. Already documented
below; the trace shows it as sequential runs `B0 B1 B2 ...` at `$9C49`/`$9C81`.

### The dungeon message box IS the window, and its height is WY — 2026-07-30

The message box and the status bar are the same window layer. In the dungeon the window
is parked at **WY (`$FF4A`) = 136**, showing one row: the status bar. A message slides WY
up to **99** over three frames, holds it, and slides it back to 136. Nothing about the
box is in `tilemap_background`, and the window's own tilemap barely changes — the text is
written once and left there. **What changes is WY.**

That makes a message's LIFETIME a number a headless run can read, which is what
`tools/msgdur.py` does, and it is the only automated check in this project that can see a
duration. The counter behind it is **`$CF03`** in the composer's `$CF00` block, set from
the nibble-packed table at `0:$22AC` by the routine at `0:$2274` — the routine whose
`ld [$CF01],a` the phantom reference corrupted.

### The composer's layout budget — 18 cells, 3 lines, and where each number lives

Read out of the ROM 2026-07-31 while building `tools/dialogue_preview.py`, and then checked
against the shipped Japanese: of **1608** dialogue lines the longest is exactly **18** and
**230** land exactly on that boundary. A model off by one cell could not produce that shape.

| | bank 13 messages | banks 11/14 dialogue |
|---|---|---|
| stager | `13:$40C5` → `$40D8`, source `hl` | `13:$6878` → `$6893`, source `$CF8F` |
| cell budget while staging | `13:$40D6 ld b,$12` = **18** | **none** |
| `$CF07` buffer cleared | `13:$40CF ld d,$32` = 50 bytes | `13:$6884 ld d,$36` = 54 |
| line ends on | `$FF`/`$EE`/`$EF` (`$40DC`-`$40E6`) | `$FF`, and `$EE`/`$EF` return `$FF` (`$6A65`/`$6A6E`) |
| renderer | `13:$44F2`, `ld b,$12` = **18** | `13:$6ABC` |

**Why the dialogue path truncates even without a counter.** `13:$6B40` holds the first TILE
INDEX of each row — `$A8`, `$BA`, `$CC` — and they are **18 apart**. The renderer composes
one fresh tile per character (`13:$6B85` writes the tile index to `$C002`) and simply walks
`inc b`, so the 19th character of a line is written to tile `$BA`, which is *row 1's first
tile*. That is exactly the reported symptom: an over-long line "ate the next line's indent".

**Three lines a box, and there is no fourth.** The same three rows, `$A8`-`$DD` = 54 tiles,
with `$DE`/`$DF` reserved for the dakuten overlay (`13:$6B06`/`$6B11`). The row-address
table at `13:$6B43` holds three tilemap addresses, `$9C40`/`$9C80`/`$9CC0`, and path A's
equivalent at `13:$4412` holds the three matching tile-DATA addresses `$8A80`/`$8BA0`/`$8CC0`
— which is `$8000 + $A8*16`, `+ $BA*16`, `+ $CC*16`. The two paths share the same 54 tiles.

**A control code costs no cell; a substitution does.** `13:$4107` pushes `bc` around the
dispatch and `$4123` pops it, so no handler can charge the cell counter. But `$E2`, `$EA`,
`$E4`/`$E5`/`$E6` and `$E3` all write into the buffer, and the renderer charges whatever it
finds there. The digit codes are bounded by their own callers: `13:$424C` and `$4261` call
`13:$4294` with `c=3`, `$4279` with `c=7`, and `$4294` suppresses leading zeros — so `<cE4>`
is 1 to 3 cells, `<cE5>` 1 to 7.

**The Japanese busts its own substitution budget**, which is why `tools/dialogue_preview.py`
fails a build only at the substitution FLOOR of one cell each. `<var>は モンスターにかこまれた！`
is 14 literal cells and leaves **4** for a monster name; `13:$48FF` leaves exactly 3 for a
`<cE4>` that can be 3 digits. Fifteen shipped lines go over 18 once `<var>` is charged the
8-cell cap in `docs/TEXT_REFERENCE.md` §4. A check that refused those would be refusing text the
original game ships, so the cap is reported as headroom instead.

### Consequence

The intuition that dialogue needs VWF least and menus need it most is **backwards relative
to the code**: dialogue is the cheap case and menus are the one that cannot be reached
from the composer at all. Getting VWF into menus means converting their draw path from
tilemap writes to composed tiles — a much larger change than the composer edit.

Before committing to that, check whether the menu **boxes can simply be widened** — see the
geometry below, which suggests they can.

### Item action menu geometry — measured from the tilemap

Captured 2026-07-28 with the content filter. The menu is drawn at **columns 13-19**:

```
cols:   13 14 15 16 17 18 19
        BE 00 1A 27 33 00 BF     たべる    eat
        BE 81 1F 13 33 00 BF     ▶なげる   throw   ($81 = cursor)
        BE 00 0F 12 00 00 BF     おく      place
        BE 00 18 1C 2C 0C BF     せつめい  description
        BE 81 30 2B 00 00 BF     ▶よむ     read
        BE 81 24 17 17 00 BF     ▶はずす   remove
```

Border, cursor slot, **4 text cells**, padding, border. `せつめい` is what sets the width.

**The important part: columns 11 and 12 are blank.** The item list beside it ends at
column 10:

```
BE 00 81 おおきいおにきり 00 00 BE ▶なげる 00 BF
0  1  2  3........10     11 12 13
```

So the box is right-aligned against the screen edge with slack to its left. Widening it
leftward yields more text cells, at worst overlaying item names — normal popup behaviour.
At 8 cells, Throw / Place / Read / Remove / Eat all fit as whole words; only
"Description" needs a shorter synonym.

**This suggests menus need wider BOXES, not variable-width glyphs** — confirmed below.

Item names also have more room than the Japanese implies — with the action menu closed the
list box runs to column 19, so roughly **16 cells**, not the 8 the Japanese names occupy.

## Menu boxes are a TABLE — SOLVED 2026-07-29

Box width is a **parameter**, not a hardcoded blit. Every menu box in the game comes out of
one geometry table, so widening one is a one-byte data edit.

```
31:$4055   box id -> pointer table at 31:$45D5 (52 entries, $45D5-$463C)
           -> 7-byte descriptor, copied verbatim to $C69A:
              +0 x   +1 y   +2 rows   +3 WIDTH   +4 flags   +5,+6 text pointer (LE)
31:$4075   writes $C69A/$C69B to $FF90/$FF91, calls $1A67 for the tilemap address,
           then: top border, `rows` text rows (advancing hl by $20), bottom border.
           Draws into the WRAM shadow tilemap at $C300, 32 bytes per row.
31:$40D8   ONE row: left border tile, `width` cells, right border tile
31:$4163   a border row: corner, `width` edge tiles, corner
           triples at 31:$417B: b8 bc b9 (top)  be 00 bf (blank)  ba bd bb (bottom)
```

So a box occupies **columns x .. x+width+1** and **rows y .. y+rows+1** — the two border
columns are outside `width`. `$C69F/$C6A0` holds the running text pointer, so consecutive
rows are simply consecutive text.

Flags (`+4`) seen: **bit 1** = row count is dynamic, taken from `$C6BB` at 31:$404A (this
is how a 3-verb item shows 3 rows in a `rows=7` box); **bit 2** = draw an extra separator
row before the bottom border (31:$40A1).

Left border is `$BE` unless the row's first byte is `$84` or `$86`, which select `$83` /
`$85` instead — a box that joins another vertically.

### The cursor is NOT part of this table — 4:$4E6E

Learned from a screenshot: widening a box worked, moving one did not. The selection cursor
is placed by **bank 4**, from its own table, and it carries its own position:

```
4:$4E2B   menu id in $C6A3 -> table at 4:$4E6E, 2 bytes/entry, 35 entries ($4E6E-$4EB3)
          -> $C6A7/$C6A8 = cursor HOME, a 16-bit offset into the $C300 shadow tilemap
4:$4F2B   hl = home + [$C6A5]*64 + $C300 ; ld [hl],$81
```

A box's home is `(y+1)*32 + (x+1)` — one row down and one column in from the corner, i.e.
the cursor slot. The table decodes cleanly against the descriptors:

| entry | offset | row, col | box |
|---|---|---|---|
| 2, 7, 16 | `$004E` | 2, 14 | box 6, the item action menu (three entries, one per verb set) |
| 20 | `$008E` | 4, 14 | box 39 |
| 25 | `$00ED` | 7, 13 | box 29, difficulty |
| 31 | `$0106` | 8, 6 | box 47 |
| 24 | `$006C` | 3, 12 | box 28, yes/no |

So moving a box means adding the same delta to every entry holding its old home.
`build.py` does this automatically and **refuses** when two boxes share a home — the
entries are keyed on position, so at `$0021` (row 1 col 1) eleven boxes are
indistinguishable. Display boxes with no cursor are marked `nocursor` in
`box_geometry.tsv`.

**Open oddity, flagged not resolved.** `4:$4F2B` computes the step as `[$C6A5] * 64`
(`ld b,a / ld c,0` then two 16-bit right shifts), which is *two* tilemap rows per
selection — but the difficulty menu's screenshot shows the cursor one row down on the
second entry. So either `$C6A5` is not a plain 0,1,2 selection index for that menu, or
some menus use a different cursor writer. It does not affect patching the HOME offset,
which is what box moves need, but do not build anything on the step until it is checked.

### Two rules from the drawer, both load-bearing

**A row ends after `width` CELLS or at an `$FF`, whichever comes first.** The terminator is
*optional*: `31:$44F7` (`ふうらいにんばんづけ`, 12 bytes = 10 cells in a 10-wide box) has
none, and the next descriptor starts immediately after. Consequences:

- splitting a block on `$FF` alone runs two boxes together;
- a short row is **blank-padded by the drawer**, so widening a box never requires
  re-padding its text;
- budgeting a terminator for a row that fills its box costs a byte it never had.

**`31:$4124` peeks the NEXT byte** to decide whether to `dec e`, so a dakuten never costs a
cell — and a row whose last character is voiced consumes its dakuten even after the width is
used up (`31:$4356` `どうぐ`, 5 bytes in a 3-wide box). Replicating the peek is the only way
to land on the true end of a block.

### The table is authoritative, and it proves it

Walking it accounts for **every byte of `$41C2-$45D5`** — 52 descriptors plus 27 text
blocks, 0 bytes unexplained, 0 overlaps. The hand-written `EXTRA_REGIONS` bounds it replaced
were a guess that cut off 17 boxes. Bank 31 went 25 strings → 59 rows.

25 of the 52 boxes have no ROM text: their rows are staged in WRAM at `$C616` (or `$C6E3`).
That includes the item list and **the item action menu (boxes 6 and 39)**, whose verbs bank
30 copies in at `30:$7E6C` — `inc de` first, leaving the cursor byte, then the verb and its
`$FF`. Their geometry is still editable; their text is bank 30's problem.

### What this makes cheap, and what it does not

Widening: cheap, declarative, `script/build-inputs/box_geometry.tsv`. Item action menu is now columns
9-19, cursor + 8 cells. Moving a box is also cheap now, but only because the cursor table
above is patched with it — that link is not discoverable from the box code alone.

Relocating: a box's rows move as a **unit**, because 31:$4075 walks them sequentially — row
1 is just whatever follows row 0's terminator. Row 0 carries the descriptor pointer, and a
row may carry an immediate of its own (`31:$418D ld hl,$4275` is row 1 of box 12, the
name-entry grid page); both get rewritten.

A box is **pinned** when bank 31 or bank 0 loads an address *inside* a row rather than at a
row start — boxes 48, 50 and 51 have a second reader that prints fragments of their text via
`call $028B` (which stows bc in `$FF90/$FF91`, the same scratch pair the box drawer uses for
x/y — so `$028B` is a print call, not a cursor call). Relocating those would leave a stale
pointer that nothing checks. Box 2 is pinned by a false positive: `0:$22BD` sits in a data
blob, not code. The rule is deliberately conservative.

### The two limits that bite

**Bank 31's free pool is fragmented by design.** Descriptors sit *between* the text blocks,
so the vacated blocks never merge: 534 bytes free, largest run 26. Boxes 33 and 34 (item
categories, 5 rows each) need 32 and 38 contiguous and cannot be placed at any total. The
**katakana grid page is 116 contiguous bytes** and is the obvious source.

**A pinned box row is bounded by bytes CONSUMED, not cells drawn.** `31:$4567` is 20 bytes
but 16 cells. English has no dakuten, so a replacement padded to 20 bytes would draw 20
cells; the drawer stops at the 18-cell width, never reaches the terminator, and row 2 starts
two bytes early. No English string consumes 20 bytes inside an 18-cell box, so that row is
not translatable in place at all. `build.py` reports it as `box_in_place`.

### Consequence for DTE — corrected 2026-07-29

An earlier version of this section said DTE could not help menus. That was wrong, and the
error was reasoning from the hook sites instead of measuring.

What is true: the menu path never touches bank 13's copy loops. `31:$40D8` reads its bytes
and writes tiles itself, and WRAM-staged rows are assembled by bank 30 before bank 31 is
mapped. So the two hooks the plan names -- `13:$40DB` and `13:$6893` -- decompress nothing
in a menu. **Menus need their own hooks at `31:$40D8` and the bank-30 staging loop
`30:$7E8A`.** That part stands.

What is false: that DTE therefore buys nothing there. Measured on the actual English:

| table trained on | corpus | yield |
|---|---|---|
| bank 30's 17 item verbs alone (65 bytes) | itself | 4 bytes, **6.2%** -- saturates at 2 pairs |
| bank 31's menu text (299 bytes) | itself | 105 bytes, **35.1%** (40 recursive pairs) |
| bank 11's menu text (216 bytes) | itself | 68 bytes, **31.5%** |
| the SNES English script (108 KB, 140 recursive pairs) | applied to the item verbs | 10 bytes, **15.4%** |

Two things fall out of that:

**Yield scales with the TABLE's corpus, not the text being compressed.** The item verbs go
from 6.2% to 15.4% purely by borrowing a table trained on a real script. A local table on
65 bytes finds two usable pairs and then saturates -- more pairs change nothing, because 17
short unrelated words share almost no byte pairs.

**Short labels will never reach the 41.8% prose figure.** These average 3.6 letters; DTE
pays on repeated pairs, and prose has "the"/"ing"/"you" recurring constantly where a verb
list does not. Budget menus at ~15% and prose at ~40%.

For bank 30 specifically that is 10 of the 13 bytes needed, and the remaining 3 come free
from the four dead verb entries (index 10 `かく` plus three empty slots -- 5 bytes if they
share one terminator). **So DTE plus dead-entry reclamation closes the item action menu**,
and the far-read helper is not needed for it.

### ~~The unsettled part of the DTE plan: where the table lives~~ — SETTLED 2026-07-29

**The premise was wrong.** This section assumed the table has to be resident "because the
expander dereferences it", and every option above follows from that. It does not: the
expander can map a table bank over the caller and put the caller back, because **byte 0 of
every bank holds that bank's own number** and can be read at `$4000`. See "DTE — BUILT AND
VERIFIED" above.

So none of the three options was needed. The table went in bank 32 — free, verified free by
inspection rather than by argument, and large enough that the table is direct-indexed by
code instead of packed. WRAM was never touched, and no boot hook exists.

Kept as a record of the shape of the mistake: **all three options were about rationing
150 bytes, and the useful move was to stop needing them.**

---

## Screens are a DISPATCH TABLE in bank 4 — SOLVED 2026-07-30

The question "how do I get the game to show box N" had been answered by driving buttons and
hoping. It has a mechanical answer.

**`4:$48AA` is bank 4's menu-screen dispatcher.** `a` is a screen index; the table is 35
16-bit entries at **`4:$48C3`**, and the routine is a plain trampoline:

```
4:$48AA  push af / push bc / push hl
4:$48AD  sla a                  ; index * 2
4:$48AF  add a,$C3              ; + table base low
4:$48B1  ld l,a
4:$48B2  ld a,$00 / adc a,$48   ; + table base high, with carry
4:$48B6  ld h,a
4:$48B7  ld a,[hl+] / ld h,[hl] / ld l,a
4:$48BA  ld bc,$48BF / push bc  ; return address
4:$48BE  jp hl
```

Index 27 is `4:$4CD0`, the item CATEGORY screen:

```
4:$4CD0  ld a,[$C6E3] / and a / jr nz,$4CDA
4:$4CD6  ld a,$21          ; box 33, consumables
4:$4CD8  jr $4CDC
4:$4CDA  ld a,$22          ; box 34, equipment
4:$4CDC  rst $08 / db $03,$1F     ; the far call that shows a box
```

`$C6E3` is the page selector (0 -> 33, else -> 34), toggled at `4:$7C99` and cleared at
`4:$7C81` alongside the name-entry page toggle `$C6F3`.

**Why this matters more than the one screen.** Forcing the dispatcher's index reaches any of
the 35 screens without knowing its in-game path. The real path to the category boxes is
still unknown — roughly 13 button scripts from both save states never found it — and it did
not need to be known: `tools/boxscan.py` hooks `4:$48AA`, rewrites `a` to 27, and the REAL
routine then draws the REAL box through the REAL drawer. That is enough to screenshot it and
enough for `--dte-scan` to legitimately observe its rows.

Two things that make the general search work:

* **A box is shown by `ld a,<box id>` then `rst $08 / db $03,$1F`** — bytes `3E xx CF 03 1F`.
  54 such sites; only `4:$4973`, `4:$4C59` and `4:$4CBE` pass a computed id. **A byte scan
  sees the fall-through and misses the branch**: it attributes `4:$4CDC` to box 34 because
  `ld a,$22` precedes it, when box 33 reaches the same instruction via a `jr`.
* **`0:$079E`** is where the far-call trampoline still has `bc` pointing at the inline bytes
  and `[$4000]` holding the caller's bank — the place to hook to attribute a far call.

### FORCING THE INDEX IS NOT ALWAYS ENOUGH — and the failure looks like a hang (2026-08-06)

**Session 9 spent a session's worth of belief on "dispatcher index 5 hangs".** It does not.
Index 5 is `4:$49F5`, the equipment SEAL screen, and it is a plain routine that ends in
`ret` — there is no input loop in it to hang in. What hangs is the byte after the screen:

```
4:$49F5   zeroes $78 bytes at $C616, de = $C616
4:$5736   stages the item NAME into the buffer
11:$7E40  a = [$C6BE + [$C6BC]]      the item's seal ids, $FF-terminated
          cp $FF / sla a / hl = $5463 + a
          copy [hl]..$FF into [de]   <- runs to the next $FF ANYWHERE in bank 11
```

`$C6BE` is the equipped item's seal array, and a save state not sitting on a melded item
leaves junk in it. A junk id is doubled into `$5463 + 2a`, so the copy starts at an
arbitrary address and runs until it happens to meet an `$FF` — straight past the 120 bytes
that were cleared, into live WRAM. The game dies some frames later, somewhere else.

**So the rule the boxscan trick rests on has a second half.** Forcing `a` at `4:$48AA`
reaches any of the 35 screens *whose drawing routine is a pure function of WRAM the state
already holds*. When the routine reads a CONTEXT — a selected item, a seal array, a topic —
that context has to be supplied too, or the real routine will do real damage with it.
`tools/helpshot.py` already did this without naming it (`$CF7A` topic, `$CF7B` table select,
`$C6BC` unit); `tools/sealshot.py` sets `$C6BE`/`$C6BD`/`$C6BC` for the same reason.

**And "it hangs" is the least informative symptom this project has.** Read the routine
before believing the index is unreachable — three sessions treated this screen as
un-photographable on the strength of one hang.

## Unidentified item Info bypasses the description table — two literals serve every category

The item Info resolver at `13:$7E0D` has two branches, selected by `$CF7B` bit 7. Known
identities double `$CF7A`, index the 157-pointer table at `$554A`, then page to the unit in
`$C6BC`. A hidden identity takes the early branch and returns `hl=$5537` directly. Topic,
category and unit never participate, which is why Sapphire Bracer, Gold Staff and every
other appearance name exposed the same Japanese body after the English font landed.

`13:$5537` is the exact 18-byte literal `みしきべつなので よくわからない` — “It is
unidentified, so its effect is unclear” — followed by `$FF`; the pointer table begins at
the very next byte, `$554A`. It was correctly absent from `script.json`: no pointer table
or immediate-reference extractor owns a code-selected literal. `itemfix.py` now asserts
all 19 bytes and replaces only the sentence with the same-length `Effect is unknown.`.
There is no relocation and no category-specific translation to maintain.

The real Dragon's Maw Log-1 fixture exposed a second producer above that body. The name
formatter at `4:$574C` directly copies the 11-byte literal at `4:$5773`,
`みしきべつのアイテム` (“Unidentified Item”), and supplies its own surrounding hyphens.
Neither `Unidentified` nor `Unknown Item` fits the 11-byte slot (both need 12), so
`itemfix.py` installs the natural compact heading `Unknown`, terminates it, and clears only
the remaining bytes of that asserted literal slot before code resumes at `$577F`.

`tools/unidentifiedhelp.py` executes the built ROM's real `13:$7E49` staging routine with
bit 7 clear and representative zero, boundary-like and `$FF` topic/unit selectors. Every
case must write the same English row. `unidentifiedspill.py` remains a different fixture:
its Hyakki Shield has a hidden **modifier** but a known identity, so the pair of native
stars is correct and its body legitimately comes from the ordinary Hyakki help entry.
`identityhiddenspill.py` boots `saves/shiren_en_log_1_dragons_maw.srm` twice and follows
the genuine five-choice action menu (identity-hidden items insert `Name` before `Info`).
Opal Bracer and Gold Staff must both render `-Unknown-` / `Effect is unknown.` plane-exact;
the bracer and staff cases prove two real categories set the shared hidden-identity branch.

## Empty Pot See bypasses item help and shares one direct row

Floor -> See for a Pot dispatches screen 13, not the ordinary item Info resolver. When the
contents count is zero, bank 4 copies the direct literal at `4:$7464` into `$C616`. Its
exact Japanese bytes decode as `−なにも はいっていません−` — “—Nothing is inside—.”
The record is code-selected and consequently absent from the extracted description table;
after the Latin font landed, those same bytes composed as plausible-looking gibberish.

`itemfix.py` asserts the complete 14-byte literal plus terminator and installs a centered
`Empty` in the same slot. This row is shared by every empty Pot that offers See; it does
not alter category-specific actions such as Back Pot or Todo Pot Press. The supplied
`saves/shiren_en_log_1_pot_see_action.srm` route is permanent in `potseespill.py`: it
requires Floor screen 20 followed by Pot screen 13, exact `$C616` staging, and the visible
proportional planes. The test demonstrably fails the preceding ROM on the Japanese row.

The separate Back/Todo charge path is now closed by
`saves/shiren_en_log_2_action_pots.srm`. Their `$CC` placeholder expands through
`4:$744A` to the direct literal `  せなか` at `4:$7473` once per charge. It is not
ordinary Pot storage: both real item IDs `$81` and `$88` show three consumable action rows.
The shorter centered `Empty` patch leaves two asserted `$FF` bytes at `$7471-$7472`, so
the literal pointer moves back two bytes and the same in-place region now holds
`  Press`. `actionpotspill.py` selects each canonical pot independently from Log 2 and
requires three exact staged rows, three proportional plane matches, and no pool spill.

## Give floor numbers and names one line, then center their visible ink

The first numbered-card generator vertically centered the number and name as independent
masks. Most number masks began at strip row 2, while the taller `Crags` and `Kuyo Pass`
labels began at row 0 and `Koma Cave` began at row 3. That is why those real cards could
put the floor number visibly above or below the name even though each component was
individually centered. The live number data is now stored top-aligned and the uploader
applies one selector-specific line origin to both components.

Horizontal centering had a related hidden-box problem. The renderer centered a reserved
32px number field, not the much narrower visible digits, and then rounded its group origin
to a tile. Each selector now has a reviewed tile-aligned number-field origin and a
pixel-precise label origin based on its active floor range. All 22 active numbered cards
have a shared component top and at most four pixels of outer-margin imbalance. The real
`19 Dragon's Maw` ink now occupies x=7..152, giving exact 7/7px margins.

`tools/floormarkerspill.py` guards the native floor and selector tables, replays every
native table combination plus numbered Moon Exit's maximum-field representative, rotates
all selectors through live values 1-50, compares 72
emulator rasters exactly, and applies the line/centering invariants to the 22 numbered
cards. `tools/dragonmawmarkerspill.py` separately boots Log 1 from
`saves/shiren_en_log_1_dragons_maw.srm` and makes the real floor-19 bounds permanent.

## A box's layout can be duplicated in ARITHMETIC — the name-entry picker

`box_geometry.tsv` treats a menu box as data: x, y, width in the descriptor. That is true for
DRAWING. It is not the whole truth for a box the game also has to *index*.

The name-entry character picker maps a cursor position to a character at `31:$4186`:

```
31:$4186  ld a,[$C6F3] / bit 7,a / jr nz,$4192
31:$418D  ld hl,$4275        ; page 1 base = box 12 row 1   <- a normal reference
31:$4192  ld hl,$42F0        ; page 2 base = box 13 row 1   <- a normal reference
31:$4195  ld a,[$C6F0] / ld c,a          ; column
31:$4199  ld a,[$C6F5] / dec a           ; row - 1
31:$41A0  ld a,$13                       ; ROW STRIDE, an immediate   <- NOT a reference
31:$41A5  call $19E5                     ; (row-1) * stride
31:$41AF  add hl,bc                      ; + column
```

The two bases are 16-bit loads pointing at real string starts, so extraction records them as
references and `build.py` repoints them with the box. **The stride is an immediate and no
mechanism sees it.** `$13` = 19 is the Japanese layout: 18 bytes plus a terminator. English
rows fill all 18 cells of an 18-wide box, so `needs_term` correctly drops their terminators
and the built stride is 18 — and the picker went on adding 19, reading one byte further per
row. Rows 2-5 selected the wrong character for as long as the English build existed
(`G` for `F`, `M` for `K`, `S` for `P`), with every byte-level check green.

`build.py` now derives the stride from the placed rows (`GRID_BOX` / `GRID_STRIDE_AT`),
requires them evenly spaced, and verifies the opcode before patching. `tools/gridprobe.py`
hooks `31:$41B0` and checks each row reads the byte it displays.

The completed 2026-08-10 layout preserves the three 5-cell cursor blocks and fills every
selectable position deliberately:

```text
ABCDE Zabcd  yz.,'
FGHIJ efghi  -!?()
KLMNO jklmn  :/[]+
PQRST opqrs  01234
UVWXY tuvwx  56789
```

There is a second dual-reader trap here: the box drawer supports DTE expansion, but the
picker returns one raw byte from the selected ROM cell. Box 12 must therefore remain
literal even though all six of its rows are now English. `build.py` excludes it from the
DTE-markable boxes and separately asserts `final == plain` for every grid row. The grid
probe derives the relocated row-1 pointer from `31:$418D`, rejects zero observations, and
checks left/middle/right samples on every row under both page branches.

There is also a **screen-lifetime collision outside the grid table itself**. The title/file
VWF is allowed to borrow `$89` while composing the Erase header and `$9E-$A0` while
composing `Erase this?`. Those tilemap references disappear when the confirmation closes,
but their VRAM planes persist. Name entry reuses `$89` for the field underline and
`$9E/$9F/$A0` for its fixed-cell `(`, `)` and `:` keys, so the exact Copy -> Erase -> New
Log route used to show fragments of the outgoing words in all four places.

The dungeon-menu lifetime is broader still. A six-action Floor menu for an unidentified
Willow Staff can borrow almost every raw tile used by the name-entry keyboard before its
`Name` action enters the same screen. Restoring only the four start-menu collisions left
the field and most rows as fragments of the Floor/action VWF. Both name-screen entry
points now pass through a 49-byte bank-44 wrapper which turns the LCD off safely and calls
the cartridge's complete native `$00-$D2` menu-font loader before initialization.
`tools/nameflowspill.py` retains the Copy -> Erase -> New Log regression;
`tools/unidentifiednamespill.py` drives the real Willow Staff Floor -> Name route and
compares the complete visible keyboard tilemap and all referenced glyph planes with fresh
name entry.

The inverse lifetime matters too. The complete native font load correctly repairs the
keyboard, but it necessarily overwrites statusvwf's private low-page tiles. Returning
through Items rebuilds status before revealing it. Most status builds reach
`statusvwf.statusdraw` with LCDC.7 clear; the Rename return reaches it with LCDC.7 set
during the visible scan. PyBoy accepted the renderer's direct VRAM stores, while Mesen
and hardware reject stores made during mode 3. A Mesen savestate showed that the status
tilemap and shadow were byte-exact but the `Strength`, `Experience`, and numeric-value
planes contained mixtures of the native font and the intended VWF pixels.

`statusvwf.statusentry` now distinguishes two lifetimes. The Name -> Items reconstruction
is not a proven direct pop, so it waits for a fresh VBlank, disables the LCD for the
private-tile repaint, and restores LCDC.7 afterward. A later direct Items -> Status pop has
the exact root/Items stack predicate and a stronger ownership proof: none of the 48
private/structured Status tile IDs is referenced by the visible outgoing Items BG or
Window. That route keeps the page live and uploads each of nine completed field slices in
its own full VBlank before native Status map publication replaces the page.

`tools/unidentifiednamespill.py` continues the fixture through Take -> Items -> Name,
types `Stun`, confirms End, returns to Items, and backs out to Status. It compares all 48
private/structured status tile planes before and after the name-screen lifetime, requires
one conservative LCD-off reconstruction followed by one LCD-on direct pop, and verifies
all nine live uploads finish inside VBlank. `tools/itemexitspill.py` independently leaves
the real four-page inventory from pages 1, 2, 3, and 4 with no LCD-off or white frame.

The inverse direct lifetime now has its own boundary. `mgbdis` shows that screen 1 enters
`4:$494E` and calls the stride-aware shadow clear at `$4951-$4956` before item count,
boxes, page markers, or VWF pixels are rebuilt. Bank 53 far index `$09` replaces only that
six-byte operation. With the exact `(Status root, Items child)` stack, screen/hardware
state, valid item selector, and four zero Status cells at visible `$986F-$9872` after
queue drain plus a fresh VBlank rendezvous, it retires BG rows 0-15 in four complete VBlanks and leaves the enabled
two-row Window and every tile plane untouched. The native draw order is box 4's item rows,
then box 14's header, then full-map publication; allowing row publication immediately
therefore exposed item names on a blank field. The entry helper now commits the empty box-14
and box-4 perimeters at the end of its fourth VBlank. Completed Item rows subsequently
appear inside established chrome, and the native final map publisher adds the header text,
page indicator, and final exact map. Unknown contexts still receive the original 20x18,
stride-32 shadow clear and conservative path.

`tools/itementryspill.py` proves the full cycle after independently leaving Items pages
1-4: exactly four entry batches end at LY `$94`, the exact empty box chrome is committed
inside VBlank before the first Item-row call, no frame disables the LCD or becomes
all-white, the Window is byte/plane-exact, and the first post-entry page change begins one
narrow regional transaction with no fallback. `tools/itempagespill.py` additionally runs
a 20-frame carried-page-only cadence. `mgbdis` shows that native Right/Left commits
`$C6AC` and synchronously calls `4:$483E`; it never reads visible `$986F-$9872` to decide
whether that redraw is owned. The page indicator is output and may still describe the
outgoing page while the incoming transaction is valid. The regional gate now drains
`$C11A` and admits from the native screen/row/allocator/count state without vetoing a
stale or partially published visible indicator. That veto was the remaining route to
state `$06` and its LCD-off full-map publisher. The separate state `$05` safety for a
genuinely unsupported regional row remains. The rare trigger was not captured
deterministically, so the fixture hooks the admission decline, regional fallback, and
exact full-map LCD-disable instruction independently so none can hide between sampled
frames. Manual playtest accepted its removal in the checkpoint-3 freeze at commit
`34a20ec` on 2026-08-25.

The selector `$FF` stage is the actual standing-item Floor page, not a dummy sentinel.
Its incoming descriptor has one row, so a five-row regional clear must zero the four
retired left borders rather than preserve them as empty Item chrome. A shape-specific
bank-58 helper now converts the settled five-row rectangle to a complete empty one-row
rectangle before Floor text, and converts it back to a complete empty five-row rectangle
before either Right-to-page-1 or Left-to-page-4 text. The Wood Arrow route proves both
directions, exact zero BG/shadow rows below the settled ground-item box, and uses `$C1B7`
to admit only its completed direct pop through the live Items-to-Status controller. The
same review also found that screen 15's atomic publisher preceded the native cursor
initializer; the selected `$81` cursor is now pre-staged by a register-transparent helper
and the entire first-published title perimeter is tested with it.

The removed visible-indicator predicate was translation code, not a Japanese-ROM check.
A fresh `../mgbdis` pass over `build/base.gb` confirms the native direction handlers at
`4:$7339` and `4:$7354`: each computes and stores the next `$C6AC`, plays the paging
sound, and immediately calls the synchronous stack redraw at `4:$483E`. That redraw
dispatches the current stacked screen and never reads visible `$986F-$9872`. The green
indicator is therefore output, not proof that the new selector owns the screen.

Removing that false veto eliminates the rare LCD-off fallback, but it also made the
renderer’s variable proportional composition time visible as a slow top-to-bottom fill.
The exact regional path now leaves completed rows 0-3 unreferenced; final body row 4
derives the native-equivalent indicator and commits all five owned row regions in one
VBlank. The visible sequence is complete old body, complete regional blank, complete new
body. `tools/itempagespill.py` hooks that sole row-4 commit directly and records zero
gate declines, fallbacks, full-map blanks, or LCD-off frames in both ordinary and rapid
cadences. Floor-to-five-row-Items can return at 23 frames when the final header/body commit
just misses a VBlank; preserving that serialized boundary prevents the previously
observed corruption under rapid page input.

The standing-item Floor page also opens screen 2/box 6, even though its verbs come from
the separate Floor table (`Take / Fire / Swap / Info` for the Wood Arrow fixture). Its B
path is the same `HL=$5689` generic pop that formerly replayed screens 0 and 1 and briefly
disabled the LCD. The private Action gate now admits selector `$FF` only with the settled
`$C1B7=$01` proof. Its VBlank restorer rebuilds the saved Floor top edge, one ground-item
row and bottom edge, zeros the remainder of box 6’s footprint, restores the exact
screen-1 Floor descriptor/state, and skips replay. `tools/flooractionspill.py` measures a
two-frame B return, one-frame acceptance of the following Left input, and zero LCD-off or
white frames.

**The general rule: when a block's byte layout changes, look for code that computes into it.
A reference gets repointed; a hardcoded stride does not.**

## Box aliasing — reclaiming a whole box's bytes

`script/build-inputs/box_alias.tsv` declares that one box renders another's text. Only the descriptor's
text pointer changes, so the box still appears exactly when it did; its own block becomes
unreferenced and its bytes join the bank's free pool as a DECLARED region.

Every 16-bit reference into the aliased block moves row for row to the target's matching row,
which covers both the descriptor pointer (row 0) and code pointing into the block.

Shipped use: **box 13, the name-entry katakana page, renders box 12** — 116 contiguous bytes
at `31:$42DB-$434E`, the largest run bank 31 can offer, and what let the item category boxes
keep `Staff`. In English box 12 alone carries A-Z, a-z, 0-9 and punctuation, so the second
page is redundant. The visible toggle action is retired; if the internal page bit is forced,
both drawing and selection still resolve to the same English grid.

This is deliberately **not** `--use-filler`. The bytes are free because a named box renders a
different one — a claim a person made and a screenshot can check — not because they looked
like padding.

## Blank Scroll is an unused item-data remnant — measured 2026-08-10

The item-name table retains `はくしのまきもの` / `Blank Scroll` at `11:$43B2`, item
ID `$66`, but the GB game does not retain the playable scribing mechanic. A name-table
entry alone is not reachability evidence.

Bank 6 `$5CE0` walks all 128 canonical object records. At `$5CED-$5CF3` it compares the
item ID with `$66` and explicitly writes `$FF` to object byte 1, establishing this record:

```
66 FF 00 04 00 00 FF FF
```

`tools/mesen_spawn_blank_scroll.lua` injects that record through SRAM bank 0's real
`$A3B0` inventory-index list and `$A406` eight-byte object table. A headless PyBoy run with
that exact record reaches the ordinary `Read / Toss / Drop / Info` menu. There is no
writing screen: Info reuses the Lost Scroll description, while Read consumes the object
without a useful effect. Joey's initial Mesen screenshot independently exposed the same
name/description mismatch while testing the earlier probe. Bank 30's dormant `かく`
(`Write`) verb is absent from every category/context table and has no reachable code path.

Therefore `$66` is useful as reverse-engineering evidence, not as game content. Do not
schedule a keyboard translation, VWF screen, item-description repair or gameplay test for
Blank Scroll unless new reachability evidence contradicts the measured route.

## The ten embedded/unframed coverage hits are non-text — audited 2026-08-10

`tools/coverage.py` deliberately uses a permissive heuristic: an unframed run of decodable
bytes with a dialogue marker and at least six consecutive kana is suspicious. That rule
found real missed prose in sessions 7/8b, but after those extraction fixes it still reported
ten hits in script banks. A count baseline could detect growth but could not establish what
the ten existing runs were. V4D traced every one to the code that consumes its surrounding
structure:

| Scanner location | Actual structure | Consumer evidence |
|---|---|---|
| `3:$7F64` | fragment of a 16-byte animation/state record | `3:$74ED` selects from the table rooted at `$7F07` after `swap c`; the loop at `3:$756D` advances by `$10` |
| `4:$514F` | misaligned fragment of a 36-entry jump-target table at `$5130` | `4:$5118` indexes a little-endian address and `4:$5123` executes `jp hl` |
| `4:$5285` | executable graphics-copy routine | called at `4:$526F`; loads `$8DE0`/`$529A` and copies a 5×8 block, writing each source byte twice |
| `11:$45E6` | item-name pointer-table bytes | lies inside the ascending little-endian table rooted at `11:$4537` |
| `11:$5067` | second bank-11 text-pointer-table bytes | lies inside the paired-address table rooted at `11:$4FC4` |
| `13:$55BD` | item-help pointer-table bytes | inside the 157-entry table at `13:$554A-$5683` |
| `13:$55CD` | item-help pointer-table bytes | same table |
| `13:$5613` | item-help pointer-table bytes | same table |
| `30:$7884` | graphics bytes | `30:$7861` copies the 128-byte block at `$7873-$78F2` to VRAM `$95C0` |
| `31:$689E` | indexed graphics/frame data | readers at `31:$62C5/$6315` select from `$657F+` and queue doubled bytes at `$C008` for VBlank transfer; related frame selection uses `$6554+` |

The false positives are therefore six pointer-table fragments (counting the jump-target
table), two graphics-data fragments, one animation-record fragment and one executable
graphics copier. No string was extracted or translated as part of this audit.

`coverage.py` now stores the exact bytes as well as the address and structural reason for
each classification. A run is exempt only if both address and bytes match; a new hit, or
different bytes at a reviewed address, fails the build. A declaration may disappear when
scanning a transformed ROM, which is harmless. This closes the static V4D candidate list,
but not the logically impossible claim that static coverage knows every runtime entry:
emulator route scans remain responsible for discovering starts inside already covered
records, as the rescued-child route demonstrated.

## Save-summary locations have two native producer contracts — measured 2026-08-11

Log summary box 26 does not receive one self-contained string per visible row. Bank 4's
builder at `$68A3` clears `$C616-$C647`, builds row 1 from `$C625`, and formerly executed
four unconditional `inc de` instructions at `$6985` before copying the selected place.
Those cells are meaningful for a numbered floor, but they are only indentation for a
numberless place. This is why the Koppa-town fixture rendered `Dragon's Maw` indented and
split despite the same label fitting elsewhere.

The row boundary is also logical rather than a fixed source address. `19F Dragon's Maw`
needs 16 source cells; under the old 14-cell summary descriptor, `aw` and the label's
terminator landed at `$C633+`, where row 2 begins. The native drawer advances to one byte
past that terminator, so the intended padded `Hard` field was skipped. Redirecting row 1
to a private complete copy solved the visual width but initially published the private
scan pointer into `$C69F/$C6A0`, skipping row 2 for a second reason.

`menuvwf.py` now replaces the four-byte indent with a context helper, keeps the four
prefix cells only when `$C627` contains the English `F`, copies a spilling row to `$C648`,
clears the original tail through its terminator, and saves the actual original next-row
pointer in `$C645/$C646`. After the private VWF scan it restores both BC and
`$C69F/$C6A0`. The location allocation grows from eight to ten tiles, making the three
row capacities 9+10+8 at `$DE-$F8`.

`tools/savesummaryspill.py` turns all three discoveries into one focused battery. It boots
the numberless Dragon's Maw, numbered Dragon's Maw, and formerly fixed-width Koma Cave
SRAMs; requires rows 0/1/2; compares the exact row-1 code stream; requires row 2 to reduce
to `Hard`; and reuses `startspill`'s shadow, two-plane, visible-lifetime and pool-collision
checks. The shipping build reports 33 exact rows, 1,422 visible checks and zero problems.

## Rankings repaints the cleared-Orochi emblem — FIXED 2026-08-12

This section preserves the failure analysis that led to the screen-scoped Rankings repair.
The replacement regression now checks the real badge tiles and repeated Rankings/Adventure
navigation; the implementation and acceptance record is in
recorded in `VWF_BUDGETS.md`.

The first diagnosis was wrong. `tools/orochisymbolspill.py` watches tile IDs
`$5B/$5C/$63/$64`, BG cells `(8,2)/(8,3)/(10,2)/(10,3)`, and framebuffer crop
`(16,64)-(32,80)`. Those are not the visible cleared-Orochi badge. The real coloured
16x16 badge in the supplied Log summary uses `$CB/$CD` on its top row and `$CC/$CE` on
its bottom row, at `$9800` BG rows 9-10, columns 5-6; its crop is `(40,72)-(56,88)`.

Visiting Rankings -> Kuyo changes those four real planes. Returning to Adventure restores
their map IDs but not their pixels, leaving VWF fragments in place of the badge. The
existing test passes because its sampled region is unaffected; its own
`build/orochisymbolspill/returned_log.png` visibly contradicts the zero-problem result.
This was a known false positive and was replaced before the repair was accepted.

Moving the Rankings-name pool from `$43-$6A` to `$80-$A7` did not establish ownership.
The census proved only that sampled fixed Rankings BG cells did not reference the new
range. It did not prove the range private across every BG/window cell, OAM/native graphic,
or adjacent-screen lifetime. Whole-page English eligibility protects the raw-kana fallback;
it does not make VRAM private.

The ROM is non-CGB/SGB (`$0143 == $42`), so a second CGB VRAM bank and attribute-map bit
cannot solve this. Rankings must retain VWF and be rebuilt as one screen-scoped allocation:
audit all simultaneously visible native graphics, keep them disjoint or explicitly
relocate them, and restore any safely borrowed offscreen planes before their maps are
revealed. Transition blanking remains useful but cannot recreate overwritten planes.
The canonical implementation record is recorded in `VWF_BUDGETS.md`.

## Ending-credit tiles are column-interleaved — fixed 2026-08-11

The approved credit asset stores each 20x2 text strip in ordinary row-major order: all 20
top tiles, then all 20 bottom tiles. Bank 31's native `$7C88` map builder instead places
even IDs across the top and odd IDs across the bottom. Uploading the asset verbatim thus
displayed alternating fragments from both rows, even though the initial emulator test
reported every VRAM byte exact—it compared the upload to the same incorrectly ordered
source rather than reconstructing what the map displayed.

`endingcredits.py` now converts each strip to `top0,bottom0,top1,bottom1,...` before ROM
installation. `endingcreditspill.py` independently resolves the live map IDs back through
VRAM, compares the resulting row-major tiles to the approved asset, waits through the
native palette fade, and compares the actual 160x32 on-screen credit raster for all 22
cards. This is the regression that the visibly broken version fails 22/22.

---

## The copy-loop inventory — use this instead of guessing

| idiom | bytes | sites |
|---|---|---|
| store-then-test | `2A 12 13 FE FF 20` | 6: `4:$7458` `11:$51F0` `11:$52D5` `11:$7E63` `14:$7C1E` `30:$7E8A` |
| box row drawer | `31:$40D8`, source in **bc** | 1 caller, `31:$4095`; hooked at `31:$4106` |
| test-then-store | `2A FE FF 28` | 44 candidates (generic pattern; includes `13:$40DB`) |
| control-aware | `2A FE E0` | 2: `13:$6893`, `13:$6AE5` |

`tools/gbrun.py --trace` hooks all of them at once and reports which fired with what source,
which is how to attribute a screen rather than reason about it.

## Two decisions worth not re-litigating

**The buffer bound is an address, not a character cap.** `emit_lit` refuses to write at or
past `$CF38` — stronger than a character cap, because it holds however many bytes a pair
expands to. `$CF38` not `$CF43` because the composer reads the buffer's zeroes as the end of
the line, so writing past the shorter clear (`$CF07+$32`) would leave text unterminated.

The box path does NOT get that guard, and should not: its destination is the `$C300`
tilemap staging buffer, and what bounds it is the box width in `e`.

**Cell counting charges the dakuten, not the base character.** `13:$40F3` peeked the next
*source* byte, which cannot survive expansion once that byte may live inside a table entry.
Charging the mark is equivalent — a mark always follows a base character, two never adjoin —
and needs no lookahead.

## Untranslated Japanese collides with the DTE code space — retracted as "cosmetic" 2026-07-30

**Untranslated Japanese collides with the DTE code space** (it uses 181 of 224 literal
codes) and renders differently garbled. The Latin font is already over the kana tiles, so
it is garbage either way, and the `$CF38` guard makes overrun impossible. Only translated,
allowlisted strings are compressed, and box text is expanded only for a box marked
compressed.

**It is not purely cosmetic, though, and this session measured that.** Expanding Japanese
changes CELL counts, so it changes message wrapping and therefore timing: with `a:120` from
`saves/dungeon.state` the status bar's second row stays hidden until the next button press.
Any change to the code set moves this around — an arbitrary `$81-$9C` does it too. It
resolves on input, the game stays healthy, and it shrinks as text gets translated.

## Code space is 46, and it is MEASURED against the script

The old plan said 140; that counted only English. A DTE code must also miss the combining
marks, be separable cheaply, and — learned the hard way — miss any byte a translation names
with a `<$XX>` escape. Free: `$43-$78`, `$81-$9D`, `$B7-$DF` = **124 codes**, five compares.
`$B3-$B6` is the reservation for layout glyphs; `$B6` is the status screen's column divider.

The 19 left over are English's punctuation, reusing the ROM's **native** glyphs at
`$7C-$B2`. (Also why `codec.encode` resolves `'F'` to `$B4` and not latinfont's `$10` —
`build.encode_en`/`EN_CODES` is the one the inserter uses.) Compacting them into `$43-$4C`
would make `$4D-$B2` one range and a one-compare test: the only DTE upgrade left.


## `$C006` is a VRAM transfer queue — settled, and both readings were right

`13:$43B8` and `13:$4484` write **the same buffer with different payload types**, because
`$C006` is not a tilemap row and not a tile buffer — it is a queue of VRAM transfers, each

```
dw   destination            ; a VRAM address
db   payload[n]             ; the bytes to put there
```

consumed by a stack-pointer blitter in bank 0 (`ld sp,$C006` / `pop hl` = destination /
`pop de` × n / `ld [hl+],a` ×2). There are two consumers and they disagree about `n`, which
is the whole reason the two readings looked irreconcilable:

| consumer | slot stride | payload | slots seen |
|---|---|---|---|
| `0:$10A0` | **22** (`dw` + 20) | a **tilemap row**, 20 entries | `$C006 $C01C $C032 $C048 $C05E` … |
| `0:$11C5` | **66** (`dw` + 64) | **tile data**, 4 tiles | `$C006 $C048 $C08A` |

`3 × 22 = 66`, so the two views agree on the boundaries at `$C006`, `$C048` and `$C08A`.
`$C0CC` has no reference anywhere in the ROM, so three 66-byte slots is the whole of it —
**192 bytes, 12 tiles**, and that is the constraint that shapes everything below.

### The geometry that falls out — measured

* A message line owns **18 consecutive VRAM tiles**. `13:$4523` writes the tilemap row as
  18 *incrementing* tile indices (`ld [hl+],a / inc a`, `ld b,$12`), so the tilemap does
  nothing but count.
* The three lines' tile bases are the table at `13:$4412`: **`$8A80`, `$8BA0`, `$8CC0`**,
  picked by `[$CF06] & 3`. They are `$120` apart = exactly 18 tiles. No slack between them.
* **A line is drawn in TWO HALVES of 9 tiles**, because 18 tiles is 288 bytes and the queue
  holds 192. `13:$43B8` renders 9 glyphs into the three slots (4 + 4 + 1) and
  `13:$43E2` adds **`$90` = 9 tiles** to the destination when `([$CF06] >> 4) & 3 == 1`.
* The caller state machine is `13:$4310`, on `([$CF06] & $30) >> 4`:
  `2` → `ld hl,$CF07` + `call $43B8` (first half) → `1` → `call $439F` + `call $43B8`
  (second half) → `0` → `call $4484` (the tilemap row). `13:$439F` is *"advance `hl` past 9
  characters"*, and `13:$6BE2` is its twin on the other caller path.
* `13:$43B8` is the **single choke point**: its five callers are `13:$4328 $433A $524B
  $6A97 $6AA3`, and `13:$4464` (the blitter) has no other caller. Patch `$43B8` and every
  path that draws composed text gets VWF.

Trace evidence, from `saves/town.state` walking into the first villager:

```
f163  13:$43B8 CF06=A0  blits c=4A,65,48,9A,1D,2C,2D,36,29 to de=C008,C018,C028,C038,
                                                                C04A,C05A,C06A,C07A,C08C
      13:$43F5 dest1=$8A80        0:$11C5 copy dests=8A80 8AC0 8B00
f164  13:$43B8 CF06=90  blits c=32,15,7B,38,B2,9B,00,00,00
      13:$43F5 dest1=$8B10        0:$11C5 copy dests=8B10 8B50 8B90
```

`$8A80 + $90 = $8B10`; `de` steps `$10` inside a slot and `$12` across a slot boundary,
which is the 2-byte destination field being skipped. `1D 2C 2D 36 29 32` is `Shiren`.

## The menu box drawer needs a GATE, and that is the whole story

The plan assumed the composer's "accepted cost" transfers: expanding a byte that is not
really a DTE code garbles some glyphs, and Japanese renders as garbage anyway. **It does
not transfer.** The composer's floor is one bad line -- its buffer is bounded, its string
ends at an `$FF` the expander refuses, and the next line starts from a fresh pointer.

The drawer has no floor. It draws a FIXED number of cells and then leaves `bc` wherever it
stopped; the next row simply continues from there. So a byte that expands to two cells
where the row budgeted one makes the row run out of cells *before* it reaches its
terminator, and **every following row of that box starts at the wrong byte**.

And the drawer's source is not always ours to vet. The file-select box draws the **player's
saved name out of SRAM** -- katakana codes, squarely inside `$43-$78`. No content test can
ever make that safe.

So expansion is gated on the BOX: **bit 7 of the descriptor's flags byte**, which reaches
the drawer at `$C69E`. Only 2 of its 8 bits are used across all 52 descriptors (`$00`,
`$02`, `$04` are the only values) and only `31:$4043` and `31:$40A1` read it. `build.py`
sets it only for a box whose **every** row is translated English and whose text is not
WRAM-staged -- exactly the condition under which every DTE-range byte in it is one the
compressor put there.

## Three white screens, because each is a rule

**1. A `<$XX>` layout escape cannot be a DTE code.** `31:$41E9` is `Weapon  <$B6>Str` --
`$B6` is the vertical bar holding the status screen's two columns, and it was inside
`$B3-$DF`. The drawer expanded it, drew two cells where the row budgeted one, and the
cascade above did the rest. **`$B3-$B6` is now reserved** and the top DTE range starts at
`$B7` (124 codes, not 128; 40.2% not 40.6%), and `build.py` rejects any translation whose
raw escape lands in the code space -- a build error naming the string, not a white screen.
A `<$XX>` byte is layout the renderer must reproduce EXACTLY, the same category as a
control code or a combining mark, and it belongs in the same exclusion.

**2. The gate above.** Reserving `$B3-$B6` fixed the status screen and the file-select
screen still died, on the player's saved name.

**3. Resident code must not run to the last byte of bank 0.** `dte_box_hi` was first
written as exactly 20 bytes, `$3FEC-$3FFF`, so its `ret` sat on `$3FFF` -- and that `ret`
did not return. White screen, CPU spinning on `rst $38`, while the identical bytes ran
clean under `tools/gbemu.py`. Moving the routine twelve bytes earlier, changing nothing
else, fixed it outright. The byte after `$3FFF` is `$4000`, which belongs to whichever bank
is mapped, and during an expansion that is the TABLE bank. `BOX_END` is `$3FFF`, not
`$4000`, and `build_box()` refuses to cross it.

## What this cost, and the one difference that remains

Reserving four codes shrank the table, and **that changes how untranslated Japanese
expands** -- which is not only cosmetic. In the dungeon, `a:120` leaves the status bar's
second row hidden until the next button press, where the pre-hook build restores it after
~46 frames. It is not the box hook: a build with the box hook and `--no-dte` behaves like
the baseline, and an ARBITRARY different code set (`$81-$9C` instead of `$81-$9D`) breaks
it the same way. It is the accepted cost, sharpened: **expanding Japanese changes cell
counts, so it can change message wrapping and therefore timing, not just glyphs.** It
resolves on input, the game stays healthy, and it goes away as text gets translated.

## A renderer's geometry can be duplicated in ARITHMETIC — the name-entry grid

Found while doing the above, in the same code. **The picker duplicates the grid box's row
spacing as an immediate**: `31:$419D` computes `base + (row - 1) * stride + column`, where
`base` is box 12 row 1 (a normal reference, repointed with the box) and `stride` is the
operand of `31:$41A0 ld a,$13`.

`$13` = 19 is correct for the Japanese — 18 bytes plus a terminator. Translated rows fill
all 18 cells, so `needs_term` drops their terminators and the real stride becomes **18**.
Nothing updated the constant, so every row below the first read one byte further along than
the row before it. Measured on the shipped build: **row 2 gave `G` for `F`, row 3 `M` for
`K`, row 4 `S` for `P`.** Typing your own name mostly did not work.

`build.py` now derives the stride from where the rows actually landed, asserts they are
evenly spaced, checks the opcode before patching, and reports the change. Verified with
`tools/gridprobe.py`: every row of both pages now reads the byte it displays.

**The general lesson: a renderer's geometry can be duplicated in ARITHMETIC somewhere else.**
`box_geometry.tsv` moves a box; it cannot know that another routine hardcoded the old
layout. When a box's byte layout changes, grep for code that indexes it.

## Menu-path facts settled once, so nobody re-derives them

* `saves/dungeon.state` loads IN the dungeon; **B opens the main menu** (start does not),
  `A` then enters the item list. Earlier confusion ("start opens the menu") cost several
  probe runs.
* The shadow→VRAM tilemap copy is command-stream driven (`0:$3C3F` appends; emitters
  around `0:$3D90-$3EAF`), consumed in vblank. No `$C300`/`$9800` immediates exist in
  bank 0 — do not search for them.
* `31:$4106` already reads `call $00F0` in the shipped ROM — the menu DTE hook LANDED;
  any VWF hook must expand DTE itself or sit above it. (Older notes calling this "still to hook" are stale.)
* The `$8800` region's 68+15 extra font tiles (`13:$7657+`) include the cursor `$81`,
  digits-for-status, borders `$B8-$BF` — indices `$80-$D2` are re-uploaded at menu open
  too, so nothing composed may live below `$D3` in that half without the same
  compose-after-upload ordering.
