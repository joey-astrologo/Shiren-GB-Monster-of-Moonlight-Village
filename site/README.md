# Shiren GB Translation

The GitHub Pages website has a home page at `/`, a [prose editor](prose/README.md)
at `/prose/`, and [subject workbenches](workbench/README.md) at
`/workbench/?subject=items` (and the other linked subjects). `/coverage.html` accounts
for the whole extracted script plus the separately stored cinematic text. Links and
assets are relative, including browser tests under a repository Pages path.

Public address: **https://joey-astrologo.github.io/Shiren-GB-Monster-of-Moonlight-Village/**

## Local preview

```sh
python3 tools/prose_editor.py serve
```

Open **http://127.0.0.1:8765/** and choose a subject. The editors load
the included Japanese TSVs automatically. This helper requires the
project's normal Python tool dependencies.

To preview exactly the public artifact, using only Python's standard library:

```sh
python3 tools/build_site.py
python3 -m http.server 8766 --bind 127.0.0.1 --directory build/pages
```

Open **http://127.0.0.1:8766/**. Japanese source loads automatically, just as on the
hosted site. **Download source TSV** saves the original file; **Replace source** optionally
loads a matching local extraction. No ROM, save or test oracle is published.

## GitHub Pages deployment

The [Deploy translation workshop workflow](../.github/workflows/pages.yml) runs on
changes to `site/`, translation TSVs, the relevant rule tools or the workflow on `main`. It can also be run
manually from **Actions → Deploy translation workshop → Run workflow**, selecting
`main`. Pull requests validate the package without deploying.

For the first deployment (or when using a fork):

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. Push the site changes to `main`, or run the workflow manually.
4. Open the URL shown by the successful `github-pages` deployment.

The workflow checks out the repository, runs `python3 tools/build_site.py` and
`python3 tools/site_check.py` (using the runner's Chrome), uploads
`build/pages`, and deploys it with the official GitHub Pages actions. The deploy job
has `pages: write` and `id-token: write`; package validation only needs `contents: read`.
No custom token, npm install, third-party Python packages or ROM extraction is needed in CI.

The packaging helper uses an explicit list of 16 public assets plus `.nojekyll`,
including the complete original TSV at `data/script.tsv` and cinematic TSV at
`data/intro.tsv`. It checks page links, catalogue integrity, current rule hashes,
translation baselines, source hashes and exactly-once coverage of all extracted entries.
Missing, duplicate, malformed or mismatched sources and stale snapshots fail the build.
Test pages/fixtures, Markdown documentation and local working files are excluded.
Add new public assets to `PUBLIC_FILES` in `tools/build_site.py` when adding editors.

## Updating the catalogues

Pages publishes the checked-in `prose/catalog.json` and `workbench/catalog.json`; it cannot regenerate extraction
on GitHub. After accepting translation or validation-rule changes, regenerate and check
the catalogue locally before committing it:

```sh
python3 tools/prose_editor.py export
python3 tools/prose_editor.py export --check
python3 tools/workbench.py export
python3 tools/prose_editor_check.py
python3 tools/workbench_check.py
python3 tools/site_check.py --with-prose
python3 tools/build_site.py
```

Commit the generated catalogues, coverage/navigation updates and browser oracle together.
See the [workbench documentation](workbench/README.md) for TSV import instructions.

## Updating the bundled Japanese source

`data/script.tsv` is a tracked snapshot of the full extracted `script/script.tsv`,
including records used by other translation sections. It retains the original TSV
columns and text. CI and visitors do not need to extract a ROM.

After changing the extraction, regenerate both catalogues, then refresh the snapshot:

```sh
python3 tools/prose_editor.py export
python3 tools/workbench.py export
python3 tools/build_site.py --refresh-source
python3 tools/prose_editor_check.py
python3 tools/workbench_check.py
```

The refresh command validates the proposed source against the catalogue before replacing
the snapshot. Commit `site/data/script.tsv` and any catalogue changes together. Ordinary
Pages builds use the tracked snapshot and do not read the ignored local extraction.
