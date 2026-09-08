# Prose editor

A static browser editor for Shiren GB prose. It contains **480 records in 25 event
groups**: 436 ordinary prose drafts are editable, and 44 structured/verbatim records are
read-only reference. Clear-condition and file-menu labels are excluded.

## Open locally

From the repository root:

```sh
python3 tools/prose_editor.py serve
```

Open **http://127.0.0.1:8765/** and choose **Open prose editor**, or go directly to
**http://127.0.0.1:8765/prose/**. The preview binds only to localhost. The Japanese
column loads automatically from the included `site/data/script.tsv`, just as on GitHub
Pages. No source-file import is needed on first load or on later visits.

The checked-in `catalog.json` contains English drafts, accepted English layouts, event
groups, approved glyph pixels/advances, control contracts and hashes. The complete
original Japanese TSV is published separately at `site/data/script.tsv`. The packager
and browser verify every prose record's source hash before using it.

**Download source TSV** saves the included original. **Replace source** optionally loads
a matching local extraction without uploading it. If the included file is unavailable
or mismatched, the editor reports the problem and offers **Load source TSV** for recovery.
Local replacements apply to the current visit; the included source loads on the next visit.

## Editing and downloading

- Choose an event or search across dialogue, speakers, addresses and loaded Japanese.
- Edit the right-hand draft. Enter inserts `<br>`; Ctrl/Cmd+Enter inserts `<brk>`.
  The two buttons beneath the field insert the same controls.
- The browser saves edits locally, including drafts with errors. Storage failures are
  reported. Older incompatible drafts are preserved with a recovery download before a
  fresh draft can replace them. Download TSVs as portable backups of validated edits;
  browser storage alone is not a cross-device backup.
- Check the game-font preview, per-line pixels/glyphs, required tokens and messages.
  Each preview shows one box at a time. Shaded spans represent runtime substitutions.
- **Download changes** exports only changed, valid ordinary prose rows. **Import edits**
  resumes a compatible download and rejects conflicting existing edits without merging
  part of the file. **Reset entry** restores that row's original draft after confirmation.

The editor preserves the accepted `en.tsv` layout while a draft is unchanged. On an edit,
it applies the current wrapping rules to that row. This matters because some accepted
line breaks differ from what rerunning today's wrapper across the whole draft would make.

## Use a downloaded TSV in the project

First validate and inspect the proposed diff:

```sh
python3 tools/prose_editor.py import /path/to/shiren-prose-changes.tsv
```

To apply it after review:

```sh
python3 tools/prose_editor.py import /path/to/shiren-prose-changes.tsv --apply
sh build.sh
python3 tools/prose_editor.py export
python3 tools/workbench.py export
python3 tools/workbench_check.py
```

The importer uses the existing **Python** encoder, wrapper, layout validator and complete
English glossary lint. It checks every row before applying anything, then updates only
changed addresses in `script/prose_draft.tsv` and their generated rows in `script/en.tsv`.
It preserves all other rows and comments. It neither builds a ROM nor modifies a glossary.
The normal build and applicable playtest gates still determine whether the result is
ready to use in-game. A new catalogue is generated explicitly after accepted edits.

The file uses the existing `loc<TAB>english` draft data rows, preceded by comment metadata:

```text
# format<TAB>shiren-prose-edits-v1
# revision<TAB>catalogue SHA-256
# rules<TAB>implementation/font SHA-256
# base<TAB>loc<TAB>baseline SHA-256
# loc<TAB>english
loc<TAB>draft text
```

`<TAB>` above means a literal tab. Each changed row has one `base` comment binding its
Japanese source, original draft and accepted English layout. Unrelated catalogue changes
may be merged, but edited-row baseline changes and different rule revisions are rejected.
Duplicate/unknown addresses, malformed fields, structured-row edits and invalid text are
also rejected. The importer handles UTF-8 BOMs and CRLF downloads.

## Rules and limits

`tools/prose_editor.py export` derives the catalogue from the current Python toolchain
and extraction. `rules.js` mirrors prose wrapping, source indents, selector spacing,
bank-11/14 encoding, painted pixel extent, source/buffer limits and close checks. It also
preserves the reviewed significant-token/raw-byte sequence. All 480 accepted layouts and
all 436 editable drafts are checked against independent Python results by the browser suite.

The font currently supports the existing 77 English glyphs. Unsupported characters are
errors; broader language support requires project font/encoding work. English glossary
consistency is checked by the importer, not by a translated Japanese dictionary in the
public website. Unresolved runtime values use the same minimum contribution as the
current toolchain and carry a review warning; `<name>` reserves the full six-character
player-name footprint. A green browser result does not prove every runtime substitution,
gameplay route, allocation or pacing choice.

Event groups and their row order come from the draft's existing headings. They are useful
editing context, not a verified chronological walkthrough or a complete speaker/event map.
Inferred speaker labels come from English attribution. The [other workbenches](../workbench/README.md)
cover items, names, descriptions, menus, gameplay messages, opening cinematic text and
structured choices. The 44 structured records remain references on this prose page and
link to their editable workbench. Graphics and fixed composite fields need project changes.

## Regenerate and check

Catalogue generation needs the normal Python dependencies and local extraction. Serving the
already generated site needs only Python's standard library plus the repository's
installed tool dependencies for the preview helper; a generic static host needs neither.

```sh
python3 tools/prose_editor.py export
python3 tools/prose_editor.py export --check
python3 tools/workbench.py export
python3 tools/prose_editor_check.py
python3 tools/workbench_check.py
python3 tools/prose_editor.py serve --test
```

Open **http://127.0.0.1:8765/prose/checks.html** for browser differential and interaction checks.
The Python command writes its oracle under ignored `build/`. Tests cover baseline layout,
wrapping, pixel/source boundaries, controls, source integrity, TSV rejection/round trips,
automatic source loading, missing/mismatched-source recovery, file-input import, downloads,
autosave, reload and stale-draft recovery. The browser
harness restores any pre-existing local draft afterward; an isolated browser profile is
recommended for automated runs.

## GitHub Pages

The [home page](https://joey-astrologo.github.io/Shiren-GB-Monster-of-Moonlight-Village/)
links to the [prose editor](https://joey-astrologo.github.io/Shiren-GB-Monster-of-Moonlight-Village/prose/).
The [Pages workflow](../../.github/workflows/pages.yml) packages the landing page and
public editor assets in `build/pages`, then deploys on site changes to `main` or a
manual run. Visitors need only a browser; the original Japanese source is included
and loads automatically.

See [website deployment instructions](../README.md) for the initial GitHub Pages
setting, artifact preview and publication details. Test pages and fixtures are excluded
from the public artifact.

The font credit is displayed in the UI and its bundled license is in `font-license.txt`.
