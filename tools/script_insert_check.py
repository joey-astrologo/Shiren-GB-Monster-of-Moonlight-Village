#!/usr/bin/env python3
"""Check spreadsheet imports and failure recovery using isolated destination files.

The real validators run against the current project. Small build fixtures exercise
the transaction boundary; they are not a substitute for a full sh build.sh run.
"""
import copy
from pathlib import Path
import tempfile

import build
import fontaudit
import prose_editor
import script_dump as dump
import script_insert as insert
import textlayout


def rejects(action, label):
    try:
        action()
    except (ValueError, RuntimeError, OSError):
        return
    raise AssertionError(label)


def main():
    baseline = dump.dump_rows()
    native = prose_editor.read_manifest()
    prose = prose_editor.catalogue()
    prose_rows = {row['loc']: row for row in prose['records']}
    manifest = {'strings': list(native.values())}
    translated, _, unknown = fontaudit.load_translations(
        manifest, str(insert.ROOT / 'script/en.tsv'), str(insert.ROOT / 'script/glossary.tsv'))
    encoded, errors = fontaudit.encoded_translations(manifest['strings'], translated)
    assert not unknown and not errors
    checked_prose = 0
    for row in baseline:
        loc = row['loc']
        if loc not in native or native[loc]['id'] not in encoded:
            continue
        authored = insert.authored_text(row['en'], bytes.fromhex(native[loc]['hex']))
        assert build.encode_en(textlayout.renderer_text(authored, bytes.fromhex(native[loc]['hex'])),
                               native[loc]['bank']) == encoded[native[loc]['id']], loc
        if loc in prose_rows and prose_rows[loc]['editable']:
            draft = insert.prose_draft(authored, prose_rows[loc])
            prose_editor.compile_draft(prose_rows[loc], draft, native[loc], prose)
            checked_prose += 1
    assert checked_prose == 436
    before = {insert.ROOT / 'script' / (name + '.tsv'): (insert.ROOT / 'script' / (name + '.tsv')).read_bytes()
              for name in ('en', 'glossary', 'prose_draft', 'intro', 'script_full')}
    with tempfile.TemporaryDirectory(prefix='shiren-script-insert-check-') as directory:
        root = Path(directory)
        sheet = root / 'edits.tsv'

        def write(edits=None, mutate=None):
            rows = copy.deepcopy(baseline)
            for row in rows:
                if edits and row['loc'] in edits:
                    row['edited_en'] = edits[row['loc']]
            if mutate:
                mutate(rows)
            sheet.write_bytes(dump.serialize(rows))

        write()
        assert insert.prepare_import(sheet) == ({}, {})
        write(mutate=lambda rows: [row.update(edited_en=row['en']) for row in rows])
        assert insert.prepare_import(sheet) == ({}, {}), 'Copied references must be no-ops'
        assert insert.read_proposals(sheet, baseline) == {}
        for field in dump.FIELDS[:-1]:
            write(mutate=lambda rows, field=field: rows[2].update({field: 'Wrong'}))
            rejects(lambda: insert.prepare_import(sheet), f'Modified {field} accepted')
        for label, mutate in (
            ('missing row', lambda rows: rows.pop()),
            ('duplicate row', lambda rows: rows.append(dict(rows[0]))),
            ('unknown address', lambda rows: rows[0].update(loc='0:$1234')),
        ):
            write(mutate=mutate)
            rejects(lambda: insert.prepare_import(sheet), label)

        for loc, text in (
            ('14:$5037', '   '), ('14:$5037', 'Bad\nline'), ('14:$5037', 'Bad\tfield'),
            ('14:$5037', 'é'), ('14:$5037', 'W' * 40),
            ('14:$5037', 'Keyaki: Hi.<end>More text'),
            ('14:$51D3', 'Keyaki: Wait up!'),
            ('30:$7EC6', 'W' * 50), ('30:$7EC6', '<br>Read'),
            ('31:$5D1A', 'Short.'), ('31:$5E46', 'Look!<br>There!'),
            ('11:$55C6', 'W' * 22), ('11:$4012', 'W' * 15),
            ('3:$4E4F', 'Edit a reference'),
        ):
            write({loc: text})
            rejects(lambda: insert.prepare_import(sheet), f'Unsafe edit accepted: {loc} {text!r}')

        def rendered(loc, text):
            return textlayout.renderer_text(text, bytes.fromhex(native[loc]['hex']))

        # Five edits span all four destinations and exercise a joint prose/workbench
        # import. The pending row lives in edited_en; the baseline en stays intact.
        edits = {'30:$7EC6': rendered('30:$7EC6', 'Use'), '31:$5CEF': 'Mom: My child...',
                 '11:$401E': rendered('11:$401E', 'New Blade 3'),
                 '11:$7246': rendered('11:$7246', "Fumi's Mom: Um... have<br> this.<end><mode0>"),
                 '14:$5037': rendered('14:$5037', "Keyaki: You're awake!")}
        write(edits)
        changes, outputs = insert.prepare_import(sheet)
        assert len(changes) == 5 and len(outputs) == 4
        assert "14:$5037\tKeyaki: You're awake!\n" in outputs[insert.ROOT / 'script/prose_draft.tsv'][1]
        assert "11:$7246\t=Fumi's Mom: Um... have<br> this.<end><mode0>\n" in outputs[insert.ROOT / 'script/prose_draft.tsv'][1]
        assert '\titem\tしんきぶき3\tNew Blade 3\n' in outputs[insert.ROOT / 'script/glossary.tsv'][1]
        assert 'Mom: My child...' in outputs[insert.ROOT / 'script/intro.tsv'][1]
        write(edits, lambda rows: rows.reverse())
        assert insert.prepare_import(sheet) == (changes, outputs), 'Sorting the spreadsheet changed its import'
        sheet.write_bytes(sheet.read_bytes().replace(b'\n', b'\r\n'))
        assert insert.prepare_import(sheet) == (changes, outputs), 'CRLF export changed the import'

        # A prose-only import must take its own validation path and retain drafts.
        write({'14:$5037': edits['14:$5037']})
        prose_changes, prose_outputs = insert.prepare_import(sheet)
        assert len(prose_changes) == 1 and len(prose_outputs) == 2
        # The inserted selector continuation has two spaces; en.tsv stores one.
        choice = '<cEC:08>Can I ask a favor?<br><$81>Yes<br> No'
        write({'14:$541F': rendered('14:$541F', choice)})
        _, choice_outputs = insert.prepare_import(sheet)
        assert '14:$541F\t' + choice + '\n' in choice_outputs[insert.ROOT / 'script/en.tsv'][1]
        write({'14:$541F': rendered('14:$541F', choice).replace('<br>  No', '<br> No')})
        rejects(lambda: insert.prepare_import(sheet), 'Lost selector space accepted')
        indented = next(row for row in baseline if row['loc'] in native and row['en']
                        and textlayout.source_indent(bytes.fromhex(native[row['loc']]['hex'])))
        rejects(lambda: insert.authored_text(indented['en'][1:], bytes.fromhex(native[indented['loc']]['hex'])),
                'Lost native leading space accepted')

        (root / 'script').mkdir()
        (root / 'build').mkdir()
        isolated = {root / 'script' / path.name: pair for path, pair in outputs.items()}
        for path, pair in isolated.items():
            path.write_text(pair[0])
        artifacts = {root / 'build' / name: ('old ' + name).encode() for name in insert.ARTIFACTS}
        for path, payload in artifacts.items():
            path.write_bytes(payload)
        build_body = ('cp script/en.tsv build/shiren_en.gb\n'
                      'cp script/glossary.tsv build/shiren_en.ips\n'
                      'cp script/intro.tsv build/shiren_en.gb.relocmap.tsv\n'
                      'cp script/prose_draft.tsv build/shiren_en.gb.ram\n'
                      'printf "diagnostic retained\\n" > build/diagnostic.txt\n')
        (root / 'build.sh').write_text('set -e\n' + build_body + 'exit 23\n')
        rejects(lambda: insert.apply_and_build(isolated, root), 'Failed build reported success')
        assert all(path.read_text() == pair[0] for path, pair in isolated.items())
        assert all(path.read_bytes() == payload for path, payload in artifacts.items())
        assert (root / 'build/diagnostic.txt').exists()
        # Restore absence too: a failed first build must not leave new release files.
        for path in artifacts:
            path.unlink()
        rejects(lambda: insert.apply_and_build(isolated, root), 'Failed first build reported success')
        assert not any(path.exists() for path in artifacts)
        assert all(path.read_text() == pair[0] for path, pair in isolated.items())
        (root / 'build.sh').write_text('exit 0\n')
        rejects(lambda: insert.apply_and_build(isolated, root), 'Missing release outputs reported success')
        (root / 'build.sh').write_text('set -e\n' + build_body)
        insert.apply_and_build(isolated, root)
        assert all(path.read_text() == pair[1] for path, pair in isolated.items())
        assert (root / 'build/shiren_en.gb').read_text() == isolated[root / 'script/en.tsv'][1]
        rejects(lambda: insert.apply_and_build(isolated, root), 'Concurrent project change overwritten')

    assert all(path.read_bytes() == content for path, content in before.items()), 'Checks changed project inputs'
    print(f'Passed: {len(encoded)} insertion round trips, {checked_prose} prose conversions, '
          'spreadsheet references/controls/layout, all destinations, no-op edits, sorting/CRLF, '
          'and successful/failed build transactions. Project translations unchanged.')


if __name__ == '__main__':
    main()
