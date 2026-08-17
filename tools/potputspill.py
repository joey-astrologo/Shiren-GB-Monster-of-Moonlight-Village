#!/usr/bin/env python3
"""No V4F publication may cancel a native LCD-off interval on the way back to the field.

Joey's playtesters reported a brief frame of character garbage when the item menu closes
-- most visibly after putting an item into a Pot.  The blanking was not missing.  The
native return-to-dungeon sequence blanks correctly (the VBlank LCDC refresh at `0:$0737`
writes `$67`), rebuilds `$9000-$97FF` from menu font back to terrain, then re-enables.
Our renderer cancelled that interval: ``publishmap`` copied the stale `$C300` menu shadow
map over `$9800` and set LCDC bit 7 while the reload was still in flight, so one frame
showed the dungeon map drawn through menu-font tiles under a leftover main-menu box.

The trigger was a shared byte.  The transaction state lived at `$C0D7`, which is also
propvwf's ``S_LOCAL``: ``place`` stores the pen there for every glyph and ``buildmap``'s
``bmkeep`` stores a cell index 0-17.  Both aliased every live state value, so what a
dungeon message left behind read as an open transaction.  Two different completions were
measured on this one route, which is why the assertion below watches the publication and
not any single path: putting in the Big Onigiri leaves `$10` and ``startfinish``'s
title/file path completes on the in-dungeon main menu, while the Power-Up Scroll leaves
`$11` and ``pagepublish`` completes on the one-row `Items` header -- that path tests the
byte with ``and a`` alone, so any nonzero leftover arms it.  The state now lives at
`$C1B3`, which propvwf never writes.

Two assertions, because either alone would miss a variant:

* once gameplay is live, no ``publishmap`` LCD re-enable happens inside a blank no
  menuvwf/rankvwf code contributed to.  Every legitimate in-game publication closes an
  interval its own transaction opened;
* the route settles with the LCD on, the transaction byte clear and the CPU healthy,
  and it really opened the item list and the Pot's action box first -- a run that never
  published anything proves nothing.

The route is the player's: Log 2 stands on a Storage Pot.  Floor -> Take, dismiss both
messages, then Menu -> Items -> Storage Pot -> Put -> Big Onigiri.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gbasm                                                     # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
BANKSZ = 0x4000
STATE = 0xC1B3

# Take the floor Pot, clear its pickup and description messages, then put the first
# inventory item inside it.  Both teardowns exercised the defect; the second is the one
# players reported.
SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 500: 'a',        # Adventure -> Log 2
    2200: 'b', 2280: 'down', 2360: 'a', 2460: 'a',    # Menu -> Floor -> Take
    2700: 'a', 2800: 'a', 2900: 'a',                  # dismiss pickup + description
    3000: 'b', 3120: 'a',                             # Menu -> Items
    3180: 'down', 3240: 'down', 3300: 'down',         # -> Storage Pot
    3360: 'a', 3420: 'down', 3480: 'a',               # action box -> Put -> `Which?`
    3600: 'a',                                        # -> Big Onigiri
}
FRAMES = 3800
SETTLED = 3760              # by here the field and its message have published or never will
# The title/file composite legitimately publishes into the blank the native boot loader
# already holds, under a flat BGP nobody can see through.  This route owns the gameplay
# teardowns; titlecardspill and copylogspill own the start flow.
GAMEPLAY = 2000


def lcdc_sites(rom):
    """Every `ldh [$FF40],a` / `ld [$FF40],a` in the ROM, as (bank, cpu address)."""
    with open(rom, 'rb') as handle:
        buf = handle.read()
    found = []
    for bank in range(len(buf) // BANKSZ):
        base = bank * BANKSZ
        origin = 0x0000 if bank == 0 else 0x4000
        for offset in range(BANKSZ - 2):
            byte = buf[base + offset]
            if byte == 0xE0 and buf[base + offset + 1] == 0x40:
                found.append((bank, origin + offset))
            elif (byte == 0xEA and buf[base + offset + 1] == 0x40
                  and buf[base + offset + 2] == 0xFF):
                found.append((bank, origin + offset))
    return found


def publish_lcd_on():
    """Address of the `ldh [$FF40],a` that ends ``publishmap``."""
    code, labels = gbasm.assemble(menuvwf.ITEM_PAGE_SRC, menuvwf.ITEM_PAGE_AT)
    end = menuvwf.ITEM_PAGE_AT + len(code)
    # publishmap's last three bytes are `set 7,a` / `ldh [$FF40],a` / `ret`.
    at = end - 3
    if code[at - menuvwf.ITEM_PAGE_AT:end - menuvwf.ITEM_PAGE_AT] != b'\xe0\x40\xc9':
        raise SystemExit('potputspill: publishmap does not end in ldh [$FF40],a / ret')
    return labels['publishmap'], at


def run(rom, ram, png=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('potputspill: requires the approved proportional renderer')
    _publish_at, lcd_on_at = publish_lcd_on()
    PyBoy = _import_pyboy()
    problems = []

    with tempfile.TemporaryDirectory(prefix='potputspill-') as tmp:
        work = os.path.join(tmp, 'potput.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        blankers = [[]]                # sites that cleared LCDC bit 7 in this interval
        cancelled = []                 # our publications inside somebody else's blank
        publications = []
        halts = []

        def lcdc_write(bank, addr):
            def callback(_context=None):
                if not pb.register_file.A & 0x80:
                    blankers[0].append((bank, addr))
                    return
                if (bank, addr) != (menuvwf.ITEM_PAGE_BANK, lcd_on_at):
                    blankers[0] = []
                    return
                publications.append((frame[0], pb.memory[STATE], tuple(blankers[0])))
                # A transaction that opened its own interval always cleared bit 7 from
                # its own code, which lives in the pool banks; the native VBlank LCDC
                # refresh at 0:$0737 rewrites the same OFF value under it, so the LAST
                # writer is not the owner.  A blank nothing of ours contributed to is a
                # native reload we are cancelling mid-flight.
                if (frame[0] >= GAMEPLAY and blankers[0]
                        and not any(bank >= 0x20 for bank, _at in blankers[0])):
                    cancelled.append((frame[0], blankers[0][0], pb.memory[STATE],
                                      pb.memory[0xFF43], pb.memory[0xFF42]))
                blankers[0] = []
            return callback

        for bank, addr in lcdc_sites(rom):
            try:
                pb.hook_register(bank, addr, lcdc_write(bank, addr), None)
            except Exception:                    # a site may not exist in every build
                pass

        for current in range(FRAMES):
            frame[0] = current
            button = SCRIPT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current >= SETTLED and pb.register_file.PC == 0x0038:
                halts.append(current)

        final = pb.screen.image.copy()
        final_state = pb.memory[STATE]
        final_lcdc = pb.memory[0xFF40]
        if png:
            final.save(png)
            print('potputspill: wrote %s' % png)
        pb.stop(save=False)

    for at, site, state, scx, scy in cancelled:
        problems.append('frame %d: publishmap re-enabled the LCD inside the native '
                        'blank opened by %02d:$%04X (state $%02X, SCX=%d SCY=%d) -- '
                        'the half-restored screen is exposed for a frame'
                        % (at, site[0], site[1], state, scx, scy))
    # The menu half of the route has to have happened, or a clean result proves nothing:
    # opening Items and opening the Pot's action box are both real publications.
    in_menu = [at for at, _state, _blankers in publications if at >= 3000]
    if len(in_menu) < 2:
        problems.append('only %d publication(s) after the menu opened (%s); the route '
                        'did not reach the item list and the Pot action box'
                        % (len(in_menu), in_menu))
    if final_state != 0:
        problems.append('transaction byte $%04X settled at $%02X, expected $00'
                        % (STATE, final_state))
    if not final_lcdc & 0x80:
        problems.append('route ended with the LCD disabled (LCDC=$%02X)' % final_lcdc)
    if halts:
        problems.append('CPU reached rst $38 at frame(s) %s' % halts[:8])

    print('potputspill: %d publication(s) %s; %d cancelled native blank(s); '
          'final state $%02X LCDC=$%02X; %d problem(s)'
          % (len(publications),
             ' '.join('f%d:$%02X' % (at, state) for at, state, _o in publications),
             len(cancelled), final_state, final_lcdc, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('potputspill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
