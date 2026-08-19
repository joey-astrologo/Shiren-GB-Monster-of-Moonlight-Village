# Translating Shiren GB

## Start here → [`script/README.md`](script/README.md)

That page is the working guide. It tells you **which file to open for each kind of text** —
item names, monster names, menu strings, story prose, combat messages — and the rules and
limits that apply to each.

## The one-minute version

```sh
python3 tools/wrap_en.py script/prose_draft.tsv --apply   # sentences -> en.tsv lines
sh build.sh                                               # build + every check
cat build/worklist.tsv                                    # anything that did not fit
```

Three things worth knowing before you write anything:

- **Keys are `loc` (`bank:$address`), never the row number.** Ids get reassigned by sorted
  offset, so an id-keyed edit silently retranslates the wrong string.
- **A failed translation never corrupts the ROM.** It is reported and the original Japanese
  is kept for that string, so the build always boots. Failures appear *only* in
  `build/worklist.tsv`, and a clean build deletes that file — so "no such file" means
  nothing failed. A green build is not proof you read it.
- **How much room you have depends on how the game reaches the string**, and it ranges from
  "must be same-or-shorter" to "length does not matter at all". That is
  [`docs/TEXT_REFERENCE.md` §3](docs/TEXT_REFERENCE.md), and it is worth reading once
  before a large batch.

## Going deeper

| Document | What it is for |
|---|---|
| [`script/README.md`](script/README.md) | **The working guide.** Which file, which rules, per text type |
| [`docs/TEXT_REFERENCE.md`](docs/TEXT_REFERENCE.md) | The measured reference: character set, storage classes, control tokens, pixel budgets, worklist errors, and what the build does not check |
| [`docs/VWF_BUDGETS.md`](docs/VWF_BUDGETS.md) | The canonical fit register |
| [`docs/FINDINGS.md`](docs/FINDINGS.md) | How the ROM works. Not needed to translate |
| [`docs/README.md`](docs/README.md) | Index of all reference documentation |

[`docs/ENGINEERING_RULES.md`](docs/ENGINEERING_RULES.md) covers the gates a change must
pass, and [`docs/TRAPS.md`](docs/TRAPS.md) the mistakes that have cost real time.
