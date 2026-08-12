#!/usr/bin/env python3
"""Make a Decoy Staff target use the live player name without a Japanese prefix.

The actor-name producer at ``11:$51CA`` returns the player-name buffer at ``$CF81``.
For an ordinary player (``[$FF92] == $12``) it returns that pointer directly. For a
Decoy Staff target it first writes the two source-font bytes ``$20,$18`` -- ``にせ``
(``fake``) -- to the destination and then appends the player name.

Those two bytes are runtime text, so the glossary cannot translate them. On the English
font page they are ``V`` and ``N``, which made the default-name battle report read
``VNShiren``. The approved compact localization is simply the live player name. Change
the existing conditional jump to an unconditional jump: both paths now skip the prefix,
while the original pointer/copy routine and custom player names remain untouched.

``--no-decoyname`` in ``tools/build.py`` is the one-byte bisect control.
"""
import sys


BANKSZ = 0x4000
BANK = 11
BRANCH = 0x51D0
JR_Z = 0x28
JR = 0x18

# Guard the whole decision and prefix writer, not only the byte being changed. A future
# source revision that moves or changes the routine must fail instead of patching blind.
ORIGINAL = bytes.fromhex('28 08 3e 20 12 13 3e 18 12 13 21 81 cf')
PATCHED = bytes([JR]) + ORIGINAL[1:]


def _off(bank, addr):
    return bank * BANKSZ + (addr - 0x4000)


def install(buf, notes):
    at = _off(BANK, BRANCH)
    got = bytes(buf[at:at + len(ORIGINAL)])
    if got != ORIGINAL:
        raise SystemExit(
            'decoyname: expected decoy-prefix branch/writer at %d:$%04X, found %s; '
            'patching blind would corrupt code' % (BANK, BRANCH, got.hex(' ')))
    buf[at:at + len(PATCHED)] = PATCHED
    notes.append(
        'decoyname: 11:$51D0 `jr z` -> `jr`; Decoy Staff targets use the live player '
        'name without raw Japanese `ni-se` prefix bytes $20,$18')


def selftest():
    buf = bytearray([0xFF] * ((BANK + 1) * BANKSZ))
    at = _off(BANK, BRANCH)
    buf[at:at + len(ORIGINAL)] = ORIGINAL
    notes = []
    install(buf, notes)
    assert bytes(buf[at:at + len(PATCHED)]) == PATCHED
    assert buf[at] == JR and buf[at + 1] == 0x08
    assert bytes(buf[at + 2:at + len(PATCHED)]) == ORIGINAL[2:]
    print('decoyname selftest: guarded one-byte branch patch at 11:$51D0 -- OK')


if __name__ == '__main__':
    if sys.argv[1:] != ['--selftest']:
        raise SystemExit('usage: decoyname.py --selftest')
    selftest()
