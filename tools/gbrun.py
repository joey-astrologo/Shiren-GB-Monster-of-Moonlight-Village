#!/usr/bin/env python3
"""Boot a ROM headless, drive it, screenshot it, and trace which routine drew the text.

The point of this over Mesen is that it is REPEATABLE and scriptable: the same button
script produces the same frame every run, so a screen can be diffed across builds, and a
hook can attribute a string on screen to the routine that copied it.

    gbrun.py <rom> --frames 600 --png out.png
    gbrun.py <rom> --frames 600 --trace          # which copy loop ran, and on what

`--trace` hooks every string-copy loop known in this ROM (COPY_SITES) plus the DTE
expander, and reports hit counts with the source addresses each one read. That is how to
answer "which renderer draws this screen" without guessing -- the question that made the
first DTE hook attempt wrong, because bank 11's menu labels turned out to be copied by
11:$52C6, a site no earlier list named.

Buttons: --press a,start,down:120 presses at the given frame (default 60 apart).
"""
import argparse
import json
import os
import sys

import codec
import lcdblankaudit


LCD_TRACE_ENV = 'SHIREN_LCD_TRACE'
LCD_TRACE_ALL_ENV = 'SHIREN_LCD_TRACE_ALL'


def _install_lcd_trace(pb, rom):
    """Install an opt-in instruction-level LCD-off recorder on a new PyBoy instance.

    Every runtime fixture obtains PyBoy through :func:`_import_pyboy`, so this gives the
    audit one observation point without weakening or duplicating the fixtures.  It is
    inert unless SHIREN_LCD_TRACE names a JSONL output file.
    """
    output = os.environ.get(LCD_TRACE_ENV)
    if not output:
        return
    directory = os.path.dirname(os.path.abspath(output))
    os.makedirs(directory, exist_ok=True)
    sites = lcdblankaudit.display_mutators(rom)
    if not os.environ.get(LCD_TRACE_ALL_ENV):
        # The causal set contains every locally provable direct blank, every shadow
        # producer which can request a later blank, and the one native VBlank publisher
        # which applies that request.  Hooking all 153 enable/scroll/configuration sites
        # makes long smoke tests prohibitively slow; SHIREN_LCD_TRACE_ALL remains
        # available for a focused exhaustive run.
        sites = [site for site in sites
                 if ((site['target'] == 'LCDC-shadow' and
                      site['effect'] != 'explicit-on') or
                     (site['target'] == 'LCDC' and
                      (lcdblankaudit._is_locally_off(site['effect']) or
                       (site['bank'], site['address']) == (0, 0x0737))))]

    def stack_ids():
        depth = pb.memory[0xC534]
        if depth > 9:
            return []
        return [pb.memory[0xC535 + index] for index in range(depth + 1)]

    def make(site):
        def callback(_context):
            target_address = 0xFF40 if site['target'] == 'LCDC' else 0xC110
            before = pb.memory[target_address]
            if site['encoding'] == 'res-[hl]':
                incoming = before & 0x7F
            elif site['encoding'] == 'set-[hl]':
                incoming = before | 0x80
            else:
                incoming = pb.register_file.A
            if incoming & 0x80:
                return
            sp = pb.register_file.SP
            returns = []
            for offset in range(0, 12, 2):
                lo = pb.memory[(sp + offset) & 0xFFFF]
                hi = pb.memory[(sp + offset + 1) & 0xFFFF]
                returns.append(lo | (hi << 8))
            record = {
                'fixture': os.path.basename(sys.argv[0]),
                'argv': sys.argv[1:],
                'rom': os.path.basename(rom),
                'frame': pb.frame_count,
                'site': '%d:$%04X' % (site['bank'], site['address']),
                'target': site['target'],
                'encoding': site['encoding'],
                'effect': site['effect'],
                'before': before,
                'incoming': incoming,
                'transition': bool(before & 0x80),
                'lcdc': pb.memory[0xFF40],
                'lcdc_shadow': pb.memory[0xC110],
                'rom_bank': pb.memory[0x4000],
                'screen': pb.memory[0xC6A3],
                'depth': pb.memory[0xC534],
                'stack': stack_ids(),
                'state': [pb.memory[address] for address in
                          (0xC1B1, 0xC1B2, 0xC1B3, 0xC1B4,
                           0xC1B5, 0xC1B6, 0xC1B7)],
                'menu': [pb.memory[address] for address in
                         (0xC6A4, 0xC6A5, 0xC6A6, 0xC6AA,
                          0xC6AC, 0xC6BB, 0xC6DE)],
                'sp': sp,
                'returns': returns,
            }
            with open(output, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(record, sort_keys=True) + '\n')
        return callback

    for site in sites:
        try:
            pb.hook_register(site['bank'], site['address'], make(site), None)
        except Exception:
            # The static census deliberately includes uncertain native/data matches.
            # A non-hookable address remains in the TSV for review and must not prevent
            # executable sites from being observed.
            pass


def _import_pyboy():
    """Import pyboy with this directory OFF sys.path.

    `tools/dis.py` shadows the stdlib `dis`, and Python always puts a script's own
    directory at sys.path[0]. `inspect` does `import dis`, pysdl2 imports `inspect`, and
    pyboy imports pysdl2 -- so importing pyboy from anything in tools/ dies with
    "module 'dis' has no attribute COMPILER_FLAG_NAMES". Dropping our own directory and
    evicting the wrong module fixes it for good; nothing local is needed in this file.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    mod = sys.modules.get('dis')
    if mod is not None and not hasattr(mod, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    if not os.environ.get(LCD_TRACE_ENV):
        return pyboy.PyBoy

    def TracedPyBoy(rom, *args, **kwargs):
        pb = pyboy.PyBoy(rom, *args, **kwargs)
        _install_lcd_trace(pb, rom)
        return pb
    return TracedPyBoy

# Every routine seen to copy string bytes toward the screen, and what it is.
#   (bank, cpu-addr, name, source-register)
# The register named is the one holding the SOURCE. Getting this wrong is how the box
# drawer came to be described as reading WRAM: at 31:$40D8 hl is its DESTINATION (the
# $C300 tilemap staging buffer) and bc is its source, loaded from $C69F/$C6A0 -- so the
# site is listed at $40E4, by which point bc is loaded and not yet advanced.
COPY_SITES = [
    (13, 0x40DB, 'composer 18-cell loop', 'hl'),
    (13, 0x6893, 'composer uncapped loop (now jp to bank 0)', 'hl'),
    (31, 0x40E4, 'menu box row drawer', 'bc'),
    (30, 0x7E8A, 'item verb staging -> $C616', 'hl'),
    (11, 0x52C6, 'bank 11 menu label, via the $52E0 table', 'table'),
    (11, 0x52BC, 'bank 11 raw copy until $FF', 'hl'),
    (11, 0x52D5, 'bank 11 menu label inner copy', 'hl'),
]

EXPANDER = (0, 0x0092, 'dte_emit', 'a')

# HOLD each press for several frames. pyboy's default is one frame and this ROM does not
# always sample the pad that frame: the seeded dungeon walk driven with 1-frame presses
# moved the player but reached the composer ZERO times, which is what made "a scripted
# walk never triggers a dungeon message" look like a fact about the game. The same walk
# with 5-frame presses fires the composer 186 times and produces real combat messages.
PRESS_FRAMES = 5

# The same seeded walk msgdur.py and crashscan.py use, so a run is comparable across all
# three. Movement and attacks only: `start` opens the menu and `a` then selects Quit.
WALK_SEQ = ['right', 'down', 'left', 'up', 'a', 'right', 'down', 'a']



def _reg16(pb, name):
    """A 16-bit register pair by name. pyboy exposes HL whole but bc/de only as halves."""
    rf = pb.register_file
    if name == 'hl':
        return rf.HL
    hi, lo = name.upper()
    return (getattr(rf, hi) << 8) | getattr(rf, lo)


def run(rom, frames, presses=(), trace=False, png=None, quiet=False, state=None,
        walk_seed=None):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)

    hits = {}
    if trace:
        def make(name, kind):
            def cb(ctx):
                rec = hits.setdefault(name, {'n': 0, 'src': set(), 'events': set()})
                rec['n'] += 1
                if kind in ('hl', 'bc') and len(rec['src']) < 12:
                    rec['src'].add(_reg16(pb, kind))
                elif kind == 'table' and len(rec['src']) < 12:
                    # 11:$52C6 receives the $52E0 pointer-table index in A.  Recording
                    # only the routine hit count made short, state-dependent labels
                    # impossible to associate with the screen that requested them.
                    rec['src'].add(pb.register_file.A)
                    rec['events'].add((pb.register_file.A, _reg16(pb, 'de')))
            return cb
        for bank, addr, name, kind in COPY_SITES + [EXPANDER]:
            try:
                pb.hook_register(bank, addr, make(name, kind), None)
            except Exception as exc:            # a site may not exist in every build
                if not quiet:
                    print('  (no hook at %d:$%04X: %s)' % (bank, addr, exc))

    sched = {}
    for i, p in enumerate(presses):
        if ':' in p:
            btn, at = p.split(':')
            sched.setdefault(int(at), []).append(btn)
        else:
            sched.setdefault(60 * (i + 1), []).append(p)

    # A press SCHEDULE cannot reach combat, death or the village wake-up scene -- those
    # need real play, which is what --walk-seed is for. Same walk dte_scan, msgdur and
    # crashscan drive, same seed, same run, so a screenshot taken this way is reproducible
    # and lines up frame for frame with a msglog.py transcript of the same seed.
    rng = __import__('random').Random(walk_seed) if walk_seed is not None else None
    for f in range(frames):
        if rng is not None:
            if f >= 60 and (f - 60) % 12 == 0:
                pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        else:
            for btn in sched.get(f, ()):
                pb.button(btn, PRESS_FRAMES)
        pb.tick()

    if png:
        pb.screen.image.save(png)
    result = {'hits': hits, 'tiles': None}
    if trace:
        result['tiles'] = [[pb.tilemap_background[x, y] for x in range(20)]
                           for y in range(18)]
    pb.stop(save=False)
    return result


def _scan_sites():
    """-> [(bank, addr, name, reg)] for the loops that DO expand, from dte_rom's labels.

    `reg` names the register holding the source pointer. It is not always hl: the menu
    box drawer keeps its DESTINATION in hl and reads through bc, which is what the
    previous attempt at this got backwards.

    Imported only after pyboy is loaded, so the `dis` shadowing described in
    _import_pyboy() cannot bite, and the path is put back afterwards.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    try:
        import dte_rom
        _, labels = dte_rom.build_expander()
        out = []
        for bank, addr, name, reg in dte_rom.SCAN_SITES + dte_rom.STAGER_SITES:
            out.append((bank, labels[addr] if isinstance(addr, str) else addr, name, reg))
        return out
    finally:
        sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]


def dte_scan(rom, frames, presses=(), state=None, walk_seed=None):
    """Record which strings an EXPANDING copy loop actually reads.

    -> (seen, initial_seen), two ``{loc: site}`` maps in the `bank:$addr` form
    translations are keyed on.

    Hooked at the points where the source register still holds the START of the string:
    `13:$40D8` (the `ld de,$CF07` before the 18-cell loop), bank 0's relocated `loop2`,
    the raw copy, and the box drawer. The current ROM bank is read from `[$4000]` -- byte
    0 of every switchable bank holds that bank's own number, the same convention the
    expander uses to restore its caller.

    ALSO hooked: `dte_rom.STAGER_SITES`, the two routines that copy a dialogue line out of
    the ROM into `$CF8F` before loop2 expands it. Village and story text can be observed
    NO OTHER WAY -- loop2's source is WRAM, so the ROM address never appears in a register
    at the expander and every bank-11/bank-14 string would stay uncompressed for ever. See
    the comment on STAGER_SITES for the three checks that close the gap between "reaches
    the expander" and "was read by the expander".

    Whatever this reports is safe to compress. Whatever it does not report is not proven
    either way, and stays uncompressed.
    """
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    if state:
        # A state parked in the village or a dungeon is the only way to reach the composer:
        # boot, file menu and name entry never touch it, and it is the whole dialogue budget.
        with open(state, 'rb') as f:
            pb.load_state(f)
    seen = {}
    initial_seen = {}

    # Translate built addresses back to the `loc` the allowlist is keyed on. The scan
    # watches the BUILT rom, so a relocated string appears at its new address; without
    # this map it gets recorded under an address that matches no string at all.
    relocmap = {}
    mapfile = os.path.join(os.path.dirname(os.path.abspath(rom)), 'relocmap.tsv')
    if os.path.exists(mapfile):
        for line in open(mapfile, encoding='utf-8'):
            t = line.split('#')[0].strip()
            if '\t' in t:
                built, orig = t.split('\t')[:2]
                relocmap[built.strip()] = orig.strip()

    def make(site, reg):
        def cb(ctx):
            src = _reg16(pb, reg)
            if not 0x4000 <= src <= 0x7FFF:
                return                      # a WRAM-staged line has no ROM home
            bank = pb.memory[0x4000]        # the ROM's own bank-id convention
            built = '%d:$%04X' % (bank, src)
            seen.setdefault(relocmap.get(built, built), site)
        return cb

    for bank, addr, name, reg in _scan_sites():
        pb.hook_register(bank, addr, make('%d:$%04X %s' % (bank, addr, name), reg), None)

    # The stagers also fire at each <br> continuation, so their unknown addresses cannot
    # automatically be dismissed as harmless interior positions.  Observe the queue gate
    # separately as supporting evidence.  Some event continuations enter through $688A,
    # so the decisive check below is structural: an unknown stager entry is safe only if
    # it follows an actual $EE/$EF line boundary (or is a control-only record).
    # The stored pointer is tagged:
    # bit 7 set selects bank 14 and XOR $C0 restores its window; otherwise bank 11 sets
    # bit 6.  Continuations have bit 6 set and do not pass through this initial gate.
    def initial_gate(_ctx=None):
        tagged = pb.memory[0xCF7F] | (pb.memory[0xCF80] << 8)
        hi, lo = tagged >> 8, tagged & 0xFF
        if hi & 0x80:
            bank, addr = 14, ((hi ^ 0xC0) << 8) | lo
        else:
            bank, addr = 11, ((hi | 0x40) << 8) | lo
        if 0x4000 <= addr <= 0x7FFF:
            built = '%d:$%04X' % (bank, addr)
            initial_seen.setdefault(relocmap.get(built, built),
                                    '13:$67ED initial dialogue queue gate')

    pb.hook_register(13, 0x67ED, initial_gate, None)

    sched = {}
    for i, p in enumerate(presses):
        btn, at = (p.split(':') + [str(60 * (i + 1))])[:2]
        sched.setdefault(int(at), []).append(btn)
    # A press SCHEDULE cannot reach combat, death or the village wake-up scene: those need
    # real play. `--walk-seed` swaps in msgdur.py's seeded random walk, which is what makes
    # the composer and the dialogue stagers fire at all. Same seed, same run, so an
    # allowlist entry generated this way is reproducible -- which is the whole point of
    # requiring an observation.
    rng = __import__('random').Random(walk_seed) if walk_seed else None
    for f in range(frames):
        if rng is not None:
            if f >= 60 and (f - 60) % 12 == 0:
                pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        else:
            for btn in sched.get(f, ()):
                pb.button(btn, PRESS_FRAMES)
        pb.tick()
    pb.stop(save=False)
    return seen, initial_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--frames', type=int, default=600)
    ap.add_argument('--png')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--walk-seed', type=int,
                    help='drive with the seeded random walk instead of --press; the only '
                         'way to reach combat, death or the inn scene. Honoured by --png '
                         'and --compare too, so a screenshot of dialogue is reproducible '
                         'and shares frame numbers with msglog.py at the same seed')
    ap.add_argument('--dte-scan', action='store_true',
                    help='report strings an expanding loop read; append to script/build-inputs/dte_ok.tsv')
    ap.add_argument('--append', metavar='TSV',
                    help='merge --dte-scan results into this allowlist')
    ap.add_argument('--press', default='')
    ap.add_argument('--state', help='load a pyboy save state before running (see saves/)')
    ap.add_argument('--compare', metavar='ROM2',
                    help='render the same frame from ROM2 and require it be pixel-identical')
    args = ap.parse_args()
    presses = [p for p in args.press.split(',') if p]

    if args.compare:
        # THE test for a render-path change: a correct DTE build must draw the frame the
        # uncompressed build draws, pixel for pixel. Byte-level round-tripping cannot say
        # this -- it was all green while the file menu drew raw katakana.
        from PIL import Image, ImageChops
        shots = []
        for rom in (args.rom, args.compare):
            out = '/tmp/_gbrun_%d.png' % len(shots)
            run(rom, args.frames, presses, False, out, state=args.state,
                walk_seed=args.walk_seed)
            shots.append(Image.open(out).convert('L'))
        box = ImageChops.difference(*shots).getbbox()
        print('%s vs %s: %s' % (args.rom, args.compare,
                                'IDENTICAL' if box is None else 'DIFFERS at %r' % (box,)))
        sys.exit(0 if box is None else 1)

    if args.dte_scan:
        seen, initial_seen = dte_scan(args.rom, args.frames, presses, args.state,
                                      args.walk_seed)
        rom_bytes = open(args.rom, 'rb').read()
        # Dialogue stagers re-enter after $EE/$EF line boundaries.  The old scanner
        # discarded EVERY address absent from script.json under that label; the rescued-
        # child route proved why that is unsafe, because 14:$5AFD follows an ordinary
        # space inside 14:$5AF5 and is a separately live event entry.  Derive the legal
        # continuation positions from the manifest bytes and fail on anything else.
        starts = continuations = None
        sj = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'script', 'script.json')
        if os.path.exists(sj):
            import json
            records = json.load(open(sj, encoding='utf-8'))['strings']
            starts = {r['loc'] for r in records}
            continuations = set()

            def add_continuations(data, bank, address):
                """Record real line resumes, skipping control-code argument bytes."""
                i = 0
                arity = codec.arity_for(bank)
                while i < len(data):
                    code = data[i]
                    i += 1
                    if code == codec.TERMINATOR:
                        break
                    if code in (0xEE, 0xEF):
                        continuations.add('%d:$%04X' % (bank, address + i))
                    if codec.CONTROL_MIN <= code <= codec.CONTROL_MAX:
                        i += arity.get(code, 0)

            for record in records:
                data = bytes.fromhex(record['hex'])
                bank, address = record['bank'], int(record['loc'].split('$')[1], 16)
                # $EC consumes one argument and its special handler resumes at +2.
                if data[:1] == b'\xEC' and len(data) > 2:
                    continuations.add('%d:$%04X' % (bank, address + 2))
                add_continuations(data, bank, address)

            # Relocation and English wrapping change byte offsets.  The stager observes
            # the BUILT address after each $EE/$EF, while ``script.json`` necessarily
            # describes the original Japanese layout.  Validate those resumes against
            # the actual built records as well.  Exact record starts are still translated
            # back to canonical TSV locations by dte_scan's relocmap; only an interior
            # continuation remains under its built address and reaches this set.
            mapfile = os.path.join(os.path.dirname(os.path.abspath(args.rom)),
                                   'relocmap.tsv')
            if os.path.exists(mapfile):
                for line in open(mapfile, encoding='utf-8'):
                    t = line.split('#')[0].strip()
                    if '\t' not in t:
                        continue
                    built = t.split('\t', 1)[0].strip()
                    bank_s, address_s = built.split(':$')
                    bank, address = int(bank_s), int(address_s, 16)
                    offset = bank * 0x4000 + address - (0x4000 if bank else 0)
                    # A dialogue record cannot legitimately cross the bank boundary.
                    end = min(len(rom_bytes), (bank + 1) * 0x4000)
                    data = rom_bytes[offset:min(end, offset + 0x4000)]
                    add_continuations(data, bank, address)

        def control_only(loc):
            """Is this an untranslatable control record such as ``EC 84 FF``?"""
            bank_s, address_s = loc.split(':$')
            bank, address = int(bank_s), int(address_s, 16)
            offset = bank * 0x4000 + address - (0x4000 if bank else 0)
            arity = {0xE0: 1, 0xE7: 1, 0xEC: 1, 0xF0: 1}
            used = False
            for _ in range(64):
                if not 0 <= offset < len(rom_bytes):
                    return False
                code = rom_bytes[offset]
                offset += 1
                if code == 0xFF:
                    return used
                if not 0xE0 <= code <= 0xF4:
                    return False
                used = True
                offset += arity.get(code, 0)
            return False

        if starts is not None:
            unknown = {k: v for k, v in seen.items() if k not in starts}
            interior = {k: v for k, v in unknown.items() if k in continuations}
            controls = {k: v for k, v in unknown.items() if control_only(k)}
            unexplained = {k: v for k, v in unknown.items()
                           if k not in interior and k not in controls}
            seen = {k: v for k, v in seen.items() if k in starts}
            if interior:
                print('%d continuation address(es) dropped (mid-string <br> re-entry)'
                      % len(interior))
            if controls:
                print('%d control-only runtime entry address(es) dropped' % len(controls))
            if unexplained:
                for loc, site in sorted(unexplained.items()):
                    evidence = initial_seen.get(loc, site)
                    print('UNEXTRACTED runtime entry %-11s via %s' % (loc, evidence))
                raise SystemExit('gbrun: %d live dialogue entry point(s) are neither '
                                 'extracted starts nor proven line continuations'
                                 % len(unexplained))
        print('%d string(s) read by an expanding loop' % len(seen))
        for loc, site in sorted(seen.items()):
            print('  %-11s  via %s' % (loc, site))
        if args.append:
            old = set()
            blocked = set()
            if os.path.exists(args.append):
                for line in open(args.append, encoding='utf-8'):
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[:2] == ['#', 'BLOCK']:
                        blocked.add(fields[2])
                    t = line.split('#')[0].strip()
                    if t:
                        old.add(t.split('\t')[0].strip())
            new = sorted(set(seen) - old - blocked)
            with open(args.append, 'a', encoding='utf-8') as f:
                if not old:
                    f.write('# strings OBSERVED being read by a copy loop that expands DTE.\n'
                            '# Generated by gbrun.py --dte-scan. Never edit by hand: an\n'
                            '# unobserved string here renders DTE codes as raw glyphs.\n'
                            '# loc\tsite\n')
                for loc in new:
                    f.write('%s\t%s\n' % (loc, seen[loc]))
            skipped = set(seen) & blocked
            if skipped:
                print('skipped %d BLOCKed loc(s) whose prior compression failed a route '
                      'battery' % len(skipped))
            print('appended %d new loc(s) to %s' % (len(new), args.append))
        return

    r = run(args.rom, args.frames, presses, args.trace, args.png, state=args.state,
            walk_seed=args.walk_seed)
    if args.png:
        print('wrote %s' % args.png)
    if args.trace:
        if not r['hits']:
            print('no copy site fired')
        for name, rec in sorted(r['hits'].items(), key=lambda kv: -kv[1]['n']):
            src = ' '.join('$%04X' % s for s in sorted(rec['src'])[:8])
            if rec['events']:
                src += '  ' + ' '.join('$%02X->$%04X' % event
                                       for event in sorted(rec['events'])[:8])
            print('%6d  %-44s %s' % (rec['n'], name, src))


if __name__ == '__main__':
    main()
