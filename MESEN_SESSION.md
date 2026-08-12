# Mesen session checklist — four answers in one sitting

Two ROMs matter here:

- `build/shiren_en_slice.gb` — the English slice (font + 12 menu strings)
- `build/base.gb` — the untouched Japanese original (symlink to the real file)

---

## 1. Does English render? (5 min, `shiren_en_slice.gb`)

Load it and look at the **title / main menu**, which appears within seconds of boot.
Expect:

| Was | Now |
|---|---|
| ぼうけんにでる | `Adventure` |
| にっきをつくる | `New Save` |
| にっきをうつす | `Copy` |
| にっきをけす | `Erase` |
| なまえをかえる | `Rename` |
| ばんづけ／パスワード | `Rank/Password` |
| かいそう | `Sort` |
| フェイのもんだい | `Fei's Task` |

Difficulty select should read `Easy` / `Mid` / `Hard`, and the first dungeon `Village`.

**Everything else in the game will look like garbage — that is expected.** The Latin
alphabet is written over the kana tiles, so any still-Japanese text now renders as
English letters. It is not a bug; it is the same tiles being reused.

What to report back: a screenshot, or just whether the words are legible and correctly
positioned. Things worth noticing — letters too cramped, baseline sitting wrong,
trailing pad-spaces causing a visible gap.

## 2. Mapper conversion — ANSWERED 2026-07-28

The logger run settled it: **every** ROM bank write lands in `$3F00-$3FFF` (6137 of
them, 100%), because the bank-switch routine at bank 0 `$07A8` does `ld d,$3F` /
`ld [de],a`. So **MBC5 is out** — it reads that page as ROM bank bit 8.

**MBC3 is the target instead** (`$147` = `$13`): its ROM bank register spans the whole
`$2000-$3FFF` exactly like MBC1, so those writes work unchanged, and it reaches 2 MB.

### 2b. Confirm the MBC3 build plays identically (~10 min)

ROM: **`build/shiren_mbc3_test.gb`** — a 2-byte diff from the original (cart type +
header checksum), nothing else changed, so any difference in behaviour is down to the
mapper alone.

Play the same ground as the logger run, watching for these specific failure shapes:

| Test | What a failure looks like |
|---|---|
| Boot, title, menus | freeze, or garbled tiles |
| Enter a dungeon, walk a few floors | corrupted graphics = wrong ROM bank loaded |
| Use items, open the inventory | wrong text/graphics appearing |
| **Save, quit, reload** | lost or corrupted save = RAM banking broken |
| **Ranking / password screen** | garbled entries = SRAM bank select broken |

The save and ranking screens matter most — they are the parts that exercise the 4 SRAM
banks, which is where a mapper swap is most likely to go wrong.

If it plays normally, expansion to 1 MB is unblocked and repointing can proceed.

## 3. The `$EB` arity discrepancy (~2 min)

A real unresolved conflict. The skip-chain at bank 13 `$441B` advances **two** bytes for
control code `$EB`, but `$EB`'s handler at `$416D` reads no argument — it only sets
`$CF05 = 1`. The codec currently assumes **0 arguments**, following the handler.

If that is wrong, the inserter will corrupt every string containing `$EB` (29 in the
script). To check: breakpoint on execute at bank 13 `$416D`, then inspect `bc` — if `bc`
points at a byte that gets consumed, it takes an argument.

## 4. Control-code parameters, rung 4 (~10 min)

Three codes take an argument byte whose *meaning* still needs eyes on screen:

| Code | Handler | What it does | Guess |
|---|---|---|---|
| `$F0` | `$42BB` | reads arg, passes to `rst $10` | ? |
| `$E7` | `$415D` | reads arg -> `$CFC3` | ? |
| `$EC` | `$4149` | reads arg = count, `rst $18` xN | padding / repeat |

`$E0` (45 uses) reads an arg then conditionally `call $3F84` — likely a sound effect.
Easiest confirmation: play with sound on and see whether `$E0` strings coincide with a
sound. Strings using them are listed in `script/script.json` (search for `<cF0:`,
`<cE7:`, `<cEC:`, `<cE0:`).

---

## Priority if time is short

1 and 2 are the valuable ones. 3 matters before the inserter goes beyond same-length
replacement. 4 is polish and can wait.
