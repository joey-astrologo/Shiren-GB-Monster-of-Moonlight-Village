#!/usr/bin/env python3
"""Rebuild the saves/*.state fixtures from a save the ROM wrote.

Three states: `town.state` (Moonlight village), `dungeon.state` (a floor of 変化の森), and
`floorname.state` — the floor-arrival banner, caught mid-display, which is the only fixture
for the per-floor name graphic. It is on screen for about 120 frames on the way in and
there is no other way to stop on it.

WHY THIS IS A TOOL AND NOT A README PARAGRAPH. The states carry WRAM *and* cartridge RAM,
so any change to a WRAM or SRAM layout makes them silently wrong -- they keep loading, and
whatever reads the moved field reads the old address. name6 moved the packed player name
from `$D100` to `$D0FD` and the states went on returning `00 00 00 Shi` for a whole
session, during which the rankings insert looked broken and was not. Regenerate rather
than hand-edit: the point of a fixture is that the ROM wrote it.

THE DUNGEON HAS TO BE WALKED INTO, and that is not a detail. **Shiren does not let you save
inside a dungeon** -- it is the genre -- so no `.srm` will ever hold a log parked on a
floor, and the recipe in `docs/TRAPS.md` that says to continue "log 3" describes a save that
cannot exist. Nor can the entrance be found by searching: directional sweeps from four
village positions and four 20,000-frame seeded random walks stayed in the village for all
of it, every fade-to-white a house door. Joey gave the route; it is `WEST` below.

    mkstate.py <rom> <srm> [--out-dir saves] [--png-dir DIR]

`--png-dir` writes a checkpoint frame per state, which is the only way to notice that the
route has drifted -- a state that loads is not a state that is where you think it is.
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gbrun import _import_pyboy                                     # noqa: E402

PRESS_FRAMES = 5            # gbrun's hold; this ROM does not sample the pad every frame
STEP = 6                    # frames between steps -- one tile of movement

# Boot -> the log list -> Continue. Four `start`s clear the title screens, `a` picks
# Adventure, `a` selects the (only) log, `a` takes Continue.
BOOT = [(60, 'start'), (120, 'start'), (180, 'start'), (240, 'start'),
        (300, 'a'), (420, 'a'), (480, 'a')]
BOOT_SETTLE = 2400          # the village is drawn well before this

# The log loads INSIDE the first house. Down is the door.
OUT_OF_HOUSE = 40

# Then west, all the way. The villagers on the way stop the walk with a text box, so `a`
# is pressed every fourth step to clear them; past the west gate one more square opens the
# "enter the dungeon?" prompt, which the same `a` accepts.
WEST = 190

# The floor-arrival banner is up roughly 780-900 frames INTO THE WALK -- counted from the
# first step out of the house, not from boot. It is a timed screen with no input to key
# off, so an offset is the only handle there is; look at the `--png-dir` frame after any
# change to the route above.
BANNER_INTO_WALK = 850


def drive(pb, presses, upto, png=None):
    held = {}
    for f in range(upto + 1):
        for btn in presses.get(f, []):
            pb.button_press(btn)
            held[btn] = f + PRESS_FRAMES
        for btn in [b for b, t in held.items() if t == f]:
            pb.button_release(btn)
            del held[btn]
        pb.tick(1, f == upto and png is not None)
    if png:
        pb.screen.image.save(png)


def sched(pairs):
    out = {}
    for at, btn in pairs:
        out.setdefault(at, []).append(btn)
    return out


# The new-game route to the entrance signboard. Not driven by `drive()` because name
# entry is not driven by BUTTONS at all -- namerun.py establishes that counting d-pad
# presses to spell a name types the wrong one, and writes the picker's cursor variables
# instead. This borrows that loop rather than restating it.
SIGN_NAME = 'Shiren'
SIGN_SETTLE = 1600      # frames from confirming the name to the village being walkable
SIGN_FACE = 40          # ... and then `up`, which faces the sign one square above


def new_log_at_the_sign(PyBoy, rom, png=None):
    """-> a PyBoy parked in front of the village-entrance sign on a brand new log."""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from namerun import WHERE, NAV_FRESH, FIRST, STEP, END_COL       # noqa: E402
    sys.path.pop(0)

    ram = rom + '.ram'
    if os.path.exists(ram):
        os.remove(ram)                       # a blank cart: the route is New Log
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    steps = [WHERE[c] + (None,) for c in SIGN_NAME] + [(0, None, END_COL)]
    end_at = FIRST + STEP * len(steps)
    for i in range(end_at + SIGN_SETTLE + SIGN_FACE):
        if FIRST <= i < end_at:
            row, col, hdr = steps[(i - FIRST) // STEP]
            pb.memory[0xC6F5] = row
            if col is not None:
                pb.memory[0xC6F0] = col
            if hdr is not None:
                pb.memory[0xC6F4] = hdr
            if (i - FIRST) % STEP == 25:
                pb.button('a', 5)
        elif i in NAV_FRESH:
            pb.button(NAV_FRESH[i], 4)
        elif i == end_at + SIGN_SETTLE:
            pb.button('up', 5)
        pb.tick()
    if png:
        pb.screen.image.save(png)
    return pb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('srm', help='a save THIS build wrote -- not an older one')
    ap.add_argument('--out-dir', default=os.path.join(ROOT, 'saves'))
    ap.add_argument('--png-dir')
    a = ap.parse_args()

    work = a.rom + '.mkstate'
    shutil.copyfile(a.rom, work)
    shutil.copyfile(a.srm, work + '.ram')
    PyBoy = _import_pyboy()

    def boot():
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        return pb

    def png(name):
        return os.path.join(a.png_dir, name + '.png') if a.png_dir else None

    # ---- the village
    pb = boot()
    drive(pb, sched(BOOT), BOOT_SETTLE, png('town'))
    town = os.path.join(a.out_dir, 'town.state')
    with open(town, 'wb') as f:
        pb.save_state(f)
    name = bytes(pb.memory[0xD0FD:0xD103])
    pb.stop(save=False)
    print('wrote %s   packed name $D0FD = %s' % (town, name.hex(' ')))

    # ---- the dungeon, walked into from there
    pb = boot()
    moves = list(BOOT)
    f = BOOT_SETTLE
    for _ in range(OUT_OF_HOUSE):
        moves.append((f, 'down'))
        f += STEP
    for i in range(WEST):
        moves.append((f, 'left'))
        f += STEP
        if i % 4 == 3:
            moves.append((f, 'a'))
            f += 8
    dungeon = os.path.join(a.out_dir, 'dungeon.state')
    drive(pb, sched(moves), f, png('dungeon'))
    with open(dungeon, 'wb') as fh:
        pb.save_state(fh)
    name = bytes(pb.memory[0xD0FD:0xD103])
    pb.stop(save=False)
    print('wrote %s   packed name $D0FD = %s' % (dungeon, name.hex(' ')))

    # ---- the floor-arrival banner, caught while it is up
    #
    # An offset, not a landmark, which is as fragile as it sounds -- it is the only handle
    # there is, because the banner is a timed screen with no input to key off. It moves
    # with any change to the route above, AND with the boot path: the same walk driven
    # from a loaded town.state puts the banner 140 frames earlier than driving it from a
    # cold boot does. The `--png-dir` frame is the check, and it is not optional.
    pb = boot()
    banner_at = BOOT_SETTLE + BANNER_INTO_WALK
    banner_moves = [(at, b) for at, b in moves if at <= banner_at]
    drive(pb, sched(banner_moves), banner_at, png('floorname'))
    floorname = os.path.join(a.out_dir, 'floorname.state')

    # Do not accept a merely loadable state here. This timed checkpoint used to drift
    # past the card while still producing a valid .state. The English card uploader owns
    # three tile rows plus a blank guard row; their exact map proves we stopped while the
    # card is live and that the route/source SRAM still starts in the expected house.
    upper = bytes(pb.memory[0x9900:0x9914])
    lower = bytes(pb.memory[0x9920:0x9934])
    third = bytes(pb.memory[0x9940:0x9954])
    blank = bytes(pb.memory[0x9960:0x9974])
    expected_upper = bytes(range(0x80, 0xA8, 2))
    expected_lower = bytes(range(0x81, 0xA8, 2))
    expected_third = bytes(range(0xA8, 0xBC))
    expected_blank = bytes((0xBC,)) * 20
    if (upper, lower, third, blank) != (expected_upper, expected_lower,
                                        expected_third, expected_blank):
        pb.stop(save=False)
        raise SystemExit('floorname.state route drifted: the arrival-card tilemap is '
                         'not live at frame %d; update and inspect BANNER_INTO_WALK'
                         % banner_at)
    with open(floorname, 'wb') as fh:
        pb.save_state(fh)
    lcdc = pb.memory[0xFF40]
    pb.stop(save=False)
    print('wrote %s   LCDC=$%02X (banner is BG rows 8-9, tiles $80-$A7)'
          % (floorname, lcdc))

    # ---- the village-entrance SIGNBOARD, faced but not yet read
    #
    # Joey's route, and it is the only cheap one: a NEW log drops the player one square
    # below the entrance sign, so `up` faces it and `a` reads it. Everything else that
    # renders a signboard is deep in the village, and four 20,000-frame seeded walks never
    # reached one -- which is why the `<cEC>` class went three sessions without a fixture.
    #
    # This state is the entry point for `tools/msgshot.py`, which substitutes the queued
    # pointer at `13:$67ED` and can therefore draw ANY bank-11/14 message from here.
    # It boots a BLANK cart deliberately: the route is New Log, so an existing save would
    # put "Adventure" above it and shift every press.
    signstate = os.path.join(a.out_dir, 'sign.state')
    pb = new_log_at_the_sign(PyBoy, a.rom, png('sign'))
    with open(signstate, 'wb') as fh:
        pb.save_state(fh)
    pb.stop(save=False)
    print('wrote %s   facing the entrance sign; one `a` reads it' % signstate)

    os.remove(work)
    if os.path.exists(work + '.ram'):
        os.remove(work + '.ram')
    if not a.png_dir:
        print('note: pass --png-dir to photograph all four. A state that LOADS is not a '
              'state that is where you think it is -- and floorname.state is a bare frame '
              'offset into a timed screen, so it is the one that will drift first.')


if __name__ == '__main__':
    main()
