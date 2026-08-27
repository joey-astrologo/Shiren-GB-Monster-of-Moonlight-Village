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

# Whole-LCD blanking is a governed resource. Catalogue hardware LCDC mutations and the
# native $C110 shadow producers which VBlank later publishes. Keep separate caller-level
# worklists for the in-dungeon Item/Status system and the title Start system, and fail if
# a translation-added explicit bit-7 clear has no reviewed owner/policy.
python3 tools/lcdblankaudit.py build/base.gb build/shiren_en.gb \
        --tsv build/lcd_blank_audit.tsv \
        --item-menu-tsv build/lcd_blank_item_paths.tsv \
        --start-menu-tsv build/lcd_blank_start_paths.tsv

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
# `<var>` has route-specific runtime producers. Exact domains and exhaustive actor-role
# contracts are enforced while every unclassified dynamic line is regenerated as a
# complete human-review TSV.
python3 tools/varaudit.py
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
# source-raster silhouette stays intact through all fade shades. The title-card test
# verifies
# Joey's approved full 160x144 copyright mock-up plus the native palette/fade/scene-0
# path; the following
# test compares the later illustrated title pixel-for-pixel.
# The final test continues beyond the marker and proves the same New Log route still
# reaches a live, walkable village.
python3 tools/titlecardspill.py build/shiren_en.gb
python3 tools/titlelogospill.py build/shiren_en.gb \
  --ram saves/shiren_en096_broken_title_screen.srm
python3 tools/markerspill.py build/shiren_en.gb
python3 tools/newgamesmoke.py build/shiren_en.gb

# Curated route-specific SRAM regressions are tracked under tests/fixtures and staged at
# the legacy saves/ paths above. Machine-state routes remain conditional because PyBoy
# states are generated locally for the current ROM/WRAM layout. The fixtures enforce atomic item-page and
# Floor action/Info transitions (including Gitan's shorter action box), the proportional
# dungeon status fields and standing stair/trap command box, the Log-2 Path selector,
# title/file-menu transitions (including Erase Log 3 rebuilding
# Copy Log), cursed/plated/unidentified equipment-marker VWF, an exhaustive Items/Info
# textual-glyph pass, the Copy/Erase/New-Log and Floor Willow-Staff name-screen
# restores, the Ground box-5 VWF path, the Decoy Staff live-name producer, rescued-child
# nested dialogue entries and the one-HP death-result Rankings page. A fresh clone
# therefore runs every SRAM-backed route; generate
# town.state/dungeon.state with tools/fixtures.py to enable the remaining state routes.
if [ -f saves/town.state ]; then
  # Exact source cards plus all 50 live floor fields over every dungeon selector.
  python3 tools/floormarkerspill.py build/shiren_en.gb
fi
if [ -f saves/dungeon.state ]; then
  python3 tools/menuspill.py build/shiren_en.gb
  # Hostile 11-tile Item tails exercise the Action B parent reconstruction beyond
  # the ordinary real-save rows, whose covered right-hand cells happen to be empty.
  python3 tools/menuspill.py build/shiren_en.gb --long
  python3 tools/menuglyphspill.py build/shiren_en.gb
  python3 tools/equipmentmarkerspill.py build/shiren_en.gb
  python3 tools/fusioncountspill.py build/shiren_en.gb
  python3 tools/statusspill.py build/shiren_en.gb
  python3 tools/groundpopupspill.py build/shiren_en.gb
fi
# fusioncountspill covers seal counts 1-9 ($8C-$94). Zero seals is a tenth reachable count
# that emits $8B, and an unadmitted code rejects the WHOLE row to fixed width, so the
# visible damage is the item name rather than the mark. Needs its own real fused save.
if [ -f saves/shiren_en_log2_weapon_VWF_break.srm ]; then
  python3 tools/fusedzerospill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_item_menu.srm ]; then
  python3 tools/itempagespill.py build/shiren_en.gb
  # Repeat without a long idle gap. This catches queue/marker phase bugs that a fixed
  # 90-frame settle cannot expose; avoid only the native two-input right-wrap sentinel,
  # whose separate ownership path is covered by the ordinary run above.
  python3 tools/itempagespill.py build/shiren_en.gb --settle-frames 20 --no-wrap
  # Leave each real page independently. The outgoing Items screen must stay live until
  # the native Status publisher replaces it; all nine private-field uploads are bounded
  # to complete VBlanks and the persistent Window is immutable.
  python3 tools/itemexitspill.py build/shiren_en.gb
  # Reopen Items independently after leaving pages 1-4. Status -> Items must blank only
  # visible BG rows 0-15 in four VBlanks, commit both empty box perimeters before item
  # text, retain the bottom Window, and keep the next page change regional.
  python3 tools/itementryspill.py build/shiren_en.gb
  # Apply the real hidden-menu GameShark writes only after Menu -> Items has borrowed
  # its low font planes. Both category pages, all screen-28 item lists, and every
  # reachable screen-29 weapon enhancement value 0..99 must remain plane-exact VWF.
  python3 tools/debugmenuspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_item_menu_wood_arrow.srm ]; then
  # This save has four carried-item pages plus the special one-row standing-item Floor
  # page. Its retired rows must be structurally zero; B must return live to Status, while
  # Right/Left must rebuild complete five-row Item chrome before returning to page 1/4.
  python3 tools/floorpagespill.py build/shiren_en.gb
  # Repeat at the earliest input boundary exposed by the native screen-1 redraw return.
  # This crosses pages 1-4 and the Items/Floor shape boundary with only one idle frame,
  # catching mixed headers, swallowed ownership, LCD-off fallbacks and white frames.
  python3 tools/floorpagespill.py build/shiren_en.gb --rapid --settle-frames 1
  # The standing-item Floor page also owns a four-row Action overlay. B must restore
  # that exact one-row parent in one VBlank and return directly to responsive input.
  python3 tools/flooractionspill.py build/shiren_en.gb
  # Checkpoint 4: carried Item Info leaves with B, while the standing-item Floor Info
  # advances both pages and leaves its final page with A. Screen-4 descriptions and
  # screen-5 equipment-seal pages preserve box chrome and the Window, restore the exact
  # parent, and keep LCDC.7 set. A local dungeon state adds the five-page Fusion Pot audit.
  if [ -f saves/shiren_en_log_1_shield_VWF.srm ] && \
     [ -f saves/shiren_en_log_1_dragons_maw.srm ]; then
    python3 tools/iteminfospill.py build/shiren_en.gb
  fi
  # Audit the regional screen-20 lifecycle with both its original Wood Arrow route and
  # a six-row/five-page Fusion Pot route. Entry retains complete Action chrome until
  # Info chrome plus row zero; paging keeps at least one whole old/new row visible.
  # Neither direction may disable the LCD or retain old Action tail/footer pixels.
  python3 tools/floorinfospill.py build/shiren_en.gb
  python3 tools/floorinfospill.py build/shiren_en.gb --fusion
  python3 tools/floorinfospill.py build/shiren_en.gb --seal
  # Reproduce mesen_spawn_fusion_kit.lua exactly, first isolating the injected bytes and
  # then visiting the carried Fusion Pot Action before screen-20 Floor Info. A
  # gameplay-bound Action used to leave its private-pool admission at one and
  # incorrectly force this later route to LCD-off.
  python3 tools/floorinfospill.py build/shiren_en.gb --fusion-kit
  python3 tools/floorinfospill.py build/shiren_en.gb --fusion-kit-history
fi
if [ -f saves/shiren_en_log2_storage_pot_menu.srm ]; then
  python3 tools/storagepotinfospill.py build/shiren_en.gb
  # The no-Lua Storage Pot path reaches screen 13 above screen-20 Floor. Entry must keep
  # LCDC enabled and publish empty Pot chrome before text. Its B return must publish the
  # complete six-row parent before labels, suppress the transient underlying Floor-page
  # indicator, and settle byte-exactly.
  python3 tools/groundpotreturnspill.py build/shiren_en.gb --screen20
  python3 tools/groundpotreturnspill.py build/shiren_en.gb --items-first
  python3 tools/groundpotreturnspill.py build/shiren_en.gb --screen20 --items-first
  # Closing the menu is a NATIVE LCD-off reload of $9000-$97FF from menu font back to
  # terrain. A V4F publication that re-enables the LCD inside it exposes one frame of
  # dungeon map drawn through menu glyphs. That is what a transaction state sharing
  # propvwf's $C0D7 scratch did after every dungeon message.
  python3 tools/potputspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log2_scroll_menu.srm ]; then
  python3 tools/scrollinfospill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log2_gitan_menu_boarder.srm ]; then
  python3 tools/gitanmenuborderspill.py build/shiren_en.gb
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
if [ -f saves/shiren_en_log2_walk_left.srm ]; then
  python3 tools/keyakigiftspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_path_select.srm ]; then
  python3 tools/pathspill.py build/shiren_en.gb
  python3 tools/mainmenuspill.py build/shiren_en.gb
  python3 tools/nameflowspill.py build/shiren_en.gb \
          --ram saves/shiren_en_path_select.srm
fi
if [ -f saves/shiren_log3_unidentified_naming.srm ]; then
  python3 tools/unidentifiednamespill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_menu.srm ] &&
   [ -f saves/shiren_en_ranking_repaired.srm ]; then
  # The standing Trap/Stairs popup and Rank/Pass are both six cells wide. Exercise
  # their complete classifiers together so one cannot steal the other's VWF route.
  python3 tools/startspill.py build/shiren_en.gb \
          --ram saves/shiren_en_menu.srm \
          --wide-ram saves/shiren_en_ranking_repaired.srm
fi
if [ -f saves/shiren_en_fays_puzzles.srm ]; then
  python3 tools/faypathspill.py build/shiren_en.gb
  python3 tools/orochipopupspill.py build/shiren_en.gb
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
  python3 tools/potseespill.py build/shiren_en.gb \
    --ram saves/shiren_en_log2_storage_pot_menu.srm
fi
if [ -f saves/shiren_en_log_2_action_pots.srm ]; then
  python3 tools/actionpotspill.py build/shiren_en.gb
  # Carried Pot See -> Items is a two-level pop from screen 12 or 13. Keep the viewer live until
  # complete empty Items windows are committed, then reveal restored rows. Repeat on
  # a full page-4 inventory and require the settled Items title raster to be identical.
  python3 tools/potreturnspill.py build/shiren_en.gb
  python3 tools/potreturnspill.py build/shiren_en.gb --full-page
  # The five-row Egg/Egg/Happy/Fusion/Manji mix rejects the private Action tile pool,
  # so screen 12 legitimately reaches See with a zero admission latch. Keep this exact
  # route in the release battery; it exposed the old LCD-off and `Potms` return.
  python3 tools/potreturnspill.py build/shiren_en.gb --exact-five
fi
# Queued message fragments are composed by native code with substitutions pushed between
# them, so an authored <br> is not part of that ABI. One in the Fluffy Bunny heal line --
# the only one among all 179 fragments in the ROM -- garbled the line, blanked the box and
# fired unrelated actor behaviour. Static: floor actors are not serializable to a fixture.
python3 tools/healfragmentspill.py build/_base_expanded.gb
# The only seven-row Floor action box. Freeze proportional coverage plus the independent
# screen-7 Info lifecycle: no whole-LCD blank, armed 4 -> 0 -> 7 replay, chrome before
# text, exact returned BG/Window pixels, and responsive final state.
if [ -f saves/shiren_en_log3_unidentified_pot_crash.srm ]; then
  python3 tools/unidentifiedpotspill.py build/shiren_en.gb
  # The same Pot reached through Items is a different native parent: screen 1 pushes
  # screen 2, whose protected Action pool has six slices. Freeze the seventh Info row's
  # collision-safe ordinary allocation so it cannot fall back to corrupt raw tiles.
  python3 tools/unidentifiedflooractionspill.py build/shiren_en.gb
  python3 tools/unidentifiedflooractionspill.py build/shiren_en.gb --path info
  # The same no-Lua save reaches ground-Pot screen 12 above the alternate screen-7
  # picker. Entry keeps LCDC enabled and publishes empty Pot chrome before text. B is a
  # one-level 0,7,12 pop: suppress only disposable screen 0, publish complete parent
  # chrome before labels, and restore exact pixels.
  python3 tools/groundpotreturnspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_password.srm ]; then
  python3 tools/awardspill.py build/shiren_en.gb \
    --ram saves/shiren_en_log_1_password.srm \
    --matrix --control build/_base_expanded.gb \
    --csv build/award_passwords.csv
fi
if [ -f saves/shiren_en_logs_passwords.srm ]; then
  python3 tools/awardspill.py build/shiren_en.gb \
    --ram saves/shiren_en_logs_passwords.srm --multi-log
fi
if [ -f saves/shiren_en_log_1_dragons_maw.srm ]; then
  python3 tools/dragonmawmarkerspill.py build/shiren_en.gb
  python3 tools/identityhiddenspill.py build/shiren_en.gb
  # Held Items -> Action -> B is one ownership unit across pages 1-4. The real save
  # supplies Equip/Remove plus four-, five-, and six-row pickers; every run proves the
  # parent restore returns directly to Item input, with no Status/Items replay, while
  # keeping the bottom Window and all pixels outside box 6 live.
  python3 tools/actionmenuspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log1_player_named_items.srm ]; then
  python3 tools/playernamedspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log3_shop.srm ] &&
   [ -f saves/shiren_en_log3_invincible_herb_price.srm ]; then
  python3 tools/shopspill.py build/shiren_en.gb
fi
if [ -f saves/shiren_en_log_1_talk_to_koppa.srm ] &&
   [ -f saves/shiren_en_log_1_dragons_maw.srm ] &&
   [ -f saves/shiren_en_log_1_fixed_width_save_info.srm ] &&
   [ -f saves/shiren_en_log1_moonlight_exit.srm ]; then
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
   [ -f saves/shiren_en_ranking_repaired.srm ] ||
   [ -f saves/shiren_en_log2_about_to_die.srm ]; then
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
if [ -f saves/shiren_en_log2_about_to_die.srm ]; then
  python3 tools/deathrankspill.py build/shiren_en.gb \
          --native-control build/orochisymbolspill_native_control.gb
fi
if [ -f saves/shiren_en_log_1_orochi_symbol.srm ]; then
  python3 tools/orochisymbolspill.py build/shiren_en.gb \
          --native-control build/orochisymbolspill_native_control.gb
fi
if [ -f saves/shiren_en_log_1_trigger_ending.srm ]; then
  python3 tools/endingcreditspill.py build/shiren_en.gb
  python3 tools/normalendspill.py build/shiren_en.gb
fi

# `build/_base_expanded.gb` is KEPT, not deleted. It is the input every diagnostic build
# needs -- `--redirect-all`, `--shuffle`, `--no-reloc`, the reference ROM for
# reloc_verify -- and the old script deleted it as `_e.gb` on the way out, so the checks
# `docs/ENGINEERING_RULES.md` tells you to run had no input until you rebuilt it by hand. It is
# regenerable and gitignored; it just should not have to be regenerated by hand.

# pyboy reads cartridge RAM from <rom>.ram, so drop the battery save in beside the ROM.
# That is what lets tools/gbrun.py boot straight into a real file instead of a blank cart.
# This optional convenience save is personal and remains gitignored; copy a Mesen .srm
# there as saves/shiren_en.srm to boot it automatically.
if [ -f saves/shiren_en.srm ]; then
  cp -f saves/shiren_en.srm build/shiren_en.gb.ram
fi
