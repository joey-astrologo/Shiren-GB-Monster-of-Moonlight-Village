#!/usr/bin/env python3
"""Check catalogue coverage/imports and generate browser fixtures from build tools."""
import copy
import json
from pathlib import Path
import tempfile

import build_site
import workbench as w


def tsv(data, edits):
    records = {r['key']: r for r in data['records']}
    return '\n'.join([f'# format\t{w.FORMAT}', f'# revision\t{data["revision"]}', f'# rules\t{data["rulesRevision"]}'] +
                     [f'# base\t{k}\t{records[k]["base"]}' for k in edits] + ['# key\tenglish'] +
                     [f'{k}\t{v}' for k, v in edits.items()]) + '\n'


def rejects(fn, label):
    try: fn()
    except (ValueError, KeyError): return
    raise AssertionError(label)


def main():
    data = w.catalogue(); records = {r['key']: r for r in data['records']}
    assert data == json.loads(w.CATALOG.read_text()), 'Regenerate the workbench catalogue'
    assert not w.validate_all(data, {}), 'Current project text must pass'
    assert len(data['coverage']) == 1424 and len(records) == 1000
    assert sum(r['editable'] for r in records.values()) == 972
    public = {name: (build_site.SOURCE / name).read_bytes() for name in build_site.PUBLIC_FILES}
    build_site.validate(public)
    for label, mutate in [
        ('missing coverage', lambda d: d['coverage'].pop()),
        ('duplicate coverage', lambda d: d['coverage'].append(d['coverage'][0])),
        ('wrong owner', lambda d: d['coverage'][0].update(subject='items')),
        ('missing record', lambda d: d['records'].pop()),
        ('wrong source', lambda d: d['records'][0].update(jp='different')),
        ('wrong count', lambda d: d['subjects'][0].update(count=0)),
        ('stale rules', lambda d: d.update(rulesRevision='0' * 64)),
    ]:
        bad = copy.deepcopy(data); mutate(bad); bad.pop('revision')
        bad['revision'] = w.digest(json.dumps(bad, ensure_ascii=False, sort_keys=True))
        files = dict(public); files['workbench/catalog.json'] = json.dumps(bad).encode()
        rejects(lambda: build_site.validate(files), label)
    for payload in (b'', public['data/intro.tsv'] + public['data/intro.tsv'].splitlines()[-1] + b'\n'):
        files = dict(public); files['data/intro.tsv'] = payload
        rejects(lambda: build_site.validate(files), 'Malformed cinematic source was accepted')

    baseline = {key: w.validate_row(row, row['current'], data)['lines'] for key, row in records.items()}
    cases = []
    def case(key, value, label):
        result = w.validate_row(records[key], value, data)
        cases.append({'key': key, 'text': value, 'label': label, 'valid': not result['errors'], 'lines': result['lines']})
    for subject in data['subjects']:
        if subject['id'] in ('prose', 'reference'): continue
        row = next(r for r in records.values() if r['subject'] == subject['id'])
        case(row['key'], row['current'], subject['id'] + ' accepted baseline')
        case(row['key'], row['current'] + 'W' * 50, subject['id'] + ' overflow/slots')
        case(row['key'], row['current'] + 'é', subject['id'] + ' unsupported glyph')
        case(row['key'], row['current'] + '\n', subject['id'] + ' literal newline')
        case(row['key'], '<$01>' + row['current'], subject['id'] + ' injected raw byte')
    for key in ('30:$7F02', '31:$41D0', '31:$422F', '31:$441B', '31:$4549', '11:$53C1'):
        for n in (1, 4, 8, 12, 17, 18, 19, 22, 30):
            case(key, 'W' * n, key + ' scanner/pixel/allocation boundary ' + str(n))
    for row in records.values():
        if row['editable'] and row['subject'] != 'cinematic' and row['controls']:
            token = row['controls'][0]
            case(row['key'], row['current'].replace(token, '', 1), 'required token removed')
    for key in ('13:$4571', '11:$7257'):
        row = records[key]; token = row['controls'][0]
        case(key, 'i' + row['current'], 'leading producer moved')
        case(key, row['current'].replace(token, '<cE3:01:02>', 1), 'wrong bank arity')
    choice = records['14:$541F']
    case(choice['key'], choice['current'].replace('<$81>Sure', 'Sure<$81>'), 'choice cursor may not move after its label')
    assert not cases[-1]['valid'], 'Choice cursor moved inside a label without rejection'
    counter = next(r for r in records.values() if r['profile'].get('suffix') == 'counter')
    case(counter['key'], 'i' * 16, 'renaming cannot remove the native counter class')
    for key in ('11:$444E', '11:$447C', '11:$44FB'):
        assert records[key]['profile']['suffix'] == 'counter', 'Unused staff/pot slots retain their category'
        case(key, 'i' * 16, 'placeholder counter survives rename')
    case('intro_02', 'Short.', 'cinematic may not leave a screen slot empty')
    case('intro_08', 'Look!<br>There!', 'cinematic page count retained')
    locked = next(r for r in records.values() if not r['editable'])
    case(locked['key'], 'New text', 'reference is not editable')

    batches = []
    def batch(edits, label):
        errors = w.validate_all(data, edits)
        batches.append({'edits': edits, 'label': label, 'invalid': sorted(errors)})
        return errors
    assert batch({'11:$55C6': 'W' * 22}, 'shared fragment invalidates unchanged help')
    assert batch({r['key']: 'W' * 20 for r in records.values() if r['subject'] == 'conditions'}, 'any-five condition allocation')
    duplicate = next(r for r in records.values() if r.get('nameClass') == 'monster' and sum(o['jp'] == r['jp'] for o in records.values()) > 1)
    assert batch({duplicate['key']: 'Different'}, 'duplicate Japanese name agreement')
    assert batch({counter['key']: 'i' * 16}, 'counter scanner retained after rename')
    assert batch({'13:$46AC': 'Carefully consumed <cE3>'}, 'herb producer domain')
    assert batch({'11:$4012': 'W' * 15}, 'item suffix and consuming message')
    valid_edits = {'30:$7EC6': 'Use', 'intro_01': 'Mom: My child...', '11:$401E': 'New Blade 3',
                   '11:$7246': "Fumi's Mom: Um... have<br> this.<end><mode0>"}
    assert not batch(valid_edits, 'valid edits spanning four destinations')
    before = {p: p.read_bytes() for p in [w.ROOT / 'script' / (name + '.tsv') for name in ('en', 'glossary', 'prose_draft', 'intro')]}
    changes, outputs = w.prepare_import(tsv(data, valid_edits))
    assert changes == valid_edits and len(outputs) == 4
    assert all(p.read_bytes() == original for p, original in before.items()), 'Dry run modified project files'
    assert '\titem\tしんきぶき3\tNew Blade 3\n' in outputs[w.ROOT / 'script/glossary.tsv'][1]
    assert "11:$7246\t=Fumi's Mom: Um... have<br> this.<end><mode0>\n" in outputs[w.ROOT / 'script/prose_draft.tsv'][1]
    prose = w.prose_editor.catalogue(); ordinary = next(r for r in prose['records'] if r['loc'] == '14:$5037')
    prose_edit = "Keyaki: You're awake!"
    combined = '\n'.join([f'# format\t{w.prose_editor.FORMAT}', f'# revision\t{prose["revision"]}', f'# rules\t{prose["rulesRevision"]}',
                          f'# base\t{ordinary["loc"]}\t{ordinary["base"]}', f'{ordinary["loc"]}\t{prose_edit}']) + '\n'
    merged_changes, merged_outputs = w.prepare_import(tsv(data, valid_edits), combined)
    assert merged_changes[ordinary['loc']] == prose_edit and len(merged_changes) == 5
    assert f'{ordinary["loc"]}\t{prose_edit}\n' in merged_outputs[w.ROOT / 'script/prose_draft.tsv'][1]
    assert all(p.read_bytes() == original for p, original in before.items()), 'Combined dry run modified translations'
    # Apply only to isolated files; the shared transactional writer is exercised with
    # every destination, while current project translations stay byte-identical.
    with tempfile.TemporaryDirectory() as directory:
        isolated = {}
        for path, pair in outputs.items():
            target = Path(directory) / path.name; target.write_text(pair[0]); isolated[target] = pair
        w.prose_editor.apply_import(isolated)
        assert all(path.read_text() == pair[1] for path, pair in isolated.items())
    good = tsv(data, {'30:$7EC6': 'Use'})
    for bad in (good.replace(data['rulesRevision'], '0' * 64), good.replace(records['30:$7EC6']['base'], '0' * 64), good + '30:$7EC6\tUse\n',
                tsv(data, {locked['key']: locked['current']}), tsv(data, {'30:$7EC6': 'W' * 30})):
        rejects(lambda: w.prepare_import(bad), 'Unsafe import accepted')
    # The fixture contains no ROM bytes: only public text and measurements.
    oracle = {'revision': data['revision'], 'baseline': baseline, 'cases': cases, 'batches': batches,
              'validEdits': valid_edits, 'validTSV': tsv(data, valid_edits)}
    target = w.ROOT / 'site/workbench/checks-oracle.json'
    target.write_text(json.dumps(oracle, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Coverage/import checks passed; {len(baseline)} baselines, {len(cases)} edits and {len(batches)} dependency fixtures for the browser.')


if __name__ == '__main__': main()
