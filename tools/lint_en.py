#!/usr/bin/env python3
"""Check a translation against its Japanese for the things `encode_en` cannot see.

THE HOLE THIS CLOSES. `build.encode_en` already rejects a character with no glyph, an
unknown token and a wrong argument count. All three are errors of FORM, and a model
producing translations in bulk rarely makes them. What it does make is an error of
CONTENT: it drops a token, or keeps the token and loses its argument, because the token
carries no meaning in the sentence it is rewriting.

That is silent. `<var>` pulls a monster name out of the message queue at runtime; a
translation that omits it encodes cleanly, inserts cleanly, passes every reference check
and every crash seed, and then prints "The  attacked!" on a screen no test looks at.

WHAT IS THE TRANSLATOR'S CHOICE AND WHAT IS NOT. This is the whole design, so it is
stated rather than implied:

  SUBSTITUTION and EFFECT tokens must survive exactly -- same tokens, same arguments,
  same counts. They inject runtime data or change renderer state, so dropping one loses
  information the English cannot carry by itself:

      <var>       $E2  pulls 3 bytes from the queue
      <cE3>       $E3  pulls 6 bytes from the queue
      <name>      $EA  copies the player's name from $CF81
      <cF0:xx>    $F0  passes xx to `11:$7E26`, which appends a table string
      <cE0:xx> <cE7:xx> <cEC:xx>   read an argument and act on it
      <mode0> <mode1>              $E8/$EB, a paired renderer mode

  LAYOUT tokens are free: <br> and <brk> are where lines and pages break, and <end> is
  where a box stops -- all three are translation decisions that differ between languages.
  Natural English runs about 2.15x the Japanese, so it needs MORE pages, not the same
  number: the innkeeper speech is 3 `<end>` in Japanese and 7 in English, and both are
  correct. Over-long and too-deep results are already caught by dialogue_preview's
  `line_too_long` / `box_too_deep`. The one thing worth checking is that a message which
  ended does not stop ending -- see `end_lost` below.

  RAW BYTES `<$XX>` are not checked for parity either. The Japanese carries a layout
  glyph like `▌` as a CHARACTER, and the English writes the same byte as `<$B6>`, so the
  two spellings never match and requiring them to would fail every status-screen
  composite. `build.escape_is_dte_code` is the check that actually covers these.

CALIBRATION. These three exclusions are not guesses -- the rule was written stricter,
run against the 117 already-translated strings, and every one of its three complaints was
a correct translation (the innkeeper's pagination, and `<$B6>` in the two status-screen
composites). A check that fires on known-good work trains its reader to ignore it.

MULTISET, NOT SEQUENCE. Order is deliberately not checked. "Shiren attacked <var>" and
"<var> dodged" are both legitimate renderings of the same Japanese, and requiring the
token to stay in place would fail correct English for no reason.

THE GLOSSARY IS THE SECOND SILENT FAILURE. `script/glossary.tsv` freezes 391 item,
monster and NPC names so that `こんぼう` is Club in the item list, in help text, in a
combat line and in a shop's dialogue. Nothing about a batch that renders it "Cudgel"
fails: it encodes, inserts, fits its cells and boots. It is only wrong across strings,
and no one holding 1,263 of them in their head is going to notice. So three checks:

    glossary_split       one Japanese name rendered two ways. `くねくねハニー` appears
                         at three tiers and must be Wriggle Honey at all three.
    glossary_collision   two DIFFERENT Japanese names rendered the same way, which makes
                         two monsters indistinguishable in a message.
    term_ignored         a translated string whose Japanese contains a frozen name, and
                         whose English does not use the frozen rendering. This is the
                         one that catches terminology drift in prose.

CALIBRATION, same rule as above: a check that fires on known-good work gets ignored.
`term_ignored` matches longest-term-first with the matched span masked, so
`つぼぞうだいのまきもの` is tested as Big Pot Scroll and not also as つぼ/Pot; it skips
terms under MIN_TERM characters, because two-kana names like フミ and ポチ occur inside
unrelated words; and it skips the placeholder slots (`New Weapon 3`), which name nothing.
It was run against every translated string before being turned on.

    lint_en.py                  check script/en.tsv, human-readable
    lint_en.py --tsv            one machine-readable row per problem, for a repair pass
    lint_en.py --en other.tsv   check a different file
    lint_en.py --no-glossary    token parity only, the pre-2026-08-04 behaviour
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec                                                    # noqa: E402
import dialogue_preview as dialogue      # shared measured renderer contracts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pagination and line breaks are the translator's. So is `<end>` -- see the docstring.
FREE = {'br', 'brk', 'end'}


def significant(text):
    """-> Counter of the tokens a translation is not allowed to change.

    Keyed on the token as written, arguments included, because `<cF0:02>` and `<cF0:03>`
    name two different table strings -- treating them as one token would let a repair
    swap the item being described.
    """
    out = collections.Counter()
    for m in codec.TOKEN_RE.finditer(text):
        tok = m.group(1)
        if tok.startswith('$') or tok.split(':')[0] in FREE:
            continue
        out[tok] += 1
    return out


def ends(text):
    return sum(1 for m in codec.TOKEN_RE.finditer(text) if m.group(1) == 'end')


def check_one(jp, en, bank=None):
    """-> list of (kind, detail) for one string."""
    want, got = significant(jp), significant(en)
    bad = []
    for tok in sorted(set(want) | set(got)):
        n, m = want[tok], got[tok]
        if n == m:
            continue
        bad.append(('token_lost' if m < n else 'token_added',
                    '<%s> appears %d time(s) in the Japanese, %d in the English'
                    % (tok, n, m)))
    # Pagination is free, but a message that ended has to keep ending: `<end>` sets
    # $CFC4, and with none of them the box never closes.
    if ends(jp) and not ends(en):
        bad.append(('end_lost', 'the Japanese ends the message %d time(s) and the English '
                                'never does -- the box will not close' % ends(jp)))
    # ...and it must not end LAST. A trailing `<end>` makes the composer draw the final
    # box a second time, identically, so the player presses A twice for one screen -- Joey
    # photographed it on 2026-08-05 and the A/B is `new -> SAME -> closed` against
    # `new -> closed`. The shipped Japanese never leaves one trailing in dialogue: of the
    # 63 bank-11/14 strings whose last box holds an `<end>`, 32 are followed by a `<br>`
    # and 31 by more text, none by nothing. Scoped by the Japanese rather than absolute --
    # 89 strings outside banks 11/14 do end with one, and those renderers are not this one.
    if en.rstrip().endswith('<end>') and not jp.rstrip().endswith('<end>'):
        bad.append(('end_trailing', 'the English ends with <end> and the Japanese does not '
                                    '-- the last box is drawn twice and costs a second '
                                    'button press. Move it before the last <br>'))
    # `<end><brk>` at the physical end is the same bug wearing a page break: `<end>`
    # completes the message, then `<brk>` asks the caller for one more page.  The town
    # Koppa line at 14:$7BC2 exposed this as `message -> empty box -> closed`; its native
    # source has neither control and closes directly on $FF.  Limit the rule to dialogue
    # whose Japanese has no `<end>` at all: messages with native event terminators may
    # deliberately preserve one at a page boundary.
    if (bank in (11, 14) and not ends(jp)
            and re.search(r'<end>(?:<brk>)+\s*$', en)):
        bad.append(('end_before_terminal_brk',
                    'the English adds terminal <end><brk> to a Japanese dialogue with '
                    'no <end> -- it draws an empty final box. Let $FF close the message'))
    # The Dot dialogue reveal cannot safely resume printable text after `<end>` inside a
    # box.  The suffix is omitted while the unchanged box still consumes a press. Joey
    # found this on 11:$6713 (`He went to rescue<end> Fumi!`) and 11:$67A8
    # (`I'm not going up<end> there!`) on 2026-08-10. A real page boundary is safe, as is
    # an end followed only by terminal effect controls such as `<mode0>`.
    if bank in (11, 14) and re.search(r'<end>(?!(?:<[^>]+>)*$|<brk>)', en):
        bad.append(('end_resumes_text', 'printable dialogue resumes after <end> without a '
                                          '<brk> -- the suffix can disappear and the box '
                                          'costs an empty press. Put the semantic pause '
                                          'at a <brk> instead'))
    return bad


# A glossary term shorter than this is not searched for in prose. `フミ`, `ポチ`, `つぼ`
# and `ナギ` are 2-3 cells and occur inside unrelated words; the names that actually drift
# are the compounds. Measured: at 3 this fires 0 times on the 508 translated strings.
MIN_TERM = 3

# ---- the speaker attribution, and why it is not the name
#
# Ruled by Joey 2026-08-05, off two real screens (`build/speakertag_choice.png`).
#
# Six NPCs are frozen as role+name compounds, because that is what the NPC NAME TABLE has
# to say: `<var>` substitutes one into a combat line, and "Kinji attacked!" does not tell
# a player who Kinji is. But 99 of session 5's 323 village strings open by ATTRIBUTING a
# line to one of them, and there the compound is not a name -- it is a stage direction.
# `だいくのキンジ「` is 7 cells of an 18-cell Japanese line. "Builder Kinji: " uses 15
# staged Dot glyphs today; its real line fit is decided by the 30/144 composer checks.
#
# So the glossary keeps the compound and prose may open with the short form. This is
# deliberately NOT a glossary_ok entry: that file is for a reviewed one-off with a
# sentence of justification, and 99 of them would make it a silencer -- the exact failure
# its own header warns about.
#
# THE EXEMPTION IS NARROW ON PURPOSE. It applies only where the Japanese string OPENS with
# `<name>「`, which is the attribution position, and only to the short form named here.
# The same name later in the same sentence is still checked, because there it is a name.
# `フミのはは` is not in this table: she has no personal name anywhere in the script, so
# the short form would be the generic "Mother". She was reworded in the glossary instead,
# to `Fumi's Mom` -- the same rendering in both places; its actual runtime uses are
# measured by `fontaudit.py`, not excused by a universal name cap.
ATTRIBUTION = {
    'だいくのキンジ': 'Kinji',
    'だいくのマサ': 'Masa',
    'むらおさ': 'Chief',
    'ぱしりのゴン': 'Gon',
    'かんぬし': 'Priest',
}


def attribution_terms(jp, en):
    """-> {jp term} whose frozen rendering this string may replace with a short tag.

    Empty unless the Japanese OPENS with the name and the English opens with the short
    form and a colon. Both halves are required: the first is what makes it an attribution
    rather than a mention, and the second is what stops the exemption from excusing an
    English line that simply forgot the name.

    Matched as a prefix rather than as `TERM「`, because the farewell messages put a pause
    between the two -- `だいくのマサ<mode1>こ「じゃあな」` is an attribution with `<mode1>`
    and its argument byte sitting where the bracket would be. Requiring the bracket made
    those read as mentions and demanded `Builder Masa` in a nine-cell line.
    """
    head_jp = re.sub(r'^(?:<[^>]*>)*', '', jp)
    head_en = re.sub(r'^(?:<[^>]*>)*', '', en)
    for term, short in ATTRIBUTION.items():
        if head_jp.startswith(term) and head_en.startswith(short + ':'):
            return frozenset([term])
    return frozenset()

# Historical reservations retained only so old reports can explain where 14/16 came from.
# They are not enforced: current source and painted-pixel checks live with each measured
# renderer path, and a glossary name has no single universal line budget.
CAP = {'item': dialogue.ITEM_CAP, 'appearance': dialogue.ITEM_CAP,
       'monster': dialogue.NAME_CAP, 'npc': dialogue.NAME_CAP}

# ---- the usage counter, and why staffs and pots get a tighter cap than the rest
#
# Joey photographed `Stopgap Staff[6]` in play on 2026-08-04, which is 13 cells of name
# and three more of counter. The glossary had been sized against a bare 16-cell name in a
# 17-cell row -- measured, but measured on an item that has no counter -- so `Paralysis
# Staff` and `Pain Split Staff` were already losing characters on the real screen.
#
# `4:$5D58` writes `[`, calls the formatter at `4:$5CDC`, then writes `]`. The formatter
# converts the byte at `$FFB8` and suppresses AT MOST two leading zeros (`ld b,$02`), so
# the count is 1-3 digits and never padded: `[6]` costs 3 cells, `[12]` costs 4, `[100]`
# 5. Both routines charge `$C6DC`, the row's cell counter, so the game measures this --
# it just has nothing to say when the total does not fit.
#
# Budget at TWO digits. Staff uses stack through fusion, so 10+ is ordinary play; three
# digits is not, and a name is not worth shortening for it.
ITEM_ROW_CELLS = 18       # VWF stager/scan contract, including any runtime suffix.
COUNTER_CELLS = 4         # `[` + two digits + `]`


def carries_counter(en):
    """True if the item list draws a `[N]` after this name.

    Keyed on the frozen category noun, which is exactly why the nouns are frozen: staffs
    and pots are the two classes the game counts, and after the glossary every one of them
    ends in `Staff` or `Pot`.
    """
    return en.endswith(' Staff') or en.endswith(' Pot') or en.split()[-1] in ('Staff', 'Pot')


def spreadsheet_line(line):
    """-> one logical line, tolerant of what a spreadsheet export does to a TSV.

    Joey reviews the glossary in OSX Numbers, which is the right tool for the job and
    exports a TSV that is not quite this one:

      * every line is padded with tabs out to the widest row, so the English field comes
        back as `Sickle\\t\\t\\t` and fails to encode;
      * any line containing a comma is wrapped in double quotes -- which here means the
        COMMENT block, so the file no longer starts with `#` and the parser rejects line 1;
      * CRLF endings (harmless: Python's universal newlines already fold those).

    Only these three are absorbed. A quoted or padded field in the DATA is left alone to
    fail loudly, because there it would mean something went wrong rather than something
    was reformatted.
    """
    line = line.rstrip('\n').rstrip('\r').rstrip('\t')
    if len(line) > 1 and line[0] == '"' and line.endswith('"'):
        # CSV quoting doubles an embedded quote, so undo both halves together. Missing
        # this leaves `""One-Eye Killer""` behind, and it doubles again on every trip
        # through the spreadsheet.
        line = line[1:-1].replace('""', '"')
    return line


def load_glossary(path):
    """-> list of {loc, cls, jp, en}, or [] if there is no glossary."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as source:
        for n, line in enumerate(source, 1):
            line = spreadsheet_line(line)
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) != 4:
                raise SystemExit('%s:%d expects `loc<TAB>class<TAB>jp<TAB>en`, got %d field(s)'
                                 % (path, n, len(parts)))
            loc, cls, jp, en = (p.strip() for p in parts)
            if cls not in CAP:
                raise SystemExit('%s:%d unknown class %r (want %s)'
                                 % (path, n, cls, '/'.join(sorted(CAP))))
            out.append({'loc': loc, 'cls': cls, 'jp': jp, 'en': en, 'line': n})
    return out


def check_glossary(gloss, by_loc):
    """-> list of (loc, kind, detail) for the glossary itself."""
    bad = []
    j2e, e2j = collections.defaultdict(set), collections.defaultdict(set)
    for g in gloss:
        r = by_loc.get(g['loc'])
        if r is None:
            bad.append((g['loc'], 'unknown_loc',
                        'no string at this loc -- extraction moved or the key is wrong'))
        elif r['jp'] != g['jp']:
            # The jp column is not decoration: term_ignored searches for it. If it drifts
            # from the ROM the search quietly stops matching anything.
            bad.append((g['loc'], 'jp_drift', 'glossary says %r, the script says %r'
                        % (g['jp'], r['jp'])))
        if carries_counter(g['en']):
            room = ITEM_ROW_CELLS - COUNTER_CELLS
            if len(g['en']) > room:
                bad.append((g['loc'], 'counter_overflow',
                            '%r is %d source characters and the item list draws `[NN]` '
                            'after it, so the staged row needs %d of the current %d. This '
                            'is a source-path guard, not a Dot pixel verdict; measure and '
                            'widen the stager instead of shortening automatically. The '
                            'current source allowance for a staff or pot name is %d.'
                            % (g['en'], len(g['en']), len(g['en']) + COUNTER_CELLS,
                               ITEM_ROW_CELLS, room)))
        j2e[g['jp']].add(g['en'])
        e2j[g['en']].add(g['jp'])
    for g in gloss:
        if len(j2e[g['jp']]) > 1:
            bad.append((g['loc'], 'glossary_split', '%s is rendered %s -- one Japanese '
                        'name takes one English name at every tier'
                        % (g['jp'], ' and '.join(sorted(map(repr, j2e[g['jp']]))))))
        if len(e2j[g['en']]) > 1:
            bad.append((g['loc'], 'glossary_collision', '%r also renders %s -- two names '
                        'the player cannot tell apart in a message'
                        % (g['en'], ' / '.join(sorted(e2j[g['en']] - {g['jp']})))))
    # One row per problem, not one per duplicate pair.
    return sorted(set(bad))


def terms_for_search(gloss):
    """-> [(jp, en)] longest first, minus what must not be searched for.

    Placeholders name nothing (`しんきぶき3` is an unused slot), so a string that happens
    to contain one is not drifting from anything.
    """
    seen, out = set(), []
    for g in gloss:
        if len(g['jp']) < MIN_TERM or g['en'].startswith('New ') or g['jp'] in seen:
            continue
        seen.add(g['jp'])
        out.append((g['jp'], g['en']))
    return sorted(out, key=lambda t: -len(t[0]))


def load_glossary_ok(path):
    """-> {(loc, jp term)} reviewed exceptions. See script/glossary_ok.tsv."""
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as source:
        for line in source:
            if line.startswith('#') or line.count('\t') < 2:
                continue
            loc, term, _why = line.rstrip('\n').split('\t', 2)
            out.add((loc.strip(), term.strip()))
    return out


# Layout that can fall INSIDE a frozen name. `Village Chief` wrapped across a line is
# stored as `the Village<br> Chief`, and a plain substring search then says the English
# does not use the name -- which is false, and it fired on two correct strings the moment
# tools/wrap_en.py started breaking lines by measurement rather than by hand. Only the
# LAYOUT tokens are removed and the gap is closed to a single space, so a name genuinely
# missing is still missing.
_LAYOUT = re.compile(r'<(?:br|brk|end)>')


def flatten(en):
    """Translation -> one line, for substring matching. Layout out, spacing normalised."""
    return ' '.join(_LAYOUT.sub(' ', en).split())


def check_terms(jp, en, terms, allowed=frozenset()):
    """-> list of (kind, detail) where the English ignores a frozen name.

    Longest first, with each match masked out, so a compound is tested as itself and its
    parts are not tested again inside it. `allowed` is this string's reviewed exceptions.
    """
    bad = []
    mask = [False] * len(jp)
    low = flatten(en).lower()
    for term, want in terms:
        start = 0
        while True:
            i = jp.find(term, start)
            if i < 0:
                break
            start = i + 1
            if any(mask[i:i + len(term)]):
                continue
            for k in range(i, i + len(term)):
                mask[k] = True
            if want.lower() not in low and term not in allowed:
                bad.append(('term_ignored',
                            'the Japanese says %s, which the glossary freezes as %r -- '
                            'the English does not use it' % (term, want)))
    return bad


def load_en(path):
    out = {}
    with open(path, encoding='utf-8') as source:
        for line in source:
            if line.startswith('#') or '\t' not in line:
                continue
            k, v = line.split('\t', 1)
            if v.strip():
                out[k.strip()] = v.rstrip('\n')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--en', default=os.path.join(ROOT, 'script/en.tsv'))
    ap.add_argument('--script', default=os.path.join(ROOT, 'script/script.json'))
    ap.add_argument('--tsv', action='store_true', help='machine-readable, for a repair pass')
    ap.add_argument('--glossary', default=os.path.join(ROOT, 'script/glossary.tsv'))
    ap.add_argument('--no-glossary', action='store_true',
                    help='token parity only, the pre-2026-08-04 behaviour')
    a = ap.parse_args()

    by_loc = {r['loc']: r for r in json.load(open(a.script, encoding='utf-8'))['strings']}
    trans = load_en(a.en)

    gloss = [] if a.no_glossary else load_glossary(a.glossary)
    gloss_ok = load_glossary_ok(os.path.join(ROOT, 'script/glossary_ok.tsv'))
    terms = terms_for_search(gloss)
    frozen = {g['loc'] for g in gloss}

    problems, unknown = [], []
    for loc, kind, detail in check_glossary(gloss, by_loc):
        if kind == 'unknown_loc':
            unknown.append(loc)
        else:
            g = next(x for x in gloss if x['loc'] == loc)
            problems.append((loc, kind, detail, g['jp'], g['en']))
    for loc, en in sorted(trans.items()):
        r = by_loc.get(loc)
        if r is None:
            unknown.append(loc)
            continue
        for kind, detail in check_one(r['jp'], en, r['bank']):
            problems.append((loc, kind, detail, r['jp'], en))
        # A glossary entry is the definition, so it is not also drift from itself.
        if loc not in frozen:
            allowed = {t for l, t in gloss_ok if l == loc}
            allowed |= attribution_terms(r['jp'], en)
            for kind, detail in check_terms(r['jp'], en, terms, allowed):
                problems.append((loc, kind, detail, r['jp'], en))

    if a.tsv:
        print('loc\tkind\tdetail\tjp\ten')
        for row in problems:
            print('\t'.join(x.replace('\t', ' ') for x in row))
        for loc in unknown:
            print('%s\tunknown_loc\tno string at this loc -- extraction moved or the key '
                  'is wrong\t\t' % loc)
    else:
        for loc, kind, detail, jp, en in problems:
            print('%-12s %s' % (loc, kind))
            print('    %s' % detail)
            print('    jp: %s' % jp)
            print('    en: %s' % en)
        for loc in unknown:
            print('%-12s unknown_loc  no string at this loc' % loc)
        print('lint_en: %d translated string(s), %d frozen name(s), %d problem(s)%s'
              % (len(trans), len(gloss), len(problems),
                 ', %d unknown loc(s)' % len(unknown) if unknown else ''))
    return 1 if problems or unknown else 0


if __name__ == '__main__':
    sys.exit(main())
