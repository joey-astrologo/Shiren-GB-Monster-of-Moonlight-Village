#!/usr/bin/env python3
"""Audit every dialogue ``<var>`` against confirmed and candidate runtime values.

``fontaudit.py`` deliberately charges an unresolved ``<var>`` only its narrowest
possible glyph for the definite-failure gate. That prevents false build failures, but it
also means a real producer value can hide in the legacy-reservation warning list. This
companion audit closes that review gap without pretending every monster, NPC, item and
appearance name is reachable from every message.

Confirmed producer values live in ``script/var_domains.tsv``. Exhaustive producer roles
live in ``script/var_roles.tsv``; they keep monsters, combat actors and player names
separate without enumerating a glossary in the contract file. Both are build contracts,
and overflow is fatal. ``script/var_advisories.tsv`` narrows proven producer classes whose
exact reachable pairs remain unknown, while deliberately keeping their overflows
non-fatal and visible. Every other dynamic line is written to the same complete TSV review
list with a deliberately broad glossary census.
"""
import argparse
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build                                                         # noqa: E402
import dialogue_preview as dialogue                                  # noqa: E402
import dotfont                                                       # noqa: E402
import fontaudit                                                     # noqa: E402
import lint_en                                                       # noqa: E402


def load_domains(path):
    domains = {}
    for number, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) != 6:
            raise SystemExit('%s:%d: expected six tab-separated fields' % (path, number))
        loc, box, row, occurrence, values, evidence = fields
        key = (loc.strip(), int(box), int(row), int(occurrence))
        if key in domains:
            raise SystemExit('%s:%d: duplicate domain %r' % (path, number, key))
        choices = tuple(value.strip() for value in values.split('|') if value.strip())
        if not choices:
            raise SystemExit('%s:%d: domain has no values' % (path, number))
        domains[key] = (choices, evidence.strip(), number)
    return domains


def load_roles(path):
    roles = {}
    for number, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) != 6:
            raise SystemExit('%s:%d: expected six tab-separated fields' % (path, number))
        loc, box, row, occurrence, role, evidence = fields
        key = (loc.strip(), int(box), int(row), int(occurrence))
        if key in roles:
            raise SystemExit('%s:%d: duplicate role %r' % (path, number, key))
        roles[key] = (role.strip(), evidence.strip(), number)
    return roles


def metric(data, font, bank, pixel_controls, source_controls):
    advance, extent, raw = dialogue.dot_metrics(data, font, bank, pixel_controls)
    source = dialogue.Line(data, 'end', 0, 0, bank).cells(source_controls)
    return advance, extent, source, frozenset(raw)


def combine(left, right):
    """Concatenate two premeasured runs, preserving advance and painted extent."""
    left_advance, left_extent, left_source, left_raw = left
    right_advance, right_extent, right_source, right_raw = right
    extent = max(left_extent,
                 left_advance + right_extent if right_extent else left_extent)
    return (left_advance + right_advance, extent, left_source + right_source,
            left_raw | right_raw)


def clean(value):
    return value.replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', default=os.path.join(ROOT, 'script', 'script.json'))
    parser.add_argument('--en', default=os.path.join(ROOT, 'script', 'en.tsv'))
    parser.add_argument('--glossary', default=os.path.join(ROOT, 'script', 'glossary.tsv'))
    parser.add_argument('--domains', default=os.path.join(ROOT, 'script', 'var_domains.tsv'))
    parser.add_argument('--roles', default=os.path.join(ROOT, 'script', 'var_roles.tsv'))
    parser.add_argument('--advisories',
                        default=os.path.join(ROOT, 'script', 'var_advisories.tsv'))
    parser.add_argument('--output', default=os.path.join(ROOT, 'build', 'var_review.tsv'))
    args = parser.parse_args(argv)

    manifest = json.load(open(args.script, encoding='utf-8'))
    strings = manifest['strings']
    by_id = {row['id']: row for row in strings}
    translated, _sources, unknown = fontaudit.load_translations(
        manifest, args.en, args.glossary)
    encoded, encode_errors = fontaudit.encoded_translations(strings, translated)
    if unknown or encode_errors:
        raise SystemExit('varaudit: translation inputs are not clean; run fontaudit.py first')

    font = dotfont.load_approved()
    domains = load_domains(args.domains)
    roles = load_roles(args.roles)
    advisories = load_roles(args.advisories)
    duplicate_roles = sorted(set(roles) & set(advisories))
    if duplicate_roles:
        raise SystemExit('varaudit: substitution(s) are both contracted and advisory: %s' %
                         ', '.join('%s box %d line %d occurrence %d' % key
                                   for key in duplicate_roles))
    used_domains = set()
    used_roles = set()
    used_advisories = set()

    glossary_classes = {}
    for entry in lint_en.load_glossary(args.glossary):
        if entry['cls'] not in ('monster', 'npc', 'item', 'appearance'):
            continue
        glossary_classes.setdefault(entry['cls'], []).append(entry['en'])
    for cls, values in glossary_classes.items():
        glossary_classes[cls] = sorted(set(values))

    # The save format permits six input characters. These are the same representative
    # strings used by the ranking regressions, including the widest approved glyph six
    # times; that bounds every other six-character player name in this font.
    player_names = ('Shiren', 'WWWWWW', 'iiiiii', 'Abcdef', '+-[]?.')
    companions = ('Nagi', 'Fumi', 'Pochi', 'Rooster', 'Tanmomo', 'Baby Mamel')
    role_values = {
        'monster': tuple(glossary_classes['monster']),
        'npc': tuple(glossary_classes['npc']),
        'player': player_names,
        'combat-actor': tuple(sorted(set(glossary_classes['monster']) |
                                     set(companions) | set(player_names))),
        # The two-name damage template is bypassed when target E is player actor $12;
        # its second value is therefore a monster or companion, never a player name.
        'combat-target': tuple(sorted(set(glossary_classes['monster']) |
                                      set(companions))),
        'actor': tuple(sorted(set(glossary_classes['monster']) |
                              set(glossary_classes['npc']) | set(player_names))),
    }
    for key, (role, _evidence, number) in roles.items():
        if role not in role_values:
            raise SystemExit('%s:%d: unknown role %r' % (args.roles, number, role))
    for key, (role, _evidence, number) in advisories.items():
        if role not in role_values:
            raise SystemExit('%s:%d: unknown advisory role %r' %
                             (args.advisories, number, role))

    # This is intentionally much broader than any known actor producer. It remains the
    # fallback for lines whose producer has not yet been classified at all.
    candidates = sorted(set().union(*glossary_classes.values()))
    pixel_controls = dialogue.dot_production_widths(font)
    source_controls = dialogue.production_widths()
    name_metrics = {
        bank: {
            value: metric(build.encode_en(value, bank), font, bank,
                          pixel_controls, source_controls)
            for value in candidates
        }
        for bank in (11, 13, 14)
    }

    records = []
    contract_failures = []
    advisory_scope_failures = []
    for ident, data in encoded.items():
        row = by_id[ident]
        if not dialogue.is_dialogue(row):
            continue
        for line in dialogue.split_lines(data, row['bank']):
            count = line.data.count(0xE2)
            if not count:
                continue
            keys = [(row['loc'], line.box + 1, line.row + 1, occurrence)
                    for occurrence in range(1, count + 1)]
            present = [key in domains for key in keys]
            for key, is_present in zip(keys, present):
                if is_present:
                    used_domains.add(key)
                if key in roles:
                    used_roles.add(key)
            scoped = [key in roles for key in keys]
            advised = [key in advisories for key in keys]
            for key, is_advised in zip(keys, advised):
                if is_advised:
                    used_advisories.add(key)
            status = ('confirmed' if all(present) else
                      'scoped' if any(scoped) else
                      'advisory' if any(advised) else
                      'partial' if any(present) else 'unresolved')

            # An exhaustive producer contract is narrower and stronger than its broad
            # semantic role.  Prefer it whenever both are recorded; the role remains in
            # the report as useful documentation.
            broad_domains = [domains[key][0] if key in domains else
                             role_values[roles[key][0]] if key in roles else
                             role_values[advisories[key][0]] if key in advisories else
                             tuple(candidates)
                             for key in keys]
            # Today there are at most two substitutions on one line. Keep the review
            # exhaustive, but fail loudly if a future edit would create an accidental
            # combinatorial monster rather than silently sampling it.
            combinations = 1
            for choices in broad_domains:
                combinations *= len(choices)
            if combinations > 500000:
                raise SystemExit('varaudit: %s box %d line %d needs %d combinations; '
                                 'confirm at least one producer domain first' %
                                 (row['loc'], line.box + 1, line.row + 1, combinations))

            segment_metrics = [metric(segment, font, row['bank'], pixel_controls,
                                      source_controls)
                               for segment in line.data.split(b'\xe2')]
            outcomes = []
            for values in itertools.product(*broad_domains):
                measured = segment_metrics[0]
                for index, value in enumerate(values):
                    value_metric = name_metrics[row['bank']].get(value)
                    if value_metric is None:
                        value_metric = metric(build.encode_en(value, row['bank']), font,
                                              row['bank'], pixel_controls, source_controls)
                    measured = combine(measured, value_metric)
                    measured = combine(measured, segment_metrics[index + 1])
                _advance, extent, source, raw = measured
                over = (extent > fontaudit.COMPOSER_PX or source > dialogue.WIDTH or
                        bool(raw))
                outcomes.append((over, extent, source, values, raw))
            outcomes.sort(key=lambda item: (item[1], item[2], item[3]))
            unsafe = [item for item in outcomes if item[0]]
            first = unsafe[0] if unsafe else None
            worst = max(outcomes, key=lambda item: (item[1], item[2]))

            # The current combat advisory is intentionally allowed to overflow, but the
            # audited claim is precise: only monster-versus-monster pairs are risky.
            # Fail the build if a companion or representative player name ever joins the
            # unsafe subset after a font, glossary, wording or role-domain change.
            monsters = set(glossary_classes['monster'])
            for item in unsafe:
                values = item[3]
                for key, value in zip(keys, values):
                    if key in advisories and advisories[key][0] in (
                            'combat-actor', 'combat-target') and value not in monsters:
                        advisory_scope_failures.append((row, line, values, value))

            confirmed_values = ''
            evidence = ''
            role_domains = ''
            role_evidence = ''
            if any(present):
                confirmed_values = ' ; '.join(
                    '|'.join(domains[key][0]) if key in domains else '?'
                    for key in keys)
                evidence = ' ; '.join(domains[key][1] for key in keys if key in domains)
            if any(scoped):
                role_domains = ' ; '.join(roles[key][0] if key in roles else '?'
                                          for key in keys)
                role_evidence = ' ; '.join(roles[key][1] for key in keys if key in roles)
            if any(advised):
                role_domains = ' ; '.join(
                    (advisories[key][0] + ' (advisory)') if key in advisories else
                    roles[key][0] if key in roles else '?'
                    for key in keys)
                role_evidence = ' ; '.join(
                    advisories[key][1] for key in keys if key in advisories)

            # An exact domain or an approved exhaustive role is a build contract. Mixed
            # lines are valid too: use the exact subset where known and the full role
            # elsewhere. Only wholly unclassified broad-census rows remain advisory.
            if all(key in domains or key in roles for key in keys):
                contract_domains = [domains[key][0] if key in domains else
                                    role_values[roles[key][0]] for key in keys]
                contract_outcomes = []
                for values in itertools.product(*contract_domains):
                    measured = segment_metrics[0]
                    for index, value in enumerate(values):
                        value_metric = name_metrics[row['bank']].get(value)
                        if value_metric is None:
                            value_metric = metric(build.encode_en(value, row['bank']), font,
                                                  row['bank'], pixel_controls,
                                                  source_controls)
                        measured = combine(measured, value_metric)
                        measured = combine(measured, segment_metrics[index + 1])
                    _advance, extent, source, raw = measured
                    if (extent > fontaudit.COMPOSER_PX or source > dialogue.WIDTH or raw):
                        contract_outcomes.append((True, extent, source, values, raw))
                if contract_outcomes:
                    contract_failures.append((row, line, contract_outcomes))

            records.append({
                'loc': row['loc'], 'box': line.box + 1, 'line': line.row + 1,
                'vars': count, 'status': status, 'template': line.text(),
                'combinations': len(outcomes), 'safe': len(outcomes) - len(unsafe),
                'unsafe': len(unsafe),
                'first_over': ('%s => %dpx/%d glyphs' %
                               (' + '.join(first[3]), first[1], first[2]) if first else ''),
                'worst': '%s => %dpx/%d glyphs' %
                         (' + '.join(worst[3]), worst[1], worst[2]),
                'role_domains': role_domains, 'role_evidence': role_evidence,
                'confirmed_values': confirmed_values, 'evidence': evidence,
            })

    unused = sorted(set(domains) - used_domains)
    if unused:
        lines = ', '.join('%s box %d line %d occurrence %d' % key for key in unused)
        raise SystemExit('varaudit: domain rows no longer match a <var>: ' + lines)
    unused = sorted(set(roles) - used_roles)
    if unused:
        lines = ', '.join('%s box %d line %d occurrence %d' % key for key in unused)
        raise SystemExit('varaudit: role rows no longer match a <var>: ' + lines)
    unused = sorted(set(advisories) - used_advisories)
    if unused:
        lines = ', '.join('%s box %d line %d occurrence %d' % key for key in unused)
        raise SystemExit('varaudit: advisory rows no longer match a <var>: ' + lines)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    columns = ('loc', 'box', 'line', 'vars', 'status', 'template', 'combinations',
               'safe', 'unsafe', 'first_over', 'worst', 'role_domains', 'role_evidence',
               'confirmed_values', 'evidence')
    with open(args.output, 'w', encoding='utf-8') as out:
        out.write('\t'.join(columns) + '\n')
        for record in records:
            out.write('\t'.join(clean(str(record[column])) for column in columns) + '\n')

    counts = {status: sum(record['status'] == status for record in records)
              for status in ('confirmed', 'scoped', 'advisory', 'partial', 'unresolved')}
    risky = sum(record['unsafe'] > 0 for record in records)
    print('varaudit: %d dynamic line(s): %d confirmed, %d scoped, %d advisory, '
          '%d partial, %d unresolved; %d review risk(s)' %
          (len(records), counts['confirmed'], counts['scoped'], counts['advisory'],
           counts['partial'], counts['unresolved'], risky))
    print('varaudit: complete review list: %s' % os.path.relpath(args.output, ROOT))
    for record in records:
        if record['status'] == 'confirmed' or not record['unsafe']:
            continue
        print('REVIEW %-11s box %d line %d [%s]: %d/%d candidates overflow; '
              'first %s; %s' %
              (record['loc'], record['box'], record['line'],
               record['role_domains'] or 'broad-unresolved', record['unsafe'],
               record['combinations'], record['first_over'], record['template']))
    for row, line, unsafe in contract_failures:
        first = unsafe[0]
        print('CONTRACT OVERFLOW %s box %d line %d: %s => %d/%dpx, %d/%d glyphs'
              % (row['loc'], line.box + 1, line.row + 1, ' + '.join(first[3]),
                 first[1], fontaudit.COMPOSER_PX, first[2], dialogue.WIDTH))
    for row, line, values, value in advisory_scope_failures:
        print('ADVISORY SCOPE DRIFT %s box %d line %d: %s includes unsafe non-monster '
              'value %s' % (row['loc'], line.box + 1, line.row + 1,
                            ' + '.join(values), value))
    return 1 if contract_failures or advisory_scope_failures else 0


if __name__ == '__main__':
    sys.exit(main())
