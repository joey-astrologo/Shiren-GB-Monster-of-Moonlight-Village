#!/bin/sh
# Full build: base ROM -> MBC3 -> 1 MiB -> font + script -> verified English ROM
set -e

# Verify every public SRAM regression and stage ignored links at the legacy saves/ paths
# consumed by the emulator tools. Personal saves and generated machine states remain
# untracked. A differing local file is never overwritten.
python3 tools/fixtures.py --quiet stage

python3 tools/setmapper.py build/base.gb build/_m.gb --type 13 >/dev/null
python3 tools/expand.py    build/_m.gb  build/_base_expanded.gb --size-code 5 >/dev/null
python3 tools/build.py     build/_base_expanded.gb script/en.tsv build/shiren_en.gb \
        --report build/worklist.tsv --dot-font

# Gameplay-data collision gate. Ending-credit code once occupied a zero-filled-looking
# span which was actually the high-byte plane of the native tier-3 enemy EXP table.
# Protect all 303 rewards across all three tiers in their split low/middle/high
# representation, not merely a live Mouse Don actor (floor actors are not serialized by
# ordinary Quit saves).
python3 tools/enemyexp.py build/_base_expanded.gb build/shiren_en.gb

# Translator-facing semantic and proportional-layout gates. build.py already rejects
# dialogue/help source or pixel clipping; these add token/glossary parity and enumerate
# every current signed/[NN] item variant against its measured menu path.
python3 tools/lint_en.py
python3 tools/fontaudit.py --details 4
python3 tools/propvwf.py --selftest
python3 tools/unidentifiedhelp.py build/shiren_en.gb
rm -f build/_m.gb

# EXTRACTION COVERAGE. Every other check verifies that what we extracted round-trips,
# renders and fits; this one asks whether known-alphabet framed bytes are covered and
# whether declared runtime-interior starts are manifested. It cannot discover a new event
# pointer inside already covered bytes; route scans do that. It still has to run on every
# build because its byte-coverage answer is an input to several others
# -- dte_rom's code space is "bytes untranslated Japanese never uses", measured against
# script.json, so an incomplete script.json silently invalidates it. That is exactly how
# $C8 and $DC stayed in the DTE range while 143 unextracted strings used them.
python3 tools/coverage.py

# Fresh-cart graphics and transition gates. The village marker is visible for only a
# short interval after name confirmation; its three-row test also proves the complete
# Poppins silhouette stays intact through all fade shades. The title-card test verifies
# Joey's approved
# full 160x144 copyright mock-up plus the native palette/fade/scene-0 path; the following
# test compares the later illustrated title pixel-for-pixel.
# The final test continues beyond the marker and proves the same New Log route still
# reaches a live, walkable village.
python3 tools/titlecardspill.py build/shiren_en.gb
python3 tools/titlelogospill.py build/shiren_en.gb
python3 tools/markerspill.py build/shiren_en.gb
python3 tools/newgamesmoke.py build/shiren_en.gb

# Curated route-specific SRAM regressions are tracked under tests/fixtures and staged at
# the legacy saves/ paths above. Machine-state routes remain conditional because PyBoy
# states are generated locally for the current ROM/WRAM layout. The fixtures enforce atomic item-page and
# Floor action/Info transitions (including Gitan's shorter action box), the Log-2 Path
# selector/status field, title/file-menu transitions (including Erase Log 3 rebuilding
# Copy Log), cursed/plated/unidentified equipment-marker VWF, an exhaustive Items/Info
# textual-glyph pass, the Copy/Erase/New-Log name-screen
# restore, the Ground box-5 VWF path, the Decoy Staff live-name producer, and rescued-child
# nested dialogue entries. A fresh clone therefore runs every SRAM-backed route; generate
# town.state/dungeon.state with tools/fixtures.py to enable the remaining state routes.
if [ -f saves/town.state ]; then
  # Exact Forest 1 reference plus all 50 live floor fields over every dungeon selector.
  python3 tools/floormarkerspill.py build/shiren_en.gb
fi
if [ -f saves/dungeon.state ]; then
  python3 tools/menuspill.py build/shiren_en.gb
  python3 tools/menuglyphspill.py build/shiren_en.gb
  python3 tools/equipmentmarkerspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_item_menu.srm ]; then
  python3 tools/itempagespill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_item_menu_wood_arrow.srm ]; then
  python3 tools/floorinfospill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_3_gitan_crash.srm ]; then
  python3 tools/waitcardspill.py build/shiren_en.gb
  python3 tools/gitaninfospill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_decoy_staff_enemy.srm ]; then
  python3 tools/decoynamespill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_hunger_bracer_message.srm ]; then
  python3 tools/nohungerbracerspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_path_select.srm ]; then
  python3 tools/pathspill.py build/shiren_en.gb
  python3 tools/mainmenuspill.py build/shiren_en.gb
  python3 tools/nameflowspill.py build/shiren_en.gb \
          --ram saves/shiren_en_path_select.srm
fi
if [ -f saves/shiren_en_log_3_erase_copy_log_vwf.srm ] &&
   [ -f saves/shiren_en_log_1_quit_erase_copy_log_vwf.srm ]; then
  python3 tools/copylogspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_ground.srm ]; then
  python3 tools/groundspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_shield_VWF.srm ]; then
  python3 tools/unidentifiedspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_pot_see_action.srm ]; then
  python3 tools/potseespill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_2_action_pots.srm ]; then
  python3 tools/actionpotspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_password.srm ]; then
  python3 tools/awardspill.py build/shiren_en.gb \
    --ram saves/shiren_en_log_1_password.srm \
    --matrix --control build/_base_expanded.gb \
    --csv build/award_passwords.csv
fi
if [ -f saves/shiren_en_log_1_dragons_maw.srm ]; then
  python3 tools/dragonmawmarkerspill.py build/shiren_en.gb
  python3 tools/identityhiddenspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_talk_to_koppa.srm ] &&
   [ -f saves/shiren_en_log_1_dragons_maw.srm ] &&
   [ -f saves/shiren_en_log_1_fixed_width_save_info.srm ]; then
  python3 tools/savesummaryspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_rescue.srm ]; then
  python3 tools/rescuespill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_talk_to_koppa.srm ] &&
   [ -f saves/shiren_en_log_1_koppa_exit_pee.srm ]; then
  python3 tools/koppatalkspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_koppa_exit_pee.srm ] &&
   [ -f saves/shiren_en_log_1_koppa_exit_pee_v2.srm ] &&
   [ -f saves/shiren_en_rescue.srm ] &&
   [ -f saves/shiren_en_log_1_dragons_maw.srm ]; then
  python3 tools/koppastairspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_freeze_on_exit.srm ]; then
  python3 tools/rescueexitspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_orochi_symbol.srm ] ||
   [ -f saves/shiren_en_ranking_repaired.srm ]; then
  python3 tools/build.py build/_base_expanded.gb script/en.tsv \
          build/orochisymbolspill_native_control.gb \
          --dot-font --no-menuvwf
fi
if [ -f saves/shiren_en_ranking_repaired.srm ]; then
  python3 tools/build.py build/_base_expanded.gb script/en.tsv \
          build/rankvwf_control.gb --dot-font --no-rankvwf
  python3 tools/rankspill.py build/shiren_en.gb \
          --control build/rankvwf_control.gb \
          --native-control build/orochisymbolspill_native_control.gb
fi
if [ -f saves/shiren_en_log_1_orochi_symbol.srm ]; then
  python3 tools/orochisymbolspill.py build/shiren_en.gb \
          --native-control build/orochisymbolspill_native_control.gb
fi
if [ -f saves/shiren_en_log_1_trigger_ending.srm ]; then
  python3 tools/endingcreditspill.py build/shiren_en.gb
fi

# `build/_base_expanded.gb` is KEPT, not deleted. It is the input every diagnostic build
# needs -- `--redirect-all`, `--shuffle`, `--no-reloc`, the reference ROM for
# reloc_verify -- and the old script deleted it as `_e.gb` on the way out, so the checks
# HANDOFF_NEXT.md tells you to run had no input until you rebuilt it by hand. It is
# regenerable and gitignored; it just should not have to be regenerated by hand.

# pyboy reads cartridge RAM from <rom>.ram, so drop the battery save in beside the ROM.
# That is what lets tools/gbrun.py boot straight into a real file instead of a blank cart.
# This optional convenience save is personal and remains gitignored; copy a Mesen .srm
# there as saves/shiren_en.srm to boot it automatically.
if [ -f saves/shiren_en.srm ]; then
  cp -f saves/shiren_en.srm build/shiren_en.gb.ram
fi
