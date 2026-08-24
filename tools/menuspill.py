#!/usr/bin/env python3
"""Do composed menu rows show EXACTLY the pixels the glyph table says, and nothing else?

boxspill.py's idea for the menu renderer, with the two lessons §4 of `docs/VWF_BUDGETS.md`
paid for baked in:

  * PLANE-EXACT, never OR'd. The one-cell park stomp put garbage in ONE plane of one
    row of one tile; an OR'd-planes dump hid it for a session and a DMG screenshot hid
    it from every PNG. Planes are compared separately, byte for byte.
  * The screen's own memory, not a model. Every frame, every visible BG cell holding a
    pool-tile index ($43-$7B) must belong POSITIONALLY to a live allocator record: cell
    (row, col) maps to shadow $C300 + 32*row + col, some record must cover it, and the
    index must equal base + (cell - first text cell). A stale slice, a leak, or a
    neighbour stomp all break that equality.

The settled-screen check detects the installed uniform-6px or Dot-proportional renderer,
then recomposes every eligible staged row IN PYTHON from the ROM's own shifted glyph and
width tables. It demands the VRAM slice match byte-for-byte, per plane. That proves the
queue upload — both passes, the ext tile, the park fix — delivered every byte.

--long is the worst case the dungeon save cannot show: it rewrites the staging block at
the drawer's first call with five synthetic rows — 17 characters with a real `$7E
digits $7F` counter and hyphens, so long-row and allocator paths run on the REAL screen
through the REAL queue. The uniform renderer fills four 13-tile caps and must fall back
on row five. The proportional hostile page uses one representative of the tied widest
signed equipment variants at 11 tiles, four widest real counter-bearing names at 11 tiles
each, and four 4-tile action verbs, for the measured 71-tile peak. The tool
derives allocation expectations from the installed ROM instead of hard-coding either
font's outcome.

--ram boots Joey's floor-7 fixture, checks three real pages and the equipped `Remove`
overlay plane-exact, and audits every page-change frame. A legal regional transition is
old rows, five blank name interiors, then completed rows from top to bottom while the LCD
stays on; any old/new mixture or unowned row fails. ``itempagespill.py`` owns the exact
transaction-state, locked-cell, and real multi-page acceptance checks.

--help-seals forces the real box-7 item-information screen and all five groups of box-19
equipment seals. It also injects one 16-tile row and one 21-character narrow row, checks
both LCD-off direct writes and LCD-on overlapping queue passes, and requires every visible
slice to match the approved Dot glyph planes exactly.

Every mode also forces screen 20's exact box-5 Floor item header and injects
``True Rapier+99`` after the game stages `$C616`.  That one-row `$x0,y0,w18` path was
missing from the original VWF allowlist; its one raw cell, composed planes and following
action popup now remain a permanent component regression fixture. ``groundspill.py``
owns the real save-driven acceptance route.

Screenshots are taken CGB-colourised when pyboy allows it — a colour palette is what
showed Joey the park stomp that every DMG grey PNG hid.

    menuspill.py build/shiren_en.gb
    menuspill.py build/shiren_en.gb --long --png build/menuvwf_long.png
    menuspill.py build/shiren_en.gb --ram saves/shiren_en_menu.srm
    menuspill.py build/shiren_en.gb --help-seals

Exit 1 on any violation, or if no composed row was ever seen (a clean sweep that
verified nothing does not pass).
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gbrun import _import_pyboy, PRESS_FRAMES               # noqa: E402
import menuvwf                                               # noqa: E402
import gbasm                                                  # noqa: E402
import propvwf                                               # noqa: E402
import structvwf                                             # noqa: E402
import statusvwf                                             # noqa: E402
from latinfont import EN_CODES                               # noqa: E402

POOL_LO, POOL_HI = menuvwf.POOL_BASE, menuvwf.POOL_END - 1   # $43-$7B inclusive
LEGACY_RUNS = ((0x43, 0x7C),)
PROP_RUNS = ((menuvwf.POOL_BASE, menuvwf.POOL_END),
             (0x8B, 0x96), (0x9A, 0x9E))
SHADOW = 0xC300
BGMAP = 0x9800
VISIBLE_ROWS, VISIBLE_COLS = 18, 20
RECORDS = 0xC163            # records are (key lo, key hi, base, cap, raw cells)
LEGACY_REC_COUNT = 0xC0D8
PROP_REC_COUNT = 0xC1B2
STAGING = 0xC616
# Exact high codes supported by the proportional menu scanner and its pixel model.
# Most use Dot metadata; fusion-count $8C-$94 uses menuvwf's compact auxiliary shifter.
# The scanner's wider native range also contains $B1/$B3, but those have no proportional
# implementation and are therefore deliberately excluded from stress fixtures.
ELIGIBLE_EXTRA = {0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0xA0,
                  0x88, 0x8A, *menuvwf.FUSED_CODES,
                  0x9E, 0x9F, 0xB0, 0xB2, 0xB4, 0xB5}

FAR_BANK = menuvwf.FAR_BANK


def renderer_profile(rom_path):
    rom = open(rom_path, 'rb').read()
    bank = rom[FAR_BANK * 0x4000:(FAR_BANK + 1) * 0x4000]
    index = menuvwf.FAR_INDEX - 1
    entry = bank[index] | (bank[index + 1] << 8)
    if entry == menuvwf.CODE_AT:
        mode = 'uniform6'
    elif entry == menuvwf.PROP_CODE_AT:
        mode = 'dot-proportional'
    else:
        raise SystemExit('menuspill: far index %d points to $%04X, expected menu VWF '
                         'at $%04X or $%04X'
                         % (menuvwf.FAR_INDEX, entry, menuvwf.CODE_AT,
                            menuvwf.PROP_CODE_AT))
    return {'mode': mode, 'bank': bank, 'entry': entry,
            'runs': PROP_RUNS if mode == 'dot-proportional' else LEGACY_RUNS,
            'record_count': (PROP_REC_COUNT if mode == 'dot-proportional'
                             else LEGACY_REC_COUNT)}


def in_pool(profile, tile):
    return any(lo <= tile < hi for lo, hi in profile['runs'])


def tile_data_addr(tile):
    """VRAM address selected by a BG tile number in LCDC's signed $8800 mode.

    $00-$7F live at $9000-$97F0; $80-$FF wrap to $8800-$8FF0.  The original
    single-run allocator never crossed $7F, so the old linear $9000+16*n read
    accidentally worked until the proportional allocator began using $8B-$95.
    """
    return 0x9000 + (tile if tile < 0x80 else tile - 0x100) * 16


def structured_static_cells():
    """Exact context-shared V3 cells that numerically sit in the dynamic pool.

    Fay's two ``No`` fragments remain allocator capacity on item/action screens.  They
    are static owners only at the measured Fay coordinates below, and only while their
    live planes still equal the approved fragment raster.  A collision therefore fails
    this same-frame invariant instead of being hidden by a blanket tile-ID exemption.
    """
    font = structvwf.dotfont.load_approved()
    specs = ((1, 1, 'No', 0), (1, 2, 'No', 1))
    out = {}
    for row, col, word, fragment in specs:
        ids = (structvwf.BOX2_TILES if word == 'Weapon' else
               structvwf.QUIZ_TILES)[word]
        raster = structvwf._render(word, font)[fragment]
        out[(row, col, ids[fragment])] = b''.join(
            bytes((bits, bits)) for bits in raster)
    return out


STRUCTURED_STATIC = structured_static_cells()
_POPUP_STATIC = {}


def popup_static_cells(profile):
    """Exact record-free cells owned only by saved-Log Continue/New Game.

    The popup deliberately borrows the confirmation slices so its ROM-backed text
    cannot repaint the still-visible Orochi badge at $CB-$CE.  Keep this exemption
    position-, tile- and plane-exact: adding $82/$9A globally would conceal genuine
    ownership collisions in the ordinary menu allocator.
    """
    if profile['mode'] != 'dot-proportional':
        return {}
    key = profile['mode']
    if key not in _POPUP_STATIC:
        cells = {}
        rows = ((5, 5, 'Continue', menuvwf.CONFIRM_POOL_ROWS[0]),
                (7, 5, 'New Game', menuvwf.CONFIRM_POOL_ROWS[1]))
        for row, col, label, base in rows:
            pixels = compose([EN_CODES[c] for c in label], profile)
            for index, raster in enumerate(pixels):
                cells[(row, col + index, base + index)] = bytes(raster)
        _POPUP_STATIC[key] = cells
    return _POPUP_STATIC[key]


def status_fragment_problems(pb):
    """Verify box 2 after the real saved-game item-menu lifetime route.

    The status labels remain visible behind the item list.  The regression that produced
    a plus-shaped first letter in ``Weapon`` did not damage the shadow row; an item tile
    upload changed the shared VRAM planes after box 2 had drawn.  Check both the restored
    rows and every private fragment plane after backing out of the item menu.
    """
    problems = []
    rows = (
        (11 * 32 + 1,
         bytes(statusvwf.WEAPON_TILES) + bytes((0,)) * 4 + bytes((structvwf.DIVIDER,))
         + bytes(range(0x0B, 0x11)) + bytes((0,)) * 3),
        (13 * 32 + 1,
         bytes(statusvwf.SHIELD_TILES) + bytes((0,)) * 4 + bytes((structvwf.DIVIDER,))
         + bytes(range(0x04, 0x0B)) + bytes((0,)) * 2),
    )
    shadow = bytes(pb.memory[SHADOW:SHADOW + 32 * VISIBLE_ROWS])
    bg = bytes(pb.memory[BGMAP:BGMAP + 32 * VISIBLE_ROWS])
    for start, expected in rows:
        if shadow[start:start + len(expected)] != expected:
            problems.append('item return: status shadow row +$%03X was not restored' % start)
        if bg[start:start + len(expected)] != expected:
            problems.append('item return: visible status row +$%03X was not restored' % start)

    font = structvwf.dotfont.load_approved()
    for text, ids in structvwf.BOX2_TILES.items():
        for tile_id, raster in zip(ids, structvwf._render(text, font)):
            expected = b''.join(bytes((bits, bits)) for bits in raster)
            at = tile_data_addr(tile_id)
            got = bytes(pb.memory[at:at + 16])
            if got != expected:
                problems.append('item return: %s tile $%02X planes were overwritten'
                                % (text, tile_id))
    for text, ids in (('Strength', tuple(range(0x0B, 0x11))),
                      ('Experience', tuple(range(0x04, 0x0B)))):
        for tile_id, raster in zip(ids, structvwf._render(text, font)):
            expected = b''.join(bytes((bits, bits)) for bits in raster)
            at = tile_data_addr(tile_id)
            if bytes(pb.memory[at:at + 16]) != expected:
                problems.append('item return: %s tile $%02X planes were overwritten'
                                % (text, tile_id))
    for name, map_at in (('Gitan', 0xC34E), ('Floor', 0xC391), ('Path', 0xC3CF),
                         ('Weapon value', 0xC485), ('Strength value', 0xC48F),
                         ('Shield value', 0xC4C5), ('Experience value', 0xC4CF)):
        base, cap = statusvwf.PRIVATE_RUNS[name]
        start = map_at - SHADOW
        expected = bytes(range(base, base + cap))
        if shadow[start:start + cap] != expected or bg[start:start + cap] != expected:
            problems.append('item return: %s VWF map was not restored' % name)
    return problems


def visible_row_matches(pb, profile, key, codes, raw=2):
    """Does the row's currently displayed tilemap resolve to these exact pixels?"""
    want = compose(codes, profile)
    first = key + 1 + raw - SHADOW
    for i, tile_bytes in enumerate(want):
        tile = pb.memory[BGMAP + first + i]
        if not in_pool(profile, tile):
            return False
        at = tile_data_addr(tile)
        if bytes(pb.memory[at:at + 16]) != bytes(tile_bytes):
            return False
    return True


def visible_item_row_blank(pb, key):
    """Recognize the earlier blank-name transition and native incremental clears."""
    first = key + 3 - SHADOW
    return all(pb.memory[BGMAP + first + i] == 0 for i in range(16))


def visible_item_row_erasing(pb, profile, key, codes):
    """True while VBlank is replacing one exact row with blank cells.

    Sampling can land in the middle of the 80-byte VBlank loop. Every nonblank cell
    must still resolve to its old exact tile (or a zero padding tile); accepting any
    arbitrary pool byte here would hide the very old/new corruption this checks.
    """
    want = compose(codes, profile)
    first = key + 3 - SHADOW
    saw_blank = False
    for i in range(16):
        tile = pb.memory[BGMAP + first + i]
        if tile == 0:
            saw_blank = True
            continue
        if not in_pool(profile, tile):
            return False
        at = tile_data_addr(tile)
        got = bytes(pb.memory[at:at + 16])
        expected = bytes(want[i]) if i < len(want) else bytes(16)
        if got != expected:
            return False
    return saw_blank


def eligible(codes, max_chars=18):
    return (1 <= len(codes) <= max_chars and
            all(c < 0x43 or c in ELIGIBLE_EXTRA for c in codes))


def _dot_metric(profile, code):
    if code == 0x7D:       # item-information title delimiter -> approved Dot hyphen
        code = EN_CODES['-']
    bank = profile['bank']
    if code in menuvwf.FUSED_CODES:
        width = 8
        slot = None
        start = propvwf.NATIVE_ORG - 0x4000 + code * propvwf.GLYPH_BYTES
        rows = bank[start:start + propvwf.GLYPH_BYTES]
    elif code < propvwf.CORE_CODES:
        slot = code
        width = bank[propvwf.CORE_WIDTH_ORG - 0x4000 + code]
        unshifted = propvwf.GLYPH_ORG - 0x4000 + slot * propvwf.DOT_GLYPH_STRIDE
        rows = bank[unshifted:unshifted + 8]
    else:
        at = propvwf.META_ORG - 0x4000 + 2 * code
        slot, width = bank[at:at + 2]
        if slot == 0xFF:
            raise AssertionError('unsupported proportional menu code $%02X' % code)
        unshifted = propvwf.GLYPH_ORG - 0x4000 + slot * propvwf.DOT_GLYPH_STRIDE
        rows = bank[unshifted:unshifted + 8]
    ink = [x for x in range(8) if any(row & (0x80 >> x) for row in rows)]
    return slot, width, (max(ink) + 1 if ink else width)


def compose(codes, profile):
    """Mirror either installed far renderer using the ROM's own shifted glyph bytes."""
    tiles = [bytearray(16) for _ in range(16)]
    pen = extent = 0
    for c in codes:
        t = pen >> 3
        if profile['mode'] == 'uniform6':
            shift = (pen & 7) >> 1
            at = (menuvwf.GLYPHS - 0x4000
                  + shift * menuvwf.SHIFT_STRIDE + c * 16)
            entry = profile['bank'][at:at + 16]
            width = ink_width = 6
        else:
            slot, width, ink_width = _dot_metric(profile, c)
            shift = pen & 7
            if slot is None:
                at = (propvwf.NATIVE_ORG - 0x4000
                      + c * propvwf.GLYPH_BYTES)
                glyph = profile['bank'][at:at + propvwf.GLYPH_BYTES]
                entry = (bytes(value >> shift for value in glyph) +
                         bytes(((value << (8 - shift)) & 0xFF) if shift else 0
                               for value in glyph))
            else:
                at = (propvwf.GLYPH_ORG - 0x4000
                      + slot * propvwf.DOT_GLYPH_STRIDE + shift * 16)
                entry = profile['bank'][at:at + 16]
        for r in range(8):
            tiles[t][2 * r] |= entry[r]
            tiles[t][2 * r + 1] |= entry[r]
            if t + 1 <= 15:
                tiles[t + 1][2 * r] |= entry[8 + r]
                tiles[t + 1][2 * r + 1] |= entry[8 + r]
        extent = pen + ink_width
        pen += width
    n = ((6 * len(codes) + 7) >> 3 if profile['mode'] == 'uniform6'
         else (extent + 7) >> 3)
    return tiles[:n]


def capneed(tiles):
    if tiles <= 4:
        return 4
    if tiles <= 8:
        return 8
    return tiles


def records(pb, profile):
    out = []
    for k in range(pb.memory[profile['record_count']]):
        lo, hi, base, cap, raw = pb.memory[RECORDS + 5 * k:RECORDS + 5 * k + 5]
        out.append(((hi << 8) | lo, base, cap, raw))
    return out


def frame_invariant(pb, profile, fallback_rows=None):
    """[(row, col, tile, why)] for every visible pool-index cell that does not sit
    exactly where a live record says it must."""
    recs = records(pb, profile)
    bad = []
    bg = bytes(pb.memory[BGMAP:BGMAP + 0x400])
    sh = bytes(pb.memory[SHADOW:SHADOW + 32 * VISIBLE_ROWS])
    popup_static = popup_static_cells(profile)
    uniform_frame = None
    for row in range(VISIBLE_ROWS):
        for col in range(VISIBLE_COLS):
            v = bg[32 * row + col]
            if not in_pool(profile, v):
                continue
            if sh[32 * row + col] != v:
                # the shadow no longer says this: a menu is not up (terrain tiles
                # share these indices) or the copy is mid-flight; not ours to judge
                continue
            addr = SHADOW + 32 * row + col
            static = STRUCTURED_STATIC.get((row, col, v))
            got_plane = bytes(pb.memory[tile_data_addr(v):tile_data_addr(v) + 16])
            if (profile['mode'] == 'dot-proportional' and static is not None and
                    got_plane == static):
                continue
            popup = popup_static.get((row, col, v))
            if profile['mode'] == 'dot-proportional' and popup is not None:
                if got_plane == popup:
                    continue
                # Continue clears its borrowed font planes three frames before the
                # obsolete popup map is replaced, but only after the native transition
                # has faded the entire rendered frame to one colour.  Admit that exact
                # invisible zero-plane retirement without masking a visible blank row.
                if got_plane == bytes(16):
                    if uniform_frame is None:
                        extrema = pb.screen.image.getextrema()
                        uniform_frame = all(low == high for low, high in extrema)
                    if uniform_frame:
                        continue
            # a cell may sit under SEVERAL records' cap ranges (an overlay box's
            # rows cross the rows it covers); it is legal if ANY record explains
            # its exact value at its exact position
            for key, base, cap, raw in recs:
                first = key + 1 + raw    # border + the shape's raw cursor cells
                if first <= addr < first + cap and v == base + (addr - first):
                    break
            else:
                # Box 7/19's untranslated item-name fixture deliberately takes the raw
                # fallback and contains native codes numerically inside the VWF pool.
                # It is legal only when the captured raw row explains this exact cell
                # and no proportional record owns that destination.
                record_keys = {key for key, _base, _cap, _raw in recs}
                if fallback_rows:
                    for key, codes in fallback_rows.items():
                        offset = addr - (key + 1)
                        # Native dakuten/handakuten bytes overlay the preceding cell and
                        # do not advance the raw drawer's horizontal cursor.
                        cells = [code for code in codes if code not in (0x79, 0x7A)]
                        if (key not in record_keys and 0 <= offset < len(cells) and
                                cells[offset] == v):
                            break
                    else:
                        bad.append((row, col, v, 'no record explains this cell'))
                    continue
                bad.append((row, col, v, 'no record explains this cell'))
    return bad


def staged_rows(pb):
    """Parse the staging block: [(codes, offset)] per $FF-terminated row, RAW --
    no prefix stripping here, because the raw-cell prefix is one zero for the main
    menu and two for the item lists; the caller strips per-record."""
    mem = bytes(pb.memory[STAGING:STAGING + 0x84])
    rows, i = [], 0
    while i < len(mem):
        j = i
        while j < len(mem) and mem[j] != 0xFF:
            j += 1
        if j >= len(mem):
            break
        if j > i:
            rows.append((list(mem[i:j]), i))
        i = j + 1
    return rows


def settled_check(pb, profile, label, report, drawn):
    """Plane-exact: each record paired with the codes CAPTURED AT DRAW TIME for its
    dest (`drawn`, filled by the far-entry hook) -- the staging block is reused by
    later boxes on the same screen build, so parsing it after the fact pairs the
    main menu's records with the status box's text. Gated on liveness: only a
    record whose dest row still shows exactly its slice is verified. A gate-skip
    cannot silently pass: zero verified rows fails the whole run."""
    recs = records(pb, profile)
    checked = 0
    problems = []
    sh = bytes(pb.memory[SHADOW:SHADOW + 32 * VISIBLE_ROWS])
    for k, (key, base, cap, raw) in enumerate(recs):
        first = key + 1 + raw - SHADOW
        if not (0 <= first < len(sh) - 17):
            continue
        shown = 0
        while (shown < 17 and first + shown < len(sh)
               and in_pool(profile, sh[first + shown])):
            shown += 1
        if sh[first] != base or not shown:
            continue
        row = drawn.get(key)
        if row is None:
            continue
        if raw == 0:
            if not row:
                continue
        elif raw == 1:
            if len(row) <= 1 or row[0] != 0:
                continue
        elif raw == 2:
            # Item prefix: byte 0 is $00, equipped marker $84/$86, or the unequipped
            # curse marker $87. It stays raw in column 1; byte 1 is the cursor cell.
            if len(row) <= 2 or row[0] not in (0, 0x84, 0x86, 0x87) or row[1] != 0:
                continue
        else:
            continue
        codes = row[raw:]
        if not eligible(codes, 21 if raw == 0 else 18):
            continue
        want = compose(codes, profile)
        if len(want) != shown:
            continue
        need = shown
        data_at = tile_data_addr(base)
        got = bytes(pb.memory[data_at:data_at + need * 16])
        for t in range(need):
            for plane in (0, 1):
                w = bytes(want[t][plane::2])
                g = bytes(got[t * 16 + plane:t * 16 + 16:2])
                if w != g:
                    problems.append('%s: record %d tile %d plane %d differs: '
                                    'want %s got %s'
                                    % (label, k, t, plane, w.hex(), g.hex()))
        checked += 1
    report[0] += checked
    return problems


LONG_ROWS = [
    # The exact row-0 regression followed by four REAL glossary staff/pot names. Every
    # True Rapier is the real glossary weapon; the remaining four rows retain the hostile
    # widest two-digit counter class and paint 11 approved-font tiles each. Each widest
    # two-digit counter row. The current hostile peak is 9 + 11*4 item tiles plus 4*4
    # action tiles = 69/72
    # usable tiles. The old row-number policy forced row 0 into the 11-run, fell back to
    # fixed width, and spilled the last digit into row 1. Row 0 carries Joey's $84 marker.
    'True Rapier-99',
    'Stopgap Staff[77]',
    'Weakening Pot[77]',
    'Sorcery Staff[77]',
    'Unlucky Staff[77]',
]

LONG_ACTION_ROWS = ('Remove', 'Toss', 'Drop', 'Info')


def encode(text):
    return [EN_CODES[c] for c in text]


def drive(rom, profile, long_mode, png, frames=680, ram=None):
    if long_mode:
        frames = max(frames, 780)
    if ram:
        frames = max(frames, 2240)
    PyBoy = _import_pyboy()
    tmp = None
    run_rom = rom
    if ram:
        tmp = tempfile.TemporaryDirectory(prefix='menuspill-')
        run_rom = os.path.join(tmp.name, 'menu.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
    kwargs = {}
    if png:
        try:
            pb = PyBoy(run_rom, window='null', cgb=True)
            pb.stop(save=False)
            kwargs['cgb'] = True
        except Exception:
            kwargs = {}
    pb = PyBoy(run_rom, window='null', **kwargs)
    pb.set_emulation_speed(0)
    if not ram:
        with open('saves/dungeon.state', 'rb') as f:
            try:
                pb.load_state(f)
            except Exception:
                # a CGB context cannot load a DMG state; fall back to grey
                pb.stop(save=False)
                pb = PyBoy(run_rom, window='null')
                pb.set_emulation_speed(0)
                with open('saves/dungeon.state', 'rb') as f2:
                    pb.load_state(f2)

    frame = {'n': 0}
    drawn = {}
    long_seen = set()
    item_trace = []
    page_build = {'value': None}
    completed_page = {'value': None}
    flips = []

    def capture(_ctx=None):
        # what menurow is ABOUT to read: dest = hl, source = [$C69F]
        key = pb.register_file.HL
        src = (pb.memory[0xC6A0] << 8) | pb.memory[0xC69F]
        if 0xC000 <= src < 0xE000:
            row = []
            for i in range(src, src + 32):
                v = pb.memory[i]
                if v == 0xFF:
                    break
                row.append(v)
            drawn[key] = row
            shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
            if ram and shape[0:2] == (0, 3) and shape[3] == 18:
                rownum = pb.register_file.D
                codes = tuple(row[2:])
                item_trace.append((frame['n'], rownum, key, codes))
                if rownum == 0:
                    prior = page_build['value']
                    if prior is not None and len(prior['rows']) == 5:
                        completed_page['value'] = prior
                    page_build['value'] = {
                        'start': frame['n'], 'complete': None, 'rows': {},
                        'old': completed_page['value'], 'observations': [],
                        'settled': False,
                    }
                    if completed_page['value'] is not None:
                        flips.append(page_build['value'])
                page = page_build['value']
                if page is not None:
                    page['rows'][key] = codes
                    if len(page['rows']) == 5:
                        page['complete'] = frame['n']
            if long_mode:
                for index, text in enumerate(LONG_ROWS):
                    if row[2:] == encode(text):
                        long_seen.add(index)

    rewrite = None
    if long_mode:
        rows = b''
        for i, text in enumerate(LONG_ROWS):
            prefix = [0x84, 0] if i == 0 else [0, 0]
            rows += bytes(prefix + encode(text) + [0xFF])
        armed = {'done': False}

        def rewrite(_ctx=None):
            # the item list is RE-STAGED by the game on every open, so the rewrite
            # must land at the first far call of one specific draw sequence -- the
            # reopen at f560 draws a few frames later (traced) -- after the game
            # staged and before any row was read. Anywhere earlier is silently
            # restaged over, which is exactly how this mode once verified nothing.
            if armed['done'] or not 556 <= frame['n'] <= 572:
                return
            armed['done'] = True
            for i, b in enumerate(rows):
                pb.memory[STAGING + i] = b

    def at_far(_ctx=None):
        if rewrite is not None:
            rewrite()
        capture()
    pb.hook_register(FAR_BANK, profile['entry'], lambda _ctx: at_far(), None)

    # b opens the main menu, a enters the item list; then cursor moves, the action
    # menu over the list, close, and reopen -- the POC's proven redraw gauntlet.
    # --long then closes the menu entirely after the live Items -> Status redraw has
    # settled, so the font-upload reset frees the records. It reopens (500/560) and
    # rewrites the fresh staging: reused records from
    # the first open would cap the synthetic rows at the REAL rows' needs, which is
    # correct fallback behaviour but not the scenario under test
    if ram:
        # Boot Joey's floor-7 cartridge save, enter the dungeon, visit three real
        # item pages, return to page two, open the equipped weapon's Remove menu, then
        # back out to status.  The final return is the exact lifetime route where an item
        # upload used to turn the first Weapon fragment into a plus-shaped glyph.
        script = {
            60: 'start', 120: 'start', 180: 'start', 240: 'start', 300: 'a',
            350: 'down', 390: 'down', 430: 'a', 500: 'a', 1700: 'b', 1780: 'a',
            1840: 'right', 1900: 'right', 1960: 'left', 2020: 'a',
            2080: 'b', 2140: 'b',
        }
        check_at = (1715, 1800, 1860, 1920, 2045, frames - 2)
    else:
        script = {60: 'b', 120: 'a', 200: 'down', 230: 'down', 260: 'a',
                  320: 'b', 380: 'b', 440: 'b', 500: 'b', 560: 'a'}
        check_at = (110, 180, 310, 620, 660, frames - 2)
    if long_mode:
        # Stack the four-row action box over the fully composed 56-tile hostile
        # page, then close it only after the f700 residency/plane snapshot.
        script.update({640: 'a', 710: 'b'})
    problems, invariant_frames = [], 0
    long_records = action_records = None
    long_parent_region = None
    long_restore_events = []
    checked = [0]

    def action_region():
        planes = []
        for row in range(1, 10):
            for col in range(13, 20):
                tile = pb.memory[BGMAP + 32 * row + col]
                at = tile_data_addr(tile)
                planes.append(bytes(pb.memory[at:at + 16]))
        return tuple(planes)

    if long_mode:
        _blank_code, blank_labels = gbasm.assemble(
            menuvwf.ACTION_BLANK_SRC, menuvwf.ACTION_BLANK_AT)

        def long_restored(_ctx=None):
            if frame['n'] >= 700:
                long_restore_events.append((frame['n'], action_region()))

        pb.hook_register(menuvwf.ACTION_BLANK_BANK, blank_labels['abrestored'],
                         long_restored, None)

    for f in range(frames):
        frame['n'] = f
        if f in script:
            pb.button(script[f], PRESS_FRAMES)
        pb.tick()
        if pb.memory[0xFF40] & 0x80:
            bad = frame_invariant(pb, profile)
            if bad:
                invariant_frames += 1
                if len(problems) < 8:
                    problems += ['f%d (%d,%d) tile $%02X -- %s' % ((f,) + b)
                                 for b in bad[:3]]
        if ram and flips:
            flip = flips[-1]
            # Keep sampling until the next row-0 starts another page.  The game's
            # shadow-to-BG publish happens several frames after all five row drawers,
            # so a short fixed tail would miss the actual settle point.
            if flip is page_build['value'] and not flip['settled']:
                if not pb.memory[0xFF40] & 0x80:
                    # Retain the legacy classification for unrelated/fallback routes;
                    # a true regional Items flip is required to avoid it below.
                    states = 'W' * len(flip['old']['rows'])
                else:
                    states = []
                    for key, old_codes in sorted(flip['old']['rows'].items()):
                        new_codes = flip['rows'].get(key)
                        old_match = visible_row_matches(pb, profile, key, old_codes)
                        new_match = (new_codes is not None and
                                     visible_row_matches(pb, profile, key, new_codes))
                        blank = (visible_item_row_blank(pb, key) or
                                 visible_item_row_erasing(pb, profile, key, old_codes) or
                                 (new_codes is not None and visible_item_row_erasing(
                                     pb, profile, key, new_codes)))
                        if new_match and old_match:
                            state = '='
                        elif new_match:
                            state = 'N'
                        elif old_match:
                            state = 'O'
                        elif blank:
                            state = 'B'
                        else:
                            state = 'X'
                        states.append(state)
                    states = ''.join(states)
                flip['observations'].append((f, states))
                if all(state in 'N=' for state in states):
                    flip['settled'] = True
        if f in check_at:
            problems += settled_check(pb, profile, 'f%d' % f, checked, drawn)
        if long_mode and f == 620:
            long_records = records(pb, profile)
            long_parent_region = action_region()
        if long_mode and f == 700:
            action_records = records(pb, profile)
            if png:
                stem, ext = os.path.splitext(png)
                action_png = stem + '_action' + (ext or '.png')
                pb.screen.image.save(action_png)
                print('  wrote %s%s' % (action_png,
                                        ' (CGB colour)' if kwargs else ' (DMG grey)'))
        # Keep both sides of the first saved-game page flip.  The compact transition
        # state trace can prove ownership without showing whether otherwise-valid
        # rows are being published at visibly different times.
        if ram and png and f in (1842, 1843, 1844, 1849, 1850, 1851, 1852):
            stem, ext = os.path.splitext(png)
            flip_png = '%s_f%d%s' % (stem, f, ext or '.png')
            pb.screen.image.save(flip_png)
            print('  wrote %s%s' % (flip_png,
                                    ' (CGB colour)' if kwargs else ' (DMG grey)'))
        if ram and f == frames - 2:
            problems += status_fragment_problems(pb)
            if png:
                stem, ext = os.path.splitext(png)
                return_png = stem + '_status_return' + (ext or '.png')
                pb.screen.image.save(return_png)
                print('  wrote %s%s' % (return_png,
                                        ' (CGB colour)' if kwargs else ' (DMG grey)'))
    if png:
        pb.screen.image.save(png)
        print('  wrote %s%s' % (png, ' (CGB colour)' if kwargs else ' (DMG grey)'))

    if ram:
        print('  saved-flow item row calls: ' + ', '.join(
            'f%d/r%d' % (at, rownum) for at, rownum, _key, _codes in item_trace))
        for flip in flips:
            if len(flip['rows']) != 5:
                problems.append('--ram: item page beginning f%d captured only %d rows'
                                % (flip['start'], len(flip['rows'])))
                continue
            old_sig = tuple(sorted(flip['old']['rows'].items()))
            new_sig = tuple(sorted(flip['rows'].items()))
            if old_sig == new_sig:
                continue
            changes = []
            for observation in flip['observations']:
                if not changes or changes[-1][1] != observation[1]:
                    changes.append(observation)
            trace = ', '.join('f%d:%s' % observation for observation in changes)
            print('  page flip f%d: %s' % (flip['start'], trace))
            for at, states in flip['observations']:
                if 'X' in states:
                    problems.append('--ram: page flip f%d has unowned pixels at f%d (%s)'
                                    % (flip['start'], at, states))
                    break
                if 'N' in states and 'O' in states:
                    problems.append('--ram: page flip f%d mixes new and old rows at '
                                    'f%d (%s)' % (flip['start'], at, states))
                    break
            settled = flip['observations'][-1][1] if flip['observations'] else ''
            if any(state not in 'N=' for state in settled):
                problems.append('--ram: page flip f%d does not settle to the new page (%s)'
                                % (flip['start'], settled or 'no observation'))

    if long_mode:
        # prove the synthetic rows really landed -- this mode once "passed" while
        # verifying only the real inventory, because the rewrite fired on the main
        # menu draw and was restaged over
        if long_seen != set(range(len(LONG_ROWS))):
            problems.append('--long: synthetic row calls seen %s, expected 0-%d'
                            % (sorted(long_seen), len(LONG_ROWS) - 1))
        recs = long_records or []
        by_key = {key: (base, cap, raw) for key, base, cap, raw in recs}
        used = 0
        for i, text in enumerate(LONG_ROWS):
            tiles = len(compose(encode(text), profile))
            cap = capneed(tiles)
            expected = used + cap <= menuvwf.POOL_END - menuvwf.POOL_BASE
            if expected:
                used += cap
            key = SHADOW + 32 * (4 + 2 * i)
            record = by_key.get(key)
            if expected and record is None:
                problems.append('--long: row %d (%s) should allocate %d tiles but '
                                'fell back raw' % (i + 1, text, cap))
            elif expected and record[1] != cap:
                problems.append('--long: row %d (%s) cap is %d, expected %d'
                                % (i + 1, text, record[1], cap))
            elif not expected and record is not None:
                problems.append('--long: row %d (%s) has a record after modeled pool '
                                'exhaustion' % (i + 1, text))
            elif not expected:
                raw = bytes(pb.memory[key + 3:key + 7])
                if all(in_pool(profile, value) for value in raw):
                    problems.append('--long: row %d cells hold pool tiles, expected raw '
                                    'codes after exhaustion' % (i + 1))
        if profile['mode'] == 'dot-proportional':
            if action_records is None:
                problems.append('--long: no worst-page action-overlay snapshot captured')
            else:
                caps = [cap for _key, _base, cap, _raw in action_records]
                expected_caps = [
                    capneed(len(compose(encode(text), profile)))
                    for text in LONG_ROWS + list(LONG_ACTION_ROWS)
                ]
                if len(caps) != len(expected_caps) or sum(caps) != sum(expected_caps):
                    problems.append('--long: worst item+action residency is %d record(s), '
                                    '%d cap tiles; expected %d and %d'
                                    % (len(caps), sum(caps), len(expected_caps),
                                       sum(expected_caps)))
                occupied = []
                admitted_runs = tuple(profile['runs']) + (
                    (menuvwf.ACTION_POOL_BASE, menuvwf.ACTION_POOL_END),)
                for _key, base, cap, _raw in action_records:
                    if not any(lo <= base and base + cap <= hi
                               for lo, hi in admitted_runs):
                        problems.append('--long: slice $%02X+%d crosses a proven pool run'
                                        % (base, cap))
                    occupied.extend(range(base, base + cap))
                if len(occupied) != len(set(occupied)):
                    problems.append('--long: worst item+action slices overlap in VRAM')
        if long_parent_region is None:
            problems.append('--long: hostile parent region snapshot was not captured')
        if len(long_restore_events) != 1:
            problems.append('--long: B-cancel parent restore events are %s, expected one'
                            % [event[0] for event in long_restore_events])
        elif long_parent_region is not None and \
                long_restore_events[0][1] != long_parent_region:
            problems.append('--long: exact B-cancel restore differs from hostile parent')
    pb.stop(save=False)
    if tmp is not None:
        tmp.cleanup()
    return problems, invariant_frames, checked[0]


def drive_info_screen(rom, profile, kind, seals=(), synthetic=False, png=None,
                      frames=600):
    """Force the real box-7/19 dispatch and verify every proportional row plane-exact.

    ``synthetic`` replaces box 7's already-staged rows at the first drawer call.  It
    proves both ends of the wider contract: an 18-slash, 16-tile row exercises the
    overlapping queue passes, while 21 narrow ``i`` glyphs exercise the character cap.
    The title stays deliberately ineligible, proving raw fallback can share the box.
    """
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open('saves/dungeon.state', 'rb') as state:
        pb.load_state(state)

    if kind not in ('help', 'seals'):
        raise ValueError(kind)
    frame = {'n': 0}
    dispatches = {'n': 0}
    rewritten = {'done': False}
    target_seen = {'value': False}
    drawn = {}

    def on_dispatch(_ctx=None):
        dispatches['n'] += 1
        if dispatches['n'] != 1:
            return
        if kind == 'help':
            pb.memory[0xCF7A] = 4
            pb.memory[0xCF7B] = 0x80
            pb.memory[0xC6BC] = 0
            pb.register_file.A = 4
        else:
            pb.memory[0xC6BC] = 0
            pb.memory[0xC6BD] = len(seals)
            for i, seal in enumerate(seals):
                pb.memory[0xC6BE + i] = seal
            pb.memory[0xC6BE + len(seals)] = 0xFF
            pb.register_file.A = 5

    synthetic_rows = None
    if synthetic:
        rows = [[0x7D], encode('/' * 18), encode('i' * 21),
                encode('Boundary overlap'), encode('Tail')]
        synthetic_rows = b''.join(bytes(row + [0xFF]) for row in rows) + b'\xFF'

    def at_far(_ctx=None):
        shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
        if shape == (0, 3, 5, 18, 0):
            target_seen['value'] = True
        if (synthetic_rows is not None and not rewritten['done'] and
                shape == (0, 3, 5, 18, 0) and pb.register_file.D == 0):
            rewritten['done'] = True
            for i, value in enumerate(synthetic_rows):
                pb.memory[STAGING + i] = value
        if synthetic_rows is not None and shape == (0, 3, 5, 18, 0) and pb.register_file.D == 1:
            # The real help transition draws with LCD off, which already tests the
            # direct 16-tile copier. Turn it on for the synthetic wide row so the same
            # fixture also traverses both overlapping VBlank queue passes.
            pb.memory[0xFF40] |= 0x80
        key = pb.register_file.HL
        src = (pb.memory[0xC6A0] << 8) | pb.memory[0xC69F]
        if 0xC000 <= src < 0xE000:
            row = []
            for at in range(src, src + 32):
                value = pb.memory[at]
                if value == 0xFF:
                    break
                row.append(value)
            drawn[key] = row

    pb.hook_register(4, 0x48AA, on_dispatch, None)
    pb.hook_register(FAR_BANK, profile['entry'], at_far, None)
    problems = []
    badframes = 0
    checked = [0]
    for f in range(frames):
        frame['n'] = f
        if f == 120:
            pb.button('b', PRESS_FRAMES)
        pb.tick()
        if target_seen['value'] and f >= 150 and pb.memory[0xFF40] & 0x80:
            bad = frame_invariant(pb, profile, drawn)
            if bad:
                badframes += 1
                if len(problems) < 8:
                    problems += ['f%d (%d,%d) tile $%02X -- %s' % ((f,) + entry)
                                 for entry in bad[:3]]
        if f in (160, 240, 400, frames - 2):
            problems += settled_check(pb, profile, '%s f%d' % (kind, f),
                                      checked, drawn)

    recs = records(pb, profile)
    if not recs:
        problems.append('%s: no proportional record was allocated' % kind)
    for key, base, cap, raw in recs:
        if raw != 0 and key in drawn:
            problems.append('%s: row $%04X recorded raw prefix %d, expected 0'
                            % (kind, key, raw))
        if not any(lo <= base and base + cap <= hi for lo, hi in profile['runs']):
            problems.append('%s: slice $%02X+%d crosses a proven pool run'
                            % (kind, base, cap))
    if synthetic:
        if not rewritten['done']:
            problems.append('synthetic help rows were never injected')
        by_codes = {tuple(drawn.get(key, ())): (base, cap, raw)
                    for key, base, cap, raw in recs}
        wide = by_codes.get(tuple(encode('/' * 18)))
        narrow = by_codes.get(tuple(encode('i' * 21)))
        if wide is None or wide[1:] != (16, 0):
            problems.append('synthetic 16-tile row record is %r, expected cap=16 raw=0'
                            % (wide,))
        if len(compose(encode('/' * 18), profile)) != 16:
            problems.append('synthetic wide fixture no longer paints exactly 16 tiles')
        if narrow is None or narrow[2] != 0:
            problems.append('synthetic 21-character row was not proportionally recorded')
    if png:
        pb.screen.image.save(png)
        print('  wrote %s' % png)
    pb.stop(save=False)
    return problems, badframes, checked[0], len(recs)


def help_seal_battery(rom, profile, png=None):
    if profile['mode'] != 'dot-proportional':
        return ['--help-seals requires the approved proportional renderer'], 0, 0
    cases = [('help real', 'help', (), False),
             ('help synthetic-wide', 'help', (), True)]
    cases += [('seals %d-%d' % (start, start + 3), 'seals', tuple(range(start, start + 4)),
               False) for start in range(0, 20, 4)]
    problems, badframes, checked = [], 0, 0
    for index, (label, kind, seals, synthetic) in enumerate(cases):
        shot = None
        if png:
            stem, ext = os.path.splitext(png)
            shot = '%s_%02d%s' % (stem, index, ext or '.png')
        case_problems, case_bad, case_checked, rec_count = drive_info_screen(
            rom, profile, kind, seals, synthetic, shot)
        print('  %-23s %2d record(s), %2d exact check(s), %d problem(s)'
              % (label, rec_count, case_checked, len(case_problems)))
        problems += ['%s: %s' % (label, problem) for problem in case_problems]
        badframes += case_bad
        checked += case_checked
    return problems, badframes, checked


def ground_header_battery(rom, profile, png=None, frames=440):
    """Force the real Floor action screen and verify box 5 plane-exact."""
    if profile['mode'] != 'dot-proportional':
        return [], 0, 0
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open('saves/dungeon.state', 'rb') as state:
        pb.load_state(state)

    dispatched = {'n': 0}
    injected = {'done': False}
    target = encode('True Rapier+99')
    drawn = {}
    target_key = {'value': None}

    def on_dispatch(_ctx=None):
        dispatched['n'] += 1
        if dispatched['n'] == 1:
            pb.register_file.A = 20

    def at_far(_ctx=None):
        shape = tuple(pb.memory[a] for a in range(0xC69A, 0xC69F))
        key = pb.register_file.HL
        src = (pb.memory[0xC6A0] << 8) | pb.memory[0xC69F]
        if shape == (0, 0, 1, 18, menuvwf.ROM_RAW_PREFIX_BIT):
            if pb.register_file.D != 0 or src != STAGING:
                return
            row = bytes([0] + target + [0xFF])
            for index, value in enumerate(row):
                pb.memory[STAGING + index] = value
            injected['done'] = True
            target_key['value'] = key
        if 0xC000 <= src < 0xE000:
            row = []
            for at in range(src, src + 32):
                value = pb.memory[at]
                if value == 0xFF:
                    break
                row.append(value)
            drawn[key] = row

    pb.hook_register(4, 0x48AA, on_dispatch, None)
    pb.hook_register(FAR_BANK, profile['entry'], at_far, None)
    problems, badframes, checked = [], 0, [0]
    for frame in range(frames):
        if frame == 60:
            pb.button('b', PRESS_FRAMES)
        if frame == 160:
            pb.button('a', PRESS_FRAMES)
        pb.tick()
        if injected['done'] and frame >= 220 and pb.memory[0xFF40] & 0x80:
            bad = frame_invariant(pb, profile, drawn)
            if bad:
                badframes += 1
                if len(problems) < 8:
                    problems += ['Floor f%d (%d,%d) tile $%02X -- %s'
                                 % ((frame,) + entry) for entry in bad[:3]]
        if frame in (260, 340, frames - 2):
            problems += settled_check(pb, profile, 'Floor f%d' % frame,
                                      checked, drawn)

    if not dispatched['n']:
        problems.append('Floor: bank-4 dispatcher never fired')
    if not injected['done'] or target_key['value'] is None:
        problems.append('Floor: exact box-5 header never reached the proportional path')
    else:
        key = target_key['value']
        match = [record for record in records(pb, profile)
                 if record[0] == key and record[3] == 1]
        if not match:
            problems.append('Floor: header has no raw-prefix-1 allocator record')
        elif not visible_row_matches(pb, profile, key, target, raw=1):
            problems.append('Floor: True Rapier+99 visible planes do not match approved font')
    if png:
        pb.screen.image.save(png)
        print('  wrote %s' % png)
    pb.stop(save=False)
    return problems, badframes, checked[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--long', action='store_true',
                    help='synthetic worst-case rows: counters, hyphens, '
                         'pool exhaustion')
    ap.add_argument('--png')
    ap.add_argument('--ram', help='boot this cartridge-RAM fixture and verify Joey\'s '
                                  'real floor-7 pages plus the Remove action menu')
    ap.add_argument('--help-seals', action='store_true',
                    help='force box 7 plus all five box-19 seal pages, including '
                         'synthetic 16-tile/21-character rows')
    a = ap.parse_args()
    if sum(bool(mode) for mode in (a.long, a.ram, a.help_seals)) > 1:
        raise SystemExit('menuspill: --long, --ram and --help-seals are separate flows')
    if a.ram and not os.path.exists(a.ram):
        raise SystemExit('menuspill: missing RAM fixture: %s' % a.ram)

    profile = renderer_profile(a.rom)
    print('menuspill: detected %s renderer at %d:$%04X'
          % (profile['mode'], FAR_BANK, profile['entry']))
    if a.help_seals:
        problems, badframes, checked = help_seal_battery(a.rom, profile, a.png)
    else:
        problems, badframes, checked = drive(a.rom, profile, a.long, a.png, ram=a.ram)
    ground_png = None
    if a.png:
        stem, ext = os.path.splitext(a.png)
        ground_png = stem + '_ground' + (ext or '.png')
    ground_problems, ground_badframes, ground_checked = ground_header_battery(
        a.rom, profile, ground_png)
    print('  Floor header: %d exact check(s), %d invariant frame(s), %d problem(s)'
          % (ground_checked, ground_badframes, len(ground_problems)))
    problems += ground_problems
    badframes += ground_badframes
    checked += ground_checked
    label = 'menuspill%s' % (' --long' if a.long else
                             (' --ram' if a.ram else
                              (' --help-seals' if a.help_seals else '')))
    for p in problems[:12]:
        print('  ' + p)
    if not checked:
        raise SystemExit('%s: no composed row was ever verified -- the target screen '
                         'never opened, so this measured nothing.' % label)
    print('%s: %d plane-exact row check(s), %d invariant-violating frame(s), '
          '%d problem(s)' % (label, checked, badframes, len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
