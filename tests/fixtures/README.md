# Regression SRAM fixtures

This directory contains tester-created 32 KiB battery-backed SRAM snapshots used by the
emulator regressions. They do not contain a ROM image. Every fixture uses the default
player name `Shiren`; `manifest.tsv` records its SHA-256 and the route it protects.

Personal saves still belong in the ignored top-level `saves/` directory. Stage links to
the curated files and verify their hashes/privacy fields with:

```sh
python3 tools/fixtures.py stage
```

PyBoy `.state` snapshots are deliberately not tracked. They contain a complete emulator
machine snapshot and must match the current ROM's WRAM/SRAM layout. After building once,
regenerate them from the curated repaired-ranking SRAM (whose Log 1 starts in the first
village house) and inspect the four checkpoint images:

```sh
python3 tools/fixtures.py states build/shiren_en.gb \
    --png-dir build/fixture-state-shots
python3 tools/fixtures.py preflight --require-states
```

The state generator writes `town.state`, `dungeon.state`, `floorname.state`, and
`sign.state` beneath the ignored `saves/` directory. A state that loads is not necessarily
on the intended screen, which is why the checkpoint images are part of regeneration.
