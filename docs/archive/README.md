# Archived engineering handoffs

These files preserve completed investigations and implementation records. They are useful
when changing the subsystem they describe, but they are **not required onboarding** and
do not define the current work queue.

Start with the repository [README](../../README.md). For current project status and
remaining work, read [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md). Use
[HANDOFF.md](../../HANDOFF.md) as the durable low-level tools and traps reference.

| Document | Status | Read it when |
|---|---|---|
| [HANDOFF_NEXT_HISTORY.md](HANDOFF_NEXT_HISTORY.md) | Superseded | Looking up the former session-by-session roadmap or dated measurements |
| [HANDOFF_BUG.md](HANDOFF_BUG.md) | Fixed | Investigating phantom pointer rewrites or message expiry |
| [HANDOFF_SPACE.md](HANDOFF_SPACE.md) | Closed | Reviewing pool/relocation capacity decisions |
| [HANDOFF_1B.md](HANDOFF_1B.md) | Optional historical design | Revisiting dialogue DTE/compression |
| [HANDOFF_VWF.md](HANDOFF_VWF.md) | Landed | Changing the dialogue composer VWF |
| [HANDOFF_MENUVWF.md](HANDOFF_MENUVWF.md) | Complete | Changing menu/item/status VWF or VRAM ownership |
| [HANDOFF_RANKVWF.md](HANDOFF_RANKVWF.md) | Complete | Changing Rankings/Orochi screen-scoped ownership |

Addresses, measurements and failure analyses remain here intentionally. Historical
statements such as “current blocker” describe the date of that record; the root README
and `HANDOFF_NEXT.md` take precedence.
