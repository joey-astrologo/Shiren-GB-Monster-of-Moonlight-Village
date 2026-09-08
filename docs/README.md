# Documentation

Subject-organised reference for the Shiren GB translation. Nothing here is required
onboarding — start with the repository [README](../README.md), and if you are translating,
[`script/README.md`](../script/README.md).

| Document | Subject | Read it when |
|---|---|---|
| [TEXT_REFERENCE.md](TEXT_REFERENCE.md) | Translation rules | You need the character set, storage classes, control tokens, per-renderer pixel budgets, or the worklist error list |
| [Prose Studio](../site/prose/README.md) | Browser editor proof of concept | You want to edit prose with Japanese reference, preview text fit, and download/import a changes TSV |
| [FINDINGS.md](FINDINGS.md) | How the ROM works | You need encoding, pointer tables, renderers, the DTE design, or any measured ROM behaviour |
| [VWF_BUDGETS.md](VWF_BUDGETS.md) | Renderer contracts | You are changing a variable-width font path — dialogue, menus, items, status, Rankings |
| [ROM_BANK_MAP.md](ROM_BANK_MAP.md) | Memory ownership | **Before** placing or moving ROM code, tables, text or graphics |
| [ENGINEERING_RULES.md](ENGINEERING_RULES.md) | How to work here | Before changing anything: the gates a change must pass, fixtures, and how to verify a render-path change |
| [TRAPS.md](TRAPS.md) | Mistakes that cost time | You are about to trust a measurement, a bisect, a scan, or a green build |
| [FUTURE_PLANS.md](FUTURE_PLANS.md) | Regional-blanking design history | You need the original checkpoint rationale; use MENU_STRUCTURE.md for current route status |
| [MENU_STRUCTURE.md](MENU_STRUCTURE.md) | Menu navigation and display ownership | You are changing menu transitions, screen/box drawing, tile lifetimes, or regional blanking |

## A note on provenance

Current translation rules were reconciled with the toolchain on **2026-09-08**.
`TEXT_REFERENCE.md` indexes the implementation sources; `VWF_BUDGETS.md` summarizes
renderer contracts, and `script/README.md` gives the editing workflow. When those rules
change, update all affected guides and TSV header comments together. A historical count,
font measurement or checkpoint restriction must not silently become a current limit.

These files absorbed the project's engineering handoffs. The handoffs recorded work
session by session, which meant a fact's home was whenever it was discovered rather than
what it was about — and their dated status blocks contradicted the current README. The
durable content was moved into the files above and the handoffs were removed.

Two consequences worth knowing:

- **Some records are retractions.** A claim that was measured, believed, and then
  disproved is kept deliberately — see the retracted DTE "purely cosmetic" note in
  `FINDINGS.md`, and most of `TRAPS.md`. They are the cheapest way to stop the next
  person repeating the work.
- **Dates in these files describe when something was measured**, not the current state.
  The repository [README](../README.md) is authoritative for current status and hashes.
