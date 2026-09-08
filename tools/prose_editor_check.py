#!/usr/bin/env python3
"""Prose editor import regressions and Python oracles for the browser checks.

Run this, serve with prose_editor.py serve --test, then open /prose/checks.html.
No ROM is rebuilt and no project translation is changed.
"""
import json
from pathlib import Path
import re
import tempfile

import build
import build_site
import dialogue_preview as dialogue
import dotfont
import prose_editor as editor
import textlayout
import wrap_en


def expect_failure(action, label):
    try:
        action()
    except ValueError:
        return
    raise AssertionError(label)


def tsv(data, edits):
    rows = {row['loc']: row for row in data['records']}
    lines = [f'# format\t{editor.FORMAT}', f'# revision\t{data["revision"]}',
             f'# rules\t{data["rulesRevision"]}']
    lines += [f'# base\t{loc}\t{rows[loc]["base"]}' for loc in edits]
    lines += [f'{loc}\t{text}' for loc, text in edits.items()]
    return '\n'.join(lines) + '\n'


def line_oracle(record, compiled, native, font):
    encoded = build.encode_en(textlayout.renderer_text(compiled, bytes.fromhex(native['hex'])), native['bank'])
    controls = dialogue.dot_production_widths(font)
    rows = []
    for line in dialogue.split_lines(encoded, native['bank']):
        advance, extent, _ = dialogue.dot_metrics(line.data, font, native['bank'], controls)
        rows.append({'box': line.box, 'row': line.row, 'advance': advance, 'extent': extent,
                     'cells': line.cells(dialogue.production_widths()),
                     'buffer': dialogue.buffer_bytes(line.data, widths=dialogue.production_widths(), bank=native['bank'])})
    return rows


def main():
    data = editor.catalogue()
    assert json.loads(editor.CATALOG.read_text()) == json.loads(json.dumps(data)), 'Regenerate catalog.json first'
    assert not re.search('[\u3040-\u30ff\u4e00-\u9fff]', json.dumps(data, ensure_ascii=False)), 'Japanese belongs in the separate source TSV'
    public = {name: (build_site.SOURCE / name).read_bytes() for name in build_site.PUBLIC_FILES}
    source_tsv = public[build_site.SOURCE_TSV]
    assert source_tsv == (editor.ROOT / 'script/script.tsv').read_bytes(), 'Refresh the bundled source TSV'
    build_site.validate(public)
    lines = source_tsv.decode('utf-8').splitlines()
    source_line = next(line for line in lines if '\t14:$5037\t' in line)
    bad = dict(public)
    for label, replacement in [
        ('missing source', ''),
        ('missing prose row', '\n'.join(line for line in lines if line != source_line)),
        ('duplicate source row', source_tsv.decode('utf-8') + source_line + '\n'),
        ('wrong Japanese source', source_tsv.decode('utf-8').replace(source_line, source_line.replace(source_line.split('\t')[3], 'Wrong source'))),
    ]:
        bad[build_site.SOURCE_TSV] = replacement.encode('utf-8')
        expect_failure(lambda: build_site.validate(bad), f'Packager accepted {label}')
    assert len(data['records']) == 480 and sum(row['editable'] for row in data['records']) == 436
    assert {loc for event in data['events'] for loc in event['locs']} == {row['loc'] for row in data['records']}
    native = editor.read_manifest()
    font = dotfont.load_approved()
    by_loc = {row['loc']: row for row in data['records']}
    baseline, wrapping = [], []
    for row in data['records']:
        baseline.append({'loc': row['loc'], 'compiled': row['current'],
                         'lines': line_oracle(row, row['current'], native[row['loc']], font)})
        if not row['editable']:
            continue
        editor.compile_draft(row, row['draft'], native[row['loc']], data)
        def measure(text):
            return dialogue.dot_metrics(build.encode_en(text, row['bank']), font, row['bank'],
                                        dialogue.dot_production_widths(font))[:2]
        compiled, _ = wrap_en.wrap(row['draft'], terminal_end=row['terminalSuffix'], measure=measure,
                                  pixel_limit=144, first_indent=row['sourceIndent'])
        wrapping.append({'loc': row['loc'], 'compiled': compiled,
                         'lines': line_oracle(row, compiled, native[row['loc']], font)})

    loc = '14:$5037'
    edited = "Keyaki: You're awake!"
    assert by_loc[loc]['editable'] and edited != by_loc[loc]['draft']
    text = tsv(data, {loc: edited})
    paths = [editor.ROOT / 'script/prose_draft.tsv', editor.ROOT / 'script/en.tsv']
    before = {path: path.read_bytes() for path in paths}
    changed, outputs = editor.prepare_import(text, data)
    assert changed == {loc: edited}
    assert all(path.read_bytes() == value for path, value in before.items()), 'dry run changed translations'
    for path, (old, new) in outputs.items():
        old_rows = dict(wrap_en.load_draft(path))
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'candidate.tsv'; candidate.write_text(new)
            new_rows = dict(wrap_en.load_draft(candidate))
        assert {key for key in old_rows if old_rows[key] != new_rows[key]} == {loc}
    expect_failure(lambda: editor.prepare_import(text.replace(by_loc[loc]['base'], '0' * 64), data), 'stale base accepted')
    expect_failure(lambda: editor.prepare_import(text + f'{loc}\t{edited}\n', data), 'duplicate accepted')
    expect_failure(lambda: editor.prepare_import(text.replace(data['rulesRevision'], '0' * 64), data), 'stale rules accepted')
    expect_failure(lambda: editor.prepare_import(tsv(data, {loc: 'A' * 40}), data), 'overflow accepted')
    expect_failure(lambda: editor.prepare_import(tsv(data, {loc: 'é'}), data), 'unsupported glyph accepted')
    expect_failure(lambda: editor.prepare_import(tsv(data, {'14:$51D3': 'Keyaki: Wait up!'}), data), 'lost player token accepted')
    locked = next(row for row in data['records'] if not row['editable'])
    expect_failure(lambda: editor.prepare_import(tsv(data, {locked['loc']: 'Changed'}), data), 'read-only row accepted')
    expect_failure(lambda: editor.prepare_import(tsv(data, {loc: 'Keyaki:\tHello'}), data), 'extra tab accepted')
    expect_failure(lambda: editor.prepare_import(tsv(data, {loc: '=Hello'}), data), 'verbatim bypass accepted')
    # English glossary enforcement remains a project gate, beyond the browser fit model.
    expect_failure(lambda: editor.prepare_import(tsv(data, {'14:$4BF6': "Someone read the Dragon's Cry Scroll."}), data), 'glossary drift accepted')
    with tempfile.TemporaryDirectory() as directory:
        first, second = Path(directory) / 'draft.tsv', Path(directory) / 'en.tsv'
        first.write_text('old draft'); second.write_text('old en')
        first.chmod(0o640)
        editor.apply_import({first: ('old draft', 'new draft'), second: ('old en', 'new en')})
        assert first.read_text() == 'new draft' and second.read_text() == 'new en'
        expect_failure(lambda: editor.apply_import({first: ('stale', 'bad')}), 'concurrent change overwritten')
        assert first.read_text() == 'new draft'
        assert first.stat().st_mode & 0o777 == 0o640
        original_replace = Path.replace
        def fail_second(temporary, target):
            if target == second:
                raise OSError('simulated second-file replacement failure')
            return original_replace(temporary, target)
        Path.replace = fail_second
        try:
            try:
                editor.apply_import({first: ('new draft', 'bad draft'), second: ('new en', 'bad en')})
            except OSError:
                pass
            else:
                raise AssertionError('replacement failure was not propagated')
        finally:
            Path.replace = original_replace
        assert first.read_text() == 'new draft' and second.read_text() == 'new en', 'failed import did not roll back'
        assert not list(Path(directory).glob('.prose-import-*')), 'staged files left behind'
    # Independent edge cases check painted tails, source/indent limits and argument bytes.
    metrics = []
    for text in ['i' * 30, 'i' * 31, 'W' * 24 + '!', 'W' * 25, ' ' + 'i' * 30,
                 '<name>!', '<cE3:05>!', '<mode1><$3C>Hi<mode0>', 'Hi ', '<cE7>Hi<cF0>']:
        encoded = build.encode_en(text, 14)
        advance, extent, _ = dialogue.dot_metrics(encoded, font, 14, dialogue.dot_production_widths(font))
        metrics.append({'text': text, 'advance': advance, 'extent': extent,
                        'cells': dialogue.Line(encoded, 'end', 0, 0, 14).cells(dialogue.production_widths())})
    oracle = {'revision': data['revision'], 'baseline': baseline, 'wrapping': wrapping,
              'metrics': metrics, 'validEdit': {'loc': loc, 'text': edited, 'tsv': tsv(data, {loc: edited})}}
    destination = editor.ROOT / 'build/prose-editor-oracle.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(oracle, ensure_ascii=False))
    print(f'PASS: bundled source integrity, {len(baseline)} baseline records, {len(wrapping)} editable drafts, '
          'changed-row import, glossary/fit/token rejection, conflict handling and isolated apply.')
    print('Browser oracle: build/prose-editor-oracle.json. Open /prose/checks.html on the test preview.')


if __name__ == '__main__':
    main()
