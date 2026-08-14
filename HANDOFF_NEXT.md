# Current handoff — Shiren GB English translation

**Current through 2026-08-13. This is the entry point for a new development session.**

The project is in release-candidate validation. There is no known gameplay blocker and no
open renderer rewrite. Continue the full-game playtest, capture any newly found route as a
save-backed regression, and keep the complete battery green.

## Read this much

1. [README.md](README.md) — current status, build instructions, complete release battery
   and repository map.
2. [TRANSLATING.md](TRANSLATING.md) — mandatory before editing `script/en.tsv`; control
   tokens, storage classes and wrapping rules.
3. [VWF_BUDGETS.md](VWF_BUDGETS.md) — measured renderer contracts.
4. [docs/ROM_BANK_MAP.md](docs/ROM_BANK_MAP.md) — mandatory before moving ROM code,
   tables, text or graphics.
5. [FINDINGS.md](FINDINGS.md) and [HANDOFF.md](HANDOFF.md) — lookup references for ROM
   behavior, tools and traps; do not read them front to back.

Completed subsystem records are indexed in
[docs/archive/README.md](docs/archive/README.md). Read one only when changing that
subsystem. The former session-by-session handoff is preserved as
[HANDOFF_NEXT_HISTORY.md](docs/archive/HANDOFF_NEXT_HISTORY.md).

## Current release candidate

- Ordinary extracted script: **1,406 of 1,424 records translated**. The other 18 are
  proven unrendered: six aliased name-entry records and 12 entries no live path draws.
- Cinematics: all **12 canonical lines** across the prologue and ending programs are
  translated. All **22 ending-credit cards** retain their native order and timing.
- Production font: **Thin Pixel-7 GB Compact** for dialogue, menus and cinematics.
- Town/dungeon cards: all eight labels and every live floor value 1–50 use the approved
  Poppins-derived raster.
- VWF: dialogue, Items/Info, item/status menus, main/file menus, save summaries, Awards,
  Fay, and Rankings are complete. Rankings uses screen-scoped ownership and restores
  native graphics plus the Orochi badge before adjacent screens become visible.
- Known playtest blockers: **none**. The rescued-child exit freeze, ordinary stair text,
  Gitan Info dismissal, Copy Log lifetime, hidden-item rendering, Pot actions and the
  Rankings/Orochi corruption all have permanent regressions.
- Manual Rankings acceptance: Joey repeated the Kuyo/Adventure cycle and checked Village
  Exit in Mesen on 2026-08-12; VWF and native graphics remained correct.

Current verified artifacts:

| Build | SHA-256 |
|---|---|
| `build/shiren_en.gb` | `bfbe87b57adba0d06fa800f89cdd487bf595c76f447437cc8ab69b4e023f975a` |
| `build/shiren_en_shuffle.gb` | `55219fc2e9e2ec4da34cfe09f327bbfbc0a101b69b0d8d78775684661192e753` |
| `build/shiren_en_redirect_all.gb` | `11b59056986003a23e5cdb4154f10cd709b902ed9d08d2ccb584d24e61d55390` |

The complete battery passed on 2026-08-13 with all 72 CPU-health seeds healthy, byte-exact
renderer uploads and zero spill across 1,226,636 text-visible containment frames. Run it
from the repository root with `python3 tools/release_battery.py`.

The frozen pre-Rankings-repair diagnostic ROM remains intentionally known-bad at SHA-256
`b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`.

## What remains

1. **Continue the full-game playtest.** This is the primary discovery mechanism. Static
   coverage cannot discover an unknown interior event entry, and automated navigation
   cannot judge every sentence or animation transition.
2. **Turn every reproducible defect into a fixture and regression first.** Store local
   `.srm`/state files under `saves/`; they remain gitignored game data. Add the route to
   `build.sh` when it should gate ordinary builds.
3. **V6 release freeze.** When the playthrough is accepted, stop changing font, text,
   graphics and geometry; run `python3 tools/release_battery.py`, verify a clean
   clone with locally supplied ROM/fixtures, and record final hashes.
4. **Optional research only:** replace legacy runtime-substitution warning estimates with
   an exact producer-to-template census. `13:$4B66` remains the one broad-candidate audit
   risk. The current combat pair is unchanged and works in live routes; do not change its
   `<var>` / `<cE4>` token ABI without tracing and patching the native producer.

## Non-negotiable engineering rules

- `sh build.sh` is only the normal-build gate. A release claim requires
  `python3 tools/release_battery.py`, including fixture preflight plus the normal,
  shuffled and redirect-all matrix.
- Text must satisfy control-token parity, source staging, physical pixel width, temporary
  tile allocation and frame time. Passing one limit does not imply the others pass.
- The redirect-all layout is a real timing gate. On 2026-08-13 it exposed a 160-scanline
  reveal-map pass that normal placement missed; the optimized direct-pointer builder now
  completes the same route within 143/154 scanlines and uploads byte-exact.
- Preserve all `<...>` control tokens and their ordering. Never infer that `<end>`, `<brk>`
  or a mode argument is decorative.
- Space is not a translation constraint. Relocation is complete and has large headroom;
  write natural English, then wrap it with the measured renderer tools.
- Rankings must remain VWF. Do not fall back to fixed-width text or weaken the Orochi,
  repeated-navigation, native-control or hostile-layout regressions.
- A green model is not visual approval. Photograph or inspect the actual emulator route
  for player-facing graphics and transitions.
- Do not commit ROMs, SRAM, save states, credentials or generated screenshots.

## Fast orientation by task

| Task | Start here |
|---|---|
| Translation or wrapping | `TRANSLATING.md`, `script/prose_draft.tsv`, `script/en.tsv` |
| Font/dialogue renderer | `VWF_BUDGETS.md`, `tools/dialogue_preview.py`, archived [HANDOFF_VWF.md](docs/archive/HANDOFF_VWF.md) |
| Item/menu/status VWF | `tools/menuvwf.py`, `tools/menuspill.py`, archived [HANDOFF_MENUVWF.md](docs/archive/HANDOFF_MENUVWF.md) |
| Rankings/Orochi | `tools/rankvwf.py`, `tools/orochisymbolspill.py`, archived [HANDOFF_RANKVWF.md](docs/archive/HANDOFF_RANKVWF.md) |
| Prologue/ending | `script/intro.tsv`, `tools/intro.py`, `tools/introspill.py` |
| Town/dungeon/title graphics | `tools/markers.py`, `tools/titlecard.py`, `tools/titlelogo.py` |
| ROM internals or a new crash | `FINDINGS.md`, `HANDOFF.md`, `tools/crashscan.py` |

For archived rows in the table, use [docs/archive/README.md](docs/archive/README.md) to
open the corresponding record.
