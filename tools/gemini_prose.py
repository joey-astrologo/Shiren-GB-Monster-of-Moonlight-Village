#!/usr/bin/env python3
"""Human-reviewed Gemini translation queue for Shiren GB story prose.

Gemini never writes the production TSVs. ``next`` stores a structured candidate in
``script/prose_review.json``; ``review`` validates it with the same codec, glossary,
wrapper and Dot geometry used by the build, then a human may accept it. Acceptance is an
atomic update of ``prose_draft.tsv`` and its generated ``en.tsv`` row, followed by the
standing fast semantic/layout checks.

The Japanese source remains in the generated, gitignored ``script/script.json``. The
tracked review file stores hashes rather than duplicating extracted game text.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

# This repo has ``tools/dis.py``. When this file is run as a script, ``tools`` is first on
# sys.path; Pillow -> typing_extensions -> inspect can then import that ROM disassembler
# as Python's stdlib ``dis`` and fail on ``COMPILER_FLAG_NAMES``. Preload stdlib inspect
# (and therefore stdlib dis) with the tools directory temporarily absent.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_original_path = list(sys.path)
sys.path[:] = [path for path in sys.path
               if os.path.abspath(path or os.curdir) != TOOLS_DIR]
import inspect as _stdlib_inspect                              # noqa: E402,F401
sys.path[:] = _original_path
sys.path.insert(0, TOOLS_DIR)
import build as build_tool                                      # noqa: E402
import codec                                                   # noqa: E402
import dialogue_preview as dialogue                            # noqa: E402
import dotfont                                                 # noqa: E402
import lint_en                                                 # noqa: E402
import wrap_en                                                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROSE_PATH = os.path.join(ROOT, 'script/prose_draft.tsv')
EN_PATH = os.path.join(ROOT, 'script/en.tsv')
SCRIPT_PATH = os.path.join(ROOT, 'script/script.json')
GLOSSARY_PATH = os.path.join(ROOT, 'script/glossary.tsv')
GLOSSARY_OK_PATH = os.path.join(ROOT, 'script/glossary_ok.tsv')
PROSE_TERMS_PATH = os.path.join(ROOT, 'script/prose_terms.tsv')
REVIEW_PATH = os.path.join(ROOT, 'script/prose_review.json')
CREDENTIALS_PATH = os.path.join(ROOT, '.gemini-credentials.json')

# New story terminology is binding only when it can be traced to one of the sources
# approved for this project. The existing gameplay glossary remains a consistency rule;
# this allowlist governs additions made specifically for Gemini prose review.
PROSE_TERM_AUTHORITIES = frozenset([
    'official-wiki',
    'project-owner',
    'shiren2-n64-fan',
])

SCHEMA_VERSION = 1
PROMPT_VERSION = 'prose-v5-batch'
DEFAULT_MODEL = 'gemini-3.5-flash-lite'
DEFAULT_BATCH_SIZE = 8
MAX_BATCH_SIZE = 20

# Verified against Google's public pricing page on 2026-08-10. This is a guard against
# accidentally naming a paid-only model, not a billing guarantee: tier eligibility and
# the project's billing state are controlled by Google and can change.
FREE_TIER_MODELS = frozenset([
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
])

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'translation': {
            'type': 'string',
            'description': 'Natural native English translation in prose-draft format.',
        },
        'ambiguities': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'Genuine ambiguities a human reviewer should resolve.',
        },
        'translator_notes': {
            'type': 'string',
            'description': 'Brief rationale only when it helps review.',
        },
    },
    'required': ['translation', 'ambiguities', 'translator_notes'],
    'additionalProperties': False,
}

BATCH_ITEM_SCHEMA = {
    'type': 'object',
    'properties': {
        'loc': {
            'type': 'string',
            'description': 'The exact stable loc supplied for this target.',
        },
        **RESPONSE_SCHEMA['properties'],
    },
    'required': ['loc', 'translation', 'ambiguities', 'translator_notes'],
    'additionalProperties': False,
}

BATCH_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'translations': {
            'type': 'array',
            'items': BATCH_ITEM_SCHEMA,
            'description': 'One independently reviewable result per input target.',
        },
    },
    'required': ['translations'],
    'additionalProperties': False,
}

SMART_ASCII = str.maketrans({
    '\u2018': "'", '\u2019': "'", '\u201c': "'", '\u201d': "'",
    '\u2013': '-', '\u2014': '-', '\u2026': '...', '\u00a0': ' ',
})


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def atomic_write(path, text):
    """Replace ``path`` without exposing a half-written review or TSV file."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix='.%s-' % os.path.basename(path), dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def normalized_section(comment):
    text = comment.lstrip('#').strip().strip('=- ').strip()
    if not text or text.startswith('SESSION '):
        return None
    if re.match(r'^bank (?:11|14)\b', text, re.I):
        return text
    return None


def load_prose(path=PROSE_PATH):
    """Return ordered prose rows while retaining the nearest authored section heading."""
    rows, seen = [], set()
    section = 'unsectioned prose'
    with open(path, encoding='utf-8') as source_file:
        for line_no, raw in enumerate(source_file, 1):
            line = raw.rstrip('\n')
            if line.lstrip().startswith('#'):
                heading = normalized_section(line)
                if heading:
                    section = heading
                continue
            if not line.strip():
                continue
            if '\t' not in line:
                raise ValueError('%s:%d: expected loc<TAB>english' % (path, line_no))
            loc, text = line.split('\t', 1)
            loc, text = loc.strip(), text.strip()
            if loc in seen:
                raise ValueError('%s:%d: duplicate loc %s' % (path, line_no, loc))
            seen.add(loc)
            verbatim = text.startswith(wrap_en.VERBATIM)
            rows.append({
                'loc': loc,
                'text': text[1:] if verbatim else text,
                'raw_text': text,
                'verbatim': verbatim,
                'section': section,
                'line': line_no,
            })
    return rows


def load_script(path=SCRIPT_PATH):
    if not os.path.exists(path):
        raise SystemExit('%s is absent; extract the base ROM before using this tool' % path)
    with open(path, encoding='utf-8') as source_file:
        strings = json.load(source_file)['strings']
    return {r['loc']: r for r in strings}


def classify(row):
    if row['verbatim']:
        return False, 'verbatim layout/menu row'
    section = row['section'].lower()
    if 'record / password labels' in section or "log menu's one missing label" in section:
        return False, 'label section'
    return True, None


def fresh_entry(row, source):
    eligible, why = classify(row)
    return {
        'section': row['section'],
        'eligible': eligible,
        'skip_reason': why,
        'verified': False,
        'state': 'pending' if eligible else 'excluded',
        'source_sha256': sha256_text(source['jp']),
        'current_en_sha256': sha256_text(row['raw_text']),
        'candidate_en': None,
        'ambiguities': [],
        'translator_notes': '',
        'provenance': None,
        'checks': None,
        'review_notes': '',
    }


def load_review(path=REVIEW_PATH):
    if not os.path.exists(path):
        return {'schema_version': SCHEMA_VERSION, 'prompt_version': PROMPT_VERSION,
                'entries': {}}
    with open(path, encoding='utf-8') as source_file:
        state = json.load(source_file)
    if state.get('schema_version') != SCHEMA_VERSION:
        raise SystemExit('%s has schema %r; expected %d' %
                         (path, state.get('schema_version'), SCHEMA_VERSION))
    if not isinstance(state.get('entries'), dict):
        raise SystemExit('%s has no entries object' % path)
    return state


def save_review(state, path=REVIEW_PATH):
    state['schema_version'] = SCHEMA_VERSION
    state['prompt_version'] = PROMPT_VERSION
    state['updated_at'] = utc_now()
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + '\n')


def sync_review(rows, by_loc, state):
    """Merge source/draft changes without destroying candidates or review history."""
    old_entries = state.get('entries', {})
    entries = {}
    validator = CandidateValidator(by_loc)
    for row in rows:
        loc = row['loc']
        if loc not in by_loc:
            raise SystemExit('%s from prose draft is absent from script.json' % loc)
        source = by_loc[loc]
        new_source_hash = sha256_text(source['jp'])
        new_en_hash = sha256_text(row['raw_text'])
        entry = dict(old_entries.get(loc) or fresh_entry(row, source))
        eligible, why = classify(row)
        changed = (entry.get('source_sha256') != new_source_hash or
                   entry.get('current_en_sha256') != new_en_hash)
        entry.update({
            'section': row['section'],
            'eligible': eligible,
            'skip_reason': why,
            'source_sha256': new_source_hash,
            'current_en_sha256': new_en_hash,
        })
        if not eligible:
            entry['verified'] = False
            entry['state'] = 'excluded'
        elif changed:
            entry['verified'] = False
            entry['state'] = 'stale' if entry.get('candidate_en') else 'pending'
            checks = dict(entry.get('checks') or {})
            checks['stale'] = 'Japanese source or current prose changed after this state was recorded'
            entry['checks'] = checks
        elif entry.get('state') == 'excluded':
            entry['state'] = 'pending'
        # A verified wording remains a human decision even when the approved font or
        # wrapper changes.  Keep its stored fit snapshot synchronized with the current
        # validator so the review queue does not claim obsolete line breaks.
        if entry.get('verified'):
            current = validator.validate(row, row['text'])
            entry['checks'] = current
            if not current['valid']:
                entry['verified'] = False
                entry['state'] = 'stale'
        entries[loc] = entry
    state['entries'] = entries
    state['source_file'] = 'script/prose_draft.tsv'
    state['source_count'] = len(rows)
    return state


def init_state(review_path=REVIEW_PATH):
    rows = load_prose()
    by_loc = load_script()
    state = load_review(review_path)
    before = json.dumps({key: value for key, value in state.items() if key != 'updated_at'},
                        ensure_ascii=False, sort_keys=True)
    state = sync_review(rows, by_loc, state)
    after = json.dumps({key: value for key, value in state.items() if key != 'updated_at'},
                       ensure_ascii=False, sort_keys=True)
    if not os.path.exists(review_path) or before != after:
        save_review(state, review_path)
    return rows, by_loc, state


def token_counter(text, raw=False):
    out = collections.Counter()
    for match in codec.TOKEN_RE.finditer(text):
        tok = match.group(1)
        if tok.startswith('$') == raw:
            out['<%s>' % tok] += 1
    return out


def ordered_control_tokens(text):
    """Return non-layout controls in byte-significant order, including raw bytes."""
    out = []
    for match in codec.TOKEN_RE.finditer(text):
        token = match.group(1)
        if token.split(':', 1)[0] in ('br', 'brk', 'end'):
            continue
        out.append('<%s>' % token)
    return out


def protected_argument_sequences(text):
    """Return controls whose following byte/unit is an inseparable runtime argument.

    Banks 11/14 stage ``mode1`` and ``cE3`` with the next encoded unit serving as an
    argument even though the canonical codec deliberately exposes that unit separately.
    A model must therefore neither translate it nor insert a space or text between it and
    the control. See TRANSLATING.md section 7.
    """
    out = []
    for match in codec.TOKEN_RE.finditer(text):
        if match.group(1).split(':', 1)[0] not in ('mode1', 'cE3'):
            continue
        at = match.end()
        if at >= len(text):
            out.append(match.group(0) + '<missing>')
            continue
        following = codec.TOKEN_RE.match(text, at)
        unit = following.group(0) if following else text[at]
        out.append(match.group(0) + unit)
    return out


def format_counter(counter):
    return [token if count == 1 else '%s x%d' % (token, count)
            for token, count in sorted(counter.items())]


def terms_in(source_jp, terms):
    """The same longest-first masking as lint_en, returned as prompt constraints."""
    found, mask = [], [False] * len(source_jp)
    for jp, en in terms:
        start = 0
        while True:
            at = source_jp.find(jp, start)
            if at < 0:
                break
            start = at + 1
            if any(mask[at:at + len(jp)]):
                continue
            for i in range(at, at + len(jp)):
                mask[i] = True
            found.append({'japanese': jp, 'english': en})
    return found


def load_prose_terms(path=PROSE_TERMS_PATH):
    """Load source-backed story terms that have no standalone glossary string/loc."""
    if not os.path.exists(path):
        return []
    terms = []
    with open(path, encoding='utf-8') as source_file:
        for line_no, raw in enumerate(source_file, 1):
            line = raw.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) != 5 or not all(part.strip() for part in parts):
                raise ValueError(
                    '%s:%d: expected japanese<TAB>english<TAB>authority<TAB>source<TAB>reason' %
                    (path, line_no))
            authority, source = parts[2].strip(), parts[3].strip()
            if authority not in PROSE_TERM_AUTHORITIES:
                raise ValueError('%s:%d: unsupported authority %r (expected one of %s)' %
                                 (path, line_no, authority,
                                  ', '.join(sorted(PROSE_TERM_AUTHORITIES))))
            if authority == 'project-owner':
                if not re.match(r'^conversation:\d{4}-\d{2}-\d{2}$', source):
                    raise ValueError(
                        '%s:%d: project-owner source must be conversation:YYYY-MM-DD' %
                        (path, line_no))
            elif not source.startswith('https://'):
                raise ValueError('%s:%d: source must be a traceable https URL' %
                                 (path, line_no))
            terms.append((parts[0].strip(), parts[1].strip()))
    return sorted(terms, key=lambda pair: -len(pair[0]))


def translation_terms(glossary=None):
    """Combine the game-name consistency list and sourced prose canon."""
    glossary = lint_en.load_glossary(GLOSSARY_PATH) if glossary is None else glossary
    terms = lint_en.terms_for_search(glossary)
    # A prose term may deliberately refine a shorter glossary term. Deduplicate exact
    # Japanese keys with prose_terms taking precedence, then restore longest-first order.
    merged = {}
    for jp, en in terms:
        merged[jp] = en
    for jp, en in load_prose_terms():
        merged[jp] = en
    return sorted(merged.items(), key=lambda pair: -len(pair[0]))


def required_speaker_prefix(row, source, glossary=None):
    """Return the canonical dialogue prefix, including short names skipped by term lint."""
    head_jp = re.sub(r'^(?:<[^>]*>)*', '', source['jp'])
    if '「' not in head_jp:
        return ''
    for jp, en in lint_en.ATTRIBUTION.items():
        if head_jp.startswith(jp):
            return en + ':'
    glossary = lint_en.load_glossary(GLOSSARY_PATH) if glossary is None else glossary
    for item in sorted((item for item in glossary if item['cls'] == 'npc'),
                       key=lambda item: -len(item['jp'])):
        if head_jp.startswith(item['jp']):
            return item['en'] + ':'
    # Some authored attributions vary slightly from the fixed NPC table (for example the
    # Old Seer's オババ/ババ spelling). Reuse only the established prefix, never the old
    # sentence, so the model is not anchored to the existing prose.
    head_en = re.sub(r'^(?:<[^>]*>)*', '', row['text'])
    match = re.match(r"([A-Za-z][A-Za-z ']+):(?: |$)", head_en)
    return match.group(1) + ':' if match else ''


def context_item(row, by_loc, state):
    item = {'loc': row['loc'], 'japanese': by_loc[row['loc']]['jp']}
    review = state['entries'].get(row['loc'], {})
    if review.get('verified'):
        item['approved_english'] = row['text']
    return item


def target_payload(row, source, terms):
    significant = collections.Counter(
        {'<%s>' % token: count for token, count in lint_en.significant(source['jp']).items()})
    raw_tokens = token_counter(row['text'], raw=True)
    required_prefix = required_speaker_prefix(row, source)
    return {
        'loc': row['loc'],
        'section': row['section'],
        'japanese': source['jp'],
        'required_semantic_tokens': format_counter(significant),
        'required_raw_control_bytes': format_counter(raw_tokens),
        'required_control_order': ordered_control_tokens(row['text']),
        'inseparable_control_arguments': protected_argument_sequences(row['text']),
        'required_authored_brk_count': row['text'].count('<brk>'),
        'glossary_constraints': terms_in(source['jp'], terms),
        'required_english_prefix': required_prefix,
    }


PRODUCTION_RULES = """Production rules:
- Return sentence-form prose, not manually wrapped screen lines.
- Never emit <br> or <end>; the project's measured wrapper owns those.
- Japanese <br>/<end> tokens are source layout only. Do not copy or convert them. Emit only
  the exact requested number of authored <brk> tokens, even when Japanese has more breaks.
- Emit exactly the requested number of authored <brk> page breaks at natural boundaries.
- Preserve every required semantic token and raw control byte exactly, including counts.
- Emit no raw <$XX> byte unless it appears in required_raw_control_bytes. Translate an
  unlisted Japanese button/direction glyph into ordinary English such as D-Pad.
- Keep required controls in the supplied order. Copy every inseparable control/argument
  pair exactly; never interpret the argument as speech or insert text/space inside it.
- Use the supplied glossary spellings and speaker tags exactly.
- When required_english_prefix is nonempty, the translation's very first characters MUST
  be that exact prefix. It is required output text, not merely metadata or a note.
- When a speaker tag is supplied, Japanese dialogue brackets are delimiters; do not add
  English quotation marks around that character's speech.
- Do not retain Japanese honorific suffixes such as -san, -chan, -sama, or -kun. Convey
  familiarity, respect, or affection through natural English wording when it matters.
- The available text characters are A-Z, a-z, 0-9, space, and: ! ' ( ) + , - . / : ? [ ] ~
- Prefer clear native English over literal Japanese syntax. Do not shorten merely to
  guess at screen width; deterministic project tools perform the actual fit check.
- Return JSON matching the supplied response schema. Keep notes brief."""


def prompt_for(row, source, rows, by_loc, state, terms, context_size=2):
    idx = next(i for i, candidate in enumerate(rows) if candidate['loc'] == row['loc'])
    context = []
    lo, hi = max(0, idx - context_size), min(len(rows), idx + context_size + 1)
    for other in rows[lo:hi]:
        if other['loc'] == row['loc'] or other['section'] != row['section']:
            continue
        context.append(context_item(other, by_loc, state))

    payload = {
        'target': target_payload(row, source, terms),
        'surrounding_context': context,
    }
    return """You are translating Japanese story dialogue from Shiren the Wanderer GB.

Translate only TARGET into fluent, idiomatic English that reads naturally to a native
speaker. Preserve meaning, characterization, register, jokes and uncertainty. Do not
summarize, embellish, censor, or imitate the wording of a previous English translation.

%s

TRANSLATION INPUT (JSON):
%s
""" % (PRODUCTION_RULES, json.dumps(payload, ensure_ascii=False, indent=2))


def prompt_for_batch(target_rows, rows, by_loc, state, terms, context_size=2):
    """Build one coherent-scene prompt while retaining independent row contracts."""
    if not target_rows:
        raise ValueError('batch prompt needs at least one target')
    sections = {row['section'] for row in target_rows}
    if len(sections) != 1:
        raise ValueError('batch targets must share one authored section')
    indices = [next(i for i, candidate in enumerate(rows)
                    if candidate['loc'] == row['loc']) for row in target_rows]
    target_locs = {row['loc'] for row in target_rows}
    lo = max(0, min(indices) - context_size)
    hi = min(len(rows), max(indices) + context_size + 1)
    context = [context_item(other, by_loc, state) for other in rows[lo:hi]
               if other['loc'] not in target_locs and other['section'] in sections]
    payload = {
        'section': target_rows[0]['section'],
        'targets': [target_payload(row, by_loc[row['loc']], terms)
                    for row in target_rows],
        'surrounding_context': context,
    }
    return """You are translating one coherent scene from Shiren the Wanderer GB.

Translate every TARGET independently into fluent, idiomatic English that reads naturally
to a native speaker. Use the other targets and SURROUNDING CONTEXT for continuity, voice,
and pronoun resolution. Preserve meaning, characterization, register, jokes and
uncertainty. Do not summarize, merge entries, embellish, censor, or imitate the wording of
a previous English translation. Return each exact loc once, in the supplied target order.

%s

TRANSLATION INPUT (JSON):
%s
""" % (PRODUCTION_RULES, json.dumps(payload, ensure_ascii=False, indent=2))


def normalize_candidate(text):
    if not isinstance(text, str):
        raise ValueError('translation must be a string')
    if '\n' in text or '\r' in text:
        raise ValueError('translation must be one TSV-safe line, not contain newlines')
    out = text.translate(SMART_ASCII).strip()
    out = re.sub(r'[ \t]+', ' ', out)
    return out


class CandidateValidator:
    """Apply the production prose contract without modifying either canonical TSV."""

    def __init__(self, by_loc=None, en_path=EN_PATH):
        self.by_loc = by_loc or load_script()
        self.trans = lint_en.load_en(en_path)
        self.gloss = lint_en.load_glossary(GLOSSARY_PATH)
        self.terms = translation_terms(self.gloss)
        self.gloss_ok = lint_en.load_glossary_ok(GLOSSARY_OK_PATH)
        self.frozen = {g['loc'] for g in self.gloss}
        self.font = dotfont.load_approved()
        cf0_cells, cf0_text = dialogue.cf0_from_trans(self.trans, build_tool.encode_en)
        cf0_data = {}
        for index, value in cf0_text.items():
            try:
                cf0_data[index] = build_tool.encode_en(value, 11)
            except ValueError:
                pass
        self.cf0_cells = cf0_cells
        self.help_pixels = dialogue.dot_help_widths(self.font, cf0_data)
        self.composer_pixels = dialogue.dot_floor_widths(self.font)

    def validate(self, row, candidate):
        problems, notes = [], []
        source = self.by_loc[row['loc']]
        try:
            normalized = normalize_candidate(candidate)
        except ValueError as exc:
            return {'valid': False, 'candidate_en': candidate, 'wrapped_en': None,
                    'problems': [{'kind': 'format', 'detail': str(exc)}], 'notes': []}
        if normalized != candidate:
            notes.append({'kind': 'ascii_normalized',
                          'detail': 'typographic punctuation/spacing was normalized'})
        if not normalized:
            problems.append({'kind': 'empty', 'detail': 'candidate is empty'})
        if row['verbatim']:
            problems.append({'kind': 'excluded', 'detail': 'verbatim layout rows are not prose'})
        # Ordinary drafts do not author wrapping, but one hybrid story record begins with
        # a three-line sign inscription before continuing into prose. Preserve exactly
        # the source-required content line breaks already present on that row; never let
        # a candidate add, remove, or move them. Control-order validation below provides
        # the second half of that contract.
        want_br, got_br = row['text'].count('<br>'), normalized.count('<br>')
        if '<end>' in normalized or want_br != got_br:
            problems.append({'kind': 'authored_layout',
                             'detail': 'expected %d source-required <br> and no <end>; got %d '
                                       '<br>' % (want_br, got_br)})
        want_brk, got_brk = row['text'].count('<brk>'), normalized.count('<brk>')
        if want_brk != got_brk:
            problems.append({'kind': 'brk_count',
                             'detail': 'expected %d authored <brk>, got %d' %
                                       (want_brk, got_brk)})
        if normalized.endswith('<brk>'):
            problems.append({'kind': 'trailing_brk',
                             'detail': 'an authored page break cannot end prose with an '
                                       'empty final page'})
        want_semantic = lint_en.significant(source['jp'])
        got_semantic = lint_en.significant(normalized)
        for token in sorted(set(want_semantic) | set(got_semantic)):
            expected, actual = want_semantic[token], got_semantic[token]
            if expected == actual:
                continue
            problems.append({
                'kind': 'token_lost' if actual < expected else 'token_added',
                'detail': '<%s> appears %d time(s) in Japanese, %d in the candidate' %
                          (token, expected, actual),
            })
        want_raw, got_raw = token_counter(row['text'], raw=True), token_counter(normalized, raw=True)
        if want_raw != got_raw:
            problems.append({'kind': 'raw_token_parity',
                             'detail': 'expected %s, got %s' %
                                       (format_counter(want_raw), format_counter(got_raw))})
        want_order = ordered_control_tokens(row['text'])
        got_order = ordered_control_tokens(normalized)
        if want_order != got_order:
            problems.append({'kind': 'control_order',
                             'detail': 'expected controls in order %s, got %s' %
                                       (want_order, got_order)})
        want_arguments = protected_argument_sequences(row['text'])
        got_arguments = protected_argument_sequences(normalized)
        if want_arguments != got_arguments:
            problems.append({'kind': 'control_argument',
                             'detail': 'runtime argument sequences must remain inseparable; '
                                       'expected %s, got %s' %
                                       (want_arguments, got_arguments)})
        jp_head = re.match(r'^(<cEC:[^>]+>)', source['jp'])
        if jp_head and not normalized.startswith(jp_head.group(1)):
            problems.append({'kind': 'ec_prefix_lost',
                             'detail': '%s must remain the first token' % jp_head.group(1)})
        speaker_prefix = required_speaker_prefix(row, source, self.gloss)
        candidate_head = re.sub(r'^(?:<[^>]*>)*', '', normalized)
        if speaker_prefix and not candidate_head.startswith(speaker_prefix):
            problems.append({'kind': 'speaker_prefix',
                             'detail': 'dialogue must begin with %s' % speaker_prefix})
        if problems:
            return {'valid': False, 'candidate_en': normalized, 'wrapped_en': None,
                    'problems': problems, 'notes': notes}

        width, per_box, _buffer = dialogue.geometry_for(source)
        help_ = dialogue.is_help(source)
        widths = dialogue.help_widths(cf0=self.cf0_cells) if help_ else dialogue.floor_widths()
        pixel_widths = self.help_pixels if help_ else self.composer_pixels

        def measure(value):
            data = build_tool.encode_en(value, source['bank'])
            return dialogue.dot_metrics(data, self.font, source['bank'], pixel_widths)[:2]

        terminal = re.search(r'<end>((?:<[^>]+>)*)$', source['jp'])
        terminal_end = terminal.group(1) if terminal and terminal.group(1) else ''
        try:
            wrapped, wrap_notes = wrap_en.wrap(
                normalized, width, per_box, widths, True, terminal_end,
                measure=measure, pixel_limit=dialogue.LINE_PX)
        except (ValueError, KeyError) as exc:
            problems.append({'kind': 'wrap', 'detail': str(exc)})
            return {'valid': False, 'candidate_en': normalized, 'wrapped_en': None,
                    'problems': problems, 'notes': notes}
        for kind, detail in wrap_notes:
            target = problems if kind == 'unwrappable' else notes
            target.append({'kind': kind, 'detail': detail})

        try:
            build_tool.encode_en(wrapped, source['bank'])
        except ValueError as exc:
            problems.append({'kind': 'encode', 'detail': str(exc)})
        for kind, detail in lint_en.check_one(source['jp'], wrapped, source['bank']):
            problems.append({'kind': kind, 'detail': detail})
        if row['loc'] not in self.frozen:
            allowed = {term for loc, term in self.gloss_ok if loc == row['loc']}
            allowed |= lint_en.attribution_terms(source['jp'], wrapped)
            for kind, detail in lint_en.check_terms(source['jp'], wrapped, self.terms, allowed):
                problems.append({'kind': kind, 'detail': detail})
        return {'valid': not problems, 'candidate_en': normalized, 'wrapped_en': wrapped,
                'problems': problems, 'notes': notes}


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('Gemini response must be a JSON object')
    if set(payload) != {'translation', 'ambiguities', 'translator_notes'}:
        raise ValueError('Gemini response has missing or extra fields')
    if not isinstance(payload['translation'], str):
        raise ValueError('translation must be a string')
    if (not isinstance(payload['ambiguities'], list) or
            any(not isinstance(v, str) for v in payload['ambiguities'])):
        raise ValueError('ambiguities must be an array of strings')
    if not isinstance(payload['translator_notes'], str):
        raise ValueError('translator_notes must be a string')
    return payload


def validate_batch_payload(payload, expected_locs):
    if not isinstance(payload, dict) or set(payload) != {'translations'}:
        raise ValueError('Gemini batch response must contain only translations')
    translations = payload['translations']
    if not isinstance(translations, list):
        raise ValueError('Gemini batch translations must be an array')
    expected_locs = list(expected_locs)
    actual_locs = []
    for item in translations:
        if not isinstance(item, dict) or set(item) != {
                'loc', 'translation', 'ambiguities', 'translator_notes'}:
            raise ValueError('Gemini batch item has missing or extra fields')
        loc = item.get('loc')
        if not isinstance(loc, str):
            raise ValueError('Gemini batch item loc must be a string')
        validate_payload({key: item[key] for key in
                          ('translation', 'ambiguities', 'translator_notes')})
        actual_locs.append(loc)
    if actual_locs != expected_locs:
        raise ValueError('Gemini batch locs must exactly match input order; expected %s, got %s' %
                         (expected_locs, actual_locs))
    return translations


def credentials(path=CREDENTIALS_PATH):
    # Match the official SDK's precedence when both variables exist.
    key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if key:
        return key.strip(), 'environment'
    if not os.path.exists(path):
        raise SystemExit('no Gemini key: set GEMINI_API_KEY or copy '
                         '.gemini-credentials.example.json to .gemini-credentials.json')
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        print('WARNING: %s is readable by group/others; chmod 600 is recommended' % path,
              file=sys.stderr)
    with open(path, encoding='utf-8') as source_file:
        data = json.load(source_file)
    key = data.get('api_key') if isinstance(data, dict) else None
    if not isinstance(key, str) or not key.strip() or 'PASTE_' in key:
        raise SystemExit('%s does not contain a usable api_key' % path)
    return key.strip(), path


class GeminiClient:
    def __init__(self, api_key):
        try:
            from google import genai
        except ImportError:
            raise SystemExit('live mode needs google-genai; install requirements-gemini.txt')
        self.client = genai.Client(api_key=api_key)

    def generate(self, model, prompt, response_schema=RESPONSE_SCHEMA):
        try:
            # New SDKs expose Google's Interactions API; 1.x releases that still support
            # Python 3.9 expose generateContent instead. Both are official Gemini APIs
            # and both enforce the same response JSON Schema. Keeping this compatibility
            # branch lets the repo's current system Python run the POC without weakening
            # the structured-output contract.
            if hasattr(self.client, 'interactions'):
                response = self.client.interactions.create(
                    model=model,
                    input=prompt,
                    response_format={
                        'type': 'text',
                        'mime_type': 'application/json',
                        'schema': response_schema,
                    },
                )
                output_text = response.output_text
                usage = getattr(response, 'usage', None)
            else:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_json_schema': response_schema,
                    },
                )
                output_text = ''.join(
                    part.text for candidate in (response.candidates or [])
                    for part in ((candidate.content.parts if candidate.content else []) or [])
                    if getattr(part, 'text', None))
                usage = getattr(response, 'usage_metadata', None)
        except Exception as exc:
            message = str(exc)
            if '429' in message or 'RESOURCE_EXHAUSTED' in message:
                raise RuntimeError('Gemini rate limit reached; state was not changed: %s' % message)
            raise RuntimeError('Gemini request failed; state was not changed: %s' % message)
        try:
            payload = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError('Gemini returned invalid JSON: %s' % exc)
        if hasattr(usage, 'model_dump'):
            usage = usage.model_dump(mode='json', exclude_none=True)
        elif hasattr(usage, 'to_dict'):
            usage = usage.to_dict()
        elif usage is not None and not isinstance(usage, (dict, list, str, int, float, bool)):
            usage = str(usage)
        meta = {
            'response_id': (getattr(response, 'id', None) or
                            getattr(response, 'response_id', None)),
            'usage': usage,
        }
        return payload, meta


def request_candidate(client, model, prompt):
    """Small injection seam: unit tests prove the workflow without touching a network."""
    payload, meta = client.generate(model, prompt)
    return validate_payload(payload), dict(meta or {})


def request_batch(client, model, prompt, expected_locs):
    """Request one scene batch and reject malformed/partial payloads before state changes."""
    payload, meta = client.generate(model, prompt, BATCH_RESPONSE_SCHEMA)
    translations = validate_batch_payload(payload, expected_locs)
    return translations, dict(meta or {})


def select_next(rows, state, loc=None, require_candidate=False):
    by_row = {row['loc']: row for row in rows}
    if loc:
        if loc not in by_row:
            raise SystemExit('no prose row at %s' % loc)
        entry = state['entries'][loc]
        if not entry.get('eligible'):
            raise SystemExit('%s is excluded: %s' % (loc, entry.get('skip_reason')))
        if require_candidate and not entry.get('candidate_en'):
            raise SystemExit('%s has no candidate to review' % loc)
        return by_row[loc]
    for row in rows:
        entry = state['entries'][row['loc']]
        if require_candidate:
            if (entry.get('candidate_en') and not entry.get('verified') and
                    entry.get('state') in ('candidate', 'fit_failed')):
                return row
        elif (entry.get('eligible') and not entry.get('verified') and
              entry.get('state') in ('pending', 'stale', 'fit_failed')):
            return row
    raise SystemExit('no matching prose entries remain')


def select_batch(rows, state, count=DEFAULT_BATCH_SIZE, loc=None):
    """Select pending rows from one authored section without crossing a scene boundary."""
    if count < 2 or count > MAX_BATCH_SIZE:
        raise SystemExit('batch count must be between 2 and %d' % MAX_BATCH_SIZE)
    by_index = {row['loc']: i for i, row in enumerate(rows)}
    pending_states = ('pending', 'stale')
    if loc:
        if loc not in by_index:
            raise SystemExit('no prose row at %s' % loc)
        entry = state['entries'][loc]
        if not entry.get('eligible'):
            raise SystemExit('%s is excluded: %s' % (loc, entry.get('skip_reason')))
        if entry.get('verified') or entry.get('state') not in pending_states:
            raise SystemExit('%s is not pending batch work (state: %s)' %
                             (loc, entry.get('state')))
        start = by_index[loc]
    else:
        start = next((i for i, row in enumerate(rows)
                      if state['entries'][row['loc']].get('eligible') and
                      not state['entries'][row['loc']].get('verified') and
                      state['entries'][row['loc']].get('state') in pending_states), None)
        if start is None:
            raise SystemExit('no pending prose entries remain for a batch')
    section = rows[start]['section']
    selected = []
    for row in rows[start:]:
        if row['section'] != section:
            break
        entry = state['entries'][row['loc']]
        if (entry.get('eligible') and not entry.get('verified') and
                entry.get('state') in pending_states):
            selected.append(row)
            if len(selected) == count:
                break
    if not selected:
        raise SystemExit('no pending prose entries remain in %s' % section)
    return selected


def store_candidate(row, state, payload, result, model, meta,
                    batch_size=1, batch_index=0):
    entry = state['entries'][row['loc']]
    provenance = {
        'provider': 'google-gemini',
        'model': model,
        'prompt_version': PROMPT_VERSION,
        'generated_at': utc_now(),
        'response_id': meta.get('response_id'),
        'usage': meta.get('usage'),
    }
    if batch_size > 1:
        provenance.update({'batch_size': batch_size, 'batch_index': batch_index})
    entry.update({
        'verified': False,
        'state': 'candidate' if result['valid'] else 'fit_failed',
        'candidate_en': result['candidate_en'],
        'ambiguities': payload['ambiguities'],
        'translator_notes': payload['translator_notes'],
        'provenance': provenance,
        'checks': result,
    })
    return entry


def print_generation_result(row, entry, result):
    print('%s  %s' % (row['loc'], entry['state']))
    print(result['candidate_en'])
    for problem in result['problems']:
        print('  FAIL %s: %s' % (problem['kind'], problem['detail']))
    for note in result['notes']:
        print('  NOTE %s: %s' % (note['kind'], note['detail']))


def do_next(args):
    rows, by_loc, state = init_state(args.review)
    row = select_next(rows, state, args.loc)
    terms = translation_terms()
    prompt = prompt_for(row, by_loc[row['loc']], rows, by_loc, state, terms, args.context)
    if args.dry_run:
        print(prompt)
        return 0
    if args.model not in FREE_TIER_MODELS and not args.allow_unlisted_model:
        raise SystemExit('%s is not in the 2026-08-10 free-tier allowlist; pass '
                         '--allow-unlisted-model only after checking current pricing' % args.model)
    key, source = credentials(args.credentials)
    print('Gemini credential loaded from %s; key is not logged' % source, file=sys.stderr)
    print('Model %s was free-tier eligible on 2026-08-10; project billing still controls '
          'whether a request can be charged.' % args.model, file=sys.stderr)
    client = GeminiClient(key)
    payload, meta = request_candidate(client, args.model, prompt)
    result = CandidateValidator(by_loc).validate(row, payload['translation'])
    entry = store_candidate(row, state, payload, result, args.model, meta)
    save_review(state, args.review)
    print_generation_result(row, entry, result)
    print('Run: python3 tools/gemini_prose.py review --loc %s' % row['loc'])
    return 0 if result['valid'] else 1


def do_batch(args):
    rows, by_loc, state = init_state(args.review)
    targets = select_batch(rows, state, args.count, args.loc)
    terms = translation_terms()
    prompt = prompt_for_batch(targets, rows, by_loc, state, terms, args.context)
    if args.dry_run:
        print(prompt)
        return 0
    if args.model not in FREE_TIER_MODELS and not args.allow_unlisted_model:
        raise SystemExit('%s is not in the 2026-08-10 free-tier allowlist; pass '
                         '--allow-unlisted-model only after checking current pricing' % args.model)
    key, source = credentials(args.credentials)
    print('Gemini credential loaded from %s; key is not logged' % source, file=sys.stderr)
    print('Sending %d rows from one scene to %s in one request.' %
          (len(targets), args.model), file=sys.stderr)
    client = GeminiClient(key)
    expected_locs = [row['loc'] for row in targets]
    payloads, meta = request_batch(client, args.model, prompt, expected_locs)
    validator = CandidateValidator(by_loc)
    results = []
    for index, (row, payload) in enumerate(zip(targets, payloads)):
        result = validator.validate(row, payload['translation'])
        entry = store_candidate(row, state, payload, result, args.model, meta,
                                batch_size=len(targets), batch_index=index)
        results.append((row, entry, result))
    save_review(state, args.review)
    for row, entry, result in results:
        print_generation_result(row, entry, result)
    print('Stored %d independently reviewable candidate(s) from one request.' % len(results))
    return 0 if all(result['valid'] for _row, _entry, result in results) else 1


def replace_tsv_row(path, loc, value):
    with open(path, encoding='utf-8') as source_file:
        lines = source_file.read().splitlines()
    found = 0
    for i, line in enumerate(lines):
        if line.startswith('#') or '\t' not in line:
            continue
        key = line.split('\t', 1)[0].strip()
        if key == loc:
            lines[i] = '%s\t%s' % (loc, value)
            found += 1
    if found != 1:
        raise ValueError('%s has %d rows for %s; expected exactly one' % (path, found, loc))
    return '\n'.join(lines) + '\n'


def fast_checks():
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    commands = [
        [sys.executable, 'tools/lint_en.py'],
        [sys.executable, 'tools/dialogue_preview.py', '--check'],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode:
            raise RuntimeError('%s failed with exit %d' % (' '.join(command), result.returncode))


def accept(row, state, result, review_path, run_checks=True):
    if not result['valid']:
        raise ValueError('candidate does not pass validation')
    with open(PROSE_PATH, encoding='utf-8') as source_file:
        old_prose = source_file.read()
    with open(EN_PATH, encoding='utf-8') as source_file:
        old_en = source_file.read()
    new_prose = replace_tsv_row(PROSE_PATH, row['loc'], result['candidate_en'])
    new_en = replace_tsv_row(EN_PATH, row['loc'], result['wrapped_en'])
    atomic_write(PROSE_PATH, new_prose)
    atomic_write(EN_PATH, new_en)
    try:
        if run_checks:
            fast_checks()
    except Exception:
        atomic_write(PROSE_PATH, old_prose)
        atomic_write(EN_PATH, old_en)
        raise
    entry = state['entries'][row['loc']]
    entry.update({
        'verified': True,
        'state': 'accepted',
        'candidate_en': result['candidate_en'],
        'checks': result,
        'current_en_sha256': sha256_text(result['candidate_en']),
        'verified_at': utc_now(),
    })
    save_review(state, review_path)


def print_review(row, source, entry, result):
    print('\n%s — %s' % (row['loc'], row['section']))
    print('Japanese : %s' % source['jp'])
    print('Current  : %s' % row['text'])
    print('Candidate: %s' % (entry.get('candidate_en') or '(none)'))
    if entry.get('ambiguities'):
        print('Ambiguities: %s' % '; '.join(entry['ambiguities']))
    if entry.get('translator_notes'):
        print('Gemini note: %s' % entry['translator_notes'])
    if result.get('wrapped_en'):
        print('Wrapped  : %s' % result['wrapped_en'])
    for problem in result['problems']:
        print('FAIL %s: %s' % (problem['kind'], problem['detail']))
    for note in result['notes']:
        print('NOTE %s: %s' % (note['kind'], note['detail']))


def do_review(args):
    rows, by_loc, state = init_state(args.review)
    row = select_next(rows, state, args.loc, require_candidate=True)
    entry = state['entries'][row['loc']]
    validator = CandidateValidator(by_loc)
    result = validator.validate(row, entry['candidate_en'])
    entry['checks'] = result
    if result['valid'] and entry.get('state') == 'fit_failed':
        entry['state'] = 'candidate'
    elif not result['valid'] and entry.get('state') == 'candidate':
        entry['state'] = 'fit_failed'
    print_review(row, by_loc[row['loc']], entry, result)
    if args.accept:
        choice = 'a'
    elif args.edit is not None:
        choice = 'e'
    elif args.reject:
        choice = 'r'
    elif args.needs_user:
        choice = 'u'
    elif not sys.stdin.isatty():
        save_review(state, args.review)
        return 0 if result['valid'] else 1
    else:
        choice = input('[a]ccept, [e]dit, [r]eject, [u]ser decision, '
                       '[s]kip, [q]uit: ').strip().lower()
    if choice == 'e':
        edited = args.edit if args.edit is not None else input('Edited candidate (one line): ')
        result = validator.validate(row, edited)
        entry['candidate_en'] = result['candidate_en']
        entry['checks'] = result
        entry['state'] = 'candidate' if result['valid'] else 'fit_failed'
        entry['review_notes'] = 'human-edited candidate'
        save_review(state, args.review)
        print_review(row, by_loc[row['loc']], entry, result)
        print('Saved edit; review again to accept it.')
        return 0 if result['valid'] else 1
    if choice == 'a':
        if not result['valid']:
            raise SystemExit('cannot accept: candidate has validation failures')
        accept(row, state, result, args.review, run_checks=not args.no_checks)
        print('%s accepted, wrapped into script/en.tsv, and marked verified' % row['loc'])
        return 0
    if choice == 'r':
        entry['verified'] = False
        entry['state'] = 'rejected'
        entry['review_notes'] = args.note or 'rejected by human reviewer'
        save_review(state, args.review)
        print('%s rejected' % row['loc'])
        return 0
    if choice == 'u':
        note = args.note
        if not note and sys.stdin.isatty():
            note = input('What decision is needed? ').strip()
        if not note:
            raise SystemExit('--needs-user requires --note in non-interactive use')
        entry['verified'] = False
        entry['state'] = 'needs_user'
        entry['review_notes'] = note
        save_review(state, args.review)
        print('%s deferred for user decision' % row['loc'])
        return 0
    if choice == 's':
        entry['verified'] = False
        entry['state'] = 'skipped'
        entry['review_notes'] = args.note or 'skipped by human reviewer'
        save_review(state, args.review)
        print('%s skipped' % row['loc'])
        return 0
    save_review(state, args.review)
    print('No change.')
    return 0


def do_status(args):
    _rows, _by_loc, state = init_state(args.review)
    counts = collections.Counter(entry.get('state', 'unknown')
                                 for entry in state['entries'].values())
    eligible = sum(1 for entry in state['entries'].values() if entry.get('eligible'))
    verified = sum(1 for entry in state['entries'].values() if entry.get('verified'))
    print('prose review: %d total, %d eligible, %d verified' %
          (len(state['entries']), eligible, verified))
    for name, count in sorted(counts.items()):
        print('  %-12s %d' % (name, count))
    return 0


TRIAGE_STATES = frozenset(['needs_user', 'rejected', 'fit_failed'])
ALL_REVIEW_STATES = frozenset([
    'pending', 'candidate', 'fit_failed', 'accepted', 'rejected', 'needs_user',
    'skipped', 'stale', 'excluded',
])


def tsv_cell(value):
    return str(value or '').replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')


def triage_tsv(rows, by_loc, state, states=TRIAGE_STATES):
    """Build an untracked, Japanese-inclusive report for decisions needing attention."""
    columns = [
        'loc', 'section', 'state', 'japanese', 'current_english', 'candidate_english',
        'ambiguities', 'validation_problems', 'review_notes',
    ]
    lines = ['\t'.join(columns)]
    for row in rows:
        entry = state['entries'][row['loc']]
        if entry.get('verified') or entry.get('state') not in states:
            continue
        checks = entry.get('checks') or {}
        raw_problems = checks.get('problems', []) if isinstance(checks, dict) else []
        problems = '; '.join(
            '%s: %s' % (problem.get('kind', 'problem'), problem.get('detail', ''))
            for problem in raw_problems if isinstance(problem, dict))
        values = [
            row['loc'], row['section'], entry.get('state'), by_loc[row['loc']]['jp'],
            row['text'], entry.get('candidate_en'), '; '.join(entry.get('ambiguities') or []),
            problems, entry.get('review_notes'),
        ]
        lines.append('\t'.join(tsv_cell(value) for value in values))
    return '\n'.join(lines) + '\n'


def do_triage(args):
    rows, by_loc, state = init_state(args.review)
    states = frozenset(args.states)
    unknown = states - ALL_REVIEW_STATES
    if unknown:
        raise SystemExit('unknown triage state(s): %s' % ', '.join(sorted(unknown)))
    report = triage_tsv(rows, by_loc, state, states)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    atomic_write(args.output, report)
    count = max(0, report.count('\n') - 1)
    print('wrote %d triage row(s) to %s' % (count, args.output))
    return 0


def do_verify_current(args):
    """Record that a human already approves the current prose, without an API request."""
    rows, by_loc, state = init_state(args.review)
    row = select_next(rows, state, args.loc)
    result = CandidateValidator(by_loc).validate(row, row['text'])
    if not result['valid']:
        for problem in result['problems']:
            print('FAIL %s: %s' % (problem['kind'], problem['detail']), file=sys.stderr)
        raise SystemExit('current prose at %s cannot be verified' % row['loc'])
    entry = state['entries'][row['loc']]
    entry.update({
        'verified': True,
        'state': 'accepted',
        'candidate_en': row['text'],
        'ambiguities': [],
        'translator_notes': '',
        'provenance': {
            'provider': 'human-existing',
            'model': None,
            'prompt_version': None,
            'generated_at': None,
            'response_id': None,
            'usage': None,
        },
        'checks': result,
        'review_notes': args.note or 'current prose verified without a Gemini request',
        'verified_at': utc_now(),
    })
    save_review(state, args.review)
    print('%s current prose marked verified; no API request was made' % row['loc'])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', default=REVIEW_PATH,
                        help='review-state JSON (default: script/prose_review.json)')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('init', help='create or synchronize the offline review queue')
    sub.add_parser('status', help='summarize queue states')

    nxt = sub.add_parser('next', help='translate the next unverified prose entry')
    nxt.add_argument('--loc', help='translate this loc instead of the next pending one')
    nxt.add_argument('--dry-run', action='store_true', help='print the prompt; make no API call')
    nxt.add_argument('--model', default=DEFAULT_MODEL)
    nxt.add_argument('--context', type=int, default=2,
                     help='neighboring rows on each side supplied as scene context')
    nxt.add_argument('--credentials', default=CREDENTIALS_PATH)
    nxt.add_argument('--allow-unlisted-model', action='store_true')

    batch = sub.add_parser('batch',
                           help='translate pending entries from one scene in one request')
    batch.add_argument('--loc', help='start at this pending loc instead of the queue head')
    batch.add_argument('--count', type=int, default=DEFAULT_BATCH_SIZE,
                       help='maximum targets in this request (default: %(default)s)')
    batch.add_argument('--dry-run', action='store_true', help='print the prompt; make no API call')
    batch.add_argument('--model', default=DEFAULT_MODEL)
    batch.add_argument('--context', type=int, default=2,
                       help='neighboring rows supplied as scene context')
    batch.add_argument('--credentials', default=CREDENTIALS_PATH)
    batch.add_argument('--allow-unlisted-model', action='store_true')

    review = sub.add_parser('review', help='inspect and decide a stored candidate')
    review.add_argument('--loc')
    decision = review.add_mutually_exclusive_group()
    decision.add_argument('--accept', action='store_true', help='non-interactive accept')
    decision.add_argument('--edit', metavar='TEXT',
                          help='store one reviewed edit; validate but do not accept it yet')
    decision.add_argument('--reject', action='store_true', help='non-interactive reject')
    decision.add_argument('--needs-user', action='store_true',
                          help='defer an unclear wording/meaning decision to the user')
    review.add_argument('--note')
    review.add_argument('--no-checks', action='store_true',
                        help='skip whole-corpus fast checks (intended for unit tests only)')

    verify = sub.add_parser('verify-current',
                            help='mark an already-reviewed current prose row verified')
    verify.add_argument('--loc', required=True)
    verify.add_argument('--note')

    triage = sub.add_parser('triage', help='write an ignored TSV of unresolved decisions')
    triage.add_argument('--output', default=os.path.join(ROOT, 'build/prose_triage.tsv'))
    triage.add_argument('--states', nargs='+', default=sorted(TRIAGE_STATES),
                        help='states to include (default: needs_user rejected fit_failed)')

    args = parser.parse_args(argv)
    if args.command == 'init':
        rows, _by_loc, state = init_state(args.review)
        eligible = sum(1 for entry in state['entries'].values() if entry['eligible'])
        print('initialized %d prose rows: %d eligible, %d excluded' %
              (len(rows), eligible, len(rows) - eligible))
        return 0
    if args.command == 'status':
        return do_status(args)
    if args.command == 'next':
        return do_next(args)
    if args.command == 'batch':
        return do_batch(args)
    if args.command == 'review':
        return do_review(args)
    if args.command == 'verify-current':
        return do_verify_current(args)
    if args.command == 'triage':
        return do_triage(args)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as exc:
        print('gemini_prose: %s' % exc, file=sys.stderr)
        sys.exit(1)
