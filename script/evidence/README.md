# Runtime evidence — not translation files

Nothing here is text you translate. These files record what the game actually substitutes
into a `<var>` (`$E2`) at runtime, so `tools/varaudit.py` can prove a translated line still
fits once the longest real value is pasted in. `varaudit.py` runs on every build.

**If you are translating the game, you can ignore this folder.** See `../README.md`.

| File | What it records |
|---|---|
| `var_domains.tsv` | Confirmed runtime domains — the exact value set a given `<var>` can take, with the evidence for it |
| `var_roles.tsv` | Role-scoped review domains, keeping monster, combat-actor and player-name substitutions separated |
| `var_advisories.tsv` | Advisory roles that narrow a proven producer class where overflow would otherwise be treated as fatal |

All three share the format `loc <TAB> box <TAB> line <TAB> occurrence <TAB> … <TAB> evidence`,
documented in each file's header. The `evidence` column is the point: a row without a
traceable reason for its claim is worth less than no row at all.
