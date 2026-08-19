# Engineering rules

The standing rules for changing this repository, and the approach that produced the
current state. These are prescriptive: they say what a change must satisfy before it
counts as done.

For the mistakes behind them see [`TRAPS.md`](TRAPS.md).

## Gates

- `sh build.sh` is only the normal-build gate. A release claim requires
  `python3 tools/release_battery.py`, including fixture preflight plus the normal,
  shuffled and redirect-all matrix.
- Text must satisfy control-token parity, source staging, physical pixel width, temporary
  tile allocation and frame time. Passing one limit does not imply the others pass.
- The redirect-all layout is a real timing gate. On 2026-08-13 it exposed a 160-scanline
  reveal-map pass that normal placement missed; the optimized direct-pointer builder now
  completes the same route within 143/154 scanlines and uploads byte-exact.
- Preserve all `<...>` control tokens and their ordering. Never infer that `<end>`, `<brk>`
  or a mode argument is decorative.
- Space is not a translation constraint. Relocation is complete and has large headroom;
  write natural English, then wrap it with the measured renderer tools.
- Rankings must remain VWF. Do not fall back to fixed-width text or weaken the Orochi,
  repeated-navigation, native-control or hostile-layout regressions.
- A green model is not visual approval. Photograph or inspect the actual emulator route
  for player-facing graphics and transitions.
- Do not commit ROMs, SRAM, save states, credentials or generated screenshots.

## Fixtures and regressions

**Turn every reproducible defect into a fixture and a regression before fixing it.** That
ordering is the reason the defect list stays closed: a fix without a regression is a fix
that comes back.

- Store `.srm` and machine-state files under `saves/`. They are gitignored game data.
- Curated tester-created SRAM regressions are the exception and *are* versioned, under
  `tests/fixtures/saves/`.
- Machine states are generated, not committed: regenerate them with
  `python3 tools/fixtures.py states build/shiren_en.gb`.
- Add the route to `build.sh` when it should gate ordinary builds, and to
  `tools/release_battery.py` when it belongs in the release matrix.
- A regression that needs a floor actor cannot use an ordinary save: floor actors are not
  serialized by Quit/save. Either drive the route from a machine state, or make the check
  static — `tools/healfragmentspill.py` is the worked example of the static form.

## Playtesting is the discovery mechanism

Static coverage cannot discover an unknown interior event entry, and automated navigation
cannot judge a sentence or an animation transition. The full-game playthrough is what finds
what the battery cannot, and every route it discovers should become a fixture.

## Releasing

When a playthrough is accepted: stop changing font, text, graphics and geometry; run
`python3 tools/release_battery.py`; verify a clean clone with a locally supplied ROM and
fixtures; and record the final hashes in [`../README.md`](../README.md).

## Verifying a render-path change

Byte verification, reference decoders and the build's own checks have all been green on a
white screen. The only checks that catch a missing hook are a screen diff against a
pre-change build, and a duration check:

**Proven on screen 2026-07-30.** Build the pre-hook ROM to compare against, then diff
screens. Everything below is IDENTICAL except where noted:

```
git stash && sh build.sh && cp build/shiren_en.gb build/prehook.gb && git stash pop
sh build.sh
python3 tools/gbrun.py build/shiren_en.gb --compare build/prehook.gb --frames 1400 \
        --press start:700,start:760,start:820,start:880,a:940,a:1000     # file menu
python3 tools/gbrun.py build/shiren_en.gb --compare build/prehook.gb \
        --state saves/dungeon.state --frames 800 --press b:120           # status screen
python3 tools/msgdur.py build/shiren_en.gb build/shiren_nohook.gb        # message TIMING
```

**Run those after every render-path change.** The two `--compare` lines are the only check
that catches a missing hook -- and once, the only check that caught THREE separate white
screens that byte verification, the reference decoder and 1451 build checks were all green
on. They are necessary and NOT sufficient: pixel comparison samples one frame, so it cannot
see a duration, which is how the message-timing bug survived every check in the project.
`msgdur.py` is the third line for exactly that reason -- expect the same 10 boxes at the
same frames with the same durations in both builds.

**Necessary and not sufficient.** Pixel comparison samples one frame, so it cannot see a
duration — which is how the message-timing bug survived every other check in the project.
That is what `msgdur.py` is for: expect the same boxes at the same frames with the same
durations in both builds.

## Rebuilding the save fixtures

`saves/` holds the battery save plus the generated pyboy machine states. All of it is
gitignored game data, so a fresh clone has to rebuild it:

data), so on a fresh clone it has to be rebuilt:

```sh
cp ~/Library/Application\ Support/MesenCE/Saves/shiren_en.srm saves/shiren_en.srm
sh build.sh                    # copies it to build/shiren_en.gb.ram, which is what pyboy reads
python3 tools/mkstate.py build/shiren_en.gb saves/shiren_en.srm --png-dir build/mkstate
```

```
saves/town.state       Moonlight village, inside the first house
saves/dungeon.state    a floor of 変化の森
saves/floorname.state  the floor-arrival banner, caught while it is up
```

> **THE OLD RECIPE HERE WAS WRONG and is deleted.** It said to pick "Log 3 in the dungeon"
> from the title screen. **Shiren does not let you save inside a dungeon** — that is the
> genre — so no `.srm` can hold a log parked on a floor, and no such save exists. The
> dungeon has to be WALKED into from the village, and it cannot be found by searching
> either: four 20,000-frame seeded random walks never left the village. Joey gave the
> route on 2026-08-04 and `mkstate.py` drives it: out of the house, then **west across
> town** to the gate, clearing the villagers' text boxes, one more square, accept.

Use them with `gbrun.py --state saves/dungeon.state`. **This is what finally reached the
composer** — `13:$40D8` fired 98 times and `dte_emit` 587 from the dungeon state, against
zero from the title screen.

One caveat when scripting: ~5000 frames of random input from `dungeon.state` walks out of the
dungeon and back to the village, and the level resets 2 -> 1. That is the Shiren mechanic for
leaving, not a bug.

~~A screenshot of the item action menu.~~ **Done 2026-07-30** -- `See / Put / Toss / Drop /
Info` all correct in a real dungeon, all five stored compressed, `See` a single byte.
