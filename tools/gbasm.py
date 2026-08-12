#!/usr/bin/env python3
"""Minimal LR35902 assembler -- the inverse of dis.py, built from dis.py's own tables.

The opcode table is not retyped here. It is DERIVED by inverting `dis.py`'s format
strings, so the assembler and the disassembler cannot drift apart: if a byte assembles
to something, disassembling it prints the line back. `selftest()` asserts exactly that
over every instruction this module can emit, which is why hand-written ROM patches can
be trusted without an emulator in the loop.

Source syntax is whatever dis.py PRINTS, plus labels:

    label:              ; a colon-terminated name, alone on the line
      ld a,$20          ; operands may be $hex or a decimal int
      ld [$3F00],a
      jr nz,label       ; jr/jp/call take a label or a literal address
      db $00,$FF        ; raw bytes

usage: gbasm.py --selftest
"""
import re
import sys
import os
import importlib.util


def _load_gbdis():
    """Load tools/dis.py BY PATH, under a name that cannot collide.

    `import dis` is ambiguous here: this directory holds a `dis.py`, but the stdlib has
    one too, and `inspect` imports the stdlib one -- so whichever landed in sys.modules
    first wins. That resolved differently depending on whether pyboy had been imported
    yet, which is not a thing any module should be sensitive to.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dis.py')
    spec = importlib.util.spec_from_file_location('_shiren_gbdis', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gbdis = _load_gbdis()


def _patterns():
    """-> {normalised-text: (opcode, kind)}; kind in {'', 'd8', 'a8', 'r8', 'd16'}."""
    pats = {}

    def add(text, op, kind):
        # first definition wins: dis.py's tables are unambiguous, but ld a,a etc.
        # appear in both the regular grid and nowhere else, so this is just a guard
        pats.setdefault(_norm(text), (op, kind))

    for tbl in (gbdis.LOW, gbdis.HIGH):
        for op, (fmt, extra) in tbl.items():
            if '%(r8s)s' in fmt:      # ld hl,sp+n -- no call site needs it
                continue
            if extra == 0:
                add(fmt, op, '')
            elif extra == 1:
                for kind in ('d8', 'a8', 'r8'):
                    if '%%(%s)s' % kind in fmt:
                        add(fmt.replace('%%(%s)s' % kind, '{}'), op, kind)
            else:
                for kind in ('d16', 'a16'):
                    if '%%(%s)s' % kind in fmt:
                        add(fmt.replace('%%(%s)s' % kind, '{}'), op, 'd16')

    # the regular grids dis.py decodes arithmetically rather than from a table
    for op in range(0x40, 0x80):
        if op == 0x76:
            continue
        add('ld %s,%s' % (gbdis.R[(op >> 3) & 7], gbdis.R[op & 7]), op, '')
    add('halt', 0x76, '')
    for op in range(0x80, 0xC0):
        add('%s%s' % (gbdis.ALU[(op >> 3) & 7], gbdis.R[op & 7]), op, '')
    return pats


def _norm(s):
    """Collapse whitespace so `ld  a , $20` and `ld a,$20` are the same line."""
    return re.sub(r'\s+', ' ', s.replace(' ,', ',').replace(', ', ',')).strip().lower()


PATTERNS = _patterns()
# Exact forms are tried before templates, and templates longest-prefix first, so that
# `cp a` beats `cp {}` and `jr nz,label` beats `jr {}` -- otherwise `jr {}` swallows the
# condition as part of its operand.
EXACT = {p: v for p, v in PATTERNS.items() if '{}' not in p}
TEMPLATES = sorted(((p.split('{}')[0], p.split('{}')[1], op, kind)
                    for p, (op, kind) in PATTERNS.items() if '{}' in p),
                   key=lambda t: -len(t[0]))
# CB-prefixed ops, assembled separately: `bit 7,a` / `sla a` / `res 3,[hl]` ...
CB_BIT = {'bit': 1, 'res': 2, 'set': 3}


def _match(line):
    """-> (opcode, kind, operand-text) for one normalised instruction."""
    if line in EXACT:
        op, kind = EXACT[line]
        return op, kind, None
    for head, tail, op, kind in TEMPLATES:
        if line.startswith(head) and line.endswith(tail) and len(line) > len(head) + len(tail):
            return op, kind, line[len(head):len(line) - len(tail)] if tail else line[len(head):]
    raise SyntaxError('cannot assemble %r' % line)


def _cb(line):
    m = re.match(r'^(bit|res|set) (\d),(\S+)$', line)
    if m and m.group(3) in gbdis.R:
        return bytes([0xCB, (CB_BIT[m.group(1)] << 6) | (int(m.group(2)) << 3)
                      | gbdis.R.index(m.group(3))])
    m = re.match(r'^(%s) (\S+)$' % '|'.join(gbdis.CBOPS), line)
    if m and m.group(2) in gbdis.R:
        return bytes([0xCB, (gbdis.CBOPS.index(m.group(1)) << 3) | gbdis.R.index(m.group(2))])
    return None


def _value(tok, labels, where):
    tok = tok.strip()
    if tok in labels:
        return labels[tok]
    try:
        return int(tok[1:], 16) if tok.startswith('$') else int(tok, 0)
    except ValueError:
        raise SyntaxError('%s: cannot resolve operand %r' % (where, tok))


def _split(src):
    """-> [(kind, payload)] with comments and blank lines removed."""
    out = []
    for raw in src.splitlines():
        line = raw.split(';')[0].strip()
        while line:
            m = re.match(r'^([A-Za-z_.][A-Za-z0-9_.]*):\s*', line)
            if not m:
                break
            out.append(('label', m.group(1)))
            line = line[m.end():]
        if line:
            out.append(('insn', _norm(line)))
    return out


def _size(line):
    if line.startswith('db '):
        return len(line[3:].split(','))
    if _cb(line):
        return 2
    _, kind, arg = _match(line)
    if arg is None:
        return 1
    return 1 + (2 if kind == 'd16' else 1)


def assemble(src, org):
    """Assemble `src` as if loaded at CPU address `org`. -> (bytes, {label: addr})."""
    items = _split(src)

    labels, pc = {}, org
    for kind, payload in items:
        if kind == 'label':
            if payload in labels:
                raise SyntaxError('duplicate label %r' % payload)
            labels[payload] = pc
        else:
            pc += _size(payload)

    out, pc = bytearray(), org
    for kind, line in items:
        if kind == 'label':
            continue
        if line.startswith('db '):
            for tok in line[3:].split(','):
                out.append(_value(tok, labels, line) & 0xFF)
            pc = org + len(out)
            continue
        cb = _cb(line)
        if cb:
            out += cb
            pc = org + len(out)
            continue
        op, akind, arg = _match(line)
        out.append(op)
        if arg is not None:
            v = _value(arg, labels, line)
            if akind == 'd16':
                out += bytes([v & 0xFF, (v >> 8) & 0xFF])
            elif akind == 'a8':
                out.append(v & 0xFF)
            elif akind == 'r8':
                rel = v - (pc + 2)
                if not -128 <= rel <= 127:
                    raise SyntaxError('%r: jr out of range (%d)' % (line, rel))
                out.append(rel & 0xFF)
            else:
                if not 0 <= v <= 0xFF:
                    raise SyntaxError('%r: %s does not fit a byte' % (line, arg))
                out.append(v & 0xFF)
        pc = org + len(out)
    return bytes(out), labels


def disassemble(code, org):
    """Round-trip helper: the lines dis.py prints for `code` placed at `org`."""
    lines, off = [], 0
    while off < len(code):
        txt, n = gbdis.decode(code, off, org + off)
        lines.append(_norm(txt))
        off += n
    return lines


def selftest():
    """Assemble every emittable instruction, then require dis.py to read it back."""
    checked = 0
    for pat, (op, kind) in sorted(PATTERNS.items(), key=lambda kv: kv[1][0]):
        if kind == 'r8':
            src = 'here:\n %s' % pat.replace('{}', 'here')
            code, _ = assemble(src, 0x0100)
            assert code[0] == op and code[1] == 0xFE, (pat, code.hex())
        else:
            arg = {'': None, 'd8': '$5A', 'a8': '$FF47', 'd16': '$3F00'}[kind]
            src = pat if arg is None else pat.replace('{}', arg)
            code, _ = assemble(src, 0x0100)
            assert code[0] == op, (pat, code.hex())
            back = disassemble(code, 0x0100)
            assert back == [_norm(src)], (pat, back)
        checked += 1
    for line in ('bit 7,a', 'res 3,[hl]', 'set 0,b', 'sla a', 'swap a', 'srl [hl]'):
        code, _ = assemble(line, 0x0100)
        assert disassemble(code, 0x0100) == [line], (line, disassemble(code, 0x0100))
        checked += 1
    # labels, forward and backward branches, and db
    code, labels = assemble("""
        start:  ld a,$20
                jr nz,start
                call target
                db $01,$02
        target: ret
    """, 0x0062)
    assert labels == {'start': 0x0062, 'target': 0x006B}, labels
    assert code == bytes([0x3E, 0x20, 0x20, 0xFC, 0xCD, 0x6B, 0x00, 0x01, 0x02, 0xC9]), code.hex()
    checked += 1
    print('gbasm selftest: %d instruction forms OK' % checked)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        print(__doc__)
