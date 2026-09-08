# Translation workbenches

The [control code reference](../controls/index.html) explains code meanings, examples
and differences between rendering paths. It is linked from every editor, and required
codes beside an entry open their explanation in a new tab.

Open [Shiren GB Translation](https://joey-astrologo.github.io/Shiren-GB-Monster-of-Moonlight-Village/)
and choose a subject. The Japanese TSVs and current English translation load automatically.
All 1,424 extracted entries have a primary workbench; 12 additional entries come from
`script/intro.tsv`. The [coverage page](../coverage.html) lists the counts and exceptions.

## Editing

Japanese is on the left; the translation is on the right. Select a group, search by text
or address, and use **Needs attention** to find errors. Each entry displays its actual
renderer contract. The first preview is open; other previews open on request.

- Items include identified and unidentified names. Descriptions, shared help fragments
  and seals are separate because they use different rendering and staging rules.
  Enhancement/counter classes come from native table slots, including placeholders;
  renaming a Staff or Pot cannot remove its runtime suffix checks.
- Menus use their box/row geometry and runtime tile allocation. Item actions are grouped
  by category and shared submenu use, retaining their source-table order.
- Gameplay messages and structured dialogue preserve explicit breaks, controls and
  structural spaces. They do not use the prose wrapper.
- Descriptions permit line breaks to move, retaining page boundaries and control order.
  Their `<cF0:xx>` expansions use the current shared-fragment draft.
- Cinematic text wraps at 152 pixels into the exact occupied slots for each event.
  Use `<br>` for an explicit line break and retain `<page>` transitions.
- The 28 reference entries explain why a TSV-only edit is unavailable: fixed composite
  fields, keyboard mappings/aliases, generated shop text or unconfirmed extraction data.
  Graphics and code-generated text are linked from the coverage page.

The current font contains 77 English glyphs. Other characters require a project font
change. The source byte count is not a general text-length limit.

These workbenches share one local draft and one **Download changes** action. Invalid
edits are saved too, but cannot be exported. Changes that invalidate another entry,
such as a shared fragment that makes an unchanged description too long, block export
and link to the affected entry. A newer draft in another tab triggers recovery instead
of silently overwriting it. Browser storage failure is reported explicitly.

The [prose editor](../prose/README.md) retains its separate draft, automatic wrapping and
TSV format. Its 44 structured references link to the editable Choices workbench.

## Download and project import

The UTF-8 TSV format is `shiren-workbench-edits-v1`. It contains metadata comments for
the catalogue/rules revisions and each edited row's baseline hash, followed by
`key<TAB>english` rows. Extracted entries use `bank:$address`; cinematic entries use
`intro_01`–`intro_12`. Only changed entries are exported, including changes in other
workbenches in the same browser draft. Preserve spaces and metadata when moving the file.

**Import edits** reopens a download in the browser. Unknown keys, duplicate rows, changed
baselines, incompatible rules and conflicts with an existing draft are rejected.
Invalid text from an otherwise compatible TSV can be opened for repair.

In the project, with the normal extraction and Python tool dependencies available:

```sh
# Validate without modifying translation files.
python3 tools/workbench.py import /path/to/shiren-workbench-edits.tsv

# Apply the validated changes.
python3 tools/workbench.py import /path/to/shiren-workbench-edits.tsv --apply
```

The importer independently encodes and measures the merged text using the existing
Python tools, then runs the complete English glossary lint and font audit. Names update
`glossary.tsv`; direct text updates `en.tsv`; structured/condition rows also update
`prose_draft.tsv` with their explicit-layout marker; cinematic edits update only the
English field in `intro.tsv`. The Gitan override retains its required leading separator
in `en.tsv` while its glossary spelling remains unpadded. Writes preserve unrelated rows
and source metadata, with baseline/concurrent-change checks and transactional rollback.

For a coordinated name change that also changes ordinary dialogue, validate and apply
both downloads together:

```sh
python3 tools/workbench.py import /path/to/shiren-workbench-edits.tsv \
  --prose-edits /path/to/shiren-prose-changes.tsv
# Add --apply after reviewing the dry run.
```

Terminology lint applies to the project's English glossary. A different-language project
must update the glossary and its uses together. The importer checks the merged files;
the browser does not claim complete terminology coverage of ordinary prose.

Run the project build and relevant game checks before accepting translation changes.
Browser and importer fit checks do not establish ROM relocation capacity, every runtime
substitution, shared item/action allocation, VBlank timing or visual acceptance. Existing
unknown runtime producers are measured at their minimum contribution and carry a warning;
the settled player-name field reserves all six characters. Release acceptance still uses
the project's release battery.

## Regenerate and verify

```sh
python3 tools/prose_editor.py export
python3 tools/workbench.py export
python3 tools/build_site.py
python3 tools/prose_editor_check.py
python3 tools/workbench_check.py
python3 tools/site_check.py
```

`workbench.py export` writes the catalogue, copies the cinematic TSV and updates the home
links/coverage page. `workbench_check.py` verifies coverage, accepted baselines, importer
routing and rejection cases; it generates `checks-oracle.json` from the actual Python
codec/layout tools. Commit that fixture with the catalogue. `site_check.py` runs Chrome
against a temporary project-subdirectory preview, checks browser/Python agreement and
exercises editing, invalid drafts, TSV import conflicts, recovery and mobile layout.
The test page and fixture are excluded from the Pages artifact.

For an interactive preview, run `python3 tools/prose_editor.py serve` and open
`http://127.0.0.1:8765/`. Browser checks can also be opened at
`http://127.0.0.1:8765/workbench/checks.html`.

Rule sources are indexed in [TEXT_REFERENCE.md](../../docs/TEXT_REFERENCE.md). Changes to
the codec, font, renderer census or allocation oracle invalidate the published rule hash;
the Pages packager refuses a stale catalogue. Unknown extracted entries cannot disappear
from the census simply because they are not editable.
