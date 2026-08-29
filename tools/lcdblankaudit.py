#!/usr/bin/env python3
"""Catalogue every LCDC mutator and govern translation-added whole-LCD blankers.

The Japanese ROM writes ``$FF40`` from many shared hardware paths. A write site is not
automatically a blanker: some set bit 7, while many publish a cached LCDC value whose
runtime state depends on the caller. The English build also adds writers for new screen
transactions and conservative menu fallbacks.

This audit has three deliberately separate products:

* every ``ldh [$FF40],a`` / ``ld [$FF40],a`` site and direct
  ``ld hl,$FF40`` + ``res/set 7,[hl]`` mutation is emitted to TSV, so native and
  translation-owned control flow stays enumerable; and
* every direct mutation of the native LCDC shadow at ``$C110`` is emitted too, because
  VBlank's generic ``0:$0737`` publisher turns a shadow bit-7 clear into a hardware
  blank later; and
* every translation-added site which *explicitly* clears bit 7 immediately before the
  write must appear in ``TRANSLATION_OFF`` below. An unclassified explicit blanker is a
  build failure.

Runtime fixtures remain responsible for proving which variable-value native writers
actually turn the LCD off on a particular route. Static provenance and dynamic route
coverage answer different questions and neither replaces the other.
"""
import argparse
import csv
import os


BANK_SIZE = 0x4000


# (bank, write address): (owner, route/purpose, current policy)
#
# ``keep`` means the route intentionally replaces an independent complete screen or
# reloads tile data while already dark. ``replace-menu`` is a conservative same-menu
# fallback: scoped menu callers must acquire regional ownership instead, and fixtures
# must reject reaching it. ``mixed`` means the physical instruction has both an
# intentional complete-screen caller and rejected same-menu callers; each caller needs
# a direct fixture. ``review`` is a complete-screen menu transaction whose final product
# is correct but whose whole-LCD policy has not been frozen with the user.
TRANSLATION_OFF = {
    (38, 0x408F): (
        'structvwf.feirestore',
        "Fay's Puzzle composite entry and native fixed-tile reload",
        'keep',
    ),
    (41, 0x40E1): (
        'menuvwf.starttransition',
        'title/file composite shadow-map replacement',
        'review',
    ),
    (43, 0x40B6): (
        'rankvwf.rankfinish',
        'completed Rankings whole-map publication',
        'review',
    ),
    (44, 0x4066): (
        'name6.namerestore',
        'complete native menu-font reload retained for Start naming and rejected '
        'screen-9 callers; exact carried-Item and screen-20 Floor callers are regional',
        'mixed',
    ),
    (46, 0x42B5): (
        'rankvwf.nativerestore',
        'Rankings result/native-font restoration',
        'keep',
    ),
    (53, 0x4560): (
        'statusvwf.statusentry',
        'rejected LCD-on Status reconstruction; observed after the Pot Put return and '
        'retained for unknown callers',
        'replace-menu',
    ),
    (59, 0x406F): (
        'normalending.install',
        'Normal-ending full-screen art installation',
        'keep',
    ),
    (60, 0x4222): (
        'menuvwf.itemregion',
        'rejected regional Item-row transaction; observed on the synthetic equipment '
        'Status-to-Items route',
        'replace-menu',
    ),
    (60, 0x4338): (
        'menuvwf.itempage',
        'rejected Item/Pot transaction; observed on Action -> Pot Put selector',
        'replace-menu',
    ),
    (62, 0x4476): (
        'menuvwf.infolifecycle',
        'legacy Item/Floor Info or seal whole-map fallback',
        'replace-menu',
    ),
}


# One physical blanker can have several player-facing callers. Keep this separate from
# TRANSLATION_OFF: that table proves ownership of emitted instructions, while these rows
# are the caller-level worklist. ``remaining`` is an observed same-menu blank which still
# needs a regional owner. ``review`` is an observed menu-to-menu atomic blank which has
# not been accepted as permanent. ``keep`` is an independent-screen or gameplay
# replacement. ``dormant`` is executable fallback code with no observed admitted caller.
# ``coverage-gap`` names a real menu edge for which the current fixture suite has not yet
# resolved the causal instruction. Sites prefixed ``shadow`` clear $C110; VBlank later
# publishes the resulting off value at 0:$0737.
MENU_BLANK_PATHS = (
    # In-dungeon Status/Items/Floor menu system. Keep the order player-facing rather
    # than sorting by ROM address; this is also the intended visual test order.
    dict(system='item', key='field-to-status',
         sites=(('shadow', 4, 0x4154),), origin='base', stack='0',
         route='Dungeon field -> Status root', status='keep',
         fixture='potputspill.py',
         evidence='replacement boundary; observed when B opens Status'),
    dict(system='item', key='status-to-items-equipment',
         sites=(('LCDC', 60, 0x4222),), origin='translation', stack='0,1',
         route='Status -> Items with the canonical injected cursed/plated/fused rows',
         status='remaining', fixture='equipmentmarkerspill.py',
         evidence='observed exact irdisable execution; ordinary Status -> Items is zero'),
    dict(system='item', key='item-name-entry',
         sites=(), origin='translation', stack='0,1,2,9',
         route='Carried unidentified item Action -> Name keyboard',
         status='regional', fixture='unidentifiednamespill.py + '
                 'shiren_en_log3_carried_unidentified_naming.srm',
         evidence='exact stack admitted to four-row BG retirement plus selective '
                  'native-plane restore; LCDC.7 stays set and Name return is zero'),
    dict(system='item', key='item-name-empty-cancel',
         sites=(), origin='translation', stack='0,1',
         route='B from an empty carried-item Name keyboard -> Items reconstruction',
         status='regional', fixture='unidentifiednamespill.py + '
                 'shiren_en_log3_carried_unidentified_naming.srm',
         evidence='exact no-Lua screen-9 cancel arms state $0E, suppresses disposable '
                  'Status, publishes chrome before rows, and accepts immediate input'),
    dict(system='item', key='item-name-erased-cancel',
         sites=(), origin='translation', stack='0,1',
         route='B after erasing a reopened carried-item name -> Items reconstruction',
         status='regional', fixture='unidentifiednamespill.py + '
                 'shiren_en_log3_carried_unidentified_naming.srm',
         evidence='real End/reopen/four-delete/final-B route preserves native mode 3; '
                  'exact state $0F suppresses disposable Status, publishes chrome '
                  'before rows, and accepts immediate input'),
    dict(system='item', key='floor-name-entry',
         sites=(), origin='translation', stack='0,20 -> 0,20,9',
         route='Unidentified Floor item Action -> Name keyboard',
         status='regional', fixture='unidentifiednamespill.py + '
                 'shiren_log3_unidentified_naming.srm',
         evidence='exact stack/ground/box-39 owner uses four BG retirement and eighteen '
                  'native-plane batches; Status -> Floor predecessor is independently '
                  'zero-off and LCD-live'),
    dict(system='item', key='floor-name-end-return',
         sites=(('LCDC', 53, 0x4560),), origin='translation', stack='0,20',
         route='End from a screen-20 Floor item Name keyboard -> Floor reconstruction',
         status='remaining', fixture='unidentifiednamespill.py + '
                 'shiren_log3_unidentified_naming.srm',
         evidence='exact real-input End trace dispatches 9,0,20 with mode/row 3/0 and '
                  'executes statusdisable'),
    dict(system='item', key='floor-name-empty-cancel',
         sites=(('LCDC', 53, 0x4560),), origin='translation', stack='0,20',
         route='B from an initially empty screen-20 Floor Name keyboard -> Floor',
         status='remaining', fixture='unidentifiednamespill.py + '
                 'shiren_log3_unidentified_naming.srm',
         evidence='exact real-input B trace dispatches 9,0,20 with mode/row 0/1 and '
                  'executes statusdisable'),
    dict(system='item', key='floor-name-erased-cancel',
         sites=(('LCDC', 53, 0x4560),), origin='translation', stack='0,20',
         route='B after erasing a reopened screen-20 Floor item name -> Floor',
         status='remaining', fixture='unidentifiednamespill.py + '
                 'shiren_log3_unidentified_naming.srm',
         evidence='real End/reopen/delete/final-B trace dispatches 9,0,20 with mode/row '
                  '3/1 and executes statusdisable'),
    dict(system='item', key='pot-put-selector',
         sites=(('LCDC', 60, 0x4338),), origin='translation', stack='0,1,2,11',
         route='Carried Pot Action -> Put item selector', status='remaining',
         fixture='potputspill.py', evidence='observed exact pbdisable execution'),
    dict(system='item', key='pot-put-commit-return',
         sites=(('shadow', 2, 0x463C), ('shadow', 4, 0x4154)),
         origin='base', stack='0,1,2,11',
         route='Commit Put -> return to Pot Action/Items', status='remaining',
         fixture='potputspill.py',
         evidence='returns to the menu, so this is not the final gameplay teardown'),
    dict(system='item', key='pot-put-items-to-status',
         sites=(('LCDC', 53, 0x4560),), origin='translation', stack='0,1',
         route='Back out after Put -> Status reconstruction', status='remaining',
         fixture='potputspill.py', evidence='observed exact statusdisable execution'),
    dict(system='item', key='unknown-status-fallback',
         sites=(('LCDC', 53, 0x4560),), origin='translation', stack='unknown -> 0',
         route='Any other rejected LCD-on child -> Status reconstruction',
         status='dormant', fixture='all admitted Item/Info/Pot/Name/Floor returns',
         evidence='fallback remains in ROM; all other admitted success/return routes '
                  'require zero; both Name-cancel histories are separately admitted'),
    dict(system='item', key='unknown-item-region-fallback',
         sites=(('LCDC', 60, 0x4222),), origin='translation', stack='unknown -> 1',
         route='Any other rejected Item page/sort/shape regional transaction',
         status='dormant', fixture='itempagespill.py, floorpagespill.py',
         evidence='fallback remains in ROM; known paging/sort/Floor paths require zero'),
    dict(system='item', key='unknown-item-page-fallback',
         sites=(('LCDC', 60, 0x4338),), origin='translation', stack='unknown Item/Pot',
         route='Any other rejected Item redraw or Pot-viewer replacement',
         status='dormant',
         fixture='itempagespill.py, potseespill.py, potreturnspill.py, '
                 'groundpotreturnspill.py',
         evidence='fallback remains in ROM; admitted page/See routes require zero'),
    dict(system='item', key='unknown-info-fallback',
         sites=(('LCDC', 62, 0x4476),), origin='translation', stack='unknown -> 4/5',
         route='Any rejected Item/Floor Info, seal, or Pot lifecycle',
         status='dormant',
         fixture='iteminfospill.py, floorinfospill.py, unidentifiedpotspill.py, '
                 'potseespill.py',
         evidence='no execution in the complete 2026-08-27 fixture battery'),
    dict(system='item', key='shop-floor-native-transitions',
         sites=(('shadow', 2, 0x463C), ('shadow', 4, 0x4154)),
         origin='base', stack='0 and 0,20',
         route='Shop Status/Floor/action transitions outside the admitted ordinary Info owner',
         status='review', fixture='shopspill.py',
         evidence='observed, but one fixture covers several inputs; add one-edge traces '
                  'before assigning keep versus remaining'),
    dict(system='item', key='action-to-gameplay',
         sites=(('shadow', 2, 0x463C), ('shadow', 4, 0x4154)),
         origin='base', stack='0,...',
         route='Take/Toss/other action whose destination is gameplay or a field message',
         status='keep', fixture='potputspill.py, floorinfospill.py --fusion-kit-history',
         evidence='replacement boundary; distinguish from Put, which returns to menu'),
    dict(system='item', key='status-to-field',
         sites=(('shadow', 2, 0x463C),), origin='base', stack='0',
         route='B from Status -> dungeon field', status='keep',
         fixture='potputspill.py', evidence='intentional final menu teardown'),

    # Start/title menu system. Each named choice gets its own row even when several
    # choices share the same physical transition helper.
    dict(system='start', key='boot-title-presentation',
         sites=(('LCDC', 29, 0x411A), ('shadow', 31, 0x49B1),
                ('shadow', 31, 0x4AE8), ('shadow', 31, 0x4D59),
                ('shadow', 31, 0x4899), ('shadow', 4, 0x65F4)),
         origin='base', stack='pre-menu', route='Boot/logo/title presentation -> Start root',
         status='keep', fixture='titlecardspill.py, titlelogospill.py',
         evidence='pre-interactive display initialization, not a menu blanking target'),
    dict(system='start', key='adventure-log-summary',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,23',
         route='Adventure -> saved-log summary and log changes', status='review',
         fixture='mainmenuspill.py, copylogspill.py, savesummaryspill.py',
         evidence='observed title/file composite replacement'),
    dict(system='start', key='adventure-to-gameplay',
         sites=(('shadow', 2, 0x463C), ('shadow', 4, 0x4154)),
         origin='base', stack='15,23,21', route='Select Adventure log -> gameplay',
         status='keep', fixture='all save-backed menu fixtures',
         evidence='replacement boundary'),
    dict(system='start', key='new-log-selector',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,22',
         route='New Log -> log selector', status='review',
         fixture='mainmenuspill.py, nameflowspill.py', evidence='observed screen 22'),
    dict(system='start', key='new-log-difficulty',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,22,25',
         route='New Log -> difficulty and explanation composite', status='review',
         fixture='mainmenuspill.py, nameflowspill.py', evidence='observed screen 25'),
    dict(system='start', key='new-log-name',
         sites=(('LCDC', 44, 0x4066),), origin='translation', stack='15,22,25,8',
         route='New Log -> personal-name keyboard', status='keep',
         fixture='nameflowspill.py, newgamesmoke.py', evidence='caller 4:$4B04'),
    dict(system='start', key='new-log-to-gameplay',
         sites=(('shadow', 2, 0x463C),), origin='base', stack='15,22,25,8',
         route='Confirm New Log name -> village/gameplay', status='keep',
         fixture='newgamesmoke.py', evidence='replacement boundary'),
    dict(system='start', key='copy-log',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,23 and 15,23,24',
         route='Copy Log -> source/destination summaries and confirmation', status='review',
         fixture='copylogspill.py', evidence='observed screens 23 and 24'),
    dict(system='start', key='erase-log',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,23 and 15,23,24',
         route='Erase Log -> log summary and confirmation', status='review',
         fixture='copylogspill.py, startspill.py', evidence='observed screens 23 and 24'),
    dict(system='start', key='rename-log-selector',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,23,26',
         route='Rename -> alternate log-selector wrapper', status='review',
         fixture='nameflowspill.py', evidence='observed screen 26'),
    dict(system='start', key='rename-log-name',
         sites=(('LCDC', 44, 0x4066),), origin='translation', stack='screen 8 variant',
         route='Rename -> personal-name keyboard', status='keep',
         fixture='no isolated Rename entry fixture',
         evidence='static caller 4:$4B04 is shared with New Log; exact Rename visual '
                  'route remains a coverage gap'),
    dict(system='start', key='return-to-start-root',
         sites=(('LCDC', 46, 0x42B5),), origin='translation', stack='15',
         route='Return from file/Rank children -> Start root/native font', status='keep',
         fixture='nameflowspill.py, copylogspill.py, rankspill.py',
         evidence='observed beyond Rankings; physical owner is rankvwf.nativerestore'),
    dict(system='start', key='rank-pass',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,30 and 15,30,32',
         route='Rank/Pass -> root/category/Pass log composites', status='review',
         fixture='mainmenuspill.py, awardspill.py', evidence='observed screens 30 and 32'),
    dict(system='start', key='rankings-display',
         sites=(('LCDC', 43, 0x40B6), ('LCDC', 46, 0x42B5)),
         origin='translation', stack='15,30[,31],33',
         route='Rank category -> completed Rankings display/native-font restore',
         status='review', fixture='rankspill.py, orochisymbolspill.py, deathrankspill.py',
         evidence='both publication and restoration execute on screen 33'),
    dict(system='start', key='fay-entry',
         sites=(('LCDC', 38, 0x408F),), origin='translation', stack='15 -> 17',
         route="Fay's Puzzle -> task composite", status='keep',
         fixture='faypathspill.py', evidence='observed at the screen-15 boundary'),
    dict(system='start', key='fay-to-gameplay',
         sites=(('shadow', 2, 0x463C), ('shadow', 4, 0x4154)),
         origin='base', stack='15,17', route="Fay's Puzzle task -> gameplay",
         status='keep', fixture='faypathspill.py', evidence='replacement boundary'),
    dict(system='start', key='replay-log-summary',
         sites=(('LCDC', 41, 0x40E1),), origin='translation', stack='15,23',
         route='Replay -> saved-log summary before replay begins', status='review',
         fixture='focused exhaustive gbrun trace, 2026-08-27',
         evidence='observed screen 23; selecting the log produced no additional LCD-off '
                  'producer before the replay handoff'),
)


def _classify_before(buf, offset, bank_start):
    """Classify only locally provable A values immediately before an LCDC write."""
    before = buf[max(bank_start, offset - 8):offset]
    if before.endswith(b'\xCB\xBF'):
        return 'explicit-off'
    if before.endswith(b'\xCB\xFF'):
        return 'explicit-on'
    if before.endswith(b'\xAF'):
        return 'immediate-off-$00'
    if len(before) >= 2 and before[-2] == 0x3E:
        value = before[-1]
        return ('immediate-on-' if value & 0x80 else 'immediate-off-') + '$%02X' % value
    return 'variable'


def lcdc_writers(path):
    with open(path, 'rb') as handle:
        buf = handle.read()
    if len(buf) % BANK_SIZE:
        raise SystemExit('%s: ROM size is not bank-aligned' % path)
    found = []
    for bank in range(len(buf) // BANK_SIZE):
        bank_start = bank * BANK_SIZE
        origin = 0 if bank == 0 else 0x4000
        for rel in range(BANK_SIZE - 2):
            offset = bank_start + rel
            encoding = None
            if buf[offset:offset + 2] == b'\xE0\x40':
                encoding = 'ldh'
            elif buf[offset:offset + 3] == b'\xEA\x40\xFF':
                encoding = 'ld'
            if encoding is None:
                continue
            found.append({
                'target': 'LCDC',
                'bank': bank,
                'address': origin + rel,
                'encoding': encoding,
                'effect': _classify_before(buf, offset, bank_start),
            })
        # The base ROM also mutates LCDC without a store instruction.  The old audit
        # missed this form entirely, so it could not truthfully claim a complete LCD
        # control census.  Record the address of the CB instruction, which is also the
        # address runtime hooks must use.
        for rel in range(BANK_SIZE - 4):
            offset = bank_start + rel
            op = buf[offset:offset + 5]
            if op not in (b'\x21\x40\xFF\xCB\xBE', b'\x21\x40\xFF\xCB\xFE'):
                continue
            found.append({
                'target': 'LCDC',
                'bank': bank,
                'address': origin + rel + 3,
                'encoding': 'res-[hl]' if op[-1] == 0xBE else 'set-[hl]',
                'effect': 'explicit-off' if op[-1] == 0xBE else 'explicit-on',
            })
    found.sort(key=lambda site: (site['bank'], site['address']))
    return found


def lcdc_shadow_writers(path):
    """Return direct mutators of the VBlank-published LCDC shadow at ``$C110``.

    Clearing bit 7 here is just as important as writing an off value to ``$FF40``:
    bank 0's VBlank publisher at ``0:$0737`` copies this byte to hardware.  Keeping the
    producer sites in the census is what associates that otherwise-generic hardware
    write with the menu route which requested the blank.
    """
    with open(path, 'rb') as handle:
        buf = handle.read()
    found = []
    for bank in range(len(buf) // BANK_SIZE):
        bank_start = bank * BANK_SIZE
        origin = 0 if bank == 0 else 0x4000
        for rel in range(BANK_SIZE - 2):
            offset = bank_start + rel
            if buf[offset:offset + 3] != b'\xEA\x10\xC1':
                continue
            found.append({
                'target': 'LCDC-shadow',
                'bank': bank,
                'address': origin + rel,
                'encoding': 'ld',
                'effect': _classify_before(buf, offset, bank_start),
            })
        for rel in range(BANK_SIZE - 4):
            offset = bank_start + rel
            op = buf[offset:offset + 5]
            if op not in (b'\x21\x10\xC1\xCB\xBE', b'\x21\x10\xC1\xCB\xFE'):
                continue
            found.append({
                'target': 'LCDC-shadow',
                'bank': bank,
                'address': origin + rel + 3,
                'encoding': 'res-[hl]' if op[-1] == 0xBE else 'set-[hl]',
                'effect': 'explicit-off' if op[-1] == 0xBE else 'explicit-on',
            })
    found.sort(key=lambda site: (site['bank'], site['address']))
    return found


def display_mutators(path):
    """All statically enumerable hardware and shadow LCDC mutation sites."""
    rows = lcdc_writers(path) + lcdc_shadow_writers(path)
    rows.sort(key=lambda site: (site['target'], site['bank'], site['address']))
    return rows


def menu_path_rows(system=None):
    """Return path-level menu rows, optionally restricted to ``item`` or ``start``."""
    rows = list(MENU_BLANK_PATHS)
    if system is not None:
        rows = [row for row in rows if row['system'] == system]
    return rows


def write_menu_tsv(path, rows):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fields = ('system', 'key', 'route', 'stack', 'sites', 'origin', 'status',
              'fixture', 'evidence')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            cooked = dict(row)
            cooked['sites'] = ' + '.join(
                ('shadow ' if target == 'shadow' else '') + '%d:$%04X' % (bank, address)
                for target, bank, address in row['sites'])
            if not cooked['sites']:
                cooked['sites'] = ('none (regional)' if row['status'] == 'regional'
                                   else 'unresolved')
            writer.writerow(cooked)


def _is_locally_off(effect):
    return effect == 'explicit-off' or effect.startswith('immediate-off-')


def validate_menu_paths(rows):
    """Keep the two path catalogues tied to real, locally provable off producers."""
    actual = {(row['target'], row['bank'], row['address']): row for row in rows}
    problems = []
    keys = set()
    referenced_translation = set()
    for path in MENU_BLANK_PATHS:
        key = (path['system'], path['key'])
        if key in keys:
            problems.append('duplicate menu path key %s/%s' % key)
        keys.add(key)
        if not path['sites'] and path['status'] not in ('coverage-gap', 'regional'):
            problems.append('%s/%s has no LCD-off site' % key)
        for target, bank, address in path['sites']:
            target_name = 'LCDC-shadow' if target == 'shadow' else target
            site = actual.get((target_name, bank, address))
            label = '%s/%d:$%04X' % (target_name, bank, address)
            if site is None:
                problems.append('%s/%s references missing site %s' % (key[0], key[1], label))
                continue
            if not _is_locally_off(site['effect']):
                problems.append('%s/%s references non-off site %s (%s)' %
                                (key[0], key[1], label, site['effect']))
            if site['origin'] == 'translation':
                referenced_translation.add((bank, address))

    # The normal ending is deliberately outside both menu systems. Every other explicit
    # translation-owned blanker must appear in at least one of the two path catalogues.
    menu_translation = set(TRANSLATION_OFF) - {(59, 0x406F)}
    missing = menu_translation - referenced_translation
    if missing:
        problems.append('translation menu blanker(s) absent from caller catalogues: %s' %
                        ' '.join('%d:$%04X' % site for site in sorted(missing)))
    return problems


def audit(base_path, built_path):
    base = display_mutators(base_path)
    built = display_mutators(built_path)
    base_keys = {(site['target'], site['bank'], site['address']) for site in base}
    rows = []
    for site in built:
        key = (site['target'], site['bank'], site['address'])
        native = key in base_keys
        owner = route = policy = ''
        instruction_key = (site['bank'], site['address'])
        if site['target'] == 'LCDC' and instruction_key in TRANSLATION_OFF:
            owner, route, policy = TRANSLATION_OFF[instruction_key]
        elif native:
            owner = 'base ROM'
            route = 'native/shared LCDC writer; runtime value is caller-dependent'
            policy = 'native-observe'
        else:
            owner = 'translation-added writer'
            route = 'does not locally prove an LCD-off transition'
            policy = 'observe'
        row = dict(site)
        row.update({
            'origin': 'base' if native else 'translation',
            'owner': owner,
            'route': route,
            'policy': policy,
        })
        rows.append(row)

    actual_added_off = {
        (row['target'], row['bank'], row['address']) for row in rows
        if row['origin'] == 'translation' and _is_locally_off(row['effect'])
    }
    expected_added_off = {('LCDC', bank, address) for bank, address in TRANSLATION_OFF}
    problems = []
    missing = expected_added_off - actual_added_off
    extra = actual_added_off - expected_added_off
    if missing:
        problems.append('manifested translation blanker(s) missing or no longer explicit: %s' %
                        ' '.join('%s/%d:$%04X' % key for key in sorted(missing)))
    if extra:
        problems.append('UNCLASSIFIED translation blanker(s): %s' %
                        ' '.join('%s/%d:$%04X' % key for key in sorted(extra)))
    return base, rows, problems


def write_tsv(path, rows):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fields = ('target', 'bank', 'address', 'encoding', 'effect', 'origin',
              'owner', 'policy', 'route')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            cooked = dict(row)
            cooked['bank'] = str(row['bank'])
            cooked['address'] = '$%04X' % row['address']
            writer.writerow(cooked)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base', help='matching unmodified Japanese ROM')
    parser.add_argument('built', help='current English ROM')
    parser.add_argument('--tsv', help='write the complete LCDC-writer catalogue here')
    parser.add_argument('--menu-tsv',
                        help='write the caller-level Item/Status and Start-menu worklist')
    parser.add_argument('--item-menu-tsv',
                        help='write only the caller-level Item/Status LCD-off worklist')
    parser.add_argument('--start-menu-tsv',
                        help='write only the caller-level Start-menu LCD-off worklist')
    args = parser.parse_args()
    base, rows, problems = audit(args.base, args.built)
    problems.extend(validate_menu_paths(rows))
    if args.tsv:
        write_tsv(args.tsv, rows)
    if args.menu_tsv:
        write_menu_tsv(args.menu_tsv, menu_path_rows())
    if args.item_menu_tsv:
        write_menu_tsv(args.item_menu_tsv, menu_path_rows('item'))
    if args.start_menu_tsv:
        write_menu_tsv(args.start_menu_tsv, menu_path_rows('start'))

    added = [row for row in rows if row['origin'] == 'translation']
    explicit = [row for row in added if _is_locally_off(row['effect'])]
    policies = {}
    for row in explicit:
        policies[row['policy']] = policies.get(row['policy'], 0) + 1
    print('lcdblankaudit: base/current display mutators %d/%d; translation-added %d; '
          'explicit added LCD-off %d' % (len(base), len(rows), len(added), len(explicit)))
    print('lcdblankaudit: explicit policies %s' %
          ' '.join('%s=%d' % item for item in sorted(policies.items())))
    for row in explicit:
        print('  %d:$%04X %-12s %-27s %s' %
              (row['bank'], row['address'], row['policy'], row['owner'], row['route']))
    if args.tsv:
        print('lcdblankaudit: complete catalogue: %s' % args.tsv)
    if args.menu_tsv:
        counts = {system: len(menu_path_rows(system)) for system in ('item', 'start')}
        print('lcdblankaudit: menu paths item=%d start=%d: %s' %
              (counts['item'], counts['start'], args.menu_tsv))
    if args.item_menu_tsv:
        print('lcdblankaudit: Item/Status paths %d: %s' %
              (len(menu_path_rows('item')), args.item_menu_tsv))
    if args.start_menu_tsv:
        print('lcdblankaudit: Start paths %d: %s' %
              (len(menu_path_rows('start')), args.start_menu_tsv))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('lcdblankaudit: %d problem(s)' % len(problems))
    print('lcdblankaudit: every explicit translation-owned LCD blanker is classified')


if __name__ == '__main__':
    main()
