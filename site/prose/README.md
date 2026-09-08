# Prose Studio — proof of concept

A static browser editor for Shiren GB prose. It contains **480 records in 25 event
groups**: 436 ordinary prose drafts are editable, and 44 structured/verbatim records are
read-only reference. Clear-condition and file-menu labels are excluded.

## Open locally

From the repository root:

```sh
python3 tools/prose_editor.py serve
```

Open **http://127.0.0.1:8765/**. The preview binds only to localhost and supplies the
Japanese column from your existing, ignored `script/script.tsv`. It does not accept writes.
If extraction is missing, generate it using the repository's normal extraction command,
or use **Load Japanese TSV** to select a matching extraction in the browser.

The checked-in `catalog.json` contains English drafts, accepted English layouts, event
groups, approved glyph pixels/advances, control contracts and hashes. It contains no
Japanese prose or ROM bytes. A publicly hosted copy asks visitors to load `script.tsv`
locally; no file is uploaded. The Japanese source must match every catalogue record's
hash. Source text stays in memory and must be loaded again on a later visit.

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

## Rules and limits of this proof of concept

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
Inferred speaker labels come from English attribution. Opening/ending cinematics, items,
menus, graphics and glossary editing are outside this first version.

## Regenerate and check

Generation needs the normal Python dependencies and local extraction. Serving the
already generated site needs only Python's standard library plus the repository's
installed tool dependencies for the preview helper; a generic static host needs neither.

```sh
python3 tools/prose_editor.py export
python3 tools/prose_editor.py export --check
python3 tools/prose_editor_check.py
python3 tools/prose_editor.py serve --test
```

Open **http://127.0.0.1:8765/checks.html** for browser differential and interaction checks.
The Python command writes its oracle under ignored `build/`. Tests cover baseline layout,
wrapping, pixel/source boundaries, controls, source integrity, TSV rejection/round trips,
file-input import, downloads, autosave, reload and stale-draft recovery. The browser
harness restores any pre-existing local draft afterward; an isolated browser profile is
recommended for automated runs.

## GitHub Pages

The editor needs only static files and relative URLs. Publish the **contents of this
directory** as a GitHub Pages artifact; no Python, account, API key or server is required
by visitors. Include `index.html`, `style.css`, `app.js`, `rules.js`, `catalog.json` and
`font-license.txt`. The test pages and this README are optional. Keep the Japanese
extraction and `build/` out of the published artifact. This change prepares the site;
it does not enable Pages or publish a deployment.

The font credit is displayed in the UI and its bundled license is in `font-license.txt`.
