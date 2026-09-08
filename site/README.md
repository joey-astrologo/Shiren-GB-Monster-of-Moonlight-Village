# Shiren GB Translation

The GitHub Pages website has a home page at `/` and a [prose editor](prose/README.md)
at `/prose/`. Links and assets are relative so both work under a repository Pages path.

Public address: **https://joey-astrologo.github.io/Shiren-GB-Monster-of-Moonlight-Village/**

## Local preview

```sh
python3 tools/prose_editor.py serve
```

Open **http://127.0.0.1:8765/** and choose **Open prose editor**. The editor loads
Japanese from the ignored local extraction automatically. This helper requires the
project's normal Python tool dependencies.

To preview exactly the public artifact, using only Python's standard library:

```sh
python3 tools/build_site.py
python3 -m http.server 8766 --bind 127.0.0.1 --directory build/pages
```

Open **http://127.0.0.1:8766/**. Use **Load Japanese TSV** to provide source text,
just as on the hosted site. No extracted Japanese, ROM, save or test oracle is published.

## GitHub Pages deployment

The [Deploy translation workshop workflow](../.github/workflows/pages.yml) runs on
changes to `site/`, the packaging helper or the workflow on `main`. It can also be run
manually from **Actions → Deploy translation workshop → Run workflow**, selecting
`main`. Pull requests validate the package without deploying.

For the first deployment (or when using a fork):

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment → Source**, select **GitHub Actions**.
3. Push the site changes to `main`, or run the workflow manually.
4. Open the URL shown by the successful `github-pages` deployment.

The workflow checks out the repository, runs `python3 tools/build_site.py`, uploads
`build/pages`, and deploys it with the official GitHub Pages actions. The deploy job
has `pages: write` and `id-token: write`; package validation only needs `contents: read`.
No custom token, npm install, Python packages or ROM extraction is needed in CI.

The packaging helper uses an explicit list of eight public assets plus `.nojekyll`.
It checks page links, catalogue integrity and allowed record fields, then replaces the
generated artifact. Test pages, documentation and all local source files are excluded.
Add new public assets to `PUBLIC_FILES` in `tools/build_site.py` when adding editors.

## Updating the prose catalogue

Pages publishes the checked-in `prose/catalog.json`; it cannot regenerate extraction
on GitHub. After accepting translation or validation-rule changes, regenerate and check
the catalogue locally before committing it:

```sh
python3 tools/prose_editor.py export
python3 tools/prose_editor.py export --check
python3 tools/prose_editor_check.py
python3 tools/build_site.py
```

See the [editor documentation](prose/README.md) for browser checks and TSV import instructions.
