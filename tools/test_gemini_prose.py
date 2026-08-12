#!/usr/bin/env python3
"""Offline regression tests for tools/gemini_prose.py."""
import copy
import json
import os
import re
import sys
import tempfile
import unittest
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_prose as gp                                      # noqa: E402

warnings.simplefilter('ignore', ResourceWarning)


class FakeClient:
    def __init__(self, translation):
        self.translation = translation
        self.calls = []

    def generate(self, model, prompt, response_schema=gp.RESPONSE_SCHEMA):
        self.calls.append((model, prompt, response_schema))
        return ({
            'translation': self.translation,
            'ambiguities': [],
            'translator_notes': 'offline fixture',
        }, {'response_id': 'fake-response'})


class FakeBatchClient:
    def __init__(self, translations):
        self.translations = translations
        self.calls = []

    def generate(self, model, prompt, response_schema=gp.RESPONSE_SCHEMA):
        self.calls.append((model, prompt, response_schema))
        return ({'translations': [
            {'loc': loc, 'translation': translation, 'ambiguities': [],
             'translator_notes': 'offline batch fixture'}
            for loc, translation in self.translations
        ]}, {'response_id': 'fake-batch-response'})


class GeminiProseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = gp.load_prose()
        cls.by_loc = gp.load_script()
        cls.by_row = {row['loc']: row for row in cls.rows}
        cls.validator = gp.CandidateValidator(cls.by_loc)

    def test_scope_is_prose_only(self):
        eligible = [row for row in self.rows if gp.classify(row)[0]]
        excluded = [row for row in self.rows if not gp.classify(row)[0]]
        self.assertEqual(519, len(self.rows))
        self.assertEqual(434, len(eligible))
        self.assertEqual(85, len(excluded))
        self.assertTrue(all(row['verbatim'] for row in excluded))

    def test_dialogue_never_resumes_printable_text_after_end(self):
        translations = {}
        with open(gp.EN_PATH, encoding='utf-8') as source_file:
            for raw in source_file:
                if raw.startswith('#') or '\t' not in raw:
                    continue
                loc, value = raw.rstrip('\n').split('\t', 1)
                translations[loc] = value
        bad = []
        for row in self.rows:
            value = translations[row['loc']]
            if re.search(r'<end>(?!(?:<[^>]+>)*$|<brk>)', value):
                bad.append(row['loc'])
        self.assertEqual([], bad)

    def test_dialogue_lint_rejects_printable_text_after_end(self):
        broken = gp.lint_en.check_one('例<end>文', 'He went to rescue<end> Fumi!', 11)
        safe = gp.lint_en.check_one('例<end>文', 'He went to rescue<end><brk> Fumi!', 11)
        self.assertIn('end_resumes_text', {kind for kind, _detail in broken})
        self.assertNotIn('end_resumes_text', {kind for kind, _detail in safe})

    def test_dialogue_lint_rejects_end_before_terminal_break(self):
        broken = gp.lint_en.check_one('コッパ「こわかった」',
                                      'Koppa: That was scary.<end><brk>', 14)
        safe = gp.lint_en.check_one('コッパ「こわかった」',
                                    'Koppa: That was scary.', 14)
        self.assertIn('end_before_terminal_brk',
                      {kind for kind, _detail in broken})
        self.assertNotIn('end_before_terminal_brk',
                         {kind for kind, _detail in safe})

    def test_verified_review_snapshots_match_current_wrapper(self):
        state = gp.load_review()
        for row in self.rows:
            entry = state['entries'][row['loc']]
            if not entry.get('verified'):
                continue
            current = self.validator.validate(row, row['text'])
            self.assertTrue(current['valid'], row['loc'])
            self.assertEqual(current['wrapped_en'], entry['checks']['wrapped_en'], row['loc'])

    def test_bulk_default_uses_high_quota_flash_lite(self):
        self.assertEqual('gemini-3.5-flash-lite', gp.DEFAULT_MODEL)

    def test_review_json_does_not_duplicate_japanese(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'review.json')
            state = gp.sync_review(self.rows, self.by_loc,
                                   {'schema_version': gp.SCHEMA_VERSION, 'entries': {}})
            gp.save_review(state, path)
            with open(path, encoding='utf-8') as source_file:
                serialized = source_file.read()
            first_jp = self.by_loc[self.rows[0]['loc']]['jp']
            self.assertNotIn(first_jp, serialized)
            self.assertIn('source_sha256', serialized)

    def test_clean_init_does_not_rewrite_review_timestamp(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'review.json')
            state = gp.sync_review(self.rows, self.by_loc,
                                   {'schema_version': gp.SCHEMA_VERSION, 'entries': {}})
            state['updated_at'] = 'sentinel-time'
            gp.atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + '\n')
            gp.init_state(path)
            with open(path, encoding='utf-8') as source_file:
                unchanged = json.load(source_file)
            self.assertEqual('sentinel-time', unchanged['updated_at'])

    def test_external_edit_invalidates_candidate(self):
        row = copy.deepcopy(self.rows[0])
        source = self.by_loc[row['loc']]
        entry = gp.fresh_entry(row, source)
        entry.update({'candidate_en': 'Candidate.', 'verified': True, 'state': 'accepted'})
        state = {'schema_version': gp.SCHEMA_VERSION,
                 'entries': {row['loc']: entry}}
        row['raw_text'] += ' changed'
        row['text'] += ' changed'
        synced = gp.sync_review([row], {row['loc']: source}, state)
        result = synced['entries'][row['loc']]
        self.assertFalse(result['verified'])
        self.assertEqual('stale', result['state'])

    def test_prompt_uses_japanese_but_not_target_current_english(self):
        state = gp.sync_review(self.rows, self.by_loc,
                               {'schema_version': gp.SCHEMA_VERSION, 'entries': {}})
        row = self.rows[0]
        terms = gp.translation_terms()
        prompt = gp.prompt_for(row, self.by_loc[row['loc']], self.rows,
                               self.by_loc, state, terms)
        self.assertIn(self.by_loc[row['loc']]['jp'], prompt)
        self.assertNotIn(row['text'], prompt)
        self.assertIn('Yoshizota', prompt)
        self.assertIn("Dragon's Cry Scroll", prompt)
        self.assertIn('Do not retain Japanese honorific suffixes', prompt)

    def test_batch_prompt_is_one_scene_and_hides_target_current_english(self):
        state = gp.sync_review(self.rows, self.by_loc,
                               {'schema_version': gp.SCHEMA_VERSION, 'entries': {}})
        targets = gp.select_batch(self.rows, state, count=8, loc='14:$5281')
        self.assertEqual(['14:$5281', '14:$5294'], [row['loc'] for row in targets])
        prompt = gp.prompt_for_batch(targets, self.rows, self.by_loc, state,
                                     gp.translation_terms())
        self.assertIn(self.by_loc['14:$5281']['jp'], prompt)
        self.assertIn(self.by_loc['14:$5294']['jp'], prompt)
        self.assertNotIn(self.by_row['14:$5281']['text'], prompt)
        self.assertNotIn(self.by_row['14:$5294']['text'], prompt)
        self.assertNotIn(self.by_loc['14:$52B8']['jp'], prompt)

    def test_short_name_and_variant_speaker_prefixes_are_required(self):
        nagi = self.by_row['14:$5BB2']
        seer = self.by_row['14:$57E7']
        self.assertEqual('Nagi:', gp.required_speaker_prefix(
            nagi, self.by_loc[nagi['loc']]))
        self.assertEqual('Old Seer:', gp.required_speaker_prefix(
            seer, self.by_loc[seer['loc']]))
        result = self.validator.validate(nagi, 'Grandpaaa!')
        self.assertFalse(result['valid'])
        self.assertIn('speaker_prefix',
                      {problem['kind'] for problem in result['problems']})

    def test_batch_payload_requires_exact_order_and_no_missing_rows(self):
        expected = ['14:$5281', '14:$5294']
        payload = {'translations': [
            {'loc': loc, 'translation': 'Okay.', 'ambiguities': [],
             'translator_notes': ''} for loc in reversed(expected)
        ]}
        with self.assertRaisesRegex(ValueError, 'exactly match input order'):
            gp.validate_batch_payload(payload, expected)

    def test_existing_reviewed_translation_passes_production_validator(self):
        row = self.rows[0]
        result = self.validator.validate(row, row['text'])
        self.assertTrue(result['valid'], result['problems'])
        self.assertIsNotNone(result['wrapped_en'])

    def test_source_required_content_line_breaks_must_be_preserved(self):
        row = self.by_row['14:$4905']
        result = self.validator.validate(row, row['text'])
        self.assertTrue(result['valid'], result['problems'])
        missing = self.validator.validate(row, row['text'].replace('<br>', ' ', 1))
        self.assertFalse(missing['valid'])
        self.assertIn('authored_layout',
                      {problem['kind'] for problem in missing['problems']})

    def test_source_backed_prose_term_loads(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'terms.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('term\tTerm\tofficial-wiki\thttps://example.test/wiki/term'
                          '\tOfficial English listing.\n')
            self.assertEqual([('term', 'Term')], gp.load_prose_terms(path))

    def test_explicit_project_owner_term_loads_without_official_claim(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'terms.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('term\tTerm\tproject-owner\tconversation:2026-08-10'
                          '\tExplicit wording decision.\n')
            self.assertEqual([('term', 'Term')], gp.load_prose_terms(path))

    def test_unsourced_prose_term_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'terms.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('term\tTerm\tExisting patch wording.\n')
            with self.assertRaisesRegex(ValueError, 'expected japanese'):
                gp.load_prose_terms(path)

    def test_unapproved_prose_term_authority_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'terms.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('term\tTerm\tcurrent-patch\thttps://example.test/term'
                          '\tExisting wording.\n')
            with self.assertRaisesRegex(ValueError, 'unsupported authority'):
                gp.load_prose_terms(path)

    def test_project_owner_term_requires_dated_conversation_source(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'terms.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('term\tTerm\tproject-owner\tcurrent-patch\tExisting wording.\n')
            with self.assertRaisesRegex(ValueError, 'conversation:YYYY-MM-DD'):
                gp.load_prose_terms(path)

    def test_dropped_semantic_token_fails(self):
        row = next(row for row in self.rows
                   if '<name>' in row['text'] and not row['verbatim'])
        result = self.validator.validate(row, row['text'].replace('<name>', '', 1))
        self.assertFalse(result['valid'])
        self.assertIn('token_lost', {problem['kind'] for problem in result['problems']})

    def test_trailing_authored_page_break_fails(self):
        row = self.by_row['11:$6A42']
        unsafe = row['text'].replace('<brk>', '') + '<brk>'
        result = self.validator.validate(row, unsafe)
        self.assertFalse(result['valid'])
        self.assertIn('trailing_brk',
                      {problem['kind'] for problem in result['problems']})

    def test_dropped_raw_argument_fails(self):
        row = next(row for row in self.rows
                   if gp.token_counter(row['text'], raw=True) and not row['verbatim'])
        token = next(iter(gp.token_counter(row['text'], raw=True)))
        result = self.validator.validate(row, row['text'].replace(token, '', 1))
        self.assertFalse(result['valid'])
        self.assertIn('raw_token_parity',
                      {problem['kind'] for problem in result['problems']})

    def test_text_inside_runtime_argument_sequence_fails(self):
        row = self.by_row['14:$4F36']
        unsafe = row['text'].replace('<mode1><$3C>', '<mode1>Agh!<$3C>')
        result = self.validator.validate(row, unsafe)
        self.assertFalse(result['valid'])
        self.assertIn('control_argument',
                      {problem['kind'] for problem in result['problems']})

    def test_reordered_controls_fail_even_when_counts_match(self):
        row = self.by_row['14:$4F36']
        unsafe = row['text'].replace('<cE7><mode0>', '<mode0><cE7>')
        result = self.validator.validate(row, unsafe)
        self.assertFalse(result['valid'])
        self.assertIn('control_order',
                      {problem['kind'] for problem in result['problems']})

    def test_fake_client_never_needs_credentials_or_network(self):
        fake = FakeClient(self.rows[0]['text'])
        payload, meta = gp.request_candidate(fake, gp.DEFAULT_MODEL, 'fixture prompt')
        self.assertEqual(self.rows[0]['text'], payload['translation'])
        self.assertEqual('fake-response', meta['response_id'])
        self.assertEqual([(gp.DEFAULT_MODEL, 'fixture prompt', gp.RESPONSE_SCHEMA)], fake.calls)

    def test_fake_batch_client_returns_independent_rows_without_network(self):
        translations = [('14:$5281', self.by_row['14:$5281']['text']),
                        ('14:$5294', self.by_row['14:$5294']['text'])]
        fake = FakeBatchClient(translations)
        payloads, meta = gp.request_batch(fake, gp.DEFAULT_MODEL, 'fixture batch prompt',
                                          [loc for loc, _text in translations])
        self.assertEqual([loc for loc, _text in translations],
                         [payload['loc'] for payload in payloads])
        self.assertEqual('fake-batch-response', meta['response_id'])
        self.assertIs(fake.calls[0][2], gp.BATCH_RESPONSE_SCHEMA)

    def test_batch_validation_keeps_partial_failures_per_entry(self):
        good_row = self.by_row['14:$5281']
        bad_row = self.by_row['14:$5294']
        state = {'entries': {
            good_row['loc']: gp.fresh_entry(good_row, self.by_loc[good_row['loc']]),
            bad_row['loc']: gp.fresh_entry(bad_row, self.by_loc[bad_row['loc']]),
        }}
        good = self.validator.validate(good_row, good_row['text'])
        bad = self.validator.validate(bad_row, bad_row['text'].replace('<name>', 'Shiren'))
        gp.store_candidate(good_row, state,
                           {'ambiguities': [], 'translator_notes': ''}, good,
                           gp.DEFAULT_MODEL, {}, batch_size=2, batch_index=0)
        gp.store_candidate(bad_row, state,
                           {'ambiguities': [], 'translator_notes': ''}, bad,
                           gp.DEFAULT_MODEL, {}, batch_size=2, batch_index=1)
        self.assertEqual('candidate', state['entries'][good_row['loc']]['state'])
        self.assertEqual('fit_failed', state['entries'][bad_row['loc']]['state'])

    def test_response_shape_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            gp.validate_payload({'translation': 'Okay.', 'ambiguities': [],
                                 'translator_notes': '', 'surprise': True})

    def test_tsv_replacement_is_exactly_one_row(self):
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            path = os.path.join(directory, 'sample.tsv')
            with open(path, 'w', encoding='utf-8') as out:
                out.write('# comment\n11:$4000\tOld\n11:$4001\tOther\n')
            changed = gp.replace_tsv_row(path, '11:$4000', 'New')
            self.assertIn('11:$4000\tNew\n', changed)
            self.assertIn('11:$4001\tOther\n', changed)

    def test_accept_updates_both_tsvs_and_verified_state(self):
        row = self.rows[0]
        result = self.validator.validate(row, row['text'])
        source = self.by_loc[row['loc']]
        state = {'schema_version': gp.SCHEMA_VERSION,
                 'entries': {row['loc']: gp.fresh_entry(row, source)}}
        with tempfile.TemporaryDirectory(prefix='gemini-prose-test-') as directory:
            prose_path = os.path.join(directory, 'prose.tsv')
            en_path = os.path.join(directory, 'en.tsv')
            review_path = os.path.join(directory, 'review.json')
            with open(prose_path, 'w', encoding='utf-8') as out:
                out.write('# prose\n%s\tOld prose\n' % row['loc'])
            with open(en_path, 'w', encoding='utf-8') as out:
                out.write('# en\n%s\tOld wrapped\n' % row['loc'])
            old_prose, old_en = gp.PROSE_PATH, gp.EN_PATH
            try:
                gp.PROSE_PATH, gp.EN_PATH = prose_path, en_path
                gp.accept(row, state, result, review_path, run_checks=False)
            finally:
                gp.PROSE_PATH, gp.EN_PATH = old_prose, old_en
            self.assertTrue(state['entries'][row['loc']]['verified'])
            with open(prose_path, encoding='utf-8') as source_file:
                self.assertIn(row['text'], source_file.read())
            with open(en_path, encoding='utf-8') as source_file:
                self.assertIn(result['wrapped_en'], source_file.read())

    def test_triage_report_contains_only_unresolved_decisions(self):
        row, accepted = self.rows[0], self.rows[1]
        state = {'entries': {
            row['loc']: gp.fresh_entry(row, self.by_loc[row['loc']]),
            accepted['loc']: gp.fresh_entry(accepted, self.by_loc[accepted['loc']]),
        }}
        state['entries'][row['loc']].update({
            'state': 'needs_user',
            'candidate_en': 'Candidate wording.',
            'ambiguities': ['Which title?'],
            'review_notes': 'Choose a title.',
        })
        state['entries'][accepted['loc']].update({
            'state': 'accepted', 'verified': True, 'candidate_en': accepted['text'],
        })
        report = gp.triage_tsv([row, accepted], self.by_loc, state)
        self.assertIn(self.by_loc[row['loc']]['jp'], report)
        self.assertIn('Candidate wording.', report)
        self.assertIn('Choose a title.', report)
        self.assertNotIn(self.by_loc[accepted['loc']]['jp'], report)


if __name__ == '__main__':
    unittest.main()
