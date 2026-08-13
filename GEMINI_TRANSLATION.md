# Gemini-assisted prose review

## Current project policy and status

Gemini is optional, not the primary bulk translator. A 20-line blind comparison on
2026-08-10 produced 5 direct-translation wins, 3 Gemini wins and 12 ties for native-English
presentation; Gemini also produced candidates that required terminology and control-code
repairs. For speed and insertion safety, the remaining corpus was reviewed directly from
the Japanese. Gemini stays useful as a second opinion on selected lines.

The direct pass reviewed the eligible prose corpus. The synchronized ledger currently has
521 rows: 426 accepted, 8 stale after later source/control-token edits, 2 pending, and 85
excluded byte-exact/layout rows. The 供養/Kuyou place-name wordplay at `11:$5CE2` was
resolved by the project owner as “Kuyo Pass, where the lost find rest.” The excluded rows
received a separate manual semantic/control-layout audit on 2026-08-10, with every edited
row rechecked against the proportional source, pixel and shared-tile limits.

`tools/gemini_prose.py` is a proposal and review layer for the 521 rows in
`script/prose_draft.tsv`. It does not translate menus, labels, item descriptions, the
frozen glossary, or `script/intro.tsv`. Eighty-five byte-exact/layout rows whose draft
starts with `=` are excluded automatically, leaving 436 ordinary story-prose candidates.

Gemini never writes `script/prose_draft.tsv` or `script/en.tsv`. A live request writes a
candidate to the tracked `script/prose_review.json`; a human must review and accept it.
Acceptance re-runs the production wrapper, control-token/glossary checks and measured Dot
layout checks before atomically changing both TSVs. Failed checks roll both files back.

## Security and cost

Never paste a key into source, a commit, an issue, or a screenshot. Google recommends the
`GEMINI_API_KEY` environment variable. For a local repository-only setup, copy the tracked
example and restrict its permissions:

```sh
cp .gemini-credentials.example.json .gemini-credentials.json
chmod 600 .gemini-credentials.json
```

The real file is explicitly gitignored. The environment variable takes precedence over
the file, and the tool never prints the key.

The default model is `gemini-3.5-flash-lite`. On 2026-08-10 this project's AI Studio
dashboard showed a 500-request daily free-tier limit for that model, versus 20 for regular
3.5/3.6 Flash. It and the other models in the tool's allowlist were shown as free-tier
eligible on Google's pricing page that day. That allowlist is a guard against accidentally
selecting a paid-only model, not a billing guarantee. Google controls the project's tier
and can change model eligibility. Use a project with billing disabled if a charge must be
impossible, inspect current quotas in AI Studio, and remember that Google currently says
free-tier content may be used to improve its products.

The tool makes exactly one request per `next` or `batch` command. It does not retry a 429
and never falls back to another model or paid service automatically. `batch` reduces quota
use by returning several independently validated scene entries from that one request.

## Install

The ordinary offline commands use the same Python/Pillow environment as the build. Live
mode additionally needs Google's SDK. A self-contained local environment is:

```sh
python3 -m venv .venv-gemini
.venv-gemini/bin/python -m pip install -r requirements-gemini.txt
```

`.venv-gemini/` is gitignored. Python 3.11 or newer is recommended; the macOS Command Line
Tools Python 3.9 still works through the SDK's official `generateContent` surface, but its
dependencies warn that Python 3.9 and the bundled LibreSSL are old.

## Workflow

Extract the Japanese script first, then initialize or synchronize the review database:

```sh
python3 tools/extract.py build/base.gb
python3 tools/gemini_prose.py init
python3 tools/gemini_prose.py status
```

Inspect the exact prompt without credentials or a network request:

```sh
python3 tools/gemini_prose.py next --dry-run
```

Generate one candidate, either the next pending entry or a chosen location:

```sh
.venv-gemini/bin/python tools/gemini_prose.py next
.venv-gemini/bin/python tools/gemini_prose.py next --loc '14:$4C0F'
```

Quote a `loc` in the shell: an unquoted `$4C0F` can be expanded as a shell variable.

For the bulk pass, generate up to eight pending rows from one authored scene in a single
request. The command stops at the next section heading even when fewer rows were selected:

```sh
.venv-gemini/bin/python tools/gemini_prose.py batch
.venv-gemini/bin/python tools/gemini_prose.py batch --count 12 --loc '14:$5281'
```

The accepted range is 2–20. A malformed response, duplicate/missing location, or reordered
location rejects the entire response before review state changes. Once the response shape
is sound, each translation receives its own local control, glossary, codec, wrapping and
pixel-fit result; one bad entry therefore cannot hide behind valid neighbors.

Review interactively:

```sh
python3 tools/gemini_prose.py review --loc '14:$4C0F'
```

The choices are accept, edit, reject, defer for a user decision, skip, or quit. An edit is
stored and must be reviewed again before acceptance. Use `--needs-user --note 'question'`
for a genuinely ambiguous decision rather than guessing. For an automation-friendly
approval after a human has inspected the candidate:

```sh
python3 tools/gemini_prose.py review --loc '14:$4C0F' --accept
```

If the existing hand-written prose is already approved, mark it verified and skip Gemini
entirely:

```sh
python3 tools/gemini_prose.py verify-current --loc '14:$4C0F' \
        --note 'Reviewed in emulator by Joey'
```

For a direct translation pass, edit `script/prose_draft.tsv`, run `wrap_en.py --apply` and
the standing checks, then use `verify-current` with a note identifying the direct review.
Do not mark a genuinely unresolved row verified: add its stable location and question to
`script/prose_uncertainties.tsv` instead.

Never use `--no-checks` in translation work; it exists only so unit tests can exercise an
acceptance update without launching whole-corpus subprocesses.

After a scene or bulk pass, generate an ignored TSV containing only rejected, mechanically
failed, and user-decision rows:

```sh
python3 tools/gemini_prose.py triage
```

The default output is `build/prose_triage.tsv`. It combines the generated Japanese source,
current English, candidate, ambiguity notes, validation failures and the reviewer's reason.
It stays under ignored `build/` because extracted Japanese game text must not be committed.

## What is sent

One single-row request contains:

- the target Japanese and stable `loc`;
- up to two neighboring Japanese rows on each side within the same authored scene;
- neighboring English only after those rows are human-verified;
- mandatory control tokens and raw argument bytes;
- the byte-significant control order and inseparable `mode1`/`cE3` argument sequences;
- the existing count of authored `<brk>` page breaks;
- matching established gameplay-glossary entries and source-backed
  `script/prose_terms.tsv` entries;
- the established short speaker tag where one applies.

A batch request contains the same contract independently for every target, plus Japanese
scene context around the group. It excludes every target's existing English and requires
one result per stable `loc` in input order. Verified neighboring English may be supplied as
continuity context.

The target's existing English is deliberately not sent, avoiding a paraphrase anchored on
the old wording. Existing patch wording is never evidence that a new story term is canon.
Japanese honorific suffixes are not retained; relevant relationship or tone is expressed
through natural English instead.
New binding entries in `script/prose_terms.tsv` require an approved authority, source, and
reason: an official English term matched through a Shiren wiki (`official-wiki`), a term
from the Shiren 2 N64 fan translation (`shiren2-n64-fan`), or an explicit project-local
wording decision by Joey (`project-owner`). External authorities require a traceable HTTPS
URL. Project-owner decisions use `conversation:YYYY-MM-DD`; they are canon for this patch
without being presented as official terminology.

`script/glossary.tsv` is still supplied as the project's gameplay-name consistency list;
that keeps item, monster and NPC references aligned with the rest of this patch. It should
not be read as provenance that every one of those 391 project decisions is an official
English name.

The tracked review file stores source/current hashes so an extraction or manual prose edit
invalidates stale approvals. It does not duplicate the extracted target Japanese text.

## Validation and states

Gemini returns schema-constrained JSON containing a translation, ambiguities and a short
note. The local validator remains authoritative. It rejects:

- malformed structured output or multi-line TSV values;
- missing/extra semantic controls, raw bytes, or `<brk>` markers;
- reordered controls or text inserted inside an inseparable runtime argument sequence;
- model-authored `<end>` layout, or added/removed/reordered `<br>` controls (the hybrid
  sign-and-dialogue row `14:$4905` must preserve its two source-required content breaks);
- an authored `<brk>` placed at the end, which would create an empty final page;
- loss of the position-sensitive leading `<cEC:xx>` token;
- unsupported game characters;
- established gameplay-glossary or source-backed story-term drift;
- a word/control sequence that cannot fit 30 staged glyphs and 144 painted pixels.

Valid prose is wrapped with the production `wrap_en.py` policy. Automatic extra boxes are
reported as pacing notes rather than silently treated as semantic failures.

Review states are `pending`, `candidate`, `fit_failed`, `accepted`, `rejected`,
`needs_user`, `skipped`, `stale`, and `excluded`. Only a successful human acceptance sets
`verified: true`; `next` skips verified entries. Re-run `init` after changing the Japanese
extraction or prose TSV to mark affected entries stale.

## Tests

The regression suite uses a fake client and never reads credentials or reaches the network:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/test_gemini_prose.py -v
```

After accepting prose, also run the standing full build and emulator checks described in
`README.md` and `TRANSLATING.md`.
