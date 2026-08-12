#!/usr/bin/env python3
"""Canonical Shiren GB text codec. decode(bytes) <-> encode(str), losslessly.

Design rules:

* Readable Japanese out. Dakuten is a *following* byte in the ROM (か,79 = が), but a
  translator should see が. We emit the combining mark and NFC-compose; encode() runs
  NFD and maps the marks back. Verified round-trip for both 3099 and 309A.

* Anything not positively identified becomes a `<$XX>` token rather than a guess, so a
  byte we do not understand still survives a decode/encode cycle untouched.

* Control codes become named tokens (`<br>`, `<end>`, `<name>`) so they are obvious in a
  translation file and cannot be silently deleted by an editor.
"""
import re
import unicodedata

HIRAGANA = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'
KATAKANA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'
SMALL_HIRA = 'ぁぃぅぇぉゃゅょっ'
SMALL_KATA = 'ァィゥェォャュョッ'

VOICED = '゙'      # combining dakuten
SEMIVOICED = '゚'  # combining handakuten

# ---- character table -----------------------------------------------------
# Positions are derived from the font (gojuon order, tile index = code + 16) and
# then confirmed against real strings.
CHARS = {0x00: ' '}
for _i, _c in enumerate('0123456789'):
    CHARS[0x01 + _i] = _c
for _i, _c in enumerate(HIRAGANA):
    CHARS[0x0B + _i] = _c          # 0x0B..0x38
for _i, _c in enumerate(SMALL_HIRA):
    CHARS[0x39 + _i] = _c          # 0x39..0x41
for _i, _c in enumerate(KATAKANA):
    CHARS[0x42 + _i] = _c          # 0x42..0x6F
for _i, _c in enumerate(SMALL_KATA):
    CHARS[0x70 + _i] = _c          # 0x70..0x78
CHARS[0x7B] = 'ー'

# Punctuation block, read off the font and cross-checked behaviourally:
#   0xA1 is mid-sentence (4.9% sentence-final), 0xA2 is sentence-final (26.7%,
#   usually followed by <end>/<br>), 0xA3 self-repeats 646x as an ellipsis.
CHARS.update({
    0x9A: '「', 0x9B: '」', 0x9C: '『', 0x9D: '』', 0x9E: '（', 0x9F: '）',
    0xA0: '：', 0xA1: '、', 0xA2: '。', 0xA3: '・',
    0xAF: '～', 0xB2: '！', 0xB3: '…',
})
# Partial Latin set, present for stat labels (HP) and button prompts (A/B).
CHARS.update({0xA8: 'A', 0xA9: 'B', 0xAD: 'H', 0xAE: 'P', 0xB4: 'F', 0xB5: 'G', 0x84: 'E'})

# Symbols and brackets, read off the font at indices 140-199.
# 0x80 = ? is worth noting: 100 occurrences, and its top followers are <end> (32x) and
# the closing quote (24x), exactly where a question mark belongs.
CHARS.update({
    0x7C: '＋', 0x7D: '−', 0x7E: '［', 0x7F: '］', 0x80: '？',
    0x81: '▶', 0x82: '◀', 0x89: '▬', 0x8A: '★', 0x97: '▲', 0x98: '▼',
    0xA4: '□', 0xB0: '／', 0xB1: '％', 0xB6: '▌', 0xB7: '↓',
})

# A SECOND set of digit glyphs (a different style, presumably for stat readouts).
# These must map to characters distinct from 0x01-0x0A or the reverse table collides
# and encode() would silently emit the wrong code.
for _i, _c in enumerate('０１２３４５６７８９'):
    CHARS[0x8B + _i] = _c

COMBINING = {0x79: VOICED, 0x7A: SEMIVOICED}

# ---- control codes -------------------------------------------------------
# Authoritative, from the game's own dispatch table at bank 13 $4126:
#   handler = [$4126 + (code - $E0) * 2],  17 entries, so codes $E0-$F0 exactly.
# $4110 does `sub $E0` and $40E8 does `cp $E0 / jr c`, so < $E0 is a character and
# >= $E0 is a control code. Codes $F1-$FE are past the table and cannot appear in
# valid script -- a string containing one is not script.
TERMINATOR = 0xFF          # ends a string; handled by the splitter, never decoded
CONTROL_MIN = 0xE0
# $F4, not $F0. THE TWO DISPATCH TABLES ARE DIFFERENT LENGTHS, which is a fact this file
# carried wrongly until 2026-08-05 and which cost 532 bytes of dialogue:
#
#   13:$4126  the MESSAGE path (bank 13)          17 entries, $E0-$F0. Entry 18 is $F5C9.
#   13:$68CF  the DIALOGUE path (banks 11/14)     21 entries, $E0-$F4. Entry 22 is $FAF5.
#
# `13:$68B3` does `sub $E0 / sla a / add a,$CF` and indexes with NO upper bound, so on the
# dialogue path $F1-$F4 really do dispatch, to $6A33/$6A3E/$6A5D/$6A55 -- four ordinary
# handlers in the same idiom as $EE/$EF, all `ret`-terminated, none reading an argument.
# $F3/$F4 are a matched `res`/`set 7,[$CF8A]` pair, exactly as $E8/$EB are mode0/mode1.
#
# CONTROL_MAX is the union of the two paths, because this file is path-agnostic and its
# job is to represent a byte losslessly. What must stay path-aware is the question of
# which codes are LEGAL where -- that is `extract.impossible()`, which reads $E0-$F4 for
# banks 11/14 and $E0-$F0 everywhere else.
CONTROL_MAX = 0xF4

CONTROL = {
    0xE0: 'cE0',           # reads 1 arg, then conditional call $3F84 (sound trigger?)
    0xE1: 'cE1',
    0xE2: 'var',           # pulls 3 bytes from the queue -- runtime variable
    0xE3: 'cE3',           # pulls 6 bytes from the queue
    0xE4: 'cE4',
    0xE5: 'cE5',
    0xE6: 'cE6',
    0xE7: 'cE7',           # reads 1 arg -> $CFC3
    0xE8: 'mode0',         # $CF05 = 0   (paired with $EB)
    0xE9: 'nop',           # handler is a bare `ret`
    0xEA: 'name',          # copies from $CF81 until $FF -- variable substitution
    0xEB: 'mode1',         # $CF05 = 1   (paired with $E8)
    0xEC: 'cEC',           # reads 1 arg = repeat count, then rst $18 that many times
    0xED: 'end',           # sets $CFC4 = 1 -- end of message
    0xEE: 'brk',           # dispatch handler is `ret`; callers treat it as a line end
    0xEF: 'br',            # dispatch handler is `ret`; callers treat it as a line end
    0xF0: 'cF0',           # reads 1 arg, passes it to rst $10
    # DIALOGUE PATH ONLY ($68CF). Handlers read to their `ret` 2026-08-05: none takes an
    # argument from the string. Named neutrally because the behaviour is observed, not
    # understood -- the house rule for a code whose purpose is not established.
    0xF1: 'cF1',           # $6A33: $CFC1 = $C118 = $28
    0xF2: 'cF2',           # $6A3E: three calls to $6C3B with bc = $9C00 (tilemap rows)
    0xF3: 'cF3',           # $6A5D: res 7,[$CF8A]   -- paired with $F4
    0xF4: 'cF4',           # $6A55: set 7,[$CF8A]   -- paired with $F3
}

# Argument bytes each control code consumes FROM THE STRING. Established by reading
# each handler for `ld a,[bc]` + `inc bc`. Getting this wrong corrupts the ROM, since
# an argument byte would otherwise be treated as text and be re-encoded as a glyph.
#
# This is the MESSAGE path, 13:$4126. It is the default because most of the script is on
# it and because it is what this file assumed for its whole life.
ARITY = {0xE0: 1, 0xE7: 1, 0xEC: 1, 0xF0: 1}

# Banks whose strings are staged by 13:$68A8 instead, and the codes where that costs a
# byte. MEASURED 2026-08-05 by running the ROM's own staging loop (13:$6893) over
# `code + あいう` in tools/gbemu.py and reading the $CF07 buffer back:
#
#   $E0  ->  <cE0:0B>いう     the code AND one argument are staged     arity 1, agrees
#   $EC  ->  <cEC:0B>いう     likewise                                 arity 1, agrees
#   $E7  ->  あいう           the code vanishes, THE BYTE AFTER IT IS TEXT   arity 0
#   $F0  ->  あいう           likewise                                       arity 0
#   $F1-$F4 -> あいう         effect-only, as already recorded               arity 0
#
# $E7/$F0/$F1-$F4 dispatch to handlers that never `ld [de],a`, so they do not reach the
# composer buffer at all: no glyph, no cell, and no argument taken. Reading them at the
# message path's arity swallows a real character into the token, which is invisible in
# Japanese (the bytes round-trip either way) and prints as garbage the moment English is
# written around it -- `<cF0:56>ギ` is ナギ, "Nagi", and `<cF0:49>スリ` is クスリ, "drug".
#
# FINDINGS.md recorded the $E7 and $F0 differences in 2026-07-31 and closed them with
# "$F0 never appears in banks 11/14, so its difference is inert". That was true of the
# script as extracted THEN. Sessions 7 and 8b extracted 158 more strings and seven $F0
# sites came with them, in six strings, every one of them still untranslated.
DIALOGUE_PATH_BANKS = (11, 14)
DIALOGUE_ARITY = {**ARITY, 0xE7: 0, 0xF0: 0}


def arity_for(bank=None):
    """Argument counts for the dispatch path `bank` is read by. None = the message path.

    Defaulting to the message table rather than requiring a bank is deliberate: every
    caller that does not know one keeps the behaviour it has always had, and only the
    callers that can be exact are asked to be.
    """
    return DIALOGUE_ARITY if bank in DIALOGUE_PATH_BANKS else ARITY

# NOTE: the skip-chain at bank 13 $441B advances TWO bytes for $EB, but $EB's handler
# ($416D) reads no argument. Unresolved discrepancy -- treated as 0 args here, matching
# the handler. Worth confirming in Mesen before the inserter relies on it.

REV_CHARS = {v: k for k, v in CHARS.items()}
REV_COMBINING = {v: k for k, v in COMBINING.items()}
REV_CONTROL = {v: k for k, v in CONTROL.items()}

TOKEN_RE = re.compile(r'<(\$[0-9A-Fa-f]{2}|[A-Za-z][A-Za-z0-9]*(?::[0-9A-Fa-f]{2})*)>')


def decode(data, bank=None):
    """ROM bytes -> readable text with tokens. Never raises; unknown bytes survive.

    A control code that takes arguments swallows them into its token, e.g. $F0 05
    becomes `<cF0:05>` -- otherwise the 05 would render as a digit and a translator
    could not tell it apart from real text.

    `bank` picks the dispatch path, because five codes read a different number of
    arguments on each. Omitting it reads the message table, which is what this file did
    before the paths were separated. See arity_for.
    """
    arity = arity_for(bank)
    out = []
    i = 0
    while i < len(data):
        b = data[i]
        if b in CHARS:
            out.append(CHARS[b])
        elif b in COMBINING:
            out.append(COMBINING[b])
        elif b in CONTROL:
            n = arity.get(b, 0)
            args = data[i + 1:i + 1 + n]
            if len(args) < n:
                # The string ends on a code that wants an argument it has not got. That
                # happens when `bank` was not supplied for a dialogue-path string, which
                # is legal -- `arity_for(None)` is the message table by design.
                #
                # Emit the raw byte rather than a token that claims an argument it does not
                # have. That is this file's stated rule for anything not positively
                # identified, and it is the only form that round-trips: `<cE7>` on the
                # message path would come back through encode() as "takes 1, got 0".
                out.append('<$%02X>' % b)
            else:
                out.append('<%s%s>' % (CONTROL[b], ''.join(':%02X' % x for x in args)))
                i += len(args)
        else:
            out.append('<$%02X>' % b)
        i += 1
    # NFC turns  か + U+3099  into  が
    return unicodedata.normalize('NFC', ''.join(out))


def encode(text, bank=None):
    """Text with tokens -> ROM bytes. Raises ValueError on anything unmappable.

    `bank` picks the dispatch path, and must match whatever decoded the text: `<cF0>`
    is right for banks 11/14 and `<cF0:xx>` for everywhere else.
    """
    arity = arity_for(bank)
    out = bytearray()
    pos = 0
    for m in TOKEN_RE.finditer(text):
        _encode_run(text[pos:m.start()], out)
        tok = m.group(1)
        if tok.startswith('$'):
            out.append(int(tok[1:], 16))
        else:
            parts = tok.split(':')
            name, args = parts[0], parts[1:]
            if name not in REV_CONTROL:
                raise ValueError('unknown token <%s>' % tok)
            code = REV_CONTROL[name]
            want = arity.get(code, 0)
            if len(args) != want:
                raise ValueError('<%s> takes %d argument(s), got %d' % (name, want, len(args)))
            out.append(code)
            out.extend(int(x, 16) for x in args)
        pos = m.end()
    _encode_run(text[pos:], out)
    return bytes(out)


def _encode_run(run, out):
    if not run:
        return
    # NFD splits が back into か + U+3099 so the mark gets its own byte
    for ch in unicodedata.normalize('NFD', run):
        if ch in REV_CHARS:
            out.append(REV_CHARS[ch])
        elif ch in REV_COMBINING:
            out.append(REV_COMBINING[ch])
        else:
            raise ValueError('cannot encode %r (U+%04X)' % (ch, ord(ch)))


def split_strings(data, start, end=None):
    """Walk 0xFF-terminated strings. -> list of (offset, bytes-without-terminator)."""
    end = len(data) if end is None else end
    out, cur, base = [], bytearray(), start
    i = start
    while i < end:
        b = data[i]
        if b == TERMINATOR:
            out.append((base, bytes(cur)))
            cur = bytearray()
            base = i + 1
        else:
            cur.append(b)
        i += 1
    if cur:
        out.append((base, bytes(cur)))
    return out


def kana_ratio(data):
    if not data:
        return 0.0
    return sum(1 for b in data if 0x0B <= b <= 0x78) / len(data)


if __name__ == '__main__':
    # self-test: every byte value must survive decode -> encode unchanged
    import sys
    bad = []
    for bank in (None, 11):                # the message path and the dialogue path
        for b in range(256):
            if b == TERMINATOR:
                continue
            blob = bytes([0x0B, b, 0x0C])  # sandwich it between kana
            try:
                if encode(decode(blob, bank), bank) != blob:
                    bad.append((bank, b))
            except Exception as e:
                bad.append((bank, b, str(e)))
    print('single-byte round-trip failures:', bad if bad else 'none')
    # The arity difference itself: on the dialogue path $E7/$F0 take no argument, so the
    # byte after one is text. Measured against the ROM's staging loop -- see DIALOGUE_ARITY.
    for code in (0xE7, 0xF0):
        blob = bytes([code, 0x0B])
        msg, dlg = decode(blob), decode(blob, 11)
        print('  $%02X + あ  message %-12r  dialogue %-14r  %s'
              % (code, msg, dlg,
                 'OK' if encode(dlg, 11) == blob and 'あ' in dlg else 'FAIL'))
        if encode(dlg, 11) != blob or 'あ' not in dlg:
            bad.append(code)
    # dakuten specifically
    for blob in (bytes([0x15, 0x79]), bytes([0x1F, 0x7A]), bytes([0x5B, 0x79, 0x68])):
        d = decode(blob)
        print('  %s -> %r -> %s  %s' % (blob.hex(' '), d, encode(d).hex(' '),
                                        'OK' if encode(d) == blob else 'FAIL'))
    sys.exit(1 if bad else 0)
